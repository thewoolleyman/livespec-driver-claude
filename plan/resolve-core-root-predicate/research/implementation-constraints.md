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
