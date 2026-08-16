# Proof submission audit record

Use this record whenever a proof document (Lean file, LaTeX proof, candidate
proof, or formalization scaffold) is submitted for acceptance into the
repository. The process has three mandatory stages:

1. **Repository comparison** - compare the submission with existing results.
2. **Lean verification and audit** - machine-check and independently audit.
3. **Add by rules** - update repository records only after the first two stages
   pass (or pass with explicit partial/scaffold status).

```text
- **Submission ID:** `SUB-...`
- **Date:** `YYYY-MM-DDTHH:MM:SSZ`
- **Submitter:** `<agent/human id>`
- **Proof type:** `lean | latex | markdown | scaffold`
- **Target problem / result slug:** `...`
```

## 1. Repository comparison

List the existing records checked and the result of each comparison:

- Existing result IDs / paths checked (docs, runs, lean-proof/STATUS.md,
  tools, knowledge, papers).
- Duplicate / superseded / contradictory findings:
  - `NO_CONFLICT` | `DUPLICATE` | `SUPERSEDED` | `CONTRADICTS` (+ details)
- If `SUPERSEDED` or `CONTRADICTS`, record the exact old record and whether the
  submission replaces it.

## 2. Lean verification and audit

- Lean files submitted: path + sha256.
- Machine checks:
  - `lake build` exit: `PASS | FAIL` (+ log path)
  - `sorry/admit/axiom` hits: list or `NONE`
  - statement fidelity: `FAITHFUL | MINOR_PARAPHRASE | UNFAITHFUL`
- Independent audit:
  - Auditor ID (must differ from submitter)
  - Verdict: `FORMALLY_VERIFIED | MACHINE_ACCEPTED_PENDING_AUDIT |
    CANDIDATE_VERIFIED | REPAIRABLE_GAP | FATAL_GAP |
    VERIFICATION_INCOMPLETE | SCAFFOLDED`
  - Critical errors / gaps / repair hints.
- If no Lean file was submitted, state whether a scaffold was created
  (mandatory for new/partial results) and its path.

## 3. Add by rules

Only after the above passes (or is explicitly registered as partial/scaffold):

- Files to add/update:
  - `lean-proof/STATUS.md`, `lean-proof/README.md`,
    `formalization_progress.md`
  - `index/`, `state/current.json`, `state/RESUME.md`
  - `papers/` (for verified human-readable proofs)
  - `tools/` (if a new reusable method/tool)
- Superseded records: list old results marked `superseded` with pointers.
- Commit hash after adding.
- Git sync status: `origin/fork` both updated.

## Acceptance decision

- `ACCEPT` - full verification passed and repository comparison clean.
- `ACCEPT_AS_SCAFFOLD` - partial result accepted with scaffold status.
- `REJECT` - fatal gap, unfaithful statement, or repository conflict.
- `REVISE_AND_RESUBMIT` - repairable gap or missing required record.
