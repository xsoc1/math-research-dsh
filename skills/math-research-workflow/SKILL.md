---
name: math-research-workflow
description: Support a long-running mathematics project with reusable research knowledge, literature tools, continuity across sessions, and optional Lean verification. Use when coordinating research across problems or sessions, or choosing the relevant research tools.
---

## DSH runtime notes (DSH adaptation)

Load a relevant `$skill-name` with DSH's `skill` tool using its exact name.
Resolve bundled files from the returned `resourceBase`. Run Python helpers
with a local interpreter (`PYTHONUTF8=1` on Windows).

Plugin-level helpers are merged into this bundle's `scripts/`, including
`research_state.py`, `validate_pipeline.py` and `legacy_pipeline.py`.
Blueprint uses the manage skill's `resourceBase/runtime/blueprintctl.py`.

[DSH execution options](references/dsh-execution.md).

# Mathematics research workflow

Help the user advance the mathematics and improve the project's understanding.
Choose direct reasoning, literature, experiments, counterexamples, collaboration,
or formalization according to the problem. No fixed stage sequence is required.

Start from the project's current progress and relevant tool pointers. Read the
underlying proof or source when relying on a claim; a summary or status label is
not its justification. Continue useful work without recreating completed work.

Preserve ideas worth reusing: a transformation, construction, lemma, executable
certificate, obstruction, or changed understanding. Describe where a failed
route failed and what new fact would make it worth revisiting. An interrupted
computation is not mathematical evidence against the route. Compare routes when
that can produce a testable new explanation; keep it a candidate until checked.

Use components independently as needed:

- `$rigorous-open-math-research`: develop or audit a mathematical argument.
- `$manage-math-research-program`: read and curate literature, tools, annotations,
  research experience, and a human editable project understanding page.
- `$lean-verify`: obtain compiler feedback or check a precise formal target.

Keep the current goal, useful findings with pointers, remaining uncertainty and
next ideas in the project's existing progress page. If interrupted, read its
current contents and reconcile actual in-flight jobs before redispatching those
jobs. Unrelated work can continue. The [continuity tools](references/v2-continuity.md)
provide atomic snapshots, stale-write protection, durable local jobs and external
job receipts. They never consume credits or submit remote work automatically.

Proof, conditional reduction, numerical evidence, conjecture and infrastructure
status describe different things. Report the actual scope and remaining gaps.
Only use an accepted-knowledge receiver when writing canonical accepted claims;
ordinary notes and human intuition remain freely editable.

[Release history](references/changelog.md). The [1.x compatibility guide](references/v1-compatibility.md)
is only for interpreting or operating existing sealed artifacts.
