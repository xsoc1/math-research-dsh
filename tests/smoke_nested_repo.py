#!/usr/bin/env python3
"""Smoke test: the pipeline gate must ignore nested git repositories.

A project may contain a cloned plugin repo (e.g. `_xsoc1_work/`) whose test
fixtures intentionally contain failing handoffs/whiteboards. The gate must not
validate those as part of the parent project.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "math-research-workflow" / "scripts" / "validate_pipeline.py"


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td)
        ok_packet = proj / "agenda" / "task-packets" / "Q-ok.md"
        write(
            ok_packet,
            "# Task packet Q-20260816-demo-ABCD1234\n"
            "- **Task ID:** Q-20260816-demo-ABCD1234\n"
            "- **Project ID:** P\n"
            "- **Task state:** IN_PROGRESS\n"
            "- **Task type:** solve\n\n"
            "## Novelty preflight (B0)\n"
            "- **Openness verdict:** OPEN (checked 2026-08-16)\n"
            "- **Novelty audit path:** demo/audit.md\n"
            "- **Snapshot hash:** N/A\n"
            "## Upstream invocation\nUse $rigorous-open-math-research.\n"
            "## Source bundle\n- item\n"
            "## Required run location\nruns/x/\n",
        )
        # A nested git repo (fake .git dir) with an intentionally broken handoff.
        nested = proj / "_nested_repo"
        (nested / ".git").mkdir(parents=True)
        bad_handoff = (
            nested / "tests" / "fixtures" / "handoff-interrupted-20260813T000000Z.md"
        )
        write(bad_handoff, "# Interruption handoff record\n(no fields)\n")

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--project", str(proj)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print("FAIL: gate failed on a project containing a nested repo")
            print(proc.stdout)
            print(proc.stderr)
            return 1
        if "handoff_interrupted" in proc.stdout and "missing required" in proc.stdout:
            print("FAIL: nested repo handoff was validated (should be skipped)")
            print(proc.stdout)
            return 1

    print("nested-repo skip smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
