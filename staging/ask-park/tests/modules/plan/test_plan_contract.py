import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "modules" / "plan"
MODULE_DOC = ROOT / "modules" / "01-plan" / "MODULE.md"
ACCEPTANCE_DOC = ROOT / "modules" / "01-plan" / "acceptance-contract.md"
MODULES = ("plan", "build", "cloudbase", "experience", "device", "release")
RISK_CATEGORIES = {"intent", "identity", "backend", "experience", "device", "release", "migration"}


class PlanContractTests(unittest.TestCase):
    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assert_common_contract(self, document):
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["module"], "plan")
        self.assertIn(document["mode"], {"new", "takeover", "scope-change"})
        self.assertIn(document["complexity"]["label"], {"S", "M", "L"})
        self.assertTrue(document["outcome"]["statement"].strip())
        self.assertTrue(document["outcome"]["first_useful_moment"].strip())
        criteria = document["acceptance_criteria"]
        self.assertGreaterEqual(len(criteria), 3)
        self.assertLessEqual(len(criteria), 7)
        self.assertTrue(all(isinstance(item, str) and item.strip() for item in criteria))
        self.assertEqual(set(document["applicability"]), set(MODULES))
        self.assertTrue(all(value in {"required", "not-applicable"} for value in document["applicability"].values()))
        reasons = document["applicability_reasons"]
        self.assertEqual(set(reasons), {module for module, value in document["applicability"].items() if value == "not-applicable"})
        self.assertTrue(all(isinstance(reason, str) and reason.strip() for reason in reasons.values()))
        for risk in document["risk_map"]:
            self.assertIn(risk["category"], RISK_CATEGORIES)
            self.assertIn(risk["status"], {"known", "unknown", "mitigated", "blocked"})
            self.assertTrue(risk["mitigation"])
        self.assertTrue(document["solution_search"])
        for result in document["solution_search"]:
            self.assertTrue(result["evidence_ref"].startswith("redacted:"))
        contract = document["issue_contract"]
        self.assertIsInstance(contract["version"], int)
        self.assertGreater(contract["version"], 0)
        self.assertTrue(contract["contract_id"])
        for story in document["ordered_work"]:
            self.assertGreaterEqual(len(story["acceptance_criteria"]), 3)
            self.assertLessEqual(len(story["acceptance_criteria"]), 7)
            self.assertTrue(story["issue_contract_ready"] in {True, False})
        self.assertTrue(document["ordered_work"] or document["control_outcome"] != "none")
        self.assertIn("outcome", document)
        self.assertIn("scope", document)
        self.assertIn("forbidden_changes", document)

    def test_new_idea_is_issue_ready_without_creating_an_issue(self):
        document = self.fixture("new-idea.json")
        self.assert_common_contract(document)
        self.assertEqual(document["mode"], "new")
        self.assertTrue(document["issue_ready"])
        self.assertEqual(document["control_outcome"], "none")
        self.assertTrue(document["issue_contract"]["immutable"])
        self.assertEqual(document["issue_actions"], ["prepare"])
        self.assertNotIn("created_issue_id", document)
        self.assertTrue(document["outcome"]["first_useful_moment"])
        self.assertFalse(any("created_issue_id" in key for key in document))

    def test_takeover_requires_source_evidence_and_preserves_unknowns(self):
        document = self.fixture("takeover.json")
        self.assert_common_contract(document)
        self.assertEqual(document["mode"], "takeover")
        self.assertTrue(document["source_evidence"])
        self.assertTrue(any(item["category"] == "identity" for item in document["risk_map"]))
        self.assertTrue(any(item["status"] == "unknown" for item in document["risk_map"]))
        self.assertTrue(document["issue_ready"])

    def test_material_scope_change_stops_at_baseline_conflict(self):
        document = self.fixture("scope-change.json")
        self.assert_common_contract(document)
        self.assertEqual(document["mode"], "scope-change")
        self.assertEqual(document["control_outcome"], "baseline-conflict")
        self.assertTrue(document["superseding_contract_required"])
        self.assertFalse(document["issue_ready"])
        self.assertEqual(document["issue_actions"], [])
        self.assertTrue(document["decision_needed"])

    def test_plan_fixtures_do_not_cross_the_persistence_boundary(self):
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

    def test_unresolved_intent_stops_before_issue_contract(self):
        document = self.fixture("unresolved-intent.json")
        self.assert_common_contract(document)
        self.assertEqual(document["control_outcome"], "unknown")
        self.assertFalse(document["issue_ready"])
        self.assertEqual(document["ordered_work"], [])
        self.assertTrue(document["decision_needed"])

    def test_plan_docs_state_the_six_part_contract_and_boundary(self):
        module_text = MODULE_DOC.read_text(encoding="utf-8")
        acceptance_text = ACCEPTANCE_DOC.read_text(encoding="utf-8")
        for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"):
            self.assertIn(phrase, module_text)
        for phrase in ("3–7", "applicability", "risk map", "solution search", "S/M/L", "issue contract"):
            self.assertIn(phrase, acceptance_text)


if __name__ == "__main__":
    unittest.main()
