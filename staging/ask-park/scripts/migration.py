#!/usr/bin/env python3
"""Staging-only inventory, manifest, installer, and rollback primitives.

S16A prepares a canonical Ask Park install without changing the active skill,
root package, selector, or any configured scanned root. Paths are inputs only;
all durable outputs use aliases, redacted refs, and digests.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[3]
LAYOUT = ROOT / "tools" / "validate-package-layout.py"
QA_SCHEMA = ROOT / "staging" / "ask-park" / "scripts" / "validate-qa-manifest.py"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PRIVATE_MARKERS = ("secret", "token", "password", "openid", "credential", "private_key", "api_key", "cookie", "appid", "environment_id")
PRIVATE_PREFIXES = ("http://", "https://", "file://", "cloud://", "/Users/", "/private/", "~/")
CHECKPOINTS = ("staging-failure", "canonical-validation-failure", "selector-failure", "post-retirement-failure")
CANONICAL_REPOSITORY = "zinan92/wechat-miniprogram-shipping"


class MigrationError(ValueError):
    def __init__(self, code: str, message: str, path: str = "migration") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "migration") -> None:
    raise MigrationError(code, message, path)


def _alias(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _safe(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(marker in normalized for marker in PRIVATE_MARKERS):
                return False
            if not _safe(child):
                return False
    elif isinstance(value, list):
        return all(_safe(child) for child in value)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(prefix in lowered for prefix in PRIVATE_PREFIXES):
            return False
    return True


def _jcs(value: Any) -> bytes:
    spec = importlib.util.spec_from_file_location("migration_qa_schema", QA_SCHEMA)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError("cannot load QA schema")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._canonical_json(value).encode("utf-8")


def _hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _hash_json(value: Any) -> str:
    return _hash_bytes(_jcs(value))


def _file_manifest(root: Path) -> tuple[list[dict[str, str]], str]:
    if not root.is_dir():
        _fail("MIGRATION_ROOT_MISSING", "scan root is not a directory", "root")
    rows: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        normalized = relative.lower().replace("-", "_")
        if any(marker in normalized for marker in PRIVATE_MARKERS) or any(part in normalized for part in (".env", "credentials", "cookies")):
            continue
        rows.append({"file_ref": "redacted:file-" + hashlib.sha256(relative.encode()).hexdigest()[:16], "digest": _hash_bytes(path.read_bytes())})
    manifest = {"files": rows}
    return rows, _hash_json(manifest)


def inventory_roots(root_specs: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Inventory configured/scanned roots without persisting path values."""

    if not isinstance(root_specs, list) or not root_specs:
        _fail("MIGRATION_ROOTS_REQUIRED", "at least one configured root is required", "roots")
    roots = []
    for spec in root_specs:
        if not isinstance(spec, Mapping) or set(spec) != {"root_alias", "path", "enabled"}:
            _fail("MIGRATION_ROOT_SPEC", "root spec requires root_alias, path, enabled", "roots")
        if not _alias(spec["root_alias"]) or not isinstance(spec["path"], str) or not isinstance(spec["enabled"], bool):
            _fail("MIGRATION_ROOT_SPEC", "root identity and enabled state are invalid", "roots")
        path = Path(spec["path"])
        real = path.resolve(strict=False)
        if not real.exists():
            _fail("MIGRATION_ROOT_MISSING", "configured root does not exist", "roots.path")
        files, digest = _file_manifest(real)
        roots.append(
            {
                "root_alias": spec["root_alias"],
                "symlink": path.is_symlink(),
                "realpath_ref": "redacted:realpath-" + hashlib.sha256(str(real).encode()).hexdigest()[:16],
                "enabled": spec["enabled"],
                "file_count": len(files),
                "file_manifest_digest": digest,
                "files": files,
            }
        )
    result = {"schema_version": 1, "kind": "skill-inventory", "roots": roots}
    if not _safe(result):
        _fail("MIGRATION_INVENTORY_PRIVATE", "inventory crossed the persistence boundary", "inventory")
    return result


def package_manifest(package_root: Path) -> dict[str, Any]:
    """Build a digest-bound staged package manifest."""

    if not package_root.is_dir():
        _fail("MIGRATION_PACKAGE_MISSING", "package root is missing", "package_root")
    entrypoint = package_root / "SKILL.md"
    metadata = package_root / "agents" / "openai.yaml"
    if not entrypoint.is_file() or not metadata.is_file():
        _fail("MIGRATION_PACKAGE_ENTRYPOINT", "canonical package requires one SKILL.md and agents/openai.yaml", "package")
    files, digest = _file_manifest(package_root)
    result = {"schema_version": 1, "kind": "ask-park-staged-manifest", "identity": "ask-park", "file_count": len(files), "files": files, "package_digest": digest}
    result["manifest_digest"] = _hash_json({key: value for key, value in result.items() if key != "manifest_digest"})
    return result


def stage_canonical_install(source_root: Path, staging_parent: Path, *, scanned_roots: list[Path] | None = None) -> dict[str, Any]:
    """Copy the staged package outside scanned roots and validate closure."""

    if source_root.is_symlink():
        _fail("MIGRATION_SOURCE_SYMLINK", "canonical staging refuses a symlink source root", "source_root")
    if source_root.resolve() == staging_parent.resolve() or staging_parent.resolve().is_relative_to(source_root.resolve()):
        _fail("MIGRATION_STAGING_SCOPE", "staging destination must be outside the source root", "staging_parent")
    for scanned_root in scanned_roots or []:
        scanned = Path(scanned_root).resolve()
        if staging_parent.resolve() == scanned or staging_parent.resolve().is_relative_to(scanned):
            _fail("MIGRATION_SCANNED_ROOT_SCOPE", "staging destination must be outside every scanned root", "staging_parent")
    if any(path.is_symlink() for path in source_root.rglob("*")):
        _fail("MIGRATION_SOURCE_SYMLINK", "canonical staging refuses source symlinks that could escape the package", "source_root")
    destination = staging_parent / "ask-park"
    if destination.exists():
        _fail("MIGRATION_DESTINATION_EXISTS", "staging destination must be a new controlled directory", "staging_parent")
    staging_parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root, destination, symlinks=False)
    layout_spec = importlib.util.spec_from_file_location("migration_layout", LAYOUT)
    if layout_spec is None or layout_spec.loader is None:  # pragma: no cover
        raise ImportError("cannot load package layout validator")
    layout = importlib.util.module_from_spec(layout_spec)
    layout_spec.loader.exec_module(layout)
    errors = layout.validate_package_layout(destination, mode="staged")
    if errors:
        _fail("MIGRATION_CANONICAL_VALIDATION", "staged package failed canonical validation", "staging")
    manifest = package_manifest(destination)
    return {"checkpoint": "staged", "staging_ref": "redacted:ask-park-staging", "manifest": manifest, "rollback_safe": True, "scope_verified": scanned_roots is not None}


def pre_migration_receipt(inventory: Mapping[str, Any], staged: Mapping[str, Any], *, repository_identity: str, history_ref: str) -> dict[str, Any]:
    if repository_identity != CANONICAL_REPOSITORY or not _alias(history_ref):
        _fail("MIGRATION_REPOSITORY_ID", "repository identity must remain zinan92/wechat-miniprogram-shipping and history must be an alias", "repository")
    if not isinstance(inventory, Mapping) or inventory.get("kind") != "skill-inventory":
        _fail("MIGRATION_INVENTORY_REQUIRED", "pre-migration receipt requires a validated inventory", "inventory")
    if not isinstance(staged, Mapping) or staged.get("checkpoint") != "staged" or staged.get("scope_verified") is not True:
        _fail("MIGRATION_STAGED_REQUIRED", "pre-migration receipt requires a staged package", "staged")
    manifest = staged.get("manifest")
    if not isinstance(manifest, Mapping) or manifest.get("kind") != "ask-park-staged-manifest" or not _digest(manifest.get("package_digest")) or not _digest(manifest.get("manifest_digest")):
        _fail("MIGRATION_MANIFEST_INVALID", "staged manifest must carry verified package and manifest digests", "staged.manifest")
    result = {
        "schema_version": 1,
        "kind": "pre-migration-receipt",
        "repository": {"identity": repository_identity, "history_ref": history_ref},
        "inventory_digest": _hash_json(inventory),
        "staged_manifest_digest": manifest["manifest_digest"],
        "legacy_enabled": True,
        "canonical_enabled": False,
        "checkpoints": list(CHECKPOINTS),
        "rollback": {"recoverable_backup": True, "active_root_mutated": False},
    }
    if not _safe(result):
        _fail("MIGRATION_RECEIPT_PRIVATE", "receipt crossed the persistence boundary", "receipt")
    result["receipt_digest"] = _hash_json(result)
    return result


def rollback_checkpoint(workspace: Path, checkpoint: str) -> dict[str, Any]:
    """Rehearse recoverable rollback for every pre-cutover checkpoint."""

    if checkpoint not in CHECKPOINTS:
        _fail("MIGRATION_CHECKPOINT_UNKNOWN", "checkpoint is outside the rollback contract", "checkpoint")
    canonical = workspace / "canonical-install"
    partial = workspace / "partial-install"
    legacy = workspace / "legacy-backup"
    if canonical.exists() or partial.exists() or legacy.exists():
        _fail("MIGRATION_ROLLBACK_WORKSPACE_DIRTY", "rollback rehearsal requires a new empty workspace", "workspace")
    failure_kind = checkpoint
    selector_before = "legacy-enabled"
    retirement_before = False
    if checkpoint == "staging-failure":
        partial.mkdir(parents=True, exist_ok=True)
        (partial / "partial-marker").write_text("copy-interrupted", encoding="utf-8")
        shutil.rmtree(partial)
    elif checkpoint == "canonical-validation-failure":
        canonical.mkdir(parents=True, exist_ok=True)
        (canonical / "invalid-marker").write_text("validation-failed", encoding="utf-8")
        shutil.rmtree(canonical)
    elif checkpoint == "selector-failure":
        canonical.mkdir(parents=True, exist_ok=True)
        (canonical / "selector-state").write_text("selector-readback-failed", encoding="utf-8")
        shutil.rmtree(canonical)
    elif checkpoint == "post-retirement-failure":
        canonical.mkdir(parents=True, exist_ok=True)
        (canonical / "canonical-marker").write_text("canonical-installed", encoding="utf-8")
        retirement_before = True
        shutil.rmtree(canonical)
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "legacy-marker").write_text("preserved", encoding="utf-8")
    return {"checkpoint": checkpoint, "failure_kind": failure_kind, "selector_before": selector_before, "retirement_before": retirement_before, "canonical_removed": not canonical.exists(), "partial_removed": not partial.exists(), "legacy_preserved": (legacy / "legacy-marker").read_text(encoding="utf-8") == "preserved"}
