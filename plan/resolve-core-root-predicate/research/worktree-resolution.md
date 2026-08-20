# The worktree case is the normal case, and rule 3 does not handle it

Eighth research note for plan `resolve-core-root-predicate`. Prompted by an
unsolicited live measurement from the `livespec-overseer`
`supervision-safety-and-attention-truth` thread on 2026-08-19, which hit the
misresolution while driving `/livespec:revise` and reported it here. Every claim
below was re-verified locally before being recorded.

This note corrects the framing in `post-fix-operational-impact.md` and raises a
scope decision the plan had not surfaced.

## What the other thread measured

Running `/livespec:revise` from
`.worktrees/livespec-overseer/revise-acting-safety` — a linked WORKTREE of
livespec-overseer, not the primary checkout — rule 2 resolved to that worktree's
own `.claude-plugin`, because it carries `foreman.md`, `overseer.md` and
`supervise-plan.md`. Verified locally: that directory holds exactly those three
files and the worktree has NO `livespec@livespec` registry record.

Their observation that reframes this plan: **spec-side operations are
tracked-file writes, and this fleet mandates worktree → PR → merge for those.**
So for `revise` and `propose-change`, running from a worktree is the NORMAL
execution context, not an edge case. And worktrees do not acquire registry
records under normal workflow.

## The correction this forces

`post-fix-operational-impact.md` measured that 288 of 291 affected project roots
hold no install record, and framed that as: those roots were always
mis-provisioned, and the fix merely converts a silent wrong answer into a loud
correct diagnostic.

That is technically true and practically misleading. It implies a provisioning
backlog somebody could go clear. The truth is structural: worktrees will never
carry records under the mandated workflow, so fixing rule 2 alone converts the
NORMAL spec-op path from "silently wrong root" to "loudly broken". Still an
improvement — a loud failure beats a silent wrong answer — but not the
operational footnote that note described.

## Rule 3 can be made to handle it, and the fix is cheap to state

A linked worktree knows its owning checkout. Measured:

```
$ git -C <worktree> rev-parse --path-format=absolute --git-common-dir
/data/projects/livespec-overseer/.git
```

Strip the trailing `/.git` and the result is the primary checkout — which DOES
hold the registry record, pointing at the correct build.

## How much this actually recovers

Measured across the full affected set:

| | rule-2 fix alone | rule-2 fix + primary walk-up |
|---|---|---|
| resolve correctly | 3 | **291** |
| hard-fail with `project_not_installed` | 288 | **0** |

The walk-up closes every remaining case. Not most — all 291. That moves the
change from "a fix that breaks the mandated workflow loudly" to "a fix that
works where the work actually happens".

This is the single largest lever found on this plan, and it is not the predicate.

## A second failure mode: worktree records drift from their primary

Worktrees CAN acquire their own records, and then pin a different core build
than the repo they belong to. Exactly one instance on this host:

```
.worktrees/livespec-overseer/spec-parked-delivery-routing
    own record     -> ebd39d24cba6
    primary record -> 1768d10c92c5   (/data/projects/livespec-overseer)
```

So a walk-up needs a stated PRECEDENCE, and the choice is a real decision rather
than an obvious default:

- **own record first, primary as fallback** — literal, and matches the existing
  contract wording ("the record whose `projectPath` equals the project root").
  But it preserves the drift above: that worktree keeps resolving to a build its
  own repo no longer uses.
- **primary always** — makes every worktree of a repo agree with that repo, and
  eliminates drift by construction. But it overrides an explicit per-worktree
  install, which someone may have created deliberately.

**Superseded 2026-08-20 — the plan now takes a position: primary always.** See
`worktree-record-staleness.md`. When this note was written the drift above was a
single SNAPSHOT, which is consistent with a deliberate pin. Re-measured a day
later, that worktree's primary had advanced while the worktree record had not,
and BOTH worktree records that exist host-wide (2 of 2) are stale while both
their owning primaries are current. A record that fossilizes cannot be read as
intent, and rule 1 already covers the deliberate-pin case without rotting.

## Scope consequences

This collides with `implementation-constraints.md`. That note measured ~30
logical lines of headroom in `resolve_core_root.py` against an ARMED 250 LLOC
hard ceiling, and `partial-core-checkout-hole.md` has since consumed much of it
with a three-way predicate and a new `CoreRootUnresolved` kind. A worktree
walk-up — a subprocess call to `git`, its failure handling, and the precedence
rule — will not also fit.

So this is a genuine fork, and it is the maintainer's:

1. **Land the predicate fix alone.** Smallest changeset, fits the ceiling, and
   is a strict improvement. Leaves the mandated worktree workflow loudly broken
   at 288 roots until a follow-up.
2. **Land both together.** Requires splitting `resolve_core_root.py` first — the
   file is already over its 200-line soft ceiling with a standing refactor
   warning — which makes this a materially bigger changeset than `d7d` describes.
3. **Land the predicate fix, file the walk-up as its own child of this plan.**
   Keeps each changeset inside the gates, at the cost of an interval where
   spec-side operations from consumer worktrees fail loudly.

Option 3 is the shape the plan's own constraints point at, but the interval in
option 3 is not free and the maintainer may not want it.

## Note on the reporting thread

They asked whether to file the worktree half separately in this repo. I asked
them not to: the Driver owns core-root resolution so it is this plan's scope,
and this repo already has an intake problem — `livespec-driver-claude-d7d`
carries no `intake:triaged` label, so no dispatch surface admits it and `next`
ranks nothing. Adding another untriaged item would make that worse. Their
measurement is recorded here instead, attributed; whether it becomes its own
child item is the maintainer's call.

Their workaround was the sanctioned rule-1 override, pointed at the build the
registry names for their project.
