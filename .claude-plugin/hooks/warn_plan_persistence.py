#!/usr/bin/env python3
"""
warn_plan_persistence — Stop hook detecting unpersisted plan artifacts.

Declared in hooks.json on the `Stop` event. Scans the agent's last turn
(the transcript entries after the last REAL user message — tool results do
NOT reset the window) for substantial planning artifacts: markdown headings,
table rows, and list items above mechanical thresholds. When such an artifact
exists and NO file-persisting tool call (Write / Edit / MultiEdit /
NotebookEdit) happened in the same window, it emits a `systemMessage` WARNING
on stdout.

WARN-ONLY BY CONTRACT (work-item livespec-driver-claude-4jp, lineage
livespec-c1nf / livespec-1f5-rest item 6, realizing livespec core
non-functional-requirements' completion-includes-persistence rule): this hook
NEVER blocks the stop — it never emits a `decision` key and never exits
non-zero — and it never auto-files anything.

Fail-open contract: ANY failure (malformed stdin, missing/unreadable
transcript, malformed transcript lines) is a silent pass-through with exit 0.
`main()` owns stdin/stdout at the hook boundary, catches every failure, and
returns 0 on every path; it is importable (no work at module import) so the
body is testable in-process for real per-file coverage.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or the sibling `_result` railway module.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import cast

from _result import Failure, IOFailure, IOResult, IOSuccess, Result, Success

# Mechanical "substantial planning artifact" thresholds over the aggregated
# assistant text of the last turn.
HEADING_THRESHOLD = 3
TABLE_ROW_THRESHOLD = 5
LIST_ITEM_THRESHOLD = 10

# Tool calls that count as persisting content to disk.
PERSISTING_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")


def _as_object_dict(value: object) -> dict[str, object] | None:
    """Narrow an arbitrary JSON value to a string-keyed dict, else None."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _is_real_user_entry(*, entry: dict[str, object]) -> bool:
    """A user entry typed by the human — NOT a tool_result delivery."""
    if entry.get("type") != "user":
        return False
    message = _as_object_dict(entry.get("message"))
    if message is None:
        return False
    content = message.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if not isinstance(content, list):
        return False
    has_text = False
    for block in cast("list[object]", content):
        block_dict = _as_object_dict(block)
        if block_dict is None:
            continue
        if block_dict.get("type") == "tool_result":
            return False
        if block_dict.get("type") == "text":
            has_text = True
    return has_text


def _last_turn(*, entries: list[dict[str, object]]) -> tuple[str, set[str]]:
    """Aggregate assistant text + tool names after the last real user message."""
    start = 0
    for index, entry in enumerate(entries):
        if _is_real_user_entry(entry=entry):
            start = index + 1
    texts: list[str] = []
    tool_names: set[str] = set()
    for entry in entries[start:]:
        if entry.get("type") != "assistant":
            continue
        message = _as_object_dict(entry.get("message"))
        if message is None:
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in cast("list[object]", content):
            block_dict = _as_object_dict(block)
            if block_dict is None:
                continue
            block_type = block_dict.get("type")
            if block_type == "text":
                text = block_dict.get("text")
                if isinstance(text, str):
                    texts.append(text)
            elif block_type == "tool_use":
                name = block_dict.get("name")
                if isinstance(name, str):
                    tool_names.add(name)
    return "\n".join(texts), tool_names


def _artifact_counts(*, text: str) -> tuple[int, int, int]:
    """Count headings, table rows, and list items in the aggregated text."""
    headings = 0
    table_rows = 0
    list_items = 0
    for raw in text.splitlines():
        line = raw.rstrip()
        if _HEADING_RE.match(line):
            headings += 1
        elif line.lstrip().startswith("|") and line.lstrip().count("|") >= 2:
            table_rows += 1
        elif _LIST_ITEM_RE.match(line):
            list_items += 1
    return headings, table_rows, list_items


def _warning(*, raw: str) -> str | None:
    """Return the systemMessage JSON, or None for a silent pass-through."""
    payload = _as_object_dict(json.loads(raw))
    if payload is None or payload.get("stop_hook_active"):
        return None
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    transcript = Path(transcript_path)
    if not transcript.is_file():
        return None
    entries: list[dict[str, object]] = []
    for line in transcript.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = _as_object_dict(json.loads(line))
        except ValueError:
            continue  # fail-open per line: skip malformed transcript lines
        if parsed is not None:
            entries.append(parsed)
    text, tool_names = _last_turn(entries=entries)
    if tool_names & PERSISTING_TOOLS:
        return None
    headings, table_rows, list_items = _artifact_counts(text=text)
    substantial = (
        headings >= HEADING_THRESHOLD
        or table_rows >= TABLE_ROW_THRESHOLD
        or list_items >= LIST_ITEM_THRESHOLD
    )
    if not substantial:
        return None
    message = (
        "livespec plan-persistence WARN: this turn produced a substantial "
        f"planning artifact ({headings} headings, {table_rows} table rows, "
        f"{list_items} list items) but no file-persisting tool call "
        "(Write/Edit/NotebookEdit) was observed in the same turn. If this "
        "plan should outlive the session, persist it (a plan/doc file, or "
        "work-items via the active impl-plugin) before moving on."
    )
    return json.dumps({"systemMessage": message})



def _read_stdin() -> tuple[str, IOResult[str, Exception]]:
    try:
        raw = sys.stdin.read()
        return raw, IOSuccess(raw)
    except Exception as exc:  # noqa: BLE001 - stdin boundary captured on IO rail
        return "", IOFailure(exc)


def _write_stdout(*, text: str) -> IOResult[int, Exception]:
    try:
        written = sys.stdout.write(text)
        return IOSuccess(written)
    except Exception as exc:  # noqa: BLE001 - stdout boundary captured on IO rail
        return IOFailure(exc)


def _warning_result(*, raw: str) -> Result[str | None, Exception]:
    try:
        return Success(_warning(raw=raw))
    except (OSError, ValueError) as exc:
        return Failure(exc)


def main() -> int:
    """Hook entry point: emit the plan-persistence WARN, if any; always exit 0.

    Owns the stdin read + stdout write at the hook boundary and catches every
    failure so the Stop hook stays fail-open by contract — WARN-only, it never
    emits a `decision` key and never exits non-zero.
    """
    try:
        raw, read_result = _read_stdin()
        read_io = read_result.value_or(default="")
        _ = read_io
        warning = _warning_result(raw=raw).value_or(default=None)
        if warning is not None:
            write_result = _write_stdout(text=warning + "\n")
            written_io = write_result.value_or(default=0)
            _ = written_io
    except Exception:  # noqa: BLE001 — fail-open by contract
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
