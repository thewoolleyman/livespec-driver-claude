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

## Refinement: arm the band on CORE-EXCLUSIVE names only

The amendment above was itself stress-tested, and as first written it introduces
a new fragility. Arming the 1-7 band assumes no consumer repo ships a file whose
NAME collides with one of the eight. Two of the eight are generic enough to
collide: `next.md` and `help.md`.

This is not hypothetical. `livespec-orchestrator-beads-fabro` ALREADY has a
`next` operation — `.claude-plugin/skills/next/` exists — and ships no
`prose/next.md` today only because that skill is thin-transport and prose-less.
The moment it gains prose, which is the natural evolution for any operation, that
repo scores 1/8 and the rule as written above turns it into a HARD ERROR for
every `/livespec:*` spec-side operation run there. That converts "correctly
declines" into "hard error" on a single filename collision — a worse outcome than
the defect being fixed.

The fix is to separate the two jobs the file set is doing:

- **MATCHING core** stays on all eight. 8/8 means the project IS core.
- **ARMING the error band** keys only on the CORE-EXCLUSIVE six:
  `critique.md`, `doctor.md`, `propose-change.md`, `prune-history.md`,
  `revise.md`, `seed.md`. These name spec-lifecycle operations that no
  orchestrator or control-plane plugin has any reason to own. `next.md` and
  `help.md` are excluded from the arming set precisely because they are generic.

So rule 2 reads:

| checkout state | behavior |
|---|---|
| all eight present | IS core — use the checkout |
| none of the core-exclusive six present | ordinary consumer repo — decline to rule 3 |
| some core-exclusive six present, but not all eight | ERROR: name the missing files and stop |

Checked against the two live consumer repos: `livespec-orchestrator-beads-fabro`
ships `capture-impl-gaps`, `capture-spec-drift`, `capture-work-item`, `groom`,
`implement`, `plan`; `livespec-overseer` ships `foreman`, `overseer`,
`supervise-plan`. Neither collides with any of the six, so both still decline
cleanly. A hypothetical future `prose/next.md` in fabro also declines cleanly,
because `next.md` is not in the arming set.

And the partial-core case still errors loudly: a core checkout missing
`revise.md` still carries five of the core-exclusive six, so it lands in the
error band rather than silently falling through to the installed cache.

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

## Core's second opinion: ruling, and one binding condition

Added 2026-08-20. Routed via the `livespec-overseer-foreman` seat from livespec
core's report-only valve; core filed nothing. Core's readable record:
`/data/projects/livespec/tmp/overseer/foreman/records/core-root-discriminator-second-opinion.md`.

**Core ADOPTS the amendment**: 1-7 is an error, not a decline. Its reasoning is
independent of the argument above and stronger on one point.

Core has never shipped a partial set — all eight prose files landed in a single
commit (`85f795f9`, 2026-06-11) with no adds, renames or deletes to
`.claude-plugin/prose/*.md` since. So there is no HISTORICAL 1-7 state to protect
against. The exposure is prospective, and it comes from core's own contract:
`contracts.md` admits the rename path in terms — "Renaming any operation's
command surface requires a propose-change cycle" (verified in core's live
contract, in the paragraph that also enumerates the eight operations).

The bite is that such a rename is executed by core's maintainers in a WORKTREE of
`/data/projects/livespec`, driving `propose-change` and `revise` — the very
operations the predicate gates. During that worktree's life the set is seven
canonical names plus one new name. Under a bare all-eight boolean that worktree
falls through to rule 3; `/data/projects/livespec` holds an install record; and
resolution lands on the installed CACHE. The maintainer then drives the OLD
RELEASED prose while editing the new prose — silently, guard clean. Core reports
having already paid for that serving-versus-editing failure once this week.

### The condition, and it applies to the REFINED rule too

Core's scenario was argued against the bare all-eight boolean. Checked against
the three-way rule above, it still lands in the error band, both ways:

- rename one of the core-exclusive six (e.g. `revise` -> `amend`): five of six
  present, not all eight -> **ERROR**.
- rename `next` or `help`: all six present, not all eight -> **ERROR**.

So the refined rule does not dodge this. Core's condition stands as stated:

> **The 1-7 diagnostic MUST name `LIVESPEC_CORE_PLUGIN_ROOT` and state that it
> is consulted BEFORE the predicate.**

Without that sentence, the amendment HARD-BLOCKS core's own ratified rename path
using the rename's intermediate state as the trigger — the maintainer could not
run the `revise` that completes the rename. With it, the error is recoverable in
one step.

The escape is real and already implemented: in `resolve_core_root(...)` the
override branch returns `source="override"` before the checkout test is reached.
Verified in this repo's source. So this is one sentence of diagnostic text, not a
design change — but it is not optional, and the test for the 1-7 branch should
assert the diagnostic MENTIONS the override, not merely that it errors.

### Do not over-design the band for growth

Core's other correction, which removes work: adding a NINTH operation needs no
amendment. An all-eight-present test is a SUBSET test, so a superset still scores
8/8 and matches. Only RENAME or REMOVAL of a canonical name can produce a 1-7
score. That branch is unreachable by growth, so it needs no headroom for it.
