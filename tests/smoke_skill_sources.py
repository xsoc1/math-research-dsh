#!/usr/bin/env python3
"""Offline source diagnostics preserve local copies and distinguish their hashes."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/math-research-workflow/scripts"))
from skill_sources import source_inventory


class SourceTests(unittest.TestCase):
	def test_distinct_sources_are_diagnostic_only(self):
		with tempfile.TemporaryDirectory() as Temp:
			Root = Path(Temp)
			Source = Root / "market with spaces"
			Plain = Root / "skills/example/SKILL.md"
			Market = Source / "skills/example/SKILL.md"
			Cache = Root / "plugins/cache/test/example/1.0.0/skills/example/SKILL.md"
			for path, Content in ((Plain, "old"), (Market, "new"), (Cache, "new")):
				path.parent.mkdir(parents=True)
				path.write_text(Content, encoding="utf-8")
			Listing = f"example@test  installed, enabled  1.0.0  {Source}\n"
			Result = source_inventory(Root, Listing, ["example", "missing"])
			self.assertEqual(Result["selection"], "NOT_INFERRED")
			self.assertTrue(Result["skills"][0]["different_content"])
			self.assertEqual(len(Result["skills"][0]["copies"]), 3)
			self.assertEqual(Result["skills"][1]["copies"], [])
			self.assertEqual(Plain.read_text(), "old")
			Market.write_text("old", encoding="utf-8")
			Cache.write_text("old", encoding="utf-8")
			self.assertFalse(source_inventory(Root, Listing, ["example"])["skills"][0]["different_content"])


if(__name__ == "__main__"):
	unittest.main()
