#!/usr/bin/env python3
"""Hermetic Browser QA-2 raw-site drift and matrix checks."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
from typing import Any, Mapping


SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
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


def _safe_text(value: Any) -> bool:
    return isinstance(value, str) and not value.startswith(("http://", "https://", "file://", "cloud://", "/Users/", "/private/", "~/"))


def validate_site(site: Mapping[str, Any], *, target: bool = False) -> dict[str, Any]:
    if not isinstance(site, Mapping):
        _fail("BROWSER_SITE_TYPE", "raw site record must be an object", "site")
    allowed = {"source_sha", "index_digest", "js_digest", "css_digest", "auth_mode", "deep_links", "spa_fallback", "mock_marker", "render_digest"} | ({"target_alias"} if target else set()) | {"matrix_identity_alias", "compile_provenance"}
    if any(key not in allowed for key in site):
        _fail("BROWSER_SITE_UNKNOWN_FIELD", "raw site contains an undeclared field", "site.<key>")
    if not all(_safe_text(value) for value in site.values() if isinstance(value, str)):
        _fail("BROWSER_SITE_PRIVATE", "raw site contains a private target value", "site")
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
    if not target and (not _alias(site.get("matrix_identity_alias")) or not _alias(site.get("compile_provenance")) or not _digest(site.get("render_digest"))):
        _fail("BROWSER_COMPILE_PROVENANCE", "candidate requires matrix identity, compile provenance, and render digest", "site")
    if target and not _digest(site.get("render_digest")):
        _fail("BROWSER_RENDER_PROVENANCE", "target requires render digest", "site.render_digest")
    return copy.deepcopy(dict(site))


def validate_matrix(matrix: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(matrix, list) or not matrix:
        _fail("BROWSER_MATRIX_REQUIRED", "Browser matrix must be non-empty", "matrix")
    states = set()
    for row in matrix:
        allowed = {"route", "viewport", "role", "data_state", "state", "tool", "runtime", "before_hash", "after_hash", "source_identity", "final_compile_provenance", "observed_at"}
        if any(key not in allowed for key in row):
            _fail("BROWSER_MATRIX_UNKNOWN_FIELD", "matrix row contains an undeclared field", "matrix.<key>")
        for key in ("route", "viewport", "role", "data_state", "state", "tool", "runtime", "before_hash", "after_hash", "source_identity", "final_compile_provenance", "observed_at"):
            if key not in row:
                _fail("BROWSER_MATRIX_REQUIRED", "matrix row field is required", f"matrix.{key}")
        if not all(_alias(row[key]) for key in ("route", "viewport", "role", "data_state", "state", "tool", "runtime", "source_identity", "final_compile_provenance")):
            _fail("BROWSER_MATRIX_ALIAS", "matrix identity fields must be aliases", "matrix")
        if not _digest(row["before_hash"]) or not _digest(row["after_hash"]):
            _fail("BROWSER_MATRIX_HASH", "matrix before/after hashes must be full SHA-256", "matrix")
        if any(not _safe_text(value) for value in row.values() if isinstance(value, str)):
            _fail("BROWSER_MATRIX_PRIVATE", "matrix row contains a private value", "matrix")
        if not ISO_RE.fullmatch(str(row["observed_at"])):
            _fail("BROWSER_MATRIX_TIME", "matrix observed_at must be ISO-8601", "matrix.observed_at")
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
    expected_source = candidate_site.get("matrix_identity_alias", candidate_site["source_sha"])
    expected_compile = candidate_site.get("compile_provenance")
    if candidate_site.get("render_digest") and any(row["before_hash"] != candidate_site["render_digest"] for row in matrix):
        findings.append("matrix before hashes differ from candidate render digest")
    if target_site.get("render_digest") and any(row["after_hash"] != target_site["render_digest"] for row in matrix):
        findings.append("matrix after hashes differ from target render digest")
    for row in matrix:
        if row["source_identity"] != expected_source:
            findings.append("matrix source identity differs from candidate")
            break
        if expected_compile is not None and row["final_compile_provenance"] != expected_compile:
            findings.append("matrix final-compile provenance differs from candidate")
            break
    result = "QA_PASS" if not findings else "QA_FAIL"
    return {"result": result, "findings": findings, "automated_checks_passed": not findings, "limitations": ["Browser evidence does not prove Mini Program or physical-device behavior."], "matrix_rows": len(matrix)}


@contextmanager
def _fixture_server(payload: Mapping[str, Any]):
    body = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib protocol name
            if self.path != "/raw.json":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/raw.json"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def run_hermetic_qa2(candidate: Mapping[str, Any], target: Mapping[str, Any], matrix: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare two raw localhost fixture servers and emit sanitized evidence."""

    with _fixture_server(candidate) as candidate_url, _fixture_server(target) as target_url:
        candidate_raw = urllib.request.urlopen(candidate_url, timeout=2).read()
        target_raw = urllib.request.urlopen(target_url, timeout=2).read()
    candidate_document = json.loads(candidate_raw.decode("utf-8"))
    target_document = json.loads(target_raw.decode("utf-8"))
    result = compare_candidate_target(candidate_document, target_document, matrix)
    result.update(
        {
            "adapter": {"candidate_server_ref": "redacted:localhost-candidate", "target_server_ref": "redacted:localhost-target", "external_network_events": [], "mutation_events": [], "transport": "ephemeral-only"},
            "evidence": {
                "before": {"surface": "local-browser", "ref": "redacted:browser-before", "sha256": "sha256:" + hashlib.sha256(candidate_raw).hexdigest(), "sanitized": True, "identity": candidate_document["source_sha"]},
                "after": {"surface": "local-browser", "ref": "redacted:browser-after", "sha256": "sha256:" + hashlib.sha256(target_raw).hexdigest(), "sanitized": True, "identity": target_document["source_sha"]},
            },
            "candidate_source_sha": candidate_document["source_sha"],
        }
    )
    return result


def capture_qa1(candidate: Mapping[str, Any], matrix: list[Mapping[str, Any]], *, browser_available: bool = True) -> dict[str, Any]:
    """Record a sanitized QA-1 before/after capture plan from raw fixture input."""

    if not browser_available:
        return prerequisite_missing(browser_available=False, qa_run_id="browser-qa1")
    site = validate_site(candidate)
    validate_matrix(matrix)
    return {
        "execution_state": "complete",
        "result": "QA_PASS",
        "browser_first": True,
        "evidence_mode": "sanitized-persisted",
        "candidate_source_sha": site["source_sha"],
        "captures": [{"route": row["route"], "viewport": row["viewport"], "role": row["role"], "data_state": row["data_state"], "state": row["state"], "tool": row["tool"], "runtime": row["runtime"], "before_ref": "redacted:qa1-before", "after_ref": "redacted:qa1-after", "before_hash": row["before_hash"], "after_hash": row["after_hash"], "source_identity": row["source_identity"], "final_compile_provenance": row["final_compile_provenance"], "captured_at": row["observed_at"], "sanitized": True} for row in matrix],
        "external_network_events": [],
        "mutation_events": [],
    }


def prerequisite_missing(*, browser_available: bool, qa_run_id: str) -> dict[str, Any]:
    if not _alias(qa_run_id):
        _fail("BROWSER_RUN_ID", "qa_run_id must be an alias", "qa_run_id")
    if browser_available:
        _fail("BROWSER_PREREQUISITE_UNEXPECTED", "prerequisite is available", "browser_available")
    return {"execution_state": "unavailable", "result": "none", "control_outcome": "qa-prerequisite-missing", "qa_run_id": qa_run_id}
