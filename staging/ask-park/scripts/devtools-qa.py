#!/usr/bin/env python3
"""Hermetic DevTools QA raw-event evaluator."""

from __future__ import annotations

import copy
from typing import Any, Mapping


EVENTS = {"project-open", "compile", "screenshot", "upload-note", "platform-readback", "final-compile"}
DEFECTS = {"duplicate-title", "one-character-wrap", "double-safe-area", "stale-copy", "stale-package", "alignment", "removed-control", "missing-final-compile"}


class DevToolsQAError(ValueError):
    def __init__(self, code: str, message: str, path: str = "devtools-qa") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "devtools-qa") -> None:
    raise DevToolsQAError(code, message, path)


def validate_events(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(events, list) or not events:
        _fail("DEVTOOLS_EVENTS_REQUIRED", "raw event list is required", "events")
    normalized: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping) or event.get("type") not in EVENTS:
            _fail("DEVTOOLS_EVENT_UNKNOWN", "event type is outside the raw adapter enum", "events.type")
        if event.get("external_network") is True or event.get("platform_mutation") is True:
            _fail("DEVTOOLS_EXTERNAL_SIDE_EFFECT", "fixture adapter cannot perform external mutation", "events")
        normalized.append(copy.deepcopy(dict(event)))
    return normalized


def evaluate_events(events: list[Mapping[str, Any]], matrix: list[Mapping[str, Any]]) -> dict[str, Any]:
    raw = validate_events(events)
    types = [event["type"] for event in raw]
    findings: list[str] = []
    if "project-open" not in types:
        findings.append("exact project was not opened")
    if "compile" not in types:
        findings.append("compile event is missing")
    if "final-compile" not in types:
        findings.append("missing-final-compile")
    if "screenshot" not in types:
        findings.append("screenshot evidence is missing")
    for event in raw:
        for defect in event.get("defects", []):
            if defect in DEFECTS and defect not in findings:
                findings.append(defect)
    candidate_sha = next((event.get("source_sha") for event in raw if event["type"] == "compile"), None)
    final_sha = next((event.get("source_sha") for event in raw if event["type"] == "final-compile"), None)
    if candidate_sha != final_sha:
        findings.append("final compile source identity differs")
    upload_notes = [event for event in raw if event["type"] == "upload-note"]
    readbacks = [event for event in raw if event["type"] == "platform-readback"]
    if upload_notes and readbacks and upload_notes[-1].get("candidate_digest") != readbacks[-1].get("candidate_digest"):
        findings.append("upload note and platform read-back candidate differ")
    result = "QA_PASS" if not findings else "QA_FAIL"
    return {"result": result, "findings": findings, "automated_checks_passed": not findings, "verified_device": False, "candidate_sha": candidate_sha, "matrix_rows": len(matrix), "evidence": {"sanitized": True, "refs": ["redacted:devtools-before", "redacted:devtools-after"]}, "limitations": ["Simulator does not prove physical-device behavior."]}


def prerequisite_missing(*, devtools_available: bool, qa_run_id: str) -> dict[str, Any]:
    if devtools_available:
        _fail("DEVTOOLS_PREREQUISITE_UNEXPECTED", "DevTools is available", "devtools_available")
    return {"execution_state": "unavailable", "result": "none", "control_outcome": "qa-prerequisite-missing", "qa_run_id": qa_run_id}
