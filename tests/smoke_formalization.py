#!/usr/bin/env python3
"""Smoke test for the formalization-decision gate (silent lean-verify skip)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "math-research-workflow" / "scripts" / "validate_pipeline.py"
GOOD = ROOT / "tests" / "fixtures" / "pipeline-formalization-good"
MISSING = ROOT / "tests" / "fixtures" / "pipeline-formalization-missing"
REQUESTED = ROOT / "tests" / "fixtures" / "pipeline-formalization-requested"


def run(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(target)],
        capture_output=True,
        text=True,
    )


def main() -> int:
    good = run(GOOD)
    if good.returncode != 0:
        print("good formalization fixture unexpectedly failed the gate")
        print(good.stdout)
        print(good.stderr)
        return 1

    missing = run(MISSING)
    if missing.returncode == 0:
        print("fixture without a formalization decision unexpectedly passed")
        return 1
    if "without a formalization decision" not in missing.stdout:
        print("missing-decision fixture did not report the formalization check")
        print(missing.stdout)
        return 1

    requested = run(REQUESTED)
    if requested.returncode == 0:
        print("requested-but-unverified fixture unexpectedly passed")
        return 1
    if "formalization requested" not in requested.stdout:
        print("requested fixture did not report the missing verification evidence")
        print(requested.stdout)
        return 1

    print("formalization gate smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
