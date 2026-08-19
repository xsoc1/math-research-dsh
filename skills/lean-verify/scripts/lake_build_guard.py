#!/usr/bin/env python3
"""Guard against runaway `lake build` loops and repeated mathlib4 cloning.

Problem fixed: a long-running research session can get stuck repeatedly running
`lake build` / cloning mathlib4, saturating network and CPU. This guard makes a
build start only when the project is not already building and not repeatedly
attempting builds within a short window.

Usage (called by verify_lean_project.py before/after a build):
  python lake_build_guard.py --project DIR --check
  python lake_build_guard.py --project DIR --release

State files (inside .lake/):
  .lake/build_guard.lock        - created on --check, removed on --release
  .lake/build_attempts.log      - timestamp lines for loop detection
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import sys

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW_MINUTES = 10
DEFAULT_LOCK_MINUTES = 30


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def recent_attempts(log_path: pathlib.Path, window: datetime.timedelta) -> int:
    if not log_path.is_file():
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - window
    count = 0
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            ts = datetime.datetime.fromisoformat(line.strip())
        except ValueError:
            continue
        if ts >= cutoff:
            count += 1
    return count


def check(root: pathlib.Path, max_attempts: int, window_minutes: int, lock_minutes: int) -> int:
    lake_dir = root / ".lake"
    lake_dir.mkdir(parents=True, exist_ok=True)
    lock = lake_dir / "build_guard.lock"
    log = lake_dir / "build_attempts.log"

    if lock.is_file():
        try:
            mtime = datetime.datetime.fromtimestamp(lock.stat().st_mtime, datetime.timezone.utc)
            age = datetime.datetime.now(datetime.timezone.utc) - mtime
            if age < datetime.timedelta(minutes=lock_minutes):
                print(f"FAIL: build guard lock is fresh ({age.total_seconds():.0f}s old). "
                      "A lake build may already be running or a loop is occurring. "
                      "Remove .lake/build_guard.lock only if no build is running.")
                return 1
        except OSError:
            pass

    attempts = recent_attempts(log, datetime.timedelta(minutes=window_minutes))
    if attempts >= max_attempts:
        print(f"FAIL: {attempts} lake build attempts within the last {window_minutes} minutes "
              f"(max {max_attempts}). Refusing to start another build. "
              "Check for a runaway session; use `lake exe cache get` instead of repeated "
              "cloning mathlib4, and remove .lake/build_attempts.log only after confirming "
              "the session is stopped.")
        return 1

    # Warn about missing mathlib4 cache without failing.
    lakefile = root / "lakefile.lean"
    if lakefile.is_file() and "mathlib" in lakefile.read_text(encoding="utf-8", errors="replace"):
        mathlib = lake_dir / "packages" / "mathlib4"
        if not mathlib.is_dir():
            print("WARN: mathlib4 package dir not found under .lake/packages. "
                  "Prefer `lake exe cache get` (or a single `lake update`) over repeated cloning.")

    lock.write_text(now_iso() + "\n", encoding="utf-8")
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(now_iso() + "\n")
    print("OK: build guard acquired.")
    return 0


def release(root: pathlib.Path) -> int:
    lock = root / ".lake" / "build_guard.lock"
    if lock.is_file():
        lock.unlink()
        print("OK: build guard released.")
    else:
        print("OK: build guard already released.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".", help="Lean project root directory")
    ap.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    ap.add_argument("--window-minutes", type=int, default=DEFAULT_WINDOW_MINUTES)
    ap.add_argument("--lock-minutes", type=int, default=DEFAULT_LOCK_MINUTES)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="pre-build guard check")
    mode.add_argument("--release", action="store_true", help="post-build lock release")
    args = ap.parse_args()

    root = pathlib.Path(args.project).resolve()
    if not root.is_dir():
        print(f"FAIL: project directory not found: {root}")
        return 2

    if args.check:
        return check(root, args.max_attempts, args.window_minutes, args.lock_minutes)
    return release(root)


if __name__ == "__main__":
    sys.exit(main())
