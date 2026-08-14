#!/usr/bin/env python3
"""Smoke test for the context-audit tool."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "context-audit.py"


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(AUDIT), "--root", str(ROOT), "--skills-root", str(ROOT / "skills")],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        return 1
    if "AUDIT:" not in proc.stdout:
        print("human report missing the AUDIT summary line")
        print(proc.stdout)
        return 1
    if "rigorous-open-math-research" not in proc.stdout:
        print("skill scan did not find the rigorous bundle")
        print(proc.stdout)
        return 1

    proc = subprocess.run(
        [
            sys.executable,
            str(AUDIT),
            "--root",
            str(ROOT),
            "--skills-root",
            str(ROOT / "skills"),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr)
        return 1
    payload = json.loads(proc.stdout)
    if "total_tokens" not in payload or not isinstance(payload.get("skills"), list):
        print("JSON payload missing expected keys")
        return 1
    names = [s["name"] for s in payload["skills"]]
    if "rigorous-open-math-research" not in names:
        print("JSON payload missing the rigorous skill")
        return 1

    print("context-audit smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
