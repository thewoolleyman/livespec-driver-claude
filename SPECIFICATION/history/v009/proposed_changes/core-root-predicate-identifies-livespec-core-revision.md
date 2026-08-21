---
proposal: core-root-predicate-identifies-livespec-core.md
decision: accept
revised_at: 2026-08-21T09:55:28Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

ACCEPT, all three proposals, unmodified in substance. The proposal describes behavior that is already implemented, merged and CI-green on master (PR 570, bb025e5), so this revision closes a live spec-to-impl gap rather than commissioning new work: before it, the resolver emitted a core_checkout_incomplete outcome and required the complete core operation prose set for a rule-2 match, and NEITHER appeared anywhere in the spec -- contracts.md enumerated five step-3 outcomes and never mentioned checkout completeness. The resulting text was reconciled against the merged resolver rather than pasted from the plan's drafts: the code DECLINES to rule 3 only when no core-exclusive name is present, so the error band is 'at least one core-exclusive name present AND the operation-prose set incomplete', which is exactly what the filed scenario states. No count appears in either file, in keeping with the proposal's own reasoning about the clause-lockstep defect: the code deliberately keeps two independent name lists of different sizes, and any number in the spec would make two separately-true statements silently depend on each other. Two shaping decisions were taken while accepting. First, the contract clause was rendered as three house-style paragraphs rather than the proposal's single block-quoted block, and the ninth-operation reasoning was folded into the designation paragraph where the ARMING-versus-MATCHING asymmetry it explains actually lives; every normative sentence is preserved verbatim in substance and no requirement was added, dropped, or weakened. Second, the three new scenario headings were added to tests/heading-coverage.json in the same commit -- that file is outside <spec-target>/ so it cannot travel in resulting_files[], but the repo's check-heading-coverage gate requires every scenarios.md heading to be mapped, and the authoring discipline requires the link to be co-edited atomically with the scenario. Independent ratification review was obtained under auto-spawn with the configured reviewer model, read-only and separate from the authoring seat. The reviewer (self-identified indie-ratify-fable-01) BLOCKED the first submission: the paragraphing had promoted an explanatory sentence out of the proposal's commentary into the contract text, and it carried the ordinal 'a ninth operation' -- a count pinning the size of core's operation set inside ratified contract text, which is the very clause-lockstep defect this amendment exists to prevent, reintroduced by its own fix. The ordinal was replaced with 'a newly added operation', preserving the MATCHING-safe/ARMING-unsafe asymmetry, and the corrected bytes were re-reviewed and returned NO BLOCKERS against this digest.

## Resulting Changes

- scenarios.md
- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-21T09:54:48Z
verdict: NO BLOCKERS
proposal_stem: core-root-predicate-identifies-livespec-core
content_digest: 03e4ad35ac6a3f9c68a568e90f0fdd588afc8b4825f27078d47615abb031de01
