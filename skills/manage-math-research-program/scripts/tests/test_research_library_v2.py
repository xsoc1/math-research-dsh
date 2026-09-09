#!/usr/bin/env python3
"""Library behavior tests. All writes use isolated temporary projects."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))
import research_library as library


class LibraryV2Tests(unittest.TestCase):
	def setUp(self):
		self.Temp = tempfile.TemporaryDirectory()
		self.Root = Path(self.Temp.name).resolve()
		self.Card = library.save_card(self.Root, dict(content="A compact positivity estimate.", title="Estimate", conditions=["x in [0, 1]"]))
		library.make_index(self.Root)

	def tearDown(self):
		self.Temp.cleanup()

	def test_small_card_reuses_identity_and_retains_metadata(self):
		Again = library.save_card(self.Root, dict(content="A compact positivity estimate.", title="Estimate", conditions=["x in [0, 1]"]))
		self.assertTrue(Again["reused"])
		self.assertEqual(Again["sha256"], self.Card["sha256"])
		Changed = library.save_card(self.Root, dict(content="A sharper compact estimate.", scope="Fixed interval only."), self.Card["location"], self.Card["sha256"])
		self.assertEqual(Changed["tool_id"], self.Card["tool_id"])
		Front, _, _ = library.read_metadata((self.Root / Changed["location"]).read_bytes())
		self.assertEqual(Front["conditions"], ["x in [0, 1]"])
		library.make_index(self.Root)
		Hit = library.query_tools(self.Root, "sharper")["hits"][0]
		self.assertEqual(Hit["scope"], "Fixed interval only.")
		self.assertEqual(Hit["conditions"], ["x in [0, 1]"])
		self.assertEqual(library.digest((self.Root / self.Card["version"]).read_bytes()), self.Card["sha256"])
		with self.assertRaises(ValueError):
			library.save_card(self.Root, dict(content="Overwrite another author's revision."), Changed["location"], self.Card["sha256"])

	def test_free_annotation_immediate_query_and_historical_match(self):
		Note = library.annotate(self.Root, self.Card["location"], text="endpoint-transfer-sentinel", kind="my own idea")
		Before = (library.library_root(self.Root) / "annotations" / (Note["annotation_id"] + ".json")).read_bytes()
		self.assertTrue(library.query_tools(self.Root, "endpoint-transfer-sentinel")["hits"])
		self.assertTrue(library.query_tools(self.Root, "my own idea")["hits"])
		Changed = library.save_card(self.Root, dict(content="Revised endpoint estimate."), self.Card["location"], self.Card["sha256"])
		library.make_index(self.Root)
		self.assertFalse(library.query_tools(self.Root, "endpoint-transfer-sentinel")["hits"])
		Hit = library.query_tools(self.Root, "endpoint-transfer-sentinel", IncludeStale=True)["hits"][0]
		self.assertTrue(Hit["matched_historical_annotation"])
		self.assertEqual(Hit["annotations"][0]["state"], "STALE")
		self.assertEqual(Hit["annotations"][0]["tool_sha256"], self.Card["sha256"])
		self.assertNotEqual(Changed["sha256"], self.Card["sha256"])
		self.assertEqual((library.library_root(self.Root) / "annotations" / (Note["annotation_id"] + ".json")).read_bytes(), Before)

	def test_corrupt_card_annotation_and_duplicate_id_isolate_health(self):
		(library.library_root(self.Root) / "annotations").mkdir()
		BadNote = library.library_root(self.Root) / "annotations" / ("a" * 64 + ".json")
		BadNote.write_bytes(b"{truncated")
		(self.Root / "tools/bad.md").write_bytes(b"---\ntitle: Bad: YAML\n---\nBad\n")
		(self.Root / "tools/binary.md").write_bytes(b"\xff\x00")
		for Name in ("dupe-a", "dupe-b"):
			library.save_card(self.Root, dict(content="Colliding ID.", tool_id="duplicate"), "tools/" + Name + ".md")
		Result = library.make_index(self.Root)
		self.assertEqual(len(Result["needs_metadata_review"]), 4)
		Query = library.query_tools(self.Root, "positivity")
		self.assertEqual(len(Query["hits"]), 1)
		self.assertTrue(any(str(BadNote) == Item["path"] for Item in Query["issues"]))
		self.assertFalse(library.query_tools(self.Root, "duplicate")["hits"])
		self.assertEqual(len(library.query_tools(self.Root, "duplicate", IncludeUnreviewed=True)["hits"]), 2)

	def test_changed_or_new_card_does_not_clear_healthy_hits(self):
		Other = library.save_card(self.Root, dict(content="Separate body."))
		Query = library.query_tools(self.Root, "positivity")
		self.assertEqual(Query["verdict"], "STALE_INDEX")
		self.assertEqual(Query["changed_paths"], [Other["location"]])
		self.assertEqual(len(Query["hits"]), 1)
		library.make_index(self.Root)
		(self.Root / Other["location"]).unlink()
		self.assertEqual(len(library.query_tools(self.Root, "positivity")["hits"]), 1)

	def test_incremental_parse_and_legacy_byte_retention(self):
		Legacy = self.Root / "tools/legacy.md"
		Raw = b"\xef\xbb\xbf---\r\napplicability:\r\n- status: retired\r\n---\r\n# Old bound\r\n"
		Legacy.write_bytes(Raw)
		Index = self.Root / "index/tools.json"
		Previous = dict(custom="retain index metadata", items=[dict(location="tools/legacy.md", tool_id="legacy-stable-id", custom={"failure": "bad bound on this domain"})])
		OldBytes = library.json_bytes(Previous)
		Index.write_bytes(OldBytes)
		library.make_index(self.Root)
		self.assertEqual(Legacy.read_bytes(), Raw)
		self.assertEqual((library.library_root(self.Root) / "index-history" / (library.digest(OldBytes) + ".json")).read_bytes(), OldBytes)
		Hit = library.query_tools(self.Root, "legacy-stable-id", IncludeArchived=True)["hits"][0]
		self.assertEqual(Hit["lifecycle"], "archived")
		self.assertFalse(library.query_tools(self.Root, "legacy-stable-id")["hits"])
		with mock.patch.object(library, "parse_card", wraps=library.parse_card) as Parse:
			Result = library.make_index(self.Root)
			self.assertEqual(Parse.call_count, 0)
			self.assertEqual(Result["reused"], 2)
		NewIndex = library.read_json(Index)
		self.assertEqual(NewIndex["custom"], Previous["custom"])
		self.assertEqual(next(Row for Row in NewIndex["items"] if Row["location"] == "tools/legacy.md")["custom"], Previous["items"][0]["custom"])

	def test_source_versions_coverage_unicode_reads_and_one_bad_record(self):
		Input = self.Root / "source.txt"
		Content = "\u7532" * 13000 + "\n\fpage two\n"
		Input.write_bytes(Content.encode("utf-8"))
		First = library.capture_source(self.Root, Input, "https://example.org/test-fixture", "v1", "Fixture", Coverage="excerpt", Locators=["p. 2, equation 3"])
		Second = library.capture_source(self.Root, Input, "https://example.org/test-fixture", "v2", "Fixture")
		self.assertNotEqual(First["source_id"], Second["source_id"])
		Offset, Pieces = 0, []
		while(Offset is not None):
			Part = library.read_source(self.Root, First["source_id"], StartOffset=Offset)
			Pieces.append(Part["content"])
			Offset = Part["next_offset"]
		self.assertEqual("".join(Pieces), Content)
		self.assertEqual(Part["metadata"]["original_locators"], ["p. 2, equation 3"])
		Bad = library.library_root(self.Root) / "sources" / ("b" * 64)
		Bad.mkdir()
		(Bad / "source.json").write_bytes(b"[]")
		Result = library.find_sources(self.Root, "page two", SearchContent=True)
		self.assertEqual(Result["total_matches"], 2)
		self.assertEqual(len(Result["issues"]), 1)
		(library.library_root(self.Root) / "sources" / First["source_id"] / "raw.bin").write_bytes(b"changed")
		self.assertEqual(library.find_sources(self.Root, "page two", SearchContent=True)["total_matches"], 1)

	def test_program_and_exact_lean_reference_are_searchable_and_versioned(self):
		Program = self.Root / "check.py"
		Program.write_text("raise RuntimeError('The library must not execute me')\n", encoding="utf-8")
		Lean = self.Root / "Example.lean"
		Lean.write_text("theorem identity (x : Nat) : x = x := rfl\n", encoding="utf-8")
		Card = library.save_card(self.Root, dict(content="Exact identity, not a positivity theorem.", resources=[dict(path="check.py", kind="program")], lean=[dict(repository="https://example.org/test-fixture", commit="1" * 40, module="Example", declaration="identity", actual_type="(x : Nat) -> x = x", environment=dict(lean="fixture-unexecuted"), source=dict(path="Example.lean"), conversion_lemmas=["identity"]) ]))
		library.make_index(self.Root)
		Hit = library.query_tools(self.Root, "Example identity")["hits"][0]
		self.assertEqual(Hit["location"], Card["location"])
		self.assertEqual(Hit["resources"][0]["binding_state"], "CURRENT")
		self.assertEqual(Hit["lean"][0]["source"]["binding_state"], "CURRENT")
		self.assertEqual(Hit["lean"][0]["identity_fields_missing"], [])
		self.assertEqual(Hit["lean"][0]["trust"], "UNVERIFIED_DECLARATION_REFERENCE")
		Program.write_bytes(b"changed")
		Lean.write_text("theorem identity (x : Nat) (h : x = 0) : x = 0 := h\n", encoding="utf-8")
		Hit = library.query_tools(self.Root, "Example identity")["hits"][0]
		self.assertEqual(Hit["resources"][0]["binding_state"], "STALE_OR_UNBOUND")
		self.assertEqual(Hit["lean"][0]["source"]["binding_state"], "STALE_OR_UNBOUND")

	def test_json_card_needs_no_yaml_dependency(self):
		with mock.patch.object(library, "yaml", None):
			Card = library.save_card(self.Root, dict(content="JSON header, no dependency."))
			library.make_index(self.Root)
			self.assertTrue(library.query_tools(self.Root, "dependency")["hits"])
			self.assertEqual(library.read_metadata((self.Root / Card["location"]).read_bytes())[2], "VALID")

	def test_interruption_between_index_and_readme_retries_without_duplicate_notes(self):
		Readme = self.Root / "tools/README.md"
		Human = b"# Human notes\r\nHandwritten thought.\r\n"
		Readme.write_bytes(Human)
		library.annotate(self.Root, self.Card["location"], text="retained note")
		Original = library.atomic_write
		def fail_readme(PathValue, Data):
			if(PathValue == Readme):
				raise OSError("injected interruption after index publish")
			Original(PathValue, Data)
		with mock.patch.object(library, "atomic_write", side_effect=fail_readme):
			with self.assertRaises(OSError):
				library.make_index(self.Root, ReadmePath="tools/README.md")
		self.assertEqual(Readme.read_bytes(), Human)
		self.assertEqual(len(library.query_tools(self.Root, "retained note")["hits"]), 1)
		library.make_index(self.Root)
		self.assertTrue(Readme.read_bytes().startswith(Human))
		self.assertEqual(Readme.read_bytes().count(library.START.encode()), 1)
		self.assertEqual(len(library.collect_notes(self.Root)), 1)

	def test_real_process_exit_after_annotation_publish_reuses_identical_note(self):
		Code = """import os, sys
sys.path.insert(0, sys.argv[1])
import research_library as library
Original = library.immutable_write
def interrupted_write(PathValue, Data):
\tOriginal(PathValue, Data)
\tif(PathValue.parent.name == 'annotations'):
\t\tos._exit(91)
library.immutable_write = interrupted_write
library.annotate(sys.argv[2], sys.argv[3], text='durable note before abrupt exit')
"""
		Result = subprocess.run([sys.executable, "-c", Code, str(SCRIPT_ROOT), str(self.Root), self.Card["location"]], capture_output=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=20)
		self.assertEqual(Result.returncode, 91, Result.stderr)
		Root = library.library_root(self.Root)
		NotesBefore = {PathValue.name: PathValue.read_bytes() for PathValue in (Root / "annotations").glob("*.json")}
		self.assertEqual(len(NotesBefore), 1)
		self.assertTrue((Root / "writer.lock").exists())
		(Root / "writer.lock").rename(Root / "writer-exited-91.lock")
		Note = library.annotate(self.Root, self.Card["location"], text="durable note before abrupt exit")
		self.assertEqual(NotesBefore[Note["annotation_id"] + ".json"], (Root / "annotations" / (Note["annotation_id"] + ".json")).read_bytes())
		self.assertEqual(len(library.collect_notes(self.Root)), 1)

	def test_partial_capture_retry_keeps_raw_and_text(self):
		Source = self.Root / "paper.txt"
		Source.write_bytes(b"Actual fixture bytes.\n")
		Original = library.immutable_write
		def interrupt_metadata(PathValue, Data):
			if(PathValue.name == "source.json"):
				raise OSError("metadata has not published")
			Original(PathValue, Data)
		with mock.patch.object(library, "immutable_write", side_effect=interrupt_metadata):
			with self.assertRaises(OSError):
				library.capture_source(self.Root, Source, "https://example.org/test-fixture", "v1", "Fixture")
		Saved = library.capture_source(self.Root, Source, "https://example.org/test-fixture", "v1", "Fixture")
		self.assertEqual(library.read_source(self.Root, Saved["source_id"])["content"], "Actual fixture bytes.\n")
		self.assertEqual(len(list((library.library_root(self.Root) / "sources").glob("*/source.json"))), 1)

	def test_index_reconstruction_keeps_old_ids_annotations_and_custom_fields(self):
		Legacy = self.Root / "tools/legacy.md"
		Legacy.write_bytes(b"# Legacy card\nOriginal mathematical scope.\n")
		Index = self.Root / "index/tools.json"
		Index.write_bytes(library.json_bytes(dict(items=[dict(tool_id="stable-different-from-filename", location="tools/legacy.md", conditions="An old restricted domain.", custom="Preserve this identity.")])))
		First = library.make_index(self.Root)
		Note = library.annotate(self.Root, "tools/legacy.md", text="a legacy-bound retrieval cue")
		NotePath = library.library_root(self.Root) / "annotations" / (Note["annotation_id"] + ".json")
		NoteBytes = NotePath.read_bytes()
		Index.unlink()
		library.make_index(self.Root, PreviousIndex=First["previous_index_snapshot"])
		Hit = library.query_tools(self.Root, "legacy-bound retrieval cue")["hits"][0]
		self.assertEqual(Hit["tool_id"], "stable-different-from-filename")
		self.assertEqual(Hit["conditions"], "An old restricted domain.")
		self.assertIn("conditions", Hit["inherited_metadata"])
		self.assertEqual(NoteBytes, NotePath.read_bytes())
		self.assertEqual(next(Row for Row in library.read_json(Index)["items"] if Row["location"] == "tools/legacy.md")["custom"], "Preserve this identity.")

	def test_unchanged_refresh_does_not_rewrite_index_or_snapshot(self):
		Before = (self.Root / "index/tools.json").read_bytes()
		with mock.patch.object(library, "atomic_write", wraps=library.atomic_write) as Write:
			with mock.patch.object(library.os, "fsync", wraps=library.os.fsync) as Flush:
				Result = library.make_index(self.Root)
				self.assertEqual(Write.call_count, 0)
				self.assertEqual(Flush.call_count, 0)
		self.assertFalse(Result["index_changed"])
		self.assertEqual((self.Root / "index/tools.json").read_bytes(), Before)

	def test_cli_round_trip_for_sources_cards_notes_and_experience(self):
		def run_cli(Script, Command, *Arguments):
			Run = subprocess.run([sys.executable, str(SCRIPT_ROOT / Script), Command, "--project", str(self.Root), *Arguments], capture_output=True, text=True, timeout=20)
			self.assertEqual(Run.returncode, 0, Run.stdout + Run.stderr)
			return json.loads(Run.stdout)
		def input_json(Name, Data):
			PathValue = self.Root / Name
			PathValue.write_bytes(library.json_bytes(Data))
			return str(PathValue)
		Library = "research_library.py"
		Experience = "research_experience.py"
		Source = self.Root / "cli-source.txt"
		Source.write_bytes(b"CLI fixture source text.\n")
		Captured = run_cli(Library, "capture-source", "--input", str(Source), "--url", "https://example.org/test-fixture", "--version", "v1", "--title", "CLI fixture", "--coverage", "one fixture line")
		self.assertEqual(run_cli(Library, "find-source", "--query", "CLI fixture")["total_matches"], 1)
		self.assertEqual(run_cli(Library, "read-source", "--source-id", Captured["source_id"])["content"], Source.read_text(encoding="utf-8"))
		Card = run_cli(Library, "card", "--input", input_json("cli-card.json", dict(content="A CLI card with a source.", sources=[dict(source_id=Captured["source_id"], locator="line 1")])) )
		Note = self.Root / "cli-note.txt"
		Note.write_bytes(b"CLI-round-trip-note")
		run_cli(Library, "annotate", "--tool", Card["location"], "--text-file", str(Note), "--kind", "free thoughts", "--expected-sha256", Card["sha256"])
		run_cli(Library, "index")
		self.assertEqual(run_cli(Library, "query", "--query", "CLI-round-trip-note")["hits"][0]["location"], Card["location"])
		First = run_cli(Experience, "record", "--input", input_json("cli-first.json", dict(conclusion="First CLI observation.")))
		Second = run_cli(Experience, "record", "--input", input_json("cli-second.json", dict(conclusion="Second CLI observation.")))
		Report = run_cli(Experience, "compare", "--route", First["location"], "--route", Second["location"])
		self.assertEqual(Report["hypotheses"], [])
		Page = run_cli(Experience, "understanding", "--route", First["location"], "--route", Second["location"], "--comparison", Report["path"])
		self.assertEqual(Page["assembled_routes"], 2)


if(__name__ == "__main__"):
	unittest.main()
