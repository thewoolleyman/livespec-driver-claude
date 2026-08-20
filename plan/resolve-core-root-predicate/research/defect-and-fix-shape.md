# resolve_core_root rule 2: the predicate does not identify livespec core

Initial research note for plan `resolve-core-root-predicate`.
Ledger anchor for this defect: **livespec-driver-claude-d7d** (filed
2026-08-04). Re-measured 2026-08-19 in this repo before the plan was opened.

## The defect, at the line

`.claude-plugin/lib/resolve_core_root.py`, in `resolve_core_root(...)`:

```python
checkout = project_root / ".claude-plugin"
if (checkout / "prose").is_dir():
    return CoreRootResolved(path=checkout, source="project_checkout")
```

The contract this realizes (`SPECIFICATION/contracts.md` §"Core-root
resolution", rule 2) says `<project-root>/.claude-plugin/` is the core root
"when the governed project IS the livespec core repo — the `--plugin-dir .`
dev / dogfooding path". The predicate does not test that. It tests only that
SOME `prose/` directory exists, which is true of every repo shipping a plugin
in the family's now-standard thin-binding-plus-prose shape. Rule 2 therefore
matches non-core repos and SHADOWS rule 3, which holds the correct answer.

## Measurement, 2026-08-19

Run from `/data/projects/livespec-overseer` (a control-plane plugin, not core):

```
$ python3 /data/projects/livespec-driver-claude/.claude-plugin/lib/resolve_core_root.py --project-root .
.claude-plugin
exit=0
```

Rule-3 control — `~/.claude/plugins/installed_plugins.json` under
`plugins["livespec@livespec"]` DOES hold a record for this project:

```
/data/projects/livespec-overseer -> /home/ubuntu/.claude/plugins/cache/livespec/livespec/1768d10c92c5
```

So the correct core root was reachable and rule 2 pre-empted it. The failure
is silent at resolution time and surfaces later as a missing
`prose/<operation>.md`, whose prescribed remedies do not apply.

## Blast radius across live repos

Repos under `/data/projects` that ship `.claude-plugin/prose/`:

| repo | ships `prose/` | is core | rule 2 today |
|---|---|---|---|
| `livespec` | yes | yes | correct |
| `livespec-overseer` | yes | no | **false match** |
| `livespec-orchestrator-beads-fabro` | yes | no | **false match** |
| `livespec-driver-claude` | no | no | not reached (unaffected) |

Two of the three `prose/`-shipping repos are broken. That counts REPOS; counted
as PROJECT ROOTS (a git worktree is its own), the affected set is 291 — see
`post-fix-operational-impact.md` for the corrected sweep. Every spec-side
`/livespec:*` operation (seed, propose-change, critique, revise, doctor,
prune-history, next, help) driven from such a repo misresolves.

## Why the obvious discriminators do not work

- **`plugin.json` `name`** is `"livespec"` for BOTH livespec core AND this
  Driver (verified 2026-08-19). Manifest name alone cannot identify core.
- **A single marker file** (e.g. `prose/revise.md`) is cheap but is the same
  CLASS of almost-right predicate: any future family repo shipping a `revise`
  operation false-matches again. The resolver's own module docstring already
  warns twice about almost-right discriminators.
- **Reordering rule 3 before rule 2** removes the false match without any
  predicate, but breaks dogfooding: `/data/projects/livespec` itself HAS an
  install record, so core would resolve to its installed cache rather than to
  the working checkout — defeating `--plugin-dir .` dev mode. It also inverts
  the ordering `SPECIFICATION/contracts.md` ratifies, so it would require a
  spec change rather than an implementation fix.

## Candidate fix, prototyped

Rule 2 requires the CORE OPERATION-PROSE SET — all eight operation prose
files that `contracts.md` §"Skill set" already binds this Driver to:
`critique.md`, `doctor.md`, `help.md`, `next.md`, `propose-change.md`,
`prune-history.md`, `revise.md`, `seed.md`.

Prototyped against the five live family checkouts on 2026-08-19: `livespec`
matches; `livespec-overseer`, `livespec-orchestrator-beads-fabro`,
`livespec-driver-claude` and `livespec-dev-tooling` do not. The set IS the
Driver's contract with core, and it is exactly what the bindings go on to
read, so the predicate tests the thing the caller actually depends on.

Known coupling to weigh: an all-eight check ties rule 2 to core's operation
set. That coupling already exists and is already enforced — this repo's
`check-plugin-structure` gate requires exactly those eight skill directories.

## Surfaces the fix must touch

1. `.claude-plugin/lib/resolve_core_root.py` — the rule 2 predicate.
2. `tests/hooks/test_resolve_core_root.py` — `test_governed_project_that_is_core_uses_its_own_checkout`
   (line 128) currently PINS the defect: its fixture creates an EMPTY
   `prose/` dir and asserts `source == "project_checkout"`. The fixture must
   become core-shaped, and a negative test must be added.
3. The eight `.claude-plugin/skills/*/SKILL.md` — each restates rule 2 as
   "when it carries `prose/`", and each post-resolve guard tests
   `[ ! -d "$LIVESPEC_CORE_ROOT/prose" ]`, which passes on the wrong root and
   so suppresses any early failure. This is the standing item
   `livespec-driver-claude-tun`.
4. `SPECIFICATION/` — `contracts.md` rule 2 is already correct as written, so
   no correction is owed there; `scenarios.md` has no NEGATIVE scenario for a
   non-core repo shipping its own prose. Adding one is a spec addition, routed
   through `/livespec:propose-change`.

## Prior filings in this tenant

The same defect is on file six times. `d7d` (P1, 2026-08-04) is the anchor and
carries the fullest measurements. `zgqrta`, `4xc` and `zeh4ft` are duplicates.
`tun` (2026-07-20) is the distinct SKILL.md-guard surface listed above and is
still live. `6lc` (2026-07-19) reported the `entries[0]` POSITIONAL defect,
which is already fixed — the resolver selects by `projectPath` today — so it
is stale and should be dispositioned as such rather than reworked.


## The `tun` guard fix, prototyped and gate-tested (2026-08-20)

Surface 3 above — the eight `SKILL.md` post-resolve guards — is the
`livespec-driver-claude-tun` carrier. The resolver half was prototyped and
measured (`implementation-constraints.md`). The guard half never was. Done now.

### The eight guards are byte-identical

Checked: the guard block in all eight bindings hashes identically. So the port is
a single uniform substitution, not eight judgement calls.

### The proposed guard, and what it catches that the current one does not

    for op in critique doctor help next propose-change prune-history revise seed; do
      [ -f "$LIVESPEC_CORE_ROOT/prose/$op.md" ] && continue
      echo "resolved root is not livespec core: no prose/$op.md in $LIVESPEC_CORE_ROOT" >&2
      exit 1
    done

Run against real roots on this host:

| root | current guard | proposed guard |
|---|---|---|
| real core checkout | PASS | PASS |
| real installed cache build | PASS | PASS |
| cache build with prose and NO `scripts/` | PASS | PASS |
| **non-core repo shipping its own `prose/`** | **PASS** | **FAIL** |
| **partial 7/8 core checkout** | **PASS** | **FAIL**, names `revise.md` |
| pre-prose orphaned build | FAIL | FAIL |

The two rows in bold are the whole item. The current guard PASSES on both failure
cases — the misresolved root `d7d` describes, and the mid-rename checkout the
1-7 amendment exists for. A guard that passes on every case it exists to catch is
not a weak guard; it is an absent one.

Note the third row: the guard must stay PROSE-ONLY. A real cache build ships the
complete prose set and no `scripts/livespec/` package at all, so a guard reaching
into the scripts tree would false-negative on it.

### "Costs no gate update" — confirmed, by running it

All eight guards were replaced in a scratch worktree and the full aggregate run:

    just check-plugin-structure   -> exit 0
    just check                    -> green, no failures

So `tun` can land as a pure eight-file substitution with no test change and no
gate change. The reason is precise: `check-plugin-structure` delegates to
`_plugin_structure_claude.fenced_invocation_violations`, which constrains only
fenced lines that INVOKE a `bin/<name>.py` wrapper (they must use
`$LIVESPEC_CORE_ROOT`, they must not use `uv run`). The guard is a `[ -f ... ]`
test, not a wrapper invocation, so the gate does not look at it. That module
contains zero occurrences of `prose`.

This also confirms the standing claim that `tests/e2e-cli` needs no fixture
change — it passed unmodified.

### The uncomfortable half: gate-clean is not tested

The same measurement establishes something the plan should not celebrate.
Nothing under `tests/` or `dev-tooling/` references the guard text at all —
grepped for both `LIVESPEC_CORE_ROOT/prose` and the current failure message,
zero hits. The guards are shell inside markdown, executed by the agent at
runtime, exercised by no test.

So `just check` passing after the substitution does not mean the new guard is
correct. It means no gate looked. A BROKEN guard would pass equally, which is
part of how the current one survived: it has been wrong in all eight copies for
as long as it has existed, and nothing in CI could ever have said so.

Folding `tun` in therefore costs no gate update AND gains no gate protection. The
behavioural table above is the only verification this change can have today,
which is an argument for putting those six cases in the changeset description
rather than leaving them here.

### Scope

Prototype only. The eight `SKILL.md` files were patched in a scratch worktree to
run the gates and then REVERTED; nothing under `.claude-plugin/` is changed by
this commit. `tun` remains open and unimplemented, and its suggested disposition
(keep open, retitle to name the surviving guard defect) is unchanged.
