---
name: manage-math-research-program
description: Maintain a long-running mathematics project's literature, reusable tools, annotations, research experience and human editable understanding. Retrieve and connect knowledge across papers, problems and sessions, and manage canonical accepted knowledge when the project uses Blueprint.
---

## DSH runtime notes (DSH adaptation)

Load a relevant `$skill-name` with DSH's `skill` tool using its exact name.
Resolve bundled files from the returned `resourceBase`. Run Python helpers
with a local interpreter (`PYTHONUTF8=1` on Windows).

This bundle includes `scripts/`, `assets/` and `runtime/`. For Blueprint,
`<manage-plugin>` and `<active-manage-plugin>` mean this `resourceBase`;
the gateway is `runtime/blueprintctl.py`.

[DSH execution options](references/dsh-execution.md).

# Long-term mathematics research

Make accumulated research useful to the next mathematical decision. Prefer the
project's existing progress page, tool cards and research map over parallel
ledgers. A small project can start with a few Markdown files. Organize or solve
the requested work directly; specialized research and Lean skills are available
when their methods or tools help.

## Literature and reusable knowledge

The core is an annotatable library with pointers to actual content. Use
[scripts/research_library.py](scripts/research_library.py) to capture a retrieved
source, read it in bounded segments, index tools, query them and add annotations.
The [library guide](references/v2-library.md) describes the concrete commands,
experience comparison and the human editable understanding page.

Read enough of the original source to verify the material being used. Preserve
its URL or publication identity, version, raw/text hashes and locators. OCR or
text extraction may damage formulas; inspect the original when meaning is
unclear. Distinguish actual reading from capture, and your interpretation from
the source's claim.

A tool can be a theorem, useful inequality, transformation, construction,
algorithm or executable certificate. Start with mathematical content, known
conditions and a source or derivation pointer. Add examples, aliases, Lean
references or failure modes when useful. Small cards do not need an exhaustive
form. Agent annotations are searchable and bound to the card version they
comment on; they do not silently broaden its proof or verification scope.

An experience entry can preserve a successful route or a useful obstruction.
Record what failed, its conditions and what new fact would justify another
attempt. Distinguish disproved statements, weak methods, missing lemmas and
infrastructure failures. Keep the old evidence when revising an interpretation.
Cross-route comparisons can suggest a candidate invariant, definition or common
mechanism; attach a testable prediction and keep candidate status visible.

Keep the project understanding page readable by the human collaborator: current
explanations, competing ideas, recent changes in understanding, and decisions or
questions that would benefit from discussion. Preserve human edits and label
intuition as intuition. Generated pointers and comparison views are disposable;
source notes, comments and proofs are the durable content.

## Continuity and accepted knowledge

Before ending substantive work, leave enough current information to continue:
the goal, findings and artifact pointers, unresolved points and useful next
ideas. Use the existing progress page. For tracked jobs or atomic snapshots,
read the workflow plugin's continuity guide if installed; otherwise use ordinary
files and the actual task identities. Do not treat a missing response as a
mathematical failure or restart an unknown external action blindly.

A project using Blueprint keeps its physical layout in `blueprint-project.json`.
Resolve the active manage plugin's `runtime/blueprintctl.py`, run `ensure` once for
that project/runtime, and use the gateway for canonical query, proposals and
reviewed integration. Do not copy or execute stale project-local Blueprint tools.
Read [the runtime guide](references/blueprint-runtime-gateway.md) when using it.
Preserve immutable evidence and protected accepted claims. Free-form notes and
hypotheses need no canonical submission.

[Release history](references/changelog.md).
