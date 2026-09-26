# DSH STORE issue #1185: local repair evidence

The [DSH STORE notice](https://github.com/AI-Scarlett/DSH-Store/issues/1185)
identified the 2.0.0 fixed source at
`4f750265875ea1e0ba3f7abc67e26d31fd830409` as `catalog-blocked`.
Its stated reasons were absent DSH and Node.js compatibility declarations plus
file, network and command source signals. The notice is a fixed-source policy
result, not a vulnerability finding or a runtime test.

## Reproduced failure and repair

The first disposable Profile, before the runtime entry repair, installed the
local Bundle successfully and included its Patch row in `--dump-config`, but
DSH startup warned that
`math-research-dsh` failed to import. Its direct import of
`@deepseek-ai/dsh-skill-filesystem` had no matching package in the clean
Profile's dependency closure, which explains the warning. This is a
runtime fault which the STORE's static automation did not claim to test.

Version 2.0.1 registers the four immutable packaged skills through the
public injected `ctx.skills.register` service. It parses each packaged
`SKILL.md` at import, requires the expected name and supplies the directory
`resourceBase`. The Bundle has no npm runtime dependency or install lifecycle
script. The 2.0 parent skill files and their `upstream.lock.json` were not
changed.

## Disposable acceptance

The candidate was packed from this worktree and tested on Linux, Node.js
`v24.17.0`, with the official `@deepseek-ai/dsh@0.1.7-rc.2` CLI. The exact
tested tarball SHA-256 is
`90bc6de1e6cb0f8872343c2b2c4bf9af3fff3ae76eef0a6029076a9b2cfda67f`
(797894 bytes). The sanitized machine-readable result is
[dsh-store-issue-1185-evidence.json](dsh-store-issue-1185-evidence.json).

| Check | Observed result |
| --- | --- |
| Install | Official `dsh plugin --profile <disposable> add <local tarball>` returned 0 for `headless` and `web` Profiles. |
| Config | Each `--dump-config` contained exactly one `math-research-dsh` entry. |
| Start | Both Profile `--help` boot paths returned 0 without an inactive-entry warning. The Web Profile also listened on `127.0.0.1`; an unauthenticated GET returned the expected HTTP 401. |
| Uninstall | Official `plugin remove math-research-dsh` returned 0 for both Profiles. Their composed configs matched the respective preinstall baselines byte for byte. |
| Rollback | A separate headless reinstall and removal restored the composed config, Profile `package.json` and `pnpm-lock.yaml` byte for byte. |

The test driver is [test_store_disposable_profile.py](../tests/test_store_disposable_profile.py).
It creates a temporary `DSH_HOME`, uses the official CLI for package changes,
and emits no Web token in its report. The added CI job is configured to run it
against the same fixed DSH release and retain its sanitized JSON artifact.
A local replay returned
`STORE_PROFILE_OK` with the tarball hash above.

Repository validation returned 51/51 checks, the Bundle gate returned
`BUNDLE OK`, and root unit discovery returned 36 tests with 2 skips. These
results cover structure and the named tests, not all mathematical behavior.

## Remaining boundary

The exact `0.1.7-rc.2` compatibility and install/start/uninstall/rollback
results are declared in `package.json`. `0.1.7-alpha.2` and `0.1.7-rc.1`
remain `unknown`; they were not installed in this check. An authenticated
model session invoking each skill, Windows/macOS, and the user's real Profile
were not tested.

The shipped research helpers still have real project file operations, optional
Git/Lean command execution, and a same-origin Blueprint viewer `fetch` call.
The automatic low-risk STORE policy may therefore keep installation blocked
after a new fixed Commit. A guarded `user-reviewed` route or any status change
requires the STORE's separate review. This repository does not claim that a
manifest declaration by itself grants approval.
