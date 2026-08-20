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

**Ratified 2026-08-20 by livespec core's report-only second opinion, with ONE
BINDING CONDITION**: the 1-7 diagnostic MUST name `LIVESPEC_CORE_PLUGIN_ROOT` and
state that it is consulted BEFORE the predicate. Otherwise the amendment
hard-blocks core's OWN ratified rename path — a rename is executed in a worktree
of core, which transits the 1-7 state precisely while driving the
`propose-change`/`revise` operations the predicate gates. The override branch
already returns before the checkout test, so this is one sentence of diagnostic
text; the 1-7 test should assert the diagnostic MENTIONS the override, not merely
that it errors. Core also removed work here: adding a NINTH operation needs no
amendment, because an all-eight-present test is a SUBSET test — only rename or
removal can score 1-7.

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
marker matches core across 22 independent checkouts and nothing else.

**Re-measured 2026-08-20 (333 roots) and the separation held**, with two method
upgrades: core identity is now confirmed by `git remote get-url origin` on all 22
rather than by path inspection, and the ARMING BAND was swept full-host for the
first time — 311 score 0 on the core-exclusive six, 22 score 6, nothing between,
and **zero** roots would hard-error. The count moved 314 -> 333 while the
separation did not, which demonstrates the snapshot-versus-durable distinction
this file asserts below rather than merely claiming it. See
`partial-core-checkout-hole.md` §"Full-host validation of the ARMING BAND". All 292
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

2. **LLOC: the amended predicate does NOT fit. Measured 2026-08-20.**
   `resolve_core_root.py` measures 220 against an ARMED 250 hard ceiling. A
   prototype of the RATIFIED three-way design measures **266** — and **255 even
   without core's required 1-7 diagnostic**, so the predicate does not fit by
   itself either. Extracting the operator-facing text (`_diagnostic`,
   `_mismatch_detail`, `_INSTALL_INSTRUCTIONS`) to a sibling module recovers the
   main file to 213 and was built and RUN, not just counted. Consequence: "land
   the predicate alone as the smallest changeset" is not available at the current
   file size — the split is the entry price for every option, not a cost specific
   to bundling. See `implementation-constraints.md` §"MEASURED: the amended
   predicate does NOT fit". Bundling the adjacent rule-3 `installPath`-existence
   hardening still does not fit — keep it out.

3. **The fix will look like a regression on first contact — and the worktree case
   is the NORMAL case.** See `worktree-resolution.md`: spec ops are tracked-file
   writes run from worktrees by fleet mandate, and worktrees carry no registry
   record. A primary-checkout walk-up in rule 3 takes the affected set from "3
   resolve, 288 hard-fail" to "291 resolve, 0 fail", but will not fit the LLOC
   ceiling alongside the predicate change — so sequencing is an open maintainer
   decision. **Both are now decided** — the precedence rule is primary always
   (`worktree-record-staleness.md`), and the changeset shape is one changeset
   carrying the split, the predicate, its tests, the eight `tun` guards and the
   guard test, with the walk-up as a child (`changeset-shape-decision.md`). 289 project roots
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

## Two independent defects, and the bigger one is not the predicate

| defect | roots affected | failure today |
|---|---|---|
| rule 2 predicate | 291 | SILENT wrong root |
| rule 3 worktree gap | 420 | LOUD `project_not_installed` |

They overlap on 288 roots, where rule 2's silent misresolution MASKS the rule-3
gap. Only 16 of 502 governed project roots on this host hold a registry record of
their own; a primary-checkout walk-up recovers 420, and 66 are genuinely
unprovisioned. The rule-2 defect is the worse KIND of failure — a confident wrong
answer — but the worktree gap is the larger population and is already live. See
`worktree-gap-scale.md`.

## Known blockers that are not the fix

- **`d7d` is not admitted by any dispatch surface.** It carries no
  `intake:triaged` label, so the intake Definition-of-Ready gate never ran and
  `next` ranks nothing. Hand-driving is unaffected; any ranked route is blocked
  until it is triaged. **Triage is DOWNSTREAM of the drive-personally directive,
  not a separate decision** — this repo's dispatcher runs
  `auto_approve_ready: true` with `acceptance_mode: "ai-only"` and a default
  factory, so triaging would route the work to a factory by configured
  automation, which is exactly what the directive forbids. See
  `changeset-shape-decision.md` §Postscript. There is ONE open decision on this
  plan, not two.
- **`tun`'s title has drifted.** Its stated-file-vs-tested-directory
  contradiction was resolved in the WRONG direction (the prose was rewritten to
  match the defective code) in all 8/8 bindings, so a reader may wrongly close it
  as stale. Its real weakness — the directory-only guard that cannot catch a
  misresolved root — is still live in all eight.
  **No core drift to hunt** (verified 2026-08-20): core's prose and spec carry
  ZERO hits for `LIVESPEC_CORE_PLUGIN_ROOT`, `resolve_core_root`, or core-root
  language, so the rewritten-to-match-the-defect text is entirely Driver-owned
  `SKILL.md` content. Nobody needs to sweep core. The mis-title finding belongs
  as a COMMENT ON THE ITEM rather than in session messages, precisely because the
  failure mode is a reader checking the title against the source.
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
| `worktree-resolution.md` | the worktree case is the normal case; rule 3 needs a primary walk-up; the scope fork |
| `worktree-gap-scale.md` | the walk-up recovers 420 of 502 governed roots; the gap is already live and larger than the predicate defect |
| `worktree-record-staleness.md` | worktree install records fossilize (2 of 2 stale); resolves the walk-up precedence fork to **primary always** |
| `changeset-shape-decision.md` | the changeset shape, DECIDED: split + predicate + tests + tun + guard test in one; walk-up as a child |

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

## The 2026-08-20 cross-seat exchange

The `livespec-overseer-foreman` seat routed this defect here rather than filing a
seventh duplicate in this tenant, and carried a second opinion back from livespec
core. Three things entered the plan through it, all recorded in the notes above:

- **Core's ruling on the 1-7 amendment, with its one binding condition** (the
  diagnostic must name the override). See `partial-core-checkout-hole.md`.
- **The clause-lockstep hazard** in the cross-driver port, plus the refinement
  that `contracts.md` already rename-gates the eight-name set, so the minimal fix
  is one appended sentence rather than a new contract section. See
  `cross-driver-blast-radius.md`.
- **The prose-only marker result** from the `unknown` cache build, which also
  retired a proposed `scripts/livespec/schemas/` discriminator. See
  `predicate-justification.md`.

Two claims from that exchange were checked and did NOT survive as stated, which
is worth recording because both were reported confidently:

- A count of "4 of 281 worktrees hold install records" came from a substring grep
  over the whole registry file, which counts paths across EVERY plugin key. Only
  `livespec@livespec` governs core-root resolution, and under that key exactly
  ONE worktree path holds a record. The affected population is 280 of 281.
- A `prose/revise.md` + `scripts/livespec/schemas/` discriminator was offered
  with a passing three-way control. The control was sound and irrelevant: it
  proved separation on TODAY's population, which is exactly what an almost-right
  discriminator does. The schemas half additionally false-negatives on a real
  cache build.

The generalizable lesson, in the routing seat's own words: a grep over a file is
not a query against the structure the code actually reads.
