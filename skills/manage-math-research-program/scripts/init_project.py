#!/usr/bin/env python3
"""Initialize a manage-math-research-program repository.

This script creates only project-management files. It never creates any
problem-level artifacts owned by $rigorous-open-math-research.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


DIRECTORIES = [
    "state/checkpoints",
    "state/stage-summaries",
    "index",
    "literature/search-log",
    "literature/papers",
    "literature/maps",
    "agenda/problems",
    "agenda/task-packets",
    "knowledge/tools",
    "knowledge/submissions",
    "knowledge/backups",
    "knowledge/viewer",
    "knowledge/artifacts",
    "runs/rigorous-open-math-research",
    "reports",
    "archive/superseded",
    "archive/rejected-duplicates",
]

INDEX_NAMES = [
    "papers",
    "paper-relations",
    "open-problems",
    "tools",
    "task-packets",
    "runs",
    "artifacts",
]


class InitError(RuntimeError):
    """Raised for a safe, user-facing initialization failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "math-research"


def render(template_path: Path, replacements: dict[str, str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", text)))
    if unresolved:
        raise InitError(f"Unresolved template tokens in {template_path.name}: {unresolved}")
    return text


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise InitError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path, help="Directory to create or initialize")
    parser.add_argument("--name", required=True, help="Human-readable project name")
    parser.add_argument("--slug", help="Filesystem/project slug; derived from the name by default")
    parser.add_argument(
        "--research-budget-hours",
        type=float,
        default=None,
        help="Configured evidence-backed effective-time target. Omit for no target.",
    )
    parser.add_argument(
        "--budget-configured-by",
        default=None,
        help="Provenance label for the budget setting; inferred as user/unset by default",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    slug = slugify(args.slug or args.name)

    if args.research_budget_hours is not None and args.research_budget_hours <= 0:
        raise InitError("--research-budget-hours must be positive when supplied")

    if root.exists() and any(root.iterdir()):
        raise InitError(f"Target directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)

    package_root = Path(__file__).resolve().parent.parent
    assets = package_root / "assets"
    required_templates = [
        "project.template.json",
        "current-state.template.json",
        "project-overview.template.md",
    ]
    for name in required_templates:
        if not (assets / name).is_file():
            raise InitError(f"Missing skill asset: {assets / name}")

    created_at = utc_now()
    identity_seed = f"{slug}|{created_at}".encode("utf-8")
    project_id = f"MRP-{created_at[:10].replace('-', '')}-{slug}-{sha256(identity_seed).hexdigest()[:6]}"

    target_json = "null" if args.research_budget_hours is None else json.dumps(args.research_budget_hours)
    target_display = "unset" if args.research_budget_hours is None else f"{args.research_budget_hours:g} effective hours"
    budget_configured_by = args.budget_configured_by or (
        "user" if args.research_budget_hours is not None else "unset"
    )
    replacements = {
        "PROJECT_ID": project_id,
        "PROJECT_NAME": args.name,
        "PROJECT_NAME_JSON": json.dumps(args.name, ensure_ascii=False),
        "PROJECT_SLUG": slug,
        "PROJECT_SLUG_JSON": json.dumps(slug, ensure_ascii=False),
        "CREATED_AT": created_at,
        "TARGET_HOURS": target_json,
        "TARGET_HOURS_DISPLAY": target_display,
        "BUDGET_CONFIGURED_BY_JSON": json.dumps(budget_configured_by, ensure_ascii=False),
    }

    for directory in DIRECTORIES:
        (root / directory).mkdir(parents=True, exist_ok=True)

    write_new(root / "project.json", render(assets / "project.template.json", replacements))
    write_new(root / "PROJECT.md", render(assets / "project-overview.template.md", replacements))
    write_new(root / "state/current.json", render(assets / "current-state.template.json", replacements))

    resume = f"""# Resume this mathematics research program

- **Project:** {args.name}
- **Project ID:** `{project_id}`
- **Updated:** {created_at}

## Current objective

Define the project scope and run the first dated literature search.

## Read these files first

1. `project.json`
2. `PROJECT.md`
3. `state/current.json`

## Last completed action

Initialized the project repository.

## Active tasks and runs

None.

## Exact next action

Complete the scope and inclusion criteria in `PROJECT.md`, then create the first search log from the installed skill asset `assets/search-log.template.md`.

## Blockers or missing inputs

None recorded.

## Budget remaining

{target_display}.

## Validation command

```bash
python /path/to/manage-math-research-program/scripts/validate_project.py "{root}"
```
"""
    write_new(root / "state/RESUME.md", resume)
    write_new(root / "state/activity.jsonl", "")

    for index_name in INDEX_NAMES:
        payload = {"schema_version": 1, "updated_at": created_at, "items": []}
        write_new(root / f"index/{index_name}.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    seed_files = {
        "literature/maps/PAPER_MAP.md": "# Paper map\n\nNo papers registered yet.\n",
        "literature/maps/FRONTIER.md": "# Literature frontier\n\nNo dated frontier scan completed yet.\n",
        "literature/maps/TERMINOLOGY.md": "# Terminology map\n\nRecord aliases and formulation differences here.\n",
        "agenda/DIRECTIONS.md": "# Research directions\n\nDefine program-level directions here.\n",
        "agenda/PRIORITIES.md": "# Portfolio priorities\n\nRecord planning priorities and rationales here.\n",
        "knowledge/GLOSSARY.md": "# Project glossary\n\n",
        "knowledge/FAILURE_PATTERNS.md": "# Reusable failure and obstruction patterns\n\nOnly add source-located or upstream-supported mechanisms.\n",
    }
    for relative_path, content in seed_files.items():
        write_new(root / relative_path, content)

    knowledge_seed = assets / "blueprint-accepted-knowledge"
    if not knowledge_seed.is_dir():
        raise InitError(f"Missing skill asset: {knowledge_seed}")
    for source in sorted(knowledge_seed.rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        relative = source.relative_to(knowledge_seed)
        target = root / "knowledge" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative == Path("blueprint.json"):
            target.write_text(render(source, replacements), encoding="utf-8")
        else:
            shutil.copy2(source, target)
    write_new(root / "knowledge/blueprint_update_requests.jsonl", "")
    print(json.dumps({
        "project_root": str(root),
        "project_id": project_id,
        "research_budget_hours": args.research_budget_hours,
        "next_file": str(root / "state/RESUME.md"),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
