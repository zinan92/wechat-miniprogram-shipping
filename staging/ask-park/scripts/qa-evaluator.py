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
PACKET_KEYS = {"worker_identity", "evaluator_identity", "fresh_context", "read_only", "candidate_sha_before", "candidate_sha_after", "worktree_sha_before", "worktree_sha_after", "bounded_inputs", "exclusions", "verdict", "findings", "advisory_earliest_layer", "automation_passed", "human_gate_required", "human_gate_ref", "issue_contract_id", "attempt", "limitations"}
PRIVATE_PARTS = ("secret", "token", "password", "openid", "credential", "private_key", "api_key", "cookie", "next_module", "current_module")


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


def _walk_safe(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(part in str(key).lower().replace("-", "_") for part in PRIVATE_PARTS):
                return False
            if not _walk_safe(child):
                return False
    elif isinstance(value, list):
        return all(_walk_safe(child) for child in value)
    elif isinstance(value, str) and value.startswith(("http://", "https://", "file://", "/Users/", "/private/", "~/")):
        return False
    return True


def validate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a fresh-context, read-only evaluator packet without routing."""

    if not isinstance(packet, Mapping):
        _fail("QA_PACKET_TYPE", "evaluator packet must be an object", "packet")
    if any(key not in PACKET_KEYS for key in packet):
        _fail("QA_PACKET_UNKNOWN_FIELD", "evaluator packet contains an undeclared field", "packet.<key>")
    if not _walk_safe(packet):
        _fail("QA_PACKET_PRIVATE_FIELD", "evaluator packet contains private or routing data", "packet")
    required = ("worker_identity", "evaluator_identity", "fresh_context", "read_only", "candidate_sha_before", "candidate_sha_after", "worktree_sha_before", "worktree_sha_after", "bounded_inputs", "exclusions", "verdict", "findings", "advisory_earliest_layer", "automation_passed", "human_gate_required", "limitations", "issue_contract_id", "attempt")
    for key in required:
        if key not in packet:
            _fail("QA_PACKET_REQUIRED", "evaluator packet field is required", f"packet.{key}")
    if not _alias(packet["worker_identity"]) or not _alias(packet["evaluator_identity"]):
        _fail("QA_IDENTITY_INVALID", "worker and evaluator identities must be aliases", "packet.identity")
    if packet["worker_identity"] == packet["evaluator_identity"]:
        _fail("QA_EVALUATOR_NOT_INDEPENDENT", "worker and evaluator identities must differ", "packet.identity")
    if packet["fresh_context"] is not True or packet["read_only"] is not True:
        _fail("QA_INDEPENDENCE_REQUIRED", "fresh context and read-only mode are required", "packet")
    if not _digest(packet["candidate_sha_before"]) or not _digest(packet["candidate_sha_after"]) or not _digest(packet["worktree_sha_before"]) or not _digest(packet["worktree_sha_after"]):
        _fail("QA_CANDIDATE_IDENTITY", "candidate before/after values must be full digests", "packet.candidate_sha")
    if packet["candidate_sha_before"] != packet["candidate_sha_after"] or packet["worktree_sha_before"] != packet["worktree_sha_after"]:
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
    if not isinstance(packet["automation_passed"], bool):
        _fail("QA_AUTOMATION_FLAG", "automation_passed must be boolean", "packet.automation_passed")
    if packet["verdict"] == "QA_PASS" and packet["automation_passed"] is not True:
        _fail("QA_PASS_AUTOMATION", "QA_PASS requires automation passed", "packet.automation_passed")
    if packet["verdict"] == "QA_BLOCKED" and packet["automation_passed"] is not True:
        _fail("QA_BLOCKED_AUTOMATION", "QA_BLOCKED requires automation passed", "packet.automation_passed")
    if packet["verdict"] == "QA_BLOCKED" and packet["human_gate_required"] is not True:
        _fail("QA_BLOCKED_GATE", "QA_BLOCKED requires a human gate", "packet.human_gate_required")
    if packet["verdict"] == "QA_BLOCKED" and not _alias(packet.get("human_gate_ref")):
        _fail("QA_BLOCKED_GATE", "QA_BLOCKED requires a named human gate reference", "packet.human_gate_ref")
    if not isinstance(packet.get("limitations"), list) or not packet["limitations"]:
        _fail("QA_LIMITATIONS_REQUIRED", "evaluator packet requires limitations", "packet.limitations")
    return copy.deepcopy(dict(packet))


def start_attempt(*, worker_identity: str, evaluator_identity: str, candidate_sha: str, issue_contract_id: str, attempt: int = 1) -> dict[str, Any]:
    if not _digest(candidate_sha):
        _fail("QA_CANDIDATE_IDENTITY", "candidate SHA must be a full digest", "candidate_sha")
    if not _alias(issue_contract_id):
        _fail("QA_ISSUE_INVALID", "issue contract must be an alias", "issue_contract_id")
    if not isinstance(attempt, int) or attempt < 1 or attempt > 3:
        _fail("QA_ATTEMPT_INVALID", "attempt must be 1..3", "attempt")
    packet = {
        "worker_identity": worker_identity,
        "evaluator_identity": evaluator_identity,
        "fresh_context": True,
        "read_only": True,
        "candidate_sha_before": candidate_sha,
        "candidate_sha_after": candidate_sha,
        "worktree_sha_before": candidate_sha,
        "worktree_sha_after": candidate_sha,
        "bounded_inputs": [issue_contract_id],
        "exclusions": ["live-provider", "credentials", "private-data"],
        "verdict": "QA_PASS",
        "findings": [],
        "advisory_earliest_layer": None,
        "automation_passed": True,
        "human_gate_required": False,
        "limitations": ["Evaluator has not yet completed a verdict."],
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
    running_packet = current.get("packet")
    for key in ("worker_identity", "evaluator_identity", "candidate_sha_before", "candidate_sha_after", "worktree_sha_before", "worktree_sha_after", "issue_contract_id", "attempt"):
        if not isinstance(running_packet, Mapping) or checked.get(key) != running_packet.get(key):
            _fail("QA_PACKET_STATE_MISMATCH", "packet does not match the running attempt", f"packet.{key}")
    current["execution_state"] = "complete"
    current["result"] = checked["verdict"]
    current["control_outcome"] = "needs-park-decision" if checked["verdict"] == "QA_FAIL" and attempt == 3 else "none"
    current["packet"] = checked
    return current


def repair_attempt(state: Mapping[str, Any], *, candidate_sha: str, same_contract: bool, prior_result: str = "none") -> dict[str, Any]:
    if not _digest(candidate_sha):
        _fail("QA_CANDIDATE_IDENTITY", "candidate SHA must be a full digest", "candidate_sha")
    current = copy.deepcopy(dict(state))
    if same_contract and candidate_sha == current.get("candidate_sha"):
        _fail("QA_CANDIDATE_NOT_NEW", "same-contract repair requires a new candidate digest", "candidate_sha")
    if not same_contract or prior_result in {"QA_PASS", "QA_BLOCKED"}:
        attempt = 1
    else:
        attempt = int(current.get("attempt", 0)) + 1
    if attempt > 3:
        _fail("QA_THIRD_FAILURE_ESCALATION", "a fourth blind repair is not allowed", "attempt")
    current.update({"execution_state": "ready", "result": "none", "control_outcome": "none", "attempt": attempt})
    current["candidate_sha"] = candidate_sha
    if isinstance(current.get("packet"), dict):
        current["packet"].update({
            "candidate_sha_before": candidate_sha,
            "candidate_sha_after": candidate_sha,
            "worktree_sha_before": candidate_sha,
            "worktree_sha_after": candidate_sha,
            "attempt": attempt,
        })
    return current


def prerequisite_missing(*, origin_module: str, gate: str = "qa-1") -> dict[str, Any]:
    if origin_module not in LAYERS or gate not in {"contract", "qa-1", "target", "qa-2", "evidence", "final"}:
        _fail("QA_PREREQUISITE_INPUT", "origin module or gate is invalid", "prerequisite_missing")
    return {"schema_version": 1, "kind": "qa-state", "qa": {"execution_state": "unavailable", "result": "none", "control_outcome": "qa-prerequisite-missing", "gate": gate, "candidate_manifest_digest": None, "target_manifest_digest": None, "attempt": 1, "max_attempts": 3, "origin_module": origin_module, "result_receipt_id": None}}
