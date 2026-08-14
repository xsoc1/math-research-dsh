# math-research-dsh

DSH (DeepSeek Harness) adaptation of the [math-research](https://github.com/xsoc1/rigorous-open-math-research)
Codex plugin marketplace. The four Codex plugins ship here as four native DSH
skills with their scripts and assets bundled:

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
   frontmatter (explains the `$name` -> skill-tool mapping, `resourceBase`
   file access, and how to run the bundled Python scripts);
2. a DSH changelog block in each `SKILL.md`;
3. the workflow `SKILL.md` doctor passages rewritten for the repository-level
   `scripts/dsh-doctor.py` (the Codex `scripts/doctor.py` is dropped).

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

## Validation

```powershell
python scripts\validate_all.py .      # structure, MANIFEST, lock, UTF-8/LF, py_compile, JSON/YAML
cd tests
python smoke_pipeline_gate.py         # pipeline gate fixtures
python smoke_handoff.py               # interruption handoff fixtures
python smoke_lean_verify.py           # lean-verify scanner (no Lean toolchain needed)
python smoke_sync_remotes.py          # multi-remote sync (local bare repos, no network)
python smoke_doctor.py                # dsh-doctor via simulated environments
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
scripts/
  sync-from-parent.py             parent sync + layer replay + lock
  validate_all.py                 repository validation
  dsh-doctor.py                   DSH environment preflight
tests/                            smoke tests + fixtures
upstream.lock.json                parent commit + per-file hashes
install.ps1                       junction install into $DSH_HOME/skills
```

## Maintenance rules

1. Run `python scripts/validate_all.py .` after every change.
2. Never hand-edit a synced file: change it upstream and re-run
   `sync-from-parent.py`, or extend the DSH layer inside that script.
3. Keep every new file UTF-8 without BOM, LF line endings, ASCII punctuation.
4. After pushing `origin`, update `upstream.lock.json` via a fresh sync if
   the parent moved.

License: MIT (same as the parent repository).
