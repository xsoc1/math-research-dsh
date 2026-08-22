#!/usr/bin/env python3
"""Manage class-scoped lifecycle of mathematical tool entries.

Tool entries are Markdown files with a YAML frontmatter block. Each entry may
carry an `applicability` list:

    applicability:
      - class: spectral-gap-ratio
        status: active | conditional | retired
        last_verified: 2026-08-23
        failure_records:
          - mechanism: <exact failure mechanism>
            evidence_run: <run id>

A class-specific retirement does NOT remove the tool from other classes. A tool
whose every known class is retired is reported as `archived` and retained for
explicit retrieval.

Usage:
    python manage_tool_lifecycle.py list --root tools [--class CLASS] [--include-archived]
    python manage_tool_lifecycle.py status --root tools --slug NAME
    python manage_tool_lifecycle.py set-class --root tools --slug NAME \
        --class CLASS --status active|conditional|retired \
        [--mechanism "..."] [--run RUN] [--note "..."]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

VALID_STATUSES = {"active", "conditional", "retired"}


def read_tool(path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML is required for manage_tool_lifecycle.py")
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return None, None
    front = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    return front, body


def write_tool(path: Path, front: dict, body: str):
    fm_text = yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


def tool_slug(path: Path, front: dict) -> str:
    return str(front.get("slug") or front.get("tool_id") or path.stem)


def derived_status(front: dict) -> str:
    rows = front.get("applicability") or []
    statuses = {str(r.get("status", "")) for r in rows if isinstance(r, dict)}
    if "active" in statuses:
        return "active"
    if "conditional" in statuses:
        return "conditional"
    if "retired" in statuses:
        return "archived"
    return "unclassified"


def update_applicability(front: dict, cls: str, status: str, mechanism=None,
                         run=None, note=None):
    rows = front.setdefault("applicability", [])
    if not isinstance(rows, list):
        raise ValueError("applicability must be a list")
    target = None
    for r in rows:
        if isinstance(r, dict) and str(r.get("class")) == cls:
            target = r
            break
    if target is None:
        target = {"class": cls, "status": status,
                  "last_verified": _dt.date.today().isoformat()}
        rows.append(target)
    else:
        target["status"] = status
        target["last_verified"] = _dt.date.today().isoformat()

    if note:
        target["note"] = note
    if mechanism or run:
        records = target.setdefault("failure_records", [])
        if not isinstance(records, list):
            records = []
            target["failure_records"] = records
        records.append({
            "mechanism": mechanism or "",
            "evidence_run": run or "",
            "date": _dt.date.today().isoformat(),
            "note": note or "",
        })
    front["updated_at"] = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_tools(root: Path):
    if not root.exists():
        return []
    out = []
    for p in sorted(root.rglob("*.md")):
        front, body = read_tool(p)
        if front is None or "slug" not in front and "tool_id" not in front and "title" not in front:
            continue
        out.append((p, front, body))
    return out


def cmd_list(args):
    rows = collect_tools(Path(args.root))
    table = []
    for p, front, _ in rows:
        slug = tool_slug(p, front)
        st = derived_status(front)
        classes = [r.get("class") for r in (front.get("applicability") or [])
                   if isinstance(r, dict)]
        if args.class_name and args.class_name not in classes:
            continue
        if not args.include_archived and st == "archived":
            continue
        table.append((slug, st, ", ".join(str(c) for c in classes if c)))
    if not table:
        print("(no matching tools)")
        return
    print(f"{'slug':<40} {'status':<14} classes")
    for slug, st, classes in table:
        print(f"{slug:<40} {st:<14} {classes}")


def cmd_status(args):
    for p, front, _ in collect_tools(Path(args.root)):
        if tool_slug(p, front) == args.slug:
            print(f"slug: {args.slug}")
            print(f"derived status: {derived_status(front)}")
            print("applicability:")
            for r in front.get("applicability") or []:
                if isinstance(r, dict):
                    print(f"  - class={r.get('class')} status={r.get('status')} "
                          f"last_verified={r.get('last_verified')}")
                    for fr in r.get("failure_records") or []:
                        print(f"      failure: {fr.get('mechanism')} "
                              f"[{fr.get('evidence_run')}]")
            return
    print(f"tool not found: {args.slug}", file=sys.stderr)
    return 1


def cmd_set_class(args):
    for p, front, body in collect_tools(Path(args.root)):
        if tool_slug(p, front) == args.slug:
            update_applicability(front, args.class_name, args.status,
                                 mechanism=args.mechanism, run=args.run,
                                 note=args.note)
            write_tool(p, front, body)
            print(f"updated {p}: {args.slug} / {args.class_name} -> {args.status}")
            return
    print(f"tool not found: {args.slug}", file=sys.stderr)
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--root", required=True)
    p_list.add_argument("--class", dest="class_name")
    p_list.add_argument("--include-archived", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status")
    p_status.add_argument("--root", required=True)
    p_status.add_argument("--slug", required=True)
    p_status.set_defaults(func=cmd_status)

    p_set = sub.add_parser("set-class")
    p_set.add_argument("--root", required=True)
    p_set.add_argument("--slug", required=True)
    p_set.add_argument("--class", dest="class_name", required=True)
    p_set.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    p_set.add_argument("--mechanism")
    p_set.add_argument("--run")
    p_set.add_argument("--note")
    p_set.set_defaults(func=cmd_set_class)

    args = ap.parse_args()
    rc = args.func(args)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
