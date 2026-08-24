import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "installed-cutover.py"


def load_cutover():
    spec = importlib.util.spec_from_file_location("ask_park_installed_cutover", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class InstalledCutoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cutover = load_cutover()

    def package(self, root: Path, identity: str):
        (root / "agents").mkdir(parents=True)
        (root / "SKILL.md").write_text(f"---\nname: {identity}\ndescription: fixture\n---\n", encoding="utf-8")
        (root / "agents" / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")

    def test_selector_readback_and_recoverable_apply_rollback(self):
        with tempfile.TemporaryDirectory(prefix="installed-cutover-") as directory:
            base = Path(directory)
            skills = base / "skills"
            skills.mkdir()
            legacy = skills / "wechat-miniprogram-shipping"
            self.package(legacy, "wechat-miniprogram-shipping")
            staged = base / "staged-ask-park"
            self.package(staged, "ask-park")
            backup = base / "legacy-backup"
            before = self.cutover.selector_readback([skills])
            self.assertEqual(before["legacy_enabled_count"], 1)
            self.cutover.apply_cutover(legacy_root=legacy, canonical_root=skills / "ask-park", staged_root=staged, backup_root=backup)
            after = self.cutover.selector_readback([skills])
            self.assertTrue(after["one_canonical"])
            restored = self.cutover.rollback_cutover(legacy_root=legacy, canonical_root=skills / "ask-park", backup_root=backup)
            self.assertTrue(restored["legacy_restored"])
            self.assertTrue(restored["canonical_removed"])

    def test_installed_canary_and_manifest_equality(self):
        with tempfile.TemporaryDirectory(prefix="installed-canary-") as directory:
            home = Path(directory) / "clean-clone-home-test"
            home.mkdir()
            installed = self.cutover.CLEAN_MODULE.install_isolated(ROOT, home)
            canary = self.cutover.installed_canary(installed["destination"], ROOT)
            self.assertTrue(canary["router_loaded"])
            self.assertTrue(canary["qa_paths_loaded"])
            self.assertEqual(canary["module_contracts"], 7)

    def test_operational_receipt_requires_clean_selector_and_rollback(self):
        inventory = {"kind": "skill-inventory", "roots": []}
        selector = {"ask_park_enabled_count": 1, "legacy_enabled_count": 0, "one_canonical": True}
        canary = {"router_loaded": True, "qa_paths_loaded": True, "module_contracts": 7, "manifest_digest": "sha256:" + "a" * 64}
        rollbacks = [{"legacy_restored": True, "canonical_removed": True} for _ in self.cutover.MIGRATION_MODULE.CHECKPOINTS]
        receipt = self.cutover.operational_receipt(inventory=inventory, selector=selector, canary=canary, backup_ref="redacted:legacy-backup", rollback_results=rollbacks)
        self.assertEqual(receipt["repository_identity"], "zinan92/wechat-miniprogram-shipping")
        self.assertTrue(receipt["receipt_digest"].startswith("sha256:"))
        self.assertNotIn(str(ROOT), json.dumps(receipt))

    def test_local_cutover_rehearses_rollback_then_reapplies_canonical(self):
        with tempfile.TemporaryDirectory(prefix="installed-local-") as directory:
            base = Path(directory)
            skills = base / "skills"
            skills.mkdir()
            legacy = skills / "wechat-miniprogram-shipping"
            self.package(legacy, "wechat-miniprogram-shipping")
            result = self.cutover.run_local_cutover(
                repository_root=ROOT,
                scanned_roots=[("synthetic-skills", skills)],
                legacy_root=legacy,
                canonical_root=skills / "ask-park",
                migration_root=base / "migration-root",
                backup_root=base / "legacy-backup",
                receipt_path=base / "receipt.json",
            )
            self.assertTrue(result["final_selector"]["one_canonical"])
            self.assertEqual(result["final_selector"]["legacy_enabled_count"], 0)
            self.assertTrue(result["final_canary"]["router_loaded"])
            self.assertTrue(result["legacy_backup_preserved"])
            self.assertFalse((base / "migration-root").exists())
            self.assertTrue((base / "receipt.json").is_file())

    def test_docs_define_installed_canary_selector_and_rollback(self):
        text = (ROOT / "quality" / "installed-cutover.md").read_text(encoding="utf-8")
        for phrase in ("installed-path", "exactly one", "$ask-park", "legacy", "backup", "manifest digest", "canary", "rollback"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
