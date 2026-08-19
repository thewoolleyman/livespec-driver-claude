# The worktree gap is bigger than this plan, and already live

Ninth research note for plan `resolve-core-root-predicate`. Measured 2026-08-19,
by applying to rule 3 the question that the `livespec-overseer` thread's report
applied to rule 2: not "how many roots are affected" but "can the affected roots
reach the right answer another way".

`worktree-resolution.md` established that a primary-checkout walk-up recovers all
288 record-less roots among the 291 that ship their own `prose/`. This note
measures the walk-up against EVERY governed project on the host, and the answer
is larger — because rule 3 has no worktree awareness AT ALL, which has nothing to
do with whether a project ships prose.

## The measurement

Every governed project root on this host — every directory carrying a
`.livespec.jsonc` — under `/data/projects` and `~/.worktrees`:

| | roots |
|---|---|
| governed project roots | 499 |
| **ARE core** — rule 2 resolves them directly | 88 |
| resolve today via their OWN registry record | 15 |
| would resolve via a primary-checkout walk-up | **395** |
| genuinely unresolvable | **1** |

**CORRECTED after first landing.** The first pass reported 502 / 16 / 420 / 66,
and described the 66 residual as "roots whose primary ALSO holds no record —
genuinely unprovisioned". That was wrong, and wrong in the same way the sweep
this note was written to correct: it asked only "does this root have a record,
or does its primary" without first asking "would rule 2 resolve it".

Nearly all 66 were `<worktree>/.livespec-core/...` — VENDORED CLONES OF LIVESPEC
CORE sitting inside janitor worktrees. They carry a `.livespec.jsonc` because
core itself carries one, and they score 8/8 on the core prose set, so rule 2
resolves them directly and they never reach rule 3 at all. Counting them as
unprovisioned overstated the residual by ~65 and would have pointed someone at
provisioning work that is not needed.

Re-measured with rule 2 evaluated first, exactly ONE governed root on this host
is genuinely unresolvable after both fixes: `/data/projects/homelab-05-nixrepro-tree`,
which holds no record and whose primary holds none either.

(Totals drift by a few between sweeps — 502 vs 499 — because other sessions
create and remove worktrees while work proceeds. The counts are snapshots; the
SHAPE is the durable finding.)

## This half is already failing, today, with no fix applied

The 288 roots in `worktree-resolution.md` are the intersection of "is a worktree"
and "ships its own `prose/`" — the ones rule 2 currently misresolves SILENTLY.
The remaining ~132 governed worktrees do NOT ship prose, so rule 2 already
declines them correctly and rule 3 already fails. Verified live from a worktree
of `livespec-dev-tooling`, which ships no `prose/`:

```
$ python3 .../lib/resolve_core_root.py --project-root .
livespec core is installed on this host, but NOT for this project.
  this project root : .
  records exist for :
    /data/projects/livespec-runtime
    ...
```

So spec-side operations from a governed worktree already fail today unless the
worktree happens to hold its own record (16 of 502) or the operator reaches for
the `LIVESPEC_CORE_PLUGIN_ROOT` override. That is very likely why the override is
in routine use across this fleet, including as the workaround the overseer thread
reported.

## What this means for priority

The rule-2 predicate defect and the rule-3 worktree gap are independent, and on
this host the worktree gap is the larger of the two:

| defect | roots affected | failure mode today |
|---|---|---|
| rule 2 predicate | 291 | SILENT wrong root |
| rule 3 worktree gap | 420 | LOUD `project_not_installed` |

They overlap on 288 roots, where rule 2's silent misresolution currently MASKS
the rule-3 gap — which is why fixing rule 2 alone converts those 288 from silent
to loud rather than to working.

The rule-2 defect is still the worse KIND of failure: a confident wrong answer
beats no answer for damage. But the worktree gap is the larger population, it is
already live, and it is the one that decides whether spec-side operations work
from the execution context this fleet mandates.

None of that reorders the plan by itself. It is recorded so the sequencing
decision in `worktree-resolution.md` is made against the real numbers rather than
against the 288 subset this plan happened to measure first.

## A separate small defect in the diagnostic

Visible in the output above: `this project root : .` — the diagnostic prints the
RAW `--project-root` argument rather than the resolved absolute path.

`main()` builds `project_root = Path(cast("str", args.project_root))` with no
`.resolve()`, and `_mismatch_detail(...)` interpolates that value directly. The
comparison path is unaffected — `_record_for` normalizes via `_normalized(...)`
before matching — so this is a message-quality defect, not a resolution defect.

It matters more than it looks. The whole point of that diagnostic is to tell an
operator WHICH project has no record, and every binding invokes the resolver as
`--project-root .`, so in practice the message always says `.` and never names
the project. An operator in a worktree, told that "." is not provisioned while
being shown a list of absolute paths that look plausible, has been given the
least useful form of a correct answer.

One-line fix (`.resolve()` at the `main()` boundary), and it belongs with
whichever changeset touches this file — it is far too small to carry its own
LLOC budget.
