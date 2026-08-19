# What changes for operators when the rule-2 fix lands

Fourth research note for plan `resolve-core-root-predicate`. Read
`predicate-justification.md` first for the marker and the evidence behind it.
This note records the one BEHAVIOR CHANGE the fix produces that is not simply
"the bug stops happening", so it is not mistaken for a regression after merge.

All measurements 2026-08-19.

## The blast radius is larger than the three-repo table

`defect-and-fix-shape.md` measured five family checkouts;
`cross-driver-blast-radius.md` measured three Drivers. Neither swept the whole
host. A full scan of every project under `/data/projects` finds exactly three
repos shipping `.claude-plugin/prose/` — `livespec` (8/8 on the marker),
`livespec-orchestrator-beads-fabro` (0/8) and `livespec-overseer` (0/8) — so the
earlier table was complete for repos.

It was NOT complete for project roots. A git worktree is its own project root,
and a worktree of an affected repo carries the same `.claude-plugin/prose/`.

**CORRECTED 2026-08-19, after this note first landed.** The original sweep used
`find -maxdepth 3`, which reaches `~/.worktrees/<name>/.claude-plugin/prose` but
NOT the nested `~/.worktrees/<repo>/<branch>/.claude-plugin/prose` layout that
most of this host's worktrees actually use. It reported SEVEN affected worktrees.
Re-swept at `-maxdepth 5`:

    affected project roots : 291
      with install record  :   3
      without              : 288

The three with records are `/data/projects/livespec-orchestrator-beads-fabro`,
`/data/projects/livespec-overseer`, and one worktree
(`.worktrees/livespec-overseer/spec-parked-delivery-routing`). Everything else —
288 project roots, overwhelmingly `livespec-overseer` and
`livespec-orchestrator-beads-fabro` worktrees — has none.

Every one of the 291 scores 0/8 on the marker, so the fix correctly declines rule
2 in each. The discrimination result is unchanged and in fact strengthened by the
larger sample: still zero near-misses across 291 candidates.

One of those roots is a natural adversarial case worth keeping:
`.worktrees/livespec-orchestrator-beads-fabro/janitor-bd-ib-n94z` ships EIGHT
files in its own `.claude-plugin/prose/` and still scores 0/8 — same file COUNT
as core, zero overlap in file NAMES. A predicate that counted prose files rather
than naming them would match it. That is a live argument for naming the eight.

### A vendoring convention that does NOT false-match

The same sweep found ~50 directories carrying a complete 8/8 core prose set at
`<project-root>/.livespec-core/.claude-plugin/prose/` — janitor worktrees vendor
core there. These do NOT affect rule 2, which tests `<project-root>/.claude-plugin/`
only, and their own top-level `.claude-plugin/prose/` scores 0/8. Recorded so a
later reader does not rediscover them and mistake them for false positives.

## The behavior change: none of those worktrees has an install record

Checked against `~/.claude/plugins/installed_plugins.json`: 288 of the 291
affected project roots have no `projectPath` entry under `livespec@livespec`. So
for almost every affected root, rule 3 has no record to select.

Simulating the PROPOSED rule 2 plus the SHIPPED rule 3 against live host state
(the shipped `_record_for(...)` called directly; no repo modification):

| project root | after the fix |
|---|---|
| `/data/projects/livespec` | `.claude-plugin` — dogfooding preserved |
| `/data/projects/livespec-overseer` | `cache/livespec/livespec/1768d10c92c5` — CORRECT |
| `/data/projects/livespec-orchestrator-beads-fabro` | `cache/livespec/livespec/1768d10c92c5` — CORRECT |
| `.worktrees/livespec-overseer-revert-v017` | `UNRESOLVED[project_not_installed]` |
| `.worktrees/overseer-2607` | `UNRESOLVED[project_not_installed]` |

Three things to read off that table:

1. The dogfooding case is preserved — the whole reason rule 2 exists.
2. The two broken repos resolve to the correct installed core. The defect is
   fixed at the level it was reported.
3. The 288 affected roots with no install record move from a silent wrong
   answer to a loud `project_not_installed` diagnostic.

## FRAMING CORRECTED — see `worktree-resolution.md`

The section above, and the "always a provisioning defect" reading below it, are
too soft. They imply a provisioning backlog somebody could clear. It is
structural instead: spec-side operations are tracked-file writes, this fleet
mandates worktree -> PR -> merge for those, so for `revise` and `propose-change`
the WORKTREE IS THE NORMAL execution context — and worktrees do not acquire
registry records under normal workflow.

So fixing rule 2 alone converts the NORMAL spec-op path from a silent wrong root
to a loud failure, rather than exposing a backlog. Still an improvement, but not
a footnote.

It is also recoverable, which this note did not know: a linked worktree can
resolve its owning primary checkout via `git rev-parse --git-common-dir`, and the
primary DOES hold the record. Measured, the walk-up takes the affected set from
"3 resolve, 288 hard-fail" to "291 resolve, 0 fail" — every remaining case. See
`worktree-resolution.md` for the numbers, the build-drift second failure mode,
and the scope fork that follows.

## Why (3) is the fix working, not the fix breaking

Today a `/livespec:*` operation in one of those worktrees resolves rule 2 to the
worktree's own `.claude-plugin`, the binding's directory-only guard passes on it,
and the operation runs until it fails on a missing `prose/<operation>.md` — a
late, confusing failure whose prescribed remedies do not apply.

After the fix it stops at resolution with the diagnostic this repo's
`SPECIFICATION/contracts.md` §"Core-root resolution" already REQUIRES for this
state: records exist for other projects but none for this one, which the contract
calls "a provisioning defect, NOT a stale plugin" and requires be "named AS" such
rather than reported as staleness. That diagnostic is already implemented and
already correct — `_mismatch_detail(...)` names the mismatch and explicitly warns
against running `claude plugin update`.

So the worktree state was ALWAYS a provisioning defect. Rule 2 was masking it by
answering the question wrongly before rule 3 could report it. The fix does not
create the gap; it stops hiding it.

## What an operator should do when they hit it

Both remedies are already sanctioned and need no new mechanism:

- the rule-1 override `LIVESPEC_CORE_PLUGIN_ROOT=<a real core root>`, which is
  the documented path for nonstandard dev setups and is what the earlier live
  reproductions used as their control; or
- install core for that project root, per the diagnostic's own instructions.

## Recommendation for the merge

State this in the fix's own changeset description, not only here. A correct fix
whose first visible effect is "288 project roots started failing" is the shape of
change that gets reverted by whoever meets it first without context. The
countermeasure is cheap: name the behavior change, name the two remedies, and
point at this note.
