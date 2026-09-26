#!/usr/bin/env python3
"""Exercise one fixed DSH release with a disposable Bundle Profile on Linux.

The caller supplies an installed official DSH CLI and a locally packed tarball.
No user Profile, credentials, model call, or public STORE state is touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def run_cli(CliPath: Path, DshHome: Path, *Arguments: str) -> str:
	Environment = dict(os.environ, DSH_HOME=str(DshHome))
	Result = subprocess.run(
		["node", str(CliPath), *Arguments],
		capture_output=True,
		text=True,
		timeout=90,
		env=Environment,
	)
	if(Result.returncode != 0):
		raise RuntimeError(f"DSH CLI failed for {Arguments[:3]}: exit {Result.returncode}")
	if("entry did not activate" in Result.stderr or "failed to import" in Result.stderr):
		raise RuntimeError(f"DSH Bundle entry did not activate for {Arguments[:3]}")
	return Result.stdout


def dump_config(CliPath: Path, DshHome: Path, Profile: str, Template: str | None = None) -> str:
	Arguments = ["--profile", Profile]
	if(Template is not None):
		Arguments.extend(["--from-default-profile", Template])
	Arguments.append("--dump-config")
	return run_cli(CliPath, DshHome, *Arguments)


def assert_entry(Config: str, Expected: bool) -> None:
	Count = Config.count("\n- id: math-research-dsh\n")
	if(Count != int(Expected)):
		raise RuntimeError(f"Expected Bundle entry count {int(Expected)}, got {Count}")


def web_start(CliPath: Path, DshHome: Path, WorkDir: Path) -> int:
	LogPath = WorkDir / "web-start-private.log"
	Environment = dict(os.environ, DSH_HOME=str(DshHome))
	Command = ["node", str(CliPath), "--profile", "store-web", "--no-open", "--host", "127.0.0.1", "--port", "0"]
	with LogPath.open("w", encoding="utf-8") as Log:
		Process = subprocess.Popen(
			Command,
			stdout=Log,
			stderr=subprocess.STDOUT,
			env=Environment,
			start_new_session=True,
		)
		try:
			Port = None
			for _ in range(80):
				time.sleep(0.25)
				Text = LogPath.read_text(encoding="utf-8")
				if("entry did not activate" in Text or "failed to import" in Text):
					raise RuntimeError("Web Bundle entry did not activate")
				Match = re.search(r"dsh web: http://127\.0\.0\.1:(\d+)/", Text)
				if(Match is not None):
					Port = int(Match.group(1))
					break
				if(Process.poll() is not None):
					raise RuntimeError(f"Web Profile exited before listening: {Process.returncode}")
			if(Port is None):
				raise RuntimeError("Web Profile did not listen within 20 seconds")
			try:
				urllib.request.urlopen(f"http://127.0.0.1:{Port}/", timeout=5)
				HttpStatus = 200
			except urllib.error.HTTPError as Error:
				HttpStatus = Error.code
			if(HttpStatus != 401):
				raise RuntimeError(f"Expected unauthenticated HTTP 401, got {HttpStatus}")
			return HttpStatus
		finally:
			if(Process.poll() is None):
				os.killpg(Process.pid, signal.SIGTERM)
				try:
					Process.wait(timeout=5)
				except subprocess.TimeoutExpired:
					os.killpg(Process.pid, signal.SIGKILL)
					Process.wait(timeout=5)


def main() -> int:
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--dsh-cli", type=Path, required=True)
	Parser.add_argument("--package-dir", type=Path, required=True)
	Parser.add_argument("--report", type=Path, required=True)
	Arguments = Parser.parse_args()
	CliPath = Arguments.dsh_cli.resolve(strict=True)
	Tarballs = list(Arguments.package_dir.resolve(strict=True).glob("math-research-dsh-*.tgz"))
	if(len(Tarballs) != 1):
		raise RuntimeError(f"Expected one math-research-dsh tarball, found {len(Tarballs)}")
	PackagePath = Tarballs[0]
	PackageHash = hashlib.sha256(PackagePath.read_bytes()).hexdigest()
	NodeVersion = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True).stdout.strip()
	with tempfile.TemporaryDirectory(prefix="math-research-dsh-store-") as Temporary:
		WorkDir = Path(Temporary)
		DshHome = WorkDir / "dsh-home"
		DshVersion = run_cli(CliPath, DshHome, "--version").strip()
		if(DshVersion != "0.1.7-rc.2"):
			raise RuntimeError(f"This evidence targets DSH 0.1.7-rc.2, got {DshVersion}")
		Baselines = {
			"store-headless": dump_config(CliPath, DshHome, "store-headless", "headless"),
			"store-web": dump_config(CliPath, DshHome, "store-web", "web"),
		}
		for Profile in Baselines:
			assert_entry(Baselines[Profile], False)
			run_cli(CliPath, DshHome, "plugin", "--profile", Profile, "add", str(PackagePath))
			assert_entry(dump_config(CliPath, DshHome, Profile), True)
		run_cli(CliPath, DshHome, "--profile", "store-headless", "--help")
		run_cli(CliPath, DshHome, "--profile", "store-web", "--help")
		HttpStatus = web_start(CliPath, DshHome, WorkDir)
		for Profile, Baseline in Baselines.items():
			run_cli(CliPath, DshHome, "plugin", "--profile", Profile, "remove", "math-research-dsh")
			if(dump_config(CliPath, DshHome, Profile) != Baseline):
				raise RuntimeError(f"{Profile} config differs after uninstall")
		ProfileRoot = DshHome / "profiles" / "store-headless"
		PackageBefore = (ProfileRoot / "package.json").read_bytes()
		LockBefore = (ProfileRoot / "pnpm-lock.yaml").read_bytes()
		run_cli(CliPath, DshHome, "plugin", "--profile", "store-headless", "add", str(PackagePath))
		run_cli(CliPath, DshHome, "--profile", "store-headless", "--help")
		run_cli(CliPath, DshHome, "plugin", "--profile", "store-headless", "remove", "math-research-dsh")
		if(dump_config(CliPath, DshHome, "store-headless") != Baselines["store-headless"]):
			raise RuntimeError("Rollback did not restore the composed headless config")
		if((ProfileRoot / "package.json").read_bytes() != PackageBefore):
			raise RuntimeError("Rollback did not restore the headless package manifest")
		if((ProfileRoot / "pnpm-lock.yaml").read_bytes() != LockBefore):
			raise RuntimeError("Rollback did not restore the headless lockfile")
	Report = {
		"schemaVersion": 1,
		"status": "passed",
		"checkedAt": datetime.now(timezone.utc).isoformat(),
		"packageSha256": PackageHash,
		"packageBytes": PackagePath.stat().st_size,
		"node": NodeVersion,
		"dsh": DshVersion,
		"system": "Linux",
		"profiles": ["headless", "web"],
		"operations": {"install": "passed", "start": "passed", "uninstall": "passed", "rollback": "passed"},
		"webUnauthenticatedHttpStatus": HttpStatus,
		"realProfile": "not-targeted",
		"modelSkillInvocation": "not-tested",
	}
	Arguments.report.parent.mkdir(parents=True, exist_ok=True)
	Arguments.report.write_text(json.dumps(Report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"STORE_PROFILE_OK dsh={DshVersion} node={NodeVersion} package_sha256={PackageHash}")
	return 0


if(__name__ == "__main__"):
	raise SystemExit(main())
