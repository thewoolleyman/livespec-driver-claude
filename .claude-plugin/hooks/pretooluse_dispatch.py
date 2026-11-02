#!/usr/bin/env python3
"""Single entry point for the Driver's Bash-matched PreToolUse guards."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import NamedTuple, cast

__all__: list[str] = []

GUARD_MODULE_NAMES = (
    "tmux_fleet_guard",
    "github_rate_limit_guard",
    "block_raw_bd_create",
    "fleet_host_guard",
    "block_auto_memory",
)


@dataclass
class _DispatchState:
    """The completed dispatch state retained if the dispatcher boundary fails."""

    raw: str = ""
    index: int = 0
    refusal: tuple[int, str, str] | None = None


class _FailClosedResult(NamedTuple):
    """A fleet failure stays refused even when its refusal payload is malformed."""

    exit_code: int
    stdout: str
    stderr: str


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    """Narrow an arbitrary JSON value to a string-keyed object, else None."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


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


def _is_deny_output(*, stdout: str) -> bool:
    """Whether a guard's stdout is a protocol-shaped refusal decision."""
    try:
        payload = _as_object_dict(value=json.loads(stdout))
    except ValueError:
        return False
    if payload is None:
        return False
    specific = _as_object_dict(value=payload.get("hookSpecificOutput"))
    return specific is not None and specific.get("permissionDecision") == "deny"


def _denies(*, result: tuple[int, str, str]) -> bool:
    """Whether a standalone-shaped result refuses the tool call."""
    exit_code, stdout, _ = result
    return exit_code == 2 or isinstance(result, _FailClosedResult) or _is_deny_output(stdout=stdout)


def _evaluate_guard(*, name: str, raw: str) -> tuple[int, str, str]:
    """Apply an individual guard's fail-open boundary without stopping later guards."""
    guard = _load_guard(name=name)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_runs_in_process, guard=guard, raw=raw)
        if future.exception() is None:
            return future.result()
    if name == "fleet_host_guard":
        decision = guard.fail_closed_decision()
        output = decision if decision.endswith("\n") else decision + "\n"
        return _FailClosedResult(exit_code=0, stdout=output, stderr="")
    return 0, "", ""


def _standalone_command(*, name: str) -> list[str]:
    """Build the unchanged standalone command for one unvisited guard."""
    return [sys.executable, str(Path(__file__).with_name(f"{name}.py"))]


def _run_standalone(*, name: str, raw: str) -> tuple[int, str, str]:
    """Run an unvisited guard through its standalone executable after dispatcher failure."""
    completed = subprocess.run(
        _standalone_command(name=name),
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


def _dispatch(*, state: _DispatchState) -> int:
    """Evaluate guards in registration order, retaining the first refusal."""
    state.raw = sys.stdin.read()
    for index, name in enumerate(GUARD_MODULE_NAMES):
        state.index = index
        result = _evaluate_guard(name=name, raw=state.raw)
        if state.refusal is None and _denies(result=result):
            state.refusal = result
    return 0 if state.refusal is None else _emit(result=state.refusal)


def main() -> int:
    """Dispatch every guard, then complete any interrupted dispatch standalone."""
    state = _DispatchState()
    try:
        return _dispatch(state=state)
    except Exception:  # noqa: BLE001 — sole fail-open hook boundary: silent pass-through, exit 0
        fallback = _fallback(index=state.index, raw=state.raw, refusal=state.refusal)
        return 0 if fallback is None else _emit(result=fallback)


if __name__ == "__main__":
    raise SystemExit(main())
