#!/usr/bin/env python3
"""Exercise DSH layout replay in disposable repositories; no harness actions."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dsh_sync", ROOT / "scripts/sync-from-parent.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)
COMMIT = "a" * 40


def tree_hashes(Root):
	return {
		Item.relative_to(Root).as_posix(): hashlib.sha256(Item.read_bytes()).hexdigest()
		for Item in Root.rglob("*") if Item.is_file() and "__pycache__" not in Item.parts
	}


class SyncControls(unittest.TestCase):
	def setUp(self):
		self.Directory = tempfile.TemporaryDirectory(prefix="dsh-sync-unit-")
		self.Root = Path(self.Directory.name)
		self.Parent = self.Root / "parent"
		self.Dsh = self.Root / "dsh"
		self.Preview = self.Root / "preview"
		self.Dsh.mkdir()
		for Name in ("package.json", "index.mjs", "cordis.patch.yml", "README.md", "README_EN.md", "AGENTS.md", "AGENTS_HISTORY.md", "LICENSE"):
			Content = '{"version": "2.0.0"}\n' if Name == "package.json" else "Original checkout content\n"
			SYNC.write_norm(self.Dsh / Name, Content)
		SYNC.write_norm(self.Dsh / "skills/untouched.txt", "Original installed bundle\n")
		SYNC.write_norm(self.Dsh / "upstream.lock.json", '{"original": true}\n')
		SYNC.write_norm(self.Dsh / "tests/smoke_doctor.py", "# DSH-owned doctor\n")
		for Name, Relative in SYNC.BUNDLE_SOURCES.items():
			Bundle = self.Parent / Relative
			SYNC.write_norm(Bundle / "SKILL.md", f"---\nname: {Name}\ndescription: Research guidance\n---\n\n# Research\n\nChoose methods for the question.\n\n[Release history](references/changelog.md).\n")
			SYNC.write_norm(Bundle / "references/changelog.md", "# Parent releases\n\n2.0.0\n")
			for Extra in SYNC.EXTRA_SOURCES.get(Name, ()):
				(self.Parent / "plugins" / Name / Extra).mkdir(parents=True)
		Manage = self.Parent / SYNC.BUNDLE_SOURCES["manage-math-research-program"]
		SYNC.write_norm(Manage / "references/blueprint-runtime-gateway.md", "In a Codex plugin install, the gateway is `../../runtime/blueprintctl.py` relative to the skill.\n")
		SYNC.write_norm(Manage / "assets/blueprint-accepted-knowledge/tools/query.py", "VALUE = 'gateway'\n")
		SYNC.write_norm(self.Parent / "plugins/manage-math-research-program/runtime/blueprintctl.py", "from pathlib import Path\nprint((Path(__file__).resolve().parents[1] / 'assets/blueprint-accepted-knowledge/tools/query.py').is_file())\n")
		Workflow = self.Parent / "plugins/math-research-workflow/scripts"
		SYNC.write_norm(Workflow / "research_state.py", "VALUE = 'v2-continuity'\n")
		SYNC.write_norm(Workflow / "legacy_pipeline.py", "VALUE = 'v1-compatibility'\n")
		SYNC.write_norm(Workflow / "doctor.py", "raise RuntimeError('Codex-only doctor')\n")
		SYNC.write_norm(self.Parent / "plugins/lean-verify/scripts/lean_feedback.py", "VALUE = 'feedback'\n")
		SYNC.write_norm(self.Parent / "plugins/lean-verify/scripts/LeanVerifyProbe.lean.template", "-- Parent compiler probe\n")
		SYNC.write_norm(self.Parent / "plugins/lean-verify/scripts/run_manifest.schema.json", '{"type": "object"}\n')
		SYNC.write_norm(self.Parent / "plugins/lean-verify/scripts/tests/test_portable.py", "import unittest\n")
		SYNC.write_norm(self.Parent / "plugins/lean-verify/scripts/tests/_probe/output.json", "{}\n")
		SYNC.write_norm(self.Parent / "plugins/lean-verify/scripts/tests/real-active/temporary.txt", "temporary\n")
		SYNC.write_norm(self.Parent / "tests/test_research_state.py", 'import sys\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nsys.path.insert(0, str(ROOT / "plugins/math-research-workflow/scripts"))\nfrom research_state import VALUE\nprint(VALUE)\n')
		SYNC.write_norm(self.Parent / "tests/smoke_pipeline_gate.py", 'from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nSCRIPT = ROOT / "plugins" / "math-research-workflow" / "scripts" / "legacy_pipeline.py"\nARGS = ["--legacy-v1"]\n')
		SYNC.write_norm(self.Parent / "tests/smoke_doctor.py", "# Codex-owned doctor\n")
		SYNC.write_norm(self.Parent / "tests/fixtures/example/input.txt", "original fixture\n")
		SYNC.write_norm(self.Parent / "tests/fixtures/lean-v2-runtime/lean-toolchain", "leanprover/lean4:v4.31.0\n")
		SYNC.write_norm(self.Parent / "tests/fixtures/lean-v2-runtime/lakefile.toml", 'name = "lean-verifier-runtime"\nversion = "0.1.0"\ndefaultTargets = []\n')
		SYNC.write_norm(self.Parent / "tests/fixtures/lean-v2-runtime/lake-manifest.json", '{"version": "1.2.0", "packagesDir": ".lake/packages", "packages": [], "name": "lean-verifier-runtime", "lakeDir": ".lake", "fixedToolchain": false}\n')
		Cache = self.Parent / "tests/fixtures/lean-v2-runtime/.lake/ignored.olean"
		Cache.parent.mkdir(parents=True)
		Cache.write_bytes(b"\xff\xfe\x00")
		SYNC.write_norm(self.Parent / "docs/v2.0-guide.md", "[Runtime](../plugins/manage-math-research-program/skills/manage-math-research-program/references/blueprint-runtime-gateway.md)\n[Plan](v2.0-refactor-plan.md#scope)\n")
		SYNC.write_norm(self.Parent / "docs/v2.0-refactor-plan.md", "# Historical design\n")
		SYNC.write_norm(self.Parent / "docs/pipeline-full-flow.md", "[Guide](v2.0-guide.md)\n")
		self.RepoPatch = patch.object(SYNC, "REPO", self.Dsh)
		self.HeadPatch = patch.object(SYNC, "upstream_head", return_value=COMMIT)
		self.DirtyPatch = patch.object(SYNC, "upstream_dirty", return_value=True)
		self.RepoPatch.start()
		self.HeadPatch.start()
		self.DirtyPatch.start()
		self.addCleanup(self.Directory.cleanup)
		self.addCleanup(self.RepoPatch.stop)
		self.addCleanup(self.HeadPatch.stop)
		self.addCleanup(self.DirtyPatch.stop)

	def preview(self):
		return SYNC.write_preview(self.Parent, self.Preview, COMMIT)

	def test_preview_keeps_both_sources_unchanged_and_copies_new_layout(self):
		DshBefore, ParentBefore = tree_hashes(self.Dsh), tree_hashes(self.Parent)
		Lock = self.preview()
		self.assertEqual(tree_hashes(self.Dsh), DshBefore)
		self.assertEqual(tree_hashes(self.Parent), ParentBefore)
		Metadata = json.loads((self.Preview / "PREVIEW.json").read_text())
		self.assertFalse(Metadata["release_ready"])
		self.assertTrue(Metadata["source_dirty"])
		self.assertEqual(Lock["upstream_commit"], COMMIT)
		for Relative in (
			"skills/math-research-workflow/scripts/research_state.py",
			"skills/math-research-workflow/scripts/legacy_pipeline.py",
			"skills/lean-verify/scripts/lean_feedback.py",
			"skills/lean-verify/scripts/LeanVerifyProbe.lean.template",
			"skills/lean-verify/scripts/run_manifest.schema.json",
			"skills/lean-verify/scripts/tests/test_portable.py",
			"skills/manage-math-research-program/runtime/blueprintctl.py",
			"tests/test_research_state.py", "tests/fixtures/example/input.txt", "docs/v2.0-guide.md",
			"tests/fixtures/lean-v2-runtime/lean-toolchain",
			"tests/fixtures/lean-v2-runtime/lakefile.toml",
			"tests/fixtures/lean-v2-runtime/lake-manifest.json",
		):
			self.assertTrue((self.Preview / Relative).is_file(), Relative)
		self.assertFalse((self.Preview / "tests/fixtures/lean-v2-runtime/.lake").exists())
		for Name in SYNC.LEAN_RUNTIME_PACKAGE_FILES:
			Relative = Path(SYNC.LEAN_RUNTIME_FIXTURE) / Name
			self.assertEqual((self.Preview / Relative).read_bytes(), (self.Parent / Relative).read_bytes())
		self.assertFalse((self.Preview / "skills/math-research-workflow/scripts/doctor.py").exists())
		self.assertFalse((self.Preview / "skills/lean-verify/scripts/tests/_probe").exists())
		self.assertFalse((self.Preview / "skills/lean-verify/scripts/tests/real-active").exists())
		self.assertEqual((self.Preview / "tests/smoke_doctor.py").read_text(), "# DSH-owned doctor\n")
		for Name in SYNC.SKILL_NAMES:
			Source = SYNC.read_norm(self.Parent / SYNC.BUNDLE_SOURCES[Name] / "SKILL.md")
			Actual = SYNC.read_norm(self.Preview / "skills" / Name / "SKILL.md")
			self.assertEqual(Actual, SYNC.insert_after_frontmatter(Source, SYNC.RUNTIME_NOTES[Name]))

	def test_incomplete_lean_fixture_is_rejected_before_destination_changes(self):
		Before = tree_hashes(self.Dsh)
		for Name in SYNC.LEAN_RUNTIME_PACKAGE_FILES:
			with self.subTest(file=Name):
				Source = self.Parent / SYNC.LEAN_RUNTIME_FIXTURE / Name
				Content = Source.read_bytes()
				Source.unlink()
				try:
					with self.assertRaisesRegex(ValueError, "missing " + Name):
						SYNC.write_snapshot(self.Parent, self.Dsh, COMMIT)
					self.assertEqual(tree_hashes(self.Dsh), Before)
				finally:
					Source.write_bytes(Content)

	def test_replay_is_deterministic_and_manifest_covers_relocated_runtime(self):
		First = self.preview()
		Other = self.Root / "other"
		Second = SYNC.write_snapshot(self.Parent, Other, COMMIT)
		self.assertEqual(First, Second)
		Bundle = Other / "skills/manage-math-research-program"
		Entries = {}
		for Line in (Bundle / "MANIFEST.sha256").read_text().splitlines():
			Hash, Relative = Line.split("  ", 1)
			self.assertEqual(Hash, SYNC.sha256_norm(Bundle / Relative))
			Entries[Relative] = Hash
		self.assertIn("./runtime/blueprintctl.py", Entries)
		Gateway = subprocess.run([sys.executable, str(Bundle / "runtime/blueprintctl.py")], capture_output=True, text=True)
		self.assertEqual((Gateway.returncode, Gateway.stdout.strip()), (0, "True"))

	def test_rewritten_root_tests_run_and_legacy_selector_is_preserved(self):
		self.preview()
		Result = subprocess.run([sys.executable, str(self.Preview / "tests/test_research_state.py")], capture_output=True, text=True)
		self.assertEqual(Result.returncode, 0, Result.stderr)
		self.assertEqual(Result.stdout.strip(), "v2-continuity")
		Namespace = {}
		exec((self.Preview / "tests/smoke_pipeline_gate.py").read_text(), {"__file__": str(self.Preview / "tests/smoke_pipeline_gate.py")}, Namespace)
		self.assertEqual(Namespace["ARGS"], ["--legacy-v1"])
		self.assertTrue(Namespace["SCRIPT"].is_file())
		for Name, Relative in SYNC.BUNDLE_SOURCES.items():
			for Quote in ('"', "'"):
				Joined = " /\n ".join(Quote + Part + Quote for Part in Relative.split("/"))
				Text = "Result = (Root / " + Joined + ")\n"
				Namespace = {"Root": self.Preview}
				exec(SYNC.rewrite_parent_paths(Text), Namespace)
				self.assertEqual(Namespace["Result"], self.Preview / "skills" / Name)

	def test_guide_links_resolve_locally_or_bind_parent_commit(self):
		self.preview()
		Guide = (self.Preview / "docs/v2.0-guide.md").read_text()
		self.assertIn("../skills/manage-math-research-program/references/blueprint-runtime-gateway.md", Guide)
		self.assertIn(f"/blob/{COMMIT}/docs/v2.0-refactor-plan.md#scope", Guide)
		RuntimeNote = (self.Preview / "skills/manage-math-research-program/references/blueprint-runtime-gateway.md").read_text()
		self.assertIn("In this DSH bundle", RuntimeNote)
		self.assertIn("`runtime/blueprintctl.py`", RuntimeNote)
		self.assertNotIn("../../runtime/", RuntimeNote)

	def test_q9_discovery_is_preserved_and_absent_explicit_replay_fails(self):
		Bundle = self.Parent / SYNC.BUNDLE_SOURCES["manage-math-research-program"]
		Fixture = '''import unittest
from pathlib import Path
import sys
REPO_ROOT = next((Parent for Parent in Path(__file__).resolve().parents if (Parent / "benchmarks/codex-20260908-q9/evidence").is_dir()), None)
def run_replay():
	if(REPO_ROOT is None):
		raise ValueError("frozen Q9 evidence is absent; run this optional replay from the source repository")
	return (REPO_ROOT / "benchmarks/codex-20260908-q9/evidence/proof.txt").read_text()
class Q9ReplayTests(unittest.TestCase):
	@unittest.skipUnless(REPO_ROOT, "optional frozen Q9 evidence is not bundled with installed plugins")
	def test_source(self):
		self.assertEqual(run_replay(), "synthetic source-discovery fixture")
if(__name__ == "__main__"):
	if("--output" in sys.argv):
		run_replay()
	else:
		unittest.main()
'''
		SYNC.write_norm(Bundle / "scripts/tests/test_library_q9_reuse.py", Fixture)
		self.preview()
		Script = self.Preview / "skills/manage-math-research-program/scripts/tests/test_library_q9_reuse.py"
		self.assertEqual(Script.read_text(), Fixture)
		Missing = subprocess.run([sys.executable, str(Script), "-v"], capture_output=True, text=True)
		self.assertEqual(Missing.returncode, 0, Missing.stderr)
		self.assertIn("skipped=1", Missing.stderr)
		self.assertIn("optional frozen Q9 evidence is not bundled", Missing.stderr)
		Invalid = subprocess.run([sys.executable, str(Script), "--output"], capture_output=True, text=True)
		self.assertNotEqual(Invalid.returncode, 0)
		self.assertIn("frozen Q9 evidence is absent", Invalid.stderr)
		self.assertNotIn("skipped=", Invalid.stderr)
		SYNC.write_norm(self.Preview / "benchmarks/codex-20260908-q9/evidence/proof.txt", "synthetic source-discovery fixture")
		Valid = subprocess.run([sys.executable, str(Script), "-v"], capture_output=True, text=True)
		self.assertEqual(Valid.returncode, 0, Valid.stderr)
		self.assertNotIn("skipped=", Valid.stderr)

	def test_lean_tests_write_to_external_temporary_storage(self):
		Tests = self.Parent / "plugins/lean-verify/scripts/tests"
		for Name, Directory in (
			("test_v2_verifier.py", 'Path(__file__).parent'),
			("test_v2_lean_real.py", 'os.environ.get("LEAN_VERIFY_TEST_TMPDIR", Path(__file__).parent)'),
		):
			Fixture = 'import os\nimport tempfile\nfrom pathlib import Path\nwith tempfile.TemporaryDirectory(prefix="unit-", dir=' + Directory + ') as Folder:\n\tprint(Folder)\n'
			SYNC.write_norm(Tests / Name, Fixture)
		self.preview()
		External = self.Root / "test-output"
		External.mkdir()
		Before = tree_hashes(self.Preview)
		for Name in ("test_v2_verifier.py", "test_v2_lean_real.py"):
			Script = self.Preview / "skills/lean-verify/scripts/tests" / Name
			Env = dict(os.environ, LEAN_VERIFY_TEST_TMPDIR=str(External))
			Result = subprocess.run([sys.executable, str(Script)], env=Env, capture_output=True, text=True)
			self.assertEqual(Result.returncode, 0, Result.stderr)
			self.assertEqual(Path(Result.stdout.strip()).parent, External)
			Env.pop("LEAN_VERIFY_TEST_TMPDIR", None)
			Result = subprocess.run([sys.executable, str(Script)], env=Env, capture_output=True, text=True)
			self.assertEqual(Result.returncode, 0, Result.stderr)
			self.assertFalse(Path(Result.stdout.strip()).is_relative_to(self.Preview))
		self.assertEqual(tree_hashes(self.Preview), Before)

	def test_dirty_source_and_wrong_commit_cannot_change_live_bundles(self):
		Before = tree_hashes(self.Dsh)
		for Extra in ([], ["--expect-commit", "b" * 40]):
			with patch.object(sys, "argv", ["sync-from-parent.py", "--upstream", str(self.Parent), *Extra]), contextlib.redirect_stderr(io.StringIO()):
				self.assertEqual(SYNC.main(), 1)
		self.assertEqual(tree_hashes(self.Dsh), Before)
		for Destination in (self.Dsh / "preview", self.Parent / "preview", self.Dsh):
			with self.assertRaises(ValueError):
				SYNC.write_preview(self.Parent, Destination, COMMIT)
		self.assertEqual(tree_hashes(self.Dsh), Before)

	@unittest.skipUnless(shutil.which("node"), "Node.js is required to execute the optional workflow template")
	def test_optional_template_dispatches_only_supplied_tasks_in_dependency_order(self):
		Script = self.Root / "template-control.cjs"
		Harness = '''const assert = require("node:assert/strict")
const Template = process.env.DSH_TEMPLATE
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor
const Run = new AsyncFunction("args", "phase", "pipeline", "agent", Template)
;(async () =>
{
	const Calls = [], Finished = new Set()
	const Output = await Run({tasks: [
		{id: "read", prompt: "Read a definition"},
		{id: "calculate", prompt: "Calculate a bound"},
		{id: "compare", prompt: "Compare routes", deps: ["read", "calculate"]}
	], verify: true}, () => {}, (Wave, Work) => Promise.all(Wave.map(Work)), async (Prompt, Options) =>
	{
		if(Options.label === "compare")
		{
			assert.deepEqual([...Finished].sort(), ["calculate", "read"])
		}
		Calls.push({Prompt, Options})
		await Promise.resolve()
		Finished.add(Options.label)
		return "execution output"
	})
	assert.deepEqual(Output.results.map(Item => Item.id), ["read", "calculate", "compare"])
	assert.equal(Calls.length, 3)
	assert.equal(Calls[0].Prompt, "Read a definition")
	for(const Tasks of [
		[{id: "x", prompt: "p", deps: ["missing"]}],
		[{id: "x", prompt: "p", deps: ["y"]}, {id: "y", prompt: "p", deps: ["x"]}],
		[{id: "x", prompt: "p"}, {id: "x", prompt: "p"}]
	])
	{
		let Dispatched = 0
		await assert.rejects(() => Run({tasks: Tasks}, () => {}, (Wave, Work) => Promise.all(Wave.map(Work)), async () => { Dispatched++ }))
		assert.equal(Dispatched, 0)
	}
	console.log("optional template controls passed")
})().catch(Error => { console.error(Error); process.exitCode = 1 })
'''
		Script.write_text(Harness, encoding="utf-8")
		Env = dict(os.environ, DSH_TEMPLATE=SYNC.WORKFLOW_TEMPLATE_JS)
		Result = subprocess.run([shutil.which("node"), str(Script)], capture_output=True, text=True, env=Env)
		self.assertEqual(Result.returncode, 0, Result.stderr)
		self.assertIn("optional template controls passed", Result.stdout)


if(__name__ == "__main__"):
	unittest.main()
