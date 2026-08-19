# Why the core operation-prose set is the right rule-2 predicate

Third research note for plan `resolve-core-root-predicate`. Read
`defect-and-fix-shape.md` for the defect and `cross-driver-blast-radius.md` for
the three-Driver scope. This note answers the one open decision those two leave
to the maintainer: WHICH core-identity marker rule 2 should test.

All measurements 2026-08-19.

## The candidate

Rule 2 matches only when `<project-root>/.claude-plugin/prose/` carries all
eight core operation prose files:

```
critique.md  doctor.md  help.md  next.md
propose-change.md  prune-history.md  revise.md  seed.md
```

Four objections were raised against it when the plan was opened. Each was
checked; all four fail.

**A FIFTH consideration, found later by trying to refute this note rather than
confirm it, does NOT fail** — see `partial-core-checkout-hole.md`. A bare
all-eight boolean silently falls through to rule 3 when core's own checkout
carries a partial prose set, resolving to the installed cache instead of the
working tree. The marker below is still the right base, but rule 2 must treat
the 1-7 band as an ERROR rather than a decline. Read that note alongside this
one.

## Objection 1 — "this needs a new core contract"

It does not, and this is the strongest argument for this marker over any other.

This repo's `SPECIFICATION/contracts.md` §"Core-root resolution" states that
resolution is Driver-owned and that "livespec core is agnostic to how a Driver
finds it". livespec core's own `contracts.md` confirms it: core ratifies no
core-root resolution rule anywhere. So there is no existing place to ratify a
marker, and inventing one would mean amending core's deliberate agnosticism.

But core DOES already ratify the eight-operation set, in
`livespec/SPECIFICATION/contracts.md`:

> After installing core plus a runtime Driver, the Driver exposes the same eight
> operations ...: `seed`, `propose-change`, `critique`, `revise`, `doctor`,
> `prune-history`, `help`, `next`. ... Renaming any operation's command surface
> requires a propose-change cycle. ... core supplies the harness-neutral prose,
> wrapper CLIs, templates, and schemas that each Driver binds.

So a predicate keyed on those eight prose files rides an ALREADY change-controlled
core contract. Each Driver can adopt it independently and still agree, because
all three are keying off the same core-owned, propose-change-gated list — not off
a marker three repos would have to keep in sync by copying. That directly answers
scope question 1 in `cross-driver-blast-radius.md`: no new core contract, no
cross-repo coordination, and no new agreement to maintain.

## Objection 2 — "an all-eight check is brittle across core versions"

Empirically it is not. Core's `prose/` history was traced end to end: the eight
files have been complete since `85f795f9` (2026-06-11), the very commit that
created the prose decomposition ("chore(skills): decompose spec-side skills into
core prose + thin Claude bindings"). Spot-checked at that commit and at three
later points (`HEAD~600` 2026-07-28, `HEAD~200` 2026-08-12, `HEAD` 2026-08-19):
8 prose files at every one.

There is no core revision in which `prose/` exists with fewer than eight files.
The brittleness this objection imagines has never once occurred, and the contract
above means it cannot occur silently — a rename requires a propose-change cycle.

## Objection 3 — "it might false-negative on a real installed core"

Checked against every distinct `livespec@livespec` build in the local install
cache (six distinct `installPath`s across sixteen project records):

| build | prose/ present | core files |
|---|---|---|
| `ebd39d24cba6` | yes | 8/8 |
| `1768d10c92c5` | yes | 8/8 |
| `d57b5eb308fd` | yes | 8/8 |
| `dfa518239fbf` | yes | 8/8 |
| `5f3eea72711c` | yes | 8/8 |
| `6ef6447ec342` | yes | 8/8 |

All 8/8. This matters beyond rule 2: it means the SAME marker can replace the
weak `[ -d "$LIVESPEC_CORE_ROOT/prose" ]` post-resolve guard in the eight
bindings (the `livespec-driver-claude-tun` surface) without producing a single
false negative on a real cache. One marker, both places.

## Objection 4 — "a single marker file is simpler"

It is, and it is the shape the original source report suggested
(`prose/revise.md`). It works against today's repos but reintroduces the same
failure class: any future family repo that ships a `revise` operation
false-matches again. This module's own docstring already warns twice about
almost-right discriminators, and this plan exists because one of them shipped.

The `plugin.json` `name` field is not an alternative either — verified 2026-08-19
that it is `"livespec"` for BOTH livespec core AND this Driver, so manifest name
cannot distinguish them.

## Discrimination check

The predicate was prototyped against the five family checkouts present on this
host:

| repo | ships `prose/` | eight-file marker |
|---|---|---|
| `livespec` | yes | **matches** |
| `livespec-overseer` | yes | no |
| `livespec-orchestrator-beads-fabro` | yes | no |
| `livespec-driver-claude` | no | no |
| `livespec-dev-tooling` | no | no |

Exactly one match, and it is core.

Re-checked 2026-08-19 against the full host sweep rather than these five: across
**291** candidate project roots that ship their own `.claude-plugin/prose/`, every
non-core one scores 0/8 and core scores 8/8. No near-miss at any point in the
larger sample. One candidate ships eight prose files of its own and still scores
0/8 — same count as core, no overlap in names — which is why the predicate must
name the eight files rather than count them.

## Rule 3 is already correct — confirm before touching it

Worth stating so the fix does not widen: rule 3 needs no change. Run from
`/data/projects/livespec-dev-tooling`, which ships no `prose/` (so rule 2
correctly declines and rule 3 is the path actually exercised):

```
$ python3 .../lib/resolve_core_root.py --project-root .
/home/ubuntu/.claude/plugins/cache/livespec/livespec/1768d10c92c5
```

That is the record whose `projectPath` IS that repo. The FIRST record in the
array is `/data/projects/livespec-runtime -> .../ebd39d24cba6`, which positional
selection would have returned. Rule 3 selects by `projectPath` correctly today;
the only reason it appears broken from a `prose/`-shipping repo is that rule 2
shadows it. (This also retires `livespec-driver-claude-6lc`, which reports the
positional defect as live — see that item's 2026-08-19 comment.)

One adjacent gap, noted but NOT proposed as in-scope: rule 3 returns the record's
`installPath` without checking that the path exists or carries prose. The
post-resolve guard in the bindings is currently the only thing covering a stale
or half-fetched cache entry, which is an argument for tightening that guard
rather than leaving it as the weak directory test.
