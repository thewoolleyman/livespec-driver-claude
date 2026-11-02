"""Tests for the single-process Bash PreToolUse guard dispatcher."""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType

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


def test_dispatcher_failure_falls_back_to_each_remaining_standalone_guard(
    monkeypatch, capsys
) -> None:
    dispatcher = _load_dispatcher()
    prior_deny = (0, '{"prior": "deny"}\n', "")
    fallback_deny = (0, '{"fallback": "deny"}\n', "")
    first_guard, failing_guard, *remaining_guards = dispatcher.GUARD_MODULE_NAMES
    fallback_runs: list[str] = []

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
        return 0, "", ""

    monkeypatch.setattr(dispatcher, "_denies", is_deny)
    monkeypatch.setattr(dispatcher, "_evaluate_guard", fails_after_prior)
    monkeypatch.setattr(dispatcher, "_run_standalone", fallback_allows, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command="git status")))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == prior_deny[1]
    assert fallback_runs == [failing_guard, *remaining_guards]

    fallback_runs.clear()

    def allows_before_failure(*, name: str, raw: str) -> tuple[int, str, str]:
        assert raw == _bash_payload(command="git status")
        if name == first_guard:
            return 0, "", ""
        assert name == failing_guard
        raise RuntimeError("dispatcher broke")

    def fallback_refuses_once(*, name: str, raw: str) -> tuple[int, str, str]:
        assert raw == _bash_payload(command="git status")
        fallback_runs.append(name)
        return fallback_deny if name == failing_guard else (0, "", "")

    monkeypatch.setattr(dispatcher, "_evaluate_guard", allows_before_failure)
    monkeypatch.setattr(dispatcher, "_run_standalone", fallback_refuses_once)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command="git status")))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == fallback_deny[1]
    assert fallback_runs == [failing_guard, *remaining_guards]


def test_crashing_fail_closed_guard_refuses_while_every_other_guard_runs(
    monkeypatch, capsys
) -> None:
    dispatcher = _load_dispatcher()
    evaluated: list[str] = []
    failure_decision = '{"fleet_host_guard": "fail-closed"}\n'

    def allows(*, name: str) -> int:
        evaluated.append(name)
        return 0

    def crashes() -> int:
        evaluated.append("fleet_host_guard")
        raise RuntimeError("the fail-closed guard crashed")

    fleet_guard = ModuleType("fleet_host_guard")
    fleet_guard.main = crashes
    fleet_guard.fail_closed_decision = lambda: failure_decision
    guards: dict[str, ModuleType] = {"fleet_host_guard": fleet_guard}
    for name in dispatcher.GUARD_MODULE_NAMES:
        if name == "fleet_host_guard":
            continue
        guard = ModuleType(name)
        guard.main = lambda name=name: allows(name=name)
        guards[name] = guard

    monkeypatch.setattr(dispatcher, "_load_guard", lambda name: guards[name])
    monkeypatch.setattr(sys, "stdin", io.StringIO(_bash_payload(command="git status")))
    assert dispatcher.main() == 0
    assert capsys.readouterr().out == failure_decision
    assert evaluated == list(dispatcher.GUARD_MODULE_NAMES)
