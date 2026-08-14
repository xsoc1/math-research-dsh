> Phase file for the rigorous-open-math-research skill. Read this file before executing the phases it covers; the global contracts live in the parent SKILL.md. Relative paths in this file (assets/, references/, scripts/) resolve against the skill root (the directory containing SKILL.md).
## Phase 6 — Computational and evolutionary search

Use computation as a discovery and falsification instrument.

Before running code, specify:

```markdown
Mathematical object returned:
Property checked exactly:
Objective or score:
Penalty for invalidity:
Parameter domain and test distribution:
Exact versus floating-point operations:
Time and memory limits:
Random seeds:
Certificate or witness produced:
How a successful candidate could imply a general theorem:
Known evaluator exploits or blind spots:
```

Required safeguards:

- Separate validity from quality scores.
- Include small, large, random, structured, and adversarial parameters.
- Hold out tests not seen during search when possible.
- Minimize or symbolically simplify successful programs to expose a general pattern.
- Search for counterexamples to every inferred formula.
- Preserve the best candidate, its full provenance, and a replay command.
- Audit whether the candidate exploits an implementation detail rather than the mathematical definition.

After finding a pattern, create a **proof bridge**:

1. state the candidate formula or construction for general parameters;
2. prove it is well-defined;
3. prove validity for every allowed parameter;
4. prove the claimed bound or objective;
5. identify what remains unproved about optimality.

Never label a high-scoring numerical path as an optimal theorem without this bridge.
