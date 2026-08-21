# Run whiteboard (Planner memory)

Compact live memory of a stage B or C run, maintained by the solve-run lead
(Planner role) and refreshed after every planner step. It is read as input at
every step (analogous to a reasoning cache), so it must stay short and always
current. Detailed material lives in repository items (slug files under the run
directory); this file keeps the plan, the route history, the deferred ideas,
and the artifact index.

Keep it inside the run directory: `runs/<skill>/<run_id>/whiteboard.md`. The
manager records its path and sha256 in the project index. The interruption
handoff (`handoff-interrupted-<ts>.md`) is a frozen snapshot of this record
plus recovery context; keep them consistent.

```text
- **Run ID:** `R-...`
- **Task packet ID:** `Q-...`
- **Last updated:** `YYYY-MM-DDTHH:MM:SSZ`
- **Current cost tier:** `0 | 1 | 2 | 3` (recommended)
- **Last escalation reason:** `<zero-gain | counterexample | load-bearing gap | user request; one line>` (recommended)
```

## Current plan

The currently executed plan: which obligation is being attacked, which route
is active, which worker owns it, and the immediate next deliverable. Replace
this section wholesale on every planner step; do not accumulate old plans.

## Route history

One line per route or method tried, newest first, with its outcome marker:

```text
- <route_key> `[FAILED|BLOCKED|PARTIAL|SUCCEEDED]`: one-line method summary;
  failure mechanism or partial progress; evidence slug + sha256.
```

This is the in-run contract against duplicate exploration: never re-run a
`[FAILED]` route without a new reason, and register any new attempt here before
executing it.

## Ideas to return to

Brief deferred ideas, observations, and notes that did not fit the active plan
but should not be lost (one line each, with the slug of any related item).

## Open obligations

Every obligation still open with its exact gap, or "none" when the run is
complete. Do not promote numerical evidence to proof here: reuse upstream
status labels verbatim.

## Key artifacts

One line per repository item (slug), each with a one-line summary and sha256:

```text
- `runs/<run_id>/<slug>` -- summary; sha256 <hash>
```

Repository rule: a Lean item is stored only if it passed machine verification;
otherwise its errors/warnings are fed back to the responsible worker instead
of being stored. Slugs and one-line summaries are all the Planner observes of
the repository at each step.
