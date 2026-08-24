import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "tools" / "validate-package-layout.py"
STAGED_TEMPLATE = REPO_ROOT / "staging" / "ask-park"


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
        nested.mkdir()
        (nested / "SKILL.md").write_text("---\nname: accidental\n---\n", encoding="utf-8")

        result = self.run_validator(package)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nested SKILL.md", result.stdout)


class FixtureHarnessTests(unittest.TestCase):
    def test_record_replay_reads_fixture_without_external_side_effects(self):
        harness_path = REPO_ROOT / "staging" / "ask-park" / "tests" / "fixture_harness.py"
        spec = __import__("importlib.util").util.spec_from_file_location("fixture_harness", harness_path)
        module = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(module)

        adapter = module.RecordReplayAdapter({"home": {"status": 200, "body": "fixture"}})
        self.assertEqual(adapter.read("home")["status"], 200)
        self.assertEqual(adapter.events, [{"kind": "read", "key": "home"}])
        module.assert_no_external_side_effects(adapter.events)

    def test_fixture_harness_rejects_network_or_mutation_events(self):
        harness_path = REPO_ROOT / "staging" / "ask-park" / "tests" / "fixture_harness.py"
        spec = __import__("importlib.util").util.spec_from_file_location("fixture_harness", harness_path)
        module = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with self.assertRaises(module.ExternalSideEffectError):
            module.assert_no_external_side_effects([{"kind": "network", "target": "example.invalid"}])


if __name__ == "__main__":
    unittest.main()
