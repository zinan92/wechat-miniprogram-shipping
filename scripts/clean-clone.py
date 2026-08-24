#!/usr/bin/env python3
"""Clean-clone installer and installed-path canary for S16B."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import argparse
from pathlib import Path
from typing import Any


class CleanCloneError(ValueError):
    def __init__(self, code: str, message: str, path: str = "clean-clone") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "clean-clone") -> None:
    raise CleanCloneError(code, message, path)


REQUIRED_DIRECTORIES = ("modules", "quality", "references", "scripts", "tests", "fixtures")
REQUIRED_FILES = ("SKILL.md", "agents/openai.yaml")
CLOSURE = ("SKILL.md", "agents", "modules", "quality", "references", "scripts", "tests", "fixtures")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _files(root: Path, *, closure_only: bool = False) -> list[dict[str, str]]:
    ignored = {".git", ".pytest_cache", "__pycache__"}
    candidates: list[Path] = []
    for entry in CLOSURE if closure_only else (".",):
        base = root / entry if entry != "." else root
        if base.is_file():
            candidates.append(base)
        elif base.is_dir():
            candidates.extend(base.rglob("*"))
    rows = []
    for path in sorted(candidates):
        relative = path.relative_to(root)
        if path.is_file() and not any(part in ignored or path.suffix == ".pyc" for part in relative.parts):
            rows.append({"file_ref": "redacted:file-" + hashlib.sha256(relative.as_posix().encode()).hexdigest()[:16], "digest": _digest(path)})
    return rows


def package_manifest(root: Path, *, closure_only: bool = False) -> dict[str, Any]:
    if not root.is_dir() or any(not (root / required).is_file() for required in REQUIRED_FILES):
        _fail("CLEAN_CLONE_PACKAGE", "package entrypoint or metadata is missing", "package")
    files = _files(root, closure_only=closure_only)
    payload = {"identity": "ask-park", "files": files}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**payload, "manifest_digest": "sha256:" + hashlib.sha256(canonical).hexdigest()}


def quick_validate(root: Path, *, final: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    if not root.is_dir():
        errors.append("package root missing")
    for directory in REQUIRED_DIRECTORIES:
        if not (root / directory).is_dir():
            errors.append(f"missing directory: {directory}")
    for required in REQUIRED_FILES:
        if not (root / required).is_file():
            errors.append(f"missing file: {required}")
    skill_files = list(root.rglob("SKILL.md"))
    metadata_files = list(root.rglob("openai.yaml"))
    if len(skill_files) != 1:
        errors.append("expected exactly one SKILL.md")
    if len(metadata_files) != 1:
        errors.append("expected exactly one openai.yaml")
    if final and (root / "staging" / "ask-park").exists():
        errors.append("staging source remains in final package")
    if skill_files and "name: ask-park" not in skill_files[0].read_text(encoding="utf-8"):
        errors.append("SKILL.md identity is not ask-park")
    if errors:
        raise CleanCloneError("CLEAN_CLONE_VALIDATION", "; ".join(errors), "package")
    return {"valid": True, "manifest": package_manifest(root)}


def install_isolated(repo_root: Path, codex_home: Path) -> dict[str, Any]:
    """Follow the README closure into an isolated CODEX_HOME."""

    quick_validate(repo_root, final=True)
    if not codex_home.is_absolute() or codex_home.resolve() == repo_root.resolve() or codex_home.resolve().is_relative_to(repo_root.resolve()) or not codex_home.name.startswith("clean-clone-home-"):
        _fail("CLEAN_CLONE_HOME_SCOPE", "clean-clone requires a new managed temporary CODEX_HOME outside the repository", "codex_home")
    if any(path.is_symlink() for path in repo_root.rglob("*")):
        _fail("CLEAN_CLONE_SOURCE_SYMLINK", "clean-clone refuses source symlinks", "repo_root")
    destination = codex_home / "skills" / "ask-park"
    if destination.exists():
        _fail("CLEAN_CLONE_DESTINATION", "isolated destination must be new", "destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    for entry in CLOSURE:
        source = repo_root / entry
        target = destination / entry
        if source.is_dir():
            shutil.copytree(source, target, symlinks=False)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    quick_validate(destination)
    source = package_manifest(repo_root, closure_only=True)
    installed = package_manifest(destination, closure_only=True)
    if source["manifest_digest"] != installed["manifest_digest"]:
        _fail("CLEAN_CLONE_MANIFEST_MISMATCH", "installed manifest differs from repository package", "manifest")
    receipt_dir = codex_home / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt = {"schema_version": 1, "kind": "clean-clone-install", "identity": "ask-park", "source_manifest_digest": source["manifest_digest"], "installed_manifest_digest": installed["manifest_digest"], "files": installed["files"], "codex_home_ref": "redacted:isolated-codex-home"}
    (receipt_dir / "ask-park-installed-manifest.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"destination_ref": "redacted:isolated-ask-park", "receipt": receipt, "destination": destination}


def canary(installed_root: Path) -> dict[str, Any]:
    """Load router, lifecycle, every module contract, and QA seams."""

    quick_validate(installed_root)
    for reference in ("references/router.md", "references/status-contract.md", "references/evidence-contract.md", "references/human-gates-contract.md", "references/transition-contract.md"):
        if not (installed_root / reference).is_file():
            _fail("CLEAN_CLONE_REFERENCE_CLOSURE", "installed referenced contract is missing", reference)
    module_contracts = [installed_root / "modules" / directory / "MODULE.md" for directory in ("01-plan", "02-build", "03-cloudbase", "04-experience", "05-device", "06-release", "07-diagnose")]
    missing_contracts = [str(path) for path in module_contracts if not path.is_file() or any(phrase not in path.read_text(encoding="utf-8") for phrase in ("Input", "Output", "Success predicate", "Failure outcomes", "Evidence", "Forbidden boundary"))]
    if missing_contracts:
        _fail("CLEAN_CLONE_MODULE_CLOSURE", "module contract is missing", "modules")
    script_names = ("router.py", "state-lifecycle.py", "qa-evaluator.py", "browser-qa.py", "devtools-qa.py", "qa-routing.py", "validate-qa-manifest.py", "validate-state.py")
    for script in script_names:
        path = installed_root / "scripts" / script
        if not path.is_file():
            _fail("CLEAN_CLONE_QA_CLOSURE", "router or QA script is missing", script)
    loaded = {}
    for script in script_names:
        path = installed_root / "scripts" / script
        spec = importlib.util.spec_from_file_location("installed_ask_park_" + script.replace("-", "_").replace(".", "_"), path)
        if spec is None or spec.loader is None:
            _fail("CLEAN_CLONE_QA_LOAD", "installed script cannot load", script)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            _fail("CLEAN_CLONE_QA_LOAD", "installed script raised during load", script)
        loaded[script] = module
    router = loaded["router.py"]
    state_path = installed_root / "fixtures" / "state" / "valid-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    decision = router.route(state, "continuation")
    return {"router_loaded": True, "qa_paths_loaded": True, "module_contracts": len(module_contracts), "canary_current_module": decision.current_module, "canary_map_size": len(decision.progress_map)}


def missing_file_failure(installed_root: Path) -> dict[str, Any]:
    required = ["SKILL.md", "agents/openai.yaml", "references/router.md", "modules/01-plan/MODULE.md", "scripts/router.py", "scripts/devtools-qa.py", "fixtures/state/valid-state.json"]
    rejected: list[str] = []
    for relative in required:
        with tempfile.TemporaryDirectory(prefix="ask-park-missing-") as directory:
            copy_root = Path(directory) / "ask-park"
            shutil.copytree(installed_root, copy_root)
            target = copy_root / relative
            if target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target, ignore_errors=True)
            try:
                canary(copy_root)
            except Exception:
                rejected.append(relative)
    return {"missing_file_rejected": len(rejected) == len(required), "rejected_files": rejected}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, required=True)
    args = parser.parse_args(argv)
    installed = install_isolated(args.repo_root, args.codex_home)
    result = {"install": installed["receipt"], "canary": canary(installed["destination"]), "missing_file": missing_file_failure(installed["destination"])}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
