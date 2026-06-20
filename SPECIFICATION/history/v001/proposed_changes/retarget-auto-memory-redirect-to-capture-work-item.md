---
topic: retarget-auto-memory-redirect-to-capture-work-item
author: claude-opus-4-8
created_at: 2026-06-20T16:33:51Z
---

## Proposal: retarget-auto-memory-redirect-to-capture-work-item

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The Driver's auto-memory PreToolUse redirect hook (block-auto-memory.sh) names the active impl-plugin's capture-memo skill. The memo surface is retired family-wide (W7 memo kill); in-flight observations now route to the work-item ledger via capture-work-item. Retarget the redirect to capture-work-item across the Driver's own spec.

### Motivation

Core's contracts.md §"Driver-shipped hooks" already says the block-auto-memory.sh redirect points at the active impl-plugin's capture-work-item skill (was capture-memo), merged in core PR #497 / history v123. The Driver dogfoods livespec and must conform: its contracts.md hook description and its scenarios.md scenario both still name capture-memo. The hook's name (block-auto-memory.sh) and its Write(**/memory/*.md) matcher are unchanged — only the redirect TARGET skill changes.

### Proposed Changes

In SPECIFICATION/contracts.md §"Driver-shipped hooks", change the PreToolUse hook bullet so the redirect target reads the active impl-plugin's `capture-work-item` skill instead of `capture-memo`. In SPECIFICATION/scenarios.md, rename the H2 heading from `## Scenario: auto-memory write in a governed project is redirected to capture-memo` to `## Scenario: auto-memory write in a governed project is redirected to capture-work-item`, and change the Gherkin line `And the block reason names the active impl-plugin's capture-memo skill` to `And the block reason names the active impl-plugin's capture-work-item skill`. Because the scenarios.md H2 heading is renamed, co-edit tests/heading-coverage.json (the matching entry) so its `heading` field stays in lockstep, per the self-application revise co-edit discipline.
