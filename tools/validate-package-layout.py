#!/usr/bin/env python3
"""Validate the single-entry staged/final Ask Park package layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_DIRECTORIES = ("modules", "quality", "references", "scripts", "tests", "fixtures")


def _frontmatter(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    try:
        end = lines.index("---", 1)
    except ValueError:
        return []
    return lines[1:end]


def validate_package_layout(root: Path, mode: str = "staged") -> list[str]:
    errors: list[str] = []
    if mode not in {"staged", "final"}:
        return [f"unsupported mode: {mode}"]
    if not root.is_dir():
        return [f"package root is missing: {root}"]

    entrypoint = root / "SKILL.md"
    metadata = root / "agents" / "openai.yaml"
    if not entrypoint.is_file():
        errors.append("missing SKILL.md entrypoint")
    if not metadata.is_file():
        errors.append("missing agents/openai.yaml metadata")
    for directory in REQUIRED_DIRECTORIES:
        if not (root / directory).is_dir():
            errors.append(f"missing required directory: {directory}")

    if entrypoint.is_file():
        frontmatter = _frontmatter(entrypoint)
        if "name: ask-park" not in frontmatter:
            errors.append("SKILL.md must declare name: ask-park")
        if not any(line.startswith("description:") for line in frontmatter):
            errors.append("SKILL.md frontmatter is missing description")

    all_entrypoints = list(root.rglob("SKILL.md"))
    if len(all_entrypoints) != 1:
        errors.append(f"expected exactly one package SKILL.md, found {len(all_entrypoints)}")
    all_metadata = list(root.rglob("openai.yaml"))
    if len(all_metadata) != 1:
        errors.append(f"expected exactly one package agents/openai.yaml, found {len(all_metadata)}")

    nested_skill: list[Path] = []
    for base in (root / "modules", root / "quality"):
        if base.is_dir():
            nested_skill.extend(p for p in base.rglob("SKILL.md") if p.is_file())
    if nested_skill:
        errors.append("nested SKILL.md is not allowed: " + ", ".join(str(p.relative_to(root)) for p in nested_skill))
    nested_metadata: list[Path] = []
    for base in (root / "modules", root / "quality"):
        if base.is_dir():
            nested_metadata.extend(p for p in base.rglob("openai.yaml") if p.is_file())
    if nested_metadata:
        errors.append("nested agents/openai.yaml is not allowed: " + ", ".join(str(p.relative_to(root)) for p in nested_metadata))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mode", choices=("staged", "final"), default="staged")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate_package_layout(args.root, args.mode)
    payload = {"mode": args.mode, "root": str(args.root), "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("PASS" if not errors else "FAIL")
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
