---
topic: core-root-predicate-identifies-livespec-core
author: claude-opus-5
created_at: 2026-08-21T09:36:01Z
---

## Proposal: Pin that a non-core project checkout is rejected by core-root resolution

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Adds the missing negative scenario pinning that core-root resolution does NOT use `<project-root>/.claude-plugin/` when that checkout is not livespec core, and sharpens the existing positive checkout scenario so its Given-block states an observable rather than an unfalsifiable identity claim. The negative case was never pinned, which is how a `prose/`-directory test -- satisfied by every plugin-shipping repo in this family -- passed as a faithful realization of the rule and silently shadowed the install-record step that held the right answer.

### Motivation

Filed from plan `resolve-core-root-predicate` (ledger epic
livespec-driver-claude-cezqks), which commissioned the fix now merged as PR 570
at master bb025e5. The defect it closed: `.claude-plugin/lib/resolve_core_root.py`
rule 2 accepted `<project-root>/.claude-plugin/` as livespec core whenever that
directory carried a `prose/` subdirectory. Every plugin-shipping repo in this
family satisfies that, so rule 2 matched non-core projects and shadowed rule 3 --
the `projectPath`-keyed install record, which holds the correct answer.

`contracts.md` already stated the right RULE ("when the governed project IS the
livespec core repo"). Only the implementation was wrong, so no CORRECTION is
owed to the existing contract text. What was missing was a scenario pinning the
negative case, which is why the defect survived: a broken predicate satisfied
every scenario on file.

Measured full-host on 2026-08-19 and re-measured on 2026-08-20 across 333
project roots shipping their own `.claude-plugin/prose/`: 22 score the complete
core operation prose set and 311 score none of the core-exclusive names, with
NOTHING in between. All 22 were confirmed to be genuine livespec core checkouts
by `git remote get-url origin`. The separation is total, so there is no
threshold to tune and no near-miss.

The implementation is already merged and CI-green on master, and both
requirement carriers (livespec-driver-claude-d7d and -tun) are closed. This
proposal exists so the ratified behavior lives in the spec rather than only in
plan notes and in code. Because the behavior is already implemented, no
spec-to-impl commitment is declared: nothing is owed after this proposal is
revised in beyond the atomic `tests/heading-coverage.json` co-edit named above.

### Proposed Changes

`scenarios.md` today carries four core-root resolution scenarios: the operator
override, the governed-project checkout, install-record selection, and the
`projectPath` mismatch diagnostic. None of them pins the case that broke. This
proposal adds the missing negative scenario and sharpens the existing positive
one so that neither can be satisfied by the discriminator that failed.

A new `## Scenario: core-root resolution rejects a non-core project checkout`
MUST be added, to sit directly after
`## Scenario: core-root resolution falls back to the governed-project checkout`:

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

This scenario MUST remain predicate-independent: it states the required
behavior -- that the project checkout is not used when that checkout is not
core -- and MUST NOT name the marker used to decide it. It is the regression
pin, not the design, and it stays valid whichever discriminator a realization
adopts.

The existing `## Scenario: core-root resolution falls back to the
governed-project checkout` SHOULD have its Given-block replaced, because its
present wording ("the governed project IS the livespec core repo loaded with
--plugin-dir .") is true but states no observable, leaving a reader
implementing from it to invent the test:

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And <project-root>/.claude-plugin/prose/ carries the complete core operation
    prose set -- the dev / dogfooding case, loaded with --plugin-dir .
When a binding resolves <core-root>
Then it uses <project-root>/.claude-plugin/
```

The `When`/`Then` blocks of that scenario MUST NOT change; only the `Given`
block gains the observable. The ordering of the three resolution steps MUST NOT
change: `/data/projects/livespec` holds an install record of its own, so
promoting the install-record step above the checkout step would resolve core to
its installed cache instead of the working checkout and defeat `--plugin-dir .`
dogfooding entirely.

Per this repo's clause-to-scenario linking, `tests/heading-coverage.json` MUST
gain one entry for the new scenario heading, co-edited atomically with the
scenario itself. That file lies outside `<spec-target>/` and so is not listed
in this proposal's target specification files.

## Proposal: An incomplete core checkout must error rather than fall through, and say how to recover

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Adds two scenarios covering the third outcome of core-root step 2: a checkout carrying evidence of being livespec core but NOT the complete operation prose set MUST fail, naming the missing files, and MUST NOT fall through to the install record; and the resulting diagnostic MUST name LIVESPEC_CORE_PLUGIN_ROOT and state that the override is consulted BEFORE the completeness check. The second is livespec core's binding ratification condition, without which the error band hard-blocks core's own rename path.

### Motivation

Filed from plan `resolve-core-root-predicate` (ledger epic
livespec-driver-claude-cezqks). This half of the design was NOT in the original
recommendation. It was added by a refutation recorded in the plan's
`partial-core-checkout-hole.md`: a bare all-present boolean silently falls
through to rule 3 when core's own checkout is mid-rename or partial, and
because `/data/projects/livespec` holds an install record, that resolves to the
installed cache instead of the working tree -- trading a loud common defect for
a silent rarer one.

Arming the band costs nothing measurable. The in-between score band is empty
across all 333 roots swept full-host on 2026-08-20, and ZERO roots anywhere on
that host would hard-error.

livespec core's report-only second opinion RATIFIED the amendment on 2026-08-20
with ONE BINDING CONDITION: the incomplete-checkout diagnostic MUST name
LIVESPEC_CORE_PLUGIN_ROOT and state that the override is consulted BEFORE the
predicate, otherwise the amendment hard-blocks core's own rename path. That
condition is the entire reason the second scenario exists as a separate
assertion. Filing it here is what keeps the condition from living only in this
plan's notes and in core's report-only record, where nothing in either repo's
spec would require it and a later revision could drop it while still satisfying
every ratified scenario.

The behavior is implemented and merged (PR 570, master bb025e5): the resolver
returns a `core_checkout_incomplete` outcome naming the missing files, and its
guidance text names the override and states that it is consulted first. Both
are covered by tests. No spec-to-impl commitment is declared, for that reason.

### Proposed Changes

Matching livespec core MUST require the COMPLETE core operation prose set. A
checkout that carries EVIDENCE of being core while NOT carrying the complete
set MUST be reported as an error, and MUST NOT be treated as a non-core project.
Two scenarios pin this, both to sit directly after the non-core rejection
scenario proposed alongside this one.

`## Scenario: an incomplete core checkout fails rather than falling back`:

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

The final `And` carries the weight and MUST NOT be dropped as redundant.
Falling through is the SILENT failure this scenario exists to prevent: a core
checkout mid-rename would otherwise resolve to its own installed cache and
serve the OLD released prose to a maintainer editing its replacement. A
scenario stating only that resolution fails would leave a conforming
realization free to DECLINE instead of ERROR, which is the same silent
fall-through by another name.

`## Scenario: the incomplete-checkout diagnostic names the recovery`:

```gherkin
Given resolution has failed because the core prose set is incomplete
When the diagnostic is emitted
Then it names LIVESPEC_CORE_PLUGIN_ROOT
And it states that the override is consulted BEFORE the completeness check
```

This MUST be a separate scenario rather than another `And` on the one above. A
diagnostic that errors correctly but says nothing about recovery satisfies the
first scenario completely; only a separate assertion pins the text. Without it
the error band hard-blocks livespec core's OWN ratified rename path -- a rename
is executed in a worktree of core, which transits the incomplete state
precisely while driving the `propose-change` and `revise` operations this
predicate gates, leaving the maintainer unable to run the `revise` that
completes the rename. The override already returns before the completeness
check, so the recovery exists; the requirement is that the diagnostic SAYS so.

Both scenarios MUST stay free of any count. Neither names how many prose files
constitute the complete set, and neither names which subset arms the error --
see the companion contracts.md proposal for why the designation is delegated
rather than restated here.

Per this repo's clause-to-scenario linking, `tests/heading-coverage.json` MUST
gain one entry per new scenario heading, co-edited atomically with the
scenarios. That file lies outside `<spec-target>/` and so is not listed in this
proposal's target specification files.

## Proposal: Name what decides that a project checkout IS the livespec core repo

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Adds a clause to contracts.md §"Core-root resolution" requiring step 2's condition to be decided by a marker livespec core carries and a non-core plugin does not, explicitly ruling out the presence of a `prose/` directory. The clause requires the complete operation prose set for a MATCH, requires an error naming the missing files when evidence of core is present but the set is incomplete, and binds the evidence designation to be single-sourced and identical across Drivers while hardcoding no count.

### Motivation

Filed from plan `resolve-core-root-predicate` (ledger epic
livespec-driver-claude-cezqks). `contracts.md` §"Core-root resolution" already
states the correct rule for step 2, so no correction is owed to it. What is
missing is a sentence naming what the condition is decided BY -- the absence
that let a `prose/`-directory test be written and pass review as a faithful
realization of "the governed project IS the livespec core repo".

The wording here is the product of two corrections reported by livespec core's
seat before either side was filed, both recorded in the plan's
`draft-spec-text.md`.

The first is the count trap. Earlier drafts said a checkout "carrying SOME of
that set but not all of it" must error, while the implementation arms the error
band on the core-exclusive names only. Those disagree demonstrably -- a
checkout shipping only `help.md` and `next.md` declines in code while that
sentence says it must error -- and the disagreement would have survived review,
because each sentence is true in its own right and no reviewer comparing either
against its neighbours finds a contradiction. It is not a wrong claim; it is two
right claims that must move together, recorded as if independent. That is the
clause-lockstep defect this amendment exists to prevent, reintroduced by its own
fix. The clause above therefore states that the error arms on EVIDENCE OF CORE
and delegates which names those are, while binding the constraint that generic
names must not be designated.

The second is ownership. An earlier draft called the evidence names "the
reference realization's to designate", which in core's own vocabulary reads as
a per-Driver choice, since core names three reference Drivers. The fix keeps
`MAY be a proper subset` intact and moves only the OWNERSHIP, to a single
binding designation.

Also recorded so nobody re-derives it: core carries no live core-root
resolution text of its own -- zero occurrences of LIVESPEC_CORE_PLUGIN_ROOT or
resolve_core_root anywhere under core's SPECIFICATION or its eight prose files
-- so this clause has no counterpart in core to keep in sync, and no core sweep
is owed. The behavior is implemented and merged (PR 570, master bb025e5), so no
spec-to-impl commitment is declared.

### Proposed Changes

A sentence naming what "IS the livespec core repo" is decided BY MUST be added
to `contracts.md` §"Core-root resolution", after the numbered list and before
the "This resolution order is load-bearing" paragraph, so that a future
realization cannot drift back to an almost-right discriminator:

> Step 2's condition -- that the governed project IS the livespec core repo --
> MUST be decided by a marker that livespec core carries and a non-core plugin
> does not. The presence of a `prose/` directory is NOT such a marker: every
> plugin in this family ships harness-neutral prose under its own
> `.claude-plugin/prose/`, so testing the directory alone matches any
> plugin-shipping consumer and pre-empts step 3, which holds that consumer's
> correct answer. The marker MUST distinguish livespec core from a repo that
> merely ships a plugin with prose. The reference realization requires the
> complete set of core operation prose files -- one per operation named in
> livespec core's `contracts.md` §"Plugin distribution" -- which is a
> change-controlled core contract rather than a marker each Driver invents
> separately. MATCHING core requires the COMPLETE set. A checkout that carries
> evidence of being core -- operation prose whose names no non-core plugin has
> reason to own -- while NOT carrying the complete set MUST be reported as an
> error naming the missing files, and MUST NOT be treated as a non-core
> project: falling through to step 3 there resolves a mid-rename core checkout
> to its own installed cache, serving released prose to a maintainer who is
> editing its replacement. Which names carry that evidence is designated ONCE
> and binds every realization; the designation MUST be identical across
> Drivers, and MAY be a proper subset of the operation set. Names generic
> enough that a consumer plugin might legitimately own one MUST NOT be
> designated, or a single filename collision turns "correctly declines" into
> "hard error" in a repository that has nothing to do with livespec. The
> designation MAY be changed only by a propose-change cycle, and adding an
> operation to the set above does NOT add its name to the designation. Because
> that error is reachable during core's own ratified rename cycle, its
> diagnostic MUST name the step-1 override and state that the override is
> consulted first.

The clause deliberately hardcodes NO COUNT, and that is load-bearing rather
than stylistic. The RULE belongs in the contract because the rule is what was
violated; the exact evidence names belong with the reference realization so the
contract does not enumerate core's operations a second time. Core already
enumerates them, under propose-change control, at its `SPECIFICATION/spec.md`
§"livespec defines eight spec-side sub-commands", which is the sentence the
marker actually reads.

The clause states the designation MAY be a proper subset of the operation set
and MUST be identical across Drivers. Those two MUST move together and MUST NOT
be weakened independently: core has THREE reference realizations
(`livespec-driver-claude`, `livespec-driver-codex`, `livespec-driver-pi`), so a
per-Driver designation would let the SAME partial core checkout hard-error on
one runtime and fall silently through to rule 3 on another -- producing a
diagnostic reproducible from only some operators' seats, which neither operator
can settle from their own.

The sentence "adding an operation to the set above does NOT add its name to the
designation" MUST NOT be dropped as redundant with the subset rule. Adding a
name is safe for MATCHING precisely because matching is a subset test, so a
superset still matches and a ninth operation needs no amendment; only rename or
removal can produce a partial score. It is NOT automatically safe for ARMING,
because arming decides whether a stranger's repository gets a hard error.
Without that sentence, core adds a ninth operation with a generic name, it
joins the evidence set by default, and every unrelated plugin shipping that
filename begins hard-erroring with nobody having decided anything.
