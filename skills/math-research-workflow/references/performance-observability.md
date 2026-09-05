# Performance Observability and Alerts

Use recorded costs to detect candidate regressions. Keep mathematical quality,
resource cost and infrastructure failures as separate observations.

## Metrics and unknown values

Record a `performance.json` with the observed metric scope and provenance:

```json
{
  "run_id": "...",
  "variant": "...",
  "model_responses": null,
  "tool_calls": null,
  "uncached_input_tokens": null,
  "cached_input_tokens": null,
  "output_tokens": null,
  "root_active_wall_seconds": null,
  "metric_scope": "root-and-children-tokens; root-active-wall",
  "task_sha256": "...",
  "prompt_sha256": "...",
  "model": "observed-model",
  "reasoning_effort": "observed-effort",
  "cli_sha256": "...",
  "harness_sha256": "...",
  "source_sha256": "...",
  "network_policy": "frozen-policy-id",
  "budget_policy": "frozen-policy-id",
  "artifact_profile": "frozen-required-profile"
}
```

Replace placeholders with actual observations; never use them as matched
identities. `source_sha256` binds the frozen mathematical input bundle, while
plugin versions and hashes identify the compared variants separately.
Record CLI version, operating system, provider and raw-log paths alongside the
fingerprints. Do not infer the actual model or effort from the user's default.

Omitted values, JSON null and `unknown` remain unknown. Zero means measured
zero. The normalizer rejects negative, Boolean, non-finite and conflicting
alias values. Supported aliases are `steps` for `model_responses`,
`cache_read_tokens` for `cached_input_tokens`, and `wall_seconds`/`wall_ms` for
`root_active_wall_seconds` (milliseconds are converted). Use these aliases
only if the raw producer has that meaning; planner steps and full pipeline
elapsed time are not automatically model responses and active root wall time.
Output tokens count as resource consumption, not as a quality score.

Keep root/child IDs and cumulative segments in the raw manifest. Across quota
resumes, use the existing checkpoint experiment-integrity rules for cumulative
counters and active time; do not sum cumulative snapshots twice or fabricate
missing child usage. Shared account percentages are operational limits, not
per-run tokens or cost. Report direct monetary cost only from observed billing
or an explicitly dated rate table, with cached/uncached/output pricing separate.

## Matched comparisons

`performance_alert.py --strict` requires matching nonempty task, prompt,
model, effort, CLI, harness, source, network-policy, budget-policy, artifact-profile
and metric-scope identities. A known mismatch is `INCOMPARABLE`, even without
strict mode. Missing identities are `INCOMPARABLE` under strict mode and
`ADVISORY_UNMATCHED` otherwise. A zero or missing baseline has no percentage
delta. Missing identities never prove that two runs are comparable.

A same-class historical run can provide context, but does not establish a
causal plugin speedup. Freeze conditions before a scored A/B run, keep held-out
inputs and auditors separate, and report repeated paired outcomes and uncertainty.
Change plugin behavior and model/effort in separate experiments. Keep invalid
infrastructure runs and post-hoc repairs outside scored arm metrics.

## Quality and alerts

The helper emits `WARN` when any known comparable cost rises at least 50%,
`INFO` otherwise, and `INCOMPARABLE` when identities fail. These are cost
signals only. Missing metrics are shown as unknown. It does not infer proof
quality, completeness or documentation loss from file count or output length.
Use an independent audit and the preregistered artifact profile for those
judgments, including exact remaining mathematical gaps.

Write the generated report to the run directory and connect any warning to
its raw metrics, quality audit and likely mechanism. One run is insufficient
for a broad regression claim. Do not launch another costly benchmark merely
because the advisory says WARN; use the remaining quota and the declared
experiment plan to decide the next discriminating check.

```text
python performance_alert.py --metrics performance.json --baseline baseline.json --output performance_alert.md --strict
```

Default mode is advisory. `--strict` exits nonzero for incomparable records;
`--fail-on-alert` additionally exits nonzero for a non-INFO cost signal.
