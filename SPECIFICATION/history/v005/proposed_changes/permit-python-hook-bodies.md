---
topic: permit-python-hook-bodies
author: claude-opus-4-8
created_at: 2026-07-13T20:24:19Z
---

## Proposal: permit Python hook bodies in the Driver bundle

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md

### Summary

The Claude Driver's own spec currently describes the plugin-shipped hook
bundle as two POSIX shell scripts plus one Python script
(`no_shadow_ledger.py`). Slice 3 of the `driver-hook-body` epic
(`livespec-nj7d`) converts the two remaining shell hooks —
`block-auto-memory.sh` and `warn-plan-persistence.sh` — into importable
Python hook modules (`block_auto_memory.py`, `warn_plan_persistence.py`),
so that every hook body can be imported and measured in-process for real
per-file coverage. After the refactor the bundle ships THREE Python hook
scripts, each invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`.
This proposal reconciles the Driver's own `SPECIFICATION/` with that shape
BEFORE the code refactor lands, keeping the required fail-open posture and
keeping `no_shadow_ledger.py` as the declared cross-Driver neutral,
byte-identical shared body.

The change is consistent with — and downstream of — the Slice 1 core
amendment (`livespec-pxj9`), which already widened
`livespec/SPECIFICATION/contracts.md` §"Driver-shipped hooks" to permit
the auto-memory-redirect and plan-persistence WARN hooks to be shell OR
Python (`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`) and stated the
importable-`main() -> int` discipline. Core permits either form; this
Driver's own spec now describes the all-Python bundle this repo actually
ships. No H2 heading text changes, so no `tests/heading-coverage.json`
co-edit is required.

### Motivation

The three plugin-shipped hooks cannot be measured for real in-process
Python coverage while two of them are shell wrappers with their Python
bodies passed as strings to `python3 -c`. Converting them to importable
Python modules exposing `main() -> int` is the smallest change that makes
the hook bodies importable and measurable. The Driver's own spec text
still says the hooks are "POSIX shell scripts invoked … `<name>.sh`",
which will contradict the refactored bundle; it must be reconciled to the
all-Python shape first so the Driver `SPECIFICATION/` stays consistent
with the live bundle. The fail-open posture and the `no_shadow_ledger.py`
neutral-byte-identical-body contract are unchanged — only the file form of
the auto-memory-redirect and plan-persistence WARN hooks changes (shell →
Python).

### Proposed Changes

#### 1. SPECIFICATION/spec.md §"Purpose"

In the "This repo ships exactly three things" list, replace item 2's
description of the hook bundle so it no longer says the scripts are POSIX
shell scripts.

Replace this text verbatim:

> `hooks.json` plus fail-open POSIX shell scripts. This is Driver-owned
>    runtime surface (unlike the prose and CLIs, which are core's).

with:

> `hooks.json` plus fail-open Python hook scripts. This is Driver-owned
>    runtime surface (unlike the prose and CLIs, which are core's).

(Only "POSIX shell scripts" becomes "Python hook scripts"; the
"fail-open" qualifier and the surrounding sentence are preserved.)

#### 2. SPECIFICATION/contracts.md §"Hook bundle"

In the opening paragraph, replace the shell-vs-Python composition text
(which currently distinguishes "most" hooks as shell from the one Python
`no_shadow_ledger.py`) with an all-Python description, and drop the now
obsolete "Either way" clause that only made sense while two file forms
coexisted.

Replace this text verbatim:

> Most are
> POSIX shell scripts invoked by the harness as
> `"${CLAUDE_PLUGIN_ROOT}/hooks/<name>.sh"`; the cross-Driver
> no-shadow-ledger hook is a Python script invoked as
> `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/no_shadow_ledger.py"` so its one
> neutral body ships byte-identically in both Drivers' bundles (per
> `livespec/SPECIFICATION/contracts.md`, cross-Driver single-sourcing).
> Either way the Driver's own plugin-root
> placeholder IS correct — the hooks are Driver-owned and live in the
> Driver bundle.

with:

> Every hook is a Python script invoked by the harness as
> `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`; the cross-Driver
> no-shadow-ledger hook (`no_shadow_ledger.py`) is the declared neutral
> shared body and ships byte-identically in both Drivers' bundles (per
> `livespec/SPECIFICATION/contracts.md`, cross-Driver single-sourcing).
> The Driver's own plugin-root placeholder IS correct — the hooks are
> Driver-owned and live in the Driver bundle.

The immediately preceding sentence ("The Driver SHIPS a Claude Code hook
bundle at `.claude-plugin/hooks/`: a `hooks.json` registration plus one
fail-open script per hook.") and the immediately following sentences
(beginning "The bundle's *existence and wiring* are this repo's
contract; …", which already defer the fail-open requirement, block-vs-warn
posture, and gating predicates upstream to
`livespec/SPECIFICATION/contracts.md`) are UNCHANGED. The
importable-`main() -> int` discipline stays core-owned per this spec's
§"Scope boundary" and is not restated here; it is realized by the code
refactor and by the code slice that follows this ratification. The
per-hook bullets, including the `no_shadow_ledger.py` byte-identity
statement in the third bullet, are unchanged.

### Notes on scope

- The fail-open posture is unchanged: every hook still exits 0 on any
  failure and acts only when it POSITIVELY identifies its gating
  condition.
- `no_shadow_ledger.py` remains the single cross-Driver neutral,
  byte-identical shared body.
- No `## ` (H2) heading text is added, removed, or renamed, so no
  `tests/heading-coverage.json` co-edit is required.
- This propose-change is Phase 1 of Slice 3. Ratification via
  `/livespec:revise` requires an independent Fable review first; the code
  refactor (converting the shell hooks, refactoring `no_shadow_ledger.py`
  to `main() -> int`, updating `hooks.json`, tests, coverage config, ruff
  exclusions, and supervisor-entry config) is Phase 2 and does not land in
  this proposal.
