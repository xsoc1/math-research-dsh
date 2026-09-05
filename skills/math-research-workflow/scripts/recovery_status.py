#!/usr/bin/env python3
"""Inspect the latest sealed run and prepare its existing canonical receipt.

Inspection is read-only. Preparing a receipt is idempotent and never dispatches
work or edits a sealed artifact. An existing receipt requires runtime/action
reconciliation, not replay of its first action.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
import re

import checkpoint_resume as engine


def run_snapshot(project, RunRoot):
	Root = Path(project).resolve()
	Run = engine.inside_project(Root, Path(RunRoot), "run root", must_exist=False)
	if(not Run.is_dir()):
		raise engine.CheckpointError("run root must be an existing directory")
	Candidates = []
	for path in Run.glob("interruption_checkpoint-*.json"):
		Match = re.fullmatch(r"interruption_checkpoint-(\d+)\.json", path.name)
		if(not Match or path.name != f"interruption_checkpoint-{int(Match.group(1)):02d}.json"):
			raise engine.CheckpointError("noncanonical checkpoint filename")
		Candidates.append((int(Match.group(1)), path))
	if(not Candidates):
		raise engine.CheckpointError("no sealed checkpoint; preserve and inspect the draft, never infer completion")
	Sequence, CheckpointPath = max(Candidates, key=lambda Item: Item[0])
	Snapshot = engine._verify_checkpoint_snapshot(Root, CheckpointPath)
	Pending = []
	for path in Run.glob("interruption_state-*.json"):
		Match = re.fullmatch(r"interruption_state-(\d+)\.json", path.name)
		if(Match and int(Match.group(1)) > Sequence):
			Pending.append(path.relative_to(Root).as_posix())
	ReceiptPath = Run / f"resume_receipt-{Sequence:02d}.json"
	Receipt = None
	if(ReceiptPath.exists()):
		Receipt = engine.validate_resume_receipt(Root, CheckpointPath, ReceiptPath, snapshot=Snapshot)
	State = Snapshot["state"]
	Result = dict(verdict="PENDING_DRAFT" if Pending else "READY", checkpoint=CheckpointPath.relative_to(Root).as_posix(),
		checkpoint_id=Snapshot["verification"]["checkpoint_id"], sequence=Sequence,
		result_status=State["result_status"], receipt_exists=Receipt is not None,
		pending_drafts=sorted(Pending), first_action=State["resume"]["first_action"],
		minimal_read_set=State["resume"]["minimal_read_set"], budget=State["resume"]["budget"],
		stop_condition=State["resume"]["stop_condition"],
		inflight_work=State["inflight_work"],
		do_not_repeat_action_ids=Snapshot["effective_do_not_repeat_action_ids"],
		dispatch_performed=False,
		next_step="RECONCILE_DRAFT_AND_RUNTIME" if Pending else
			("RECONCILE_RUNTIME_BEFORE_CONTINUING" if Receipt else "PREPARE_RECEIPT"))
	return Result, Root, CheckpointPath, ReceiptPath


def inspect_run(project, RunRoot):
	return run_snapshot(project, RunRoot)[0]


def prepare_resume(project, RunRoot, ResumedAt=None):
	Result, Root, CheckpointPath, ReceiptPath = run_snapshot(project, RunRoot)
	if(Result["pending_drafts"]):
		return Result
	Created = False
	if(not Result["receipt_exists"]):
		try:
			engine.write_resume_receipt(Root, CheckpointPath, ReceiptPath, ResumedAt or engine.canonical_utc_timestamp())
			Created = True
		except FileExistsError:
			engine.validate_resume_receipt(Root, CheckpointPath, ReceiptPath)
	Fresh, _, FreshCheckpoint, _ = run_snapshot(Root, RunRoot)
	if(Fresh["pending_drafts"]):
		return Fresh
	if(FreshCheckpoint != CheckpointPath):
		return dict(verdict="STATE_CHANGED", dispatch_performed=False, next_step="REINSPECT_LATEST_CHECKPOINT")
	Result = Fresh
	Result.update(verdict="RESUME_PREPARED" if Created else "RESUME_RECEIPT_REUSED",
		receipt=ReceiptPath.relative_to(Root).as_posix(), dispatch_performed=False,
		next_step="RECONCILE_RUNTIME_THEN_ADVANCE_DRAFT")
	return Result


def as_time(value):
	Time = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
	if(Time.tzinfo is None):
		raise ValueError("quota observation must have a timezone")
	return Time.astimezone(dt.timezone.utc)


def quota_gate(Snapshot, MinRemaining, MaxAgeSeconds=300, Now=None, LimitId="codex"):
	if(not math.isfinite(MinRemaining) or not 0 <= MinRemaining <= 100 or MaxAgeSeconds <= 0):
		raise ValueError("invalid quota headroom or snapshot age")
	Clock = as_time(Now) if Now else dt.datetime.now(dt.timezone.utc)
	try:
		Observed = as_time(Snapshot["observed_at"])
	except (KeyError, TypeError, ValueError):
		return dict(verdict="UNKNOWN", action="REFRESH_USAGE_OR_SAVE_CHECKPOINT", reason="missing valid observed_at")
	Age = (Clock - Observed).total_seconds()
	if(Age < 0 or Age > MaxAgeSeconds):
		return dict(verdict="UNKNOWN", action="REFRESH_USAGE_OR_SAVE_CHECKPOINT", reason="stale or future quota observation")
	Buckets = Snapshot.get("rateLimitsByLimitId")
	Bucket = Buckets.get(LimitId) if isinstance(Buckets, dict) else Snapshot.get("rateLimits")
	if(not isinstance(Bucket, dict) or Bucket.get("limitId", LimitId) != LimitId):
		return dict(verdict="UNKNOWN", action="REFRESH_USAGE_OR_SAVE_CHECKPOINT", reason="quota bucket unavailable")
	Windows = []
	for name in ("primary", "secondary"):
		Window = Bucket.get(name)
		Used = Window.get("usedPercent") if isinstance(Window, dict) else None
		if(isinstance(Used, bool) or not isinstance(Used, (int, float)) or not math.isfinite(Used) or not 0 <= Used <= 100):
			return dict(verdict="UNKNOWN", action="REFRESH_USAGE_OR_SAVE_CHECKPOINT", reason=f"{name} usage unavailable")
		Reset = Window.get("resetsAt")
		if(Reset is not None and (isinstance(Reset, bool) or not isinstance(Reset, (int, float)) or not math.isfinite(Reset))):
			return dict(verdict="UNKNOWN", action="REFRESH_USAGE_OR_SAVE_CHECKPOINT", reason="invalid reset timestamp")
		if(Reset is not None and Reset <= Clock.timestamp()):
			return dict(verdict="UNKNOWN", action="REFRESH_USAGE_OR_SAVE_CHECKPOINT", reason="reset boundary passed; request a fresh snapshot")
		Windows.append(dict(window=name, remaining_percent=100 - Used, resets_at=Reset))
	Remaining = min(Window["remaining_percent"] for Window in Windows)
	Pause = Remaining <= MinRemaining
	return dict(verdict="HEADROOM_LOW" if Pause else "HEADROOM_AVAILABLE",
		action="SAVE_CHECKPOINT_BEFORE_NEW_WORK" if Pause else "CONTINUE_WITHIN_DECLARED_BUDGET",
		remaining_percent=Remaining, windows=Windows, headroom_percent=MinRemaining,
		warning="Shared account quota is not per-task token accounting. No reset credit is consumed.")


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Sub = Parser.add_subparsers(dest="command", required=True)
	for name in ("inspect", "prepare-resume"):
		Command = Sub.add_parser(name)
		Command.add_argument("--project", required=True)
		Command.add_argument("--run-root", required=True)
		if(name == "prepare-resume"):
			Command.add_argument("--resumed-at")
	Quota = Sub.add_parser("quota")
	Quota.add_argument("--snapshot", required=True)
	Quota.add_argument("--min-remaining", required=True, type=float)
	Quota.add_argument("--max-age-seconds", type=int, default=300)
	Quota.add_argument("--limit-id", default="codex")
	Args = Parser.parse_args()
	try:
		if(Args.command == "inspect"):
			Result = inspect_run(Args.project, Args.run_root)
		elif(Args.command == "prepare-resume"):
			Result = prepare_resume(Args.project, Args.run_root, Args.resumed_at)
		else:
			Snapshot = engine.load_json(Path(Args.snapshot), "quota snapshot")
			Result = quota_gate(Snapshot, Args.min_remaining, Args.max_age_seconds, LimitId=Args.limit_id)
	except (engine.CheckpointError, OSError, ValueError, TypeError, KeyError) as Error:
		Result = dict(verdict="STALE", error=str(Error), dispatch_performed=False)
	print(json.dumps(Result, ensure_ascii=False, sort_keys=True))
	return 0 if Result["verdict"] in ("READY", "RESUME_PREPARED", "RESUME_RECEIPT_REUSED", "HEADROOM_AVAILABLE") else 1


if(__name__ == "__main__"):
	raise SystemExit(main())
