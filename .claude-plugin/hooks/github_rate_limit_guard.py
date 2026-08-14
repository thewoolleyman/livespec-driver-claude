#!/usr/bin/env python3
"""PreToolUse guard for GitHub CLI polling and mutation bursts.

Declared in hooks.json on the `Bash` tool. This hook denies only the
load-bearing conjunctions that exhaust GitHub budgets quickly:

- shell loops or sleeps combined with repeated `gh run`, `gh pr`, or
  read-only `gh api` calls;
- shell loops or `xargs` combined with mutating `gh api` calls.

Hook protocol: hook-input JSON on stdin (`tool_name`, `tool_input.command`).
Exit 2 denies the tool call and puts the reason on stderr. Exit 0 allows it.
Every error path returns 0 (fail-open), including crashes and unparseable
input, because a failing plugin-shipped hook can wedge every governed repo.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is from the standard library.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import cast

__all__: list[str] = []

_READ_DENY_REASON = (
    "DENIED by github_rate_limit_guard.py: looped or sleeping GitHub reads "
    "must use the cached alternative `gh api --cache <duration>`; a 304 "
    "response costs no primary rate-limit budget."
)
_MUTATION_DENY_REASON = (
    "DENIED by github_rate_limit_guard.py: looped or xargs-fed mutating "
    "GitHub API calls are rate-limit hazards. GitHub API mutations cost five "
    "points against a nine-hundred-point-per-minute ceiling, so more than "
    "about one hundred eighty per minute trips it regardless of hourly budget; "
    "at least one second between mutations is required."
)

_SHELL_SELECT = r"(?:^|[;&|]\s*)select\s+[A-Z_][A-Z0-9_]*(?=\s+(?:in|do)\b|\s*;)"
_LOOP_OR_SLEEP = re.compile(
    rf"\b(?:for|while|until)\b|{_SHELL_SELECT}|\bsleep\b",
    re.IGNORECASE,
)
_LOOP_OR_XARGS = re.compile(
    rf"\b(?:for|while|until|xargs)\b|{_SHELL_SELECT}",
    re.IGNORECASE,
)
_GH_READ = re.compile(r"\bgh\s+(?:run|pr)\b", re.IGNORECASE)
_GH_API = re.compile(r"\bgh\s+api\b(?P<args>[^\n;&|]*)", re.IGNORECASE)
_MUTATING_METHOD = re.compile(
    r"(?:\s|^)(?:-X|--method)(?:=|\s+)(?P<method>delete|post|patch|put)\b",
    re.IGNORECASE,
)


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _log_event(*, level: str, event: str, check_id: str, command: object = None) -> None:
    payload: dict[str, object] = {
        "level": level,
        "timestamp": _utc_timestamp(),
        "check_id": check_id,
        "event": event,
    }
    if command is not None:
        payload["command"] = command
    _ = sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _load_hook_input(*, raw: str) -> dict[str, object] | None:
    try:
        return _as_object_dict(value=json.loads(raw))
    except json.JSONDecodeError:
        return None


def _has_loop_or_sleep(*, command: str) -> bool:
    return bool(_LOOP_OR_SLEEP.search(command))


def _has_loop_or_xargs(*, command: str) -> bool:
    return bool(_LOOP_OR_XARGS.search(command))


def _has_mutating_gh_api(*, command: str) -> bool:
    return any(_MUTATING_METHOD.search(match.group("args")) for match in _GH_API.finditer(command))


def _has_read_gh_call(*, command: str) -> bool:
    if _GH_READ.search(command):
        return True
    for match in _GH_API.finditer(command):
        if not _MUTATING_METHOD.search(match.group("args")):
            return True
    return False


def _deny_reason(*, command: str) -> str | None:
    if _has_loop_or_xargs(command=command) and _has_mutating_gh_api(command=command):
        return _MUTATION_DENY_REASON
    if _has_loop_or_sleep(command=command) and _has_read_gh_call(command=command):
        return _READ_DENY_REASON
    return None


def _guard(*, raw_input: str) -> int:
    hook_input = _load_hook_input(raw=raw_input)
    if hook_input is None:
        _log_event(
            level="warning",
            check_id="github-rate-limit-guard-unparseable",
            event="unparseable hook input; failing open",
        )
        return 0
    if hook_input.get("tool_name") != "Bash":
        return 0
    tool_input = _as_object_dict(value=hook_input.get("tool_input"))
    if tool_input is None:
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str):
        return 0
    reason = _deny_reason(command=command)
    if reason is None:
        return 0
    _log_event(
        level="error",
        check_id="github-rate-limit-guard-deny",
        event=reason,
        command=command,
    )
    return 2


def main() -> int:
    try:
        return _guard(raw_input=sys.stdin.read())
    except Exception as exc:  # noqa: BLE001 — sole fail-open hook boundary: silent pass-through, exit 0
        _log_event(
            level="warning",
            check_id="github-rate-limit-guard-crash",
            event="github_rate_limit_guard crashed; failing open",
            command=repr(exc),
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
