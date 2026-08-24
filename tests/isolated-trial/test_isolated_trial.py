import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "isolated-trial.py"
FIXTURE = ROOT / "fixtures" / "isolated-trial" / "trial-fixture.json"


def load_trial():
    spec = importlib.util.spec_from_file_location("ask_park_isolated_trial", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class IsolatedTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trial = load_trial()

    def test_synthetic_trial_catches_browser_and_devtools_defects(self):
        result = self.trial.run_trial()
        self.assertEqual(result["browser"], {"pass": "QA_PASS", "defect": "QA_FAIL", "restore": "QA_PASS", "candidate_sha_unchanged": True})
        self.assertEqual(result["devtools"]["pass"], "QA_PASS")
        self.assertEqual(result["devtools"]["defect"], "QA_FAIL")
        self.assertEqual(result["devtools"]["stale_package"], "QA_FAIL")
        self.assertEqual(result["devtools"]["missing_final_compile"], "QA_FAIL")
        self.assertEqual(result["devtools"]["restore"], "QA_PASS")
        self.assertTrue(result["devtools"]["candidate_sha_unchanged"])
        self.assertTrue(result["devtools"]["project_bound"])
        self.assertEqual(result["devtools"]["candidate_sha_unchanged"], result["browser"]["candidate_sha_unchanged"])
        self.assertEqual(result["external_network_events"], [])
        self.assertEqual(result["mutation_events"], [])
        self.assertTrue(result["artifact_tree_clean"])
        self.assertNotIn("wechat-xingqiu", result["forbidden_targets_touched"])
        self.assertNotIn("production-cloudbase", result["forbidden_targets_touched"])
        self.assertTrue(result["touched_targets"])

    def test_repair_is_new_candidate_with_fresh_evidence(self):
        result = self.trial.run_trial()
        self.assertEqual(result["repair"]["result"], "QA_PASS")
        self.assertTrue(result["repair"]["fresh_evidence"])
        self.assertNotEqual(result["repair"]["new_candidate_sha"], result["candidate_source_sha"])

    def test_physical_device_is_blocked_only_after_automation(self):
        result = self.trial.run_trial()
        self.assertTrue(result["physical_device"]["automation_passed"])
        self.assertEqual(result["physical_device"]["result"], "QA_BLOCKED")
        self.assertEqual(result["physical_device"]["route_kind"], "human-gate")
        self.assertEqual(result["physical_device"]["diagnose"], "standby")
        self.assertEqual(result["physical_device"]["gate"], "awaiting-human")

    def test_three_failures_escalate_and_fourth_is_rejected(self):
        result = self.trial.run_trial()
        self.assertEqual(result["repair_loop"]["third_result"], "QA_FAIL")
        self.assertEqual(result["repair_loop"]["third_control_outcome"], "needs-park-decision")
        self.assertTrue(result["repair_loop"]["fourth_rejected"])

    def test_trial_fixture_is_synthetic_and_has_no_verdict(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertNotIn("verdict", fixture)
        self.assertNotIn("expected_result", fixture)
        self.assertEqual(fixture["transport"], "synthetic-localhost-only")
        self.assertNotIn("wechat-xingqiu", json.dumps(fixture))
        self.assertNotIn("production-cloudbase", json.dumps(fixture))
        self.assertFalse(self.trial._safe({"ref": "file:///tmp/secret.json"}))
        self.assertFalse(self.trial._safe({"ref": "~/private.json"}))

    def test_docs_define_isolation_and_ordering(self):
        text = (ROOT / "quality" / "isolated-trial.md").read_text(encoding="utf-8")
        for phrase in ("synthetic-reader-trial-v1", "stale live bundle", "duplicate title", "double safe area", "stale package", "QA_BLOCKED", "awaiting-human", "no blind fourth", "read-only"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
