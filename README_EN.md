# math-research-dsh

[中文版: README.md](README.md)

DSH (DeepSeek Harness) adaptation of the `math-research` Codex plugin
marketplace: the four Codex plugins (rigorous-open-math-research /
manage-math-research-program / math-research-workflow / lean-verify) ship here
as native DSH skills with their scripts and assets bundled.

## Background and current status

- The upstream Codex marketplace repository can only be installed through the
  Codex packaging (plugin.json / openai.yaml / marketplace.json / cachebuster),
  which DSH cannot consume. This repository turns each plugin into a DSH skill
  bundle (directory + SKILL.md frontmatter) and keeps the content in sync with
  upstream.
- Status as of 2026-08-14: all four skills adapted; installed on this machine
  via `install.ps1` as junctions under `$DSH_HOME/skills`; the skills appear in
  DSH session catalogs immediately (the watcher follows the junctions);
  repository validation and the five smoke tests are green; GitHub Actions is
  wired up.

## Repository topology

```text
xsoc1/rigorous-open-math-research            Codex marketplace parent repo (public, content source)
  +-- fork: Zhongshan-Big-Jun/rigorous-open-math-research    organization fork (follows the parent)
xsoc1/math-research-dsh                     this repo (DSH adaptation, public)
  +-- one-way sync: scripts/sync-from-parent.py copies from the parent and replays the DSH layer
```

- This repository only consumes the parent read-only and never modifies it; the
  parent's own maintenance rules (validate_all, cachebuster, dual-repo push)
  are unaffected by this repository.
- When upstream content moves, re-run `sync-from-parent.py` here; the CI
  sync-check job compares against the parent on every push.
- This repository does not modify the DSH harness itself and is not tied to any
  agent preset; once installed under the user skill root (`$DSH_HOME/skills`),
  every standard/cordis session discovers the four skills automatically.

## Skill overview

| DSH skill | Role | Bundled tooling |
|---|---|---|
| `math-research-workflow` | Orchestration: manage -> solve -> verify pipeline, stage gates, handoff protocol | `scripts/validate_pipeline.py`, `assets/` templates |
| `manage-math-research-program` | Program management: project init, literature, tool library, task packets, accepted-knowledge pipeline | `scripts/{init_project,validate_project,sync_remotes}.py`, `assets/` templates, blueprint tools |
| `rigorous-open-math-research` | Solver layer: theorem contracts, route search, adversarial audit, calibrated reporting | `references/`, `assets/` |
| `lean-verify` | Lean 4 formalization audit: sorry/axiom scan, obligation audit, structured verdict | `scripts/verify_lean_project.py`, `assets/` templates |

## How DSH loads these skills

DSH discovers skills from the **user skill root** `$DSH_HOME/skills`
(`$DSH_HOME` defaults to `~/.dsh`), the **project skill roots**
`.dsh/skills` and `.agents/skills` of a session workspace, and preset
bundles. A skill is a directory containing a `SKILL.md` whose YAML
frontmatter declares `name` and `description`. Loading a skill with the
`skill` tool returns its content plus a `resourceBase` directory path; the
bundled `references/`, `assets/`, and `scripts/` are read or run through
that path. A user message whose first line is `/skill-name` loads that skill
directly (the DSH equivalent of the Codex `$skill-name` mention; every
`$skill-name` reference in the upstream content maps to this gesture).

## Install

```powershell
git clone https://github.com/xsoc1/math-research-dsh.git "$env:DSH_HOME\math-research-dsh"
powershell -ExecutionPolicy Bypass -File "$env:DSH_HOME\math-research-dsh\install.ps1"
```

`install.ps1` mounts the four bundles under `$DSH_HOME\skills` as directory
junctions, so `git pull` hot-updates every skill (the DSH skill watcher
follows the links). Re-run with `-Force` to replace an earlier plain-copy
install. For a single project only, copy or link the bundles into the
project's `.dsh\skills` instead.

Verify with:

```powershell
python "$env:DSH_HOME\math-research-dsh\scripts\dsh-doctor.py"
```

## Sync contract with the parent repository

Upstream content lives in the Codex marketplace repository
[xsoc1/rigorous-open-math-research](https://github.com/xsoc1/rigorous-open-math-research).
This repository keeps every upstream file byte-identical except a minimal,
machine-applied **DSH layer**:

1. a `## DSH runtime notes (DSH adaptation)` block after each `SKILL.md`
   frontmatter (the `$name` -> skill-tool mapping, `resourceBase` file access,
   how to run the bundled Python scripts, and the DSH execution patterns);
2. each `SKILL.md`'s changelog sections moved to
   `references/upstream-changelog.md` (keeps DSH skill loads light), replaced
   by a one-line pointer in the body;
3. the workflow `SKILL.md` doctor passages rewritten for the repository-level
   `scripts/dsh-doctor.py` (the Codex `scripts/doctor.py` is dropped);
4. layer-owned additions: `references/dsh-execution.md` (rigorous + workflow)
   and `assets/dsh-solve-audit-workflow.js` (workflow).

`scripts/sync-from-parent.py` copies the parent bundles, re-applies the layer,
regenerates the manage bundle `MANIFEST.sha256`, and writes
`upstream.lock.json` (parent commit + per-file hashes).

```powershell
# full sync (requires a clone of the parent repo)
git clone https://github.com/xsoc1/rigorous-open-math-research.git "$env:DSH_HOME\_math-research-upstream\rigorous-open-math-research"
python scripts\sync-from-parent.py --upstream "$env:DSH_HOME\_math-research-upstream\rigorous-open-math-research"

# drift check (exit 1 when the parent moved or skills/ was hand-edited)
python scripts\sync-from-parent.py --upstream <parent-clone> --check
```

## DSH performance adaptation

Targeted adaptations for how the DSH runtime actually works (details in each
bundle's `references/dsh-execution.md` and runtime notes):

| DSH mechanism | Adaptation |
|---|---|
| skill load puts the whole body in context | changelog history moved out of the SKILL.md bodies; references/assets read on demand through `resourceBase` |
| tool results truncated (~8K, head 4096 + tail 1024) | repository-level `scripts/dsh_run.py` wrapper: verdict + FAIL lines at the head, verdict repeated at the tail, full output on disk; scripts print verdicts last |
| background jobs (no timeout) | long computations (numerical scans, lake build) run with `run_in_background: true`, collected via job_output |
| spawn subagents start without the conversation | adversarial audit / verify roles use fresh `subagent` (zero chain-of-thought sharing by construction); `subagent_fork` is for context-heavy continuation |
| workflow tool | `assets/dsh-solve-audit-workflow.js` template: per-packet parallel solve + audit, verify stage for qualified results only |
| goal tools | multi-round objectives tracked with create_goal / get_goal / update_goal |
| Windows environment | PYTHONUTF8=1, full python path, avoid one-line -c (write a temp .py) |

## Validation

```powershell
python scripts\validate_all.py .      # structure, MANIFEST, lock, UTF-8/LF, py_compile, JSON/YAML
cd tests
python smoke_pipeline_gate.py         # pipeline gate fixtures
python smoke_handoff.py               # interruption handoff fixtures
python smoke_lean_verify.py           # lean-verify scanner (no Lean toolchain needed)
python smoke_sync_remotes.py          # multi-remote sync (local bare repos, no network)
python smoke_doctor.py                # dsh-doctor via simulated environments
python smoke_dsh_run.py               # prune-aware dsh_run wrapper
```

GitHub Actions runs all of the above plus the `--check` drift comparison
against the parent repository on every push.

## Repository layout

```text
skills/                         DSH skill bundles (synced from the parent + DSH layer)
  rigorous-open-math-research/
  manage-math-research-program/   (incl. MANIFEST.sha256)
  math-research-workflow/
  lean-verify/
  inside each bundle: references/upstream-changelog.md (relocated changelogs)
                      references/dsh-execution.md (rigorous/workflow, execution playbook)
                      assets/dsh-solve-audit-workflow.js (workflow, fan-out template)
scripts/
  sync-from-parent.py             parent sync + layer replay + lock
  validate_all.py                 repository validation
  dsh-doctor.py                   DSH environment preflight
  dsh_run.py                      prune-aware script wrapper (verdict head+tail, full log on disk)
tests/                            smoke tests + fixtures
upstream.lock.json                parent commit + per-file hashes
install.ps1                       junction install into $DSH_HOME/skills
```

## Maintenance rules

1. Run `python scripts/validate_all.py .` after every change.
2. Never hand-edit a synced file: change it upstream and re-run
   `sync-from-parent.py`, or extend the DSH layer inside that script.
3. Keep both READMEs in sync (README.md in Chinese + README_EN.md in English,
   cross-linked at the top).
4. Keep every new file UTF-8 without BOM, LF line endings, ASCII punctuation.
5. After pushing `origin`, update `upstream.lock.json` via a fresh sync if
   the parent moved.

License: MIT (same as the parent repository).
