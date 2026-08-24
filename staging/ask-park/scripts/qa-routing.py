#!/usr/bin/env python3
"""Ask Park-owned integration for QA findings, Diagnose, and repair routing.

S10–S13 QA components are read-only evidence producers. This module is the
single integration owner that may prepare a human gate, activate Diagnose, or
pass a confirmed causal invalidation proposal to the S01B lifecycle engine.
It never lets a QA packet choose ``current_module`` or promote a module.
"""

from __future__ import annotations

import copy
import importlib.util
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


_ROOT = Path(__file__).parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging failure
        raise ImportError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LIFECYCLE = _load_module("ask_park_lifecycle_for_qa_routing", _ROOT / "state-lifecycle.py")
_ROUTER = _load_module("ask_park_router_for_qa_routing", _ROOT / "router.py")
_EVALUATOR = _load_module("ask_park_evaluator_for_qa_routing", _ROOT / "qa-evaluator.py")

MODULES = tuple(_LIFECYCLE.MODULES)
LAYERS = set(MODULES)
DEPENDENCIES = (
    "s02-router",
    "s04-diagnose",
    "s09-release",
    "s10-qa-schema",
    "s11-qa-evaluator",
    "s12-browser-qa",
    "s13-devtools-qa",
)
VERDICTS = {"QA_PASS", "QA_FAIL", "QA_BLOCKED"}
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PRIVATE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "openid",
    "credential",
    "private_key",
    "api_key",
    "cookie",
    "next_module",
    "current_module",
    "route_to",
    "routing",
)
PRIVATE_PREFIXES = ("http://", "https://", "file://", "cloud://", "/Users/", "/private/", "~/")
DIAGNOSIS_KEYS = {
    "incident_id",
    "confirmed",
    "interrupted_module",
    "recovery_goal",
    "earliest_module",
    "changed_fields",
    "reason_code",
}
GATE_REQUEST_KEYS = {"action_type", "action_scope", "authorizing_role", "requested_at", "evidence_ref"}


class QARoutingError(ValueError):
    """Stable, value-safe integration rejection."""

    def __init__(self, code: str, message: str, path: str = "qa-routing") -> None:
        self.code = code
        self.error_code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "qa-routing") -> None:
    raise QARoutingError(code, message, path)


def _alias(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _safe(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in PRIVATE_KEY_PARTS):
                return False
            if not _safe(child):
                return False
    elif isinstance(value, list):
        return all(_safe(child) for child in value)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(prefix in lowered for prefix in ("http://", "https://", "file://", "cloud://")):
            return False
        if any(marker in lowered for marker in ("next_module", "current_module", "route_to")):
            return False
        if any(value.startswith(prefix) for prefix in PRIVATE_PREFIXES[3:]):
            return False
    return True


def _state(state: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return _LIFECYCLE._validate_state(state)
    except _LIFECYCLE.LifecycleError as exc:
        _fail("QA_ROUTING_STATE_INVALID", "state does not satisfy the lifecycle contract", "state")
    raise AssertionError("unreachable")  # pragma: no cover


def _packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    try:
        checked = _EVALUATOR.validate_packet(packet)
    except _EVALUATOR.EvaluatorError as exc:
        _fail("QA_PACKET_INVALID", "QA packet does not satisfy the independent evaluator contract", "packet")
    if checked["verdict"] not in VERDICTS:
        _fail("QA_VERDICT_INVALID", "QA verdict is outside the integration enum", "packet.verdict")
    return checked


def advisory_from_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the only durable authority a QA packet may emit: an advisory."""

    checked = _packet(packet)
    return {
        "verdict": checked["verdict"],
        "findings": copy.deepcopy(checked["findings"]),
        "advisory_earliest_layer": checked["advisory_earliest_layer"],
        "automation_passed": checked["automation_passed"],
        "human_gate_required": checked["human_gate_required"],
        "attempt": checked["attempt"],
        "issue_contract_id": checked["issue_contract_id"],
        "evaluator_identity": checked["evaluator_identity"],
        "read_only": True,
    }


def _diagnosis(diagnosis: Mapping[str, Any], *, current_module: str) -> dict[str, Any]:
    if not isinstance(diagnosis, Mapping) or any(key not in DIAGNOSIS_KEYS for key in diagnosis):
        _fail("QA_DIAGNOSIS_INVALID", "diagnosis must use the bounded causal proposal shape", "diagnosis")
    if not _safe(diagnosis):
        _fail("QA_DIAGNOSIS_PRIVATE", "diagnosis contains private or routing data", "diagnosis")
    required = {"incident_id", "confirmed", "interrupted_module", "recovery_goal", "earliest_module", "changed_fields", "reason_code"}
    if set(diagnosis) != required:
        _fail("QA_DIAGNOSIS_REQUIRED", "diagnosis must contain every causal proposal field", "diagnosis")
    if not _alias(diagnosis["incident_id"]):
        _fail("QA_DIAGNOSIS_ID", "incident_id must be a stable alias", "diagnosis.incident_id")
    if not isinstance(diagnosis["confirmed"], bool):
        _fail("QA_DIAGNOSIS_CONFIRMED", "confirmed must be boolean", "diagnosis.confirmed")
    if diagnosis["interrupted_module"] not in MODULES or diagnosis["interrupted_module"] != current_module:
        _fail("QA_DIAGNOSE_MODULE_MISMATCH", "diagnosis must preserve the interrupted current module", "diagnosis.interrupted_module")
    if not isinstance(diagnosis["recovery_goal"], str) or not diagnosis["recovery_goal"].strip() or "\n" in diagnosis["recovery_goal"]:
        _fail("QA_DIAGNOSIS_GOAL_REQUIRED", "recovery_goal must be bounded non-empty text", "diagnosis.recovery_goal")
    if not isinstance(diagnosis["changed_fields"], list) or any(not _alias(item) for item in diagnosis["changed_fields"]):
        _fail("QA_DIAGNOSIS_FIELDS", "changed_fields must be safe aliases", "diagnosis.changed_fields")
    if diagnosis["confirmed"]:
        earliest = diagnosis["earliest_module"]
        if earliest not in MODULES or MODULES.index(earliest) > MODULES.index(current_module):
            _fail("QA_DIAGNOSIS_EARLIEST", "confirmed causal repair must rewind to an earlier or equal module", "diagnosis.earliest_module")
        if not diagnosis["changed_fields"] or not _alias(diagnosis["reason_code"]):
            _fail("QA_DIAGNOSIS_CAUSAL_FIELDS", "confirmed diagnosis requires changed fields and a reason code", "diagnosis")
    else:
        if diagnosis["earliest_module"] is not None or diagnosis["changed_fields"] or diagnosis["reason_code"] is not None:
            _fail("QA_DIAGNOSIS_DEVICE_ONLY", "unconfirmed device-only diagnosis cannot carry causal invalidation", "diagnosis")
    return copy.deepcopy(dict(diagnosis))


def _decision(decision: Any) -> dict[str, Any]:
    return decision.as_dict()


def request_human_gate(
    state: Mapping[str, Any], packet: Mapping[str, Any], *, gate_request: Mapping[str, Any]
) -> dict[str, Any]:
    """Prepare a human gate for QA_BLOCKED without activating Diagnose."""

    checked_state = _state(state)
    checked_packet = _packet(packet)
    if checked_state["diagnose"]["state"] == "active":
        _fail("QA_HUMAN_GATE_DIAGNOSE_ACTIVE", "a human-only gate cannot bypass an active Diagnose overlay", "state.diagnose")
    if checked_packet["verdict"] != "QA_BLOCKED" or checked_packet["automation_passed"] is not True or checked_packet["human_gate_required"] is not True:
        _fail("QA_HUMAN_GATE_NOT_ALLOWED", "only an automated-pass QA_BLOCKED packet may request a human gate", "packet")
    if checked_packet["findings"]:
        _fail("QA_HUMAN_GATE_DEFECT", "a human gate cannot hide automatable findings", "packet.findings")
    if not isinstance(gate_request, Mapping) or set(gate_request) != GATE_REQUEST_KEYS or not _safe(gate_request):
        _fail("QA_HUMAN_GATE_REQUEST", "gate request must be a complete redacted action envelope", "gate_request")
    try:
        prepared = _LIFECYCLE.prepare_human_gate(checked_state["human_gate"], **dict(gate_request))
        prepared = _LIFECYCLE.transition_human_gate(prepared, "awaiting-human")
    except _LIFECYCLE.LifecycleError:
        _fail("QA_HUMAN_GATE_INVALID", "human gate request failed the S01 contract", "gate_request")
    next_state = copy.deepcopy(checked_state)
    next_state["human_gate"] = prepared
    next_state["control_outcome"] = "blocked-external"
    next_state = _state(next_state)
    decision = _ROUTER.route(next_state, "continuation", authority_required=True)
    return {
        "route_kind": "human-gate",
        "state": next_state,
        "advisory": advisory_from_packet(checked_packet),
        "decision": _decision(decision),
        "diagnose_activated": False,
        "invalidated_receipt_ids": [],
        "control_outcome": "blocked-external",
    }


def route_qa_result(
    state: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    diagnosis: Mapping[str, Any] | None = None,
    receipts: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
    gate_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Let Ask Park consume one independent QA result and choose the route.

    QA_PASS is advisory and does not promote state. QA_BLOCKED prepares a
    human gate. QA_FAIL is inert until Diagnose supplies a bounded causal
    proposal; only then does Ask Park invalidate receipts and activate the
    Diagnose overlay.
    """

    checked_state = _state(state)
    checked_packet = _packet(packet)
    advisory = advisory_from_packet(checked_packet)
    verdict = checked_packet["verdict"]
    if verdict == "QA_PASS":
        decision = _ROUTER.route(checked_state, "continuation")
        return {
            "route_kind": "qa-pass-advisory",
            "state": checked_state,
            "advisory": advisory,
            "decision": _decision(decision),
            "diagnose_activated": False,
            "invalidated_receipt_ids": [],
            "control_outcome": decision.control_outcome,
        }
    if verdict == "QA_BLOCKED":
        if diagnosis is not None:
            _fail("QA_BLOCKED_DIAGNOSE", "QA_BLOCKED human evidence must not activate Diagnose", "diagnosis")
        if gate_request is None:
            _fail("QA_HUMAN_GATE_REQUIRED", "QA_BLOCKED requires an explicit gate_request", "gate_request")
        return request_human_gate(checked_state, checked_packet, gate_request=gate_request)
    if diagnosis is None:
        _fail("QA_DIAGNOSIS_REQUIRED", "QA_FAIL findings are advisory until Diagnose confirms the cause", "diagnosis")
    if checked_state["diagnose"]["state"] == "active":
        _fail("QA_DIAGNOSE_ALREADY_ACTIVE", "Ask Park cannot start a second Diagnose overlay", "state.diagnose")
    proposal = _diagnosis(diagnosis, current_module=checked_state["current_module"])
    invalidated_ids: list[str] = []
    rewound_state = checked_state
    receipt_input = receipts
    if receipts is not None and not isinstance(receipts, Mapping):
        receipt_input = list(receipts)
    if proposal["confirmed"]:
        if receipt_input is None or (isinstance(receipt_input, Mapping) and not receipt_input) or (not isinstance(receipt_input, Mapping) and not receipt_input):
            _fail("QA_CAUSAL_RECEIPTS_REQUIRED", "confirmed diagnosis requires the raw receipt chain", "receipts")
        try:
            rewound_state, invalidation = _LIFECYCLE.invalidate_state(
                checked_state,
                receipt_input,
                changed_fields=proposal["changed_fields"],
                reason_code=proposal["reason_code"],
            )
        except _LIFECYCLE.LifecycleError:
            _fail("QA_CAUSAL_INVALIDATION", "Ask Park could not validate the causal invalidation proposal", "diagnosis")
        if invalidation.earliest_invalidated_module != proposal["earliest_module"]:
            _fail("QA_CAUSAL_PROPOSAL_MISMATCH", "Diagnose earliest module does not match the receipt closure", "diagnosis.earliest_module")
        invalidated_ids = list(invalidation.invalidated_receipt_ids)
    elif receipt_input is not None:
        if (isinstance(receipt_input, Mapping) and receipt_input) or (not isinstance(receipt_input, Mapping) and receipt_input):
            _fail("QA_DEVICE_ONLY_RECEIPTS", "device-only diagnosis cannot invalidate receipts", "receipts")
    recovery_module = rewound_state["current_module"]
    try:
        diagnosed_state = _LIFECYCLE.activate_diagnose(rewound_state, recovery_module, proposal["recovery_goal"])
    except _LIFECYCLE.LifecycleError:
        _fail("QA_DIAGNOSE_ACTIVATION", "Ask Park could not activate Diagnose on the recovery module", "state.diagnose")
    decision = _ROUTER.route(diagnosed_state, "failure", failure_module=recovery_module)
    incident = {
        "incident_id": proposal["incident_id"],
        "interrupted_module": proposal["interrupted_module"],
        "recovery_module": recovery_module,
        "post_recovery_current_module": recovery_module,
        "recovery_goal": proposal["recovery_goal"],
        "causal_confirmed": proposal["confirmed"],
        "earliest_invalidated_module": proposal["earliest_module"],
    }
    return {
        "route_kind": "diagnose",
        "state": diagnosed_state,
        "advisory": advisory,
        "decision": _decision(decision),
        "incident": incident,
        "diagnose_activated": True,
        "invalidated_receipt_ids": invalidated_ids,
        "control_outcome": None,
    }


def start_qa_attempt(**kwargs: Any) -> dict[str, Any]:
    """Delegate bounded attempt creation to the independent evaluator seam."""

    try:
        return _EVALUATOR.start_attempt(**kwargs)
    except _EVALUATOR.EvaluatorError as exc:
        _fail("QA_ATTEMPT_INVALID", "attempt could not be started", "attempt")


def complete_qa_attempt(state: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    """Complete an evaluator attempt without routing or state promotion."""

    try:
        return _EVALUATOR.complete_attempt(state, packet)
    except _EVALUATOR.EvaluatorError as exc:
        _fail("QA_ATTEMPT_INVALID", "attempt packet does not match the running attempt", "attempt")


def prepare_repair_attempt(state: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Prepare a new candidate attempt; no route or receipt mutation occurs."""

    try:
        return _EVALUATOR.repair_attempt(state, **kwargs)
    except _EVALUATOR.EvaluatorError as exc:
        _fail("QA_REPAIR_INVALID", "repair attempt violates the bounded loop", "repair")
