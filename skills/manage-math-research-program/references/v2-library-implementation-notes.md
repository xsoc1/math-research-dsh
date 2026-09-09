# Library and long-term experience implementation, 2026-09-09

This implements the authorized library portion of 2.0. The public command guide
is [v2-library.md](v2-library.md). General research-state/job recovery, entrypoint
changes and release manifests belong to the coordinating implementation.

Only `research_library.py`, the new `research_experience.py`, their three scoped
test files and these two references were edited for this portion. No mathematical
canonical graph, frozen Q9 file, old card or old annotation was rewritten in the
source research project. No commit, push, additional agent, vector database or
approval workflow was introduced by this work.

## Delivered interfaces

`LIBRARY` denotes `scripts/research_library.py`; `EXPERIENCE` denotes
`scripts/research_experience.py`. Supply an explicit quoted `PROJECT` path.

```text
python LIBRARY capture-source --project PROJECT --input paper.pdf --text-file paper.txt --url SOURCE_URL --version SOURCE_VERSION --title TITLE --coverage "actual retrieved pages" --locator "original theorem/page"
python LIBRARY read-source --project PROJECT --source-id SOURCE_ID --start-offset NEXT_OFFSET
python LIBRARY card --project PROJECT --input card.json
python LIBRARY annotate --project PROJECT --tool CARD --expected-sha256 CARD_HASH --text-file note.txt --kind "reconsideration" --author RUN_OR_PERSON
python LIBRARY index --project PROJECT
python LIBRARY query --project PROJECT --query "reconsideration cue"
python LIBRARY query --project PROJECT --query "historical failure cue" --include-stale
python EXPERIENCE record --project PROJECT --input experience.json
python EXPERIENCE record --project PROJECT --input updated-experience.json --tool CARD --expected-sha256 CARD_HASH
python EXPERIENCE compare --project PROJECT --route CARD_A --route CARD_B --hypothesis hypotheses.json
python EXPERIENCE understanding --project PROJECT --route CARD_A --route CARD_B --comparison COMPARISON_PATH --output research/understanding.md
```

Existing capture/read/find/index/query/annotate signatures remain usable. New
cards need only content. Scope, sources, programs and Lean declarations remain
optional. An ordinary note is searchable immediately, with its exact card
version. Kind is free text. Missing scope remains `UNSPECIFIED`.

The index reports unhealthy/stale records individually and retains healthy
hits. Inherited old metadata is explicitly named. Changed versions keep old
notes and raw card snapshots. `index --from-index SNAPSHOT_PATH` reconstructs
old identities/custom metadata after loss of the live index while reading
current card bytes. Unchanged refreshes do not rewrite the index or snapshots.

Local program/evidence hashes are checked independently of the card hash.
Optional Lean references preserve the exact supplied identity/type and local
source/report hashes. They are labeled as references the library has not
independently verified; source changes invalidate their local byte binding.

Experience cards retain scope, actual transformations, reported outcome,
failure mechanism, reconsideration triggers and explicit non-applicability.
`no_return` cannot become a mathematical counterexample. Comparison hypotheses
must be supplied with a scope, prediction and proposed test. They remain
unvalidated candidates, including when input tries to label them accepted.

The understanding page mechanically assembles records and candidates. Human
text outside its generated markers is preserved byte for byte. Manual edits
inside the generated region cause refresh to refuse the overwrite. Updating a
reconsideration note preserves an old evidence hash even if the referenced
argument has changed; the association is then visibly stale.

## Behavioral tests executed

From the plugin repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -X utf8 -m unittest discover -s plugins/manage-math-research-program/skills/manage-math-research-program/scripts/tests -p 'test_*.py' -v
```

Observed final functional suite: **26 tests passed**, exit 0, 5.611 seconds on
this WSL/Python environment. This local duration is not a solver benchmark.

| Tests | Observed behavior |
| --- | --- |
| 14 library tests | Small cards, safe updates and retained metadata; immediate free-note retrieval; stale-note lookup; bad cards/UTF-8/annotations and duplicate IDs isolated; healthy hits survive another card changing; old IDs/custom fields rebuilt; archived restrictions retained; versioned source coverage and exact Unicode continuation; program/Lean-reference staleness; no PyYAML requirement for new JSON headers; no writes on unchanged refresh; actual CLI round trip |
| 11 experience tests | Scope and reconsideration cues survive record/update/query; distinct failure kinds; `NO_RETURN` stays an infrastructure outcome; candidate comparison cannot become accepted; changed input versions are visible; human UTF-8/CRLF prefix and suffix bytes survive refresh; generated-region manual edits are protected; bad records isolated; input cards cannot become output pages; historical evidence binding survives a new note |
| 1 frozen Q9 replay | A/B/C proof bytes and original source versions captured and reconstructed; scoped experience assembled; exact program retrieved in a fresh process; polynomial reuse inside a new subrectangle passes and an outside-domain request is rejected as not covered |

Interruption tests include an actual child process calling `os._exit(91)` just
after its annotation file was published. After establishing that this process
had exited, the test archived its remaining writer lock and retried the same
write. Exactly one annotation remained, with identical bytes. Another fault
occurred after index publication but before README replacement; retry completed
the generated view without duplicating a note or changing human text. Partial
source capture and a failed understanding-page publication also recovered by
retry. These exercise the library's own disk writes, not Codex quota handling
or a remote job API.

`tests/smoke_research_library.py` was also run without editing it. Six of its
seven 1.x tests passed. Its remaining assertion expects one damaged annotation
to throw an exception for the entire query. That expectation intentionally
conflicts with the approved 2.0 behavior; the new corruption test instead
requires an explicit issue and a healthy result. The root implementation owns
updating that shared smoke expectation and including this scoped suite in CI.

Python AST parsing, UTF-8/no-BOM, LF, tab-indentation inspection and scoped
`git diff --check` passed for the changed runtime/test files. The repository
validator returned 81 passing checks at an intermediate integration snapshot.
After the final scoped edits, it returned exit 1 with exactly six stale manifest
hashes for the runtime, guide and tests; no other validator errors were reported.
The root implementation owns regenerating the manifest, including this new
notes file, and running release validation against the complete final snapshot.

## Actual old-card migration and frozen Q9 evidence

The first real replay ran:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -X utf8 plugins/manage-math-research-program/skills/manage-math-research-program/scripts/tests/test_library_q9_reuse.py --output /mnt/f/tools/math-research-v2-library-20260909 --legacy-project "/mnt/f/LaTeX/BVE research"
```

It passed with 77 old cards, all 3 custom legacy index rows retained, 14 existing
metadata problems isolated, and 89 original inputs retaining their hashes. Its
results and source hashes are in the external replay's `results.json`. The
first run took 59.565 seconds including copying and durable writes on this
mounted filesystem. It exposed needless republishing of identical snapshots;
the implementation now reuses existing identical bytes and tests that a no-op
refresh performs zero atomic replacements and zero fsync calls.

The final replay uses the same command with output directory
`/mnt/f/tools/math-research-v2-library-20260909-final`. Its local result bundle
contains the original input hashes, generated project, source captures,
understanding page, candidate comparison, program-check output and two new
process reuse results. **Final replay: PASS**, exit 0, 55.457 seconds. It again
retained 77 cards, 3 legacy rows and all 89 original input hashes, isolated the
same 14 existing metadata problems, checked 9 frozen artifact bindings, and
matched all 230 certificate coefficients and four polynomial definitions.
The two runs are local engineering replays, not a controlled timing comparison.
`implementation-runtime-bindings.json` in the final bundle records the two
helper and three test-file hashes measured after the final functional run.

The selected evidence is the existing frozen Q9 A/B/C answers, B's route notes,
Route11 reconciliation and C's four exact certificate files/program. Nine
artifact hashes are checked against the frozen solver manifests. Source proof
bytes are also checked against the Git commit used in their source URLs.

The experience cards keep these boundaries:

- A uses `Q>0` to obtain `sqrt(r)<12/25`; B obtains `r<c^2/4`; C obtains `r<1/9`,
  within the stated Q9 domain and C2/C3 assumptions.
- C1 is unused for the specified Q9 conclusion. Nothing here removes it from
  the full KP-DET problem or upgrades the main project's canonical status.
- B's failed crude cotangent relaxation lost information and left large-g
  gaps. Its reopening trigger concerns a sharper bound retaining the angular
  dependency. It is a method limitation, not a counterexample to Q9.
- Route11's no-return wave supplies no mathematical result. W16's cause is
  unknown; W17 was rejected at the usage limit. Neither outcome is a refutation.

The later deterministic consumer receives a problem/query and a project
retrieval entry. It retrieves the indexed certificate program and reads its
recorded domain. For `Npstar`, it recomputes 130 rational Bernstein coefficients
on `c in [3/4,5/6]`, `t in [2/5,3/5]`. The observed minimum is
`3375573111339/1000000000000 > 0`. For `c in [1/2,3/5]`, it returns
`NOT_COVERED` because the recorded polynomial box starts at `2/3`, without
claiming a mathematical counterexample. The final replay additionally compares
all 230 coefficients and all four polynomial definitions with the frozen JSON
certificates, rather than checking only their minima.

## What this does not establish about literature understanding

This batch uses real frozen mathematical proof artifacts as primary source
content, plus explicitly synthetic fixtures for version/transport/error cases.
It does **not** add a new live-paper comprehension study. In particular:

- No new network search-to-full-paper reading task was performed by an agent.
- No PDF/OCR formula transcription was certified against original page images.
- No agent extracted and audited a complete paper's hypotheses, definitions,
  theorem scopes or convention changes as part of this batch.
- No fresh agent was tested on an unfamiliar mathematical problem requiring
  discovery and correct application of a paper's theorem from this library.
- No new Lean proof or paper-to-Lean semantic equivalence was verified by this
  library work; the Lean test is an explicitly unexecuted reference fixture.

The earlier `scripts/replay_literature.py` PDF exercise established byte
transport, source versioning and bounded reading. It did not establish paper
comprehension, and it is not counted as such here. The new process polynomial
consumer establishes a narrower engineering fact: evidence can survive
organization and be retrieved with enough scope to support a checked reuse or
an explicit non-applicability result. It is not an independent agent study,
new mathematical discovery, a general research-speedup estimate or a full Q9
proof audit. A stranger-use check is owned by the root implementation.
