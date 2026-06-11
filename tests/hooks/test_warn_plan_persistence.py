"""Unit tests for `.claude-plugin/hooks/warn-plan-persistence.sh`.

The script is exercised exactly as Claude Code runs it: as a
subprocess, with the Stop hook input JSON on stdin and a fabricated
transcript JSONL materialized under `tmp_path`.

Contract under test (work-item livespec-driver-claude-4jp):

- The last turn (transcript entries after the last REAL user message;
  tool_result deliveries do NOT reset the window) is scanned for
  substantial planning artifacts — headings / table rows / list items
  above thresholds.
- Substantial artifact + NO file-persisting tool call in the window
  emits a `systemMessage` WARNING on stdout.
- WARN-only: the output NEVER carries a `decision` key and the exit
  code is ALWAYS 0 (the hook can never block the stop).
- Everything else — persisted plans, trivial responses, missing
  transcripts, malformed stdin, `stop_hook_active` — is a silent
  pass-through (fail-open).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / ".claude-plugin" / "hooks" / "warn-plan-persistence.sh"

_PLAN_TEXT = (
    "# Migration plan\n"
    "## Phase 1 — inventory\n"
    "- enumerate the call sites\n"
    "- pin the contract\n"
    "## Phase 2 — cutover\n"
    "- flip the config\n"
    "- delete the shim\n"
)

_TABLE_TEXT = (
    "| repo | status |\n"
    "|---|---|\n"
    "| livespec | green |\n"
    "| livespec-impl-beads | green |\n"
    "| livespec-dev-tooling | red |\n"
)


def _user_entry(*, text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _tool_result_entry() -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "ok"}],
        },
    }


def _assistant_text_entry(*, text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def _assistant_tool_use_entry(*, name: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "tu_1", "name": name, "input": {}}],
        },
    }


def _write_transcript(*, root: Path, entries: list[dict | str]) -> Path:
    transcript = root / "transcript.jsonl"
    lines = [entry if isinstance(entry, str) else json.dumps(entry) for entry in entries]
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return transcript


def _run_hook(*, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_HOOK_SCRIPT)],
        input=stdin,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _stop_input(*, transcript: Path, stop_hook_active: bool = False) -> str:
    return json.dumps(
        {
            "hook_event_name": "Stop",
            "session_id": "s-1",
            "transcript_path": str(transcript),
            "stop_hook_active": stop_hook_active,
        }
    )


def _assert_silent(*, result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0
    assert result.stdout == ""


def _assert_warn_only(*, result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "WARN" in output["systemMessage"]
    assert "decision" not in output  # NEVER blocks
    return output


def test_script_is_executable() -> None:
    assert _HOOK_SCRIPT.is_file()
    assert os.access(_HOOK_SCRIPT, os.X_OK)


def test_warns_on_unpersisted_heading_plan(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[_user_entry(text="plan the migration"), _assistant_text_entry(text=_PLAN_TEXT)],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    output = _assert_warn_only(result=result)
    assert "3 headings" in output["systemMessage"]


def test_warns_on_unpersisted_table(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[_user_entry(text="status?"), _assistant_text_entry(text=_TABLE_TEXT)],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_warn_only(result=result)


def test_silent_when_plan_was_persisted_via_write(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="plan the migration"),
            _assistant_text_entry(text=_PLAN_TEXT),
            _assistant_tool_use_entry(name="Write"),
            _tool_result_entry(),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_silent(result=result)


def test_silent_when_plan_was_persisted_via_edit(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="plan the migration"),
            _assistant_tool_use_entry(name="Edit"),
            _tool_result_entry(),
            _assistant_text_entry(text=_PLAN_TEXT),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_silent(result=result)


def test_silent_on_trivial_response(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[_user_entry(text="hi"), _assistant_text_entry(text="Done. Two notes:\n- a\n- b")],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_silent(result=result)


def test_tool_results_do_not_reset_the_turn_window(tmp_path: Path) -> None:
    half = _PLAN_TEXT.splitlines()
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="plan the migration"),
            _assistant_text_entry(text="\n".join(half[:3])),
            _assistant_tool_use_entry(name="Read"),  # non-persisting tool
            _tool_result_entry(),
            _assistant_text_entry(text="\n".join(half[3:])),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_warn_only(result=result)


def test_window_resets_at_a_real_user_message(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="plan the migration"),
            _assistant_text_entry(text=_PLAN_TEXT),
            _user_entry(text="thanks, looks good"),
            _assistant_text_entry(text="Great — proceeding."),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_silent(result=result)


def test_silent_when_stop_hook_active(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[_user_entry(text="plan"), _assistant_text_entry(text=_PLAN_TEXT)],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript, stop_hook_active=True))
    _assert_silent(result=result)


def test_silent_on_missing_transcript(tmp_path: Path) -> None:
    result = _run_hook(stdin=_stop_input(transcript=tmp_path / "absent.jsonl"))
    _assert_silent(result=result)


def test_silent_on_malformed_stdin() -> None:
    result = _run_hook(stdin="not json at all")
    _assert_silent(result=result)


def test_malformed_transcript_lines_are_skipped_not_fatal(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="plan the migration"),
            "this line is not json {",
            _assistant_text_entry(text=_PLAN_TEXT),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_warn_only(result=result)
