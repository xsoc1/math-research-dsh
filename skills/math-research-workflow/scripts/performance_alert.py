#!/usr/bin/env python3
"""Compare recorded metrics; --strict requires matching benchmark identities."""
import argparse
import json
from pathlib import Path

from performance_metrics import compare


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--metrics", required=True)
	Parser.add_argument("--baseline", required=True)
	Parser.add_argument("--output", required=True)
	Parser.add_argument("--strict", action="store_true")
	Parser.add_argument("--fail-on-alert", action="store_true")
	Args = Parser.parse_args()
	try:
		Run = json.loads(Path(Args.metrics).read_text(encoding="utf-8"))
		Base = json.loads(Path(Args.baseline).read_text(encoding="utf-8"))
		Result = compare(Run, Base, Args.strict)
		Level = "INCOMPARABLE" if Result["comparison"] == "INCOMPARABLE" else (
			"WARN" if any(Row["fractional_change"] is not None and Row["fractional_change"] >= 0.5 for Row in Result["metrics"]) else "INFO")
		Lines = ["# Performance alert", "", f"- Run ID: {Run.get('run_id', 'unknown')}",
			f"- Alert level: {Level}", f"- Comparison: {Result['comparison']}",
			f"- Missing identity: {', '.join(Result['missing_identity']) or 'none'}",
			f"- Mismatched identity: {', '.join(Result['mismatched_identity']) or 'none'}", "",
			"| Metric | Run | Baseline | Change |", "| --- | ---: | ---: | ---: |"]
		for Row in Result["metrics"]:
			Value = Row["value"] if Row["value"] is not None else "unknown"
			BaseValue = Row["baseline"] if Row["baseline"] is not None else "unknown"
			Delta = f"{Row['fractional_change']:+.1%}" if Row["fractional_change"] is not None else "n/a"
			Lines.append(f"| {Row['metric']} | {Value} | {BaseValue} | {Delta} |")
		Lines.extend(["", Result["quality_assessment"], "", "Alerts are candidates, not verdicts. Compare audited root closure, exact gaps and profile completeness before judging a cost change.", ""])
		Path(Args.output).write_text("\n".join(Lines), encoding="utf-8", newline="\n")
		print(json.dumps(dict(level=Level, **Result), ensure_ascii=False))
		return int((Args.strict and Level == "INCOMPARABLE") or (Args.fail_on_alert and Level != "INFO"))
	except (OSError, ValueError, TypeError, AttributeError) as Error:
		print(json.dumps(dict(level="INVALID", error=str(Error))))
		return 1


if(__name__ == "__main__"):
	raise SystemExit(main())
