#!/usr/bin/env python3
"""Exercise experience scope, route comparison and human-owned page regions."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_experience as experience
import research_library as library


class ExperienceTests(unittest.TestCase):
	def setUp(self):
		self.Temp = tempfile.TemporaryDirectory()
		self.Root = Path(self.Temp.name)
		self.Data = dict(title="Scoped method limit", question="Can the relaxation prove the bound?", outcome="failed", failure_kind="method_limit",
			scope="The relaxation on a compact parameter interval.", mechanism="The relaxation discards the angular dependency.",
			transformations=["retain angular dependence", "polynomial certificate"],
			reconsider_when=["A sharp angular comparison becomes available."], not_applicable_to=["The original conjecture is not disproved."])
		self.First = experience.record_experience(self.Root, self.Data)
		self.Second = experience.record_experience(self.Root, dict(title="Successful refinement", conclusion="A conditional bound was obtained.", outcome="success", scope=self.Data["scope"], transformations=["retain angular dependence"]))
		self.Hypothesis = dict(explanation="Retaining the angular dependency may be decisive.", scope="Related compact-domain relaxations only.", prediction="The sharper relaxation will close a held-out subinterval.", test="Check its exact positivity certificate on the held-out subinterval.", falsifier="An admissible nonpositive witness.")

	def tearDown(self):
		self.Temp.cleanup()

	def test_record_index_and_reconsideration_are_searchable(self):
		library.make_index(self.Root)
		Hit = library.query_tools(self.Root, "sharp angular comparison")["hits"][0]
		self.assertEqual(Hit["kind"], "experience")
		self.assertEqual(Hit["experience"]["failure_kind"], "method_limit")
		self.assertEqual(Hit["experience"]["not_applicable_to"], self.Data["not_applicable_to"])
		self.assertEqual(Hit["experience"]["reconsider_when"], self.Data["reconsider_when"])
		library.annotate(self.Root, self.First["location"], text="A future route supplies the missing angular lemma.", kind="reopen trigger")
		self.assertTrue(library.query_tools(self.Root, "future route")["hits"])

	def test_no_return_does_not_turn_into_a_counterexample(self):
		Saved = experience.record_experience(self.Root, dict(question="Did the worker return?", outcome="no_return", mechanism="No artifact; cause unknown.", reconsider_when=["Artifacts or a new authorized attempt become available."]))
		Record = experience.read_route(self.Root, Saved["location"])
		self.assertEqual(Record["experience"]["outcome"], "no_return")
		self.assertEqual(Record["experience"]["failure_kind"], "infrastructure")
		self.assertEqual(Record["experience"]["mechanism"], "No artifact; cause unknown.")
		with self.assertRaises(ValueError):
			experience.record_experience(self.Root, dict(question="Did the worker return?", outcome="no_return", failure_kind="counterexample"))

	def test_failure_kinds_preserve_distinct_meanings(self):
		for Kind in experience.FAILURE_KINDS:
			Saved = experience.record_experience(self.Root, dict(conclusion="Caller-supplied observation, not an audit verdict.", outcome="failed", failure_kind=Kind))
			self.assertEqual(experience.read_route(self.Root, Saved["location"])["experience"]["failure_kind"], Kind)

	def test_partial_update_retains_scope_and_past_failure(self):
		Saved = experience.record_experience(self.Root, dict(reconsider_when=["A new lemma has arrived; retry the scoped estimate."]), self.First["location"], self.First["sha256"])
		Record = experience.read_route(self.Root, Saved["location"])
		self.assertEqual(Record["experience"]["scope"], self.Data["scope"])
		self.assertEqual(Record["experience"]["mechanism"], self.Data["mechanism"])
		self.assertEqual(Record["experience"]["failure_kind"], self.Data["failure_kind"])

	def test_comparison_keeps_testable_candidates_and_does_not_infer_accepted_facts(self):
		Routes = [self.First["location"], self.Second["location"]]
		Report = experience.compare_routes(self.Root, Routes, [dict(self.Hypothesis, status="ACCEPTED", validated=True)])
		self.assertEqual(Report["shared_transformations"], ["retain angular dependence"])
		self.assertEqual(Report["hypotheses"][0]["status"], "CANDIDATE_EXPLANATION")
		self.assertFalse(Report["hypotheses"][0]["validated"])
		self.assertFalse(Report["accepted_graph_modified"])
		Again = experience.compare_routes(self.Root, Routes, [dict(self.Hypothesis, status="ACCEPTED", validated=True)])
		self.assertEqual(Again["sha256"], Report["sha256"])
		self.assertEqual(experience.compare_routes(self.Root, Routes)["hypotheses"], [])
		with self.assertRaises(ValueError):
			experience.compare_routes(self.Root, Routes, dict(explanation="An untestable generalization."))

	def test_comparison_marks_changed_input_stale(self):
		Report = experience.compare_routes(self.Root, [self.First["location"], self.Second["location"]], self.Hypothesis)
		experience.record_experience(self.Root, dict(conclusion="A revised conditional bound."), self.Second["location"], self.Second["sha256"])
		Current = experience.read_comparison(self.Root, Report["path"])
		self.assertEqual([Route["binding_state"] for Route in Current["routes"]], ["CURRENT", "STALE"])
		Page = experience.update_understanding(self.Root, [self.First["location"]], [Report["path"]])
		self.assertIn("STALE", (self.Root / Page["path"]).read_text(encoding="utf-8"))

	def test_human_notes_are_byte_exact_and_generated_manual_edits_are_not_overwritten(self):
		Page = self.Root / "understanding.md"
		Human = "# My intuition\r\nThis is a question, not a theorem. \u6570\u5b66\r\n".encode("utf-8")
		Page.write_bytes(Human)
		Routes = [self.First["location"], self.Second["location"]]
		Report = experience.compare_routes(self.Root, Routes, self.Hypothesis)
		experience.update_understanding(self.Root, Routes, [Report["path"]], "understanding.md")
		self.assertTrue(Page.read_bytes().startswith(Human))
		Tail = b"\n## Handwritten next question\nKeep this exactly.\r\n"
		Page.write_bytes(Page.read_bytes() + Tail)
		experience.update_understanding(self.Root, [self.First["location"]], [Report["path"]], "understanding.md")
		self.assertTrue(Page.read_bytes().startswith(Human))
		self.assertTrue(Page.read_bytes().endswith(Tail))
		Page.write_bytes(Page.read_bytes().replace(b"## Evidence and candidate explanations", b"## My edit inside the generated region"))
		Before = Page.read_bytes()
		with self.assertRaises(ValueError):
			experience.update_understanding(self.Root, Routes, OutputPath="understanding.md")
		self.assertEqual(Page.read_bytes(), Before)

	def test_bad_route_is_named_without_losing_healthy_understanding(self):
		Bad = self.Root / "bad.md"
		Bad.write_bytes(b"---\nkind: broken: mapping\n---\n")
		Result = experience.update_understanding(self.Root, [self.First["location"], "bad.md"])
		self.assertEqual(Result["assembled_routes"], 1)
		self.assertEqual(len(Result["issues"]), 1)
		self.assertIn("The relaxation discards the angular dependency.", (self.Root / Result["path"]).read_text(encoding="utf-8"))

	def test_page_write_interruption_retry_preserves_human_region(self):
		Page = self.Root / "understanding.md"
		Before = b"# Human research notes\n"
		Page.write_bytes(Before)
		with mock.patch.object(library, "atomic_write", side_effect=OSError("injected prepublication failure")):
			with self.assertRaises(OSError):
				experience.update_understanding(self.Root, [self.First["location"]], OutputPath="understanding.md")
		self.assertEqual(Page.read_bytes(), Before)
		experience.update_understanding(self.Root, [self.First["location"]], OutputPath="understanding.md")
		Saved = Page.read_bytes()
		Again = experience.update_understanding(self.Root, [self.First["location"]], OutputPath="understanding.md")
		self.assertTrue(Again["reused"])
		self.assertEqual(Page.read_bytes(), Saved)
		self.assertTrue(Saved.startswith(Before))

	def test_bad_experience_fields_are_isolated_and_output_cannot_overwrite_an_input(self):
		Bad = library.save_card(self.Root, dict(content="Invalid imported experience metadata.", experience=dict(mechanism=dict(bad="mapping"))))
		Result = experience.update_understanding(self.Root, [self.First["location"], Bad["location"]])
		self.assertEqual(Result["assembled_routes"], 1)
		self.assertEqual(len(Result["issues"]), 1)
		PathValue = self.Root / self.First["location"]
		Before = PathValue.read_bytes()
		with self.assertRaises(ValueError):
			experience.update_understanding(self.Root, [self.First["location"]], OutputPath=self.First["location"])
		self.assertEqual(PathValue.read_bytes(), Before)

	def test_note_update_preserves_historical_evidence_binding(self):
		Proof = self.Root / "proof.md"
		Proof.write_bytes(b"Version one of a recorded argument.\n")
		Saved = experience.record_experience(self.Root, dict(conclusion="A recorded conditional claim.", evidence=[dict(path="proof.md")]))
		OriginalHash = library.digest(Proof.read_bytes())
		Proof.write_bytes(b"A different argument now occupies this path.\n")
		Updated = experience.record_experience(self.Root, dict(reconsider_when=["Read the new argument; the old evidence binding remains historical."]), Saved["location"], Saved["sha256"])
		Record = experience.read_route(self.Root, Updated["location"])
		self.assertEqual(Record["evidence"][0]["sha256"], OriginalHash)
		self.assertEqual(Record["evidence"][0]["binding_state"], "STALE_OR_UNBOUND")


if(__name__ == "__main__"):
	unittest.main()
