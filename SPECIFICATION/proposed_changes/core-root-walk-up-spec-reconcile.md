---
topic: core-root-walk-up-spec-reconcile
author: claude-opus-5
created_at: 2026-08-21T11:41:59Z
---

## Proposal: Retarget step 3 to a defined resolution root, and state the walk-up's cost

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Reconciles contracts.md §"Core-root resolution" with the primary-checkout walk-up shipped in PR 579. Defines the step-3 resolution root (the owning primary for a linked worktree, the project root otherwise), retargets the projectPath selection sentence and the no-matching-record outcome to it, requires the primary's record to win even when the worktree holds one, and states the walk-up's one operator-visible cost: the plugin-update remedy must be issued from the primary, because run inside a worktree it writes a record step 3 deliberately does not read.

### Motivation

Filed from plan `resolve-core-root-predicate` (ledger epic
livespec-driver-claude-cezqks) to repair a contradiction the plan itself created,
found by the independent completeness reviewer commissioned at its archive gate.

WHAT HAPPENED. The plan ratified SPECIFICATION v009 (PR 577, master 38bf8d5),
then merged PR 579 (master 512a1c2) adding the rule-3 primary-checkout walk-up.
`git diff --stat 38bf8d5 512a1c2` shows PR 579 touched
`.claude-plugin/lib/resolve_core_root.py`, `.livespec.jsonc` and the tests, and
ZERO files under `SPECIFICATION/`. So the shipped algorithm changed and the
ratified text describing it did not.

These are CONTRADICTIONS, not gaps -- the spec makes claims the shipped resolver
falsifies:

1. `contracts.md` step 3 selects the record "whose `projectPath` equals the
   project root". From a linked worktree the shipped resolver selects the record
   whose `projectPath` equals the owning PRIMARY.
2. `contracts.md` says "Selection is BY `projectPath`, never by position." The
   shipped code deliberately DECLINES a record whose `projectPath` does equal the
   project root when that root is a worktree -- pinned by the merged test
   `test_the_primary_record_wins_over_the_worktrees_own`, in which the worktree's
   own matching record is rejected in favour of the primary's.
3. `contracts.md` says the no-matching-record state "MUST NOT fall through to
   another project's record". The walk-up falls through to the owning primary's
   record in exactly that state.
4. `contracts.md` argues the `claude plugin update --scope project` remedy "is
   coherent only when the binding reads the same record the command writes --
   which is precisely what `projectPath` selection guarantees." The walk-up
   knowingly breaks that pairing for worktrees, and the justification never
   reached the spec.
5. `scenarios.md` "core-root resolution reports a projectPath mismatch as such"
   asserts that when no record's `projectPath` equals the project root,
   resolution FAILS. That is now false for the worktree-with-provisioned-primary
   case -- which is the majority case the walk-up was built for.

The walk-up itself is correct and is not in question here: it is measured
(recovers 415 of 502 governed roots, residual zero), its precedence was decided
on evidence (worktree install records fossilize; 2 of 2 available ones were stale
while both owning primaries were current), and it is fully tested. What is wrong
is that the ratified text still describes the algorithm it replaced.

This is the exact spec-to-impl drift class the plan exists to eliminate, produced
by the plan's own last merge. Filing it here rather than as a follow-up because
the walk-up shipped as a child of this plan and the contradiction is this plan's
to close.

### Proposed Changes

Step 3 MUST select against a RESOLUTION ROOT rather than against the project root
directly, and that root MUST be defined. Replace the step-3 line so it reads:

> 3. else the `livespec@livespec` install record in
>    `~/.claude/plugins/installed_plugins.json` **whose `projectPath` equals the
>    step-3 resolution root**, resolved to that record's `installPath`.

and add, immediately after the numbered list:

> The step-3 RESOLUTION ROOT is the project root's owning primary checkout when
> the project root is a linked worktree, and the project root itself otherwise.
> A linked worktree records its owner on disk -- its `.git` is a file naming the
> primary's git directory, where a primary checkout's `.git` is a directory -- so
> a realization MUST NOT require invoking `git` to make the distinction.
>
> The walk-up is not a convenience. Governed projects perform tracked-file writes
> from worktrees by fleet mandate, because the primary checkout refuses direct
> commits, and a worktree never acquires an install record of its own. Without
> the walk-up every such operation fails before doing any work, which is the
> majority case rather than an edge case.
>
> The primary's record MUST win EVEN WHEN the worktree holds a record of its own.
> A worktree record MUST NOT be read as a deliberate pin: records advance only
> for the project a session opens in, so a worktree that stops receiving sessions
> freezes at whatever build it last saw, while its owning primary moves on. A
> deliberate pin is expressed by step 1, which is explicit at the call site and
> does not go stale.

The paragraph beginning "The registry key holds an ARRAY of install records" MUST
have its selection sentence retargeted, because as written it now describes
behavior the realization does not have. Replace "Selection is BY `projectPath`,
never by position." with:

> Selection is BY `projectPath` against the step-3 resolution root, never by
> position.

The rest of that paragraph, including the citation to livespec core's
`contracts.md` §"Plugin distribution", MUST NOT change: core's rule is about how a
PROJECT is provisioned, and the walk-up changes which root a Driver asks about,
not what correct provisioning means.

In the step-3 outcome list, the bullet currently reading "records present, but
none whose `projectPath` is the project root" MUST be retargeted to the
resolution root, and its remedy sentence MUST name where the install belongs:

> - **records present, but none whose `projectPath` is the step-3 resolution
>   root** -- the defective state core's §"Plugin distribution" requires be
>   "detected and reported loudly". The binding MUST name the `projectPath`
>   mismatch AS SUCH, MUST report which project roots DO hold records, and MUST
>   NOT fall through to a record that is neither the resolution root's nor its
>   own. The remedy is an install scoped to the resolution root -- for a
>   worktree, that is its owning primary, not the worktree.

Finally, the staleness paragraph's coherence argument MUST be corrected rather
than left standing, because the walk-up changes the condition under which it
holds. After the sentence ending "which is precisely what `projectPath` selection
guarantees.", the spec MUST state:

> For a worktree, that pairing holds only when the update command is issued from
> the resolution root: `claude plugin update livespec@livespec --scope project`
> run inside a worktree writes the worktree's own record, which step 3
> deliberately does not read. The remedy MUST therefore be run from the owning
> primary checkout.

That sentence is the honest cost of the walk-up and MUST NOT be omitted: it is
the one operator-visible behavior the walk-up makes worse, and leaving it
unstated reproduces the loop the surrounding paragraph exists to prevent.

## Proposal: Give the walk-up scenarios, and correct the mismatch scenario it falsified

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Adds the two scenarios the walk-up needs -- resolving from a worktree via its primary's record, and the primary's record winning when the worktree also holds one -- and corrects the existing projectPath-mismatch scenario, whose Given asserts that no record matching the project root means resolution fails, which the shipped resolver now falsifies for every worktree with a provisioned primary.

### Motivation

Filed from plan `resolve-core-root-predicate` (ledger epic
livespec-driver-claude-cezqks) to repair a contradiction the plan itself created,
found by the independent completeness reviewer commissioned at its archive gate.

WHAT HAPPENED. The plan ratified SPECIFICATION v009 (PR 577, master 38bf8d5),
then merged PR 579 (master 512a1c2) adding the rule-3 primary-checkout walk-up.
`git diff --stat 38bf8d5 512a1c2` shows PR 579 touched
`.claude-plugin/lib/resolve_core_root.py`, `.livespec.jsonc` and the tests, and
ZERO files under `SPECIFICATION/`. So the shipped algorithm changed and the
ratified text describing it did not.

These are CONTRADICTIONS, not gaps -- the spec makes claims the shipped resolver
falsifies:

1. `contracts.md` step 3 selects the record "whose `projectPath` equals the
   project root". From a linked worktree the shipped resolver selects the record
   whose `projectPath` equals the owning PRIMARY.
2. `contracts.md` says "Selection is BY `projectPath`, never by position." The
   shipped code deliberately DECLINES a record whose `projectPath` does equal the
   project root when that root is a worktree -- pinned by the merged test
   `test_the_primary_record_wins_over_the_worktrees_own`, in which the worktree's
   own matching record is rejected in favour of the primary's.
3. `contracts.md` says the no-matching-record state "MUST NOT fall through to
   another project's record". The walk-up falls through to the owning primary's
   record in exactly that state.
4. `contracts.md` argues the `claude plugin update --scope project` remedy "is
   coherent only when the binding reads the same record the command writes --
   which is precisely what `projectPath` selection guarantees." The walk-up
   knowingly breaks that pairing for worktrees, and the justification never
   reached the spec.
5. `scenarios.md` "core-root resolution reports a projectPath mismatch as such"
   asserts that when no record's `projectPath` equals the project root,
   resolution FAILS. That is now false for the worktree-with-provisioned-primary
   case -- which is the majority case the walk-up was built for.

The walk-up itself is correct and is not in question here: it is measured
(recovers 415 of 502 governed roots, residual zero), its precedence was decided
on evidence (worktree install records fossilize; 2 of 2 available ones were stale
while both owning primaries were current), and it is fully tested. What is wrong
is that the ratified text still describes the algorithm it replaced.

This is the exact spec-to-impl drift class the plan exists to eliminate, produced
by the plan's own last merge. Filing it here rather than as a follow-up because
the walk-up shipped as a child of this plan and the contradiction is this plan's
to close.

### Proposed Changes

The walk-up is load-bearing behavior with NO scenario, which the authoring
discipline forbids: a clause MUST have a `## Scenario` exercising it. Two
scenarios MUST be added, to sit directly after
`## Scenario: core-root resolution selects the install record for this project`.

`## Scenario: core-root resolution walks up from a worktree to its primary`:

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project is a linked worktree of a primary checkout
And no installed_plugins.json record's projectPath equals the worktree
And one record's projectPath equals the owning primary checkout
When a binding resolves <core-root>
Then it uses that record's installPath
```

`## Scenario: the primary's record wins over a worktree's own record`:

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project is a linked worktree of a primary checkout
And installed_plugins.json holds a record whose projectPath equals the worktree
And it also holds a record whose projectPath equals the owning primary
When a binding resolves <core-root>
Then it uses the PRIMARY record's installPath
And it does NOT use the worktree record's installPath
```

The second scenario MUST NOT be folded into the first as an extra `Then`. The
first is satisfied by any realization that falls back to the primary when the
worktree has no record; only the second pins that the primary wins when BOTH
exist, which is the precedence the fossilization evidence decided and the only
part a naive own-record-first implementation would get wrong.

The existing `## Scenario: core-root resolution reports a projectPath mismatch as
such` MUST have its Given block corrected, because it currently asserts something
the shipped resolver falsifies. Replace:

```gherkin
And no record's projectPath equals the project root
```

with:

```gherkin
And no record's projectPath equals the step-3 resolution root
```

Its `Then` block MUST NOT change: when nothing matches the resolution root,
resolution still fails, still names the mismatch as such, still reports which
roots DO hold records, still refuses to fall through, and still MUST NOT be
reported as plugin staleness. Only the identity of the root being matched moves.

## Proposal: Restate step 3 in the eight bindings so the narrative matches the resolver

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Requires the eight SKILL.md bindings to state step 3 against the resolution root and name the walk-up. All eight currently say the record's projectPath is the project root and mention no walk-up, so the operator-facing narrative disagrees with the resolver they call -- the same failure class the carrier livespec-driver-claude-tun existed to remove, returning three merges after it was closed.

### Motivation

Filed from plan `resolve-core-root-predicate` (ledger epic
livespec-driver-claude-cezqks) to repair a contradiction the plan itself created,
found by the independent completeness reviewer commissioned at its archive gate.

WHAT HAPPENED. The plan ratified SPECIFICATION v009 (PR 577, master 38bf8d5),
then merged PR 579 (master 512a1c2) adding the rule-3 primary-checkout walk-up.
`git diff --stat 38bf8d5 512a1c2` shows PR 579 touched
`.claude-plugin/lib/resolve_core_root.py`, `.livespec.jsonc` and the tests, and
ZERO files under `SPECIFICATION/`. So the shipped algorithm changed and the
ratified text describing it did not.

These are CONTRADICTIONS, not gaps -- the spec makes claims the shipped resolver
falsifies:

1. `contracts.md` step 3 selects the record "whose `projectPath` equals the
   project root". From a linked worktree the shipped resolver selects the record
   whose `projectPath` equals the owning PRIMARY.
2. `contracts.md` says "Selection is BY `projectPath`, never by position." The
   shipped code deliberately DECLINES a record whose `projectPath` does equal the
   project root when that root is a worktree -- pinned by the merged test
   `test_the_primary_record_wins_over_the_worktrees_own`, in which the worktree's
   own matching record is rejected in favour of the primary's.
3. `contracts.md` says the no-matching-record state "MUST NOT fall through to
   another project's record". The walk-up falls through to the owning primary's
   record in exactly that state.
4. `contracts.md` argues the `claude plugin update --scope project` remedy "is
   coherent only when the binding reads the same record the command writes --
   which is precisely what `projectPath` selection guarantees." The walk-up
   knowingly breaks that pairing for worktrees, and the justification never
   reached the spec.
5. `scenarios.md` "core-root resolution reports a projectPath mismatch as such"
   asserts that when no record's `projectPath` equals the project root,
   resolution FAILS. That is now false for the worktree-with-provisioned-primary
   case -- which is the majority case the walk-up was built for.

The walk-up itself is correct and is not in question here: it is measured
(recovers 415 of 502 governed roots, residual zero), its precedence was decided
on evidence (worktree install records fossilize; 2 of 2 available ones were stale
while both owning primaries were current), and it is fully tested. What is wrong
is that the ratified text still describes the algorithm it replaced.

This is the exact spec-to-impl drift class the plan exists to eliminate, produced
by the plan's own last merge. Filing it here rather than as a follow-up because
the walk-up shipped as a child of this plan and the contradiction is this plan's
to close.

### Proposed Changes

All eight `.claude-plugin/skills/*/SKILL.md` bindings state step 3 as "the
`livespec@livespec` install record ... **whose `projectPath` is the project
root**" and mention no walk-up. That narrative no longer describes the resolver
they call, so each binding MUST be updated to state step 3 against the resolution
root and to name the walk-up.

This is the SAME failure class the carrier `livespec-driver-claude-tun` existed to
remove, and it MUST NOT be treated as cosmetic. `tun` was not about a cosmetic
mismatch: it was about operator-facing narrative that disagreed with the code, and
the contradiction was resolved in the WRONG direction once already -- the prose
was rewritten to match the defective code rather than the code fixed to match the
prose. Eight bindings again describing an algorithm the resolver does not run is
that condition returning, three merges after it was closed.

Each binding's step 3 SHOULD read:

> 3. Else the `livespec@livespec` install record in
>    `~/.claude/plugins/installed_plugins.json` whose `projectPath` is the
>    step-3 resolution root -- the project root itself, or, when the project
>    root is a linked worktree, its owning primary checkout. Worktrees never
>    acquire records of their own, so without that walk-up every spec-side
>    operation run from one fails before doing any work.

The bindings MUST NOT restate the walk-up's mechanism (how a worktree's owner is
discovered on disk). They already delegate the algorithm to the Driver-owned
resolver and MUST continue to, for the reason their own text gives: eight
independently-maintained copies of a resolution rule are kept in agreement only by
copying, which is how one defect came to live in all eight at once. The narrative
states WHICH root is consulted; the resolver remains the single realization of HOW
it is found.

The eight edits MUST be a uniform substitution rather than eight independent
rewordings, so that a future drift check can compare them for equality.
