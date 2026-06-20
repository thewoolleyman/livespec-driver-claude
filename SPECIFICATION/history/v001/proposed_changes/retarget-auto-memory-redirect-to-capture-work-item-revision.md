---
proposal: retarget-auto-memory-redirect-to-capture-work-item.md
decision: accept
revised_at: 2026-06-20T16:34:47Z
author_human: E2E Test <e2e-test@example.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Conforms the Driver's own spec to core's already-merged contract change (core PR #497 / history v123): the block-auto-memory.sh redirect now targets the active impl-plugin's capture-work-item skill, not capture-memo, as part of the W7 memo kill. The hook's name and Write(**/memory/*.md) matcher are unchanged; only the redirect target skill is retargeted. The scenarios.md H2 heading rename is co-edited into tests/heading-coverage.json per the self-application revise co-edit discipline.

## Resulting Changes

- contracts.md
- scenarios.md
- ../tests/heading-coverage.json
