#!/usr/bin/env python3
"""Validate S10 QA manifests, results, state, and evidence rows.

Only the JSON data model is accepted. The validator is deterministic, provider-
free, and deliberately rejects private evidence before type-specific checks.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
REDacted_RE = re.compile(r"^redacted:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
EVIDENCE_MODES = {"sanitized-persisted", "ephemeral-only", "approved-store-reference"}
MODULES = {"plan", "build", "cloudbase", "experience", "device", "release"}
FORBIDDEN_KEY_PARTS = ("openid", "payment", "qr", "credential", "secret", "token", "password", "filename", "bytes", "private_key", "access_key", "api_key", "cookie", "environment_id", "env_id", "appid", "url", "uri", "target_url")


class ValidationError:
    __slots__ = ("code", "path", "message")

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message


class ValidationResult:
    __slots__ = ("kind", "document", "errors")

    def __init__(self, kind: str, document: dict[str, Any], errors: list[ValidationError]) -> None:
        self.kind = kind
        self.document = document
        self.errors = tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.errors


class _Collector:
    def __init__(self) -> None:
        self.errors: list[ValidationError] = []

    def add(self, code: str, path: str, message: str) -> None:
        self.errors.append(ValidationError(code, path, message))

    def required(self, document: dict[str, Any], keys: Iterable[str], prefix: str) -> None:
        for key in keys:
            if key not in document:
                self.add("QA_REQUIRED_FIELD", f"{prefix}.{key}", "required field is missing")


def _is_alias(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _is_redacted(value: Any) -> bool:
    return isinstance(value, str) and bool(REDacted_RE.fullmatch(value))


def _is_iso(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_RE.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _walk_privacy(value: Any, path: str, errors: _Collector) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            child_path = f"{path}.{key}" if path else str(key)
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                errors.add("QA_PRIVATE_FIELD", child_path, "sensitive evidence field is not persistable")
            _walk_privacy(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_privacy(child, f"{path}[{index}]", errors)
    elif isinstance(value, str):
        if value.startswith(("http://", "https://", "file://", "cloud://", "/Users/", "/private/", "~/")):
            errors.add("QA_PRIVATE_VALUE", path, "private target value is not persistable")


def _canonical_json(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, str)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, float):
        raise ValueError("floating JSON numbers are not accepted; use integers for this JCS profile")
    if isinstance(value, list):
        return "[" + ",".join(_canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            json.dumps(key, ensure_ascii=False, separators=(",", ":")) + ":" + _canonical_json(value[key])
            for key in sorted(value, key=lambda item: str(item).encode("utf-16be", "surrogatepass"))
        ) + "}"
    raise ValueError("unsupported JSON value")


def canonical_digest(document: dict[str, Any]) -> str:
    payload = copy.deepcopy(document)
    payload.pop("digest", None)
    canonical = _canonical_json(payload).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _check_digest(document: dict[str, Any], errors: _Collector, path: str = "manifest.digest") -> None:
    if not _is_digest(document.get("digest")):
        errors.add("QA_DIGEST", path, "digest must be sha256 plus 64 lowercase hex characters")
        return
    try:
        expected = canonical_digest(document)
    except ValueError:
        errors.add("QA_CANONICAL_JSON", "manifest", "manifest contains a value outside the JSON canonicalization profile")
        return
    if document.get("digest") != expected:
        errors.add("QA_DIGEST_MISMATCH", path, "digest does not match canonical manifest bytes")


def _check_evidence_mode(document: dict[str, Any], prefix: str, errors: _Collector) -> None:
    mode = document.get("evidence_mode")
    if mode not in EVIDENCE_MODES:
        errors.add("QA_EVIDENCE_MODE", f"{prefix}.evidence_mode", "unsupported evidence mode")
        return
    refs = document.get("evidence_refs", [])
    if not isinstance(refs, list):
        errors.add("QA_EVIDENCE_REFS", f"{prefix}.evidence_refs", "evidence_refs must be a list")
    if mode == "ephemeral-only" and refs:
        errors.add("QA_EPHEMERAL_REFERENCE", f"{prefix}.evidence_refs", "ephemeral evidence cannot persist refs")
    if mode == "approved-store-reference":
        governance = document.get("store_governance")
        if not isinstance(governance, dict):
            errors.add("QA_STORE_GOVERNANCE", f"{prefix}.store_governance", "approved-store evidence requires governance")
        else:
            for key in ("audience", "retention", "deletion", "access_control", "redacted_ref"):
                if not isinstance(governance.get(key), str) or not governance[key].strip():
                    errors.add("QA_STORE_GOVERNANCE", f"{prefix}.store_governance.{key}", "governance field is required")
            if not _is_redacted(governance.get("redacted_ref")):
                errors.add("QA_STORE_GOVERNANCE", f"{prefix}.store_governance.redacted_ref", "store reference must be redacted")


def _check_common_manifest(document: Any, kind: str, errors: _Collector) -> None:
    if not isinstance(document, dict):
        errors.add("QA_TYPE", "manifest", "manifest must be a JSON object")
        return
    _walk_privacy(document, "manifest", errors)
    allowed = {
        "schema_version", "kind", "digest", "qa_run_id", "issue_contract_id",
        "issue_contract_version", "origin_module", "candidate", "target_manifest_digest",
        "candidate_manifest_digest", "target", "predecessor_receipt_ids", "qa1_evidence_hashes",
        "result", "gate", "target_receipt_id", "observed_at", "evidence_mode", "evidence_refs",
        "evidence_hashes", "passed_checks", "limitations", "automated_checks_passed",
        "store_governance", "findings",
    }
    for key in document:
        if key not in allowed:
            errors.add("QA_UNKNOWN_FIELD", "manifest.<key>", "field is not in the QA schema")
    if document.get("schema_version") != 1:
        errors.add("QA_SCHEMA_VERSION", "manifest.schema_version", "schema_version must be 1")
    if document.get("kind") != kind:
        errors.add("QA_KIND", "manifest.kind", f"manifest kind must be {kind}")
    _check_digest(document, errors)
    for key in ("qa_run_id", "issue_contract_id"):
        if not _is_alias(document.get(key)):
            errors.add("QA_ALIAS", f"manifest.{key}", "field must be a stable alias")
    _check_evidence_mode(document, "manifest", errors)


def _check_hash_list(value: Any, path: str, errors: _Collector) -> None:
    if not isinstance(value, list) or any(not _is_digest(item) for item in value):
        errors.add("QA_HASH_LIST", path, "evidence hashes must be full SHA-256 digests")


def validate_candidate(document: Any) -> ValidationResult:
    errors = _Collector()
    _check_common_manifest(document, "qa-candidate", errors)
    if isinstance(document, dict):
        errors.required(document, ("issue_contract_version", "origin_module", "candidate", "predecessor_receipt_ids", "qa1_evidence_hashes"), "manifest")
        if document.get("target_manifest_digest") is not None:
            errors.add("QA_TARGET_BINDING", "manifest.target_manifest_digest", "candidate manifest must exist before target and cannot bind one")
        if document.get("origin_module") not in MODULES:
            errors.add("QA_ORIGIN_MODULE", "manifest.origin_module", "origin_module must be sequential")
        candidate = document.get("candidate")
        if not isinstance(candidate, dict):
            errors.add("QA_CANDIDATE", "manifest.candidate", "candidate must be an object")
        else:
            if not _is_digest(candidate.get("source_sha")):
                errors.add("QA_SOURCE_SHA", "manifest.candidate.source_sha", "source SHA must be a full digest")
            for key in ("lockfile_digest", "build_config_digest", "build_artifact_digest", "native_project_config_digest", "runtime_config_digest"):
                if candidate.get(key) is not None and not _is_digest(candidate[key]):
                    errors.add("QA_DIGEST", f"manifest.candidate.{key}", "candidate digest is invalid")
        if not isinstance(document.get("predecessor_receipt_ids"), list) or any(not _is_alias(item) for item in document.get("predecessor_receipt_ids", [])):
            errors.add("QA_PREDECESSORS", "manifest.predecessor_receipt_ids", "predecessors must be aliases")
        _check_hash_list(document.get("qa1_evidence_hashes"), "manifest.qa1_evidence_hashes", errors)
    return ValidationResult("candidate", document if isinstance(document, dict) else {}, errors.errors)


def validate_target(document: Any) -> ValidationResult:
    errors = _Collector()
    _check_common_manifest(document, "qa-target", errors)
    if isinstance(document, dict):
        errors.required(document, ("candidate_manifest_digest", "predecessor_receipt_ids", "target"), "manifest")
        if not _is_digest(document.get("candidate_manifest_digest")):
            errors.add("QA_CANDIDATE_DIGEST", "manifest.candidate_manifest_digest", "target must reference a candidate digest")
        target = document.get("target")
        if not isinstance(target, dict):
            errors.add("QA_TARGET", "manifest.target", "target must be an object")
        else:
            for key in ("target_alias", "deployment_receipt_id", "environment_contract_alias", "platform_version"):
                if not _is_alias(target.get(key)):
                    errors.add("QA_ALIAS", f"manifest.target.{key}", "target field must be a stable alias")
            if not isinstance(target.get("upload_note"), str) or not target.get("upload_note").strip():
                errors.add("QA_TARGET", "manifest.target.upload_note", "upload note is required")
            for key in ("live_index_digest",):
                if target.get(key) is not None and not _is_digest(target[key]):
                    errors.add("QA_DIGEST", f"manifest.target.{key}", "target digest is invalid")
            if not isinstance(target.get("asset_digests"), list) or any(not _is_digest(item) for item in target.get("asset_digests", [])):
                errors.add("QA_HASH_LIST", "manifest.target.asset_digests", "asset digests must be full SHA-256")
        if not isinstance(document.get("predecessor_receipt_ids"), list) or any(not _is_alias(item) for item in document.get("predecessor_receipt_ids", [])):
            errors.add("QA_PREDECESSORS", "manifest.predecessor_receipt_ids", "predecessors must be aliases")
    return ValidationResult("target", document if isinstance(document, dict) else {}, errors.errors)


def validate_result(document: Any) -> ValidationResult:
    errors = _Collector()
    _check_common_manifest(document, "qa-result", errors)
    if isinstance(document, dict):
        errors.required(document, ("result", "gate", "candidate_manifest_digest", "target_manifest_digest", "target_receipt_id", "predecessor_receipt_ids", "observed_at", "evidence_hashes", "passed_checks", "limitations"), "manifest")
        if document.get("result") not in {"none", "QA_PASS", "QA_FAIL", "QA_BLOCKED"}:
            errors.add("QA_RESULT", "manifest.result", "result is outside the QA enum")
        if document.get("gate") not in {"contract", "qa-1", "target", "qa-2", "evidence", "final"}:
            errors.add("QA_GATE", "manifest.gate", "gate is outside the QA enum")
        pre_target = document.get("gate") in {"contract", "qa-1"}
        if not _is_digest(document.get("candidate_manifest_digest")):
            errors.add("QA_CANDIDATE_DIGEST", "manifest.candidate_manifest_digest", "candidate result binding is required")
        if pre_target and document.get("target_manifest_digest") is not None:
            errors.add("QA_TARGET_BINDING", "manifest.target_manifest_digest", "pre-target result cannot bind a target")
        if pre_target and document.get("target_receipt_id") is not None:
            errors.add("QA_TARGET_RECEIPT", "manifest.target_receipt_id", "pre-target result cannot bind a target receipt")
        if not pre_target and not _is_digest(document.get("target_manifest_digest")):
            errors.add("QA_TARGET_BINDING", "manifest.target_manifest_digest", "post-target result must bind a target")
        if not pre_target and not _is_alias(document.get("target_receipt_id")):
            errors.add("QA_TARGET_RECEIPT", "manifest.target_receipt_id", "post-target result requires a target receipt alias")
        if not pre_target and (not isinstance(document.get("predecessor_receipt_ids"), list) or any(not _is_alias(item) for item in document.get("predecessor_receipt_ids", []))):
            errors.add("QA_PREDECESSORS", "manifest.predecessor_receipt_ids", "post-target result requires predecessor receipt aliases")
        if not _is_iso(document.get("observed_at")):
            errors.add("QA_TIMESTAMP", "manifest.observed_at", "observed_at must be ISO-8601")
        if not isinstance(document.get("passed_checks"), list) or not document.get("passed_checks"):
            errors.add("QA_CHECKS", "manifest.passed_checks", "passed_checks must be a non-empty list")
        _check_hash_list(document.get("evidence_hashes"), "manifest.evidence_hashes", errors)
        if not isinstance(document.get("limitations"), list) or not document.get("limitations"):
            errors.add("QA_LIMITATIONS", "manifest.limitations", "limitations are required")
        if document.get("evidence_mode") == "ephemeral-only" and document.get("evidence_refs"):
            errors.add("QA_EPHEMERAL_REFERENCE", "manifest.evidence_refs", "ephemeral result cannot persist refs")
        if document.get("result") == "QA_BLOCKED" and document.get("automated_checks_passed") is not True:
            errors.add("QA_BLOCKED_AUTOMATION", "manifest.automated_checks_passed", "BLOCKED requires automation passed")
        if document.get("result") == "QA_FAIL" and (not isinstance(document.get("findings"), list) or not document.get("findings")):
            errors.add("QA_FINDINGS", "manifest.findings", "QA_FAIL requires observable findings")
    return ValidationResult("result", document if isinstance(document, dict) else {}, errors.errors)


def validate_evidence(document: Any) -> ValidationResult:
    errors = _Collector()
    if not isinstance(document, dict):
        errors.add("QA_TYPE", "evidence", "evidence row must be an object")
        return ValidationResult("evidence", {}, errors.errors)
    _walk_privacy(document, "evidence", errors)
    for key in ("surface", "route", "viewport", "role", "data_state", "equivalence", "tool", "evidence_mode", "after_evidence", "limitations"):
        if key not in document:
            errors.add("QA_REQUIRED_FIELD", f"evidence.{key}", "required evidence field is missing")
    _check_evidence_mode(document, "evidence", errors)
    for key in ("surface", "route", "viewport", "role", "data_state"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            errors.add("QA_EVIDENCE_FIELD", f"evidence.{key}", "evidence field must be non-empty")
    if document.get("equivalence") not in {"exact", "approved-reference", "historical-exception"}:
        errors.add("QA_EQUIVALENCE", "evidence.equivalence", "equivalence is invalid")
    tool = document.get("tool")
    if not isinstance(tool, dict) or not all(isinstance(tool.get(key), str) and tool.get(key) for key in ("name", "version", "runtime_or_base_library")):
        errors.add("QA_TOOL", "evidence.tool", "tool/runtime identity is required")
    before = document.get("before_evidence")
    if before is not None and (document.get("evidence_mode") == "ephemeral-only" or not isinstance(before, dict) or not _is_redacted(before.get("ref")) or not _is_digest(before.get("sha256")) or not _is_iso(before.get("captured_at")) or not isinstance(before.get("identity"), str) or not before.get("identity")):
        errors.add("QA_BEFORE", "evidence.before_evidence", "before evidence identity is invalid")
    after = document.get("after_evidence")
    if not isinstance(after, dict):
        errors.add("EVIDENCE_AFTER_REQUIRED", "evidence.after_evidence", "after evidence is always required")
    else:
        for key in ("ref", "source_or_package_identity", "final_compile_receipt_id"):
            if key == "ref" and document.get("evidence_mode") == "ephemeral-only":
                if after.get(key) is not None:
                    errors.add("QA_EPHEMERAL_REFERENCE", "evidence.after_evidence.ref", "ephemeral evidence cannot persist nested refs")
                continue
            if not isinstance(after.get(key), str) or not after.get(key):
                errors.add("EVIDENCE_FINAL_COMPILE" if key == "final_compile_receipt_id" else "QA_AFTER", f"evidence.after_evidence.{key}", "after evidence field is required")
        if document.get("evidence_mode") != "ephemeral-only" and not _is_redacted(after.get("ref")):
            errors.add("QA_AFTER_REF", "evidence.after_evidence.ref", "after evidence ref must be redacted")
        if not _is_digest(after.get("sha256")):
            errors.add("QA_AFTER_HASH", "evidence.after_evidence.sha256", "after evidence hash is required")
        if not _is_iso(after.get("captured_at")):
            errors.add("QA_AFTER_TIME", "evidence.after_evidence.captured_at", "after timestamp is required")
    return ValidationResult("evidence", document, errors.errors)


def validate_qa_state(document: Any) -> ValidationResult:
    errors = _Collector()
    if not isinstance(document, dict) or not isinstance(document.get("qa"), dict):
        errors.add("QA_STATE_TYPE", "qa", "qa state must be an object")
        return ValidationResult("qa-state", document if isinstance(document, dict) else {}, errors.errors)
    _walk_privacy(document, "qa-state", errors)
    if document.get("schema_version") != 1 or document.get("kind") != "qa-state":
        errors.add("QA_SCHEMA_VERSION", "qa-state", "qa-state requires schema_version 1 and kind qa-state")
    if any(key not in {"schema_version", "kind", "qa"} for key in document):
        errors.add("QA_UNKNOWN_FIELD", "qa-state.<key>", "field is not in the QA state schema")
    qa = document["qa"]
    errors.required(qa, ("execution_state", "result", "control_outcome", "gate", "candidate_manifest_digest", "target_manifest_digest", "attempt", "max_attempts", "origin_module", "result_receipt_id"), "qa")
    allowed_qa_keys = {"execution_state", "result", "control_outcome", "gate", "candidate_manifest_digest", "target_manifest_digest", "attempt", "max_attempts", "origin_module", "result_receipt_id"}
    for key in qa:
        if key not in allowed_qa_keys:
            errors.add("QA_UNKNOWN_FIELD", "qa.<key>", "field is not in the QA state schema")
    if qa.get("execution_state") not in {"unavailable", "ready", "running", "complete"}:
        errors.add("QA_STATE", "qa.execution_state", "execution state is invalid")
    if qa.get("result") not in {"none", "QA_PASS", "QA_FAIL", "QA_BLOCKED"}:
        errors.add("QA_STATE", "qa.result", "result is invalid")
    if qa.get("control_outcome") not in {"none", "qa-prerequisite-missing", "needs-park-decision"}:
        errors.add("QA_STATE", "qa.control_outcome", "control outcome is invalid")
    if qa.get("gate") not in {"contract", "qa-1", "target", "qa-2", "evidence", "final"}:
        errors.add("QA_GATE", "qa.gate", "gate is invalid")
    if qa.get("origin_module") not in MODULES:
        errors.add("QA_ORIGIN_MODULE", "qa.origin_module", "origin module is invalid")
    if qa.get("result_receipt_id") is not None and not _is_alias(qa.get("result_receipt_id")):
        errors.add("QA_ALIAS", "qa.result_receipt_id", "result receipt ID must be an alias or null")
    if qa.get("execution_state") == "unavailable" and qa.get("control_outcome") != "qa-prerequisite-missing":
        errors.add("QA_PREREQUISITE", "qa.control_outcome", "unavailable evaluator requires prerequisite-missing")
    if qa.get("execution_state") == "unavailable" and qa.get("result") != "none":
        errors.add("QA_PREREQUISITE", "qa.result", "unavailable evaluator cannot issue a result")
    if qa.get("result") == "QA_BLOCKED" and qa.get("execution_state") != "complete":
        errors.add("QA_STATE", "qa.execution_state", "blocked result must be complete")
    if qa.get("execution_state") == "unavailable" and qa.get("result") == "QA_BLOCKED":
        errors.add("QA_PREREQUISITE", "qa.result", "unavailable evaluator cannot produce BLOCKED")
    if qa.get("candidate_manifest_digest") is not None and not _is_digest(qa.get("candidate_manifest_digest")):
        errors.add("QA_DIGEST", "qa.candidate_manifest_digest", "candidate binding must be a full digest or null")
    if qa.get("target_manifest_digest") is not None and not _is_digest(qa.get("target_manifest_digest")):
        errors.add("QA_DIGEST", "qa.target_manifest_digest", "target binding must be a full digest or null")
    if not isinstance(qa.get("attempt"), int) or qa.get("attempt") < 1 or qa.get("attempt") > 3:
        errors.add("QA_ATTEMPT", "qa.attempt", "attempt must be 1..3")
    if qa.get("max_attempts") != 3:
        errors.add("QA_ATTEMPT", "qa.max_attempts", "max_attempts must be 3")
    return ValidationResult("qa-state", document, errors.errors)


def validate_document(document: Any, kind: str) -> ValidationResult:
    return {
        "candidate": validate_candidate,
        "target": validate_target,
        "result": validate_result,
        "evidence": validate_evidence,
        "qa-state": validate_qa_state,
    }.get(kind, lambda value: ValidationResult(kind, {}, [ValidationError("QA_KIND", "kind", "unknown QA document kind")]))(document)


def invalidate_result(result: dict[str, Any], *, candidate_manifest_digest: str | None = None, target_manifest_digest: str | None = None) -> dict[str, Any]:
    updated = copy.deepcopy(result)
    if candidate_manifest_digest is not None and candidate_manifest_digest != result.get("candidate_manifest_digest"):
        updated.update({"result": "none", "candidate_manifest_digest": None, "target_manifest_digest": None, "evidence_hashes": [], "evidence_refs": []})
    elif target_manifest_digest is not None and target_manifest_digest != result.get("target_manifest_digest"):
        updated.update({"result": "none", "target_manifest_digest": None, "evidence_hashes": [], "evidence_refs": []})
    return updated


def _read_json(path: Path) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
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
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--kind", choices=("candidate", "target", "result", "evidence", "qa-state"), required=True)
    args = parser.parse_args(argv)
    try:
        result = validate_document(_read_json(args.input), args.kind)
    except ValueError as exc:
        print(json.dumps({"valid": False, "errors": [{"code": "QA_INPUT", "message": str(exc)}]}, sort_keys=True))
        return 2
    print(json.dumps({"valid": result.valid, "kind": result.kind, "errors": [{"code": error.code, "path": error.path, "message": error.message} for error in result.errors]}, sort_keys=True))
    return 0 if result.valid else 1


if __name__ == "__main__":
    sys.exit(main())
