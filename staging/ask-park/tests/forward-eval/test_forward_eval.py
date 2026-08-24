import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "forward-eval.py"
FIXTURES = ROOT / "fixtures" / "forward-eval"


def load_forward_eval():
    spec = importlib.util.spec_from_file_location("ask_park_forward_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ForwardEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eval = load_forward_eval()
        cls.manifest = json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))

    def test_full_matrix_runs_from_raw_fixtures_without_intended_verdict(self):
        result = self.eval.run_forward_evaluation(self.manifest)
        self.assertEqual(result["scenario_count"], 45)
        self.assertEqual(result["architecture_count"], 23)
        self.assertEqual(result["qa_count"], 22)
        self.assertTrue(all(row["status"] == "observed" for row in result["results"]))
        self.assertEqual(result["external_network_events"], [])
        self.assertEqual(result["mutation_events"], [])
        self.assertTrue(result["artifact_tree_clean"])

    def test_surface_pass_defect_restore_controls_and_third_attempt_escalation(self):
        result = self.eval.run_forward_evaluation(self.manifest)
        controls = result["surface_controls"]
        self.assertEqual(controls["browser"], {"pass": "QA_PASS", "defect": "QA_FAIL", "restore": "QA_PASS"})
        self.assertEqual(controls["devtools"], {"pass": "QA_PASS", "defect": "QA_FAIL", "restore": "QA_PASS"})
        self.assertEqual(controls["evaluator"]["pass"], "QA_PASS")
        self.assertEqual(controls["evaluator"]["third_result"], "QA_FAIL")
        self.assertEqual(controls["evaluator"]["third_control_outcome"], "needs-park-decision")
        self.assertTrue(controls["qa_schema"]["reset"])
        self.assertEqual(controls["state"]["pass"], "valid")
        self.assertTrue(controls["state"]["defect"])
        self.assertEqual(controls["state"]["restore"], "valid")

    def test_architecture_oracles_are_observable_state_or_result_fields(self):
        result = self.eval.run_forward_evaluation(self.manifest)
        rows = {row["id"]: row["observations"] for row in result["results"]}
        self.assertEqual(rows["A01"]["selected_module"], "plan")
        self.assertEqual(rows["A04"]["selected_module"], "device")
        self.assertTrue(rows["A07"]["diagnose_requested"])
        self.assertEqual(rows["A11"]["selected_module"], "build")
        self.assertEqual(rows["A12"]["selected_module"], "cloudbase")
        self.assertEqual(rows["A13"]["selected_module"], "experience")
        self.assertEqual(rows["A16"]["diagnose_outcome"], "unresolved")
        self.assertEqual(rows["A17"]["payment_applicability"], "not-applicable")
        self.assertEqual(rows["A21"]["current_module"], "release")
        self.assertEqual(rows["A22"], {"before": "unknown", "after": "none"})
        self.assertEqual(rows["A23"]["contract_version"], "ask-park.receipt/v2")

    def test_qa_oracles_cover_authority_prerequisites_and_privacy(self):
        result = self.eval.run_forward_evaluation(self.manifest)
        rows = {row["id"]: row["observations"] for row in result["results"]}
        self.assertEqual(rows["Q04"]["route_kind"], "human-gate")
        self.assertEqual(rows["Q04"]["diagnose"], "standby")
        self.assertEqual(rows["Q05"]["rejected"], "QA_HUMAN_GATE_DEFECT")
        self.assertEqual(rows["Q13"]["control_outcome"], "qa-prerequisite-missing")
        self.assertEqual(rows["Q14"]["browser"], "qa-prerequisite-missing")
        self.assertTrue(rows["Q19"]["artifact_tree_clean"])
        self.assertTrue(rows["Q21"]["input_unchanged"])
        self.assertTrue(rows["Q22"]["seven_anchors"])
        self.assertTrue(rows["Q22"]["qa_command_absent"])

    def test_manifest_rejects_canned_verdict_and_missing_scenario(self):
        forged = copy.deepcopy(self.manifest)
        forged[0]["expected_verdict"] = "QA_PASS"
        with self.assertRaises(self.eval.ForwardEvalError) as raised:
            self.eval.validate_manifest(forged)
        self.assertEqual(raised.exception.code, "FORWARD_INTENDED_VERDICT")

        missing = self.manifest[:-1]
        with self.assertRaises(self.eval.ForwardEvalError) as raised:
            self.eval.validate_manifest(missing)
        self.assertEqual(raised.exception.code, "FORWARD_MANIFEST_COUNT")

    def test_adapter_rejects_network_and_mutation(self):
        adapter = self.eval.RecordReplayAdapter({"fixture": {"ok": True}})
        self.assertEqual(adapter.read("fixture"), {"ok": True})
        with self.assertRaises(self.eval.ForwardEvalError):
            adapter.request("external")
        with self.assertRaises(self.eval.ForwardEvalError):
            adapter.write("external", {})
        with self.assertRaises(self.eval.ForwardEvalError):
            adapter.delete("external")

    def test_docs_define_forward_matrix_and_privacy_boundary(self):
        text = (ROOT / "quality" / "forward-evaluation.md").read_text(encoding="utf-8")
        for phrase in ("23 architecture", "22 QA", "no intended verdict", "pass", "seeded defect", "restore", "external_network_events", "artifact_tree_clean", "no blind fourth", "read-only"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
