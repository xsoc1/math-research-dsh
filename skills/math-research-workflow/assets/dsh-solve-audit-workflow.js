// DSH workflow template: per-packet solve + adversarial audit in parallel,
// then formalization only for results that qualify.
//
// The orchestration agent fills `args.tasks` from the current task packet:
//   [{ title, problem, runRoot }]
// and sets `args.verify = true` to enable the lean-verify stage. The spawned
// agents see no conversation context, so every prompt must be self-contained
// (paths, contracts, obligations, hashes). The workflow script itself has no
// filesystem or network access; agents do the work.
//
// Usage: pass this file's body as the workflow tool's `script` parameter.

phase("solve-and-audit")

function solvePrompt(task) {
  return [
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
  ].join("\n")
}

function auditPrompt(task) {
  return [
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
  ].join("\n")
}

const attacked = await pipeline(args.tasks, async (task) => {
  log("attacking: " + task.title)
  const [solve, audit] = await parallel([
    () => agent(solvePrompt(task), { phase: "solve", label: "solve: " + task.title }),
    () => agent(auditPrompt(task), { phase: "audit", label: "audit: " + task.title })
  ])
  return { title: task.title, runRoot: task.runRoot, solve, audit }
})

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
      ].join("\n"),
      { phase: "verify", label: "verify: " + entry.title }
    )
    return { title: entry.title, runRoot: entry.runRoot, verdict }
  })
}

return { attacked, verified }
