import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "qa-evaluator.py"
FIXTURES = ROOT / "fixtures" / "qa-evaluator"


def load_evaluator():
    spec = importlib.util.spec_from_file_location("ask_park_qa_evaluator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = load_evaluator()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assertCode(self, code, operation, *args, **kwargs):
        with self.assertRaises(self.evaluator.EvaluatorError) as raised:
            operation(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_distinct_fresh_readonly_evaluator_can_pass(self):
        packet = self.fixture("pass-packet.json")
        validated = self.evaluator.validate_packet(packet)
        self.assertEqual(validated["verdict"], "QA_PASS")
        self.assertNotEqual(validated["worker_identity"], validated["evaluator_identity"])

    def test_self_signing_and_candidate_edit_are_rejected(self):
        packet = self.fixture("pass-packet.json")
        packet["evaluator_identity"] = packet["worker_identity"]
        self.assertCode("QA_EVALUATOR_NOT_INDEPENDENT", self.evaluator.validate_packet, packet)
        packet = self.fixture("pass-packet.json")
        packet["candidate_sha_after"] = "sha256:" + "f" * 64
        self.assertCode("QA_CANDIDATE_EDITED", self.evaluator.validate_packet, packet)

    def test_fail_requires_findings_and_blocked_requires_automation_and_gate(self):
        packet = self.fixture("fail-packet.json")
        self.assertEqual(self.evaluator.validate_packet(packet)["verdict"], "QA_FAIL")
        packet["findings"] = []
        self.assertCode("QA_FAIL_FINDINGS", self.evaluator.validate_packet, packet)
        blocked = self.fixture("blocked-packet.json")
        self.assertEqual(self.evaluator.validate_packet(blocked)["verdict"], "QA_BLOCKED")
        blocked["automation_passed"] = False
        self.assertCode("QA_BLOCKED_AUTOMATION", self.evaluator.validate_packet, blocked)
        passed = self.fixture("pass-packet.json")
        passed["automation_passed"] = False
        self.assertCode("QA_PASS_AUTOMATION", self.evaluator.validate_packet, passed)

    def test_three_attempt_loop_escalates_without_fourth_repair(self):
        state = self.evaluator.start_attempt(worker_identity="worker-build-a", evaluator_identity="evaluator-fresh-b", candidate_sha="sha256:" + "a" * 64, worktree_sha="sha256:" + "a" * 64, issue_contract_id="issue-24")
        for attempt in (1, 2, 3):
            packet = self.fixture("fail-packet.json")
            packet["candidate_sha_before"] = "sha256:" + chr(96 + attempt) * 64
            packet["candidate_sha_after"] = packet["candidate_sha_before"]
            packet["worktree_sha_before"] = packet["candidate_sha_before"]
            packet["worktree_sha_after"] = packet["candidate_sha_before"]
            packet["attempt"] = attempt
            state["attempt"] = attempt
            state = self.evaluator.complete_attempt(state, packet)
            if attempt < 3:
                state = self.evaluator.repair_attempt(state, candidate_sha="sha256:" + chr(96 + attempt + 1) * 64, worktree_sha="sha256:" + chr(96 + attempt + 1) * 64, same_contract=True, prior_result="QA_FAIL")
                state["execution_state"] = "running"
        self.assertEqual(state["result"], "QA_FAIL")
        self.assertEqual(state["control_outcome"], "needs-park-decision")
        self.assertCode("QA_THIRD_FAILURE_ESCALATION", self.evaluator.repair_attempt, state, candidate_sha="sha256:" + "e" * 64, worktree_sha="sha256:" + "f" * 64, same_contract=True, prior_result="QA_FAIL")
        self.assertEqual(state["repair_provenance"]["worktree_sha_before"], "sha256:" + "b" * 64)

    def test_repair_requires_completed_result(self):
        state = self.evaluator.start_attempt(worker_identity="worker-build-a", evaluator_identity="evaluator-fresh-b", candidate_sha="sha256:" + "a" * 64, worktree_sha="sha256:" + "a" * 64, issue_contract_id="issue-24")
        self.assertCode("QA_REPAIR_STATE", self.evaluator.repair_attempt, state, candidate_sha="sha256:" + "b" * 64, worktree_sha="sha256:" + "b" * 64, same_contract=True)

    def test_pass_or_blocked_or_identity_change_resets_attempt(self):
        state = {"execution_state": "complete", "result": "QA_PASS", "control_outcome": "none", "attempt": 2, "max_attempts": 3}
        state["candidate_sha"] = "sha256:" + "a" * 64
        reset = self.evaluator.repair_attempt(state, candidate_sha="sha256:" + "b" * 64, worktree_sha="sha256:" + "c" * 64, same_contract=True, prior_result="QA_PASS")
        self.assertEqual(reset["attempt"], 1)
        self.assertIsNone(reset["packet"])
        self.assertCode("QA_ATTEMPT_INVALID", self.evaluator.start_attempt, worker_identity="worker-a", evaluator_identity="evaluator-b", candidate_sha="sha256:" + "a" * 64, worktree_sha="sha256:" + "b" * 64, issue_contract_id="issue-24", attempt=0)
        self.assertCode("QA_ATTEMPT_INVALID", self.evaluator.start_attempt, worker_identity="worker-a", evaluator_identity="evaluator-b", candidate_sha="sha256:" + "a" * 64, worktree_sha="sha256:" + "b" * 64, issue_contract_id="issue-24", attempt=4)
        state["result"] = "QA_FAIL"
        reset = self.evaluator.repair_attempt(state, candidate_sha="sha256:" + "c" * 64, worktree_sha="sha256:" + "d" * 64, same_contract=False, prior_result="QA_FAIL", issue_contract_id="issue-25", evaluator_identity="evaluator-c")
        self.assertEqual(reset["attempt"], 1)
        self.assertEqual(reset["issue_contract_id"], "issue-25")
        self.assertEqual(reset["evaluator_identity"], "evaluator-c")

    def test_no_evaluator_is_prerequisite_missing_not_blocked(self):
        state = self.evaluator.prerequisite_missing(origin_module="build")
        self.assertEqual(state["qa"]["execution_state"], "unavailable")
        self.assertEqual(state["qa"]["result"], "none")
        self.assertEqual(state["qa"]["control_outcome"], "qa-prerequisite-missing")

    def test_fixtures_reject_verdict_conversation_and_candidate_mutation(self):
        for name in ("self-signed-invalid.json", "candidate-edited-invalid.json", "reuse-invalid.json"):
            packet = self.fixture(name)
            with self.assertRaises(self.evaluator.EvaluatorError):
                self.evaluator.validate_packet(packet)
        packet = self.fixture("fail-packet.json")
        packet["findings"] = ["next_module=release"]
        self.assertCode("QA_PACKET_PRIVATE_FIELD", self.evaluator.validate_packet, packet)
        packet = self.fixture("fail-packet.json")
        packet["findings"] = [{"route_to": "release"}]
        self.assertCode("QA_PACKET_PRIVATE_FIELD", self.evaluator.validate_packet, packet)
        packet = self.fixture("fail-packet.json")
        packet["exclusions"] = ["cloud://private-target"]
        self.assertCode("QA_PACKET_PRIVATE_FIELD", self.evaluator.validate_packet, packet)

    def test_docs_define_independence_and_bounded_loop(self):
        for name, phrases in {
            "QA-AGENT.md": ("fresh-context", "read-only", "QA_PASS", "QA_FAIL", "QA_BLOCKED"),
            "regression-loop.md": ("attempt one", "attempt three", "no blind fourth", "Ask Park"),
        }.items():
            text = (ROOT / "quality" / name).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
