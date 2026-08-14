// DSH workflow template v2: per-packet solve + adversarial audit in parallel,
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
  ].join("\n"))
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
  ].join("\n"))
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
      ].join("\n"),
      agentOpts("verify", "verify: " + entry.title, "verify", entry)
    )
    return { title: entry.title, runRoot: entry.runRoot, verdict }
  })
}

return { attacked, verified }
