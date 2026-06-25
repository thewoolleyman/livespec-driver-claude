"""Unit tests for `.claude-plugin/hooks/no_shadow_ledger.py`.

The script is exercised exactly as Claude Code runs it: as a subprocess
invoked `python3 <script>` (mirroring the hooks.json Stop registration
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/no_shadow_ledger.py"`), with the
Stop hook input JSON on stdin and a fabricated transcript JSONL
materialized under `tmp_path`.

Contract under test (livespec core `contracts.md` §"Driver-shipped
hooks"; `non-functional-requirements.md` §"Planning Lane guidance" →
"No shadow ledger"):

- The last turn (transcript entries after the last REAL user message;
  tool_result deliveries do NOT reset the window) is scanned for
  file-persisting tool calls (Write / Edit / MultiEdit) that wrote a
  PLANNING ARTIFACT — a handoff, or any markdown file under a `plan/`
  or `prompts/` directory.
- A persisted planning artifact whose content carries markdown checkbox
  task-list items (`[ ]` / `[x]`) at or above the mechanical threshold
  (3) emits a `systemMessage` WARNING on stdout.
- WARN-only: the output NEVER carries a `decision` key and the exit
  code is ALWAYS 0 (the hook can never block the stop).
- Everything else — clean artifacts (incl. inline `` `[ ]` `` in prose),
  non-planning paths, missing transcripts, malformed stdin,
  `stop_hook_active` — is a silent pass-through (fail-open).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / ".claude-plugin" / "hooks" / "no_shadow_ledger.py"

# A planning artifact carrying a checkbox task queue at/above threshold.
_CHECKBOX_QUEUE = (
    "# Handoff\n"
    "## Next actions\n"
    "- [ ] wire the gate into lefthook\n"
    "- [x] land the config block\n"
    "- [ ] open the follow-up PR\n"
)

# A clean planning artifact: real prose, NO checkbox list items. The
# inline `[ ]` inside backticks is prose quoting the forbidden syntax,
# never a list item — the hook's line-anchored regex must not match it.
_CLEAN_PLAN = (
    "# Handoff\n"
    "## Status\n"
    "Status is derived from the ledger as the first action. A checklist\n"
    "item like `[ ]` written inline in prose is not a task queue.\n"
    "Next session: run `just orchestrate` to pick up ledger id li-abc.\n"
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


def _write_tool_entry(*, file_path: str, content: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu_1",
                    "name": "Write",
                    "input": {"file_path": file_path, "content": content},
                }
            ],
        },
    }


def _edit_tool_entry(*, file_path: str, new_string: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu_1",
                    "name": "Edit",
                    "input": {"file_path": file_path, "new_string": new_string},
                }
            ],
        },
    }


def _write_transcript(*, root: Path, entries: list[dict | str]) -> Path:
    transcript = root / "transcript.jsonl"
    lines = [entry if isinstance(entry, str) else json.dumps(entry) for entry in entries]
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return transcript


def _run_hook(*, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
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


def test_warns_on_handoff_write_with_checkbox_queue(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="write the handoff"),
            _write_tool_entry(file_path="tmp/HANDOFF-session.md", content=_CHECKBOX_QUEUE),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    output = _assert_warn_only(result=result)
    assert "tmp/HANDOFF-session.md" in output["systemMessage"]


def test_warns_on_plan_dir_markdown_with_checkbox_queue(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="draft the plan"),
            _write_tool_entry(file_path="plan/topic/steps.md", content=_CHECKBOX_QUEUE),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_warn_only(result=result)


def test_warns_on_prompts_dir_markdown_with_checkbox_queue(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="update the prompts doc"),
            _edit_tool_entry(file_path="prompts/AGENTS.md", new_string=_CHECKBOX_QUEUE),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_warn_only(result=result)


def test_silent_on_clean_planning_artifact(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="write the handoff"),
            _write_tool_entry(file_path="tmp/HANDOFF-session.md", content=_CLEAN_PLAN),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_silent(result=result)


def test_silent_on_non_planning_path(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="edit the readme"),
            _write_tool_entry(file_path="README.md", content=_CHECKBOX_QUEUE),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript))
    _assert_silent(result=result)


def test_silent_when_stop_hook_active(tmp_path: Path) -> None:
    transcript = _write_transcript(
        root=tmp_path,
        entries=[
            _user_entry(text="write the handoff"),
            _write_tool_entry(file_path="tmp/HANDOFF-session.md", content=_CHECKBOX_QUEUE),
        ],
    )
    result = _run_hook(stdin=_stop_input(transcript=transcript, stop_hook_active=True))
    _assert_silent(result=result)


def test_silent_on_malformed_stdin() -> None:
    result = _run_hook(stdin="not json at all")
    _assert_silent(result=result)
