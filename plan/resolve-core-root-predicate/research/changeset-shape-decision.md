# The changeset shape, decided

Eleventh research note for plan `resolve-core-root-predicate`. Decided
2026-08-20.

`worktree-resolution.md` §"Scope consequences" framed a three-way fork and called
it "the maintainer's". Every input it lacked has since been measured, and this
repo's `CLAUDE.md` §"Decision authority" is explicit that a question answerable
with a recommendation is a finding rather than a maintainer question. So this
note decides it and records the reasoning. It remains open to objection; it is
not open as a question.

## The decision

**One changeset carrying the file split, the three-way predicate, its four tests,
all eight `tun` guards, and the guard test. The rule-3 primary walk-up becomes a
child of this plan, landing second.**

## Why the original fork collapsed

The fork was:

1. predicate alone — smallest, fits the ceiling
2. both together — requires splitting the file first, materially bigger
3. predicate now, walk-up as a child

Option 1's stated advantage does not exist. Measured
(`implementation-constraints.md`): the ratified three-way predicate makes the
resolver **266 LLOC against an ARMED 250 hard ceiling**, and **255 even with
core's required diagnostic stripped**. The predicate overruns BY ITSELF.
Extracting the operator-facing text to a sibling module brings the main file to
213, and that split was built and run, not merely counted.

So the file split is the entry price for EVERY option, not a cost specific to
bundling. Once that is true, option 1 and option 2 differ only by what rides
along with a changeset that is already splitting a file.

## Why `tun` rides along rather than following

Three measurements, all in `defect-and-fix-shape.md`:

- **It is free on every gate.** All eight guards replaced, then
  `check-plugin-structure` exit 0 and full `just check` green, `e2e-cli`
  unmodified. `file_lloc` measures only `.py`, so eight bash-in-markdown guards
  cost nothing against the ceiling the resolver is fighting.
- **It is one uniform substitution.** All eight guard blocks hash identically.
  This is not eight judgement calls.
- **Deferring it leaves the diagnostic silent for the NEXT regression.** The
  guard's failure is not that it is wrong about today's defect; it is that it
  cannot distinguish the case it exists to catch, so a misresolution exits 0,
  the guard reads clean, and the failure surfaces later as a bare
  file-not-found with nothing pointing at resolution. Fixing rule 2 while
  leaving that in place means the next predicate regression — from a rename, a
  port, a refactor — is equally silent.

Against that, the only argument for deferring was changeset size, which is the
argument the LLOC measurement just removed.

## Why the guard test rides along too

`defect-and-fix-shape.md` establishes that nothing under `tests/` or
`dev-tooling/` exercises the guards at all, and that a BROKEN guard passes
`just check` exactly as cleanly as a correct one. That is how the current guard
survived wrong in all eight copies for its entire existence.

A test was prototyped: extraction works on 8 of 8, three fixture roots give 24
assertions, and it scores **16 failures against the shipped guards and 0 against
the patched ones**. Roughly forty lines.

Landing `tun` without it means shipping a change whose only verification is a
table in a research note. It also leaves the drift hole open: nothing enforces
that the eight guards stay identical, which is precisely the failure mode that
produced this plan.

## Why the walk-up does NOT ride along

It is the one thing that genuinely does not fit. It needs a `git` subprocess, its
failure handling, and a precedence rule, against a file that will sit at 213
after the split — inside the hard ceiling but with the 200 soft ceiling already
exceeded and a standing refactor warning.

Its precedence question is no longer open (`worktree-record-staleness.md`: primary
always), and its value is measured and large (`post-fix-operational-impact.md`:
it rescues all 415 hard-failing governed roots, residual zero). So it is ready to
be a child — it simply is not part of this changeset.

**Accepting the interval deliberately.** Between the two changesets, spec-side
operations from consumer worktrees fail loudly with `project_not_installed`. That
interval is real and was the reason option 3 was called "not free". It is the
right trade anyway: a loud, correctly-diagnosed failure with two documented
remedies beats the silent wrong answer those roots get today, and the
`LIVESPEC_CORE_PLUGIN_ROOT` override is one step. The changeset description must
name the behaviour change and both remedies — that requirement is unchanged and
is the highest-risk part of the merge.

## The spec change

File the `propose-change` alongside this changeset, not before it. Use Drafts 1,
2, 4 and 5 plus Draft 3's amended contract sentence from `draft-spec-text.md` —
noting that note's staleness section: Drafts 4 and 5 exist because the earlier
drafts predate the three-way rule and core's binding condition, and Draft 5 is
what keeps that condition from living only in plan notes.

## What this does not decide

Whether the maintainer implements it personally. The ledger records that
`livespec-driver-claude-d7d` is factory-ineligible BY DIRECTIVE — the maintainer
stated they intend to drive this track — and that directive is specific,
by-name, and about authorship rather than about gating an engineering call.
Nothing here lifts it. This note decides the SHAPE so that whoever does implement
is not re-deciding it; the routing question is separate and is the one genuine
gate left on this plan.

Cross-repo routing likewise stays the foreman's, unchanged.

## Order of work, if it helps

1. Extract `_diagnostic`, `_mismatch_detail`, `_INSTALL_INSTRUCTIONS` to a
   sibling module. Pure move; suite stays green.
2. Stage the resolver negative test ALONE — it is the only clean red (16 of 18
   existing tests are untouched, and the core-shaped fixture repair is a no-op
   under the old predicate). Commit.
3. `--amend` with the three-way predicate, its union member, and the diagnostic
   naming the override. Suite goes 19 green.
4. Add the 1-7 test and the diagnostic-text test (four predicate tests total —
   the fourth is what pins core's binding condition).
5. Replace the eight guards; add the guard test.
6. File the propose-change.


## Postscript: triage is DOWNSTREAM of the directive, not a second decision

Every handoff on this plan has listed two things waiting on the maintainer:
triage `d7d`, and choose the changeset shape. The shape is decided above. The
triage item turns out not to be independent, and the reason is mechanical rather
than procedural.

`.livespec.jsonc` §`dispatcher` on master:

    "auto_approve_ready": true,
    "acceptance_mode": "ai-only",
    "wip_cap": 10,
    "factories": { "hp": ..., "vps": ... },
    "default_factory": "hp"

Two of the three policy levers are deliberately off their safe defaults, and the
block's own comment says so in terms: ready work is "ADMITTED and ACCEPTED
without a human valve".

So labelling `d7d` `intake:triaged` does not merely make it visible to `next`. It
makes it admissible, `auto_approve_ready` carries it pending-approval -> ready
with no human, and the dispatcher can hand it to the `hp` factory. That is
precisely the outcome the standing directive forbids: the ledger records `d7d` as
factory-ineligible BY DIRECTIVE because the maintainer stated they intend to
drive this track personally.

**Triage would therefore route the work away from the person who reserved it, by
configured automation, without anyone deciding to.** That is not a gate this plan
invented for caution; it is a real coupling in this repo's configuration.

Three consequences worth stating plainly:

1. **There is ONE open decision on this plan, not two.** The directive is
   upstream; triage follows from it mechanically. Any handoff listing them as
   separate items is overstating what is outstanding.
2. **Triage is safe the moment the directive is lifted, and not before.** If the
   maintainer lifts it, `d7d` becomes "an ordinary `drive` dispatch" exactly as
   the epic already says — triage is then the enabling step rather than a
   separate judgement.
3. **This is why the earlier deferral was right, retroactively.** The epic said
   "triage is an intake decision and was deliberately left to the maintainer"
   without saying why. The why is this coupling. Recording it means the next
   session does not have to re-derive it, and does not mistake it for excess
   caution under a decision-authority rule that would otherwise say self-resolve.

Researched rather than assumed: the dispatcher block was read on master, and the
`auto_approve_ready` / `acceptance_mode` semantics are the ones its own inline
comment documents, citing livespec `contracts.md` §"The three policy settings".
