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

    def events(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_valid_raw_event_sequence_passes_without_device_claim(self):
        result = self.qa.evaluate_events(self.events("events-valid.json"), [{"route": "reader-home"}])
        self.assertEqual(result["result"], "QA_PASS")
        self.assertFalse(result["verified_device"])
        self.assertEqual(result["findings"], [])

    def test_render_package_and_readback_defects_fail(self):
        result = self.qa.evaluate_events(self.events("events-defect.json"), [{"route": "reader-home"}])
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("duplicate-title", result["findings"])
        self.assertIn("upload note and platform read-back candidate differ", result["findings"])

    def test_missing_final_compile_fails(self):
        result = self.qa.evaluate_events(self.events("events-missing-final-compile.json"), [{"route": "reader-home"}])
        self.assertEqual(result["result"], "QA_FAIL")
        self.assertIn("missing-final-compile", result["findings"])

    def test_missing_devtools_is_prerequisite_missing(self):
        state = self.qa.prerequisite_missing(**json.loads((FIXTURES / "devtools-missing.json").read_text(encoding="utf-8")))
        self.assertEqual(state["result"], "none")
        self.assertEqual(state["control_outcome"], "qa-prerequisite-missing")

    def test_external_mutation_event_is_rejected(self):
        events = self.events("events-valid.json")
        events[0]["platform_mutation"] = True
        with self.assertRaises(self.qa.DevToolsQAError) as raised:
            self.qa.validate_events(events)
        self.assertEqual(raised.exception.code, "DEVTOOLS_EXTERNAL_SIDE_EFFECT")

    def test_docs_define_raw_events_and_no_device_claim(self):
        text = (ROOT / "quality" / "devtools-qa.md").read_text(encoding="utf-8")
        for phrase in ("project-open", "final-compile", "duplicate title", "one-character", "QA_FAIL", "verified-device", "zero external network"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
