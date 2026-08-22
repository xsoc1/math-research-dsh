# Lightweight Reuse Protocol

## Purpose

This protocol is the default reuse behaviour for Stage B runs. It is based on
three rounds of controlled performance experiments on hard open mathematics
problems (A6, B3, DensBC O1'). The evidence showed:

- A heavy per-route reuse gate costs significant input/cache tokens without
  improving the mathematical outcome on small problems.
- A lightweight protocol on a hard problem reduced steps, tool calls and
  cache-read tokens substantially while preserving a minimum artifact set.
- The main risk of efficiency-focused reuse is documentation loss, so the
  minimum artifact checklist is mandatory.

## Lightweight pre-scan (before major derivation)

Read compact summaries first, not full proofs:

1. `research_map.md` -- project-wide routes, avoid list, status.
2. `tools/README.md` plus the relevant tool entries' summaries.
3. `lean-proof/LEMMA_INDEX.md` -- existing formalized declarations.
4. The latest relevant run's `final_report.md` or `handoff-interrupted-*.md`
   when present.

Read full candidate proofs only when a specific detail is needed.

## Minimum artifact set for every material run

Each Stage B run with material progress must write at least:

- `problem_contract.md`
- `status_and_literature.md`
- `approach_registry.md`
- `research_ledger.md`
- `obligation_graph.md` (or an explicit note if not applicable)
- `candidate_proof.md` (if any mathematical result)
- `escalation_ladder.md`
- `audit_report.md` (or an explicit audit note if independent audit was
  not possible)
- `performance_log.md`
- `final_report.md`
- `reuse_summary.md`
- Lean scaffold (`lean-proof/*.lean` or `formalization_progress.md` entry)
  for every new STRICT/partial result, when the project has `lean-proof/`.

## No per-route tags

Do not require `REUSE:` / `REUSE_MISS:` lines for every attempted route. This
adds overhead without creating a reusable asset. Instead, record actual reuse
actions after the run in `reuse_summary.md`.

## Reuse summary (post-run)

Write `reuse_summary.md` at the run close. It must contain:

- existing tools/results actually reused (paths or slugs);
- duplicate work that was avoided;
- duplicate work that still happened (e.g. re-deriving an existing result);
- new tools/methods created;
- one-line assessment of whether the pre-scan was worth its cost.

## Cross-run discovery

When a parallel sibling run is discovered:

- record it as an external reuse event;
- state whether the sibling result was independently re-derived or only
  cross-checked;
- do not treat an early missing sibling artifact as a reuse miss.

## Lean scaffold requirement

Every new STRICT or partial result must receive a Lean scaffold in the
project's `lean-proof/` directory (or an explicit `formalization: scaffold`
record). Scafolds are not formal verification and must never be labelled
`FORMALLY_VERIFIED`.

## Why this protocol

- It keeps token/cache costs low on hard problems.
- It preserves auditability through the minimum artifact checklist.
- It converts reuse information into a durable per-run asset.
- It prevents the round-2 failure mode of trading documentation depth for
  speed.
