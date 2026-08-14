# Example 2 — Program management followed by a solver delegation

## User request

```text
继续此前的离散几何研究项目。根据现有论文地图，选出最有杠杆的一个未解决子问题，整理所有相关来源和工具，然后至少投入八小时有效研究，尝试证明或反驳它。阶段结束后把结果并回项目。
```

## Correct skill behavior

1. Trigger `manage-math-research-program` in `PROGRAM_AND_DELEGATE` mode.
2. Resume from `state/RESUME.md`, `state/current.json`, indexes, and the latest checkpoint.
3. Treat eight hours as this stage's configured effective-time budget; do not make it a universal rule and do not fabricate elapsed time.
4. Refresh the literature cutoff and priority rationale at project level.
5. Select one problem from the existing portfolio without creating its theorem contract.
6. Build `agenda/task-packets/TASK_ID.md` containing the authoritative source, exact paper versions, analysis paths, tool leads, ambiguities, constraints, and run root.
7. Invoke:

```text
Use $rigorous-open-math-research on the concrete problem in
agenda/task-packets/TASK_ID.md.
Treat the packet as project context, independently rebuild and audit the exact theorem
contract, and recheck cited theorems against original sources. Write all upstream
artifacts under runs/rigorous-open-math-research/RUN_ID/. Return the upstream status
verbatim and artifact locations.
```

8. Do not prebuild `problem_contract.md`, `obligation_graph.md`, `approach_registry.md`, `research_ledger.md`, `candidate_proof.md`, or `audit_report.md`.
9. After the solver returns, register the run and artifact paths/hashes. Preserve its status label exactly.
10. Update the open-problem portfolio, tool library, failure patterns, budget log, maps, checkpoint, resume entry, and stage summary.
11. If a complete proof exists, link the upstream proof and audit documents. If not, preserve rigorous intermediate results, exact failure mechanisms, and remaining gaps without upgrading their status.
