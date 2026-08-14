# Mathematical Tool Library Specification

## Purpose

The tool library is a persistent retrieval system for reusable mathematics learned from papers or audited project runs. It may contain:

- theorems and lemmas;
- constructions and decomposition schemes;
- inequalities and estimates;
- representations and changes of variables;
- invariants and monotonicity principles;
- proof techniques and local-to-global mechanisms;
- counterexample strategies and obstruction patterns;
- computational certificates or exact finite procedures, when their scope is explicit.

It is not a substitute theorem database and not an independent proof-certification system.

## One canonical entry per mathematical tool

Store each tool in `knowledge/tools/TOOL_ID.md` using `assets/tool-entry.template.md`, and register it in `index/tools.json`.

A tool entry must include:

```text
tool_id
title and aliases
kind
canonical_key
provenance_maturity
source papers and exact locations
supporting upstream runs and artifact locations
mathematical content
input objects and assumptions
output or conclusion
parameter and constant dependencies
applicable scope
known limitations and failure modes
typical uses
worked or cited examples
relations to other tools
reuse checklist
last reviewed date
```

## Kinds

Use a concrete kind:

```text
theorem
lemma
construction
estimate
representation
invariant
proof_technique
reduction_pattern
counterexample_strategy
obstruction
exact_computational_tool
```

A broad label such as “algebraic method” is not a useful tool entry.

## Provenance maturity

Use project-level provenance maturity, not a new proof-result label:

- `LEAD` — remembered, mentioned, or found in a secondary source; not reusable as a premise.
- `SOURCE_LOCATED` — primary source and exact location recorded; statement still requires task-specific hypothesis checking.
- `ANALYSIS_EXTRACTED` — extracted into a version-specific paper analysis with explicit assumptions and limitations.
- `UPSTREAM_AUDITED` — supported by a specified `$rigorous-open-math-research` proof or audit artifact.
- `DEPRECATED` — retained for history but known to be misstated, superseded, or unsafe to reuse.

These labels describe provenance handling. They do not replace the upstream result labels and do not certify a concrete application.

## Promotion rules

### From literature

A candidate may enter as `LEAD`. Promote it only after recording the primary source, exact theorem or section location, source version, assumptions, and limitations.

A manager may summarize a source, but it must not declare a theorem valid for a new context. Every concrete use is rechecked by `$rigorous-open-math-research`.

### From an upstream run

Promote a derived result only when:

1. the exact supporting claim is identifiable in an upstream artifact;
2. its upstream status and audit finding are recorded verbatim;
3. the reusable scope is no broader than the audited statement;
4. all prerequisites and exclusions are copied accurately into the tool entry;
5. the entry links to the proof and audit paths rather than reproducing them.

If any condition is missing, keep the item as a lead or pending extraction.

### Failed mechanisms

A failure can become a reusable obstruction or counterexample-strategy entry when the failure mechanism is exact and supported by a source or upstream artifact. Do not store “this approach did not work” without the smallest failing claim, witness, or structural reason.

## Deduplication

Create a normalized `canonical_key` based on:

- mathematical object class;
- assumptions;
- conclusion or operation;
- parameter dependencies;
- equivalence aliases.

Merge entries only when those components are materially equivalent. Keep variants separate when one has weaker hypotheses, stronger conclusions, different uniformity, or a different domain.

When merging:

1. retain one stable tool ID;
2. add aliases and all source pointers;
3. preserve version-specific differences;
4. record the merge in the activity log;
5. archive the duplicate record with a pointer to the canonical entry.

## Reuse checklist

Before placing a tool in a concrete task packet, record:

- exact source version and location;
- intended target claim;
- matching object class and domain;
- matching hypotheses and regularity;
- constant and parameter dependencies;
- excluded edge cases;
- whether the tool is used directly or only as inspiration;
- items requiring upstream revalidation.

The task packet must say explicitly that the tool is a lead and that `$rigorous-open-math-research` must verify its applicability.

## Relationship to paper analyses and maps

Paper analyses explain where a tool came from. Tool entries explain how it can be retrieved and where it may apply. Paper maps explain how works and directions relate. Do not duplicate the full paper analysis in the tool entry.
