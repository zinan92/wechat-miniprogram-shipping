import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "modules" / "device"
MODULE_DOC = ROOT / "modules" / "05-device" / "MODULE.md"
RECEIPT_DOC = ROOT / "modules" / "05-device" / "device-matrix.md"
DEVICE_CLASSES = {"ios", "android"}
EVIDENCE_RUNGS = {"projection", "http-reachability", "pixels-layout", "expiry-fallback"}


class DeviceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        validator_path = ROOT / "scripts" / "validate-state.py"
        spec = importlib.util.spec_from_file_location("device_contract_validator", validator_path)
        cls.validator = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.validator)

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assert_common_contract(self, document):
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["module"], "device")
        self.assertTrue(document["experience_receipt_id"])
        self.assertTrue(document["experience_version_alias"])
        self.assertIn(document["status"], {"verified-device", "failed", "blocked-external", "not-applicable"})
        self.assertTrue(document["matrix"])
        for cell in document["matrix"]:
            self.assertIn(cell["device_class"], DEVICE_CLASSES)
            self.assertTrue(cell["device_profile"])
            self.assertIn(cell["role"], {"admin", "member", "guest"})
            self.assertTrue(cell["task"])
            self.assertTrue(cell["experience_version_alias"] == document["experience_version_alias"])
            self.assertIn(cell["result"], {"pass", "fail", "blocked", "not-applicable"})
        self.assertEqual(set(document["evidence_ladder"]), EVIDENCE_RUNGS)
        for rung, record in document["evidence_ladder"].items():
            self.assertIn(record["result"], {"pass", "fail", "blocked", "not-applicable"})
            self.assertTrue(record["proves"])
            self.assertTrue(record["cannot_prove"])
        self.assertTrue(document["weak_network"]["retry_policy"])
        self.assertTrue(document["weak_network"]["expiry_policy"])
        for event in document["client_logs"]:
            self.assertEqual(event["source"], "client")
            self.assertTrue(event["request_id"])
        self.assertTrue(document["unproven_claims"])
        receipt_result = self.validator.validate_receipt(document["receipt"])
        self.assertTrue(receipt_result.valid, receipt_result.errors)

    def test_device_matrix_binds_fresh_version_role_and_task_results(self):
        document = self.fixture("device-matrix-ready.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "verified-device")
        self.assertTrue(all(cell["result"] == "pass" for cell in document["matrix"]))
        self.assertTrue(document["human_gate"]["required"] is False)
        self.assertEqual(document["receipt"]["status"], "valid")

    def test_physical_device_gate_blocks_after_automation_passes(self):
        document = self.fixture("physical-gate-blocked.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "blocked-external")
        self.assertTrue(document["automation_passed"])
        self.assertTrue(document["human_gate"]["required"])
        self.assertTrue(document["human_gate"]["ref"].startswith("redacted:"))
        self.assertEqual(document["receipt"]["status"], "invalid")

    def test_cli_events_are_excluded_from_real_client_log_attribution(self):
        document = self.fixture("cli-log-excluded.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "verified-device")
        self.assertEqual(document["client_log_summary"]["excluded_sources"], ["cli"])
        self.assertTrue(all(event.startswith("redacted:") for event in document["attributed_client_events"]))

    def test_protected_content_failure_is_not_smoothed_by_http_success(self):
        document = self.fixture("protected-content-failure.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["evidence_ladder"]["http-reachability"]["result"], "pass")
        self.assertEqual(document["evidence_ladder"]["pixels-layout"]["result"], "fail")

    def test_module_docs_define_ladder_and_human_boundary(self):
        module_text = MODULE_DOC.read_text(encoding="utf-8")
        receipt_text = RECEIPT_DOC.read_text(encoding="utf-8")
        for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"):
            self.assertIn(phrase, module_text)
        for phrase in ("projection", "HTTP", "pixels", "expiry", "Simulator", "human gate"):
            self.assertIn(phrase, receipt_text)

    def test_device_fixtures_do_not_cross_private_or_automation_boundary(self):
        forbidden_keys = {"secret", "token", "password", "appid", "appsecret", "environment_id", "openid", "private_key", "access_key", "api_key", "cookie"}

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = key.lower().replace("-", "_")
                    self.assertFalse(any(part in normalized for part in forbidden_keys))
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
            elif isinstance(value, str):
                self.assertFalse(value.startswith(("http://", "https://", "file://", "/Users/", "/private/")))

        for fixture in FIXTURES.glob("*.json"):
            walk(json.loads(fixture.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
