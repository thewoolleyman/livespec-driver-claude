---
proposal: block-auto-memory-intent-routing.md
decision: accept
revised_at: 2026-06-26T05:17:59Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-sonnet-4-6
---

## Decision and Rationale

The proposed change reconciles the driver-claude SPECIFICATION/ to the live hook implementation. The hook already intent-routes by kind (livespec-co9h reword); contracts.md and scenarios.md both still describe the old capture-work-item-only redirect. Accepting the proposal updates both files to describe intent-routing behavior, and updates the stale heading in tests/heading-coverage.json to match the renamed scenario heading.

## Resulting Changes

- contracts.md
- scenarios.md
- ../tests/heading-coverage.json
