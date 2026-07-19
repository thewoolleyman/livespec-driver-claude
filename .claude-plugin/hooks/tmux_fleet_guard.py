#!/usr/bin/env python3
"""
tmux_fleet_guard - PreToolUse hook blocking default-socket tmux fleet kills.

Declared in hooks.json on the `Bash` tool. This hook denies commands that can
destroy every agent session sharing the user's default tmux socket:

- unscoped or default-scoped `tmux kill-server`;
- `pkill` / `killall` invocations whose arguments mention tmux.

Explicitly scoped tmux servers remain allowed: use `tmux -L <name> kill-server`
with a non-default socket name, or `tmux -S <path> kill-server` with a path
that is not the default `/tmp/tmux-<uid>/default` socket.

This module owns the hook BOUNDARY only — reading the PreToolUse payload from
stdin, emitting the deny decision, and always exiting 0. The verdict itself
comes from the sibling `_tmux_hazard` module, whose docstring documents the
evasion families it closes (wrapper prefixes such as `env -i` and `sudo`,
`-S` socket-path spellings that resolve to the fleet socket, and nested
`sh -lc` / `xargs` payloads).

Fail-closed safety: ANY parsing or main-loop failure on a command that carries
the hazard hints (`kill-server`, `pkill`, or `killall`) emits a deny decision.
Commands without those hints fail open silently with exit 0.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it.
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
from typing import cast

from _tmux_hazard import classify


__all__: list[str] = []

_DENY_REASON = (
    "BLOCKED by tmux_fleet_guard.py: this command can kill shared/default "
    "tmux agent sessions. Do not run unscoped `tmux kill-server`, "
    "`pkill ... tmux`, or `killall tmux`. Use the safe alternative "
    "`tmux -L <name> kill-server` for a deliberately scoped tmux socket."
)

_HAZARD_HINT = re.compile(r"\b(?:kill-server|pkill|killall)\b")


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    """Narrow an arbitrary JSON value to a string-keyed dict, else None."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _has_hazard_hint(*, command: str) -> bool:
    return bool(_HAZARD_HINT.search(command))


def _deny_decision() -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": _DENY_REASON,
            }
        }
    )


def _decision(*, raw: str) -> str | None:
    payload = _as_object_dict(value=json.loads(raw))
    if payload is None or payload.get("tool_name") != "Bash":
        return None
    tool_input = _as_object_dict(value=payload.get("tool_input"))
    if tool_input is None:
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None
    if classify(command=command):
        return _deny_decision()
    return None


def main() -> int:
    """Guard entry point: deny hinted hazards even when classification fails; exit 0."""
    raw = ""
    try:
        raw = sys.stdin.read()
        decision = _decision(raw=raw)
        if decision is not None:
            _ = sys.stdout.write(decision + "\n")
    except Exception:  # noqa: BLE001 — sole fail-closed guard boundary: deny per policy, exit 0
        if _has_hazard_hint(command=raw):
            with contextlib.suppress(OSError):
                _ = sys.stdout.write(_deny_decision() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
