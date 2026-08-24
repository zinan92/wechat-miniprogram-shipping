#!/usr/bin/env python3
"""Run the S15 synthetic Browser + DevTools + Ask Park trial."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
SCRIPTS = ROOT / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BROWSER = _load("trial_browser", SCRIPTS / "browser-qa.py")
DEVTOOLS = _load("trial_devtools", SCRIPTS / "devtools-qa.py")
ROUTING = _load("trial_routing", SCRIPTS / "qa-routing.py")
EVALUATOR = _load("trial_evaluator", SCRIPTS / "qa-evaluator.py")
LIFECYCLE = _load("trial_lifecycle", SCRIPTS / "state-lifecycle.py")


class TrialError(ValueError):
    def __init__(self, code: str, message: str, path: str = "isolated-trial") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "isolated-trial") -> None:
    raise TrialError(code, message, path)


def _read(relative: str) -> Any:
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


def _safe(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(marker in normalized for marker in ("secret", "token", "password", "openid", "appid", "environment_id", "cookie", "private_key")):
                return False
            if not _safe(child):
                return False
    elif isinstance(value, list):
        return all(_safe(child) for child in value)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in ("http://", "https://", "cloud://", "/users/", "/private/", "wechat-xingqiu", "production-cloudbase", "customer-project")):
            return False
    return True


def _fresh_candidate(candidate: dict[str, Any], target: dict[str, Any], matrix: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    next_candidate = copy.deepcopy(candidate)
    next_target = copy.deepcopy(target)
    next_candidate["source_sha"] = "sha256:" + "b" * 64
    next_target["source_sha"] = next_candidate["source_sha"]
    next_candidate["render_digest"] = "sha256:" + "3" * 64
    next_target["render_digest"] = "sha256:" + "4" * 64
    next_matrix = copy.deepcopy(matrix)
    for row in next_matrix:
        row["before_hash"] = next_candidate["render_digest"]
        row["after_hash"] = next_target["render_digest"]
        row["source_identity"] = next_candidate["matrix_identity_alias"]
    return next_candidate, next_target, next_matrix


def _repair_loop() -> dict[str, Any]:
    sha_a = "sha256:" + "a" * 64
    sha_b = "sha256:" + "b" * 64
    fail = _read("qa-evaluator/fail-packet.json")
    state = EVALUATOR.start_attempt(worker_identity="trial-worker", evaluator_identity="trial-evaluator", candidate_sha=sha_a, worktree_sha=sha_a, issue_contract_id="synthetic-reader-trial")
    for number, current, next_sha in ((1, sha_a, sha_b), (2, sha_b, "sha256:" + "c" * 64)):
        packet = copy.deepcopy(fail)
        packet.update({"worker_identity": "trial-worker", "evaluator_identity": "trial-evaluator", "candidate_sha_before": current, "candidate_sha_after": current, "worktree_sha_before": current, "worktree_sha_after": current, "issue_contract_id": "synthetic-reader-trial", "attempt": number})
        state["attempt"] = number
        state = EVALUATOR.complete_attempt(state, packet)
        state = EVALUATOR.repair_attempt(state, candidate_sha=next_sha, worktree_sha=next_sha, same_contract=True, prior_result="QA_FAIL")
        state["execution_state"] = "running"
    packet = copy.deepcopy(fail)
    third = "sha256:" + "c" * 64
    packet.update({"worker_identity": "trial-worker", "evaluator_identity": "trial-evaluator", "candidate_sha_before": third, "candidate_sha_after": third, "worktree_sha_before": third, "worktree_sha_after": third, "issue_contract_id": "synthetic-reader-trial", "attempt": 3})
    state["attempt"] = 3
    state = EVALUATOR.complete_attempt(state, packet)
    fourth_rejected = False
    try:
        EVALUATOR.repair_attempt(state, candidate_sha="sha256:" + "d" * 64, worktree_sha="sha256:" + "d" * 64, same_contract=True, prior_result="QA_FAIL")
    except EVALUATOR.EvaluatorError:
        fourth_rejected = True
    return {"third_result": state["result"], "third_control_outcome": state["control_outcome"], "fourth_rejected": fourth_rejected}


def run_trial() -> dict[str, Any]:
    trial = _read("isolated-trial/trial-fixture.json")
    if not _safe(trial) or any(value in json.dumps(trial).lower() for value in ("wechat-xingqiu", "production-cloudbase", "customer-project")):
        _fail("TRIAL_PRIVATE_FIXTURE", "trial fixture crosses the forbidden target boundary", "trial")
    candidate = _read("browser-qa/candidate-site-valid.json")
    target = _read("browser-qa/target-site-valid.json")
    stale = _read("browser-qa/target-stale.json")
    browser_matrix = _read("browser-qa/matrix-valid.json")
    if candidate["source_sha"] != trial["browser_source_sha_raw"] or target["target_alias"] != trial["browser_target_alias_raw"]:
        _fail("TRIAL_RAW_IDENTITY", "raw Browser fixture identity does not match the trial contract", "browser")
    candidate["source_sha"] = trial["candidate_source_sha"]
    target["source_sha"] = trial["candidate_source_sha"]
    target["target_alias"] = trial["target_alias"]
    if candidate["source_sha"] != trial["browser_candidate_source_sha"] or target["target_alias"] != trial["browser_target_alias"]:
        _fail("TRIAL_CANDIDATE_BINDING", "Browser candidate/target identity does not match the trial contract", "browser")
    browser_pass = BROWSER.run_hermetic_qa2(candidate, target, browser_matrix)
    browser_fail = BROWSER.run_hermetic_qa2(candidate, stale, browser_matrix)
    browser_restore = BROWSER.run_hermetic_qa2(candidate, target, browser_matrix)

    dev_matrix = _read("devtools-qa/matrix-valid.json")
    dev_valid = _read("devtools-qa/events-valid.json")
    dev_defect = _read("devtools-qa/events-defect.json")
    dev_missing_final = _read("devtools-qa/events-missing-final-compile.json")
    if any(event_set[0]["project_alias"] != trial["devtools_project_alias_raw"] for event_set in (dev_valid, dev_defect, dev_missing_final)):
        _fail("TRIAL_RAW_IDENTITY", "raw DevTools project identity does not match the trial contract", "devtools")
    for event_set in (dev_valid, dev_defect, dev_missing_final):
        event_set[0]["project_alias"] = trial["project_alias"]
    if dev_valid[1]["source_sha"] != trial["devtools_candidate_source_sha"]:
        _fail("TRIAL_CANDIDATE_BINDING", "DevTools compile source does not match the trial contract", "devtools")
    dev_pass = DEVTOOLS.run_hermetic_qa(dev_valid, dev_matrix)
    dev_fail = DEVTOOLS.run_hermetic_qa(dev_defect, dev_matrix)
    dev_missing = DEVTOOLS.run_hermetic_qa(dev_missing_final, dev_matrix)
    dev_stale_events = copy.deepcopy(dev_valid)
    dev_stale_events[2]["defects"] = ["stale-package"]
    dev_stale = DEVTOOLS.run_hermetic_qa(dev_stale_events, dev_matrix)
    dev_restore = DEVTOOLS.run_hermetic_qa(dev_valid, dev_matrix)
    nested_runs = (browser_pass, browser_fail, browser_restore, dev_pass, dev_fail, dev_missing, dev_stale, dev_restore)
    if any(run["adapter"]["external_network_events"] or run["adapter"].get("mutation_events", run["adapter"].get("platform_mutation_events", [])) for run in nested_runs):
        _fail("TRIAL_EXTERNAL_SIDE_EFFECT", "nested Browser/DevTools adapter reported an external side effect", "surfaces")
    if browser_pass["result"] != "QA_PASS" or dev_pass["result"] != "QA_PASS":
        _fail("TRIAL_AUTOMATION_ORDER", "human gate cannot be reached before automation passes", "human")

    fresh_candidate, fresh_target, fresh_matrix = _fresh_candidate(candidate, target, browser_matrix)
    fresh = BROWSER.run_hermetic_qa2(fresh_candidate, fresh_target, fresh_matrix)
    nested_runs = nested_runs + (fresh,)
    if any(run["adapter"]["external_network_events"] or run["adapter"].get("mutation_events", run["adapter"].get("platform_mutation_events", [])) for run in (fresh,)):
        _fail("TRIAL_EXTERNAL_SIDE_EFFECT", "fresh repair adapter reported an external side effect", "repair")
    if fresh["candidate_source_sha"] == candidate["source_sha"]:
        _fail("TRIAL_REPAIR_IDENTITY", "repair did not create a new candidate identity", "repair")

    blocked = _read("qa-evaluator/blocked-packet.json")
    gate_request = {"action_type": "physical-device-observation", "action_scope": "synthetic-device-v1", "authorizing_role": "owner", "requested_at": "2026-08-24T15:30:00Z", "evidence_ref": "redacted:trial-device-gate"}
    state = _read("lifecycle/experience-completed.json")
    human = ROUTING.route_qa_result(state, blocked, gate_request=gate_request)
    if human["state"]["diagnose"]["state"] != "standby" or human["state"]["human_gate"]["state"] != "awaiting-human":
        _fail("TRIAL_HUMAN_GATE_ORDER", "physical-device requirement was not blocked after automation", "human")

    repair = _repair_loop()
    nested_network = [event for run in nested_runs for event in run["adapter"]["external_network_events"]]
    nested_mutations = [event for run in nested_runs for event in run["adapter"].get("mutation_events", run["adapter"].get("platform_mutation_events", []))]
    automation_passed = browser_pass["result"] == "QA_PASS" and dev_pass["result"] == "QA_PASS" and blocked["automation_passed"] is True
    touched_targets = [target["target_alias"], dev_matrix[0]["device"]]
    forbidden_touched = [target_alias for target_alias in touched_targets if target_alias in trial["forbidden_targets"]]
    if forbidden_touched:
        _fail("TRIAL_FORBIDDEN_TARGET", "trial touched a forbidden target alias", "targets")
    result = {
        "fixture_id": trial["fixture_id"],
        "candidate_source_sha": candidate["source_sha"],
        "browser": {"pass": browser_pass["result"], "defect": browser_fail["result"], "restore": browser_restore["result"], "candidate_sha_unchanged": browser_restore["candidate_source_sha"] == candidate["source_sha"]},
        "devtools": {"pass": dev_pass["result"], "defect": dev_fail["result"], "stale_package": dev_stale["result"], "missing_final_compile": dev_missing["result"], "restore": dev_restore["result"], "candidate_sha_unchanged": dev_restore["candidate_sha"] == dev_valid[1]["source_sha"], "project_bound": dev_valid[0]["project_alias"] == trial["project_alias"]},
        "repair": {"result": fresh["result"], "new_candidate_sha": fresh["candidate_source_sha"], "fresh_evidence": fresh["candidate_source_sha"] == fresh_candidate["source_sha"]},
        "physical_device": {"automation_passed": automation_passed, "result": "QA_BLOCKED", "route_kind": human["route_kind"], "diagnose": human["state"]["diagnose"]["state"], "gate": human["state"]["human_gate"]["state"]},
        "repair_loop": repair,
        "touched_targets": touched_targets,
        "forbidden_targets_touched": forbidden_touched,
        "external_network_events": nested_network,
        "mutation_events": nested_mutations,
        "artifact_tree_clean": False,
        "evidence_mode": trial["evidence_mode"],
        "fixture_digest": "sha256:" + hashlib.sha256(json.dumps(trial, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    if not _safe(result):
        _fail("TRIAL_OUTPUT_PRIVATE", "trial output contains private data", "result")
    with tempfile.TemporaryDirectory(prefix="ask-park-trial-") as directory:
        path = Path(directory) / "trial-result.json"
        path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        if any(marker in path.read_bytes().lower() for marker in (b"http://", b"https://", b"cloud://", b"wechat-xingqiu")):
            _fail("TRIAL_ARTIFACT_PRIVATE", "trial artifact contains forbidden bytes", "artifact")
        result["artifact_tree_clean"] = True
        path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        if any(marker in path.read_bytes().lower() for marker in (b"http://", b"https://", b"cloud://", b"wechat-xingqiu")):
            _fail("TRIAL_ARTIFACT_PRIVATE", "final trial artifact contains forbidden bytes", "artifact")
    return result
