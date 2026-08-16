#!/usr/bin/env python3
"""Generate a Lean scaffold and its registration records.

This script automates the "scaffold every new result" rule (manage workflow 8d)
and the "proof submission audit" record (workflow 8e). It creates:

  1. `lean-proof/SL/<slug>.lean` - a Lean scaffold with a `-- SCAFFOLD` header.
  2. An entry in `lean-proof/STATUS.md` under `## Scaffold register`.
  3. A `formalization_progress.md` section in the run directory (or lean-proof).
  4. A prefilled `proof-submission-audit.md` in the run directory.

Usage:
  py -3 scripts/scaffold_result.py \
      --slug DensBC_O1_core \
      --status RIGOROUS_PARTIAL_RESULT \
      --source runs/.../candidate_proof.md \
      --obligations "O1'; O2" \
      --lean-proof lean-proof \
      --run-dir runs/rigorous-open-math-research/R-...
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

DEFAULT_TEMPLATE = """/-
SCAFFOLD: {slug} {status} {obligations}
This file is a formalization scaffold. It is NOT a verified artifact.
Open obligations: {obligations}
-/
import Mathlib

/-!
# {slug}

Source: {source}
Status: {status}
Open obligations: {obligations}
-/

namespace {namespace}

/-- Placeholder for the main statement of {slug}. Replace the statement and remove `sorry` when proved. -/
theorem {name}_main : True := by
  sorry

/-- Placeholder for the first open obligation. -/
lemma {name}_obligation_1 : True := by
  sorry

end {namespace}
"""


def slug_namespace(slug: str) -> str:
    parts = re.split(r"[^A-Za-z0-9_]+", slug)
    return "".join(part.capitalize() for part in parts if part) or "Scaffold"


def slug_name(slug: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", slug)


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def update_status(status_path: pathlib.Path, slug: str, status: str, source: str, obligations: str) -> None:
    if status_path.is_file():
        text = status_path.read_text(encoding="utf-8")
    else:
        text = "# lean-proof 形式化状态总表\n"
    marker = "## Scaffold register"
    line = f"- `SL/{slug}.lean` | {status} | {source} | open: {obligations}"
    if marker in text:
        # Insert after the marker line (keep existing entries below).
        head, tail = text.split(marker, 1)
        # tail starts with newline and existing content; insert before the next heading if any.
        if tail.lstrip("\n").startswith("## "):
            new_tail = "\n" + line + "\n" + tail
        else:
            new_tail = "\n" + line + tail
        text = head + marker + new_tail
    else:
        text = text.rstrip() + f"\n\n{marker}\n\n{line}\n"
    write_text(status_path, text)


def update_progress(progress_path: pathlib.Path, slug: str, status: str, source: str, lean_file: pathlib.Path) -> None:
    entry = (
        f"\n## {slug}\n\n"
        f"- Status: `{status}`\n"
        f"- Source: `{source}`\n"
        f"- Lean scaffold: `{lean_file}`\n"
        f"- Registered: `{datetime.datetime.utcnow().isoformat()}Z`\n"
    )
    if progress_path.is_file():
        text = progress_path.read_text(encoding="utf-8")
        if f"## {slug}" in text:
            print(f"note: {progress_path} already contains a section for {slug}; not duplicated")
            return
        text = text.rstrip() + "\n" + entry
    else:
        text = "# Formalization progress\n" + entry
    write_text(progress_path, text)


def create_audit(audit_path: pathlib.Path, slug: str, status: str, source: str, lean_file: pathlib.Path) -> None:
    if audit_path.exists():
        print(f"note: {audit_path} already exists; not overwritten")
        return
    text = f"""# Proof submission audit record

- **Submission ID:** `SUB-{slug}`
- **Date:** `{datetime.datetime.utcnow().isoformat()}Z`
- **Proof type:** `scaffold`
- **Target problem / result slug:** `{slug}`

## 1. Repository comparison

- Existing records checked: (to be filled)
- Duplicate / superseded / contradictory findings: (to be filled)

## 2. Lean verification and audit

- Lean file: `{lean_file}`
- Status: `{status}`
- Machine checks: pending (scaffold; not a verified artifact)
- Independent audit: pending

## 3. Add by rules

- Files to add/update: (to be filled)
- Superseded records: (to be filled)
- Commit hash: (to be filled)

## Acceptance decision

- `REVISE_AND_RESUBMIT` (scaffold registered; full verification/audit pending)
"""
    write_text(audit_path, text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="result slug, e.g. DensBC_O1_core")
    parser.add_argument("--status", default="RIGOROUS_PARTIAL_RESULT", help="status label")
    parser.add_argument("--source", default="", help="source document/run path")
    parser.add_argument("--obligations", default="", help="open obligations, comma separated")
    parser.add_argument("--lean-proof", default="lean-proof", help="path to lean-proof directory")
    parser.add_argument("--run-dir", default=None, help="run directory for progress/audit records")
    args = parser.parse_args()

    slug = args.slug
    obligations = args.obligations or "TBD"
    lean_root = pathlib.Path(args.lean_proof)
    sl_dir = lean_root / "SL"
    lean_file = sl_dir / f"{slug}.lean"

    content = DEFAULT_TEMPLATE.format(
        slug=slug,
        status=args.status,
        source=args.source or "TBD",
        obligations=obligations,
        namespace=slug_namespace(slug),
        name=slug_name(slug),
    )
    write_text(lean_file, content)

    update_status(lean_root / "STATUS.md", slug, args.status, args.source or "TBD", obligations)

    if args.run_dir:
        run_dir = pathlib.Path(args.run_dir)
        update_progress(run_dir / "formalization_progress.md", slug, args.status, args.source or "TBD", lean_file)
        create_audit(run_dir / "proof-submission-audit.md", slug, args.status, args.source or "TBD", lean_file)
    else:
        update_progress(lean_root / "formalization_progress.md", slug, args.status, args.source or "TBD", lean_file)

    print(f"OK: scaffold created at {lean_file}")
    print(f"OK: STATUS updated at {lean_root / 'STATUS.md'}")
    print(f"OK: formalization progress updated")
    if args.run_dir:
        print(f"OK: audit record at {pathlib.Path(args.run_dir) / 'proof-submission-audit.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
