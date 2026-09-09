#!/usr/bin/env python3
"""Behavior controls for execution, source locations, ownership, and route closure."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lean_runtime import aggregate_results, full_output, hash_json, process_identity, run, scan_file, sha256_file, write_json
from lake_build_guard import acquire, release
from lean_routes import evaluate_routes
from verify_lean_project import make_parser, verify_project


class VerifierControls(unittest.TestCase):
	def setUp(self):
		self.Directory = tempfile.TemporaryDirectory(prefix="unit-", dir=os.environ.get("LEAN_VERIFY_TEST_TMPDIR"))
		self.Root = Path(self.Directory.name).resolve()

	def tearDown(self):
		self.Directory.cleanup()

	def test_incomplete_results_never_aggregate_to_success(self):
		for Status in ("missing", "timeout", "unavailable", "failed", "unknown"):
			with self.subTest(Status=Status):
				Result = aggregate_results([{"status": "passed", "exit_code": 0}, {"status": Status, "exit_code": None}])
				self.assertNotEqual(Result["status"], "passed")
				self.assertNotEqual(Result["exit_code"], 0)
		self.assertEqual(aggregate_results([])["status"], "not_run")
		self.assertEqual(aggregate_results([{"exit_code": None}])["status"], "unknown")

	def test_comments_preserve_actual_locations(self):
		Source = self.Root / "Comments.lean"
		Source.write_text('/- sorry\n/- admit -/ axiom bogus : False\n-/\ndef note := r##"sorry /- admit -/"##\n-- sorry\ntheorem unfinished : True := by\n  sorry\n')
		self.assertEqual([{Key: Hit[Key] for Key in ("line", "kind")} for Hit in scan_file(Source, set())], [{"line": 7, "kind": "sorry"}])

	def test_complete_logs_are_not_truncated(self):
		Result = run([sys.executable, "-c", "import sys; print('x'*30000); print('y'*20000, file=sys.stderr)"], self.Root, log_dir=self.Root / "logs")
		self.assertEqual(Result["status"], "passed")
		self.assertEqual(len(full_output(Result)), 30001)
		self.assertEqual(len(full_output(Result, "stderr")), 20001)
		self.assertLess(len(Result["stdout"]), len(full_output(Result)))

	def test_timeout_retains_partial_output(self):
		Result = run([sys.executable, "-u", "-c", "import sys,time; print('before-timeout',flush=True); print('partial-error',file=sys.stderr,flush=True); time.sleep(20)"], self.Root, timeout=0.3, log_dir=self.Root / "logs")
		self.assertEqual(Result["status"], "timeout")
		self.assertIsNone(Result["exit_code"])
		self.assertIn("before-timeout", full_output(Result))
		self.assertIn("partial-error", full_output(Result, "stderr"))

	def test_mock_timeout_cannot_pass(self):
		class TimedProcess:
			pid = 99999999
			returncode = None
			def communicate(self, Data, timeout):
				raise subprocess.TimeoutExpired("mock", timeout, output=b"not-used-as-complete-output")
			def wait(self, timeout):
				self.returncode = -9
		CleanupTarget = "lean_runtime.subprocess.run" if os.name == "nt" else "lean_runtime.os.killpg"
		with patch("lean_runtime.subprocess.Popen", return_value=TimedProcess()), patch(CleanupTarget) as Cleanup:
			Result = run(["mock"], self.Root, timeout=0.1, log_dir=self.Root / "logs")
		if(os.name == "nt"):
			Cleanup.assert_called_once_with(["taskkill", "/PID", str(TimedProcess.pid), "/T", "/F"], capture_output=True, timeout=10)
		else:
			Cleanup.assert_called_once_with(TimedProcess.pid, signal.SIGKILL)
		self.assertEqual(Result["status"], "timeout")
		self.assertIsNone(Result["exit_code"])
		self.assertNotEqual(aggregate_results([Result])["exit_code"], 0)

	def test_unavailable_tool_and_missing_file(self):
		Result = run([str(self.Root / "no-compiler")], self.Root, log_dir=self.Root / "logs")
		self.assertEqual(Result["status"], "unavailable")
		Arguments = make_parser().parse_args(["--project", str(self.Root), "--build", "--build-targets", "Missing.lean", "--direct", "--lean", str(self.Root / "missing-lean"), "--lake", str(self.Root / "missing-lake"), "--output", str(self.Root / "output")])
		Manifest, _ = verify_project(Arguments)
		self.assertFalse(Manifest["machine_verification_passed"])
		self.assertFalse(Manifest["exact_root_passed"])
		self.assertEqual(Manifest["build"]["status"], "missing")

	def test_read_only_scan_runs_no_compiler(self):
		(self.Root / "Target.lean").write_text("theorem target : True := by sorry\n")
		Arguments = make_parser().parse_args(["--project", str(self.Root), "--output", str(self.Root / "output")])
		with patch("lean_runtime.subprocess.Popen", side_effect=AssertionError("no process expected")):
			Manifest, _ = verify_project(Arguments)
		self.assertFalse(Manifest["machine_verification_passed"])
		self.assertEqual(Manifest["machine"]["status"], "not_run")

	def test_guard_live_process_token_and_unlimited_iterations(self):
		First = acquire(self.Root, "source1")
		self.assertEqual(First["status"], "acquired")
		self.assertEqual(acquire(self.Root, "source2")["status"], "conflict")
		self.assertEqual(release(self.Root, "incorrect-token")["status"], "conflict")
		self.assertEqual(release(self.Root, First["token"])["status"], "released")
		for Index in range(7):
			Record = acquire(self.Root, str(Index))
			self.assertEqual(Record["status"], "acquired")
			release(self.Root, Record["token"])

	def test_guard_rejects_pid_reuse_and_retains_legacy_unknown(self):
		State = self.Root / ".lake"
		State.mkdir()
		write_json(State / "build_guard.lock", {"owner_pid": os.getpid(), "process_identity": "old-incarnation", "token": "old"})
		Record = acquire(self.Root)
		self.assertEqual(Record["status"], "acquired")
		release(self.Root, Record["token"])
		(State / "build_guard.lock").write_text("2025-01-01\n")
		self.assertEqual(acquire(self.Root)["status"], "conflict")

	@patch("lean_routes.recheck_manifest", return_value={"exact_root_passed": True, "semantic_sha256": hash_json("leaf-v1")})
	def test_route_cycle_open_leaves_and_alternative(self, Recheck):
		Evidence = self.Root / "evidence.json"
		write_json(Evidence, {"exact_root_passed": True, "target": {"semantic_sha256": "leaf-v1"}, "evidence": {"status": "current"}})
		Graph = {"nodes": [
			{"id": "root", "semantic_sha256": "root-v1", "routes": [{"id": "cyclic", "statement_sha256": "root-v1", "dependencies": ["cycle"]}, {"id": "two-open", "statement_sha256": "root-v1", "dependencies": ["one", "two"]}]},
			{"id": "cycle", "semantic_sha256": "cycle-v1", "routes": [{"id": "back", "statement_sha256": "cycle-v1", "dependencies": ["root"]}]},
			{"id": "one", "semantic_sha256": "one-v1"}, {"id": "two", "semantic_sha256": "two-v1"},
			{"id": "leaf", "semantic_sha256": "leaf-v1", "evidence": {"manifest": str(Evidence), "sha256": sha256_file(Evidence)}}]}
		for Node in Graph["nodes"]:
			Node["semantic_sha256"] = hash_json(Node["semantic_sha256"])
			for Route in Node.get("routes", []):
				Route["statement_sha256"] = Node["semantic_sha256"]
		self.assertEqual(evaluate_routes(Graph, "root")["status"], "open")
		Graph["nodes"][0]["routes"].append({"id": "alternative", "statement_sha256": hash_json("root-v1"), "dependencies": ["leaf"]})
		Result = evaluate_routes(Graph, "root")
		self.assertEqual(Result["status"], "ready_to_materialize")
		self.assertEqual(Result["selected_routes"]["root"], "alternative")
		self.assertFalse(Result["exact_root_passed"])
		Graph["nodes"][0]["routes"][-1]["statement_sha256"] = "old-version"
		self.assertEqual(evaluate_routes(Graph, "root")["status"], "open")

	def test_route_rejects_success_flags_without_receipts(self):
		Evidence = self.Root / "forged.json"
		write_json(Evidence, {"exact_root_passed": True, "target": {"semantic_sha256": hash_json("root")}, "evidence": {"status": "current"}})
		Graph = {"nodes": [{"id": "root", "semantic_sha256": hash_json("root"), "evidence": {"manifest": str(Evidence), "sha256": sha256_file(Evidence)}}]}
		Result = evaluate_routes(Graph, "root", Evidence)
		self.assertFalse(Result["exact_root_passed"])
		self.assertNotIn("root", Result["ready_nodes"])
		for Digest in (None, "", "not-a-hash"):
			Graph["nodes"][0]["semantic_sha256"] = Digest
			with self.assertRaises(ValueError):
				evaluate_routes(Graph, "root", Evidence)

	def test_schema_entries_agree_and_reject_incomplete_success(self):
		import jsonschema
		Scripts = Path(__file__).resolve().parents[1]
		Schema = json.loads((Scripts / "run_manifest.schema.json").read_text(encoding="utf-8"))
		self.assertEqual(Schema, json.loads((Scripts.parent / "assets/verification_output.schema.json").read_text(encoding="utf-8")))
		jsonschema.Draft202012Validator.check_schema(Schema)
		Arguments = make_parser().parse_args(["--project", str(self.Root), "--output", str(self.Root / "output")])
		Manifest, _ = verify_project(Arguments)
		jsonschema.validate(Manifest, Schema)
		Manifest["exact_root_passed"] = True
		with self.assertRaises(jsonschema.ValidationError):
			jsonschema.validate(Manifest, Schema)


if(__name__ == "__main__"):
	unittest.main()
