# Performance alert

- Run ID:
- Variant:
- Problem class:
- Date:
- Alert level: INFO | WARN | ALERT
- Baseline ID:

## Changed metrics

| Metric | Run | Baseline | Delta |
| --- | ---: | ---: | ---: |
| steps | | | |
| tool_calls | | | |
| uncached_input_tokens | | | |
| cache_read_tokens | | | |
| output_tokens | | | |
| wall_ms | | | |
| artifact_count | | | |
| reused_item_count | | | |
| duplicate_work_count | | | |

## Output/artifact assessment

- Did mathematical output improve, stay similar, or degrade?
- Did documentation/artifact completeness improve, stay similar, or degrade?
- Is the change plausibly explained by problem difficulty or class?

## Candidate interpretation

(Describe what may have caused the change, without claiming certainty.)

## Next checks

- [ ] Repeat the same variant in the same problem class.
- [ ] Repeat on a different problem class with a comparable baseline.
- [ ] Inspect `reuse_summary.md` for duplicate work or avoided work.
- [ ] Re-run after any intended protocol/config change.
