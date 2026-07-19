"""Unit tests for `.claude-plugin/hooks/tmux_fleet_guard.py`.

The hook body is exercised IN-PROCESS via its importable `main() -> int`
(swapped `sys.stdin`, stdout/stderr via `redirect_stdout`/`redirect_stderr`)
for real per-file coverage, plus ONE retained subprocess smoke that proves
the shipped script still speaks the PreToolUse stdin/stdout protocol.

Contract under test (work-item livespec-driver-claude-w6f):

- DENY unscoped/default-resolving `tmux kill-server` and broad
  `pkill`/`killall` invocations whose arguments mention tmux.
- ALLOW explicitly non-default `tmux -L <name> kill-server` and
  non-fleet `tmux -S <path> kill-server` usage, ordinary tmux subcommands,
  and hazard words that appear only as data such as quoted echo/grep text or
  here-doc bodies.
- FAIL CLOSED when a raw command carries hazard hints but parsing or main
  handling raises; otherwise fail open silently.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / ".claude-plugin" / "hooks" / "tmux_fleet_guard.py"
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"


@dataclass(frozen=True, kw_only=True)
class HookResult:
    returncode: int
    stdout: str
    stderr: str


def _load_hook() -> ModuleType:
    assert _HOOK_SCRIPT.is_file()
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("tmux_fleet_guard", None)
    return importlib.import_module("tmux_fleet_guard")


def _bash_input(*, command: str, tool_name: str = "Bash") -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})


def _run_loaded(*, hook: ModuleType, stdin: str) -> HookResult:
    old_stdin = sys.stdin
    stdout = StringIO()
    stderr = StringIO()
    try:
        sys.stdin = StringIO(stdin)
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = hook.main()
    finally:
        sys.stdin = old_stdin
    return HookResult(returncode=returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def _run(*, stdin: str) -> HookResult:
    return _run_loaded(hook=_load_hook(), stdin=stdin)


def _run_hook_subprocess(*, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(_HOOK_SCRIPT)],
        input=stdin,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _assert_denied(*, result: HookResult | subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    decision = payload["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert "tmux -L <name> kill-server" in decision["permissionDecisionReason"]
    assert result.stderr == ""


def _assert_silent(*, result: HookResult | subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    "command",
    [
        "/usr/bin/tmux kill-server 2>/dev/null; /usr/bin/tmux new-session -d -s "
        "b2probe 'sleep 10'; /usr/bin/tmux list-sessions",
        "cd /tmp && TMUX_TMPDIR=/tmp /usr/bin/tmux kill-server 2>/dev/null; echo done",
        "tmux -L default kill-server",
        "TMUX_TMPDIR=/tmp tmux kill-server",
        "bash -c 'tmux kill-server'",
        "env TMUX_TMPDIR=/tmp tmux kill-server",
        "tmux -S /tmp/tmux-1000/default kill-server",
        "tmux kill-server",
        "pkill tmux",
        "pkill -f tmux",
        "killall tmux",
        "sh -c 'ls && tmux kill-server'",
        "tmux   kill-server",
        "TMUX_TMPDIR=/run/user/1000/agent tmux kill-server",
    ],
)
def test_blocks_hazardous_tmux_commands(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    _assert_denied(result=result)


@pytest.mark.parametrize(
    "command",
    [
        "tmux -L lc_e2e_x kill-server",
        "tmux -Llc_e2e_x kill-server",
        "tmux -S /run/agent/scratch.sock kill-server",
        "tmux kill-session -t foo",
        "tmux new-session -d -s work",
        "tmux list-sessions",
        "TMUX_TMPDIR=/tmp/tmux-agents-1000 tmux -L scratch kill-server",
        "echo hello && ls -la",
        "git commit -m 'fix the tmux launcher'",
        "git status",
        "tmux -L build_check kill-server && echo cleaned",
        "python3 -c 'print(1)'",
        "tmux -L foo kill-server",
        'echo "tmux kill-server"',
        'grep -rn "pkill tmux" tests',
        "git commit -F - <<'EOF'\n" "document pkill|killall tmux and tmux kill-server\n" "EOF",
    ],
)
def test_allows_scoped_or_non_executed_tmux_mentions(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    _assert_silent(result=result)


def test_subprocess_smoke_blocks_tmux_kill_server() -> None:
    """The shipped script path still speaks the PreToolUse hook protocol."""
    result = _run_hook_subprocess(stdin=_bash_input(command="tmux kill-server"))
    _assert_denied(result=result)


def test_hook_manifest_loads_guard_for_bash_pre_tool_use() -> None:
    manifest = json.loads((_REPO_ROOT / ".claude-plugin" / "hooks" / "hooks.json").read_text())
    bash_entries = [
        entry for entry in manifest["hooks"]["PreToolUse"] if entry.get("matcher") == "Bash"
    ]
    assert bash_entries == [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/tmux_fleet_guard.py"',
                }
            ],
        }
    ]


def test_ignores_non_bash_tool() -> None:
    result = _run(stdin=_bash_input(command="tmux kill-server", tool_name="Write"))
    _assert_silent(result=result)


def test_silent_on_empty_stdin() -> None:
    result = _run(stdin="")
    _assert_silent(result=result)


def test_silent_on_malformed_json() -> None:
    result = _run(stdin="{not valid json")
    _assert_silent(result=result)


def test_allows_dash_c_without_inner_command() -> None:
    result = _run(stdin=_bash_input(command="bash -c"))
    _assert_silent(result=result)


def test_allows_compact_dash_c_without_hazard() -> None:
    result = _run(stdin=_bash_input(command="bash -cecho"))
    _assert_silent(result=result)


def test_allows_dash_l_equals_scope() -> None:
    result = _run(stdin=_bash_input(command="tmux -L=scope kill-server"))
    _assert_silent(result=result)


def test_allows_operator_only_command() -> None:
    result = _run(stdin=_bash_input(command=";"))
    _assert_silent(result=result)


def test_allows_non_mapping_payload() -> None:
    result = _run(stdin="[]")
    _assert_silent(result=result)


def test_allows_missing_tool_input() -> None:
    result = _run(stdin=json.dumps({"tool_name": "Bash"}))
    _assert_silent(result=result)


def test_allows_missing_command() -> None:
    result = _run(stdin=json.dumps({"tool_name": "Bash", "tool_input": {}}))
    _assert_silent(result=result)


def test_fail_closes_when_classify_raises_with_hazard_hint(monkeypatch) -> None:
    hook = _load_hook()

    def broken_classify(*, command: str) -> bool:
        raise ValueError(command)

    monkeypatch.setattr(hook, "_classify", broken_classify)
    result = _run_loaded(hook=hook, stdin=_bash_input(command="tmux kill-server"))
    _assert_denied(result=result)


def test_fails_open_when_classify_raises_without_hazard_hint(monkeypatch) -> None:
    hook = _load_hook()

    def broken_classify(*, command: str) -> bool:
        raise ValueError(command)

    monkeypatch.setattr(hook, "_classify", broken_classify)
    result = _run_loaded(hook=hook, stdin=_bash_input(command="git status"))
    _assert_silent(result=result)


def test_main_fail_closes_when_decision_raises_with_hazard_hint(monkeypatch) -> None:
    hook = _load_hook()

    def broken_decision(*, raw: str) -> str | None:
        raise ValueError(raw)

    monkeypatch.setattr(hook, "_decision", broken_decision)
    result = _run_loaded(hook=hook, stdin=_bash_input(command="tmux kill-server"))
    _assert_denied(result=result)


def test_main_fail_closes_when_legacy_decision_result_raises_with_hazard_hint(
    monkeypatch,
) -> None:
    hook = _load_hook()

    def broken_decision_result(*, raw: str):
        raise RuntimeError(raw)

    if hasattr(hook, "_decision_result"):
        monkeypatch.setattr(hook, "_decision_result", broken_decision_result)
    result = _run_loaded(hook=hook, stdin=_bash_input(command="tmux kill-server"))
    _assert_denied(result=result)


def test_main_fails_open_when_decision_raises_without_hazard_hint(monkeypatch) -> None:
    hook = _load_hook()

    def broken_decision(*, raw: str) -> str | None:
        raise ValueError(raw)

    monkeypatch.setattr(hook, "_decision", broken_decision)
    result = _run_loaded(hook=hook, stdin=_bash_input(command="git status"))
    _assert_silent(result=result)


def test_allows_unterminated_heredoc_body_mentions() -> None:
    command = "git commit -F - <<'EOF'\ntmux kill-server"
    result = _run(stdin=_bash_input(command=command))
    _assert_silent(result=result)


def test_allows_shell_without_dash_c() -> None:
    result = _run(stdin=_bash_input(command="bash -l"))
    _assert_silent(result=result)


def test_missing_option_value_returns_none() -> None:
    hook = _load_hook()
    assert hook._option_value(tokens=["tmux", "-L"], flag="-L") is None


def test_env_only_segment_is_not_hazard() -> None:
    result = _run(stdin=_bash_input(command="TMUX_TMPDIR=/tmp"))
    _assert_silent(result=result)
