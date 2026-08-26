# The fix is released — is it IN FORCE? Rollout verification and the re-measured rate

Recorded 2026-08-26 for work-item `livespec-driver-claude-mbg4zg.6`. Succeeds
`001-measurement-and-architecture.md`, which measured the 40.5% false-positive
rate that motivated W1 and W2.

"Merged to master" is not "in force". The Driver plugin reaches a governed repo
only through a release plus that repo's `ensure-plugins` picking up the new
cache ref, so `dd3b301` and `c0814ac` stopped the bleeding nowhere until the
rollout is confirmed per repo.

## 1. The mechanism: positive verification, never inference

Every claim below is read off an artifact, never off a command's exit status.
livespec `SPECIFICATION/contracts.md` section "Install verification" forbids the
inference outright, and `livespec_dev_tooling.fleet.ensure_plugins` states the
same rule from the other side: *"a zero exit from a scoped plugin command does
not establish which project's record it touched, so provisioning is confirmed
against the record itself."*

`dev-tooling/bin/verify_guard_rollout.py` (`just verify-guard-rollout`) is that
confirmation, made repeatable:

1. Read `~/.claude/plugins/installed_plugins.json` — the install RECORD.
2. Select every record under `livespec@livespec-driver-claude`, each carrying
   its own `projectPath` and `installPath`. Records are selected by KEY, never
   by position: the array holds one row per project, and a positional read
   answers about whichever project installed the plugin earliest (the defect
   `resolve_core_root.py` already paid for).
3. Replay the committed regression corpus
   (`tests/hooks/fixtures/github_rate_limit_guard_replay_corpus.json`) through
   `python3 <installPath>/hooks/github_rate_limit_guard.py` — the bare-system
   interpreter and path the bundle's `hooks.json` names, so what is exercised is
   the body that governed repo's Claude Code actually loads.
4. A project is IN FORCE only when all fourteen vectors return their recorded
   verdict from THAT body.

Presence of the file is deliberately not the test. A body can be present and
still be the pre-fix build, and a body can be "fixed" by having its decision
logic switched off — the corpus settles both, because it carries the true
positives as controls alongside the false-positive vectors.

The verifier fails CLOSED: no install record, an unreadable record, or an
`installPath` with no hook body all report NOT in force. Absence of evidence is
not evidence the fix is in force, which is the whole reason this item exists.

## 2. The released artifacts, verified body by body

Each tag's `github_rate_limit_guard.py` was fetched from GitHub at that ref and
replayed through the verifier, so the column below is what the RELEASED body
does — not what the changelog says it does.

| Release | Carries | Corpus vectors wrong | Verdict |
| --- | --- | --- | --- |
| v0.5.11 | pre-fix build | 8 / 14 | not in force |
| v0.5.12 | **W1** — `gh api --cache` exemption (`dd3b301`) | 5 / 14 | b1 cleared |
| v0.5.13 | **W1 + W2** — quoted/heredoc masking (`c0814ac`) | 3 / 14 | b1 + b2 cleared |
| v0.6.0 | + bounded literal loops / bare sleep (`63c9491`) | 0 / 14 | IN FORCE |
| v0.7.0 | + guard verdict telemetry (`cf1aefa`, `f2ad38b`) | 0 / 14 | IN FORCE |

Two independent confirmations fall out of this table:

- **v0.5.13 discharges the acceptance criterion**: a `livespec-driver-claude`
  release containing both W1 and W2 exists, and the released body proves it by
  behaviour rather than by changelog text.
- **The corpus's own baseline is validated externally.** The fixture pins
  `pre_fix_baseline.vectors_wrong: 8`; the real v0.5.11 released body returns
  exactly 8 wrong verdicts. The fixture was cut from a session-scratch replay,
  so this is the first time its baseline has been checked against a build
  fetched independently of the session that produced it.

`refs/heads/release` — the ref every governed repo's
`.claude/settings.json` `extraKnownMarketplaces` pins — is
`24e97340f1079d6b1bcdf97a0bc27b1c17e2bbb2` (v0.7.0) as of 2026-08-26T09:15Z, so
the ref an `ensure-plugins` run resolves today carries the fixes.

## 3. The re-measured false-positive rate

Replaying each released body against the W4 fixture and weighting each bucket by
the denial count it was measured at over 2026-08-19 .. 2026-08-26:

| Release | Denials / 7 days | False | Rate |
| --- | --- | --- | --- |
| v0.5.11 (pre-fix) | 615 | 249 | **40.5%** |
| v0.5.12 (W1) | 519 | 153 | 29.5% |
| v0.5.13 (W1 + W2) | 410 | 44 | 10.7% |
| v0.6.0, v0.7.0 | 366 | 0 | **0.0%** |

The 366 true positives still deny at every step: the rate falls because false
denials are removed, not because the guard was weakened.

W1 + W2 alone take the rate from 40.5% to 10.7%. The residue is bucket `b3` —
one `sleep`, no loop, a single polite poll, 44 denials — which `63c9491`
cleared in v0.6.0. Bucket `b4` (bounded literal loops) carries no measured
denial count of its own, having been reclassified out of the true-positive
population after the measurement, so it does not move this arithmetic; v0.5.13
still denied it and v0.6.0 does not.

## 4. What is confirmed, and what the per-repo sweep still needs

Confirmed here: the release exists, the released bodies behave, the corpus
baseline is externally valid, and the rate is re-measured at 0.0% on the ref
governed repos install from.

NOT confirmable from this sandbox: which governed repos have actually PICKED UP
that ref. Install records are host state. This clone's
`~/.claude/plugins/installed_plugins.json` reads `{"version": 2, "plugins": {}}`
— no records at all, so nothing was verified here and the verifier exits 1,
which is the correct fail-closed answer rather than a silent pass.

The sweep is one command per host carrying governed checkouts:

```bash
mise exec -- just verify-guard-rollout
```

It emits one JSON line per `projectPath` with `in_force` and, when stale, the
vectors that disagreed. A `false` line is repaired by that project's
`claude plugin update livespec@livespec-driver-claude --scope project` (or
simply its next `ensure-plugins` at SessionStart) — and then re-verified, since
the update command's own exit status proves nothing.
