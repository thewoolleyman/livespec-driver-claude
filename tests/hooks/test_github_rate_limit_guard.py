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
from typing import cast

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
_HOOK_SCRIPT = _HOOKS_DIR / "github_rate_limit_guard.py"

_BACKTICKED = re.compile(r"`([^`]+)`")
_PLACEHOLDER = re.compile(r"<[^>]+>")
_UNCACHED_LOOPED_READ = "while true; do gh api repos/acme/project/pulls/1; sleep 5; done"
# The literal-iteration threshold the hook's module docstring records and its
# decision logic enforces. Restated here rather than imported, so an edit that
# moves the number in one place and not the other fails the pinning test below.
_LITERAL_ITERATION_THRESHOLD = 10


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
        'for id in $(seq 1 20); do gh run view "$id" --json status; done',
        "until gh api repos/acme/project/actions/runs; do sleep 2; done",
        # A literal list is bounded, but a `sleep` in the body makes it a POLL
        # rather than an enumeration, so the bounded exemption does not apply.
        "for id in 1 2; do gh run view $id --json status; sleep 5; done",
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
        'cd /repo\nfor id in $(seq 1 9); do gh run view "$id" --json status; done',
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
        # own stated rationale for prescribing it. Every loop here is one the
        # bounded-literal exemption does NOT reach, so the cached form is the
        # only thing standing between these commands and a denial.
        "for r in $(seq 1 50); do gh api --cache 10m repos/acme/project/pulls/$r; done",
        "until gh api --cache 5m repos/acme/project/actions/runs; do sleep 30; done",
        "while true; do gh api --cache=1h repos/acme/project/pulls/1; sleep 5; done",
        # Several reads in one loop body, every one of them cached.
        (
            "cd /repo\nfor r in $(cat refs); do gh api --cache 10m repos/acme/p/pulls/$r; "
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
            "for r in $(cat refs); do gh api --cache 10m repos/acme/p/pulls/$r; "
            "gh api repos/acme/p/issues/$r; done"
        ),
        # `gh run` / `gh pr` have no response cache, so `--cache` on a
        # NEIGHBOURING `gh api` cannot exempt them.
        "while true; do gh api --cache 10m repos/acme/p; gh pr view 7 --json state; sleep 5; done",
        "for id in $(seq 1 30); do gh api --cache 10m repos/acme/p; gh run view $id; done",
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


@pytest.mark.parametrize(
    "command",
    [
        # A Python heredoc. `for run in runs:` starts a line, which under
        # MULTILINE reads exactly like shell command position, and `gh pr view`
        # is text the script PRINTS rather than a command the shell RUNS.
        "python3 - <<'PY'\nfor run in runs:\n    print(\"gh pr view\", run)\nPY",
        # The live instance hit while measuring this defect: a heredoc body
        # carrying both a loop and the guard's own matching regex as a literal.
        (
            "python3 - <<'PY'\n"
            "for c in denied:\n"
            '    if re.search(r"gh\\s+(?:run|pr|api)", c):\n'
            '        print("gh pr view", c)\n'
            "PY"
        ),
        # An unquoted delimiter, and a `<<-` terminator indented with a tab.
        (
            "cat > /tmp/note.md <<-EOF\n"
            "for each PR we run gh pr view once, which is the burst to avoid.\n"
            "\tEOF"
        ),
        # A second heredoc opened after the first one closes.
        (
            "cat <<A > /tmp/a\nfor a in 1; do gh pr view 1; done\nA\n"
            "cat <<B > /tmp/b\nsleep 5; gh api repos/acme/p\nB"
        ),
    ],
)
def test_allows_heredoc_bodies_that_only_look_like_shell_loops(command: str) -> None:
    """A heredoc body is DATA the shell hands to a program, not commands it runs.

    `_CMD_POS` anchors loop keywords to command position, but every line of a
    heredoc body begins a line, so under MULTILINE the whole body reads as
    command position. 31 of the 109 no-`gh`-at-command-position false denials
    over the 7 days to 2026-08-26 were bodies of exactly this shape.
    """
    result = _run(stdin=_bash_input(command=command))
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "command",
    [
        # A multi-line `python3 -c` script: the interpreter is not a shell, so
        # its `for` is a Python loop and its `gh pr view` is a printed string.
        "python3 -c \"\nfor run in runs:\n    print('gh pr view', run)\n\"",
        # `-c` on a non-shell interpreter is a quoted argument like any other.
        "node -e \"\nfor (const id of ids) {\n  log('gh run view ' + id)\n}\n\"",
        # A `grep` whose SEARCH PATTERN spells both signals. This exact shape
        # was refused twice while the defect was being measured.
        'grep -rnE "gh api|for loop" .',
        "rg -nE 'sleep 5|gh pr view' .",
        # A real shell loop whose only `gh` is inside the grep PATTERN it reads
        # from: the loop runs, but it spends no GitHub budget.
        "grep -rn 'gh api' logs | while read -r line; do echo \"$line\"; done",
    ],
)
def test_allows_quoted_bodies_and_search_patterns_that_merely_spell_the_tokens(
    command: str,
) -> None:
    """A token inside a quoted string is an ARGUMENT, not a command.

    109 of 615 denials over the 7 days to 2026-08-26 carried no `gh` invocation
    at command position at all -- `gh` appeared only inside a string, a path or
    a regex.
    """
    result = _run(stdin=_bash_input(command=command))
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "command",
    [
        # A shell interpreter's `-c` payload IS shell, so it is re-read rather
        # than masked: this is a genuine polling loop over uncached reads.
        "bash -c 'while true; do gh pr view 7 --json state; sleep 5; done'",
        'sh -lc "for id in $(seq 1 30); do gh run view $id; done"',
        "/bin/bash -c 'for r in $(cat refs); do gh api repos/acme/p/pulls/$r; done'",
        # The mutation-burst shape that hides a `gh api -X PATCH` one quoting
        # level down from the `xargs` that drives it.
        "cat ids | xargs -I{} bash -c 'gh api -X PATCH repos/acme/p/issues/{}'",
        # `<<<` is a HERE-STRING, not a heredoc: nothing after it is a body.
        "while true; do gh api repos/acme/p <<<'{}'; sleep 5; done",
        # An escaped quote is a literal character; it must not open a span that
        # swallows the real loop behind it.
        'echo \\" ; while true; do gh pr view 1; sleep 5; done',
        # A trailing backslash must not run the scanner off the end.
        "while true; do gh pr view 1; sleep 5; done \\",
    ],
)
def test_still_denies_real_loops_over_uncached_reads_after_masking(command: str) -> None:
    """Masking removes data, never behavior: every true positive still denies."""
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "DENIED by github_rate_limit_guard.py" in str(event)


@pytest.mark.parametrize(
    "command",
    [
        # An unterminated quote and an unterminated heredoc are shell syntax
        # errors. The guard resolves them the way the shell reads them -- as an
        # open span running to the end -- which is the fail-OPEN direction.
        "echo 'oops ; while true; do gh pr view 1; sleep 5; done",
        'echo "oops ; while true; do gh pr view 1; sleep 5; done',
        "cat <<EOF\nfor i in 1 2; do gh pr view $i; done",
        # An escaped quote INSIDE a double-quoted span does not close it.
        'echo "say \\"hi\\"; while true; do gh pr view 1; sleep 5; done"',
    ],
)
def test_unbalanced_quoting_fails_open(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "command",
    [
        # Six calls, and the six is written out in the command itself.
        "for id in 1 2 3 4 5 6; do gh pr view $id --json state; done",
        'for id in 1 2; do gh run view "$id" --json status; done',
        # A loop that starts on a later line is bounded just the same.
        "cd /repo\nfor id in 1 2; do gh run view $id --json status; done",
        # Several reads per iteration still totals a legible, small number.
        "for r in a b; do gh api repos/acme/p/pulls/$r; gh api repos/acme/p/issues/$r; done",
        # A `sleep` OUTSIDE every loop body does not turn enumeration into
        # polling, whichever side of the loop it falls on.
        "sleep 5; for id in 1 2 3; do gh pr view $id --json state; done",
        "for id in 1 2 3; do gh pr view $id --json state; done; sleep 5",
    ],
)
def test_allows_bounded_literal_loops_over_reads(command: str) -> None:
    """A loop whose iteration count is written out in the command is not a burst.

    The ceiling this guard defends is nine hundred points per minute and a read
    costs one of them, so a handful of reads cannot approach it. Denying a
    six-iteration literal loop exactly as hard as `for p in $(seq 1 500)` was
    true only in letter.
    """
    result = _run(stdin=_bash_input(command=command))
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "command",
    [
        "sleep 10 && gh api repos/acme/project/pulls/1",
        "sleep 30; gh api repos/acme/project/actions/runs",
        "sleep 60 && gh pr view 7 --json state",
    ],
)
def test_allows_a_bare_sleep_before_a_single_read(command: str) -> None:
    """One sleep and one read is polite polling, the opposite of a burst.

    44 of 615 denials over the 7 days to 2026-08-26 were exactly this shape.
    """
    result = _run(stdin=_bash_input(command=command))
    _assert_allowed(result=result)


@pytest.mark.parametrize(
    "command",
    [
        # Command substitution: the word count is produced at run time, so it
        # is not readable from the command text at any apparent size.
        "for p in $(seq 1 500); do gh pr view $p --json state; done",
        "for p in $(seq 1 3); do gh pr view $p --json state; done",
        "for p in `cat prs.txt`; do gh pr view $p --json state; done",
        # A parameter expansion, a glob and a brace expansion are all expanded
        # by the shell into an unknown number of words.
        "for p in $PRS; do gh pr view $p --json state; done",
        "for f in *.json; do gh api repos/acme/p/pulls/1; done",
        "for p in {1..500}; do gh pr view $p --json state; done",
        # `"$@"` masks to the same token as `"main"` but expands to as many
        # words as the caller passed, so a bare masked item cannot be trusted.
        'for p in "$@"; do gh pr view $p --json state; done',
        # A C-style header carries no `in` list to read a bound out of.
        "for ((i=0; i<50; i++)); do gh pr view $i --json state; done",
        # `while`, `until` and `select` have no bound to read at all.
        "while read -r p; do gh pr view $p --json state; done < prs.txt",
        "until gh pr view 7 --json state; do sleep 2; done",
        "select R in a b; do gh pr view $R --json state; done",
    ],
)
def test_denies_loops_whose_iteration_count_is_not_readable(command: str) -> None:
    """Only a literal list states its own size; everything else stays denied."""
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "gh api --cache <duration>" in str(event)


@pytest.mark.parametrize(
    "command",
    [
        # A `sleep` in the body means the loop is waiting for state to change
        # rather than fetching a known list -- polling, not enumeration.
        "for id in 1 2 3; do gh pr view $id --json state; sleep 5; done",
        # A missing `done` is a shell syntax error; the body runs to the end of
        # the command, which is where the shell itself would take it.
        "for id in 1 2 3; do gh pr view $id --json state; sleep 5",
        # A `done` with no open `do` is likewise a syntax error: it closes
        # nothing, so it cannot move the sleep out of the body before it.
        "for id in 1 2; do gh pr view $id; sleep 1; done; done",
        # Nested bounded loops: the sleep sits in the INNER body.
        "for a in 1 2; do for b in 3 4; do gh pr view $a$b; sleep 1; done; done",
    ],
)
def test_denies_a_sleep_inside_a_bounded_literal_loop_body(command: str) -> None:
    result = _run(stdin=_bash_input(command=command))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "gh api --cache <duration>" in str(event)


def _literal_loop(*, count: int) -> str:
    items = " ".join(str(number) for number in range(1, count + 1))
    return f"for p in {items}; do gh pr view $p --json state; done"


def test_allows_a_literal_loop_at_the_recorded_threshold() -> None:
    result = _run(stdin=_bash_input(command=_literal_loop(count=_LITERAL_ITERATION_THRESHOLD)))
    _assert_allowed(result=result)


def test_denies_a_literal_loop_one_past_the_recorded_threshold() -> None:
    result = _run(stdin=_bash_input(command=_literal_loop(count=_LITERAL_ITERATION_THRESHOLD + 1)))
    event = _stderr_event(result=result)
    assert result.returncode == 2
    assert "gh api --cache <duration>" in str(event)


def test_module_docstring_records_the_literal_iteration_threshold() -> None:
    """The threshold is a judgement call, so the number and its reason are pinned.

    A bounded-literal exemption is auditable only if the number that turns it on
    is written down beside the budget arithmetic it comes from. This reads the
    LIVE module docstring rather than restating it, so moving the threshold in
    the decision logic without moving the recorded number fails here -- as does
    dropping the per-minute ceiling the number is derived from.
    """
    docstring = _load_hook().__doc__ or ""
    assert f"at most {_LITERAL_ITERATION_THRESHOLD} " in docstring
    assert "900-point-per-minute" in docstring


# ---------------------------------------------------------------------------
# Replay corpus — the committed successor to the session-scratch harness that
# measured a 40.5% false-positive rate over 73,162 real Bash commands. The
# vectors, their expected verdicts and the per-bucket denial counts live in the
# JSON fixture beside this file so the gate's arithmetic is auditable rather
# than a bare percentage, and so a cross-runtime port -- where byte-identity of
# the decision function is impossible -- has one shared thing to conform to.
# ---------------------------------------------------------------------------

_CORPUS_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "github_rate_limit_guard_replay_corpus.json"
)


def _mapping(*, value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _text(*, mapping: dict[str, object], key: str) -> str:
    value = mapping[key]
    assert isinstance(value, str)
    return value


def _whole_number(*, mapping: dict[str, object], key: str) -> int:
    value = mapping[key]
    assert isinstance(value, int)
    return value


def _percentage(*, mapping: dict[str, object], key: str) -> float:
    value = mapping[key]
    assert isinstance(value, float)
    return value


def _measured_denials(*, bucket: dict[str, object]) -> int | None:
    """The bucket's share of the measured denial population, or None when it has none.

    `b4` was carved out of the true-positive population AFTER the measurement,
    so it has no measured count of its own; recording that as null keeps it out
    of the baseline arithmetic instead of silently counting it as zero.
    """
    value = bucket["measured_denials"]
    if value is None:
        return None
    assert isinstance(value, int)
    return value


_CORPUS = _mapping(value=json.loads(_CORPUS_PATH.read_text(encoding="utf-8")))
_CORPUS_MEASUREMENT = _mapping(value=_CORPUS["measurement"])
_CORPUS_BASELINE = _mapping(value=_CORPUS["pre_fix_baseline"])
_CORPUS_BUCKETS = {
    name: _mapping(value=bucket) for name, bucket in _mapping(value=_CORPUS["buckets"]).items()
}
# The four buckets the 7-day measurement actually partitioned its denials into.
_MEASURED_BUCKETS = frozenset({"tp", "b1", "b2", "b3"})
# Credential shapes and session identifiers. The fixture is a REDACTED corpus of
# command SHAPES; raw transcript text would carry all of these.
_UNREDACTED_SECRET = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{4}|github_pat_|authorization\s*:|bearer\s+[A-Za-z0-9]"
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
# An absolute path rooted in a home directory or a checkout root is repo-private
# even when it carries no secret: it names whose machine the command ran on.
_UNREDACTED_PRIVATE_PATH = re.compile(
    r"(?:^|[^\w.])(?:~/|\$HOME|/(?:Users|home|root|data|repos|mnt|workspace)/)",
    re.MULTILINE,
)


@dataclass(frozen=True, kw_only=True)
class ReplayVector:
    identifier: str
    bucket: str
    expected_verdict: str
    pre_fix_verdict: str
    command: str


def _replay_vectors() -> list[ReplayVector]:
    raw = _CORPUS["vectors"]
    assert isinstance(raw, list)
    entries = [_mapping(value=entry) for entry in cast("list[object]", raw)]
    return [
        ReplayVector(
            identifier=_text(mapping=entry, key="id"),
            bucket=_text(mapping=entry, key="bucket"),
            expected_verdict=_text(mapping=entry, key="expected_verdict"),
            pre_fix_verdict=_text(mapping=entry, key="pre_fix_verdict"),
            command=_text(mapping=entry, key="command"),
        )
        for entry in entries
    ]


_REPLAY_VECTORS = _replay_vectors()


def _observed_verdict(*, vector: ReplayVector) -> str:
    """Replay one vector through the real hook boundary and name what it did.

    The verdict is read off the hook's EXIT STATUS rather than off the
    decision function, so the fixture pins the behaviour a governed repo
    actually sees -- a deny that never reaches exit 2 is not a deny.
    """
    result = _run(stdin=_bash_input(command=vector.command))
    if result.returncode == 0:
        _assert_allowed(result=result)
        return "allow"
    assert result.returncode == 2, result.stderr
    assert "DENIED by github_rate_limit_guard.py" in str(_stderr_event(result=result))
    return "deny"


@pytest.mark.parametrize(
    "vector", [pytest.param(vector, id=vector.identifier) for vector in _REPLAY_VECTORS]
)
def test_replay_corpus_vector_returns_its_recorded_verdict(vector: ReplayVector) -> None:
    assert _observed_verdict(vector=vector) == vector.expected_verdict


def test_replay_corpus_covers_every_measured_bucket() -> None:
    """Each bucket the measurement partitioned denials into carries a vector.

    A corpus that covers only the buckets a given fix touched would go green
    against a guard that had regressed in one of the others.
    """
    covered = {vector.bucket for vector in _REPLAY_VECTORS}
    assert covered >= _MEASURED_BUCKETS
    assert covered == set(_CORPUS_BUCKETS)


def test_replay_corpus_vectors_agree_with_their_bucket_verdict() -> None:
    """A vector's expected verdict is the verdict its whole bucket is labelled with."""
    for vector in _REPLAY_VECTORS:
        bucket = _CORPUS_BUCKETS[vector.bucket]
        assert vector.expected_verdict == _text(mapping=bucket, key="expected_verdict")


def test_measured_false_positive_rate_is_reproducible_from_the_recorded_buckets() -> None:
    """The 40.5% figure must be derivable from the counts the fixture carries.

    A bare percentage in a plan note cannot be checked; per-bucket counts that
    sum to the recorded denial total, with the false share divided out of it,
    can. This is the arithmetic the gate below is measured against.
    """
    denials = {
        name: count
        for name, bucket in _CORPUS_BUCKETS.items()
        if (count := _measured_denials(bucket=bucket)) is not None
    }
    assert set(denials) == _MEASURED_BUCKETS
    total = sum(denials.values())
    assert total == _whole_number(mapping=_CORPUS_MEASUREMENT, key="denials")
    false = sum(
        count
        for name, count in denials.items()
        if _text(mapping=_CORPUS_BUCKETS[name], key="expected_verdict") == "allow"
    )
    recorded = _percentage(mapping=_CORPUS_MEASUREMENT, key="false_positive_rate_percent")
    assert round(100 * false / total, 1) == recorded


def test_replayed_corpus_has_no_false_positives_and_no_disabled_controls() -> None:
    """The gate: every false-positive vector allows WHILE every control still denies.

    Both halves are load-bearing. The first is the defect this corpus was cut
    to measure; the second is the control proving a green fixture came from a
    fixed guard rather than a switched-off one -- deleting the decision logic
    outright would satisfy the first half alone.
    """
    observed = {vector.identifier: _observed_verdict(vector=vector) for vector in _REPLAY_VECTORS}
    allow_vectors = [v for v in _REPLAY_VECTORS if v.expected_verdict == "allow"]
    deny_vectors = [v for v in _REPLAY_VECTORS if v.expected_verdict == "deny"]
    assert allow_vectors
    assert deny_vectors
    false_positives = [v.identifier for v in allow_vectors if observed[v.identifier] == "deny"]
    not_denied = [v.identifier for v in deny_vectors if observed[v.identifier] == "allow"]
    assert 100 * len(false_positives) / len(allow_vectors) == 0.0, false_positives
    assert 100 * len(not_denied) / len(deny_vectors) == 0.0, not_denied


def test_replay_corpus_retains_every_vector_the_pre_fix_build_got_wrong() -> None:
    """The corpus keeps its regression value only while it still holds the failures.

    Each vector records what the pre-fix build returned for it. Dropping one --
    the cheapest way to make a stubborn fixture green -- moves this count.
    """
    wrong = [v.identifier for v in _REPLAY_VECTORS if v.pre_fix_verdict != v.expected_verdict]
    assert len(wrong) == _whole_number(mapping=_CORPUS_BASELINE, key="vectors_wrong"), wrong


def test_replay_corpus_carries_no_credentials_session_ids_or_private_paths() -> None:
    """Redaction is a property of the FILE, not just of the command strings.

    Notes and provenance lines are prose written by hand, so they leak as
    easily as a command would; the whole fixture text is scanned.
    """
    text = _CORPUS_PATH.read_text(encoding="utf-8")
    assert _UNREDACTED_SECRET.search(text) is None
    assert _UNREDACTED_PRIVATE_PATH.search(text) is None


# ---------------------------------------------------------------------------
# Verdict telemetry. The 40.5% figure above had to be derived by replaying the
# decision function over a week of local transcripts, because the guard emitted
# nothing on the ALLOW path and nothing at all off the machine. The guard now
# emits one structured verdict record per Bash call, so the false-positive
# signature -- a `rate_limited` verdict that found no `gh` at command position
# -- is a query rather than an investigation.
# ---------------------------------------------------------------------------

_ENDPOINT_ENV = "LIVESPEC_SANDBOX_OTEL_ENDPOINT"


@dataclass(frozen=True, kw_only=True)
class VerdictRecord:
    matched_rule: str | None
    gh_cached: bool
    gh_at_command_position: bool


def _recorded_verdicts(
    *, monkeypatch: pytest.MonkeyPatch, command: str
) -> tuple[HookResult, list[VerdictRecord]]:
    hook = _load_hook()
    assert hasattr(hook, "emit_verdict"), "the guard does not emit a verdict record at all"
    records: list[VerdictRecord] = []

    def _capture(
        *, matched_rule: str | None, gh_cached: bool, gh_at_command_position: bool
    ) -> None:
        records.append(
            VerdictRecord(
                matched_rule=matched_rule,
                gh_cached=gh_cached,
                gh_at_command_position=gh_at_command_position,
            )
        )

    monkeypatch.setattr(hook, "emit_verdict", _capture)
    return _run_loaded(hook=hook, stdin=_bash_input(command=command)), records


@pytest.mark.parametrize(
    ("command", "matched_rule"),
    [
        ("while true; do gh pr view 7 --json headRefOid; done", "loop+read"),
        ('for id in $(seq 1 20); do gh run view "$id" --json status; done', "loop+read"),
        ("for id in 1 2; do gh run view $id --json status; sleep 5; done", "sleep+read"),
        (
            "printf '%s\\n' 1 2 | xargs -I{} gh api --method PATCH repos/acme/project/issues/{}",
            "loop+mutation",
        ),
    ],
    ids=["unbounded-loop", "unreadable-bound", "sleeping-loop", "xargs-mutation"],
)
def test_a_denied_command_emits_the_rule_that_convicted_it(
    monkeypatch: pytest.MonkeyPatch, command: str, matched_rule: str
) -> None:
    result, records = _recorded_verdicts(monkeypatch=monkeypatch, command=command)

    assert result.returncode == 2
    assert [record.matched_rule for record in records] == [matched_rule]
    assert records[0].gh_at_command_position is True


def test_an_allowed_command_emits_a_verdict_record_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the allow half there is no denominator, and no near-miss visibility."""
    result, records = _recorded_verdicts(
        monkeypatch=monkeypatch, command="gh pr view 123 --json headRefOid"
    )

    _assert_allowed(result=result)
    assert len(records) == 1
    assert records[0].matched_rule is None
    assert records[0].gh_at_command_position is True


def test_the_record_reports_a_read_already_in_the_sanctioned_cached_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, records = _recorded_verdicts(
        monkeypatch=monkeypatch,
        command="for r in $(cat refs); do gh api --cache 10m repos/acme/project/pulls; done",
    )

    _assert_allowed(result=result)
    assert records[0].gh_cached is True
    assert records[0].matched_rule is None


def test_the_false_positive_signature_is_a_command_with_no_gh_at_command_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`gh` spelled inside a search pattern is text, not an invocation.

    This is bucket b2 of the replay corpus -- the largest false-positive family.
    The guard no longer denies it, and the record now SAYS why: no `gh` ran.
    """
    result, records = _recorded_verdicts(
        monkeypatch=monkeypatch,
        command="for f in a b; do grep -n gh_api_helper $f; done",
    )

    _assert_allowed(result=result)
    assert records[0].gh_at_command_position is False


@pytest.mark.parametrize(
    "endpoint",
    ["http://127.0.0.1:1", "not-a-url", ""],
    ids=["refused", "malformed", "empty"],
)
def test_a_telemetry_failure_is_a_silent_pass_through_that_never_moves_the_verdict(
    monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """The real emit path, against a receiver that cannot answer.

    No mock: the guard builds a real payload and attempts a real POST. The
    verdict, the exit code and the stderr deny record must all be exactly what
    they are when the receiver is healthy.
    """
    monkeypatch.setenv(_ENDPOINT_ENV, endpoint)

    denied = _run(stdin=_bash_input(command=_UNCACHED_LOOPED_READ))
    allowed = _run(stdin=_bash_input(command="gh pr view 123 --json headRefOid"))

    assert denied.returncode == 2
    assert "gh api --cache <duration>" in str(_stderr_event(result=denied))
    _assert_allowed(result=allowed)
