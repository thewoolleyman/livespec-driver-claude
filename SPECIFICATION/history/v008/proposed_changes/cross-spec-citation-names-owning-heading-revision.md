---
proposal: cross-spec-citation-names-owning-heading.md
decision: accept
revised_at: 2026-08-06T11:38:00Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

The citation named a section that does not exist in livespec core. Core's SPECIFICATION/contracts.md carries `## Plugin distribution`, with "Install verification." as a leading paragraph label inside it, so the existing `§"Install verification"` citations resolve to nothing. This was latent while livespec was absent from this repository's cross_repo_targets: the citation checker had no clone to resolve against. Registering livespec as a cross-repo target - required so the Dispatcher readiness gate can resolve sibling_work_item dependencies on livespec instead of failing closed to UNKNOWN - armed real resolution and exposed the broken citation. The registration is correct and stays; the citation is what was wrong, and it was wrong before the registration revealed it. Verified by construction in a scratch worktree: with the registration and the old citation, doctor-no-cross-spec-reference FAILS at contracts.md:73; with the citations and the matching external_references entry naming `§"Plugin distribution"`, check-doctor-static passes with zero non-pass findings.

## Resulting Changes

- contracts.md

## Ratification Review

ratification_review: manual-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-06T11:34:59Z
verdict: NO BLOCKERS
proposal_stem: cross-spec-citation-names-owning-heading
content_digest: fe7ed533620146458f45f629fc3921306f90021dece5de17120ff269a5cd22b6
