---
topic: cli-end-to-end-harness-contract
author: claude-opus-4-8
created_at: 2026-06-26T03:57:52Z
---

## Proposal: CLI end-to-end harness contract

### Target specification files

- SPECIFICATION/contracts.md
- tests/heading-coverage.json

### Summary

Relocate the `## CLI end-to-end harness contract` (a 6-point contract) out of livespec core and into this Driver's own contracts.md, since the contract states a requirement on the Claude Driver's own user-surface end-to-end tier (sole interaction surface is the `claude` CLI binary). Adapts the voice to this repo and maps the heading to a TODO heading-coverage entry pending the deferred li-e2ecli harness epic, whose harness ships from livespec-dev-tooling.

### Motivation

livespec-besm.6 (RELOCATE decision, maintainer 2026-06-26): clear core's final release-gate heading-coverage TODOs by relocating the two genuinely sibling-owned contract sections into the repos that own them. This is the B4 half. The real test (the full claude-CLI e2e harness) is a deferred obligation that travels with this Driver; the heading-coverage entry stays TODO until li-e2ecli lands here.

### Proposed Changes

Append a `## CLI end-to-end harness contract` section to SPECIFICATION/contracts.md restating the 6-point contract in this Driver's voice: sole entry point is the claude CLI binary; core-and-Driver scope (orchestrator-side e2e owned by each orchestrator; cross-boundary seam only via the three named orchestrator CLIs); structural Driver-skill discovery via the installed plugin's skills/ tree; per-skill fixtures convention; fail-closed time-bomb coverage gate; single canonical harness implementation shipped from livespec-dev-tooling. Add a tests/heading-coverage.json TODO entry for the new heading citing the deferred li-e2ecli harness epic. NOTE: this v002 cut also brings the previously out-of-band `## Hook bundle` edits (the no_shadow_ledger Stop hook, livespec-co9h / commit ee8ec92) into history/ — driver-claude's active contracts.md had diverged from history/v001.
