#!/usr/bin/env python3
"""Maintain the human-readable research map for a project.

The research map is a living, survey-style document (`research_map.md`) that
collects every route/method tried, intermediate results, unexpected findings,
failures and their reasons, tools, open directions, an avoid list, and human /
other-agent contributions. It is updated continuously at stage boundaries.

Usage:
  py -3 scripts/update_research_map.py --project <root>
  py -3 scripts/update_research_map.py --project <root> --route "key|who|status|evidence"
  py -3 scripts/update_research_map.py --project <root> --finding "new observation"
  py -3 scripts/update_research_map.py --project <root> --failure "tried X, failed because ..."
  py -3 scripts/update_research_map.py --project <root> --avoid "route Y is a dead end"
  py -3 scripts/update_research_map.py --project <root> --human "human-supplied route Z to verify"
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import sys

TEMPLATE_NAME = "research-map.template.md"


def default_template(root: pathlib.Path, slug: str) -> str:
    template = pathlib.Path(__file__).resolve().parents[1] / "assets" / TEMPLATE_NAME
    if template.is_file():
        text = template.read_text(encoding="utf-8")
        return text.replace("<problem slug>", slug)
    return f"# Research map: {slug}\n\n(Template missing; maintain sections below.)\n"


def section_lines(text: str, heading: str) -> list[str]:
    marker = f"## {heading}"
    parts = text.split(marker, 1)
    if len(parts) < 2:
        return []
    body = parts[1].split("\n## ", 1)[0]
    return [ln for ln in body.splitlines() if ln.strip()]


def insert_after_section(text: str, heading: str, lines: list[str]) -> str:
    if not lines:
        return text
    # Match a section whose displayed name ends with the given heading
    # (e.g. "## 2. Routes and methods tried" matches "Routes and methods tried").
    marker = None
    for line in text.splitlines():
        if line.startswith("## ") and line[3:].strip().endswith(heading):
            marker = line
            break
    if marker is None:
        text = text.rstrip() + f"\n\n## {heading}\n\n" + "\n".join(lines) + "\n"
        return text
    head, tail = text.split(marker, 1)
    # tail starts with newline + content up to the next heading.
    if "\n## " in tail:
        body, rest = tail.split("\n## ", 1)
        new_tail = "\n" + "\n".join(lines) + body + "\n## " + rest
    else:
        new_tail = "\n" + "\n".join(lines) + tail
    return head + marker + new_tail


def apply_updates(args: argparse.Namespace, text: str) -> str:
    if args.route:
        # format: key|who|status|evidence
        text = insert_after_section(text, "Routes and methods tried", [f"| {args.route} |"])
    if args.finding:
        text = insert_after_section(text, "Intermediate results and unexpected findings", [f"- {args.finding}"])
    if args.failure:
        text = insert_after_section(text, "Failed attempts and failure reasons", [f"- {args.failure}"])
    if args.avoid:
        text = insert_after_section(text, "Avoid list (dead ends)", [f"- {args.avoid}"])
    if args.human:
        text = insert_after_section(text, "Human / other-agent contributions", [f"- {args.human}"])
    return text


def stamp(text: str, now: str) -> str:
    if text.startswith("# Research map:"):
        # insert/refresh the Last updated line right after the H1.
        head, sep, tail = text.partition("\n")
        lines = [head, f"\nLast updated: {now}\n"]
        for ln in tail.split("\n"):
            if ln.startswith("Last updated:"):
                continue
            lines.append(ln)
        return "\n".join(lines)
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="project root directory")
    parser.add_argument("--map", default=None, help="research map path (default: <project>/research_map.md)")
    parser.add_argument("--route", default=None, help="append route row: key|who|status|evidence")
    parser.add_argument("--finding", default=None, help="append an intermediate finding")
    parser.add_argument("--failure", default=None, help="append a failed attempt + reason")
    parser.add_argument("--avoid", default=None, help="append an avoid / dead-end note")
    parser.add_argument("--human", default=None, help="append a human/other-agent contribution")
    args = parser.parse_args()

    project = pathlib.Path(args.project).resolve()
    map_path = pathlib.Path(args.map) if args.map else project / "research_map.md"
    slug = project.name

    if map_path.is_file():
        text = map_path.read_text(encoding="utf-8")
    else:
        text = default_template(project, slug)

    text = apply_updates(args, text)
    text = stamp(text, datetime.datetime.utcnow().isoformat() + "Z")

    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"OK: research map updated at {map_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
