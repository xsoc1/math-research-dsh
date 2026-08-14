#!/usr/bin/env python3
"""Smoke test for the deterministic pipeline gate validator (DSH layout)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "math-research-workflow" / "scripts" / "validate_pipeline.py"
GOOD = ROOT / "tests" / "fixtures" / "pipeline-good"
BAD = ROOT / "tests" / "fixtures" / "pipeline-bad"
NUMERICAL_ABUSE = ROOT / "tests" / "fixtures" / "pipeline-numerical-abuse"
GATE_NO_EVIDENCE = ROOT / "tests" / "fixtures" / "pipeline-gate-noevidence"


def run(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(target)],
        capture_output=True,
        text=True,
    )


def main() -> int:
    good = run(GOOD)
    if good.returncode != 0:
        print(good.stdout)
        print(good.stderr)
        return 1

    bad = run(BAD)
    if bad.returncode == 0:
        print("bad fixture unexpectedly passed the gate")
        return 1

    abuse = run(NUMERICAL_ABUSE)
    if abuse.returncode == 0:
        print("numerical-abuse fixture unexpectedly passed the gate")
        return 1
    if "numerical-evidence labels" not in abuse.stdout:
        print("numerical-abuse fixture did not trigger the numerical-evidence check")
        print(abuse.stdout)
        return 1

    no_evidence = run(GATE_NO_EVIDENCE)
    if no_evidence.returncode == 0:
        print("gate-no-evidence fixture unexpectedly passed the gate")
        return 1
    if "without candidate_proof.md or audit_report.md" not in no_evidence.stdout:
        print("gate-no-evidence fixture did not trigger the run-evidence check")
        print(no_evidence.stdout)
        return 1

    print("pipeline gate smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
