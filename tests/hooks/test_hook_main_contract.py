"""Importable `main() -> int` contract tests for the plugin-shipped hooks.

Every plugin-shipped hook body under `.claude-plugin/hooks/` MUST expose an
importable `main() -> int` that owns stdin/stdout at the hook boundary,
returns 0 on every path (fail-open), and does nothing at module import — so
the body is measurable in-process for real per-file coverage. These tests pin
that contract for all three hooks in one place.
"""

from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_HOOK_MODULES = ("block_auto_memory", "warn_plan_persistence", "no_shadow_ledger")


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
