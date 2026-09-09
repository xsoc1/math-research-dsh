#!/usr/bin/env python3
"""Persistent JSON-lines Lean LSP feedback, with explicit CLI fallback and no proof verdict."""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from lean_runtime import ArtifactHashCache, LeanRuntime, full_output, hash_bytes, hash_json, host_path, now_iso, process_identity, result_status, sha256_file, source_snapshot, tool_path, windows_executable, write_json


class ProtocolFailure(RuntimeError):
	pass


def document_uri(FilePath, Command):
	if(windows_executable(Command)):
		return "file:///" + quote(tool_path(FilePath, Command).replace("\\", "/"), safe="/:")
	return Path(FilePath).resolve().as_uri()


class LeanLsp:
	def __init__(self, Runtime, Timeout=60):
		self.Runtime = Runtime
		self.Timeout = Timeout
		self.SessionId = uuid.uuid4().hex
		self.Messages = queue.Queue()
		self.Diagnostics = {}
		self.Documents = {}
		self.Counter = 0
		self.Closed = False
		self.LogDir = Runtime.LogDir / self.SessionId
		self.LogDir.mkdir(parents=True, exist_ok=True)
		self.ProtocolLog = (self.LogDir / "protocol.jsonl").open("a", encoding="utf-8")
		self.LogLock = threading.Lock()
		self.ErrorLog = (self.LogDir / "stderr.log").open("wb")
		self.Process = subprocess.Popen(Runtime.Command + ["--server"], cwd=Runtime.Root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.ErrorLog, env=Runtime.command_env())
		self.Reader = threading.Thread(target=self.read_messages, daemon=True)
		self.Reader.start()
		self.Identity = {"session_id": self.SessionId, "pid": self.Process.pid, "process_identity": process_identity(self.Process.pid), "protocol_log": str(self.LogDir / "protocol.jsonl"), "stderr_log": str(self.LogDir / "stderr.log")}
		try:
			Initialized = self.request("initialize", {"processId": None, "rootUri": document_uri(Runtime.Root, Runtime.Command), "capabilities": {"textDocument": {"publishDiagnostics": {"versionSupport": True}}, "general": {"positionEncodings": ["utf-16"]}}, "initializationOptions": {"hasWidgets": False}})
			write_json(self.LogDir / "session.json", {**self.Identity, "server_capabilities": Initialized.get("capabilities", {})})
			self.notify("initialized", {})
		except Exception:
			self.close()
			raise

	def log_message(self, Direction, Message):
		with self.LogLock:
			if(not self.ProtocolLog.closed):
				self.ProtocolLog.write(json.dumps({"at": now_iso(), "direction": Direction, "message": Message}, ensure_ascii=False) + "\n")
				self.ProtocolLog.flush()

	def read_messages(self):
		try:
			while(True):
				Headers = {}
				while(True):
					Line = self.Process.stdout.readline()
					if(not Line):
						raise EOFError("Lean language server closed stdout")
					if(Line in (b"\r\n", b"\n")):
						break
					Key, Value = Line.decode("ascii").split(":", 1)
					Headers[Key.lower()] = Value.strip()
				Length = int(Headers["content-length"])
				Body = self.Process.stdout.read(Length)
				if(len(Body) != Length):
					raise EOFError("incomplete Lean protocol frame")
				Message = json.loads(Body.decode("utf-8"))
				self.log_message("received", Message)
				self.Messages.put(Message)
		except (OSError, ValueError, EOFError, KeyError) as Failure:
			self.Messages.put(ProtocolFailure(str(Failure)))

	def send(self, Message):
		if(self.Closed or self.Process.poll() is not None):
			raise ProtocolFailure("Lean session is unavailable")
		self.log_message("sent", Message)
		Data = json.dumps(Message, ensure_ascii=False).encode("utf-8")
		self.Process.stdin.write(f"Content-Length: {len(Data)}\r\n\r\n".encode("ascii") + Data)
		self.Process.stdin.flush()

	def notify(self, Method, Parameters):
		self.send({"jsonrpc": "2.0", "method": Method, "params": Parameters})

	def request(self, Method, Parameters):
		self.Counter += 1
		RequestId = self.Counter
		self.send({"jsonrpc": "2.0", "id": RequestId, "method": Method, "params": Parameters})
		Deadline = time.monotonic() + self.Timeout
		while(True):
			try:
				Message = self.Messages.get(timeout=max(0.001, Deadline - time.monotonic()))
			except queue.Empty:
				self.notify("$/cancelRequest", {"id": RequestId})
				raise ProtocolFailure(f"Lean request timed out: {Method}")
			if(isinstance(Message, Exception)):
				raise Message
			if(Message.get("id") == RequestId and "method" not in Message):
				if("error" in Message):
					raise ProtocolFailure(json.dumps(Message["error"]))
				return Message.get("result")
			if(Message.get("method") == "textDocument/publishDiagnostics"):
				Parameters = Message["params"]
				self.Diagnostics[(Parameters["uri"], Parameters.get("version"))] = Parameters.get("diagnostics", [])
			elif("method" in Message and "id" in Message):
				self.send({"jsonrpc": "2.0", "id": Message["id"], "error": {"code": -32601, "message": "client request unsupported"}})
			if(time.monotonic() >= Deadline):
				raise ProtocolFailure(f"Lean request timed out: {Method}")

	def open_document(self, FilePath, Text):
		Uri = document_uri(FilePath, self.Runtime.Command)
		Digest = hash_bytes(Text.encode())
		Previous = self.Documents.get(Uri)
		Version = 1 if Previous is None else Previous["version"] + (Previous["sha256"] != Digest)
		if(Previous is None):
			self.notify("textDocument/didOpen", {"textDocument": {"uri": Uri, "languageId": "lean4", "version": Version, "text": Text}})
		elif(Previous["sha256"] != Digest):
			self.notify("textDocument/didChange", {"textDocument": {"uri": Uri, "version": Version}, "contentChanges": [{"text": Text}]})
		self.Documents[Uri] = {"version": Version, "sha256": Digest, "path": str(FilePath)}
		return Uri, Version, Digest

	def feedback(self, FilePath, Text, Action="diagnostics", Line=0, Character=0, Query=""):
		Uri, Version, Digest = self.open_document(FilePath, Text)
		self.request("textDocument/waitForDiagnostics", {"uri": Uri, "version": Version})
		Diagnostics = self.Diagnostics.get((Uri, Version))
		if(Diagnostics is None and (Uri, None) in self.Diagnostics):
			raise ProtocolFailure("server diagnostics have no document version; using CLI fallback")
		Parameters = {"textDocument": {"uri": Uri}, "position": {"line": Line, "character": Character}}
		Result = {"status": "complete", "backend": "lsp", "file": str(FilePath), "version": Version, "source_sha256": Digest, "diagnostics": Diagnostics or [], "exact_root_passed": False, "scope": "editor feedback, not root verification", **self.Identity}
		if(Action == "goals"):
			Result["goals"] = self.request("$/lean/plainGoal", Parameters)
			Result["term_goal"] = self.request("$/lean/plainTermGoal", Parameters)
		elif(Action == "hover"):
			Result["hover"] = self.request("textDocument/hover", Parameters)
		elif(Action == "definition"):
			Result["definition"] = self.request("textDocument/definition", Parameters)
		elif(Action == "symbols"):
			Symbols = self.request("textDocument/documentSymbol", {"textDocument": {"uri": Uri}})
			Result["symbols"] = [Item for Item in Symbols or [] if Query.lower() in Item.get("name", "").lower()]
		return Result

	def close(self):
		if(self.Closed):
			return
		try:
			if(self.Process.poll() is None):
				self.notify("exit", {})
				self.Process.wait(timeout=3)
		except (OSError, subprocess.TimeoutExpired, ProtocolFailure):
			self.Process.kill()
			try:
				self.Process.wait(timeout=3)
			except subprocess.TimeoutExpired:
				pass
		finally:
			self.Closed = True
			self.Reader.join(timeout=1)
			self.Process.stdin.close()
			self.Process.stdout.close()
			self.ProtocolLog.close()
			self.ErrorLog.close()


class FeedbackSession:
	def __init__(self, Runtime, Timeout=60, Backend="auto"):
		self.Runtime = Runtime
		self.Timeout = Timeout
		self.Backend = Backend
		self.Server = None
		self.DependencyKey = None
		self.OpenFiles = set()
		self.ImportInventory = {}
		self.ImportHeader = None
		self.HashCache = ArtifactHashCache()
		self.Environment = Runtime.environment()

	def import_header(self, Text):
		# Lean parses this copied header itself. No proof body is added to the inventory query.
		from lean_runtime import mask_lean_source
		Lines = mask_lean_source(Text).splitlines()
		Header = []
		Reading = False
		for Line in Lines:
			Stripped = Line.strip()
			if(not Stripped or Stripped in ("module", "prelude")):
				continue
			if(Stripped.startswith(("import ", "public import ", "private import "))):
				Header.append(Stripped.replace("public import ", "import ").replace("private import ", "import ").replace("import all ", "import "))
				Reading = True
			elif(Reading and Line[:1].isspace()):
				Header.append(Line)
			else:
				break
		return "\n".join(Header)

	def inventory(self, Header):
		Directory = self.Runtime.LogDir / ("imports-" + uuid.uuid4().hex)
		Directory.mkdir(parents=True)
		FilePath = Directory / "Inventory.lean"
		Output = Directory / "imports.json"
		from verify_lean_project import valid_name
		ModuleNames = ["Init"] + [valid_name(Name) for Name in Header.replace("import ", "").split()]
		ImportArray = "#[" + ", ".join("{ module := `" + Name + " }" for Name in ModuleNames) + "]"
		Code = "import Lean\nopen Lean Elab Command\nrun_cmd do\n  let Environment ← importModules " + ImportArray + " {}\n  let mut Modules := #[]\n  for Name in Environment.header.moduleNames do\n    let File ← findOLean Name\n    Modules := Modules.push (Json.mkObj [(\"module\", toJson Name.toString), (\"olean\", toJson File.toString)])\n  IO.FS.writeFile " + json.dumps(tool_path(Output, self.Runtime.Command)) + " (Json.arr Modules |>.compress)\n"
		FilePath.write_text(Code, encoding="utf-8")
		Result = self.Runtime.execute([tool_path(FilePath, self.Runtime.Command)], self.Timeout)
		if(result_status(Result) != "passed" or not Output.is_file()):
			raise ProtocolFailure("cannot bind imported artifacts: " + full_output(Result)[-1000:])
		Inventory = {}
		for Module in json.loads(Output.read_text()):
			Olean = host_path(Module["olean"])
			if(not Olean.is_file()):
				raise ProtocolFailure("imported artifact is missing: " + str(Olean))
			for Suffix in ("", ".server", ".private"):
				FilePath = Path(str(Olean) + Suffix)
				if(FilePath.is_file()):
					Inventory[Module["module"] + Suffix] = str(FilePath)
		return Inventory

	def dependency_key(self, FilePath, Text):
		Header = self.import_header(Text)
		if(Header != self.ImportHeader):
			self.ImportInventory.update(self.inventory(Header))
			self.ImportHeader = Header
		Imports = {Name: self.HashCache.digest(File) if Path(File).is_file() else None for Name, File in self.ImportInventory.items()}
		Inputs = source_snapshot(self.Runtime.Root, [self.Runtime.LogDir])
		self.OpenFiles.add(str(FilePath.relative_to(self.Runtime.Root)))
		Dependencies = {Name: Digest for Name, Digest in Inputs.items() if Name != str(FilePath.relative_to(self.Runtime.Root))}
		self.Runtime.Environment = None
		self.Environment = self.Runtime.environment()
		return hash_json({"environment": self.Environment["sha256"], "imports": Imports, "inputs": Dependencies})

	def cli_feedback(self, FilePath, Text, Action, Reason=None):
		from lean_runtime import run
		Result = run(self.Runtime.Command + ["--json", "--stdin", tool_path(FilePath, self.Runtime.Command)], self.Runtime.Root, self.Timeout, self.Runtime.LogDir, self.Runtime.command_env(), Text)
		Diagnostics = []
		Unparsed = []
		for Line in full_output(Result).splitlines():
			try:
				Value = json.loads(Line)
				Diagnostics.append(Value)
			except ValueError:
				Unparsed.append(Line)
		return {"status": result_status(Result), "backend": "cli", "source_sha256": hash_bytes(Text.encode()), "file": str(FilePath), "diagnostics": Diagnostics, "unparsed_output": Unparsed[-20:], "execution": Result, "fallback_reason": Reason, "requested_action": Action, "unsupported": [] if Action == "diagnostics" else [Action], "exact_root_passed": False, "scope": "current buffer compilation; semantic and root closure unexamined"}

	def query(self, Request):
		Action = Request.get("action", "diagnostics")
		if(Action == "close"):
			self.close()
			return {"status": "closed"}
		if(Action == "restart"):
			self.close()
			self.ImportHeader = None
			self.ImportInventory = {}
			self.DependencyKey = None
			self.HashCache = ArtifactHashCache()
			return {"status": "restarted", "cache": "discarded"}
		if(Action not in ("diagnostics", "goals", "hover", "definition", "symbols")):
			raise ValueError("unknown feedback action")
		FilePath = (self.Runtime.Root / Request["file"]).resolve()
		if(not FilePath.is_relative_to(self.Runtime.Root)):
			raise ValueError("feedback file must be inside the project")
		Text = Request.get("text")
		if(Text is None):
			Text = FilePath.read_text(encoding="utf-8-sig")
		InitialDiskHash = sha256_file(FilePath) if FilePath.is_file() else None
		InitialInputs = source_snapshot(self.Runtime.Root, [self.Runtime.LogDir])
		self.Runtime.Environment = None
		self.Environment = self.Runtime.environment()
		if(self.Backend == "cli"):
			Result = self.cli_feedback(FilePath, Text, Action)
		else:
			try:
				Key = self.dependency_key(FilePath, Text)
				if(self.Server and Key != self.DependencyKey):
					self.close()
				self.DependencyKey = Key
				if(self.Server is None):
					self.Server = LeanLsp(self.Runtime, self.Timeout)
				Result = self.Server.feedback(FilePath, Text, Action, Request.get("line", 0), Request.get("character", 0), Request.get("query", ""))
				Result["dependency_sha256"] = Key
				if(Key != self.dependency_key(FilePath, Text)):
					Result.update(status="stale", reason="dependencies changed while computing feedback")
					self.close()
			except (OSError, ProtocolFailure, ValueError) as Failure:
				self.close()
				if(self.Backend == "lsp"):
					return {"status": "unavailable", "backend": "lsp", "reason": str(Failure), "exact_root_passed": False}
				Result = self.cli_feedback(FilePath, Text, Action, str(Failure))
		FinalDiskHash = sha256_file(FilePath) if FilePath.is_file() else None
		if(InitialDiskHash != FinalDiskHash or InitialInputs != source_snapshot(self.Runtime.Root, [self.Runtime.LogDir])):
			Result.update(status="stale", reason="source or configuration changed while computing feedback")
		Result["buffer_is_saved"] = FinalDiskHash == hash_bytes(Text.encode())
		Result["environment_sha256"] = self.Environment["sha256"]
		return Result

	def close(self):
		if(self.Server):
			self.Server.close()
			self.Server = None


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--project", required=True)
	Parser.add_argument("--output", required=True)
	Parser.add_argument("--lean", default="lean")
	Parser.add_argument("--lake", default="lake")
	Parser.add_argument("--direct", action="store_true")
	Parser.add_argument("--backend", choices=("auto", "lsp", "cli"), default="auto")
	Parser.add_argument("--timeout", type=float, default=60)
	Parser.add_argument("--request", help="one JSON object; omit to serve JSON lines on stdin")
	Arguments = Parser.parse_args()
	Runtime = LeanRuntime(Arguments.project, Arguments.output, Arguments.lean, Arguments.lake, Arguments.direct)
	Session = FeedbackSession(Runtime, Arguments.timeout, Arguments.backend)
	try:
		Requests = [Arguments.request] if Arguments.request else sys.stdin
		for Line in Requests:
			try:
				Result = Session.query(json.loads(Line))
			except (OSError, ValueError, KeyError) as Failure:
				Result = {"status": "unavailable", "reason": str(Failure), "exact_root_passed": False}
			print(json.dumps(Result, ensure_ascii=False), flush=True)
	finally:
		Session.close()
	return 0


if(__name__ == "__main__"):
	sys.exit(main())
