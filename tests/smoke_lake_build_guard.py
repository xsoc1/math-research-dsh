#!/usr/bin/env python3
"""Smoke test for lake_build_guard.py.

Verifies that the guard:
  1. allows a first build check;
  2. refuses when a fresh lock exists;
  3. releases the lock;
  4. refuses when too many recent build attempts are logged;
  5. allows again after clearing state.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "lean-verify" / "scripts" / "lake_build_guard.py"


def run(project: pathlib.Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(project), f"--{mode}"],
        capture_output=True,
        text=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td)
        (proj / ".lake").mkdir()

        # 1. First check should pass and create a lock.
        r = run(proj, "check")
        if r.returncode != 0:
            print("FAIL: first check should pass")
            print(r.stdout, r.stderr)
            return 1

        # 2. Immediate second check should fail on the fresh lock.
        r = run(proj, "check")
        if r.returncode == 0:
            print("FAIL: second check should be refused by fresh lock")
            return 1
        if "build guard lock" not in r.stdout:
            print("FAIL: fresh-lock refusal message not found")
            print(r.stdout)
            return 1

        # 3. Release lock.
        r = run(proj, "release")
        if r.returncode != 0:
            print("FAIL: release should pass")
            print(r.stdout, r.stderr)
            return 1

        # 4. Too many recent attempts -> refuse.
        log = proj / ".lake" / "build_attempts.log"
        now = time.time()
        lines = []
        for i in range(6):
            ts = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now - i * 10))
            lines.append(ts)
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = run(proj, "check")
        if r.returncode == 0:
            print("FAIL: too many recent attempts should be refused")
            return 1
        if "build attempts" not in r.stdout:
            print("FAIL: attempts-refusal message not found")
            print(r.stdout)
            return 1

        # 5. Clean state -> pass again.
        log.unlink()
        r = run(proj, "check")
        if r.returncode != 0:
            print("FAIL: clean state should pass")
            print(r.stdout, r.stderr)
            return 1

    print("lake build guard smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
