"""Unit tests for `.claude-plugin/hooks/_shell_io.py`.

The stdin and payload channels: what a segment produces for a pipe, what the
next one reads, what an interpreter is handed, and which redirection tokens
are stripped before a remote command is re-read. Every string is inert data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _shell_io import (  # noqa: E402 — path-dependent import after sys.path insert.
    DATA_HEADS,
    PAYLOAD_HEADS,
    SCRIPT_HEADS,
    payload_of,
    produced_text,
    stdin_text,
    without_stdin_redirects,
)
from _shell_lex import SHELLS  # noqa: E402 — path-dependent import after sys.path insert.

__all__: list[str] = []


def test_the_head_classes_name_the_interpreters_and_the_data_printers() -> None:
    assert SHELLS <= SCRIPT_HEADS
    assert {"script", "su"} <= SCRIPT_HEADS
    assert {"eval", "watch", "tmux"} == PAYLOAD_HEADS
    assert {"echo", "printf"} == DATA_HEADS


@pytest.mark.parametrize(
    ("tokens", "bodies", "text"),
    [
        (["echo", "put", "x"], [], "put x"),
        (["X=1", "printf", "put x\\n"], [], "put x\n"),
        (["echo", "-e", "a"], [], "a"),
        (["cat", "<<EOF"], ["ssh host 'sudo x'"], "ssh host 'sudo x'"),
        (["cat", "-", "<<EOF"], ["body"], "body"),
        (["cat", "batch.txt"], [], None),
        (["cat", "<<EOF"], [], None),
        (["curl", "x"], [], None),
        (["X=1"], [], None),
    ],
)
def test_produced_text_is_what_a_readable_producer_writes(
    tokens: list[str], bodies: list[str], text: str | None
) -> None:
    assert produced_text(tokens=tokens, bodies=bodies) == text


def test_stdin_text_collects_here_docs_a_here_string_and_a_data_pipe() -> None:
    assert stdin_text(tokens=["bash", "<<<", "x"], bodies=[], piped=None) == "x"
    assert stdin_text(tokens=["bash", "<<<"], bodies=[], piped=None) is None
    assert stdin_text(tokens=["sftp", "h", "<<EOF"], bodies=["put x"], piped=None) == "put x"
    assert stdin_text(tokens=["sftp", "h"], bodies=[], piped="rm y") == "rm y"
    assert (
        stdin_text(tokens=["sftp", "h", "<<EOF"], bodies=["put x"], piped="rm y") == "put x\nrm y"
    )
    assert stdin_text(tokens=["sftp", "h"], bodies=[], piped=None) is None


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
