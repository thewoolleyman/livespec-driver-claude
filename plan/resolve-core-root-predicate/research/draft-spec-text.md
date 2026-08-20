# Draft spec text for the rule-2 predicate

Sixth research note for plan `resolve-core-root-predicate`. This is a DRAFT of
the spec-side wording the fix will need, prepared so it is ready to paste when
the maintainer drives `/livespec:propose-change`. **Nothing here is filed.** No
proposed change exists in `SPECIFICATION/proposed_changes/`, and this note
commits the spec to nothing.

Drafted 2026-08-19 against `SPECIFICATION/scenarios.md` and
`SPECIFICATION/contracts.md` as they stand on master.

## What the spec already gets right, and must not change

`contracts.md` §"Core-root resolution" rule 2 already states the correct RULE:

> 2. else `<project-root>/.claude-plugin/` when the governed project IS the
>    livespec core repo — the `--plugin-dir .` dev / dogfooding path;

That sentence is not the defect. The defect is that the implementation does not
realize it. So this is an implementation gap, and no CORRECTION is owed to
`contracts.md`. What is missing is (a) a scenario pinning the negative case and
(b) a sentence naming what "IS the livespec core repo" is decided BY, so the next
implementation cannot drift back to an almost-right discriminator.

## Draft 1 — the missing negative scenario

`scenarios.md` today has three core-root resolution scenarios: override,
governed-project checkout, and install-record selection. None pins the case that
broke. Proposed addition, in the file's existing house style, to sit directly
after "core-root resolution falls back to the governed-project checkout":

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project ships its OWN plugin carrying a prose/ directory
And that prose/ does NOT hold the livespec core operation prose
And installed_plugins.json holds a livespec@livespec record whose projectPath
    equals the project root
When a binding resolves <core-root>
Then it does NOT use <project-root>/.claude-plugin/
And it uses that record's installPath
```

Heading: `## Scenario: core-root resolution rejects a non-core project checkout`

Note the scenario is PREDICATE-INDEPENDENT. It states the required behavior
("does not use the project checkout when that checkout is not core"), not the
marker used to decide it, so it stays valid whichever discriminator is ratified.
That is deliberate: it is the regression pin, not the design.

## Draft 2 — sharpening the existing positive scenario

The existing scenario says "the governed project IS the livespec core repo loaded
with `--plugin-dir .`", which is true but states no observable. A reader
implementing from it has to invent the test — which is how the current defect
arose. Proposed replacement Given-line:

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And <project-root>/.claude-plugin/prose/ carries the complete core operation
    prose set — the dev / dogfooding case, loaded with --plugin-dir .
When a binding resolves <core-root>
Then it uses <project-root>/.claude-plugin/
```

## Draft 3 — the contract sentence naming the discriminator

Proposed addition to `contracts.md` §"Core-root resolution", after the numbered
list and before the "This resolution order is load-bearing" paragraph:

> Step 2's condition — that the governed project IS the livespec core repo — MUST
> be decided by a marker that livespec core carries and a non-core plugin does
> not. The presence of a `prose/` directory is NOT such a marker: every plugin in
> this family ships harness-neutral prose under its own
> `.claude-plugin/prose/`, so testing the directory alone matches any
> plugin-shipping consumer and pre-empts step 3, which holds that consumer's
> correct answer. The marker MUST distinguish livespec core from a repo that
> merely ships a plugin with prose. The reference realization requires the
> complete set of core operation prose files — one per operation named in
> livespec core's `contracts.md` §"Plugin distribution" — which is a
> change-controlled core contract rather than a marker each Driver invents
> separately.

Rationale for putting the RULE in the contract but the SET in the reference
realization: the contract must forbid the almost-right predicate (that is what
was violated), while the exact file list belongs with the implementation so the
three Drivers can adopt it without the contract enumerating core's operations a
second time — core already enumerates them, under propose-change control.

## What this does NOT propose

- No change to the ORDERING of the three steps. Reordering was measured and
  rejected in `predicate-justification.md`: `/data/projects/livespec` holds an
  install record, so putting step 3 first would resolve core to its installed
  cache instead of the working checkout and defeat `--plugin-dir .` dogfooding.
- No scenario for the post-resolve guard in the bindings. That surface is
  `livespec-driver-claude-tun`, and whether it lands in the same changeset is an
  open maintainer decision recorded in the plan's handoff; drafting its spec text
  now would presume that answer.
- No scenario for the adjacent rule-3 `installPath` existence gap, which
  `implementation-constraints.md` recommends keeping out on both scope and LLOC
  grounds.

## Handling note

If the maintainer ratifies a different marker, Draft 1 stands unchanged
(predicate-independent), Draft 2 needs its Given-line reworded to name the chosen
marker, and Draft 3's final sentence needs replacing. Drafts 1 and 2 are the ones
worth keeping regardless.

## STALENESS NOTICE (2026-08-20) — read before pasting any of the above

Drafts 1-3 were written 2026-08-19, BEFORE two things that are now part of the
ratified design:

1. `partial-core-checkout-hole.md` amended the rule from a two-way boolean to a
   THREE-WAY outcome: 8/8 matches, none-of-the-core-exclusive-six declines, and
   anything in between is an ERROR rather than a decline.
2. livespec core's second opinion RATIFIED that amendment with one BINDING
   CONDITION: the 1-7 diagnostic MUST name `LIVESPEC_CORE_PLUGIN_ROOT` and state
   that it is consulted BEFORE the predicate.

Neither appears in Drafts 1-3. Checked: the only occurrences of
`LIVESPEC_CORE_PLUGIN_ROOT` above are the "is unset" Given-lines, which are a
different use.

**Consequence if pasted as-is.** The filed proposed change would pin the positive
and negative cases correctly and say NOTHING about the error band or the
override sentence. Core's condition would then exist only in this plan's notes
and in core's own report-only record — nothing in either repo's spec would
require it, nothing would stop a later revision from dropping it, and the
implementation could satisfy every ratified scenario while still hard-blocking
core's rename path. That is the failure the condition exists to prevent, arriving
by a different route.

Drafts 1 and 2 remain correct and paste-ready. Draft 3's closing sentence needs
the replacement below. Drafts 4 and 5 are new and cover the gap.

## Draft 4 — the 1-7 error scenario (NEW)

To sit directly after Draft 1's negative scenario:

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And <project-root>/.claude-plugin/prose/ holds CORE-EXCLUSIVE operation prose
    but NOT the complete core operation prose set
And installed_plugins.json holds a livespec@livespec record whose projectPath
    equals the project root
When a binding resolves <core-root>
Then resolution FAILS and names the missing prose files
And it does NOT fall through to that record's installPath
```

Heading: `## Scenario: an incomplete core checkout fails rather than falling back`

Why the last line carries the weight: falling through is the SILENT failure the
amendment exists to prevent. A core checkout mid-rename would otherwise resolve
to the installed cache and serve the OLD released prose while the maintainer
edits the new. Stating only "resolution fails" would leave a conforming
implementation free to decline instead of error.

## Draft 5 — core's binding condition (NEW)

```gherkin
Given resolution has failed because the core prose set is incomplete
When the diagnostic is emitted
Then it names LIVESPEC_CORE_PLUGIN_ROOT
And it states that the override is consulted BEFORE the completeness check
```

Heading: `## Scenario: the incomplete-checkout diagnostic names the recovery`

This is the scenario that must not be dropped. Without it the error band
hard-blocks core's OWN ratified rename path: a rename is executed in a worktree
of core, which transits the incomplete state precisely while driving the
`propose-change` and `revise` operations the predicate gates, and the maintainer
could not run the `revise` that completes the rename. The override already
returns before the checkout test, so the recovery exists — the requirement is
that the diagnostic SAYS so.

Note this is deliberately a separate scenario from Draft 4 rather than another
`And` on it. A diagnostic that errors correctly but says nothing satisfies Draft
4 completely; only a separate assertion pins the text.

## Draft 3, replacement closing sentence

Replace the final sentence of Draft 3 ("The reference realization requires the
complete set...") with:

> The reference realization requires the complete set of core operation prose
> files — one per operation named in livespec core's `contracts.md` §"Plugin
> distribution" — which is a change-controlled core contract rather than a marker
> each Driver invents separately. MATCHING core requires the COMPLETE set. A
> checkout that carries evidence of being core — operation prose whose names no
> non-core plugin has reason to own — while NOT carrying the complete set MUST be
> reported as an error naming the missing files, and MUST NOT be treated as a
> non-core project: falling through to step 3 there resolves a mid-rename core
> checkout to its own installed cache, serving released prose to a maintainer who
> is editing its replacement. Which names carry that evidence is designated ONCE
> and binds every realization; the designation MUST be identical across Drivers,
> and MAY be a proper subset of the operation set. Names generic enough that a
> consumer plugin might legitimately own one MUST NOT be designated, or a single
> filename collision turns "correctly declines" into "hard error" in a repository
> that has nothing to do with livespec. The designation MAY be changed only by a
> propose-change cycle, and adding an operation to the set above does NOT add its
> name to the designation. Because that error is reachable during core's own
> ratified rename cycle, its diagnostic MUST name the step-1 override and state
> that the override is consulted first.

## Handling note, revised

If the maintainer ratifies a different marker: Draft 1 stands unchanged
(predicate-independent), Draft 4 stands unchanged for the same reason — it says
"some but not all of the core operation prose set" without naming the arming
subset — and Draft 5 stands unchanged, since it constrains the diagnostic rather
than the predicate. Only Draft 2's Given-line and Draft 3's closing sentence are
marker-specific. That is one more argument for keeping the arming detail (the
core-exclusive six) in the reference realization rather than in the contract.


## The count trap, and why this wording is what it is

Added 2026-08-20, reported by livespec core's seat while reviewing the matching
contract amendment — before either side was filed.

The earlier drafts said a checkout "carrying SOME of that set but not all of it"
must error. The implementation arms the error band on the CORE-EXCLUSIVE six, not
on all eight. Those disagree, and the disagreement is demonstrable: a checkout
shipping only `help.md` and `next.md` DECLINES to rule 3 in code, while that
sentence says it must error.

Why it would have survived review, which is the part worth remembering. Core's
`contracts.md` paragraph enumerates THE EIGHT and already says renaming an
operation requires a propose-change cycle. A sentence appended there stating that
resolution keys off "the eight" is true in its own right. The Driver keying off
six is true in its own right. No reviewer comparing either sentence against its
neighbours finds a contradiction — **it is not a wrong claim, it is two right
claims that must move together, recorded as if independent.** That is the
clause-lockstep defect this whole amendment exists to prevent, reintroduced by
its own fix.

So the drafts above hardcode NO COUNT. They say the error arms on EVIDENCE OF
CORE — names no non-core plugin has reason to own — and explicitly delegate which
names those are to the reference realization, while stating the constraint that
generic names must not arm it. A rename, or a ninth operation, then moves the
implementation without stranding the contract.

Two corollaries core supplied, so nobody spends measurement on them:

- **Adding a ninth operation needs no amendment.** An all-present test over a
  fixed name set is a SUBSET test, so a superset still scores full marks. Only
  RENAME or REMOVAL of a discriminating name can produce a partial score. The
  band is unreachable by growth; do not design it for growth.
- **Core carries no live resolution text.** Zero occurrences of
  `LIVESPEC_CORE_PLUGIN_ROOT` or `resolve_core_root` anywhere under core's
  `SPECIFICATION/`, and zero across all eight `prose/*.md`. The only loose
  "core root" hits are two non-contract artifacts. So no core sweep is owed.

Core also confirmed the SET is ratified at its `SPECIFICATION/spec.md` line 238,
not merely in `contracts.md` — "livespec defines eight spec-side sub-commands ...
Each sub-command has a core-owned operation prose artifact under
`.claude-plugin/prose/<name>.md`". That is the sentence the marker actually
reads, and it is why the marker reads a contract rather than a coincidence.


## Correction: ONE designation, not one per Driver (2026-08-20)

Reported by core's seat on review of the wording above, and it is not a nit.

The previous clause said the evidence names were "the reference realization's to
designate". **Core has THREE reference realizations**, stated at its
`SPECIFICATION/spec.md` line 424: "Three per-runtime Driver plugin repositories
are current reference work ... `livespec-driver-claude` (Claude Code),
`livespec-driver-codex` ... and `livespec-driver-pi`". Verified. So in core's own
vocabulary that phrase reads as a PER-DRIVER designation.

Follow it through and the consequence is worse than ambiguity. Three Drivers may
designate three different evidence sets, so the SAME partial core checkout
hard-errors on Claude and falls silently through to rule 3 on Codex — resolving
the installed cache, which is the exact silent failure this predicate exists to
eliminate. The result is a diagnostic reproducible only on some runtimes: the
operator who reports it and the operator who cannot reproduce it are both right,
and neither can settle it from their own seat.

This is NOT the clause-lockstep defect returning. That was two true statements of
a number that had to move together. This is one designation with three owners.
Different failure, same root cause: a fact recorded where nothing makes its
holders agree.

**The fix keeps `MAY be a proper subset` intact — only the OWNERSHIP moves**, from
per-Driver choice to a single binding designation. Core's established pattern for
this shape is `spec.md` line 378, where a reference realization is named
concretely and then bound at SPEC level rather than at implementation level: the
reference realization is where a thing is written down, not who gets to choose it.

### And two fail-safes, because the evidence set is a claim about the world

"Names no non-core plugin has reason to own" is a DERIVED fact, recorded where
nothing re-derives it. It is true of the six today. If some plugin later ships a
`revise.md`, nothing notices and the contract quietly asserts something false. So:

- the designation may be changed only by a propose-change cycle, which makes
  narrowing deliberate and records the reasoning beside the change;
- **adding an operation to core's set does NOT add its name to the designation.**

The second is load-bearing, and it is the MIRROR of the ninth-operation argument
recorded above. Adding a name is safe for MATCHING precisely because matching is
a subset test. It is NOT automatically safe for ARMING, because arming is what
decides whether a stranger's repository gets a hard error. Without this sentence,
core adds a ninth operation with a generic name, it joins the evidence set by
default, and every unrelated plugin shipping that filename begins hard-erroring.

Two questions that sound identical — "is adding a ninth operation safe?" — with
opposite correct answers depending on which half of the predicate is asking. That
is exactly the kind of thing that is easy to miss and expensive to discover.
