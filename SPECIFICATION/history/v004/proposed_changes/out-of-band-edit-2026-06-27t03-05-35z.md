---
topic: out-of-band-edit-2026-06-27t03-05-35z
author: livespec-doctor
created_at: 2026-06-27T03:05:35Z
---

## Proposal: out-of-band-edit-2026-06-27t03-05-35z

doctor detected drift between HEAD-active spec content and the
HEAD-history-vN snapshot; this auto-backfill records the active
state as the new canonical version.

### Proposed Changes

```diff
--- history/vN/contracts.md
+++ active/contracts.md
@@ -23,7 +23,7 @@
   `plugin.json` is the source of truth for the description.
 
 This is the Driver-local realization of livespec core's
-`contracts.md` §"Plugin distribution", which owns the cross-cutting rule
+`contracts.md`, which owns the cross-cutting rule
 that plugin and marketplace share the value `livespec` by deliberate
 choice (renaming either flows through a core propose-change cycle). Note
 that core's contract leaves description-equality un-enforced at v1 ("v1
@@ -43,8 +43,8 @@
 - that `SKILL.md`'s frontmatter `name` MUST equal `<name>`.
 
 No extra skill directories may exist, and none of the eight may be
-missing. The operation *set* is a core contract (`livespec/SPECIFICATION/spec.md`
-§"Sub-command lifecycle"); this contract governs the Driver-local
+missing. The operation *set* is a core contract
+(`livespec/SPECIFICATION/spec.md`); this contract governs the Driver-local
 binding directories that realize it.
 
 ## Core-root resolution
@@ -94,14 +94,14 @@
 no-shadow-ledger hook is a Python script invoked as
 `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/no_shadow_ledger.py"` so its one
 neutral body ships byte-identically in both Drivers' bundles (per
-`livespec/SPECIFICATION/contracts.md` §"Driver-shipped hooks" →
-cross-Driver single-sourcing). Either way the Driver's own plugin-root
+`livespec/SPECIFICATION/contracts.md`, cross-Driver single-sourcing).
+Either way the Driver's own plugin-root
 placeholder IS correct — the hooks are Driver-owned and live in the
 Driver bundle. The bundle's *existence and wiring* are this repo's
 contract; the hooks' *behavioral disciplines and postures* (the
 fail-open requirement, block-vs-warn, the gating predicates) are owned
-upstream by `livespec/SPECIFICATION/contracts.md` §"Driver-shipped
-hooks", which this repo realizes. The script implementations and their
+upstream by `livespec/SPECIFICATION/contracts.md`, which this repo
+realizes. The script implementations and their
 unit tests live in THIS repo (`tests/hooks/`).
 
 The bundle carries three hooks:
@@ -125,16 +125,15 @@
   content carries markdown checkbox task-list items (`[ ]` / `[x]`) at or
   above a mechanical threshold, directing the agent to derive status from
   the work-item ledger instead of embedding a parallel work queue
-  (`livespec/SPECIFICATION/non-functional-requirements.md` §"Planning Lane
-  guidance" → "No shadow ledger"); WARN-only, always exit 0, never
-  auto-edits. Its detection body is single-sourced and ships
+  (`livespec/SPECIFICATION/non-functional-requirements.md`); WARN-only,
+  always exit 0, never auto-edits. Its detection body is single-sourced
+  and ships
   BYTE-IDENTICALLY in both Drivers' bundles per
-  `livespec/SPECIFICATION/contracts.md` §"Driver-shipped hooks" →
-  cross-Driver single-sourcing.
+  `livespec/SPECIFICATION/contracts.md`, cross-Driver single-sourcing.
 
 Adding or removing a hook, renaming a hook surface, or changing a hook's
 posture requires a propose-change cycle against the upstream
-§"Driver-shipped hooks" contract; the mechanical detection internals
+Driver-shipped hooks contract; the mechanical detection internals
 (matcher predicates, artifact thresholds) are Driver implementation
 detail and MAY be tuned without a spec cycle, provided the postures hold.
 
@@ -143,8 +142,8 @@
 `plugin.json.version` is the single source of truth for the shipped
 Driver plugin's version and is auto-managed by `release-please` from
 per-commit Conventional Commits. `marketplace.json` MUST NOT carry a
-`version` field. This mirrors livespec core's `contracts.md`
-§"Plugin versioning"; the Driver follows the same release mechanism for
+`version` field. This mirrors livespec core's `contracts.md`;
+the Driver follows the same release mechanism for
 its own plugin artifact.
 
 ## CLI end-to-end harness contract
@@ -154,8 +153,8 @@
 binary. The harness installs livespec core plus this Driver
 (`livespec-driver-claude`), then drives the Driver's slash-command bindings
 end-to-end over core's prose and wrapper CLIs. This tier is a sibling to core's
-wrapper-chain tier (`livespec/SPECIFICATION/contracts.md` §"E2E harness
-contract"): it adds a higher tier, replaces neither, and both coexist in CI.
+wrapper-chain tier (`livespec/SPECIFICATION/contracts.md`): it adds a
+higher tier, replaces neither, and both coexist in CI.
 Codex and future Drivers need their own equivalent user-surface proof when they
 claim a distributed Driver surface.
 
@@ -172,8 +171,8 @@
 2. **Core-and-Driver scope.** Orchestrator-side end-to-end coverage is owned by
    each orchestrator's own repository and specification. This harness MAY
    exercise the cross-boundary seam only through the three config-named
-   orchestrator CLIs per `livespec/SPECIFICATION/contracts.md` §"Orchestrator
-   CLI contract — the three named CLIs" (e.g. against a stub orchestrator
+   orchestrator CLIs per `livespec/SPECIFICATION/contracts.md` (e.g.
+   against a stub orchestrator
    fixture); it MUST NOT exercise that seam through plugin installation or skill
    enumeration.
 
--- history/vN/non-functional-requirements.md
+++ active/non-functional-requirements.md
@@ -22,8 +22,7 @@
   → PR → merge → cleanup path; the primary checkout refuses direct
   commits/pushes. The hook body and its doctor fingerprint invariant are
   owned by `livespec/SPECIFICATION/non-functional-requirements.md`
-  §"Primary-checkout commit-refuse hook" and `livespec/SPECIFICATION/contracts.md`
-  §"`primary-checkout-commit-refuse-hook-installed`". This repo carries a
+  and `livespec/SPECIFICATION/contracts.md`. This repo carries a
   copy of the canonical scaffold under `dev-tooling/`; it does not
   re-specify it.
 - **Toolchain pinning** via `mise`; **`uv`** as the Python toolchain
--- history/vN/spec.md
+++ active/spec.md
@@ -17,8 +17,8 @@
 A **Driver** is the thin, agent-runtime-specific wrapper through which a
 human drives the livespec spec lifecycle interactively. `livespec-driver-claude`
 is the first reference Driver under livespec's contract-plus-reference-
-implementations architecture (per `livespec/SPECIFICATION/spec.md`
-§"Contract + reference implementations architecture"). It binds livespec
+implementations architecture (per `livespec/SPECIFICATION/spec.md`).
+It binds livespec
 core's harness-neutral material to ONE tool runtime — Claude Code.
 
 This repo ships exactly three things, all Claude-runtime mechanics:
@@ -59,10 +59,10 @@
 exit codes, and wire contracts; the JSON schemas; the built-in templates;
 the eight slash-command *names* and any rename (those require a core
 propose-change cycle); and the hook *disciplines and postures* (fail-open
-contract, block-vs-warn) — those live in `livespec/SPECIFICATION/contracts.md`
-§"Driver-shipped hooks". The family-standard primary-checkout commit-refuse
-hook is likewise core-owned (`livespec/SPECIFICATION/non-functional-requirements.md`
-§"Primary-checkout commit-refuse hook"); this repo carries the scaffold but
+contract, block-vs-warn) — those live in `livespec/SPECIFICATION/contracts.md`.
+The family-standard primary-checkout commit-refuse
+hook is likewise core-owned (`livespec/SPECIFICATION/non-functional-requirements.md`);
+this repo carries the scaffold but
 does not re-specify it.
 
 Upstream-wins: when a rule here conflicts with livespec core's
@@ -71,7 +71,7 @@
 ## Terminology
 
 The family vocabulary is defined upstream in `livespec/SPECIFICATION/spec.md`
-§"Terminology" and §"Contract + reference implementations architecture";
+§"Terminology";
 this tree uses it without redefinition. The terms that recur here:
 
 - **Driver** — the thin, agent-runtime-specific wrapper (this repo, for
```
