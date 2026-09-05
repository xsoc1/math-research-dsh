#!/usr/bin/env python3
"""Exercise source capture, bounded reads, legacy pointers and versioned notes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/manage-math-research-program/scripts"))
import research_library as library


class LibraryTests(unittest.TestCase):
	def setUp(self):
		self.Temp = tempfile.TemporaryDirectory()
		self.Root = Path(self.Temp.name)
		(self.Root / "tools").mkdir()
		self.Card = self.Root / "tools" / "lemma.md"
		self.Card.write_text('---\ntitle: Test lemma\nsummary: compact interval estimate\n---\n# Statement\nSynthetic fixture only.\n', encoding="utf-8")
		(self.Root / "tools/README.md").write_text("# Human notes\nKeep this exactly.\n", encoding="utf-8")

	def tearDown(self):
		self.Temp.cleanup()

	def test_source_capture_resume_and_tamper(self):
		Source = self.Root / "input.txt"
		Source.write_text("甲" * 13000 + "\nsecond line\n", encoding="utf-8")
		First = library.capture_source(self.Root, Source, "https://example.org/fixture", "v1", "Synthetic")
		Again = library.capture_source(self.Root, Source, "https://example.org/fixture", "v1", "Synthetic")
		self.assertEqual(First, Again)
		Second = library.capture_source(self.Root, Source, "https://example.org/fixture", "v2", "Synthetic")
		self.assertNotEqual(First["source_id"], Second["source_id"])
		Hits = library.find_sources(self.Root, "fixture", limit=1)
		self.assertEqual(Hits["total_matches"], 2)
		self.assertEqual(len(Hits["hits"]), 1)
		Passage = library.read_source(self.Root, First["source_id"])
		self.assertEqual(len(Passage["content"]), 12000)
		Tail = library.read_source(self.Root, First["source_id"], StartOffset=Passage["next_offset"])
		self.assertEqual(Passage["content"] + Tail["content"], Source.read_bytes().decode("utf-8"))
		Stored = library.library_root(self.Root) / "sources" / First["source_id"] / "raw.bin"
		Stored.write_bytes(b"changed")
		with self.assertRaises(ValueError):
			library.read_source(self.Root, First["source_id"])

	def test_extraction_line_numbers_include_pdf_page_breaks(self):
		Source = self.Root / "pages.txt"
		Source.write_bytes(b"first\r\n\fsecond\rthird\n")
		Saved = library.capture_source(self.Root, Source, "https://example.org/pages", "v1", "Page break fixture")
		Chunk = library.read_source(self.Root, Saved["source_id"], StartLine=3, MaxLines=1)
		self.assertEqual(Chunk["content"], "second\r")
		self.assertEqual(Chunk["start_line"], 3)
		self.assertEqual(Chunk["end_line"], 3)
		Tail = library.read_source(self.Root, Saved["source_id"], StartOffset=Chunk["next_offset"])
		self.assertEqual(Tail["start_line"], 4)

	def test_legacy_index_and_stale_annotations(self):
		Index = self.Root / "index/tools.json"
		Index.parent.mkdir()
		Index.write_text(json.dumps(dict(schema_version=1, note="retain metadata", items=[dict(tool_id="stable-id", location="tools/lemma.md", custom="keep")])) , encoding="utf-8")
		library.make_index(self.Root, ["tools"], ReadmePath="tools/README.md")
		Data = library.read_json(Index)
		self.assertEqual(Data["items"][0]["custom"], "keep")
		Hash = library.digest(self.Card.read_bytes())
		First = library.annotate(self.Root, "tools/lemma.md", Hash, "agent-1", "retrieval_hint", "Statement", "boundary correction")
		self.assertEqual(First, library.annotate(self.Root, "tools/lemma.md", Hash, "agent-1", "retrieval_hint", "Statement", "boundary correction"))
		Hit = library.query_tools(self.Root, "boundary")["hits"][0]
		self.assertEqual(Hit["tool_id"], "stable-id")
		self.Card.write_text(self.Card.read_text(encoding="utf-8") + "Changed statement.\n", encoding="utf-8")
		self.assertEqual(library.query_tools(self.Root, "lemma")["verdict"], "STALE_INDEX")
		with self.assertRaises(ValueError):
			library.annotate(self.Root, "tools/lemma.md", Hash, "agent", "observation", "Statement", "new")
		library.make_index(self.Root, ["tools"], ReadmePath="tools/README.md")
		self.assertFalse(library.query_tools(self.Root, "boundary")["hits"])
		Hit = library.query_tools(self.Root, "lemma")["hits"][0]
		self.assertEqual(Hit["annotations"][0]["state"], "STALE")
		Readme = (self.Root / "tools/README.md").read_text(encoding="utf-8")
		self.assertTrue(Readme.startswith("# Human notes\nKeep this exactly.\n"))
		self.assertEqual(Readme.count(library.START), 1)
		(self.Root / "tools/new.md").write_text("# New card\n", encoding="utf-8")
		self.assertEqual(library.query_tools(self.Root, "lemma")["verdict"], "STALE_INDEX")

	def test_path_escape_lock_and_annotation_integrity(self):
		with self.assertRaises(ValueError):
			library.make_index(self.Root, ["../"])
		library.make_index(self.Root, ["tools"])
		with library.writer_lock(library.library_root(self.Root)):
			with self.assertRaises(FileExistsError):
				library.make_index(self.Root, ["tools"])
		Hash = library.digest(self.Card.read_bytes())
		Note = library.annotate(self.Root, "tools/lemma.md", Hash, "a", "correction", "line 1", "candidate only")
		Stored = library.library_root(self.Root) / "annotations" / (Note["annotation_id"] + ".json")
		Stored.write_text("{}", encoding="utf-8")
		with self.assertRaises(ValueError):
			library.query_tools(self.Root, "lemma")

	def test_legacy_retirement_and_malformed_index_preserve_records(self):
		Index = self.Root / "index/tools.json"
		Index.parent.mkdir()
		self.Card.write_text("# Legacy bound\n", encoding="utf-8")
		Applicability = [dict(class_name="gap-bound", status="retired", failure_records=["run/failed.md"])]
		Row = dict(tool_id="legacy-bound", location="tools/lemma.md", applicability=Applicability, lifecycle="archived")
		Index.write_text(json.dumps(dict(items=[Row])), encoding="utf-8")
		library.make_index(self.Root, ["tools"])
		self.assertEqual(library.read_json(Index)["items"][0]["applicability"], Applicability)
		self.assertFalse(library.query_tools(self.Root, "legacy-bound")["hits"])
		self.assertEqual(len(library.query_tools(self.Root, "legacy-bound", IncludeArchived=True)["hits"]), 1)
		Saved = Index.read_bytes()
		Readme = self.Root / "tools/README.md"
		Readme.write_text(library.END + "\nkeep\n" + library.START, encoding="utf-8")
		with self.assertRaises(ValueError):
			library.make_index(self.Root, ["tools"], ReadmePath="tools/README.md")
		self.assertEqual(Index.read_bytes(), Saved)
		Index.write_text(json.dumps(dict(items=[Row, Row])), encoding="utf-8")
		Saved = Index.read_bytes()
		with self.assertRaises(ValueError):
			library.make_index(self.Root, ["tools"])
		self.assertEqual(Index.read_bytes(), Saved)

	def test_bom_crlf_and_header_only_cards_preserve_retirement(self):
		for Ending in ("\n", "\r\n", "\r"):
			for Bom in ("", "\ufeff"):
				for Body in ("", Ending + "# Retired"):
					Raw = (Bom + Ending.join(["---", "title: Old bound", "applicability:", "- status: retired", "---"]) + Body).encode("utf-8")
					self.Card.write_bytes(Raw)
					Result = library.make_index(self.Root, ["tools"])
					self.assertEqual(Result["needs_metadata_review"], [])
					self.assertFalse(library.query_tools(self.Root, "bound")["hits"])
					Hit = library.query_tools(self.Root, "bound", IncludeArchived=True)["hits"][0]
					self.assertEqual(Hit["metadata_status"], "VALID")
					self.assertEqual(self.Card.read_bytes(), Raw)

	def test_malformed_card_does_not_hide_healthy_cards_or_imply_current_metadata(self):
		Broken = self.Root / "tools/broken.md"
		Broken.write_text("---\ntitle: Bound: missing quotes\n---\n# Broken metadata\n", encoding="utf-8")
		Raw = Broken.read_bytes()
		Result = library.make_index(self.Root, ["tools"])
		self.assertEqual(Result["needs_metadata_review"], ["tools/broken.md"])
		self.assertEqual(len(library.query_tools(self.Root, "lemma")["hits"]), 1)
		self.assertFalse(library.query_tools(self.Root, "broken")["hits"])
		Hit = library.query_tools(self.Root, "broken", IncludeUnreviewed=True)["hits"][0]
		self.assertEqual(Hit["metadata_status"], "UNPARSEABLE")
		self.assertEqual(Broken.read_bytes(), Raw)
		Index = self.Root / "index/tools.json"
		Data = library.read_json(Index)
		Row = next(Item for Item in Data["items"] if Item["location"] == "tools/broken.md")
		Row.update(lifecycle="archived", applicability=[dict(status="retired")])
		Index.write_bytes(library.json_bytes(Data))
		library.make_index(self.Root, ["tools"])
		self.assertFalse(library.query_tools(self.Root, "broken", IncludeUnreviewed=True)["hits"])
		self.assertTrue(library.query_tools(self.Root, "broken", IncludeArchived=True, IncludeUnreviewed=True)["hits"])
		Unterminated = self.Root / "tools/unterminated.md"
		Unterminated.write_text("---\napplicability:\n- status: retired\n# Missing closing delimiter\n", encoding="utf-8")
		Result = library.make_index(self.Root, ["tools"])
		self.assertIn("tools/unterminated.md", Result["needs_metadata_review"])
		self.assertFalse(library.query_tools(self.Root, "unterminated")["hits"])


if(__name__ == "__main__"):
	unittest.main()
