---
proposal: permit-python-hook-bodies.md
decision: accept
revised_at: 2026-07-13T22:32:38Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Accept the S3 own-spec change permitting all-Python hook bodies (invoked python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"), reconciling the Driver spec with the shell->Python hook refactor. Fail-open posture unchanged; no_shadow_ledger.py stays the neutral byte-identical shared body. Independent Fable review returned NO-BLOCKERS.

## Resulting Changes

- spec.md
- contracts.md
