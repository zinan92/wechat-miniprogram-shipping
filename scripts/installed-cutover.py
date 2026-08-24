#!/usr/bin/env python3
"""S16C installed-path canary and recoverable local cutover primitives."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import argparse
import tempfile
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
MIGRATION = importlib.util.spec_from_file_location("installed_cutover_migration", ROOT / "scripts" / "migration.py")
if MIGRATION is None or MIGRATION.loader is None:  # pragma: no cover
    raise ImportError("cannot load migration tooling")
MIGRATION_MODULE = importlib.util.module_from_spec(MIGRATION)
MIGRATION.loader.exec_module(MIGRATION_MODULE)
CLEAN = importlib.util.spec_from_file_location("installed_cutover_clean", ROOT / "scripts" / "clean-clone.py")
if CLEAN is None or CLEAN.loader is None:  # pragma: no cover
    raise ImportError("cannot load clean-clone tooling")
CLEAN_MODULE = importlib.util.module_from_spec(CLEAN)
CLEAN.loader.exec_module(CLEAN_MODULE)


class CutoverError(ValueError):
    def __init__(self, code: str, message: str, path: str = "installed-cutover") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, path: str = "installed-cutover") -> None:
    raise CutoverError(code, message, path)


def _safe(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(marker in normalized for marker in ("secret", "token", "password", "openid", "credential", "private_key", "api_key", "cookie", "url")):
                return False
            if not _safe(child):
                return False
    elif isinstance(value, list):
        return all(_safe(child) for child in value)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in ("http://", "https://", "file://", "cloud://", "/users/", "/private/", "~/")):
            return False
    return True


def selector_readback(scanned_roots: list[Path]) -> dict[str, Any]:
    """Read enabled identities from actual scanned roots without selectors writes."""

    identities: list[dict[str, Any]] = []
    for root in scanned_roots:
        if not root.is_dir():
            continue
        for skill_file in sorted(root.glob("*/SKILL.md")):
            text = skill_file.read_text(encoding="utf-8")
            identity = "ask-park" if "name: ask-park" in text else "wechat-miniprogram-shipping" if "name: wechat-miniprogram-shipping" in text else "unknown"
            identities.append({"root_alias": root.name, "identity": identity, "enabled": True, "path_ref": "redacted:selector-entry"})
    ask = [item for item in identities if item["identity"] == "ask-park" and item["enabled"]]
    legacy = [item for item in identities if item["identity"] == "wechat-miniprogram-shipping" and item["enabled"]]
    return {"entries": identities, "ask_park_enabled_count": len(ask), "legacy_enabled_count": len(legacy), "one_canonical": len(ask) == 1 and not legacy}


def installed_canary(canonical_root: Path, repository_root: Path) -> dict[str, Any]:
    if not canonical_root.is_dir():
        _fail("CUTOVER_CANONICAL_MISSING", "canonical installed root is missing", "canonical_root")
    canary = CLEAN_MODULE.canary(canonical_root)
    expected = CLEAN_MODULE.package_manifest(repository_root, closure_only=True)
    actual = CLEAN_MODULE.package_manifest(canonical_root, closure_only=True)
    if expected["manifest_digest"] != actual["manifest_digest"]:
        _fail("CUTOVER_MANIFEST_MISMATCH", "installed manifest differs from repository closure", "manifest")
    return {"manifest_digest": actual["manifest_digest"], "router_loaded": canary["router_loaded"], "qa_paths_loaded": canary["qa_paths_loaded"], "module_contracts": canary["module_contracts"], "current_module": canary["canary_current_module"]}


def backup_legacy(legacy_root: Path, backup_root: Path) -> dict[str, Any]:
    if not legacy_root.is_dir() or backup_root.exists():
        _fail("CUTOVER_BACKUP_SCOPE", "legacy root must exist and backup destination must be new", "backup")
    backup_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(legacy_root, backup_root, symlinks=False)
    return {"backup_ref": "redacted:legacy-backup", "backup_manifest": CLEAN_MODULE.package_manifest(backup_root, closure_only=False)}


def apply_cutover(*, legacy_root: Path, canonical_root: Path, staged_root: Path, backup_root: Path) -> dict[str, Any]:
    """Atomically move legacy to a recoverable backup and staged to canonical."""

    if not legacy_root.is_dir() or canonical_root.exists() or not staged_root.is_dir() or backup_root.exists():
        _fail("CUTOVER_PRECONDITION", "legacy/canonical/staged/backup preconditions are invalid", "cutover")
    backup_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(legacy_root, backup_root)
    try:
        os.replace(staged_root, canonical_root)
    except Exception:
        os.replace(backup_root, legacy_root)
        raise
    return {"legacy_retired": True, "canonical_active": True, "backup_ref": "redacted:legacy-backup"}


def rollback_cutover(*, legacy_root: Path, canonical_root: Path, backup_root: Path) -> dict[str, Any]:
    if not canonical_root.is_dir() or not backup_root.is_dir() or legacy_root.exists():
        _fail("CUTOVER_ROLLBACK_PRECONDITION", "rollback requires canonical + backup and no legacy collision", "rollback")
    rollback_canonical = canonical_root.parent / (canonical_root.name + ".rollback")
    if rollback_canonical.exists():
        _fail("CUTOVER_ROLLBACK_DESTINATION", "rollback destination already exists", "rollback")
    os.replace(canonical_root, rollback_canonical)
    try:
        os.replace(backup_root, legacy_root)
    except Exception:
        os.replace(rollback_canonical, canonical_root)
        raise
    shutil.rmtree(rollback_canonical)
    return {"legacy_restored": legacy_root.is_dir(), "canonical_removed": not canonical_root.exists(), "backup_consumed": not backup_root.exists()}


def operational_receipt(*, inventory: Mapping[str, Any], selector: Mapping[str, Any], canary: Mapping[str, Any], backup_ref: str, rollback_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(backup_ref, str) or not re.fullmatch(r"redacted:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", backup_ref):
        _fail("CUTOVER_RECEIPT_REF", "backup reference must be a redacted alias", "backup_ref")
    if not _safe(inventory) or not _safe(canary) or not _safe(rollback_results):
        _fail("CUTOVER_RECEIPT_PRIVATE", "operational receipt contains private data", "receipt")
    if not isinstance(canary, Mapping) or not isinstance(canary.get("manifest_digest"), str) or not SHA_RE.fullmatch(canary["manifest_digest"]):
        _fail("CUTOVER_CANARY_DIGEST", "canary must carry a full manifest digest", "canary")
    if not isinstance(rollback_results, list) or {item.get("checkpoint") for item in rollback_results if isinstance(item, Mapping)} != set(MIGRATION_MODULE.CHECKPOINTS) or any(not isinstance(item, Mapping) or not all(isinstance(item.get(key), bool) and item.get(key) is True for key in ("legacy_restored", "canonical_removed", "partial_removed")) for item in rollback_results):
        _fail("CUTOVER_ROLLBACK_RECEIPT", "rollback receipt rows are malformed", "rollback_results")
    result = {"schema_version": 1, "kind": "ask-park-installed-cutover", "repository_identity": "zinan92/wechat-miniprogram-shipping", "inventory": copy.deepcopy(dict(inventory)), "inventory_digest": MIGRATION_MODULE._hash_json(inventory), "selector": {"ask_park_enabled_count": selector["ask_park_enabled_count"], "legacy_enabled_count": selector["legacy_enabled_count"], "one_canonical": selector["one_canonical"]}, "canary": copy.deepcopy(dict(canary)), "backup_ref": backup_ref, "rollback_results": copy.deepcopy(rollback_results), "evidence_mode": "sanitized-persisted", "limitations": ["Installed selector state is local to the scanned roots read during this operation."]}
    if not selector["one_canonical"]:
        _fail("CUTOVER_SELECTOR_INVALID", "selector read-back is not one canonical Ask Park and zero legacy", "selector")
    if any(not result.get("legacy_restored") or not result.get("canonical_removed") for result in rollback_results):
        _fail("CUTOVER_ROLLBACK_INCOMPLETE", "rollback rehearsal did not restore legacy cleanly", "rollback_results")
    if not canary.get("router_loaded") or not canary.get("qa_paths_loaded"):
        _fail("CUTOVER_CANARY_INCOMPLETE", "installed canary did not load router and QA paths", "canary")
    result["receipt_digest"] = MIGRATION_MODULE._hash_json(result)
    return result


def _outside(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    return all(resolved != root.resolve() and not resolved.is_relative_to(root.resolve()) for root in roots)


def run_local_cutover(*, repository_root: Path, scanned_roots: list[tuple[str, Path]], legacy_root: Path, canonical_root: Path, migration_root: Path, backup_root: Path, receipt_path: Path) -> dict[str, Any]:
    roots = [path for _, path in scanned_roots]
    root_set = {path.resolve() for path in roots}
    if legacy_root.resolve().parent not in root_set or canonical_root.resolve().parent not in root_set or legacy_root.is_symlink() or canonical_root.is_symlink():
        _fail("CUTOVER_TARGET_SCOPE", "legacy and canonical targets must be direct children of a scanned root", "targets")
    if legacy_root.name != "wechat-miniprogram-shipping" or canonical_root.name != "ask-park" or not (legacy_root / "SKILL.md").is_file() or "name: wechat-miniprogram-shipping" not in (legacy_root / "SKILL.md").read_text(encoding="utf-8"):
        _fail("CUTOVER_TARGET_IDENTITY", "legacy/canonical target names and identities do not match the cutover contract", "targets")
    if not _outside(migration_root, roots) or not _outside(backup_root, roots) or (not receipt_path.resolve().is_relative_to(repository_root.resolve()) and (receipt_path.parent.name != "receipts" or not _outside(receipt_path.parent, roots))):
        _fail("CUTOVER_SCOPE", "migration and backup roots must be outside scanned roots", "scope")
    if migration_root.exists() or not migration_root.name.startswith("ask-park-migration-"):
        _fail("CUTOVER_MIGRATION_SCOPE", "migration root must be a new managed workspace", "migration_root")
    inventory = MIGRATION_MODULE.inventory_roots([{"root_alias": alias, "path": str(path), "enabled": True} for alias, path in scanned_roots])
    before_selector = selector_readback(roots)
    if before_selector["legacy_enabled_count"] != 1 or before_selector["ask_park_enabled_count"] != 0:
        _fail("CUTOVER_PRE_SELECTOR", "cutover requires exactly one legacy entry and no canonical duplicate", "selector")
    migration_root.mkdir(parents=True, exist_ok=False)
    cutover_applied = False
    completed = False
    try:
        first_home = migration_root / "clean-clone-home-actual"
        staged = CLEAN_MODULE.install_isolated(repository_root, first_home)
        staged_canary = installed_canary(staged["destination"], repository_root)
        apply_cutover(legacy_root=legacy_root, canonical_root=canonical_root, staged_root=staged["destination"], backup_root=backup_root)
        cutover_applied = True
        selector = selector_readback(roots)
        installed = installed_canary(canonical_root, repository_root)
        rollback_results = []
        for checkpoint in MIGRATION_MODULE.CHECKPOINTS:
            workspace = migration_root / ("migration-rollback-" + checkpoint)
            rehearsal = MIGRATION_MODULE.rollback_checkpoint(workspace, checkpoint)
            rollback_results.append({"checkpoint": checkpoint, "legacy_restored": rehearsal["legacy_preserved"], "canonical_removed": rehearsal["canonical_removed"], "partial_removed": rehearsal["partial_removed"]})
        rollback_cutover(legacy_root=legacy_root, canonical_root=canonical_root, backup_root=backup_root)
        cutover_applied = False
        second_home = migration_root / "clean-clone-home-final"
        staged_again = CLEAN_MODULE.install_isolated(repository_root, second_home)
        apply_cutover(legacy_root=legacy_root, canonical_root=canonical_root, staged_root=staged_again["destination"], backup_root=backup_root)
        cutover_applied = True
        final_selector = selector_readback(roots)
        final_canary = installed_canary(canonical_root, repository_root)
        receipt = operational_receipt(inventory=inventory, selector=final_selector, canary=final_canary, backup_ref="redacted:legacy-backup", rollback_results=rollback_results)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        completed = True
        return {"pre_cutover_canary": staged_canary, "first_installed_canary": installed, "final_selector": final_selector, "final_canary": final_canary, "receipt": receipt, "legacy_backup_preserved": backup_root.is_dir()}
    finally:
        if cutover_applied and not completed and canonical_root.is_dir() and backup_root.is_dir() and not legacy_root.exists():
            rollback_cutover(legacy_root=legacy_root, canonical_root=canonical_root, backup_root=backup_root)
        if migration_root.exists():
            shutil.rmtree(migration_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--canonical-root", type=Path, required=True)
    parser.add_argument("--migration-root", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--receipt-path", type=Path, required=True)
    parser.add_argument("--scanned-root", action="append", nargs=2, metavar=("ALIAS", "PATH"), required=True)
    args = parser.parse_args(argv)
    result = run_local_cutover(repository_root=args.repository_root, scanned_roots=[(alias, Path(path)) for alias, path in args.scanned_root], legacy_root=args.legacy_root, canonical_root=args.canonical_root, migration_root=args.migration_root, backup_root=args.backup_root, receipt_path=args.receipt_path)
    print(json.dumps({key: value for key, value in result.items() if key != "receipt"} | {"receipt_digest": result["receipt"]["receipt_digest"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
