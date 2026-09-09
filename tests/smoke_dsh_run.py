#!/usr/bin/env python3
"""Smoke test for the prune-aware dsh_run wrapper."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "dsh_run.py"


def main() -> int:
	with tempfile.TemporaryDirectory(prefix="dsh wrapper ") as Folder:
		Target = Path(Folder) / "output fixture.py"
		Target.write_text(
			"import sys\nprint('begin')\nprint('x' * 20000)\n"
			"print('FAIL: controlled child failure' if int(sys.argv[1]) else 'child completed')\n"
			"print('stderr tail', file=sys.stderr)\nraise SystemExit(int(sys.argv[1]))\n",
			encoding="utf-8",
		)
		for ExitCode in (7, 0):
			Result = subprocess.run(
				[sys.executable, str(WRAPPER), str(Target), str(ExitCode)],
				capture_output=True, text=True,
			)
			assert Result.returncode == ExitCode, (Result.stdout, Result.stderr)
			Lines = Result.stdout.splitlines()
			assert Lines[0].startswith(f"VERDICT: exit={ExitCode} | log: "), Result.stdout
			assert Lines[0] == Lines[-1], "wrapper must repeat the verdict last"
			LogPath = Path(Lines[0].split("| log: ", 1)[1])
			assert LogPath.parent == Target.parent, "log must stay beside the disposable fixture"
			LogText = LogPath.read_text(encoding="utf-8")
			assert 'x' * 20000 in LogText, "complete child output must survive report truncation"
			assert LogText.endswith("stderr tail\n"), "stderr must survive in the full log"
			assert len(Result.stdout) < 1500, "wrapper report must remain compact"
			if(ExitCode):
				assert "FAIL: controlled child failure" in Result.stdout
	print("dsh_run smoke passed")
	return 0


if(__name__ == "__main__"):
	sys.exit(main())
