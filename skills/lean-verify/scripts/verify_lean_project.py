#!/usr/bin/env python3
"""Lean file checks and exact, input-bound root verification. See v2-verification.md."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

from lean_runtime import LeanRuntime, aggregate_results, full_output, hash_json, host_path, mask_lean_source, now_iso, result_status, run, scan_file, sha256_file, snapshot_exclusions, source_snapshot, tool_path, write_json
from lake_build_guard import acquire, release
from lean_evidence import TOOL_NAMES, bind_receipt

ALLOWED_AXIOMS = frozenset(("propext", "Classical.choice", "Quot.sound"))
SCRIPT_DIR = Path(__file__).resolve().parent
PROBE_TEMPLATE = SCRIPT_DIR / "LeanVerifyProbe.lean.template"
LAKE_BUILD_GUARD = SCRIPT_DIR / "lake_build_guard.py"
NAME_PATTERN = re.compile(r"[^\W\d]\w*(?:'*)?(?:\.[^\W\d]\w*(?:'*)?)*", re.UNICODE)


def valid_name(Name):
	if(not isinstance(Name, str) or not NAME_PATTERN.fullmatch(Name)):
		raise ValueError(f"unsupported Lean name spelling: {Name!r}; use an ordinary fully qualified name")
	return Name


def dependency_paths(Result, Suffix):
	Names = [Line.strip() for Line in full_output(Result).splitlines() if Line.strip()]
	if(any(not Name.endswith(Suffix) for Name in Names)):
		raise ValueError("unsupported Lean dependency output; see the retained compiler log")
	return [host_path(Name).resolve() for Name in Names]


def source_imports(Result, Root):
	Imports = json.loads(full_output(Result))
	if(not isinstance(Imports, list)):
		raise ValueError("Lean import header output is not an array")
	Sources = []
	for Item in Imports:
		Parts = Item["components"]
		if(not Parts or any(not isinstance(Part, str) or not Part or Part in (".", "..") or "/" in Part or "\\" in Part for Part in Parts)):
			raise ValueError("module name cannot be mapped safely to a local source")
		Source = Root.joinpath(*Parts).with_suffix(".lean")
		# Append the extension; a quoted name component can itself contain a dot.
		Source = Source.parent / (Parts[-1] + ".lean")
		if(not Source.resolve().is_relative_to(Root) or Source.resolve().is_relative_to(Root / ".lake")):
			raise ValueError("import source escapes the current project source tree")
		Sources.append(Source.resolve() if Source.is_file() else None)
	return Imports, Sources


def compile_local_tree(Runtime, FilePath, WorkDir, Timeout):
	Library = WorkDir / "lib"
	Library.mkdir(parents=True, exist_ok=True)
	Commands = []
	Visiting = set()
	Completed = {}

	def compile_file(Source):
		if(Source in Visiting):
			Commands.append({"status": "failed", "exit_code": None, "reason": "cyclic local imports", "file": str(Source)})
			return False
		if(Source in Completed):
			return Completed[Source]
		if(not Source.is_relative_to(Runtime.Root)):
			raise ValueError("target and project-local imports must be inside the project")
		if(not Source.is_file()):
			Commands.append({"status": "missing", "exit_code": None, "reason": "target file not found", "file": str(Source)})
			return False
		Visiting.add(Source)
		Discovery = Runtime.source_dependencies(Source, WorkDir, Timeout)
		Discovery.update(kind="source_dependencies", file=str(Source.relative_to(Runtime.Root)))
		Commands.append(Discovery)
		if(result_status(Discovery) != "passed"):
			Discovery["reason"] = "Lean import header parsing failed or is unsupported by this compiler; no source freshness claim was made"
			return False
		try:
			Imports, Dependencies = source_imports(Discovery, Runtime.Root)
		except (ValueError, KeyError, TypeError) as Failure:
			Discovery.update(status="unavailable", reason=str(Failure))
			return False
		LocalSources = [Dependency for Dependency in Dependencies if Dependency is not None]
		Discovery["local_sources"] = [str(Dependency.relative_to(Runtime.Root)) for Dependency in LocalSources]
		for Dependency in LocalSources:
			if(not compile_file(Dependency)):
				Visiting.remove(Source)
				Completed[Source] = False
				return False
		Relative = Source.relative_to(Runtime.Root)
		Resolution = Runtime.execute(["--deps", tool_path(Source, Runtime.Command)], Timeout, [Library])
		Resolution.update(kind="import_resolution", file=str(Relative))
		Commands.append(Resolution)
		if(result_status(Resolution) != "passed"):
			return False
		try:
			Resolved = dependency_paths(Resolution, ".olean")
			if(len(Dependencies) != len(Resolved)):
				raise ValueError("source and artifact dependency discovery disagree")
			for Dependency, Artifact in zip(Dependencies, Resolved):
				if(Dependency is not None and Artifact != (Library / Dependency.relative_to(Runtime.Root)).with_suffix(".olean")):
					raise ValueError("project-local import did not resolve to its fresh build: " + str(Dependency))
		except ValueError as Failure:
			Resolution.update(status="unavailable", reason=str(Failure))
			return False
		Olean = (Library / Relative).with_suffix(".olean")
		Olean.parent.mkdir(parents=True, exist_ok=True)
		Command = Runtime.execute(["-R", tool_path(Runtime.Root, Runtime.Command), "-o", tool_path(Olean, Runtime.Command), tool_path(Source, Runtime.Command)], Timeout, [Library])
		Command.update(kind="target", file=str(Relative), olean=str(Olean))
		Commands.append(Command)
		Completed[Source] = result_status(Command) == "passed" and Olean.is_file()
		if(result_status(Command) == "passed" and not Olean.is_file()):
			Command.update(status="unknown", reason="compiler returned without expected artifact")
		Visiting.remove(Source)
		return Completed[Source]

	compile_file(FilePath)
	return Library, Commands


def module_artifacts(Modules, ExcludedModules=()):
	Files = {}
	Missing = []
	for Module in Modules:
		if(Module["module"] in ExcludedModules):
			continue
		Olean = host_path(Module["olean"])
		for Suffix in ("", ".server", ".private"):
			FilePath = Path(str(Olean) + Suffix)
			if(FilePath.is_file()):
				Files[Module["module"] + Suffix] = {"path": str(FilePath), "sha256": sha256_file(FilePath), "mtime_ns": FilePath.stat().st_mtime_ns}
			elif(not Suffix):
				Missing.append(str(FilePath))
	return Files, Missing


def inspection_source(Contract, ModuleName, OutputName):
	Declaration = valid_name(Contract["declaration"])
	ExpectedName = "LeanVerifyV2.no_expected"
	ExpectedSource = ""
	if(Contract.get("expected_type")):
		Universes = [valid_name(Name) for Name in Contract.get("universes", [])]
		ExpectedName = "LeanVerifyV2.expected_statement"
		Parameters = ".{" + ",".join(Universes) + "}" if Universes else ""
		ExpectedSource = f"axiom {ExpectedName}{Parameters} : {Contract['expected_type']}\n"
	return f"import LeanVerifyProbe\nimport {ModuleName}\nset_option maxRecDepth 100000\nset_option maxHeartbeats 0\n" + ExpectedSource + f"#lean_verify_v2 {Declaration} expected {ExpectedName} output {json.dumps(OutputName)}\n"


def extract_target(Runtime, Contract, WorkDir, Timeout):
	FilePath = (Runtime.Root / Contract["file"]).resolve()
	StartedNs = time.time_ns()
	Library, Commands = compile_local_tree(Runtime, FilePath, WorkDir, Timeout)
	if(aggregate_results(Commands)["status"] != "passed"):
		return {"status": "unavailable", "reason": "target compilation incomplete", "commands": Commands}
	ModuleName = valid_name(".".join(FilePath.relative_to(Runtime.Root).with_suffix("").parts))
	Declaration = valid_name(Contract["declaration"])
	# Lean forbids tab tokens. The maintained template uses tabs and is expanded only in generated Lean.
	ProbeSource = WorkDir / "LeanVerifyProbe.lean"
	ProbeSource.write_text(PROBE_TEMPLATE.read_text(encoding="utf-8").expandtabs(2), encoding="utf-8")
	ProbeOlean = Library / "LeanVerifyProbe.olean"
	# Keep the project cwd for elan's toolchain pin and Lake configuration.
	Probe = Runtime.execute(["-R", tool_path(WorkDir, Runtime.Command), "-o", tool_path(ProbeOlean, Runtime.Command), tool_path(ProbeSource, Runtime.Command)], Timeout, [Library])
	Probe.update(kind="inspector_compile", olean=str(ProbeOlean))
	Commands.append(Probe)
	if(result_status(Probe) != "passed" or not ProbeOlean.is_file()):
		return {"status": "unavailable", "reason": "inspector unsupported by this Lean environment", "commands": Commands}
	Output = WorkDir / "declaration.json"
	Inspector = WorkDir / "InspectRoot.lean"
	Inspector.write_text(inspection_source(Contract, ModuleName, tool_path(Output, Runtime.Command)), encoding="utf-8")
	Inspection = Runtime.execute([tool_path(Inspector, Runtime.Command)], Timeout, [Library])
	Inspection["kind"] = "declaration_inspection"
	Commands.append(Inspection)
	if(result_status(Inspection) != "passed" or not Output.is_file()):
		return {"status": "unavailable", "reason": "declaration extraction did not complete", "commands": Commands}
	Target = json.loads(Output.read_text(encoding="utf-8"))
	Target.update(status="checked", commands=Commands, file=Contract["file"], module=ModuleName, expected_type=Contract.get("expected_type"), extraction_file=str(Output))
	Artifacts, Missing = module_artifacts(Target["imported_modules"], (ModuleName, "LeanVerifyProbe"))
	Target["import_artifacts"] = Artifacts
	Target["missing_artifacts"] = Missing
	# Local imports were freshly compiled from the snapshotted sources. External imports must predate this run.
	Target["imports_changed_during_check"] = [Name for Name, Item in Artifacts.items() if Item["mtime_ns"] > StartedNs and not Path(Item["path"]).is_relative_to(Library)]
	Target.update(derive_target(Target, Runtime.environment(), Contract))
	return Target


def derive_target(Target, Environment, Contract):
	Target = dict(Target)
	Modules = [Item["module"] for Item in Target["imported_modules"]]
	if(Target.get("module_inventory_scope") != "loaded_environment" or Target.get("loaded_module_count") != len(Modules) or len(set(Modules)) != len(Modules)):
		raise ValueError("incomplete loaded-module inventory; replay is required")
	Artifacts = Target["import_artifacts"]
	Expected = Target["expected_statement"]
	if(bool(Contract.get("expected_type")) != (Expected is not None)):
		raise ValueError("the elaborated expected statement is missing or unrequested")
	ExpectedModules = Expected["semantic_modules"] if Expected else []
	Target["environment_sha256"] = hash_json({"runtime": Environment["sha256"], "imports": {Name: Item["sha256"] for Name, Item in Artifacts.items()}})
	SemanticKeys = {Name + Suffix for Name in Target["semantic_modules"] + ExpectedModules for Suffix in ("", ".server", ".private")}
	Target["semantic_environment_sha256"] = hash_json({"runtime": Environment["sha256"], "imports": {Name: Item["sha256"] for Name, Item in Artifacts.items() if Name in SemanticKeys}})
	Definitions = definition_hashes(Target)
	Target["definition_hashes"] = Definitions
	Target["type_sha256"] = hash_json({"type": Target["type_expression"], "universes": Target["universes"]})
	if(Expected is not None):
		Expected = dict(Expected)
		ExpectedKeys = {Name + Suffix for Name in ExpectedModules for Suffix in ("", ".server", ".private")}
		Expected["definition_hashes"] = definition_hashes(Expected)
		Expected["type_sha256"] = hash_json({"type": Expected["type_expression"], "universes": Expected["universes"]})
		Expected["semantic_environment_sha256"] = hash_json({"runtime": Environment["sha256"], "imports": {Name: Item["sha256"] for Name, Item in Artifacts.items() if Name in ExpectedKeys}})
		Expected["semantic_sha256"] = hash_json({"type": Expected["type_sha256"], "definitions": Expected["definition_hashes"], "environment": Expected["semantic_environment_sha256"]})
	Target["expected_statement"] = Expected
	Target["semantic_sha256"] = hash_json({"declaration": Target["declaration"], "type": Target["type_sha256"], "definitions": Definitions, "environment": Target["semantic_environment_sha256"], "expected_statement": Expected["semantic_sha256"] if Expected else None})
	Nodes = Target["dependencies"] + (Expected["dependencies"] if Expected else [])
	Axioms = Target["axioms"] + (Expected["axioms"] if Expected else [])
	Target["unexpected_axioms"] = sorted(set(Axioms) - ALLOWED_AXIOMS)
	Target["allowed_axioms"] = sorted(ALLOWED_AXIOMS)
	Target["unsafe_dependencies"] = sorted({Node["name"] for Node in Nodes if Node.get("unsafe")})
	Target["unknown_dependencies"] = sorted({Node["name"] for Node in Nodes if Node.get("missing")})
	Target["identity_mismatches"] = compare_identity(Target, Contract)
	return Target


def definition_hashes(Statement):
	SemanticNames = set(Statement["semantic_dependencies"])
	return {Node["name"]: hash_json({Key: Node[Key] for Key in ("kind", "universes", "unsafe", "type_expression", "value_expression", "missing") if Key in Node}) for Node in Statement["dependencies"] if Node["name"] in SemanticNames}


def compare_identity(Target, Expected):
	Mismatches = []
	for Key in ("declaration", "semantic_sha256", "environment_sha256", "semantic_environment_sha256", "type_sha256"):
		if(Expected.get(Key) and Expected[Key] != Target.get(Key)):
			Mismatches.append(Key)
	for Name, Digest in Expected.get("definition_hashes", {}).items():
		if(Target.get("definition_hashes", {}).get(Name) != Digest):
			Mismatches.append("definition:" + Name)
	return Mismatches


def semantic_review(Target, AuditPath, Root):
	Result = {"status": "not_reviewed", "reused": False, "semantic_sha256": Target.get("semantic_sha256")}
	if(not AuditPath):
		return Result
	try:
		Audit = json.loads(Path(AuditPath).read_text(encoding="utf-8"))
		Binding = Audit.get("binding", {})
		Missing = [Key for Key in ("declaration", "semantic_sha256") if not Binding.get(Key)]
		if(not Binding.get("semantic_environment_sha256") and not Binding.get("environment_sha256")):
			Missing.append("semantic_environment_sha256")
		Mismatch = Missing + compare_identity(Target, Binding)
		for Name, Digest in Audit.get("source_hashes", {}).items():
			Source = (Root / Name).resolve()
			if(not Source.is_file() or sha256_file(Source) != Digest):
				Mismatch.append("mathematical_source:" + Name)
		Accepted = Audit.get("result") == "faithful" and bool(Audit.get("reviewer")) and bool(Audit.get("notes"))
		Result.update(status="reviewed" if not Mismatch and Accepted else "stale" if Mismatch else "not_accepted", reused=not Mismatch and Accepted, binding_mismatches=Mismatch, audit_file=str(Path(AuditPath).resolve()), audit_sha256=sha256_file(AuditPath), reviewer=Audit.get("reviewer"), independence=Audit.get("independence", "not_recorded"), result=Audit.get("result"))
	except (OSError, ValueError, TypeError) as Failure:
		Result.update(status="unavailable", reason=str(Failure))
	return Result


def root_result(Target, MachinePassed, Fresh):
	if(not Target):
		return {"status": "not_requested", "exact_root_passed": False, "reason": "only file/build scope was requested"}
	if(Target.get("status") != "checked" or not MachinePassed or not Fresh):
		return {"status": "incomplete", "exact_root_passed": False, "reason": "execution or evidence is incomplete"}
	Leaves = Target["unexpected_axioms"] + Target["unknown_dependencies"] + Target["unsafe_dependencies"]
	if(Leaves):
		return {"status": "open", "exact_root_passed": False, "unproved_or_untrusted_leaves": sorted(set(Leaves))}
	if(Target["identity_mismatches"] or Target["comparison"]["status"] == "mismatched"):
		return {"status": "target_mismatch", "exact_root_passed": False, "reason": "the expected type or frozen definition/environment identity does not match"}
	if(Target["comparison"]["status"] != "matched"):
		return {"status": "declaration_closed_uncompared", "exact_root_passed": False, "declaration_closed": True}
	return {"status": "closed", "exact_root_passed": True, "declaration_closed": True, "scope": "expected Lean type in the recorded environment; semantic review is separate"}


def verify_project(Arguments):
	Root = Path(Arguments.project).resolve()
	Output = Path(Arguments.output).resolve() if Arguments.output else Root
	Output.mkdir(parents=True, exist_ok=True)
	RunId = uuid.uuid4().hex
	RunDir = Output / "lean-verification-runs" / RunId
	RunDir.mkdir(parents=True)
	Logs = RunDir / "logs"
	Exclusions = snapshot_exclusions(Root, Output)
	Initial = source_snapshot(Root, Exclusions)
	ToolHashes = {Name: sha256_file(SCRIPT_DIR / Name) for Name in TOOL_NAMES}
	Runtime = LeanRuntime(Root, Logs, Arguments.lean, Arguments.lake, Arguments.direct)
	Environment = None
	Whitelist = {Name.strip() for Name in Arguments.whitelist.split(",") if Name.strip()}
	Files = [Root / Name for Name in Arguments.lean_files] if Arguments.lean_files is not None else [Root / Name for Name in Initial if Name.endswith(".lean")]
	MissingFiles = [str(File) for File in Files if not File.is_file()]
	Hits = [Hit for File in Files if File.is_file() for Hit in scan_file(File, Whitelist)]
	Contract = json.loads(Path(Arguments.contract).read_text(encoding="utf-8")) if Arguments.contract else {}
	if(Arguments.target_file):
		Contract["file"] = str((Root / Arguments.target_file).resolve().relative_to(Root))
	if(Arguments.declaration):
		Contract["declaration"] = Arguments.declaration
	if(Arguments.expected_type):
		Contract["expected_type"] = Arguments.expected_type
	if(Arguments.universes):
		Contract["universes"] = Arguments.universes.split(",")
	if(Arguments.expect_manifest):
		Previous = json.loads(Path(Arguments.expect_manifest).read_text(encoding="utf-8"))["target"]
		for Key in ("file", "declaration", "expected_type", "universes"):
			Contract.setdefault(Key, Previous.get(Key))
		for Key in ("semantic_sha256", "semantic_environment_sha256", "definition_hashes", "type_sha256"):
			if(not Previous.get(Key) and Key != "definition_hashes"):
				raise ValueError("previous manifest lacks a usable target identity")
			Contract[Key] = Previous[Key]
	Environment = Runtime.environment() if Arguments.build or Contract else {"lean_version": None, "lake_version": None, "lean_status": "not_probed", "lake_status": "not_probed", "scope": "source scan; no runtime launched"}
	Build = None
	Target = None
	if(Contract and (not Contract.get("file") or not Contract.get("declaration"))):
		raise ValueError("exact checks require both file and full declaration name")
	if(Contract):
		Contract["file"] = str((Root / Contract["file"]).resolve().relative_to(Root))
	write_json(RunDir / "input-snapshot.json", {"run_id": RunId, "inputs": Initial, "tool_hashes": ToolHashes, "contract": Contract})
	Guard = None
	Commands = []
	try:
		if(Arguments.build or Contract):
			# Read-only isolated checks can run concurrently; full project builds share one process lock.
			if(Arguments.build and not Arguments.build_targets and not Contract):
				Guard = acquire(Root, hash_json(Initial))
				if(Guard["status"] != "acquired"):
					Commands.append({"status": "conflict", "exit_code": None, "reason": Guard})
			if(not Commands and Arguments.use_cache):
				Commands.append({"kind": "cache", **run([Runtime.Lake, "exe", "cache", "get"], Root, Arguments.build_timeout, Logs)})
			if(not Commands or aggregate_results(Commands)["status"] == "passed"):
				if(Contract):
					Target = extract_target(Runtime, Contract, RunDir, Arguments.build_timeout)
					Commands.extend(Target.pop("commands"))
				elif(Arguments.build_targets):
					for Index, Name in enumerate(Arguments.build_targets):
						_, Results = compile_local_tree(Runtime, (Root / Name).resolve(), RunDir / f"target-{Index}", Arguments.build_timeout)
						Commands.extend(Results)
				elif(Arguments.build):
					Commands.append({"kind": "full", **run([Runtime.Lake, "build"], Root, Arguments.build_timeout, Logs)})
			Build = {"mode": "declaration" if Contract else "targets" if Arguments.build_targets else "full", "commands": Commands, **aggregate_results(Commands)}
	finally:
		if(Guard and Guard["status"] == "acquired"):
			release(Root, Guard["token"])
	Final = source_snapshot(Root, Exclusions)
	Changed = sorted(Name for Name in set(Initial) | set(Final) if Initial.get(Name) != Final.get(Name))
	ArtifactChanges = []
	if(Target and Target.get("status") == "checked"):
		for Name, Item in Target["import_artifacts"].items():
			if(not Path(Item["path"]).is_file() or sha256_file(Item["path"]) != Item["sha256"]):
				ArtifactChanges.append(Name)
		ArtifactChanges += Target["imports_changed_during_check"] + Target["missing_artifacts"]
	Fresh = not Changed and not ArtifactChanges
	ChangedTools = [Name for Name, Digest in ToolHashes.items() if sha256_file(SCRIPT_DIR / Name) != Digest]
	Fresh = Fresh and not ChangedTools
	ExecutionPassed = bool(Build and Build["status"] == "passed" and not MissingFiles and Fresh)
	MachinePassed = ExecutionPassed and (Target.get("status") == "checked" if Target else not Hits)
	Semantic = semantic_review(Target or {}, Arguments.semantic_audit, Root)
	RootClosure = root_result(Target, MachinePassed, Fresh)
	Manifest = {
		"schema_version": 2, "run_id": RunId, "generated_at": now_iso(), "project_root": str(Root),
		"environment": Environment, "files_scanned": sum(File.is_file() for File in Files), "input_hashes": Initial,
		"whitelist": sorted(Whitelist), "sorry_axiom_hits": Hits, "build": Build,
		"machine_verification_available": Environment.get("lean_status") == "passed" and (Arguments.direct or Environment.get("lake_status") == "passed"),
		"machine_verification_passed": MachinePassed, "exact_root_passed": RootClosure["exact_root_passed"],
		"machine": {"status": Build["status"] if Build else "not_run", "execution_passed": ExecutionPassed, "scope": "exact_declaration" if Contract else "specified_files" if Arguments.build_targets else "default_build_targets" if Arguments.build else "source_scan_only", "missing_files": MissingFiles, "scan_is_authoritative": False},
		"target": Target, "semantic": Semantic, "root_closure": RootClosure,
		"evidence": {"status": "current" if Fresh else "stale", "run_directory": str(RunDir), "input_sha256": hash_json(Initial), "snapshot_exclusions": [str(Item) for Item in Exclusions], "changed_inputs": Changed, "changed_imports": ArtifactChanges, "changed_tools": ChangedTools, "tool_hashes": ToolHashes, "contract": Contract, "contract_sha256": hash_json(Contract), "checker": "Lean compiler and Lean collectAxioms; no independent second kernel"},
	}
	bind_receipt(Manifest)
	write_json(RunDir / "run-manifest.json", Manifest)
	write_json(Output / "run-manifest.json", Manifest)
	return Manifest, Output / "run-manifest.json"


def make_parser():
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--project", required=True)
	Parser.add_argument("--lean-files", nargs="*", default=None)
	Parser.add_argument("--build", action="store_true")
	Parser.add_argument("--build-targets", nargs="*", default=None)
	Parser.add_argument("--use-cache", action="store_true")
	Parser.add_argument("--build-timeout", type=float, default=3600)
	Parser.add_argument("--whitelist", default="", help="legacy source-location filter only; cannot whitelist root sorryAx or extra axioms")
	Parser.add_argument("--output")
	Parser.add_argument("--target-file")
	Parser.add_argument("--declaration")
	Parser.add_argument("--expected-type")
	Parser.add_argument("--universes")
	Parser.add_argument("--contract")
	Parser.add_argument("--expect-manifest")
	Parser.add_argument("--semantic-audit")
	Parser.add_argument("--lean", default="lean")
	Parser.add_argument("--lake", default="lake")
	Parser.add_argument("--direct", action="store_true")
	Parser.add_argument("--strict-exit", action="store_true")
	return Parser


def main():
	Arguments = make_parser().parse_args()
	if(not Path(Arguments.project).is_dir()):
		print(json.dumps({"error": "project directory not found", "project": Arguments.project}))
		return 2
	try:
		Manifest, ManifestPath = verify_project(Arguments)
	except (OSError, ValueError, KeyError, TypeError) as Failure:
		print(json.dumps({"error": str(Failure), "machine_verification_passed": False, "exact_root_passed": False}))
		return 2
	print(json.dumps({"manifest": str(ManifestPath), "files_scanned": Manifest["files_scanned"], "hits": Manifest["sorry_axiom_hits"], "build_exit_code": Manifest["build"] and Manifest["build"]["exit_code"], "machine_verification_passed": Manifest["machine_verification_passed"], "exact_root_passed": Manifest["exact_root_passed"], "root_closure": Manifest["root_closure"], "semantic": Manifest["semantic"]}, ensure_ascii=False, indent="\t"))
	Passed = Manifest["exact_root_passed"] if Manifest["target"] is not None else Manifest["machine_verification_passed"]
	return 1 if Arguments.strict_exit and not Passed else 0


if(__name__ == "__main__"):
	sys.exit(main())
