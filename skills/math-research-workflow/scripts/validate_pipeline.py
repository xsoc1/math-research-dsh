#!/usr/bin/env python3
"""Check current continuity data, or explicitly validate a legacy 1.x protocol.

This is data health, not a theorem verdict or authorization to do research.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

import research_state


def main():
	if("--legacy-v1" in sys.argv):
		sys.argv.remove("--legacy-v1")
		import legacy_pipeline
		return legacy_pipeline.main()
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--project", required=True)
	Parser.add_argument("--scope")
	Parser.add_argument("--check-git", action="store_true")
	Parser.add_argument("--allow-dirty", action="store_true")
	Parser.add_argument("--archives", action="store_true")
	Args = Parser.parse_args()
	try:
		Project = Path(Args.project).resolve()
		Root = research_state.inside(Project, Args.scope or ".")
		if(not Root.is_dir()):
			raise ValueError("project or scope directory missing")
		Snapshot = research_state.inspect_project(Root, Archives=Args.archives)
		Errors = list(Snapshot["problems"])
		Warnings = []
		for Job in Snapshot["jobs"]:
			if(not Job["result_evidence_matches"]):
				Errors.append(dict(job_id=Job["job_id"], reason="saved result evidence changed"))
			if(not Job["inputs_match"]):
				Warnings.append(dict(job_id=Job["job_id"], reason="job belongs to older inputs"))
			if(Job.get("input_mismatch_detected")):
				Warnings.append(dict(job_id=Job["job_id"], reason="declared inputs differed at an observed execution boundary"))
			if(Job.get("recovery_error_log")):
				Warnings.append(dict(job_id=Job["job_id"], reason="supervisor persistence or monitoring requires reconciliation", log=Job["recovery_error_log"]))
			if(Job.get("observed_state") == "UNKNOWN"):
				Warnings.append(dict(job_id=Job["job_id"], reason="original process requires reconciliation"))
		if(Args.check_git):
			Git = subprocess.run(["git", "status", "--porcelain", "--", str(Root)], cwd=Project,
				capture_output=True, text=True, timeout=30)
			if(Git.returncode != 0):
				Errors.append(dict(reason="Git status unavailable", detail=Git.stderr.strip()))
			elif(Git.stdout.strip()):
				(Warnings if Args.allow_dirty else Errors).append(dict(reason="working tree has changes in the requested scope"))
		print(json.dumps(dict(status="DATA_ISSUES" if Errors else "DATA_CHECKS_PASSED", scope=str(Root),
			mathematical_verdict="NOT_ASSESSED", errors=Errors, warnings=Warnings,
			checked="Current progress pointer and recorded job inputs/results; archive identities also checked when requested. No immutable execution or mathematical applicability certification.",
			archives_checked=Args.archives),
			ensure_ascii=False, sort_keys=True))
		return 1 if Errors else 0
	except (OSError, ValueError, subprocess.TimeoutExpired) as Error:
		print(json.dumps(dict(status="ERROR", error=str(Error))))
		return 2


if(__name__ == "__main__"):
	raise SystemExit(main())
