#!/usr/bin/env python3
"""Smoke test for dsh-doctor.py via simulated environments."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "scripts" / "dsh-doctor.py"

ALL_BUNDLES = {
    "rigorous-open-math-research": True,
    "manage-math-research-program": True,
    "math-research-workflow": True,
    "lean-verify": True,
}


def run(list_file: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DOCTOR), "--list-file", str(list_file), *extra],
        capture_output=True,
        text=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        healthy = tmp / "healthy.json"
        healthy.write_text(
            json.dumps(
                {
                    "dsh_home": str(tmp / "dsh"),
                    "repo_present": True,
                    "bundles": ALL_BUNDLES,
                    "python_cmds": {"python": True},
                    "lean": True,
                }
            ),
            encoding="utf-8",
        )
        proc = run(healthy, "--json")
        if proc.returncode != 0:
            print("healthy environment unexpectedly failed")
            print(proc.stdout)
            return 1
        payload = json.loads(proc.stdout[proc.stdout.index("{") :])
        if payload["problems"] != 0:
            print("healthy environment reported problems")
            print(payload)
            return 1

        broken = tmp / "broken.json"
        broken.write_text(
            json.dumps(
                {
                    "dsh_home": str(tmp / "dsh"),
                    "repo_present": False,
                    "bundles": {
                        "rigorous-open-math-research": False,
                        "manage-math-research-program": True,
                        "math-research-workflow": False,
                        "lean-verify": True,
                    },
                    "python_cmds": {"python": False, "py -3": False},
                    "lean": False,
                }
            ),
            encoding="utf-8",
        )
        proc = run(broken)
        if proc.returncode == 0:
            print("broken environment unexpectedly passed")
            print(proc.stdout)
            return 1
        for needle in (
            "'rigorous-open-math-research' not mounted",
            "'math-research-workflow' not mounted",
            "no usable python interpreter",
        ):
            if needle not in proc.stdout:
                print(f"broken environment did not report: {needle}")
                print(proc.stdout)
                return 1

        proc = run(broken, "--require-lean")
        if proc.returncode == 0:
            print("--require-lean unexpectedly passed without lake")
            return 1
        if "lean toolchain (lake) not found" not in proc.stdout:
            print("--require-lean failure message missing")
            print(proc.stdout)
            return 1

    print("dsh-doctor smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
