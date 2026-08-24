import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "clean-clone.py"


def load_clean_clone():
    spec = importlib.util.spec_from_file_location("ask_park_clean_clone", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CleanCloneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = load_clean_clone()

    def test_staged_package_quick_validate_and_isolated_install(self):
        package = ROOT
        self.assertTrue((package / "SKILL.md").is_file())
        # S16B runs against a package root after cutover; staging remains the
        # source in this pre-cutover test and is validated separately below.
        staged = self.clean.quick_validate(ROOT)
        self.assertTrue(staged["valid"])

    def test_clean_clone_manifest_canary_and_missing_file_failure(self):
        with tempfile.TemporaryDirectory(prefix="clean-clone-home-") as directory:
            installed = self.clean.install_isolated(ROOT, Path(directory))
            self.assertEqual(installed["receipt"]["source_manifest_digest"], installed["receipt"]["installed_manifest_digest"])
            canary = self.clean.canary(installed["destination"])
            self.assertTrue(canary["router_loaded"])
            self.assertEqual(canary["module_contracts"], 7)
            self.assertEqual(canary["canary_map_size"], 7)
            missing = self.clean.missing_file_failure(installed["destination"])
            self.assertTrue(missing["missing_file_rejected"])
            self.assertEqual(len(missing["rejected_files"]), 7)
            self.assertNotIn(str(directory), json.dumps(installed["receipt"]))

    def test_docs_define_atomic_clean_clone_and_missing_dependency(self):
        text = (ROOT / "quality" / "clean-clone.md").read_text(encoding="utf-8")
        for phrase in ("exactly one", "CODEX_HOME", "every installed file digest", "router", "seven module", "missing-file failure", "S16C"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
