"""Policy checks for the hook Result/IOResult railway adoption."""

from __future__ import annotations

import importlib.util
import sys
from io import StringIO
from pathlib import Path

import tomli

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_HOOK_FILES = (
    _REPO_ROOT / ".claude-plugin" / "hooks" / "block_auto_memory.py",
    _REPO_ROOT / ".claude-plugin" / "hooks" / "warn_plan_persistence.py",
    _REPO_ROOT / ".claude-plugin" / "hooks" / "tmux_fleet_guard.py",
    _REPO_ROOT / ".claude" / "hooks" / "livespec_footgun_guard.py",
)


def _pyproject() -> dict[str, object]:
    return tomli.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_returns_is_vendored_under_vendor() -> None:
    vendor_root = _REPO_ROOT / "_vendor" / "returns"
    assert (vendor_root / "__init__.py").is_file()
    assert (vendor_root / "result.py").is_file()
    assert (vendor_root / "io.py").is_file()

    spec = importlib.util.spec_from_file_location("returns", vendor_root / "__init__.py")
    assert spec is not None


def test_ruff_ble_and_pyright_unused_call_result_are_errors() -> None:
    config = _pyproject()
    ruff_lint = config["tool"]["ruff"]["lint"]  # type: ignore[index]
    assert "BLE" in ruff_lint["select"]  # type: ignore[index]

    pyright = config["tool"]["pyright"]  # type: ignore[index]
    assert pyright["reportUnusedCallResult"] == "error"  # type: ignore[index]


def test_repo_owned_hook_bodies_import_result_railway() -> None:
    for hook_file in _HOOK_FILES:
        source = hook_file.read_text(encoding="utf-8")
        assert "returns.result" in source or "returns.io" in source, hook_file


def test_vendor_path_helpers_are_idempotent() -> None:
    import block_auto_memory
    import tmux_fleet_guard
    import warn_plan_persistence

    assert block_auto_memory._add_vendor_path() is None
    assert tmux_fleet_guard._add_vendor_path() is None
    assert warn_plan_persistence._add_vendor_path() is None


def test_vendor_path_helpers_insert_when_path_is_absent(monkeypatch) -> None:
    import tmux_fleet_guard
    import warn_plan_persistence

    for module in (tmux_fleet_guard, warn_plan_persistence):
        vendor_path = str(module.Path(module.__file__).resolve().parents[2] / "_vendor")
        monkeypatch.setattr(
            module.sys, "path", [item for item in module.sys.path if item != vendor_path]
        )
        assert module._add_vendor_path() is None
        assert vendor_path in module.sys.path


class _BrokenStdin:
    def read(self) -> str:
        raise OSError("stdin failed")


class _BrokenStdout:
    def write(self, text: str) -> int:
        raise OSError(text)


def test_rail_helpers_capture_io_failures(monkeypatch) -> None:
    import block_auto_memory
    import tmux_fleet_guard
    import warn_plan_persistence

    for module in (block_auto_memory, tmux_fleet_guard, warn_plan_persistence):
        monkeypatch.setattr(module.sys, "stdin", _BrokenStdin())
        read_io = module._read_stdin()[1].value_or("fallback")
        assert read_io is not None

        monkeypatch.setattr(module.sys, "stdout", _BrokenStdout())
        write_io = module._write_stdout(text="x").value_or(0)
        assert write_io is not None


def test_main_fail_open_when_rail_raises(monkeypatch, capsys) -> None:
    import block_auto_memory
    import tmux_fleet_guard
    import warn_plan_persistence

    def broken_decision(*, raw: str):
        raise RuntimeError(raw)

    monkeypatch.setattr(block_auto_memory.sys, "stdin", StringIO("{}"))
    monkeypatch.setattr(block_auto_memory, "_decision_result", broken_decision)
    assert block_auto_memory.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    monkeypatch.setattr(warn_plan_persistence.sys, "stdin", StringIO("{}"))
    monkeypatch.setattr(warn_plan_persistence, "_warning_result", broken_decision)
    assert warn_plan_persistence.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    def broken_read():
        raise RuntimeError("read rail failed")

    monkeypatch.setattr(tmux_fleet_guard, "_read_stdin", broken_read)
    assert tmux_fleet_guard.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_vendor_path_helpers_tolerate_missing_vendor(monkeypatch) -> None:
    import block_auto_memory
    import tmux_fleet_guard
    import warn_plan_persistence

    for module in (block_auto_memory, tmux_fleet_guard, warn_plan_persistence):
        monkeypatch.setattr(module.Path, "is_dir", lambda _path: False)
        assert module._add_vendor_path() is None
