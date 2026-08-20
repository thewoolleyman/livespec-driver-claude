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
And <project-root>/.claude-plugin/prose/ holds SOME but not all of the core
    operation prose set
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
> each Driver invents separately. A checkout carrying SOME of that set but not
> all of it MUST be reported as an error naming the missing files, and MUST NOT
> be treated as a non-core project: falling through to step 3 there resolves a
> mid-rename core checkout to its own installed cache, serving released prose to
> a maintainer who is editing its replacement. Because that error is reachable
> during core's own ratified rename cycle, its diagnostic MUST name the step-1
> override and state that the override is consulted first.

## Handling note, revised

If the maintainer ratifies a different marker: Draft 1 stands unchanged
(predicate-independent), Draft 4 stands unchanged for the same reason — it says
"some but not all of the core operation prose set" without naming the arming
subset — and Draft 5 stands unchanged, since it constrains the diagnostic rather
than the predicate. Only Draft 2's Given-line and Draft 3's closing sentence are
marker-specific. That is one more argument for keeping the arming detail (the
core-exclusive six) in the reference realization rather than in the contract.
