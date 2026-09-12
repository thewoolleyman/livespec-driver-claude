"""Integration-tier realizations of the core-root-resolution and structural-gate
scenarios in SPECIFICATION/scenarios.md.

Node ids live under `tests.integration.` (an allowlisted scenario tier), so the
heading-coverage scenario-tier direction resolves them without a marker. Each
test drives the real shipped code end to end — the single core-root resolver
(`.claude-plugin/lib/resolve_core_root.py`) against hermetic registry/checkout
fixtures, and the shared structural check against a byte copy of the shipped
plugin tree with one deliberate mutation — never a live host or network.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest
from livespec_dev_tooling.driver_checks.plugin_structure import claude_profile_violations
from returns.io import IOSuccess
from returns.unsafe import unsafe_perform_io

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESOLVER_PATH = _REPO_ROOT / ".claude-plugin" / "lib" / "resolve_core_root.py"
_CORE_OPS = "critique doctor help next propose-change prune-history revise seed".split()
_CORE_ONLY_OPS = "critique doctor propose-change prune-history revise seed".split()


def _load_resolver() -> ModuleType:
    # The resolver imports its sibling `_resolve_core_root_text` by bare name, so
    # its directory must be importable before the module itself is loaded.
    lib_dir = str(_RESOLVER_PATH.parent)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    spec = importlib.util.spec_from_file_location("resolve_core_root", _RESOLVER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: under `from __future__ import annotations`, dataclasses
    # resolves field annotations via sys.modules[cls.__module__], which is None for
    # an unregistered module and dies with an unrelated-looking AttributeError.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_RESOLVER = _load_resolver()


def _resolve(*, project_root: Path, home: Path, environ: dict[str, str]):
    return _RESOLVER.resolve_core_root(project_root=project_root, home=home, environ=environ)


def _write_registry(
    *, home: Path, records: list[dict[str, str]] | None, key: str = "livespec@livespec"
) -> None:
    reg = home / ".claude" / "plugins" / "installed_plugins.json"
    reg.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {} if records is None else {"plugins": {key: records}}
    reg.write_text(json.dumps(payload), encoding="utf-8")


def _make_core_checkout(*, project_root: Path, ops: list[str]) -> None:
    prose = project_root / ".claude-plugin" / "prose"
    prose.mkdir(parents=True, exist_ok=True)
    for op in ops:
        (prose / f"{op}.md").write_text("prose\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Core-root resolution scenarios
# --------------------------------------------------------------------------


def test_scenario_resolution_via_operator_override(tmp_path: Path) -> None:
    out = _resolve(
        project_root=tmp_path / "proj",
        home=tmp_path / "home",
        environ={"LIVESPEC_CORE_PLUGIN_ROOT": str(tmp_path / "override")},
    )
    assert out.source == "override"
    assert out.path == tmp_path / "override"


def test_scenario_resolution_falls_back_to_governed_project_checkout(tmp_path: Path) -> None:
    proj = tmp_path / "core"
    _make_core_checkout(project_root=proj, ops=_CORE_OPS)
    out = _resolve(project_root=proj, home=tmp_path / "home", environ={})
    assert out.source == "project_checkout"
    assert out.path == proj / ".claude-plugin"


def test_scenario_resolution_rejects_a_non_core_project_checkout(tmp_path: Path) -> None:
    # Ships only generic prose (no core-exclusive op), so it is NOT core and the
    # resolver declines rule 2 and falls through to the registry rule.
    proj = tmp_path / "consumer"
    _make_core_checkout(project_root=proj, ops=["next", "help"])
    out = _resolve(project_root=proj, home=tmp_path / "home", environ={})
    # Declined rule 2 (not treated as core) and fell through — never resolved as a
    # project checkout, and NOT the hard incomplete-core error reserved for a
    # checkout carrying core-exclusive prose.
    assert getattr(out, "source", None) != "project_checkout"
    assert out.kind != "core_checkout_incomplete"


def test_scenario_incomplete_core_checkout_fails_rather_than_falling_back(tmp_path: Path) -> None:
    proj = tmp_path / "core"
    _make_core_checkout(
        project_root=proj, ops=["doctor", "revise"]
    )  # core-exclusive but incomplete
    out = _resolve(project_root=proj, home=tmp_path / "home", environ={})
    assert out.kind == "core_checkout_incomplete"


def test_scenario_incomplete_checkout_diagnostic_names_the_recovery(tmp_path: Path) -> None:
    proj = tmp_path / "core"
    _make_core_checkout(project_root=proj, ops=["doctor", "revise"])
    out = _resolve(project_root=proj, home=tmp_path / "home", environ={})
    diagnostic = _RESOLVER._diagnostic(unresolved=out)
    assert "LIVESPEC_CORE_PLUGIN_ROOT" in diagnostic


def test_scenario_resolution_selects_the_install_record_for_this_project(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    other = tmp_path / "other"
    _write_registry(
        home=tmp_path / "home",
        records=[
            {"projectPath": str(other), "installPath": str(tmp_path / "wrong")},
            {"projectPath": str(proj), "installPath": str(tmp_path / "right")},
        ],
    )
    out = _resolve(project_root=proj, home=tmp_path / "home", environ={})
    assert out.source == "install_record"
    assert out.path == tmp_path / "right"


def test_scenario_resolution_reports_a_projectpath_mismatch_as_such(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    _write_registry(
        home=tmp_path / "home",
        records=[{"projectPath": str(tmp_path / "elsewhere"), "installPath": str(tmp_path / "x")}],
    )
    out = _resolve(project_root=proj, home=tmp_path / "home", environ={})
    assert out.kind == "project_not_installed"


def test_scenario_unreadable_registry_is_not_reported_as_core_uninstalled(tmp_path: Path) -> None:
    home = tmp_path / "home"
    reg = home / ".claude" / "plugins" / "installed_plugins.json"
    # A directory where the registry file belongs makes the read fail with an
    # OSError — an unreadable (non-answer) registry, distinct from malformed JSON.
    reg.mkdir(parents=True, exist_ok=True)
    out = _resolve(project_root=tmp_path / "proj", home=home, environ={})
    assert out.kind == "registry_unreadable"


def test_scenario_absent_registry_yields_the_install_instructions(tmp_path: Path) -> None:
    out = _resolve(project_root=tmp_path / "proj", home=tmp_path / "home", environ={})
    assert out.kind == "registry_absent"
    diagnostic = _RESOLVER._diagnostic(unresolved=out)
    assert "Install" in diagnostic


# --------------------------------------------------------------------------
# Structural-gate scenarios
# --------------------------------------------------------------------------


@pytest.fixture
def plugin_tree(tmp_path: Path) -> Path:
    """A byte copy of the shipped .claude-plugin tree that passes the check clean."""
    root = tmp_path / "tree"
    root.mkdir()
    shutil.copytree(_REPO_ROOT / ".claude-plugin", root / ".claude-plugin")
    assert _violations(root=root) == [], "shipped tree must pass before any mutation"
    return root


def _violations(*, root: Path) -> list[str]:
    outcome = claude_profile_violations(root=root)
    assert isinstance(outcome, IOSuccess), outcome
    return list(unsafe_perform_io(outcome.unwrap()))


def test_scenario_structural_check_rejects_skill_md_invoking_uv_run(plugin_tree: Path) -> None:
    skill = plugin_tree / ".claude-plugin" / "skills" / "seed" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + '\n```bash\nuv run python3 "$LIVESPEC_CORE_ROOT/scripts/bin/seed.py"\n```\n',
        encoding="utf-8",
    )
    assert any("uv run" in v for v in _violations(root=plugin_tree))


def test_scenario_structural_check_rejects_driver_plugin_root_placeholder(
    plugin_tree: Path,
) -> None:
    skill = plugin_tree / ".claude-plugin" / "skills" / "seed" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + '\n```bash\npython3 "${CLAUDE_PLUGIN_ROOT}/scripts/bin/seed.py"\n```\n',
        encoding="utf-8",
    )
    assert any("placeholder" in v for v in _violations(root=plugin_tree))


def test_scenario_structural_check_rejects_extra_or_missing_skill_directory(
    plugin_tree: Path,
) -> None:
    shutil.rmtree(plugin_tree / ".claude-plugin" / "skills" / "seed")
    assert _violations(root=plugin_tree) != []


def test_scenario_structural_check_rejects_marketplace_description_drift(plugin_tree: Path) -> None:
    mkt_path = plugin_tree / ".claude-plugin" / "marketplace.json"
    mkt = json.loads(mkt_path.read_text(encoding="utf-8"))
    mkt["plugins"][0]["description"] = "drifted description that differs from plugin.json"
    mkt_path.write_text(json.dumps(mkt, indent=2), encoding="utf-8")
    assert any("description" in v for v in _violations(root=plugin_tree))
