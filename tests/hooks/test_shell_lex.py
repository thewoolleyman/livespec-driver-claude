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
    SHELLS,
    basename,
    shell_payload,
    split_heredocs,
    split_segments,
    strip_heredoc_bodies,
    ungrouped,
    without_continuations,
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


def test_split_heredocs_returns_the_shell_and_the_bodies_separately() -> None:
    command = "ssh host bash -s <<'EOF'\nsudo x\nsudo y\nEOF\necho done"
    shell, bodies = split_heredocs(command=command)
    assert shell == "ssh host bash -s <<'EOF'\necho done"
    assert bodies == ["sudo x\nsudo y"]


def test_an_unterminated_heredoc_body_runs_to_the_end() -> None:
    shell, bodies = split_heredocs(command="cat <<EOF\nline one\nline two")
    assert shell == "cat <<EOF"
    assert bodies == ["line one\nline two"]


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
    ],
)
def test_split_segments_is_quote_and_escape_aware(command: str, segments: list[str]) -> None:
    assert split_segments(command=command) == segments


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


def test_the_shell_set_names_the_interpreters_whose_payloads_are_re_classified() -> None:
    assert {"bash", "sh", "zsh"} <= SHELLS
