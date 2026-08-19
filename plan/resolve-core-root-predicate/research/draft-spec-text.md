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
