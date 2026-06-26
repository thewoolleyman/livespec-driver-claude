---
proposal: cli-end-to-end-harness-contract.md
decision: accept
revised_at: 2026-06-26T03:58:09Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Accept the B4 relocation (livespec-besm.6): the CLI e2e harness contract is a requirement on this Claude Driver's own user-surface tier. Lands the 6-point section and the TODO heading-coverage entry (real test = deferred li-e2ecli harness epic). This v002 cut also brings the previously out-of-band ## Hook bundle edits (no_shadow_ledger Stop hook, livespec-co9h) into history, since active had diverged from v001.

## Resulting Changes

- contracts.md
- ../tests/heading-coverage.json
