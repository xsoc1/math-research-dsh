#!/usr/bin/env python3
"""Static smoke coverage for community methods distilled into the skills.

This does not verify agent behavior; it guards against accidental deletion or
renaming of the distilled method contracts while keeping the test cheap and
deterministic (stdlib only, no network, no subagents).

Run from the tests/ directory or the repository root:
    py -3 tests/smoke_distilled_methods.py
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

CHECKS = [
    (
        "rigorous/search-status",
        "skills/rigorous-open-math-research/references/phase-23-search.md",
        ["coverage_gaps", "fetch_required", "uncertainty", "warnings", "fetch status"],
    ),
    (
        "rigorous/audit-scope",
        "skills/rigorous-open-math-research/references/phase-78-synthesis-audit.md",
        ["covered_scope", "residual_risk"],
    ),
    (
        "rigorous/route-discipline",
        "skills/rigorous-open-math-research/references/phase-45-routes-loop.md",
        ["forward-only", "evidence tri-state"],
    ),
    (
        "rigorous/forbidden-moves",
        "skills/rigorous-open-math-research/references/phase-01-contract.md",
        ["Forbidden moves", "fetch_required"],
    ),
    (
        "workflow/team-discipline",
        "skills/math-research-workflow/references/workflow-design.md",
        ["claim", "gaps", "loop"],
    ),
    (
        "lean/gate-discipline",
        "skills/lean-verify/SKILL.md",
        ["gate", "counterexample", "convergence"],
    ),
    (
        "manage/evidence-boundary",
        "skills/manage-math-research-program/SKILL.md",
        ["evidence", "traceable", "uncontrolled"],
    ),
]


def main() -> int:
    failures: list[str] = []
    for label, rel, needles in CHECKS:
        path = REPO / rel
        if not path.is_file():
            failures.append(f"{label}: missing {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            failures.append(f"{label}: missing markers {missing} in {rel}")
        else:
            print(f"ok: {label} markers present in {rel}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("All distilled-method markers present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
