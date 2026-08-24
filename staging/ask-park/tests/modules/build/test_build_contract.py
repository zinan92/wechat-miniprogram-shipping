import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "modules" / "build"
MODULE_DOC = ROOT / "modules" / "02-build" / "MODULE.md"
RECEIPT_DOC = ROOT / "modules" / "02-build" / "software-receipt.md"


class BuildContractTests(unittest.TestCase):
    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assert_common_contract(self, document):
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["module"], "build")
        self.assertTrue(document["issue_contract_id"])
        self.assertRegex(document["source_sha"], r"^(?:sha256:)?[0-9a-f]{7,64}$")
        self.assertTrue(document["service_boundary"]["page_facing_api"])
        self.assertEqual(set(document["service_boundary"]["mock_api"]), set(document["service_boundary"]["cloud_api"]))
        self.assertEqual(document["service_boundary"]["mock_result_shapes"], document["service_boundary"]["cloud_result_shapes"])
        self.assertEqual(document["service_boundary"]["mock_error_codes"], document["service_boundary"]["cloud_error_codes"])
        self.assertEqual(document["plan_boundary"]["cloudbase_claim"], False)
        self.assertTrue(document["authorization"]["unknown_role"] == "deny")
        self.assertTrue(document["authorization"]["missing_role"] == "deny")
        self.assertTrue(document["authorization"]["suspended_state"] == "deny")
        self.assertTrue(document["plan_boundary"]["code_work_authorized"] == (document["plan_boundary"]["issue_contract_status"] == "accepted" and document["plan_boundary"]["plan_receipt_status"] == "valid"))
        self.assertTrue(document["ordered_content"]["blocks"])
        positions = [block["position"] for block in document["ordered_content"]["blocks"]]
        self.assertEqual(positions, list(range(len(positions))))
        self.assertTrue(document["content_contract"]["capabilities"])
        self.assertTrue(document["content_contract"]["version"].startswith("content/v"))
        self.assertNotIn("extension", document["content_contract"]["version_source"].lower())
        self.assertTrue(document["first_party_assets"])
        self.assertTrue(all(asset["source"].startswith("redacted:") for asset in document["first_party_assets"]))
        gates = document["software_gates"]
        for name in ("tests", "audit", "secret_scan", "diff_check"):
            self.assertIn(name, gates)
            self.assertIn(gates[name], {"pass", "fail", "blocked"})
        self.assertTrue(document["unverified_assumptions"])
        self.assertTrue(document["evidence_limitations"])
        self.assertEqual(document["evidence_claims"], ["verified-software"])
        self.assertNotIn("device", document["evidence_claims"])
        self.assertNotIn("simulator", document["evidence_claims"])

    def test_mock_first_slice_requires_parity_and_software_gates(self):
        document = self.fixture("mock-first-ready.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "verified-software")
        self.assertEqual(document["software_gates"]["tests"], "pass")
        self.assertEqual(document["software_gates"]["secret_scan"], "pass")
        self.assertTrue(document["state_machine"]["fail_closed"])
        self.assertTrue(document["receipt"]["receipt_id"])
        self.assertEqual(document["receipt"]["module"], "build")

    def test_auth_failure_stops_build_without_collecting_credentials(self):
        document = self.fixture("credential-blocked.json")
        self.assert_common_contract(document)
        self.assertEqual(document["status"], "blocked-external")
        self.assertFalse(document["issue_ready"])
        self.assertEqual(document["authorization"]["unknown_role"], "deny")
        self.assertTrue(document["human_gate_required"])
        self.assertEqual(document["plan_boundary"]["plan_receipt_status"], "missing")
        self.assertFalse(document["plan_boundary"]["code_work_authorized"])
        self.assertNotIn("credential", json.dumps(document).lower())

    def test_content_capabilities_bind_order_and_version(self):
        document = self.fixture("ordered-content.json")
        self.assert_common_contract(document)
        blocks = document["ordered_content"]["blocks"]
        self.assertEqual([block["kind"] for block in blocks], ["text", "image", "text"])
        self.assertEqual(document["content_contract"]["version_source"], "parsed-capabilities")
        self.assertEqual(document["content_contract"]["extension_hint"], "ignored")

    def test_module_docs_define_contract_and_receipt_limits(self):
        module_text = MODULE_DOC.read_text(encoding="utf-8")
        receipt_text = RECEIPT_DOC.read_text(encoding="utf-8")
        for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"):
            self.assertIn(phrase, module_text)
        for phrase in ("source SHA", "issue contract", "verified-software", "cannot prove", "Simulator", "result shapes", "Plan receipt"):
            self.assertIn(phrase, receipt_text)

    def test_build_fixtures_do_not_cross_private_or_live_mutation_boundary(self):
        forbidden_keys = {"secret", "token", "password", "appid", "appsecret", "environment_id", "openid", "private_key", "access_key", "api_key", "cookie"}

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = key.lower().replace("-", "_")
                    if normalized != "secret_scan":
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
