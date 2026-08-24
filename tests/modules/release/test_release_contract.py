import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "modules" / "release"
MODULE_DOC = ROOT / "modules" / "06-release" / "MODULE.md"
RECEIPT_DOC = ROOT / "modules" / "06-release" / "release-receipt.md"


class ReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        validator_path = ROOT / "scripts" / "validate-state.py"
        spec = importlib.util.spec_from_file_location("release_contract_validator", validator_path)
        cls.validator = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.validator)

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assert_common_contract(self, document):
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["module"], "release")
        self.assertTrue(document["issue_contract_id"])
        self.assertTrue(document["predecessor_receipt_ids"])
        self.assertIn(document["status"], {"released", "failed", "blocked-external"})
        self.assertIn(document["project_state"], {"active", "released"})
        self.assertTrue(document["version_binding"]["experience_version_alias"])
        bindings = document["predecessor_bindings"]
        for binding in bindings.values():
            self.assertIn(binding["receipt_id"], document["predecessor_receipt_ids"])
        self.assertEqual(set(document["receipt"]["predecessor_receipt_ids"]), set(document["predecessor_receipt_ids"]))
        if document["version_binding"]["matches_predecessors"]:
            self.assertEqual(document["version_binding"]["source_sha"], bindings["experience"]["source_sha"])
            self.assertEqual(bindings["experience"]["source_sha"], bindings["device"]["source_sha"])
            self.assertEqual(document["version_binding"]["experience_version_alias"], bindings["experience"]["version_alias"])
            self.assertEqual(document["version_binding"]["device_version_alias"], bindings["device"]["version_alias"])
        if document["version_binding"]["matches_predecessors"]:
            self.assertEqual(document["version_binding"]["experience_version_alias"], document["version_binding"]["device_version_alias"])
        payment = document["payment"]
        self.assertIn(payment["applicability"], {"required", "not-applicable"})
        if payment["applicability"] == "required":
            self.assertEqual(payment["provider_truth"], "verified")
            self.assertTrue(payment["server_verification_ref"].startswith("redacted:"))
        else:
            self.assertTrue(payment["not_applicable_reason"])
        for gate in ("review", "release_readback", "smoke"):
            self.assertIn(document[gate]["result"], {"pass", "fail", "blocked", "not-applicable"})
        self.assertTrue(document["human_authorizations"])
        for authorization in document["human_authorizations"]:
            self.assertIn(authorization["state"], {"authorized", "executed", "read-back", "awaiting-human", "denied", "expired"})
            self.assertTrue(authorization["action_scope"])
            self.assertTrue(authorization["evidence_ref"].startswith("redacted:"))
            gate_result = self.validator.validate_human_gate(authorization)
            self.assertTrue(gate_result.valid, gate_result.errors)
        self.assertTrue(document["unproven_claims"])
        receipt_result = self.validator.validate_receipt(document["receipt"])
        self.assertTrue(receipt_result.valid, receipt_result.errors)

    def test_release_ready_requires_provider_truth_human_gates_version_and_smoke(self):
        document = self.fixture("release-ready.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "released")
        self.assertEqual(document["project_state"], "released")
        self.assertEqual(document["payment"]["provider_truth"], "verified")
        self.assertEqual(document["review"]["result"], "pass")
        self.assertEqual(document["release_readback"]["result"], "pass")
        self.assertEqual(document["smoke"]["result"], "pass")
        self.assertEqual(document["receipt"]["status"], "valid")

    def test_payment_not_applicable_does_not_skip_review_or_release(self):
        document = self.fixture("payment-not-applicable.json")
        self.assert_common_contract(document)
        self.assertEqual(document["payment"]["applicability"], "not-applicable")
        self.assertEqual(document["review"]["result"], "pass")
        self.assertEqual(document["release_readback"]["result"], "pass")
        self.assertEqual(document["project_state"], "released")

    def test_human_gate_blocks_without_terminal_release(self):
        document = self.fixture("release-blocked-human.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "blocked-external")
        self.assertEqual(document["project_state"], "active")
        self.assertTrue(any(item["state"] == "awaiting-human" for item in document["human_authorizations"]))
        self.assertNotEqual(document["release_readback"]["result"], "pass")

    def test_version_mismatch_is_not_smoothed_by_review_or_payment(self):
        document = self.fixture("release-version-mismatch.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["project_state"], "active")
        self.assertFalse(document["version_binding"]["matches_predecessors"])
        self.assertEqual(document["review"]["result"], "not-applicable")

    def test_module_docs_define_distinct_final_gates_and_boundary(self):
        module_text = MODULE_DOC.read_text(encoding="utf-8")
        receipt_text = RECEIPT_DOC.read_text(encoding="utf-8")
        for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"):
            self.assertIn(phrase, module_text)
        for phrase in ("payment", "provider/server truth", "review", "release read-back", "smoke", "human authorization"):
            self.assertIn(phrase, receipt_text)

    def test_release_fixtures_do_not_cross_private_or_terminal_boundary(self):
        forbidden_keys = {"secret", "token", "password", "appid", "appsecret", "environment_id", "openid", "private_key", "access_key", "api_key", "cookie"}

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = key.lower().replace("-", "_")
                    if normalized not in {"appid_ref", "environment_ref"}:
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
