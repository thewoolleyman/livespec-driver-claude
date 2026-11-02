#!/usr/bin/env python3
"""Single entry point for the Driver's Bash-matched PreToolUse guards."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
from types import ModuleType

__all__: list[str] = []

GUARD_MODULE_NAMES = (
    "tmux_fleet_guard",
    "github_rate_limit_guard",
    "block_raw_bd_create",
    "fleet_host_guard",
    "block_auto_memory",
)


def _load_guard(*, name: str) -> ModuleType:
    """Import one installed guard from the plugin bundle."""
    return importlib.import_module(name)


def _runs_in_process(*, guard: ModuleType, raw: str) -> tuple[int, str, str]:
    """Run a guard through its standalone boundary while capturing its hook output."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    original_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(raw)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = guard.main()
    finally:
        sys.stdin = original_stdin
    if type(result) is not int:
        raise TypeError(f"{guard.__name__}.main() returned {type(result).__name__}, not int")
    return result, stdout.getvalue(), stderr.getvalue()


def _denies(*, result: tuple[int, str, str]) -> bool:
    """Whether a standalone-shaped result refuses the tool call."""
    exit_code, stdout, _ = result
    if exit_code == 2:
        return True
    try:
        payload = json.loads(stdout)
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    specific = payload.get("hookSpecificOutput")
    return isinstance(specific, dict) and specific.get("permissionDecision") == "deny"


def _evaluate_guard(*, name: str, raw: str) -> tuple[int, str, str]:
    """Apply an individual guard's fail-open boundary without stopping later guards."""
    try:
        return _runs_in_process(guard=_load_guard(name=name), raw=raw)
    except Exception:  # noqa: BLE001 -- per-guard fail-open boundary; fleet is added separately below.
        return 0, "", ""


def _emit(*, result: tuple[int, str, str]) -> int:
    """Emit the first refusal exactly as its standalone guard did."""
    exit_code, stdout, stderr = result
    if exit_code == 2:
        _ = sys.stderr.write(stderr)
        return exit_code
    _ = sys.stdout.write(stdout)
    return 0


def main() -> int:
    """Evaluate every Bash-matched guard and retain the first refusal in dispatch order."""
    raw = sys.stdin.read()
    refusal: tuple[int, str, str] | None = None
    for name in GUARD_MODULE_NAMES:
        result = _evaluate_guard(name=name, raw=raw)
        if refusal is None and _denies(result=result):
            refusal = result
    return 0 if refusal is None else _emit(result=refusal)


if __name__ == "__main__":
    raise SystemExit(main())
