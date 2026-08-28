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

When selecting tools, regard their `applicability` entries: a tool marked
`active` or `conditional` for the current problem class may be suggested; a
tool marked `retired` for that class must not be suggested for it; a tool that
is `archived` (all known classes retired) is not suggested by default but
remains in the archive and is available on explicit search. Class-scoped
retirement never deletes a tool.

## Artifact profiles

Use the proof-first boundary set when the closure-first run reaches a certified
fast close without opening a multi-route portfolio:

- `problem_contract.md`
- `status_and_literature.md`
- `research_ledger.md`
- canonical `obligation_graph.json` (plus `obligation_graph.md` when a human view is useful)
- `closure_gate.md` with hash bindings to `completion_manifest.json` and
  `completion_audit.json`
- `candidate_proof.md`
- `audit_report.md` from one fresh independent package audit
- `repro_manifest.md`
- `final_report.md`
- `reuse_summary.md`
- Lean scaffold (`lean-proof/*.lean` or `formalization_progress.md` entry)
  for every new STRICT/partial result, when the project has `lean-proof/`.

Use the extended research profile when the run escalates, carries multiple live
routes, closes partial or interrupted, produces reusable computation, or runs a
requested frontier upgrade. Add the artifacts that acquired content, including
`approach_registry.md`, `counterexample_log.md`, `escalation_ladder.md`,
`performance_log.md`/`performance.json`, and `reproducibility/`. At a boundary,
record an explicit `not applicable` in `final_report.md` for an expected profile
item that never acquired content; do not create an empty duplicate file.

After a certified fast close, populate indexes, hashes, status files, and concise
summaries deterministically when possible. Do not purchase a research-model call
solely to expand a minimal proof package into the extended profile.

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
