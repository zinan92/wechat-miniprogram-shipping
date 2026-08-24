#!/usr/bin/env python3
"""Run the isolated S14B Ask Park and QA forward-evaluation matrix.

The manifest contains raw scenario inputs, allowed-input bounds, and
exclusions only. It deliberately contains no intended verdict. Each oracle is
derived by executing the staged router, lifecycle, QA schema, Browser/DevTools,
evaluator, and QA-routing seams against record/replay fixtures.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping


_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _ROOT / "fixtures"
_SCRIPTS = _ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LIFECYCLE = _load_module("ask_park_lifecycle_for_forward_eval", _SCRIPTS / "state-lifecycle.py")
_ROUTER = _load_module("ask_park_router_for_forward_eval", _SCRIPTS / "router.py")
_BROWSER = _load_module("ask_park_browser_for_forward_eval", _SCRIPTS / "browser-qa.py")
_DEVTOOLS = _load_module("ask_park_devtools_for_forward_eval", _SCRIPTS / "devtools-qa.py")
_EVALUATOR = _load_module("ask_park_evaluator_for_forward_eval", _SCRIPTS / "qa-evaluator.py")
_QA_SCHEMA = _load_module("ask_park_schema_for_forward_eval", _SCRIPTS / "validate-qa-manifest.py")
_QA_ROUTING = _load_module("ask_park_routing_for_forward_eval", _SCRIPTS / "qa-routing.py")
_CANONICAL_SCENARIOS = json.loads((_FIXTURES / "forward-eval/scenarios.json").read_text(encoding="utf-8"))
CANONICAL_OPERATIONS = {item["id"]: item["operation"] for item in _CANONICAL_SCENARIOS}

ARCHITECTURE_IDS = {f"A{index:02d}" for index in range(1, 24)}
QA_IDS = {f"Q{index:02d}" for index in range(1, 23)}
ALL_IDS = ARCHITECTURE_IDS | QA_IDS
TRACKS = {"architecture", "qa"}
ID_RE = _ROUTER._LIFECYCLE._VALIDATOR.ID_RE
PRIVATE_MARKERS = ("secret", "token", "password", "openid", "credential", "private_key", "api_key", "cookie", "appid", "environment_id")
PRIVATE_PREFIXES = ("http://", "https://", "file://", "cloud://", "/Users/", "/private/", "~/")


class ForwardEvalError(ValueError):
    def __init__(self, code: str, message: str, path: str = "forward-eval") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "forward-eval") -> None:
    raise ForwardEvalError(code, message, path)


def _alias(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _safe(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(marker in normalized for marker in PRIVATE_MARKERS):
                return False
            if not _safe(child):
                return False
    elif isinstance(value, list):
        return all(_safe(child) for child in value)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(prefix in lowered for prefix in PRIVATE_PREFIXES):
            return False
        if any(marker in lowered for marker in ("next_module", "current_module", "route_to")):
            return False
    return True


class RecordReplayAdapter:
    """Read deterministic records and make every external action fail closed."""

    def __init__(self, records: Mapping[str, Any], *, allowed_aliases: set[str] | None = None) -> None:
        if not isinstance(records, Mapping) or not _safe(records):
            _fail("FORWARD_RECORD_PRIVATE", "raw fixture records contain private values or fields", "records")
        self.records = copy.deepcopy(dict(records))
        self.allowed_aliases = set(allowed_aliases or self.records)
        self.events: list[dict[str, str]] = []

    def read(self, alias: str) -> Any:
        if alias not in self.allowed_aliases:
            _fail("FORWARD_UNBOUNDED_INPUT", "scenario attempted to read a fixture outside its declared manifest closure", alias)
        if alias not in self.records:
            _fail("FORWARD_FIXTURE_MISSING", "scenario requested an undeclared fixture alias", alias)
        self.events.append({"kind": "read", "alias": alias})
        return copy.deepcopy(self.records[alias])

    def request(self, target: str) -> None:
        self.events.append({"kind": "network", "alias": "external"})
        raise ForwardEvalError("FORWARD_EXTERNAL_NETWORK", "network is forbidden in forward fixtures", "adapter")

    def write(self, target: str, value: Any) -> None:
        self.events.append({"kind": "mutation", "alias": "external"})
        raise ForwardEvalError("FORWARD_EXTERNAL_MUTATION", "provider mutation is forbidden in forward fixtures", "adapter")

    def delete(self, target: str) -> None:
        self.events.append({"kind": "mutation", "alias": "external"})
        raise ForwardEvalError("FORWARD_EXTERNAL_MUTATION", "provider deletion is forbidden in forward fixtures", "adapter")

    def assert_no_external_side_effects(self) -> None:
        violations = [event for event in self.events if event["kind"] != "read"]
        if violations:
            _fail("FORWARD_EXTERNAL_SIDE_EFFECT", "fixture execution emitted a non-read event", "adapter.events")

    @property
    def external_network_events(self) -> list[dict[str, str]]:
        return [event for event in self.events if event["kind"] == "network"]

    @property
    def mutation_events(self) -> list[dict[str, str]]:
        return [event for event in self.events if event["kind"] == "mutation"]


FIXTURE_FILES = {
    "state-valid": "state/valid-state.json",
    "state-experience-current": "lifecycle/experience-current.json",
    "state-experience-completed": "lifecycle/experience-completed.json",
    "state-released-ready": "lifecycle/released-ready.json",
    "state-control-outcome": "lifecycle/control-outcomes.json",
    "receipt-plan": "lifecycle/valid-plan-receipt.json",
    "receipt-build": "lifecycle/valid-build-receipt.json",
    "receipt-cloudbase": "lifecycle/valid-cloudbase-receipt.json",
    "receipt-experience": "lifecycle/valid-experience-receipt.json",
    "human-awaiting": "lifecycle/awaiting-human-gate.json",
    "human-readback": "lifecycle/human-read-back.json",
    "module-release-payment-na": "modules/release/payment-not-applicable.json",
    "module-release-release-ready": "modules/release/release-ready.json",
    "module-device-protected-failure": "modules/device/protected-content-failure.json",
    "browser-candidate": "browser-qa/candidate-site-valid.json",
    "browser-target": "browser-qa/target-site-valid.json",
    "browser-stale": "browser-qa/target-stale.json",
    "browser-matrix": "browser-qa/matrix-valid.json",
    "browser-missing": "browser-qa/browser-missing.json",
    "dev-events-valid": "devtools-qa/events-valid.json",
    "dev-events-defect": "devtools-qa/events-defect.json",
    "dev-events-missing": "devtools-qa/events-missing-final-compile.json",
    "dev-matrix": "devtools-qa/matrix-valid.json",
    "devtools-missing": "devtools-qa/devtools-missing.json",
    "qa-pass": "qa-evaluator/pass-packet.json",
    "qa-fail": "qa-evaluator/fail-packet.json",
    "qa-blocked": "qa-evaluator/blocked-packet.json",
    "qa-result-qa1": "qa-schema/result-qa1-valid.json",
    "qa-evidence-row": "qa-schema/evidence-row-valid.json",
}


def load_records() -> dict[str, Any]:
    records: dict[str, Any] = {}
    for alias, relative in FIXTURE_FILES.items():
        records[alias] = json.loads((_FIXTURES / relative).read_text(encoding="utf-8"))
    records["skill-entry"] = (_ROOT / "SKILL.md").read_text(encoding="utf-8")
    records["qa-run"] = {"qa_run_id": "forward-eval-1"}
    records["human-gate-request"] = {
        "action_type": "physical-device-observation",
        "action_scope": "device-v1",
        "authorizing_role": "owner",
        "requested_at": "2026-08-24T15:30:00Z",
        "evidence_ref": "redacted:device-gate",
    }
    records["diagnosis-build"] = json.loads((_FIXTURES / "qa-routing/diagnosis-build.json").read_text(encoding="utf-8"))
    records["diagnosis-device"] = json.loads((_FIXTURES / "qa-routing/diagnosis-device.json").read_text(encoding="utf-8"))
    return records


def validate_manifest(manifest: Any) -> list[dict[str, Any]]:
    if not isinstance(manifest, list) or len(manifest) != len(ALL_IDS):
        _fail("FORWARD_MANIFEST_COUNT", "forward manifest must contain every architecture and QA scenario", "manifest")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in manifest:
        if not isinstance(item, Mapping):
            _fail("FORWARD_SCENARIO_TYPE", "scenario must be an object", "manifest")
        if any(key in item for key in ("expected", "expected_verdict", "verdict", "oracle", "result")):
            _fail("FORWARD_INTENDED_VERDICT", "raw forward fixtures cannot carry an intended verdict", "manifest")
        allowed = {"id", "track", "operation", "input_alias", "fixtures", "allowed_inputs", "exclusions"}
        if any(key not in allowed for key in item):
            _fail("FORWARD_SCENARIO_UNKNOWN_FIELD", "scenario contains an undeclared field", "manifest.<key>")
        for key in ("id", "track", "operation", "input_alias"):
            if not _alias(item.get(key)):
                _fail("FORWARD_SCENARIO_ID", "scenario identity fields must be aliases", f"manifest.{key}")
        if item["id"] in seen or item["id"] not in ALL_IDS:
            _fail("FORWARD_SCENARIO_ID", "scenario ID is duplicate or outside the merged matrix", "manifest.id")
        if item["operation"] != CANONICAL_OPERATIONS.get(item["id"]):
            _fail("FORWARD_OPERATION_BINDING", "scenario operation is not bound to its reviewed case", "manifest.operation")
        seen.add(item["id"])
        if item["track"] not in TRACKS:
            _fail("FORWARD_SCENARIO_TRACK", "scenario track is invalid", "manifest.track")
        for key in ("fixtures", "allowed_inputs", "exclusions"):
            if not isinstance(item.get(key), list) or not item[key] or any(not _alias(value) for value in item[key]):
                _fail("FORWARD_SCENARIO_BOUNDS", "scenario bounds must be non-empty alias lists", f"manifest.{key}")
        if not _safe(item):
            _fail("FORWARD_SCENARIO_PRIVATE", "scenario contains private or routing data", "manifest")
        normalized.append(copy.deepcopy(dict(item)))
    if seen != ALL_IDS:
        _fail("FORWARD_SCENARIO_COVERAGE", "scenario IDs do not cover the full matrix", "manifest.id")
    canonical_path = _FIXTURES / "forward-eval" / "scenarios.json"
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    if _manifest_digest(manifest) != _manifest_digest(canonical):
        _fail("FORWARD_MANIFEST_BINDING", "scenario bounds and operations must match the reviewed canonical manifest", "manifest")
    return normalized


def _manifest_digest(value: Any) -> str:
    try:
        canonical = _QA_SCHEMA._canonical_json(value).encode("utf-8")
    except (AttributeError, ValueError):
        _fail("FORWARD_MANIFEST_CANONICAL", "manifest is outside the shared JCS JSON profile", "manifest")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _state(adapter: RecordReplayAdapter, alias: str) -> dict[str, Any]:
    value = adapter.read(alias)
    if not isinstance(value, dict):
        _fail("FORWARD_STATE_FIXTURE", "state fixture must be an object", alias)
    return value


def _receipts(adapter: RecordReplayAdapter, *aliases: str) -> dict[str, dict[str, Any]]:
    result = {}
    for alias in aliases:
        receipt = adapter.read(alias)
        result[receipt["receipt_id"]] = receipt
    return result


def _route_summary(decision: Any) -> dict[str, Any]:
    return {
        "current_module": decision.current_module,
        "selected_module": decision.selected_module,
        "control_outcome": decision.control_outcome,
        "diagnose_requested": decision.diagnose_requested,
        "map_size": len(decision.progress_map),
        "current_count": sum(1 for item in decision.progress_map.values() if item.get("current")),
    }


def _reset_to_current(state: dict[str, Any], module: str) -> dict[str, Any]:
    result = copy.deepcopy(state)
    for name in _LIFECYCLE.MODULES:
        if name == module:
            result["modules"][name]["activity_state"] = "current"
            result["modules"][name]["evidence_state"] = "absent"
        elif _LIFECYCLE.MODULE_INDEX[name] < _LIFECYCLE.MODULE_INDEX[module]:
            result["modules"][name]["activity_state"] = "completed"
            result["modules"][name]["evidence_state"] = "valid"
        else:
            result["modules"][name]["activity_state"] = "locked"
            result["modules"][name]["evidence_state"] = "absent"
    result["current_module"] = module
    result["project_state"] = "active"
    result["control_outcome"] = "none"
    return result


def _architecture(case_id: str, adapter: RecordReplayAdapter) -> dict[str, Any]:
    if case_id == "A01":
        state = _reset_to_current(_state(adapter, "state-valid"), "plan")
        return _route_summary(_ROUTER.route(state, "new"))
    if case_id == "A02":
        state = _reset_to_current(_state(adapter, "state-valid"), "cloudbase")
        return _route_summary(_ROUTER.route(state, "continuation"))
    if case_id == "A03":
        state = _reset_to_current(_state(adapter, "state-valid"), "cloudbase")
        state["modules"]["cloudbase"]["activity_state"] = "failed"
        return _route_summary(_ROUTER.route(state, "continuation"))
    if case_id in {"A04", "A05"}:
        return _route_summary(_ROUTER.route(_state(adapter, "state-experience-completed"), "continuation"))
    if case_id == "A06":
        return _route_summary(_ROUTER.route(_state(adapter, "state-released-ready"), "release"))
    if case_id == "A07":
        return _route_summary(_ROUTER.route(_state(adapter, "state-valid"), "failure"))
    if case_id == "A08":
        return _route_summary(_ROUTER.route(_state(adapter, "state-valid"), "continuation", baseline_conflict=True))
    if case_id == "A09":
        return _route_summary(_ROUTER.route(_state(adapter, "state-valid"), "release", authority_required=True))
    if case_id == "A10":
        return _route_summary(_ROUTER.route(_state(adapter, "state-valid"), "continuation"))
    if case_id == "A11":
        decision = _ROUTER.route(
            _state(adapter, "state-experience-completed"),
            "continuation",
            receipts=_receipts(adapter, "receipt-build", "receipt-cloudbase", "receipt-experience"),
            changed_fields=["source.commit_sha"],
        )
        return _route_summary(decision)
    if case_id == "A12":
        decision = _ROUTER.route(
            _state(adapter, "state-experience-completed"),
            "continuation",
            receipts=_receipts(adapter, "receipt-cloudbase", "receipt-experience"),
            changed_fields=["target.environment_contract_alias"],
        )
        return _route_summary(decision)
    if case_id == "A13":
        decision = _ROUTER.route(
            _state(adapter, "state-experience-completed"),
            "continuation",
            receipts=_receipts(adapter, "receipt-experience"),
            changed_fields=["package.digest"],
        )
        return _route_summary(decision)
    if case_id == "A14":
        state = _state(adapter, "state-experience-current")
        failed = _LIFECYCLE.transition_activity(state, "experience", "failed")
        blocked = _LIFECYCLE.transition_activity(state, "experience", "blocked-external")
        return {"failed_current": failed["current_module"], "blocked_current": blocked["current_module"]}
    if case_id == "A15":
        decision = _ROUTER.route(
            _state(adapter, "state-released-ready"),
            "continuation",
            receipts=_receipts(adapter, "receipt-build", "receipt-cloudbase", "receipt-experience"),
            changed_fields=["source.commit_sha"],
        )
        return _route_summary(decision)
    if case_id == "A16":
        state = _LIFECYCLE.activate_diagnose(_state(adapter, "state-experience-current"), "experience", "bounded-runtime-hypothesis")
        state = _LIFECYCLE.set_diagnose_outcome(state, "unresolved")
        return {"diagnose_state": state["diagnose"]["state"], "diagnose_outcome": state["diagnose"]["outcome"], "current_module": state["current_module"]}
    if case_id == "A17":
        document = adapter.read("module-release-payment-na")
        return {"payment_applicability": document["payment"]["applicability"], "review": document["review"]["result"], "release_readback": document["release_readback"]["result"]}
    if case_id == "A18":
        gate = adapter.read("human-awaiting")
        denied = _LIFECYCLE.transition_human_gate(gate, "denied")
        authorized = _LIFECYCLE.authorize_human_gate(gate, authorized_at="2026-08-24T10:01:00Z", authority_basis="owner decision recorded outside credentials")
        expired = _LIFECYCLE.transition_human_gate(authorized, "expired")
        return {"denied": denied["state"], "expired": expired["state"]}
    if case_id == "A19":
        receipt = adapter.read("receipt-build")
        predecessor = adapter.read("receipt-plan")
        reused = _LIFECYCLE.reuse_receipt(receipt, predecessors={predecessor["receipt_id"]: predecessor})
        return {"receipt_id": reused["receipt_id"], "status": reused["status"]}
    if case_id == "A20":
        text = adapter.read("skill-entry")
        return {"canonical_entry": text.count("$ask-park") >= 1, "qa_command": "$qa" in text or "/qa" in text, "anchors": all(name in text for name in ("Plan", "Build", "CloudBase", "Experience", "Device", "Release", "Diagnose"))}
    if case_id == "A21":
        state = _state(adapter, "state-released-ready")
        state["project_state"] = "released"
        state["current_module"] = "release"
        state["modules"]["release"].update({"activity_state": "completed", "evidence_state": "valid", "receipt_id": "release-r1"})
        state["human_gate"] = adapter.read("human-readback")
        return _route_summary(_ROUTER.route(state, "release"))
    if case_id == "A22":
        state = _state(adapter, "state-control-outcome")
        resolved = _LIFECYCLE.clear_control_outcome(state, evidence={"resolves": "unknown", "evidence_ref": "redacted:forward-readback"})
        return {"before": state["control_outcome"], "after": resolved["control_outcome"]}
    if case_id == "A23":
        migrated = _LIFECYCLE.migrate_receipt(
            adapter.read("receipt-build"),
            target_contract_version="ask-park.receipt/v2",
            migration={"compatible": True, "preserves_causal_identity": True, "verified": True},
        )
        return {"contract_version": migrated["contract_version"], "receipt_id": migrated["receipt_id"]}
    _fail("FORWARD_CASE_UNKNOWN", "architecture scenario is not implemented", case_id)


def _browser_surface_control(adapter: RecordReplayAdapter) -> dict[str, Any]:
    matrix = adapter.read("browser-matrix")
    passed = _BROWSER.compare_candidate_target(adapter.read("browser-candidate"), adapter.read("browser-target"), matrix)
    defect = _BROWSER.run_hermetic_qa2(adapter.read("browser-candidate"), adapter.read("browser-stale"), matrix)
    restored = _BROWSER.run_hermetic_qa2(adapter.read("browser-candidate"), adapter.read("browser-target"), matrix)
    return {"pass": passed["result"], "defect": defect["result"], "restore": restored["result"], "nested_side_effects": {"external_network_events": defect["adapter"]["external_network_events"], "mutation_events": defect["adapter"]["mutation_events"]}}


def _devtools_surface_control(adapter: RecordReplayAdapter) -> dict[str, Any]:
    matrix = adapter.read("dev-matrix")
    passed = _DEVTOOLS.run_hermetic_qa(adapter.read("dev-events-valid"), matrix)
    defect = _DEVTOOLS.run_hermetic_qa(adapter.read("dev-events-defect"), matrix)
    restored = _DEVTOOLS.run_hermetic_qa(adapter.read("dev-events-valid"), matrix)
    return {"pass": passed["result"], "defect": defect["result"], "restore": restored["result"], "nested_side_effects": {"external_network_events": defect["adapter"]["external_network_events"], "mutation_events": defect["adapter"]["platform_mutation_events"]}}


def _evaluator_surface_control(adapter: RecordReplayAdapter) -> dict[str, Any]:
    sha_a = "sha256:" + "a" * 64
    sha_b = "sha256:" + "b" * 64
    state = _EVALUATOR.start_attempt(worker_identity="worker-forward-a", evaluator_identity="evaluator-forward-b", candidate_sha=sha_a, worktree_sha=sha_a, issue_contract_id="forward-eval")
    packet = adapter.read("qa-fail")
    packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": sha_a, "candidate_sha_after": sha_a, "worktree_sha_before": sha_a, "worktree_sha_after": sha_a, "issue_contract_id": "forward-eval", "attempt": 1})
    state = _EVALUATOR.complete_attempt(state, packet)
    fail_result = state["result"]
    state = _EVALUATOR.repair_attempt(state, candidate_sha=sha_b, worktree_sha=sha_b, same_contract=True, prior_result="QA_FAIL")
    state["execution_state"] = "running"
    packet = adapter.read("qa-pass")
    packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": sha_b, "candidate_sha_after": sha_b, "worktree_sha_before": sha_b, "worktree_sha_after": sha_b, "issue_contract_id": "forward-eval", "attempt": 2})
    restored = _EVALUATOR.complete_attempt(state, packet)
    third = _EVALUATOR.start_attempt(worker_identity="worker-forward-a", evaluator_identity="evaluator-forward-b", candidate_sha=sha_a, worktree_sha=sha_a, issue_contract_id="forward-eval")
    for number, current, next_sha in ((1, sha_a, sha_b), (2, sha_b, "sha256:" + "c" * 64)):
        packet = adapter.read("qa-fail")
        packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": current, "candidate_sha_after": current, "worktree_sha_before": current, "worktree_sha_after": current, "issue_contract_id": "forward-eval", "attempt": number})
        third["attempt"] = number
        third = _EVALUATOR.complete_attempt(third, packet)
        third = _EVALUATOR.repair_attempt(third, candidate_sha=next_sha, worktree_sha=next_sha, same_contract=True, prior_result="QA_FAIL")
        third["execution_state"] = "running"
    third_sha = "sha256:" + "c" * 64
    packet = adapter.read("qa-fail")
    packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": third_sha, "candidate_sha_after": third_sha, "worktree_sha_before": third_sha, "worktree_sha_after": third_sha, "issue_contract_id": "forward-eval", "attempt": 3})
    third["attempt"] = 3
    third = _EVALUATOR.complete_attempt(third, packet)
    fourth_rejected = False
    try:
        _EVALUATOR.repair_attempt(third, candidate_sha="sha256:" + "d" * 64, worktree_sha="sha256:" + "d" * 64, same_contract=True, prior_result="QA_FAIL")
    except _EVALUATOR.EvaluatorError:
        fourth_rejected = True
    return {"pass": restored["result"], "defect": fail_result, "candidate_changed": restored["candidate_sha"] == sha_b, "third_result": third["result"], "third_control_outcome": third["control_outcome"], "fourth_rejected": fourth_rejected}


def _qa_schema_surface_control(adapter: RecordReplayAdapter) -> dict[str, Any]:
    result = adapter.read("qa-result-qa1")
    failed = _QA_SCHEMA.invalidate_result(result, candidate_manifest_digest="sha256:" + "f" * 64)
    return {"pass": result["result"], "defect": failed["result"], "reset": failed["result"] == "none"}


def _state_surface_control(adapter: RecordReplayAdapter) -> dict[str, Any]:
    state = _state(adapter, "state-experience-completed")
    failed = _LIFECYCLE.transition_evidence(copy.deepcopy(state), "experience", "stale")
    restored = _state(adapter, "state-experience-completed")
    return {"pass": state["modules"]["experience"]["evidence_state"], "defect": failed["rewind"]["active"], "restore": restored["modules"]["experience"]["evidence_state"]}


def _qa_routing_surface_control(adapter: RecordReplayAdapter) -> dict[str, Any]:
    before = _state(adapter, "state-experience-completed")
    defect = _QA_ROUTING.route_qa_result(before, adapter.read("qa-fail"), diagnosis=adapter.read("diagnosis-device"))
    recovered = _LIFECYCLE.recover_diagnose(defect["state"])
    restored = _QA_ROUTING.route_qa_result(recovered, adapter.read("qa-pass"))
    return {"pass": restored["route_kind"], "defect": defect["route_kind"], "restore": restored["state"]["diagnose"]["state"]}


def _surface_controls(adapter: RecordReplayAdapter) -> dict[str, Any]:
    browser_matrix = adapter.read("browser-matrix")
    browser_pass = _BROWSER.compare_candidate_target(adapter.read("browser-candidate"), adapter.read("browser-target"), browser_matrix)
    stale = _BROWSER.run_hermetic_qa2(adapter.read("browser-candidate"), adapter.read("browser-stale"), browser_matrix)
    browser_restore = _BROWSER.run_hermetic_qa2(adapter.read("browser-candidate"), adapter.read("browser-target"), browser_matrix)

    dev_matrix = adapter.read("dev-matrix")
    dev_pass = _DEVTOOLS.run_hermetic_qa(adapter.read("dev-events-valid"), dev_matrix)
    dev_fail = _DEVTOOLS.run_hermetic_qa(adapter.read("dev-events-defect"), dev_matrix)
    dev_restore = _DEVTOOLS.run_hermetic_qa(adapter.read("dev-events-valid"), dev_matrix)

    sha_a = "sha256:" + "a" * 64
    sha_b = "sha256:" + "b" * 64
    attempt = _EVALUATOR.start_attempt(worker_identity="worker-forward-a", evaluator_identity="evaluator-forward-b", candidate_sha=sha_a, worktree_sha=sha_a, issue_contract_id="forward-eval")
    fail_packet = adapter.read("qa-fail")
    fail_packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": sha_a, "candidate_sha_after": sha_a, "worktree_sha_before": sha_a, "worktree_sha_after": sha_a, "issue_contract_id": "forward-eval", "attempt": 1})
    attempt = _EVALUATOR.complete_attempt(attempt, fail_packet)
    evaluator_fail_result = attempt["result"]
    repaired = _EVALUATOR.repair_attempt(attempt, candidate_sha=sha_b, worktree_sha=sha_b, same_contract=True, prior_result="QA_FAIL")
    pass_packet = adapter.read("qa-pass")
    pass_packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": sha_b, "candidate_sha_after": sha_b, "worktree_sha_before": sha_b, "worktree_sha_after": sha_b, "issue_contract_id": "forward-eval", "attempt": 2})
    repaired["execution_state"] = "running"
    evaluator_restore = _EVALUATOR.complete_attempt(repaired, pass_packet)

    third_state = _EVALUATOR.start_attempt(worker_identity="worker-forward-a", evaluator_identity="evaluator-forward-b", candidate_sha=sha_a, worktree_sha=sha_a, issue_contract_id="forward-eval")
    for attempt_number, current_sha, next_sha in ((1, sha_a, sha_b), (2, sha_b, "sha256:" + "c" * 64)):
        packet = adapter.read("qa-fail")
        packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": current_sha, "candidate_sha_after": current_sha, "worktree_sha_before": current_sha, "worktree_sha_after": current_sha, "issue_contract_id": "forward-eval", "attempt": attempt_number})
        third_state["attempt"] = attempt_number
        third_state = _EVALUATOR.complete_attempt(third_state, packet)
        third_state = _EVALUATOR.repair_attempt(third_state, candidate_sha=next_sha, worktree_sha=next_sha, same_contract=True, prior_result="QA_FAIL")
        third_state["execution_state"] = "running"
    packet = adapter.read("qa-fail")
    third_sha = "sha256:" + "c" * 64
    packet.update({"worker_identity": "worker-forward-a", "evaluator_identity": "evaluator-forward-b", "candidate_sha_before": third_sha, "candidate_sha_after": third_sha, "worktree_sha_before": third_sha, "worktree_sha_after": third_sha, "issue_contract_id": "forward-eval", "attempt": 3})
    third_state["attempt"] = 3
    third_state = _EVALUATOR.complete_attempt(third_state, packet)
    fourth_rejected = False
    try:
        _EVALUATOR.repair_attempt(third_state, candidate_sha="sha256:" + "d" * 64, worktree_sha="sha256:" + "d" * 64, same_contract=True, prior_result="QA_FAIL")
    except _EVALUATOR.EvaluatorError:
        fourth_rejected = True

    schema_result = adapter.read("qa-result-qa1")
    schema_fail = _QA_SCHEMA.invalidate_result(schema_result, candidate_manifest_digest="sha256:" + "f" * 64)
    schema_restore = copy.deepcopy(schema_result)

    state = _state(adapter, "state-experience-completed")
    state_pass = copy.deepcopy(state)
    state_fail = _LIFECYCLE.transition_evidence(state_pass, "experience", "stale")
    state_restore = _state(adapter, "state-experience-completed")

    routing_before = _state(adapter, "state-experience-completed")
    routing_defect = _QA_ROUTING.route_qa_result(routing_before, adapter.read("qa-fail"), diagnosis=adapter.read("diagnosis-device"))
    routing_recovered = _LIFECYCLE.recover_diagnose(routing_defect["state"])
    routing_restore = _QA_ROUTING.route_qa_result(routing_recovered, adapter.read("qa-pass"))
    return {
        "browser": {"pass": browser_pass["result"], "defect": stale["result"], "restore": browser_restore["result"]},
        "devtools": {"pass": dev_pass["result"], "defect": dev_fail["result"], "restore": dev_restore["result"]},
        "evaluator": {"pass": evaluator_restore["result"], "defect": evaluator_fail_result, "candidate_changed": evaluator_restore["candidate_sha"] == sha_b, "third_result": third_state["result"], "third_control_outcome": third_state["control_outcome"], "fourth_rejected": fourth_rejected},
        "qa_schema": {"pass": schema_restore["result"], "defect": schema_fail["result"], "reset": schema_fail["result"] == "none"},
        "state": {"pass": state_pass["modules"]["experience"]["evidence_state"], "defect": state_fail["rewind"]["active"], "restore": state_restore["modules"]["experience"]["evidence_state"]},
        "qa_routing": {"pass": routing_restore["route_kind"], "defect": routing_defect["route_kind"], "restore": routing_restore["state"]["diagnose"]["state"]},
        "nested_side_effects": {
            "browser": {"external_network_events": stale["adapter"]["external_network_events"], "mutation_events": stale["adapter"]["mutation_events"]},
            "devtools": {"external_network_events": dev_fail["adapter"]["external_network_events"], "mutation_events": dev_fail["adapter"]["platform_mutation_events"]},
        },
    }


def _qa(case_id: str, adapter: RecordReplayAdapter) -> dict[str, Any]:
    if case_id == "Q01":
        return _devtools_surface_control(adapter)
    if case_id == "Q02":
        return _browser_surface_control(adapter)
    if case_id == "Q03":
        events = adapter.read("dev-events-valid")
        matrix = adapter.read("dev-matrix")
        events[2]["source_sha"] = "sha256:" + "b" * 64
        failed = _DEVTOOLS.evaluate_events(events, matrix)
        restored = _DEVTOOLS.evaluate_events(adapter.read("dev-events-valid"), matrix)
        return {"defect": failed["result"], "restore": restored["result"]}
    if case_id == "Q04":
        result = _QA_ROUTING.route_qa_result(_state(adapter, "state-experience-completed"), adapter.read("qa-blocked"), gate_request=adapter.read("human-gate-request"))
        return {"route_kind": result["route_kind"], "diagnose": result["state"]["diagnose"]["state"], "gate": result["state"]["human_gate"]["state"]}
    if case_id == "Q05":
        packet = adapter.read("qa-blocked")
        packet["findings"] = ["automatable-defect"]
        try:
            _QA_ROUTING.route_qa_result(_state(adapter, "state-experience-completed"), packet, gate_request=adapter.read("human-gate-request"))
        except _QA_ROUTING.QARoutingError as exc:
            return {"rejected": exc.code}
        _fail("FORWARD_QA_BLOCKED_DEFECT", "QA_BLOCKED hid an automatable finding", case_id)
    if case_id == "Q06":
        result = adapter.read("qa-result-qa1")
        reset = _QA_SCHEMA.invalidate_result(result, candidate_manifest_digest="sha256:" + "f" * 64)
        return {"before": result["result"], "after_identity_change": reset["result"]}
    if case_id == "Q07":
        events = [event for event in adapter.read("dev-events-valid") if event["type"] != "screenshot"]
        result = _DEVTOOLS.evaluate_events(events, adapter.read("dev-matrix"))
        return {"result": result["result"], "finding": "screenshot evidence is missing" in result["findings"]}
    if case_id == "Q08":
        evidence = adapter.read("qa-evidence-row")
        evidence["equivalence"] = "historical-exception"
        evidence["before_evidence"] = None
        result = _QA_SCHEMA.validate_evidence(evidence)
        return {"valid_without_before": result.valid}
    if case_id == "Q09":
        matrix = adapter.read("browser-matrix")[:-1]
        try:
            _BROWSER.validate_matrix(matrix)
        except _BROWSER.BrowserQAError as exc:
            return {"rejected": exc.code}
        _fail("FORWARD_SHARED_ROUTE_OMITTED", "matrix omission was not rejected", case_id)
    if case_id == "Q10":
        candidate = adapter.read("browser-candidate")
        target = adapter.read("browser-target")
        matrix = adapter.read("browser-matrix")
        matrix[0]["before_hash"] = "sha256:" + "9" * 64
        failed = _BROWSER.compare_candidate_target(candidate, target, matrix)
        restored = _BROWSER.compare_candidate_target(candidate, target, adapter.read("browser-matrix"))
        return {"old_screenshot": failed["result"], "restore": restored["result"]}
    if case_id == "Q11":
        result = _QA_ROUTING.route_qa_result(_state(adapter, "state-experience-completed"), adapter.read("qa-fail"), diagnosis=adapter.read("diagnosis-build"), receipts=_receipts(adapter, "receipt-build", "receipt-cloudbase", "receipt-experience"))
        return {"current_module": result["state"]["current_module"], "diagnose": result["state"]["diagnose"]["state"], "invalidated": result["invalidated_receipt_ids"]}
    if case_id == "Q12":
        controls = _evaluator_surface_control(adapter)
        return {"third_failure": controls["third_result"], "third_control_outcome": controls["third_control_outcome"], "candidate_changed": controls["candidate_changed"], "fourth_rejected": controls["fourth_rejected"]}
    if case_id == "Q13":
        state = _EVALUATOR.prerequisite_missing(origin_module="build")
        return {"execution_state": state["qa"]["execution_state"], "control_outcome": state["qa"]["control_outcome"]}
    if case_id == "Q14":
        browser = _BROWSER.prerequisite_missing(browser_available=False, qa_run_id="forward-browser")
        devtools = _DEVTOOLS.prerequisite_missing(devtools_available=False, qa_run_id="forward-devtools")
        return {"browser": browser["control_outcome"], "devtools": devtools["control_outcome"]}
    if case_id == "Q15":
        result = _BROWSER.compare_candidate_target(adapter.read("browser-candidate"), adapter.read("browser-stale"), adapter.read("browser-matrix"))
        return {"result": result["result"], "findings": len(result["findings"])}
    if case_id == "Q16":
        result = _DEVTOOLS.evaluate_events(adapter.read("dev-events-defect"), adapter.read("dev-matrix"))
        return {"result": result["result"], "mismatch": "upload note and platform read-back candidate differ" in result["findings"]}
    if case_id == "Q17":
        evidence = adapter.read("qa-evidence-row")
        evidence["tool"].pop("runtime_or_base_library")
        result = _QA_SCHEMA.validate_evidence(evidence)
        return {"valid": result.valid, "errors": len(result.errors)}
    if case_id == "Q18":
        evidence = adapter.read("qa-evidence-row")
        evidence["after_evidence"] = None
        result = _QA_SCHEMA.validate_evidence(evidence)
        return {"valid": result.valid, "after_required": any(error.code == "EVIDENCE_AFTER_REQUIRED" for error in result.errors)}
    if case_id == "Q19":
        return {"artifact_tree_clean": _artifact_tree_control()}
    if case_id == "Q20":
        result = _QA_ROUTING.route_qa_result(_state(adapter, "state-experience-completed"), adapter.read("qa-fail"), diagnosis=adapter.read("diagnosis-device"))
        return {"route_kind": result["route_kind"], "diagnose": result["state"]["diagnose"]["state"], "invalidated": result["invalidated_receipt_ids"]}
    if case_id == "Q21":
        state = _state(adapter, "state-experience-current")
        before = copy.deepcopy(state)
        _QA_ROUTING.route_qa_result(state, adapter.read("qa-pass"))
        return {"input_unchanged": state == before}
    if case_id == "Q22":
        text = adapter.read("skill-entry")
        return {"seven_anchors": all(name in text for name in ("Plan", "Build", "CloudBase", "Experience", "Device", "Release", "Diagnose")), "qa_command_absent": "$qa" not in text and "/qa" not in text}
    _fail("FORWARD_CASE_UNKNOWN", "QA scenario is not implemented", case_id)


def _artifact_tree_clean(root: Path) -> bool:
    names = [path.name.lower() for path in root.rglob("*")]
    content = b"".join(path.read_bytes() for path in root.rglob("*") if path.is_file())
    forbidden_names = ("secret", "openid", "password", "cookie", "private", "credential")
    forbidden_bytes = (b"openid", b"secret", b"password", b"cookie", b"http://", b"https://", b"cloud://")
    return not any(any(marker in name for marker in forbidden_names) for name in names) and not any(marker in content.lower() for marker in forbidden_bytes)


def _artifact_tree_control() -> bool:
    with tempfile.TemporaryDirectory(prefix="ask-park-forward-") as directory:
        root = Path(directory)
        ephemeral = root / "ephemeral"
        ephemeral.mkdir()
        safe = root / "sanitized-evidence.json"
        safe.write_text('{"ref":"redacted:forward"}', encoding="utf-8")
        return _artifact_tree_clean(root)


def run_forward_evaluation(manifest: Any, *, records: Mapping[str, Any] | None = None) -> dict[str, Any]:
    scenarios = validate_manifest(manifest)
    source_records = records or load_records()
    for scenario in scenarios:
        source_records.setdefault(scenario["input_alias"], {"scenario_id": scenario["id"], "operation": scenario["operation"], "allowed_inputs": scenario["allowed_inputs"], "exclusions": scenario["exclusions"]})
    declared_aliases = {fixture_alias for scenario in scenarios for fixture_alias in scenario["fixtures"]}
    for required_alias in declared_aliases:
        if required_alias not in source_records:
            _fail("FORWARD_FIXTURE_MISSING", "manifest fixture alias is not available to the adapter", required_alias)
    rows = []
    scenario_network: list[dict[str, str]] = []
    scenario_mutation: list[dict[str, str]] = []
    for scenario in scenarios:
        scenario_aliases = set(scenario["fixtures"]) | {scenario["input_alias"]}
        scenario_records = {alias: source_records[alias] for alias in scenario_aliases}
        adapter = RecordReplayAdapter(scenario_records, allowed_aliases=scenario_aliases)
        input_record = adapter.read(scenario["input_alias"])
        if not isinstance(input_record, Mapping) or input_record.get("scenario_id") != scenario["id"]:
            _fail("FORWARD_INPUT_BINDING", "scenario input alias does not bind the current scenario", scenario["input_alias"])
        observations = _architecture(scenario["id"], adapter) if scenario["track"] == "architecture" else _qa(scenario["id"], adapter)
        if not _safe(observations):
            _fail("FORWARD_OUTPUT_PRIVATE", "scenario oracle contains a private value", scenario["id"])
        adapter.assert_no_external_side_effects()
        actual_reads = [event["alias"] for event in adapter.events if event["kind"] == "read"]
        if not set(actual_reads) <= scenario_aliases:
            _fail("FORWARD_UNBOUNDED_INPUT", "scenario read escaped its declared fixture closure", scenario["id"])
        scenario_network.extend(adapter.external_network_events)
        scenario_mutation.extend(adapter.mutation_events)
        rows.append({"id": scenario["id"], "track": scenario["track"], "operation": scenario["operation"], "input_alias": scenario["input_alias"], "allowed_inputs": copy.deepcopy(scenario["allowed_inputs"]), "exclusions": copy.deepcopy(scenario["exclusions"]), "reads": actual_reads, "observations": observations})
    control_adapter = RecordReplayAdapter({alias: source_records[alias] for alias in declared_aliases}, allowed_aliases=declared_aliases)
    controls = _surface_controls(control_adapter)
    control_adapter.assert_no_external_side_effects()
    nested_network = []
    nested_mutation = []
    for surface in controls.get("nested_side_effects", {}).values():
        nested_network.extend(surface.get("external_network_events", []))
        nested_mutation.extend(surface.get("mutation_events", []))
    if nested_network or nested_mutation:
        _fail("FORWARD_NESTED_SIDE_EFFECT", "nested QA adapter emitted an external side effect", "surface_controls")
    with tempfile.TemporaryDirectory(prefix="ask-park-forward-artifacts-") as directory:
        artifact_root = Path(directory)
        for row in rows:
            (artifact_root / f"{row['id']}.json").write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        artifact_clean = _artifact_tree_clean(artifact_root)
    if not artifact_clean:
        _fail("FORWARD_ARTIFACT_PRIVATE", "forward evaluation output tree contains private bytes or names", "artifacts")
    return {
        "scenario_count": len(rows),
        "architecture_count": sum(row["track"] == "architecture" for row in rows),
        "qa_count": sum(row["track"] == "qa" for row in rows),
        "results": rows,
        "surface_controls": controls,
        "external_network_events": scenario_network + control_adapter.external_network_events + nested_network,
        "mutation_events": scenario_mutation + control_adapter.mutation_events + nested_mutation,
        "artifact_tree_clean": artifact_clean,
        "manifest_digest": _manifest_digest(manifest),
    }
