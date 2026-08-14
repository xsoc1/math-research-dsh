---
name: lean-verify
description: >-
  Verify a Lean 4 formalization of a mathematical theorem with a strict, reproducible audit:
  pin the Lean environment, check statement fidelity against the informal contract, run machine
  checks (lake build, sorry/admit/axiom scan), independently audit every proof obligation, and
  emit a structured verdict plus a hash-bound run manifest. Use when asked to verify, audit, or
  certify a Lean 4 proof, or to check that a formalization faithfully represents a stated theorem.
  中文触发: 适用于 Lean 4 形式化验证, 证明审计, 陈述保真检查, 义务级独立审计,
  sorry/axiom 泄漏检查, 可复现验证报告, 形式化-非形式化一致性核对.
---

## DSH runtime notes (DSH adaptation)

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
- The DSH adaptation keeps every upstream file byte-identical except this block;
  the synced upstream commit is recorded in the repository `upstream.lock.json`.

# Lean Verify

## 中文使用说明 (摘要)

本 Skill 用于对一个数学定理的 Lean 4 形式化做严格、可复现的验证. 它把验证拆成
机器可执行的部分 (环境固定, lake build, sorry/admit/axiom 扫描) 与需要独立判断的
部分 (陈述保真审计, 义务级独立审计, 引用核验), 最终产出结构化裁决与 hash 绑定的
运行清单.

- 触发场景: Lean 证明验证, 证明审计, 陈述保真检查, 义务级独立审计, 形式化一致性核对.
- 机器验证与独立审计分离: 机器检查证明 "Lean 接受", 独立审计检查 "形式化忠实于原问题".
- 输出必须按 "Output protocol" 的状态标签开头, 未闭合的义务不得标为完成.
- 本 Skill 是验证执行层; 长期项目管理与已接受知识入库由 `$manage-math-research-program` 负责.

## Purpose

Use this skill to certify a Lean 4 formalization of a mathematical statement, or to audit one.
The goal is a verdict that separates four distinct questions that are usually collapsed:

- Does the Lean code compile with a pinned environment and no leaked `sorry`/`admit`/`axiom`?
- Does the Lean statement faithfully represent the informal theorem contract (no silent
  quantifier, hypothesis, definition, or boundary-case change)?
- Is each proof obligation independently supported by a correct argument (not just accepted on
  the authority of the draft author)?
- Is the result reproducible from the recorded inputs, versions, and commands?

Never claim "formally verified" when only some of these hold. Machine acceptance proves the
formal statement, not its fidelity to the original problem, and not its novelty.

## Inputs

- A Lean 4 project directory (`lakefile.*`, `lean-toolchain`) and/or one or more `.lean` files.
- The informal theorem contract: original problem statement, target theorem, hypotheses,
  boundary cases, and completion criteria. When absent, the contract must be reconstructed and
  audited before verification.
- Optional: an obligation list (O1..On) mapping the theorem to its sub-claims; when absent,
  derive one and record the derivation.
- Optional: cited-source files or links for every external result used by the proof.

## Hard rules

1. Machine verification and independent audit are separate passes. A single pass may not
   certify both compilation and fidelity.
2. No `sorry`, `admit`, or undeclared `axiom` in the final artifact. Axioms outside an explicit
   whitelist are failures; each whitelisted axiom must be justified.
3. The Lean statement must be checked line by line against the informal contract. A proof of a
   different statement is not progress.
4. Cited literature must be real and linked. Never fabricate a paper, a citation, a theorem, a
   conclusion, or a compile result. Any claim about what a source proves must be checked against
   the actual source and version.
5. Numerical evidence is evidence, not proof. Label it and separate it from proof-level claims.
6. Record every input, version, command, and hash. A verification that cannot be replayed is
   incomplete.
7. Do not invent run counts, model settings, tool traces, or human interventions. Mark unknown
   fields as unknown.
8. At a resource boundary, report the strongest verified status and the exact remaining gaps.
   Only the completion label is withheld until verification actually closes.

## Workflow

### Phase 0 - Environment and input inventory

1. Record `lean --version`, `lake --version`, the `lean-toolchain` content, and the `lakefile`
   dependencies before any check.
2. Inventory every input: contract file, Lean files, imports, external sources, scripts, and
   their sha256 hashes. Record which inputs are untrusted or unverified.
3. When the run workspace is a git repository, record the commit hash and dirty files.
4. If `lean`/`lake` is not installed, record that machine verification cannot run and continue
   with the static checks and the independent audit; never pretend a build ran.

### Phase 1 - Contract and obligation mapping

1. Normalize the informal contract: objects, definitions, hypotheses, target conclusion,
   quantifiers, boundary and degenerate cases, permitted outcomes, completion criteria.
2. Audit the contract against its source; a proof of the wrong contract is not verification.
3. Map every obligation O1..On to the Lean declarations that discharge it (`theorem`,
   `lemma`, `def`, or `structure` instance). Record the mapping table; obligations without a
   mapping are open obligations.

### Phase 2 - Statement fidelity audit

For each Lean declaration mapped to an obligation:

1. Compare the Lean statement with the contract text: objects, hypotheses, quantifier order,
   constants and their dependencies, definitions, and boundary cases.
2. Flag silent strengthening, weakening, or redefinition. Two definitions that look alike but
   differ in a formula, notation, or hypothesis are different definitions; say so explicitly.
3. Check that imported names refer to the intended objects (same-name collisions across
   libraries).
4. Record the fidelity result per obligation: `FAITHFUL` | `MINOR_PARAPHRASE` | `UNFAITHFUL`.

### Phase 3 - Machine verification

1. Scan all `.lean` files for `sorry`, `admit`, and `axiom` outside the declared whitelist;
   report file and line for each hit.
2. Run the build (typically `lake build`) with the pinned environment; capture the full log and
   the exit code. `#check`/`#eval` probes for the mapped declarations may be added only in a
   scratch file that is excluded from the final artifact.
3. If the build fails, record the first error and its location; the artifact cannot be
   `FORMALLY_VERIFIED` until the build passes.
4. Record the machine results exactly as observed: exit code, error text, scan hits. Do not
   summarize away failures.

### Four gates and semantic review

Any edited declaration proposed for acceptance must pass four gates: (1) compile check,
(2) sorry/admit scan, (3) axiom-set check, and (4) a guard that protected statement
signatures did not change since the last approval. After the gates, a human semantic review
confirms the Lean statement still means what the source means; this last check cannot be
delegated to the same LLM that wrote the statement. Any change to an already-approved
statement requires a fresh statement re-audit and a new guard snapshot before proof work
resumes.

### Repair strategy (when the artifact is incomplete)

When the build fails or obligations remain open, repair instead of regenerating from scratch:

- **Statement freeze**: keep the statement signatures fixed while repairing proofs; a statement change is a new audit, not a repair.
- **Sorrifier decomposition**: replace the failing proof block with `sorry`, re-check that the remaining skeleton compiles, extract the failing block as a clean subproblem, and solve it recursively.
- **Error taxonomy first**: classify each failure (statement layer / proof layer / dependency layer / boundary-convention) before fixing; diagnose in the order 判定 -> 分类 -> 定位 -> 修正.
- Track every `sorry`; the final artifact must contain none.

### Phase 4 - Independent audit

Perform this pass as a separate role/pass from the formalizer. For each obligation:

1. Re-derive the argument independently; do not accept any step on the authority of the draft,
   a previous audit, or a repair list.
2. Check logical validity, theorem application, missing assumptions, unjustified jumps, and
   whether the Lean proof actually proves the Lean statement.
3. Check every external citation: the source exists, states the needed result, hypotheses match,
   and the result was not used under another name. Unverifiable citations are failures.
4. Check non-circularity: no obligation is discharged by a statement equivalent in strength to
   the target without a new proof.
5. Classify findings and return a verdict from the structured taxonomy (see Output protocol).
6. When a localized defect is found, specify the smallest failing claim and a concrete repair;
   after repair, re-run the affected checks from the changed point onward. The auditor cannot
   self-certify closure of its own repair.

7. Localize the **first** erroneous step (step index or smallest failing claim) for every
   finding and classify its error layer (statement / proof / dependency /
   boundary-convention); do not give vague comments.

### Phase 5 - Structured output and status label

Write three artifacts:

- `verification.json`: the structured verdict (schema in `assets/verification_output.schema.json`).
- `audit_report.md`: the full audit report (template in `assets/lean-audit-report.template.md`).
- `run-manifest.json`: input hashes, environment, commands, observed machine results, and status.

Status labels (first line of any report):

- `FORMALLY_VERIFIED` - build passes, no leaked sorry/axiom, statement fidelity audited, and an
  independent audit closes every obligation.
- `MACHINE_ACCEPTED_PENDING_AUDIT` - build passes with no sorry/axiom leak, but fidelity or
  independent audit is not complete.
- `CANDIDATE_VERIFIED` - independent audit passes but machine verification is unavailable or
  incomplete.
- `REPAIRABLE_GAP` - localized defect found and specified, conclusion unaffected.
- `FATAL_GAP` - a required obligation is false, unsupported, or unfaithful.
- `VERIFICATION_INCOMPLETE` - any required check is missing; report what remains.

Do not present `MACHINE_ACCEPTED_PENDING_AUDIT` as `FORMALLY_VERIFIED`. Do not bury a fatal gap
in a footnote.

## Output protocol

Structured verdict JSON (schema enforced by `assets/verification_output.schema.json`):

```json
{
  "verdict": "FORMALLY_VERIFIED | MACHINE_ACCEPTED_PENDING_AUDIT | CANDIDATE_VERIFIED | REPAIRABLE_GAP | FATAL_GAP | VERIFICATION_INCOMPLETE",
  "machine": {
    "lean_version": "...",
    "build_passed": true,
    "sorry_axiom_hits": []
  },
  "statement_fidelity": [
    {"obligation": "O1", "result": "FAITHFUL", "notes": "..."}
  ],
  "critical_errors": [{"location": "...", "issue": "..."}],
  "gaps": [{"location": "...", "issue": "..."}],
  "repair_hints": "...",
  "first_error": {"location": "...", "issue": "...", "category": "statement | proof | dependency | boundary-convention"}  // optional field
}
```

Strict rule: a finding list is empty only when the corresponding check found nothing. Any
non-complete verdict must include non-empty `repair_hints`. Aggregate without dropping issues.

## Artifacts

- `problem_contract.md` - normalized contract and completion criteria.
- `obligation_map.md` - obligations to Lean declarations, with fidelity results.
- `machine_check.log` - build log and scan output (raw).
- `verification.json` - structured verdict.
- `audit_report.md` - independent audit with provenance and findings log.
- `run-manifest.json` - hashes, environment, commands, status.

## Anti-patterns

- Claiming "verified" from a passing build alone.
- Trusting `#check` of the theorem name without reading the statement.
- Accepting a citation without checking it exists and states the needed result.
- Treating a Lean proof as settling fidelity or novelty.
- Reporting a repair as independently verified by the same pass that made it.
- Deleting failed checks or build errors from the record.

## Changelog (2026-08-12)

- 新增四道闸 + 人工语义复核 (Phase 3): 编译 / sorry 扫描 / axiom 集 / 陈述守护 + 人确认形式化陈述仍忠于来源; 已批准陈述的修改需重新过审与新 guard 快照.
- 新增修复策略 (Phase 3): 陈述冻结 (修证明不动陈述签名) + sorrifier 分解 (失败块 sorry 化保留骨架, 子问题递归) + 错误分类优先 (判定 -> 分类 -> 定位 -> 修正), 最终 sorry 清零.
- 新增首错定位与错误层分类 (Phase 4): 每个发现定位第一个错误步骤并分类 (陈述/证明/依赖/边界约定); 结构化输出新增可选 first_error 字段 (schema 同步).
- 方法来源: M2F (https://github.com/optsuite/M2F), MechMath sorrifier (https://github.com/MechMath/MechMath-v1), MMAT fl-prover (https://github.com/MechMath/MechMath-agent-team), FaithSieve (https://github.com/TropicalFatFish/anonymous-faithsieve), FormalRx (https://github.com/LARK-AI-Lab/formalrx, arXiv:2607.04655).
## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block; all upstream content is byte-identical
  otherwise (see `upstream.lock.json`). This bundle is the DSH counterpart of
  the Codex plugin `lean-verify` in the math-research marketplace repository
  (https://github.com/xsoc1/rigorous-open-math-research).
