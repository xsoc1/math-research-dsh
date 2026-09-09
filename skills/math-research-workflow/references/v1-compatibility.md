# Operate existing 1.x evidence

Read this only when interpreting or operating an existing sealed 1.x run. Its
immutable checkpoint, proof, source, audit and receipt bytes remain authoritative
for that historical record. Do not rewrite them to pretend they used 2.0.

The old helpers remain available:

- `scripts/recovery_status.py inspect` locates the latest sealed checkpoint.
- `scripts/recovery_status.py prepare-resume` prepares an idempotent receipt.
- `scripts/checkpoint_resume.py` verifies, seals and advances the historical
  protocol. See [its reference](quota-interruption-recovery.md) only if using it.
- `scripts/validate_pipeline.py --legacy-v1 --project <project>` explicitly
  checks old task-packet, whiteboard, handoff and formalization contracts.
- `scripts/formalization_handoff.py` verifies old cross-root proof handoffs.

These contracts and their historical regression tests are not requirements for
ordinary 2.0 research. The new continuity tool can use an existing current
progress page without making a new numbered ledger. Keep old checkpoint pointers
where useful. A migration or index rebuild changes no mathematical status.

The `quota` subcommand in the legacy recovery helper only interprets a supplied
old observation. It makes no account requests and is not called by 2.0. Frozen
benchmark runners retain their experimental accounting and seals; do not apply
those restrictions as a general research policy.
