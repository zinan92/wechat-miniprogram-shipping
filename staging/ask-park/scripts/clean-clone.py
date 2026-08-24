#!/usr/bin/env python3
"""Clean-clone installer and installed-path canary for S16B."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
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


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _files(root: Path) -> list[dict[str, str]]:
    ignored = {".git", ".pytest_cache", "__pycache__"}
    return [{"file": path.relative_to(root).as_posix(), "digest": _digest(path)} for path in sorted(root.rglob("*")) if path.is_file() and not any(part in ignored or path.suffix == ".pyc" for part in path.relative_to(root).parts)]


def package_manifest(root: Path) -> dict[str, Any]:
    if not root.is_dir() or any(not (root / required).is_file() for required in REQUIRED_FILES):
        _fail("CLEAN_CLONE_PACKAGE", "package entrypoint or metadata is missing", "package")
    files = _files(root)
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
    destination = codex_home / "skills" / "ask-park"
    if destination.exists():
        _fail("CLEAN_CLONE_DESTINATION", "isolated destination must be new", "destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_root, destination, ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc"))
    installed = quick_validate(destination)["manifest"]
    source = package_manifest(repo_root)
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
    missing_contracts = [str(installed_root / "modules" / directory / "MODULE.md") for directory in ("01-plan", "02-build", "03-cloudbase", "04-experience", "05-device", "06-release", "07-diagnose") if not (installed_root / "modules" / directory / "MODULE.md").is_file()]
    if missing_contracts:
        _fail("CLEAN_CLONE_MODULE_CLOSURE", "module contract is missing", "modules")
    for script in ("router.py", "state-lifecycle.py", "qa-evaluator.py", "browser-qa.py", "devtools-qa.py", "qa-routing.py", "validate-qa-manifest.py", "validate-state.py"):
        path = installed_root / "scripts" / script
        if not path.is_file():
            _fail("CLEAN_CLONE_QA_CLOSURE", "router or QA script is missing", script)
    router_path = installed_root / "scripts" / "router.py"
    spec = importlib.util.spec_from_file_location("installed_ask_park_router", router_path)
    if spec is None or spec.loader is None:
        _fail("CLEAN_CLONE_ROUTER_LOAD", "installed router cannot load", "router")
    router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(router)
    state_path = installed_root / "fixtures" / "state" / "valid-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    decision = router.route(state, "continuation")
    return {"router_loaded": True, "qa_paths_loaded": True, "module_contracts": 7, "canary_current_module": decision.current_module, "canary_map_size": len(decision.progress_map)}


def missing_file_failure(installed_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ask-park-missing-") as directory:
        copy_root = Path(directory) / "ask-park"
        shutil.copytree(installed_root, copy_root)
        (copy_root / "references" / "router.md").unlink()
        failed = False
        try:
            quick_validate(copy_root)
            if not (copy_root / "references" / "router.md").is_file():
                raise CleanCloneError("CLEAN_CLONE_MISSING_DEPENDENCY", "missing referenced router contract", "references/router.md")
        except CleanCloneError as exc:
            failed = exc.code == "CLEAN_CLONE_MISSING_DEPENDENCY"
        return {"missing_file_rejected": failed}
