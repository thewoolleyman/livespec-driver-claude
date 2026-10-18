#!/usr/bin/env python3
"""
block_auto_memory — PreToolUse hook redirecting auto-memory writes to the
right durable destination BY INTENT.

Declared in hooks.json on the `Write`, `Edit`, `MultiEdit` and `Bash` tools
(work-item livespec-driver-claude-cb2mzo, per livespec core v225). For a file
tool it acts when the target file's immediate parent directory is `memory` and
the filename ends in `.md` (the Claude Code auto-memory layout,
`~/.claude/projects/<slug>/memory/*.md`), or when the target lies under the
Codex local-memory store `~/.codex/memories/`. For `Bash` it acts when the
sibling `_memory_write` classifier POSITIVELY identifies the command as
writing into either directory; reads and `rm` pass. The deny reason is the
same on every route.

Behavior (per work-item livespec-driver-claude-e1s, lineage
livespec-hookimpl / li-zmlkrl; reason reworded per bug livespec-co9h):

1. Read the PreToolUse hook input JSON from stdin.
2. When the write targets an agent memory directory AND the governed project
   (`$CLAUDE_PROJECT_DIR`) carries a `.livespec.jsonc` declaring an active
   impl-plugin (`implementation.plugin` — NEVER hardcoded here), emit
   block-decision JSON on stdout whose `reason` routes the would-be memory
   write BY WHAT IT IS — trackable work to the resolved
   `/<plugin>:capture-work-item` skill, a spec-level rule to
   `/livespec:propose-change`, durable agent guidance / a learned preference
   / a convention to a short AGENTS.md entry pointing at a `.ai/<topic>.md`
   file (or AGENTS.md alone when the guidance is short), and only
   genuinely session-only notes dropped — so durable NON-work-item memory is
   never misfiled as a bogus work-item or silently lost (livespec-co9h).
3. Otherwise: no-op pass-through (no output).

Fail-open contract: ANY failure (malformed stdin, unreadable or unparseable
`.livespec.jsonc`, unset `CLAUDE_PROJECT_DIR`) is a silent pass-through with
exit 0. The hook only blocks when it POSITIVELY identifies a livespec-governed
project. `main()` owns stdin/stdout at the hook boundary, catches every
failure, and returns 0 on every path; it is importable (no work at module
import) so the body is testable in-process for real per-file coverage.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it —
the `_result` railway, and the `_livespec_project` resolver that reads the
active impl-plugin namespace out of the governed project's `.livespec.jsonc`
(shared with the sibling `block_raw_bd_create.py` redirect, which routes to
the same `/<plugin>:capture-work-item` operation).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import PurePosixPath
from typing import cast

from _livespec_project import resolve_impl_plugin
from _memory_write import writes_memory
from _result import Failure, Result, Success

__all__: list[str] = []

_FILE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})
_CODEX_MEMORY_STORE = (".codex", "memories")


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    """Narrow an arbitrary JSON value to a string-keyed dict, else None."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _deny_reason(*, namespace: str) -> str:
    """The intent-routing deny reason naming all four destinations."""
    return (
        "This project is livespec-governed. Per-session agent memory files "
        "(~/.claude/projects/<slug>/memory/*.md, ~/.codex/memories/) are NOT used "
        "here — ephemeral, per-user, and "
        "invisible to other agents/runtimes. Do NOT silently drop what you were about "
        "to write; route it by what it IS:\n"
        "  - Trackable work (task/bug/refactor/follow-up) -> file in the beads ledger "
        f"via /{namespace}:capture-work-item.\n"
        "  - A spec-level rule or behavior -> /livespec:propose-change.\n"
        "  - Durable agent guidance / a learned preference / a convention -> a "
        "short, discoverable AGENTS.md entry that points at a .ai/<topic>.md file "
        "holding the content (or AGENTS.md alone when the guidance is itself short).\n"
        "  - ONLY genuinely session-only, throwaway notes that matter nowhere outside "
        "this session may be dropped."
    )


def _is_memory_file(*, file_path: str) -> bool:
    """A Claude Code `**/memory/*.md` note, or any file under the Codex store."""
    target = PurePosixPath(file_path)
    if target.suffix == ".md" and target.parent.name == "memory":
        return True
    parts = target.parent.parts
    width = len(_CODEX_MEMORY_STORE)
    return any(parts[i : i + width] == _CODEX_MEMORY_STORE for i in range(len(parts)))


def _memory_write(*, tool_name: object, tool_input: dict[str, object]) -> bool:
    """Whether this tool call writes into an agent memory directory."""
    if tool_name == "Bash":
        command = tool_input.get("command")
        return isinstance(command, str) and writes_memory(command=command)
    file_path = tool_input.get("file_path")
    return (
        tool_name in _FILE_TOOLS
        and isinstance(file_path, str)
        and _is_memory_file(file_path=file_path)
    )


def _block_decision(*, raw: str) -> str | None:
    """Return the block-decision JSON, or None for a pass-through."""
    payload = _as_object_dict(value=json.loads(raw))
    if payload is None:
        return None
    tool_input = _as_object_dict(value=payload.get("tool_input"))
    if tool_input is None or not _memory_write(
        tool_name=payload.get("tool_name"), tool_input=tool_input
    ):
        return None
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if not project_dir:
        return None
    namespace = resolve_impl_plugin(project_dir=project_dir).value_or(default=None)
    if namespace is None:
        return None
    reason = _deny_reason(namespace=namespace)
    return json.dumps(
        {
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        }
    )


def _decision_result(*, raw: str) -> Result[str | None, Exception]:
    """Lift expected pass-through failures from decision logic onto the rail.

    `ValueError` is raised by `json.loads`, including `JSONDecodeError`
    subclasses. The `.livespec.jsonc` read has its own rail inside
    `resolve_impl_plugin`, so it never surfaces here.
    """
    try:
        return Success(_block_decision(raw=raw))
    except ValueError as exc:
        return Failure(exc)


def main() -> int:
    """Hook entry point: emit the block decision, if any; always exit 0.

    Owns the stdin read + stdout write at the hook boundary and catches every
    failure so the PreToolUse hook stays fail-open by contract — it only blocks
    when it POSITIVELY identifies a governed memory write, and never exits
    non-zero.
    """
    try:
        raw = sys.stdin.read()
        decision = _decision_result(raw=raw).value_or(default=None)
        if decision is not None:
            _ = sys.stdout.write(decision + "\n")
    except Exception:  # noqa: BLE001 — sole fail-open hook boundary: silent pass-through, exit 0
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
