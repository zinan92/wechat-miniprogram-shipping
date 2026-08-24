import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validate-qa-manifest.py"
FIXTURES = ROOT / "fixtures" / "qa-schema"


def load_validator():
    spec = importlib.util.spec_from_file_location("ask_park_qa_validator", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class QAManifestContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assertValid(self, document, kind):
        result = self.validator.validate_document(document, kind)
        self.assertTrue(result.valid, result.errors)
        return result

    def test_candidate_manifest_is_jcs_bound_before_target(self):
        candidate = self.fixture("candidate-valid.json")
        result = self.assertValid(candidate, "candidate")
        self.assertEqual(result.document["digest"], self.validator.canonical_digest(candidate))
        self.assertEqual(candidate["target_manifest_digest"], None)
        self.assertTrue(candidate["candidate"]["source_sha"].startswith("sha256:"))
        candidate_extra = copy.deepcopy(candidate)
        candidate_extra["candidate"]["unmodeled"] = "x"
        candidate_extra["digest"] = self.validator.canonical_digest(candidate_extra)
        invalid = self.validator.validate_document(candidate_extra, "candidate")
        self.assertFalse(invalid.valid)
        self.assertIn("QA_UNKNOWN_FIELD", {error.code for error in invalid.errors})

    def test_target_manifest_references_candidate_and_post_target_result_binds_both(self):
        candidate = self.fixture("candidate-valid.json")
        target = self.fixture("target-valid.json")
        qa1 = self.fixture("result-qa1-valid.json")
        qa2 = self.fixture("result-qa2-valid.json")
        self.assertValid(candidate, "candidate")
        self.assertValid(target, "target")
        self.assertValid(qa1, "result")
        self.assertValid(qa2, "result")
        self.assertEqual(target["candidate_manifest_digest"], candidate["digest"])
        self.assertIsNone(qa1["target_manifest_digest"])
        self.assertEqual(qa2["target_manifest_digest"], target["digest"])
        target_extra = copy.deepcopy(target)
        target_extra["target"]["unmodeled"] = "x"
        target_extra["digest"] = self.validator.canonical_digest(target_extra)
        invalid = self.validator.validate_document(target_extra, "target")
        self.assertFalse(invalid.valid)
        self.assertIn("QA_UNKNOWN_FIELD", {error.code for error in invalid.errors})
        qa1_with_target = copy.deepcopy(qa1)
        qa1_with_target["target_receipt_id"] = "experience-r1"
        qa1_with_target["digest"] = self.validator.canonical_digest(qa1_with_target)
        invalid = self.validator.validate_document(qa1_with_target, "result")
        self.assertFalse(invalid.valid)
        self.assertIn("QA_TARGET_RECEIPT", {error.code for error in invalid.errors})
        qa1_bad_predecessor = copy.deepcopy(qa1)
        qa1_bad_predecessor["predecessor_receipt_ids"] = [None]
        qa1_bad_predecessor["digest"] = self.validator.canonical_digest(qa1_bad_predecessor)
        invalid = self.validator.validate_document(qa1_bad_predecessor, "result")
        self.assertFalse(invalid.valid)
        self.assertIn("QA_PREDECESSORS", {error.code for error in invalid.errors})

    def test_evidence_matrix_requires_after_identity_and_final_compile(self):
        row = self.fixture("evidence-row-valid.json")
        self.assertValid(row, "evidence")
        malformed = copy.deepcopy(row)
        malformed["after_evidence"].pop("final_compile_receipt_id")
        result = self.validator.validate_document(malformed, "evidence")
        self.assertFalse(result.valid)
        self.assertIn("EVIDENCE_FINAL_COMPILE", {error.code for error in result.errors})
        malformed = copy.deepcopy(row)
        malformed["after_evidence"]["source_or_package_identity"] = "not an alias"
        malformed["after_evidence"]["unknown_field"] = "unexpected"
        result = self.validator.validate_document(malformed, "evidence")
        self.assertFalse(result.valid)
        codes = {error.code for error in result.errors}
        self.assertIn("QA_UNKNOWN_FIELD", codes)
        self.assertIn("QA_AFTER", codes)
        enum_bad = copy.deepcopy(row)
        enum_bad["surface"] = "unknown"
        enum_bad["role"] = "root"
        enum_bad["route"] = "not an alias"
        result = self.validator.validate_document(enum_bad, "evidence")
        self.assertFalse(result.valid)
        codes = {error.code for error in result.errors}
        self.assertIn("QA_SURFACE", codes)
        self.assertIn("QA_ROLE", codes)
        self.assertIn("QA_ALIAS", codes)

    def test_historical_before_exception_does_not_excuse_missing_after(self):
        row = self.fixture("evidence-row-valid.json")
        row["equivalence"] = "historical-exception"
        row["before_evidence"] = None
        self.assertValid(row, "evidence")
        row["after_evidence"] = None
        result = self.validator.validate_document(row, "evidence")
        self.assertFalse(result.valid)
        self.assertIn("EVIDENCE_AFTER_REQUIRED", {error.code for error in result.errors})

    def test_unavailable_evaluator_is_prerequisite_missing_not_blocked(self):
        state = self.fixture("qa-state-unavailable.json")
        self.assertValid(state, "qa-state")
        self.assertEqual(state["qa"]["control_outcome"], "qa-prerequisite-missing")
        self.assertNotEqual(state["qa"]["result"], "QA_BLOCKED")

    def test_identity_change_invalidates_result_without_editing_candidate(self):
        result = self.fixture("result-qa1-valid.json")
        candidate_sha = result["candidate_manifest_digest"]
        invalidated = self.validator.invalidate_result(result, candidate_manifest_digest="sha256:" + "f" * 64)
        self.assertEqual(invalidated["result"], "none")
        self.assertEqual(invalidated["candidate_manifest_digest"], None)
        self.assertEqual(candidate_sha, self.fixture("candidate-valid.json")["digest"])

    def test_ephemeral_evidence_cannot_persist_refs(self):
        result = self.fixture("result-qa1-valid.json")
        result["evidence_mode"] = "ephemeral-only"
        result["evidence_refs"] = ["redacted:should-not-persist"]
        validation = self.validator.validate_document(result, "result")
        self.assertFalse(validation.valid)
        self.assertIn("QA_EPHEMERAL_REFERENCE", {error.code for error in validation.errors})
        row = self.fixture("evidence-row-valid.json")
        row["evidence_mode"] = "ephemeral-only"
        row["after_evidence"]["ref"] = "redacted:embedded-persistent-ref"
        validation = self.validator.validate_document(row, "evidence")
        self.assertFalse(validation.valid)
        self.assertIn("QA_EPHEMERAL_REFERENCE", {error.code for error in validation.errors})

    def test_approved_store_requires_governance_and_state_schema_is_complete(self):
        candidate = self.fixture("candidate-valid.json")
        candidate["evidence_mode"] = "approved-store-reference"
        validation = self.validator.validate_document(candidate, "candidate")
        self.assertFalse(validation.valid)
        self.assertIn("QA_STORE_GOVERNANCE", {error.code for error in validation.errors})
        state = self.fixture("qa-state-unavailable.json")
        del state["qa"]["gate"]
        validation = self.validator.validate_document(state, "qa-state")
        self.assertFalse(validation.valid)
        self.assertIn("QA_REQUIRED_FIELD", {error.code for error in validation.errors})
        state = self.fixture("qa-state-unavailable.json")
        state["qa"]["gate"] = "garbage"
        state["qa"]["origin_module"] = "unknown"
        state["qa"]["result"] = "QA_PASS"
        validation = self.validator.validate_document(state, "qa-state")
        self.assertFalse(validation.valid)
        codes = {error.code for error in validation.errors}
        self.assertIn("QA_GATE", codes)
        self.assertIn("QA_ORIGIN_MODULE", codes)
        self.assertIn("QA_PREREQUISITE", codes)

    def test_privacy_and_malformed_negative_fixtures_fail(self):
        for name in ("candidate-private-invalid.json", "candidate-duplicate-key.json", "target-stale-invalid.json"):
            document = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
            result = self.validator.validate_document(document, "candidate" if "candidate" in name else "target")
            self.assertFalse(result.valid, name)
        self.assertIn("QA_PRIVATE_VALUE", {error.code for error in self.validator.validate_document(self.fixture("candidate-private-invalid.json"), "candidate").errors})

    def test_negative_control_fail_and_restore_keep_candidate_digest(self):
        candidate = self.fixture("candidate-valid.json")
        malformed = self.fixture("candidate-malformed.json")
        restored = copy.deepcopy(candidate)
        self.assertEqual(candidate["digest"], restored["digest"])
        self.assertNotEqual(candidate["digest"], malformed["digest"])
        self.assertFalse(self.validator.validate_document(malformed, "candidate").valid)
        self.assertValid(restored, "candidate")
        failed = self.fixture("result-qa1-valid.json")
        failed["result"] = "QA_FAIL"
        failed["findings"] = ["known fixture defect"]
        failed["digest"] = self.validator.canonical_digest(failed)
        self.assertValid(failed, "result")
        self.assertEqual(failed["candidate_manifest_digest"], candidate["digest"])

    def test_docs_define_qa_state_manifest_and_matrix_contracts(self):
        for name, phrases in {
            "qa-state.md": ("prerequisite missing", "QA_PASS", "QA_FAIL", "QA_BLOCKED"),
            "qa-manifests.md": ("JCS", "candidate", "target", "ephemeral-only"),
            "qa-results.md": ("identity change", "three", "QA_FAIL", "BLOCKED"),
            "evidence-matrix.md": ("route", "viewport", "role", "final-compile", "after evidence"),
        }.items():
            text = (ROOT / "quality" / name).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
