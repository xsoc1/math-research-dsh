# Closure gate

- Target ID: <target obligation ID>
- Target claim: <exact normalized statement>
- Shortest dependency chain: <accepted premise IDs -> target ID>
- First open load-bearing claim: <obligation ID + exact statement>
- Why it is load-bearing: <one sentence>
- Existing support: <artifact paths, theorem IDs, or none>
- Coordinator direct attempt: <artifact path + outcome>
- Cheapest falsification probe: <test + exact domain + outcome>
- Gate decision: <CLOSED | FALSIFIED | OPEN_EXACT_GAP | ESCALATE | REPAIR_CONTRACT>
- Spawn trigger: <decision that delegated work can change, or none>
- Next decision-changing action: <one bounded action>
- Root obligations: <OPEN | CLOSED>
- Completion manifest: <path=completion_manifest.json; sha256=64-hex, or none>
- Fresh package audit: <path=completion_audit.json; sha256=64-hex, or pending>
- Load-bearing gaps: <nonnegative integer or unknown>
- Fast-close decision: <NOT_READY | CONTINUE_REQUIRED | REPAIR | STOP>
- Frontier upgrade: <path=frontier_upgrade.json; sha256=64-hex, or none>
- Last updated: <timestamp>
