#!/usr/bin/env python3
"""Real CLI checks for process ownership and unrestricted default iteration."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/lean-verify/scripts/lake_build_guard.py"


def run(Project, Mode, *Extra):
	Result = subprocess.run([sys.executable, str(SCRIPT), "--project", str(Project), "--" + Mode, *Extra], capture_output=True, text=True)
	return Result, json.loads(Result.stdout)


def main():
	with tempfile.TemporaryDirectory() as Temp:
		Project = Path(Temp)
		First, Lock = run(Project, "check", "--input-hash", "proof-v1")
		assert First.returncode == 0 and Lock["status"] == "acquired"
		Second, Busy = run(Project, "check", "--input-hash", "proof-v2")
		assert Second.returncode != 0 and Busy["status"] == "conflict"
		Wrong, _ = run(Project, "release", "--token", "wrong-owner-token")
		assert Wrong.returncode != 0
		Released, _ = run(Project, "release", "--token", Lock["token"])
		assert Released.returncode == 0
		for _ in range(7):
			Result, Current = run(Project, "check")
			assert Result.returncode == 0, Current
			Released, _ = run(Project, "release", "--token", Current["token"])
			assert Released.returncode == 0
	print("lake build guard ownership and default iteration smoke passed")
	return 0


if(__name__ == "__main__"):
	raise SystemExit(main())
