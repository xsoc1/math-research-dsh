# State, Checkpoints, Research Budgets, and Stage Reports

## State model

Use program-level lifecycle states only:

```text
SETUP
ACTIVE
PAUSED
REVIEW
CLOSED
```

These describe the research program, not the truth or completeness of a theorem.

For a task packet use:

```text
DRAFT
READY
DISPATCHED
INGESTED
CANCELLED
```

For an open-problem portfolio item use planning states such as:

```text
WATCH
CANDIDATE
PRIORITIZED
QUEUED
DELEGATED
FOLLOW_UP
ARCHIVED
```

Keep the upstream mathematical result label in a separate verbatim field.

## Current state

`state/current.json` is the machine-readable resumption state. It should include:

- project lifecycle state;
- current stage and objective;
- active direction, paper, problem, task, and run IDs;
- latest checkpoint path;
- next actions in priority order;
- blockers;
- budget configuration and recorded consumption;
- last literature cutoff date;
- last updated timestamp.

`state/RESUME.md` is the human-readable entry point. Keep it brief enough to read first in a new session.

Required `RESUME.md` sections:

```text
Current objective
Read these files first
Last completed action
Active tasks and runs
Exact next action
Blockers or missing inputs
Budget remaining, if configured
Validation command
```

## Effective research time

A research-time threshold is configurable per project or stage.

Possible configuration:

```json
{
  "mode": "effective_time",
  "target_hours": 8.0,
  "scope": "stage",
  "counting_policy": "evidence_backed",
  "configured_by": "user",
  "configured_at": "ISO-8601 timestamp"
}
```

Leave `target_hours` as `null` when the user did not request a threshold.

### Countable effective time

Count only recorded periods with a concrete research activity and resulting evidence, for example:

- literature search and source verification;
- paper reading and structured analysis;
- map, portfolio, or tool-library updates based on sources;
- task-packet preparation;
- ingestion and provenance checking;
- project synthesis and checkpointing.

Do not count:

- unattended waiting;
- tool latency with no active work;
- duplicate formatting or file copying;
- idle wall-clock time between sessions;
- estimated time not supported by a record.

### Activity log

Append one JSON object per material activity to `state/activity.jsonl`:

```json
{
  "activity_id": "ACT-...",
  "started_at": "...",
  "ended_at": "...",
  "effective_minutes": 0,
  "category": "literature|paper_analysis|mapping|tool_curation|task_packaging|ingestion|synthesis|administration",
  "related_ids": [],
  "artifacts_created_or_updated": [],
  "summary": "",
  "evidence": [],
  "recorded_by": "",
  "notes": ""
}
```

Do not backfill precise minutes from vague memory. Mark uncertain records as estimates and exclude them from strict thresholds unless the user accepts an estimation policy.

## Checkpoints

Create a checkpoint after:

- project initialization;
- a substantive literature batch;
- every important paper analysis;
- a material map or tool-library revision;
- task dispatch;
- upstream result ingestion;
- a stage review or pause.

Use `assets/checkpoint.template.md`.

A checkpoint must be sufficient for another session to resume without reconstructing hidden context. It contains facts and file pointers, not private reasoning.

## Checkpoint naming

```text
state/checkpoints/YYYY-MM-DDTHHMMSSZ--SLUG.md
```

The checkpoint path goes into `state/current.json` and `state/RESUME.md`.

## Stage summary

Use `assets/stage-summary.template.md` for project-level reporting.

Required sections:

1. scope, dates, and configured budget;
2. literature coverage and cutoff;
3. papers added, versions changed, and analyses completed;
4. paper-map and frontier changes;
5. open-problem portfolio changes and priority rationale;
6. tools added, merged, deprecated, or promoted;
7. delegated runs with upstream statuses verbatim and artifact links;
8. rigorous reusable intermediate results;
9. exact failed mechanisms and remaining gaps;
10. time accounting and limitations;
11. next-stage plan and recovery entry;
12. integrity-validation result.

A stage summary is not a proof report and must not adopt the upstream output protocol as its own.

## Stage closure

A stage may close when its management deliverables are complete even if every open problem remains open. Conversely, a solver run may return a complete proof while the program stage remains open because indexing, source verification, or downstream synthesis is unfinished.
