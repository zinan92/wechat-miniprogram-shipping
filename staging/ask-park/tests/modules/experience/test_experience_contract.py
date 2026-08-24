import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "modules" / "experience"
MODULE_DOC = ROOT / "modules" / "04-experience" / "MODULE.md"
RECEIPT_DOC = ROOT / "modules" / "04-experience" / "upload-receipt.md"


class ExperienceContractTests(unittest.TestCase):
    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assert_common_contract(self, document):
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["module"], "experience")
        self.assertTrue(document["issue_contract_id"])
        self.assertTrue(document["build_receipt_id"])
        self.assertTrue(document["cloudbase_receipt_id"])
        self.assertRegex(document["source_sha"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(document["project_identity"]["project_alias"])
        self.assertTrue(document["project_identity"]["appid_ref"].startswith("redacted:"))
        self.assertTrue(document["project_identity"]["environment_ref"].startswith("redacted:"))
        self.assertTrue(document["compile"]["result"] in {"pass", "fail", "blocked", "not-applicable"})
        self.assertTrue(document["simulator"]["result"] in {"pass", "fail", "blocked", "not-applicable"})
        self.assertTrue(document["upload"]["result"] in {"pass", "fail", "blocked", "not-applicable"})
        self.assertTrue(document["target_readback"]["result"] in {"pass", "fail", "blocked", "not-applicable"})
        self.assertTrue(document["version"]["version_alias"])
        self.assertTrue(document["version"]["note_alias"])
        self.assertRegex(document["version"]["observed_at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertTrue(document["tool"]["name"])
        self.assertTrue(document["tool"]["version"])
        self.assertTrue(document["tool"]["base_library"])
        self.assertTrue(document["environment_contract_alias"])
        self.assertIn(document["review"]["result"], {"pass", "fail", "blocked", "not-applicable"})
        self.assertIn(document["release"]["result"], {"pass", "fail", "blocked", "not-applicable"})
        self.assertTrue(document["evidence_limitations"])
        self.assertTrue(document["receipt"]["receipt_id"])

    def test_experience_ready_binds_compile_upload_target_and_clean_source(self):
        document = self.fixture("experience-ready.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "verified-experience")
        self.assertTrue(document["clean_tree"])
        self.assertTrue(document["ignored_config"]["restored"])
        self.assertEqual(document["compile"]["result"], "pass")
        self.assertEqual(document["simulator"]["result"], "pass")
        self.assertEqual(document["upload"]["result"], "pass")
        self.assertEqual(document["target_readback"]["result"], "pass")
        self.assertEqual(document["receipt"]["status"], "valid")

    def test_uncommitted_source_stops_before_upload(self):
        document = self.fixture("stale-source-blocked.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "failed")
        self.assertFalse(document["clean_tree"])
        self.assertFalse(document["upload"]["attempted"])

    def test_backend_only_not_applicable_requires_client_impact_analysis(self):
        document = self.fixture("backend-only-not-applicable.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "not-applicable")
        self.assertTrue(document["backend_only"])
        self.assertTrue(document["client_contract_unchanged"])
        self.assertTrue(document["impact_analysis"])
        self.assertTrue(document["not_applicable_reason"])
        self.assertEqual(document["receipt"]["status"], "not-applicable")

    def test_upload_target_mismatch_is_not_release(self):
        document = self.fixture("upload-readback-mismatch.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["upload"]["result"], "pass")
        self.assertEqual(document["target_readback"]["result"], "fail")
        self.assertEqual(document["review"]["result"], "not-applicable")
        self.assertEqual(document["release"]["result"], "not-applicable")

    def test_module_docs_define_contract_and_receipt_limits(self):
        module_text = MODULE_DOC.read_text(encoding="utf-8")
        receipt_text = RECEIPT_DOC.read_text(encoding="utf-8")
        for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"):
            self.assertIn(phrase, module_text)
        for phrase in ("source SHA", "Compile", "Simulator", "Upload", "target read-back", "not-applicable"):
            self.assertIn(phrase, receipt_text)

    def test_experience_fixtures_do_not_cross_private_or_upload_boundary(self):
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
