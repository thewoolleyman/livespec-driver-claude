"""Unit tests for `.claude/hooks/livespec_footgun_guard.py`.

The script is exercised exactly as Claude Code runs it: as a subprocess
invoked `python3 <script>` (mirroring the project-local `.claude/`
PreToolUse Bash hook registration), with the PreToolUse hook input JSON
on stdin.

Contract under test (the hook's own docstring; livespec footgun-guard
family convention):

- Blocks ONLY patterns never legitimate in the livespec family, each as
  the EXECUTED leading command of a shell segment:
  - `git ... commit/push ... --no-verify`,
  - `git ... config core.bare <truthy>` (a SET, not a `--get`/`--unset`
    read),
  - a leading `LEFTHOOK=0|false|off|no` env-assignment.
  A block is emitted as a PreToolUse `permissionDecision: "deny"` JSON on
  stdout, and the process ALWAYS exits 0 (the guard is advisory; the
  commit-refuse hook + branch protection are the real backstops).
- Everything else is a silent pass-through (no stdout, exit 0): the same
  dangerous strings appearing as DATA (an `echo`, a here-doc body), a
  benign leading command, a read-only `git config --get`, a non-Bash
  tool, empty stdin, and malformed JSON (fails OPEN).

This test also pins the keyword-only refactor of the hook's internal
helpers (fleet-check-coverage `check-keyword-only-args` coverage): the
end-to-end deny/allow behavior below is invariant across that refactor,
so it guards against a regression in the helper call chain.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / ".claude" / "hooks" / "livespec_footgun_guard.py"


def _run_hook(*, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
        input=stdin,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _bash_input(*, command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _assert_denied(*, result: subprocess.CompletedProcess[str], reason_substring: str) -> None:
    assert result.returncode == 0
    output = json.loads(result.stdout)
    decision = output["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert reason_substring in decision["permissionDecisionReason"]


def _assert_silent(*, result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0
    assert result.stdout == ""


def test_denies_commit_no_verify() -> None:
    result = _run_hook(stdin=_bash_input(command="git commit --no-verify -m wip"))
    _assert_denied(result=result, reason_substring="--no-verify")


def test_denies_push_no_verify() -> None:
    result = _run_hook(stdin=_bash_input(command="git push --no-verify origin HEAD"))
    _assert_denied(result=result, reason_substring="--no-verify")


def test_denies_no_verify_after_mise_exec_wrapper() -> None:
    result = _run_hook(stdin=_bash_input(command="mise exec -- git commit --no-verify -m x"))
    _assert_denied(result=result, reason_substring="--no-verify")


def test_denies_core_bare_set_true() -> None:
    result = _run_hook(stdin=_bash_input(command="git config core.bare true"))
    _assert_denied(result=result, reason_substring="core.bare")


def test_denies_core_bare_equals_true() -> None:
    result = _run_hook(stdin=_bash_input(command="git config core.bare=true"))
    _assert_denied(result=result, reason_substring="core.bare")


def test_denies_lefthook_disabled_prefix() -> None:
    result = _run_hook(stdin=_bash_input(command="LEFTHOOK=0 git commit -m wip"))
    _assert_denied(result=result, reason_substring="LEFTHOOK")


def test_allows_no_verify_inside_heredoc_body() -> None:
    command = "cat > f <<'EOF'\ngit commit --no-verify\nEOF"
    result = _run_hook(stdin=_bash_input(command=command))
    _assert_silent(result=result)


def test_allows_no_verify_as_echo_data() -> None:
    result = _run_hook(stdin=_bash_input(command="echo git commit --no-verify"))
    _assert_silent(result=result)


def test_allows_core_bare_read() -> None:
    result = _run_hook(stdin=_bash_input(command="git config --get core.bare"))
    _assert_silent(result=result)


def test_allows_plain_commit() -> None:
    result = _run_hook(stdin=_bash_input(command="git commit -m 'real work'"))
    _assert_silent(result=result)


def test_ignores_non_bash_tool() -> None:
    stdin = json.dumps({"tool_name": "Write", "tool_input": {"command": "git commit --no-verify"}})
    result = _run_hook(stdin=stdin)
    _assert_silent(result=result)


def test_silent_on_empty_stdin() -> None:
    result = _run_hook(stdin="")
    _assert_silent(result=result)


def test_fails_open_on_malformed_json() -> None:
    result = _run_hook(stdin="{not valid json")
    _assert_silent(result=result)


def test_hook_script_present_and_executable() -> None:
    assert _HOOK_SCRIPT.is_file()
    assert os.access(_HOOK_SCRIPT, os.X_OK)
