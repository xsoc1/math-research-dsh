# Pipeline handoff record

Fill one record per stage transition. Keep it inside the run directory or the
project state directory; the manager records its path and hash in the project
index.

```text
handoff:          <A->B | B->C | C->done>
run_id:           <R-...>
task_packet_id:   <Q-...>
date:             <UTC timestamp>
from:             <manager | solver | formalizer>
to:               <solver | formalizer | verifier | knowledge base>
artifacts:        <paths + sha256 of each handed artifact>
status_labels:    <verbatim upstream status, e.g. CANDIDATE_COMPLETE_PROOF>
decisions:        <gate decisions: accepted / rejected / deferred, with reason>
next_actions:     <exact next steps>
```
