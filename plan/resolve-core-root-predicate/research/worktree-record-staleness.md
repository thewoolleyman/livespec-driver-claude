# Worktree install records fossilize, and that decides the walk-up precedence

Ninth research note for plan `resolve-core-root-predicate`. Measured 2026-08-20.

`worktree-resolution.md` raised a precedence fork for the rule-3 primary-checkout
walk-up and explicitly declined to choose: "The plan takes no position. One case
is not enough evidence to choose, and the existing contract language points at
the first option while the failure it produces points at the second."

This note closes that fork. The evidence is no longer one case, and it no longer
points both ways.

## What changed since 2026-08-19

`worktree-resolution.md` recorded the single drift instance as a SNAPSHOT:

```
.worktrees/livespec-overseer/spec-parked-delivery-routing
    own record     -> ebd39d24cba6
    primary record -> 1768d10c92c5   (/data/projects/livespec-overseer)
```

Re-measured 2026-08-20, that primary now reads `ffcd6892e221`. The worktree
record still reads `ebd39d24cba6`. The primary moved; the worktree record did
not.

That is not merely a wider gap. It is a different KIND of fact. A snapshot is
consistent with "somebody pinned this deliberately"; a time series in which the
primary advances while the worktree record never moves is not.

**A THIRD POINT, observed live later the same day.** While this plan's other
measurements were running, that primary advanced AGAIN — `ffcd6892e221` ->
`4262e3e1899c` — and the worktree record still read `ebd39d24cba6`. The full
series for one worktree:

| when | primary `/data/projects/livespec-overseer` | worktree record |
|---|---|---|
| 2026-08-19 | `1768d10c92c5` | `ebd39d24cba6` |
| 2026-08-20, earlier | `ffcd6892e221` | `ebd39d24cba6` |
| 2026-08-20, later | `4262e3e1899c` | `ebd39d24cba6` |

Three primary advances, zero worktree movement, the last one watched happening
rather than reconstructed from a prior reading. Whatever else a per-worktree
record is, it is not tracking the repository it belongs to.

## The full population, and it is unanimous

`~/.claude/plugins/installed_plugins.json`, key `livespec@livespec`, 16 records.
Current build at time of measurement is `ffcd6892e221`.

| kind | count | at current build | stale |
|---|---|---|---|
| primary checkout | 14 | 10 | 4 |
| **linked worktree** | **2** | **0** | **2** |

Both worktree records host-wide:

```
.worktrees/livespec-driver-claude/codex/livespec-nj7d-hook-main -> dfa518239fbf
.worktrees/livespec-overseer/spec-parked-delivery-routing       -> ebd39d24cba6
```

Neither is at the current build. **Both owning primaries ARE** — both
`/data/projects/livespec-driver-claude` and `/data/projects/livespec-overseer`
read `ffcd6892e221`.

### The shape is convergence at the primaries, divergence at the worktrees

Sharper than "both stale", and the part that makes the mechanism OBSERVABLE
rather than inferred. The two primaries agree on ONE build; the two worktrees
disagree, sitting on TWO DIFFERENT past builds:

```
primary   /data/projects/livespec-driver-claude          -> ffcd6892e221  }  same
primary   /data/projects/livespec-overseer               -> ffcd6892e221  }  build

worktree  .../livespec-driver-claude/codex/livespec-nj7d-hook-main -> dfa518239fbf  }  two
worktree  .../livespec-overseer/spec-parked-delivery-routing       -> ebd39d24cba6  }  builds
```

Two independent repos CONVERGED on the current build while their worktrees
DIVERGED to different past ones. That is exactly the signature "records advance
only for the project a session opens in" predicts: the surfaces that keep getting
sessions track forward together, and the ones that stopped getting sessions
freeze wherever they happened to be.

It also rules out the competing explanation. A shared cause — one bad update, one
registry rewrite, one platform bug — would have left both worktrees on the SAME
stale build. They are not on the same build, so whatever stopped them acted per
worktree, at whatever time each was last used. That is abandonment, not an event.

(Observation owed to the `livespec-overseer-foreman` seat, which verified the
2-of-2 result against the registry rather than accepting it and noticed the
divergence the first write-up had not used.)

So in 2 of 2 available cases, own-record-first resolves to a stale build and
primary-always resolves to the current one. The fork does not need a tiebreak;
the sample is unanimous as far as it goes.

Note the first of those two is in THIS repo. The fossilization is not a
`livespec-overseer` peculiarity — this plan's own repo carries an instance.

## Why worktree records fossilize by construction

The mechanism is visible in this session's own startup. The plugin update runs at
session start and is scoped to the project the session opened in:

```
Plugin "livespec" updated from 1768d10c92c5 to ffcd6892e221
    for scope project (/data/projects/livespec-driver-claude)
```

Records advance for the project a session opens in. A worktree acquires a record
only if someone installs into it, and advances it only if sessions keep opening
there with an update running. Under the mandated worktree -> PR -> merge -> DELETE
workflow, worktrees are short-lived and their records outlive them; the two that
exist here are both leftovers whose branches have moved on. Staleness is
therefore the DEFAULT state of a worktree record, not an accident that befell
these two.

This also explains the 4 stale primaries (`livespec` at `4262e3e1899c`,
`livespec-orchestrator-git-jsonl` and `openbrain` at `1768d10c92c5`, `resume` at
`d57b5eb308fd`): those are repos no session has opened recently. Same mechanism,
benign cause. `/data/projects/livespec` is additionally moot — core resolves via
rule 2 dogfooding, so its own record is never consulted.

## The decision this supports

Adopt **primary always** for the walk-up, if and when it is implemented.

The defense of own-record-first was that a per-worktree install might be
deliberate and should be honoured. That defense assumes the record tracks intent.
It does not — it fossilizes at creation, and the gap grows every time the primary
advances. Intent that cannot be distinguished from staleness after two primary
updates is not something a resolver can honour, because nothing in the record
says which it is.

The cost held against primary-always was that it overrides an explicit
per-worktree install. That cost is already covered by rule 1: an operator who
genuinely wants a specific build sets `LIVESPEC_CORE_PLUGIN_ROOT`, which is
explicit, visible at the call site, and does not rot.

The difference between the two options is that **one of them ages and the other
does not**. (Phrasing owed to the `livespec-overseer-foreman` seat, which asked
for it in the plan verbatim.)

## Caveat on strength

Two cases is unanimous but small, and both are leftover worktrees rather than
deliberately-pinned ones — so this measures that records fossilize, not that
nobody ever pins on purpose. What it forecloses is the claim that a worktree
record can be READ as a deliberate pin. It cannot: the two observable instances
are indistinguishable from abandonment, and the mechanism predicts that is the
normal outcome.

If a counter-example appears — a worktree record at the current build, actively
maintained — this conclusion is worth revisiting. None exists on this host today.

## Provenance

Prompted by the `livespec-overseer-foreman` seat on 2026-08-20, which routed the
rule-2 predicate defect and the binding-guard half here rather than filing a
seventh duplicate. The precedence measurement above was taken while verifying a
figure in that exchange; the drift time series is the part that was new to this
plan. See also the correction recorded in `README.md` under the same date.
