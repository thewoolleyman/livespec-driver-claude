# The rule-2 predicate defect is fleet-wide across all three Drivers

Second research note for plan `resolve-core-root-predicate`. Measured
2026-08-19, after the plan was opened. Read
`defect-and-fix-shape.md` first — this note only extends its blast-radius
section.

## Why this note exists

`defect-and-fix-shape.md` scoped the defect to this repo's
`.claude-plugin/lib/resolve_core_root.py` and measured which GOVERNED repos it
misresolves from. It did not ask the converse question: do the SIBLING Drivers
carry the same predicate? They do. All three do, and the anchor item
`livespec-driver-claude-d7d` is on file in only one of the three tenants.

## Measured state, all three Drivers

| Driver | realization | rule-2 predicate | on file in its tenant |
|---|---|---|---|
| `livespec-driver-claude` | `.claude-plugin/lib/resolve_core_root.py` (single, Python) | `(checkout / "prose").is_dir()` | yes — `d7d`, `tun`, +4 dups |
| `livespec-driver-pi` | `lib/resolve-core-root.sh` (single, shell) | `[ -d "$candidate/prose" ]` | **no** |
| `livespec-driver-codex` | none — inline in all 8 `livespec/skills/*/SKILL.md` | `[ -d "./.claude-plugin/prose" ]` | **no** |

Sibling tenants were read with the fleet credential wrapper on 2026-08-19:
`livespec-driver-pi` holds 7 items and `livespec-driver-codex` holds 30, and
neither has any item whose title names core-root resolution.

## Live reproduction — pi Driver

Run from `/data/projects/livespec-overseer`, which is a control-plane plugin
and not livespec core:

```
$ /data/projects/livespec-driver-pi/lib/resolve-core-root.sh .
/data/projects/livespec-overseer/.claude-plugin
exit=0
```

Control, run from livespec core itself:

```
$ cd /data/projects/livespec && /data/projects/livespec-driver-pi/lib/resolve-core-root.sh .
/data/projects/livespec/.claude-plugin
exit=0
```

The pi resolver is structured as an ordered candidate list with ONE shared
acceptance test applied to every candidate:

```bash
for candidate in "${candidates[@]}"; do
    if [ -d "$candidate/prose" ]; then
```

Candidate 2 is `$project_root/.claude-plugin`. So the false match shadows
candidates 3 and 4 — pi's own project-scope and user-scope package clones,
which are the pi equivalent of this Driver's rule 3 and hold the correct
answer. Same defect, same shadowing, different substrate.

Note the shared acceptance test is load-bearing for a DIFFERENT and correct
purpose in that script: it rejects a half-fetched clone at candidates 3 and 4,
which the script's own comment calls out deliberately. A fix there must tighten
candidate 2 WITHOUT weakening the half-fetched-clone rejection on 3 and 4 —
those two candidates want "carries prose/", not "is core".

## The codex Driver is the worst-affected of the three

It has no shared resolver at all. Each of its eight
`livespec/skills/<op>/SKILL.md` files restates the algorithm inline, and each
carries BOTH defects at once:

- the stated rule names the operation's prose FILE
  (`<project-root>/.claude-plugin/prose/help.md` exists), while
- the bash two lines below tests the prose DIRECTORY
  (`[ -d "./.claude-plugin/prose" ]`), and
- the post-resolve guard tests the directory again
  (`[ ! -d "$LIVESPEC_CORE_ROOT/prose" ]`), so it cannot catch the miss.

That is the `livespec-driver-claude-tun` shape, replicated eight times in a
repo where no single resolver exists to fix it once. It is also precisely the
"eight independently-maintained inline copies" anti-pattern that BOTH this
repo's `resolve_core_root.py` docstring and pi's `resolve-core-root.sh` header
comment cite as the reason they were single-sourced — the codex Driver has not
yet had that consolidation.

## The fix is NOT uniform across the three Drivers

Added 2026-08-19 after auditing each Driver's step 3. The rule-2 lesson transfers
to all three; the `projectPath` lesson does NOT, because the three runtimes have
genuinely different plugin models. Assuming one patch shape for all three is the
natural mistake here, and it would be wrong.

| Driver | step-3 substrate | positional-selection risk |
|---|---|---|
| `livespec-driver-claude` | `installed_plugins.json`, an ARRAY of per-project records | REAL — this is `livespec-driver-claude-6lc`, already fixed by selecting on `projectPath` |
| `livespec-driver-codex` | `codex plugin list --json`, host-wide | NONE |
| `livespec-driver-pi` | two filesystem clone paths, project- and user-scope | NONE |

The codex binding reads:

```bash
for plugin in data.get("installed", []):
    if plugin.get("pluginId") == "livespec@livespec":
        sys.stdout.write(plugin.get("source", {}).get("path", ""))
        break
```

That takes the FIRST match and breaks, which LOOKS like the positional defect but
is not one. Codex plugin enablement is HOST-WIDE — livespec core's
`contracts.md` §"Plugin distribution" states it is persisted in
`~/.codex/config.toml` and "applies to every project on the host" — so there is
exactly one `livespec@livespec` record per host and no per-project array to
select wrongly from. The `break` simply stops after the single match.

The pi resolver likewise consults no registry at all: its candidates 3 and 4 are
fixed filesystem paths (`$project_root/.pi/git/github.com/thewoolleyman/livespec/.claude-plugin`
and `$HOME/.pi/agent/...`), which are pi's project- and user-scope package clone
locations.

CONSEQUENCE. A cross-Driver fix should port the rule-2 CORE-IDENTITY predicate to
all three, and should NOT port this repo's `projectPath` selection logic — there
is nothing in the other two runtimes for it to select over. Conversely, a
reviewer who finds the codex `break` and files it as "the same positional defect"
would be filing a non-defect.

## What this changes for the plan

Nothing about the fix SHAPE: a core-identity predicate is still the right
answer, and the recommendation in `defect-and-fix-shape.md` (require the full
core operation-prose set) is substrate-independent — it is expressible in
Python, in shell, and inline in prose.

What it changes is SCOPE, and that is a maintainer decision this plan should
not make silently:

1. Whether the predicate is ratified ONCE in livespec core's contract, so all
   three Drivers realize one agreed marker, or whether each Driver picks its
   own. Three Drivers independently choosing a core-identity marker is the same
   copy-kept-in-agreement failure mode one level up.
2. Whether the sibling defects get filed in their own tenants now, or after
   this repo's fix proves the predicate. Neither sibling has ANY item on file
   today, so the current state is silent breakage in two of three Drivers.
3. Whether the codex Driver's missing resolver consolidation is folded in or
   tracked separately. Fixing its predicate in eight inline copies without
   consolidating first re-creates the exact defect-in-all-eight-at-once
   condition that motivated the other two Drivers' single-sourcing.

This plan's scope event deliberately did NOT admit cross-repo children, and
this note does not change that. Cross-repo routing is the foreman's call.
