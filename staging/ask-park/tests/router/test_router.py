import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "scripts" / "router.py"
STATE_FIXTURES = ROOT / "fixtures" / "state"
LIFECYCLE_FIXTURES = ROOT / "fixtures" / "lifecycle"
ROUTER_FIXTURES = ROOT / "fixtures" / "router"


def load_router():
    spec = importlib.util.spec_from_file_location("ask_park_router", ROUTER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RouterTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router = load_router()
        cls.cases = json.loads((ROUTER_FIXTURES / "cases.json").read_text(encoding="utf-8"))

    def state(self, name="valid-state.json"):
        return json.loads((STATE_FIXTURES / name).read_text(encoding="utf-8"))

    def lifecycle_state(self, name):
        return json.loads((LIFECYCLE_FIXTURES / name).read_text(encoding="utf-8"))

    def assertCode(self, code, operation, *args, **kwargs):
        with self.assertRaises(self.router.RouterError) as raised:
            operation(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)


class ClassificationTests(RouterTestCase):
    def test_explicit_and_natural_language_intents(self):
        for case in self.cases["classification"]:
            self.assertEqual(self.router.classify_intent(case["input"]), case["intent"])
        self.assertEqual(self.router.classify_intent({"intent": "release"}), "release")

    def test_ambiguous_or_unclassified_intent_is_not_guessed(self):
        self.assertCode("ROUTER_INTENT_AMBIGUOUS", self.router.classify_intent, "继续发布上线")
        self.assertCode("ROUTER_INTENT_UNCLASSIFIED", self.router.classify_intent, "随便看看")


class RoutingTests(RouterTestCase):
    def test_new_request_selects_plan_and_renders_all_anchors(self):
        state = self.state()
        for module in self.router.MODULES:
            state["modules"][module]["activity_state"] = "locked"
            state["modules"][module]["evidence_state"] = "absent"
            state["modules"][module]["receipt_id"] = None
        state["modules"]["plan"]["activity_state"] = "current"
        state["current_module"] = "plan"
        original = copy.deepcopy(state)

        decision = self.router.route(state, "new")

        self.assertEqual(decision.selected_module, "plan")
        self.assertEqual(decision.control_outcome, "missing-evidence")
        self.assertEqual(list(decision.progress_map), self.cases["map_order"])
        for section in self.cases["operator_sections"]:
            self.assertIn(section, decision.rendered)
        self.assertEqual(state, original)

    def test_router_selects_earliest_required_module_lacking_valid_evidence(self):
        state = self.state()
        state["modules"]["build"]["evidence_state"] = "absent"
        state["modules"]["build"]["activity_state"] = "current"
        state["modules"]["experience"]["activity_state"] = "locked"
        state["current_module"] = "build"

        decision = self.router.route(state, "continuation")

        self.assertEqual(decision.selected_module, "build")
        self.assertEqual(decision.control_outcome, "missing-evidence")
        self.assertEqual(decision.next_verifiable_step, "Load the Build contract and establish its first valid evidence receipt.")

    def test_failed_or_blocked_module_remains_current_and_failure_overlays_diagnose(self):
        state = self.state()
        state["modules"]["experience"]["activity_state"] = "failed"
        state["current_module"] = "experience"
        failed = self.router.route(state, "continuation")
        self.assertEqual(failed.selected_module, "experience")
        self.assertEqual(failed.progress_map["experience"]["activity_state"], "failed")

        failure = self.router.route(state, "failure")
        self.assertEqual(failure.selected_module, "experience")
        self.assertTrue(failure.diagnose_requested)
        self.assertIn("references/transition-contract.md", failure.load_contracts)

        reported_failure = self.router.route(self.state(), "failure")
        self.assertTrue(reported_failure.diagnose_requested)
        self.assertEqual(reported_failure.reason_code, "failure-diagnose-overlay")
        self.assertTrue(reported_failure.next_verifiable_step.startswith("Load Diagnose"))

        state["modules"]["experience"]["activity_state"] = "blocked-external"
        blocked = self.router.route(state, "continuation")
        self.assertEqual(blocked.selected_module, "experience")
        self.assertEqual(blocked.control_outcome, "blocked-external")

    def test_release_route_retains_release_as_formal_terminal_current_module(self):
        state = self.lifecycle_state("released-ready.json")
        state["project_state"] = "released"
        state["modules"]["release"]["activity_state"] = "completed"
        state["modules"]["release"]["evidence_state"] = "valid"
        state["modules"]["release"]["receipt_id"] = "release-r1"
        state["human_gate"] = self.lifecycle_state("human-read-back.json")

        decision = self.router.route(state, "release")

        self.assertEqual(decision.selected_module, "release")
        self.assertEqual(decision.current_module, "release")
        self.assertEqual(decision.reason_code, "formal-release-complete")

        legacy = copy.deepcopy(state)
        legacy.pop("project_state")
        legacy["project_terminal_state"] = "released"
        legacy_decision = self.router.route(legacy, "release")
        self.assertEqual(legacy_decision.current_module, "release")
        self.assertEqual(legacy_decision.reason_code, "formal-release-complete")

        target = self.lifecycle_state("experience-completed.json")
        target["modules"]["device"]["activity_state"] = "completed"
        target["modules"]["device"]["evidence_state"] = "valid"
        target["modules"]["device"]["receipt_id"] = "device-r1"
        target["modules"]["release"] = {
            "applicability": "not-applicable",
            "activity_state": "not-applicable",
            "evidence_state": "not-applicable",
            "receipt_id": None,
            "not_applicable_reason": "Target stops before Release.",
        }
        target.pop("project_state")
        target["project_terminal_state"] = "target-achieved"
        target_decision = self.router.route(target, "continuation")
        self.assertEqual(target_decision.reason_code, "terminal-project-state")

    def test_conflicts_and_authority_are_explicit_control_outcomes(self):
        state = self.state()
        self.assertEqual(
            self.router.route(state, "takeover", source_conflict=True).control_outcome,
            "needs-human-state-reconciliation",
        )
        self.assertEqual(
            self.router.route(state, "takeover", baseline_conflict=True).control_outcome,
            "baseline-conflict",
        )
        self.assertEqual(
            self.router.route(state, "release", authority_required=True).control_outcome,
            "blocked-external",
        )

    def test_router_owns_causal_invalidation_and_rewinds_to_earliest_module(self):
        state = self.lifecycle_state("experience-completed.json")
        receipts = {
            receipt["receipt_id"]: receipt
            for receipt in (
                self.lifecycle_state("valid-build-receipt.json"),
                self.lifecycle_state("valid-cloudbase-receipt.json"),
                self.lifecycle_state("valid-experience-receipt.json"),
            )
        }

        decision = self.router.route(
            state,
            "continuation",
            receipts=receipts,
            changed_fields=["source.commit_sha"],
        )

        self.assertEqual(decision.selected_module, "build")
        self.assertEqual(decision.state["current_module"], "build")
        self.assertEqual(decision.invalidated_receipt_ids, ("build-r1", "cloudbase-r1", "experience-r1"))
        self.assertNotIn("next_module", decision.state)

    def test_missing_causal_receipts_becomes_control_outcome_instead_of_inference(self):
        state = self.state()
        decision = self.router.route(state, "continuation", changed_fields=["source.commit_sha"])
        self.assertEqual(decision.control_outcome, "needs-human-state-reconciliation")
        self.assertEqual(decision.reason_code, "causal-receipt-missing")


if __name__ == "__main__":
    unittest.main()
