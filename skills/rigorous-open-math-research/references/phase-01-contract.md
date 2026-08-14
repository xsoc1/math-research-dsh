> Phase file for the rigorous-open-math-research skill. Read this file before executing the phases it covers; the global contracts live in the parent SKILL.md. Relative paths in this file (assets/, references/, scripts/) resolve against the skill root (the directory containing SKILL.md).
## Phase 0 — Provenance, status, and scope

Before mathematical search:

1. Identify the authoritative problem statement and date/version.
2. Check whether the problem is genuinely open as of the research date, unless the user explicitly requests a blind benchmark phase.
3. Locate variants whose quantifiers or definitions differ.
4. Inventory every attachment, program, verifier, seed, example, formal library, and environment version.
5. When the run provides a per-problem reference directory (for example `data/<id>.refs/` with markdown, LaTeX, plain text, or pre-extracted PDF text), read those user-provided files before external search. Treat them as user-provided context, not verified facts; cite them in the ledger and in proof steps when they influence the proof. Never present user-provided notes as independently verified results.
6. Record tool and web restrictions exactly.
7. Separate historical facts from reconstructed prompts or suggested workflows.
8. When the run workspace is a git repository, check its state before starting: record the current commit hash and any dirty files in the ledger. Do not silently overwrite uncommitted artifacts; commit them or record the divergence first.

If exact-solution search is forbidden for benchmarking, use two phases:

- **Blind discovery phase:** obey the restriction and record it.
- **Post-discovery novelty audit:** search the literature before making any novelty claim, unless the user explicitly forbids even a later audit.

## Phase 1 — Build the theorem contract

Write `problem_contract.md` with this schema:

```markdown
# Problem contract

## Objects and definitions
## Hypotheses
## Target conclusion
## Quantifiers and dependency of constants
## Equivalent formulations that are actually proved equivalent
## Boundary and degenerate cases
## Permitted outcomes
- affirmative proof
- negative proof / counterexample
- independence or inconsistency result, when logically relevant

## Completion criteria
## Answer space (what decision or judgment the result must support)
## Acceptance criteria per subproblem (when a subproblem is done)
## Results that do not count as completion
## Tool, citation, and search constraints
## Ambiguities or competing interpretations
## Contract audit
```

For an open conjecture, do not assume an affirmative proof exists by default. Preserve both proof and disproof routes unless a trusted benchmark guarantees polarity. If the wording is ambiguous, either obtain clarification or analyze each materially different interpretation separately.

Assign a second role or pass to audit the contract against the source. A proof of the wrong contract is not progress on the original problem.

Fix the answer space before searching: the contract must state which decision or judgment the result is supposed to support (`scope`), and every subproblem must carry acceptance criteria that decide when it is done. A search that does not know what its result must support wastes every round. (Inspired by dsh-deep-research: https://github.com/omdsh-dev/dsh-deep-research.)

When a canonical knowledge base exists, freeze these fields on the `research_goal` record and mirror them in `problem_contract.md`: `contract_version`, `quantifier_contract`, explicit `boundary_cases`, `completion_criteria`, `non_completion_conditions`, `permitted_outcomes`, and `tool_constraints`. A statement or completion-contract change requires a new goal or claim version with an explicit supersession relation; never mutate a frozen statement in place.
