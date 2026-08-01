---
proposal: core-root-project-path-selection.md
decision: accept
revised_at: 2026-08-01T02:22:22Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5-rop-railway-enforcement
---

## Decision and Rationale

ACCEPTED. The rule it states is already ratified UPSTREAM — livespec core's contracts.md §'Install verification' requires an entry 'whose projectPath equals the project root' and names installed-against-a-different-projectPath a defective state that MUST be detected and reported loudly. So this is non-conformance with ratified text in the RELAXING direction, not a new requirement, and accepting it is fidelity rather than a tightening.

The measurement is decisive and was produced by RUNNING the two paths rather than reasoning about them: entries[0] resolves another project's record and the wrapper exits 78; the projectPath-matched record exits 0. The self-contradiction the proposal names is real and verbatim — step 3 assumed a single installation shape while the closing paragraph of the same section forbade assuming one.

Accepted WITH the three additions the proposal itself argues for and which are load-bearing rather than incidental:

(1) The absent / unreadable split. Collapsing them is the recorded fail-open of this family: an unreadable registry told to 'install core' is an articulate wrong answer about a host where core may well be installed. Absence is an ANSWER and keeps the install instructions; only a read that did not happen leaves that track.

(2) The mismatch diagnostic must not be spelled as STALENESS. This is what made the defect unfixable rather than merely wrong: a correct currency signal reached a remedy that could not work, because the command writes the record the binding does not read. Naming the mismatch AS SUCH is what terminates the operator's loop.

(3) Single-sourcing the algorithm. Eight byte-identical copies are how one positional defect became eight, and the corrected rule is materially larger than the line it replaces — eight copies of it would deepen the copy-family, not remove it. The resolver ships as a Driver-owned bundle asset, which the §'Hook bundle' contract already establishes as the correct use of the Driver's own plugin-root placeholder.

The consequential edit to §'Fenced-invocation discipline' is included in the same revision rather than deferred: that bullet's justification ('the Driver bundle carries no scripts/ tree') becomes FALSE the moment the resolver ships. The RULE is unchanged and still right — core wrappers resolve through $LIVESPEC_CORE_ROOT — but leaving a true rule standing on a false reason is how the next reader derives a wrong conclusion from it.

ONE CORRECTION MADE WHILE IMPLEMENTING, folded in here rather than left for a later revision, because the ratified text names the path: the resolver ships at `.claude-plugin/lib/`, NOT `.claude-plugin/scripts/`. The fleet-wide `check-skill-invocation-paths` auto-detects which of two mutually contradictory plugin models a repo is held to purely from whether `.claude-plugin/scripts/` exists — a bare directory-presence test with no config key and no diagnostic. Naming the directory `scripts/` silently reclassified this Driver as a core-carrying plugin, after which that check demanded `${CLAUDE_PLUGIN_ROOT}` for CORE wrapper invocations while this repo's own §'Fenced-invocation discipline' forbids exactly that — no set of bindings can satisfy both. Measured, not predicted: it turned every unchanged `$LIVESPEC_CORE_ROOT` wrapper line in the bindings into a violation. The constraint is written INTO the ratified text so a later editor cannot tidy the directory back.

## Resulting Changes

- contracts.md
- scenarios.md
