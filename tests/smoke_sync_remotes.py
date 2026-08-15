#!/usr/bin/env python3
"""Smoke test for the manage-skill multi-remote sync helper.

Uses local bare repositories only; no network access is required.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills" / "manage-math-research-program"
    / "scripts"
    / "sync_remotes.py"
)


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, errors="replace"
    )


def commit_all(repo: Path, message: str) -> None:
    run(repo, "add", "-A")
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=smoke",
            "-c",
            "user.email=smoke@example.com",
            "commit",
            "-m",
            message,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"commit failed: {proc.stderr}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bare_a = tmp / "bare-a.git"
        bare_b = tmp / "bare-b.git"
        for bare in (bare_a, bare_b):
            subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
            # bare repos need a default branch for push to be deterministic
            subprocess.run(
                ["git", "--git-dir", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"],
                capture_output=True,
                check=True,
            )

        work = tmp / "work"
        subprocess.run(["git", "init", "-b", "main", str(work)], capture_output=True, check=True)
        run(work, "remote", "add", "origin", str(bare_a))
        run(work, "remote", "add", "fork", str(bare_b))
        (work / "baseline.txt").write_text("baseline", encoding="utf-8")
        (work / "project.json").write_text(
            json.dumps({"git_sync": {"push_order": ["origin", "fork"]}}), encoding="utf-8"
        )
        commit_all(work, "initial")

        ok = subprocess.run(
            [sys.executable, str(SCRIPT), "--project", str(work)],
            capture_output=True,
            text=True,
        )
        if ok.returncode != 0:
            print(ok.stdout)
            print(ok.stderr)
            return 1
        expected = run(work, "rev-parse", "HEAD").stdout.strip()
        for bare in (bare_a, bare_b):
            head = subprocess.run(
                ["git", "--git-dir", str(bare), "rev-parse", "main"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            if head != expected:
                print(f"remote {bare} HEAD {head} != work HEAD {expected}")
                return 1

        # dirty tree must fail without --allow-dirty
        (work / "dirty.txt").write_text("dirty", encoding="utf-8")
        dirty = subprocess.run(
            [sys.executable, str(SCRIPT), "--project", str(work)],
            capture_output=True,
            text=True,
        )
        if dirty.returncode == 0:
            print("dirty tree unexpectedly passed the sync")
            print(dirty.stdout)
            return 1
        if "working tree is dirty" not in dirty.stdout:
            print("dirty-tree failure message missing")
            print(dirty.stdout)
            return 1

    print("sync_remotes smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
