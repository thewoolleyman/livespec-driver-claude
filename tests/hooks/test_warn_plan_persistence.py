"""Unit tests for `.claude-plugin/hooks/warn_plan_persistence.py`.

The hook body is exercised IN-PROCESS via its importable `main() -> int`
(monkeypatched `sys.stdin`, stdout via `capsys`) for real per-file coverage,
plus ONE retained subprocess smoke that proves the shipped script still
speaks the `Stop` hook stdin/stdout protocol.

Contract under test (work-item livespec-driver-claude-4jp): WARN-only. When
the last turn produced a substantial planning artifact (>= 3 headings, >= 5
table rows, or >= 10 list items in the aggregated assistant text) with NO
file-persisting tool call in the same window, a `{"systemMessage": ...}`
payload is emitted on stdout; otherwise a silent pass-through. The hook NEVER
blocks the stop (no `decision` key) and NEVER exits non-zero.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / ".claude-plugin" / "hooks" / "warn_plan_persistence.py"
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import warn_plan_persistence  # noqa: E402 — path-dependent hook import.


def _real_user_entry(*, text: str) -> dict[str, object]:
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def _assistant_text_entry(*, text: str) -> dict[str, object]:
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def _assistant_tool_entry(*, name: str) -> dict[str, object]:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": {"file_path": "x"}}]},
    }


def _write_transcript(*, root: Path, entries: list[dict[str, object]]) -> Path:
    transcript = root / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )
    return transcript


def _stop_input(*, transcript_path: str, stop_hook_active: bool = False) -> str:
    return json.dumps({"transcript_path": transcript_path, "stop_hook_active": stop_hook_active})


def _run(*, monkeypatch, capsys, stdin: str) -> tuple[int, str]:
    monkeypatch.setattr(sys, "stdin", StringIO(stdin))
    returncode = warn_plan_persistence.main()
    captured = capsys.readouterr()
    assert captured.err == ""
    return returncode, captured.out


def _assert_warns(*, returncode: int, stdout: str) -> str:
    assert returncode == 0
    assert stdout.strip(), "expected a systemMessage payload on stdout"
    payload = json.loads(stdout)
    assert "decision" not in payload
    message = payload["systemMessage"]
    assert isinstance(message, str)
    assert message
    return message


def _assert_silent(*, returncode: int, stdout: str) -> None:
    assert returncode == 0
    assert stdout.strip() == "", f"expected silent pass-through; got {stdout!r}"


_THREE_HEADINGS = "# One\n## Two\n### Three\nsome prose\n"


def test_script_is_executable() -> None:
    assert _HOOK_SCRIPT.is_file()
    assert os.access(_HOOK_SCRIPT, os.X_OK)


def test_warns_on_headings_without_persist(monkeypatch, capsys, tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _real_user_entry(text="think about the plan"),
            _assistant_text_entry(text=_THREE_HEADINGS),
        ],
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=_stop_input(transcript_path=str(transcript))
    )
    message = _assert_warns(returncode=returncode, stdout=stdout)
    assert "plan-persistence WARN" in message
    assert "3 headings" in message


def test_subprocess_smoke_warns_on_headings(tmp_path: Path) -> None:
    """The shipped script path still speaks the Stop hook stdin/stdout protocol."""
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _real_user_entry(text="think about the plan"),
            _assistant_text_entry(text=_THREE_HEADINGS),
        ],
    )
    result = subprocess.run(
        ["python3", str(_HOOK_SCRIPT)],
        input=_stop_input(transcript_path=str(transcript)),
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "systemMessage" in payload


def test_warns_on_table_rows(monkeypatch, capsys, tmp_path: Path) -> None:
    rows = "\n".join(f"| a{i} | b{i} |" for i in range(5))
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _real_user_entry(text="tabulate"),
            _assistant_text_entry(text="intro\n" + rows + "\n"),
        ],
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=_stop_input(transcript_path=str(transcript))
    )
    message = _assert_warns(returncode=returncode, stdout=stdout)
    assert "5 table rows" in message


def test_warns_on_list_items(monkeypatch, capsys, tmp_path: Path) -> None:
    items = "\n".join(f"- item {i}" for i in range(10))
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _real_user_entry(text="enumerate"),
            _assistant_text_entry(text="intro\n" + items + "\n"),
        ],
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=_stop_input(transcript_path=str(transcript))
    )
    message = _assert_warns(returncode=returncode, stdout=stdout)
    assert "10 list items" in message


def test_silent_when_persisting_tool_used(monkeypatch, capsys, tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _real_user_entry(text="write the plan"),
            _assistant_text_entry(text=_THREE_HEADINGS),
            _assistant_tool_entry(name="Write"),
        ],
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=_stop_input(transcript_path=str(transcript))
    )
    _assert_silent(returncode=returncode, stdout=stdout)


def test_silent_below_threshold(monkeypatch, capsys, tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _real_user_entry(text="a small note"),
            _assistant_text_entry(text="# only one heading\nprose only\n"),
        ],
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=_stop_input(transcript_path=str(transcript))
    )
    _assert_silent(returncode=returncode, stdout=stdout)


def test_window_resets_at_real_user_message(monkeypatch, capsys, tmp_path: Path) -> None:
    # A persist BEFORE the last real user message must not suppress the WARN;
    # only the window AFTER the last real user message counts.
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _real_user_entry(text="first"),
            _assistant_tool_entry(name="Write"),
            _real_user_entry(text="now just plan, do not persist"),
            _assistant_text_entry(text=_THREE_HEADINGS),
        ],
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=_stop_input(transcript_path=str(transcript))
    )
    _assert_warns(returncode=returncode, stdout=stdout)


def test_silent_when_stop_hook_active(monkeypatch, capsys, tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[_real_user_entry(text="plan"), _assistant_text_entry(text=_THREE_HEADINGS)],
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_stop_input(transcript_path=str(transcript), stop_hook_active=True),
    )
    _assert_silent(returncode=returncode, stdout=stdout)


def test_silent_on_non_mapping_payload(monkeypatch, capsys) -> None:
    returncode, stdout = _run(monkeypatch=monkeypatch, capsys=capsys, stdin="[]")
    _assert_silent(returncode=returncode, stdout=stdout)


def test_silent_on_missing_transcript_path(monkeypatch, capsys) -> None:
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=json.dumps({"stop_hook_active": False})
    )
    _assert_silent(returncode=returncode, stdout=stdout)


def test_silent_when_transcript_missing(monkeypatch, capsys, tmp_path: Path) -> None:
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_stop_input(transcript_path=str(tmp_path / "missing.jsonl")),
    )
    _assert_silent(returncode=returncode, stdout=stdout)


def test_fail_open_on_malformed_stdin(monkeypatch, capsys) -> None:
    returncode, stdout = _run(monkeypatch=monkeypatch, capsys=capsys, stdin="not json at all")
    _assert_silent(returncode=returncode, stdout=stdout)


def test_skips_blank_malformed_and_non_mapping_transcript_lines(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\nnot json\n[]\n"
        + json.dumps(_real_user_entry(text="plan"))
        + "\n"
        + json.dumps(_assistant_text_entry(text=_THREE_HEADINGS))
        + "\n",
        encoding="utf-8",
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch, capsys=capsys, stdin=_stop_input(transcript_path=str(transcript))
    )
    _assert_warns(returncode=returncode, stdout=stdout)


def test_is_real_user_entry_variants() -> None:
    f = warn_plan_persistence._is_real_user_entry
    assert f(entry={"type": "assistant"}) is False
    assert f(entry={"type": "user", "message": []}) is False
    assert f(entry={"type": "user", "message": {"content": "hi"}}) is True
    assert f(entry={"type": "user", "message": {"content": ""}}) is False
    assert f(entry={"type": "user", "message": {"content": 123}}) is False
    assert f(entry={"type": "user", "message": {"content": ["not a block"]}}) is False
    assert f(entry={"type": "user", "message": {"content": [{"type": "tool_result"}]}}) is False
    assert f(entry={"type": "user", "message": {"content": [{"type": "image"}]}}) is False
    assert f(entry={"type": "user", "message": {"content": [{"type": "text"}]}}) is True


def test_last_turn_skips_non_conforming_shapes() -> None:
    # Covers: a non-assistant entry (skipped), a non-mapping message, a
    # non-list content, a non-mapping block, and a multi-block message with a
    # block whose type is neither text nor tool_use, a text block with non-str
    # text, a tool_use with non-str name, plus the real text + tool_use kept.
    entries: list[dict[str, object]] = [
        {"type": "system", "message": {}},
        {"type": "assistant", "message": []},
        {"type": "assistant", "message": {"content": "bad"}},
        {"type": "assistant", "message": {"content": ["bad block"]}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking"},
                    {"type": "text", "text": 5},
                    {"type": "tool_use", "name": 9},
                    {"type": "text", "text": "kept"},
                    {"type": "tool_use", "name": "Edit"},
                ]
            },
        },
    ]
    text, tool_names = warn_plan_persistence._last_turn(entries=entries)
    assert text == "kept"
    assert tool_names == {"Edit"}


def test_as_object_dict_narrows_only_mappings() -> None:
    assert warn_plan_persistence._as_object_dict({"k": 1}) == {"k": 1}
    assert warn_plan_persistence._as_object_dict([1]) is None
