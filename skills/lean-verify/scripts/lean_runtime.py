#!/usr/bin/env python3
"""Shared local execution, identity, and source-location helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

CONFIGURATION_NAMES = ("lean-toolchain", "lake-manifest.json", "lakefile.lean", "lakefile.toml", "lakefile")
RUNTIME_BINARY_NAMES = ("bin/lean", "bin/lean.exe", "bin/lake", "bin/lake.exe", "bin/libleanshared.dll", "lib/lean/libleanshared.so", "lib/lean/libleanshared.dylib")


def named_hashes(Root, Names):
	return {Name: sha256_file(Path(Root) / Name) for Name in Names if (Path(Root) / Name).is_file()}


def snapshot_exclusions(Root, Output):
	Root, Output = Path(Root).resolve(), Path(Output).resolve()
	return [Output] if Output != Root and Output.is_relative_to(Root) else [Output / "lean-verification-runs"]


def now_iso():
	return datetime.now(timezone.utc).isoformat()


def hash_bytes(Data):
	return hashlib.sha256(Data).hexdigest()


def hash_json(Data):
	return hash_bytes(json.dumps(Data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def sha256_file(PathName):
	Digest = hashlib.sha256()
	with Path(PathName).open("rb") as Stream:
		for Chunk in iter(lambda: Stream.read(1 << 20), b""):
			Digest.update(Chunk)
	return Digest.hexdigest()


class ArtifactHashCache:
	"""Disposable acceleration for editor feedback on a trusted local filesystem."""
	def __init__(self):
		self.Entries = {}

	def digest(self, FilePath):
		FilePath = Path(FilePath)
		Stat = FilePath.stat()
		Identity = (Stat.st_dev, Stat.st_ino, Stat.st_size, Stat.st_mtime_ns, Stat.st_ctime_ns)
		Previous = self.Entries.get(str(FilePath))
		if(Previous and Previous[0] == Identity):
			return Previous[1]
		Digest = sha256_file(FilePath)
		After = FilePath.stat()
		if(Identity != (After.st_dev, After.st_ino, After.st_size, After.st_mtime_ns, After.st_ctime_ns)):
			raise OSError("artifact changed while hashing: " + str(FilePath))
		self.Entries[str(FilePath)] = (Identity, Digest)
		return Digest


def write_json(PathName, Data):
	PathName = Path(PathName)
	PathName.parent.mkdir(parents=True, exist_ok=True)
	Temporary = PathName.with_name(PathName.name + "." + uuid.uuid4().hex + ".tmp")
	try:
		Temporary.write_text(json.dumps(Data, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")
		os.replace(Temporary, PathName)
	finally:
		Temporary.unlink(missing_ok=True)


def host_path(PathName):
	Text = str(PathName)
	if(os.name != "nt" and re.match(r"^[a-zA-Z]:[\\/]", Text)):
		return Path("/mnt" / Path(Text[0].lower()) / Text[3:].replace("\\", "/"))
	return Path(Text)


def executable_path(Name):
	Found = shutil.which(Name)
	return str(Path(Found).absolute()) if Found else Name


def windows_executable(Command):
	try:
		return Path(Command[0]).resolve().suffix.lower() == ".exe"
	except OSError:
		return str(Command[0]).lower().endswith(".exe")


def tool_path(PathName, Command):
	PathName = Path(PathName).resolve()
	if(os.name != "nt" and windows_executable(Command)):
		Result = subprocess.run(["wslpath", "-w", str(PathName)], capture_output=True, text=True, timeout=10)
		if(Result.returncode != 0):
			raise OSError(Result.stderr.strip())
		return Result.stdout.strip()
	return str(PathName)


def process_identity(ProcessId):
	if(os.name == "posix" and Path("/proc").is_dir()):
		try:
			Fields = (Path("/proc") / str(ProcessId) / "stat").read_text().rsplit(")", 1)[1].split()
			if(Fields[0] == "Z"):
				return None
			return "linux:" + Fields[19]
		except (OSError, IndexError):
			return None
	if(os.name == "nt"):
		import ctypes
		from ctypes import wintypes
		Kernel = ctypes.windll.kernel32
		Kernel.OpenProcess.restype = wintypes.HANDLE
		Handle = Kernel.OpenProcess(0x1000, False, ProcessId)
		if(not Handle):
			return None
		try:
			Times = [wintypes.FILETIME() for _ in range(4)]
			if(Kernel.GetProcessTimes(Handle, *(ctypes.byref(Item) for Item in Times))):
				return "windows:" + str((Times[0].dwHighDateTime << 32) | Times[0].dwLowDateTime)
		finally:
			Kernel.CloseHandle(Handle)
	return "unknown"


def mask_lean_source(Text):
	"""Preserve positions while masking nested comments and literal contents.
	This is a location aid, not an extensible Lean parser or axiom checker.
	"""
	Masked = list(Text)
	Index = 0
	Size = len(Text)
	while(Index < Size):
		End = Index
		if(Text.startswith("--", Index)):
			End = Text.find("\n", Index)
			End = Size if End < 0 else End
		elif(Text.startswith("/-", Index)):
			Depth = 1
			End = Index + 2
			while(End < Size and Depth):
				if(Text.startswith("/-", End)):
					Depth += 1
					End += 2
				elif(Text.startswith("-/", End)):
					Depth -= 1
					End += 2
				else:
					End += 1
		elif(Text[Index] == "«"):
			End = Text.find("»", Index + 1)
			End = Size if End < 0 else End + 1
		else:
			Raw = re.match(r'r(#+)?"', Text[Index:]) if Text[Index] == "r" else None
			if(Raw):
				Closing = '"' + (Raw.group(1) or "")
				End = Text.find(Closing, Index + len(Raw.group(0)))
				End = Size if End < 0 else End + len(Closing)
			elif(Text[Index] == '"'):
				End = Index + 1
				while(End < Size):
					if(Text[End] == "\\"):
						End += 2
					elif(Text[End] == '"'):
						End += 1
						break
					else:
						End += 1
		if(End > Index):
			for Position in range(Index, min(End, Size)):
				if(Masked[Position] not in "\r\n"):
					Masked[Position] = " "
			Index = End
		else:
			Index += 1
	return "".join(Masked)


def scan_file(PathName, Whitelist):
	Code = mask_lean_source(Path(PathName).read_text(encoding="utf-8-sig", errors="replace"))
	Hits = []
	for Match in re.finditer(r"\b(sorry|admit|axiom)\b", Code):
		Kind = Match.group(1)
		if(Kind in Whitelist):
			continue
		if(Kind == "axiom"):
			Name = re.match(r"\s+([\w.']+)", Code[Match.end():])
			if(Name and Name.group(1) in Whitelist):
				continue
		Hits.append({"file": str(PathName), "line": Code.count("\n", 0, Match.start()) + 1, "kind": Kind})
	return Hits


def source_snapshot(Root, Excluded=()):
	Root = Path(Root).resolve()
	Excluded = [Path(Item).resolve() for Item in Excluded]
	Files = {}
	for Directory, Subdirs, Names in os.walk(Root):
		Subdirs[:] = sorted(Name for Name in Subdirs if Name not in (".git", ".lake", ".lean-verify", "__pycache__") and not any((Path(Directory) / Name).resolve().is_relative_to(Item) for Item in Excluded))
		for Name in sorted(Names):
			if(Name.endswith(".lean") or Name in ("lean-toolchain", "lake-manifest.json", "lakefile.toml", "lakefile")):
				FilePath = Path(Directory) / Name
				Files[str(FilePath.relative_to(Root))] = sha256_file(FilePath)
	return Files


def result_status(Result):
	if(Result.get("status")):
		return Result["status"]
	Code = Result.get("exit_code")
	return "passed" if Code == 0 else "failed" if Code is not None else "unknown"


def aggregate_results(Results):
	Statuses = [result_status(Result) for Result in Results]
	if(not Statuses):
		return {"status": "not_run", "exit_code": None}
	if(all(Status == "passed" for Status in Statuses)):
		return {"status": "passed", "exit_code": 0}
	for Status in ("failed", "timeout", "unavailable", "missing", "stale", "conflict", "unknown", "not_run"):
		if(Status in Statuses):
			Codes = [Result.get("exit_code") for Result in Results if Result.get("exit_code") not in (None, 0)]
			return {"status": Status, "exit_code": Codes[0] if Codes else None}
	return {"status": "unknown", "exit_code": None}


def run(Command, Cwd, timeout=3600, log_dir=None, Env=None, InputText=None):
	Command = [str(Item) for Item in Command]
	JobId = uuid.uuid4().hex
	LogDir = Path(log_dir) if log_dir else Path(Cwd) / ".lean-verify" / "logs"
	LogDir.mkdir(parents=True, exist_ok=True)
	OutputPath = LogDir / (JobId + ".stdout.log")
	ErrorPath = LogDir / (JobId + ".stderr.log")
	JobPath = LogDir / (JobId + ".job.json")
	Result = {"job_id": JobId, "command": Command, "cwd": str(Cwd), "status": "running", "exit_code": None, "started_at": now_iso(), "stdout_log": str(OutputPath), "stderr_log": str(ErrorPath), "job_record": str(JobPath)}
	Started = time.monotonic()
	write_json(JobPath, Result)
	with OutputPath.open("wb") as Output, ErrorPath.open("wb") as Error:
		try:
			Process = subprocess.Popen(Command, cwd=str(Cwd), stdout=Output, stderr=Error, stdin=subprocess.PIPE if InputText is not None else subprocess.DEVNULL, env=Env, start_new_session=os.name == "posix")
			Result.update({"pid": Process.pid, "process_identity": process_identity(Process.pid)})
			write_json(JobPath, Result)
			try:
				Process.communicate(InputText.encode() if InputText is not None else None, timeout=timeout)
				Result.update(status="passed" if Process.returncode == 0 else "failed", exit_code=Process.returncode)
			except subprocess.TimeoutExpired:
				Result.update(status="timeout", reason=f"timeout after {timeout}s")
				if(os.name == "posix"):
					try:
						os.killpg(Process.pid, signal.SIGKILL)
					except ProcessLookupError:
						pass
				elif(os.name == "nt"):
					subprocess.run(["taskkill", "/PID", str(Process.pid), "/T", "/F"], capture_output=True, timeout=10)
				try:
					Process.wait(timeout=5)
					Result["cleanup"] = "unconfirmed_windows_children" if os.name != "nt" and windows_executable(Command) else "process_group_stopped"
				except subprocess.TimeoutExpired:
					Result["cleanup"] = "unconfirmed"
		except (OSError, ValueError) as Failure:
			Result.update(status="unavailable", reason=str(Failure))
			Error.write((str(Failure) + "\n").encode())
	Result.update({"finished_at": now_iso(), "elapsed_seconds": round(time.monotonic() - Started, 6)})
	for StreamName, FilePath in (("stdout", OutputPath), ("stderr", ErrorPath)):
		Data = FilePath.read_bytes()
		Result[StreamName] = Data[-8000:].decode("utf-8", errors="replace")
		Result[StreamName + "_bytes"] = len(Data)
		Result[StreamName + "_sha256"] = hash_bytes(Data)
	write_json(JobPath, Result)
	return Result


def full_output(Result, StreamName="stdout"):
	LogPath = Result.get(StreamName + "_log")
	return Path(LogPath).read_text(encoding="utf-8", errors="replace") if LogPath else Result.get(StreamName, "")


class LeanRuntime:
	def __init__(self, Root, LogDir, Lean="lean", Lake="lake", Direct=False, SearchPaths=()):
		self.Root = Path(Root).resolve()
		self.LogDir = Path(LogDir).resolve()
		self.Lean = executable_path(Lean)
		self.Lake = executable_path(Lake)
		self.Direct = Direct
		self.Command = [self.Lean] if Direct else [self.Lake, "env", "lean"]
		self.SearchPaths = [Path(Item).resolve() for Item in SearchPaths]
		self.Environment = None

	def environment(self):
		if(self.Environment is not None):
			return self.Environment
		Versions = {}
		for Name, Command in (("lean", self.Command), ("lake", [self.Lake])):
			Result = run(Command + ["--version"], self.Root, timeout=30, log_dir=self.LogDir)
			Versions[Name + "_version"] = full_output(Result).strip() if result_status(Result) == "passed" else None
			Versions[Name + "_status"] = result_status(Result)
		Prefix = run(self.Command + ["--print-prefix"], self.Root, timeout=30, log_dir=self.LogDir)
		PrefixPath = host_path(full_output(Prefix).strip()) if result_status(Prefix) == "passed" else None
		BinaryHashes = named_hashes(PrefixPath, RUNTIME_BINARY_NAMES) if PrefixPath and PrefixPath.is_dir() else {}
		Configuration = named_hashes(self.Root, CONFIGURATION_NAMES)
		Versions.update({"lean_toolchain": (self.Root / "lean-toolchain").read_text(encoding="utf-8-sig").strip() if (self.Root / "lean-toolchain").is_file() else None, "configuration_hashes": Configuration, "binary_hashes": BinaryHashes, "prefix": str(PrefixPath) if PrefixPath else None, "mode": "direct" if self.Direct else "lake", "inherited_lean_path": os.environ.get("LEAN_PATH", ""), "inherited_lean_src_path": os.environ.get("LEAN_SRC_PATH", "")})
		Versions["sha256"] = hash_json(Versions)
		self.Environment = Versions
		return Versions

	def command_env(self, ExtraPaths=()):
		Paths = [Path(Item).resolve() for Item in ExtraPaths] + self.SearchPaths
		if(self.Direct):
			Paths += [self.Root, self.Root / ".lake" / "build" / "lib" / "lean"]
			Paths += sorted((self.Root / ".lake" / "packages").glob("*/.lake/build/lib/lean"))
		Separator = ";" if windows_executable(self.Command) or os.name == "nt" else ":"
		Values = [tool_path(Item, self.Command) for Item in Paths if Item.is_dir()]
		if(os.environ.get("LEAN_PATH")):
			Values.append(os.environ["LEAN_PATH"])
		Environment = dict(os.environ, LEAN_PATH=Separator.join(Values))
		if(os.name != "nt" and windows_executable(self.Command)):
			Parts = [Item for Item in Environment.get("WSLENV", "").split(":") if Item and Item.split("/")[0] != "LEAN_PATH"]
			Environment["WSLENV"] = ":".join(Parts + ["LEAN_PATH"])
		return Environment

	def execute(self, Arguments, Timeout=3600, ExtraPaths=(), Cwd=None):
		return run(self.Command + [str(Item) for Item in Arguments], Cwd or self.Root, timeout=Timeout, log_dir=self.LogDir, Env=self.command_env(ExtraPaths))

	def source_dependencies(self, Source, WorkDir, Timeout=3600):
		Probe = WorkDir / "DiscoverImports.lean"
		Probe.write_text(HEADER_PROBE.expandtabs(2), encoding="utf-8")
		return self.execute(["--run", tool_path(Probe, self.Command), tool_path(Source, self.Command)], Timeout)


HEADER_PROBE = '''import Lean

def main (Arguments : List String) : IO UInt32 := do
	let [FileName] := Arguments | throw (IO.userError "expected one source path")
	let Source <- IO.FS.readFile FileName
	let (Header, _, Messages) <- Lean.Parser.parseHeader (Lean.Parser.mkInputContext Source FileName)
	if Messages.hasErrors then
		throw (IO.userError "Lean import header parse failed")
	let Imports := Lean.Elab.headerToImports Header
	let Records := Imports.map fun Item => Lean.Json.mkObj [
		("module", Lean.toJson Item.module.toString),
		("components", Lean.toJson (Item.module.components.map Lean.Name.getString!))]
	IO.println (Lean.Json.arr Records).compress
	return 0
'''
