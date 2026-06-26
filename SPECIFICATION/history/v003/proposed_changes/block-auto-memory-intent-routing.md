---
topic: block-auto-memory-intent-routing
author: claude-sonnet-4-6
created_at: 2026-06-26T05:14:19Z
---

## Proposal: block-auto-memory hook describes intent-routing not capture-work-item-only redirect

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The Hook bundle section of contracts.md and the matching scenario in scenarios.md both describe the block-auto-memory PreToolUse hook as redirecting auto-memory writes solely to the active impl-plugin's capture-work-item skill. The live hook implementation (reworded per livespec-co9h) already intent-routes by what the would-be write IS: trackable work to /<plugin>:capture-work-item, spec-level rules to /livespec:propose-change, durable agent guidance and conventions to AGENTS.md or a referenced .ai/<topic>.md file, and only genuinely session-only notes dropped. The spec is stale and must be reconciled to the live hook behavior.

### Motivation

livespec-co9h (enforce slot of the agent-instruction .ai/ convention epic hso8): the hook impl was already reworded to intent-route; now driver-claude's own spec must reflect that behavior so the driver-claude SPECIFICATION/ is consistent with the live hook.

### Proposed Changes

In SPECIFICATION/contracts.md §"Hook bundle", replace the first bullet describing the PreToolUse hook so it describes intent-routing behavior: the hook intercepts auto-memory writes in livespec-governed projects and routes the would-be write by what it IS — trackable work to the active impl-plugin's capture-work-item skill, spec-level rules to /livespec:propose-change, durable agent guidance and conventions to AGENTS.md or a referenced .ai/<topic>.md file, and only genuinely session-only notes dropped. In SPECIFICATION/scenarios.md, rename §"Scenario: auto-memory write in a governed project is redirected to capture-work-item" to §"Scenario: auto-memory write in a governed project is intent-routed by the block-auto-memory hook" and replace the single "And the block reason names the active impl-plugin's capture-work-item skill" step with three steps that separately assert each routing destination.
