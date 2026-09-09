# Literature, reusable tools and research experience

Use `scripts/research_library.py` for captured literature, small tool cards and
annotations. Use `scripts/research_experience.py` when a route teaches something
worth retaining or several routes merit comparison. These commands organize
records; they do not modify the accepted Blueprint graph or prove applicability.

In the examples, `LIBRARY` and `EXPERIENCE` stand for those script paths, and
`PROJECT` is the explicit research project directory. Quote paths in the shell.

## Read actual source content

Search and read with the available web or PDF tools, then capture the bytes you
actually obtained. A title or search snippet is not a full paper. Record the
edition, commit or arXiv version, original page/theorem/equation and actual
coverage. Retain the raw PDF alongside extracted text when available.

```text
python LIBRARY capture-source --project PROJECT --input paper.pdf --text-file paper.txt --url SOURCE_URL --version v2 --title "Paper title" --method pdftotext --coverage "pages 7-9" --locator "Theorem 2, p. 8"
python LIBRARY find-source --project PROJECT --query "paper title"
python LIBRARY find-source --project PROJECT --query "comparison inequality" --content
python LIBRARY read-source --project PROJECT --source-id SOURCE_ID --start-line 1 --max-lines 80
python LIBRARY read-source --project PROJECT --source-id SOURCE_ID --start-offset NEXT_OFFSET
```

`read-source` checks metadata, raw and extracted hashes. Continue at its returned
Unicode character offset to avoid gaps, including inside a long line. Extraction
line numbers are navigation aids. Revisit the original page when a formula is
uncertain. The helper neither fetches papers nor certifies OCR or comprehension.
Source IDs retain the version and exact captured bytes; repeated identical
captures reuse them. Earlier 1.x source IDs are unchanged.

## Small cards and free annotations

Existing Markdown cards can be indexed without rewriting them. For a new card,
only `content` is required. Add the scope and source pointers that make it useful.
Omitted conditions are reported as `UNSPECIFIED`, not treated as universal.
Queries also return the card's separate `scope` field when present; it is not
silently substituted for an explicit list of conditions.

```json
{
	"title": "A useful comparison step",
	"content": "State the actual inequality or describe the operation.",
	"conditions": ["State the domain and hypotheses actually needed."],
	"sources": [{"source_id": "SOURCE_ID", "locator": "Theorem 2, p. 8"}],
	"evidence_status": "CANDIDATE"
}
```

```text
python LIBRARY card --project PROJECT --input card.json
python LIBRARY card --project PROJECT --input revised-card.json --tool tools/existing.md --expected-sha256 CARD_SHA256
python LIBRARY index --project PROJECT --tool-root tools --readme tools/README.md
python LIBRARY query --project PROJECT --query "comparison inequality" --limit 8
python LIBRARY annotate --project PROJECT --tool tools/existing.md --text-file note.txt --author RUN_OR_PERSON --kind observation
python LIBRARY annotate --project PROJECT --tool tools/existing.md --expected-sha256 CARD_SHA256 --text-file correction.txt --locator "Theorem 2, p. 8" --source-id SOURCE_ID
```

Use the returned card path/hash; IDs are generated when absent. Different
contents do not merge merely because titles match. A changed existing card
requires its current hash. Repeating the same saved bytes is idempotent.
The helper preserves unspecified metadata when updating an existing card.

Annotation kinds are free text. Author defaults to `unspecified` and locator to
`card`; provide a precise source locator for a literature correction. The card
hash is optional for convenience, but passing the hash you read detects an
intervening edit. Notes are immediately searchable without an index refresh.
Their candidacy label does not prevent retrieval and does not promote a theorem.

`index` refreshes `index/tools.json` and only the generated marker block in the
chosen README. Repeat `--tool-root` for custom roots. Later calls can omit roots
to reuse the stored selection. Experience cards are included automatically when
present. Unchanged cards reuse parsed metadata; current file hashes are checked.

Old cards, old annotations and custom index fields retain their identities.
Card snapshots live in `research/library/card-versions/`; previous index bytes
are retained in `index-history/` when replaced. Paths follow a configured
`blueprint-project.json` research root. The live index is a derived pointer view.
`index` returns `previous_index_snapshot` when replacing an existing index. If
the live index is lost, rebuild with `--from-index SNAPSHOT_PATH` to retain old
IDs and custom metadata while rescanning actual current card bytes. This option
requires a missing destination, so it cannot silently roll back a newer index.
`inherited_metadata` names fields retained from an older index rather than
asserted by the current card; recheck these when deciding applicability.

A changed or missing card gives `STALE_INDEX` and `changed_paths`, while healthy
hits remain available. The CLI returns exit 1 for this partial stale view; its
JSON distinguishes it from `INVALID`. Refresh before using an affected card.
Bad card metadata, duplicate IDs or damaged annotations are isolated and named.
Use `--include-unreviewed` to inspect uncertain card pointers and
`--include-archived` for retired cards. Neither option repairs or reactivates them.

After a card changes, old notes retain their original card hash and appear as
`STALE` pointers. They do not affect current keyword matches unless requested:

```text
python LIBRARY query --project PROJECT --query "old failure mechanism" --include-stale
```

## Programs and exact Lean references

Attach local files through `resources` or `evidence`, for example
`{"path": "checks/positivity.py", "locator": "check_certificate", "kind": "program"}`.
Saving binds their actual hashes. They are searchable and queries report
`CURRENT`, `STALE_OR_UNBOUND` or `INVALID` per reference. The library does not
execute a program just because it was retrieved. Record its inputs, domain,
output meaning and limitations in the card.

The optional `lean` array can retain `repository`, fixed `commit`, `module`, full
`declaration`, `environment`, `actual_type`, and `conversion_lemmas`. Its optional
`source` and `verification` objects and `definitions` list use the same local
path/hash references. Obtain these values from actual Lean tooling; omitted
identity fields are listed in query results. Local byte checks do not certify
the declaration, its premises or the meaning of a verification report. The
returned `UNVERIFIED_DECLARATION_REFERENCE` means the library has not performed
that verification itself. Keep conditional statements conditional.

## Retain experience from successful and failed routes

An experience record can hold a question or a conclusion, with optional free
content. Add information when it helps later research, not after every action.

```json
{
	"title": "What the attempted relaxation lost",
	"question": "Can this bound control the remaining parameter range?",
	"outcome": "failed",
	"failure_kind": "method_limit",
	"scope": "The attempted relaxation on the specified domain.",
	"mechanism": "Describe which dependency was discarded and where the estimate stopped working.",
	"transformations": ["Name the reusable transformation, with its scope."],
	"reconsider_when": ["A sharper bound retains the missing dependency."],
	"not_applicable_to": ["This does not disprove the original conjecture."],
	"evidence": [{"path": "runs/route/notes.md", "locator": "Failed bound"}]
}
```

```text
python EXPERIENCE record --project PROJECT --input experience.json
python LIBRARY index --project PROJECT
python LIBRARY query --project PROJECT --query "missing dependency"
```

Outcomes are `success`, `partial`, `failed`, `no_return`, `unknown`. Failure kinds
are `counterexample`, `method_limit`, `missing_lemma`, `infrastructure`, `unknown`.
They describe reported evidence rather than assigning an audit verdict.
`no_return` is a process outcome and cannot be recorded as a mathematical
counterexample. The cause may still be unknown. Reconsideration triggers remain
searchable; a failed approach does not become a permanent prohibition.

Experience cards default to `research/library/experiences/`. To update one, use
`record --tool RETURNED_PATH --expected-sha256 RETURNED_HASH`, as for ordinary
cards. Free annotations work on these cards too.

## Compare routes and maintain shared understanding

```text
python EXPERIENCE compare --project PROJECT --route CARD_A --route CARD_B --hypothesis hypotheses.json
python EXPERIENCE understanding --project PROJECT --route CARD_A --route CARD_B --comparison COMPARISON_PATH --output research/understanding.md
```

`compare` binds the selected route versions and mechanically collects their
scopes, mechanisms, evidence and exact matching transformation labels. It does
not infer a new theorem from matching phrases. An optional hypothesis JSON
object or list contains `explanation`, `scope`, `prediction`, `test` and optional
`falsifier`. The author supplies the mathematical idea and a test that could
distinguish it from alternatives. Output hypotheses always remain unvalidated
`CANDIDATE_EXPLANATION` records. Without supplied hypotheses, the comparison
contains evidence and no invented explanation. Repeating it reuses the same
content-addressed comparison file.

`understanding` assembles these records and candidates into an editable page,
defaulting to `research/understanding.md`. Without `--route`, it uses indexed
experience cards. It marks comparison inputs that changed since the comparison.
Write human intuition, competing explanations, questions and decisions outside
the generated markers. Those bytes are preserved exactly. If the generated
region itself was manually edited, refresh refuses to overwrite it: move the
handwritten material outside the markers before retrying. No user intuition is
automatically relabeled as an accepted mathematical fact.

## Library write recovery

Source records, card versions, notes and comparisons publish complete immutable
files. Retry the identical command after a failed write. Card replacements and
index/README/page writes are individually atomic. If interruption occurs after
the index but before the README, rerun `index` with the saved roots; the generated
view catches up without duplicating notes. Historical records are never edited
to make a retry succeed.

Writers cooperate through `research/library/writer.lock`. A live writer causes
explicit contention. After a hard process exit, establish that the recorded
writer has ended before archiving its lock and retrying; never delete a live
writer's lock. This helper does not recover unsaved reasoning or reconstruct
unknown remote side effects. General progress and job recovery belong to the
workflow's `research_state.py`.

Implementation checks, the frozen Q9 replay and their limits are recorded in
[v2-library-implementation-notes.md](v2-library-implementation-notes.md).
