#!/bin/sh
# block-auto-memory — PreToolUse hook redirecting auto-memory writes to
# the active impl-plugin's capture-work-item skill.
#
# Declared in hooks.json on the `Write` tool. The effective matcher is
# `Write(**/memory/*.md)`: this script inspects the tool input and acts
# only when the written file's immediate parent directory is `memory`
# and the filename ends in `.md` (the Claude Code auto-memory layout,
# `~/.claude/projects/<slug>/memory/*.md`).
#
# Behavior (per work-item livespec-driver-claude-e1s, lineage
# livespec-hookimpl / li-zmlkrl):
#
# 1. Read the PreToolUse hook input JSON from stdin.
# 2. When the write targets `**/memory/*.md` AND the governed project
#    (`$CLAUDE_PROJECT_DIR`) carries a `.livespec.jsonc` declaring an
#    active impl-plugin (`implementation.plugin` — currently
#    `livespec-orchestrator-beads-fabro` family-wide, but NEVER hardcoded here), emit
#    block-decision JSON on stdout naming the resolved
#    `/<plugin>:capture-work-item` skill, and exit 0.
# 3. Otherwise: no-op pass-through (exit 0, no output).
#
# Note on the gating key: the originating item predates the beads
# migration and gated on a `memos_path` config key. That key is retired
# (impl-beads contracts.md: "There is no `work_items_path` /
# `memos_path` key" — the substrate is the tenant DB), so the live gate
# is the presence of a declared `implementation.plugin`.
#
# Fail-open contract: ANY failure (no python3 on PATH, malformed stdin,
# unreadable or unparseable .livespec.jsonc, unset CLAUDE_PROJECT_DIR)
# is a silent pass-through with exit 0. The hook only blocks when it
# POSITIVELY identifies a livespec-governed project.

if ! command -v python3 >/dev/null 2>&1; then
    exit 0
fi

# The program text is loaded into a variable and passed via `-c` (NOT
# `python3 - <<heredoc`, which would consume stdin for the program and
# lose the hook input JSON the harness pipes to us).
PYTHON_CODE=$(cat <<'PY'
import json
import os
import sys
from pathlib import Path, PurePosixPath


def _strip_jsonc_comments(*, text: str) -> str:
    """String-aware removal of // line and /* block */ comments."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _block_decision() -> str | None:
    """Return the block-decision JSON, or None for a pass-through."""
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict) or payload.get("tool_name") != "Write":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    target = PurePosixPath(file_path)
    if target.suffix != ".md" or target.parent.name != "memory":
        return None
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if not project_dir:
        return None
    config_path = Path(project_dir) / ".livespec.jsonc"
    if not config_path.is_file():
        return None
    config = json.loads(
        _strip_jsonc_comments(text=config_path.read_text(encoding="utf-8"))
    )
    if not isinstance(config, dict):
        return None
    implementation = config.get("implementation")
    if not isinstance(implementation, dict):
        return None
    plugin = implementation.get("plugin")
    if not isinstance(plugin, str) or not plugin.strip():
        return None
    namespace = plugin.strip()
    reason = (
        f"This project uses livespec. Use /{namespace}:capture-work-item "
        "(the active impl-plugin's capture-work-item skill) to file work "
        "items into the ledger."
    )
    return json.dumps(
        {
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        }
    )


try:
    decision = _block_decision()
except Exception:  # noqa: BLE001 — fail-open by contract
    decision = None
if decision is not None:
    sys.stdout.write(decision + "\n")
sys.exit(0)
PY
)

exec python3 -c "$PYTHON_CODE"
