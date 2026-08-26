"""Tests for the rate-limit-guard rollout verifier.

The verifier answers the question `dd3b301` and `c0814ac` do NOT answer on
their own: is the fixed hook body actually IN FORCE in a governed repo? These
tests pin the two properties that make its answer trustworthy -- the verdict is
read from the install RECORD's own `installPath`, and absence of evidence is
reported as STALE rather than passed over.
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "dev-tooling" / "bin" / "verify_guard_rollout.py"
_SHIPPED_HOOKS = _REPO_ROOT / ".claude-plugin" / "hooks"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_CORPUS_PATH = _FIXTURES / "github_rate_limit_guard_replay_corpus.json"
_PLUGIN = "livespec@livespec-driver-claude"


def _load_verifier() -> ModuleType:
    """Import the verifier by path, asserting it exists before importing it."""
    assert _MODULE_PATH.is_file(), f"{_MODULE_PATH} is not a file"
    directory = str(_MODULE_PATH.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    return importlib.import_module("verify_guard_rollout")


def _corpus_text() -> str:
    return _CORPUS_PATH.read_text(encoding="utf-8")


def _registry_text(*, records: list[dict[str, str]], plugin: str = _PLUGIN) -> str:
    return json.dumps({"version": 2, "plugins": {plugin: records}})


def _expected_verdicts() -> dict[str, str]:
    """Each corpus command mapped to the verdict a fixed body must return."""
    corpus = json.loads(_corpus_text())
    return {vector["command"]: vector["expected_verdict"] for vector in corpus["vectors"]}


def _fixed_runner(*, hook_path: Path, command: str) -> int:  # noqa: ARG001
    """A stand-in for a cache carrying the fixed body: every vector agrees."""
    return 2 if _expected_verdicts()[command] == "deny" else 0


def _allow_everything_runner(*, hook_path: Path, command: str) -> int:  # noqa: ARG001
    """A stand-in for a guard switched off rather than fixed."""
    return 0


def _install_cache(*, root: Path) -> Path:
    """A plugin cache directory carrying this checkout's shipped hook bundle."""
    cache = root / "cache" / "livespec-driver-claude" / "livespec" / "9bf53bc550dc"
    shutil.copytree(_SHIPPED_HOOKS, cache / "hooks")
    (cache / "plugin.json").write_text('{"name": "livespec"}', encoding="utf-8")
    return cache


def test_in_force_when_the_installed_body_returns_every_recorded_verdict(tmp_path: Path) -> None:
    verifier = _load_verifier()
    cache = tmp_path / "cache"
    (cache / "hooks").mkdir(parents=True)
    (cache / "hooks" / "github_rate_limit_guard.py").write_text("", encoding="utf-8")
    verdicts = verifier.verify_rollout(
        registry_text=_registry_text(
            records=[{"projectPath": "/data/projects/livespec", "installPath": str(cache)}]
        ),
        corpus_text=_corpus_text(),
        plugin=_PLUGIN,
        run_hook=_fixed_runner,
    )
    assert [verdict.project_path for verdict in verdicts] == ["/data/projects/livespec"]
    assert verdicts[0].in_force is True
    assert verdicts[0].disagreements == ()
    assert verdicts[0].vectors == len(_expected_verdicts())


def test_a_switched_off_body_is_stale_not_in_force(tmp_path: Path) -> None:
    """A cache that allows everything must fail: the true positives are the control."""
    verifier = _load_verifier()
    cache = tmp_path / "cache"
    (cache / "hooks").mkdir(parents=True)
    (cache / "hooks" / "github_rate_limit_guard.py").write_text("", encoding="utf-8")
    verdicts = verifier.verify_rollout(
        registry_text=_registry_text(
            records=[{"projectPath": "/data/projects/livespec", "installPath": str(cache)}]
        ),
        corpus_text=_corpus_text(),
        plugin=_PLUGIN,
        run_hook=_allow_everything_runner,
    )
    assert verdicts[0].in_force is False
    assert verdicts[0].disagreements


def test_an_install_path_carrying_no_hook_body_is_stale(tmp_path: Path) -> None:
    verifier = _load_verifier()
    verdicts = verifier.verify_rollout(
        registry_text=_registry_text(
            records=[{"projectPath": "/data/projects/livespec", "installPath": str(tmp_path)}]
        ),
        corpus_text=_corpus_text(),
        plugin=_PLUGIN,
        run_hook=_fixed_runner,
    )
    assert verdicts[0].in_force is False
    assert any("no hook body" in finding for finding in verdicts[0].disagreements)


def test_every_recorded_project_is_verified_separately(tmp_path: Path) -> None:
    """One stale project must not be masked by a sibling that is in force."""
    verifier = _load_verifier()
    fresh = tmp_path / "fresh"
    (fresh / "hooks").mkdir(parents=True)
    (fresh / "hooks" / "github_rate_limit_guard.py").write_text("", encoding="utf-8")
    verdicts = verifier.verify_rollout(
        registry_text=_registry_text(
            records=[
                {"projectPath": "/data/projects/livespec", "installPath": str(fresh)},
                {"projectPath": "/data/projects/livespec-overseer", "installPath": str(tmp_path)},
            ]
        ),
        corpus_text=_corpus_text(),
        plugin=_PLUGIN,
        run_hook=_fixed_runner,
    )
    assert [verdict.in_force for verdict in verdicts] == [True, False]


@pytest.mark.parametrize(
    "registry_text",
    [
        pytest.param('{"version": 2, "plugins": {}}', id="no-records-at-all"),
        pytest.param(
            json.dumps({"version": 2, "plugins": {"livespec@livespec": []}}),
            id="records-for-another-plugin-only",
        ),
        pytest.param("not json", id="unreadable-record"),
    ],
)
def test_absence_of_an_install_record_yields_no_verdict(registry_text: str) -> None:
    """Absence of evidence is not evidence the fix is in force."""
    verifier = _load_verifier()
    assert (
        verifier.verify_rollout(
            registry_text=registry_text,
            corpus_text=_corpus_text(),
            plugin=_PLUGIN,
            run_hook=_fixed_runner,
        )
        == ()
    )


def test_exit_status_is_non_zero_when_nothing_was_verified() -> None:
    """No record means UNVERIFIED, and unverified must never read as rolled out."""
    verifier = _load_verifier()
    assert verifier.exit_status(verdicts=()) == 1


def test_exit_status_is_zero_only_when_every_project_is_in_force() -> None:
    verifier = _load_verifier()
    in_force = verifier.ProjectVerdict(
        project_path="/data/projects/livespec",
        install_path="/cache/a",
        vectors=14,
        disagreements=(),
    )
    stale = verifier.ProjectVerdict(
        project_path="/data/projects/livespec-overseer",
        install_path="/cache/b",
        vectors=14,
        disagreements=("b1-cached-loop: expected allow, installed body returned deny",),
    )
    assert in_force.in_force is True
    assert stale.in_force is False
    assert verifier.exit_status(verdicts=(in_force,)) == 0
    assert verifier.exit_status(verdicts=(in_force, stale)) == 1


@pytest.mark.integration
def test_a_cache_carrying_this_checkouts_bundle_reports_in_force(tmp_path: Path) -> None:
    """End to end over the REAL hook boundary, not a stand-in runner.

    The shipped bundle is copied into a plugin-cache shape, named by a
    synthetic install record, and every corpus vector is replayed through
    `python3 <installPath>/hooks/github_rate_limit_guard.py`. This is the
    check an operator runs against a live host, with the cache substituted.
    """
    verifier = _load_verifier()
    cache = _install_cache(root=tmp_path)
    verdicts = verifier.verify_rollout(
        registry_text=_registry_text(
            records=[{"projectPath": str(_REPO_ROOT), "installPath": str(cache)}]
        ),
        corpus_text=_corpus_text(),
        plugin=_PLUGIN,
        run_hook=verifier.subprocess_hook_runner,
    )
    assert verdicts[0].disagreements == ()
    assert verdicts[0].in_force is True
    assert verifier.exit_status(verdicts=verdicts) == 0
