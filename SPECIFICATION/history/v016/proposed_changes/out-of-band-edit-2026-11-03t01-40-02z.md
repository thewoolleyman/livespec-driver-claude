---
topic: out-of-band-edit-2026-11-03t01-40-02z
author: livespec-doctor
created_at: 2026-11-03T01:40:02Z
---

## Proposal: out-of-band-edit-2026-11-03t01-40-02z

doctor detected drift between HEAD-active spec content and the
HEAD-history-vN snapshot; this auto-backfill records the active
state as the new canonical version.

### Proposed Changes

```diff
--- history/vN/contracts.md
+++ active/contracts.md
@@ -200,7 +200,7 @@
 a `hooks.json` registration plus one script per hook. Every hook is a Python module in the bundle. A guard is
 **Bash-matched** when any matcher it is registered on includes `Bash`. The harness MUST start every Bash-matched
 PreToolUse guard, for a `Bash` call, through ONE dispatcher entry point,
-`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse_dispatch.py"` registered on the `Bash` matcher, so one Bash tool call
+`/usr/bin/python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse_dispatch.py"` registered on the `Bash` matcher, so one Bash tool call
 starts one Python process for the Driver's PreToolUse guards rather than one per guard. A Bash-matched guard that is
 also registered on other tools (for example `block_auto_memory.py` on `Write`, `Edit` and `MultiEdit`) keeps its own
 entry point on those other matchers and is removed from the `Bash` matcher. The dispatcher imports each Bash-matched
```
