"""Tests for the single-process Bash PreToolUse guard dispatcher."""

from __future__ import annotations

import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
_DISPATCHER = _HOOKS_DIR / "pretooluse_dispatch.py"
_DISPATCH_COMMAND = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse_dispatch.py"'
_BASH_GUARDS = (
    "tmux_fleet_guard",
    "github_rate_limit_guard",
    "block_raw_bd_create",
    "fleet_host_guard",
    "block_auto_memory",
)


def _load_dispatcher():
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("pretooluse_dispatch", None)
    return importlib.import_module("pretooluse_dispatch")


def _bash_payload(*, command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def test_non_object_guard_output_fails_open() -> None:
    """A guard's malformed stdout cannot turn an otherwise-allowed call into a deny."""
    dispatcher = _load_dispatcher()

    assert dispatcher._as_object_dict(value=[]) is None


def test_denial_output_must_be_a_protocol_object() -> None:
    """Only a protocol-shaped denial JSON is a refusal."""
    dispatcher = _load_dispatcher()

    assert dispatcher._is_deny_output(
        stdout='{"hookSpecificOutput": {"permissionDecision": "deny"}}'
    )
    assert not dispatcher._is_deny_output(stdout='{"permissionDecision": "deny"}')


def test_standalone_command_uses_the_installed_guard_script() -> None:
    """Fallback preserves the standalone executable shape for each unvisited guard."""
    dispatcher = _load_dispatcher()

    assert dispatcher._standalone_command(name="tmux_fleet_guard") == [
        sys.executable,
        str(_HOOKS_DIR / "tmux_fleet_guard.py"),
    ]


def test_malformed_and_non_object_guard_outputs_fail_open() -> None:
    dispatcher = _load_dispatcher()

    assert not dispatcher._is_deny_output(stdout="{")
    assert not dispatcher._is_deny_output(stdout="[]")


def test_non_integer_guard_result_is_not_a_valid_standalone_boundary() -> None:
    dispatcher = _load_dispatcher()
    guard = ModuleType("invalid_guard")
    guard.main = lambda: True

    with pytest.raises(TypeError):
        dispatcher._runs_in_process(guard=guard, raw="")


def test_standalone_and_emit_failure_boundaries_preserve_exit_two(monkeypatch, capsys) -> None:
    dispatcher = _load_dispatcher()
    expected = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="refusal\n")
    monkeypatch.setattr(dispatcher.subprocess, "run", lambda *_args, **_kwargs: expected)

    assert dispatcher._run_standalone(name="tmux_fleet_guard", raw="payload") == (
        2,
        "",
        "refusal\n",
    )
    assert dispatcher._emit(result=(2, "", "refusal\n")) == 2
    assert capsys.readouterr().err == "refusal\n"


def test_fallback_continues_when_one_standalone_process_cannot_start(monkeypatch) -> None:
    dispatcher = _load_dispatcher()
    runs: list[str] = []

    def unavailable_once(*, name: str, raw: str) -> tuple[int, str, str]:
        _ = raw
        runs.append(name)
        if name == dispatcher.GUARD_MODULE_NAMES[0]:
            raise OSError("not executable")
        return 0, "", ""

    monkeypatch.setattr(dispatcher, "_run_standalone", unavailable_once)

    assert dispatcher._fallback(index=0, raw="payload", refusal=None) is None
    assert runs == list(dispatcher.GUARD_MODULE_NAMES)


@pytest.mark.integration
def test_one_bash_tool_call_starts_one_python_process_for_driver_pretooluse_guards(
    monkeypatch, capsys
) -> None:
    manifest = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    bash_entries = [
        entry for entry in manifest["hooks"]["PreToolUse"] if entry.get("matcher") == "Bash"
    ]

    assert bash_entries == [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": _DISPATCH_COMMAND}]}
    ]
    assert _DISPATCHER.is_file()

    dispatcher = _load_dispatcher()
    assert dispatcher.GUARD_MODULE_NAMES == _BASH_GUARDS
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == ""

    memory_entries = [
        entry
        for entry in manifest["hooks"]["PreToolUse"]
        if entry.get("matcher") == "Write|Edit|MultiEdit"
    ]
    assert memory_entries == [
        {
            "matcher": "Write|Edit|MultiEdit",
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/block_auto_memory.py"',
                }
            ],
        }
    ]


@pytest.mark.integration
def test_crashing_fail_open_guard_does_not_disable_other_guards_or_the_call(
    monkeypatch, capsys
) -> None:
    dispatcher = _load_dispatcher()
    evaluated: list[str] = []
    deny = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "the next guard's standalone reason",
            }
        }
    )

    def crashing_main() -> int:
        evaluated.append("github_rate_limit_guard")
        raise RuntimeError("fail open")

    def denying_main() -> int:
        evaluated.append("tmux_fleet_guard")
        _ = sys.stdout.write(deny + "\n")
        return 0

    def allowing_main(*, name: str) -> int:
        evaluated.append(name)
        return 0

    guards: dict[str, ModuleType] = {
        "github_rate_limit_guard": ModuleType("github_rate_limit_guard"),
        "tmux_fleet_guard": ModuleType("tmux_fleet_guard"),
        "block_raw_bd_create": ModuleType("block_raw_bd_create"),
        "fleet_host_guard": ModuleType("fleet_host_guard"),
        "block_auto_memory": ModuleType("block_auto_memory"),
    }
    guards["github_rate_limit_guard"].main = crashing_main
    guards["tmux_fleet_guard"].main = denying_main
    for name in ("block_raw_bd_create", "fleet_host_guard", "block_auto_memory"):
        guards[name].main = lambda name=name: allowing_main(name=name)

    monkeypatch.setattr(dispatcher, "_load_guard", lambda name: guards[name], raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command="git status")))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == deny + "\n"
    assert evaluated == list(dispatcher.GUARD_MODULE_NAMES)

    evaluated.clear()
    guards["tmux_fleet_guard"].main = lambda: allowing_main(name="tmux_fleet_guard")
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command="git status")))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == ""
    assert evaluated == list(dispatcher.GUARD_MODULE_NAMES)


@pytest.mark.integration
def test_dispatcher_failure_falls_back_to_each_remaining_standalone_guard(
    monkeypatch, capsys
) -> None:
    dispatcher = _load_dispatcher()
    prior_deny = (0, '{"prior": "deny"}\n', "")
    fallback_deny = (0, '{"fallback": "deny"}\n', "")
    first_guard, failing_guard, *remaining_guards = dispatcher.GUARD_MODULE_NAMES
    fallback_runs: list[str] = []
    fallback_inputs: list[str] = []

    def is_deny(*, result: tuple[int, str, str]) -> bool:
        return result in (prior_deny, fallback_deny)

    def fails_after_prior(*, name: str, raw: str) -> tuple[int, str, str]:
        assert raw == _bash_payload(command="git status")
        if name == first_guard:
            return prior_deny
        assert name == failing_guard
        raise RuntimeError("dispatcher broke")

    def fallback_allows(*, name: str, raw: str) -> tuple[int, str, str]:
        assert raw == _bash_payload(command="git status")
        fallback_runs.append(name)
        fallback_inputs.append(raw)
        return 0, "", ""

    monkeypatch.setattr(dispatcher, "_denies", is_deny)
    monkeypatch.setattr(dispatcher, "_evaluate_guard", fails_after_prior)
    monkeypatch.setattr(dispatcher, "_run_standalone", fallback_allows, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command="git status")))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == prior_deny[1]
    assert fallback_runs == [failing_guard, *remaining_guards]
    assert fallback_inputs == [_bash_payload(command="git status")] * len(fallback_runs)

    fallback_runs.clear()
    fallback_inputs.clear()

    def allows_before_failure(*, name: str, raw: str) -> tuple[int, str, str]:
        assert raw == _bash_payload(command="git status")
        if name == first_guard:
            return 0, "", ""
        assert name == failing_guard
        raise RuntimeError("dispatcher broke")

    def fallback_refuses_once(*, name: str, raw: str) -> tuple[int, str, str]:
        assert raw == _bash_payload(command="git status")
        fallback_runs.append(name)
        fallback_inputs.append(raw)
        return fallback_deny if name == failing_guard else (0, "", "")

    monkeypatch.setattr(dispatcher, "_evaluate_guard", allows_before_failure)
    monkeypatch.setattr(dispatcher, "_run_standalone", fallback_refuses_once)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command="git status")))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == fallback_deny[1]
    assert fallback_runs == [failing_guard, *remaining_guards]
    assert fallback_inputs == [_bash_payload(command="git status")] * len(fallback_runs)

    class BrokenInput:
        def read(self) -> str:
            raise OSError("stdin is unreadable")

    fallback_runs.clear()
    fallback_inputs.clear()
    monkeypatch.setattr(sys, "stdin", BrokenInput())

    def fallback_after_read_failure(*, name: str, raw: str) -> tuple[int, str, str]:
        assert raw == ""
        fallback_runs.append(name)
        fallback_inputs.append(raw)
        return 0, "", ""

    monkeypatch.setattr(dispatcher, "_run_standalone", fallback_after_read_failure)
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == ""
    assert fallback_runs == list(dispatcher.GUARD_MODULE_NAMES)
    assert fallback_inputs == [""] * len(fallback_runs)


def _run_with_crashing_fleet_guard(
    *, dispatcher, monkeypatch, command: str, hinted: bool, failure_decision: str
) -> list[str]:
    evaluated: list[str] = []

    def allows(*, name: str) -> int:
        evaluated.append(name)
        return 0

    def crashes() -> int:
        evaluated.append("fleet_host_guard")
        raise RuntimeError("the fail-closed guard crashed")

    fleet_guard = ModuleType("fleet_host_guard")
    fleet_guard.main = crashes
    fleet_guard.fail_closed_decision = lambda: failure_decision
    fleet_guard.has_hazard_hint = lambda *, raw: hinted and command in raw
    guards: dict[str, ModuleType] = {"fleet_host_guard": fleet_guard}
    for name in dispatcher.GUARD_MODULE_NAMES:
        if name == "fleet_host_guard":
            continue
        guard = ModuleType(name)
        guard.main = lambda name=name: allows(name=name)
        guards[name] = guard

    monkeypatch.setattr(dispatcher, "_load_guard", lambda name: guards[name])
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command=command)))
    return evaluated


@pytest.mark.integration
def test_crashing_fail_closed_guard_refuses_while_every_other_guard_runs(
    monkeypatch, capsys
) -> None:
    dispatcher = _load_dispatcher()
    failure_decision = '{"fleet_host_guard": "fail-closed"}\n'
    evaluated = _run_with_crashing_fleet_guard(
        dispatcher=dispatcher,
        monkeypatch=monkeypatch,
        command="ssh fleet-host uptime",
        hinted=True,
        failure_decision=failure_decision,
    )
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == failure_decision
    assert evaluated == list(dispatcher.GUARD_MODULE_NAMES)


@pytest.mark.integration
def test_crashing_fail_closed_guard_allows_a_payload_without_a_hazard_hint(
    monkeypatch, capsys
) -> None:
    dispatcher = _load_dispatcher()
    evaluated = _run_with_crashing_fleet_guard(
        dispatcher=dispatcher,
        monkeypatch=monkeypatch,
        command="git status",
        hinted=False,
        failure_decision='{"fleet_host_guard": "fail-closed"}\n',
    )
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == ""
    assert evaluated == list(dispatcher.GUARD_MODULE_NAMES)


def test_fleet_guard_exposes_its_standalone_hazard_hint_judgement() -> None:
    """The dispatcher judges the fail-closed trigger with the guard's own hint rule."""
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    fleet_guard = importlib.import_module("fleet_host_guard")

    assert not fleet_guard.has_hazard_hint(raw=_bash_payload(command="git status"))
