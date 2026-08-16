# Interruption handoff record

Fill this record when a stage (B research or C formalization) must stop before
completion: budget exhaustion, user request, tool/environment failure, or any
cross-session interruption. The next agent resumes from this file instead of
re-deriving from scratch. Keep it inside the run directory
(`runs/<skill>/<run_id>/handoff-interrupted-<UTC timestamp>.md`); the manager
records its path and hash in the project index.

```text
- **Run ID:** `R-...`
- **Task packet ID:** `Q-...`
- **Date:** `YYYY-MM-DDTHH:MM:SSZ`
- **Interrupt reason:** `RESOURCE_BOUND | USER_REQUEST | TOOL_FAILURE | UNKNOWN` (details: what stopped the work)
- **Task state:** `IN_PROGRESS | BLOCKED` (+ upstream status label verbatim if any)
```

## Completed work progress

Summarize the overall progress achieved so far, independent of the obligation
list: partial results, structural theorems, reductions, counterexamples,
falsified conjectures, and the exact current status label (verbatim). This is
what the next agent should build on and must not redo.

## Completed obligations

List every obligation closed so far, with the evidence path (and sha256) for
each. Do not promote numerical evidence to a proof here; reuse the upstream
status labels verbatim (`PARTIAL` / `CANDIDATE_PARTIAL_PROOF` / gaps).

## Tools and methods tried

One line per tool/script/method/formalization attempt actually used, with its
outcome and where the evidence lives:

```text
- <tool-or-method> `[FAILED|BLOCKED|PARTIAL|SUCCEEDED]`: what it was used for,
  result or failure mechanism, command/script/Lean file path + sha256.
```

This prevents the next agent from re-inventing the same tooling or re-running
the same commands without a new reason.

## Open obligations

List every obligation still open, with the exact gap for each. If none, say
so explicitly - an interruption with zero open obligations is usually a
labeling error.

## Attempted routes

One line per route or method tried, with its outcome marker:

```text
- <route_key> `[FAILED|BLOCKED|PARTIAL|SUCCEEDED]`: method summary; failure
  mechanism or partial progress; evidence paths + sha256.
```

This is the contract against duplicate exploration: the next agent must not
re-run a `[FAILED]` route without a new reason, and any new attempt is
recorded here first.

## Next actions

Exact next steps: which obligation to attack, which file/script/command to
open, which route to continue, and what to avoid repeating.

## Key artifacts

- Task packet path + sha256
- `problem_contract.md`, `research_ledger.md`, `approach_registry.md`,
  `candidate_proof.md`, `audit_report.md`, scripts, Lean files: path + sha256
  for each artifact the next agent will need.

## Recovery read order

1. This handoff record
2. `research_ledger.md` (chronological record, last N entries first)
3. `approach_registry.md` (route states and exact gaps)
4. The key artifacts listed above
5. The original task packet (contract and verification criteria)
