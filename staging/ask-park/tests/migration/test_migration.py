import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "migration.py"
FIXTURE = ROOT / "fixtures" / "migration" / "fixture-input.json"
SOURCE = ROOT


def load_migration():
    spec = importlib.util.spec_from_file_location("ask_park_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.migration = load_migration()

    def test_inventory_enumerates_roots_symlinks_and_digests_without_paths(self):
        with tempfile.TemporaryDirectory(prefix="migration-roots-") as directory:
            root = Path(directory) / "skills"
            root.mkdir()
            (root / "safe.txt").write_text("safe", encoding="utf-8")
            link = Path(directory) / "skills-link"
            link.symlink_to(root, target_is_directory=True)
            inventory = self.migration.inventory_roots([
                {"root_alias": "root-real", "path": str(root), "enabled": True},
                {"root_alias": "root-link", "path": str(link), "enabled": False},
            ])
        self.assertEqual(inventory["kind"], "skill-inventory")
        self.assertEqual(len(inventory["roots"]), 2)
        self.assertTrue(any(root["symlink"] for root in inventory["roots"]))
        self.assertTrue(all(root["file_manifest_digest"].startswith("sha256:") for root in inventory["roots"]))
        self.assertNotIn(str(directory), json.dumps(inventory))

    def test_inventory_redacts_sensitive_files_and_values(self):
        with tempfile.TemporaryDirectory(prefix="migration-private-") as directory:
            root = Path(directory)
            (root / "safe.txt").write_text("safe", encoding="utf-8")
            (root / ".env.secret").write_text("token=private", encoding="utf-8")
            inventory = self.migration.inventory_roots([{"root_alias": "root", "path": str(root), "enabled": True}])
        serialized = json.dumps(inventory)
        self.assertNotIn(".env.secret", serialized)
        self.assertNotIn("private", serialized)

    def test_stage_manifest_and_pre_migration_receipt_leave_source_unchanged(self):
        before = self.migration.package_manifest(SOURCE)
        with tempfile.TemporaryDirectory(prefix="migration-stage-") as directory:
            staged = self.migration.stage_canonical_install(SOURCE, Path(directory), scanned_roots=[Path(directory) / "scanned-root"])
            inventory = self.migration.inventory_roots([{"root_alias": "source", "path": str(SOURCE), "enabled": True}])
            receipt = self.migration.pre_migration_receipt(inventory, staged, repository_identity="zinan92/wechat-miniprogram-shipping", history_ref="main-history")
            self.assertTrue((Path(directory) / "ask-park" / "SKILL.md").is_file())
        after = self.migration.package_manifest(SOURCE)
        self.assertEqual(before["package_digest"], after["package_digest"])
        self.assertFalse(receipt["canonical_enabled"])
        self.assertTrue(receipt["rollback"]["recoverable_backup"])
        self.assertTrue(receipt["receipt_digest"].startswith("sha256:"))
        self.assertNotIn(str(ROOT), json.dumps(receipt))

    def test_staging_rejects_destination_inside_scanned_root(self):
        with tempfile.TemporaryDirectory(prefix="migration-scope-") as directory:
            scanned = Path(directory) / "scanned"
            scanned.mkdir()
            with self.assertRaises(self.migration.MigrationError) as raised:
                self.migration.stage_canonical_install(SOURCE, scanned / "staged", scanned_roots=[scanned])
            self.assertEqual(raised.exception.code, "MIGRATION_SCANNED_ROOT_SCOPE")

    def test_pre_migration_receipt_rejects_noncanonical_identity_and_manifest(self):
        with tempfile.TemporaryDirectory(prefix="migration-receipt-") as directory:
            staged = self.migration.stage_canonical_install(SOURCE, Path(directory), scanned_roots=[])
            inventory = self.migration.inventory_roots([{"root_alias": "source", "path": str(SOURCE), "enabled": True}])
            with self.assertRaises(self.migration.MigrationError) as raised:
                self.migration.pre_migration_receipt(inventory, staged, repository_identity="evil-repo", history_ref="fake-history")
            self.assertEqual(raised.exception.code, "MIGRATION_REPOSITORY_ID")
            bad = dict(staged)
            bad["manifest"] = dict(staged["manifest"])
            bad["manifest"]["manifest_digest"] = "not-a-digest"
            with self.assertRaises(self.migration.MigrationError) as raised:
                self.migration.pre_migration_receipt(inventory, bad, repository_identity="zinan92/wechat-miniprogram-shipping", history_ref="main-history")
            self.assertEqual(raised.exception.code, "MIGRATION_MANIFEST_INVALID")

    def test_rollbacks_cover_all_checkpoints_and_preserve_legacy_backup(self):
        for checkpoint in self.migration.CHECKPOINTS:
            with tempfile.TemporaryDirectory(prefix="migration-rollback-") as directory:
                result = self.migration.rollback_checkpoint(Path(directory), checkpoint)
            self.assertEqual(result["checkpoint"], checkpoint)
            self.assertEqual(result["failure_kind"], checkpoint)
            self.assertTrue(result["canonical_removed"])
            self.assertTrue(result["partial_removed"])
            self.assertTrue(result["legacy_preserved"])

    def test_staging_rejects_source_symlink_escape(self):
        with tempfile.TemporaryDirectory(prefix="migration-symlink-") as directory:
            source = Path(directory) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("---\nname: ask-park\ndescription: test\n---\n", encoding="utf-8")
            (source / "agents").mkdir()
            (source / "agents" / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")
            (source / "linked").symlink_to(Path(directory), target_is_directory=True)
            with self.assertRaises(self.migration.MigrationError) as raised:
                self.migration.stage_canonical_install(source, Path(directory) / "out")
            self.assertEqual(raised.exception.code, "MIGRATION_SOURCE_SYMLINK")

    def test_root_identity_and_fixture_are_not_active_cutover(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["canonical_identity"], "ask-park")
        self.assertEqual(fixture["evidence_mode"], "sanitized-persisted")
        self.assertTrue((REPO_ROOT / "REGISTRY.md").is_file())
        self.assertNotIn("wechat-xingqiu", json.dumps(fixture))

    def test_docs_define_staging_identity_inventory_and_checkpoints(self):
        text = (ROOT / "quality" / "migration.md").read_text(encoding="utf-8")
        for phrase in ("staging-only", "symlink", "realpath", "digest", "staging-failure", "canonical-validation-failure", "selector-failure", "post-retirement-failure", "S16B"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
