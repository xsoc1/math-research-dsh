# DSH execution playbook

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
- Sub-agent return contract: children write full reports to files under the
  run root and return only the status label + artifact paths + hashes (the
  workflow template prompts encode this contract). The parent conversation
  receives tens of lines, never full audit reports.

## 3. Fan-out with the workflow tool

For many independent packets (batch solve/audit/formalize), use the `workflow`
tool with the template `assets/dsh-solve-audit-workflow.js` in the
math-research-workflow bundle: solve and audit run in parallel per packet,
then only qualified results enter the verify stage. The workflow script runs
in the harness with no filesystem or network access - the agents do the work.
For one or two delegations, plain subagents are cheaper than a workflow
script.

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
  approach_registry.md from the end, then key artifacts. Long changelogs were
  moved out of the SKILL bodies into references/upstream-changelog.md for the
  same reason.
- Keep numerical tables in files, not in the conversation; cite paths and
  hashes instead of pasting rows.
