---
name: lean-verify
description: Use Lean 4 compiler feedback during research and verify a precise formal target against its intended mathematical statement. Check execution, target identity, transitive axioms and semantic scope, preserving reproducible evidence and reusable reviews.
---

## DSH runtime notes (DSH adaptation)

Load a relevant `$skill-name` with DSH's `skill` tool using its exact name.
Resolve bundled files from the returned `resourceBase`. Run Python helpers
with a local interpreter (`PYTHONUTF8=1` on Windows).

Plugin-level Lean helpers, templates and tests live in this bundle's
`scripts/` and `assets/`. Resolve the Lean toolchain for the actual project.

[DSH execution options](references/dsh-execution.md).

# Lean verification

Use Lean where it helps the mathematics: test a local lemma, formalize a bridge,
inspect a goal or verify a root theorem. A small target needs no node ledger.
For commands and result formats, read [the verification tools](references/v2-verification.md).

Distinguish four questions:

1. What actually ran, in which Lean and dependency environment, and did it finish?
2. What exact declaration, implicit hypotheses, universes and definitions does
   Lean elaborate, and does that mean the intended mathematical statement?
3. Is the target's actual dependency closure free of unproved or unaccepted
   assumptions, including assumptions hidden in imported declarations or defs?
4. Which source, environment and evidence hashes does this result describe?

A build result applies to its actual checked scope. File scans are diagnostics;
root validation needs the exact declaration and transitive axiom inspection.
Missing targets, unavailable tools, failed builds and timeouts are not success.
A proved implication `H -> T` is a conditional result when the desired target is
`T`. Allowed foundational axioms are a policy about the actual closure, not a
requirement that every proof use all of them.

Read back important target statements, definitions and conversion lemmas in
mathematical language. Inspect hidden or impossible assumptions, empty domains,
boundary cases and specialized parameters where relevant. Compare this with the
user's intended theorem; restating the intended theorem is not a semantic audit.
A machine match to a saved contract does not establish that the contract itself
means the right thing.

Use incremental compiler feedback and warm environments while developing a
proof. Typed open leaves and alternative routes can make a large construction
manageable: all dependencies of the selected route must close, while an unused
failed route need not. A cycle cannot justify itself. Final success requires a
materialized root proof, not a graph's completion flags.

Reuse semantic review when its target, relevant definitions and environment
remain unchanged; proof-body changes still need fresh machine checking. Changed
inputs invalidate the affected evidence. Full compiler logs and explicit job
identities support interrupted work. LSP state and build caches are replaceable
acceleration, never the sole record of a verification result.

Present machine results, semantic review, root closure and evidence scope
separately. State any remaining leaves and assumptions. Independent review or an
additional checker can add evidence where useful; neither cloud platforms nor
per-obligation LLM re-proving is required for every proof.

[Release history](references/changelog.md).
