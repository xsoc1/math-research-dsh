# Audit report - Lean formalization verification

Status label: <FORMALLY_VERIFIED | MACHINE_ACCEPTED_PENDING_AUDIT | CANDIDATE_VERIFIED | REPAIRABLE_GAP | FATAL_GAP | VERIFICATION_INCOMPLETE>

## 0. Scope, provenance, and method

- Verifier run: <run_id>
- Formalized artifact: <paths to .lean files, commit hash>
- Informal contract: <path to problem_contract.md; version/date>
- Obligation map: <path to obligation_map.md>
- Provenance chain: <parent runs, prior audits, repair lists, cited sources with stable links>
- Method: machine checks and independent audit are separate passes; every obligation was
  re-derived independently; every citation was checked against its source and version.
  Numerical checks are evidence only; every proof-level claim is argued analytically.

## 1. Verdict taxonomy and summary table

- PASS: the obligation is closed by the audited artifact.
- REPAIRABLE_GAP: conclusion correct and verified, but the written argument had a localized
  defect that the audit specifies and repairs.
- FATAL_GAP: the claim is false, unsupported, or unfaithful.
- NOT_VERIFIABLE: no source or reproducible computation could establish it.

| Obligation | Lean declaration | Verdict | Basis |
|---|---|---|---|
| O1 ... | theorem ... | ... | Section 2.x |
| ... | ... | ... | ... |

## 2. Detailed audit findings per obligation

### 2.1 O<n> - <claim>

- Statement fidelity: <FAITHFUL | MINOR_PARAPHRASE | UNFAITHFUL> - <notes>
- Re-derived argument: <steps, exact equations, dependency on earlier results>
- Machine check: <build result, sorry/axiom hits, #check probes>
- Verdict: <PASS | ...> - <basis>

## 3. Cross-cutting checks

### 3.1 Machine verification record
### 3.2 Statement fidelity across declarations
### 3.3 Citation and premise rechecks (each cited result must carry a stable link)
### 3.4 Non-circularity audit
### 3.5 Numeric evidence vs proof-level claims

## 4. Findings log

- F-<nnn>: <location> - <classification: arithmetic/logic/fidelity/citation/precision/
  process> - <description> - <repair applied or recommended>

## 5. Residual gaps and independent re-audit instructions

- <list every open obligation and the exact re-audit step required>

## 6. Confidence by axis

- Statement fidelity:
- Machine verification:
- Mathematical correctness:
- Completeness:
- Reproducibility: