# OpenProver absorption: token-conscious planner/repo/budget protocol

This file defines the token-conscious absorption of
[OpenProver](https://arxiv.org/html/2607.09217v1) (arXiv:2607.09217) into the
workflow. It adds explicit Planner actions, a Repository item system, a
`theorem.lean` input skeleton, Planner history, and a token budget discipline
that pauses and hands off instead of losing work.

## 1. Planner action protocol

Each Planner step produces a short reasoning trace and a machine-readable
action list. Keep the trace compact (default ≤ 150 words) and the actions JSON.

Available actions:

| Action | Description | Input |
| --- | --- | --- |
| `spawn` | Spawn parallel workers | list of tasks |
| `read_items` | Read repo items | list of slugs |
| `write_items` | Create/update/delete repo items | list of `(slug, format, content)` |
| `read_theorem` | Re-read the theorem statement | none |
| `write_whiteboard` | Update the whiteboard | full whiteboard text |
| `submit_proof` | Submit informal proof | informal item slug |
| `submit_lean_proof` | Submit Lean proof | Lean item slug |
| `literature_search` | Search online literature | query |

Output shape:

```json
{
  "step": 12,
  "coT": "compact reasoning trace",
  "actions": [
    {"action": "spawn", "tasks": ["..."]},
    {"action": "write_whiteboard", "content": "..."}
  ]
}
```

## 2. Repository item system

Each run keeps a repository:

```text
runs/<run_id>/repo/
  <slug>.md
  <slug>.lean
  repo_index.md
```

- `repo_index.md` holds `slug + one-line summary` for every item.
- The Planner sees only `repo_index.md`, not full item contents, unless it calls
  `read_items`.
- Long proofs, failed attempts, literature summaries, and Lean snippets go to
  the repository instead of the whiteboard.
- **Lean items are stored only if they pass Lean verification**; otherwise the
  errors/warnings are fed back to the Planner.
- This reduces context/token usage because the whiteboard stays compact.

## 3. theorem.lean input skeleton

Every task packet may include a `theorem.lean` skeleton:

```lean
import Mathlib

theorem target : <statement> := by
  sorry
```

- The skeleton is created when the problem is dispatched, not after a proof is
  found.
- Natural-language proof search proceeds independently; formalization starts
  from this skeleton.
- Intermediate lemmas may also get their own `lemma_*.lean` skeletons.

## 4. Planner history

Each Planner step is appended to `runs/<run_id>/planner_history.jsonl`:

```json
{"step": 1, "coT": "...", "actions": [...], "outputs": [...], "whiteboard": "..."}
```

- Full history is persisted on disk for audit and resumption.
- Only the last `n` steps (default 3–5) are fed to the model; older steps are
  compressed into the whiteboard summary.

## 5. Token budget discipline (pause + handoff, never data loss)

Budget exhaustion is a **soft pause**, not an abort.

### budget_state.json

```json
{
  "total_tokens": 100000,
  "consumed_tokens": 0,
  "remaining_tokens": 100000,
  "phase": "stageB",
  "last_checkpoint": null,
  "status": "active"
}
```

### Checkpoints

Check budget at safe boundaries only:

- end of each Planner step;
- end of each Worker round;
- after each Verifier review;
- after each Lean verification.

### On budget exhaustion

1. Stop spawning new workers.
2. Let in-flight workers finish their current round (or graceful stop).
3. Persist whiteboard, repository, planner history, verified facts, failed
   paths, and `budget_state.json`.
4. Write `handoff-interrupted-<ts>.md` with completed work progress, tools and
   methods tried, open obligations, and exact next actions.
5. Update `state/RESUME.md` and indexes.
6. Mark run status as `PAUSED_BUDGET` / `RIGOROUS_PARTIAL_RESULT`.
7. On resume, read the handoff + `budget_state.json` and continue with a new
   budget (e.g. `--budget 50000`).

### Near-completion extension

If the target is almost complete (e.g. informal proof done, formalization
pending), the Planner may emit `request_extension`; the main agent surfaces it
to the operator for approval instead of stopping at the finish line.

### Budget modes

| Mode | Behavior |
| --- | --- |
| `per_round` | per-round cap, continue between rounds |
| `per_phase` | per-phase cap, resume at next phase |
| `hard_total` | pause + handoff at total cap |
| `soft_warning` | warn below threshold, do not pause |

Default for research: `per_round` + `soft_warning`.

## 6. Token-saving rules

- Planner CoT ≤ 150 words unless a hard problem justifies more.
- Whiteboard stores summaries, not full texts.
- Repository items are read on demand.
- Lean verification uses Tier 0/1 for intermediates; Tier 2 only for
  completion labels.
- Verifier feedback in prompts is limited to the top 3 issues; full report is
  persisted to disk.
- Reuse `LEMMA_INDEX.md` / fact graph before proving a new lemma.
- Evaluation harness and prompt self-improvement run offline, not in the live
  loop.
