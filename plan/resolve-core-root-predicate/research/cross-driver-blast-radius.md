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

## The marker is valid on all three runtimes' resolved core paths

Checked 2026-08-19. This matters for the SECOND use of the marker — replacing the
weak `-d <root>/prose` post-resolve guard (the `livespec-driver-claude-tun`
surface) — which each Driver applies to whatever its own step 3 returned.

| runtime | resolved core path | core prose set |
|---|---|---|
| Claude | six distinct `~/.claude/plugins/cache/livespec/livespec/<build>` roots | 8/8 each |
| Codex | `~/.codex/.tmp/marketplaces/livespec/.claude-plugin` | 8/8 |
| pi | `<project>/.pi/git/github.com/thewoolleyman/livespec/.claude-plugin` | 8/8 |

So tightening the guard to the eight-file marker produces no false negative on
any real install on this host, in any of the three runtimes. The pi user-scope
clone (`$HOME/.pi/agent/...`) is simply absent here, which is the "candidate not
present" case its resolver already handles.

MEASUREMENT CAVEAT worth recording, because it nearly landed in this note as a
result: a first pass reported 0/8 for the pi paths. That was an artifact of this
host's default shell being ZSH, where an unquoted `for f in $CORE` does NOT
word-split and iterates ONCE over the whole string, so the probe looked for a
single file whose name was all eight names joined. Sweeps in this plan that used
a literal `for f in critique doctor ... seed` list were unaffected, and the
Python re-check confirms 8/8. Any future sweep here should use Python or a
literal list, never an unquoted variable.

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

## The lockstep hazard, sharpened by core (2026-08-20)

Scope question 1 above — "whether the predicate is ratified ONCE in livespec
core's contract" — was raised here as an open maintainer decision. Core's
report-only second opinion sharpens it into a concrete failure mode and raises it
as CORE'S OWN gap rather than this plan's.

The predicate reads a core-ratified set, but nothing in core states that anything
DEPENDS on it for resolution. Verified 2026-08-20: core's live prose and live
`SPECIFICATION/` carry no mention of `LIVESPEC_CORE_PLUGIN_ROOT`, of
`resolve_core_root`, or of the core-root resolution algorithm at all. The single
grep hit in core is an ARCHIVED history artifact
(`SPECIFICATION/history/v166/proposed_changes/`), not a live surface.

So if the eight names become a PRIVATE LITERAL in each of three Drivers, then on
the day a rename lands under the `contracts.md` rename clause, all three Drivers
must move in lockstep or the predicate silently mis-scores core — and every
Driver falls through to rule 3 at once. This repo's own resolver docstring
already names the ancestor of this failure: "Eight independently-maintained
copies of a resolution rule are kept". Three independently-maintained copies of
the SET is the same shape one level up. Core names this the clause-lockstep class
from its `.ai/spec-proposal-review.md`.

### One refinement that makes the fix cheaper than core framed it

Core's suggested outs were (a) derive the list from a core-shipped artifact, or
(b) get the dependency written into core's contract so a propose-change cycle is
forced to touch it.

But (b) is already half-done. `contracts.md` ALREADY enumerates the eight
operations by name in the same paragraph that ratifies the rename gate, and that
paragraph already says "core supplies the harness-neutral prose, wrapper CLIs,
templates, and schemas that each Driver binds." The set is ratified and
rename-gated TODAY; what is missing is only a statement that Driver core-root
RESOLUTION keys off it. So the minimal out is one sentence appended at that
existing clause, not a new contract section — a materially smaller
propose-change than "write the dependency into core's contract" implies.

Option (a) remains the stronger fix (it removes the copies rather than
documenting them), and the two are not exclusive. Routing is still the foreman's
call; nothing was filed in core, whose valve is report-only.


## The port surface, counted per Driver (2026-08-20)

This note establishes that all three Drivers carry the defect and that the fix is
not uniform. It does not say how MUCH work each port is. Re-verified against
current checkouts (`livespec-driver-codex` at `cf0ea77`, `livespec-driver-pi` at
`37649c3`) and counted.

| Driver | resolver shape | rule-2 sites | guard sites | doc sites | edit sites |
|---|---|---|---|---|---|
| claude | shared Python (`lib/resolve_core_root.py`) | 1 | 8 `SKILL.md` | 0 | **9** |
| codex | **INLINE in all 8** `livespec/skills/<op>/SKILL.md` | 8 | 8 | 0 | **8 files, 16 edits** |
| pi | shared **shell** (`lib/resolve-core-root.sh`) | 1 | 1 | 1 `README.md` | **3** |

### pi is the cheapest port, and it is NOT what this note implied

This note says pi "consults fixed clone paths", which is true of its rules 3 and
4 and is why it has no `projectPath` concern. But it left the impression that pi
is structurally unlike the other two. It is not: **pi single-sources its resolver
exactly as this repo does**, in `lib/resolve-core-root.sh`. Its rule-2 defect is
one line:

    line 64:  if [ -d "$candidate/prose" ]; then

One further detail with real consequences: pi applies that predicate to EVERY
candidate in its chain, not only to rule 2. So tightening it to the eight-file
marker also hardens pi's two clone-path branches — a partial or half-fetched
clone would be caught rather than silently accepted. That aligns pi with the 1-7
amendment for free, and is an argument for porting the THREE-WAY rule to pi
rather than a bare boolean.

pi's override guard is also centralized (line 78, "carries no prose/"), so pi's
equivalent of this repo's `tun` surface is one line in the same file rather than
eight copies.

### pi has a NINTH surface the plan did not record: its README

`livespec-driver-pi/README.md:57` restates the rule in prose:

    `.claude-plugin/` when it carries `prose/` (the project IS core), else the
    project-scope pi clone, else the user-scope pi clone.

Note the shape: the stated INTENT is correct ("the project IS core") while the
stated TEST is the defective one. That is the same stated-versus-tested gap
`livespec-driver-claude-tun` describes, appearing in documentation rather than
code. A port that fixes only the resolver leaves pi's README documenting the old
rule. Neither codex's nor this repo's README carries equivalent text — checked.

### codex is the expensive one, and single-sourcing should come first

codex has no shared resolver — confirmed, nothing matching `resolve*core*` exists
outside its venv. Each of its eight bindings carries BOTH halves inline:

    line 41:  if [ -z "$LIVESPEC_CORE_ROOT" ] && [ -d "./.claude-plugin/prose" ]
    line 55:  if [ -z "$LIVESPEC_CORE_ROOT" ] || [ ! -d "$LIVESPEC_CORE_ROOT/prose" ]

So codex needs sixteen edits across eight files, and scope question 3 above —
whether to consolidate codex's resolver first — is answered by the count rather
than by preference. Applying a three-way predicate plus an error diagnostic
sixteen times, by hand, in eight files, re-creates precisely the
defect-in-all-eight-at-once condition that motivated single-sourcing in the other
two Drivers.

### What this does not change

Routing is still the foreman's call and nothing was filed in either sibling
tenant. The recommendation is unchanged: port the PREDICATE to all three, do NOT
port this repo's `projectPath` selection logic. This section only prices the
three ports, which the routing decision needs and this note did not have.


## The port is now a SHARED DESIGNATION, not three independent ports (2026-08-21)

This note has said throughout: port the PREDICATE to all three Drivers, do NOT
port this repo's `projectPath` selection logic. That is still right and still the
recommendation. But it is now insufficient, and the gap was found by core's seat
reviewing the contract amendment rather than by anything measured here.

The predicate has two halves and they do not port the same way.

**MATCHING** — the complete operation-prose set — is a subset test over a set
core already ratifies at `SPECIFICATION/spec.md` line 238. Three Drivers reading
that set independently cannot disagree about it, because core owns it and a
rename goes through a propose-change cycle. Porting it three times is safe.

**ARMING** — which names constitute EVIDENCE that a checkout is core-in-progress
— is a designation, and core does not own it today. If each Driver designates its
own, the same partial core checkout hard-errors on Claude and falls silently
through to rule 3 on Codex, resolving the installed cache. That is the exact
failure this plan exists to remove, reintroduced on whichever runtime designates
loosely.

And the failure is unfalsifiable from either seat: the operator who reports the
error and the operator who cannot reproduce it are both correct, and nothing in
either repository explains why. A diagnostic reproducible on only some runtimes
is worse than no diagnostic, because it consumes the investigation that a missing
one would at least leave to the resolver's own message.

### So the routing requirement is stronger than "port it"

The designation must be made ONCE and bind every realization — identical across
Drivers. `draft-spec-text.md` now carries that wording, using core's established
pattern from `spec.md` line 378: a reference realization is where a thing is
written down, not who gets to choose it. Note core has THREE reference
realizations (`spec.md` line 424), which is precisely why "the reference
realization decides" was the wrong formulation.

Practical consequence for whoever routes this: the three ports are NOT
independent work items that can land in any order by different hands. They share
a fact. Either the designation lands in core's contract first and all three
realize it, or the three ports must be coordinated so they cannot diverge. Filing
them as three unrelated tenant items — which is the obvious shape, and what this
note's earlier framing invites — is the thing that produces the divergence.

### The fail-safe that must port with it

Also from core, and easy to lose in a port: **adding an operation to core's set
must NOT add its name to the evidence set.** Growth is safe for matching (subset
test) and unsafe for arming (it decides whether a stranger's repository errors).
So the two lists must stay independent in every Driver, and the tempting
refactor — derive the evidence set from the operation set by excluding the
generic names — is forbidden in all three, not just here. This repo's
implementation now carries that prohibition as a comment and pins it with a test;
a port that copies the predicate but not the prohibition reintroduces the slow
failure on that runtime.

Routing remains the foreman's call and nothing is filed in either sibling tenant.
