#!/usr/bin/env python3
"""Refuse Playwright MCP calls from livespec-governed primary checkouts.

The hook is registered for the complete ``mcp__playwright__*`` PreToolUse
surface. It denies only when the input cwd positively resolves to a Git
primary checkout whose repository root carries ``.livespec.jsonc``. Linked
worktrees and every ambiguous/error path pass through silently.

The installed Driver runs this file under bare system Python, so it uses only
the standard library and owns its fail-open boundary in ``main()``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

__all__: list[str] = []


_MATCH_PREFIX = "mcp__playwright__"
_DENY_REASON = (
    "DENIED by primary_checkout_playwright_guard.py: Playwright MCP calls may "
    "write screenshots, snapshots, console logs, or network logs. Run browser "
    "work from a secondary worktree so the governed primary checkout remains clean."
)


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _load_hook_input(*, raw: str) -> dict[str, object] | None:
    try:
        return _as_object_dict(value=json.loads(raw))
    except json.JSONDecodeError:
        return None


def _git_context(*, cwd: Path) -> tuple[Path, Path, Path] | None:
    if not cwd.is_dir():
        return None
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(cwd),
            "rev-parse",
            "--path-format=absolute",
            "--show-toplevel",
            "--git-dir",
            "--git-common-dir",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    lines = completed.stdout.splitlines()
    if len(lines) != 3:
        return None
    return (
        Path(lines[0]).resolve(),
        Path(lines[1]).resolve(),
        Path(lines[2]).resolve(),
    )


def _deny_decision() -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": _DENY_REASON,
        }
    }


def _guard(*, raw_input: str) -> dict[str, object] | None:
    hook_input = _load_hook_input(raw=raw_input)
    if hook_input is None:
        return None
    tool_name = hook_input.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name.startswith(_MATCH_PREFIX):
        return None
    cwd_value = hook_input.get("cwd")
    if not isinstance(cwd_value, str):
        return None
    context = _git_context(cwd=Path(cwd_value))
    if context is None:
        return None
    repo_root, git_dir, git_common_dir = context
    if not (repo_root / ".livespec.jsonc").is_file():
        return None
    if git_dir != git_common_dir:
        return None
    return _deny_decision()


def main() -> int:
    try:
        decision = _guard(raw_input=sys.stdin.read())
        if decision is not None:
            _ = sys.stdout.write(json.dumps(decision, sort_keys=True))
    except Exception:  # noqa: BLE001 — sole fail-open hook boundary: silent pass-through, exit 0
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
