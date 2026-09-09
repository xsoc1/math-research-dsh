#!/usr/bin/env python3
"""Real detached jobs and recoverable writes, without an account or quota API."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/math-research-workflow/scripts"))
import research_state as state


class ResearchStateTests(unittest.TestCase):
	def setUp(self):
		self.Temp = tempfile.TemporaryDirectory()
		self.Project = Path(self.Temp.name).resolve()
		(self.Project / "input.txt").write_text("v1")

	def tearDown(self):
		self.Temp.cleanup()

	def wait_job(self, JobId):
		Deadline = time.monotonic() + 12
		while(time.monotonic() < Deadline):
			Record = state.job_status(self.Project, JobId)
			if(Record["state"] not in ("STARTING", "RUNNING")):
				Supervisor = Record.get("supervisor_pid")
				if(not Supervisor or state.process_identity(Supervisor) != Record.get("supervisor_identity")):
					return Record
			time.sleep(0.05)
		self.fail("job failed to finish: " + json.dumps(Record))

	def start(self, JobId, Code, **Kwargs):
		return state.start_job(self.Project, JobId, [sys.executable, "-c", Code], ["input.txt"], **Kwargs)

	def test_free_form_resume_and_stale_writer(self):
		First = state.save_progress(self.Project, "A useful failed route; retry after lemma X.\n", "missing")
		Snapshot = state.checkpoint(self.Project, Inputs=["input.txt"])
		Second = state.save_progress(self.Project, "Human corrected X to Y.\n", First["sha256"])
		with self.assertRaises(ValueError):
			state.save_progress(self.Project, "Old agent overwrites human.\n", First["sha256"])
		self.assertEqual(state.inspect_project(self.Project)["progress_sha256"], Second["sha256"])
		self.assertEqual((self.Project / "RESUME.md").read_text(), "Human corrected X to Y.\n")
		self.assertTrue(Path(Snapshot["snapshot"]).is_file())
		self.assertIn("failed route", (self.Project / ".research-state/progress" / (First["sha256"] + ".md")).read_text())

	def test_atomic_write_failure_retains_previous_progress(self):
		First = state.save_progress(self.Project, "saved theorem and remaining gap", "missing")
		with patch.object(state.os, "replace", side_effect=OSError("interrupted write")):
			with self.assertRaises(OSError):
				state.save_progress(self.Project, "new partial text", First["sha256"])
		self.assertEqual((self.Project / "RESUME.md").read_text(), "saved theorem and remaining gap")

	def test_existing_project_progress_is_used(self):
		(self.Project / "state").mkdir()
		(self.Project / "state/RESUME.md").write_text("Existing project notes")
		self.assertEqual(Path(state.inspect_project(self.Project)["progress"]), self.Project / "state/RESUME.md")
		self.assertFalse((self.Project / "RESUME.md").exists())

	def test_detached_job_survives_client_and_is_not_replayed(self):
		Code = "from pathlib import Path; import time; time.sleep(.4); Path('effect.txt').open('a').write('once\\n'); print('finished')"
		Command = [sys.executable, str(Path(state.__file__)), "start", "--project", str(self.Project),
			"--job-id", "proof-check", "--input", "input.txt", "--", sys.executable, "-c", Code]
		Client = subprocess.run(Command, capture_output=True, text=True, check=True)
		self.assertTrue(json.loads(Client.stdout)["dispatched"])
		Replay = self.start("proof-check", Code)
		self.assertFalse(Replay["dispatched"])
		Record = self.wait_job("proof-check")
		self.assertEqual(Record["state"], "SUCCEEDED")
		self.assertTrue(Record["recorded_inputs_match_current"])
		self.assertIsNone(Record["result_applies_to_current_inputs"])
		self.assertEqual((self.Project / "effect.txt").read_text(), "once\n")
		self.assertEqual(Record["mathematical_verdict"], "NOT_INFERRED_FROM_JOB_STATUS")

	def test_changed_input_cannot_reuse_job_id_or_green_old_result(self):
		self.start("compile", "print('old source')")
		self.wait_job("compile")
		(self.Project / "input.txt").write_text("v2")
		self.assertFalse(state.job_status(self.Project, "compile")["result_applies_to_current_inputs"])
		with self.assertRaises(ValueError):
			self.start("compile", "print('old source')")

	def test_full_output_and_tamper_detection(self):
		self.start("long-log", "print('a'*20000)")
		Record = self.wait_job("long-log")
		Log = self.Project / Record["stdout"]
		self.assertGreater(Log.stat().st_size, 20000)
		Log.write_text("replacement")
		self.assertFalse(state.job_status(self.Project, "long-log")["result_evidence_matches"])

	def test_changed_symlink_input_invalidates_result(self):
		Alias = self.Project / "current.txt"
		try:
			Alias.symlink_to(self.Project / "input.txt")
		except OSError as Error:
			self.skipTest("symlink creation is unavailable: " + str(Error))
		(self.Project / "next.txt").write_text("v1")
		state.start_job(self.Project, "symlink", [sys.executable, "-c", "print('checked')"], ["current.txt"])
		self.wait_job("symlink")
		Alias.unlink()
		Alias.symlink_to(self.Project / "next.txt")
		self.assertFalse(state.job_status(self.Project, "symlink")["inputs_match"])

	def test_failure_timeout_and_missing_executable(self):
		self.start("failure", "raise SystemExit(7)")
		self.assertEqual(self.wait_job("failure")["exit_code"], 7)
		self.start("timeout", "import time; print('partial', flush=True); time.sleep(20)", Timeout=0.5)
		Record = self.wait_job("timeout")
		self.assertEqual(Record["state"], "TIMEOUT")
		self.assertFalse(Record["result_applies_to_current_inputs"])
		self.assertIn("partial", (self.Project / Record["stdout"]).read_text())
		state.start_job(self.Project, "missing", [str(self.Project / "absent-executable")])
		self.assertEqual(self.wait_job("missing")["state"], "FAILED_TO_START")

	def test_pid_reuse_is_unknown_and_never_dispatches(self):
		state.create_job(self.Project, "orphan", dict(kind="local", command=["unused"], cwd=".", inputs={}, timeout_seconds=None))
		state.update_job(self.Project, "orphan", dict(state="RUNNING", supervisor_pid=os.getpid(), supervisor_identity="old-process"))
		Record = state.job_status(self.Project, "orphan")
		self.assertEqual(Record["observed_state"], "UNKNOWN")
		self.assertFalse(Record["supervisor_alive"])
		self.assertFalse(Record["result_applies_to_current_inputs"])

	def test_killed_supervisor_does_not_trigger_duplicate_effect(self):
		Code = "from pathlib import Path; import time; time.sleep(.6); Path('orphan-effect').open('a').write('once')"
		self.start("killed-supervisor", Code)
		Deadline = time.monotonic() + 5
		while(time.monotonic() < Deadline):
			Record = state.job_status(self.Project, "killed-supervisor")
			if(Record.get("child_pid")):
				break
			time.sleep(.02)
		self.assertIn("child_pid", Record)
		os.kill(Record["supervisor_pid"], 9)
		Replay = self.start("killed-supervisor", Code)
		self.assertFalse(Replay["dispatched"])
		while(time.monotonic() < Deadline and not (self.Project / "orphan-effect").exists()):
			time.sleep(.02)
		self.assertEqual((self.Project / "orphan-effect").read_text(), "once")
		self.assertFalse(state.job_status(self.Project, "killed-supervisor")["result_applies_to_current_inputs"])

	def test_default_validation_does_not_require_a_legacy_pipeline(self):
		Script = ROOT / "skills/math-research-workflow/scripts/validate_pipeline.py"
		state.save_progress(self.Project, "Human question and one useful lemma", "missing")
		Result = subprocess.run([sys.executable, str(Script), "--project", str(self.Project)], capture_output=True, text=True)
		self.assertEqual(Result.returncode, 0, Result.stderr)
		self.assertEqual(json.loads(Result.stdout)["mathematical_verdict"], "NOT_ASSESSED")
		state.register_external(self.Project, "observed", "provider", "key")
		state.job_path(self.Project, "observed").write_text("{")
		Result = subprocess.run([sys.executable, str(Script), "--project", str(self.Project)], capture_output=True, text=True)
		self.assertEqual(Result.returncode, 1)
		self.assertEqual(json.loads(Result.stdout)["status"], "DATA_ISSUES")

	def test_external_lost_response_reconciles_without_resubmitting(self):
		First = state.register_external(self.Project, "remote", "test-provider", "stable-request", ["input.txt"])
		self.assertEqual(First["job"]["state"], "UNKNOWN")
		Again = state.register_external(self.Project, "remote", "test-provider", "stable-request", ["input.txt"], "actual-job-42")
		self.assertFalse(Again["dispatched"])
		self.assertEqual(Again["job"]["external_id"], "actual-job-42")
		with self.assertRaises(ValueError):
			state.register_external(self.Project, "remote", "test-provider", "stable-request", ["input.txt"], "different-job")
		(self.Project / "response.json").write_text('{"provider_status":"unknown"}')
		state.record_result(self.Project, "remote", "UNKNOWN", "response.json")
		(self.Project / "response.json").write_text('{"provider_status":"success"}')
		Record = state.record_result(self.Project, "remote", "SUCCEEDED", "response.json")
		self.assertEqual(len(Record["observations"]), 2)
		(self.Project / "response.json").write_text("later overwritten transport file")
		self.assertTrue(state.job_status(self.Project, "remote")["result_evidence_matches"])
		self.assertEqual((self.Project / Record["result"]).read_text(), '{"provider_status":"success"}')
		(self.Project / "input.txt").write_text("new source before delivery")
		self.assertFalse(state.job_status(self.Project, "remote")["result_applies_to_current_inputs"])

	def test_one_bad_job_does_not_hide_other_progress(self):
		state.save_progress(self.Project, "important route", "missing")
		state.register_external(self.Project, "good", "provider", "key")
		state.job_path(self.Project, "bad").write_text("{")
		Result = state.inspect_project(self.Project)
		self.assertEqual(len(Result["jobs"]), 1)
		self.assertEqual(len(Result["problems"]), 1)
		self.assertIsNotNone(Result["progress_sha256"])

	def test_malformed_observations_are_isolated_by_actual_clis(self):
		state.save_progress(self.Project, "keep current research readable", "missing")
		state.register_external(self.Project, "healthy", "provider", "healthy-key")
		state.register_external(self.Project, "damaged", "provider", "damaged-key")
		(self.Project / "receipt.txt").write_text("actual observed result")
		state.record_result(self.Project, "damaged", "SUCCEEDED", "receipt.txt")
		Record = state.load_job(self.Project, "damaged")
		for Observations in (None, {}, [None], [{"state": "SUCCEEDED"}], [{"state": "invalid"}]):
			Record["observations"] = Observations
			state.job_path(self.Project, "damaged").write_bytes(state.json_bytes(Record))
			Result = state.inspect_project(self.Project, Archives=True)
			self.assertEqual([Job["job_id"] for Job in Result["jobs"]], ["healthy"])
			self.assertEqual(len(Result["problems"]), 1)
			self.assertIsNotNone(Result["progress_sha256"])
		Record["observations"] = None
		state.job_path(self.Project, "damaged").write_bytes(state.json_bytes(Record))
		for Script, Extra, ExitCode in ((Path(state.__file__), ["inspect"], 0),
			(ROOT / "skills/math-research-workflow/scripts/validate_pipeline.py", [], 1)):
			Reply = subprocess.run([sys.executable, str(Script), *Extra, "--project", str(self.Project), "--archives"], capture_output=True, text=True)
			self.assertEqual(Reply.returncode, ExitCode, Reply.stderr)
			Payload = json.loads(Reply.stdout)
			if(Extra):
				self.assertEqual([Job["job_id"] for Job in Payload["jobs"]], ["healthy"])
			else:
				self.assertEqual(Payload["status"], "DATA_ISSUES")

	def test_timeout_remains_active_during_metadata_lock_contention(self):
		Code = "from pathlib import Path; import time; time.sleep(.3); Path('late-effect').write_text('too late')"
		state.create_job(self.Project, "deadline", dict(kind="local", command=[sys.executable, "-c", Code], cwd=".", inputs={}, timeout_seconds=.1))
		LockCode = "\n".join(("import sys, time", "from pathlib import Path",
			"sys.path.insert(0, " + repr(str(Path(state.__file__).parent)) + ")", "import research_state as state",
			"with state.writer_lock(Path(" + repr(str(state.job_path(self.Project, "deadline").with_suffix(".lock"))) + ")):",
			"\tprint('locked', flush=True)", "\ttime.sleep(.6)"))
		Update = state.update_job
		Lockers = []
		def contend_after_creation(Root, JobId, Changes):
			if("child_pid" in Changes and not Lockers):
				Locker = subprocess.Popen([sys.executable, "-c", LockCode], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
				Lockers.append(Locker)
				self.assertEqual(Locker.stdout.readline().strip(), "locked")
			return Update(Root, JobId, Changes)
		try:
			with patch.object(state, "update_job", side_effect=contend_after_creation):
				state.run_worker(self.Project, "deadline")
		finally:
			for Locker in Lockers:
				Output, Error = Locker.communicate(timeout=5)
				self.assertEqual(Locker.returncode, 0, Error)
		self.assertEqual(state.job_status(self.Project, "deadline")["state"], "TIMEOUT")
		self.assertFalse((self.Project / "late-effect").exists())

	def test_storage_and_input_paths_cannot_escape(self):
		with self.assertRaises(ValueError):
			state.checkpoint(self.Project, Progress="../escape.md")
		with self.assertRaises(ValueError):
			state.start_job(self.Project, "../escape", ["unused"])
		with self.assertRaises(ValueError):
			state.start_job(self.Project, "missing-input", ["unused"], ["missing.lean"])
		with self.assertRaises(ValueError):
			state.input_snapshot(self.Project, ["input.txt", "link/../input.txt"])

	def test_noncanonical_root_preserves_containment(self):
		(self.Project / "child").mkdir()
		Aliases = [self.Project / "child/..", Path(self.Temp.name)]
		if(os.name == "nt"):
			import ctypes
			from ctypes import wintypes
			ShortPath = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
			ShortPath.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
			ShortPath.restype = wintypes.DWORD
			Buffer = ctypes.create_unicode_buffer(32768)
			Length = ShortPath(str(self.Project), Buffer, len(Buffer))
			self.assertTrue(0 < Length < len(Buffer))
			Aliases.append(Path(Buffer.value))
		Expected = state.input_snapshot(self.Project, ["input.txt"])
		for Index, Alias in enumerate(Aliases):
			with self.subTest(root=str(Alias)):
				self.assertEqual(state.inside(Alias, "input.txt"), self.Project / "input.txt")
				self.assertEqual(state.input_snapshot(Alias, ["input.txt"]), Expected)
				Record, Created = state.create_job(Alias, "alias-" + str(Index), dict(kind="external", provider="fixture", request_key=str(Index), inputs=Expected))
				self.assertTrue(Created)
				self.assertEqual(Record["state"], "UNKNOWN")
				with self.assertRaises(ValueError):
					state.inside(Alias, "../outside")

	def test_progress_single_read_and_late_direct_edit_conflict(self):
		First = state.save_progress(self.Project, "original", "missing")
		Progress = self.Project / "RESUME.md"
		Original = state.preserve_blob
		def edit_after_archive(Item, Data):
			Original(Item, Data)
			Progress.write_bytes(b"new human discovery")
		with patch.object(state, "preserve_blob", side_effect=edit_after_archive):
			with self.assertRaises(ValueError):
				state.save_progress(self.Project, "agent replacement", First["sha256"])
		self.assertEqual(Progress.read_bytes(), b"new human discovery")
		Archive = self.Project / ".research-state/progress" / (First["sha256"] + ".md")
		self.assertEqual(state.digest(Archive.read_bytes()), First["sha256"])
		Progress.write_bytes(b"original")
		Read = state.read_optional
		Changed = []
		def edit_after_read(Item):
			Data = Read(Item)
			if(Item == Progress and not Changed):
				Changed.append(True)
				Progress.write_bytes(b"second human discovery")
			return Data
		with patch.object(state, "read_optional", side_effect=edit_after_read):
			with self.assertRaises(ValueError):
				state.save_progress(self.Project, "agent replacement", First["sha256"])
		self.assertEqual(Progress.read_bytes(), b"second human discovery")
		self.assertEqual(Archive.read_bytes(), b"original")

	def test_changed_inputs_before_dispatch_prevent_the_child(self):
		Create = state.create_job
		def change_after_request(*Arguments):
			Result = Create(*Arguments)
			(self.Project / "input.txt").write_text("v2")
			return Result
		with patch.object(state, "create_job", side_effect=change_after_request):
			self.start("pre-dispatch", "from pathlib import Path; Path('effect').write_text(Path('input.txt').read_text())")
		Record = self.wait_job("pre-dispatch")
		self.assertEqual(Record["state"], "INPUTS_CHANGED")
		self.assertFalse((self.Project / "effect").exists())
		(self.Project / "input.txt").write_text("v1")
		self.assertFalse(state.job_status(self.Project, "pre-dispatch")["recorded_inputs_match_current"])

	def test_observed_input_change_cannot_be_cleared_by_restoring_request(self):
		self.start("during-run", "from pathlib import Path; Path('input.txt').write_text('v2'); print(Path('input.txt').read_text())")
		Record = self.wait_job("during-run")
		self.assertEqual(Record["state"], "SUCCEEDED")
		(self.Project / "input.txt").write_text("v1")
		Record = state.job_status(self.Project, "during-run")
		self.assertTrue(Record["inputs_match"])
		self.assertTrue(Record["input_mismatch_detected"])
		self.assertFalse(Record["recorded_inputs_match_current"])
		self.assertIsNone(Record["result_applies_to_current_inputs"])
		self.start("transient-input", "from pathlib import Path; p=Path('input.txt'); p.write_text('v2'); print(p.read_text()); p.write_text('v1')")
		Transient = self.wait_job("transient-input")
		self.assertTrue(Transient["recorded_inputs_match_current"])
		self.assertIsNone(Transient["result_applies_to_current_inputs"])

	def test_missing_hashes_or_request_corruption_cannot_pass_inspection(self):
		self.start("damaged", "print('verified output')")
		self.wait_job("damaged")
		PathValue = state.job_path(self.Project, "damaged")
		Record = state.load_job(self.Project, "damaged")
		Original = PathValue.read_bytes()
		Record.pop("stdout_sha256")
		PathValue.write_bytes(state.json_bytes(Record))
		self.assertEqual(len(state.inspect_project(self.Project)["problems"]), 1)
		PathValue.write_bytes(Original)
		Record = state.load_job(self.Project, "damaged")
		Record["inputs"] = {}
		PathValue.write_bytes(state.json_bytes(Record))
		with self.assertRaises(ValueError):
			state.job_status(self.Project, "damaged")

	def test_external_result_is_hashed_from_the_archived_read(self):
		state.register_external(self.Project, "transport", "provider", "key")
		Source = self.Project / "response.json"
		Source.write_bytes(b"first observed response")
		Read = state.read_optional
		def replace_transport(Item):
			Data = Read(Item)
			if(Item == Source):
				Source.write_bytes(b"later transport response")
			return Data
		with patch.object(state, "read_optional", side_effect=replace_transport):
			Record = state.record_result(self.Project, "transport", "SUCCEEDED", "response.json")
		self.assertTrue(Record["result_evidence_matches"])
		self.assertEqual((self.Project / Record["result"]).read_bytes(), b"first observed response")
		self.assertEqual(state.digest((self.Project / Record["result"]).read_bytes()), Record["result_sha256"])

	def test_post_launch_record_failure_is_unknown_with_child_evidence(self):
		Code = "from pathlib import Path; import time; time.sleep(.15); Path('real-effect').write_text('once')"
		state.create_job(self.Project, "bookkeeping", dict(kind="local", command=[sys.executable, "-c", Code], cwd=".", inputs=state.input_snapshot(self.Project, ["input.txt"]), timeout_seconds=None))
		Update = state.update_job
		Triggered = []
		Children = []
		Popen = state.subprocess.Popen
		def capture_child(*Arguments, **Options):
			Child = Popen(*Arguments, **Options)
			Children.append(Child)
			return Child
		def fail_child_record(Root, JobId, Changes):
			if("child_pid" in Changes and not Triggered):
				Triggered.append(True)
				raise OSError("injected nonrecoverable bookkeeping error after Popen")
			return Update(Root, JobId, Changes)
		with patch.object(state, "update_job", side_effect=fail_child_record), patch.object(state.subprocess, "Popen", side_effect=capture_child):
			state.run_worker(self.Project, "bookkeeping")
		for Child in Children:
			Child.wait(timeout=5)
		Record = state.job_status(self.Project, "bookkeeping")
		self.assertEqual(Record["state"], "UNKNOWN")
		self.assertIn("child_pid", Record)
		self.assertIn("recovery_error_log", Record)
		self.assertEqual((self.Project / "real-effect").read_text(), "once")
		self.assertFalse(self.start("bookkeeping", Code)["dispatched"])

	def test_short_persistence_conflict_is_retried_without_redispatch(self):
		self.start("retry", "print('once')")
		self.wait_job("retry")
		Replace = state.os.replace
		Calls = []
		def fail_once(*Arguments):
			Calls.append(True)
			if(len(Calls) == 1):
				raise PermissionError("temporary reader sharing conflict")
			return Replace(*Arguments)
		with patch.object(state.os, "replace", side_effect=fail_once):
			state.update_job(self.Project, "retry", dict(note="saved after sharing conflict"))
		self.assertEqual(state.job_status(self.Project, "retry")["note"], "saved after sharing conflict")
		self.assertEqual(len(Calls), 2)

	def test_archive_inspection_detects_corrupted_checkpoint_and_history(self):
		state.save_progress(self.Project, "saved research", "missing")
		Checkpoint = state.checkpoint(self.Project, Inputs=["input.txt"])
		self.assertFalse(state.inspect_project(self.Project, Archives=True)["problems"])
		Path(Checkpoint["snapshot"]).write_bytes(b"{")
		History = next((self.Project / ".research-state/progress").glob("*.md"))
		History.write_bytes(b"changed history")
		self.assertEqual(len(state.inspect_project(self.Project, Archives=True)["problems"]), 2)
		self.assertEqual((self.Project / "RESUME.md").read_text(), "saved research")

	@unittest.skipUnless(os.name == "nt", "native Windows reader sharing")
	def test_native_reader_does_not_strand_worker(self):
		Create = state.create_job
		Timers = []
		def hold_reader(*Arguments):
			Result = Create(*Arguments)
			Handle = state.job_path(self.Project, "held-reader").open("rb")
			Timer = threading.Timer(.35, Handle.close)
			Timer.start()
			Timers.append(Timer)
			return Result
		with patch.object(state, "create_job", side_effect=hold_reader):
			self.start("held-reader", "print('finished')")
		self.assertEqual(self.wait_job("held-reader")["state"], "SUCCEEDED")
		for Timer in Timers:
			Timer.join()

	@unittest.skipUnless(os.name == "nt", "native Windows exit 259")
	def test_native_exit_259_is_not_alive(self):
		with subprocess.Popen([sys.executable, "-c", "raise SystemExit(259)"]) as Child:
			self.assertEqual(Child.wait(timeout=5), 259)
			self.assertIsNone(state.process_identity(Child.pid))


if(__name__ == "__main__"):
	unittest.main()
