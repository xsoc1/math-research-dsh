#!/usr/bin/env python3
"""Opt-in real Lean controls. Set LEAN_VERIFY_REAL_LEAN to a pinned executable."""

from __future__ import annotations

import json
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lean_feedback import FeedbackSession, LeanLsp, ProtocolFailure
from lean_evidence import payload_digest, recheck_manifest
from lean_routes import evaluate_routes
from lean_runtime import LeanRuntime, hash_json, sha256_file, tool_path, write_json
from verify_lean_project import make_parser, verify_project

LEAN = os.environ.get("LEAN_VERIFY_REAL_LEAN")
LAKE = os.environ.get("LEAN_VERIFY_REAL_LAKE", "lake")


@unittest.skipUnless(LEAN, "set LEAN_VERIFY_REAL_LEAN for actual compiler tests")
class RealLeanControls(unittest.TestCase):
	@classmethod
	def setUpClass(Class):
		Class.Directory = tempfile.TemporaryDirectory(prefix="real-", dir=os.environ.get("LEAN_VERIFY_TEST_TMPDIR"))
		Class.Base = Path(Class.Directory.name).resolve()
		Class.Counter = 0
		Class.Results = []

	@classmethod
	def tearDownClass(Class):
		Output = os.environ.get("LEAN_VERIFY_TEST_REPORT")
		if(Output):
			write_json(Path(Output), {"scope": "real Lean and LSP tests; no full Mathlib/project build", "results": Class.Results})
		if(os.environ.get("LEAN_VERIFY_KEEP_TEST_ARTIFACTS")):
			Class.Directory._finalizer.detach()
			print("Retained real Lean artifacts:", Class.Base)
		else:
			Class.Directory.cleanup()

	def project(self, Source, Dependency=None):
		type(self).Counter += 1
		Root = self.Base / str(type(self).Counter) / "project"
		Root.mkdir(parents=True)
		(Root / "Target.lean").write_text(Source, encoding="utf-8")
		(Root / "lean-toolchain").write_text("leanprover/lean4:v4.31.0\n")
		if(Dependency is not None):
			(Root / "Dependency.lean").write_text(Dependency, encoding="utf-8")
		return Root

	def verify(self, Root, Expected="True", Extra=()):
		Output = Root.parent / ("output-" + str(len(self.Results)))
		Arguments = ["--project", str(Root), "--output", str(Output), "--target-file", "Target.lean", "--declaration", "target", "--direct", "--lean", LEAN, "--lake", LAKE, "--build-timeout", "90"]
		if(Expected):
			Arguments += ["--expected-type", Expected]
		Arguments += list(Extra)
		Manifest, ManifestPath = verify_project(make_parser().parse_args(Arguments))
		import jsonschema
		Schema = json.loads((Path(__file__).resolve().parents[1] / "run_manifest.schema.json").read_text(encoding="utf-8"))
		jsonschema.validate(Manifest, Schema)
		self.assertIn("version 4.31.0,", Manifest["environment"]["lean_version"] or "")
		if(Manifest["exact_root_passed"]):
			Check = recheck_manifest(ManifestPath)
			self.assertTrue(Check["exact_root_passed"], Check)
		self.Results.append({"test": self.id(), "manifest": str(ManifestPath), "manifest_sha256": sha256_file(ManifestPath), "machine": Manifest["machine"], "exact_root_passed": Manifest["exact_root_passed"], "root_closure": Manifest["root_closure"], "semantic": Manifest["semantic"], "axioms": Manifest["target"].get("axioms"), "type": Manifest["target"].get("actual_type"), "environment": Manifest["environment"], "command_statuses": [{Key: Item.get(Key) for Key in ("kind", "status", "elapsed_seconds", "stdout_log", "stderr_log")} for Item in Manifest["build"]["commands"]]})
		return Manifest, ManifestPath

	def assert_closed(self, Manifest):
		self.assertTrue(Manifest["exact_root_passed"], json.dumps(Manifest, ensure_ascii=False)[-6000:])

	def compile_fixture_module(self, Root, SourceRoot, Source, Output):
		Output.parent.mkdir(parents=True, exist_ok=True)
		Runtime = LeanRuntime(Root, Root.parent / "fixture-builds", LEAN, LAKE, True)
		Result = Runtime.execute(["-R", tool_path(SourceRoot, Runtime.Command), "-o", tool_path(Output, Runtime.Command), tool_path(Source, Runtime.Command)], 45, [Output.parent])
		self.assertEqual(Result["status"], "passed", Result)
		self.Results.append({"test": self.id(), "fixture_compile": Result})

	def test_expected_only_external_definition_freshness(self):
		Root = self.project('import ExpectedOnly\ntheorem target : True := True.intro\n')
		Package = Root / ".lake/packages/expected-only"
		Package.mkdir(parents=True)
		Library = Package / ".lake/build/lib/lean"
		(Package / "ExpectedBase.lean").write_text('def expected_base : Prop := True\n', encoding="utf-8")
		(Package / "ExpectedOnly.lean").write_text('import ExpectedBase\ndef expected_goal : Prop := expected_base\n', encoding="utf-8")
		for Name in ("ExpectedBase", "ExpectedOnly"):
			self.compile_fixture_module(Root, Package, Package / (Name + ".lean"), Library / (Name + ".olean"))
		First, FirstPath = self.verify(Root, "expected_goal")
		self.assert_closed(First)
		Graph = {"nodes": [{"id": "root", "semantic_sha256": First["target"]["semantic_sha256"], "evidence": {"manifest": str(FirstPath), "sha256": sha256_file(FirstPath)}}]}
		self.assertTrue(evaluate_routes(Graph, "root", FirstPath)["exact_root_passed"])
		Audit = Root.parent / "expected-review.json"
		write_json(Audit, {"result": "faithful", "reviewer": "test fixture", "notes": "Tests expected-type identity reuse only.", "binding": {Key: First["target"][Key] for Key in ("declaration", "semantic_sha256", "semantic_environment_sha256")}})
		(Package / "ExpectedBase.lean").write_text('def expected_base : Prop := False\n', encoding="utf-8")
		for Name in ("ExpectedBase", "ExpectedOnly"):
			self.compile_fixture_module(Root, Package, Package / (Name + ".lean"), Library / (Name + ".olean"))
		Check = recheck_manifest(FirstPath)
		Routes = evaluate_routes(Graph, "root", FirstPath)
		self.Results.append({"test": self.id(), "changed_expected_recheck": Check, "changed_expected_routes": Routes})
		self.assertFalse(Check["exact_root_passed"], Check)
		self.assertFalse(Routes["exact_root_passed"], Routes)
		self.assertEqual(Routes["ready_nodes"], [])
		Fresh, _ = self.verify(Root, "expected_goal", ("--semantic-audit", str(Audit)))
		self.assertEqual(Fresh["root_closure"]["status"], "target_mismatch")
		self.assertEqual(Fresh["semantic"]["status"], "stale")
		self.assertIn("ExpectedOnly", First["target"]["import_artifacts"])
		self.assertIn("ExpectedBase", First["target"]["import_artifacts"])
		Expected = First["target"]["expected_statement"]
		self.assertIn("expected_base", Expected["definition_hashes"])
		self.assertIn("expected_goal", Expected["definition_hashes"])
		self.assertNotEqual(Expected["semantic_sha256"], Fresh["target"]["expected_statement"]["semantic_sha256"])
		self.assertEqual(Expected["axioms"], [])
		(Package / "ExpectedBase.lean").write_text('theorem expected_assumption : True := by sorry\ndef expected_base : Prop := (fun (_ : True) => True) expected_assumption\n', encoding="utf-8")
		for Name in ("ExpectedBase", "ExpectedOnly"):
			self.compile_fixture_module(Root, Package, Package / (Name + ".lean"), Library / (Name + ".olean"))
		Untrusted, _ = self.verify(Root, "expected_goal")
		self.assertEqual(Untrusted["target"]["comparison"]["status"], "matched")
		self.assertEqual(Untrusted["target"]["axioms"], [])
		self.assertIn("sorryAx", Untrusted["target"]["expected_statement"]["axioms"])
		self.assertEqual(Untrusted["root_closure"]["status"], "open")

	def test_current_module_resolution_rejects_new_shadow(self):
		Root = self.project('import Dependency\ntheorem target : dependency_goal := True.intro\n')
		SourceRoot = Root.parent / "build-input"
		SourceRoot.mkdir()
		Source = SourceRoot / "Dependency.lean"
		Source.write_text('def dependency_goal : Prop := True\n', encoding="utf-8")
		Artifact = Root / ".lake/packages/dependency/.lake/build/lib/lean/Dependency.olean"
		self.compile_fixture_module(Root, SourceRoot, Source, Artifact)
		First, FirstPath = self.verify(Root, "dependency_goal")
		self.assert_closed(First)
		OriginalHashes = {Name: sha256_file(Item["path"]) for Name, Item in First["target"]["import_artifacts"].items()}
		Graph = {"nodes": [{"id": "root", "semantic_sha256": First["target"]["semantic_sha256"], "evidence": {"manifest": str(FirstPath), "sha256": sha256_file(FirstPath)}}]}
		self.assertTrue(evaluate_routes(Graph, "root", FirstPath)["exact_root_passed"])
		Source.write_text('def dependency_goal : Prop := False\n', encoding="utf-8")
		self.compile_fixture_module(Root, SourceRoot, Source, Root / "Dependency.olean")
		self.assertFalse((Root / "Dependency.lean").exists())
		self.assertEqual(OriginalHashes, {Name: sha256_file(Item["path"]) for Name, Item in First["target"]["import_artifacts"].items()})
		Check = recheck_manifest(FirstPath)
		Routes = evaluate_routes(Graph, "root", FirstPath)
		self.Results.append({"test": self.id(), "shadow_recheck": Check, "shadow_routes": Routes, "original_import_hashes_unchanged": True})
		self.assertFalse(Check["exact_root_passed"], Check)
		self.assertIn("module_resolution:Dependency", Check["reasons"])
		self.assertFalse(Routes["exact_root_passed"], Routes)
		self.assertEqual(Routes["ready_nodes"], [])
		Fresh, _ = self.verify(Root, "dependency_goal")
		self.assertFalse(Fresh["exact_root_passed"])
		self.assertEqual(Fresh["machine"]["status"], "failed")
		for Suffix in ("", ".server", ".private"):
			Path(str(Root / "Dependency.olean") + Suffix).unlink(missing_ok=True)
		self.assertTrue(recheck_manifest(FirstPath)["exact_root_passed"])

	def test_erased_notation_context_invalidates_expected_and_source_checks(self):
		for SourceText, Expected in (("True", "expected_goal"), ("expected_goal", "True")):
			with self.subTest(source=SourceText, expected=Expected):
				Root = self.project('import ExpectedOnly\ntheorem target : ' + SourceText + ' := True.intro\n')
				Package = Root / ".lake/packages/notation-provider"
				Package.mkdir(parents=True)
				Source = Package / "ExpectedOnly.lean"
				Artifact = Package / ".lake/build/lib/lean/ExpectedOnly.olean"
				Source.write_text('notation "expected_goal" => True\n', encoding="utf-8")
				self.compile_fixture_module(Root, Package, Source, Artifact)
				First, FirstPath = self.verify(Root, Expected)
				self.assert_closed(First)
				self.assertIn("ExpectedOnly", First["target"]["import_artifacts"])
				self.assertEqual(len(First["target"]["imported_modules"]), First["target"]["loaded_module_count"])
				Graph = {"nodes": [{"id": "root", "semantic_sha256": First["target"]["semantic_sha256"]}]}
				Source.write_text('notation "expected_goal" => False\n', encoding="utf-8")
				self.compile_fixture_module(Root, Package, Source, Artifact)
				Check = recheck_manifest(FirstPath)
				Routes = evaluate_routes(Graph, "root", FirstPath)
				self.Results.append({"test": self.id(), "source_type": SourceText, "expected_type": Expected, "notation_recheck": Check, "notation_routes": Routes})
				self.assertFalse(Check["exact_root_passed"], Check)
				self.assertFalse(Routes["exact_root_passed"], Routes)
				Fresh, _ = self.verify(Root, Expected)
				self.assertFalse(Fresh["exact_root_passed"])
				self.assertEqual(Fresh["root_closure"]["status"], "target_mismatch" if SourceText == "True" else "incomplete")
				Source.write_text('notation "expected_goal" => True\n', encoding="utf-8")
				self.compile_fixture_module(Root, Package, Source, Artifact)
				self.assertTrue(recheck_manifest(FirstPath)["exact_root_passed"])

	def test_quoted_local_import_rebuilds_current_source(self):
		Root = self.project('import «Dependency»\ntheorem target : local_goal := True.intro\n', 'def local_goal : Prop := True\n')
		Cache = Root / ".lake/build/lib/lean/Dependency.olean"
		self.compile_fixture_module(Root, Root, Root / "Dependency.lean", Cache)
		CacheDigest = sha256_file(Cache)
		(Root / "Dependency.lean").write_text('def local_goal : Prop := False\n', encoding="utf-8")
		Failed, FailedPath = self.verify(Root, "local_goal")
		self.assertFalse(Failed["exact_root_passed"], Failed["root_closure"])
		self.assertEqual(Failed["machine"]["status"], "failed")
		self.assertIn("Dependency.lean", [Item.get("file") for Item in Failed["build"]["commands"] if Item.get("kind") == "target"])
		self.assertFalse(recheck_manifest(FailedPath)["exact_root_passed"])
		self.assertEqual(CacheDigest, sha256_file(Cache))
		(Root / "Dependency.lean").write_text('def local_goal : Prop := True\n', encoding="utf-8")
		Fixed, _ = self.verify(Root, "local_goal")
		self.assert_closed(Fixed)
		Nested = self.project('import\n  «Nested».«Dep File»\ntheorem target : local_goal := True.intro\n')
		(Nested / "Nested").mkdir()
		(Nested / "Nested/Dep File.lean").write_text('def local_goal : Prop := True\n', encoding="utf-8")
		Fresh, _ = self.verify(Nested, "local_goal")
		self.assert_closed(Fresh)
		self.assertIn("Nested/Dep File.lean", [Path(Item["file"]).as_posix() for Item in Fresh["build"]["commands"] if Item.get("kind") == "target"])

	def test_saved_evidence_rejects_forged_fields_and_stale_inputs(self):
		Root = self.project('theorem target : True := True.intro\n')
		Manifest, ManifestPath = self.verify(Root)
		self.assert_closed(Manifest)
		self.assertTrue(recheck_manifest(ManifestPath)["exact_root_passed"])
		Mutations = [
			("expected_type", lambda Item: Item["evidence"]["contract"].update(expected_type="False")),
			("tools_empty", lambda Item: Item["evidence"].update(tool_hashes={})),
			("imports_empty", lambda Item: Item["target"].update(import_artifacts={})),
			("configuration_empty", lambda Item: Item["environment"].update(configuration_hashes={})),
			("binary_subset", lambda Item: Item["environment"].update(binary_hashes={"bin/lean.exe": "0" * 64})),
			("compiled_empty", lambda Item: Item["evidence"].update(compiled_artifacts={})),
			("semantic_identity", lambda Item: Item["target"].update(semantic_sha256="0" * 64)),
			("identity_mismatch_erased", lambda Item: Item["evidence"]["contract"].update(semantic_sha256="0" * 64)),
			("scan_exclusion", lambda Item: Item["evidence"].update(snapshot_exclusions=[str(Root)])),
		]
		for Name, Mutate in Mutations:
			with self.subTest(Name=Name):
				Forged = copy.deepcopy(Manifest)
				Mutate(Forged)
				Forged["evidence"]["contract_sha256"] = hash_json(Forged["evidence"]["contract"])
				Forged["report_sha256"] = payload_digest(Forged)
				ForgedPath = Root.parent / (Name + ".json")
				write_json(ForgedPath, Forged)
				self.assertFalse(recheck_manifest(ForgedPath)["exact_root_passed"], Name)
		for Artifact in (Path(next(iter(Manifest["evidence"]["compiled_artifacts"]))), Path(Manifest["target"]["extraction_file"]), Path(Manifest["build"]["commands"][0]["stdout_log"])):
			with self.subTest(Artifact=str(Artifact)):
				Original = Artifact.read_bytes()
				try:
					Artifact.write_bytes(Original + b"\nchanged\n")
					self.assertFalse(recheck_manifest(ManifestPath)["exact_root_passed"])
				finally:
					Artifact.write_bytes(Original)
		(Root / "Target.lean").write_text('theorem target (h : False) : True := True.intro\n')
		Check = recheck_manifest(ManifestPath)
		self.assertFalse(Check["exact_root_passed"])
		self.assertIn("source:Target.lean", Check["reasons"])
		self.Results.append({"test": self.id(), "forgery_controls": [Name for Name, _ in Mutations], "stale_check": Check})

	def test_actual_and_or_routes_require_current_materialized_root(self):
		Root = self.project('theorem target : True := True.intro\n')
		Manifest, ManifestPath = self.verify(Root)
		Digest = Manifest["target"]["semantic_sha256"]
		Evidence = {"manifest": str(ManifestPath), "sha256": sha256_file(ManifestPath)}
		Graph = {"nodes": [
			{"id": "root", "semantic_sha256": Digest, "routes": [
				{"id": "cycle", "statement_sha256": Digest, "dependencies": ["cycle"]},
				{"id": "both", "statement_sha256": Digest, "dependencies": ["one", "two"]}]},
			{"id": "cycle", "semantic_sha256": Digest, "routes": [{"id": "back", "statement_sha256": Digest, "dependencies": ["root"]}]},
			{"id": "one", "semantic_sha256": Digest, "evidence": Evidence},
			{"id": "two", "semantic_sha256": Digest},
			{"id": "unused", "semantic_sha256": hash_json("unproved")}]}
		self.assertEqual(evaluate_routes(Graph, "root")["status"], "open")
		Graph["nodes"][0]["routes"].append({"id": "alternative", "statement_sha256": Digest, "dependencies": ["one"]})
		OrResult = evaluate_routes(Graph, "root")
		self.assertEqual(OrResult["selected_routes"]["root"], "alternative")
		self.assertFalse(OrResult["exact_root_passed"])
		Graph["nodes"][3]["evidence"] = Evidence
		AndResult = evaluate_routes(Graph, "root")
		self.assertEqual(AndResult["selected_routes"]["root"], "both")
		Closed = evaluate_routes(Graph, "root", ManifestPath)
		self.assertTrue(Closed["exact_root_passed"])
		self.assertIn("unused", Closed["open_nodes"])
		(Root / "Target.lean").write_text('theorem target (h : False) : True := True.intro\n')
		Stale = evaluate_routes(Graph, "root", ManifestPath)
		self.assertFalse(Stale["exact_root_passed"])
		self.assertEqual(Stale["ready_nodes"], [])
		self.Results.append({"test": self.id(), "and_result": AndResult, "or_result": OrResult, "closed": Closed, "stale": Stale})

	def test_changed_imported_dependency_invalidates_evidence_and_review(self):
		Root = self.project('import Dependency\ntheorem target : meaning := True.intro\n', 'def meaning : Prop := True\n')
		First, FirstPath = self.verify(Root, "meaning")
		Audit = Root.parent / "review.json"
		Source = Root / "contract.md"
		Source.write_text("The named proposition means True.\n")
		Review = {"result": "faithful", "reviewer": "test fixture", "notes": "Only a reuse control, not a mathematical review.", "binding": {Key: First["target"][Key] for Key in ("declaration", "semantic_sha256", "semantic_environment_sha256")}, "source_hashes": {"contract.md": sha256_file(Source)}}
		write_json(Audit, Review)
		Second, _ = self.verify(Root, "meaning", ("--semantic-audit", str(Audit)))
		self.assertTrue(Second["semantic"]["reused"])
		Source.write_text("The intended mathematical contract changed.\n")
		Third, _ = self.verify(Root, "meaning", ("--semantic-audit", str(Audit)))
		self.assertEqual(Third["semantic"]["status"], "stale")
		(Root / "Dependency.lean").write_text('def meaning : Prop := 1 = 1\n')
		(Root / "Target.lean").write_text('import Dependency\ntheorem target : meaning := rfl\n')
		self.assertFalse(recheck_manifest(FirstPath)["exact_root_passed"])
		Changed, _ = self.verify(Root, "meaning", ("--expect-manifest", str(FirstPath), "--semantic-audit", str(Audit)))
		self.assertFalse(Changed["exact_root_passed"])
		self.assertEqual(Changed["semantic"]["status"], "stale")

	def test_nested_comments_success_no_expected_and_missing_root(self):
		Root = self.project('/- sorry\n/- admit /- nested axiom liar : False -/ -/\n-/\ndef note := r##"sorry /- admit -/"##\ntheorem target : True := True.intro\n')
		Manifest, _ = self.verify(Root)
		self.assert_closed(Manifest)
		for Kind in ("inspector_compile", "declaration_inspection"):
			Records = [Item for Item in Manifest["build"]["commands"] if Item.get("kind") == Kind]
			self.assertEqual(len(Records), 1)
			self.assertEqual(Path(Records[0]["cwd"]), Root, "generated inspection must retain the project's toolchain and Lake context")
		self.assertEqual(Manifest["sorry_axiom_hits"], [])
		self.assertEqual(Manifest["target"]["axioms"], [])
		Manifest, _ = self.verify(Root, Expected=None)
		self.assertTrue(Manifest["machine_verification_passed"])
		self.assertFalse(Manifest["exact_root_passed"])
		self.assertEqual(Manifest["root_closure"]["status"], "declaration_closed_uncompared")
		Manifest, _ = self.verify(Root, Extra=("--declaration", "absent"))
		self.assertFalse(Manifest["machine_verification_passed"])

	def test_failed_proof_and_unfinished_comment(self):
		Root = self.project('theorem target : False := True.intro\n')
		Manifest, _ = self.verify(Root, "False")
		self.assertFalse(Manifest["machine_verification_passed"])
		self.assertFalse(Manifest["exact_root_passed"])
		(Root / "Target.lean").write_text('/- unfinished comment\ntheorem target : True := True.intro\n')
		Manifest, _ = self.verify(Root)
		self.assertFalse(Manifest["machine_verification_passed"])

	def test_imported_sorry_and_definition_type_dependencies(self):
		Root = self.project('import Dependency\ntheorem target : hidden_value = hidden_value := rfl\n', 'theorem hidden_proof : False := by sorry\nnoncomputable def hidden_value : Nat := False.elim hidden_proof\n')
		Manifest, _ = self.verify(Root, "hidden_value = hidden_value", Extra=("--whitelist", "sorry,admit,axiom"))
		self.assertTrue(Manifest["machine"]["execution_passed"])
		self.assertFalse(Manifest["exact_root_passed"])
		self.assertIn("sorryAx", Manifest["target"]["unexpected_axioms"])
		Dependencies = {Item["name"]: Item for Item in Manifest["target"]["dependencies"]}
		self.assertIn("hidden_value", Dependencies["target"]["type_dependencies"])
		self.assertIn("hidden_proof", Dependencies["hidden_value"]["body_dependencies"])
		self.assertEqual(Manifest["sorry_axiom_hits"], [])

	def test_extra_axiom_and_standard_axiom_subset(self):
		Root = self.project('axiom extra : False\nnoncomputable def hidden : Nat := False.elim extra\ntheorem target : hidden = hidden := rfl\n')
		Manifest, _ = self.verify(Root, "hidden = hidden")
		self.assertIn("extra", Manifest["target"]["unexpected_axioms"])
		self.assertFalse(Manifest["exact_root_passed"])
		(Root / "Target.lean").write_text('theorem target (A : Type) (h : Nonempty A) : Nonempty A := ⟨Classical.choice h⟩\n')
		Manifest, _ = self.verify(Root, "∀ (A : Type), Nonempty A → Nonempty A")
		self.assert_closed(Manifest)
		self.assertEqual(Manifest["target"]["axioms"], ["Classical.choice"])

	def test_conditional_proof_cannot_close_unconditional_target(self):
		Root = self.project('theorem target (h : False) : True := True.intro\n')
		Manifest, _ = self.verify(Root)
		self.assertTrue(Manifest["machine"]["execution_passed"])
		self.assertFalse(Manifest["exact_root_passed"])
		self.assertEqual(Manifest["root_closure"]["status"], "target_mismatch")
		Manifest, _ = self.verify(Root, "False → True")
		self.assert_closed(Manifest)

	def test_universe_and_typeclass_fidelity(self):
		Root = self.project('theorem target.{u} {A : Sort u} (x : A) : x = x := rfl\n')
		Manifest, _ = self.verify(Root, "∀ {A : Sort u} (x : A), x = x", ("--universes", "u"))
		self.assert_closed(Manifest)
		(Root / "Target.lean").write_text('theorem target {A : Type} (x : A) : x = x := rfl\n')
		Manifest, _ = self.verify(Root, "∀ {A : Sort u} (x : A), x = x", ("--universes", "u"))
		self.assertFalse(Manifest["exact_root_passed"])
		(Root / "Target.lean").write_text('theorem target (A : Type) [Inhabited A] : True := True.intro\n')
		Manifest, _ = self.verify(Root, "∀ (A : Type), True")
		self.assertFalse(Manifest["exact_root_passed"])
		self.assertIn("instImplicit", json.dumps(Manifest["target"]["binder_kinds"]))

	def test_semantic_audit_reuse_definition_and_environment_invalidation(self):
		Root = self.project('def meaning : Prop := True\ntheorem target : meaning := True.intro\n')
		First, FirstPath = self.verify(Root, "meaning")
		self.assert_closed(First)
		AuditPath = Root.parent / "review.json"
		write_json(AuditPath, {"result": "faithful", "reviewer": "test reviewer", "notes": "The recorded definition means True.", "independence": "test_fixture_not_independent_review", "binding": {Key: First["target"][Key] for Key in ("declaration", "semantic_sha256", "environment_sha256")}})
		(Root / "Target.lean").write_text('def meaning : Prop := True\ntheorem target : meaning := by exact True.intro\n')
		Second, _ = self.verify(Root, "meaning", ("--expect-manifest", str(FirstPath), "--semantic-audit", str(AuditPath)))
		self.assert_closed(Second)
		self.assertTrue(Second["semantic"]["reused"])
		(Root / "Target.lean").write_text('def meaning : Prop := 1 = 1\ntheorem target : meaning := rfl\n')
		Third, _ = self.verify(Root, "meaning", ("--expect-manifest", str(FirstPath), "--semantic-audit", str(AuditPath)))
		self.assertFalse(Third["exact_root_passed"])
		self.assertEqual(Third["semantic"]["status"], "stale")
		self.assertIn("definition:meaning", Third["target"]["identity_mismatches"])
		(Root / "Target.lean").write_text('def meaning : Prop := True\ntheorem target : meaning := True.intro\n')
		(Root / "lake-manifest.json").write_text('{"test_environment_revision":2}\n')
		Fourth, _ = self.verify(Root, "meaning", ("--expect-manifest", str(FirstPath), "--semantic-audit", str(AuditPath)))
		self.assertFalse(Fourth["exact_root_passed"])
		self.assertIn("semantic_environment_sha256", Fourth["target"]["identity_mismatches"])

	def test_lsp_versions_goals_hover_symbols_and_cli_fallback(self):
		Root = self.project('theorem target : True := by\n  trivial\n')
		Runtime = LeanRuntime(Root, Root.parent / "feedback", LEAN, LAKE, True)
		Session = FeedbackSession(Runtime, Timeout=45, Backend="lsp")
		try:
			First = Session.query({"file": "Target.lean", "action": "goals", "line": 1, "character": 2})
			self.assertEqual(First["status"], "complete", First)
			self.assertEqual(First["backend"], "lsp")
			self.assertIn("True", json.dumps(First.get("goals")))
			Second = Session.query({"file": "Target.lean", "action": "hover", "line": 0, "character": 10})
			self.assertEqual(First["session_id"], Second["session_id"])
			self.assertIsNotNone(Second.get("hover"))
			Symbols = Session.query({"file": "Target.lean", "action": "symbols", "query": "target"})
			self.assertTrue(Symbols["symbols"])
			Bad = Session.query({"file": "Target.lean", "action": "diagnostics", "text": "theorem target : False := True.intro\n"})
			self.assertEqual(Bad["session_id"], First["session_id"])
			self.assertGreater(Bad["version"], First["version"])
			self.assertTrue(any(Item.get("severity") == 1 for Item in Bad["diagnostics"]))
			Fixed = Session.query({"file": "Target.lean", "action": "diagnostics"})
			self.assertGreater(Fixed["version"], Bad["version"])
			self.assertEqual(Fixed["diagnostics"], [])
			(Root / "lake-manifest.json").write_text('{"test_environment_revision":2}\n')
			Changed = Session.query({"file": "Target.lean", "action": "diagnostics"})
			self.assertNotEqual(Changed["session_id"], Fixed["session_id"])
			self.Results.append({"test": self.id(), "lsp_first": First, "lsp_bad_version": Bad["version"], "lsp_fixed_version": Fixed["version"], "lsp_environment_restart": Changed["session_id"] != Fixed["session_id"]})
		finally:
			Session.close()
		Fallback = FeedbackSession(Runtime, Timeout=45, Backend="auto")
		try:
			with patch("lean_feedback.LeanLsp", side_effect=ProtocolFailure("simulated missing LSP")):
				Result = Fallback.query({"file": "Target.lean", "action": "diagnostics", "text": "theorem target : False := True.intro\n"})
			self.assertEqual(Result["backend"], "cli")
			self.assertEqual(Result["status"], "failed")
			self.assertFalse(Result["exact_root_passed"])
			self.assertTrue(Result["diagnostics"])
		finally:
			Fallback.close()


if(__name__ == "__main__"):
	unittest.main()
