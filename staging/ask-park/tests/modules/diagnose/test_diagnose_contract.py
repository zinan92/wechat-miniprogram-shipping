import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "modules" / "diagnose"
MODULE_DOC = ROOT / "modules" / "07-diagnose" / "MODULE.md"
INCIDENT_DOC = ROOT / "modules" / "07-diagnose" / "incident-contract.md"
MODULES = {"plan", "build", "cloudbase", "experience", "device", "release"}
MODULE_PATHS = {
    "plan": "modules/01-plan/MODULE.md",
    "build": "modules/02-build/MODULE.md",
    "cloudbase": "modules/03-cloudbase/MODULE.md",
    "experience": "modules/04-experience/MODULE.md",
    "device": "modules/05-device/MODULE.md",
    "release": "modules/06-release/MODULE.md",
}
FAILURE_CLASSES = {"source-drift", "artifact-drift", "deployment-drift", "runtime-drift", "identity", "permission", "network", "device-only"}
OUTCOMES = {"recovered", "unresolved", "blocked-external"}


class DiagnoseContractTests(unittest.TestCase):
    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assert_common_contract(self, document):
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["module"], "diagnose")
        self.assertIn(document["interrupted_module"], MODULES)
        self.assertTrue(document["incident_id"])
        self.assertTrue(document["symptom"]["statement"].strip())
        self.assertIn(document["failure_class"], FAILURE_CLASSES)
        self.assertTrue(document["recovery_goal"].strip())
        self.assertEqual(document["symptom"]["source_ref"][:9], "redacted:")
        self.assertTrue(document["observed_facts"])
        for fact in document["observed_facts"]:
            self.assertTrue(fact["evidence_ref"].startswith("redacted:"))
            self.assertTrue(fact["proves"].strip())
            self.assertTrue(fact["cannot_prove"].strip())
        self.assertTrue(document["hypotheses"])
        for hypothesis in document["hypotheses"]:
            self.assertTrue(hypothesis["id"])
            self.assertTrue(hypothesis["statement"].strip())
            self.assertTrue(hypothesis["falsifier"].strip())
            self.assertTrue(hypothesis["test"].strip())
            self.assertIn(hypothesis["status"], {"open", "supported", "rejected"})
        proposal = document["causal_invalidation_proposal"]
        self.assertIsInstance(proposal["confirmed"], bool)
        if proposal["confirmed"]:
            self.assertIn(proposal["earliest_module"], MODULES)
            self.assertTrue(proposal["invalidated_receipt_ids"])
            self.assertTrue(proposal["changed_fields"])
            self.assertTrue(proposal["reason_code"])
            self.assertRegex(proposal["reason_code"], r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
            self.assertTrue(all("/" not in field and "https:" not in field for field in proposal["changed_fields"]))
            self.assertTrue(all("/" not in receipt_id for receipt_id in proposal["invalidated_receipt_ids"]))
        else:
            self.assertIsNone(proposal["earliest_module"])
            self.assertEqual(proposal["invalidated_receipt_ids"], [])
            self.assertEqual(proposal["changed_fields"], [])
        self.assertIn(document["outcome"], OUTCOMES)
        if document["outcome"] == "recovered":
            self.assertEqual(document["diagnose_state"], "standby")
            self.assertEqual(document["post_recovery_current_module"], proposal["earliest_module"] or document["interrupted_module"])
        else:
            self.assertEqual(document["diagnose_state"], "active")
        self.assertTrue(document["unproven_claims"])
        self.assertTrue(document["bounded_next_action"])
        attempts = document["attempts"]
        numbers = [attempt["attempt"] for attempt in attempts]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        for attempt in attempts:
            self.assertIsInstance(attempt["attempt"], int)
            self.assertTrue(attempt["action"].strip())
            self.assertTrue(attempt["result"].strip())
        if document["human_gate_required"]:
            self.assertTrue(document["human_gate_ref"].startswith("redacted:"))
            summary = document["human_gate_summary"]
            for field in ("state", "action_type", "action_scope", "authorizing_role", "evidence_ref"):
                self.assertTrue(summary[field])
            self.assertTrue(summary["evidence_ref"].startswith("redacted:"))
        else:
            self.assertIsNone(document["human_gate_ref"])
            self.assertIsNone(document["human_gate_summary"])
        for path in document["load_contracts"]:
            self.assertTrue(path.startswith(("references/", "modules/")))
            self.assertNotIn("..", path)
            self.assertNotIn("://", path)
        self.assertEqual(document["load_contracts"][0:2], ["references/status-contract.md", "references/evidence-contract.md"])
        self.assertIn("modules/07-diagnose/MODULE.md", document["load_contracts"])
        self.assertIn(MODULE_PATHS[document["interrupted_module"]], document["load_contracts"])
        self.assertLessEqual(len(document["attempts"]), 3)

    def test_artifact_drift_recovery_proposes_earliest_rewind(self):
        document = self.fixture("artifact-drift-with-rewind.json")
        self.assert_common_contract(document)
        self.assertEqual(document["failure_class"], "artifact-drift")
        self.assertTrue(document["causal_invalidation_proposal"]["confirmed"])
        self.assertEqual(document["causal_invalidation_proposal"]["earliest_module"], "build")
        self.assertEqual(document["post_recovery_current_module"], "build")

    def test_device_only_failure_keeps_interrupted_module_without_rewind(self):
        document = self.fixture("device-only-no-rewind.json")
        self.assert_common_contract(document)
        self.assertEqual(document["failure_class"], "device-only")
        self.assertFalse(document["causal_invalidation_proposal"]["confirmed"])
        self.assertEqual(document["post_recovery_current_module"], "device")
        self.assertEqual(document["outcome"], "blocked-external")
        self.assertTrue(document["human_gate_required"])

    def test_unresolved_diagnosis_stays_active_and_is_bounded(self):
        document = self.fixture("unresolved-runtime.json")
        self.assert_common_contract(document)
        self.assertEqual(document["outcome"], "unresolved")
        self.assertEqual(document["diagnose_state"], "active")
        self.assertLessEqual(len(document["attempts"]), 3)
        self.assertNotIn("retry forever", document["bounded_next_action"].lower())

    def test_module_docs_define_contract_and_forbidden_boundary(self):
        module_text = MODULE_DOC.read_text(encoding="utf-8")
        incident_text = INCIDENT_DOC.read_text(encoding="utf-8")
        for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"):
            self.assertIn(phrase, module_text)
        for phrase in ("failure_class", "falsifier", "causal_invalidation_proposal", "bounded", "human_gate"):
            self.assertIn(phrase, incident_text)

    def test_incident_fixtures_do_not_cross_the_persistence_boundary(self):
        forbidden = {"secret", "token", "password", "appid", "appsecret", "environment_id", "openid", "private_key", "access_key", "api_key", "cookie"}

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = key.lower().replace("-", "_")
                    self.assertFalse(any(part in normalized for part in forbidden))
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
