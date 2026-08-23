#!/usr/bin/env python3
"""Generate a performance alert from a run metrics file and a baseline.

Usage:
    python performance_alert.py \
        --metrics runs/.../metrics.json \
        --baseline runs/.../baseline.json \
        --output runs/.../performance_alert.md \
        [--fail-on-alert]

A baseline is a previous `metrics.json` from a comparable run (same problem
class or similar difficulty). The alert is advisory; by default it does not
change the exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

COST_METRICS = (
    "steps",
    "tool_calls",
    "uncached_input_tokens",
    "cache_read_tokens",
    "wall_ms",
)

BENEFIT_METRICS = (
    "output_tokens",
    "artifact_count",
    "reused_item_count",
)

WARN_THRESHOLD = 0.5
ALERT_THRESHOLD = 0.8


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pct(a, b):
    if b in (None, 0):
        return None
    return (float(a) - float(b)) / float(b)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--fail-on-alert", action="store_true")
    args = ap.parse_args()

    run = load_json(Path(args.metrics))
    base = load_json(Path(args.baseline))

    rows = []
    alerts = []
    doc_alert = False
    duplicate_alert = False
    for key in COST_METRICS:
        a = run.get(key, 0)
        b = base.get(key, 0)
        d = pct(a, b)
        if key in ("steps", "tool_calls", "uncached_input_tokens", "cache_read_tokens", "wall_ms"):
            rows.append((key, a, b, d))
            if d is not None and d >= WARN_THRESHOLD:
                alerts.append((key, d))

    # Benefit: artifact_count drop is a documentation regression.
    a_art = run.get("artifact_count", 0)
    b_art = base.get("artifact_count", 0)
    d_art = pct(a_art, b_art) if b_art else None
    rows.append(("artifact_count", a_art, b_art, d_art))
    if d_art is not None and d_art <= -0.2:
        doc_alert = True

    # Duplicate work increase is a reuse regression when the field exists.
    a_dup = run.get("duplicate_work_count", 0)
    b_dup = base.get("duplicate_work_count", 0)
    d_dup = pct(a_dup, b_dup) if b_dup else None
    rows.append(("duplicate_work_count", a_dup, b_dup, d_dup))
    if d_dup is not None and d_dup >= 0.5:
        duplicate_alert = True

    level = "INFO"
    if alerts and (doc_alert or duplicate_alert):
        level = "ALERT"
    elif alerts:
        level = "WARN"

    lines = [
        "# Performance alert",
        "",
        f"- Run ID: {run.get('run_id', Path(args.metrics).parent.name)}",
        f"- Variant: {run.get('variant', 'unknown')}",
        f"- Problem class: {run.get('problem_class', 'unknown')}",
        f"- Baseline ID: {base.get('run_id', Path(args.baseline).parent.name)}",
        f"- Alert level: {level}",
        "",
        "## Changed metrics",
        "",
        "| Metric | Run | Baseline | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key, a, b, d in rows:
        dstr = "n/a" if d is None else f"{d:+.1%}"
        lines.append(f"| {key} | {a} | {b} | {dstr} |")

    lines += [
        "",
        "## Output/artifact assessment",
        "",
        "- Did mathematical output improve, stay similar, or degrade? (needs run-level judgement)",
        "- Did documentation/artifact completeness improve, stay similar, or degrade?",
        "- Is the change plausibly explained by problem difficulty or class?",
        "",
        "## Candidate interpretation",
        "",
        "The alert is a candidate, not a verdict. A single run may be misleading.",
        "Confirm before changing a protocol based on this alert.",
        "",
        "## Next checks",
        "",
        "- [ ] Repeat the same variant in the same problem class.",
        "- [ ] Repeat on a different problem class with a comparable baseline.",
        "- [ ] Inspect `reuse_summary.md` for duplicate work or avoided work.",
        "- [ ] Re-run after any intended protocol/config change.",
        "",
    ]
    text = "\n".join(lines) + "\n"
    Path(args.output).write_text(text, encoding="utf-8")

    print(f"performance_alert.py: level={level} output={args.output}")
    if args.fail_on_alert and level != "INFO":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
