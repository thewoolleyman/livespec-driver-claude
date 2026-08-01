"""Unit tests for the single core-root resolver the eight bindings share.

Lives beside the other bundle-wide suites in this directory because the
coverage recipe measures `pytest tests/hooks/`; the subject is a shipped
`.claude-plugin/` asset, the same population `test_rop_policy.py` and
`test_shipped_hooks_install_shape.py` govern.

Two disciplines this file is deliberately built around:

1. **A positive control.** `test_selects_this_projects_record_not_the_first`
   uses a registry whose FIRST record belongs to a DIFFERENT project. Without
   it, an implementation that still reads `entries[0]` would satisfy every
   other assertion here, because on a single-record registry position and
   projectPath agree. The control is what makes the rest of the file mean
   anything.

2. **Unreadability is spelled with undecodable BYTES, never `chmod`.** A
   `chmod 000` fixture is a lie when the suite runs as root: every read
   succeeds, the assertion never fires, and the test passes proving nothing.
   Invalid UTF-8 fails identically for every user.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_PATH = _REPO_ROOT / ".claude-plugin" / "lib" / "resolve_core_root.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("resolve_core_root", _MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registering before exec: under `from __future__ import annotations`,
    # `dataclasses` resolves field annotations through
    # `sys.modules[cls.__module__]`, which is None for an unregistered module
    # and dies at import with an unrelated-looking AttributeError.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_resolver = _load_module()


def _write_registry(*, home: Path, payload: object) -> Path:
    registry = home / ".claude" / "plugins" / "installed_plugins.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    _ = registry.write_text(json.dumps(payload), encoding="utf-8")
    return registry


def _records(*, entries: list[dict[str, str]]) -> dict[str, object]:
    return {"plugins": {"livespec@livespec": entries}}


def test_selects_this_projects_record_not_the_first(tmp_path: Path) -> None:
    """THE POSITIVE CONTROL: the first record belongs to another project."""
    home = tmp_path / "home"
    project = tmp_path / "this-project"
    project.mkdir()
    other = tmp_path / "other-project"
    other.mkdir()
    _ = _write_registry(
        home=home,
        payload=_records(
            entries=[
                {"projectPath": str(other), "installPath": "/cache/WRONG"},
                {"projectPath": str(project), "installPath": "/cache/RIGHT"},
            ]
        ),
    )

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootResolved)
    assert outcome.path == Path("/cache/RIGHT")
    assert outcome.source == "install_record"


def test_override_wins_over_every_fallback(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(
        home=home,
        payload=_records(entries=[{"projectPath": str(project), "installPath": "/cache/R"}]),
    )

    outcome = _resolver.resolve_core_root(
        project_root=project,
        home=home,
        environ={"LIVESPEC_CORE_PLUGIN_ROOT": "/explicit/override"},
    )

    assert isinstance(outcome, _resolver.CoreRootResolved)
    assert outcome.path == Path("/explicit/override")
    assert outcome.source == "override"


def test_empty_override_falls_through(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(
        home=home,
        payload=_records(entries=[{"projectPath": str(project), "installPath": "/cache/R"}]),
    )

    outcome = _resolver.resolve_core_root(
        project_root=project, home=home, environ={"LIVESPEC_CORE_PLUGIN_ROOT": ""}
    )

    assert isinstance(outcome, _resolver.CoreRootResolved)
    assert outcome.source == "install_record"


def test_governed_project_that_is_core_uses_its_own_checkout(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "core-repo"
    (project / ".claude-plugin" / "prose").mkdir(parents=True)

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootResolved)
    assert outcome.path == project / ".claude-plugin"
    assert outcome.source == "project_checkout"


def test_absent_registry_is_definitive_and_recommends_install(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()

    outcome = _resolver.resolve_core_root(
        project_root=project, home=tmp_path / "empty-home", environ={}
    )

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "registry_absent"
    assert "claude plugin install" in _resolver._diagnostic(unresolved=outcome)


def test_unreadable_registry_never_claims_core_is_missing(tmp_path: Path) -> None:
    """Undecodable bytes, not chmod — a root-run suite reads a chmod 000 file fine."""
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    registry = home / ".claude" / "plugins" / "installed_plugins.json"
    registry.parent.mkdir(parents=True)
    _ = registry.write_bytes(b"\xff\xfe\x00 not utf-8")

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "registry_malformed"
    message = _resolver._diagnostic(unresolved=outcome)
    assert "claude plugin install" not in message


def test_read_failure_is_distinct_from_absence(tmp_path: Path) -> None:
    """A directory where the registry file should be raises OSError, not FileNotFound."""
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    (home / ".claude" / "plugins" / "installed_plugins.json").mkdir(parents=True)

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "registry_unreadable"
    message = _resolver._diagnostic(unresolved=outcome)
    assert "claude plugin install" not in message
    assert "does NOT establish that core is missing" in message


def test_invalid_json_is_malformed_not_unreadable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    registry = home / ".claude" / "plugins" / "installed_plugins.json"
    registry.parent.mkdir(parents=True)
    _ = registry.write_text("{ not json", encoding="utf-8")

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "registry_malformed"


def test_non_object_top_level_is_malformed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(home=home, payload=["not", "an", "object"])

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "registry_malformed"


def test_missing_plugins_object_is_malformed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(home=home, payload={"version": 2})

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "registry_malformed"


def test_plugin_key_absent_is_definitive_and_recommends_install(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(home=home, payload={"plugins": {"something@else": []}})

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "plugin_absent"
    assert "claude plugin install" in _resolver._diagnostic(unresolved=outcome)


def test_plugin_value_not_an_array_is_malformed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(home=home, payload={"plugins": {"livespec@livespec": {"not": "a list"}}})

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "registry_malformed"


def test_no_record_for_this_project_names_the_mismatch(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "unprovisioned"
    project.mkdir()
    other = tmp_path / "some-other"
    other.mkdir()
    _ = _write_registry(
        home=home,
        payload=_records(entries=[{"projectPath": str(other), "installPath": "/cache/OTHER"}]),
    )

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "project_not_installed"
    message = _resolver._diagnostic(unresolved=outcome)
    assert str(project) in message
    assert str(other) in message
    assert "do not run `claude plugin update`" in message.replace("\n", " ")


def test_malformed_records_are_skipped_not_matched(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(
        home=home,
        payload={
            "plugins": {
                "livespec@livespec": [
                    "not-an-object",
                    {"installPath": "/cache/NO-PROJECT-PATH"},
                    {"projectPath": 17, "installPath": "/cache/NON-STRING"},
                    {"projectPath": str(project), "installPath": "/cache/RIGHT"},
                ]
            }
        },
    )

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootResolved)
    assert outcome.path == Path("/cache/RIGHT")


def test_matching_record_without_install_path_is_malformed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(home=home, payload=_records(entries=[{"projectPath": str(project)}]))

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "record_malformed"
    assert "claude plugin install" not in _resolver._diagnostic(unresolved=outcome)


def test_matching_record_with_empty_install_path_is_malformed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "p"
    project.mkdir()
    _ = _write_registry(
        home=home, payload=_records(entries=[{"projectPath": str(project), "installPath": ""}])
    )

    outcome = _resolver.resolve_core_root(project_root=project, home=home, environ={})

    assert isinstance(outcome, _resolver.CoreRootUnresolved)
    assert outcome.kind == "record_malformed"


def test_main_prints_the_resolved_root_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "p"
    project.mkdir()
    monkeypatch.setenv("LIVESPEC_CORE_PLUGIN_ROOT", "/explicit/override")

    code = _resolver.main(argv=["--project-root", str(project)])

    assert code == 0
    assert capsys.readouterr().out.strip() == "/explicit/override"


def test_main_writes_the_diagnostic_to_stderr_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "p"
    project.mkdir()
    monkeypatch.delenv("LIVESPEC_CORE_PLUGIN_ROOT", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "empty-home"))

    code = _resolver.main(argv=["--project-root", str(project)])

    captured = capsys.readouterr()
    assert code != 0
    assert captured.out == ""
    assert "livespec core is not installed" in captured.err
