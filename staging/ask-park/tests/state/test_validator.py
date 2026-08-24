import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = REPO_ROOT / "staging" / "ask-park" / "scripts" / "validate-state.py"
FIXTURES = REPO_ROOT / "staging" / "ask-park" / "fixtures" / "state"


def load_validator():
    spec = importlib.util.spec_from_file_location("ask_park_state_validator", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_valid_state_has_independent_axes(self):
        result = self.validator.validate_document(self.fixture("valid-state.json"))

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.kind, "state")
        state = self.fixture("valid-state.json")
        self.assertEqual(state["current_module"], "experience")
        self.assertEqual(state["modules"]["cloudbase"]["applicability"], "required")
        self.assertEqual(state["modules"]["cloudbase"]["activity_state"], "completed")
        self.assertEqual(state["modules"]["experience"]["evidence_state"], "absent")
        self.assertEqual(state["diagnose"]["state"], "standby")
        self.assertEqual(state["control_outcome"], "none")
        self.assertEqual(state["project_state"], "active")
        self.assertEqual(state["human_gate"]["state"], "not-needed")

    def test_stale_state_requires_causal_rewind_to_earliest_invalidated_module(self):
        result = self.validator.validate_document(self.fixture("stale-state.json"))

        self.assertFalse(result.valid)
        self.assertIn("STATE_REWIND_REQUIRED", {error.code for error in result.errors})

        repaired = self.fixture("causal-rewind-state.json")
        repaired_result = self.validator.validate_document(repaired)
        self.assertTrue(repaired_result.valid, repaired_result.errors)

    def test_not_applicable_is_explicit_and_has_reason(self):
        result = self.validator.validate_document(self.fixture("not-applicable-state.json"))

        self.assertTrue(result.valid, result.errors)
        cloudbase = self.fixture("not-applicable-state.json")["modules"]["cloudbase"]
        self.assertEqual(cloudbase["applicability"], "not-applicable")
        self.assertEqual(cloudbase["activity_state"], "not-applicable")
        self.assertTrue(cloudbase["not_applicable_reason"])

    def test_invalid_state_reports_stable_machine_codes(self):
        result = self.validator.validate_document(self.fixture("invalid-state.json"))

        self.assertFalse(result.valid)
        codes = {error.code for error in result.errors}
        self.assertIn("STATE_ENUM", codes)
        self.assertIn("STATE_CURRENT_MODULE", codes)
        self.assertIn("STATE_REQUIRED_FIELD", codes)

    def test_issue_terminology_project_terminal_state_is_compatible(self):
        state = self.fixture("valid-state.json")
        state["project_terminal_state"] = "none"
        del state["project_state"]

        result = self.validator.validate_document(state)

        self.assertTrue(result.valid, result.errors)

    def test_released_state_retains_completed_release_and_readback_receipt(self):
        state = self.fixture("valid-state.json")
        state["project_state"] = "released"
        state["current_module"] = "release"
        for module in ("plan", "build", "cloudbase", "experience", "device"):
            state["modules"][module]["activity_state"] = "completed"
            state["modules"][module]["evidence_state"] = "valid"
            state["modules"][module]["receipt_id"] = f"{module}-r1"
        state["modules"]["release"] = {
            "applicability": "required",
            "activity_state": "completed",
            "evidence_state": "valid",
            "receipt_id": "release-r1",
        }

        result = self.validator.validate_document(state)
        self.assertTrue(result.valid, result.errors)

        state["modules"]["release"]["receipt_id"] = None
        result = self.validator.validate_document(state)
        self.assertFalse(result.valid)
        self.assertIn("STATE_TERMINAL", {error.code for error in result.errors})


class ReceiptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_valid_receipt_binds_all_causal_identity_fields(self):
        result = self.validator.validate_document(self.fixture("valid-receipt.json"))

        self.assertTrue(result.valid, result.errors)
        receipt = self.fixture("valid-receipt.json")
        for field in (
            "schema_version",
            "contract_version",
            "source",
            "issue",
            "predecessor_receipt_ids",
            "artifact",
            "package",
            "target",
            "invalidation_rules",
        ):
            self.assertIn(field, receipt)

    def test_stale_receipt_is_validly_described_but_not_reusable(self):
        result = self.validator.validate_document(self.fixture("stale-receipt.json"))

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.document["status"], "stale")

    def test_invalid_receipt_rejects_next_module_and_missing_causal_binding(self):
        result = self.validator.validate_document(self.fixture("invalid-receipt.json"))

        self.assertFalse(result.valid)
        codes = {error.code for error in result.errors}
        self.assertIn("FORBIDDEN_NEXT_MODULE", codes)
        self.assertIn("RECEIPT_REQUIRED_FIELD", codes)

    def test_not_applicable_receipt_still_records_reason_and_redacted_target(self):
        result = self.validator.validate_document(self.fixture("not-applicable-receipt.json"))

        self.assertTrue(result.valid, result.errors)

    def test_causal_rewind_receipt_declares_invalidation(self):
        result = self.validator.validate_document(self.fixture("causal-rewind-receipt.json"))

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.document["status"], "invalid")
        self.assertTrue(result.document["invalidation_rules"]["causal_rewind"])

    def test_private_target_and_secret_never_pass_persistence_boundary(self):
        result = self.validator.validate_document(self.fixture("private-target-receipt.json"))

        self.assertFalse(result.valid)
        codes = {error.code for error in result.errors}
        self.assertIn("PRIVATE_TARGET", codes)
        self.assertIn("SENSITIVE_FIELD", codes)

    def test_unknown_and_camel_case_sensitive_fields_are_rejected(self):
        state = self.fixture("valid-state.json")
        state["apiKey"] = "fixture-value"
        state["environmentId"] = "fixture-value"
        result = self.validator.validate_document(state)

        self.assertFalse(result.valid)
        self.assertIn("UNKNOWN_FIELD", {error.code for error in result.errors})

        receipt = self.fixture("valid-receipt.json")
        receipt["target"]["privateKey"] = "fixture-value"
        result = self.validator.validate_document(receipt)
        self.assertFalse(result.valid)
        self.assertIn("UNKNOWN_FIELD", {error.code for error in result.errors})

    def test_redacted_ref_must_be_an_alias_not_a_hidden_url_or_path(self):
        receipt = self.fixture("valid-receipt.json")
        for value in ("redacted:https://private.example.invalid/env", "redacted:/Users/wendy/private"):
            receipt["target"]["redacted_ref"] = value
            result = self.validator.validate_document(receipt)
            self.assertFalse(result.valid)
            self.assertIn("RECEIPT_TARGET", {error.code for error in result.errors})

    def test_artifact_and_package_digests_require_full_sha256(self):
        receipt = self.fixture("valid-receipt.json")
        receipt["artifact"]["digest"] = "sha256:deadbee"
        receipt["package"]["digest"] = "sha256:deadbee"
        result = self.validator.validate_document(receipt)

        self.assertFalse(result.valid)
        self.assertIn("RECEIPT_DIGEST", {error.code for error in result.errors})

    def test_s01_does_not_accept_s10_qa_manifest_or_result_records(self):
        receipt = self.fixture("valid-receipt.json")
        receipt["candidate_manifest"] = {"digest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"}
        receipt["qa_result"] = {"result": "QA_PASS"}

        result = self.validator.validate_document(receipt)

        self.assertFalse(result.valid)
        codes = {error.code for error in result.errors}
        self.assertIn("FORBIDDEN_QA_SCHEMA", codes)


class HumanGateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_human_gate_record_is_machine_valid_and_redacted(self):
        result = self.validator.validate_document(self.fixture("valid-human-gate.json"))

        self.assertTrue(result.valid, result.errors)

    def test_human_gate_cannot_use_access_as_authorization(self):
        result = self.validator.validate_document(self.fixture("invalid-human-gate.json"))

        self.assertFalse(result.valid)
        self.assertIn("HUMAN_GATE_AUTHORITY", {error.code for error in result.errors})

    def test_embedded_active_gate_requires_action_type(self):
        state = self.fixture("valid-state.json")
        state["human_gate"] = {
            "state": "awaiting-human",
            "action_scope": "experience-upload",
            "authorizing_role": "owner",
            "requested_at": "2026-08-24T10:00:00Z",
            "authorized_at": None,
            "evidence_ref": "redacted:gate",
        }

        result = self.validator.validate_document(state)

        self.assertFalse(result.valid)
        self.assertIn("HUMAN_GATE_REQUIRED_FIELD", {error.code for error in result.errors})


class ValidatorCliTests(unittest.TestCase):
    def test_cli_emits_machine_readable_output_without_echoing_private_input(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--input", str(FIXTURES / "private-target-receipt.json"), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["kind"], "receipt")
        self.assertNotIn("synthetic-secret-marker-123", result.stdout)
        self.assertNotIn("https://private.example.invalid", result.stdout)
        self.assertNotIn(str(FIXTURES), result.stdout)

        validator = load_validator()
        state = json.loads((FIXTURES / "valid-state.json").read_text(encoding="utf-8"))
        state["https://private.example.invalid/env"] = "fixture-value"
        result = validator.validate_document(state)
        self.assertFalse(result.valid)
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump(state, handle)
            handle.flush()
            cli = subprocess.run(
                [sys.executable, str(VALIDATOR), "--input", handle.name, "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotIn("https://private.example.invalid/env", cli.stdout)


if __name__ == "__main__":
    unittest.main()
