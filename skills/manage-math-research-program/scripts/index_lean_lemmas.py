#!/usr/bin/env python3
"""Generate a searchable Lean lemma index for reuse.

Scans `.lean` files under a directory (default `lean-proof/SL`) and writes
`lean-proof/LEMMA_INDEX.md` with one row per declaration. Status is:
  - `SCAFFOLD` if the file contains `sorry` / `admit` / `axiom`;
  - `VERIFIED` otherwise (no leaked placeholders in the file).

Use this index before proving a new lemma: if the declaration already exists,
reuse/import it instead of re-proving.

Usage:
  py -3 scripts/index_lean_lemmas.py --lean-proof lean-proof [--output lean-proof/LEMMA_INDEX.md]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

DECL_RE = re.compile(r"^\s*(?:protected\s+|private\s+)?(theorem|lemma|def|structure|class)\s+([A-Za-z0-9_']+)", re.MULTILINE)
UNFINISHED_RE = re.compile(r"\b(sorry|admit|axiom)\b")


def status_for(text: str) -> str:
    return "SCAFFOLD" if UNFINISHED_RE.search(text) else "VERIFIED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lean-proof", default="lean-proof", help="path to the lean-proof directory")
    parser.add_argument("--output", default=None, help="output index path (default: <lean-proof>/LEMMA_INDEX.md)")
    args = parser.parse_args()

    root = pathlib.Path(args.lean_proof)
    sl_dir = root / "SL"
    if not sl_dir.is_dir():
        print(f"FAIL: {sl_dir} does not exist")
        return 1
    output = pathlib.Path(args.output) if args.output else root / "LEMMA_INDEX.md"

    rows: list[tuple[str, str, str]] = []
    for lean_file in sorted(sl_dir.glob("*.lean")):
        text = lean_file.read_text(encoding="utf-8", errors="replace")
        status = status_for(text)
        for match in DECL_RE.finditer(text):
            rows.append((lean_file.name, match.group(2), status))

    lines = [
        "# Lean lemma index (auto-generated)",
        "",
        "Reuse before re-proving: search this table for an existing declaration.",
        "",
        "| File | Declaration | Status |",
        "| --- | --- | --- |",
    ]
    for file, decl, status in rows:
        lines.append(f"| `{file}` | `{decl}` | `{status}` |")
    if not rows:
        lines.append("| _no declarations found_ | | |")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"OK: wrote {output} ({len(rows)} declarations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
