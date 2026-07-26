"""Policy checks for the hook Result/IOResult railway adoption.

Two DIFFERENT railway sources are correct here, and the split is the policy:

- **Plugin-shipped hooks** (`.claude-plugin/hooks/`) are the only files the
  installer copies, and they run under bare `python3` with no virtualenv and no
  third-party packages. Hooks that need a decision rail MUST take it from the
  self-contained sibling `_result` module, with no `returns` import and no
  `sys.path` arithmetic — a module-scope third-party import there kills the
  process before `main()` can fail open, so the hook silently guards nothing.
- **The project-local footgun guard** (`.claude/hooks/`) is NEVER shipped; it
  runs from this checkout, where the repo-root `_vendor/` tree carries the real
  dry-python/returns. It keeps using that.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path

import pytest
import tomli

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_SHIPPED_HOOKS = (
    _HOOKS_DIR / "block_auto_memory.py",
    _HOOKS_DIR / "warn_plan_persistence.py",
    # no_shadow_ledger.py is intentionally excluded: its body is owned by
    # livespec_dev_tooling.install_no_shadow_ledger.CANONICAL_NO_SHADOW_LEDGER_BODY,
    # installed via `just install-no-shadow-ledger`, and guarded byte-identical
    # across Drivers by check-no-shadow-ledger-body-identical.
    _HOOKS_DIR / "tmux_fleet_guard.py",
    _HOOKS_DIR / "_tmux_hazard.py",
)
_SHIPPED_RAILWAY_HOOKS = (
    _HOOKS_DIR / "block_auto_memory.py",
    _HOOKS_DIR / "warn_plan_persistence.py",
)
# The closed set of conforming BLE001 suppression wordings is deliberately NOT
# copied here. It is owned by livespec `SPECIFICATION/non-functional-requirements.md`
# and enforced by `check-no-except-outside-io`, which this repo already runs over
# both hook trees (see the coverage test below). A local copy was a hand-maintained
# mirror of a set owned elsewhere with nothing holding the two in lockstep — and it
# rotted exactly as that shape predicts: when the loop-iteration wording was retired
# fleet-wide (2026-07-26 ruling; livespec-dev-tooling PR #681), the copy went on
# ACCEPTING it, silently, because it is a membership allowlist and nothing here uses
# that marker. Nothing went red; the guard just got weaker than the contract it
# guards.
#
# Two incidental constraints this comment must respect, both learned from the gate:
# it must not spell the literal suppression directive (ruff reads it as a real,
# unused one via RUF100), and it must cite the spec at FILE level only — the
# heading-level form is banned because such citations rot on rename.
_LOCAL_ONLY_HOOK = _REPO_ROOT / ".claude" / "hooks" / "livespec_footgun_guard.py"


def _imported_roots(*, source: str) -> set[str]:
    """Top-level package name of every import, read off the AST not the prose."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".")[0])
    return roots


def _pyproject() -> dict[str, object]:
    return tomli.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_returns_is_vendored_under_vendor_for_the_local_only_hook() -> None:
    vendor_root = _REPO_ROOT / "_vendor" / "returns"
    assert (vendor_root / "__init__.py").is_file()
    assert (vendor_root / "result.py").is_file()
    assert (vendor_root / "io.py").is_file()

    spec = importlib.util.spec_from_file_location("returns", vendor_root / "__init__.py")
    assert spec is not None

    source = _LOCAL_ONLY_HOOK.read_text(encoding="utf-8")
    assert "returns.result" in source or "returns.io" in source


def test_ruff_ble_and_pyright_unused_call_result_are_errors() -> None:
    config = _pyproject()
    ruff_lint = config["tool"]["ruff"]["lint"]  # type: ignore[index]
    assert "BLE" in ruff_lint["select"]  # type: ignore[index]

    pyright = config["tool"]["pyright"]  # type: ignore[index]
    assert pyright["reportUnusedCallResult"] == "error"  # type: ignore[index]


def test_shipped_hook_bodies_are_self_contained() -> None:
    for hook_file in _SHIPPED_HOOKS:
        source = hook_file.read_text(encoding="utf-8")
        roots = _imported_roots(source=source)
        assert "returns" not in roots, hook_file
        assert "sys.path.insert" not in source, hook_file


def test_shipped_hook_bodies_import_the_self_contained_railway_when_needed() -> None:
    for hook_file in _SHIPPED_RAILWAY_HOOKS:
        source = hook_file.read_text(encoding="utf-8")
        roots = _imported_roots(source=source)
        assert "_result" in roots, hook_file


def test_every_shipped_hook_is_covered_by_a_declared_source_tree() -> None:
    """Marker conformance is DELEGATED to the producer; this proves the delegation is real.

    `check-no-except-outside-io` (livespec-dev-tooling) owns the closed set of
    conforming `# noqa: BLE001` wordings, the per-artifact `sole` cardinality, and
    catch position. It derives the files it inspects from this repo's declared
    `source_trees`, and this repo's `just check` runs it. So re-asserting the closed
    set here would duplicate the producer's rule — which is the defect being removed,
    not a second line of defence.

    What delegation CAN silently lose is COVERAGE: a hook that drifts outside every
    declared `source_trees` entry stops being inspected, and the producer's check goes
    on passing because it never looked. That failure is invisible without this test,
    and it is not something the producer can detect on this repo's behalf. So this
    asserts the one property that is genuinely local and genuinely losable.

    Deliberately NOT re-checked here: the retired loop-iteration wording. Proof that
    it is rejected belongs at the producer and lives there — livespec-dev-tooling's
    `test_no_except_outside_io_rejects_the_retired_loop_iteration_marker`, PR #681.
    Restating it here would recreate the duplication this change exists to delete.
    """
    declared = _pyproject()["tool"]["livespec_dev_tooling"]["source_trees"]
    assert declared, "source_trees must be declared non-empty for the check to inspect anything"
    trees = [(_REPO_ROOT / entry).resolve() for entry in declared]

    for hook_file in _SHIPPED_HOOKS:
        resolved = hook_file.resolve()
        assert any(resolved.is_relative_to(tree) for tree in trees), (
            f"{resolved} is not under any declared source_trees entry {declared}, so "
            f"check-no-except-outside-io never inspects it and its BLE001 markers are "
            f"unenforced"
        )


def test_local_footgun_guard_has_one_standardized_boundary_marker() -> None:
    source = _LOCAL_ONLY_HOOK.read_text(encoding="utf-8")
    markers = []
    for line in source.splitlines():
        if "# noqa: BLE001" not in line:
            continue
        markers.append(line[line.index("# noqa: BLE001") :])

    assert markers == ["# noqa: BLE001 — sole fail-open hook boundary: silent pass-through, exit 0"]


def test_shipped_railway_module_is_standard_library_only() -> None:
    source = (_HOOKS_DIR / "_result.py").read_text(encoding="utf-8")
    for root in _imported_roots(source=source):
        assert root in sys.stdlib_module_names, root


def test_success_rail_carries_its_value() -> None:
    from _result import IOSuccess, Success

    assert Success(3).unwrap() == 3
    assert Success(3).value_or(default=9) == 3
    assert IOSuccess("x").value_or(default="fallback") == "x"
    with pytest.raises(RuntimeError):
        _ = Success(3).failure()


def test_failure_rail_yields_the_default() -> None:
    from _result import Failure, IOFailure

    error = OSError("boom")
    assert Failure(error).failure() is error
    assert Failure(error).value_or(default=9) == 9
    assert IOFailure(error).value_or(default="fallback") == "fallback"
    with pytest.raises(RuntimeError):
        _ = Failure(error).unwrap()


class _BrokenStdin:
    def read(self) -> str:
        raise OSError("stdin failed")


class _BrokenStdout:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, text: str) -> int:
        self.writes.append(text)
        raise OSError(text)


def test_main_fail_open_when_decision_rail_raises(monkeypatch, capsys) -> None:
    import block_auto_memory
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


def test_main_boundaries_own_unexpected_io_failures(monkeypatch, capsys, tmp_path) -> None:
    import block_auto_memory
    import tmux_fleet_guard
    import warn_plan_persistence

    for module in (block_auto_memory, tmux_fleet_guard, warn_plan_persistence):
        monkeypatch.setattr(module.sys, "stdin", _BrokenStdin())
        assert module.main() == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".livespec.jsonc").write_text(
        '{"implementation": {"plugin": "livespec-orchestrator-beads-fabro"}}',
        encoding="utf-8",
    )
    memory_payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_path / "claude" / "memory" / "note.md"),
            "content": "durable note",
        },
    }
    memory_stdout = _BrokenStdout()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_dir))
    monkeypatch.setattr(block_auto_memory.sys, "stdin", StringIO(json.dumps(memory_payload)))
    monkeypatch.setattr(block_auto_memory.sys, "stdout", memory_stdout)
    assert block_auto_memory.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert len(memory_stdout.writes) == 1
    assert '"permissionDecision": "deny"' in memory_stdout.writes[0]

    transcript_path = tmp_path / "transcript.jsonl"
    transcript_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "message": {"content": "plan the implementation"},
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "\n".join(
                                        [
                                            "# Stage 1",
                                            "## Stage 2",
                                            "### Stage 3",
                                        ]
                                    ),
                                }
                            ]
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    warning_stdout = _BrokenStdout()
    warning_payload = {"transcript_path": str(transcript_path), "stop_hook_active": False}
    monkeypatch.setattr(warn_plan_persistence.sys, "stdin", StringIO(json.dumps(warning_payload)))
    monkeypatch.setattr(warn_plan_persistence.sys, "stdout", warning_stdout)
    assert warn_plan_persistence.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert len(warning_stdout.writes) == 1
    assert '"systemMessage"' in warning_stdout.writes[0]
