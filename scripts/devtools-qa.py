#!/usr/bin/env python3
"""Hermetic DevTools QA raw-event evaluator.

The production workflow is driven by Computer Use/WeChat Developer Tools, but
the tests only consume a bounded record/replay adapter. The adapter accepts raw
events and emits sanitized findings; it never turns a worker's prose into
evidence or claims physical-device completion.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator, Mapping


EVENTS = {"project-open", "compile", "screenshot", "upload-note", "platform-readback", "final-compile"}
DEFECTS = {
    "duplicate-title",
    "one-character-wrap",
    "double-safe-area",
    "stale-copy",
    "stale-package",
    "alignment",
    "removed-control",
    "missing-final-compile",
}
REQUIRED_STATES = {
    "loading",
    "empty",
    "error",
    "locked",
    "long-title-en",
    "long-title-zh",
    "narrow-screen",
    "accessibility-name",
    "tap-target",
}
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
PRIVATE_KEY_PARTS = (
    "openid",
    "payment",
    "qr",
    "credential",
    "secret",
    "token",
    "password",
    "private_key",
    "api_key",
    "cookie",
    "filename",
    "bytes",
    "environment_id",
    "appid",
    "next_module",
    "current_module",
    "routing",
)


class DevToolsQAError(ValueError):
    def __init__(self, code: str, message: str, path: str = "devtools-qa") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "devtools-qa") -> None:
    raise DevToolsQAError(code, message, path)


def _alias(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _safe_text(value: Any) -> bool:
    return isinstance(value, str) and not value.startswith(
        ("http://", "https://", "file://", "cloud://", "/Users/", "/private/", "~/")
    )


def _safe(value: Any) -> bool:
    """Reject private fields/values before any record can be persisted."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in PRIVATE_KEY_PARTS):
                return False
            if not _safe(child):
                return False
    elif isinstance(value, list):
        return all(_safe(child) for child in value)
    elif isinstance(value, str) and not _safe_text(value):
        return False
    return True


EVENT_ALLOWED = {
    "project-open": {"type", "project_alias", "external_network", "platform_mutation"},
    "compile": {
        "type",
        "source_sha",
        "tool",
        "base_library",
        "compile_provenance",
        "external_network",
        "platform_mutation",
    },
    "final-compile": {
        "type",
        "source_sha",
        "tool",
        "base_library",
        "compile_provenance",
        "external_network",
        "platform_mutation",
    },
    "screenshot": {
        "type",
        "route",
        "device",
        "state",
        "defects",
        "source_sha",
        "screenshot_hash",
        "external_network",
        "platform_mutation",
    },
    "upload-note": {"type", "candidate_digest", "note_alias", "external_network", "platform_mutation"},
    "platform-readback": {"type", "candidate_digest", "version_alias", "external_network", "platform_mutation"},
}
SINGLETON_EVENTS = {"project-open", "compile", "upload-note", "platform-readback", "final-compile"}
EVENT_ORDER = ["project-open", "compile", "screenshot", "upload-note", "platform-readback", "final-compile"]


def validate_events(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate raw DevTools events without requiring a final verdict."""

    if not isinstance(events, list) or not events:
        _fail("DEVTOOLS_EVENTS_REQUIRED", "raw event list is required", "events")
    normalized: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for event in events:
        if not isinstance(event, Mapping) or event.get("type") not in EVENTS:
            _fail("DEVTOOLS_EVENT_UNKNOWN", "event type is outside the raw adapter enum", "events.type")
        event_type = str(event["type"])
        counts[event_type] = counts.get(event_type, 0) + 1
        if event_type in SINGLETON_EVENTS and counts[event_type] > 1:
            _fail("DEVTOOLS_EVENT_DUPLICATE", "singleton raw event occurs more than once", f"events.{event_type}")
        if any(key not in EVENT_ALLOWED[event_type] for key in event):
            _fail("DEVTOOLS_EVENT_UNKNOWN_FIELD", "raw event contains an undeclared field", "events.<key>")
        if event.get("external_network") is not False or event.get("platform_mutation") is not False:
            _fail("DEVTOOLS_EXTERNAL_SIDE_EFFECT", "fixture adapter cannot perform external mutation", "events")
        if not _safe(event):
            _fail("DEVTOOLS_PRIVATE_EVENT", "raw event contains private or routing data", "events")
        if event_type == "project-open" and not _alias(event.get("project_alias")):
            _fail("DEVTOOLS_PROJECT_ID", "project-open requires a project alias", "events.project_alias")
        if event_type in {"compile", "final-compile"}:
            if not all(
                (
                    _digest(event.get("source_sha")),
                    _alias(event.get("tool")),
                    _alias(event.get("base_library")),
                    _alias(event.get("compile_provenance")),
                )
            ):
                _fail("DEVTOOLS_COMPILE_IDENTITY", "compile requires source/tool/base-library/provenance identity", "events")
        if event_type == "screenshot":
            if not all(
                (
                    _alias(event.get("route")),
                    _alias(event.get("device")),
                    _alias(event.get("state")),
                    _digest(event.get("source_sha")),
                    _digest(event.get("screenshot_hash")),
                )
            ):
                _fail("DEVTOOLS_SCREENSHOT_IDENTITY", "screenshot requires route/device/state/source/hash", "events")
            if not isinstance(event.get("defects"), list) or any(
                not isinstance(defect, str) or defect not in DEFECTS for defect in event["defects"]
            ):
                _fail("DEVTOOLS_DEFECT_ENUM", "screenshot defects must use the declared defect enum", "events.defects")
        if event_type == "upload-note" and not (
            _digest(event.get("candidate_digest")) and _alias(event.get("note_alias"))
        ):
            _fail("DEVTOOLS_UPLOAD_IDENTITY", "upload-note requires candidate digest and note alias", "events")
        if event_type == "platform-readback" and not (
            _digest(event.get("candidate_digest")) and _alias(event.get("version_alias"))
        ):
            _fail("DEVTOOLS_READBACK_IDENTITY", "platform read-back requires candidate digest and version alias", "events")
        normalized.append(copy.deepcopy(dict(event)))

    # Missing events are retained as findings by evaluate_events so a missing
    # final compile becomes QA_FAIL rather than a schema exception.
    positions = [EVENT_ORDER.index(event["type"]) for event in normalized]
    if any(left > right for left, right in zip(positions, positions[1:])):
        _fail("DEVTOOLS_EVENT_ORDER", "raw events are out of the required workflow order", "events")
    return normalized


MATRIX_ALLOWED = {
    "route",
    "viewport",
    "device",
    "role",
    "data_state",
    "state",
    "tool",
    "runtime",
    "source_sha",
    "source_identity",
    "screenshot_hash",
    "before_hash",
    "after_hash",
    "final_compile_provenance",
    "observed_at",
    "captured_at",
}
MATRIX_REQUIRED = {
    "route",
    "role",
    "data_state",
    "state",
    "tool",
    "runtime",
    "source_sha",
    "screenshot_hash",
    "final_compile_provenance",
}


def validate_matrix(matrix: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize the nine-state DevTools evidence matrix."""

    if not isinstance(matrix, list) or not matrix:
        _fail("DEVTOOLS_MATRIX_REQUIRED", "DevTools matrix must be non-empty", "matrix")
    normalized: list[dict[str, Any]] = []
    states: set[str] = set()
    seen: set[tuple[str, str, str]] = set()
    for row in matrix:
        if not isinstance(row, Mapping):
            _fail("DEVTOOLS_MATRIX_ROW", "matrix rows must be objects", "matrix")
        if any(key not in MATRIX_ALLOWED for key in row):
            _fail("DEVTOOLS_MATRIX_UNKNOWN_FIELD", "matrix row contains an undeclared field", "matrix.<key>")
        missing = MATRIX_REQUIRED - set(row)
        if missing:
            _fail("DEVTOOLS_MATRIX_REQUIRED", "matrix row field is required", f"matrix.{sorted(missing)[0]}")
        item = copy.deepcopy(dict(row))
        item.setdefault("device", item.get("viewport"))
        item.setdefault("viewport", item.get("device"))
        if not _alias(item.get("device")) or not _alias(item.get("viewport")):
            _fail("DEVTOOLS_MATRIX_DEVICE", "matrix requires device/viewport aliases", "matrix.device")
        if "observed_at" not in item and "captured_at" in item:
            item["observed_at"] = item["captured_at"]
        if not isinstance(item.get("observed_at"), str) or not ISO_RE.fullmatch(item["observed_at"]):
            _fail("DEVTOOLS_MATRIX_TIME", "matrix observed_at must be ISO-8601", "matrix.observed_at")
        if not all(
            _alias(item.get(key))
            for key in ("route", "role", "data_state", "state", "tool", "runtime", "final_compile_provenance")
        ):
            _fail("DEVTOOLS_MATRIX_ALIAS", "matrix identity fields must be aliases", "matrix")
        if not _digest(item.get("source_sha")) or not _digest(item.get("screenshot_hash")):
            _fail("DEVTOOLS_MATRIX_HASH", "matrix source and screenshot hashes must be full SHA-256", "matrix")
        if "source_identity" in item and not (_alias(item["source_identity"]) or _digest(item["source_identity"])):
            _fail("DEVTOOLS_MATRIX_IDENTITY", "source_identity must be an alias or full digest", "matrix.source_identity")
        for key in ("before_hash", "after_hash"):
            if key in item and item[key] is not None and not _digest(item[key]):
                _fail("DEVTOOLS_MATRIX_HASH", f"{key} must be a full SHA-256 when present", f"matrix.{key}")
        if not _safe(item):
            _fail("DEVTOOLS_PRIVATE_MATRIX", "matrix contains private or routing data", "matrix")
        identity = (item["route"], item["device"], item["state"])
        if identity in seen:
            _fail("DEVTOOLS_MATRIX_DUPLICATE", "matrix contains duplicate route/device/state", "matrix")
        seen.add(identity)
        states.add(item["state"])
        normalized.append(item)
    missing_states = REQUIRED_STATES - states
    if missing_states:
        _fail("DEVTOOLS_MATRIX_COVERAGE", "DevTools matrix is missing required states", "matrix.state")
    return normalized


def evaluate_events(
    events: list[Mapping[str, Any]], matrix: list[Mapping[str, Any]], *, gate: str = "qa-2"
) -> dict[str, Any]:
    """Return a sanitized QA verdict from raw events and matrix evidence."""

    if gate not in {"qa-1", "qa-2"}:
        _fail("DEVTOOLS_GATE", "gate must be qa-1 or qa-2", "gate")
    raw = validate_events(events)
    rows = validate_matrix(matrix)
    types = [event["type"] for event in raw]
    findings: list[str] = []

    required_findings = [("project-open", "exact project was not opened"), ("compile", "compile event is missing"), ("screenshot", "screenshot evidence is missing")]
    if gate == "qa-2":
        required_findings.extend(
            [
                ("upload-note", "upload note is missing"),
                ("platform-readback", "platform read-back is missing"),
                ("final-compile", "missing-final-compile"),
            ]
        )
    for event_type, finding in required_findings:
        if event_type not in types:
            findings.append(finding)

    for event in raw:
        for defect in event.get("defects", []):
            if defect in DEFECTS and defect not in findings:
                findings.append(defect)

    compile_event = next((event for event in raw if event["type"] == "compile"), None)
    final_compile = next((event for event in raw if event["type"] == "final-compile"), None)
    candidate_sha = compile_event.get("source_sha") if compile_event else None
    final_sha = final_compile.get("source_sha") if final_compile else None
    if gate == "qa-2" and compile_event and final_compile and candidate_sha != final_sha:
        findings.append("final compile source identity differs")
    final_provenance = (
        final_compile.get("compile_provenance") if final_compile else compile_event.get("compile_provenance") if gate == "qa-1" and compile_event else None
    )

    row_by_key = {(row["route"], row["device"], row["state"]): row for row in rows}
    screenshots = [event for event in raw if event["type"] == "screenshot"]
    screenshot_keys = set()
    for screenshot in screenshots:
        key = (screenshot["route"], screenshot["device"], screenshot["state"])
        screenshot_keys.add(key)
        row = row_by_key.get(key)
        if row is None:
            findings.append("screenshot is outside the declared matrix")
            continue
        if candidate_sha is not None and screenshot["source_sha"] != candidate_sha:
            findings.append("screenshot source identity differs from candidate")
        if screenshot["screenshot_hash"] != row["screenshot_hash"]:
            findings.append("screenshot hash differs from matrix evidence")
    for row_key in row_by_key:
        if row_key not in screenshot_keys:
            findings.append(f"matrix screenshot missing: {row_key[2]}")

    if candidate_sha is None:
        findings.append("matrix source identity cannot be verified")
    else:
        for row in rows:
            if row["source_sha"] != candidate_sha:
                findings.append("matrix source identity differs from candidate")
                break
    if final_provenance is None:
        if gate == "qa-2" and "final-compile" in types:
            findings.append("final compile provenance is missing")
    else:
        for row in rows:
            if row["final_compile_provenance"] != final_provenance:
                findings.append("matrix final-compile provenance differs from final compile")
                break

    upload_notes = [event for event in raw if event["type"] == "upload-note"]
    readbacks = [event for event in raw if event["type"] == "platform-readback"]
    if upload_notes and readbacks and upload_notes[-1]["candidate_digest"] != readbacks[-1]["candidate_digest"]:
        findings.append("upload note and platform read-back candidate differ")
    findings = list(dict.fromkeys(findings))

    evidence = []
    for event in screenshots:
        row = row_by_key.get((event["route"], event["device"], event["state"]))
        evidence_row = {
            "route": event["route"],
            "device": event["device"],
            "state": event["state"],
            "source_sha": event["source_sha"],
            "screenshot_hash": event["screenshot_hash"],
            "final_compile_provenance": final_provenance,
            "ref": "redacted:devtools-screenshot",
            "sanitized": True,
            "matrix_bound": row is not None,
        }
        if row is not None:
            evidence_row.update(
                {
                    "viewport": row["viewport"],
                    "role": row["role"],
                    "data_state": row["data_state"],
                    "tool": row["tool"],
                    "runtime": row["runtime"],
                    "observed_at": row["observed_at"],
                    "source_identity": row.get("source_identity", row["source_sha"]),
                    "before_hash": row.get("before_hash"),
                    "after_hash": row.get("after_hash", row["screenshot_hash"]),
                }
            )
        evidence.append(evidence_row)
    return {
        "result": "QA_PASS" if not findings else "QA_FAIL",
        "findings": findings,
        "automated_checks_passed": not findings,
        "verified_device": False,
        "candidate_sha": candidate_sha,
        "final_compile_provenance": final_provenance,
        "matrix_rows": len(rows),
        "evidence_mode": "sanitized-persisted",
        "evidence": evidence,
        "limitations": ["Simulator evidence does not prove physical-device behavior."],
    }


@contextmanager
def _fixture_server(events: list[Mapping[str, Any]]) -> Iterator[str]:
    """Serve only an in-memory fixture on loopback for record/replay tests."""

    body = json.dumps(events, ensure_ascii=False, sort_keys=True).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib protocol name
            if self.path != "/events.json":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/events.json"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def run_hermetic_qa(
    events: list[Mapping[str, Any]], matrix: list[Mapping[str, Any]], *, gate: str = "qa-2"
) -> dict[str, Any]:
    """Replay raw events through an ephemeral localhost adapter."""

    with _fixture_server(events) as fixture_url:
        raw_bytes = urllib.request.urlopen(fixture_url, timeout=2).read()
    replayed = json.loads(raw_bytes.decode("utf-8"))
    result = evaluate_events(replayed, matrix, gate=gate)
    result.update(
        {
            "adapter": {
                "transport": "ephemeral-localhost",
                "fixture_ref": "redacted:devtools-events",
                "external_network_events": [],
                "platform_mutation_events": [],
            },
            "raw_event_digest": "sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
        }
    )
    return result


def run_hermetic_qa1(events: list[Mapping[str, Any]], matrix: list[Mapping[str, Any]]) -> dict[str, Any]:
    """QA-1 alias: candidate compile and Simulator evidence only."""

    result = run_hermetic_qa(events, matrix, gate="qa-1")
    result["gate"] = "qa-1"
    return result


def run_hermetic_qa2(events: list[Mapping[str, Any]], matrix: list[Mapping[str, Any]]) -> dict[str, Any]:
    """QA-2 alias: upload/read-back and final-compile evidence."""

    result = run_hermetic_qa(events, matrix, gate="qa-2")
    result["gate"] = "qa-2"
    return result


def prerequisite_missing(
    *, devtools_available: bool, qa_run_id: str, computer_use_available: bool = True
) -> dict[str, Any]:
    if not _alias(qa_run_id):
        _fail("DEVTOOLS_RUN_ID", "qa_run_id must be a stable alias", "qa_run_id")
    missing = []
    if not devtools_available:
        missing.append("wechat-devtools")
    if not computer_use_available:
        missing.append("computer-use")
    if not missing:
        _fail("DEVTOOLS_PREREQUISITE_UNEXPECTED", "DevTools and Computer Use are available", "prerequisites")
    return {
        "execution_state": "unavailable",
        "result": "none",
        "control_outcome": "qa-prerequisite-missing",
        "qa_run_id": qa_run_id,
        "missing_prerequisites": missing,
    }
