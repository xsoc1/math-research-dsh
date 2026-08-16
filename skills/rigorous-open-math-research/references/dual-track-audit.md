# Dual-track audit: informal verification + Lean formal verification

This file defines how the Danus-style informal proof audit and our Lean-driven
formal verification coexist. They are complementary gates, not alternatives.

## Principle

- **Informal audit** checks the natural-language proof: logical flow,
  definitions, external citations, gaps. It is fast and catches semantic and
  conceptual errors before formalization.
- **Lean verification** checks the machine-checkable formal proof. It is slow
  but gives machine-level certainty.
- A complete delivery requires **both tracks** to pass, plus a paper-level
  re-verification when a paper/report is assembled.

## The four-layer protocol

```
new result
  → 1. Informal audit (Danus-style): zero critical_errors and zero gaps
  → 2. Lean scaffold (Tier 0/1): statement skeleton + load-bearing lemma checks
  → 3. Lean full verification (Tier 2): lake build + zero sorry/axiom + fidelity + independent audit
  → 4. Paper-level re-verification: the assembled document is re-checked as a whole
```

Only completion labels require all four layers. Partial/structural results
require layers 1 and 2 (informal audit + scaffold), with full verification
deferred.

## Role mapping

| Layer | Owner | Authority |
|---|---|---|
| Informal audit | rigorous-open-math-research phase-78 / manage 8e | semantic correctness |
| Lean scaffold | rigorous Phase 10 / lean-verify Scaffold mode | structural correctness |
| Lean full verification | lean-verify | machine correctness |
| Paper re-verification | manage 8c/8e + lean-verify paper-math pass | delivery correctness |

## Conflict resolution

- **Lean passes but informal audit finds a gap**: the formal statement may not
  cover the original problem, or the informal proof has a hidden step. Fix the
  informal proof first, then re-formalize.
- **Informal audit passes but Lean fails**: the formalization itself is wrong
  (types, signatures, proof block). Fix the Lean file.
- **Both pass but paper-level verification fails**: the assembled paper
  introduced a new error (rewording, dropped steps, WLOG). Fix the paper, not
  the individual facts.

Acceptance rule:

> Full delivery = informal audit zero errors/gaps AND Lean full verification
> AND paper-level re-verification.

## Danus hard prohibitions (adopt into informal audit)

1. Do not cite the problem/task description as a substantive math source.
2. Reject unproven conditional premises; every assumption must cite a fact or
   be proved in context.
3. Reject vague gestures at "well-known / classical / routine" results without
   a specific citation.
4. Require self-contained statements: a fact's statement must list its
   hypotheses.
5. Check citation chains: if a cited fact inherits an unproven premise, the
   depending proof inherits the defect.
6. External references must carry the complete statement, paper id, theorem id,
   and arXiv id when available, and must be context-checked.

## Verification matrix

Record both tracks per item in the submission audit:

```markdown
| Item | Informal (Danus-style) | Lean scaffold | Lean full | Paper re-verify |
|---|---|---|---|---|
| Lemma A | PASS | Tier 0 | Tier 2 | — |
| Main theorem | PASS | Tier 0 | Tier 2 | PASS |
```

The matrix is part of the `proof-submission-audit` record (manage workflow 8e).
