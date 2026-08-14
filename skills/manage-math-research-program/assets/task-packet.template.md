# Research task packet

- **Task ID:** `TASK-ID`
- **Project ID:** `PROJECT-ID`
- **Created:** `YYYY-MM-DDTHH:MM:SSZ`
- **Task type:** solve | disprove | construct | formalize | rigorously audit
- **Portfolio problem ID:** `PROBLEM-ID`
- **Task state:** `DRAFT`

## Project reason for this task

Explain why this concrete task is being delegated now and what project decision it may unlock.

## Authoritative problem source

Give the exact source wording or an exact source path, URL, paper ID, version ID, page, theorem, or problem number. Do not normalize a theorem contract here.

## Source bundle

| Item | Stable ID / version | Path or URL | Hash | Role | Verification note |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## Related paper analyses

List version-specific analyses as navigation aids. The upstream skill must recheck original sources.

## Relevant tool-library leads

List tool IDs, intended relevance, maturity, and known applicability risks. These are not automatically trusted premises.

## Known ambiguities and bibliographic risks

List variant formulations, terminology differences, missing sources, corrections, novelty risks, and uncertainties.

## User constraints and available resources

Record allowed searches, tools, attachments, formal systems, computing environment, time or token budget, and any blind-benchmark restrictions.

## Novelty preflight (B0)

Filled by the workflow stage B0 (or pre-filled by the manager before dispatch):
this is the deterministic gate that stops blind solver dispatch. Keep every
line below; replace the placeholders with real values.

- **Openness verdict:** `OPEN | PARTIALLY_OPEN | ALREADY_SOLVED | NOT_VERIFIABLE` (checked YYYY-MM-DD)
- **Novelty audit path:** `RUN_ROOT/status_and_literature.md` or `skip: blind_benchmark|search_forbidden` (+ post-discovery audit plan)
- **Snapshot hash:** `sha256:<snapshot-hash>` of the literature/knowledge snapshot bound to this packet
- **Backfill:** list literature records / portfolio problem IDs updated with the audit conclusions

## Required run location

`RUN_ROOT`

## Upstream invocation

Use `$rigorous-open-math-research` on the concrete problem in this task packet. Treat this packet as project context, not as a verified theorem contract. Independently normalize and audit the exact statement, and recheck every theorem used as a premise against its original source and exact version. Follow the upstream skill's own problem-level workflow and reporting protocol. Write all standard artifacts under `RUN_ROOT`. Return the upstream result status verbatim and the artifact locations. Do not call `manage-math-research-program` from inside the solver run.

## Manager ingestion checklist

- [ ] Preserve upstream status verbatim.
- [ ] Index the run root and artifact paths/hashes.
- [ ] Do not copy or replace upstream standard artifacts.
- [ ] Update the portfolio, maps, tool candidates, budget, checkpoint, and resume entry.
- [ ] Promote reusable knowledge only from exact source or audited artifact locations.
