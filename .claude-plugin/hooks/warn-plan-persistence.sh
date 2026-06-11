#!/bin/sh
# warn-plan-persistence — Stop hook detecting unpersisted plan artifacts.
#
# Declared in hooks.json on the `Stop` event. Scans the agent's last
# turn (the transcript entries after the last REAL user message — tool
# results do NOT reset the window) for substantial planning artifacts:
# markdown headings, table rows, and list items above mechanical
# thresholds. When such an artifact exists and NO file-persisting tool
# call (Write / Edit / MultiEdit / NotebookEdit) happened in the same
# window, it emits a `systemMessage` WARNING on stdout.
#
# WARN-ONLY BY CONTRACT (work-item livespec-driver-claude-4jp,
# lineage livespec-c1nf / livespec-1f5-rest item 6, realizing livespec
# core non-functional-requirements §"Completion includes persistence
# and workspace cleanup"): this hook NEVER blocks the stop — it never
# emits a `decision` key and never exits non-zero — and it never
# auto-files anything. The optional done-claims-on-non-master
# extension from the item is deliberately NOT implemented.
#
# Fail-open contract: ANY failure (no python3 on PATH, malformed
# stdin, missing/unreadable transcript, malformed transcript lines) is
# a silent pass-through with exit 0.

if ! command -v python3 >/dev/null 2>&1; then
    exit 0
fi

# The program text is loaded into a variable and passed via `-c` (NOT
# `python3 - <<heredoc`, which would consume stdin for the program and
# lose the hook input JSON the harness pipes to us).
PYTHON_CODE=$(cat <<'PY'
import json
import re
import sys
from pathlib import Path

# Mechanical "substantial planning artifact" thresholds over the
# aggregated assistant text of the last turn.
HEADING_THRESHOLD = 3
TABLE_ROW_THRESHOLD = 5
LIST_ITEM_THRESHOLD = 10

# Tool calls that count as persisting content to disk.
PERSISTING_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")


def _is_real_user_entry(*, entry: dict) -> bool:
    """A user entry typed by the human — NOT a tool_result delivery."""
    if entry.get("type") != "user":
        return False
    message = entry.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if not isinstance(content, list):
        return False
    has_text = False
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_result":
            return False
        if block.get("type") == "text":
            has_text = True
    return has_text


def _last_turn(*, entries: list[dict]) -> tuple[str, set[str]]:
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
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
            elif block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                tool_names.add(block["name"])
    return "\n".join(texts), tool_names


def _artifact_counts(*, text: str) -> tuple[int, int, int]:
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


def _warning() -> str | None:
    """Return the systemMessage JSON, or None for a silent pass-through."""
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return None
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    transcript = Path(transcript_path)
    if not transcript.is_file():
        return None
    entries: list[dict] = []
    for line in transcript.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue  # fail-open per line: skip malformed transcript lines
        if isinstance(parsed, dict):
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


try:
    warning = _warning()
except Exception:  # noqa: BLE001 — fail-open by contract
    warning = None
if warning is not None:
    sys.stdout.write(warning + "\n")
sys.exit(0)
PY
)

exec python3 -c "$PYTHON_CODE"
