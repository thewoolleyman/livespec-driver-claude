---
topic: core-root-project-path-selection
author: claude-opus-5-rop-railway-enforcement
created_at: 2026-08-01T02:21:56Z
---

## Proposal: Core-root resolution selects the install record whose projectPath is the project root

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Step 3 of the core-root resolution order currently reads 'the installed livespec@livespec plugin's flattened cache root' — singular, as though one install exists. The registry key holds a LIST of install records, one per project, and every one of the eight bindings realizes step 3 faithfully by taking entries[0]: whichever project on the host installed core FIRST, which has no relationship to the project the binding is running in. This change makes step 3 select the record whose projectPath equals the project root, states what happens when no record matches, and separates a registry that cannot be READ from one that is ABSENT.

### Motivation

MEASURED 2026-08-01 by running it, not inferred. On this host the livespec@livespec key holds 13 records; entries[0] is /data/projects/livespec-runtime at build ba62d8fdd609, while livespec-dev-tooling's own record is index 5 at 7a53085b93fb. Dispatching a core wrapper through the entries[0] path exits 78 with 'livespec plugin is stale'; dispatching through the projectPath-matched path exits 0 and resolves. So every /livespec:revise and /livespec:propose-change from that project hard-stops before doing any work. Filed as livespec-dev-tooling-e01t (P1).

This is NON-CONFORMANCE with already-ratified upstream text, not a gap. livespec core's contracts.md §'Install verification' states the rule in the identical vocabulary: a project is correctly provisioned only when the registry 'holds an entry for that plugin whose projectPath equals the project root', and it names 'installed-against-a-different-projectPath' as a defective state that 'any provisioning or currency tooling MUST detect and report loudly'. The bindings do not merely fail to select by projectPath — they SILENTLY CONSUME the exact state that ratified text says MUST be reported loudly.

And this section already contradicts itself two paragraphs apart: step 3 assumes a single installation shape, while the same section's closing paragraph says a binding 'MUST NOT assume a single installation shape'. The implementation faithfully realizes the defective half.

### Proposed Changes

### `contracts.md` §"Core-root resolution"

Replace step 3 and extend the closing paragraph:

3. else the install record for `livespec@livespec` in
   `~/.claude/plugins/installed_plugins.json` **whose `projectPath` equals
   the project root**, resolved to that record's `installPath`.

The registry key holds an ARRAY of install records, one per project that
has installed the plugin. Selecting by position — including the first —
resolves whichever project on the host installed core earliest, which
bears no relation to the project the binding is running in. Selection is
BY `projectPath`, never by position.

A binding MUST distinguish these outcomes and MUST NOT collapse them onto
one diagnostic:

- **registry absent** — core is installed for no project; the install
  instructions are the correct and complete remedy;
- **registry present but unreadable or unparseable** — a NON-ANSWER that
  says nothing about whether core is installed; the diagnostic MUST NOT
  tell the operator to install core, because it has not established that
  core is missing;
- **`livespec@livespec` key absent from a readable registry** — definitive:
  core is installed for no project; install instructions apply;
- **key present, but no record whose `projectPath` is the project root** —
  the defective state livespec core's `contracts.md` §"Install verification"
  requires be 'detected and reported loudly'. The binding MUST name the
  `projectPath` mismatch AS SUCH, MUST report which project roots DO hold
  records, and MUST NOT fall through to another project's record. The
  remedy is an install scoped to THIS project, not an update of a record
  the binding does not read;
- **matching record present but carrying no usable `installPath`** — a
  malformed record; a distinct diagnostic naming the record it found.

A resolution failure MUST NOT be reported as a staleness failure. When the
resolved record is stale, core's own plugin-currency gate reports it and
prescribes `claude plugin update livespec@livespec --scope project`; that
remedy is only coherent when the binding reads the same record the command
writes, which projectPath selection is what guarantees. Under positional
selection the operator loops: the command updates a record that is already
current, the binding keeps reading another project's, and the identical
error recurs. Core's §"Install verification" already records the mechanism
— 'claude plugin update <plugin> -s project, issued from a project holding
no install record of its own, has been observed to act on ANOTHER project's
record and report success'.

### `contracts.md` §"Core-root resolution" — single-sourced realization

Add:

The resolution algorithm is realized ONCE, by a Driver-owned script the
bundle ships at `.claude-plugin/lib/resolve_core_root.py`, invoked
through the Driver's own plugin-root placeholder. Every binding calls that
script; no binding restates the algorithm. Eight independently-maintained
copies of a resolution rule are kept in agreement only by copying, which is
how all eight came to carry the same positional defect. The Driver's own
plugin-root placeholder is correct here for the same reason it is correct
for the hook bundle: the script is Driver-owned and lives in the Driver
bundle. It is NOT a core wrapper and the §"Fenced-invocation discipline"
rules do not reach it.

### `contracts.md` §"Fenced-invocation discipline"

The third bullet's justification becomes false once the bundle ships a
Driver-owned script tree. Amend the reason, not the rule — the rule is still right:

- use the Driver's own plugin-root placeholder (`CLAUDE_PLUGIN_ROOT`) for a
  CORE wrapper, which resolves to the DRIVER root — the Driver bundle
  carries no core `bin/` wrappers, so this would resolve to a path with no
  wrapper. The Driver's own plugin-root placeholder remains correct for
  Driver-owned bundle assets (the hook bundle, and the core-root resolver).

### `scenarios.md`

Amend the existing scenario `## Scenario: core-root resolution falls back to
the installed cache` to select by `projectPath`, and add scenarios for the
four outcomes the rule now distinguishes: a registry holding records for
SEVERAL projects resolving THIS project's record (the positive control — a
registry whose first record belongs to a different project); no matching
record producing a loud projectPath-mismatch diagnostic rather than a
fall-through; an unreadable registry producing a distinct diagnostic that
does not claim core is uninstalled; and an absent registry producing the
install instructions.
