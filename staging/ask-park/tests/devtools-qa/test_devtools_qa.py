import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "devtools-qa.py"
FIXTURES = ROOT / "fixtures" / "devtools-qa"


def load_qa():
    spec = importlib.util.spec_from_file_location("ask_park_devtools_qa", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DevToolsQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qa = load_qa()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_valid_raw_event_sequence_and_full_matrix_pass_without_device_claim(self):
        result = self.qa.evaluate_events(self.fixture("events-valid.json"), self.fixture("matrix-valid.json"))
        self.assertEqual(result["result"], "QA_PASS")
        self.assertFalse(result["verified_device"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["matrix_rows"], 9)
        self.assertTrue(result["evidence"])
        self.assertTrue(all(row["sanitized"] for row in result["evidence"]))
        self.assertTrue(all(row["matrix_bound"] for row in result["evidence"]))
        self.assertEqual(
            set(result["evidence"][0]),
            {
                "route", "device", "state", "source_sha", "screenshot_hash",
                "final_compile_provenance", "ref", "sanitized", "matrix_bound",
                "viewport", "role", "data_state", "tool", "runtime", "observed_at",
                "source_identity",
            },
        )

        replay = self.qa.run_hermetic_qa(
            self.fixture("events-valid.json"), self.fixture("matrix-valid.json")
        )
        self.assertEqual(replay["result"], "QA_PASS")
        self.assertEqual(replay["adapter"]["external_network_events"], [])
        self.assertEqual(replay["adapter"]["platform_mutation_events"], [])
        self.assertTrue(replay["adapter"]["fixture_ref"].startswith("redacted:"))
        self.assertNotIn("http://", json.dumps(replay))

    def test_render_package_and_readback_defects_fail(self):
        result = self.qa.evaluate_events(self.fixture("events-defect.json"), self.fixture("matrix-valid.json"))
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("duplicate-title", result["findings"])
        self.assertIn("double-safe-area", result["findings"])
        self.assertIn("upload note and platform read-back candidate differ", result["findings"])

    def test_missing_final_compile_is_a_fail_finding(self):
        result = self.qa.evaluate_events(
            self.fixture("events-missing-final-compile.json"), self.fixture("matrix-valid.json")
        )
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("missing-final-compile", result["findings"])

    def test_matrix_requires_a_screenshot_for_every_state(self):
        events = self.fixture("events-valid.json")
        del events[2]
        result = self.qa.evaluate_events(events, self.fixture("matrix-valid.json"))
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("matrix screenshot missing: loading", result["findings"])

    def test_qa1_candidate_render_is_separate_from_qa2_upload_readback(self):
        candidate_events = self.fixture("events-valid.json")[:11]
        matrix = self.fixture("matrix-valid.json")
        qa1 = self.qa.run_hermetic_qa1(candidate_events, matrix)
        self.assertEqual(qa1["gate"], "qa-1")
        self.assertEqual(qa1["result"], "QA_PASS")
        qa2 = self.qa.run_hermetic_qa2(candidate_events, matrix)
        self.assertEqual(qa2["gate"], "qa-2")
        self.assertEqual(qa2["result"], "QA_FAIL")
        self.assertIn("missing-final-compile", qa2["findings"])

    def test_pass_defect_restore_pass_keeps_candidate_sha(self):
        events = self.fixture("events-valid.json")
        matrix = self.fixture("matrix-valid.json")
        source_sha = events[1]["source_sha"]
        self.assertEqual(self.qa.evaluate_events(events, matrix)["result"], "QA_PASS")
        events[2]["defects"] = ["stale-package"]
        failed = self.qa.run_hermetic_qa(events, matrix)
        self.assertEqual(failed["result"], "QA_FAIL")
        self.assertEqual(failed["candidate_sha"], source_sha)
        events[2]["defects"] = []
        restored = self.qa.run_hermetic_qa(events, matrix)
        self.assertEqual(restored["result"], "QA_PASS")
        self.assertEqual(restored["candidate_sha"], source_sha)

    def test_missing_devtools_or_computer_use_is_prerequisite_missing(self):
        state = self.qa.prerequisite_missing(**self.fixture("devtools-missing.json"))
        self.assertEqual(state["result"], "none")
        self.assertEqual(state["control_outcome"], "qa-prerequisite-missing")
        state = self.qa.prerequisite_missing(
            devtools_available=True, computer_use_available=False, qa_run_id="devtools-run-2"
        )
        self.assertEqual(state["missing_prerequisites"], ["computer-use"])

    def test_external_mutation_unknown_private_and_bad_order_are_rejected(self):
        events = self.fixture("events-valid.json")
        events[0]["platform_mutation"] = True
        with self.assertRaises(self.qa.DevToolsQAError) as raised:
            self.qa.validate_events(events)
        self.assertEqual(raised.exception.code, "DEVTOOLS_EXTERNAL_SIDE_EFFECT")

        events = self.fixture("events-valid.json")
        events[0]["private_url"] = "cloud://private"
        with self.assertRaises(self.qa.DevToolsQAError) as raised:
            self.qa.validate_events(events)
        self.assertEqual(raised.exception.code, "DEVTOOLS_EVENT_UNKNOWN_FIELD")

        events = self.fixture("events-valid.json")
        events[0], events[1] = events[1], events[0]
        with self.assertRaises(self.qa.DevToolsQAError) as raised:
            self.qa.validate_events(events)
        self.assertEqual(raised.exception.code, "DEVTOOLS_EVENT_ORDER")

    def test_matrix_requires_all_nine_states_and_rejects_private_fields(self):
        matrix = self.fixture("matrix-valid.json")[:-1]
        with self.assertRaises(self.qa.DevToolsQAError) as raised:
            self.qa.validate_matrix(matrix)
        self.assertEqual(raised.exception.code, "DEVTOOLS_MATRIX_COVERAGE")

        matrix = self.fixture("matrix-valid.json")
        matrix[0]["next_module"] = "release"
        with self.assertRaises(self.qa.DevToolsQAError) as raised:
            self.qa.validate_matrix(matrix)
        self.assertEqual(raised.exception.code, "DEVTOOLS_MATRIX_UNKNOWN_FIELD")

    def test_screenshot_and_matrix_identity_mismatches_fail(self):
        matrix = self.fixture("matrix-valid.json")
        events = self.fixture("events-valid.json")
        events[2]["screenshot_hash"] = "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
        result = self.qa.evaluate_events(events, matrix)
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("screenshot hash differs from matrix evidence", result["findings"])

        matrix = self.fixture("matrix-valid.json")
        matrix[0]["final_compile_provenance"] = "compile-v2"
        result = self.qa.evaluate_events(self.fixture("events-valid.json"), matrix)
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("matrix final-compile provenance differs from final compile", result["findings"])

    def test_docs_define_qa_gates_raw_events_matrix_and_boundaries(self):
        text = (ROOT / "quality" / "devtools-qa.md").read_text(encoding="utf-8")
        for phrase in (
            "QA-1",
            "QA-2",
            "project-open",
            "final-compile",
            "duplicate title",
            "one-character",
            "English",
            "Chinese",
            "QA_FAIL",
            "verified-device",
            "zero external network",
            "Computer Use",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
