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

Fail-closed safety: ANY parsing or main-loop failure on a command that carries
the hazard hints (`kill-server`, `pkill`, or `killall`) emits a deny decision.
Commands without those hints fail open silently with exit 0.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from typing import cast

__all__: list[str] = []

_DENY_REASON = (
    "BLOCKED by tmux_fleet_guard.py: this command can kill shared/default "
    "tmux agent sessions. Do not run unscoped `tmux kill-server`, "
    "`pkill ... tmux`, or `killall tmux`. Use the safe alternative "
    "`tmux -L <name> kill-server` for a deliberately scoped tmux socket."
)

_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_FLEET_DEFAULT_SOCKET = re.compile(r"^/tmp/tmux-\d+/default(?:/.*)?$")
_HAZARD_HINT = re.compile(r"\b(?:kill-server|pkill|killall)\b")
_HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_SHELL_OPERATORS = frozenset({";", "&", "&&", "|", "||"})


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    """Narrow an arbitrary JSON value to a string-keyed dict, else None."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _has_hazard_hint(*, command: str) -> bool:
    return bool(_HAZARD_HINT.search(command))


def _strip_heredoc_bodies(*, command: str) -> str:
    """Remove here-doc BODIES because they are stdin data, not executed shell."""
    lines = command.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        out.append(line)
        match = _HEREDOC.search(line)
        if match is None:
            i += 1
            continue
        terminator = match.group(1)
        i += 1
        while i < n and lines[i].strip() != terminator:
            i += 1
        if i < n:
            i += 1
    return "\n".join(out)


def _tokens_by_segment(*, command: str) -> list[list[str]]:
    """Tokenize once, then split shell command segments without re-lexing."""
    cleaned = _strip_heredoc_bodies(command=command).replace("\n", " ; ")
    lexer = shlex.shlex(cleaned, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    segments: list[list[str]] = []
    current: list[str] = []
    for token in lexer:
        if token in _SHELL_OPERATORS:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _peel_leading_env(*, tokens: list[str]) -> list[str]:
    """Peel leading VAR=VAL assignments and one or more `env` wrappers."""
    remaining = tokens
    changed = True
    while changed and remaining:
        changed = False
        while remaining and _ENV_ASSIGN.match(remaining[0]):
            remaining = remaining[1:]
            changed = True
        if remaining and remaining[0].rsplit("/", 1)[-1] == "env":
            remaining = remaining[1:]
            changed = True
            while remaining and _ENV_ASSIGN.match(remaining[0]):
                remaining = remaining[1:]
    return remaining


def _shell_c_inner(*, tokens: list[str]) -> str | None:
    if not tokens or tokens[0].rsplit("/", 1)[-1] not in _SHELLS:
        return None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token == "-c":
            if i + 1 < len(tokens):
                return tokens[i + 1]
            return None
        if token.startswith("-c") and len(token) > 2:
            return token[2:]
        i += 1
    return None


def _option_value(*, tokens: list[str], flag: str) -> str | None:
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == flag:
            if i + 1 < len(tokens):
                return tokens[i + 1]
        elif token.startswith(f"{flag}="):
            return token[len(flag) + 1 :]
        elif token.startswith(flag) and len(token) > len(flag):
            return token[len(flag) :]
        i += 1
    return None


def _is_non_default_scope(*, tokens: list[str]) -> bool:
    socket_name = _option_value(tokens=tokens, flag="-L")
    if socket_name is not None:
        return socket_name != "default"
    socket_path = _option_value(tokens=tokens, flag="-S")
    if socket_path is not None:
        return not _FLEET_DEFAULT_SOCKET.match(socket_path)
    return False


def _segment_is_hazard(*, tokens: list[str]) -> bool:
    core = _peel_leading_env(tokens=tokens)
    if not core:
        return False
    inner = _shell_c_inner(tokens=core)
    if inner is not None:
        return _classify(command=inner)
    base = core[0].rsplit("/", 1)[-1]
    if base == "tmux" and "kill-server" in core:
        return not _is_non_default_scope(tokens=core)
    if base in {"pkill", "killall"}:
        return any("tmux" in token for token in core[1:])
    return False


def _classify(*, command: str) -> bool:
    """Return True when a command must be denied."""
    for segment in _tokens_by_segment(command=command):
        if _segment_is_hazard(tokens=segment):
            return True
    return False


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
    try:
        denied = _classify(command=command)
    except Exception:  # noqa: BLE001 - fail closed for hinted hazard commands
        denied = _has_hazard_hint(command=command)
    if denied:
        return _deny_decision()
    return None


def main() -> int:
    """Hook entry point: emit a deny decision, if any; always exit 0."""
    raw = ""
    try:
        raw = sys.stdin.read()
        decision = _decision(raw=raw)
    except Exception:  # noqa: BLE001 - fail closed only for hinted hazards
        decision = _deny_decision() if _has_hazard_hint(command=raw) else None
    if decision is not None:
        sys.stdout.write(decision + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
