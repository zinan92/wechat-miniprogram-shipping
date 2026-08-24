#!/usr/bin/env python3
"""Deterministic Ask Park routing and progress-map operations.

The router is the only staged component that selects the next module or asks
the lifecycle engine to invalidate dependent receipts.  It reads an explicit
S01 state record, never infers state from chat, never calls a provider, and
returns a new decision without mutating its input.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


_LIFECYCLE_PATH = Path(__file__).with_name("state-lifecycle.py")
_LIFECYCLE_SPEC = importlib.util.spec_from_file_location("ask_park_state_lifecycle_for_router", _LIFECYCLE_PATH)
if _LIFECYCLE_SPEC is None or _LIFECYCLE_SPEC.loader is None:  # pragma: no cover - packaging failure
    raise ImportError("cannot load the S01B lifecycle engine")
_LIFECYCLE = importlib.util.module_from_spec(_LIFECYCLE_SPEC)
_LIFECYCLE_SPEC.loader.exec_module(_LIFECYCLE)

MODULES: tuple[str, ...] = tuple(_LIFECYCLE.MODULES)
MODULE_LABELS = {
    "plan": "Plan",
    "build": "Build",
    "cloudbase": "CloudBase",
    "experience": "Experience",
    "device": "Device Acceptance",
    "release": "Release",
}
DIAGNOSE_LABEL = "Diagnose & Recover"
INTENTS = ("new", "takeover", "failure", "continuation", "release")
ROUTER_CONTROL_OUTCOMES = {
    "missing-evidence",
    "needs-human-state-reconciliation",
    "baseline-conflict",
    "blocked-external",
}


class RouterError(ValueError):
    """Stable, value-safe routing rejection."""

    def __init__(self, code: str, message: str, path: str = "router") -> None:
        self.code = code
        self.error_code = code
        self.path = path
        self.message = message
        super().__init__(f"{code}: {message}")


class RouteDecision:
    """A rendered routing decision plus the state Ask Park may carry forward."""

    __slots__ = (
        "intent", "current_module", "selected_module", "control_outcome",
        "reason_code", "state", "progress_map", "load_contracts",
        "next_verifiable_step", "decision_required", "diagnose_requested",
        "invalidated_receipt_ids",
    )

    def __init__(
        self,
        *,
        intent: str,
        current_module: str,
        selected_module: str,
        control_outcome: str | None,
        reason_code: str,
        state: dict[str, Any],
        progress_map: dict[str, dict[str, Any]],
        load_contracts: tuple[str, ...],
        next_verifiable_step: str,
        decision_required: str,
        diagnose_requested: bool = False,
        invalidated_receipt_ids: tuple[str, ...] = (),
    ) -> None:
        self.intent = intent
        self.current_module = current_module
        self.selected_module = selected_module
        self.control_outcome = control_outcome
        self.reason_code = reason_code
        self.state = state
        self.progress_map = progress_map
        self.load_contracts = load_contracts
        self.next_verifiable_step = next_verifiable_step
        self.decision_required = decision_required
        self.diagnose_requested = diagnose_requested
        self.invalidated_receipt_ids = invalidated_receipt_ids

    @property
    def conclusion(self) -> str:
        if self.control_outcome:
            return f"Routing is paused by `{self.control_outcome}`; Ask Park keeps `{self.current_module}` as the authoritative current module."
        return f"Ask Park routes this request to **{MODULE_LABELS[self.selected_module]}**."

    @property
    def rendered(self) -> str:
        return render_decision(self)

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "current_module": self.current_module,
            "selected_module": self.selected_module,
            "control_outcome": self.control_outcome,
            "reason_code": self.reason_code,
            "state": copy.deepcopy(self.state),
            "progress_map": copy.deepcopy(self.progress_map),
            "load_contracts": list(self.load_contracts),
            "next_verifiable_step": self.next_verifiable_step,
            "decision_required": self.decision_required,
            "diagnose_requested": self.diagnose_requested,
            "invalidated_receipt_ids": list(self.invalidated_receipt_ids),
            "rendered": self.rendered,
        }

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]


def _error(code: str, message: str, path: str = "router") -> None:
    raise RouterError(code, message, path)


def classify_intent(request: str | Mapping[str, Any]) -> str:
    """Classify only the request shape; state always comes from a record."""

    if isinstance(request, Mapping):
        explicit = request.get("intent")
        if isinstance(explicit, str):
            if explicit in INTENTS:
                return explicit
            _error("ROUTER_INTENT_UNKNOWN", "intent is outside the Ask Park route enum", "request.intent")
        request = request.get("request", "")
    if not isinstance(request, str) or not request.strip():
        _error("ROUTER_INTENT_UNCLASSIFIED", "request needs one explicit Ask Park route class", "request")
    text = request.strip().lower()
    terms = {
        "new": ("new", "create", "新建", "从零", "想做"),
        "takeover": ("takeover", "take over", "接手", "已有项目", "迁移"),
        "failure": ("failure", "bug", "error", "broken", "报错", "失败", "阻塞", "异常"),
        "continuation": ("continue", "continuation", "resume", "继续", "恢复", "接着"),
        "release": ("release", "publish", "上线", "发布", "提审"),
    }
    hits = {intent for intent, candidates in terms.items() if any(candidate in text for candidate in candidates)}
    if len(hits) > 1:
        _error("ROUTER_INTENT_AMBIGUOUS", "request matches more than one Ask Park route class", "request")
    if not hits:
        _error("ROUTER_INTENT_UNCLASSIFIED", "request needs one explicit Ask Park route class", "request")
    return next(iter(hits))


def _validate_state(state: Any) -> dict[str, Any]:
    try:
        return _LIFECYCLE._validate_state(state)
    except _LIFECYCLE.LifecycleError as exc:
        _error("ROUTER_STATE_INVALID", "state does not satisfy the lifecycle contract", "state")
    raise AssertionError("unreachable")  # pragma: no cover


def _record(state: Mapping[str, Any], module: str) -> Mapping[str, Any]:
    if module not in MODULES:
        _error("ROUTER_UNKNOWN_MODULE", "module is not a sequential Ask Park module", "state.current_module")
    value = state.get("modules", {}).get(module)
    if not isinstance(value, Mapping):
        _error("ROUTER_STATE_INVALID", "module record is not an object", "state.modules.<module>")
    return value


def _earliest_required_gap(state: Mapping[str, Any]) -> str:
    for module in MODULES:
        record = _record(state, module)
        if record["applicability"] != "required":
            continue
        if record["activity_state"] != "completed" or record["evidence_state"] != "valid":
            return module
    return str(state["current_module"])


def _progress_map(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    current = state["current_module"]
    result: dict[str, dict[str, Any]] = {}
    for module in MODULES:
        record = _record(state, module)
        result[module] = {
            "label": MODULE_LABELS[module],
            "applicability": record["applicability"],
            "activity_state": record["activity_state"],
            "evidence_state": record["evidence_state"],
            "current": module == current,
        }
    diagnose = state["diagnose"]
    result["diagnose"] = {
        "label": DIAGNOSE_LABEL,
        "state": diagnose["state"],
        "outcome": diagnose["outcome"],
        "active": diagnose["state"] == "active",
    }
    return result


def _load_contracts(selected_module: str, diagnose_requested: bool) -> tuple[str, ...]:
    paths = [
        "references/router.md",
        "references/status-contract.md",
        "references/evidence-contract.md",
        "references/human-gates-contract.md",
        "references/transition-contract.md",
    ]
    if diagnose_requested:
        paths.append("modules/07-diagnose/MODULE.md")
    module_path = {
        "plan": "modules/01-plan/MODULE.md",
        "build": "modules/02-build/MODULE.md",
        "cloudbase": "modules/03-cloudbase/MODULE.md",
        "experience": "modules/04-experience/MODULE.md",
        "device": "modules/05-device/MODULE.md",
        "release": "modules/06-release/MODULE.md",
    }[selected_module]
    paths.append(module_path)
    return tuple(paths)


def _next_step(module: str, control_outcome: str | None, diagnose_requested: bool) -> str:
    if control_outcome == "needs-human-state-reconciliation":
        return "Reconcile the competing state sources and record the human state-reconciliation evidence."
    if control_outcome == "baseline-conflict":
        return "Obtain and record an accepted superseding contract before changing the route."
    if control_outcome == "blocked-external":
        return "Complete the named human/platform gate; technical access alone is not authorization."
    if diagnose_requested:
        return "Load Diagnose & Recover, record one falsifiable recovery goal, and keep the interrupted module current."
    if control_outcome == "missing-evidence":
        if module == "build":
            return "Load the Build contract and establish its first valid evidence receipt."
        return f"Load the {MODULE_LABELS[module]} contract and establish its first valid evidence receipt."
    return f"Load the {MODULE_LABELS[module]} contract and complete its smallest verifiable action."


def _decision_required(control_outcome: str | None, diagnose_requested: bool) -> str:
    if control_outcome == "needs-human-state-reconciliation":
        return "Park must choose the authoritative state source."
    if control_outcome == "baseline-conflict":
        return "Park must accept a superseding contract or keep the baseline."
    if control_outcome == "blocked-external":
        return "Park must provide or explicitly authorize the required human/platform action."
    if diagnose_requested:
        return "Park must confirm the bounded recovery goal before repair work begins."
    return "No new authority is inferred; proceed only with the selected module contract."


def route(
    state: Mapping[str, Any],
    intent: str | Mapping[str, Any],
    *,
    source_conflict: bool = False,
    baseline_conflict: bool = False,
    authority_required: bool = False,
    failure_module: str | None = None,
    receipts: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
    changed_fields: Iterable[str] = (),
    reason_code: str = "causal-identity-changed",
) -> RouteDecision:
    """Classify, validate, optionally rewind, and render one router decision."""

    route_intent = classify_intent(intent)
    next_state = _validate_state(state)
    invalidated_receipt_ids: tuple[str, ...] = ()
    changed = tuple(str(field) for field in changed_fields)
    control_outcome: str | None = None
    reason = "earliest-required-gap"

    if changed:
        if receipts is None:
            control_outcome = "needs-human-state-reconciliation"
            reason = "causal-receipt-missing"
        else:
            try:
                next_state, invalidation = _LIFECYCLE.invalidate_state(
                    next_state,
                    receipts,
                    changed_fields=changed,
                    reason_code=reason_code,
                )
                invalidated_receipt_ids = tuple(invalidation.invalidated_receipt_ids)
                if invalidated_receipt_ids:
                    reason = "causal-invalidation-rewind"
            except _LIFECYCLE.LifecycleError:
                control_outcome = "needs-human-state-reconciliation"
                reason = "causal-receipt-invalid"

    if source_conflict:
        control_outcome = "needs-human-state-reconciliation"
        reason = "conflicting-state-sources"
    elif baseline_conflict:
        control_outcome = "baseline-conflict"
        reason = "accepted-baseline-conflict"
    elif authority_required:
        control_outcome = "blocked-external"
        reason = "human-authority-required"
    elif next_state.get("control_outcome") != "none":
        control_outcome = str(next_state["control_outcome"])
        reason = "state-control-outcome"

    current_module = str(next_state["current_module"])
    diagnose_requested = route_intent == "failure"
    if failure_module is not None:
        if failure_module not in MODULES:
            _error("ROUTER_UNKNOWN_MODULE", "failure module is not sequential", "failure_module")
        if failure_module != current_module:
            control_outcome = "needs-human-state-reconciliation"
            reason = "failure-current-mismatch"
            diagnose_requested = False
    selected_module = current_module

    if control_outcome is None:
        project_state = next_state.get("project_state")
        if project_state == "released":
            selected_module = "release"
            reason = "formal-release-complete"
        elif project_state in ("target-achieved", "abandoned"):
            selected_module = current_module
            reason = "terminal-project-state"
        else:
            current_record = _record(next_state, current_module)
            if current_record["activity_state"] == "blocked-external":
                selected_module = current_module
                control_outcome = "blocked-external"
                reason = "current-module-blocked-external"
            elif current_record["activity_state"] == "failed":
                selected_module = current_module
                reason = "current-module-failed"
            else:
                selected_module = _earliest_required_gap(next_state)
                selected_record = _record(next_state, selected_module)
                if selected_record["activity_state"] != "completed" or selected_record["evidence_state"] != "valid":
                    control_outcome = "missing-evidence"
                    reason = "missing-module-evidence"
            if route_intent == "release" and selected_module != "release":
                reason = "release-prerequisite-missing"
    elif route_intent == "failure" and failure_module is not None:
        selected_module = current_module

    progress = _progress_map(next_state)
    contracts = _load_contracts(selected_module, diagnose_requested)
    return RouteDecision(
        intent=route_intent,
        current_module=current_module,
        selected_module=selected_module,
        control_outcome=control_outcome,
        reason_code=reason,
        state=copy.deepcopy(next_state),
        progress_map=progress,
        load_contracts=contracts,
        next_verifiable_step=_next_step(selected_module, control_outcome, diagnose_requested),
        decision_required=_decision_required(control_outcome, diagnose_requested),
        diagnose_requested=diagnose_requested,
        invalidated_receipt_ids=invalidated_receipt_ids,
    )


def render_decision(decision: RouteDecision) -> str:
    """Render the compact map followed by the four operator sections."""

    lines = ["ASK PARK · MINI PROGRAM SHIPPING", ""]
    for index, module in enumerate(MODULES, start=1):
        item = decision.progress_map[module]
        marker = item["activity_state"]
        if item["current"] and marker != "current":
            marker = f"{marker} (current)"
        lines.append(f"{index}. {item['label']:<18} {marker:<16} [evidence {item['evidence_state']}]")
    diagnose = decision.progress_map["diagnose"]
    lines.extend(
        [
            "",
            f"7. {DIAGNOSE_LABEL:<18} {diagnose['state']:<16} [outcome {diagnose['outcome']}]",
            "",
            "## 1. Conclusion",
            decision.conclusion,
            "",
            "## 2. Current module and evidence",
            f"Current module: **{MODULE_LABELS[decision.current_module]}** (`{decision.current_module}`).",
            f"Selected route: **{MODULE_LABELS[decision.selected_module]}**; reason: `{decision.reason_code}`.",
            "",
            "## 3. Decision or action needed from Park",
            decision.decision_required,
            "",
            "## 4. Next verifiable step",
            decision.next_verifiable_step,
        ]
    )
    return "\n".join(lines)


def _read_json(path: Path) -> Any:
    return _LIFECYCLE._read_json(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--source-conflict", action="store_true")
    parser.add_argument("--baseline-conflict", action="store_true")
    parser.add_argument("--authority-required", action="store_true")
    parser.add_argument("--changed-field", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        decision = route(
            _read_json(args.input),
            args.intent,
            source_conflict=args.source_conflict,
            baseline_conflict=args.baseline_conflict,
            authority_required=args.authority_required,
            changed_fields=args.changed_field,
        )
    except (ValueError, RouterError) as exc:
        payload = {"ok": False, "error": {"code": getattr(exc, "code", "INPUT_INVALID"), "message": str(exc)}}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "result": decision.as_dict()}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
