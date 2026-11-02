---
proposal: single-process-pretooluse-guard-dispatch.md
decision: modify
revised_at: 2026-11-02T01:06:57Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:anthropic-burn-mitigation
---

## Decision and Rationale

Accepted in modified form; delegated decider legacy-coordinator-agent (R301 ruling 2026-11-02 ~01:02Z, accept in both Drivers; MODIFY accepted ~01:15Z). The decider objected that a fail-open dispatcher self-failure would silently drop a fail-closed guard's deny-on-failure guarantee; resolved by falling back to the standalone guards on dispatcher self-failure, which keeps every declared posture exactly as in the standalone layout without denying calls the standalone guards would allow (the decider's suggested blanket deny would refuse every Bash call while the dispatcher is broken, which is stricter than standalone). Modifications resolve the independent Sonnet ratification reviewer's blockers without changing the ruling's substance: one process per Bash call, per-guard failure isolation, a refusal byte-identical to the standalone guard, standalone runnability, plus scenarios. Measured saving about 0.8-1.0 CPU-s per Bash call on the dev host (plan anthropic-burn-mitigation, epic bd-ib-b2jzxw). tests/heading-coverage.json entries for the new scenario headings are co-edited in the same change outside resulting_files because that file lies outside the spec target. Delegated decider confirmed "MODIFY OK" on this exact digest (~01:20Z). Independent read-only Sonnet 5.5 ratification reviewer returned NO BLOCKERS on this exact digest after three rounds.

## Modifications

Modified per the independent ratification review (three blockers): (1) each guard's failure boundary now discharges its DECLARED failure posture, fail-open by default and fail-closed for the upstream fail-closed class (fleet_host_guard), instead of treating every guard failure as an allow; (2) "Bash-matched" is defined as any matcher that includes Bash, the dispatcher is the only Bash-matcher entry, and a guard also registered on other tools (block_auto_memory) keeps its own entry there; (3) "times out" is dropped and the hang bound is the harness hook timeout for the whole process. Also: the closing sentence is scoped to hooks the bundle already carries, the opening line no longer says "fail-open script per hook", and a third scenario covers a crashing fail-closed guard.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-02T01:06:26Z
verdict: NO BLOCKERS
proposal_stem: single-process-pretooluse-guard-dispatch
content_digest: 17aea41dd0a7f186717f22fc165689d44529830b221ab532f5ea41e13c803cfd
