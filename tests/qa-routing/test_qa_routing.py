import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "qa-routing.py"
STATE_FIXTURES = ROOT / "fixtures" / "lifecycle"
QA_FIXTURES = ROOT / "fixtures" / "qa-evaluator"
ROUTING_FIXTURES = ROOT / "fixtures" / "qa-routing"


def load_routing():
    spec = importlib.util.spec_from_file_location("ask_park_qa_routing", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class QARoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routing = load_routing()

    def fixture(self, directory, name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    def state(self, name):
        return self.fixture(STATE_FIXTURES, name)

    def packet(self, name):
        return self.fixture(QA_FIXTURES, name)

    def receipts(self):
        return {
            receipt["receipt_id"]: receipt
            for receipt in (
                self.state("valid-build-receipt.json"),
                self.state("valid-cloudbase-receipt.json"),
                self.state("valid-experience-receipt.json"),
            )
        }

    def assertCode(self, code, operation, *args, **kwargs):
        with self.assertRaises(self.routing.QARoutingError) as raised:
            operation(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_qa_emits_advisory_only_and_cannot_self_promote(self):
        packet = self.packet("fail-packet.json")
        advisory = self.routing.advisory_from_packet(packet)
        self.assertEqual(advisory["verdict"], "QA_FAIL")
        self.assertEqual(advisory["advisory_earliest_layer"], "build")
        self.assertEqual(advisory["candidate_sha_before"], packet["candidate_sha_before"])
        self.assertEqual(advisory["worktree_sha_after"], packet["worktree_sha_after"])
        self.assertEqual(advisory["limitations"], packet["limitations"])
        self.assertNotIn("current_module", advisory)
        self.assertNotIn("selected_module", advisory)
        self.assertNotIn("invalidated_receipt_ids", advisory)
        self.assertNotIn("next_module", advisory)

        forged = copy.deepcopy(packet)
        forged["selected_module"] = "release"
        self.assertCode("QA_PACKET_INVALID", self.routing.advisory_from_packet, forged)

        diagnosis = self.fixture(ROUTING_FIXTURES, "diagnosis-device.json")
        diagnosis["recovery_goal"] = "inspect https://private.example"
        self.assertCode(
            "QA_DIAGNOSIS_PRIVATE",
            self.routing.route_qa_result,
            self.state("experience-completed.json"),
            packet,
            diagnosis=diagnosis,
        )
        diagnosis["recovery_goal"] = "fix /Users/private AppID=wx123"
        self.assertCode(
            "QA_DIAGNOSIS_PRIVATE",
            self.routing.route_qa_result,
            self.state("experience-completed.json"),
            packet,
            diagnosis=diagnosis,
        )

    def test_pass_is_non_promoting_and_direct_fail_routing_is_rejected(self):
        state = self.state("experience-current.json")
        original = copy.deepcopy(state)
        passed = self.routing.route_qa_result(state, self.packet("pass-packet.json"))
        self.assertEqual(passed["route_kind"], "qa-pass-advisory")
        self.assertFalse(passed["diagnose_activated"])
        self.assertEqual(passed["state"], original)
        self.assertEqual(state, original)

        self.assertCode(
            "QA_DIAGNOSIS_REQUIRED",
            self.routing.route_qa_result,
            state,
            self.packet("fail-packet.json"),
        )

    def test_observed_device_defect_activates_diagnose_without_invalidation(self):
        state = self.state("experience-completed.json")
        packet = self.packet("fail-packet.json")
        diagnosis = self.fixture(ROUTING_FIXTURES, "diagnosis-device.json")
        result = self.routing.route_qa_result(state, packet, diagnosis=diagnosis)
        self.assertEqual(result["route_kind"], "diagnose")
        self.assertTrue(result["diagnose_activated"])
        self.assertEqual(result["incident"]["interrupted_module"], "device")
        self.assertEqual(result["incident"]["recovery_module"], "device")
        self.assertEqual(result["invalidated_receipt_ids"], [])
        self.assertEqual(result["state"]["current_module"], "device")
        self.assertEqual(result["state"]["diagnose"]["state"], "active")
        self.assertEqual(result["state"]["diagnose"]["interrupted_module"], "device")

    def test_confirmed_cause_lets_ask_park_invalidate_and_rewind(self):
        state = self.state("experience-completed.json")
        packet = self.packet("fail-packet.json")
        diagnosis = self.fixture(ROUTING_FIXTURES, "diagnosis-build.json")
        result = self.routing.route_qa_result(state, packet, diagnosis=diagnosis, receipts=self.receipts())
        self.assertEqual(result["state"]["current_module"], "build")
        self.assertEqual(result["state"]["diagnose"]["state"], "active")
        self.assertEqual(result["state"]["diagnose"]["interrupted_module"], "build")
        self.assertEqual(result["incident"]["interrupted_module"], "device")
        self.assertEqual(result["incident"]["recovery_module"], "build")
        self.assertEqual(result["invalidated_receipt_ids"], ["build-r1", "cloudbase-r1", "experience-r1"])
        self.assertEqual(result["state"]["rewind"]["earliest_invalidated_module"], "build")

        self.assertCode(
            "QA_CAUSAL_RECEIPTS_INCOMPLETE",
            self.routing.route_qa_result,
            state,
            packet,
            diagnosis=diagnosis,
            receipts={"build-r1": self.receipts()["build-r1"]},
        )

    def test_missing_human_evidence_creates_gate_without_diagnose(self):
        state = self.state("experience-completed.json")
        packet = self.packet("blocked-packet.json")
        request = self.fixture(ROUTING_FIXTURES, "human-gate-request.json")
        result = self.routing.route_qa_result(state, packet, gate_request=request)
        self.assertEqual(result["route_kind"], "human-gate")
        self.assertFalse(result["diagnose_activated"])
        self.assertEqual(result["state"]["current_module"], "device")
        self.assertEqual(result["state"]["diagnose"]["state"], "standby")
        self.assertEqual(result["state"]["human_gate"]["state"], "awaiting-human")
        self.assertEqual(result["control_outcome"], "blocked-external")
        self.assertEqual(result["state"]["control_outcome"], "blocked-external")

        active = self.state("experience-completed.json")
        active["diagnose"] = {
            "state": "active",
            "outcome": "none",
            "interrupted_module": "device",
            "recovery_goal": "recheck device evidence",
        }
        self.assertCode(
            "QA_HUMAN_GATE_DIAGNOSE_ACTIVE",
            self.routing.route_qa_result,
            active,
            packet,
            gate_request=request,
        )

    def test_human_gate_cannot_hide_a_qa_defect(self):
        packet = self.packet("blocked-packet.json")
        packet["findings"] = ["observable defect"]
        self.assertCode(
            "QA_HUMAN_GATE_DEFECT",
            self.routing.route_qa_result,
            self.state("experience-completed.json"),
            packet,
            gate_request=self.fixture(ROUTING_FIXTURES, "human-gate-request.json"),
        )

    def test_attempt_loop_resets_and_escalates_without_a_fourth_repair(self):
        sha_a = "sha256:" + "a" * 64
        sha_b = "sha256:" + "b" * 64
        sha_c = "sha256:" + "c" * 64
        state = self.routing.start_qa_attempt(
            worker_identity="worker-build-a",
            evaluator_identity="evaluator-fresh-b",
            candidate_sha=sha_a,
            worktree_sha=sha_a,
            issue_contract_id="issue-27",
        )
        for attempt, current_sha, next_sha in ((1, sha_a, sha_b), (2, sha_b, sha_c)):
            packet = self.packet("fail-packet.json")
            packet.update(
                {
                    "candidate_sha_before": current_sha,
                    "candidate_sha_after": current_sha,
                    "worktree_sha_before": current_sha,
                    "worktree_sha_after": current_sha,
                    "attempt": attempt,
                    "issue_contract_id": "issue-27",
                }
            )
            state["attempt"] = attempt
            state = self.routing.complete_qa_attempt(state, packet)
            state = self.routing.prepare_repair_attempt(
                state,
                candidate_sha=next_sha,
                worktree_sha=next_sha,
                same_contract=True,
                prior_result="QA_FAIL",
            )
            state["execution_state"] = "running"
        packet = self.packet("fail-packet.json")
        packet.update(
            {
                "candidate_sha_before": sha_c,
                "candidate_sha_after": sha_c,
                "worktree_sha_before": sha_c,
                "worktree_sha_after": sha_c,
                "attempt": 3,
                "issue_contract_id": "issue-27",
            }
        )
        state["attempt"] = 3
        state = self.routing.complete_qa_attempt(state, packet)
        self.assertEqual(state["control_outcome"], "needs-park-decision")
        self.assertCode(
            "QA_REPAIR_INVALID",
            self.routing.prepare_repair_attempt,
            state,
            candidate_sha="sha256:" + "d" * 64,
            worktree_sha="sha256:" + "d" * 64,
            same_contract=True,
            prior_result="QA_FAIL",
        )

    def test_pass_blocked_and_superseding_contract_start_at_attempt_one(self):
        sha_a = "sha256:" + "a" * 64
        sha_b = "sha256:" + "b" * 64
        state = self.routing.start_qa_attempt(
            worker_identity="worker-build-a",
            evaluator_identity="evaluator-fresh-b",
            candidate_sha=sha_a,
            worktree_sha=sha_a,
            issue_contract_id="issue-27",
        )
        packet = self.packet("pass-packet.json")
        packet["issue_contract_id"] = "issue-27"
        state = self.routing.complete_qa_attempt(state, packet)
        reset = self.routing.prepare_repair_attempt(
            state,
            candidate_sha=sha_b,
            worktree_sha=sha_b,
            same_contract=True,
            prior_result="QA_PASS",
        )
        self.assertEqual(reset["attempt"], 1)

        reset["execution_state"] = "complete"
        reset["result"] = "QA_FAIL"
        reset["candidate_sha"] = sha_b
        changed = self.routing.prepare_repair_attempt(
            reset,
            candidate_sha="sha256:" + "c" * 64,
            worktree_sha="sha256:" + "c" * 64,
            same_contract=False,
            prior_result="QA_FAIL",
            issue_contract_id="issue-28",
            evaluator_identity="evaluator-c",
        )
        self.assertEqual(changed["attempt"], 1)
        self.assertEqual(changed["issue_contract_id"], "issue-28")
        self.assertEqual(changed["evaluator_identity"], "evaluator-c")

    def test_docs_define_authority_and_repair_boundary(self):
        text = (ROOT / "quality" / "qa-routing.md").read_text(encoding="utf-8")
        for phrase in (
            "advisory",
            "Ask Park alone",
            "Diagnose",
            "human gate",
            "same-contract",
            "attempt three",
            "no blind fourth",
            "next_module",
            "QA_BLOCKED",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
