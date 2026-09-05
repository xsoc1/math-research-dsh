# Literature Tracking and Paper Analysis

For cached source discovery, actual retrieved-byte capture and bounded reading,
use `references/library-runtime.md`. Preserve source versions and exact original
page/theorem locators while extracting reusable cards and candidate annotations.
The helper stores evidence; it does not certify source claims or search the web.

## Search objective

A literature cycle should answer a dated project question, such as:

- What is the strongest known result under the target hypotheses?
- Which papers introduced the currently used mechanism?
- What corrections, counterexamples, or later improvements exist?
- Which formulations of an open problem are genuinely distinct?
- Which recent papers alter the project's priorities?

Do not search only the exact wording supplied by the user. Track terminology variants, older names, adjacent subfields, and citation chains.

## Source channels

Use the following as available:

- Google for broad discovery, author pages, conference material, and terminology;
- Google Scholar for citation chains, related works, and versions;
- arXiv for version history and recent preprints;
- semantic theorem-retrieval services over indexed arXiv theorem corpora (for example a Lean-based theorem-search endpoint) when searching for exact statements of nearby theorems, lemmas, or definitions; query with a complete mathematical statement rather than keywords, and record the returned arXiv id / theorem id / paper id for every candidate before citing it;
- MathSciNet, zbMATH Open, journal databases, proceedings, theses, and specialist repositories for professional indexing and reviews;
- DOI/Crossref and publisher pages for bibliographic normalization;
- author pages or institutional repositories for legal source copies when needed.

Record lack of access rather than implying a database was searched.

## Search log

Create one file per coherent search batch in `literature/search-log/`.

Required fields:

```text
search_id
research question
search date and timezone
databases actually searched
exact query strings and filters
cutoff or date window
results screened
inclusion and exclusion rationale
citation chains followed
new terminology and aliases
new papers or versions registered
negative findings and unresolved bibliographic questions
next search actions
```

A statement such as “no later work exists” is allowed only as a dated, source-bounded search finding.

## Paper record

Use `assets/paper-record.template.json`.

Minimum content:

- stable `paper_id` and canonical identity;
- exact title and ordered authors;
- identifiers: DOI, arXiv work ID, MR, zbMATH, journal coordinates;
- source type and publication status;
- version list with labels, dates, URLs, local paths, and hashes;
- preferred version and reason;
- project relevance and related problem/tool IDs;
- relation records to earlier, parallel, corrected, or later work;
- analysis path and last verification date;
- unresolved metadata or source-access issues.

## Citation integrity

- Every citation in project records, maps, analyses, and task packets must include a stable link (DOI, arXiv work ID with version, or permanent URL) that a reader can open.
- Never fabricate a paper, author list, identifier, or source. Do not cite a work you have not verified to exist with a recorded locator.
- Never attribute a theorem, numerical value, or conclusion to a paper without checking the exact source, version, and location (page, theorem, or section).
- A conclusion recalled from memory, analogy, or a secondary summary is not project evidence until the primary source is checked and recorded.
- When a source is inaccessible, record the access failure; do not present an unread summary as if it were the paper.

## Version policy

Use one work record with explicit versions. Do not silently replace a stored source.

When a new version arrives:

1. add a version entry;
2. preserve the prior source and hash;
3. compare theorem statements, hypotheses, numbering, and proof changes relevant to the project;
4. record whether the preferred version changes and why;
5. update analyses that cite version-specific locations;
6. mark corrections or withdrawals prominently.

An erratum may be a version relation or a separate paper, depending on whether it has its own canonical bibliographic identity. In either case, link it explicitly.

## Triage levels

Use triage to allocate curation effort, not to certify mathematics.

- `DISCOVERED` — metadata lead only.
- `REGISTERED` — canonical identity and at least one source verified.
- `SCREENED` — relevance assessed from the source.
- `ANALYZED` — structured analysis completed for a specified version.
- `MONITORED` — included in recurring forward-citation or version checks.
- `SUPERSEDED` — retained for provenance but not preferred.

These are literature-workflow states, not proof-status labels.

## Structured TeX paper analysis

Use `assets/paper-analysis.template.tex`. The analysis must be version-specific and compile independently when feasible.

### Required sections

1. **Identity and provenance**
   - paper ID, exact version, retrieval date, hash or stable source, analysis date;
   - version differences relevant to this analysis.

2. **Project relevance**
   - which research directions and open problems it affects;
   - why it was selected for deep analysis.

3. **Definitions and notation**
   - the paper's conventions and any translation to project notation;
   - potentially ambiguous terms.

4. **Theorem and proposition inventory**
   - theorem number or exact location;
   - paraphrased mathematical content with quantifiers and hypotheses preserved;
   - dependency on earlier results;
   - whether the statement is used later in the project.

5. **Proof architecture**
   - high-level dependency structure among sections and lemmas;
   - central reductions and irreversible steps;
   - where compactness, regularity, induction, representation changes, or computation enter.

6. **Key techniques**
   - the mathematical mechanism, not merely a topic label;
   - input assumptions, produced output, and proof role;
   - candidates for the tool library.

7. **Hypothesis-use table**
   - each important hypothesis;
   - exact locations where it is used;
   - what appears to fail without it;
   - whether later work weakens it.

8. **Limitations and failure boundaries**
   - excluded cases, nonuniform constants, dimension restrictions, regularity assumptions, characteristic restrictions, or hidden finiteness;
   - known counterexamples and corrections.

9. **Relations to the literature**
   - prior results used;
   - independent or competing approaches;
   - later improvements, corrections, or applications;
   - terminology equivalences.

10. **Open ends and generalization candidates**
    - explicit questions raised by the authors;
    - gaps between the theorem proved and the project's target;
    - plausible extensions clearly labeled as proposals, not results.

11. **Project actions**
    - map updates;
    - tool entries to add or revise;
    - problem records affected;
    - whether a concrete task packet should be prepared.

12. **Verification notes**
    - page/theorem references checked;
    - claims not yet verified from the primary source;
    - source-access limitations.

## What the analysis must not become

Do not turn a paper analysis into:

- a theorem contract for a new open problem;
- an obligation graph for proving the paper's theorem;
- a competing candidate proof;
- an audit declaring an individual result correct, complete, or novel;
- a replacement for the original source.

When a paper theorem becomes a premise in a concrete attack, send both the source and analysis to `$rigorous-open-math-research` for exact revalidation.

## Paper map

`literature/maps/PAPER_MAP.md` should contain:

- a dated scope statement;
- thematic clusters;
- foundational papers;
- strongest current results by formulation;
- correction and counterexample chains;
- recent frontier papers;
- relation table or graph source;
- unresolved citation or terminology questions.

Prefer relation records that can be traced to paper IDs and source locations. Do not use arrows implying theorem-strength implication without evidence.

## Open-problem extraction

An open-problem record may be created from a paper, survey, or user source. Preserve:

- source wording and location;
- date and version of the source;
- known variants without declaring them equivalent;
- related papers and tools;
- current program priority and rationale;
- latest dated literature check;
- management state and delegation history.

Exact normalization and proof criteria belong to `$rigorous-open-math-research`, not to the project record.
