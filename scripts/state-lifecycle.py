#!/usr/bin/env python3
"""Deterministic state, receipt, and human-gate lifecycle operations.

S01 defines the persisted shapes.  This module is deliberately the small
mutation-free seam above those validators: every operation deep-copies its
input, performs a legal transition, and returns a new record (or a result
object).  It never calls a provider, writes a file, or infers authorization
from technical access.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


_VALIDATOR_PATH = Path(__file__).with_name("validate-state.py")
_VALIDATOR_SPEC = importlib.util.spec_from_file_location("ask_park_state_validator", _VALIDATOR_PATH)
if _VALIDATOR_SPEC is None or _VALIDATOR_SPEC.loader is None:  # pragma: no cover - packaging failure
    raise ImportError("cannot load the S01 state validator")
_VALIDATOR = importlib.util.module_from_spec(_VALIDATOR_SPEC)
_VALIDATOR_SPEC.loader.exec_module(_VALIDATOR)

MODULES: tuple[str, ...] = tuple(_VALIDATOR.MODULES)
MODULE_INDEX = {name: index for index, name in enumerate(MODULES)}
ACTIVITY_STATES: tuple[str, ...] = tuple(_VALIDATOR.ACTIVITY_STATES)
EVIDENCE_STATES: tuple[str, ...] = tuple(_VALIDATOR.EVIDENCE_STATES)
DIAGNOSE_STATES: tuple[str, ...] = tuple(_VALIDATOR.DIAGNOSE_STATES)
DIAGNOSE_OUTCOMES: tuple[str, ...] = tuple(_VALIDATOR.DIAGNOSE_OUTCOMES)
CONTROL_OUTCOMES: tuple[str, ...] = tuple(_VALIDATOR.CONTROL_OUTCOMES)
PROJECT_STATES: tuple[str, ...] = tuple(_VALIDATOR.PROJECT_STATES)
HUMAN_GATE_STATES: tuple[str, ...] = tuple(_VALIDATOR.HUMAN_GATE_STATES)


class LifecycleError(ValueError):
    """A stable, machine-readable lifecycle rejection."""

    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        self.code = code
        self.error_code = code
        self.path = path or "lifecycle"
        self.message = message
        super().__init__(f"{code}: {message}")


class InvalidationResult:
    """The causal closure selected by :func:`invalidate_receipts`."""

    __slots__ = ("receipts", "earliest_invalidated_module", "invalidated_receipt_ids", "reason_code")

    def __init__(
        self,
        receipts: dict[str, dict[str, Any]],
        earliest_invalidated_module: str | None,
        invalidated_receipt_ids: tuple[str, ...],
        reason_code: str = "causal-identity-changed",
    ) -> None:
        self.receipts = receipts
        self.earliest_invalidated_module = earliest_invalidated_module
        self.invalidated_receipt_ids = invalidated_receipt_ids
        self.reason_code = reason_code

    def __iter__(self):
        """Allow small router adapters to unpack the result deterministically."""

        yield self.receipts
        yield self.earliest_invalidated_module
        yield self.invalidated_receipt_ids

    def __getitem__(self, key: str):
        if key not in {"receipts", "earliest_invalidated_module", "invalidated_receipt_ids", "reason_code"}:
            raise KeyError(key)
        return getattr(self, key)


class MigrationResult:
    """A verified receipt migration, kept separate from routing decisions."""

    __slots__ = ("receipt", "source_contract_version", "target_contract_version", "compatible")

    def __init__(self, receipt: dict[str, Any], source_contract_version: str, target_contract_version: str, compatible: bool) -> None:
        self.receipt = receipt
        self.source_contract_version = source_contract_version
        self.target_contract_version = target_contract_version
        self.compatible = compatible


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _error(code: str, message: str, path: str | None = None) -> None:
    raise LifecycleError(code, message, path)


def _validate_state(state: Any) -> dict[str, Any]:
    result = _VALIDATOR.validate_state(state)
    if not result.valid:
        first = result.errors[0]
        _error("STATE_INVALID", f"state does not satisfy S01 ({first.code})", first.path)
    diagnose = result.document.get("diagnose", {})
    if diagnose.get("state") == "active" and diagnose.get("interrupted_module") != result.document.get("current_module"):
        _error("DIAGNOSE_MODULE_MISMATCH", "active Diagnose must overlay the current sequential module", "diagnose.interrupted_module")
    return _clone(state)


def _validate_receipt(receipt: Any, *, allow_unknown_contract: bool = False) -> dict[str, Any]:
    if allow_unknown_contract:
        if not isinstance(receipt, dict):
            _error("RECEIPT_INVALID", "receipt must be an object", "receipt")
        # Migration output is checked against the source contract before its
        # contract version changes.  Do not silently accept arbitrary shapes.
        for key in ("receipt_id", "receipt_type", "schema_version", "contract_version", "module", "status"):
            if key not in receipt:
                _error("RECEIPT_INVALID", "receipt is missing a required causal field", f"receipt.{key}")
        return _clone(receipt)
    result = _VALIDATOR.validate_receipt(receipt)
    if not result.valid:
        first = result.errors[0]
        _error("RECEIPT_INVALID", f"receipt does not satisfy S01 ({first.code})", first.path)
    return _clone(receipt)


def _validate_gate(gate: Any) -> dict[str, Any]:
    if not isinstance(gate, dict):
        _error("HUMAN_GATE_INVALID", "human gate must be an object", "human_gate")
    boundary_errors = _VALIDATOR._Collector()
    _VALIDATOR._walk_persistence_boundary(gate, "human_gate", boundary_errors)
    if boundary_errors.errors:
        first = boundary_errors.errors[0]
        _error("HUMAN_GATE_INVALID", f"human gate does not satisfy S01 ({first.code})", first.path)
    if "authority_basis" in gate and gate.get("authority_basis") is not None and not _has_explicit_human_authority(gate.get("authority_basis")):
        _error("HUMAN_AUTHORIZATION_REQUIRED", "technical access never constitutes authorization", "human_gate.authority_basis")
    if "gate_id" in gate:
        result = _VALIDATOR.validate_human_gate(gate)
        if not result.valid:
            first = result.errors[0]
            _error("HUMAN_GATE_INVALID", f"human gate does not satisfy S01 ({first.code})", first.path)
    else:
        # Embedded gates intentionally do not carry a gate_id.  Once prepared,
        # the S01 field helper is still the single source of validation.
        errors = _VALIDATOR._Collector()
        _VALIDATOR._validate_human_gate_fields(gate, "human_gate", errors)
        if errors.errors:
            first = errors.errors[0]
            _error("HUMAN_GATE_INVALID", f"human gate does not satisfy S01 ({first.code})", first.path)
    return _clone(gate)


def _post_state(state: dict[str, Any], *, validate: bool = True) -> dict[str, Any]:
    if validate:
        _validate_state(state)
    return state


def _ensure_project_progressable(state: Mapping[str, Any]) -> None:
    project_state = state.get("project_state")
    terminal_state = state.get("project_terminal_state")
    terminal = project_state if project_state in ("released", "target-achieved", "abandoned") else terminal_state
    if terminal in ("released", "target-achieved", "abandoned"):
        _error("ILLEGAL_PROJECT_TRANSITION", f"terminal project state {terminal} cannot be mutated", "project_state")


def _has_explicit_human_authority(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    return not re.search(
        r"authenticated|cli|access|permission|login|capability|token|secret|password|api[-_ ]?key",
        value,
        re.I,
    )


def _module_record(state: dict[str, Any], module: str) -> dict[str, Any]:
    if module not in MODULES:
        _error("UNKNOWN_MODULE", "module is not a sequential module", "modules.<module>")
    record = state["modules"].get(module)
    if not isinstance(record, dict):
        _error("STATE_INVALID", "module state is not an object", f"modules.{module}")
    return record


def _required_predecessors_satisfied(state: dict[str, Any], module: str) -> bool:
    index = MODULE_INDEX[module]
    for predecessor in MODULES[:index]:
        record = state["modules"][predecessor]
        if record["applicability"] == "not-applicable":
            continue
        if record["activity_state"] != "completed" or record["evidence_state"] != "valid":
            return False
    return True


def _next_required_module(state: dict[str, Any], completed_module: str) -> str | None:
    for module in MODULES[MODULE_INDEX[completed_module] + 1 :]:
        record = state["modules"][module]
        if record["applicability"] == "not-applicable":
            continue
        if record["activity_state"] != "completed" or record["evidence_state"] != "valid":
            return module
    return None


def _promote_after_completion(state: dict[str, Any], completed_module: str) -> None:
    next_module = _next_required_module(state, completed_module)
    if next_module is None:
        # An approved target may stop at the last required module when every
        # later module was explicitly marked not-applicable in Plan. Release
        # remains the only formal released state.
        state["current_module"] = completed_module
        if completed_module != "release":
            state["project_state"] = "target-achieved"
            state.pop("project_terminal_state", None)
        return
    for module in MODULES:
        record = state["modules"][module]
        if record["applicability"] == "not-applicable":
            record["activity_state"] = "not-applicable"
            record["evidence_state"] = "not-applicable"
        elif MODULE_INDEX[module] > MODULE_INDEX[next_module]:
            record["activity_state"] = "locked"
        elif module == next_module:
            record["activity_state"] = "current"
    state["current_module"] = next_module


def transition_evidence(state: Mapping[str, Any], module: str, target: str) -> dict[str, Any]:
    """Apply one legal evidence-axis transition and return a new state."""

    result = _validate_state(state)
    _ensure_project_progressable(result)
    record = _module_record(result, module)
    if target not in EVIDENCE_STATES:
        _error("ILLEGAL_EVIDENCE_TRANSITION", "evidence state is outside the contract enum", f"modules.{module}.evidence_state")
    current = record["evidence_state"]
    if current == target:
        return result
    if record["applicability"] == "not-applicable":
        _error("ILLEGAL_EVIDENCE_TRANSITION", "not-applicable evidence cannot be changed", f"modules.{module}.evidence_state")
    legal = {
        "absent": {"valid", "invalid"},
        "valid": {"stale", "invalid"},
        "stale": {"valid", "invalid"},
        "invalid": {"valid", "stale"},
        "not-applicable": set(),
    }
    if target not in legal.get(current, set()):
        _error("ILLEGAL_EVIDENCE_TRANSITION", f"cannot move evidence from {current} to {target}", f"modules.{module}.evidence_state")
    record["evidence_state"] = target
    if target in ("stale", "invalid"):
        # A stale/invalid predecessor is never left as an orphaned axis.  The
        # causal rewind is computed locally here; receipt-level graph closure
        # remains the responsibility of invalidate_receipts().
        invalidated_ids = [
            result["modules"][name].get("receipt_id")
            for name in MODULES[MODULE_INDEX[module] :]
            if result["modules"][name].get("receipt_id")
        ]
        _rewind_state_unchecked(
            result,
            earliest_module=module,
            invalidated_receipt_ids=invalidated_ids,
            reason_code="evidence-" + target,
        )
    if target == "valid" and result["rewind"].get("active"):
        stale = [
            name
            for name in MODULES
            if result["modules"][name]["applicability"] == "required"
            and result["modules"][name]["evidence_state"] in ("stale", "invalid")
        ]
        if not stale:
            result["rewind"] = {
                "active": False,
                "earliest_invalidated_module": None,
                "reason_code": None,
                "invalidated_receipt_ids": [],
            }
    return _post_state(result)


def transition_activity(state: Mapping[str, Any], module: str, target: str) -> dict[str, Any]:
    """Apply one legal module activity transition.

    Completing a module selects the next required module as current.  This is
    the only promotion performed here; no ``next_module`` field is persisted.
    """

    result = _validate_state(state)
    _ensure_project_progressable(result)
    record = _module_record(result, module)
    if target not in ACTIVITY_STATES:
        _error("ILLEGAL_ACTIVITY_TRANSITION", "activity state is outside the contract enum", f"modules.{module}.activity_state")
    current = record["activity_state"]
    if current == target:
        return result
    if record["applicability"] == "not-applicable":
        _error("ILLEGAL_ACTIVITY_TRANSITION", "not-applicable activity cannot be changed", f"modules.{module}.activity_state")
    legal = {
        "waiting": {"current"},
        "current": {"completed", "failed", "blocked-external"},
        "failed": {"current"},
        "blocked-external": {"current"},
        "locked": {"current"},
        "completed": set(),
        "not-applicable": set(),
    }
    if target not in legal.get(current, set()):
        _error("ILLEGAL_ACTIVITY_TRANSITION", f"cannot move activity from {current} to {target}", f"modules.{module}.activity_state")
    if target == "current":
        if result["current_module"] != module and not _required_predecessors_satisfied(result, module):
            _error("CURRENT_MODULE_REQUIRED", "module cannot become current before required predecessors are complete", f"modules.{module}")
        other_current = [name for name in MODULES if name != module and result["modules"][name]["activity_state"] == "current"]
        if other_current:
            _error("CURRENT_MODULE_REQUIRED", "only one sequential module may be current", "current_module")
        result["current_module"] = module
    if target == "completed":
        if result["diagnose"]["state"] == "active":
            _error("DIAGNOSE_ACTIVE", "an active Diagnose overlay must recover before module completion", "diagnose.state")
        if not _required_predecessors_satisfied(result, module):
            _error("PREDECESSOR_COMPLETION_REQUIRED", "module completion requires every earlier required module to be completed with valid evidence", f"modules.{module}")
        if record["evidence_state"] != "valid":
            _error("COMPLETION_EVIDENCE_REQUIRED", "module completion requires valid evidence", f"modules.{module}.evidence_state")
        if module == "release":
            gate = result["human_gate"]
            if gate.get("state") != "read-back":
                _error("PROJECT_RELEASE_EVIDENCE_REQUIRED", "Release completion requires a read-back human gate", "human_gate.state")
            if not _has_explicit_human_authority(gate.get("authority_basis")):
                _error("HUMAN_AUTHORIZATION_REQUIRED", "Release completion requires an explicit human authority basis", "human_gate.authority_basis")
    record["activity_state"] = target
    if target == "completed":
        _promote_after_completion(result, module)
        if module == "release":
            result["project_state"] = "released"
            result.pop("project_terminal_state", None)
    return _post_state(result)


def transition_project(state: Mapping[str, Any], target: str) -> dict[str, Any]:
    """Move the project terminal axis without conflating it with module state."""

    result = _validate_state(state)
    if target not in PROJECT_STATES:
        _error("ILLEGAL_PROJECT_TRANSITION", "project state is outside the contract enum", "project_state")
    current = result.get("project_state")
    if current is None:
        legacy_terminal = result.get("project_terminal_state", "none")
        current = "active" if legacy_terminal == "none" else legacy_terminal
    if current == target:
        return result
    if current in ("released", "abandoned", "target-achieved"):
        _error("ILLEGAL_PROJECT_TRANSITION", f"terminal project state {current} cannot transition", "project_state")
    if target == "abandoned":
        result["project_state"] = "abandoned"
        result.pop("project_terminal_state", None)
        # An abandoned target retains the current module as historical context.
        return result
    if target == "target-achieved":
        current_module = result["current_module"]
        current_record = result["modules"][current_module]
        if (
            current_record["applicability"] != "required"
            or current_record["activity_state"] != "completed"
            or current_record["evidence_state"] != "valid"
            or not _VALIDATOR._safe_identifier(current_record.get("receipt_id"))
        ):
            _error("PROJECT_TARGET_EVIDENCE_REQUIRED", "target-achieved requires a completed current target with valid evidence and a receipt", "current_module")
        later_required = [
            module for module in MODULES[MODULE_INDEX[current_module] + 1 :]
            if result["modules"][module]["applicability"] == "required"
        ]
        if later_required:
            _error("PROJECT_TARGET_SCOPE_REQUIRED", "later modules must be explicitly not-applicable before target-achieved", "project_state")
        result["project_state"] = "target-achieved"
        result.pop("project_terminal_state", None)
        # Keep the completed target module as the explicit stop point. The
        # activity axis is intentionally not auto-promoted to a successor.
        return _post_state(result)
    if target == "released":
        release = result["modules"]["release"]
        if (
            release["activity_state"] != "completed"
            or release["evidence_state"] != "valid"
            or not release.get("receipt_id")
            or result["human_gate"].get("state") != "read-back"
        ):
            _error("PROJECT_RELEASE_EVIDENCE_REQUIRED", "released requires completed valid Release evidence and a read-back gate", "project_state")
        if not _has_explicit_human_authority(result["human_gate"].get("authority_basis")):
            _error("HUMAN_AUTHORIZATION_REQUIRED", "released requires an explicit human authority basis", "human_gate.authority_basis")
        result["project_state"] = "released"
        result.pop("project_terminal_state", None)
        result["current_module"] = "release"
        return _post_state(result)
    _error("ILLEGAL_PROJECT_TRANSITION", f"cannot move project from {current} to {target}", "project_state")


def activate_diagnose(state: Mapping[str, Any], interrupted_module: str, recovery_goal: str) -> dict[str, Any]:
    result = _validate_state(state)
    _ensure_project_progressable(result)
    _module_record(result, interrupted_module)
    if result["current_module"] != interrupted_module:
        _error("DIAGNOSE_MODULE_MISMATCH", "Diagnose must overlay the current sequential module", "diagnose.interrupted_module")
    if not isinstance(recovery_goal, str) or not recovery_goal.strip():
        _error("DIAGNOSE_RECOVERY_GOAL_REQUIRED", "recovery_goal must be non-empty", "diagnose.recovery_goal")
    if result["diagnose"]["state"] == "active":
        _error("DIAGNOSE_ALREADY_ACTIVE", "Diagnose is already active", "diagnose.state")
    result["diagnose"] = {
        "state": "active",
        "outcome": "none",
        "interrupted_module": interrupted_module,
        "recovery_goal": recovery_goal.strip(),
    }
    return _post_state(result)


def set_diagnose_outcome(state: Mapping[str, Any], outcome: str, recovery_goal: str | None = None) -> dict[str, Any]:
    result = _validate_state(state)
    _ensure_project_progressable(result)
    diagnose = result["diagnose"]
    if diagnose["state"] != "active":
        _error("DIAGNOSE_NOT_ACTIVE", "Diagnose outcome requires an active Diagnose overlay", "diagnose.state")
    if outcome == "recovered":
        return recover_diagnose(result)
    if outcome not in ("none", "unresolved", "blocked-external"):
        _error("ILLEGAL_DIAGNOSE_TRANSITION", "outcome must be none, unresolved, or blocked-external while active", "diagnose.outcome")
    if outcome == "none" and recovery_goal is None:
        return result
    if recovery_goal is not None:
        if not isinstance(recovery_goal, str) or not recovery_goal.strip():
            _error("DIAGNOSE_RECOVERY_GOAL_REQUIRED", "recovery_goal must be non-empty", "diagnose.recovery_goal")
        diagnose["recovery_goal"] = recovery_goal.strip()
    diagnose["outcome"] = outcome
    return _post_state(result)


def transition_diagnose(
    state: Mapping[str, Any],
    *,
    outcome: str | None = None,
    interrupted_module: str | None = None,
    recovery_goal: str | None = None,
) -> dict[str, Any]:
    """Small adapter for routers that treat Diagnose as one axis operation."""

    if interrupted_module is not None:
        return activate_diagnose(state, interrupted_module, recovery_goal or "diagnose")
    if outcome == "recovered":
        return recover_diagnose(state)
    if outcome is None:
        return _validate_state(state)
    return set_diagnose_outcome(state, outcome, recovery_goal)


def recover_diagnose(state: Mapping[str, Any]) -> dict[str, Any]:
    result = _validate_state(state)
    _ensure_project_progressable(result)
    diagnose = result["diagnose"]
    if diagnose["state"] != "active":
        _error("DIAGNOSE_NOT_ACTIVE", "only an active Diagnose overlay can recover", "diagnose.state")
    diagnose.update({"state": "standby", "outcome": "none", "interrupted_module": None, "recovery_goal": None})
    module = result["current_module"]
    if result["modules"][module]["activity_state"] in ("failed", "blocked-external"):
        result["modules"][module]["activity_state"] = "current"
    return _post_state(result)


def _receipt_status_satisfies(receipt: Mapping[str, Any]) -> bool:
    return receipt.get("status") in ("valid", "not-applicable")


def issue_receipt(receipt: Mapping[str, Any], *, predecessors: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Issue an otherwise valid receipt only when its causal predecessors pass."""

    issued = _validate_receipt(receipt)
    if issued["status"] not in ("valid", "not-applicable"):
        _error("RECEIPT_NOT_ISSUABLE", "only valid or explicit not-applicable receipts may be issued", "receipt.status")
    predecessor_ids = list(issued.get("predecessor_receipt_ids", []))
    if len(predecessor_ids) != len(set(predecessor_ids)):
        _error("PREDECESSOR_RECEIPT_INVALID", "predecessor receipt IDs must be unique", "receipt.predecessor_receipt_ids")
    predecessor_map = dict(predecessors or {})
    for receipt_id in predecessor_ids:
        predecessor = predecessor_map.get(receipt_id)
        if predecessor is None:
            _error("PREDECESSOR_RECEIPT_MISSING", "every predecessor receipt must be supplied", "receipt.predecessor_receipt_ids")
        try:
            valid_predecessor = _validate_receipt(predecessor)
        except LifecycleError:
            if isinstance(predecessor, Mapping) and predecessor.get("status") in ("stale", "invalid"):
                _error("PREDECESSOR_RECEIPT_INVALID", "predecessor receipt is stale or invalid", "receipt.predecessor_receipt_ids")
            raise
        if valid_predecessor["receipt_id"] != receipt_id or not _receipt_status_satisfies(valid_predecessor):
            _error("PREDECESSOR_RECEIPT_INVALID", "predecessor receipt is not valid or does not match its alias", "receipt.predecessor_receipt_ids")
        if valid_predecessor["module"] not in MODULES or MODULE_INDEX[valid_predecessor["module"]] >= MODULE_INDEX[issued["module"]]:
            _error("PREDECESSOR_ORDER_INVALID", "predecessor must be an earlier sequential module", "receipt.predecessor_receipt_ids")
    return issued


def _causal_identity(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": receipt.get("receipt_id"),
        "schema_version": receipt.get("schema_version"),
        "module": receipt.get("module"),
        "applicability": receipt.get("applicability"),
        "source": _clone(receipt.get("source")),
        "issue": _clone(receipt.get("issue")),
        "predecessor_receipt_ids": _clone(receipt.get("predecessor_receipt_ids")),
        "artifact": _clone(receipt.get("artifact")),
        "package": _clone(receipt.get("package")),
        "target": _clone(receipt.get("target")),
    }


def _field_matches(rule: str, changed: str) -> bool:
    return rule == changed or rule.startswith(changed + ".") or changed.startswith(rule + ".")


def reuse_receipt(
    receipt: Mapping[str, Any],
    *,
    changed_fields: Iterable[str] = (),
    predecessors: Mapping[str, Mapping[str, Any]] | None = None,
    expected_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reuse a receipt only while every declared causal binding is unchanged."""

    existing = _validate_receipt(receipt)
    if existing["status"] != "valid":
        _error("RECEIPT_REUSE_INVALID", "only valid receipts may be reused", "receipt.status")
    changed = tuple(str(item) for item in changed_fields)
    rules = existing.get("invalidation_rules", {}).get("on", [])
    if any(_field_matches(str(rule), field) for rule in rules for field in changed):
        _error("RECEIPT_REUSE_INVALIDATED", "a declared causal invalidation rule has fired", "receipt.invalidation_rules.on")
    predecessor_ids = existing.get("predecessor_receipt_ids", [])
    if predecessor_ids and predecessors is None:
        _error("PREDECESSOR_RECEIPT_MISSING", "receipt reuse requires every predecessor receipt", "receipt.predecessor_receipt_ids")
    if predecessors is not None:
        for receipt_id in predecessor_ids:
            predecessor = predecessors.get(receipt_id)
            if predecessor is None:
                _error("PREDECESSOR_RECEIPT_MISSING", "a reused receipt has a missing predecessor", "receipt.predecessor_receipt_ids")
            try:
                validated_predecessor = _validate_receipt(predecessor)
            except LifecycleError:
                if isinstance(predecessor, Mapping) and predecessor.get("status") in ("stale", "invalid"):
                    _error("PREDECESSOR_RECEIPT_INVALID", "a reused receipt has a stale or invalid predecessor", "receipt.predecessor_receipt_ids")
                raise
            if not _receipt_status_satisfies(validated_predecessor):
                _error("PREDECESSOR_RECEIPT_INVALID", "a reused receipt has an invalid predecessor", "receipt.predecessor_receipt_ids")
            if validated_predecessor["receipt_id"] != receipt_id:
                _error("PREDECESSOR_RECEIPT_INVALID", "predecessor payload does not match its alias", "receipt.predecessor_receipt_ids")
            if validated_predecessor["module"] not in MODULES or MODULE_INDEX[validated_predecessor["module"]] >= MODULE_INDEX[existing["module"]]:
                _error("PREDECESSOR_ORDER_INVALID", "reused receipt predecessor must be an earlier sequential module", "receipt.predecessor_receipt_ids")
    if expected_identity is not None and dict(expected_identity) != _causal_identity(existing):
        _error("RECEIPT_CAUSAL_IDENTITY_CHANGED", "receipt causal identity differs from the expected identity", "receipt")
    return existing


def invalidate_receipts(
    receipts: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    changed_fields: Iterable[str],
    reason_code: str = "causal-identity-changed",
) -> InvalidationResult:
    """Compute the transitive causal closure without selecting a next module."""

    if not isinstance(reason_code, str) or not _VALIDATOR._safe_identifier(reason_code):
        _error("INVALIDATION_REASON_REQUIRED", "reason_code must be a safe non-empty alias", "reason_code")
    if isinstance(receipts, Mapping):
        source = {}
        for key, value in receipts.items():
            validated = _validate_receipt(value)
            if validated["receipt_id"] != str(key):
                _error("RECEIPT_ID_MISMATCH", "receipt mapping key does not match receipt_id", "receipts.<key>")
            source[str(key)] = validated
    else:
        source = {}
        for receipt in receipts:
            validated = _validate_receipt(receipt)
            receipt_id = validated["receipt_id"]
            if receipt_id in source:
                _error("RECEIPT_ID_DUPLICATE", "receipt iterable contains a duplicate receipt_id", "receipts.<receipt_id>")
            source[receipt_id] = validated
    changed = tuple(str(item) for item in changed_fields)
    selected: set[str] = set()
    for receipt_id, receipt in source.items():
        rules = receipt.get("invalidation_rules", {}).get("on", [])
        if any(_field_matches(str(rule), field) for rule in rules for field in changed):
            selected.add(receipt_id)

    # Follow both predecessor edges and Ask Park's declared downstream module
    # closure.  The fixed point makes multi-hop chains deterministic.
    changed_again = True
    while changed_again:
        changed_again = False
        for receipt_id, receipt in source.items():
            if receipt_id in selected:
                downstream = set(receipt.get("invalidation_rules", {}).get("downstream_modules", []))
                for other_id, other in source.items():
                    if other_id in selected:
                        continue
                    if other.get("module") in downstream or set(other.get("predecessor_receipt_ids", [])) & selected:
                        selected.add(other_id)
                        changed_again = True
            elif set(receipt.get("predecessor_receipt_ids", [])) & selected:
                selected.add(receipt_id)
                changed_again = True

    updated = {receipt_id: _clone(receipt) for receipt_id, receipt in source.items()}
    for receipt_id in selected:
        if updated[receipt_id].get("status") == "valid":
            updated[receipt_id]["status"] = "stale"
            updated[receipt_id]["stale_reason"] = reason_code
    ordered_ids = tuple(
        sorted(
            selected,
            key=lambda receipt_id: (MODULE_INDEX.get(updated[receipt_id].get("module"), len(MODULES)), receipt_id),
        )
    )
    earliest = None
    if ordered_ids:
        earliest = min((updated[receipt_id]["module"] for receipt_id in ordered_ids), key=MODULE_INDEX.__getitem__)
    return InvalidationResult(updated, earliest, ordered_ids, reason_code)


def _rewind_state_unchecked(
    result: dict[str, Any],
    *,
    earliest_module: str,
    invalidated_receipt_ids: Iterable[str],
    reason_code: str,
) -> dict[str, Any]:
    """Apply a rewind to an already-cloned state without revalidating first."""

    ids = list(dict.fromkeys(str(item) for item in invalidated_receipt_ids))
    earliest_index = MODULE_INDEX[earliest_module]
    for module in MODULES:
        module_record = result["modules"][module]
        if module_record["applicability"] == "not-applicable":
            continue
        if MODULE_INDEX[module] < earliest_index:
            continue
        if MODULE_INDEX[module] == earliest_index:
            module_record["activity_state"] = "current"
        else:
            module_record["activity_state"] = "locked"
        if module_record.get("receipt_id"):
            module_record["evidence_state"] = "stale"
            if module_record["receipt_id"] not in ids:
                ids.append(module_record["receipt_id"])
        else:
            module_record["evidence_state"] = "absent"
    result["current_module"] = earliest_module
    result["rewind"] = {
        "active": True,
        "earliest_invalidated_module": earliest_module,
        "reason_code": reason_code,
        "invalidated_receipt_ids": ids,
    }
    return result


def rewind_state(
    state: Mapping[str, Any],
    *,
    earliest_module: str,
    invalidated_receipt_ids: Iterable[str],
    reason_code: str,
) -> dict[str, Any]:
    """Mark the earliest prerequisite current and lock every later module."""

    result = _validate_state(state)
    _ensure_project_progressable(result)
    if earliest_module not in MODULES:
        _error("UNKNOWN_MODULE", "earliest invalidated module is not sequential", "rewind.earliest_invalidated_module")
    record = result["modules"][earliest_module]
    if record["applicability"] != "required":
        _error("REWIND_NOT_REQUIRED", "cannot rewind to a not-applicable module", "rewind.earliest_invalidated_module")
    _rewind_state_unchecked(
        result,
        earliest_module=earliest_module,
        invalidated_receipt_ids=invalidated_receipt_ids,
        reason_code=reason_code,
    )
    return _post_state(result)


def invalidate_state(
    state: Mapping[str, Any],
    receipts: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    changed_fields: Iterable[str],
    reason_code: str = "causal-identity-changed",
) -> tuple[dict[str, Any], InvalidationResult]:
    """Convenience operation: compute receipt closure, then rewind state."""

    validated_state = _validate_state(state)
    _ensure_project_progressable(validated_state)
    invalidation = invalidate_receipts(receipts, changed_fields=changed_fields, reason_code=reason_code)
    if invalidation.earliest_invalidated_module is None:
        return validated_state, invalidation
    return rewind_state(
        state,
        earliest_module=invalidation.earliest_invalidated_module,
        invalidated_receipt_ids=invalidation.invalidated_receipt_ids,
        reason_code=reason_code,
    ), invalidation


def prepare_human_gate(
    gate: Mapping[str, Any],
    *,
    action_type: str,
    action_scope: str,
    authorizing_role: str,
    requested_at: str,
    evidence_ref: str,
    authority_basis: str | None = None,
) -> dict[str, Any]:
    """Create a prepared gate from explicit action details."""

    if not isinstance(gate, Mapping):
        _error("HUMAN_GATE_INVALID", "human gate must be an object", "human_gate")
    prepared = _validate_gate(gate)
    if prepared.get("state") != "not-needed":
        _error("ILLEGAL_HUMAN_GATE_TRANSITION", "only a not-needed gate can be prepared", "human_gate.state")
    if not all(isinstance(value, str) and value.strip() for value in (action_type, action_scope, authorizing_role)):
        _error("HUMAN_GATE_REQUIRED_FIELD", "action type, scope, and role are required", "human_gate")
    if not _VALIDATOR._is_iso(requested_at):
        _error("HUMAN_GATE_TIMESTAMP", "requested_at must be ISO-8601", "human_gate.requested_at")
    if not _VALIDATOR._is_redacted_ref(evidence_ref):
        _error("HUMAN_GATE_EVIDENCE", "evidence_ref must be redacted", "human_gate.evidence_ref")
    prepared.update(
        {
            "state": "prepared",
            "action_type": action_type.strip(),
            "action_scope": action_scope.strip(),
            "authorizing_role": authorizing_role.strip(),
            "requested_at": requested_at,
            "authorized_at": None,
            "evidence_ref": evidence_ref,
        }
    )
    if "schema_version" in prepared and "gate_id" not in prepared:
        slug = re.sub(r"[^A-Za-z0-9._:-]+", "-", f"{action_type}-{action_scope}").strip("-")
        prepared["gate_id"] = f"gate-{slug}"
    if authority_basis is not None:
        if not _has_explicit_human_authority(authority_basis):
            _error("HUMAN_AUTHORIZATION_REQUIRED", "technical access never constitutes authorization", "human_gate.authority_basis")
        prepared["authority_basis"] = authority_basis
    _validate_gate(prepared)
    return prepared


def transition_human_gate(gate: Mapping[str, Any], target: str) -> dict[str, Any]:
    """Apply a non-authorizing human-gate transition."""

    current_gate = _validate_gate(gate)
    current = current_gate.get("state")
    legal = {
        "not-needed": {"prepared"},
        "prepared": {"awaiting-human"},
        "awaiting-human": {"denied"},
        "authorized": {"executed", "expired"},
        "executed": {"read-back"},
        "read-back": set(),
        "denied": set(),
        "expired": set(),
    }
    if target not in HUMAN_GATE_STATES or target not in legal.get(current, set()):
        _error("ILLEGAL_HUMAN_GATE_TRANSITION", f"cannot move human gate from {current} to {target}", "human_gate.state")
    if current in ("authorized", "executed", "read-back") and not _has_explicit_human_authority(current_gate.get("authority_basis")):
        _error("HUMAN_AUTHORIZATION_REQUIRED", "authorized gate transitions require an explicit authority basis", "human_gate.authority_basis")
    current_gate["state"] = target
    if target == "executed" and not _VALIDATOR._is_iso(current_gate.get("authorized_at")):
        _error("HUMAN_AUTHORIZATION_REQUIRED", "executed requires an authorized gate", "human_gate.authorized_at")
    return current_gate


def authorize_human_gate(gate: Mapping[str, Any], *, authorized_at: str, authority_basis: str) -> dict[str, Any]:
    """Authorize only with an explicit non-technical owner decision."""

    current_gate = _validate_gate(gate)
    if current_gate.get("state") != "awaiting-human":
        _error("ILLEGAL_HUMAN_GATE_TRANSITION", "only an awaiting-human gate can be authorized", "human_gate.state")
    if not _VALIDATOR._is_iso(authorized_at):
        _error("HUMAN_GATE_TIMESTAMP", "authorized_at must be ISO-8601", "human_gate.authorized_at")
    if not isinstance(authority_basis, str) or not authority_basis.strip():
        _error("HUMAN_AUTHORIZATION_REQUIRED", "explicit authority basis is required", "human_gate.authority_basis")
    if not _has_explicit_human_authority(authority_basis):
        _error("HUMAN_AUTHORIZATION_REQUIRED", "technical access never constitutes authorization", "human_gate.authority_basis")
    current_gate["state"] = "authorized"
    current_gate["authorized_at"] = authorized_at
    current_gate["authority_basis"] = authority_basis.strip()
    return _validate_gate(current_gate)


def clear_control_outcome(
    state: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None = None,
    superseding_contract: Mapping[str, Any] | None = None,
    state_reconciliation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Clear a control outcome only with its defined resolution evidence."""

    result = _validate_state(state)
    outcome = result["control_outcome"]
    if outcome == "none":
        return result
    if outcome == "baseline-conflict":
        if not isinstance(superseding_contract, Mapping) or superseding_contract.get("accepted") is not True or not isinstance(superseding_contract.get("contract_id"), str) or not superseding_contract.get("contract_id").strip():
            _error("SUPERSEDING_CONTRACT_REQUIRED", "baseline-conflict requires an accepted superseding contract", "control_outcome")
    elif outcome == "needs-human-state-reconciliation":
        if not isinstance(state_reconciliation, Mapping) or state_reconciliation.get("recorded") is not True:
            _error("STATE_RECONCILIATION_REQUIRED", "state reconciliation must be recorded before clearing", "control_outcome")
        if not _VALIDATOR._is_redacted_ref(state_reconciliation.get("evidence_ref")):
            _error("CONTROL_CLEARING_EVIDENCE_REQUIRED", "state reconciliation requires redacted evidence", "control_outcome")
    else:
        if not isinstance(evidence, Mapping) or evidence.get("resolves") != outcome or not _VALIDATOR._is_redacted_ref(evidence.get("evidence_ref")):
            _error("CONTROL_CLEARING_EVIDENCE_REQUIRED", "direct evidence matching the control outcome is required", "control_outcome")
    result["control_outcome"] = "none"
    return _post_state(result)


def migrate_receipt(
    receipt: Mapping[str, Any],
    *,
    target_contract_version: str,
    migration: Mapping[str, Any] | Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify an explicit compatible migration without changing causal identity."""

    source = _validate_receipt(receipt)
    source_version = source["contract_version"]
    if source_version == target_contract_version:
        return source
    if source["status"] not in ("valid", "not-applicable"):
        _error("RECEIPT_MIGRATION_INVALID", "only a valid or explicit not-applicable receipt may be migrated", "receipt.status")
    if not isinstance(target_contract_version, str) or not re.fullmatch(r"ask-park\.receipt/v[0-9]+(?:[-.][A-Za-z0-9._-]+)?", target_contract_version):
        _error("CONTRACT_VERSION_UNSUPPORTED", "target receipt contract version is not a supported alias", "receipt.contract_version")
    if migration is None:
        _error("CONTRACT_MIGRATION_REQUIRED", "contract-version changes require an explicit migration", "receipt.contract_version")
    if callable(migration):
        _error("INCOMPATIBLE_CONTRACT", "migration metadata must explicitly prove compatibility and verification", "migration")
    if not isinstance(migration, Mapping):
        _error("INCOMPATIBLE_CONTRACT", "migration metadata must be an object", "migration")
    metadata = migration
    if metadata.get("compatible") is not True or metadata.get("preserves_causal_identity") is not True or metadata.get("verified") is not True:
        _error("INCOMPATIBLE_CONTRACT", "migration must explicitly prove compatibility and verification", "migration")
    transform = metadata.get("transform")
    migrated = _clone(source)
    if transform is not None:
        if not callable(transform):
            _error("INCOMPATIBLE_CONTRACT", "migration transform must be callable", "migration.transform")
        try:
            migrated = transform(_clone(migrated))
        except Exception:
            _error("MIGRATION_TRANSFORM_FAILED", "migration transform failed", "migration.transform")
        if not isinstance(migrated, dict):
            _error("INCOMPATIBLE_CONTRACT", "migration transform must return a receipt object", "migration.transform")
    if _causal_identity(migrated) != _causal_identity(source):
        _error("MIGRATION_CAUSAL_IDENTITY_CHANGED", "compatible migration changed a causal identity", "migration")
    # Validate the transformed shape against the source contract before
    # swapping the version. This keeps migration from becoming a persistence
    # boundary bypass even when the target contract is a future version.
    source_contract_candidate = _clone(migrated)
    source_contract_candidate["contract_version"] = source_version
    _validate_receipt(source_contract_candidate)
    migrated["contract_version"] = target_contract_version
    return _validate_receipt(migrated, allow_unknown_contract=True)


def migrate_contract(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility alias for callers using the contract-level name."""

    return migrate_receipt(*args, **kwargs)


# Descriptive aliases keep the public seam discoverable for later modules
# without creating a second implementation or a second state machine.
transition_module = transition_activity
transition_evidence_state = transition_evidence
invalidate_downstream = invalidate_receipts
clear_control = clear_control_outcome


def _read_json(path: Path) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("input contains duplicate JSON object key")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs)
    except OSError as exc:
        raise ValueError("input cannot be read") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("input is not valid JSON") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("transition-activity", "transition-evidence", "rewind"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--module")
    parser.add_argument("--to", dest="target", required=True)
    parser.add_argument("--reason-code", default="causal-identity-changed")
    parser.add_argument("--receipt-id", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        document = _read_json(args.input)
        if args.operation == "transition-activity":
            output = transition_activity(document, args.module, args.target)
        elif args.operation == "transition-evidence":
            output = transition_evidence(document, args.module, args.target)
        else:
            output = rewind_state(document, earliest_module=args.target, invalidated_receipt_ids=args.receipt_id, reason_code=args.reason_code)
    except (ValueError, LifecycleError) as exc:
        payload = {"ok": False, "error": {"code": getattr(exc, "code", "INPUT_INVALID"), "message": str(exc)}}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "result": output}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through CLI smoke tests
    sys.exit(main())
