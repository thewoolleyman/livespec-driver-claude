"""Tests for the shipped primary-checkout Playwright PreToolUse guard."""

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
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
_HOOK_SCRIPT = _HOOKS_DIR / "primary_checkout_playwright_guard.py"


@dataclass(frozen=True, kw_only=True)
class HookResult:
    returncode: int
    stdout: str
    stderr: str


def _load_hook() -> ModuleType:
    assert _HOOK_SCRIPT.is_file()
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("primary_checkout_playwright_guard", None)
    return importlib.import_module("primary_checkout_playwright_guard")


def _payload(*, cwd: object | None, tool_name: object) -> str:
    value: dict[str, object] = {
        "tool_name": tool_name,
        "tool_input": {"filename": "install-livespec-pr-bot.png"},
    }
    if cwd is not None:
        value["cwd"] = str(cwd) if isinstance(cwd, Path) else cwd
    return json.dumps(value)


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
    return HookResult(
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )


def _run_loaded_input(*, stdin: str) -> HookResult:
    return _run_loaded(hook=_load_hook(), stdin=stdin)


def _run_hook(*, cwd: Path, tool_name: str) -> HookResult:
    completed = subprocess.run(
        ["python3", str(_HOOK_SCRIPT)],
        input=_payload(cwd=cwd, tool_name=tool_name),
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return HookResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _git(*, cwd: Path, args: tuple[str, ...]) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def _governed_repo(*, root: Path) -> Path:
    repo = root / "primary"
    repo.mkdir()
    _git(cwd=repo, args=("init", "--initial-branch=master"))
    _git(cwd=repo, args=("config", "user.email", "tests@example.invalid"))
    _git(cwd=repo, args=("config", "user.name", "Hook Tests"))
    _ = (repo / ".livespec.jsonc").write_text("{}\n", encoding="utf-8")
    _git(cwd=repo, args=("add", ".livespec.jsonc"))
    _git(cwd=repo, args=("commit", "-m", "test fixture"))
    return repo


def _assert_denied(*, result: HookResult) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout, "expected a PreToolUse deny decision"
    payload = json.loads(result.stdout)
    decision = payload["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert "secondary worktree" in decision["permissionDecisionReason"]
    assert result.stderr == ""


def _assert_allowed(*, result: HookResult) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.integration
def test_primary_checkout_playwright_guard_realizes_contract(tmp_path: Path) -> None:
    primary = _governed_repo(root=tmp_path)

    for tool_name in (
        "mcp__playwright__browser_take_screenshot",
        "mcp__playwright__browser_navigate",
    ):
        _assert_denied(result=_run_hook(cwd=primary, tool_name=tool_name))

    assert not (primary / "install-livespec-pr-bot.png").exists()
    assert not (primary / ".playwright-mcp").exists()

    linked = tmp_path / "linked"
    _git(cwd=primary, args=("worktree", "add", "-b", "browser-work", str(linked)))
    _assert_allowed(
        result=_run_hook(
            cwd=linked,
            tool_name="mcp__playwright__browser_take_screenshot",
        )
    )


def test_nested_cwd_in_governed_primary_is_denied(tmp_path: Path) -> None:
    primary = _governed_repo(root=tmp_path)
    nested = primary / "nested" / "path"
    nested.mkdir(parents=True)
    _assert_denied(
        result=_run_loaded_input(
            stdin=_payload(
                cwd=nested,
                tool_name="mcp__playwright__browser_snapshot",
            )
        )
    )


def test_non_governed_repo_and_non_repo_are_allowed(tmp_path: Path) -> None:
    repo = tmp_path / "ordinary-repo"
    repo.mkdir()
    _git(cwd=repo, args=("init", "--initial-branch=master"))
    tool_name = "mcp__playwright__browser_take_screenshot"
    _assert_allowed(result=_run_loaded_input(stdin=_payload(cwd=repo, tool_name=tool_name)))

    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()
    _assert_allowed(result=_run_loaded_input(stdin=_payload(cwd=non_repo, tool_name=tool_name)))


@pytest.mark.parametrize(
    "stdin",
    [
        "",
        "{not valid json",
        "[]",
        _payload(cwd=None, tool_name="mcp__playwright__browser_snapshot"),
        _payload(cwd=7, tool_name="mcp__playwright__browser_snapshot"),
        _payload(cwd="/tmp", tool_name=7),
        _payload(cwd="/tmp", tool_name="Bash"),
    ],
)
def test_ambiguous_and_out_of_scope_inputs_fail_open(stdin: str) -> None:
    _assert_allowed(result=_run_loaded_input(stdin=stdin))


def test_unexpected_git_output_fails_open(monkeypatch, tmp_path: Path) -> None:
    hook = _load_hook()

    def malformed_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="one\ntwo\n", stderr=""
        )

    monkeypatch.setattr(hook.subprocess, "run", malformed_git)
    result = _run_loaded(
        hook=hook,
        stdin=_payload(
            cwd=tmp_path,
            tool_name="mcp__playwright__browser_snapshot",
        ),
    )
    _assert_allowed(result=result)


def test_crash_path_fails_open(monkeypatch, tmp_path: Path) -> None:
    hook = _load_hook()

    def broken_guard(*, raw_input: str) -> dict[str, object] | None:
        raise ValueError(raw_input)

    monkeypatch.setattr(hook, "_guard", broken_guard)
    result = _run_loaded(
        hook=hook,
        stdin=_payload(
            cwd=tmp_path,
            tool_name="mcp__playwright__browser_snapshot",
        ),
    )
    _assert_allowed(result=result)


def test_hook_manifest_registers_every_playwright_tool() -> None:
    manifest = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in manifest["hooks"]["PreToolUse"]
        if entry.get("matcher") == "mcp__playwright__.*"
    ]
    assert entries == [
        {
            "matcher": "mcp__playwright__.*",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/'
                        'primary_checkout_playwright_guard.py"'
                    ),
                }
            ],
        }
    ]
