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
    SHELL_KEYWORDS_DATA,
    SHELL_KEYWORDS_PASS,
    SHELLS,
    basename,
    first_command_index,
    heredoc_count,
    operands,
    shell_payload,
    split_heredocs,
    split_segments,
    split_segments_with_separators,
    strip_heredoc_bodies,
    substitutions,
    tokens_or_none,
    ungrouped,
    without_continuations,
)

__all__: list[str] = []


def test_basename_is_the_last_path_component() -> None:
    assert basename(token="/usr/bin/ssh") == "ssh"
    assert basename(token="ssh") == "ssh"


def test_ungrouped_strips_fused_grouping_punctuation_but_keeps_the_xargs_placeholder() -> None:
    assert ungrouped(token="(ssh") == "ssh"
    assert ungrouped(token="x;}") == "x;"
    assert ungrouped(token="{}") == "{}"


def test_continuations_join_into_one_logical_line() -> None:
    assert without_continuations(command="ssh \\\n host") == "ssh   host"


def test_tokens_or_none_lexes_drops_bare_grouping_and_keeps_empty_words() -> None:
    assert tokens_or_none(seg="(ssh host 'a b')") == ["ssh", "host", "a b"]
    assert tokens_or_none(seg="{ ssh host 'x'; }") == ["ssh", "host", "x;"]
    assert tokens_or_none(seg="( ssh host )") == ["ssh", "host"]
    assert tokens_or_none(seg="xargs -I{} ssh {} x") == ["xargs", "-I", "ssh", "{}", "x"]
    assert tokens_or_none(seg="'' ssh host") == ["", "ssh", "host"]
    assert tokens_or_none(seg="ssh 'unterminated") is None


def test_heredoc_count_counts_here_doc_operators_not_here_strings() -> None:
    assert heredoc_count(tokens=["cat", "<<EOF"]) == 1
    assert heredoc_count(tokens=["cat", "<<A", ">", "x", "<<-B"]) == 2
    assert heredoc_count(tokens=["bash", "<<<", "x"]) == 0
    assert heredoc_count(tokens=["ls"]) == 0


@pytest.mark.parametrize(
    ("text", "inner"),
    [
        ("echo $(date +%s)", ["date +%s"]),
        ("a $(b $(c)) d", ["b $(c)"]),
        ("echo `pwd`", ["pwd"]),
        ("x=\"$(ssh h 'sudo x')\"", ["ssh h 'sudo x'"]),
        ("echo '$(not run)'", []),
        ("echo \\$(not run)", []),
        ("echo $(unterminated", ["unterminated"]),
        ("echo `unterminated", ["unterminated"]),
        ("echo $( )", []),
        ('echo "it\'s" $(date)', ["date"]),
        ("echo 'a' $(x) 'b'", ["x"]),
        ("plain", []),
    ],
)
def test_substitutions_returns_the_executed_text_outside_single_quotes(
    text: str, inner: list[str]
) -> None:
    assert substitutions(text=text) == inner


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


def test_two_heredocs_yield_two_bodies_in_order() -> None:
    command = "cat <<A > /tmp/a\nx\nA\nssh host bash -s <<B\nsudo y\nB"
    assert split_heredocs(command=command) == (
        "cat <<A > /tmp/a\nssh host bash -s <<B",
        ["x", "sudo y"],
    )


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
        ("echo $#; ssh host", ["echo $#", "ssh host"]),
        ("echo ${#x}\nssh host", ["echo ${#x}", "ssh host"]),
        ("{ # x\nssh host; }", ["{", "ssh host", "}"]),
        ("echo 1 >|/etc/x", ["echo 1 >|/etc/x"]),
        ("a || b", ["a", "b"]),
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


def test_the_shell_set_and_keywords_are_named() -> None:
    assert {"bash", "sh", "zsh"} <= SHELLS
    assert {"for", "case", "select"} == SHELL_KEYWORDS_DATA
    assert {"if", "then", "do", "done", "!"} <= SHELL_KEYWORDS_PASS


def test_first_command_index_skips_leading_assignments() -> None:
    assert first_command_index(tokens=["A=1", "B=2", "ssh", "host"]) == 2
    assert first_command_index(tokens=["ssh"]) == 0
    assert first_command_index(tokens=["A=1"]) is None
    assert first_command_index(tokens=[]) is None


def test_operands_drop_flags() -> None:
    assert operands(arguments=["-n", "5", "--x=y", "cmd"]) == ["5", "cmd"]
