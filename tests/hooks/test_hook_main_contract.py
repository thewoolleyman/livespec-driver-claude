"""Importable `main() -> int` contract tests for the plugin-shipped hooks.

Every plugin-shipped hook body under `.claude-plugin/hooks/` MUST expose an
importable `main() -> int` that owns stdin/stdout at the hook boundary,
returns 0 on every path (fail-open), and does nothing at module import — so
the body is measurable in-process for real per-file coverage. These tests pin
that contract for the shared hook set in one place.
"""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_HOOK_MODULES = (
    "block_auto_memory",
    "warn_plan_persistence",
    "no_shadow_ledger",
    "primary_checkout_playwright_guard",
)


def _reload_hook(*, module_name: str) -> ModuleType:
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_each_hook_main_returns_zero_on_empty_stdin(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    for module_name in _HOOK_MODULES:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        hook = _reload_hook(module_name=module_name)
        assert hook.main() == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


def test_each_hook_main_returns_zero_on_malformed_stdin(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    for module_name in _HOOK_MODULES:
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json at all"))
        hook = _reload_hook(module_name=module_name)
        assert hook.main() == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


def test_github_rate_limit_guard_allows_sleeping_single_mutation(monkeypatch, capsys) -> None:
    hook = _reload_hook(module_name="github_rate_limit_guard")
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "sleep 1 && gh api -X POST repos/acme/project/dispatches",
        },
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_primary_guard_fails_open_for_missing_path_and_linked_worktree(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    hook = _reload_hook(module_name="primary_checkout_playwright_guard")

    def assert_silent(*, cwd: Path) -> None:
        payload = {
            "tool_name": "mcp__playwright__browser_snapshot",
            "cwd": str(cwd),
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        assert hook.main() == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    assert_silent(cwd=tmp_path / "missing")

    governed_root = tmp_path / "governed"
    governed_root.mkdir()
    _ = (governed_root / ".livespec.jsonc").write_text("{}\n", encoding="utf-8")

    def linked_context(*, cwd: Path) -> tuple[Path, Path, Path]:
        del cwd
        return governed_root, tmp_path / "git-dir", tmp_path / "git-common-dir"

    monkeypatch.setattr(hook, "_git_context", linked_context)
    assert_silent(cwd=governed_root)
