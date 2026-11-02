#!/usr/bin/env python3
"""Single entry point for the Driver's Bash-matched PreToolUse guards."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

GUARD_MODULE_NAMES = (
    "tmux_fleet_guard",
    "github_rate_limit_guard",
    "block_raw_bd_create",
    "fleet_host_guard",
    "block_auto_memory",
)


class _FailClosedOutput(str):
    """A malformed fail-closed output must still refuse, unlike a malformed fail-open result."""


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
    if exit_code == 2 or isinstance(stdout, _FailClosedOutput):
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
    guard = _load_guard(name=name)
    try:
        return _runs_in_process(guard=guard, raw=raw)
    except Exception:  # noqa: BLE001 -- per-guard fail-open boundary; fleet is added separately below.
        if name == "fleet_host_guard":
            decision = guard.fail_closed_decision()
            output = decision if decision.endswith("\n") else decision + "\n"
            return 0, _FailClosedOutput(output), ""
        return 0, "", ""


def _run_standalone(*, name: str, raw: str) -> tuple[int, str, str]:
    """Run an unvisited guard through its standalone executable after dispatcher failure."""
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).with_name(f"{name}.py"))],
        input=raw,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _fallback(
    *, index: int, raw: str, refusal: tuple[int, str, str] | None
) -> tuple[int, str, str] | None:
    """Complete a failed dispatch with standalone results for every unvisited guard."""
    combined = refusal
    for name in GUARD_MODULE_NAMES[index:]:
        try:
            result = _run_standalone(name=name, raw=raw)
        except OSError:
            continue
        if combined is None and _denies(result=result):
            combined = result
    return combined


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
    raw = ""
    refusal: tuple[int, str, str] | None = None
    try:
        raw = sys.stdin.read()
    except Exception:  # noqa: BLE001 -- dispatcher boundary; run every standalone guard.
        fallback = _fallback(index=0, raw=raw, refusal=refusal)
        return 0 if fallback is None else _emit(result=fallback)
    for index, name in enumerate(GUARD_MODULE_NAMES):
        try:
            result = _evaluate_guard(name=name, raw=raw)
        except Exception:  # noqa: BLE001 -- dispatcher boundary; preserve standalone guards.
            fallback = _fallback(index=index, raw=raw, refusal=refusal)
            return 0 if fallback is None else _emit(result=fallback)
        if refusal is None and _denies(result=result):
            refusal = result
    return 0 if refusal is None else _emit(result=refusal)


if __name__ == "__main__":
    raise SystemExit(main())
