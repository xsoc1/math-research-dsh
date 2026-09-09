#!/usr/bin/env python3
"""Recheck saved evidence against current local inputs; optionally replay Lean."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from lean_runtime import CONFIGURATION_NAMES, HEADER_PROBE, RUNTIME_BINARY_NAMES, LeanRuntime, hash_json, host_path, named_hashes, sha256_file, snapshot_exclusions, source_snapshot, tool_path

TOOL_NAMES = ("verify_lean_project.py", "lean_runtime.py", "lean_evidence.py", "LeanVerifyProbe.lean.template", "lake_build_guard.py", "run_manifest.schema.json")


def require(Condition, Message):
	if(not Condition):
		raise ValueError(Message)


def compiled_artifacts(Commands):
	Artifacts = {}
	for Result in Commands:
		if(Result.get("olean")):
			for Suffix in ("", ".server", ".private"):
				Artifact = Path(Result["olean"] + Suffix)
				if(Artifact.is_file()):
					Artifacts[str(Artifact)] = sha256_file(Artifact)
	return Artifacts


def payload_digest(Manifest):
	return hash_json({Key: Value for Key, Value in Manifest.items() if Key != "report_sha256"})


def bind_receipt(Manifest):
	Target = Manifest.get("target") or {}
	Evidence = Manifest["evidence"]
	Extracted = Target.get("extraction_file")
	Evidence["extraction_sha256"] = sha256_file(Extracted) if Extracted and Path(Extracted).is_file() else None
	Evidence["compiled_artifacts"] = compiled_artifacts((Manifest.get("build") or {}).get("commands", []))
	RunDir = Path(Evidence["run_directory"])
	Evidence["generated_sources"] = named_hashes(RunDir, ("LeanVerifyProbe.lean", "InspectRoot.lean", "DiscoverImports.lean"))
	Evidence["snapshot_sha256"] = sha256_file(RunDir / "input-snapshot.json")
	Manifest["report_sha256"] = payload_digest(Manifest)


def current_module_resolution(Root, RunDir, Environment, Modules):
	from verify_lean_project import dependency_paths
	CheckDir = RunDir.parent / "rechecks" / uuid.uuid4().hex
	CheckDir.mkdir(parents=True)
	Source = CheckDir / "ResolveImports.lean"
	Names = [Module["module"] for Module in Modules]
	require(Names and len(Names) == len(set(Names)), "missing or duplicate imported module names")
	# These escaped names come from Lean's Name.toString in the retained extraction.
	Source.write_text("prelude\n" + "".join("import " + Name + "\n" for Name in Names), encoding="utf-8")
	Prefix = Path(Environment["prefix"])
	Extension = ".exe" if (Prefix / "bin/lean.exe").is_file() else ""
	Runtime = LeanRuntime(Root, CheckDir / "logs", str(Prefix / "bin" / ("lean" + Extension)), str(Prefix / "bin" / ("lake" + Extension)), Environment["mode"] == "direct")
	Result = Runtime.execute(["--deps", tool_path(Source, Runtime.Command)], 45, [RunDir / "lib"])
	if(Result.get("status") != "passed" or Result.get("exit_code") != 0):
		return ["module_resolution_unavailable:" + str(Result.get("job_record"))]
	Paths = dependency_paths(Result, ".olean")
	if(len(Paths) != len(Modules)):
		return ["module_resolution_incomplete:" + str(Result.get("stdout_log"))]
	return ["module_resolution:" + Module["module"] for Module, Resolved in zip(Modules, Paths) if Resolved != host_path(Module["olean"]).resolve()]


def recheck_manifest(ManifestPath):
	ManifestPath = Path(ManifestPath).resolve()
	Reasons = []
	try:
		Manifest = json.loads(ManifestPath.read_text(encoding="utf-8"))
		require(isinstance(Manifest, dict), "manifest must be an object")
		if(Manifest.get("schema_version") != 2 or Manifest.get("report_sha256") != payload_digest(Manifest)):
			raise ValueError("missing or invalid v2 receipt; replay is required for older reports")
		Root = Path(Manifest["project_root"]).resolve()
		Target = Manifest["target"]
		Evidence = Manifest["evidence"]
		if(not isinstance(Target, dict) or Target.get("status") != "checked"):
			raise ValueError("no checked declaration evidence")
		Contract = Evidence["contract"]
		if(not Contract.get("expected_type") or Contract.get("declaration") != Target.get("declaration") or Contract.get("file") != Target.get("file") or Contract["expected_type"] != Target.get("expected_type")):
			raise ValueError("missing exact expected statement binding")
		if(hash_json(Contract) != Evidence["contract_sha256"]):
			raise ValueError("contract receipt mismatch")
		Initial = Manifest["input_hashes"]
		if(not Initial or Target["file"] not in Initial or hash_json(Initial) != Evidence["input_sha256"]):
			raise ValueError("target source has no input receipt")
		RunDir = Path(Evidence["run_directory"]).resolve()
		require(RunDir.name == Manifest["run_id"] and RunDir.parent.name == "lean-verification-runs", "invalid run directory binding")
		Exclusions = snapshot_exclusions(Root, RunDir.parent.parent)
		require(Evidence["snapshot_exclusions"] == [str(Item) for Item in Exclusions], "invalid source exclusions")
		SnapshotPath = RunDir / "input-snapshot.json"
		require(sha256_file(SnapshotPath) == Evidence["snapshot_sha256"], "input snapshot hash mismatch")
		Snapshot = json.loads(SnapshotPath.read_text(encoding="utf-8"))
		require(Snapshot == {"run_id": Manifest["run_id"], "inputs": Initial, "tool_hashes": Evidence["tool_hashes"], "contract": Contract}, "input snapshot binding mismatch")
		Current = source_snapshot(Root, Exclusions)
		for Name in sorted(set(Initial) | set(Current)):
			if(Initial.get(Name) != Current.get(Name)):
				Reasons.append("source:" + Name)
		require(set(Evidence["tool_hashes"]) == set(TOOL_NAMES), "incomplete verifier tool identity")
		for Name, Digest in Evidence["tool_hashes"].items():
			FilePath = Path(__file__).resolve().parent / Name
			if(not FilePath.is_file() or sha256_file(FilePath) != Digest):
				Reasons.append("tool:" + Name)
		Environment = Manifest["environment"]
		require(Environment["sha256"] == hash_json({Key: Value for Key, Value in Environment.items() if Key != "sha256"}), "environment identity mismatch")
		if(named_hashes(Root, CONFIGURATION_NAMES) != Environment["configuration_hashes"]):
			Reasons.append("configuration_identity")
		Prefix = Path(Environment["prefix"])
		require(Environment["binary_hashes"] and any(Name in Environment["binary_hashes"] for Name in ("bin/lean", "bin/lean.exe")), "runtime compiler identity is missing")
		if(named_hashes(Prefix, RUNTIME_BINARY_NAMES) != Environment["binary_hashes"]):
			Reasons.append("runtime_identity")
		if(Environment.get("inherited_lean_path") != os.environ.get("LEAN_PATH", "")):
			Reasons.append("runtime_search_path")
		if(Environment.get("inherited_lean_src_path") != os.environ.get("LEAN_SRC_PATH", "")):
			Reasons.append("runtime_source_search_path")
		Artifacts = Evidence["compiled_artifacts"]
		if(not Artifacts):
			raise ValueError("compiled target artifacts are missing")
		for Name, Digest in Artifacts.items():
			FilePath = Path(Name)
			if(not FilePath.is_file() or sha256_file(FilePath) != Digest):
				Reasons.append("compiled_artifact:" + Name)
		ExtractionPath = Path(Target["extraction_file"])
		require(ExtractionPath == RunDir / "declaration.json", "declaration extraction location mismatch")
		if(not ExtractionPath.is_file() or sha256_file(ExtractionPath) != Evidence["extraction_sha256"]):
			Reasons.append("declaration_extraction")
		else:
			Extraction = json.loads(ExtractionPath.read_text(encoding="utf-8"))
			require(isinstance(Extraction, dict) and Extraction.get("dependencies") and Extraction.get("imported_modules"), "incomplete declaration extraction")
			require(isinstance(Extraction.get("expected_statement"), dict), "expected statement extraction is missing; replay required")
			for Key, Value in Extraction.items():
				if(Key == "expected_statement"):
					for ExpectedKey, ExpectedValue in Value.items():
						require(Target[Key][ExpectedKey] == ExpectedValue, "expected statement extraction binding: " + ExpectedKey)
				elif(Value != Target.get(Key)):
					Reasons.append("extraction_binding:" + Key)
		from verify_lean_project import PROBE_TEMPLATE, dependency_paths, derive_target, inspection_source, module_artifacts, root_result, source_imports
		ModuleName = ".".join(Path(Target["file"]).with_suffix("").parts)
		require(Target["module"] == ModuleName, "target module binding mismatch")
		Imports, Missing = module_artifacts(Target["imported_modules"], (ModuleName, "LeanVerifyProbe"))
		ImportBindings = lambda Items: {Name: (Item["path"], Item["sha256"]) for Name, Item in Items.items()}
		if(Missing or ImportBindings(Imports) != ImportBindings(Target["import_artifacts"])):
			Reasons.append("import_artifacts")
		DerivedTarget = derive_target(Target, Environment, Contract)
		for Key, Value in DerivedTarget.items():
			if(Target.get(Key) != Value):
				Reasons.append("derived_target:" + Key)
		Build = Manifest["build"]
		Kinds = {Result.get("kind") for Result in Build["commands"]}
		if(Build.get("mode") != "declaration" or not {"source_dependencies", "import_resolution", "target", "inspector_compile", "declaration_inspection"}.issubset(Kinds)):
			raise ValueError("actual compile and inspection records are required")
		require(Build.get("status") == "passed" and Build.get("exit_code") == 0, "build did not pass")
		require(any(Result.get("file") == Target["file"] and Result.get("kind") == "target" for Result in Build["commands"]), "target compile record is missing")
		require(Artifacts == compiled_artifacts(Build["commands"]), "compiled artifact inventory mismatch")
		Inspection = [Result for Result in Build["commands"] if Result.get("kind") == "declaration_inspection"]
		require(len(Inspection) == 1, "one declaration inspection is required")
		Generated = named_hashes(RunDir, ("LeanVerifyProbe.lean", "InspectRoot.lean", "DiscoverImports.lean"))
		require(len(Generated) == 3 and Generated == Evidence["generated_sources"], "generated source hashes mismatch")
		require((RunDir / "LeanVerifyProbe.lean").read_text(encoding="utf-8") == PROBE_TEMPLATE.read_text(encoding="utf-8").expandtabs(2), "probe source does not match verifier")
		require((RunDir / "DiscoverImports.lean").read_text(encoding="utf-8") == HEADER_PROBE.expandtabs(2), "import parser source does not match verifier")
		require((RunDir / "InspectRoot.lean").read_text(encoding="utf-8") == inspection_source(Contract, ModuleName, tool_path(ExtractionPath, Inspection[0]["command"])), "expected statement was not used in the recorded inspection")
		CompiledFiles = {Result["file"] for Result in Build["commands"] if Result.get("kind") == "target"}
		for FileName in CompiledFiles:
			Discoveries = [Result for Result in Build["commands"] if Result.get("kind") == "source_dependencies" and Result.get("file") == FileName]
			Resolutions = [Result for Result in Build["commands"] if Result.get("kind") == "import_resolution" and Result.get("file") == FileName]
			require(len(Discoveries) == 1 and len(Resolutions) == 1, "local build requires one parsed header and one import resolution")
			_, Sources = source_imports(Discoveries[0], Root)
			LocalFiles = [str(Source.relative_to(Root)) for Source in Sources if Source is not None]
			require(LocalFiles == Discoveries[0]["local_sources"] and set(LocalFiles).issubset(CompiledFiles), "local import is missing its current source build")
			Resolved = dependency_paths(Resolutions[0], ".olean")
			require(len(Resolved) == len(Sources), "incomplete import resolution record")
			for Source, Artifact in zip(Sources, Resolved):
				if(Source is not None):
					require(Artifact == (RunDir / "lib" / Source.relative_to(Root)).with_suffix(".olean"), "local source did not bind its fresh artifact")
		for Result in Build["commands"]:
			if(Result.get("status") != "passed" or Result.get("exit_code") != 0 or not Result.get("command")):
				Reasons.append("incomplete_execution")
			Job = json.loads(Path(Result["job_record"]).read_text(encoding="utf-8"))
			for Key in ("command", "cwd", "status", "exit_code", "job_id", "pid", "process_identity", "stdout_log", "stdout_sha256", "stderr_log", "stderr_sha256"):
				require(Key in Job and Job[Key] == Result[Key], "execution job binding mismatch: " + Key)
			if(Result.get("kind") in ("target", "inspector_compile")):
				Relative = Path(Result["file"]) if Result["kind"] == "target" else Path("LeanVerifyProbe.lean")
				ExpectedOlean = (RunDir / "lib" / Relative).with_suffix(".olean")
				Source = Root / Relative if Result["kind"] == "target" else RunDir / Relative
				require(str(ExpectedOlean) in Artifacts and Result.get("olean") == str(ExpectedOlean), "compiled source binding mismatch")
				require(host_path(Result["command"][-1]).resolve() == Source and host_path(Result["command"][-2]).resolve() == ExpectedOlean and Result["command"][-3] == "-o", "compile command binding mismatch")
			elif(Result.get("kind") == "declaration_inspection"):
				require(host_path(Result["command"][-1]).resolve() == RunDir / "InspectRoot.lean", "inspection command binding mismatch")
			elif(Result.get("kind") in ("source_dependencies", "import_resolution")):
				require(host_path(Result["command"][-1]).resolve() == Root / Result["file"], "dependency source binding mismatch")
				if(Result["kind"] == "source_dependencies"):
					require(Result["command"][-3] == "--run" and host_path(Result["command"][-2]).resolve() == RunDir / "DiscoverImports.lean", "dependency parser command mismatch")
				else:
					require(Result["command"][-2] == "--deps", "import resolver command mismatch")
			for Stream in ("stdout", "stderr"):
				FilePath = Path(Result[Stream + "_log"])
				if(not FilePath.is_file() or sha256_file(FilePath) != Result[Stream + "_sha256"]):
					Reasons.append("execution_log:" + str(FilePath))
		Fresh = Evidence.get("status") == "current" and not any(Evidence[Key] for Key in ("changed_inputs", "changed_imports", "changed_tools")) and not Target["missing_artifacts"] and not Target["imports_changed_during_check"]
		Machine = Manifest["machine"]
		MachinePassed = Machine.get("status") == "passed" and Machine.get("execution_passed") is True and Machine.get("scope") == "exact_declaration" and Machine.get("missing_files") == [] and Environment.get("lean_status") == "passed" and Manifest.get("machine_verification_passed") is True
		Derived = root_result(DerivedTarget, MachinePassed, Fresh)
		require(Derived == Manifest["root_closure"], "root closure binding mismatch")
		if(not Derived["exact_root_passed"] or Manifest.get("exact_root_passed") is not True):
			Reasons.append("root_not_closed")
		require(json.loads((RunDir / "run-manifest.json").read_text(encoding="utf-8")) == Manifest, "immutable run manifest mismatch")
		if(not Reasons):
			Reasons.extend(current_module_resolution(Root, RunDir, Environment, Target["imported_modules"]))
		Current = not Reasons
		return {"status": "current" if Current else "stale", "snapshot_current": Current, "exact_root_passed": Current, "declaration": Target["declaration"], "semantic_sha256": Target["semantic_sha256"], "manifest_sha256": sha256_file(ManifestPath), "reasons": Reasons, "scope": "saved evidence and current Lean module resolution checked; no new kernel proof replay"}
	except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as Failure:
		return {"status": "invalid", "snapshot_current": False, "exact_root_passed": False, "reasons": [str(Failure)]}


def replay_manifest(ManifestPath, Output):
	Manifest = json.loads(Path(ManifestPath).read_text(encoding="utf-8"))
	Prefix = Path(Manifest["environment"]["prefix"])
	Extension = ".exe" if (Prefix / "bin" / "lean.exe").is_file() else ""
	Arguments = ["--project", Manifest["project_root"], "--expect-manifest", str(ManifestPath), "--output", str(Output), "--lean", str(Prefix / "bin" / ("lean" + Extension)), "--lake", str(Prefix / "bin" / ("lake" + Extension))]
	if(Manifest["environment"].get("mode") == "direct"):
		Arguments.append("--direct")
	from verify_lean_project import make_parser, verify_project
	NewManifest, NewPath = verify_project(make_parser().parse_args(Arguments))
	return {"manifest": str(NewPath), "exact_root_passed": NewManifest["exact_root_passed"], "root_closure": NewManifest["root_closure"], "scope": "new Lean replay of the recorded expected statement"}


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--manifest", required=True)
	Parser.add_argument("--replay", action="store_true")
	Parser.add_argument("--output")
	Arguments = Parser.parse_args()
	try:
		if(Arguments.replay):
			if(not Arguments.output):
				raise ValueError("--replay requires a separate --output directory")
			Result = replay_manifest(Arguments.manifest, Arguments.output)
		else:
			Result = recheck_manifest(Arguments.manifest)
	except (OSError, ValueError, KeyError, TypeError) as Failure:
		Result = {"status": "invalid", "exact_root_passed": False, "reasons": [str(Failure)]}
	print(json.dumps(Result, ensure_ascii=False, indent="\t"))
	return 0 if Result.get("exact_root_passed") else 1


if(__name__ == "__main__"):
	sys.exit(main())
