#!/usr/bin/env python3
"""Estimate per-request context injection cost for a DSH session.

DSH injects on every request: the workspace instruction chain (AGENTS.md
files, each source capped at 65536 bytes), the session skill catalog (skill
descriptions), and whatever the model loads (skill bodies). This tool
estimates those costs and flags the reducible ones: oversized instruction
files, heavy skill bodies, exact-duplicate paragraphs across files, and
skill-name shadowing.

Token estimate is a documented heuristic (CJK chars * 0.6 + other chars *
0.25): use it for ranking and budgets, not for accounting.

Usage:
    python scripts/context-audit.py [--root DIR] [--skills-root DIR] [--json]

--root          workspace root for the AGENTS.md chain walk (default: cwd)
--skills-root   skill root to scan (default: $DSH_HOME/skills)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

INJECTION_CAP = 65536
DUPE_MIN_LEN = 40
TOP_N = 15


def est_tokens(text: str) -> int:
    cjk = 0
    other = 0
    for ch in text:
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0xF900 <= code <= 0xFAFF
            or 0x3000 <= code <= 0x303F
            or 0xFF00 <= code <= 0xFFEF
        ):
            cjk += 1
        else:
            other += 1
    return int(cjk * 0.6 + other * 0.25)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def instruction_chain(root: Path) -> list[dict]:
    entries = []
    seen = set()
    node = root.resolve()
    while True:
        for name in ("AGENTS.md",):
            p = node / name
            if p.is_file() and str(p) not in seen:
                seen.add(str(p))
                text = read(p)
                entries.append(
                    {
                        "path": str(p),
                        "bytes": p.stat().st_size,
                        "tokens": est_tokens(text),
                        "truncated": p.stat().st_size > INJECTION_CAP,
                        "text": text,
                    }
                )
        if node.parent == node:
            break
        node = node.parent
    return entries


def skill_entries(skills_root: Path) -> list[dict]:
    entries = []
    if not skills_root.is_dir():
        return entries
    for bundle in sorted(skills_root.iterdir()):
        skill_md = bundle / "SKILL.md"
        if not bundle.is_dir() or not skill_md.is_file():
            continue
        text = read(skill_md)
        name = bundle.name
        for line in text.splitlines()[1:]:
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
                break
        body_bytes = skill_md.stat().st_size
        bundle_bytes = sum(p.stat().st_size for p in bundle.rglob("*") if p.is_file())
        entries.append(
            {
                "dir": bundle.name,
                "name": name,
                "body_bytes": body_bytes,
                "body_tokens": est_tokens(text),
                "bundle_bytes": bundle_bytes,
                "text": text,
            }
        )
    # shadowing: same frontmatter name from different directories
    names: dict[str, list[str]] = {}
    for e in entries:
        names.setdefault(e["name"], []).append(e["dir"])
    for e in entries:
        e["shadowed"] = len(names[e["name"]]) > 1
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--skills-root", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dsh_home = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")
    skills_root = Path(args.skills_root).resolve() if args.skills_root else dsh_home / "skills"

    chain = instruction_chain(root)
    skills = skill_entries(skills_root)

    # exact-duplicate paragraphs across instruction files and skill bodies
    line_count: Counter[str] = Counter()
    for e in chain:
        for line in e["text"].splitlines():
            if len(line) >= DUPE_MIN_LEN:
                line_count[line] += 1
    for e in skills:
        for line in e["text"].splitlines():
            if len(line) >= DUPE_MIN_LEN:
                line_count[line] += 1
    dupes = [
        {"line": line[:120], "count": count}
        for line, count in line_count.most_common(TOP_N)
        if count > 1
    ]

    chain_tokens = sum(e["tokens"] for e in chain)
    truncated = [e["path"] for e in chain if e["truncated"]]
    catalog_tokens = est_tokens(" ".join(e["name"] + ": " for e in skills))
    body_tokens = sum(e["body_tokens"] for e in skills)
    shadowed = [e["name"] for e in skills if e["shadowed"]]

    if args.json:
        payload = {
            "root": str(root),
            "skills_root": str(skills_root),
            "chain": [
                {
                    "path": e["path"],
                    "bytes": e["bytes"],
                    "tokens": e["tokens"],
                    "truncated": e["truncated"],
                }
                for e in chain
            ],
            "chain_tokens": chain_tokens,
            "truncated_files": truncated,
            "skills": [
                {
                    "name": e["name"],
                    "dir": e["dir"],
                    "body_bytes": e["body_bytes"],
                    "body_tokens": e["body_tokens"],
                    "bundle_bytes": e["bundle_bytes"],
                    "shadowed": e["shadowed"],
                }
                for e in skills
            ],
            "catalog_tokens": catalog_tokens,
            "body_tokens": body_tokens,
            "shadowed_names": shadowed,
            "duplicates": dupes,
            "total_tokens": chain_tokens + catalog_tokens + body_tokens,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"workspace root: {root}")
    print(f"skills root: {skills_root}")
    print()
    print("== instruction chain (injected every request) ==")
    for e in sorted(chain, key=lambda x: -x["tokens"]):
        flag = " [TRUNCATED at 64KB]" if e["truncated"] else ""
        print(f"  {e['tokens']:>6} tok  {e['bytes']:>8} B  {e['path']}{flag}")
    if truncated:
        print(f"  note: {len(truncated)} file(s) exceed the 64KB injection cap; the tail is lost")
    print()
    print("== skill catalog + bodies ==")
    for e in sorted(skills, key=lambda x: -x["body_tokens"]):
        shadow = " [NAME SHADOWED]" if e["shadowed"] else ""
        print(
            f"  {e['body_tokens']:>6} tok  body {e['body_bytes']:>8} B  "
            f"{e['name']} ({e['dir']}){shadow}"
        )
    print(f"  catalog descriptions: ~{catalog_tokens} tok")
    if shadowed:
        print(f"  shadowing: {', '.join(shadowed)} appears from multiple directories")
    print()
    if dupes:
        print("== duplicate paragraphs across files ==")
        for d in dupes:
            print(f"  x{d['count']}: {d['line']}")
    else:
        print("== duplicates: none ==")
    total = chain_tokens + catalog_tokens + body_tokens
    print()
    print(f"AUDIT: {len(chain)} instruction file(s), {len(skills)} skill(s), ~{total} tokens estimated injection")
    return 0


if __name__ == "__main__":
    sys.exit(main())
