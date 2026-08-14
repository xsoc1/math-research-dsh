#!/usr/bin/env python3
"""DSH environment preflight for the math-research-dsh skill set.

Checks:
  1. every one of the four skill bundles is mounted under the DSH skill root
     ($DSH_HOME/skills/<name>/SKILL.md, DSH_HOME defaults to ~/.dsh);
  2. the math-research-dsh repository checkout is present ($DSH_HOME/math-research-dsh);
  3. a usable Python interpreter exists;
  4. on Windows, PYTHONUTF8=1 is set (scripts read UTF-8 sources);
  5. the Lean toolchain (lake) exists -- hard FAIL only with --require-lean.

Hard FAILs print an exact repair command. Exit code 0 when no FAIL, 1 otherwise.

Usage:
    python scripts/dsh-doctor.py [--require-lean] [--python CMD] [--json]
    python scripts/dsh-doctor.py --list-file PATH [--json]

--list-file reads a simulated environment instead of probing the machine
(used by the smoke tests):

    {
      "dsh_home": "/tmp/fake",
      "repo_present": true,
      "bundles": {"rigorous-open-math-research": true, ...},
      "python_cmds": {"python": true, "py -3": false},
      "lean": false
    }
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_NAMES = (
    "rigorous-open-math-research",
    "manage-math-research-program",
    "math-research-workflow",
    "lean-verify",
)

REPO_NAME = "math-research-dsh"


class Report:
    def __init__(self) -> None:
        self.problems = 0
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def ok(self, message: str) -> None:
        print(f"ok: {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"warn: {message}")

    def fail(self, message: str, repair: str) -> None:
        self.problems += 1
        self.failures.append(message)
        print(f"FAIL: {message}")
        print(f"  repair: {repair}")


def probe_python(candidates: list[str], probe: dict[str, bool] | None) -> str | None:
    if probe is not None:
        for cmd, ok in probe.items():
            if ok:
                return cmd
        return None
    for cmd in candidates:
        argv = cmd.split() + ["--version"]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0:
            return cmd
    return None


def probe_lake(probe: bool | None) -> bool:
    if probe is not None:
        return probe
    if shutil.which("lake") is None:
        return False
    proc = subprocess.run(["lake", "--version"], capture_output=True, text=True, errors="replace", timeout=20)
    return proc.returncode == 0


def check_skill_bundles(report: Report, skills_root: Path, bundles: dict[str, bool] | None) -> None:
    repair = (
        f'git clone https://github.com/xsoc1/math-research-dsh.git "{skills_root.parent / REPO_NAME}" '
        f'&& powershell -ExecutionPolicy Bypass -File "{skills_root.parent / REPO_NAME / "install.ps1"}"'
    )
    for name in SKILL_NAMES:
        if bundles is not None:
            present = bool(bundles.get(name))
            reason = "simulated"
        else:
            present = (skills_root / name / "SKILL.md").is_file()
            reason = str(skills_root / name / "SKILL.md")
        if present:
            report.ok(f"skill bundle '{name}' mounted ({reason})")
        else:
            report.fail(f"skill bundle '{name}' not mounted under {skills_root}", repair)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-lean", action="store_true")
    parser.add_argument("--python", default=None, help="python command to prefer")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list-file", default=None)
    args = parser.parse_args()

    fake: dict | None = None
    if args.list_file:
        fake = json.loads(Path(args.list_file).read_text(encoding="utf-8"))

    report = Report()
    dsh_home = (
        Path(fake["dsh_home"])
        if fake is not None and fake.get("dsh_home")
        else Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")
    )
    skills_root = dsh_home / "skills"
    report.ok(f"DSH skill root: {skills_root}")

    bundles = (fake or {}).get("bundles")
    check_skill_bundles(report, skills_root, bundles)

    repo_checkout = dsh_home / REPO_NAME
    repo_present = bool((fake or {}).get("repo_present"))
    if repo_present or (fake is None and (repo_checkout / "install.ps1").is_file()):
        report.ok(f"repository checkout present at {repo_checkout}")
    else:
        report.warn(
            f"repository checkout not found at {repo_checkout}; "
            f"dsh-doctor and the sync tooling live there"
        )

    candidates = []
    if args.python:
        candidates.append(args.python)
    candidates.append(os.environ.get("DSH_PYTHON", ""))
    candidates.append("python")
    candidates.append("py -3")
    candidates = [c for c in candidates if c]
    python_probe = (fake or {}).get("python_cmds")
    found = probe_python(candidates, python_probe)
    if found:
        report.ok(f"python interpreter available: {found}")
    else:
        report.fail(
            "no usable python interpreter found (tried: " + ", ".join(candidates) + ")",
            "install Python 3.10+ and put it on PATH, or pass --python <path>",
        )

    if sys.platform == "win32" and fake is None and os.environ.get("PYTHONUTF8") != "1":
        report.warn("PYTHONUTF8 is not 1 on Windows; set it when running the bundled scripts")

    lean_ok = probe_lake((fake or {}).get("lean"))
    if lean_ok:
        report.ok("lean toolchain (lake) available")
    elif args.require_lean:
        report.fail("lean toolchain (lake) not found but --require-lean was given", "install Lean 4 (lake on PATH)")
    else:
        report.warn("lean toolchain (lake) not found; stage C (lean-verify) needs it")

    if args.json:
        payload = {
            "dsh_home": str(dsh_home),
            "problems": report.problems,
            "failures": report.failures,
            "warnings": report.warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if report.problems else 0
    print(f"{report.problems} problem(s).")
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
