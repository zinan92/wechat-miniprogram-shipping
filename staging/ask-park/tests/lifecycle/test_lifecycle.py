import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE = ROOT / "scripts" / "state-lifecycle.py"
FIXTURES = ROOT / "fixtures" / "lifecycle"


def load_lifecycle():
    spec = importlib.util.spec_from_file_location("ask_park_state_lifecycle", LIFECYCLE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LifecycleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = load_lifecycle()

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def assertCode(self, code, operation, *args, **kwargs):
        with self.assertRaises(self.lifecycle.LifecycleError) as raised:
            operation(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)


class ModuleTransitionTests(LifecycleTestCase):
    def test_module_and_evidence_promote_only_through_legal_states(self):
        state = self.fixture("experience-current.json")
        state = self.lifecycle.transition_evidence(state, "experience", "valid")
        state = self.lifecycle.transition_activity(state, "experience", "completed")

        self.assertEqual(state["modules"]["experience"]["activity_state"], "completed")
        self.assertEqual(state["modules"]["experience"]["evidence_state"], "valid")
        self.assertEqual(state["current_module"], "device")
        self.assertEqual(state["modules"]["device"]["activity_state"], "current")
        self.assertCode(
            "ILLEGAL_ACTIVITY_TRANSITION",
            self.lifecycle.transition_activity,
            state,
            "experience",
            "waiting",
        )

    def test_failed_and_blocked_keep_the_same_current_module(self):
        state = self.fixture("experience-current.json")
        failed = self.lifecycle.transition_activity(state, "experience", "failed")
        self.assertEqual(failed["current_module"], "experience")
        blocked = self.lifecycle.transition_activity(state, "experience", "blocked-external")
        self.assertEqual(blocked["current_module"], "experience")
        self.assertCode(
            "CURRENT_MODULE_REQUIRED",
            self.lifecycle.transition_activity,
            state,
            "device",
            "current",
        )

    def test_evidence_cannot_be_removed_from_a_completed_module(self):
        state = self.fixture("experience-current.json")
        state["modules"]["experience"]["activity_state"] = "completed"
        state["modules"]["experience"]["evidence_state"] = "valid"
        state["current_module"] = "device"
        state["modules"]["device"]["activity_state"] = "current"
        self.assertCode(
            "ILLEGAL_EVIDENCE_TRANSITION",
            self.lifecycle.transition_evidence,
            state,
            "experience",
            "absent",
        )

    def test_stale_evidence_rewinds_earliest_module_and_locks_dependents(self):
        state = self.fixture("experience-completed.json")
        original = copy.deepcopy(state)
        rewound = self.lifecycle.transition_evidence(state, "build", "stale")
        self.assertEqual(rewound["current_module"], "build")
        self.assertEqual(rewound["rewind"]["earliest_invalidated_module"], "build")
        self.assertEqual(rewound["modules"]["cloudbase"]["activity_state"], "locked")
        self.assertEqual(state, original)

    def test_diagnose_overlays_without_becoming_current_module(self):
        state = self.fixture("experience-current.json")
        state = self.lifecycle.activate_diagnose(state, "experience", "reader-regression")
        self.assertEqual(state["current_module"], "experience")
        self.assertEqual(state["diagnose"]["state"], "active")
        self.assertEqual(state["diagnose"]["outcome"], "none")
        state = self.lifecycle.set_diagnose_outcome(state, "unresolved", "bounded-hypothesis")
        self.assertEqual(state["diagnose"]["outcome"], "unresolved")
        state = self.lifecycle.set_diagnose_outcome(state, "recovered")
        self.assertEqual(state["diagnose"]["state"], "standby")
        self.assertEqual(state["diagnose"]["outcome"], "none")
        self.assertEqual(state["current_module"], "experience")

    def test_project_release_requires_release_receipt_and_read_back(self):
        state = self.fixture("released-ready.json")
        self.assertCode(
            "PROJECT_RELEASE_EVIDENCE_REQUIRED",
            self.lifecycle.transition_project,
            state,
            "released",
        )
        state["human_gate"] = self.fixture("human-read-back.json")
        state = self.lifecycle.transition_evidence(state, "release", "valid")
        state["modules"]["release"]["receipt_id"] = "release-r1"
        state = self.lifecycle.transition_activity(state, "release", "completed")
        self.assertEqual(state["project_state"], "released")
        self.assertEqual(state["current_module"], "release")

    def test_project_can_stop_at_a_verified_current_target(self):
        state = self.fixture("experience-current.json")
        state = self.lifecycle.transition_evidence(state, "experience", "valid")
        for module in ("device", "release"):
            state["modules"][module] = {
                "applicability": "not-applicable",
                "activity_state": "not-applicable",
                "evidence_state": "not-applicable",
                "receipt_id": None,
                "not_applicable_reason": "Target stops at experience acceptance.",
            }
        state = self.lifecycle.transition_project(state, "target-achieved")
        self.assertEqual(state["project_state"], "target-achieved")
        self.assertEqual(state["current_module"], "experience")

    def test_last_required_completion_sets_target_achieved(self):
        state = self.fixture("experience-current.json")
        state = self.lifecycle.transition_evidence(state, "experience", "valid")
        for module in ("device", "release"):
            state["modules"][module] = {
                "applicability": "not-applicable",
                "activity_state": "not-applicable",
                "evidence_state": "not-applicable",
                "receipt_id": None,
                "not_applicable_reason": "Target stops at experience acceptance.",
            }
        state["modules"]["experience"]["receipt_id"] = "experience-r1"
        state["modules"]["experience"]["activity_state"] = "current"
        state = self.lifecycle.transition_activity(state, "experience", "completed")
        self.assertEqual(state["project_state"], "target-achieved")
        self.assertEqual(state["modules"]["experience"]["activity_state"], "completed")

    def test_target_achieved_synchronizes_legacy_terminal_alias(self):
        state = self.fixture("experience-current.json")
        state["project_terminal_state"] = "none"
        del state["project_state"]
        state = self.lifecycle.transition_evidence(state, "experience", "valid")
        for module in ("device", "release"):
            state["modules"][module] = {
                "applicability": "not-applicable",
                "activity_state": "not-applicable",
                "evidence_state": "not-applicable",
                "receipt_id": None,
                "not_applicable_reason": "Target stops at experience acceptance.",
            }
        state = self.lifecycle.transition_project(state, "target-achieved")
        self.assertEqual(state["project_state"], "target-achieved")
        self.assertNotIn("project_terminal_state", state)


class ReceiptLifecycleTests(LifecycleTestCase):
    def test_issue_receipt_requires_valid_predecessors(self):
        receipt = self.fixture("candidate-build-receipt.json")
        predecessors = {"plan-r1": self.fixture("valid-plan-receipt.json")}
        issued = self.lifecycle.issue_receipt(receipt, predecessors=predecessors)
        self.assertEqual(issued["status"], "valid")
        self.assertEqual(issued["receipt_id"], "build-r1")

        stale = copy.deepcopy(predecessors["plan-r1"])
        stale["status"] = "stale"
        stale["stale_reason"] = "fixture-stale"
        self.assertCode(
            "PREDECESSOR_RECEIPT_INVALID",
            self.lifecycle.issue_receipt,
            receipt,
            predecessors={"plan-r1": stale},
        )

    def test_receipt_reuse_requires_unchanged_causal_identity(self):
        receipt = self.fixture("valid-build-receipt.json")
        reused = self.lifecycle.reuse_receipt(
            receipt,
            changed_fields=[],
            predecessors={"plan-r1": self.fixture("valid-plan-receipt.json")},
        )
        self.assertEqual(reused["receipt_id"], receipt["receipt_id"])
        self.assertCode(
            "PREDECESSOR_RECEIPT_MISSING",
            self.lifecycle.reuse_receipt,
            receipt,
            changed_fields=[],
        )
        self.assertCode(
            "RECEIPT_REUSE_INVALIDATED",
            self.lifecycle.reuse_receipt,
            receipt,
            changed_fields=["source.commit_sha"],
            predecessors={"plan-r1": self.fixture("valid-plan-receipt.json")},
        )

        mismatched = copy.deepcopy(self.fixture("valid-cloudbase-receipt.json"))
        mismatched["receipt_id"] = "wrong-alias"
        self.assertCode(
            "PREDECESSOR_RECEIPT_INVALID",
            self.lifecycle.reuse_receipt,
            receipt,
            changed_fields=[],
            predecessors={"plan-r1": mismatched},
        )

        later = self.fixture("valid-experience-receipt.json")
        later["receipt_id"] = "plan-r1"
        self.assertCode(
            "PREDECESSOR_ORDER_INVALID",
            self.lifecycle.reuse_receipt,
            receipt,
            changed_fields=[],
            predecessors={"plan-r1": later},
        )

    def test_invalidation_is_transitive_and_selects_earliest_module(self):
        receipts = {
            receipt["receipt_id"]: receipt
            for receipt in (
                self.fixture("valid-plan-receipt.json"),
                self.fixture("valid-build-receipt.json"),
                self.fixture("valid-cloudbase-receipt.json"),
                self.fixture("valid-experience-receipt.json"),
            )
        }
        result = self.lifecycle.invalidate_receipts(receipts, changed_fields=["source.commit_sha"])
        self.assertEqual(result.earliest_invalidated_module, "build")
        self.assertEqual(
            result.invalidated_receipt_ids,
            ("build-r1", "cloudbase-r1", "experience-r1"),
        )
        self.assertEqual(result.receipts["build-r1"]["status"], "stale")
        self.assertEqual(result.receipts["build-r1"]["stale_reason"], "causal-identity-changed")
        self.assertEqual(result.receipts["experience-r1"]["status"], "stale")
        self.assertEqual(result.receipts["experience-r1"]["stale_reason"], "causal-identity-changed")

    def test_invalidation_requires_a_reason(self):
        with self.assertRaises(self.lifecycle.LifecycleError) as raised:
            self.lifecycle.invalidate_receipts({}, changed_fields=["source.commit_sha"], reason_code="")
        self.assertEqual(raised.exception.code, "INVALIDATION_REASON_REQUIRED")

    def test_rewind_locks_downstream_without_routing_authority(self):
        state = self.fixture("experience-completed.json")
        state = self.lifecycle.rewind_state(
            state,
            earliest_module="build",
            invalidated_receipt_ids=["build-r1", "cloudbase-r1", "experience-r1"],
            reason_code="source-changed",
        )
        self.assertEqual(state["current_module"], "build")
        self.assertEqual(state["modules"]["build"]["activity_state"], "current")
        self.assertEqual(state["modules"]["cloudbase"]["activity_state"], "locked")
        self.assertEqual(state["modules"]["experience"]["activity_state"], "locked")
        self.assertNotIn("next_module", state)


class HumanGateLifecycleTests(LifecycleTestCase):
    def test_human_gate_follows_prepare_await_authorize_execute_readback(self):
        gate = self.fixture("new-human-gate.json")
        gate = self.lifecycle.prepare_human_gate(
            gate,
            action_type="upload-experience",
            action_scope="experience-v1",
            authorizing_role="owner",
            requested_at="2026-08-24T10:00:00Z",
            evidence_ref="redacted:gate",
        )
        gate = self.lifecycle.transition_human_gate(gate, "awaiting-human")
        gate = self.lifecycle.authorize_human_gate(
            gate,
            authorized_at="2026-08-24T10:01:00Z",
            authority_basis="owner decision recorded outside credentials",
        )
        gate = self.lifecycle.transition_human_gate(gate, "executed")
        gate = self.lifecycle.transition_human_gate(gate, "read-back")
        self.assertEqual(gate["state"], "read-back")
        self.assertEqual(gate["authorized_at"], "2026-08-24T10:01:00Z")

    def test_access_is_not_authorization_and_denied_or_expired_are_terminal(self):
        gate = self.fixture("awaiting-human-gate.json")
        self.assertCode(
            "HUMAN_AUTHORIZATION_REQUIRED",
            self.lifecycle.authorize_human_gate,
            gate,
            authorized_at="2026-08-24T10:01:00Z",
            authority_basis="authenticated CLI access",
        )
        denied = self.lifecycle.transition_human_gate(gate, "denied")
        self.assertCode("ILLEGAL_HUMAN_GATE_TRANSITION", self.lifecycle.transition_human_gate, denied, "authorized")
        self.assertCode("ILLEGAL_HUMAN_GATE_TRANSITION", self.lifecycle.transition_human_gate, gate, "expired")


class ControlAndMigrationTests(LifecycleTestCase):
    def test_control_outcome_clear_requires_matching_evidence_or_contract(self):
        state = self.fixture("control-outcomes.json")
        self.assertCode(
            "CONTROL_CLEARING_EVIDENCE_REQUIRED",
            self.lifecycle.clear_control_outcome,
            state,
            evidence={"resolves": "unknown"},
        )
        resolved = self.lifecycle.clear_control_outcome(
            state,
            evidence={"resolves": "unknown", "evidence_ref": "redacted:readback"},
        )
        self.assertEqual(resolved["control_outcome"], "none")

        baseline = copy.deepcopy(state)
        baseline["control_outcome"] = "baseline-conflict"
        self.assertCode(
            "SUPERSEDING_CONTRACT_REQUIRED",
            self.lifecycle.clear_control_outcome,
            baseline,
            evidence={"resolves": "baseline-conflict", "evidence_ref": "redacted:evidence"},
        )
        baseline = self.lifecycle.clear_control_outcome(
            baseline,
            superseding_contract={"accepted": True, "contract_id": "issue-99"},
        )
        self.assertEqual(baseline["control_outcome"], "none")

    def test_incompatible_migration_is_rejected_and_compatible_is_explicit(self):
        receipt = self.fixture("valid-build-receipt.json")
        self.assertCode(
            "CONTRACT_MIGRATION_REQUIRED",
            self.lifecycle.migrate_receipt,
            receipt,
            target_contract_version="ask-park.receipt/v2",
        )

    def test_migration_transform_cannot_cross_the_persistence_boundary(self):
        receipt = self.fixture("valid-build-receipt.json")
        self.assertCode(
            "RECEIPT_INVALID",
            self.lifecycle.migrate_receipt,
            receipt,
            target_contract_version="ask-park.receipt/v2",
            migration={
                "compatible": True,
                "preserves_causal_identity": True,
                "verified": True,
                "transform": lambda item: {**item, "secret": "must-not-persist"},
            },
        )
        migrated = self.lifecycle.migrate_receipt(
            receipt,
            target_contract_version="ask-park.receipt/v2",
            migration={
                "compatible": True,
                "preserves_causal_identity": True,
                "verified": True,
            },
        )
        self.assertEqual(migrated["contract_version"], "ask-park.receipt/v2")
        self.assertEqual(migrated["status"], "valid")

        self.assertCode(
            "INCOMPATIBLE_CONTRACT",
            self.lifecycle.migrate_receipt,
            receipt,
            target_contract_version="ask-park.receipt/v2",
            migration=lambda item: item,
        )

        self.assertCode(
            "MIGRATION_CAUSAL_IDENTITY_CHANGED",
            self.lifecycle.migrate_receipt,
            receipt,
            target_contract_version="ask-park.receipt/v2",
            migration={
                "compatible": True,
                "preserves_causal_identity": True,
                "verified": True,
                "transform": lambda item: {**item, "source": {"repository_alias": "other", "commit_sha": item["source"]["commit_sha"]}},
            },
        )


if __name__ == "__main__":
    unittest.main()
