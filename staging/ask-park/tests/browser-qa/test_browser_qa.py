import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "browser-qa.py"
FIXTURES = ROOT / "fixtures" / "browser-qa"


def load_qa():
    spec = importlib.util.spec_from_file_location("ask_park_browser_qa", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BrowserQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qa = load_qa()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_matching_candidate_target_and_full_matrix_pass(self):
        result = self.qa.compare_candidate_target(self.fixture("candidate-site-valid.json"), self.fixture("target-site-valid.json"), self.fixture("matrix-valid.json"))
        self.assertEqual(result["result"], "QA_PASS")
        self.assertTrue(result["automated_checks_passed"])
        self.assertEqual(result["matrix_rows"], 8)

    def test_stale_bundle_mock_marker_and_deep_link_drift_fail_with_findings(self):
        result = self.qa.compare_candidate_target(self.fixture("candidate-site-valid.json"), self.fixture("target-stale.json"), self.fixture("matrix-valid.json"))
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertGreaterEqual(len(result["findings"]), 3)

    def test_missing_browser_is_prerequisite_missing_not_blocked(self):
        state = self.qa.prerequisite_missing(**self.fixture("browser-missing.json"))
        self.assertEqual(state["result"], "none")
        self.assertEqual(state["control_outcome"], "qa-prerequisite-missing")

    def test_matrix_missing_required_state_fails(self):
        matrix = self.fixture("matrix-valid.json")[:-1]
        with self.assertRaises(self.qa.BrowserQAError) as raised:
            self.qa.validate_matrix(matrix)
        self.assertEqual(raised.exception.code, "BROWSER_MATRIX_COVERAGE")

    def test_raw_candidate_target_checks_are_provider_free_and_do_not_mutate(self):
        candidate = self.fixture("candidate-site-valid.json")
        target = self.fixture("target-site-valid.json")
        original = json.dumps((candidate, target), sort_keys=True)
        self.qa.compare_candidate_target(candidate, target, self.fixture("matrix-valid.json"))
        self.assertEqual(json.dumps((candidate, target), sort_keys=True), original)

    def test_docs_define_browser_qa_boundary(self):
        text = (ROOT / "quality" / "browser-qa.md").read_text(encoding="utf-8")
        for phrase in ("QA-1", "QA-2", "deep links", "mock markers", "prerequisite-missing", "localhost", "zero network"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
