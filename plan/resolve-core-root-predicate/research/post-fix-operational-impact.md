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
Seven live `livespec-overseer` worktrees are affected today:

```
.worktrees/livespec-overseer-revert-v017
.worktrees/livespec-overseer-winddown-revise
.worktrees/livespec-overseer-27ug3t-revert
.worktrees/livespec-overseer-foreman-arm-crondirect
.worktrees/livespec-overseer-archive-supervisor-scratch-discipline
.worktrees/livespec-overseer-archive-winddown
.worktrees/overseer-2607
```

All seven score 0/8 on the marker, so the fix correctly declines rule 2 in each.
The discrimination is absolute rather than marginal everywhere it was measured:
every non-core candidate scores 0/8 and core scores 8/8. There is no near-miss
anywhere on this host.

## The behavior change: none of those worktrees has an install record

Checked against `~/.claude/plugins/installed_plugins.json`: not one of the seven
worktree paths appears as a `projectPath` under `livespec@livespec`. So for a
worktree, rule 3 has no record to select.

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
3. Every affected WORKTREE moves from a silent wrong answer to a loud
   `project_not_installed` diagnostic.

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
whose first visible effect is "seven worktrees started failing" is the shape of
change that gets reverted by whoever meets it first without context. The
countermeasure is cheap: name the behavior change, name the two remedies, and
point at this note.
