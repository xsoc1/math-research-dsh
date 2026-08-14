#!/usr/bin/env python3
"""Smoke test for the prune-aware dsh_run wrapper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "dsh_run.py"
GATE = ROOT / "skills" / "math-research-workflow" / "scripts" / "validate_pipeline.py"
BAD = ROOT / "tests" / "fixtures" / "pipeline-bad"


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(WRAPPER), str(GATE), "--project", str(BAD)],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        print("bad fixture unexpectedly passed through the wrapper")
        return 1
    lines = proc.stdout.splitlines()
    if not lines or not lines[0].startswith("VERDICT: exit="):
        print("wrapper did not print the verdict first")
        print(proc.stdout)
        return 1
    if not lines[-1].startswith("VERDICT: exit="):
        print("wrapper did not repeat the verdict last")
        print(proc.stdout)
        return 1
    log_path = Path(lines[0].split("| log: ", 1)[1])
    if not log_path.is_file():
        print("wrapper log missing:", log_path)
        return 1
    if len(log_path.read_text(encoding="utf-8")) == 0:
        print("wrapper log is empty")
        return 1

    # a passing run must exit 0 through the wrapper as well
    good = ROOT / "tests" / "fixtures" / "pipeline-good"
    ok = subprocess.run(
        [sys.executable, str(WRAPPER), str(GATE), "--project", str(good)],
        capture_output=True,
        text=True,
    )
    if ok.returncode != 0:
        print("good fixture unexpectedly failed through the wrapper")
        print(ok.stdout)
        return 1

    print("dsh_run smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
