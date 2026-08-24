import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "tools" / "validate-package-layout.py"
STAGED_TEMPLATE = REPO_ROOT


class PackageLayoutValidatorTests(unittest.TestCase):
    def run_validator(self, root: Path, mode: str = "staged"):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--root", str(root), "--mode", mode, "--json"],
            capture_output=True,
            text=True,
            check=False,
        )

    def copy_template(self):
        destination = Path(tempfile.mkdtemp(prefix="ask-park-layout-")) / "ask-park"
        shutil.copytree(STAGED_TEMPLATE, destination)
        self.addCleanup(shutil.rmtree, destination.parent, ignore_errors=True)
        return destination

    def test_staged_template_is_a_complete_single_entry_package(self):
        result = self.run_validator(STAGED_TEMPLATE)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "staged")
        self.assertEqual(payload["errors"], [])

    def test_missing_entrypoint_is_rejected(self):
        package = self.copy_template()
        (package / "SKILL.md").unlink()

        result = self.run_validator(package)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SKILL.md", result.stdout)

    def test_nested_skill_metadata_is_rejected(self):
        package = self.copy_template()
        nested = package / "modules" / "01-plan"
        nested.mkdir(exist_ok=True)
        (nested / "SKILL.md").write_text("---\nname: accidental\n---\n", encoding="utf-8")

        result = self.run_validator(package)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nested SKILL.md", result.stdout)

    def test_nested_module_file_is_allowed(self):
        package = self.copy_template()
        module = package / "modules" / "01-plan"
        module.mkdir(exist_ok=True)
        (module / "MODULE.md").write_text("# Plan module\n", encoding="utf-8")

        result = self.run_validator(package)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_nested_metadata_is_rejected(self):
        package = self.copy_template()
        metadata = package / "quality" / "agents"
        metadata.mkdir()
        (metadata / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")

        result = self.run_validator(package)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nested agents/openai.yaml", result.stdout)

    def test_missing_local_entrypoint_reference_is_rejected(self):
        package = self.copy_template()
        (package / "SKILL.md").write_text(
            "---\nname: ask-park\ndescription: staged\n---\n\n[missing](references/not-there.md)\n",
            encoding="utf-8",
        )

        result = self.run_validator(package)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing SKILL.md reference", result.stdout)

    def test_final_mode_requires_public_package_files_and_no_staging_copy(self):
        package = self.copy_template()
        (package / "README.md").write_text("# Ask Park\n", encoding="utf-8")
        (package / "REGISTRY.md").write_text("# Registry\n", encoding="utf-8")

        valid = self.run_validator(package, mode="final")
        self.assertEqual(valid.returncode, 0, valid.stdout)

        (package / "staging" / "ask-park").mkdir(parents=True)
        invalid = self.run_validator(package, mode="final")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("staging/ask-park", invalid.stdout)


class FixtureHarnessTests(unittest.TestCase):
    def test_record_replay_reads_fixture_without_external_side_effects(self):
        harness_path = REPO_ROOT / "tests" / "fixture_harness.py"
        spec = __import__("importlib.util").util.spec_from_file_location("fixture_harness", harness_path)
        module = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(module)

        adapter = module.RecordReplayAdapter({"home": {"status": 200, "body": "fixture"}})
        self.assertEqual(adapter.read("home")["status"], 200)
        self.assertEqual(adapter.events, [{"kind": "read", "key": "home"}])
        module.assert_no_external_side_effects(adapter.events)

    def test_fixture_harness_rejects_network_or_mutation_events(self):
        harness_path = REPO_ROOT / "tests" / "fixture_harness.py"
        spec = __import__("importlib.util").util.spec_from_file_location("fixture_harness", harness_path)
        module = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with self.assertRaises(module.ExternalSideEffectError):
            module.assert_no_external_side_effects([{"kind": "network", "target": "example.invalid"}])
        with self.assertRaises(module.ExternalSideEffectError):
            module.assert_no_external_side_effects([{"kind": "filesystem_write", "target": "fixture"}])

        adapter = module.RecordReplayAdapter({})
        for action in (
            lambda: adapter.request("example.invalid"),
            lambda: adapter.write("fixture", {}),
            lambda: adapter.delete("fixture"),
        ):
            with self.assertRaises(module.ExternalSideEffectError):
                action()


if __name__ == "__main__":
    unittest.main()
