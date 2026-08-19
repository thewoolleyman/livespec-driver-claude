# resolve-core-root-predicate — start here

Front door for this plan's research. Written 2026-08-19, after the notes below
had accumulated and two of them had been corrected in place. If you read only
one file, read this one; it states the current position, not the order it was
discovered in.

Plan epic: `livespec-driver-claude-cezqks`. Requirement carriers:
`livespec-driver-claude-d7d` (the resolver) and `livespec-driver-claude-tun`
(the eight bindings' post-resolve guard).

## The defect, in three sentences

`.claude-plugin/lib/resolve_core_root.py` rule 2 accepts
`<project-root>/.claude-plugin/` as livespec core whenever that directory carries
a `prose/` subdirectory. Every plugin-shipping repo in this family satisfies
that, so rule 2 matches non-core projects and shadows rule 3 — the
`projectPath`-keyed install record, which holds the correct answer. The contract
in `SPECIFICATION/contracts.md` already states the right RULE ("when the governed
project IS the livespec core repo"); only the implementation is wrong.

## The recommendation

Rule 2 should match only when `prose/` carries the complete core operation-prose
set: `critique.md`, `doctor.md`, `help.md`, `next.md`, `propose-change.md`,
`prune-history.md`, `revise.md`, `seed.md`.

**Amended 2026-08-19** — see `partial-core-checkout-hole.md`. The marker alone is
NOT sufficient: rule 2 must treat a partial core prose set (1-7 of the eight) as
an ERROR, not as a decline. A bare all-eight boolean silently falls through to
rule 3 when core's own checkout is mid-rename or partial, and because
`/data/projects/livespec` holds an install record, that resolves to the installed
cache instead of the working tree — trading a loud common defect for a silent
rarer one. The 1-7 band is empty across all 314 measured roots, so arming it as
an error costs nothing.

Four objections were raised and all four fail on measurement — see
`predicate-justification.md`. The one that decides it: this needs NO new core
contract. Core is deliberately agnostic about how a Driver finds it, so there is
nowhere to ratify a bespoke marker; but core ALREADY ratifies the eight-operation
set under propose-change control, so all three Drivers can key off one governed
list with nothing new to keep in sync.

## The numbers that matter

Full-host sweep, re-measured 2026-08-19 at `-maxdepth 5` over `/data/projects`
and `~/.worktrees`, excluding `*/.git/*`, `*/.pi/*` and `*/.livespec-core/*`:

| measurement | value |
|---|---|
| project roots shipping their own `.claude-plugin/prose/` | 314 |
| scoring 8/8 on the marker | 22 |
| scoring 0/8 | 292 |
| scoring anything in between | **0** |

The separation is total, not merely good. All 22 that score 8/8 are genuine core
checkouts — `/data/projects/livespec` plus 21 worktrees OF livespec core — so the
marker matches core across 22 independent checkouts and nothing else. All 292
that score 0/8 are non-core. No candidate anywhere on this host lands in
between, so there is no threshold to tune and no near-miss to worry about.

Of the 292 non-core roots, 3 hold a `livespec@livespec` install record and 289 do
not — which is what drives the post-fix behavior change described below.

## The three things most likely to trip up whoever implements this

1. **The existing test PINS the defect.**
   `tests/hooks/test_resolve_core_root.py:128` builds an EMPTY `prose/` dir and
   asserts `source == "project_checkout"`. Make that fixture core-shaped and it
   stays GREEN under the old predicate — so the clean red is the NEW negative
   test, not the positive one. Coverage is `fail_under = 100` with
   `.claude-plugin/lib` in `source_trees`, so the negative test is required by
   the gate, not optional.

2. **LLOC headroom is about 30 logical lines.** `resolve_core_root.py` measures
   220 against an ARMED 250 hard ceiling. The predicate fits. Bundling the
   adjacent rule-3 `installPath`-existence hardening does not — keep it out.

3. **The fix will look like a regression on first contact.** 289 project roots
   move from a silent wrong answer to a loud `project_not_installed`. That is
   the fix working: those roots were always mis-provisioned and rule 2 was
   masking it. Name it in the changeset description, with the two sanctioned
   remedies (the `LIVESPEC_CORE_PLUGIN_ROOT` override, or installing core for
   that root). See `post-fix-operational-impact.md`.

## Two fixtures worth lifting from real disk state

- A worktree that ships EIGHT files in its own `prose/` and still scores 0/8 —
  same COUNT as core, zero overlap in NAMES. It fails exactly the wrong
  implementations (count-based, size-based) that the naive empty-`prose/` fixture
  lets through.
- ~50 worktrees vendoring a COMPLETE 8/8 core set at
  `<project-root>/.livespec-core/.claude-plugin/prose/`. Rule 2 tests
  `<project-root>/.claude-plugin/` only, so these correctly do not match; a
  fixture should pin that the predicate does not start searching downward.

## Cross-repo: the fix is NOT uniform

All three Drivers carry the rule-2 defect. Only `livespec-driver-claude` has the
`projectPath` concern — Codex enablement is host-wide (one record per host) and
pi consults fixed clone paths, so neither has an array to select wrongly from.
Port the PREDICATE to all three; do NOT port this repo's `projectPath` selection
logic. `livespec-driver-pi` and `livespec-driver-codex` have NOTHING on file in
their own tenants. Routing is the foreman's call; nothing was filed there.

## Known blockers that are not the fix

- **`d7d` is not admitted by any dispatch surface.** It carries no
  `intake:triaged` label, so the intake Definition-of-Ready gate never ran and
  `next` ranks nothing. Hand-driving is unaffected; any ranked route is blocked
  until it is triaged. Triage is an intake decision and was left to the
  maintainer.
- **`tun`'s title has drifted.** Its stated-file-vs-tested-directory
  contradiction was resolved in the WRONG direction (the prose was rewritten to
  match the defective code) in all 8/8 bindings, so a reader may wrongly close it
  as stale. Its real weakness — the directory-only guard that cannot catch a
  misresolved root — is still live in all eight.
- **`6lc` is already fixed** and should be closed as such, not reworked. Rule 3
  selects by `projectPath` today, proven with a control.

## The notes

| file | what it answers |
|---|---|
| `defect-and-fix-shape.md` | the defect at the line, the rule-3 control, the four surfaces to touch |
| `cross-driver-blast-radius.md` | all three Drivers; why the fix is not uniform; marker valid on all three resolved core paths |
| `predicate-justification.md` | why the eight-file set, and why not the alternatives |
| `post-fix-operational-impact.md` | what changes for operators at merge, and why it is not a regression |
| `implementation-constraints.md` | the three repo gates that bind the fix |
| `draft-spec-text.md` | drafted scenario + contract wording, pre-validated, NOT filed |
| `partial-core-checkout-hole.md` | the refutation that amended the recommendation: arm the 1-7 band as an error |

## Corrections already folded in

Two errors were found by re-auditing this plan's own measurements, and both are
corrected in the notes above rather than left standing:

- The blast radius was first reported as SEVEN worktrees. The sweep behind it
  used `find -maxdepth 3`, which misses the nested
  `~/.worktrees/<repo>/<branch>` layout. The corrected figure is 292 non-core
  project roots. (`post-fix-operational-impact.md` records 291/288 from the
  first corrected sweep; this file's 292/289 is a later re-measure. The
  difference is one worktree created by another session mid-day, not a third
  method error — the host's worktree set changes while work proceeds, so treat
  any absolute count here as a snapshot and the SEPARATION result, which is
  method-independent, as the durable finding.)
- Earlier handoffs said `d7d` would be "an ordinary `drive` dispatch" if the
  drive-personally directive were lifted. It would not — see the triage blocker
  above.

A third error was caught before it reached the notes: a probe reporting 0/8 for
pi's package-clone paths was a ZSH artifact (an unquoted `for f in $VAR` does not
word-split in zsh; it iterates once over the joined string). Any future sweep
here should use Python or a literal list. Shipped scripts are unaffected — every
`.sh` under `.claude-plugin/` and `dev-tooling/` is `#!/usr/bin/env bash`.
