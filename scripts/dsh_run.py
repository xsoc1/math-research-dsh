#!/usr/bin/env python3
"""Run a bundled script with prune-aware output for DSH sessions.

DSH truncates tool results (default head 4096 + tail 1024 of ~8K chars): the
middle of a long run disappears from the conversation. This wrapper

  1. runs <target.py> with the current interpreter and the remaining args;
  2. tees the combined stdout/stderr to a log file next to the target;
  3. prints a compact report designed to survive truncation:
       - first line: VERDICT with the exit code and the log path;
       - the extracted FAIL/warn/error lines from the child output;
       - last line: the VERDICT repeated.

Usage:
    python scripts/dsh_run.py <target.py> [args...]

The complete log stays on disk and can be read afterwards with the read tool.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

INTEREST_RE = re.compile(
    r"(?i)(\bfail\b|error|traceback|exception|\bwarn\b|problem|invalid|missing|mismatch)"
)
MAX_INTEREST = 60


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    target = Path(sys.argv[1]).resolve()
    args = sys.argv[2:]
    if not target.is_file():
        print(f"VERDICT: exit=2 | target not found: {target}")
        return 2
    log_path = target.parent / f".{target.stem}.dsh_run.log"
    proc = subprocess.run(
        [sys.executable, str(target), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )
    combined = f"{proc.stdout or ''}\n{proc.stderr or ''}".strip("\n")
    log_path.write_text(combined + "\n", encoding="utf-8")
    interesting = [line for line in combined.splitlines() if INTEREST_RE.search(line)]
    verdict = f"VERDICT: exit={proc.returncode} | log: {log_path}"
    print(verdict)
    for line in interesting[:MAX_INTEREST]:
        print(line)
    if len(interesting) > MAX_INTEREST:
        print(f"... {len(interesting) - MAX_INTEREST} more matched lines in the log")
    print(verdict)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
