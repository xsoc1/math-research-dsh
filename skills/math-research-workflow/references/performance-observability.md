# Performance Observability and Alerts

## Purpose

Detect and surface performance regressions during research runs. The goal is
not to replace human judgement but to alert the user early when a change
(staged protocol, new skill text, new retry logic, plugin version) makes runs
more expensive without a compensating benefit.

## Metrics

When available, every material run should record a `performance.json`:

```json
{
  "run_id": "...",
  "variant": "...",
  "problem_class": "...",
  "steps": 0,
  "tool_calls": 0,
  "uncached_input_tokens": 0,
  "cache_read_tokens": 0,
  "output_tokens": 0,
  "wall_ms": 0,
  "artifact_count": 0,
  "reused_item_count": 0,
  "duplicate_work_count": 0
}
```

Metric sources may be DSH session stats, run logs, `performance_log.md`,
`reuse_summary.md`, and the run artifact directory.

## Baselines

A baseline is a previous `performance.json` from a comparable run:

- same problem class, or
- same task type and similar difficulty, or
- a configured plugin baseline.

Keep multiple baselines. A single baseline on an easy problem is not enough to
judge a hard problem.

## Alert levels

- `INFO` -- changed but no clear regression.
- `WARN` -- one or more cost metrics increased materially while output/artifacts
  did not improve.
- `ALERT` -- cost increased materially AND documentation/reuse quality
  decreased (e.g. missing minimum artifacts, high duplicate work).

Alerts are **candidates**, not verdicts. A single run may be misleading (this
is exactly what happened in the reuse-gate experiments: an easy problem showed
overhead, while a hard problem showed a different trade-off). Therefore every
alert must include:

- which metrics changed;
- how much they changed;
- whether the run's output/artifacts improved or degraded;
- the problem class and difficulty context;
- one or more suggested next checks (e.g. run the same variant on a different
  problem class, or rerun with a second agent).

## Alert writing

When an alert is produced, write `performance_alert.md` in the run root using
`assets/performance-alert.template.md`, and if the run has a `final_report.md`,
add a short "Performance alert" section summarizing the candidate issue and the
proposed next checks.

Do not claim a protocol change is bad based on one run alone. Confirmation
requires at least one of:

- a repeat run in the same class;
- a run in a different class with a meaningful baseline;
- a documented mechanism explaining why the metric change is expected and
  acceptable.

## Tooling

`scripts/performance_alert.py` compares a run's `performance.json` against a
baseline and writes the alert record. It is advisory and never blocks a run by
default.
