#!/usr/bin/env python3
"""Sync the DSH skill bundles from the parent Codex marketplace repository.

Copies the four plugin skill directories (plus the workflow and lean-verify
plugin-level scripts and assets) from the parent repository, re-applies the
DSH adaptation layer, regenerates the manage-skill MANIFEST.sha256, syncs the
upstream tests tree (smokes path-rewritten to the skills/ layout, full
fixtures), the canonical pipeline full-flow document, and writes
upstream.lock.json.

Usage:
    python scripts/sync-from-parent.py [--upstream PATH] [--check]

Options:
    --upstream PATH   local clone of xsoc1/rigorous-open-math-research.
                      Default: $DSH_HOME/_math-research-upstream/rigorous-open-math-research
                      (DSH_HOME defaults to ~/.dsh).
    --check           no writes: recompute the synced state in a temporary
                      directory and compare it with the current skills/ tree
                      and upstream.lock.json. Exit 1 when the parent has
                      changes the current sync state does not reflect.

The DSH layer is the only allowed divergence from upstream content:
   1. a DSH runtime notes block (with DSH execution patterns) inserted after
      each SKILL.md frontmatter;
   2. DSH adaptation entries appended to the upstream-disclosed
      references/changelog.md, with an inline-changelog fallback for older
      upstream revisions;
   3. the workflow SKILL.md doctor passages rewritten for
      scripts/dsh-doctor.py; the Codex scripts/doctor.py dropped;
   4. layer-owned additions: references/dsh-execution.md (rigorous + workflow)
      and assets/dsh-solve-audit-workflow.js (workflow).
Everything else is byte-identical (LF-normalized) to the parent.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SKILL_NAMES = (
    "rigorous-open-math-research",
    "manage-math-research-program",
    "math-research-workflow",
    "lean-verify",
)

# (upstream plugin dir -> local bundle dir)
BUNDLE_SOURCES = {
    "rigorous-open-math-research": "plugins/rigorous-open-math-research/skills/rigorous-open-math-research",
    "manage-math-research-program": "plugins/manage-math-research-program/skills/manage-math-research-program",
    "math-research-workflow": "plugins/math-research-workflow/skills/math-research-workflow",
    "lean-verify": "plugins/lean-verify/skills/lean-verify",
}

# plugin-level dirs merged into the corresponding bundle
EXTRA_SOURCES = {
    "math-research-workflow": ("assets", "scripts"),
    "lean-verify": ("assets", "scripts"),
}

# files excluded from a plugin-level copy
EXTRA_EXCLUDES = {"math-research-workflow/scripts/doctor.py"}

TEXT_SUFFIXES = frozenset(
    {".md", ".json", ".yaml", ".yml", ".txt", ".tex", ".lean", ".py", ".csv", ".svg", ".mmd"}
)

RUNTIME_NOTES_MARKER = "## DSH runtime notes (DSH adaptation)"
CHANGELOG_POINTER_MARKER = "Release history, method provenance, and source links live in"

CHANGELOG_POINTER = """## History

Release history, method provenance, and source links live in
`references/changelog.md`. Read it only when auditing provenance or preparing
a release.
"""

RUNTIME_NOTES = {
    "rigorous-open-math-research": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `rigorous-open-math-research`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`manage-math-research-program`, `math-research-workflow`, and `lean-verify` ship
beside this bundle under the same skill roots.

- Reference files under `references/` and `assets/` are read with the read tool
  using the `resourceBase` directory path reported by the skill load result.
- Bundled scripts (of the sibling skills) run with a local Python interpreter via
  the shell: `python <script> ...`, with `PYTHONUTF8=1` on Windows. Prefer writing
  a temporary .py file over PowerShell one-line `-c` calls.
- The DSH adaptation keeps every upstream file byte-identical except this block
  and the DSH changelog append; the synced upstream commit is recorded in the
  repository `upstream.lock.json`.

### DSH execution patterns (performance)

- Long computations (numerical scans, finite verifications, big derivations)
  run as background shell jobs (`run_in_background: true`), collected with
  job_output and cancelled with job_kill; never block a turn polling them.
- Adversarial audit / verifier roles run as fresh `subagent` (spawn provider:
  no conversation seed, artifact-only prompts), so they share no chain of
  thought with the solver; `subagent_fork` is for context-heavy continuation.
  Follow-ups go through send_message; the runtime reports completion.
- Fan-out across many packets uses the `workflow` tool with the template in
  the math-research-workflow bundle (assets/dsh-solve-audit-workflow.js).
- Multi-round objectives use the goal tools (create_goal / get_goal /
  update_goal).
- DSH truncates tool results (~8K chars, head 4096 + tail 1024): bundled
  scripts print verdicts last; for long outputs run them through the
  repository-level wrapper scripts/dsh_run.py, which pins the verdict and the
  FAIL lines outside the truncated middle and keeps the full log on disk.
- Full details: references/dsh-execution.md in this bundle. Optional external
  capabilities (vision for text-only models, document parsing to Markdown)
  and their invocation conventions: references/dsh-optional-capabilities.md.
""",
    "manage-math-research-program": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `manage-math-research-program`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`rigorous-open-math-research`, `math-research-workflow`, and `lean-verify` ship
beside this bundle under the same skill roots.

- `scripts/` (init_project.py, validate_project.py, sync_remotes.py), the
  `assets/` templates, and the blueprint-accepted-knowledge tools under
  `assets/blueprint-accepted-knowledge/tools/` live inside this bundle; run them
  with a local Python interpreter via the shell using the `resourceBase`
  directory path reported by the skill load result, with `PYTHONUTF8=1` on
  Windows. Prefer writing a temporary .py file over PowerShell one-line `-c`
  calls.
- `MANIFEST.sha256` is re-verified by the repository `scripts/validate_all.py`.
- The DSH adaptation keeps every upstream file byte-identical except this block
  and the DSH changelog append; the synced upstream commit is recorded in the
  repository `upstream.lock.json`.

### DSH execution patterns (performance)

- Long scans and bulk retrieval run as background shell jobs, collected with
  job_output; never busy-poll.
- Concrete runs are delegated with the `subagent` tool (fresh, independent) or
  `subagent_fork` (context-heavy continuation); batch fan-out uses the
  `workflow` tool (template in the math-research-workflow bundle).
- Long-running programs use the goal tools (create_goal / get_goal /
  update_goal).
- Bundled scripts print verdicts last; for long outputs use the repository
  wrapper scripts/dsh_run.py (verdict + FAIL lines at the head, verdict at
  the tail, full log on disk). Optional external capabilities (document
  parsing for the literature frontier, vision for scanned sources):
  references/dsh-optional-capabilities.md.
""",
    "math-research-workflow": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `math-research-workflow`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message
whose first line is `/skill-name` also loads it). The sibling skills ship beside
this bundle under the same skill roots.

- `scripts/validate_pipeline.py`, `scripts/checkpoint_resume.py`, and the
  `assets/` templates live inside this bundle; run them with a local Python
  interpreter via the shell using the `resourceBase` directory path reported by
  the skill load result, with `PYTHONUTF8=1` on Windows. Prefer writing a
  temporary .py file over PowerShell one-line `-c` calls.
- The DSH environment preflight is `scripts/dsh-doctor.py` in the
  `math-research-dsh` repository checkout (when installed by the repository
  `install.ps1`, the checkout lives at `$DSH_HOME/math-research-dsh`).
- The DSH adaptation keeps every upstream file byte-identical except this block,
  the DSH changelog append, and the doctor-related passages rewritten for DSH;
  the synced upstream commit is recorded in the repository `upstream.lock.json`.

### DSH execution patterns (performance)

- Stage dispatches use the DSH delegation tools: fresh `subagent` (spawn) for
  solver/audit/formalizer/verifier roles so audit and verify share no chain of
  thought with the solver; `subagent_fork` for continuation with full history.
- Batch packets fan out through the `workflow` tool with
  assets/dsh-solve-audit-workflow.js (solve + audit in parallel per packet,
  then verify only qualified results).
- `lake build` and long gate runs execute as background shell jobs, collected
  with job_output.
- Long outputs run through the repository wrapper scripts/dsh_run.py so the
  verdict and FAIL lines survive DSH result truncation (full log on disk).
- Full details: references/dsh-execution.md in this bundle.
""",
    "lean-verify": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `lean-verify`. In this
runtime, every reference written as `$skill-name` means: load the skill named
`skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`manage-math-research-program`, `math-research-workflow`, and
`rigorous-open-math-research` ship beside this bundle under the same skill roots.

- `scripts/verify_lean_project.py` and the `assets/` templates live inside this
  bundle; run them with a local Python interpreter via the shell using the
  `resourceBase` directory path reported by the skill load result, with
  `PYTHONUTF8=1` on Windows. The Lean toolchain (`lake` from Lean 4) must be
  available when a build is requested.
- The DSH adaptation keeps every upstream file byte-identical except this block
  and the DSH changelog append; the synced upstream commit is recorded in the
  repository `upstream.lock.json`.

### DSH execution patterns (performance)

- `lake build` and project scans run as background shell jobs, collected with
  job_output; do not block a turn on them.
- Verification runs as a fresh `subagent` (spawn) so the verifier shares no
  chain of thought with the formalizer.
- Long outputs go through the repository wrapper scripts/dsh_run.py so the
  verdict survives DSH result truncation; the full log stays on disk.
""",
}

DSH_CHANGELOGS = {
    "rigorous-open-math-research": """## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file (keeps DSH skill loads light); all upstream workflow content
  is byte-identical otherwise (see `upstream.lock.json`). This bundle is the
  DSH counterpart of the Codex plugin `rigorous-open-math-research` in the
  math-research marketplace repository
  (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Added references/dsh-execution.md (background jobs, spawn/fork subagent
  isolation, workflow fan-out, goal tools, prune-aware script output).
""",
    "manage-math-research-program": """## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file; all upstream content is byte-identical otherwise (see
  `upstream.lock.json`). This bundle is the DSH counterpart of the Codex
  plugin `manage-math-research-program` in the math-research marketplace
  repository (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Runtime notes extended with DSH execution patterns (background jobs,
  subagent delegation, workflow fan-out, goal tools, prune-aware output).
""",
    "lean-verify": """## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file; all upstream content is byte-identical otherwise (see
  `upstream.lock.json`). This bundle is the DSH counterpart of the Codex
  plugin `lean-verify` in the math-research marketplace repository
  (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Runtime notes extended with DSH execution patterns (background lake build,
  fresh-subagent verification, prune-aware output).
""",
    "math-research-workflow": """## Changelog (2026-08-14, DSH adaptation)

- DSH adaptation layer: this bundle now ships as a DeepSeek Harness skill.
  Added the DSH runtime notes block; the Codex environment preflight
  (`scripts/doctor.py`) is replaced by the repository-level `scripts/dsh-doctor.py`
  (DSH skill roots, Python interpreter, Lean toolchain); Stage A step 2 and the
  reference-file list were rewritten accordingly. Upstream content is otherwise
  byte-identical (see `upstream.lock.json`).
## Changelog (2026-08-14, DSH performance adaptation)

- Added references/dsh-execution.md and assets/dsh-solve-audit-workflow.js
  (parallel solve+audit per packet via the DSH workflow tool, verify stage for
  qualified results only).
""",
}

WORKFLOW_DOCTOR_STEP_OLD = """2. Run the environment preflight (`scripts/doctor.py`). On a hard `FAIL`,
   apply the printed repair command (usually `codex plugin add
   math-research-workflow@math-research`) before any dispatch; the desktop app
   may rewrite `config.toml` and drop plugin-enable entries between sessions.
"""

WORKFLOW_DOCTOR_STEP_NEW = """2. Run the DSH environment preflight (`scripts/dsh-doctor.py` in the
   math-research-dsh repository checkout, installed under
   `$DSH_HOME/math-research-dsh`). On a hard `FAIL`, apply the printed repair
   command before any dispatch. It verifies that all four skill bundles are
   mounted under the DSH skill roots (`$DSH_HOME/skills` or the project
   `.dsh/skills`), that a Python interpreter is available, and that the Lean
   toolchain exists when stage C is planned.
"""

WORKFLOW_REFERENCE_OLD = """- `scripts/doctor.py` -- environment preflight for the plugin, its dependency
  skills, the marketplace, and the `config.toml` enable entry.
"""

WORKFLOW_REFERENCE_NEW = """- Repository-level `scripts/dsh-doctor.py` -- DSH environment preflight: the
  four skill bundles under the DSH skill roots, a Python interpreter, and the
  Lean toolchain for stage C.
- `assets/dsh-solve-audit-workflow.js` -- DSH workflow-tool template: parallel
  solve + adversarial audit per packet, then a verify stage for qualified
  results.
"""

DSH_EXECUTION_MD = """# DSH execution playbook

How the math-research skills use DeepSeek Harness execution features for
throughput and context economy. This file is DSH-layer-owned (it is not synced
from the Codex parent).

## 1. Long computations run in background jobs

Anything that may exceed one turn (numerical scans, transfer-matrix or
finite-element sweeps, big exact-arithmetic checks, `lake build`) runs through
the shell tool with `run_in_background: true`. The call returns a job id
immediately; collect output with job_output (wait: true only when the next
step truly depends on the result) and stop obsolete jobs with job_kill. Never
busy-poll or sleep on a job.

## 2. Independent agents are fresh, continuations are forked

- Adversarial audit, verifier, and literature-audit roles run as `subagent`
  (spawn provider): the child starts from the prompt alone and sees none of
  the solver's conversation, which is exactly the isolation the upstream
  protocol requires (no shared chain of thought; only artifacts exchanged).
- `subagent_fork` seeds a child with this conversation: use it for
  context-heavy continuation (resuming a proof with full history), not for
  independence.
- Delegations run in the background by default and the runtime reports
  completion. Follow-up turns go through send_message; interrupt a stuck child
  with interrupt_agent; recall durable children with list_agents.
- Sub-agent return contract, graded by task type (distilled from
  dsh-multiagent-modes: https://github.com/y08lin4/dsh-multiagent-modes):
  aggregation/synthesis -> JSON; reading/analysis -> structured markdown;
  single verdicts -> 1-3 line conclusion + key basis + risks. Concretely:
  solve returns status + artifact paths/sha256 + open obligations; audit
  returns PASS or F-xxx one-liners + report path; verify returns the verdict
  summary + manifest path. Full reports always live in files; replies stay
  under ~20 lines.

## 3. Fan-out with the workflow tool

For many independent packets (batch solve/audit/formalize), use the `workflow`
tool with the template `assets/dsh-solve-audit-workflow.js` in the
math-research-workflow bundle: solve and audit run in parallel per packet,
then only qualified results enter the verify stage. The workflow script runs
in the harness with no filesystem or network access - the agents do the work.
For one or two delegations, plain subagents are cheaper than a workflow
script.

Template v2 extras:

- **Dependencies** (distilled from dsh-agent-teams:
  https://github.com/NanmiCoder/dsh-agent-teams): tasks may declare
  `deps: [titles]`; the template executes them wave by wave (topological
  layering, with a logged cycle fallback). Cross-task data flows through
  files under the run roots, never through the workflow script.
- **Roster** (distilled from the team-captain roster pattern:
  https://github.com/MoreChanger/dsh-agent-presets): pass role texts through
  `args.roles` (the orchestration agent reads them from
  assets/dsh-solve-audit-workflow.js defaults or a project role file); the
  template falls back to built-in prompts, so extending roles does not
  require editing the template.
- **Model tiering** (verified in this deployment: the workflow agent() hook
  accepts provider/model overrides): set `args.modelStrong` /
  `args.modelCheap`, or per-role `args.roles.<role>.model`. Planner,
  synthesizer, audit, and verify on the strong model; bulk research,
  retrieval, and candidate scanning on the cheap model. Roles default to the
  main agent's model when no tier is configured (distilled from
  dsh-deep-research: https://github.com/omdsh-dev/dsh-deep-research and
  dsh-multiagent-modes).

## 4. Long-running objectives use goal tools

A multi-round research objective (prove X, close a gap list) is tracked with
create_goal, read with get_goal, and updated with update_goal
(complete / blocked / edit). Do not re-derive the objective every round.

## 5. Output-pruning-aware scripts

DSH truncates tool results (default ~8K chars, head 4096 + tail 1024): the
middle of long output disappears. Consequences:

- Bundled scripts print their verdict near the END of stdout so it survives.
- For long outputs, run the script through the repository-level wrapper
  `scripts/dsh_run.py` (checkout at `$DSH_HOME/math-research-dsh`): it prints
  `VERDICT: exit=N | log: <path>` first, then the extracted FAIL/warn lines,
  then repeats the verdict last, and tees the complete output to the log file
  on disk for the read tool.
- Never depend on middle-of-output lines; re-run with dsh_run or read the log.

## 6. Context economy

- Load each skill once per session; read `references/` and `assets/` on demand
  through `resourceBase`, never bulk-load.
- Read project artifacts tail-first: latest handoff, then research_ledger.md /
  approach_registry.md from the end, then key artifacts. Long changelogs live
  outside the SKILL bodies in references/changelog.md for the same reason.
- Keep numerical tables in files, not in the conversation; cite paths and
  hashes instead of pasting rows.

## 7. Context audit

`scripts/context-audit.py` (repository checkout) estimates the per-request
injection cost: the AGENTS.md instruction chain (with the 65536-byte
truncation threshold flagged), skill catalog entries, skill bodies and
references, exact-duplicate paragraphs across files, and skill-name shadowing
across roots. Run it before long sessions and after adding skills; treat its
top consumers as pruning candidates. (Distilled from dsh-context-doctor:
https://github.com/Zhenyu98/dsh-context-doctor.)
"""

WORKFLOW_TEMPLATE_JS = """// DSH workflow template v2: per-packet solve + adversarial audit in parallel,
// formalization only for results that qualify, with declared dependencies,
// roster-injected roles, model tiering, and graded return formats.
//
// Manifest (workflow asset header):
//   name: dsh-solve-audit-workflow
//   version: 2
//   intent: per-task-packet solve + adversarial audit; verify for qualified
//           results only
//   inputs (args):
//     tasks: [{ title, problem, runRoot, deps?: [titles], model? }]
//     verify: true to enable the lean-verify stage
//     roles: optional { solve|audit|verify: { text?, model? } } roster
//     modelStrong / modelCheap: optional per-tier model names
//   outputs: { attacked: [...], verified: [...] }
//   provenance: math-research-dsh bundle assets/dsh-solve-audit-workflow.js;
//     distilled from dsh-deep-research (adaptive loops), dsh-agent-teams
//     (dependency declaration), dsh-multiagent-modes (graded returns,
//     tiering)
//   limits: concurrency is governed by the workflow engine; `deps` are
//     executed wave by wave; agents never see each other's conversations.
//
// Graded return formats (see references/dsh-execution.md):
//   solve  -> status label + artifact paths/sha256 + open obligations, one
//             line each, no narrative
//   audit  -> PASS or F-xxx findings one-liners + open obligations + report
//             path; full findings live in audit_report.md
//   verify -> verdict summary + run-manifest path + failure highlights;
//             the full verdict lives in verification.json
// Full reports always live in files; replies stay under ~20 lines.
//
// Usage: pass this file's body as the workflow tool's `script` parameter.

phase("solve-and-audit")

const STRONG = args.modelStrong
const CHEAP = args.modelCheap

function roleText(key, fallback) {
  const roles = args.roles || {}
  return (roles[key] && roles[key].text) || fallback
}

function agentOpts(phaseName, label, role, task) {
  const opts = { phase: phaseName, label: label }
  const roles = args.roles || {}
  let model
  if (roles[role] && roles[role].model) model = roles[role].model
  else if (task && task.model) model = task.model
  else if (role === "solve" || role === "audit" || role === "verify") model = STRONG
  else model = CHEAP
  if (model) opts.model = model
  return opts
}

function solvePrompt(task) {
  return roleText("solve", [
    "You are the solver agent for task: " + task.title,
    "",
    task.problem,
    "",
    "Load the rigorous-open-math-research skill with the skill tool and follow it.",
    "Work under run root: " + task.runRoot,
    "Write all standard artifacts there and return ONLY: the final status label",
    "(from the output protocol), the artifact paths with sha256, and the open",
    "obligations - one line per item, no narrative. Put every detail in the",
    "artifacts, never in your reply."
  ].join("\\n"))
}

function auditPrompt(task) {
  return roleText("audit", [
    "You are the adversarial audit agent, fully independent of the solver.",
    "You have NOT seen the solver's work or conversation; audit only the",
    "artifacts under: " + task.runRoot,
    "",
    "Load the rigorous-open-math-research skill with the skill tool and follow",
    "its Phase 8 verification protocol. Independently re-derive every",
    "obligation and attack the candidate proof. Write the complete findings",
    "into audit_report.md under the run root, then return ONLY: PASS or the",
    "F-xxx findings with exact locations (one line each), which obligations",
    "remain open, and the audit_report.md path with sha256. Keep the reply",
    "under 20 lines; the full report lives in the file."
  ].join("\\n"))
}

function computeWaves(tasks) {
  const placed = {}
  const waves = []
  let guard = 0
  const total = tasks.length
  while (Object.keys(placed).length < total) {
    guard++
    if (guard > total + 1) {
      const rest = tasks.filter(function (t) { return !placed[t.title] })
      rest.forEach(function (t) { placed[t.title] = true })
      waves.push(rest)
      break
    }
    const wave = tasks.filter(function (t) {
      return !placed[t.title] && (t.deps || []).every(function (d) { return placed[d] })
    })
    if (wave.length === 0) {
      const rest = tasks.filter(function (t) { return !placed[t.title] })
      log("warn: unresolvable dependency cycle; running together: " + rest.map(function (t) { return t.title }).join(", "))
      rest.forEach(function (t) { placed[t.title] = true })
      waves.push(rest)
      break
    }
    wave.forEach(function (t) { placed[t.title] = true })
    waves.push(wave)
  }
  return waves
}

const attacked = []
for (const wave of computeWaves(args.tasks)) {
  const out = await pipeline(wave, async (task) => {
    log("attacking: " + task.title)
    const [solve, audit] = await parallel([
      () => agent(solvePrompt(task), agentOpts("solve", "solve: " + task.title, "solve", task)),
      () => agent(auditPrompt(task), agentOpts("audit", "audit: " + task.title, "audit", task))
    ])
    return { title: task.title, runRoot: task.runRoot, solve, audit }
  })
  out.filter(Boolean).forEach(function (entry) { attacked.push(entry) })
}

function qualifies(entry) {
  const text = String(entry.solve || "")
  return /CANDIDATE_COMPLETE_PROOF|已证/.test(text)
}

let verified = []
if (args.verify) {
  phase("verify")
  verified = await pipeline(attacked.filter(qualifies), async (entry) => {
    log("verifying: " + entry.title)
    const verdict = await agent(
      [
        "You are the verifier agent for task: " + entry.title,
        "Load the lean-verify skill with the skill tool and follow it for the",
        "Lean project under: " + entry.runRoot,
        "Write the structured verdict to verification.json under the run root",
        "and return ONLY: the verdict summary line, the run-manifest path with",
        "sha256, and any failure highlights - keep the reply under 20 lines;",
        "the full verdict lives in the file."
      ].join("\\n"),
      agentOpts("verify", "verify: " + entry.title, "verify", entry)
    )
    return { title: entry.title, runRoot: entry.runRoot, verdict }
  })
}

return { attacked, verified }
"""

OPTIONAL_CAPABILITIES_MD = """# Optional external capabilities (DSH conventions)

Vendor-neutral catalog of how the math-research skills use optional external
capabilities on DSH. This file is DSH-layer-owned (not synced from the Codex
parent). All listed plugins exist in the open-source DSH ecosystem; they
install through the deployment's profile-bundle mechanism
(`dsh plugin --profile <name> add github:<owner>/<repo>`, then restart the
profile). Verify a bundle against THIS deployment before use: community
compatibility targets are pinned to the public DSH release, and a local
checkout may differ. In this deployment the mechanism exists (profile
`dsh.profile.bundles` layer stack, pnpm reconciliation); the CLI binary lives
in the harness checkout rather than on PATH.

## 1. Vision for text-only models

Plugins:

- dsh-vision-toolkit (https://github.com/Anionex/dsh-vision-toolkit): ten
  structured tools - intent-aware image Q&A, long-screenshot OCR,
  original-pixel grounding, UI restoration, pixel diff verification,
  Artifacts, Web cards.
- dsh-vision (https://github.com/william-jin-cmu/dsh-vision): a single
  `view_image` tool bridging any OpenAI-compatible VLM endpoint
  (baseURL + apiKey + model).

Conventions:

- Never trust a vision answer as evidence. Treat VLM output exactly like
  `RECALLED_UNVERIFIED` memory: useful for orientation, but it must be
  re-checked against the primary source before entering any obligation.
- For math figures and scanned formulas, ask for a verbatim transcription
  plus the coordinates of every region read (grounding), then verify the
  transcription against the rendered source.
- Record the vision service, model, and any key used (by name only, never the
  secret) in repro_manifest.md.

Cost: a free tier exists (Zhipu glm-4.6v-flash with an automatic fallback
chain) or any OpenAI-compatible endpoint (DashScope qwen3-vl, Volcano doubao,
local Ollama qwen3-vl). The DeepSeek official vision API was not open as of
2026-08 (official wording: soon).

## 2. Document parsing (PDF/images to Markdown)

Plugins:

- dsh-plugin-mineru (https://github.com/HuanLinOTO/dsh-plugin-mineru): MinerU
  document parsing - PDF/images/DOCX/PPTX/XLSX to structured Markdown/JSON
  with formula support; async job polling; output above the inline cap goes
  to a file for the read tool.
- dsh-paddle-ocr (https://github.com/omdsh-dev/dsh-paddle-ocr): OCR-only.

Conventions:

- Run the parser before Phase 0 reading for scanned or layout-heavy papers;
  record parser + version + parse method (auto/txt/ocr) in repro_manifest.md.
- Parser output is unverified input: citations, formulas, and statements
  extracted this way must be re-checked against the original PDF page before
  any proof use (upstream Phase 0 item 9).
- Prefer the file-output path for long documents; keep the conversation lean
  and cite the output path + hash instead of pasting the full Markdown.

Cost: a MinerU service endpoint (self-hosted or API) or its VLM engine
backend.

## 3. When NOT to use them

- Skip vision/parser services when the base model already accepts images
  (the harness read_image tool) or the PDF has a clean text layer.
- Never let a VLM or parser settle a mathematical claim; they transcribe,
  they do not prove.
"""

# DSH-layer-owned files added to bundles (relative path -> content)
LAYER_FILES = {
    "rigorous-open-math-research": {
        "references/dsh-execution.md": DSH_EXECUTION_MD,
        "references/dsh-optional-capabilities.md": OPTIONAL_CAPABILITIES_MD,
    },
    "math-research-workflow": {
        "references/dsh-execution.md": DSH_EXECUTION_MD,
        "assets/dsh-solve-audit-workflow.js": WORKFLOW_TEMPLATE_JS,
    },
    "manage-math-research-program": {
        "references/dsh-optional-capabilities.md": OPTIONAL_CAPABILITIES_MD,
    },
}


def rewrite_smoke_paths(text: str) -> str:
    """Rewrite upstream smoke-test bundle paths to the DSH layout.

    Upstream tests run against the Codex plugin layout
    (plugins/<plugin>/skills/<plugin>/...), while DSH bundles live under
    skills/<plugin>/... . The rewrites handle both one-line and multi-line
    path expressions; smoke_doctor.py is not synced (replaced by the DSH
    doctor smoke for scripts/dsh-doctor.py).
    """
    text = re.sub(
        r'"plugins"\s*/\s*"manage-math-research-program"\s*/\s*"skills"\s*/\s*"manage-math-research-program"',
        '"skills" / "manage-math-research-program"',
        text,
    )
    text = re.sub(
        r'"plugins"\s*/\s*"rigorous-open-math-research"',
        '"skills" / "rigorous-open-math-research"',
        text,
    )
    text = re.sub(
        r'"plugins"\s*/\s*"math-research-workflow"',
        '"skills" / "math-research-workflow"',
        text,
    )
    text = re.sub(
        r'"plugins"\s*/\s*"lean-verify"',
        '"skills" / "lean-verify"',
        text,
    )
    if "closure-first smoke passed" in text:
        text = text.replace(
            '\trigorous_skill = RIGOROUS / "skills" / "rigorous-open-math-research"',
            "\trigorous_skill = RIGOROUS",
        )
        text = text.replace(
            '\tworkflow_skill = WORKFLOW / "skills" / "math-research-workflow"',
            "\tworkflow_skill = WORKFLOW",
        )
        text = re.sub(
            r'\tfor plugin in \(RIGOROUS, WORKFLOW\):\n'
            r'\t\tmanifest = json\.loads\(\(plugin / "\.codex-plugin" / "plugin\.json"\)\.read_text\(encoding="utf-8"\)\)\n'
            r'\t\tif manifest\["version"\] != "(?P<version>\d+\.\d+\.\d+)":\n'
            r'\t\t\traise AssertionError\(f"\{manifest\[\'name\'\]\} version is not (?P=version)"\)',
            lambda match: (
                '\tpackage = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))\n'
                f'\tif package["version"] != "{match.group("version")}":\n'
                f'\t\traise AssertionError("DSH package version is not {match.group("version")}")'
            ),
            text,
        )
        text = re.sub(
            r'\texpected_versions = \{RIGOROUS: "\d+\.\d+\.\d+", WORKFLOW: "(?P<version>\d+\.\d+\.\d+)"\}\n'
            r'\tfor plugin, expected_version in expected_versions\.items\(\):\n'
            r'\t\tmanifest = json\.loads\(\(plugin / "\.codex-plugin" / "plugin\.json"\)\.read_text\(encoding="utf-8"\)\)\n'
            r'\t\tif manifest\["version"\] != expected_version:\n'
            r'\t\t\traise AssertionError\(\n'
            r'\t\t\t\tf"\{manifest\[\'name\'\]\} version is not \{expected_version\}"\n'
            r'\t\t\t\)',
            lambda match: (
                '\tpackage = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))\n'
                f'\tif package["version"] != "{match.group("version")}":\n'
                f'\t\traise AssertionError("DSH package version is not {match.group("version")}")'
            ),
            text,
        )
    if "checkpoint resume smoke passed" in text:
        text = text.replace(
            'WORKFLOW_SKILL = WORKFLOW / "skills" / "math-research-workflow"',
            "WORKFLOW_SKILL = WORKFLOW",
        )
    return text


def expected_tests(upstream: Path) -> dict[str, str]:
    """Expected DSH tests tree: upstream smokes (path-rewritten, minus the
    Codex doctor smoke) plus the full fixtures tree, LF-normalized."""
    out: dict[str, str] = {}
    tests_root = upstream / "tests"
    for p in sorted(tests_root.glob("smoke_*.py")):
        if p.name == "smoke_doctor.py":
            continue
        out[f"tests/{p.name}"] = rewrite_smoke_paths(read_norm(p))
    fixtures_root = tests_root / "fixtures"
    for p in sorted(fixtures_root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(fixtures_root).as_posix()
            out[f"tests/fixtures/{rel}"] = read_norm(p)
    return out


def sync_tests(upstream: Path) -> None:
    for rel, content in expected_tests(upstream).items():
        write_norm(REPO / rel, content)


def expected_docs(upstream: Path) -> dict[str, str]:
    source = upstream / "docs" / "pipeline-full-flow.md"
    return {"docs/pipeline-full-flow.md": read_norm(source)}


def sync_docs(upstream: Path) -> None:
    for rel, content in expected_docs(upstream).items():
        write_norm(REPO / rel, content)


def default_upstream() -> Path:
    dsh_home = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")
    return dsh_home / "_math-research-upstream" / "rigorous-open-math-research"


def normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def read_norm(path: Path) -> str:
    return normalize(path.read_bytes()).decode("utf-8")


def write_norm(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def sha256_norm(path: Path) -> str:
    return hashlib.sha256(normalize(path.read_bytes())).hexdigest()


def is_transient(path: Path) -> bool:
    """Execution artifacts (bytecode caches, dsh_run logs), not repo content."""
    return (
        "__pycache__" in path.parts
        or path.suffix == ".pyc"
        or ".dsh_run.log" in path.name
    )


def insert_after_frontmatter(text: str, block: str) -> str:
    """Insert block (plus a separating blank line) after the frontmatter close.

    Frontmatter: first line is '---' and a later '---' line closes it.
    Idempotent: no-op when the block's marker is already present.
    """
    marker = block.strip().splitlines()[0]
    if marker in text:
        return text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md does not open with frontmatter")
    close = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            close = idx
            break
    if close is None:
        raise ValueError("SKILL.md frontmatter never closes")
    out = lines[: close + 1]
    out.append("")
    out.extend(block.rstrip("\n").splitlines())
    rest = lines[close + 1 :]
    while rest and rest[0].strip() == "":
        rest.pop(0)
    out.append("")
    out.extend(rest)
    return "\n".join(out) + "\n"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise ValueError("replacement anchor not found")
    return text.replace(old, new, 1)


def split_changelog(text: str) -> tuple[str, str]:
    """Split at the first '## Changelog' heading; returns (body, changelog)."""
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("## Changelog"):
            return "\n".join(lines[:idx]).rstrip("\n") + "\n", "\n".join(lines[idx:]) + "\n"
    return text, ""


def apply_dsh_layer(bundle: Path, name: str) -> None:
    skill_md = bundle / "SKILL.md"
    text = read_norm(skill_md)
    text = insert_after_frontmatter(text, RUNTIME_NOTES[name])
    if name == "math-research-workflow":
        text = replace_once(text, WORKFLOW_DOCTOR_STEP_OLD, WORKFLOW_DOCTOR_STEP_NEW)
        text = replace_once(text, WORKFLOW_REFERENCE_OLD, WORKFLOW_REFERENCE_NEW)
    body, changelog = split_changelog(text)
    history_path = bundle / "references" / "changelog.md"
    if history_path.is_file():
        history = read_norm(history_path).rstrip() + "\n"
    elif changelog:
        history = "# Release history\n\n" + changelog.rstrip() + "\n"
    else:
        history = ""
    if changelog and CHANGELOG_POINTER_MARKER not in body:
        body = body.rstrip("\n") + "\n\n" + CHANGELOG_POINTER + "\n"
    if DSH_CHANGELOGS.get(name):
        history = history.rstrip() + "\n\n" + DSH_CHANGELOGS[name].rstrip() + "\n"
    if history:
        write_norm(history_path, history)
    write_norm(skill_md, body)
    for rel, content in LAYER_FILES.get(name, {}).items():
        write_norm(bundle / rel, content)


def normalize_tree(root: Path) -> None:
    """Rewrite text files with LF endings: upstream working trees checked out
    on Windows may carry CRLF, while this repository commits LF only."""
    for p in root.rglob("*"):
        if (
            p.is_file()
            and not is_transient(p)
            and p.suffix.lower() in TEXT_SUFFIXES
        ):
            p.write_bytes(normalize(p.read_bytes()))


def copy_bundles(upstream: Path, dest_root: Path) -> None:
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True)
    for name in SKILL_NAMES:
        src = upstream / BUNDLE_SOURCES[name]
        dst = dest_root / name
        shutil.copytree(src, dst)
        for extra in EXTRA_SOURCES.get(name, ()):
            extra_src = upstream / "plugins" / name / extra
            extra_dst = dst / extra
            if not extra_src.is_dir():
                raise FileNotFoundError(f"missing plugin-level dir: {extra_src}")
            shutil.copytree(extra_src, extra_dst, dirs_exist_ok=True)
            for rel in EXTRA_EXCLUDES:
                if rel.startswith(f"{name}/"):
                    victim = dst / rel.split("/", 1)[1]
                    if victim.exists():
                        victim.unlink()
        normalize_tree(dst)
        apply_dsh_layer(dst, name)


def regen_manifest(bundle: Path) -> None:
    # Sort by the POSIX-style relative path STRING: Path objects compare
    # case-insensitively on Windows (pathlib normcase) but case-sensitively
    # on POSIX, which would make the generated MANIFEST content differ
    # between platforms. Plain str comparison is code-point based everywhere.
    files = [
        p
        for p in bundle.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256" and not is_transient(p)
    ]
    entries = []
    for p in sorted(files, key=lambda path: path.relative_to(bundle).as_posix()):
        rel = "./" + p.relative_to(bundle).as_posix()
        entries.append(f"{sha256_norm(p)}  {rel}")
    write_norm(bundle / "MANIFEST.sha256", "\n".join(entries) + "\n")


def upstream_head(upstream: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cannot read upstream HEAD: {proc.stderr.strip()}")
    return proc.stdout.strip()


def build_lock(skills_root: Path, upstream_commit: str) -> dict:
    files = {}
    for p in sorted(skills_root.rglob("*")):
        if p.is_file() and not is_transient(p):
            files[p.relative_to(skills_root).as_posix()] = sha256_norm(p)
    return {"upstream_commit": upstream_commit, "files": files}


def current_state(skills_root: Path) -> dict:
    state = {}
    for p in sorted(skills_root.rglob("*")):
        if p.is_file() and not is_transient(p):
            state[p.relative_to(skills_root).as_posix()] = sha256_norm(p)
    return state


def main() -> int:
    args = sys.argv[1:]
    upstream_arg = None
    check = False
    it = iter(args)
    for arg in it:
        if arg == "--upstream":
            upstream_arg = next(it)
        elif arg == "--check":
            check = True
        else:
            print(f"unknown argument: {arg}", file=sys.stderr)
            return 2
    upstream = Path(upstream_arg).resolve() if upstream_arg else default_upstream()
    if not upstream.is_dir():
        print(f"upstream clone not found: {upstream}", file=sys.stderr)
        return 1
    if check:
        return run_check(upstream)
    commit = upstream_head(upstream)
    copy_bundles(upstream, REPO / "skills")
    regen_manifest(REPO / "skills" / "manage-math-research-program")
    sync_tests(upstream)
    sync_docs(upstream)
    lock = build_lock(REPO / "skills", commit)
    write_norm(
        REPO / "upstream.lock.json",
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
    )
    print(f"synced from upstream {commit}")
    print(f"locked {len(lock['files'])} files in upstream.lock.json")
    return 0


def run_check(upstream: Path) -> int:
    commit = upstream_head(upstream)
    lock_path = REPO / "upstream.lock.json"
    if not lock_path.is_file():
        print("FAIL: upstream.lock.json missing; run without --check first")
        return 1
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    problems = []
    if lock.get("upstream_commit") != commit:
        problems.append(f"upstream commit moved: {lock.get('upstream_commit')} -> {commit}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp) / "skills"
        copy_bundles(upstream, tmp_root)
        regen_manifest(tmp_root / "manage-math-research-program")
        expected = build_lock(tmp_root, commit)
        current = current_state(REPO / "skills")
        for rel in sorted(set(expected["files"]) | set(current)):
            exp = expected["files"].get(rel)
            cur = current.get(rel)
            if exp != cur:
                problems.append(f"drift in {rel}")
                print(f"  drift detail {rel}: expected={exp} current={cur}")
                exp_path = tmp_root / rel
                cur_path = REPO / "skills" / rel
                if exp_path.is_file() and cur_path.is_file():
                    exp_lines = normalize(exp_path.read_bytes()).decode("utf-8", "replace").splitlines()
                    cur_lines = normalize(cur_path.read_bytes()).decode("utf-8", "replace").splitlines()
                    if len(exp_lines) != len(cur_lines):
                        print(f"    line count: expected={len(exp_lines)} current={len(cur_lines)}")
                    for idx, (a, b) in enumerate(zip(exp_lines, cur_lines)):
                        if a != b:
                            print(f"    first diff at line {idx + 1}:")
                            print(f"      expected: {a[:160]!r}")
                            print(f"      current:  {b[:160]!r}")
                            break
        # tests tree parity: upstream smokes (path-rewritten) + fixtures must
        # match the repository copy exactly, so upstream test additions can
        # never be forgotten again
        for rel, expected_text in sorted(expected_tests(upstream).items()):
            cur_path = REPO / rel
            cur_text = read_norm(cur_path) if cur_path.is_file() else None
            if cur_text != expected_text:
                problems.append(f"drift in {rel}")
        for rel, expected_text in sorted(expected_docs(upstream).items()):
            cur_path = REPO / rel
            cur_text = read_norm(cur_path) if cur_path.is_file() else None
            if cur_text != expected_text:
                problems.append(f"drift in {rel}")
    if problems:
        print("FAIL: sync check found drift:")
        for line in problems:
            print("  " + line)
        return 1
    print(f"sync check clean (upstream {commit})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
