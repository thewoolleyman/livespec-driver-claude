---
proposal: primary-playwright-artifact-guard.md
decision: modify
revised_at: 2026-08-05T22:58:16Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: gpt-5.6
---

## Decision and Rationale

Ratify the Driver-owned realization of the upstream primary-checkout Playwright guard so one project-enabled plugin protects every fleet and adopter repository while preserving the core/Driver ownership boundary.

## Modifications

Scope the numeric enumeration to upstream-required hooks, name the Driver entry point and wildcard registration, and map both the Hook bundle contract and the new primary-versus-linked-worktree scenario to the same integration-tier hook test.

## Resulting Changes

- contracts.md
- scenarios.md
- ../tests/heading-coverage.json

## Ratification Review

ratification_review: manual-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-05T23:11:26Z
verdict: NO BLOCKERS
proposal_stem: primary-playwright-artifact-guard
content_digest: b4802421fac177e12071a743bb136da444d1c1ddc3991997e7a26e83343ae872
