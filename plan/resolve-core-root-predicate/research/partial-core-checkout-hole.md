# The partial-core-checkout hole, and the fix for it

Seventh research note for plan `resolve-core-root-predicate`. Written 2026-08-19
by trying to REFUTE this plan's own recommendation rather than confirm it again.
The attempt succeeded, so the recommendation is amended here. Read
`predicate-justification.md` first; this note supersedes its framing that all
objections to the eight-file marker fail.

## The hole

The eight-file marker requires ALL of core's operation prose to be present. A
genuine core checkout that is missing ANY ONE of the eight therefore fails rule
2. Rule 3 then runs — and `/data/projects/livespec` HOLDS a `livespec@livespec`
install record, so rule 3 succeeds and resolves to the installed cache.

The core developer's `--plugin-dir .` dogfooding session then reads core's prose
from `~/.claude/plugins/cache/...` instead of from the working tree they are
editing. Silently. No diagnostic, no warning, exit 0.

That is the SAME failure class this whole plan exists to remove: a wrong core
root, resolved confidently, with the correct answer available and unused. It is
narrower than the shipped defect — it needs core itself to be in a partial state
— but it is not hypothetical.

## Measured, not argued

Simulated against live host state, calling the SHIPPED `_record_for(...)` with
the proposed rule 2 in front of it:

```
real core checkout has 8/8 prose files
core's OWN project root HAS an install record
  -> /home/ubuntu/.claude/plugins/cache/livespec/livespec/1768d10c92c5

missing revise.md   7/8 -> rule 2 DECLINES -> rule 3 -> installed cache  (SILENT)
missing next.md     7/8 -> rule 2 DECLINES -> rule 3 -> installed cache  (SILENT)
missing help.md     7/8 -> rule 2 DECLINES -> rule 3 -> installed cache  (SILENT)
```

Under a single-file marker (`prose/revise.md`) the same three cases resolve
2-of-3 correctly, because only the loss of `revise.md` itself trips it.

So the trade-off between the two candidate markers is REAL and two-sided, which
`predicate-justification.md` did not say:

| marker | false POSITIVE (non-core matched) | false NEGATIVE (partial core missed) |
|---|---|---|
| `prose/` directory (shipped defect) | 292 roots on this host | never |
| single file (`prose/revise.md`) | any future family repo shipping a `revise` op | only if that one file is absent |
| all eight | none measured across 314 roots | any one of eight absent |

## Realistic triggers

Not exotic. A core checkout can carry 1-7 of the eight during:

- a branch mid-rename of an operation;
- a branch that adds or removes an operation — which core's own
  `contracts.md` §"Plugin distribution" explicitly permits via a
  propose-change cycle, so the operation SET is not frozen;
- a sparse or partial checkout;
- any transient editing state.

## The fix: treat the 1-7 band as an error, not a decline

Keep the eight-file marker, and make rule 2 distinguish THREE states rather than
two:

- **8/8 core prose present** — the governed project IS core. Use the checkout.
  (unchanged)
- **0/8 present** — an ordinary consumer repo shipping its own plugin prose.
  Decline and fall through to rule 3. (unchanged, and this is the shipped
  defect's fix)
- **1-7 present** — a project carrying SOME core operation prose and not all of
  it. This is not a consumer repo and it is not a usable core root. Do NOT
  silently fall through. Emit a diagnostic naming which prose files are missing,
  and stop.

This closes the silent-fallback hole while keeping the discrimination that made
the eight-file marker attractive.

## Why the 1-7 band costs nothing

This plan's own full-host sweep already measured the band, and it is EMPTY:

| score | roots |
|---|---|
| 8/8 | 22 |
| 1-7 | **0** |
| 0/8 | 292 |

314 candidates, nothing in between. So promoting 1-7 to an error state
introduces no false alarm on any real project on this host — there is nothing
there to alarm about. A root that lands in that band is, by construction, an
anomaly worth reporting rather than guessing past.

That also makes the earlier "separation is total" result do double duty: it is
not only evidence that the marker discriminates, it is evidence that the
error-state band is safe to arm.

## What this changes for the implementation

- The predicate is no longer a bare boolean. It returns three-way, which is a
  natural fit for the module's existing `CoreRootOutcome` union: the 1-7 case is
  a new `CoreRootUnresolved` kind (something like `core_checkout_incomplete`)
  alongside the six that exist.
- `implementation-constraints.md` notes about 30 LLOC of headroom against an
  ARMED 250 hard ceiling. A three-way predicate plus one new union member plus
  its diagnostic branch is larger than the two-way version — this is now the
  binding constraint on the changeset, and the adjacent rule-3 `installPath`
  hardening must definitely stay out.
- Coverage is `fail_under = 100`, so the new 1-7 branch needs its own test. That
  is a third test, not a second: 8/8 matches, 0/8 declines to rule 3, 1-7 errors.

## Honest status of the recommendation

`predicate-justification.md` said four objections were raised and all four fail.
That stands for those four. This is a FIFTH consideration that was not tested
there, and it does not fail — it required an amendment. The eight-file marker
remains the right base, but only with the 1-7 band armed as an error; the bare
all-eight boolean trades a loud, common defect for a silent, rarer one.
