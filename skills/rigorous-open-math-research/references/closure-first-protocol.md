# Closure-first protocol

Use this protocol by default for a single theorem, counterexample, construction,
or sharply scoped audit under a finite budget. Its purpose is to spend the
first research calls on the earliest claim that can decide the target, rather
than on a broad portfolio, repeated context reconstruction, or polished
partial-result packages.

Skip it only when the user explicitly requests a broad survey or when the task
packet already supplies several independent, hash-bound obligations that must
run concurrently. Record the skip reason.

## 1. Live minimum

Start with four live records only:

- the exact `problem_contract.md`;
- the shortest dependency chain from accepted premises to the target in
  `obligation_graph.md`;
- a chronological `research_ledger.md`;
- `closure_gate.md`, using `assets/closure-gate.template.md`.

Do not eagerly create empty or duplicated versions of every final artifact.
Materialize the approach registry, counterexample log, candidate proof, audit
report, reproducibility package, and other default artifacts when they acquire
content or a stopping/handoff boundary requires them. A final required artifact
may be an explicit `not applicable` record, but it may not be silently absent.

## 2. Closure preflight

Before generating a route portfolio or spawning research sub-agents:

1. Normalize the target and write its shortest known implication chain.
2. Select the **first open load-bearing claim**: the earliest unresolved node
   on that chain whose failure blocks every downstream step.
3. Run one coordinator-owned direct attempt on that exact claim. Prefer an
   existing theorem, a direct calculation, a canonical representation, or the
   smallest meaningful special case.
4. Run the cheapest decisive falsification probe: audit quantifiers and
   dependencies, test boundary/degenerate cases, enumerate exact small objects,
   or check an exact source theorem. Numerical survival is evidence only.
5. Record one gate decision:
   - `CLOSED`: the claim is proved or refuted with an auditable artifact;
   - `FALSIFIED`: the proposed claim or route failed, with an exact witness;
   - `OPEN_EXACT_GAP`: the direct attempt exposed a strictly smaller named gap;
   - `ESCALATE`: independent work can now discriminate between named live
     mechanisms;
   - `REPAIR_CONTRACT`: the statement or accepted dependencies are not yet
     well-defined.

A graceful partial theorem does not count as closure when the target still
depends on an unproved theorem-strength claim. Keep the partial result, but
return the gate to the first open load-bearing node.

## 3. Spawn gate

Sub-agent work is justified only when the packet states all of:

- the exact claim and its obligation ID;
- the coordinator's direct attempt or why no direct attempt is admissible;
- the cheapest falsification result;
- the decision that the return can change;
- success, failure, and budget-stop conditions;
- a minimal context slice by path and hash.

Use the smallest batch that can distinguish the live hypotheses. Ordinarily
this is one obligation prover and, when useful, one independent falsifier. A
larger first wave requires several genuinely independent obligations or
mechanisms plus a recorded budget reason. Difficulty alone is not a spawn
trigger.

## 4. Delta gate for continuation

Every worker round must change at least one durable state:

- close or falsify an obligation;
- expose a strictly smaller exact gap;
- eliminate a route by a verified witness;
- add a reusable exact lemma, certificate, or source theorem;
- justify a named escalation decision.

If a round returns only exposition, restates the target, or reproduces an
existing partial bound, record zero gain and do not launch a near-duplicate
round. Reopen only with a new mechanism or new evidence. Report the round's
`decision_delta` in the subtask return.

## 5. Audit placement

- Audit a new load-bearing claim before downstream work depends on it.
- While the target remains open, prefer a claim-local verifier or falsifier to
  a full-package reviewer.
- Run a global package audit when a completion claim is proposed, at a
  stopping/handoff boundary, or before canonical integration.
- Audit the strongest partial package once at the boundary; do not repeatedly
  re-audit unchanged context.

## 6. Completion certificate and fast close

When one candidate proof appears to close every root obligation, stop route
generation and enter the completion-certificate gate:

1. Write `completion_manifest.json` from
   `assets/completion-manifest.template.json`. It freezes the exact contract,
   canonical structured `obligation_graph.json`, candidate proof, cited
   dependencies or exact checks, every root ID/status/proof anchor, the candidate
   author, timestamp, and hashes. The root array must exactly equal the canonical
   graph's root array, and every proof anchor must exist in the frozen proof.
2. Run exactly one fresh independent package audit per frozen manifest. The
   reviewer writes `completion_audit.json` from
   `assets/completion-audit.template.json`;
   its reviewer must differ from the candidate author, and it binds the frozen
   manifest hash, verdict, gap array, and post-freeze review timestamp. A
   non-`PASS` audit ends that frozen manifest; after repair, freeze a new manifest
   and obtain its one audit. Higher-assurance or formal verification belongs to
   the pre-contracted Stage C, not another Stage B package audit.
3. Hash-bind the completion manifest and completion audit in `closure_gate.md`.
   The gate's root status and gap count are summaries of those structured files,
   not self-attested substitutes for them.
4. If the audit is `PASS`, every root obligation is closed, and load-bearing gaps
   equal zero, set `Fast-close decision: STOP`. End solver, Worker, route, and bonus
   calls. Produce the required boundary records without purchasing new research
   calls solely to expand prose or duplicate the proof.
5. If the audit is non-`PASS`, route only its exact gaps. Reopen a broad portfolio
   only when the failure is structural and the closure gate records the decision
   that new mechanisms can change.

After a certified `STOP`, keep `Fast-close decision: STOP`. A single post-close
frontier call is allowed only through a separate hash-bound `frontier_upgrade.json`
created from `assets/frontier-upgrade.template.json`. It must bind the certified
manifest and audit, use `sequence: 1`, cite a durable user request or named
pre-existing project frontier by path, hash, and locator, and set a positive
integer budget plus an exact stop condition. A base manifest/audit pair may appear
in only one such record. Never replace STOP with a looser decision. The certified
root result remains frozen and reportable even if the upgrade fails.

The workflow's deterministic pipeline gate validates every fast-close certificate
created after the protocol cutover. A `CLOSED` research claim is not a certified
fast close until the independent audit and hash bindings pass.

## 7. Integration

- Phase 4 opens a diverse portfolio only after the closure gate says
  `ESCALATE`.
- The cost ladder treats multi-agent fan-out as an earned escalation, not a
  default response to a hard problem.
- The coordinator owns `closure_gate.md`; workers return claim-local artifacts
  and `decision_delta` only.
- The whiteboard carries the first open claim, current gate decision, and next
  decision-changing action.
