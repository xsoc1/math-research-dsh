#!/usr/bin/env python3
"""Save free-form research progress and reconcile durable, input-bound jobs.

No command submits a remote request or resumes an unknown action automatically.
Local jobs run in a detached supervisor; their full logs survive this client.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

UNCHECKED = object()


def retry_io(Action):
	Deadline = time.monotonic() + 5
	while(True):
		try:
			return Action()
		except OSError as Error:
			Transient = isinstance(Error, (PermissionError, BlockingIOError)) or Error.errno in (errno.EAGAIN, errno.EBUSY, getattr(errno, "ENODATA", 61))
			if(not Transient or time.monotonic() >= Deadline):
				raise
			time.sleep(0.025)


def read_optional(Item):
	try:
		return retry_io(Item.read_bytes)
	except FileNotFoundError:
		return None


def utc_now():
	return datetime.now(timezone.utc).isoformat()


def digest(Data):
	return hashlib.sha256(Data).hexdigest()


def json_bytes(Data):
	return (json.dumps(Data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def inside(Root, Name):
	Root = Path(Root).resolve()
	Candidate = (Root / Name).resolve()
	if(not Candidate.is_relative_to(Root)):
		raise ValueError("path escapes project")
	return Candidate


def file_hash(Item):
	Data = read_optional(Item)
	return digest(Data) if Data is not None else None


def atomic_write(Item, Data, ExpectedData=UNCHECKED):
	Item.parent.mkdir(parents=True, exist_ok=True)
	Fd, Name = tempfile.mkstemp(prefix="." + Item.name + ".", dir=Item.parent)
	try:
		with os.fdopen(Fd, "wb") as Stream:
			Stream.write(Data)
			Stream.flush()
			os.fsync(Stream.fileno())
		def replace_current():
			if(ExpectedData is not UNCHECKED and read_optional(Item) != ExpectedData):
				raise ValueError("file changed during save; merge the current contents")
			os.replace(Name, Item)
		retry_io(replace_current)
	finally:
		Path(Name).unlink(missing_ok=True)


def preserve_blob(Item, Data):
	if(Item.exists()):
		if(Item.read_bytes() != Data):
			raise ValueError("saved immutable content changed: " + str(Item))
	else:
		atomic_write(Item, Data)


@contextmanager
def writer_lock(Item):
	Item.parent.mkdir(parents=True, exist_ok=True)
	with Item.open("a+b") as Stream:
		Stream.seek(0)
		if(os.name == "nt"):
			import msvcrt
			if(Item.stat().st_size == 0):
				Stream.write(b"0")
				Stream.flush()
			Stream.seek(0)
			msvcrt.locking(Stream.fileno(), msvcrt.LK_NBLCK, 1)
		else:
			import fcntl
			fcntl.flock(Stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
		try:
			yield
		finally:
			Stream.seek(0)
			if(os.name == "nt"):
				msvcrt.locking(Stream.fileno(), msvcrt.LK_UNLCK, 1)
			else:
				fcntl.flock(Stream, fcntl.LOCK_UN)


def storage(Root):
	return inside(Root, ".research-state")


def progress_path(Root, Requested=None):
	if(Requested):
		return inside(Root, Requested)
	for Name in ("state/RESUME.md", "RESUME.md", "whiteboard.md", "research_map.md"):
		Item = inside(Root, Name)
		if(Item.is_file()):
			return Item
	return inside(Root, "RESUME.md")


def input_snapshot(Root, Names, Require=True):
	Root = Path(Root).resolve()
	Snapshot = {}
	for Name in sorted(set(Names)):
		if(".." in Path(Name).parts):
			raise ValueError("input paths containing '..' are ambiguous across symlinks; use an explicit in-project path")
		Alias = Root / Name
		if(not Alias.is_relative_to(Root)):
			raise ValueError("input path escapes project")
		Item = inside(Root, Name)
		Hash = file_hash(Item)
		if(Require and Hash is None):
			raise ValueError("input file missing: " + str(Name))
		Snapshot[Alias.relative_to(Root).as_posix()] = dict(sha256=Hash, resolved_path=Item.relative_to(Root).as_posix())
	return Snapshot


def save_progress(Project, Text, ExpectedHash, Progress=None):
	Root = Path(Project).resolve()
	Item = progress_path(Root, Progress)
	Data = Text.encode("utf-8")
	NewHash = digest(Data)
	with writer_lock(storage(Root) / "progress.lock"):
		OldData = read_optional(Item)
		OldHash = digest(OldData) if OldData is not None else None
		if(OldHash == NewHash):
			return dict(status="UNCHANGED", path=str(Item), sha256=NewHash)
		if(OldHash != (None if ExpectedHash == "missing" else ExpectedHash)):
			raise ValueError("progress changed; read the current file before merging your notes")
		if(OldHash):
			History = storage(Root) / "progress" / (OldHash + ".md")
			preserve_blob(History, OldData)
		atomic_write(Item, Data, OldData)
	return dict(status="SAVED", path=str(Item), sha256=NewHash, previous_sha256=OldHash)


def checkpoint(Project, Progress=None, Inputs=()):
	Root = Path(Project).resolve()
	Item = progress_path(Root, Progress)
	with writer_lock(storage(Root) / "progress.lock"):
		if(not Item.is_file()):
			raise ValueError("write the current research progress before taking a snapshot")
		Data = Item.read_bytes()
		NoteHash = digest(Data)
		History = storage(Root) / "progress" / (NoteHash + ".md")
		preserve_blob(History, Data)
		Record = dict(schema="research-checkpoint/v2", progress=Item.relative_to(Root).as_posix(),
			progress_sha256=NoteHash, inputs=input_snapshot(Root, Inputs))
		SnapshotHash = digest(json_bytes(Record))
		Target = storage(Root) / "checkpoints" / (SnapshotHash + ".json")
		preserve_blob(Target, json_bytes(Record))
	return dict(status="SAVED", snapshot=str(Target), sha256=SnapshotHash,
		resume="Read current progress and reconcile job identities; this snapshot does not overwrite newer notes.")


def process_identity(Pid):
	if(os.name == "nt"):
		import ctypes
		from ctypes import wintypes
		Kernel = ctypes.WinDLL("kernel32", use_last_error=True)
		Kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
		Kernel.OpenProcess.restype = wintypes.HANDLE
		Kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
		Kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
		Kernel.CloseHandle.argtypes = [wintypes.HANDLE]
		Handle = Kernel.OpenProcess(0x1000, False, Pid)
		if(not Handle):
			return None
		try:
			Times = [wintypes.FILETIME() for _ in range(4)]
			Exit = wintypes.DWORD()
			if(not Kernel.GetExitCodeProcess(Handle, ctypes.byref(Exit)) or Exit.value != 259):
				return None
			if(not Kernel.GetProcessTimes(Handle, *[ctypes.byref(Time) for Time in Times])):
				return None
			if(Times[1].dwHighDateTime or Times[1].dwLowDateTime):
				return None
			return str((Times[0].dwHighDateTime << 32) | Times[0].dwLowDateTime)
		finally:
			Kernel.CloseHandle(Handle)
	try:
		Stat = Path(f"/proc/{Pid}/stat").read_text()
		Fields = Stat[Stat.rfind(")") + 2:].split()
		if(Fields[0] == "Z"):
			return None
		BootId = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
		return BootId + ":" + Fields[19]
	except (OSError, IndexError):
		return None


def job_path(Root, JobId):
	if(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", JobId)):
		raise ValueError("invalid job id")
	return storage(Root) / "jobs" / (JobId + ".json")


def require_hash(Value):
	if(not isinstance(Value, str) or not re.fullmatch(r"[0-9a-f]{64}", Value)):
		raise ValueError("missing or invalid evidence digest")


def validate_snapshot(Root, Snapshot, AllowMissing=False):
	if(not isinstance(Snapshot, dict)):
		raise ValueError("invalid input snapshot")
	for Name, Binding in Snapshot.items():
		if(not isinstance(Name, str) or Path(Name).is_absolute() or ".." in Path(Name).parts or not isinstance(Binding, dict)):
			raise ValueError("invalid input identity")
		Resolved = Binding.get("resolved_path")
		if(not isinstance(Resolved, str) or Path(Resolved).is_absolute() or ".." in Path(Resolved).parts):
			raise ValueError("invalid resolved input identity")
		inside(Root, Name)
		inside(Root, Resolved)
		if(not (AllowMissing and Binding.get("sha256") is None)):
			require_hash(Binding.get("sha256"))


def validate_job(Root, JobId, Record):
	if(not isinstance(Record, dict) or Record.get("schema") != "research-job/v2" or Record.get("job_id") != JobId):
		raise ValueError("invalid job schema or identity")
	Kind = Record.get("kind")
	Keys = ("kind", "command", "cwd", "inputs", "timeout_seconds") if Kind == "local" else ("kind", "provider", "request_key", "inputs")
	if(Kind not in ("local", "external") or any(Key not in Record for Key in Keys)):
		raise ValueError("incomplete job request")
	Spec = {Key: Record[Key] for Key in Keys}
	require_hash(Record.get("request_sha256"))
	if(digest(json_bytes(Spec)) != Record["request_sha256"]):
		raise ValueError("job request fingerprint changed")
	validate_snapshot(Root, Record["inputs"])
	States = ("STARTING", "RUNNING", "UNKNOWN", "SUBMITTED", "SUCCEEDED", "FAILED", "FAILED_TO_START", "TIMEOUT", "INPUTS_CHANGED")
	if(Record.get("state") not in States):
		raise ValueError("unknown job state")
	if(Kind == "local"):
		if(not isinstance(Record["command"], list) or not Record["command"] or any(not isinstance(Item, str) for Item in Record["command"])):
			raise ValueError("invalid command identity")
		if(not isinstance(Record["cwd"], str)):
			raise ValueError("invalid working directory")
		inside(Root, Record["cwd"])
		Timeout = Record["timeout_seconds"]
		if(Timeout is not None and (not isinstance(Timeout, (int, float)) or not math.isfinite(Timeout) or Timeout <= 0)):
			raise ValueError("invalid recorded timeout")
		if(Record["state"] == "FAILED_TO_START" and Record.get("child_pid")):
			raise ValueError("a launched child cannot be recorded as not started")
	else:
		if(any(not isinstance(Record[Key], str) or not Record[Key] for Key in ("provider", "request_key"))):
			raise ValueError("invalid provider request identity")
	for Key in ("supervisor_pid", "child_pid"):
		if(Key in Record and (not isinstance(Record[Key], int) or Record[Key] <= 0)):
			raise ValueError("invalid process identity")
	Required = ("stdout", "stderr") if Kind == "local" else ("result",)
	if(Record["state"] in ("SUCCEEDED", "FAILED", "TIMEOUT")):
		for Key in Required:
			if(not isinstance(Record.get(Key), str)):
				raise ValueError("terminal job is missing " + Key + " evidence")
			inside(Root, Record[Key])
			require_hash(Record.get(Key + "_sha256"))
	if(Record["state"] == "SUCCEEDED" and Kind == "local" and Record.get("exit_code") != 0):
		raise ValueError("success requires an actual zero exit code")
	for Key in ("execution_inputs_before", "execution_inputs_after"):
		if(Key in Record):
			validate_snapshot(Root, Record[Key], AllowMissing=True)
	if("observations" in Record):
		if(not isinstance(Record["observations"], list)):
			raise ValueError("invalid observations container")
		for Observation in Record["observations"]:
			if(not isinstance(Observation, dict) or Observation.get("state") not in ("SUCCEEDED", "FAILED", "UNKNOWN")):
				raise ValueError("invalid observation state")
			require_hash(Observation.get("sha256"))
			Name = Observation.get("path")
			if(not isinstance(Name, str) or not Name or Path(Name).is_absolute() or ".." in Path(Name).parts):
				raise ValueError("invalid observation evidence path")
			inside(Root, Name)
	return Record


def load_job(Root, JobId):
	Data = retry_io(lambda: job_path(Root, JobId).read_bytes())
	return validate_job(Root, JobId, json.loads(Data.decode("utf-8")))


def update_job(Root, JobId, Changes):
	Item = job_path(Root, JobId)
	def update_locked():
		with writer_lock(Item.with_suffix(".lock")):
			Record = load_job(Root, JobId)
			Record.update(Changes, updated_at=utc_now())
			validate_job(Root, JobId, Record)
			atomic_write(Item, json_bytes(Record))
			return Record
	return retry_io(update_locked)


def job_status(Project, JobId):
	Root = Path(Project).resolve()
	Record = load_job(Root, JobId)
	Current = input_snapshot(Root, Record["inputs"], Require=False)
	Record["inputs_match"] = Current == Record["inputs"]
	Record["changed_inputs"] = [Name for Name in Current if Current[Name] != Record["inputs"][Name]]
	EvidenceMatches = True
	for Key in ("stdout", "stderr", "result"):
		if(Record.get(Key + "_sha256")):
			EvidenceMatches = EvidenceMatches and file_hash(inside(Root, Record[Key])) == Record[Key + "_sha256"]
	Record["result_evidence_matches"] = EvidenceMatches
	Observed = Record.get("execution_inputs_before") == Record["inputs"] and Record.get("execution_inputs_after") == Record["inputs"] and not Record.get("input_mismatch_detected", False)
	Record["observed_inputs_match_request"] = Observed if Record["kind"] == "local" else None
	Record["recorded_inputs_match_current"] = Record["state"] == "SUCCEEDED" and Record["inputs_match"] and EvidenceMatches and (Observed or Record["kind"] == "external")
	Record["result_applies_to_current_inputs"] = None
	Record["applicability_scope"] = "Recorded hashes and observed boundaries only. Arbitrary commands and external observations do not certify immutable execution inputs or mathematical applicability."
	Record["mathematical_verdict"] = "NOT_INFERRED_FROM_JOB_STATUS"
	if(Record["kind"] == "local"):
		Record["supervisor_log"] = job_path(Root, JobId).with_suffix(".supervisor.log").relative_to(Root).as_posix()
		ErrorLog = job_path(Root, JobId).with_suffix(".recovery-error.log")
		if(ErrorLog.is_file()):
			Record["recovery_error_log"] = ErrorLog.relative_to(Root).as_posix()
	if(Record["kind"] == "local" and Record["state"] in ("STARTING", "RUNNING", "UNKNOWN")):
		Pid = Record.get("supervisor_pid")
		Identity = process_identity(Pid) if Pid else None
		Expected = Record.get("supervisor_identity")
		Record["supervisor_alive"] = bool(Expected and Identity == Expected)
		if(not Record["supervisor_alive"]):
			Child = Record.get("child_pid")
			ChildIdentity = process_identity(Child) if Child else None
			ChildAlive = bool(Record.get("child_identity") and ChildIdentity == Record["child_identity"])
			Record["observed_state"] = "RUNNING_UNSUPERVISED" if ChildAlive else "UNKNOWN"
			Record["next_step"] = "Inspect saved logs and the original process; do not infer completion or redispatch automatically."
	return Record


def create_job(Root, JobId, Spec):
	Item = job_path(Root, JobId)
	Fingerprint = digest(json_bytes(Spec))
	with writer_lock(Item.with_suffix(".lock")):
		if(Item.exists()):
			Existing = load_job(Root, JobId)
			if(Existing["request_sha256"] != Fingerprint):
				raise ValueError("job id already belongs to different inputs or a different request")
			return Existing, False
		Record = dict(Spec, schema="research-job/v2", job_id=JobId,
			request_sha256=Fingerprint, created_at=utc_now(), state="STARTING" if Spec["kind"] == "local" else "UNKNOWN")
		validate_job(Root, JobId, Record)
		atomic_write(Item, json_bytes(Record))
		return Record, True


def start_job(Project, JobId, Command, Inputs=(), Cwd=".", Timeout=None):
	Root = Path(Project).resolve()
	if(not Command or (Timeout is not None and (not math.isfinite(Timeout) or Timeout <= 0))):
		raise ValueError("a command and an optional positive timeout are required")
	RunDir = inside(Root, Cwd)
	if(not RunDir.is_dir()):
		raise ValueError("job working directory missing")
	Spec = dict(kind="local", command=list(Command), cwd=RunDir.relative_to(Root).as_posix(),
		inputs=input_snapshot(Root, Inputs), timeout_seconds=Timeout)
	Record, Created = create_job(Root, JobId, Spec)
	if(not Created):
		return dict(status="EXISTING", dispatched=False, job=job_status(Root, JobId))
	LaunchLog = job_path(Root, JobId).with_suffix(".supervisor.log")
	Options = dict(start_new_session=True) if os.name != "nt" else dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
	try:
		with LaunchLog.open("ab") as Log:
			Process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_worker",
				"--project", str(Root), "--job-id", JobId], cwd=Root, stdin=subprocess.DEVNULL,
				stdout=Log, stderr=Log, close_fds=True, **Options)
		threading.Thread(target=Process.wait, daemon=True).start()
		# The supervisor owns subsequent writes, including its process identity.
		return dict(status="DISPATCHED", dispatched=True, job_id=JobId, supervisor_pid=Process.pid)
	except OSError as Error:
		update_job(Root, JobId, dict(state="FAILED_TO_START", error=str(Error)))
		raise


def supervise_child(Process, Deadline, Outcome):
	try:
		try:
			ExitCode = Process.wait(timeout=max(0, Deadline - time.monotonic()) if Deadline is not None else None)
			Outcome.update(state="SUCCEEDED" if ExitCode == 0 else "FAILED", exit_code=ExitCode, descendants_may_still_run=False)
		except subprocess.TimeoutExpired:
			Process.kill()
			Outcome.update(state="TIMEOUT", exit_code=Process.wait(), descendants_may_still_run=True)
	except OSError as Error:
		Outcome["error"] = Error


def run_worker(Project, JobId):
	Root = Path(Project).resolve()
	Item = job_path(Root, JobId)
	with writer_lock(Item.with_suffix(".runner.lock")):
		Record = load_job(Root, JobId)
		if(Record["kind"] != "local" or Record["state"] != "STARTING"):
			return
		Stdout = Item.with_suffix(".stdout.log")
		Stderr = Item.with_suffix(".stderr.log")
		Process = None
		ChildIdentity = None
		try:
			Before = input_snapshot(Root, Record["inputs"], Require=False)
			update_job(Root, JobId, dict(state="RUNNING", supervisor_pid=os.getpid(),
				supervisor_identity=process_identity(os.getpid()), started_at=utc_now(),
				stdout=Stdout.relative_to(Root).as_posix(), stderr=Stderr.relative_to(Root).as_posix(),
				execution_inputs_before=Before, input_mismatch_detected=Before != Record["inputs"]))
			if(Before != Record["inputs"]):
				update_job(Root, JobId, dict(state="INPUTS_CHANGED", completed_at=utc_now(), reason="declared inputs changed before child dispatch"))
				return
			with Stdout.open("wb") as Out, Stderr.open("wb") as Err:
				try:
					Process = subprocess.Popen(Record["command"], cwd=inside(Root, Record["cwd"]),
						stdin=subprocess.DEVNULL, stdout=Out, stderr=Err)
				except OSError as Error:
					update_job(Root, JobId, dict(state="FAILED_TO_START", error=str(Error), completed_at=utc_now()))
					return
				Deadline = time.monotonic() + Record["timeout_seconds"] if Record["timeout_seconds"] is not None else None
				Outcome = {}
				Watcher = threading.Thread(target=supervise_child, args=(Process, Deadline, Outcome), daemon=Deadline is None)
				Watcher.start()
				ChildIdentity = process_identity(Process.pid)
				print(json.dumps(dict(event="child_started", job_id=JobId, child_pid=Process.pid, child_identity=ChildIdentity)), flush=True)
				update_job(Root, JobId, dict(child_pid=Process.pid, child_identity=ChildIdentity))
				Watcher.join()
				if("error" in Outcome):
					raise Outcome["error"]
			After = input_snapshot(Root, Record["inputs"], Require=False)
			update_job(Root, JobId, dict(**Outcome, completed_at=utc_now(),
				stdout_sha256=file_hash(Stdout), stderr_sha256=file_hash(Stderr),
				execution_inputs_after=After,
				input_mismatch_detected=Before != Record["inputs"] or After != Record["inputs"]))
		except (OSError, ValueError) as Error:
			Failure = dict(state="UNKNOWN", error=str(Error), recovery_error_at=utc_now(), child_started=Process is not None)
			if(Process is not None):
				Failure.update(child_pid=Process.pid, child_identity=ChildIdentity)
			print(json.dumps(dict(event="persistence_or_supervision_error", job_id=JobId, **Failure)), flush=True)
			try:
				atomic_write(Item.with_suffix(".recovery-error.log"), json_bytes(Failure))
				update_job(Root, JobId, Failure)
			except (OSError, ValueError) as RecoveryError:
				print(json.dumps(dict(event="reconciliation_required", error=str(RecoveryError))), flush=True)


def register_external(Project, JobId, Provider, RequestKey, Inputs=(), ExternalId=None):
	Root = Path(Project).resolve()
	Spec = dict(kind="external", provider=Provider, request_key=RequestKey,
		inputs=input_snapshot(Root, Inputs))
	Record, Created = create_job(Root, JobId, Spec)
	if(ExternalId):
		Item = job_path(Root, JobId)
		with writer_lock(Item.with_suffix(".lock")):
			Record = load_job(Root, JobId)
			if(Record.get("external_id") not in (None, ExternalId)):
				raise ValueError("external identity cannot be replaced")
			Record.update(external_id=ExternalId, updated_at=utc_now(),
				state="SUBMITTED" if Record["state"] == "UNKNOWN" else Record["state"])
			atomic_write(Item, json_bytes(Record))
	return dict(status="REGISTERED" if Created else "EXISTING", dispatched=False,
		job=Record, next_step="Use the provider's original job or request key to reconcile. Unknown submission is not permission to resubmit.")


def record_result(Project, JobId, State, ResultFile):
	Root = Path(Project).resolve()
	if(State not in ("SUCCEEDED", "FAILED", "UNKNOWN")):
		raise ValueError("invalid externally observed state")
	Item = job_path(Root, JobId)
	with writer_lock(Item.with_suffix(".lock")):
		Record = load_job(Root, JobId)
		if(Record["kind"] != "external"):
			raise ValueError("only the local supervisor may report a local job result")
		Result = inside(Root, ResultFile)
		Data = read_optional(Result)
		if(Data is None):
			raise ValueError("result evidence missing")
		Hash = digest(Data)
		if(Record["state"] in ("SUCCEEDED", "FAILED") and (Record.get("result_sha256") != Hash or Record["state"] != State)):
			raise ValueError("a recorded result cannot be overwritten; retain contradictory evidence separately")
		Archive = storage(Root) / "results" / Hash
		preserve_blob(Archive, Data)
		Observation = dict(state=State, sha256=Hash, path=Archive.relative_to(Root).as_posix())
		History = Record.setdefault("observations", [])
		if(Observation not in History):
			History.append(Observation)
		Record.update(state=State, result_sha256=Hash, result=Archive.relative_to(Root).as_posix(),
			result_source=Result.relative_to(Root).as_posix(), completed_at=utc_now())
		validate_job(Root, JobId, Record)
		atomic_write(Item, json_bytes(Record))
	return job_status(Root, JobId)


def inspect_archives(Root):
	Problems = []
	Checked = 0
	for Folder, Suffix in (("progress", ".md"), ("results", ""), ("checkpoints", ".json")):
		for Item in sorted((storage(Root) / Folder).glob("*")):
			if(not Item.is_file() or Item.name.startswith(".")):
				continue
			try:
				Hash = Item.stem if Suffix else Item.name
				require_hash(Hash)
				Data = retry_io(Item.read_bytes)
				if(digest(Data) != Hash):
					raise ValueError("archive content does not match its identity")
				if(Folder == "checkpoints"):
					Record = json.loads(Data.decode("utf-8"))
					if(Record.get("schema") != "research-checkpoint/v2"):
						raise ValueError("unknown checkpoint schema")
					require_hash(Record.get("progress_sha256"))
					inside(Root, Record["progress"])
					validate_snapshot(Root, Record["inputs"])
					Saved = storage(Root) / "progress" / (Record["progress_sha256"] + ".md")
					if(file_hash(Saved) != Record["progress_sha256"]):
						raise ValueError("checkpoint progress is missing or changed")
				Checked += 1
			except (OSError, ValueError, KeyError, TypeError, AttributeError) as Error:
				Problems.append(dict(path=str(Item), error=str(Error)))
	return dict(checked=Checked, problems=Problems, restored=False)


def inspect_project(Project, Progress=None, Archives=False):
	Root = Path(Project).resolve()
	Item = progress_path(Root, Progress)
	Jobs = []
	Problems = []
	for JobFile in sorted((storage(Root) / "jobs").glob("*.json")):
		try:
			Jobs.append(job_status(Root, JobFile.stem))
		except (ValueError, OSError, KeyError, TypeError) as Error:
			Problems.append(dict(path=str(JobFile), error=str(Error)))
	History = inspect_archives(Root) if Archives else dict(checked=None, problems=[], restored=False)
	Problems.extend(History["problems"])
	if(Archives):
		for Job in Jobs:
			for Observation in Job.get("observations", []):
				try:
					require_hash(Observation.get("sha256"))
					if(file_hash(inside(Root, Observation["path"])) != Observation["sha256"]):
						raise ValueError("historical observation evidence changed")
				except (OSError, ValueError, KeyError, TypeError, AttributeError) as Error:
					Problems.append(dict(job_id=Job["job_id"], error=str(Error)))
	return dict(schema="research-state/v2", progress=str(Item), progress_sha256=file_hash(Item),
		jobs=Jobs, problems=Problems, archives=History, dispatched=False,
		next_step="Read current progress; choose useful work. Reconcile only actions whose outcome is unknown.")


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Sub = Parser.add_subparsers(dest="command", required=True)
	for Name in ("inspect", "save", "checkpoint", "start", "status", "register-external", "record-result", "_worker"):
		Part = Sub.add_parser(Name)
		Part.add_argument("--project", required=True)
		if(Name in ("inspect", "save", "checkpoint")):
			Part.add_argument("--progress")
		if(Name == "inspect"):
			Part.add_argument("--archives", action="store_true", help="also check saved history and checkpoint identities without restoring anything")
		if(Name == "save"):
			Part.add_argument("--text-file", required=True)
			Part.add_argument("--expected-sha256", required=True, help="Current hash, or 'missing' for a new progress file")
		if(Name in ("checkpoint", "start", "register-external")):
			Part.add_argument("--input", action="append", default=[])
		if(Name in ("start", "status", "register-external", "record-result", "_worker")):
			Part.add_argument("--job-id", required=True)
		if(Name == "start"):
			Part.add_argument("--cwd", default=".")
			Part.add_argument("--timeout", type=float)
			Part.add_argument("argv", nargs=argparse.REMAINDER)
		if(Name == "register-external"):
			Part.add_argument("--provider", required=True)
			Part.add_argument("--request-key", required=True)
			Part.add_argument("--external-id")
		if(Name == "record-result"):
			Part.add_argument("--state", choices=("SUCCEEDED", "FAILED", "UNKNOWN"), required=True)
			Part.add_argument("--result-file", required=True)
	Args = Parser.parse_args()
	try:
		if(Args.command == "inspect"):
			Result = inspect_project(Args.project, Args.progress, Args.archives)
		elif(Args.command == "save"):
			Result = save_progress(Args.project, Path(Args.text_file).read_text(encoding="utf-8"), Args.expected_sha256, Args.progress)
		elif(Args.command == "checkpoint"):
			Result = checkpoint(Args.project, Args.progress, Args.input)
		elif(Args.command == "start"):
			Command = Args.argv[1:] if Args.argv[:1] == ["--"] else Args.argv
			Result = start_job(Args.project, Args.job_id, Command, Args.input, Args.cwd, Args.timeout)
		elif(Args.command == "status"):
			Result = job_status(Args.project, Args.job_id)
		elif(Args.command == "register-external"):
			Result = register_external(Args.project, Args.job_id, Args.provider, Args.request_key, Args.input, Args.external_id)
		elif(Args.command == "record-result"):
			Result = record_result(Args.project, Args.job_id, Args.state, Args.result_file)
		else:
			run_worker(Args.project, Args.job_id)
			return 0
		print(json.dumps(Result, ensure_ascii=False, sort_keys=True))
		return 0
	except (ValueError, OSError, KeyError, TypeError) as Error:
		print(json.dumps(dict(status="ERROR", error=str(Error), dispatched=False)))
		return 1


if(__name__ == "__main__"):
	raise SystemExit(main())
