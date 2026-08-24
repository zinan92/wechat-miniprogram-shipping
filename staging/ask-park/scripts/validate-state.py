#!/usr/bin/env python3
"""Validate the versioned Ask Park state, receipt, and human-gate contracts.

This validator deliberately uses only the JSON data model and Python's standard
library. It validates persisted contract records; it does not call a provider,
inspect a repository, or infer a state transition. QA manifests and QA result
records belong to S10 and are rejected here rather than being silently accepted
as generic evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
STATE_CONTRACT_VERSION = "ask-park.state/v1"
RECEIPT_CONTRACT_VERSION = "ask-park.receipt/v1"
HUMAN_GATE_CONTRACT_VERSION = "ask-park.human-gate/v1"

MODULES = ("plan", "build", "cloudbase", "experience", "device", "release")
APPLICABILITY = ("required", "not-applicable")
ACTIVITY_STATES = ("waiting", "current", "completed", "failed", "blocked-external", "locked", "not-applicable")
EVIDENCE_STATES = ("absent", "valid", "stale", "invalid", "not-applicable")
DIAGNOSE_STATES = ("standby", "active")
DIAGNOSE_OUTCOMES = ("none", "unresolved", "recovered", "blocked-external")
CONTROL_OUTCOMES = ("none", "unknown", "baseline-conflict", "needs-human-state-reconciliation", "blocked-external")
TERMINAL_STATES = ("none", "target-achieved", "released", "abandoned")
PROJECT_STATES = ("active", "target-achieved", "released", "abandoned")
RECEIPT_STATUSES = ("valid", "stale", "invalid", "not-applicable")
HUMAN_GATE_STATES = (
    "not-needed",
    "prepared",
    "awaiting-human",
    "authorized",
    "executed",
    "read-back",
    "denied",
    "expired",
)

SHA_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{7,64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")

# These fields would turn a persisted record into a credential or a complete
# target. Aliases and ``redacted_ref`` are the only durable target references.
SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "openid",
    "credential",
    "private_key",
    "access_key",
    "api_key",
    "cookie",
)
PRIVATE_TARGET_KEYS = {
    "url",
    "uri",
    "target_url",
    "environment_id",
    "env_id",
    "appid",
    "app_id",
    "appsecret",
}
FORBIDDEN_QA_KEYS = {
    "candidate_manifest",
    "target_manifest",
    "qa_manifest",
    "qa_result",
    "qa_run_id",
    "jcs_digest",
}
FORBIDDEN_NEXT_MODULE = "next_module"
SAFE_PATH_KEYS = {
    "schema_version",
    "contract_version",
    "project_id",
    "project_state",
    "project_terminal_state",
    "current_module",
    "control_outcome",
    "modules",
    "applicability",
    "activity_state",
    "evidence_state",
    "receipt_id",
    "not_applicable_reason",
    "diagnose",
    "state",
    "outcome",
    "interrupted_module",
    "recovery_goal",
    "human_gate",
    "gate_id",
    "action_type",
    "action_scope",
    "authorizing_role",
    "requested_at",
    "authorized_at",
    "evidence_ref",
    "authority_basis",
    "rewind",
    "active",
    "earliest_invalidated_module",
    "reason_code",
    "invalidated_receipt_ids",
    "receipt_id",
    "receipt_type",
    "module",
    "status",
    "source",
    "repository_alias",
    "commit_sha",
    "issue",
    "id",
    "predecessor_receipt_ids",
    "artifact",
    "package",
    "kind",
    "alias",
    "digest",
    "target",
    "url",
    "uri",
    "target_url",
    "environment_id",
    "env_id",
    "appid",
    "app_id",
    "appsecret",
    "credential",
    "environment_contract_alias",
    "redacted_ref",
    "invalidation_rules",
    "on",
    "downstream_modules",
    "causal_rewind",
    "declared_by",
    "stale_reason",
    "invalid_reason",
    "issued_at",
    "evidence_refs",
    *FORBIDDEN_QA_KEYS,
    FORBIDDEN_NEXT_MODULE,
}


class ValidationError:
    __slots__ = ("code", "path", "message")

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message


class ValidationResult:
    __slots__ = ("kind", "document", "errors")

    def __init__(self, kind: str, document: dict[str, Any], errors: tuple[ValidationError, ...]) -> None:
        self.kind = kind
        self.document = document
        self.errors = errors

    @property
    def valid(self) -> bool:
        return not self.errors


class _Collector:
    def __init__(self) -> None:
        self.errors: list[ValidationError] = []

    def add(self, code: str, path: str, message: str) -> None:
        self.errors.append(ValidationError(code, path, message))

    def required(self, document: dict[str, Any], keys: Iterable[str], prefix: str, code: str) -> None:
        for key in keys:
            if key not in document:
                self.add(code, f"{prefix}.{key}" if prefix else key, "required field is missing")


def _is_mapping(value: Any) -> bool:
    return isinstance(value, dict)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _is_iso(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_RE.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _is_redacted_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("redacted:") and len(value) > len("redacted:")


def _walk_persistence_boundary(value: Any, path: str, errors: _Collector) -> None:
    """Reject secret/private/QA records before type-specific validation.

    Error messages include only the structural key path. Values are never
    copied into errors or CLI output, which keeps the validator safe when fed a
    malformed record containing an accidental secret.
    """

    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            path_key = key_text if key_text in SAFE_PATH_KEYS or key_text in MODULES else "<key>"
            child_path = f"{path}.{path_key}" if path else path_key
            if normalized == FORBIDDEN_NEXT_MODULE:
                errors.add("FORBIDDEN_NEXT_MODULE", child_path, "receipts cannot prescribe a next module")
            if normalized in FORBIDDEN_QA_KEYS:
                errors.add("FORBIDDEN_QA_SCHEMA", child_path, "QA manifest/result records belong to S10")
            if normalized in PRIVATE_TARGET_KEYS:
                errors.add("PRIVATE_TARGET", child_path, "complete private target values are not persistable")
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                errors.add("SENSITIVE_FIELD", child_path, "credential or private identity fields are not persistable")
            _walk_persistence_boundary(child, child_path, errors)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _walk_persistence_boundary(child, f"{path}[{index}]", errors)
        return
    if isinstance(value, str):
        lower = value.lower()
        if lower.startswith(("http://", "https://", "file://", "/", "~/")):
            errors.add("PRIVATE_TARGET", path, "complete URLs or filesystem targets are not persistable")


def _check_schema_version(document: dict[str, Any], prefix: str, errors: _Collector) -> None:
    value = document.get("schema_version")
    if isinstance(value, bool) or not isinstance(value, int):
        errors.add("SCHEMA_VERSION", f"{prefix}.schema_version", "schema_version must be an integer")
    elif value != SCHEMA_VERSION:
        errors.add("SCHEMA_VERSION_UNSUPPORTED", f"{prefix}.schema_version", "unsupported schema version")


def _check_contract_version(document: dict[str, Any], expected: str, prefix: str, errors: _Collector) -> None:
    if document.get("contract_version") != expected:
        errors.add("CONTRACT_VERSION", f"{prefix}.contract_version", "unexpected contract version")


def _check_enum(document: dict[str, Any], key: str, choices: Iterable[str], prefix: str, errors: _Collector, code: str = "STATE_ENUM") -> None:
    value = document.get(key)
    if value not in choices:
        errors.add(code, f"{prefix}.{key}", "value is outside the contract enum")


def _validate_human_gate_fields(document: Any, prefix: str, errors: _Collector, *, standalone: bool = False) -> None:
    if not _is_mapping(document):
        errors.add("HUMAN_GATE_TYPE", prefix, "human gate must be an object")
        return
    if standalone:
        _check_schema_version(document, prefix, errors)
        _check_contract_version(document, HUMAN_GATE_CONTRACT_VERSION, prefix, errors)
        errors.required(
            document,
            ("gate_id", "action_type", "action_scope", "authorizing_role", "requested_at", "evidence_ref"),
            prefix,
            "HUMAN_GATE_REQUIRED_FIELD",
        )
        if not _safe_identifier(document.get("gate_id")):
            errors.add("HUMAN_GATE_ID", f"{prefix}.gate_id", "gate_id must be a stable alias")
        if not _is_nonempty_string(document.get("action_type")):
            errors.add("HUMAN_GATE_SCOPE", f"{prefix}.action_type", "action_type must be non-empty")

    state = document.get("state")
    if state not in HUMAN_GATE_STATES:
        errors.add("HUMAN_GATE_STATE", f"{prefix}.state", "state is outside the human-gate enum")
        return

    scope = document.get("action_scope")
    role = document.get("authorizing_role")
    requested_at = document.get("requested_at")
    authorized_at = document.get("authorized_at")
    evidence_ref = document.get("evidence_ref")

    if state == "not-needed":
        for key in ("action_scope", "authorizing_role", "requested_at", "authorized_at", "evidence_ref"):
            if document.get(key) is not None:
                errors.add("HUMAN_GATE_NOT_NEEDED", f"{prefix}.{key}", "not-needed gates cannot carry authorization data")
        return

    for key, value in (("action_scope", scope), ("authorizing_role", role)):
        if not _is_nonempty_string(value):
            errors.add("HUMAN_GATE_REQUIRED_FIELD", f"{prefix}.{key}", "active gate requires this field")
    if not _is_iso(requested_at):
        errors.add("HUMAN_GATE_TIMESTAMP", f"{prefix}.requested_at", "requested_at must be an ISO-8601 timestamp")
    if not _is_redacted_ref(evidence_ref):
        errors.add("HUMAN_GATE_EVIDENCE", f"{prefix}.evidence_ref", "evidence_ref must be redacted")
    if state in ("authorized", "executed", "read-back") and not _is_iso(authorized_at):
        errors.add("HUMAN_GATE_TIMESTAMP", f"{prefix}.authorized_at", "authorized gate requires authorized_at")
    if state in ("prepared", "awaiting-human", "denied", "expired") and authorized_at is not None:
        errors.add("HUMAN_GATE_TIMESTAMP", f"{prefix}.authorized_at", "gate is not authorized in this state")
    authority_basis = document.get("authority_basis")
    if authority_basis is not None and (not _is_nonempty_string(authority_basis)):
        errors.add("HUMAN_GATE_AUTHORITY", f"{prefix}.authority_basis", "authority_basis must be non-empty when present")
    if isinstance(authority_basis, str) and re.search(r"authenticated|cli|access|permission|login|capability", authority_basis, re.I):
        errors.add("HUMAN_GATE_AUTHORITY", f"{prefix}.authority_basis", "technical access never constitutes authorization")


def validate_state(document: Any) -> ValidationResult:
    errors = _Collector()
    if not _is_mapping(document):
        errors.add("STATE_TYPE", "state", "state must be a JSON object")
        return ValidationResult("state", {}, tuple(errors.errors))

    _walk_persistence_boundary(document, "", errors)
    errors.required(
        document,
        (
            "schema_version",
            "contract_version",
            "project_id",
            "current_module",
            "control_outcome",
            "modules",
            "diagnose",
            "human_gate",
            "rewind",
        ),
        "state",
        "STATE_REQUIRED_FIELD",
    )
    _check_schema_version(document, "state", errors)
    _check_contract_version(document, STATE_CONTRACT_VERSION, "state", errors)
    if not _safe_identifier(document.get("project_id")):
        errors.add("STATE_PROJECT_ID", "state.project_id", "project_id must be a non-sensitive stable alias")
    _check_enum(document, "current_module", MODULES, "state", errors, "STATE_CURRENT_MODULE")
    # The architecture spec calls this axis ``project_state`` while the issue
    # wording calls it the project terminal state. Accept both spellings at the
    # boundary, but require at least one and reject contradictory records. The
    # canonical output emitted by later stories can choose one spelling.
    has_project_state = "project_state" in document
    has_terminal_state = "project_terminal_state" in document
    if not has_project_state and not has_terminal_state:
        errors.add("STATE_REQUIRED_FIELD", "state.project_state", "project state axis is required")
    if has_project_state:
        _check_enum(document, "project_state", PROJECT_STATES, "state", errors)
    if has_terminal_state:
        _check_enum(document, "project_terminal_state", TERMINAL_STATES, "state", errors)
    project_state = document.get("project_state")
    terminal_state = document.get("project_terminal_state")
    if has_project_state and has_terminal_state:
        expected_terminal = "none" if project_state == "active" else project_state
        if terminal_state != expected_terminal:
            errors.add("STATE_TERMINAL", "state.project_state", "project_state and project_terminal_state disagree")
    elif has_project_state:
        terminal_state = "none" if project_state == "active" else project_state
    _check_enum(document, "control_outcome", CONTROL_OUTCOMES, "state", errors)

    modules = document.get("modules")
    if not _is_mapping(modules):
        errors.add("STATE_MODULES_TYPE", "state.modules", "modules must be an object")
        modules = {}
    for module in MODULES:
        if module not in modules:
            errors.add("STATE_REQUIRED_FIELD", f"state.modules.{module}", "module axis is required")
    for module in modules:
        if module not in MODULES:
            errors.add("STATE_MODULE", f"state.modules.{module}", "unknown sequential module")
    for module in MODULES:
        record = modules.get(module)
        prefix = f"state.modules.{module}"
        if not _is_mapping(record):
            errors.add("STATE_MODULE_TYPE", prefix, "module axis must be an object")
            continue
        errors.required(record, ("applicability", "activity_state", "evidence_state", "receipt_id"), prefix, "STATE_REQUIRED_FIELD")
        _check_enum(record, "applicability", APPLICABILITY, prefix, errors)
        _check_enum(record, "activity_state", ACTIVITY_STATES, prefix, errors)
        _check_enum(record, "evidence_state", EVIDENCE_STATES, prefix, errors)
        applicability = record.get("applicability")
        if applicability == "not-applicable":
            if record.get("activity_state") != "not-applicable":
                errors.add("STATE_NOT_APPLICABLE", f"{prefix}.activity_state", "not-applicable module must have not-applicable activity")
            if record.get("evidence_state") != "not-applicable":
                errors.add("STATE_NOT_APPLICABLE", f"{prefix}.evidence_state", "not-applicable module must have not-applicable evidence")
            if not _is_nonempty_string(record.get("not_applicable_reason")):
                errors.add("STATE_NOT_APPLICABLE", f"{prefix}.not_applicable_reason", "not-applicable requires an explicit reason")
        elif record.get("activity_state") == "not-applicable" or record.get("evidence_state") == "not-applicable":
            errors.add("STATE_NOT_APPLICABLE", prefix, "required module cannot carry not-applicable state")
        receipt_id = record.get("receipt_id")
        if receipt_id is not None and not _safe_identifier(receipt_id):
            errors.add("STATE_RECEIPT_ID", f"{prefix}.receipt_id", "receipt_id must be a stable alias or null")

    current_module = document.get("current_module")
    if current_module in MODULES and _is_mapping(modules.get(current_module)):
        current_record = modules[current_module]
        if current_record.get("applicability") == "required" and current_record.get("activity_state") not in ("current", "failed", "blocked-external"):
            errors.add("STATE_CURRENT_MODULE", "state.current_module", "current module must remain current, failed, or blocked-external")
    active_records = [module for module in MODULES if _is_mapping(modules.get(module)) and modules[module].get("activity_state") == "current"]
    if len(active_records) > 1:
        errors.add("STATE_CURRENT_MODULE", "state.modules", "only one module may be current")
    if current_module in MODULES and active_records and active_records != [current_module]:
        errors.add("STATE_CURRENT_MODULE", "state.current_module", "current_module disagrees with module activity axis")

    # A stale/invalid predecessor is a causal rewind, not a reason to leave a
    # later module current. S01 only validates the declaration; S01B performs
    # the actual invalidation closure.
    invalidated = [
        module
        for module in MODULES
        if _is_mapping(modules.get(module))
        and modules[module].get("applicability") == "required"
        and modules[module].get("evidence_state") in ("stale", "invalid")
    ]
    rewind = document.get("rewind")
    if not _is_mapping(rewind):
        errors.add("STATE_REWIND", "state.rewind", "rewind must be an object")
    else:
        errors.required(rewind, ("active", "earliest_invalidated_module", "reason_code", "invalidated_receipt_ids"), "state.rewind", "STATE_REQUIRED_FIELD")
        if not isinstance(rewind.get("active"), bool):
            errors.add("STATE_REWIND", "state.rewind.active", "active must be boolean")
        if invalidated:
            earliest = min(invalidated, key=MODULES.index)
            if not rewind.get("active") or rewind.get("earliest_invalidated_module") != earliest or current_module != earliest:
                errors.add("STATE_REWIND_REQUIRED", "state.rewind", "stale/invalid evidence requires a rewind to the earliest invalidated module")
        elif rewind.get("active"):
            errors.add("STATE_REWIND", "state.rewind", "active rewind requires stale or invalid module evidence")
        if rewind.get("active"):
            if rewind.get("earliest_invalidated_module") not in MODULES:
                errors.add("STATE_REWIND", "state.rewind.earliest_invalidated_module", "rewind module must be sequential module")
            if not _is_nonempty_string(rewind.get("reason_code")):
                errors.add("STATE_REWIND", "state.rewind.reason_code", "active rewind requires reason_code")
            ids = rewind.get("invalidated_receipt_ids")
            if not isinstance(ids, list) or any(not _safe_identifier(item) for item in ids):
                errors.add("STATE_REWIND", "state.rewind.invalidated_receipt_ids", "rewind receipt ids must be stable aliases")
        else:
            if rewind.get("earliest_invalidated_module") is not None or rewind.get("reason_code") is not None or rewind.get("invalidated_receipt_ids"):
                errors.add("STATE_REWIND", "state.rewind", "inactive rewind cannot carry invalidation details")

    diagnose = document.get("diagnose")
    if not _is_mapping(diagnose):
        errors.add("DIAGNOSE_TYPE", "state.diagnose", "diagnose must be an object")
    else:
        errors.required(diagnose, ("state", "outcome", "interrupted_module", "recovery_goal"), "state.diagnose", "STATE_REQUIRED_FIELD")
        _check_enum(diagnose, "state", DIAGNOSE_STATES, "state.diagnose", errors, "DIAGNOSE_STATE")
        _check_enum(diagnose, "outcome", DIAGNOSE_OUTCOMES, "state.diagnose", errors, "DIAGNOSE_OUTCOME")
        interrupted = diagnose.get("interrupted_module")
        if interrupted is not None and interrupted not in MODULES:
            errors.add("DIAGNOSE_MODULE", "state.diagnose.interrupted_module", "interrupted module must be sequential module")
        if diagnose.get("state") == "standby" and diagnose.get("outcome") != "none":
            errors.add("DIAGNOSE_STATE", "state.diagnose", "standby Diagnose must have outcome none")
        if diagnose.get("state") == "active" and interrupted is None:
            errors.add("DIAGNOSE_MODULE", "state.diagnose.interrupted_module", "active Diagnose requires interrupted module")

    _validate_human_gate_fields(document.get("human_gate"), "state.human_gate", errors)

    terminal = terminal_state
    if terminal == "released":
        release = modules.get("release")
        if not _is_mapping(release) or release.get("activity_state") != "completed" or release.get("evidence_state") != "valid":
            errors.add("STATE_TERMINAL", "state.project_terminal_state", "released requires completed valid Release evidence")
        if current_module != "release":
            errors.add("STATE_TERMINAL", "state.current_module", "released state retains current_module release")

    return ValidationResult("state", dict(document), tuple(errors.errors))


def _validate_receipt_component(document: dict[str, Any], key: str, prefix: str, errors: _Collector, *, not_applicable: bool) -> None:
    value = document.get(key)
    if not _is_mapping(value):
        errors.add("RECEIPT_TYPE", f"{prefix}.{key}", "component must be an object")
        return
    if not_applicable:
        if value.get("state") != "not-applicable" or not _is_nonempty_string(value.get("reason")):
            errors.add("RECEIPT_NOT_APPLICABLE", f"{prefix}.{key}", "not-applicable component requires state and reason")
        return
    errors.required(value, ("kind", "alias", "digest"), f"{prefix}.{key}", "RECEIPT_REQUIRED_FIELD")
    if not _is_nonempty_string(value.get("kind")) or not _safe_identifier(value.get("alias")):
        errors.add("RECEIPT_COMPONENT", f"{prefix}.{key}", "component kind and alias must be stable")
    if not _is_digest(value.get("digest")):
        errors.add("RECEIPT_DIGEST", f"{prefix}.{key}.digest", "component digest must be a SHA-256 identity")


def validate_receipt(document: Any) -> ValidationResult:
    errors = _Collector()
    if not _is_mapping(document):
        errors.add("RECEIPT_TYPE", "receipt", "receipt must be a JSON object")
        return ValidationResult("receipt", {}, tuple(errors.errors))
    _walk_persistence_boundary(document, "", errors)
    errors.required(
        document,
        (
            "receipt_id",
            "receipt_type",
            "schema_version",
            "contract_version",
            "module",
            "status",
            "applicability",
            "source",
            "issue",
            "predecessor_receipt_ids",
            "artifact",
            "package",
            "target",
            "invalidation_rules",
            "issued_at",
        ),
        "receipt",
        "RECEIPT_REQUIRED_FIELD",
    )
    _check_schema_version(document, "receipt", errors)
    _check_contract_version(document, RECEIPT_CONTRACT_VERSION, "receipt", errors)
    if document.get("receipt_type") != "module":
        errors.add("RECEIPT_TYPE", "receipt.receipt_type", "only module receipts are defined by S01")
    if not _safe_identifier(document.get("receipt_id")):
        errors.add("RECEIPT_ID", "receipt.receipt_id", "receipt_id must be a stable alias")
    if document.get("module") not in MODULES:
        errors.add("RECEIPT_MODULE", "receipt.module", "module must be a sequential module")
    if document.get("status") not in RECEIPT_STATUSES:
        errors.add("RECEIPT_STATUS", "receipt.status", "status is outside the receipt enum")
    if document.get("applicability") not in APPLICABILITY:
        errors.add("RECEIPT_APPLICABILITY", "receipt.applicability", "applicability is outside the contract enum")
    not_applicable = document.get("status") == "not-applicable" or document.get("applicability") == "not-applicable"
    if not_applicable:
        if document.get("status") != "not-applicable" or document.get("applicability") != "not-applicable":
            errors.add("RECEIPT_NOT_APPLICABLE", "receipt", "not-applicable status and applicability must agree")
        if not _is_nonempty_string(document.get("not_applicable_reason")):
            errors.add("RECEIPT_NOT_APPLICABLE", "receipt.not_applicable_reason", "not-applicable receipt requires explicit reason")
    elif document.get("status") == "stale" and not _is_nonempty_string(document.get("stale_reason")):
        errors.add("RECEIPT_STALE", "receipt.stale_reason", "stale receipt requires stale_reason")
    elif document.get("status") == "invalid" and not _is_nonempty_string(document.get("invalid_reason")):
        errors.add("RECEIPT_INVALID", "receipt.invalid_reason", "invalid receipt requires invalid_reason")

    source = document.get("source")
    if not _is_mapping(source):
        errors.add("RECEIPT_SOURCE", "receipt.source", "source must be an object")
    else:
        errors.required(source, ("repository_alias", "commit_sha"), "receipt.source", "RECEIPT_REQUIRED_FIELD")
        if not _safe_identifier(source.get("repository_alias")):
            errors.add("RECEIPT_SOURCE", "receipt.source.repository_alias", "repository_alias must be a stable alias")
        if not _is_digest(source.get("commit_sha")):
            errors.add("RECEIPT_SOURCE", "receipt.source.commit_sha", "commit_sha must be a SHA identity")
    issue = document.get("issue")
    if not _is_mapping(issue):
        errors.add("RECEIPT_ISSUE", "receipt.issue", "issue must be an object")
    elif not _safe_identifier(str(issue.get("id", ""))):
        errors.add("RECEIPT_ISSUE", "receipt.issue.id", "issue id must be a stable alias")
    predecessors = document.get("predecessor_receipt_ids")
    if not isinstance(predecessors, list) or any(not _safe_identifier(item) for item in predecessors):
        errors.add("RECEIPT_PREDECESSORS", "receipt.predecessor_receipt_ids", "predecessors must be stable receipt aliases")
    elif len(set(predecessors)) != len(predecessors):
        errors.add("RECEIPT_PREDECESSORS", "receipt.predecessor_receipt_ids", "predecessors must be unique")

    _validate_receipt_component(document, "artifact", "receipt", errors, not_applicable=not_applicable)
    _validate_receipt_component(document, "package", "receipt", errors, not_applicable=not_applicable)
    target = document.get("target")
    if not _is_mapping(target):
        errors.add("RECEIPT_TARGET", "receipt.target", "target must be an object")
    elif not_applicable:
        if target.get("state") != "not-applicable" or not _safe_identifier(target.get("alias")) or not _is_redacted_ref(target.get("redacted_ref")):
            errors.add("RECEIPT_TARGET", "receipt.target", "not-applicable target requires alias and redacted_ref")
    else:
        errors.required(target, ("alias", "environment_contract_alias", "redacted_ref"), "receipt.target", "RECEIPT_REQUIRED_FIELD")
        if not _safe_identifier(target.get("alias")) or not _safe_identifier(target.get("environment_contract_alias")):
            errors.add("RECEIPT_TARGET", "receipt.target", "target aliases must be stable")
        if not _is_redacted_ref(target.get("redacted_ref")):
            errors.add("RECEIPT_TARGET", "receipt.target.redacted_ref", "target must be represented by redacted_ref")

    invalidation = document.get("invalidation_rules")
    if not _is_mapping(invalidation):
        errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules", "invalidation_rules must be an object")
    else:
        errors.required(invalidation, ("on", "downstream_modules", "causal_rewind", "declared_by"), "receipt.invalidation_rules", "RECEIPT_REQUIRED_FIELD")
        on = invalidation.get("on")
        if not isinstance(on, list) or not on or any(not _is_nonempty_string(item) for item in on):
            errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules.on", "invalidation triggers must be non-empty strings")
        downstream = invalidation.get("downstream_modules")
        if not isinstance(downstream, list) or any(item not in MODULES for item in downstream):
            errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules.downstream_modules", "downstream modules must be sequential modules")
        if invalidation.get("declared_by") != "ask-park":
            errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules.declared_by", "Ask Park owns invalidation declarations")
        rewind = invalidation.get("causal_rewind")
        if not isinstance(rewind, (bool, dict)):
            errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules.causal_rewind", "causal_rewind must be boolean or an object")
        elif isinstance(rewind, dict):
            errors.required(rewind, ("earliest_invalidated_module", "reason_code", "invalidated_receipt_ids"), "receipt.invalidation_rules.causal_rewind", "RECEIPT_REQUIRED_FIELD")
            if rewind.get("earliest_invalidated_module") not in MODULES:
                errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules.causal_rewind.earliest_invalidated_module", "rewind module must be sequential module")
            if not _is_nonempty_string(rewind.get("reason_code")):
                errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules.causal_rewind.reason_code", "rewind reason is required")
            ids = rewind.get("invalidated_receipt_ids")
            if not isinstance(ids, list) or any(not _safe_identifier(item) for item in ids):
                errors.add("RECEIPT_INVALIDATION", "receipt.invalidation_rules.causal_rewind.invalidated_receipt_ids", "rewind receipt ids must be aliases")

    if not _is_iso(document.get("issued_at")):
        errors.add("RECEIPT_TIMESTAMP", "receipt.issued_at", "issued_at must be ISO-8601")
    refs = document.get("evidence_refs", [])
    if not isinstance(refs, list) or any(not _is_redacted_ref(item) for item in refs):
        errors.add("RECEIPT_EVIDENCE", "receipt.evidence_refs", "evidence references must be redacted")
    return ValidationResult("receipt", dict(document), tuple(errors.errors))


def validate_human_gate(document: Any) -> ValidationResult:
    errors = _Collector()
    if not _is_mapping(document):
        errors.add("HUMAN_GATE_TYPE", "human_gate", "human gate must be a JSON object")
        return ValidationResult("human-gate", {}, tuple(errors.errors))
    _walk_persistence_boundary(document, "", errors)
    _validate_human_gate_fields(document, "human_gate", errors, standalone=True)
    return ValidationResult("human-gate", dict(document), tuple(errors.errors))


def validate_document(document: Any, kind: str | None = None) -> ValidationResult:
    if kind == "state":
        return validate_state(document)
    if kind == "receipt":
        return validate_receipt(document)
    if kind in ("human-gate", "human_gate"):
        return validate_human_gate(document)
    if _is_mapping(document) and "receipt_type" in document:
        return validate_receipt(document)
    if _is_mapping(document) and ("gate_id" in document or document.get("contract_version") == HUMAN_GATE_CONTRACT_VERSION):
        return validate_human_gate(document)
    return validate_state(document)


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


def _payload(result: ValidationResult, *, input_path: str | None = None) -> dict[str, Any]:
    # Never include the document in CLI output. A malformed document may carry
    # a secret, and machine-readable output must be safe to persist in logs.
    return {
        "valid": result.valid,
        "kind": result.kind,
        # Do not echo the filesystem path: callers may place private target
        # identifiers in a filename, and the validator output is log-safe by
        # contract.
        "input": "provided" if input_path else "stdin",
        "errors": [{"code": item.code, "path": item.path, "message": item.message} for item in result.errors],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="JSON state, receipt, or human-gate record")
    source.add_argument("--state", type=Path, help="JSON state record")
    source.add_argument("--receipt", type=Path, help="JSON module receipt")
    source.add_argument("--human-gate", dest="human_gate", type=Path, help="JSON human-gate record")
    parser.add_argument("--kind", choices=("state", "receipt", "human-gate"), help="explicitly select the contract")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    input_path = args.input or args.state or args.receipt or args.human_gate
    inferred_kind = args.kind
    if args.state:
        inferred_kind = "state"
    elif args.receipt:
        inferred_kind = "receipt"
    elif args.human_gate:
        inferred_kind = "human-gate"
    try:
        document = _read_json(input_path)
        result = validate_document(document, inferred_kind)
    except ValueError as exc:
        result = ValidationResult(
            inferred_kind or "unknown",
            {},
            (ValidationError("INPUT_INVALID", "input", str(exc)),),
        )

    payload = _payload(result, input_path=str(input_path))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print("PASS" if result.valid else "FAIL")
        for error in result.errors:
            print(f"- {error.code} at {error.path}: {error.message}")
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
