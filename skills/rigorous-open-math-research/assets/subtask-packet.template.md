# Subtask packet - <subtask_id>

- Subtask ID: <e.g. SUB-O2-routeC>
- Parent obligation / route: <obligation ID or route ID>
- Spawned at: <timestamp>
- Budget: <effort cap, deadline>

## Claim

<exact statement attacked, verbatim from the contract or route card; no paraphrase>

## Inputs (by path and hash)

- <path> (sha256: <hash>)
- <path> (sha256: <hash>)

## Context slice (allowed dependencies)

- <definitions, lemmas, sources the sub-agent may rely on; nothing beyond this slice>

## Deliverable

- Return artifact: <path to write, in your own artifact area>
- Allowed status labels: <PROVED | PARTIAL | BLOCKED | REFUTED | FALSIFIED | NONE_FOUND | UNVERIFIED>
- Exact gap to report: <what remains unproved and why>

## Constraints

- Do not claim global completion of the problem.
- Do not mutate shared artifacts (ledger, obligation graph, candidate proof) - write only to
  your own paths.
- Do not repeat a recorded failure without new evidence.
- Do not fabricate run data, citations, or results. Mark unknown fields as unknown.

## Return format

Return the JSON raw (no markdown code fence).

```json
{
  "subtask_id": "...",
  "status": "<label>",
  "artifact_path": "...",
  "artifact_sha256": "...",
  "claim_tested": "...",
  "exact_gap": "...",
  "failure_mechanism": "...",
  "evidence": "..."
}
```