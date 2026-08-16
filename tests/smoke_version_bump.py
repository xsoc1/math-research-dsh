#!/usr/bin/env python3
"""Smoke test for scripts/check_version_bump.py.

Creates a throwaway git repo and verifies:
  1. a commit changing skills/ without package.json fails the gate;
  2. a commit changing skills/ together with package.json passes the gate.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "check_version_bump.py"


def run(cmd: list[str], cwd: pathlib.Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        run(["git", "init"], root)
        run(["git", "config", "user.email", "test@example.com"], root)
        run(["git", "config", "user.name", "Smoke Test"], root)

        (root / "package.json").write_text('{"version":"0.1.0"}\n', encoding="utf-8")
        skill = root / "skills" / "demo" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("initial\n", encoding="utf-8")
        run(["git", "add", "."], root)
        run(["git", "commit", "-m", "init"], root)

        # Content change without a package.json bump must fail.
        skill.write_text("changed without bump\n", encoding="utf-8")
        run(["git", "add", "."], root)
        run(["git", "commit", "-m", "content only"], root)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", "HEAD^", "--repo", str(root)],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            print("FAIL: version-bump gate accepted a skills-only change without package.json")
            return 1

        # Content change together with a package.json bump must pass.
        skill.write_text("changed with bump\n", encoding="utf-8")
        (root / "package.json").write_text('{"version":"0.1.1"}\n', encoding="utf-8")
        run(["git", "add", "."], root)
        run(["git", "commit", "-m", "content and bump"], root)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", "HEAD^", "--repo", str(root)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"FAIL: version-bump gate rejected a skills+package.json change:\n{proc.stdout}\n{proc.stderr}")
            return 1

    print("version-bump gate smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
