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

        raw = self.qa.run_hermetic_qa2(self.fixture("candidate-site-valid.json"), self.fixture("target-site-valid.json"), self.fixture("matrix-valid.json"))
        self.assertEqual(raw["result"], "QA_PASS")
        self.assertTrue(raw["adapter"]["candidate_server_ref"].startswith("redacted:"))
        self.assertEqual(raw["adapter"]["external_network_events"], [])
        self.assertEqual(raw["adapter"]["mutation_events"], [])
        self.assertTrue(raw["evidence"]["before"]["sanitized"])
        self.assertTrue(raw["evidence"]["after"]["sanitized"])
        qa1 = self.qa.capture_qa1(self.fixture("candidate-site-valid.json"), self.fixture("matrix-valid.json"))
        self.assertTrue(qa1["browser_first"])
        self.assertEqual(len(qa1["captures"]), 8)

    def test_stale_bundle_mock_marker_and_deep_link_drift_fail_with_findings(self):
        result = self.qa.compare_candidate_target(self.fixture("candidate-site-valid.json"), self.fixture("target-stale.json"), self.fixture("matrix-valid.json"))
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertGreaterEqual(len(result["findings"]), 3)

        candidate = self.fixture("candidate-site-valid.json")
        matrix = self.fixture("matrix-valid.json")
        matrix[0]["source_identity"] = "other-candidate"
        result = self.qa.compare_candidate_target(candidate, self.fixture("target-site-valid.json"), matrix)
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("matrix source identity differs from candidate", result["findings"])
        matrix = self.fixture("matrix-valid.json")
        matrix[0]["after_hash"] = "sha256:" + "9" * 64
        result = self.qa.compare_candidate_target(self.fixture("candidate-site-valid.json"), self.fixture("target-site-valid.json"), matrix)
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("matrix after hashes differ from target render digest", result["findings"])

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

    def test_pass_defect_restore_pass_keeps_candidate_identity(self):
        candidate = self.fixture("candidate-site-valid.json")
        target = self.fixture("target-site-valid.json")
        matrix = self.fixture("matrix-valid.json")
        source_sha = candidate["source_sha"]
        self.assertEqual(self.qa.compare_candidate_target(candidate, target, matrix)["result"], "QA_PASS")
        target["js_digest"] = "sha256:" + "d" * 64
        failed = self.qa.run_hermetic_qa2(candidate, target, matrix)
        self.assertEqual(failed["result"], "QA_FAIL")
        self.assertTrue(failed["evidence"]["after"]["sanitized"])
        restored = self.qa.run_hermetic_qa2(candidate, self.fixture("target-site-valid.json"), matrix)
        self.assertEqual(restored["result"], "QA_PASS")
        self.assertEqual(restored["candidate_source_sha"], source_sha)

    def test_raw_site_private_and_unknown_fields_fail(self):
        candidate = self.fixture("candidate-site-valid.json")
        candidate["private_url"] = "cloud://private"
        with self.assertRaises(self.qa.BrowserQAError):
            self.qa.validate_site(candidate)
        matrix = self.fixture("matrix-valid.json")
        matrix[0]["next_module"] = "release"
        with self.assertRaises(self.qa.BrowserQAError):
            self.qa.validate_matrix(matrix)
        candidate = self.fixture("candidate-site-valid.json")
        candidate.pop("compile_provenance")
        with self.assertRaises(self.qa.BrowserQAError):
            self.qa.validate_site(candidate)
        candidate = self.fixture("candidate-site-valid.json")
        candidate["dom_snapshot"] = "unexpected"
        with self.assertRaises(self.qa.BrowserQAError):
            self.qa.validate_site(candidate)

    def test_docs_define_browser_qa_boundary(self):
        text = (ROOT / "quality" / "browser-qa.md").read_text(encoding="utf-8")
        for phrase in ("QA-1", "QA-2", "deep links", "mock markers", "prerequisite-missing", "localhost", "zero network"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
