# Initial backlog — relocated from the livespec tenant

These two items are Claude-harness-specific by nature and belong to
this Driver repo (per the family's preserve-by-relocation directive).
They were filed in the livespec beads tenant and stay OPEN there until
this repo's own work-item tenant is provisioned, at which point they
migrate here and the livespec-tenant originals close with a pointer.

Provenance: livespec master `02ef5ccca178335da2aec690220fb2efe52bb879`
(the pre-extraction SHA; the items reference livespec spec sections as
of that commit).

---

## 1. Stop hook for plan-artifact persistence detection

- **Origin id:** `livespec-c1nf` (livespec tenant; P3, open)
- **Lineage:** preservation split from `livespec-1f5-rest` item 6;
  parent epic `livespec-4moata` (realize the v103 contract +
  reference implementations re-steering, Phases 2–6)

Full original description:

> PRESERVATION split from livespec-1f5-rest item 6. A Claude Code
> Stop hook (.claude/settings.json) scanning the agent's last turn
> for substantial planning artifacts (tables/lists/headings above
> thresholds) and WARNING when no tool call persisted equivalent
> content (never auto-files); optional extension: detect done-claims
> on non-master branches. Realizes the still-live core
> non-functional-requirements §'Completion includes persistence and
> workspace cleanup'. Harness-specific by nature → RELOCATE →
> livespec-driver-claude when W4 creates it (same destination class
> as livespec-hookimpl).

---

## 2. PreToolUse hook redirecting auto-memory writes to capture-memo

- **Origin id:** `livespec-hookimpl` (livespec tenant; P3, open;
  labels: `origin:freeform`)
- **Lineage:** implementation follow-up to `livespec-zmlkrl`
  (closed research item)

Full original description:

> ## Implementation follow-up to li-zmlkrl
>
> Research completed in li-zmlkrl close-out. Two-step landing:
>
> ### Step 1 — spec change (propose-change → revise)
>
> Add to `contracts.md` a new §"Plugin-shipped hooks" (or equivalent)
> declaring that `livespec` MAY ship Claude Code hooks via
> `.claude-plugin/hooks/hooks.json`, and specifically ships a
> `PreToolUse` hook on the `Write` tool with matcher pattern
> `Write(**/memory/*.md)`. The hook redirects to the ACTIVE
> impl-plugin's `capture-memo` skill — resolved from
> `.livespec.jsonc`'s `implementation.plugin` (currently
> `livespec-impl-beads`, so `/livespec-impl-beads:capture-memo`; do
> NOT hardcode a single impl namespace) — when the active project
> carries a `.livespec.jsonc` declaring an impl-plugin with
> `memos_path`; otherwise the hook is a no-op pass-through. Document
> the hook-script contract (read `CLAUDE_PROJECT_DIR`, check
> `.livespec.jsonc`, resolve the active impl-plugin's namespace, emit
> block-decision JSON on stdout for active projects, exit 0
> otherwise).
>
> ### Step 2 — impl
>
> Ship:
> - `.claude-plugin/hooks/hooks.json` — declares the PreToolUse
>   matcher.
> - `.claude-plugin/hooks/block-auto-memory.sh` — the wrapper script.
> - Unit-test the script via `tests/hooks/` (mock
>   `CLAUDE_PROJECT_DIR` + tmp_path).
> - Wire into `just check`.
>
> ## Reference design
>
> Plugin hooks fire automatically when installed. Response shape for
> blocking (the `reason` names the resolved active impl-plugin's
> namespace — beads under the current default):
>
> ```json
> {
>   "decision": "block",
>   "reason": "This project uses livespec. Use /livespec-impl-beads:capture-memo (the active impl-plugin's capture-memo skill) to file memos in the durable store.",
>   "hookSpecificOutput": {
>     "hookEventName": "PreToolUse",
>     "permissionDecision": "deny"
>   }
> }
> ```

Note for the spec-change step: with the Driver extraction landed, the
hook bundle described above ships from THIS repo's `.claude-plugin/`
(the Driver is the Claude-harness surface), while the spec-change step
still flows through livespec core's propose-change/revise lifecycle.
