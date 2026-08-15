# Upstream changelog history

## Changelog (2026-08-14)

- Distilled the OpenProver method (arXiv:2607.09217, github.com/kripner/OpenProver)
  into stage B/C: Planner-Worker-Verifier solve loop with a mandatory compact
  `whiteboard.md` per run (current plan, route history with outcome markers,
  deferred ideas, open obligations, key-artifact index); independent parallel
  Workers that never see each other's or the Planner's reasoning traces;
  independent Verifier feedback on finished Worker outputs; repository items
  addressed by slug with a verified-items-only rule for Lean snippets; a Lean
  real-time verification loop (`lean_verify` / `lean_search` via LeanExplore /
  `lean_store` context accumulation); a formalization feedback loop that routes
  proof-layer flaws back to the solve-run lead; and interactive steering for
  human-in-the-loop runs. `validate_pipeline.py` hard-requires the whiteboard
  (fields + sections) for stage B runs started on or after 2026-08-14; new
  `tests/smoke_whiteboard.py` wired into CI.
- Cachebuster bumped to `0.1.0+codex.20260814120000` to propagate the protocol.

## Changelog (2026-08-13)

- Added `scripts/doctor.py`, an environment preflight: verifies the workflow
  plugin, the three dependency skills, the marketplace, and the `config.toml`
  enable entry; prints exact repair commands. Stage A runs it before dispatch
  (guards against the desktop app rewriting `config.toml` and dropping the
  plugin-enable entry).
- `validate_pipeline.py` now enforces numerical-evidence discipline: a gate
  status requires `candidate_proof.md` or `audit_report.md` in the run
  directory; numerical labels mixed with strong claims need a strict label or
  an explicit downgrade statement; `verification.json` verdict
  `FORMALLY_VERIFIED` requires `machine.build_passed == true` and zero
  sorry/axiom hits; `STATUS.md` cannot claim `FORMALLY_VERIFIED` without the
  verdict file. Fixed lean-manifest input-hash resolution (paths are relative
  to `lean-proof/` and may use Windows separators).
- Fork-sync specifics removed from this plugin; git sync now defers to the
  manage skill's generic remote-topology configuration.
- Cachebuster bumped to `0.1.0+codex.20260813054312` to propagate the gate.

- Stage B now starts with a mandatory B0 novelty preflight: openness check
  (genuinely open as of the research date), divergent novelty audit with
  `query -> result -> locator` provenance, snapshot-hash backfill into the
  manage skill's literature frontier, and a deterministic gate - every
  solve/disprove/construct task packet must carry a `## Novelty preflight`
  section (openness verdict + audit path or explicit skip + snapshot hash),
  enforced by `validate_pipeline.py`. A missing preflight is a hard FAIL at
  the A -> B boundary.
- Cachebuster bumped to `0.1.0+codex.20260813101438` to propagate the B0 gate.

- Interruption handoff and resume protocol: when a stage stops before
  completion, the interrupting agent writes
  `runs/<run_id>/handoff-interrupted-<ts>.md` from
  `assets/interruption-handoff.template.md` - run/packet IDs, interrupt
  reason, task state, completed/open obligations, every route tried with
  `[FAILED|BLOCKED|PARTIAL|SUCCEEDED]` outcome markers, exact next actions,
  and hashed artifact paths; the successor agent resumes from the handoff and
  must not re-run a FAILED route without a new recorded reason.
  `validate_pipeline.py` hard-fails handoffs missing required fields or
  sections. Added `tests/smoke_handoff.py` (+ good/bad fixtures) and wired it
  into CI.
- Cachebuster bumped to `0.1.0+codex.20260813144928` to propagate the handoff protocol.

## Changelog (2026-08-14, formalization decision gate)
- 修复静默跳过 Lean 验证: 声称完成状态 (已证/CANDIDATE_COMPLETE_PROOF) 的 run 必须在
  run-manifest 记录形式化决策 (formalization: requested | not_requested | skipped);
  requested 要求 formalization_manifest 指向存在文件 + lean-proof/verification.json
  干净机器裁决; skipped 要求非占位 formalization_reason 且重新验证义务保持开放;
  门禁机械强制 (validate_pipeline.py), 缺失决策即 FAIL.
- 任务包模板新增可选 Verify: yes|no|not-requested 字段 (manage skill).
- 新增 tests/smoke_formalization.py + 三个 fixtures (good/missing/requested).
## Changelog (2026-08-14, DSH adaptation)

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
