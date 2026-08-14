# Delegation to `$rigorous-open-math-research` and Result Ingestion

## Boundary principle

The manager prepares **context and logistics**. The upstream skill performs **problem-level mathematics and auditing**.

A task packet may narrow the project goal, identify sources, and state resource constraints. It must not precompute the upstream theorem contract, proof obligations, route portfolio, audit taxonomy, or result protocol.

## Task packet creation

Create `agenda/task-packets/TASK_ID.md` from `assets/task-packet.template.md` and register it in `index/task-packets.json`.

Required content:

1. `task_id`, title, project ID, creator, and date;
2. task type requested from upstream: solve, disprove, construct, formalize, or rigorously audit;
3. authoritative problem source or exact location of the source wording;
4. reason this task is prioritized now;
5. related problem, paper, and tool IDs;
6. source bundle with exact versions, paths, URLs, and hashes when known;
7. known ambiguities, variant formulations, and bibliographic risks;
8. user constraints, available tools, environment facts, and run-specific resource budget;
9. required run root;
10. explicit upstream invocation text;
11. manager-side ingestion checklist.

## Forbidden packet content

Do not include manager-authored substitutes for:

```text
problem_contract.md
obligation_graph.md
approach_registry.md
research_ledger.md
candidate_proof.md
audit_report.md
```

Do not prescribe route families, proof-agent schedules, proof bridges, formalization stages, or verdict labels. It is acceptable to link user-supplied hints and prior notes as untrusted context.

## Invocation contract

Use this exact semantic contract, adapting only paths and user constraints:

```text
Use $rigorous-open-math-research on the concrete problem described in:
TASK_PACKET_PATH

The packet contains project context and literature leads, not a verified theorem contract.
Independently normalize and audit the exact problem statement. Recheck every theorem
used as a premise against the original source and exact source version. Follow your own
problem-level workflow and output protocol. Write all standard artifacts under:
RUN_ROOT

Return your result status verbatim together with the run root and artifact locations.
Do not call manage-math-research-program from inside the solver run.
```

The dependency remains one-way even when the manager resumes after the call.

## Upstream internal sub-agent delegation

The upstream skill may split a concrete task into parallel sub-agents (route explorers,
obligation provers, counterexample hunters, literature auditors, proof verifiers) according to
its own `references/subagent-delegation.md`. The manager does not prescribe or observe that
split; a task packet supplies only project context and constraints. Sub-agent artifacts are
bound by hash in the upstream run manifest, so ingestion reads the run root and manifest
without re-reading intermediate sub-agent work.

## Run directory

Recommended location:

```text
runs/rigorous-open-math-research/RUN_ID/
```

Before dispatch, the manager may create only:

```text
run-manifest.json
task-packet-link.txt
```

The upstream skill owns every problem-level artifact it writes there.

If the upstream run occurs elsewhere, store an external path or resource identifier. Do not copy its standard artifacts merely to fit the project layout.

## Run manifest

Use `assets/run-manifest.template.json`.

Required fields:

```text
run_id
project_id
task_id
upstream_skill
upstream_skill_version_or_hash, if known
started_at and completed_at
run_root
upstream_status_verbatim
artifact pointers and hashes
source packet path and hash
model, tool, and environment metadata when actually available
manager_ingestion_state
missing or unavailable artifacts
notes
```

Do not invent unknown environment fields. Use `null` or an explicit unknown note.

## Ingestion procedure

### 1. Integrity and provenance

- confirm the run root or external resource exists;
- read the upstream top-line status and preserve it exactly;
- enumerate available upstream artifacts;
- record paths, sizes, hashes, and timestamps when possible;
- distinguish missing, inaccessible, and not-produced files.

### 2. Project indexing

Update:

- `index/runs.json`;
- `index/artifacts.json`;
- the related task packet record;
- the related open-problem record;
- the current checkpoint and budget log.

The artifact index should point to the original upstream location. A project summary may quote a very short finding, but it must link the full proof or audit rather than recreating it.

### 3. Knowledge extraction

Extract only items supported by exact upstream locations:

- rigorous intermediate theorems;
- exact reductions or constructions;
- reusable lemmas or estimates;
- counterexamples or obstruction mechanisms;
- limitations and remaining gaps;
- bibliographic corrections;
- reproducibility assets.

Use the tool-library promotion rules. Do not broaden assumptions or conclusions.

### 4. Portfolio update

Update project management fields such as:

```text
portfolio_state
last_run_id
next_action
blocked_by
follow_up_task_ids
literature_refresh_needed
```

Store the mathematical result status only in `upstream_status_verbatim` and linked upstream artifacts. Do not translate it into a manager-defined success label.

### 5. Stage narrative

A stage summary may say:

- which task was dispatched;
- the upstream status returned;
- which rigorous intermediate result or failure mechanism is now reusable;
- where proof and audit files live;
- what exact gap remains;
- how priorities changed.

It must not claim an underlying open problem solved unless the upstream artifacts support that statement under their own protocol.

## Ingestion failure cases

- **No run root:** record the dispatch and missing output; keep task state unresolved.
- **Status without artifacts:** preserve the status but mark it unverified for ingestion and do not promote knowledge.
- **Artifacts without status:** index them and request or derive no replacement label.
- **Conflicting versions:** preserve both, mark the preferred one unresolved, and do not merge content silently.
- **Moved files:** update paths only after verifying identity by hash or other evidence.
