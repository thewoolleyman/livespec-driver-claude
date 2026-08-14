"""Unit tests for the plugin-shipped GitHub rate-limit PreToolUse guard."""

from __future__ import annotations

import importlib
import json
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
_HOOK_SCRIPT = _HOOKS_DIR / "github_rate_limit_guard.py"


@dataclass(frozen=True, kw_only=True)
class HookResult:
    returncode: int
    stdout: str
    stderr: str


def _load_hook() -> ModuleType:
    assert _HOOK_SCRIPT.is_file()
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("github_rate_limit_guard", None)
    return importlib.import_module("github_rate_limit_guard")


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


def _stderr_event(*, result: HookResult) -> dict[str, object]:
    assert result.stdout == ""
    assert result.stderr
    parsed = json.loads(result.stderr)
    assert isinstance(parsed, dict)
    return parsed


def _assert_allowed(*, result: HookResult) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    "command",
    [
        "while true; do gh pr view 7 --json headRefOid; sleep 5; done",
        'for id in 1 2; do gh run view "$id" --json status; done',
        "until gh api repos/acme/project/actions/runs; do sleep 2; done",
        "sleep 10 && gh api repos/acme/project/pulls/1",
    ],
)
def test_denies_polling_github_reads(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "gh api --cache <duration>" in str(event)
    assert "304 response costs no primary rate-limit budget" in str(event)


@pytest.mark.parametrize(
    "command",
    [
        "while read id; do gh api -X DELETE repos/acme/project/issues/comments/$id; done",
        "printf '%s\\n' 1 2 | xargs -I{} gh api --method PATCH repos/acme/project/issues/{}",
        "for ref in a b; do gh api --method post repos/acme/project/git/refs; done",
        "cat files | xargs gh api -X put repos/acme/project/contents/path",
    ],
)
def test_denies_looped_or_xargs_github_mutations(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "mutations cost five points" in str(event)
    assert "nine-hundred-point-per-minute ceiling" in str(event)
    assert "one second between mutations is required" in str(event)


def test_allows_single_ordinary_gh_pr_view() -> None:
    result = _run(stdin=_bash_input(command="gh pr view 123 --json headRefOid"))
    _assert_allowed(result=result)


def test_allows_gh_read_with_jq_select_filter() -> None:
    result = _run(
        stdin=_bash_input(
            command=(
                "gh pr list --json number,headRefName "
                "--jq '.[] | select(.headRefName == \"feature\") | .number'"
            )
        )
    )
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "stdin",
    [
        "",
        "{not valid json",
        "[]",
        json.dumps({"tool_name": "Bash"}),
        json.dumps({"tool_name": "Bash", "tool_input": {}}),
        json.dumps({"tool_name": "Bash", "tool_input": {"command": 5}}),
        _bash_input(command="while true; do gh pr view 1; done", tool_name="Write"),
    ],
)
def test_error_and_out_of_scope_paths_fail_open(stdin: str) -> None:
    result = _run(stdin=stdin)
    assert result.returncode == 0
    assert result.stdout == ""


def test_crash_path_fails_open(monkeypatch) -> None:
    hook = _load_hook()

    def broken_guard(*, raw_input: str) -> int:
        raise ValueError(raw_input)

    monkeypatch.setattr(hook, "_guard", broken_guard)
    result = _run_loaded(hook=hook, stdin=_bash_input(command="while true; do gh pr view 1; done"))
    assert result.returncode == 0
    assert result.stdout == ""
    event = _stderr_event(result=result)
    assert event.get("check_id") == "github-rate-limit-guard-crash"


def test_hook_manifest_loads_rate_limit_guard_for_bash_pre_tool_use() -> None:
    manifest = json.loads((_HOOKS_DIR / "hooks.json").read_text())
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
                },
                {
                    "type": "command",
                    "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/github_rate_limit_guard.py"',
                },
            ],
        }
    ]
