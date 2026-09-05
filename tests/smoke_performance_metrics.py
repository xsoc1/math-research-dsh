#!/usr/bin/env python3
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/math-research-workflow/scripts"))
from performance_metrics import normalize, compare, IDENTITY


class MetricsTests(unittest.TestCase):
	def test_aliases_unknown_and_conflicts(self):
		Data = normalize(dict(wall_ms=1250, cached_input_tokens=12, output_tokens=80))
		self.assertEqual(Data["root_active_wall_seconds"]["value"], 1.25)
		self.assertIsNone(Data["model_responses"]["value"])
		with self.assertRaises(ValueError):
				normalize(dict(wall_ms=1000, wall_seconds=2))
		for Value in (float("nan"), -1, True):
			with self.assertRaises(ValueError):
					normalize(dict(output_tokens=Value))

	def test_identity_and_output_cost(self):
		self.assertEqual(compare(dict(), dict(), True)["comparison"], "INCOMPARABLE")
		Base = dict.fromkeys(IDENTITY, "same")
		Base["output_tokens"] = 100
		Run = dict(Base, output_tokens=150)
		Result = compare(Run, Base, True)
		self.assertEqual(Result["comparison"], "MATCHED")
		self.assertEqual(next(Row for Row in Result["metrics"] if Row["metric"] == "output_tokens")["fractional_change"], 0.5)
		Run["model"] = "different"
		Result = compare(Run, Base)
		self.assertEqual(Result["comparison"], "INCOMPARABLE")
		self.assertTrue(all(Row["fractional_change"] is None for Row in Result["metrics"]))


if(__name__ == "__main__"):
	unittest.main()
