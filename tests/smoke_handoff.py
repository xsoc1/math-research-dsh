#!/usr/bin/env python3
"""Smoke test for interruption handoff validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "math-research-workflow" / "scripts" / "validate_pipeline.py"
GOOD = ROOT / "tests" / "fixtures" / "pipeline-handoff-good"
BAD = ROOT / "tests" / "fixtures" / "pipeline-handoff-bad"


def run(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(target)],
        capture_output=True,
        text=True,
    )


def main() -> int:
    good = run(GOOD)
    if good.returncode != 0:
        print("good handoff fixture unexpectedly failed the gate")
        print(good.stdout)
        print(good.stderr)
        return 1
    if "interruption handoff" not in good.stdout:
        print("good fixture did not run the handoff check")
        print(good.stdout)
        return 1

    bad = run(BAD)
    if bad.returncode == 0:
        print("bad handoff fixture unexpectedly passed the gate")
        return 1
    for needle in ("Attempted routes", "Next actions"):
        if needle not in bad.stdout:
            print(f"bad fixture did not report the missing {needle!r} section")
            print(bad.stdout)
            return 1

    print("interruption handoff smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
