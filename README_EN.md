# math-research-dsh

[中文版: README.md](README.md)

[![Awesome DSH Plugin](https://awesome-dsh-plugin.com/badge.svg)](https://awesome-dsh-plugin.com)

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
- Status as of 2026-08-16: all four skills adapted; installed on this machine
  via `install.ps1` as junctions under `$DSH_HOME/skills`; the skills appear in
  DSH session catalogs immediately (the watcher follows the junctions);
  repository validation and the five smoke tests are green; GitHub Actions is
  wired up; the repo root now ships as an official bundle skill pack (one
  command install + a submitted listing request).

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
| `manage-math-research-program` | Program management: project init, literature, tool library, task packets, accepted-knowledge pipeline; mandatory arXiv-style bilingual LaTeX proof delivery (`papers/`) after Lean verification | `scripts/{init_project,validate_project,sync_remotes}.py`, `assets/` templates, blueprint tools |
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

**Option A: one-command community install (official bundle plugin)**

```sh
dsh plugin --profile web add github:xsoc1/math-research-dsh
```

The repository root ships as an official bundle skill pack (`package.json`
declares `dsh.bundle.patch`; `index.mjs` registers the four skills as a custom
skill root through the official `FileSystemSkillProvider`, mounting only the
packaged directories and never re-scanning user/project skill roots). A `dsh
web` restart activates it; community markets such as
[dsh-market](https://github.com/dsh-market/dsh-market) can then find it. A
listing request has been submitted to
[awesome-dsh-plugin](https://awesome-dsh-plugin.com).

> Note: use Option A or Option B (junctions) - never both, or the same skills
> get registered twice.

**Option B: junction hot-update (development / local use)**

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
4. layer-owned additions: `references/dsh-execution.md` (rigorous + workflow),
   `assets/dsh-solve-audit-workflow.js` (workflow), and the official bundle
   packaging at the repo root (`package.json` / `index.mjs` /
   `cordis.patch.yml`) with its gate `scripts/dsh-check-bundle.py`.

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
| skill load puts the whole body in context | **progressive disclosure**: the rigorous body is now a 168-line driver (~2.7K tokens, was ~11K) + 8 phase reference files read on demand through `resourceBase`; changelog history also moved out of the body |
| tool results truncated (~8K, head 4096 + tail 1024) | repository-level `scripts/dsh_run.py` wrapper: verdict + FAIL lines at the head, verdict repeated at the tail, full output on disk; scripts print verdicts last |
| background jobs (no timeout) | long computations (numerical scans, lake build) run with `run_in_background: true`, collected via job_output |
| spawn subagents start without the conversation | adversarial audit / verify roles use fresh `subagent` (zero chain-of-thought sharing by construction); `subagent_fork` is for context-heavy continuation; **sub-agent return contract**: full reports to files, replies carry only verdict + paths + hashes |
| workflow tool | `assets/dsh-solve-audit-workflow.js` template: per-packet parallel solve + audit, verify stage for qualified results only |
| goal tools | multi-round objectives tracked with create_goal / get_goal / update_goal |
| Windows environment | PYTHONUTF8=1, full python path, avoid one-line -c (write a temp .py) |

## Distilled community methods (2026-08-14)

Methods absorbed from the open-source DSH ecosystem into this plugin
(incremental additions only, existing content untouched):

| Source | Distilled method | Landed in |
|---|---|---|
| [dsh-deep-research](https://github.com/omdsh-dev/dsh-deep-research) | answer-space + acceptance criteria before search; coverage dimensions + coverage_gaps recon; marginal information gain stop rule + evidence tri-state confirmed/uncertain/gaps | rigorous phase-01/23/45/12 |
| [dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) | declared task dependencies + wave execution (topological layering, cycle fallback) | workflow template v2 |
| [dsh-multiagent-modes](https://github.com/y08lin4/dsh-multiagent-modes) | graded return formats (aggregation→JSON / reading→structured md / single verdict→1-3 line conclusion + basis + risks); model tiering | dsh-execution.md + template v2 |
| [dsh-agent-presets captain mode](https://github.com/MoreChanger/dsh-agent-presets) | role roster as data (args.roles injection; extend roles without editing the template) | workflow template v2 |
| [dsh_workflow](https://github.com/icetomoyo/dsh_workflow) | workflow-as-asset manifest header (intent/inputs/provenance/limits) | workflow template v2 |
| [dsh-context-doctor](https://github.com/Zhenyu98/dsh-context-doctor) | context injection audit: 64KB instruction-chain truncation, skill sizes, duplicate paragraphs, name shadowing | `scripts/context-audit.py` |
| [dsh-vision](https://github.com/william-jin-cmu/dsh-vision) + [dsh-vision-toolkit](https://github.com/Anionex/dsh-vision-toolkit) | vision invocation conventions (VLM output = unverified input, re-check rule, free tier / local endpoints) | `references/dsh-optional-capabilities.md` (rigorous + manage) |
| [dsh-plugin-mineru](https://github.com/HuanLinOTO/dsh-plugin-mineru) + [dsh-paddle-ocr](https://github.com/omdsh-dev/dsh-paddle-ocr) | document-parsing conventions (PDF to structured Markdown, long-output file references) | same + upstream phase-01 item 9 |
| watching: [dsh-automation](https://github.com/titanwings/dsh-automation) (scheduled tasks) | integrate when a real need appears | — |

### Round 2 (2026-08-16, four directions)

| Direction | Source | Distilled method | Landed in |
|---|---|---|---|
| search / status | [modsearch](https://github.com/liustack/modsearch) | retrieval output contract: status tri-state (ok/degraded/unavailable) + uncertainty-vs-warnings split + engine attempt order; never invent relevance scores | rigorous phase-23 + manage §3 |
| search / status | [argo](https://github.com/taxueseek/argo) | target-problem status confirmation (fetch_required, fetch-status quartet, layered confirmation, corroboration ordering, gap hints, cross-session backfill) | rigorous phase-23/01 + workflow B0 |
| search / status | [dsh-zotero](https://github.com/Vncntvx/dsh-zotero) | local read-literature first: bounded evidence fragments (budget caps) + section-name/record-ID citation | rigorous phase-23 + manage §3 |
| search / status | [dsh-kb-sieve](https://github.com/omdsh-dev/dsh-kb-sieve) | deterministic retrieval loop + OOV gate + same-input-same-output | rigorous phase-23 semantic retrieval |
| search / status | [dsh-web-search-pro](https://github.com/anweat/dsh-web-search-pro) / [dsh-exa-mcp](https://github.com/MicroHEROX/dsh-exa-mcp) | search-log key reuse against re-tracing; semantic recall + full-text fetch pairs | manage §3 / rigorous phase-23 |
| multi-agent | [dsh-suite plugin-team-board](https://github.com/whyihaveyou/dsh-suite/tree/main/packages/plugins/plugin-team-board) | obligation claim ownership (claim before work, single owner, no duplicate proofs) | workflow Stage B |
| multi-agent | [dsh-proof](https://github.com/EvilIrving/dsh-proof) | gap re-injection hard rule (every non-pass review output consumed by a revision round; silent drop = gate failure) | workflow Stage B |
| multi-agent | [dsh-agent-team-gui](https://github.com/toolclub/dsh-agent-team-gui) | parallel member failure aggregation (no first-fail short-circuit) | workflow Efficiency rules |
| multi-agent | [dsh-trajectory-governance](https://github.com/dfycaly98931680/dsh-trajectory-governance) | loop detection (re-attempt without a new mechanism is blocked) | workflow + rigorous phase-45 |
| Lean | [forge-gates](https://github.com/jinguanghai/deepseek-harness-forge-plugins) | single structured judgment gate protocol (proved branch / localized counter-evidence branch; no free-text parsing as evidence) | lean-verify Phase 3 |
| Lean | [jacobian](https://github.com/morluto/jacobian) | lean.check atomization: pinned env + request-scoped temp dir + typed diagnostics, no session, no retained source | lean-verify Phase 3 |
| Lean | [dsh-rigorquant](https://github.com/linxichen/dsh-rigorquant) | dual-wire ground truth + counterexample-only adversary + Lean-before-implementation escalation + same-gap three-round convergence | rigorous phase-78 + workflow Stage C + lean-verify |
| Lean | [Vibe-Mathematics](https://github.com/ChongCyrus/Vibe-Mathematics) | falsification-first verdict (a verified counterexample vetoes; uncertain obligations never pass) | lean-verify Phase 4/5 |
| methodology | [Aegis](https://github.com/GanyuanRan/Aegis) | completion claim = fresh evidence + covered scope + residual risk | rigorous phase-78/12 |
| methodology | [dsh-science](https://github.com/biociao/dsh-science) | route hypothesis state machine + forward-only; artifact provenance fields (run/inputs/env/hash + append-only notes) | rigorous phase-45 + manage §5 |
| methodology | [dsh-scholar](https://github.com/lzszq/dsh-scholar) | evidence boundary: uncontrolled outputs (chat/stdout) never become formal evidence; frozen env for controlled runs | manage 8b item 8 |
| methodology | [dsh-design-skills](https://github.com/zhaiyateng/dsh-design-skills) / [dsh-ops-kit](https://github.com/LeslieWylie/dsh-ops-kit) | contract forbidden-moves list; evidence-integrity triple (prechecks/inventory/integrity) | rigorous phase-01 + manage 8b |

License note: methods only, own wording, no text copied; dsh-multiagent-modes is
CC BY-SA 4.0, so any future verbatim reuse must be open-sourced alike.

## Validation

```powershell
python scripts\validate_all.py .      # structure, MANIFEST, lock, UTF-8/LF, py_compile, JSON/YAML
python scripts\dsh-check-bundle.py    # official bundle gate (package.json / patch / index.mjs / skills)
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
package.json                      official bundle declaration (dsh.bundle.patch / marketplace info)
index.mjs                         bundle entry: registers skills/ via FileSystemSkillProvider
cordis.patch.yml                  layer-stack insert row (id = index.mjs name, name = package name)
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
  dsh-check-bundle.py             official bundle packaging gate
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
5. Bump `package.json` `version` whenever content (skill bodies / scripts)
   changes, so markets can detect updates.
6. After pushing `origin`, update `upstream.lock.json` via a fresh sync if
   the parent moved.

License: MIT (same as the parent repository).
