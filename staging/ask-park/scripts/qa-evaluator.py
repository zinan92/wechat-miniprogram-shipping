#!/usr/bin/env python3
"""Pure S11 independent evaluator packet and bounded attempt transitions."""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
LAYERS = {"plan", "build", "cloudbase", "experience", "device", "release"}
VERDICTS = {"QA_PASS", "QA_FAIL", "QA_BLOCKED"}


class EvaluatorError(ValueError):
    def __init__(self, code: str, message: str, path: str = "qa-evaluator") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "qa-evaluator") -> None:
    raise EvaluatorError(code, message, path)


def _alias(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def validate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a fresh-context, read-only evaluator packet without routing."""

    if not isinstance(packet, Mapping):
        _fail("QA_PACKET_TYPE", "evaluator packet must be an object", "packet")
    required = ("worker_identity", "evaluator_identity", "fresh_context", "read_only", "candidate_sha_before", "candidate_sha_after", "bounded_inputs", "exclusions", "verdict", "findings", "advisory_earliest_layer", "automation_passed", "human_gate_required")
    for key in required:
        if key not in packet:
            _fail("QA_PACKET_REQUIRED", "evaluator packet field is required", f"packet.{key}")
    if not _alias(packet["worker_identity"]) or not _alias(packet["evaluator_identity"]):
        _fail("QA_IDENTITY_INVALID", "worker and evaluator identities must be aliases", "packet.identity")
    if packet["worker_identity"] == packet["evaluator_identity"]:
        _fail("QA_EVALUATOR_NOT_INDEPENDENT", "worker and evaluator identities must differ", "packet.identity")
    if packet["fresh_context"] is not True or packet["read_only"] is not True:
        _fail("QA_INDEPENDENCE_REQUIRED", "fresh context and read-only mode are required", "packet")
    if not _digest(packet["candidate_sha_before"]) or not _digest(packet["candidate_sha_after"]):
        _fail("QA_CANDIDATE_IDENTITY", "candidate before/after values must be full digests", "packet.candidate_sha")
    if packet["candidate_sha_before"] != packet["candidate_sha_after"]:
        _fail("QA_CANDIDATE_EDITED", "evaluator packet observes a candidate edit", "packet.candidate_sha_after")
    if not isinstance(packet["bounded_inputs"], list) or not packet["bounded_inputs"] or not all(_alias(item) for item in packet["bounded_inputs"]):
        _fail("QA_BOUNDED_INPUTS", "bounded inputs must be non-empty aliases", "packet.bounded_inputs")
    if not isinstance(packet["exclusions"], list) or not packet["exclusions"]:
        _fail("QA_EXCLUSIONS_REQUIRED", "bounded exclusions are required", "packet.exclusions")
    if packet["verdict"] not in VERDICTS:
        _fail("QA_VERDICT_INVALID", "verdict is outside the evaluator enum", "packet.verdict")
    if packet["advisory_earliest_layer"] is not None and packet["advisory_earliest_layer"] not in LAYERS:
        _fail("QA_LAYER_INVALID", "advisory layer is not sequential", "packet.advisory_earliest_layer")
    if not isinstance(packet["findings"], list):
        _fail("QA_FINDINGS_INVALID", "findings must be a list", "packet.findings")
    if packet["verdict"] == "QA_PASS" and packet["findings"]:
        _fail("QA_PASS_FINDINGS", "QA_PASS cannot carry unresolved findings", "packet.findings")
    if packet["verdict"] == "QA_FAIL" and not packet["findings"]:
        _fail("QA_FAIL_FINDINGS", "QA_FAIL requires observable findings", "packet.findings")
    if packet["verdict"] == "QA_BLOCKED" and packet["automation_passed"] is not True:
        _fail("QA_BLOCKED_AUTOMATION", "QA_BLOCKED requires automation passed", "packet.automation_passed")
    if packet["verdict"] == "QA_BLOCKED" and packet["human_gate_required"] is not True:
        _fail("QA_BLOCKED_GATE", "QA_BLOCKED requires a human gate", "packet.human_gate_required")
    return copy.deepcopy(dict(packet))


def start_attempt(*, worker_identity: str, evaluator_identity: str, candidate_sha: str, issue_contract_id: str, attempt: int = 1) -> dict[str, Any]:
    if not _digest(candidate_sha):
        _fail("QA_CANDIDATE_IDENTITY", "candidate SHA must be a full digest", "candidate_sha")
    if not _alias(issue_contract_id):
        _fail("QA_ISSUE_INVALID", "issue contract must be an alias", "issue_contract_id")
    packet = {
        "worker_identity": worker_identity,
        "evaluator_identity": evaluator_identity,
        "fresh_context": True,
        "read_only": True,
        "candidate_sha_before": candidate_sha,
        "candidate_sha_after": candidate_sha,
        "bounded_inputs": [issue_contract_id],
        "exclusions": ["live-provider", "credentials", "private-data"],
        "verdict": "QA_PASS",
        "findings": [],
        "advisory_earliest_layer": None,
        "automation_passed": False,
        "human_gate_required": False,
        "issue_contract_id": issue_contract_id,
        "attempt": attempt,
    }
    return {"execution_state": "running", "result": "none", "control_outcome": "none", "attempt": attempt, "max_attempts": 3, "packet": packet}


def complete_attempt(state: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(dict(state))
    checked = validate_packet(packet)
    attempt = current.get("attempt")
    if current.get("execution_state") != "running" or not isinstance(attempt, int) or attempt < 1 or attempt > 3:
        _fail("QA_ATTEMPT_STATE", "only a running attempt 1..3 can complete", "state")
    current["execution_state"] = "complete"
    current["result"] = checked["verdict"]
    current["control_outcome"] = "needs-park-decision" if checked["verdict"] == "QA_FAIL" and attempt == 3 else "none"
    current["packet"] = checked
    return current


def repair_attempt(state: Mapping[str, Any], *, candidate_sha: str, same_contract: bool, prior_result: str = "none") -> dict[str, Any]:
    if not _digest(candidate_sha):
        _fail("QA_CANDIDATE_IDENTITY", "candidate SHA must be a full digest", "candidate_sha")
    current = copy.deepcopy(dict(state))
    if not same_contract or prior_result in {"QA_PASS", "QA_BLOCKED"}:
        attempt = 1
    else:
        attempt = int(current.get("attempt", 0)) + 1
    if attempt > 3:
        _fail("QA_THIRD_FAILURE_ESCALATION", "a fourth blind repair is not allowed", "attempt")
    current.update({"execution_state": "ready", "result": "none", "control_outcome": "none", "attempt": attempt})
    current["candidate_sha"] = candidate_sha
    return current
