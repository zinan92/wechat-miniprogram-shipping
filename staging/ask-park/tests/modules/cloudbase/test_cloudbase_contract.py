import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "modules" / "cloudbase"
MODULE_DOC = ROOT / "modules" / "03-cloudbase" / "MODULE.md"
RECEIPT_DOC = ROOT / "modules" / "03-cloudbase" / "cloud-receipt.md"


class CloudBaseContractTests(unittest.TestCase):
    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assert_common_contract(self, document):
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["module"], "cloudbase")
        self.assertTrue(document["issue_contract_id"])
        self.assertTrue(document["build_receipt_id"])
        self.assertIn(document["provider_role"], {"cloudbase", "serverless-backend"})
        self.assertTrue(document["target_alias"])
        self.assertTrue(document["artifact"]["digest"].startswith("sha256:"))
        self.assertTrue(document["production_package"]["clean"])
        self.assertFalse(document["production_package"]["nested_dev_dependencies"])
        for key in ("collections", "indexes", "rules", "runtime", "config"):
            self.assertIn(document["readiness_checks"][key], {"pass", "fail", "not-applicable"})
        for key in ("function_upload", "health_readback", "projection_readback", "hosting_readback", "client_evidence"):
            self.assertIn(key, document["evidence_layers"])
        self.assertEqual(document["protected_storage"]["access"], "closed")
        self.assertNotIn("public-fallback", document["protected_storage"].values())
        self.assertTrue(document["redacted_target_ref"].startswith("redacted:"))
        self.assertTrue(document["unproven_claims"])

    def test_verified_cloud_requires_readiness_health_projection_and_privacy(self):
        document = self.fixture("verified-cloud-ready.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "verified-cloud")
        self.assertTrue(all(value == "pass" for value in document["readiness_checks"].values()))
        self.assertEqual(document["evidence_layers"]["client_evidence"], "not-applicable")
        self.assertEqual(document["receipt"]["module"], "cloudbase")
        self.assertTrue(document["receipt"]["predecessor_receipt_ids"])

    def test_security_failure_has_no_public_storage_fallback(self):
        document = self.fixture("security-failure.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["protected_storage"]["access"], "closed")
        self.assertFalse(document["fallback_public_storage"])
        self.assertEqual(document["routing"], "diagnose")

    def test_not_applicable_backend_is_explicit_and_has_impact_reason(self):
        document = self.fixture("backend-not-applicable.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "not-applicable")
        self.assertTrue(document["not_applicable_reason"])
        self.assertTrue(document["impact_analysis"])
        self.assertTrue(all(value == "not-applicable" for value in document["readiness_checks"].values()))
        self.assertEqual(document["receipt"]["status"], "not-applicable")

    def test_hosting_drift_is_separate_from_function_health(self):
        document = self.fixture("hosting-drift.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["evidence_layers"]["function_upload"], "pass")
        self.assertEqual(document["evidence_layers"]["health_readback"], "pass")
        self.assertEqual(document["evidence_layers"]["hosting_readback"], "fail")
        self.assertEqual(document["routing"], "diagnose")

    def test_module_docs_define_contract_and_receipt_limits(self):
        module_text = MODULE_DOC.read_text(encoding="utf-8")
        receipt_text = RECEIPT_DOC.read_text(encoding="utf-8")
        for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"):
            self.assertIn(phrase, module_text)
        for phrase in ("target alias", "health", "projection", "Hosting", "not-applicable", "redacted"):
            self.assertIn(phrase, receipt_text)

    def test_cloudbase_fixtures_do_not_cross_private_or_deployment_boundary(self):
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
