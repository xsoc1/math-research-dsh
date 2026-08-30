# Cross-root formalization handoff

Use this protocol when Stage B runs in a self-contained nested logical project
but its Tier 0 Lean scaffold must be registered in a different Stage C project.
It closes the identity gap between two byte-identical copies without weakening
the scope boundary introduced in v1.11.

## Supported transition

Version 1 supports only:

```text
formalization=scaffold + copy_mode=exact
```

The source and destination Lean artifacts must have the same SHA-256. This is
an ingestion receipt for a Tier 0 scaffold, not a verification verdict. It must
not produce `FORMALLY_VERIFIED` or imply that any `sorry` has been discharged.

Full `formalization=requested` packages are intentionally unsupported because
they require additional bindings for verification.json, the Lean run manifest,
the build environment, and independent fidelity audit.

## Seal

Copy the already registered source scaffold into the destination Lean project,
update at least one destination index, then run:

```text
python scripts/formalization_handoff.py seal \
  --project <physical-repository-root> \
  --handoff-id FH-<stable-id> \
  --source-root <relative-source-logical-root> \
  --source-manifest <path-within-source-root> \
  --source-proof <path-within-source-root> \
  --destination-root <relative-destination-logical-root> \
  --destination-artifact <path-within-destination-root> \
  --registration "<path-within-destination>::<durable-anchor>" \
  --output research/formalization-handoffs/FH-<stable-id>.json
```

`--registration` is repeatable. The sealer stores both the index hash at seal
time and a required anchor. Later append-only index updates may change the hash,
but removing the anchor invalidates the handoff.

The sealer verifies before writing and refuses to overwrite an existing output.
It binds:

- source and destination logical roots plus their project markers and IDs;
- source run manifest, run ID, formalization status, proof, and scaffold;
- destination scaffold and durable registration anchors;
- the physical repository HEAD when available.

All paths are relative and confined to their declared roots. Nested git roots,
absolute paths, path escape, missing manifest artifact entries, hash mismatch,
and a missing registration anchor are hard failures.

## Verify before consumption

Before Stage C consumes or edits the destination scaffold, run:

```text
python scripts/formalization_handoff.py verify \
  --project <physical-repository-root> \
  --handoff research/formalization-handoffs/FH-<stable-id>.json
```

Only `READY` permits consumption. Any failure means the copy, source package,
logical project identity, or destination registration has drifted. Reconcile
deterministically and seal a new handoff ID; never mutate the existing receipt.

## Record consumption

Immediately after `READY` and before changing the destination scaffold, record
the single canonical Stage C consumption:

```text
python scripts/formalization_handoff.py consume \
  --project <physical-repository-root> \
  --handoff research/formalization-handoffs/FH-<stable-id>.json \
  --stage-c-registration "<registered-index>::<exact-receipt-anchor>"
```

The selected registration must exactly match one registration already bound by
the handoff. The command derives the immutable sibling output
`FHC-<stable-id>.json`; it accepts no caller-selected output path and refuses a
second consumption. Exclusive creation closes the check-then-write race for
both handoff and consumption records.

The consumption record binds the receipt path and hash, consumer logical root,
formalization status, scaffold hash at consumption, Stage C registration, and
the explicit effects `mathematical_status=UNCHANGED` and
`verification_status=UNCHANGED`. Consumption is an operational event, not a
proof or verification promotion.

## Verify consumption history

```text
python scripts/formalization_handoff.py verify-consumption \
  --project <physical-repository-root> \
  --consumption research/formalization-handoffs/FHC-<stable-id>.json
```

`CONSUMED_READY` rechecks the immutable receipt file, the source run, proof and
scaffold, the consumer project identity, the consumption-time artifact hash,
and the durable registration anchor. After consumption, the destination
scaffold may evolve during legitimate Stage C work; this does not erase the
historical consumption. Source drift, receipt mutation, project-ID change,
registration-anchor removal, record relocation, duplicate consumption, or any
claimed mathematical or verification promotion remains a hard failure.
