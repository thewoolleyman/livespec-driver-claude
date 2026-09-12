"""Conformance witnesses for the Driver's structural and operational spec rows.

Each test asserts a concrete, control-armed fact about THIS repo that a spec
heading commits to — the repo layout, the enforcement-suite wiring, the version
source of truth, the test surfaces, the ships-no-scripts binding constraint —
and one runs the shared task-runner check-runner against this repo (clean) plus
a violating fixture (reddens).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from livespec_dev_tooling.checks import no_direct_tool_invocation

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repo_layout_declared_paths_exist() -> None:
    """non-functional-requirements.md "Repo layout": every declared path exists."""
    for rel in (
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".claude-plugin/skills",
        ".claude-plugin/hooks/hooks.json",
        ".claude-plugin/lib/resolve_core_root.py",
        "tests/e2e-cli",
        "tests/hooks",
        "SPECIFICATION",
        "justfile",
        "lefthook.yml",
        "pyproject.toml",
    ):
        assert (_REPO_ROOT / rel).exists(), rel


def test_enforcement_suite_gates_are_wired() -> None:
    """non-functional-requirements.md "Enforcement suite": each named gate is a recipe."""
    justfile = (_REPO_ROOT / "justfile").read_text(encoding="utf-8")
    for gate in (
        "check-plugin-structure",
        "check-hooks",
        "check-e2e-cli",
        "check-heading-coverage",
        "check-lint",
        "check-format",
    ):
        assert f"\n{gate}:" in justfile, gate


def test_versioning_plugin_json_is_the_sole_version_source() -> None:
    """contracts.md "Versioning" + n-f-r "Build and release": version SoT.

    plugin.json.version is non-empty (release-please auto-manages it) and
    marketplace.json carries NO version field. Control-armed: an empty plugin
    version or a marketplace version key fails.
    """
    plugin = json.loads((_REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert plugin.get("version")
    marketplace = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert "version" not in marketplace


def test_test_discipline_surfaces_exist() -> None:
    """non-functional-requirements.md "Test discipline": the two test surfaces are populated."""
    for surface in ("e2e-cli", "hooks"):
        directory = _REPO_ROOT / "tests" / surface
        assert directory.is_dir()
        assert list(directory.glob("test_*.py")), surface


def test_binding_constraint_ships_no_scripts_tree() -> None:
    """constraints.md "Binding constraints": the Driver bundle ships NO scripts/ tree.

    The bundle ships bindings, hooks, lib, and the manifest only; core wrappers
    are resolved at runtime. Control-armed: a `.claude-plugin/scripts/` directory
    would fail here (and would also silently reclassify the plugin model — see
    contracts.md "Core-root resolution").
    """
    assert not (_REPO_ROOT / ".claude-plugin" / "scripts").exists()


def test_task_runner_discipline_bans_direct_tool_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """non-functional-requirements.md "Task-runner discipline": lefthook/CI route through just.

    Conformance: the no-direct-tool-invocation check-runner passes against THIS
    repo (clean) and reddens on a fabricated lefthook hook that shells a dev tool
    directly.
    """
    monkeypatch.chdir(_REPO_ROOT)
    assert no_direct_tool_invocation.main() == 0

    violation = tmp_path / "violation"
    violation.mkdir()
    (violation / "lefthook.yml").write_text(
        "pre-push:\n  commands:\n    tests:\n      run: pytest -q\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(violation)
    assert no_direct_tool_invocation.main() == 1
