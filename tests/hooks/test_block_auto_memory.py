"""Unit tests for `.claude-plugin/hooks/block-auto-memory.sh`.

The script is exercised exactly as Claude Code runs it: as a
subprocess, with the PreToolUse hook input JSON on stdin and the
governed project supplied via a mocked `CLAUDE_PROJECT_DIR` pointing
at a `tmp_path` fixture project.

Contract under test (work-item livespec-driver-claude-e1s):

- Writes matching `**/memory/*.md` in a livespec-governed project
  (a `.livespec.jsonc` declaring `implementation.plugin`) are BLOCKED
  with decision JSON naming the resolved `/<plugin>:capture-memo`
  skill — the namespace comes from config, never hardcoded.
- Everything else — non-memory paths, non-governed projects, missing
  config keys, unset CLAUDE_PROJECT_DIR, malformed stdin — is a silent
  pass-through: exit 0, empty stdout (fail-open).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / ".claude-plugin" / "hooks" / "block-auto-memory.sh"

_MEMORY_WRITE_PATH = "/home/user/.claude/projects/-data-projects-x/memory/MEMORY.md"


def _hook_input(*, file_path: str, tool_name: str = "Write") -> str:
    return json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": {"file_path": file_path, "content": "# memory\n"},
        }
    )


def _governed_project(*, root: Path, plugin: str = "livespec-impl-beads") -> Path:
    """Materialize a livespec-governed project with a commented JSONC config."""
    config = (
        "// Project-local livespec configuration (JSONC: comments are legal).\n"
        "{\n"
        '  "template": "livespec",\n'
        '  "spec_root": "SPECIFICATION", // trailing comment\n'
        "  /* block comment */\n"
        f'  "implementation": {{ "plugin": "{plugin}" }},\n'
        '  "cross_repo_targets": {\n'
        '    "livespec": { "github_url": "https://github.com/thewoolleyman/livespec" }\n'
        "  }\n"
        "}\n"
    )
    (root / ".livespec.jsonc").write_text(config, encoding="utf-8")
    return root


def _run_hook(*, stdin: str, project_dir: Path | None) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ["PATH"]}
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        [str(_HOOK_SCRIPT)],
        input=stdin,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _assert_pass_through(*, result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0
    assert result.stdout == ""


def test_script_is_executable() -> None:
    assert _HOOK_SCRIPT.is_file()
    assert os.access(_HOOK_SCRIPT, os.X_OK)


def test_blocks_memory_write_in_governed_project(tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    result = _run_hook(
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=project,
    )
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "/livespec-impl-beads:capture-memo" in decision["reason"]
    assert decision["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_reason_names_the_configured_plugin_namespace(tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path, plugin="livespec-impl-plaintext")
    result = _run_hook(
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=project,
    )
    decision = json.loads(result.stdout)
    assert "/livespec-impl-plaintext:capture-memo" in decision["reason"]
    assert "/livespec-impl-beads" not in decision["reason"]


def test_passes_through_without_livespec_config(tmp_path: Path) -> None:
    result = _run_hook(
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(result=result)


def test_passes_through_when_no_implementation_plugin(tmp_path: Path) -> None:
    (tmp_path / ".livespec.jsonc").write_text(
        '{ "template": "livespec", "spec_root": "SPECIFICATION" }\n',
        encoding="utf-8",
    )
    result = _run_hook(
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(result=result)


def test_passes_through_for_non_memory_write(tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    result = _run_hook(
        stdin=_hook_input(file_path=str(project / "docs" / "notes.md")),
        project_dir=project,
    )
    _assert_pass_through(result=result)


def test_passes_through_for_memory_path_without_md_suffix(tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    result = _run_hook(
        stdin=_hook_input(file_path="/home/user/.claude/projects/-x/memory/scratch.txt"),
        project_dir=project,
    )
    _assert_pass_through(result=result)


def test_passes_through_for_non_write_tool(tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    result = _run_hook(
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH, tool_name="Edit"),
        project_dir=project,
    )
    _assert_pass_through(result=result)


def test_passes_through_when_project_dir_unset(tmp_path: Path) -> None:
    _governed_project(root=tmp_path)
    result = _run_hook(
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=None,
    )
    _assert_pass_through(result=result)


def test_passes_through_on_malformed_stdin(tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    result = _run_hook(stdin="not json at all", project_dir=project)
    _assert_pass_through(result=result)


def test_passes_through_on_unparseable_config(tmp_path: Path) -> None:
    (tmp_path / ".livespec.jsonc").write_text("{ broken jsonc", encoding="utf-8")
    result = _run_hook(
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(result=result)
