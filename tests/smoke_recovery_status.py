#!/usr/bin/env python3
"""Check retry-safe receipt preparation, latest fail-closed selection and quota data."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/math-research-workflow/scripts"))
import checkpoint_resume as engine
import recovery_status as recovery
from smoke_checkpoint_resume import fixture, next_state


class RecoveryTests(unittest.TestCase):
	def test_concurrent_draft_is_not_reported_ready(self):
		with tempfile.TemporaryDirectory() as Temp:
			Project, State, Checkpoint = fixture(Path(Temp))
			engine.seal_checkpoint(Project, State, Checkpoint)
			Original = engine.write_resume_receipt
			def receipt_then_advance(*Args):
				Result = Original(*Args)
				next_state(Project, State, Checkpoint, State.with_name("resume_receipt-00.json"))
				return Result
			with patch.object(engine, "write_resume_receipt", side_effect=receipt_then_advance):
				Result = recovery.prepare_resume(Project, State.parent, "2026-08-29T13:00:00Z")
			self.assertEqual(Result["verdict"], "PENDING_DRAFT")
			self.assertFalse(Result["dispatch_performed"])

	def test_resume_retry_draft_and_latest_tamper(self):
		with tempfile.TemporaryDirectory() as Temp:
			Project, State, Checkpoint = fixture(Path(Temp))
			engine.seal_checkpoint(Project, State, Checkpoint)
			RunRoot = State.parent.relative_to(Project)
			Before = Checkpoint.read_bytes()
			self.assertEqual(recovery.inspect_run(Project, RunRoot)["verdict"], "READY")
			First = recovery.prepare_resume(Project, RunRoot, "2026-08-29T13:00:00Z")
			self.assertEqual(First["verdict"], "RESUME_PREPARED")
			Receipt = State.with_name("resume_receipt-00.json")
			Saved = Receipt.read_bytes()
			Again = recovery.prepare_resume(Project, RunRoot, "2026-08-29T13:05:00Z")
			self.assertEqual(Again["verdict"], "RESUME_RECEIPT_REUSED")
			self.assertFalse(Again["dispatch_performed"])
			self.assertEqual(Receipt.read_bytes(), Saved)
			NewState, NewCheckpoint, _ = next_state(Project, State, Checkpoint, Receipt)
			self.assertEqual(recovery.prepare_resume(Project, RunRoot)["verdict"], "PENDING_DRAFT")
			engine.seal_checkpoint(Project, NewState, NewCheckpoint)
			self.assertEqual(recovery.inspect_run(Project, RunRoot)["sequence"], 1)
			NewCheckpoint.write_text("{}", encoding="utf-8")
			with self.assertRaises(engine.CheckpointError):
				recovery.inspect_run(Project, RunRoot)
			self.assertEqual(Checkpoint.read_bytes(), Before)

	def test_quota_missing_stale_and_shared_windows(self):
		Snapshot = dict(observed_at="2026-09-05T00:00:00Z", rateLimitsByLimitId=dict(codex=dict(limitId="codex",
			primary=dict(usedPercent=40), secondary=dict(usedPercent=95))))
		Result = recovery.quota_gate(Snapshot, 10, Now="2026-09-05T00:00:01Z")
		self.assertEqual(Result["verdict"], "HEADROOM_LOW")
		self.assertEqual(Result["remaining_percent"], 5)
		self.assertEqual(recovery.quota_gate(Snapshot, 2, Now="2026-09-05T00:00:01Z")["verdict"], "HEADROOM_AVAILABLE")
		self.assertEqual(recovery.quota_gate(Snapshot, 10, Now="2026-09-05T00:20:00Z")["verdict"], "UNKNOWN")
		for Value in (None, True, float("nan"), -1, 101):
			Bad = copy.deepcopy(Snapshot)
			Bad["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] = Value
			self.assertEqual(recovery.quota_gate(Bad, 10, Now="2026-09-05T00:00:01Z")["verdict"], "UNKNOWN")
		Snapshot["rateLimitsByLimitId"]["codex"]["primary"]["resetsAt"] = 1
		self.assertEqual(recovery.quota_gate(Snapshot, 10, Now="2026-09-05T00:00:01Z")["verdict"], "UNKNOWN")


if(__name__ == "__main__"):
	unittest.main()
