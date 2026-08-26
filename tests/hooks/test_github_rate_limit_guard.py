"""Unit tests for the plugin-shipped GitHub rate-limit PreToolUse guard."""

from __future__ import annotations

import importlib
import json
import re
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

_BACKTICKED = re.compile(r"`([^`]+)`")
_PLACEHOLDER = re.compile(r"<[^>]+>")
_UNCACHED_LOOPED_READ = "while true; do gh api repos/acme/project/pulls/1; sleep 5; done"


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


@pytest.mark.parametrize(
    "command",
    [
        # The English word "for" in a PR title is not a shell loop. This exact
        # command shape was refused three times while landing a plan-thread PR.
        'gh pr create --title "parameterize provisioning for the second host"',
        'gh pr create --title "a note on while-loops in the installer"',
        'gh pr create --title "hold until the ruling lands"',
        'gh pr create --title "raise the sleep budget on the healthcheck"',
        # Paths and flags that merely contain the tokens.
        "gh pr view 12 --json body --jq .body > /tmp/sleep-notes.txt",
        'gh run view 5 --log --jq "waiting for the scheduler"',
    ],
)
def test_allows_gh_calls_whose_prose_contains_loop_words(command: str) -> None:
    """A loop KEYWORD must sit in shell command position, not merely appear.

    `_SHELL_SELECT` was already narrowed this way by an earlier fix; the
    remaining tokens (`for`, `while`, `until`, `sleep`) stayed bare `\\b`
    matches, so any `gh pr` / `gh run` command whose text happened to contain
    those very ordinary English words was denied.
    """
    result = _run(stdin=_bash_input(command=command))
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "command",
    [
        # A real loop that does not start at string position 0. Narrowing the
        # keyword match to command position must not lose these.
        'cd /repo\nfor id in 1 2; do gh run view "$id" --json status; done',
        "cd /repo\nwhile true; do gh pr view 7 --json state; done",
        "echo start\nuntil gh api repos/acme/project/actions/runs; do sleep 2; done",
    ],
)
def test_denies_multiline_polling_github_reads(command: str) -> None:
    """A loop on its own line is still a loop."""
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "gh api --cache <duration>" in str(event)


@pytest.mark.parametrize(
    "command",
    [
        "cd /repo\nfor ref in a b; do gh api --method post repos/acme/p/git/refs; done",
        "cd /repo\nwhile read id; do gh api -X DELETE repos/acme/p/issues/comments/$id; done",
    ],
)
def test_denies_multiline_looped_github_mutations(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "mutations cost five points" in str(event)


def _prescribed_remedy(*, message: str) -> str:
    """Extract the one backticked command the read-deny message prescribes."""
    quoted = _BACKTICKED.findall(message)
    assert len(quoted) == 1, f"read-deny message must prescribe exactly one remedy: {message}"
    return quoted[0]


def test_read_deny_message_prescribes_a_remedy_the_decision_logic_allows() -> None:
    """The message and the decision logic are pinned to each other.

    `_READ_DENY_REASON` tells the agent to switch to a cached read; if
    `_has_read_gh_call` does not honour that exact form, the agent is denied
    for obeying the instruction it was just given. This test reads the remedy
    OUT of the live deny message rather than restating it, so an edit that
    changes what the message prescribes without teaching the logic to allow it
    fails here.
    """
    denied = _run(stdin=_bash_input(command=_UNCACHED_LOOPED_READ))
    assert denied.returncode == 2
    prescribed = _prescribed_remedy(message=str(_stderr_event(result=denied)["event"]))
    remedy = _PLACEHOLDER.sub("10m", prescribed)
    assert "<" not in remedy, f"unsubstituted placeholder in prescribed remedy: {prescribed}"
    allowed = _run(
        stdin=_bash_input(command=f"while true; do {remedy} repos/acme/p; sleep 5; done")
    )
    _assert_allowed(result=allowed)


@pytest.mark.parametrize(
    "command",
    [
        # The prescribed form, in every shape a caller writes it. A cache hit
        # answers 304, which spends no primary rate-limit budget -- the guard's
        # own stated rationale for prescribing it.
        "for r in a b c; do gh api --cache 10m repos/acme/project/pulls/$r; done",
        "sleep 30; gh api --cache 5m repos/acme/project/actions/runs",
        "while true; do gh api --cache=1h repos/acme/project/pulls/1; sleep 5; done",
        # Several reads in one loop body, every one of them cached.
        (
            "cd /repo\nfor r in a b; do gh api --cache 10m repos/acme/p/pulls/$r; "
            "gh api --cache 10m repos/acme/p/issues/$r; done"
        ),
    ],
)
def test_allows_looped_reads_whose_every_gh_api_is_cached(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "command",
    [
        # One uncached `gh api` in the loop body still spends budget.
        (
            "for r in a b; do gh api --cache 10m repos/acme/p/pulls/$r; "
            "gh api repos/acme/p/issues/$r; done"
        ),
        # `gh run` / `gh pr` have no response cache, so `--cache` on a
        # NEIGHBOURING `gh api` cannot exempt them.
        "while true; do gh api --cache 10m repos/acme/p; gh pr view 7 --json state; sleep 5; done",
        "for id in 1 2; do gh api --cache 10m repos/acme/p; gh run view $id; done",
        # A bare `--cache` with no duration is not the sanctioned form (and is
        # not even valid `gh`), so it must not buy an exemption.
        "while true; do gh api --cache; sleep 5; done",
        "while true; do gh api --cache --jq .id repos/acme/p; sleep 5; done",
    ],
)
def test_still_denies_looped_reads_with_any_uncached_gh_call(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "gh api --cache <duration>" in str(event)


def test_cache_flag_does_not_exempt_a_looped_mutation() -> None:
    """`--cache` is meaningless on a mutation; the mutation deny path is unchanged."""
    result = _run(
        stdin=_bash_input(
            command="for ref in a b; do gh api --cache 10m -X POST repos/acme/p/git/refs; done"
        )
    )
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "mutations cost five points" in str(event)
