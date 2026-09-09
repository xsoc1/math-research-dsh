#!/usr/bin/env python3
"""Protect concurrent builds using ownership and process identity, not attempt caps."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from lean_runtime import now_iso, process_identity

DEFAULT_MAX_ATTEMPTS = 0
DEFAULT_WINDOW_MINUTES = 10
DEFAULT_LOCK_MINUTES = 30


@contextmanager
def control_lock(StateDir):
	"""Serialize stale-lock replacement and release without stale lock-file races."""
	with (StateDir / "build_guard.control").open("a+b") as Stream:
		if(os.name == "nt"):
			import msvcrt
			Stream.seek(0)
			if(not Stream.read(1)):
				Stream.write(b"0")
				Stream.flush()
			Stream.seek(0)
			msvcrt.locking(Stream.fileno(), msvcrt.LK_LOCK, 1)
		else:
			import fcntl
			fcntl.flock(Stream.fileno(), fcntl.LOCK_EX)
		try:
			yield
		finally:
			if(os.name == "nt"):
				Stream.seek(0)
				msvcrt.locking(Stream.fileno(), msvcrt.LK_UNLCK, 1)
			else:
				fcntl.flock(Stream.fileno(), fcntl.LOCK_UN)


def acquire(Root, InputHash="unspecified", StateDir=None, OwnerPid=None):
	StateDir = Path(StateDir) if StateDir else Path(Root) / ".lake"
	StateDir.mkdir(parents=True, exist_ok=True)
	with control_lock(StateDir):
		return acquire_locked(Root, InputHash, StateDir, OwnerPid)


def acquire_locked(Root, InputHash="unspecified", StateDir=None, OwnerPid=None):
	StateDir = Path(StateDir) if StateDir else Path(Root) / ".lake"
	StateDir.mkdir(parents=True, exist_ok=True)
	Lock = StateDir / "build_guard.lock"
	OwnerPid = OwnerPid or os.getpid()
	Record = {"token": uuid.uuid4().hex, "owner_pid": OwnerPid, "process_identity": process_identity(OwnerPid), "input_sha256": InputHash, "started_at": now_iso()}
	for Attempt in range(2):
		try:
			Descriptor = os.open(Lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
			with os.fdopen(Descriptor, "w", encoding="utf-8") as Stream:
				json.dump(Record, Stream, indent="\t")
				Stream.write("\n")
			return {"status": "acquired", "lock": str(Lock), **Record}
		except FileExistsError:
			try:
				Previous = json.loads(Lock.read_text(encoding="utf-8"))
				Identity = process_identity(int(Previous["owner_pid"]))
				if(Identity == "unknown" or Previous.get("process_identity") in (None, "unknown")):
					return {"status": "conflict", "reason": "owner identity cannot be established", "lock": str(Lock)}
				if(Identity is not None and Identity == Previous["process_identity"]):
					return {"status": "conflict", "reason": "owner process is still active", "owner": Previous}
				# Recheck the bytes before retiring a lock from a dead or reused PID.
				if(json.loads(Lock.read_text(encoding="utf-8")) != Previous):
					continue
				Retired = StateDir / ("build_guard.stale." + uuid.uuid4().hex + ".json")
				os.rename(Lock, Retired)
			except (OSError, ValueError, KeyError, TypeError):
				return {"status": "conflict", "reason": "unrecognized or concurrently changing lock; inspect its owner", "lock": str(Lock)}
	return {"status": "conflict", "reason": "concurrent acquisition", "lock": str(Lock)}


def release(Root, Token=None, StateDir=None, OwnerPid=None):
	StateDir = Path(StateDir) if StateDir else Path(Root) / ".lake"
	if(not StateDir.is_dir()):
		return {"status": "released", "already_absent": True}
	with control_lock(StateDir):
		return release_locked(Root, Token, StateDir, OwnerPid)


def release_locked(Root, Token=None, StateDir=None, OwnerPid=None):
	StateDir = Path(StateDir) if StateDir else Path(Root) / ".lake"
	Lock = StateDir / "build_guard.lock"
	if(not Lock.is_file()):
		return {"status": "released", "already_absent": True}
	try:
		Record = json.loads(Lock.read_text(encoding="utf-8"))
		OwnerPid = OwnerPid or os.getpid()
		Owned = Record.get("owner_pid") == OwnerPid and Record.get("process_identity") == process_identity(OwnerPid)
		if((Token is not None and Token != Record.get("token")) or (Token is None and not Owned)):
			return {"status": "conflict", "reason": "release requires the acquisition token or the same live owner"}
		Lock.unlink()
		return {"status": "released"}
	except (OSError, ValueError):
		return {"status": "conflict", "reason": "cannot establish lock ownership"}


def check(Root, MaxAttempts=0, WindowMinutes=10, LockMinutes=30):
	Result = acquire(Root, OwnerPid=os.getppid())
	print(json.dumps(Result))
	return 0 if Result["status"] == "acquired" else 1


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--project", default=".")
	Parser.add_argument("--state-dir")
	Parser.add_argument("--input-hash", default="unspecified")
	Parser.add_argument("--token")
	Parser.add_argument("--max-attempts", type=int, default=0, help="legacy option; attempts no longer prohibit valid iteration")
	Parser.add_argument("--window-minutes", type=int, default=10, help="legacy compatibility option")
	Parser.add_argument("--lock-minutes", type=int, default=30, help="legacy compatibility option; live locks never expire by age")
	Mode = Parser.add_mutually_exclusive_group(required=True)
	Mode.add_argument("--check", action="store_true")
	Mode.add_argument("--release", action="store_true")
	Arguments = Parser.parse_args()
	Root = Path(Arguments.project).resolve()
	if(not Root.is_dir()):
		print(json.dumps({"status": "missing", "reason": "project directory not found"}))
		return 2
	if(Arguments.check):
		Result = acquire(Root, Arguments.input_hash, Arguments.state_dir, os.getppid())
	else:
		Result = release(Root, Arguments.token, Arguments.state_dir, os.getppid())
	print(json.dumps(Result, indent="\t"))
	return 0 if Result["status"] in ("acquired", "released") else 1


if(__name__ == "__main__"):
	sys.exit(main())
