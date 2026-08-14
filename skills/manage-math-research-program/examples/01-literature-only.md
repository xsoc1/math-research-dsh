# Example 1 — Pure literature and knowledge management

## User request

```text
建立一个长期项目，跟踪“高维组合几何中的单位距离问题”近十年的论文、后续引用、主要技术和开放问题。先不要尝试证明任何猜想。为关键论文生成 TeX 解析，建立论文地图和数学工具库，并设置每两周一次的恢复检查点。
```

## Correct skill behavior

1. Trigger `manage-math-research-program` in `PROGRAM_ONLY` mode.
2. Initialize a project repository with no solver run.
3. Configure the scope, search dates, source channels, and checkpoint cadence.
4. Search Google, Google Scholar, arXiv, MathSciNet or zbMATH when accessible, recording exact queries and limitations.
5. Register and deduplicate papers by DOI/arXiv/work fingerprint; preserve versions and corrections.
6. Produce version-specific TeX analyses for the most important papers.
7. Update `PAPER_MAP.md`, `FRONTIER.md`, the open-problem portfolio, and tool entries.
8. Write a checkpoint and `state/RESUME.md`.
9. Do not create a theorem contract, proof-obligation graph, route registry, candidate proof, or audit report.
10. Do not invoke `$rigorous-open-math-research`, because the user explicitly excluded proof attempts.

## Expected project-level output

```text
PROJECT.md
literature/search-log/...
literature/papers/P-.../record.json
literature/papers/P-.../analysis/structured-analysis.tex
literature/maps/PAPER_MAP.md
literature/maps/FRONTIER.md
agenda/problems/...
knowledge/tools/T-....md
state/checkpoints/...
state/RESUME.md
```
