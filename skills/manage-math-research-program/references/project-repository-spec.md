# Project Repository Specification

## Design goals

The repository must support long-running, cross-session work while keeping four ownership domains separate:

1. **Program state** — owned by `manage-math-research-program`.
2. **Literature sources and analyses** — owned by `manage-math-research-program`.
3. **Reusable project knowledge** — owned by `manage-math-research-program`, with provenance gates.
4. **Concrete problem runs** — produced by `$rigorous-open-math-research`; indexed but not reimplemented by the manager.

## Canonical project layout

```text
PROJECT_ROOT/
├── project.json
├── PROJECT.md
├── state/
│   ├── current.json
│   ├── RESUME.md
│   ├── activity.jsonl
│   ├── checkpoints/
│   └── stage-summaries/
├── index/
│   ├── papers.json
│   ├── paper-relations.json
│   ├── open-problems.json
│   ├── tools.json
│   ├── task-packets.json
│   ├── runs.json
│   └── artifacts.json
├── literature/
│   ├── search-log/
│   ├── papers/
│   │   └── PAPER_ID/
│   │       ├── record.json
│   │       ├── sources/
│   │       ├── analysis/
│   │       └── relations.json
│   └── maps/
│       ├── PAPER_MAP.md
│       ├── FRONTIER.md
│       └── TERMINOLOGY.md
├── agenda/
│   ├── DIRECTIONS.md
│   ├── PRIORITIES.md
│   ├── problems/
│   └── task-packets/
├── knowledge/
│   ├── .blueprint/config.json
│   ├── blueprint.json
│   ├── evidence_inventory.csv
│   ├── blueprint_update_requests.jsonl
│   ├── submissions/
│   ├── backups/
│   ├── artifacts/
│   ├── tools/
│   ├── viewer/
│   ├── GLOSSARY.md
│   └── FAILURE_PATTERNS.md
├── runs/
│   └── rigorous-open-math-research/
├── reports/
├── papers/
│   └── <SLUG>/
│       ├── <SLUG>-en.tex      (arXiv-style human-readable proof, English)
│       ├── <SLUG>-zh.tex      (Chinese companion, same statement/proof structure)
│       ├── <SLUG>-en.pdf      (compiled, when a toolchain is available)
│       └── build/             (intermediate LaTeX artifacts)
└── archive/
    ├── superseded/
    └── rejected-duplicates/
```

The `runs/rigorous-open-math-research/` directory is an allowed destination for upstream outputs. The manager may create the run directory and a run manifest, but it does not create the upstream problem-level artifacts inside it.

## File ownership

| Path | Owner | Rule |
|---|---|---|
| `project.json`, `PROJECT.md`, `state/`, `index/` | manager | Authoritative program state. |
| `literature/`, `agenda/`, `knowledge/`, `reports/` | manager | Project-level curation and synthesis only. |
| `papers/` | manager | Human-readable LaTeX proofs of Lean-verified theorems (workflow 8c): English arXiv-style version + Chinese companion, each bound to its machine verification. |
| `knowledge/blueprint.json`, `knowledge/evidence_inventory.csv`, `knowledge/submissions/` | deterministic receiver | Canonical accepted-knowledge base; changes only through the receiver after independent review. |
| `runs/rigorous-open-math-research/RUN_ID/` | upstream solver | May contain upstream standard artifacts. Manager records paths and hashes. |
| `archive/` | manager | Superseded records and rejected duplicates; never use as an active premise. |

Protected upstream filenames include:

```text
problem_contract.md
repro_manifest.md
status_and_literature.md
obligation_graph.md
approach_registry.md
research_ledger.md
counterexample_log.md
candidate_proof.md
audit_report.md
```

Do not create manager-authored files with these names. Do not copy them into literature notes, tool entries, checkpoints, or reports.

## Stable IDs

Use stable IDs independent of directory moves.

Recommended formats:

```text
Project: MRP-YYYYMMDD-SLUG
Paper:  P-YYYY-FIRSTAUTHOR-SLUG-HASH6
Problem: O-YYYY-SLUG-HASH6
Tool:   T-KIND-SLUG-HASH6
Task:   Q-YYYYMMDD-SLUG-HASH6
Run:    R-YYYYMMDDTHHMMSSZ-SLUG-HASH6
Artifact: A-RUNID-SLUG-HASH6
```

`HASH6` is a short digest of the canonical identity, not a claim of cryptographic uniqueness. Store the full canonical identity in the record.

Never change an ID merely because a title or preferred version changes. Use aliases and supersession fields.

## Core index shape

Every JSON index uses:

```json
{
  "schema_version": 1,
  "updated_at": "ISO-8601 timestamp",
  "items": []
}
```

Each item must have its stable ID, a short title, a canonical record path, `created_at`, `updated_at`, and lifecycle fields appropriate to that item.

Indexes are navigational. Detailed records live in their canonical directories.

## Paper deduplication

Treat a mathematical work and its versions separately.

Canonical identity priority:

1. DOI, normalized to lowercase without URL wrappers;
2. arXiv work ID without the `vN` suffix;
3. MR number or zbMATH identifier;
4. normalized title + ordered authors + year fingerprint;
5. content hash only when metadata are unavailable.

One paper record may contain several versions:

- arXiv v1, v2, ...;
- journal accepted manuscript;
- published version;
- correction or erratum;
- author-hosted revision.

Do not create a second paper merely because a later version exists. Add a version entry and update `preferred_version_id` with a reason.

Before saving a paper, check identifiers, normalized title/authors, and source-file hashes. A duplicate source file should be linked to the existing version or placed in `archive/rejected-duplicates/` with a note.

## Tool deduplication

A tool's canonical key is based on mathematical content, assumptions, and output—not its nickname.

Merge entries when they represent the same theorem, construction, estimate, representation, or proof mechanism under equivalent hypotheses. Preserve aliases and all sources. Keep separate entries when assumptions or conclusions differ materially.

Do not merge merely because two papers use the same informal technique name.

## Result deduplication

A concrete run is unique by `run_id`. A mathematical result may appear in multiple runs. Link it through provenance rather than copying prose.

For a reusable result, keep one tool or project-result record with pointers to every supporting run and source. Mark later records as aliases or superseded when appropriate.

## Relations

Use explicit relation records instead of prose-only cross-references.

Paper relation types:

```text
version_of, corrects, extends, strengthens, weakens, generalizes,
specializes, uses, surveys, independent_of, equivalent_formulation,
contradicts, subsequent_work
```

Problem and tool relations may use:

```text
motivated_by, depends_on, informed_by, candidate_for, blocks,
resolves_subcase, supplies_tool, falsifies_route, supersedes
```

Every relation includes source and target IDs, type, evidence location, date recorded, and confidence note. A relation record is not a proof of mathematical implication.

## Integrity checks

At minimum validate:

- required files and directories exist (including `papers/` with its README);
- every `papers/<SLUG>/*.tex` header carries the formalization contract (Lean paths, verification commit hash, zero sorry/axiom) and, when a PDF is present, the PDF exists for both the English and the Chinese source;
- JSON parses;
- IDs are unique within and across indexes where required;
- canonical record paths resolve;
- paper canonical identifiers are not duplicated;
- source hashes are not silently duplicated;
- tool canonical keys are not duplicated;
- artifact pointers resolve or are explicitly marked external/unavailable;
- protected upstream filenames occur only inside registered upstream run roots;
- the canonical accepted-knowledge pair passes `knowledge/tools/validate_blueprint.py` (including the mathematics profile when enabled) and the knowledge event log parses as JSONL;
- `state/RESUME.md` and the latest checkpoint agree on the next action.
