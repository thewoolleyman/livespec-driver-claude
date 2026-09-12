"""Direct tests for `.claude-plugin/hooks/_shell_lex.py`.

The shared lexer is exercised end-to-end by both classifier corpora
(`test_tmux_hazard.py`, `test_host_mutation.py`); these pin the helper
contracts themselves, one observable property each, so a change to the lexer
fails here with the helper's name rather than as a corpus case two modules
away. Every string is inert data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _shell_lex import (  # noqa: E402 — path-dependent import after sys.path insert.
    DATA_HEADS,
    PAYLOAD_HEADS,
    SCRIPT_HEADS,
    SHELLS,
    basename,
    first_command_index,
    operands,
    payload_of,
    produced_text,
    shell_payload,
    split_heredocs,
    split_segments,
    split_segments_with_separators,
    stdin_text,
    strip_heredoc_bodies,
    tokens_or_none,
    ungrouped,
    without_continuations,
    without_stdin_redirects,
)

__all__: list[str] = []


def test_basename_is_the_last_path_component() -> None:
    assert basename(token="/usr/bin/ssh") == "ssh"
    assert basename(token="ssh") == "ssh"


def test_ungrouped_strips_fused_grouping_punctuation() -> None:
    assert ungrouped(token="(ssh") == "ssh"
    assert ungrouped(token="x;}") == "x;"


def test_continuations_join_into_one_logical_line() -> None:
    assert without_continuations(command="ssh \\\n host") == "ssh   host"


def test_tokens_or_none_lexes_or_reports_unlexable() -> None:
    assert tokens_or_none(seg="(ssh host 'a b')") == ["ssh", "host", "a b"]
    assert tokens_or_none(seg="ssh 'unterminated") is None


def test_split_heredocs_returns_the_shell_and_the_bodies_separately() -> None:
    command = "ssh host bash -s <<'EOF'\nsudo x\nsudo y\nEOF\necho done"
    shell, bodies = split_heredocs(command=command)
    assert shell == "ssh host bash -s <<'EOF'\necho done"
    assert bodies == ["sudo x\nsudo y"]


def test_an_unterminated_heredoc_body_runs_to_the_end() -> None:
    shell, bodies = split_heredocs(command="cat <<EOF\nline one\nline two")
    assert shell == "cat <<EOF"
    assert bodies == ["line one\nline two"]


def test_a_heredoc_marker_inside_quotes_is_a_string_not_a_heredoc() -> None:
    command = "echo '<<EOF'\nssh host x"
    assert split_heredocs(command=command) == (command, [])
    command = 'echo "<<EOF" x\nssh host x'
    assert split_heredocs(command=command) == (command, [])


def test_a_heredoc_terminator_may_carry_a_dash() -> None:
    shell, bodies = split_heredocs(command="cat <<'END-X'\nfoo\nEND-X\nssh host x")
    assert shell == "cat <<'END-X'\nssh host x"
    assert bodies == ["foo"]


def test_a_here_string_is_not_a_heredoc() -> None:
    command = "bash <<< 'ssh host x'\necho next"
    assert split_heredocs(command=command) == (command, [])


def test_a_backslash_escape_does_not_open_a_quote() -> None:
    command = "echo \\' <<EOF\nbody\nEOF"
    assert split_heredocs(command=command) == ("echo \\' <<EOF", ["body"])


def test_a_lone_heredoc_operator_with_no_terminator_opens_nothing() -> None:
    command = "cat << \nnext"
    assert split_heredocs(command=command) == (command, [])


def test_strip_heredoc_bodies_keeps_only_the_shell() -> None:
    assert strip_heredoc_bodies(command="cat <<EOF\nbody\nEOF") == "cat <<EOF"


@pytest.mark.parametrize(
    ("command", "segments"),
    [
        ("a; b && c || d | e & f\ng", ["a", "b", "c", "d", "e", "f", "g"]),
        ("echo 'a; b' && c", ["echo 'a; b'", "c"]),
        ('echo "a | b"', ['echo "a | b"']),
        ("echo a\\; b", ["echo a\\; b"]),
        ("  ;; ", []),
        ("git status # ssh host x", ["git status"]),
        ("# a comment\ngit status", ["git status"]),
        ("echo a#b 'x#y' # c", ["echo a#b 'x#y'"]),
        ("env x#y=1 ssh host", ["env x#y=1 ssh host"]),
    ],
)
def test_split_segments_is_quote_escape_and_comment_aware(
    command: str, segments: list[str]
) -> None:
    assert split_segments(command=command) == segments


def test_split_segments_with_separators_reports_what_preceded_each_segment() -> None:
    assert split_segments_with_separators(command="a | b && c; d\ne || f & g") == [
        ("", "a"),
        ("|", "b"),
        ("&&", "c"),
        (";", "d"),
        ("\n", "e"),
        ("||", "f"),
        ("&", "g"),
    ]


@pytest.mark.parametrize(
    ("arguments", "payload"),
    [
        (["-c", "ssh host x"], "ssh host x"),
        (["-lc", "ssh host x"], "ssh host x"),
        (["-cssh host x"], "ssh host x"),
        (["-c"], None),
        (["-l"], None),
        ([], None),
    ],
)
def test_shell_payload_finds_the_inline_script(arguments: list[str], payload: str | None) -> None:
    assert shell_payload(arguments=arguments) == payload


def test_the_head_classes_name_the_interpreters_and_the_data_printers() -> None:
    assert {"bash", "sh", "zsh"} <= SHELLS
    assert SHELLS <= SCRIPT_HEADS
    assert {"eval", "watch", "tmux"} == PAYLOAD_HEADS
    assert {"echo", "printf"} == DATA_HEADS


def test_first_command_index_skips_leading_assignments() -> None:
    assert first_command_index(tokens=["A=1", "B=2", "ssh", "host"]) == 2
    assert first_command_index(tokens=["ssh"]) == 0
    assert first_command_index(tokens=["A=1"]) is None
    assert first_command_index(tokens=[]) is None


def test_operands_drop_flags() -> None:
    assert operands(arguments=["-n", "5", "--x=y", "cmd"]) == ["5", "cmd"]


@pytest.mark.parametrize(
    ("tokens", "text"),
    [
        (["echo", "put", "x"], "put x"),
        (["X=1", "printf", "put x\\n"], "put x\n"),
        (["echo", "-e", "a"], "a"),
        (["cat", "x"], None),
        (["X=1"], None),
    ],
)
def test_produced_text_is_what_echo_and_printf_write(tokens: list[str], text: str | None) -> None:
    assert produced_text(tokens=tokens) == text


def test_stdin_text_collects_here_string_heredoc_and_pipe() -> None:
    assert stdin_text(seg="bash <<< 'x'", tokens=["bash", "<<<", "x"], bodies=[], piped=None) == "x"
    assert stdin_text(seg="bash <<<", tokens=["bash", "<<<"], bodies=[], piped=None) is None
    assert (
        stdin_text(seg="sftp h <<EOF", tokens=["sftp", "h", "<<EOF"], bodies=["put x"], piped=None)
        == "put x"
    )
    assert stdin_text(seg="sftp h", tokens=["sftp", "h"], bodies=["put x"], piped="rm y") == "rm y"
    assert (
        stdin_text(
            seg="sftp h <<EOF", tokens=["sftp", "h", "<<EOF"], bodies=["put x"], piped="rm y"
        )
        == "put x\nrm y"
    )
    assert stdin_text(seg="sftp h", tokens=["sftp", "h"], bodies=[], piped=None) is None


def test_without_stdin_redirects_drops_the_operator_and_its_word() -> None:
    assert without_stdin_redirects(tokens=["ssh", "h", "<<EOF"]) == ["ssh", "h"]
    assert without_stdin_redirects(tokens=["ssh", "h", "<<<", "x", "y"]) == ["ssh", "h", "y"]
    assert without_stdin_redirects(tokens=["ssh", "h", "<", "f", "y"]) == ["ssh", "h", "y"]
    assert without_stdin_redirects(tokens=["ssh", "h", ">", "f"]) == ["ssh", "h", ">", "f"]


@pytest.mark.parametrize(
    ("head", "arguments", "stdin", "payload"),
    [
        ("bash", ["-c", "x"], None, "x"),
        ("bash", ["-s"], "from stdin", "from stdin"),
        ("bash", ["-s"], None, None),
        ("eval", ["ssh", "h", "x"], None, "ssh h x"),
        ("eval", [], None, None),
        ("watch", ["-n5", "kubectl delete x"], None, "kubectl delete x"),
        ("watch", ["-n5"], None, None),
        ("tmux", ["new", "-d", "ssh h x"], None, "ssh h x"),
        ("tmux", ["send-keys", "-t", "x", "ssh h x", "Enter"], None, "ssh h x"),
        ("tmux", ["new", "-d", "-s", "work"], None, None),
    ],
)
def test_payload_of_extracts_what_each_interpreter_runs(
    head: str, arguments: list[str], stdin: str | None, payload: str | None
) -> None:
    assert payload_of(head=head, arguments=arguments, stdin=stdin) == payload
