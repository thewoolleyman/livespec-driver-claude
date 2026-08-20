# Gates that bind the fix

Fifth research note for plan `resolve-core-root-predicate`. Read
`predicate-justification.md` for the marker and `post-fix-operational-impact.md`
for what changes after merge. This note records three repo gates that constrain
HOW the fix may be written. None is visible from the defect report, and one of
them has very little headroom.

Measured 2026-08-19 on `master`.

## 1. LLOC headroom is ~30 logical lines, and the hard gate is ARMED

`pyproject.toml` sets `file_lloc_hard_gate = true` (the Phase-2 flip under fleet
epic `livespec-i5ebqd`), which hard-gates this repo's whole git-derived tree.
Current measurement:

```
.claude-plugin/lib/resolve_core_root.py  lloc=220  soft_ceiling=200  hard_ceiling=250
```

The resolver is ALREADY over the 200 soft ceiling and carries a standing
refactor warning. The hard ceiling of 250 is what fails the build, so the fix has
roughly **30 logical lines of headroom** in that file.

**MEASURED 2026-08-20 AND THIS IS WRONG FOR THE AMENDED DESIGN — see the section
at the end of this note. The three-way predicate does NOT fit. Prototyped, it
measures 266 against the 250 hard ceiling.** The paragraph below was written for
the two-way boolean and remains true only of that.

The recommended predicate fits comfortably: a module-level tuple of the eight
prose filenames plus a small `all(...)` helper is on the order of 4-6 logical
lines. What does NOT fit is bundling adjacent hardening into the same change —
for example also verifying that rule 3's returned `installPath` exists and
carries prose (the adjacent gap noted at the end of
`predicate-justification.md`). That is a second reason, beyond scope discipline,
to keep the adjacent gap out of this fix.

If the implementation does need more room, the file is 337 physical lines across
11 functions with 63 lines of docstring, and the docstrings are load-bearing
(they are what stopped the positional defect from being reintroduced). Extracting
the diagnostic-text block rather than trimming prose is the shape of refactor to
prefer. Note the sibling `.claude/hooks/livespec_footgun_guard.py` is also over
the soft ceiling at 202, so this is a known repo-wide condition, not a surprise
specific to this file.

## 2. Coverage is `fail_under = 100`, and this file is in scope

`pyproject.toml` sets `fail_under = 100` and names
`source_trees = [".claude/hooks", ".claude-plugin/hooks", ".claude-plugin/lib"]`.
`.claude-plugin/lib` is where the resolver lives, so **every new branch the
predicate introduces must be covered by a test** or `check-coverage` fails.

Practically this means the negative test is not optional-nice-to-have; it is
required by the gate. A predicate written as `all(...)` over a tuple has one
branch that must be exercised both ways, which the positive (core-shaped
fixture) and negative (non-core prose) tests together satisfy. Both are already
named in the plan's scope event as part of `livespec-driver-claude-d7d`.

There is also `check-per-file-coverage` and `check-check-coverage-incremental`
in the CI matrix, so a shortfall surfaces per-file rather than only in aggregate.

## 3. The structural gate does NOT constrain the rule-2 narrative

Worth stating because it is the natural worry when touching all eight
`SKILL.md` files. `check-plugin-structure` consumes
`livespec_dev_tooling.driver_checks.plugin_structure` (Claude profile:
`_plugin_structure_claude`). Its SKILL.md invariants cover only the FENCED
WRAPPER INVOCATION lines:

- the fenced wrapper invocation MUST use `$LIVESPEC_CORE_ROOT`
- it MUST NOT use `uv run`

The module contains no assertion about `prose`, about the core-root resolution
narrative, or about the post-resolve guard — verified by searching its source for
`prose`, `core_root`, `resolve_core_root` and `CLAUDE_PLUGIN_ROOT` (zero hits for
each except the two invocation rules above).

So the eight bindings' rule-2 wording and their `[ ! -d "$LIVESPEC_CORE_ROOT/prose" ]`
guard can both change freely, with no gate update required, as long as the
wrapper invocation lines themselves are left alone. That removes the main
perceived cost of folding `livespec-driver-claude-tun` into the same changeset.

## 4. Not a constraint: the e2e-cli tier

`tests/e2e-cli/` was checked for any dependence on core-root resolution or on a
`prose/` fixture: no references. The mock-tier harness does not exercise rule 2,
so it needs no fixture change.

## Consequence for the changeset

All three real constraints point the same way: keep the fix narrow. The
predicate change plus its two tests fits the LLOC headroom and satisfies the
coverage gate; the eight-binding `tun` surface is unconstrained by the structural
gate and can ride along; and the adjacent rule-3 `installPath` hardening should
stay out, on both scope and LLOC grounds.


## MEASURED: the amended predicate does NOT fit (2026-08-20)

This note, the plan README and two ledger handoff entries all assert that the
predicate fits the ceiling. That was assessed for the TWO-WAY boolean. The design
has since been amended twice — `partial-core-checkout-hole.md` made it three-way
with a new `CoreRootUnresolved` kind, and core's second opinion attached a BINDING
CONDITION that the 1-7 diagnostic must name `LIVESPEC_CORE_PLUGIN_ROOT`. Nobody
had measured the amended shape. Prototyped and measured today.

The prototype is a faithful implementation of the ratified design: the eight-file
and core-exclusive-six tuples, a three-way `_core_checkout_outcome(...)` helper, a
`core_checkout_incomplete` union member, the rewired rule-2 branch, and the
diagnostic carrying core's required override sentence. It was smoke-tested and
behaves correctly on all three cases (core checkout resolves to itself; a
prose-shipping non-core repo reaches rule 3 and returns the right cache; a
synthetic 7/8 checkout errors and names both the missing file and the override).

| variant | LLOC | vs 250 hard |
|---|---|---|
| shipped today | 220 | passes |
| + predicate, tuples, union kind (NO diagnostic) | 255 | **FAILS by 5** |
| + core's required 1-7 diagnostic | **266** | **FAILS by 16** |

Cost decomposition: predicate + tuples + union kind = 35 LLOC; the 1-7 diagnostic
= 11 LLOC; total 46 over the shipped file.

**The second row is the one that matters.** Even stripping core's binding
condition entirely — which is not an option, since without it the amendment
hard-blocks core's own rename path — the predicate alone still overruns. So
"land the predicate by itself as the smallest changeset" is NOT available at the
current file size. That was believed to be the cheap option in every handoff so
far.

### The refactor this note already recommends does work

This note says "extracting the diagnostic-text block rather than trimming prose is
the shape of refactor to prefer." Measured: moving the three operator-facing text
surfaces — `_diagnostic()` (40), `_mismatch_detail()` (25) and
`_INSTALL_INSTRUCTIONS` (4) — into a sibling module gives:

| file | LLOC | status |
|---|---|---|
| `resolve_core_root.py` | 213 | passes the 250 hard gate, 37 headroom |
| `_resolve_core_root_text.py` (new) | 60 | comfortable |

The split was BUILT and RUN, not just counted: a sibling module in the same
directory imports fine under direct script invocation, which is how the bindings
call it (`python3 "$LIVESPEC_CORE_ROOT/scripts/bin/..."` for core; the Driver's
own resolver is invoked the same way from `${CLAUDE_PLUGIN_ROOT}/lib/`). The
installer flattens `.claude-plugin/` into the plugin root and copies the whole
tree, so `lib/` keeps both files and the standard-library-only constraint is
unaffected — the sibling imports nothing new.

The main file stays above the 200 SOFT ceiling at 213, so the standing refactor
warning persists. That is a warning, not a gate.

### What this changes for the maintainer's changeset-shape decision

`worktree-resolution.md` framed the fork as: (1) predicate alone, smallest and
fits; (2) both together, requires splitting the file first and is therefore
materially bigger; (3) predicate now, walk-up as a child. Option 1's stated
advantage does not survive measurement — the split is required for the predicate
BY ITSELF, so "split the file first" is no longer a cost specific to option 2. It
is the entry price for any of the three.

That does not obviously favour any option, and the choice remains the
maintainer's. It does remove the reason to prefer option 1 on size grounds, and
it means whoever implements should expect a two-file changeset from the start
rather than discovering the ceiling partway in.

### Scope of this measurement

Prototype only, built in a scratch directory and NOT proposed as an
implementation. Nothing was changed in `.claude-plugin/`. The existing unit tests
were NOT run against the prototype — the three checks above are behavioural smoke
tests plus LLOC counts, which is what the question ("does it fit?") required.
`d7d` remains unimplemented and untriaged.


## The Red->Green ritual, executed against the prototype (2026-08-20)

The plan, the epic scope event and both ledger handoff entries all give the same
red-green guidance: `test_governed_project_that_is_core_uses_its_own_checkout`
(line 128) PINS the defect with an empty `prose/` fixture; making that fixture
core-shaped stays GREEN under the OLD predicate, so the clean red is the NEW
negative test. That was reasoned, not run. It has now been run, against the
prototype measured in the section above.

### 1. The existing suite under the new predicate: exactly one failure

Running the shipped `tests/hooks/test_resolve_core_root.py` UNCHANGED against the
prototype:

    17 passed, 1 failed

The single failure is `test_governed_project_that_is_core_uses_its_own_checkout`
— the test the plan identifies. Its empty-`prose/` fixture now correctly scores
0/8, declines rule 2, falls through to rule 3, and lands on `registry_absent`
because the fixture builds no registry.

**17 of 18 pass unchanged**, which is the assurance the plan did not have: the
predicate change has no collateral effect on registry reading, `projectPath`
selection, the positional control, or any diagnostic branch. The blast radius
inside the suite is exactly the one test that pins the defect.

### 2. The guidance is correct — demonstrated in both directions

With the fixture made core-shaped (all eight prose files written) AND a new
negative test added (a consumer repo shipping `foreman.md`, `overseer.md`,
`supervise-plan.md`, plus a matching install record, asserting
`source == "install_record"`):

| suite | against SHIPPED (old) | against PROTOTYPE (new) |
|---|---|---|
| core-shaped fixture + new negative test | **18 passed, 1 failed** | **19 passed** |

The one failure under the old predicate is the NEW negative test, and it fails on
exactly the defect:

    - install_record
    + project_checkout

So the ritual is clean and the plan's advice holds precisely:

- Making the fixture core-shaped is a NO-OP under the old code — it passes
  either way, and is therefore not the red.
- The new negative test is the ONLY red, and it is red for the right reason.
- Adding the predicate turns it green with nothing else to fix.

Whoever implements can stage the negative test alone, confirm one failure,
commit, then `--amend` with the resolver change and confirm 19 green. That
satisfies `check-red-green-replay` and the `fail_under = 100` coverage gate needs
the three predicate branches exercised: 8/8 matches (the core-shaped fixture),
0/8 declines (the new negative test), and 1-7 errors (a third test, which the
suite does not yet have).

### Scope

Measured against the scratch prototype from the section above. Nothing in
`.claude-plugin/` or `tests/` was changed; the modified suites were copies in a
scratch directory. `d7d` remains unimplemented and untriaged.
