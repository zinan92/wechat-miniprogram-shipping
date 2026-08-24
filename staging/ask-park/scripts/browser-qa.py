#!/usr/bin/env python3
"""Hermetic Browser QA-2 raw-site drift and matrix checks."""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping


SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
REQUIRED_STATES = {"loading", "empty", "error", "locked", "long-title", "narrow-screen", "accessibility-name", "tap-target"}


class BrowserQAError(ValueError):
    def __init__(self, code: str, message: str, path: str = "browser-qa") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "browser-qa") -> None:
    raise BrowserQAError(code, message, path)


def _digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _alias(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def validate_site(site: Mapping[str, Any], *, target: bool = False) -> dict[str, Any]:
    if not isinstance(site, Mapping):
        _fail("BROWSER_SITE_TYPE", "raw site record must be an object", "site")
    for key in ("source_sha", "index_digest", "js_digest", "css_digest", "auth_mode", "deep_links", "spa_fallback", "mock_marker"):
        if key not in site:
            _fail("BROWSER_SITE_REQUIRED", "raw site field is required", f"site.{key}")
    if not _digest(site["source_sha"]) or not all(_digest(site[key]) for key in ("index_digest", "js_digest", "css_digest")):
        _fail("BROWSER_SITE_DIGEST", "site identity and assets require full SHA-256", "site")
    if site["auth_mode"] not in {"member", "public", "owner"}:
        _fail("BROWSER_AUTH_MODE", "auth mode is outside the fixture contract", "site.auth_mode")
    if not isinstance(site["deep_links"], bool) or not isinstance(site["spa_fallback"], bool):
        _fail("BROWSER_ROUTING", "deep links and SPA fallback flags must be boolean", "site")
    if not target and (site["deep_links"] is not True or site["spa_fallback"] is not True):
        _fail("BROWSER_ROUTING", "deep links and SPA fallback must pass", "site")
    if not isinstance(site["mock_marker"], bool):
        _fail("BROWSER_MOCK_MARKER", "mock marker must be boolean", "site.mock_marker")
    if not target and site["mock_marker"] is not False:
        _fail("BROWSER_MOCK_MARKER", "mock marker must be absent", "site.mock_marker")
    if target and not _alias(site.get("target_alias")):
        _fail("BROWSER_TARGET_ALIAS", "target alias is required", "site.target_alias")
    return copy.deepcopy(dict(site))


def validate_matrix(matrix: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(matrix, list) or not matrix:
        _fail("BROWSER_MATRIX_REQUIRED", "Browser matrix must be non-empty", "matrix")
    states = set()
    for row in matrix:
        for key in ("route", "viewport", "role", "data_state", "state", "tool", "runtime", "before_hash", "after_hash", "source_identity", "final_compile_provenance"):
            if key not in row:
                _fail("BROWSER_MATRIX_REQUIRED", "matrix row field is required", f"matrix.{key}")
        if not all(_alias(row[key]) for key in ("route", "viewport", "role", "data_state", "state", "tool", "runtime", "source_identity", "final_compile_provenance")):
            _fail("BROWSER_MATRIX_ALIAS", "matrix identity fields must be aliases", "matrix")
        if not _digest(row["before_hash"]) or not _digest(row["after_hash"]):
            _fail("BROWSER_MATRIX_HASH", "matrix before/after hashes must be full SHA-256", "matrix")
        states.add(row["state"])
    missing = REQUIRED_STATES - states
    if missing:
        _fail("BROWSER_MATRIX_COVERAGE", "required Browser states are missing", "matrix.state")
    return {"rows": len(matrix), "states": sorted(states)}


def compare_candidate_target(candidate: Mapping[str, Any], target: Mapping[str, Any], matrix: list[Mapping[str, Any]]) -> dict[str, Any]:
    candidate_site = validate_site(candidate)
    target_site = validate_site(target, target=True)
    validate_matrix(matrix)
    findings: list[str] = []
    if target_site["source_sha"] != candidate_site["source_sha"]:
        findings.append("target source identity differs from candidate")
    for key in ("index_digest", "js_digest", "css_digest"):
        if target_site[key] != candidate_site[key]:
            findings.append(f"target {key} differs from candidate")
    if target_site["auth_mode"] != candidate_site["auth_mode"]:
        findings.append("target auth mode differs from candidate")
    if target_site["deep_links"] is not True:
        findings.append("target deep links are broken")
    if target_site["spa_fallback"] is not True:
        findings.append("target SPA fallback is broken")
    if target_site["mock_marker"] is not False:
        findings.append("target contains a mock marker")
    result = "QA_PASS" if not findings else "QA_FAIL"
    return {"result": result, "findings": findings, "automated_checks_passed": not findings, "limitations": ["Browser evidence does not prove Mini Program or physical-device behavior."], "matrix_rows": len(matrix)}


def prerequisite_missing(*, browser_available: bool, qa_run_id: str) -> dict[str, Any]:
    if not _alias(qa_run_id):
        _fail("BROWSER_RUN_ID", "qa_run_id must be an alias", "qa_run_id")
    if browser_available:
        _fail("BROWSER_PREREQUISITE_UNEXPECTED", "prerequisite is available", "browser_available")
    return {"execution_state": "unavailable", "result": "none", "control_outcome": "qa-prerequisite-missing", "qa_run_id": qa_run_id}
