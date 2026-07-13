"""Unit tests for `.claude-plugin/hooks/block_auto_memory.py`.

The hook body is exercised IN-PROCESS via its importable `main() -> int`
(monkeypatched `sys.stdin` + `CLAUDE_PROJECT_DIR`, stdout via `capsys`) for
real per-file coverage, plus ONE retained subprocess smoke that proves the
shipped script still speaks the PreToolUse stdin/stdout protocol.

Contract under test (work-item livespec-driver-claude-e1s; reason reworded
per bug livespec-co9h):

- Writes matching `**/memory/*.md` in a livespec-governed project (a
  `.livespec.jsonc` declaring `implementation.plugin`) are BLOCKED with
  decision JSON whose reason INTENT-ROUTES the would-be write to all four
  destinations and names the resolved `/<plugin>:capture-work-item` skill —
  the namespace comes from config, never hardcoded.
- Everything else — non-memory paths, non-governed projects, missing config
  keys, unset CLAUDE_PROJECT_DIR, malformed stdin — is a silent pass-through:
  exit 0, empty stdout (fail-open).
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
_HOOK_SCRIPT = _REPO_ROOT / ".claude-plugin" / "hooks" / "block_auto_memory.py"
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import block_auto_memory  # noqa: E402 — path-dependent hook import.

_MEMORY_WRITE_PATH = "/home/user/.claude/projects/-data-projects-x/memory/MEMORY.md"


def _hook_input(*, file_path: str, tool_name: str = "Write") -> str:
    return json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": {"file_path": file_path, "content": "# memory\n"},
        }
    )


def _governed_project(*, root: Path, plugin: str = "livespec-orchestrator-beads-fabro") -> Path:
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


def _run(*, monkeypatch, capsys, stdin: str, project_dir: Path | None) -> tuple[int, str]:
    """Drive `main()` in-process; return (returncode, stdout)."""
    monkeypatch.setattr(sys, "stdin", StringIO(stdin))
    if project_dir is None:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_dir))
    returncode = block_auto_memory.main()
    captured = capsys.readouterr()
    assert captured.err == ""
    return returncode, captured.out


def _assert_pass_through(*, returncode: int, stdout: str) -> None:
    assert returncode == 0
    assert stdout == ""


def test_script_is_executable() -> None:
    assert _HOOK_SCRIPT.is_file()
    assert os.access(_HOOK_SCRIPT, os.X_OK)


def test_blocks_memory_write_in_governed_project(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=project,
    )
    assert returncode == 0
    decision = json.loads(stdout)
    assert decision["decision"] == "block"
    assert "/livespec-orchestrator-beads-fabro:capture-work-item" in decision["reason"]
    assert decision["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_reason_routes_by_intent_not_only_capture_work_item(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    """co9h: the deny reason routes the would-be memory write BY WHAT IT IS."""
    project = _governed_project(root=tmp_path)
    _, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=project,
    )
    decision = json.loads(stdout)
    reason = decision["reason"]
    assert "/livespec-orchestrator-beads-fabro:capture-work-item" in reason
    assert "/livespec:propose-change" in reason
    assert "AGENTS.md" in reason
    assert "session-only" in reason
    assert "Do NOT silently drop" in reason
    assert decision["hookSpecificOutput"]["permissionDecisionReason"] == reason


def test_reason_names_the_configured_plugin_namespace(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path, plugin="livespec-impl-plaintext")
    _, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=project,
    )
    decision = json.loads(stdout)
    assert "/livespec-impl-plaintext:capture-work-item" in decision["reason"]
    assert "/livespec-orchestrator-beads-fabro" not in decision["reason"]


def test_subprocess_smoke_blocks_memory_write(tmp_path: Path) -> None:
    """The shipped script path still speaks the PreToolUse stdin/stdout protocol."""
    project = _governed_project(root=tmp_path)
    result = subprocess.run(
        ["python3", str(_HOOK_SCRIPT)],
        input=_hook_input(file_path=_MEMORY_WRITE_PATH),
        env={"PATH": os.environ["PATH"], "CLAUDE_PROJECT_DIR": str(project)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "/livespec-orchestrator-beads-fabro:capture-work-item" in decision["reason"]


def test_passes_through_without_livespec_config(monkeypatch, capsys, tmp_path: Path) -> None:
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_when_config_is_not_a_mapping(monkeypatch, capsys, tmp_path: Path) -> None:
    (tmp_path / ".livespec.jsonc").write_text("[]\n", encoding="utf-8")
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_when_no_implementation_plugin(monkeypatch, capsys, tmp_path: Path) -> None:
    (tmp_path / ".livespec.jsonc").write_text(
        '{ "template": "livespec", "spec_root": "SPECIFICATION" }\n',
        encoding="utf-8",
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_when_implementation_is_not_a_mapping(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    (tmp_path / ".livespec.jsonc").write_text('{ "implementation": "beads" }\n', encoding="utf-8")
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_when_plugin_is_blank(monkeypatch, capsys, tmp_path: Path) -> None:
    (tmp_path / ".livespec.jsonc").write_text(
        '{ "implementation": { "plugin": "   " } }\n', encoding="utf-8"
    )
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_for_non_memory_write(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=str(project / "docs" / "notes.md")),
        project_dir=project,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_for_memory_path_without_md_suffix(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path="/home/user/.claude/projects/-x/memory/scratch.txt"),
        project_dir=project,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_for_non_write_tool(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH, tool_name="Edit"),
        project_dir=project,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_when_tool_input_missing(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=json.dumps({"tool_name": "Write"}),
        project_dir=project,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_when_file_path_missing(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=json.dumps({"tool_name": "Write", "tool_input": {"content": "x"}}),
        project_dir=project,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_when_project_dir_unset(monkeypatch, capsys, tmp_path: Path) -> None:
    _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=None,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_on_malformed_stdin(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin="not json at all",
        project_dir=project,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_on_non_mapping_payload(monkeypatch, capsys, tmp_path: Path) -> None:
    project = _governed_project(root=tmp_path)
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin="[]",
        project_dir=project,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_passes_through_on_unparseable_config(monkeypatch, capsys, tmp_path: Path) -> None:
    (tmp_path / ".livespec.jsonc").write_text("{ broken jsonc", encoding="utf-8")
    returncode, stdout = _run(
        monkeypatch=monkeypatch,
        capsys=capsys,
        stdin=_hook_input(file_path=_MEMORY_WRITE_PATH),
        project_dir=tmp_path,
    )
    _assert_pass_through(returncode=returncode, stdout=stdout)


def test_strip_jsonc_comments_covers_string_escape_and_both_comment_forms() -> None:
    # Exercises every branch of the JSONC comment stripper: an in-string
    # escaped quote (`\"`) and escaped backslash, a closing then re-opening
    # string, a `//` line comment, and a `/* ... */` block comment.
    src = '{"a": "x\\"y\\\\z"} // line\n/* block\ncomment */ "tail"'
    stripped = block_auto_memory._strip_jsonc_comments(text=src)
    assert '"x\\"y\\\\z"' in stripped
    assert "// line" not in stripped
    assert "block" not in stripped
    assert '"tail"' in stripped


def test_as_object_dict_narrows_only_mappings() -> None:
    assert block_auto_memory._as_object_dict({"k": 1}) == {"k": 1}
    assert block_auto_memory._as_object_dict([1, 2]) is None
    assert block_auto_memory._as_object_dict("str") is None
