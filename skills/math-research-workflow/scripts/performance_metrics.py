#!/usr/bin/env python3
"""Normalize recorded metrics without replacing unknown values with zero."""
import math

ALIASES = dict(
	model_responses=(("model_responses", 1), ("steps", 1)),
	tool_calls=(("tool_calls", 1),),
	uncached_input_tokens=(("uncached_input_tokens", 1),),
	cached_input_tokens=(("cached_input_tokens", 1), ("cache_read_tokens", 1)),
	output_tokens=(("output_tokens", 1),),
	root_active_wall_seconds=(("root_active_wall_seconds", 1), ("wall_seconds", 1), ("wall_ms", 0.001)),
)
IDENTITY = ("task_sha256", "prompt_sha256", "model", "reasoning_effort", "cli_sha256", "harness_sha256",
	"source_sha256", "network_policy", "budget_policy", "artifact_profile", "metric_scope")


def normalize(Data):
	Result = dict()
	for name, Candidates in ALIASES.items():
		Values = []
		for key, Factor in Candidates:
			Value = Data.get(key)
			if(Value is None or Value == "unknown"):
				continue
			if(isinstance(Value, bool) or not isinstance(Value, (int, float)) or not math.isfinite(Value) or Value < 0):
					raise ValueError(f"invalid nonnegative metric: {key}")
			Values.append((key, Value * Factor))
		if(Values and any(not math.isclose(Value, Values[0][1], rel_tol=1e-9, abs_tol=1e-9) for _, Value in Values)):
				raise ValueError(f"conflicting aliases for {name}")
		Result[name] = dict(value=Values[0][1] if Values else None, fields=[key for key, _ in Values])
	return Result


def compare(Run, Baseline, Strict=False):
	Missing = [key for key in IDENTITY if Run.get(key) in (None, "", "unknown") or Baseline.get(key) in (None, "", "unknown")]
	Mismatch = [key for key in IDENTITY if key not in Missing and Run[key] != Baseline[key]]
	Current, Previous = normalize(Run), normalize(Baseline)
	Comparable = not Mismatch and (not Strict or not Missing)
	Rows = []
	for name in ALIASES:
		Value, BaseValue = Current[name]["value"], Previous[name]["value"]
		Delta = (Value - BaseValue) / BaseValue if Comparable and Value is not None and BaseValue not in (None, 0) else None
		Rows.append(dict(metric=name, value=Value, baseline=BaseValue, fractional_change=Delta,
			source_fields=Current[name]["fields"], baseline_fields=Previous[name]["fields"]))
	return dict(comparison="MATCHED" if Comparable and not Missing else ("ADVISORY_UNMATCHED" if Comparable else "INCOMPARABLE"),
		missing_identity=Missing, mismatched_identity=Mismatch, metrics=Rows,
		quality_assessment="Requires independent audit and the declared artifact profile; file count is not mathematical quality.")
