#!/usr/bin/env python3
"""Deterministic multi-remote sync for a research-program repository.

Reads the optional `git_sync.push_order` list from `project.json` (default:
["origin"]) and pushes the current branch to every listed remote in order.
The order matters when the project uses a parent + child-fork topology:
declare the parent first, then the fork(s), e.g.

    "git_sync": { "push_order": ["origin", "fork"] }

This script never commits and never overwrites uncommitted artifacts; a dirty
working tree is a hard failure unless `--allow-dirty` is given (it then only
warns).  Push failures keep the local commits intact and report the exact
remote that failed.

Usage:
  python sync_remotes.py --project ROOT [--dry-run] [--allow-dirty] [--json]

Exit code 0 when all pushes succeed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class Report:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self.checks = 0

    def ok(self, message: str) -> None:
        self.checks += 1
        self.entries.append({"status": "ok", "message": message})
        print(f"ok: {message}")

    def bad(self, message: str) -> None:
        self.checks += 1
        self.entries.append({"status": "FAIL", "message": message})
        print(f"FAIL: {message}")

    def warn(self, message: str) -> None:
        self.checks += 1
        self.entries.append({"status": "warn", "message": message})
        print(f"warn: {message}")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )


def load_project_config(root: Path, report: Report) -> dict[str, Any]:
    path = root / "project.json"
    if not path.is_file():
        report.warn(f"no project.json at {path}; using default push order ['origin']")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.warn(f"cannot parse project.json ({exc}); using default push order")
        return {}
    if not isinstance(data, dict):
        report.warn("project.json is not a JSON object; using default push order")
        return {}
    return data


def current_branch(root: Path, report: Report) -> str:
    proc = git(root, "branch", "--show-current")
    if proc.returncode != 0 or not proc.stdout.strip():
        report.bad(f"cannot determine current branch: {proc.stderr.strip()}")
        return ""
    return proc.stdout.strip()


def check_dirty(root: Path, report: Report, allow_dirty: bool) -> None:
    proc = git(root, "status", "--porcelain")
    if proc.returncode != 0:
        report.warn(f"cannot run git status: {proc.stderr.strip()}")
        return
    if proc.stdout.strip():
        if allow_dirty:
            report.warn("working tree is dirty (--allow-dirty); uncommitted artifacts stay local")
        else:
            report.bad(
                "working tree is dirty; commit or stash first (use --allow-dirty "
                "to push committed history anyway)"
            )
    else:
        report.ok("git working tree is clean")


def push_remotes(root: Path, remotes: list[str], branch: str, dry_run: bool, report: Report) -> None:
    for remote in remotes:
        if not remote.strip():
            continue
        proc = git(root, "remote", "get-url", remote)
        if proc.returncode != 0:
            report.bad(f"remote {remote!r} is not configured")
            continue
        args = ["push", remote, branch]
        if dry_run:
            args.append("--dry-run")
        push = git(root, *args)
        if push.returncode != 0:
            report.bad(
                f"push to {remote!r} ({branch}) failed: "
                f"{push.stderr.strip() or push.stdout.strip()}"
            )
            continue
        head = git(root, "rev-parse", "HEAD").stdout.strip()
        remote_ref = git(root, "rev-parse", f"{remote}/{branch}").stdout.strip()
        if dry_run:
            report.ok(f"dry-run push to {remote!r} ({branch}) prepared")
            continue
        if head and remote_ref and head == remote_ref:
            report.ok(f"pushed {remote!r} ({branch}): HEAD == {remote}/{branch} == {head[:12]}")
        else:
            report.warn(
                f"push to {remote!r} ({branch}) reported success but "
                f"{remote}/{branch} is {remote_ref[:12] or '<unknown>'}; verify with git status -sb"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-remote git sync for research projects")
    parser.add_argument("--project", required=True, help="project root directory")
    parser.add_argument("--dry-run", action="store_true", help="plan the pushes without sending")
    parser.add_argument("--allow-dirty", action="store_true", help="warn instead of fail on a dirty tree")
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    args = parser.parse_args()

    report = Report()
    root = Path(args.project).resolve()
    if not (root / ".git").exists() and not (root / ".git").is_dir():
        report.bad(f"project directory is not a git repository: {root}")
    else:
        config = load_project_config(root, report)
        push_order = (config.get("git_sync") or {}).get("push_order") or ["origin"]
        if not isinstance(push_order, list) or not all(isinstance(r, str) for r in push_order):
            report.warn("git_sync.push_order is not a list of strings; using ['origin']")
            push_order = ["origin"]
        report.ok(f"push order: {push_order}")
        check_dirty(root, report, args.allow_dirty)
        branch = current_branch(root, report)
        if branch:
            push_remotes(root, push_order, branch, args.dry_run, report)
        status = git(root, "status", "-sb")
        if status.returncode == 0:
            report.ok(f"final status: {status.stdout.strip()}")

    failures = [e for e in report.entries if e["status"] == "FAIL"]
    print(
        f"{len(failures)} problem(s) found, "
        f"{sum(1 for e in report.entries if e['status'] == 'warn')} warning(s), "
        f"{report.checks} check(s)."
    )
    if args.json:
        print(json.dumps({"checks": report.entries, "failures": len(failures)}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
