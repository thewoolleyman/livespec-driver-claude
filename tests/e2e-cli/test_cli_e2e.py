"""Consumer wiring for the canonical CLI end-to-end harness.

Per livespec/SPECIFICATION/contracts.md, the harness itself is the
single canonical implementation
that ships from `livespec-dev-tooling`
(`livespec_dev_tooling.testing.cli_e2e`); this Driver repo is a
CONSUMER. The consumer obligation relocated here from livespec core
together with the `/livespec:*` skill bindings (W4 Driver
extraction): structural skill discovery walks THIS repo's
`.claude-plugin/skills/*/SKILL.md` and reads the slash prefix from
`plugin.json`'s `name` — the in-repo plugin directory IS the source
of truth.

What runs in the `mock` tier (LIVESPEC_E2E_HARNESS=mock, in
`just check`):

- REAL structural skill discovery against `.claude-plugin/`;
- REAL per-skill fixture loading from `tests/e2e-cli/fixtures/<skill>/`;
- the REAL fail-closed time-bomb coverage gate;
- only the `claude -p` subprocess is mocked, via an injected
  deterministic runner that materializes each fixture's
  `expected_files`.

The `real` tier (LIVESPEC_E2E_HARNESS=real, NOT in `just check`)
drives the actual `claude` binary against the live API.

The red-baseline test at the bottom proves the coverage gate fails
CLOSED when a discovered skill lacks a fixture, then the happy-path
test proves it passes once every discovered skill is fixtured.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from livespec_dev_tooling.testing import cli_e2e
from livespec_dev_tooling.testing.cli_e2e import (
    CliResult,
    CoverageGateError,
    FixturedSkill,
    HarnessConfig,
)

_VENDOR_DIR = Path(cli_e2e.__file__).resolve().parent.parent / "_vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from returns.io import IOFailure, IOSuccess  # noqa: E402  — vendor-path-aware import.
from returns.primitives.exceptions import (  # noqa: E402  — vendor-path-aware import.
    UnwrapFailedError,
)
from returns.result import Failure, Success  # noqa: E402  — vendor-path-aware import.

__all__: list[str] = []


# The canonical entry point is named `test_workflow_full_round_trip` (fixed
# by the contract's consumer import path). Importing that bare `test_*` name
# into a pytest module would make pytest try to COLLECT it as a test with a
# missing `config` fixture — so we alias it under a non-`test_`-prefixed
# name here and call it from our own thin wrapper test.
_run_full_round_trip = cli_e2e.test_workflow_full_round_trip


def _round_trip_result(outcome: object) -> cli_e2e.WorkflowResult:
    """Normalize BOTH harness return shapes so the dev-tooling pin can move either way.

    Through `v1.0.x`, `test_workflow_full_round_trip` RAISED `WorkflowFailedError`
    on a failing step and returned a bare `WorkflowResult`. After the ROP
    conversion in dev-tooling it returns a `Result[WorkflowResult, ...]` instead.

    *** THE FAILURE THIS EXISTS TO PREVENT IS SILENT. *** A `Failure` is TRUTHY and
    carries no `.passed`, so a wrapper written for the old shape does NOT blow up
    against the new one — it simply STOPS CHECKING, and this suite goes GREEN on a
    broken round trip. That is `livespec-dev-tooling-dx8l`'s failure mode aimed at
    a test gate: the guard does not fail, it stops being a guard.

    Accepting BOTH shapes satisfies "consumer wiring lands before the change that
    assumes it" for EVERY pin version at once, so the pin can move in either
    direction — forward to the conversion or back on a revert — without re-breaking.

    Duck-typed on purpose: the helper must not depend on dev-tooling's vendored
    `returns` layout at call time, since it has to work across pin versions on
    both sides of the conversion. The tests below pin the REAL `Success`/`Failure`
    shapes, so the tolerance is proven rather than assumed.
    """
    if isinstance(outcome, cli_e2e.WorkflowResult):
        return outcome  # pre-conversion shape; a failing step would already have raised
    unwrap = getattr(outcome, "unwrap", None)
    assert unwrap is not None, (
        f"unexpected harness return shape {type(outcome).__name__}; "
        "expected a WorkflowResult or a returns Result"
    )
    # `.unwrap()` RAISES on a Failure, so a failed round trip fails this test LOUDLY
    # rather than passing silently. Asserting on the unwrapped VALUE is the point:
    # proving the call succeeded is exactly what the silent-pass bug also does.
    unwrapped = unwrap()
    assert isinstance(
        unwrapped, cli_e2e.WorkflowResult
    ), f"harness Result carried {type(unwrapped).__name__}, not a WorkflowResult"
    return unwrapped


# The repo root is three levels up from this file:
# <root>/tests/e2e-cli/test_cli_e2e.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PLUGIN_SOURCE = _REPO_ROOT / ".claude-plugin"
_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"

# The known impl plugin(s) the harness is parametrized over. The Driver
# has ZERO dependencies on any orchestrator; the id is carried through
# `HarnessConfig.impl_plugin_id` so the parameter is exercised
# end-to-end even though no impl-side skill set is discovered in this
# repo's run.
_KNOWN_IMPL_PLUGINS: tuple[str, ...] = ("livespec-orchestrator-beads-fabro",)


class _FakeCliRunner:
    """Deterministic `claude -p` seam — the one mocked boundary.

    Records every turn and, per a per-prompt recipe, materializes the files
    a real `claude -p` run of that skill's slash command would create.
    Discovery, fixture loading, the coverage gate, and orchestration all run
    for real against the on-disk fixtures tree; only this subprocess seam is
    canned (per the harness's injected-runner design).
    """

    def __init__(self, *, creates: dict[str, tuple[str, ...]]) -> None:
        self._creates = creates
        self.turns: list[dict[str, object]] = []

    def run(
        self,
        *,
        prompt: str,
        home: Path,
        cwd: Path,
        resume_session_id: str | None,
    ) -> CliResult:
        self.turns.append(
            {
                "prompt": prompt,
                "home": str(home),
                "cwd": str(cwd),
                "resume": resume_session_id,
            }
        )
        for rel in self._creates.get(prompt, ()):
            target = cwd / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = target.write_text("created by fake claude\n", encoding="utf-8")
        return CliResult(exit_code=0, stdout="", stderr="", session_id=None)


def _harness_config(*, impl_plugin_id: str, fixtures_root: Path) -> HarnessConfig:
    """Build a HarnessConfig pointing discovery at the in-repo plugin source."""
    return HarnessConfig(
        impl_plugin_id=impl_plugin_id,
        marketplace="thewoolleyman/livespec-driver-claude",
        enabled_plugins=(
            "livespec@livespec-driver-claude",
            f"{impl_plugin_id}@{impl_plugin_id}",
        ),
        plugin_install_dirs=(_PLUGIN_SOURCE,),
        fixtures_root=fixtures_root,
        install_command="/plugin install livespec@livespec-driver-claude",
    )


def _returning(*, shape: object) -> Callable[..., object]:
    """A `discover_fixtures` stand-in handing back exactly `shape`."""

    def _call(**_kwargs: object) -> object:
        return shape

    return _call


def _discovered_fixtures(*, fixtures_root: Path) -> dict[str, FixturedSkill]:
    """The harness's fixtures, from EITHER shape of `discover_fixtures`.

    CONSUMER WIRING LANDS BEFORE THE PIN THAT NEEDS IT (livespec
    `.ai/ci-gate-discipline.md` step 3, and `livespec-dev-tooling-dx8l`). Up to
    dev-tooling v1.13.15 `discover_fixtures` returns a bare
    `dict[str, FixturedSkill]`; the `livespec-dev-tooling-8o8e` railway
    conversion returns a `returns` container over that dict, because today an
    unreadable `prompt.md` raises straight out of it and an unreadable fixtures
    root yields `{}` — "no fixtures" — which the fail-closed coverage gate then
    passes VACUOUSLY. Accepting both shapes is what lets that pin move in
    EITHER direction, a revert included, without reddening this repo's master.

    ⛔ WHY `.map()` AND NOT `.unwrap()`, because the sibling `_round_trip_result`
    helper uses the latter and copying it here is wrong one container deep:
    `.unwrap()` is correct for the `Result` that helper consumes, but
    `IOResult.unwrap()` yields an `IO[dict]`, NOT a dict. That would hand the
    fake runner a container whose `.values()` does not exist; and wiring that
    instead fell back to `{}` would materialize no expected files and pass the
    round trip for the wrong reason. `.map()` is uniform across both containers,
    runs ONLY on the success track, and needs no import of the railway library.

    A failure track FAILS THIS TEST rather than degrading to `{}`: an unreadable
    fixtures tree is exactly the state the coverage gate must not pass through.
    """
    discovered = cli_e2e.discover_fixtures(fixtures_root=fixtures_root)
    if isinstance(discovered, dict):
        return discovered
    unwrapped: list[dict[str, FixturedSkill]] = []
    _ = discovered.map(unwrapped.append)
    assert unwrapped, f"discover_fixtures could not read {fixtures_root}: {discovered!r}"
    return unwrapped[0]


def _expected_files_for(*, fixtures_root: Path) -> dict[str, tuple[str, ...]]:
    """Load each fixture's prompt → its expected_files, for the fake runner.

    Reuses the harness's own fixture loader so the prompt strings the fake
    keys on are byte-identical to what the orchestrator passes through.
    """
    fixtures = _discovered_fixtures(fixtures_root=fixtures_root)
    return {fx.prompt: fx.expected_files for fx in fixtures.values()}


@pytest.mark.parametrize("impl_plugin_id", _KNOWN_IMPL_PLUGINS)
def test_cli_e2e_full_round_trip_mock_tier(*, impl_plugin_id: str, tmp_path: Path) -> None:
    """The imported harness drives every discovered /livespec:* skill.

    Mock tier: real discovery against the in-repo `.claude-plugin/` source,
    real fixture loading, the real fail-closed coverage gate, and a
    deterministic injected runner that materializes each fixture's expected
    files. Asserts the full round-trip passes and that every Driver-bound
    spec-side skill was discovered and fixtured.
    """
    config = _harness_config(impl_plugin_id=impl_plugin_id, fixtures_root=_FIXTURES_ROOT)
    creates = _expected_files_for(fixtures_root=_FIXTURES_ROOT)
    # The install command creates nothing; every skill prompt materializes
    # its fixture's expected files under the tmp project root.
    runner = _FakeCliRunner(creates=creates)
    result = _round_trip_result(
        _run_full_round_trip(
            config=config,
            home=tmp_path / "home",
            project_root=tmp_path / "project",
            injected_runner=runner,
        )
    )
    # Every Driver-bound spec-side skill is discovered and fixtured.
    assert set(result.discovered_skills) == {
        "seed",
        "propose-change",
        "critique",
        "revise",
        "doctor",
        "prune-history",
        "next",
        "help",
    }
    assert set(result.fixtured_skills) == set(result.discovered_skills)
    assert result.passed is True


def test_cli_e2e_coverage_gate_fails_closed_on_missing_fixture(*, tmp_path: Path) -> None:
    """Red baseline: a discovered skill with no fixture trips the gate.

    Proves the time-bomb coverage gate fails CLOSED: when the in-repo
    plugin exposes a skill that has no fixture directory and is not
    exempt, the harness raises `CoverageGateError` BEFORE running any
    skill turn. This is the deliberate red-baseline for the gate — the
    happy-path test above is the green counterpart once every
    discovered skill is fixtured.
    """
    # A plugin exposing one extra skill (`brand-new`) beyond the fixtured
    # set, modelling a freshly-added skill that nobody wrote a fixture for.
    plugin_dir = tmp_path / "plugin"
    skills_dir = plugin_dir / "skills"
    skills_dir.mkdir(parents=True)
    _ = (plugin_dir / "plugin.json").write_text(json.dumps({"name": "livespec"}), encoding="utf-8")
    for skill in ("seed", "brand-new"):
        sd = skills_dir / skill
        sd.mkdir()
        _ = (sd / "SKILL.md").write_text(f"# {skill}\n", encoding="utf-8")
    # Fixtures exist for `seed` only — `brand-new` is uncovered.
    fixtures_root = tmp_path / "fixtures"
    seed_fx = fixtures_root / "seed"
    seed_fx.mkdir(parents=True)
    _ = (seed_fx / "prompt.md").write_text("/livespec:seed\n", encoding="utf-8")

    config = HarnessConfig(
        impl_plugin_id="livespec-orchestrator-beads-fabro",
        marketplace="thewoolleyman/livespec-driver-claude",
        enabled_plugins=("livespec@livespec-driver-claude",),
        plugin_install_dirs=(plugin_dir,),
        fixtures_root=fixtures_root,
    )
    runner = _FakeCliRunner(creates={})
    with pytest.raises(CoverageGateError, match="brand-new"):
        _ = _run_full_round_trip(
            config=config,
            home=tmp_path / "home",
            project_root=tmp_path / "project",
            injected_runner=runner,
        )
    # Fail-closed BEFORE any skill turn ran.
    assert runner.turns == []


def test_round_trip_result_accepts_the_pre_conversion_shape() -> None:
    """A bare `WorkflowResult` passes straight through — the shape today's pin returns."""
    result = cli_e2e.WorkflowResult(discovered_skills=("seed",), fixtured_skills=("seed",))

    assert _round_trip_result(result) is result


def test_round_trip_result_unwraps_the_post_conversion_success_to_its_value() -> None:
    """A `Success` yields the WorkflowResult ITSELF, not the container.

    Asserting on the VALUE is the whole point. `frozenset(IOResult.unwrap())`
    silently yielding a set holding the wrapper — the bug that shipped in
    dev-tooling's own conversion — passes any test that only checks the call
    succeeded. A wrapper reaching the caller in place of its payload is exactly
    what this class of bug produces.
    """
    result = cli_e2e.WorkflowResult(discovered_skills=("seed",), fixtured_skills=("seed",))

    unwrapped = _round_trip_result(Success(result))

    assert unwrapped is result
    assert isinstance(unwrapped, cli_e2e.WorkflowResult)
    assert unwrapped.discovered_skills == ("seed",)


def test_round_trip_result_fails_loudly_on_the_post_conversion_failure() -> None:
    """A `Failure` RAISES rather than passing.

    This is the assertion the whole helper exists for. A `Failure` is TRUTHY and
    has no `.passed`, so wiring written for the old shape would neither raise nor
    check — this suite would go green on a broken round trip.
    """
    with pytest.raises(UnwrapFailedError):
        _ = _round_trip_result(Failure(RuntimeError("two skills failed")))


def _fixture(*, skill: str) -> FixturedSkill:
    return FixturedSkill(skill=skill, prompt=f"drive {skill}", expected_files=())


def test_discovered_fixtures_accepts_every_harness_shape(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dual-shape tolerance, PROVEN against real containers rather than assumed.

    Three shapes, because the pin must be free to move in either direction and
    the conversion's container type is dev-tooling's choice, not this repo's:
    the current bare `dict`, and the success track of both `Result` and
    `IOResult`.

    ⛔ THE `IOSuccess` CASE IS THE LOAD-BEARING ONE. The sibling
    `_round_trip_result` helper normalizes with `.unwrap()`, which is correct
    for the `Result` it consumes — but `IOResult.unwrap()` yields an `IO[dict]`,
    NOT a dict. Reusing that idiom here would hand the fake runner a container
    whose `.values()` does not exist; and wiring that instead fell back to `{}`
    would materialize no expected files and pass the round trip for the wrong
    reason. `.map()` is uniform across both containers, which is why it is used.
    """
    fixtures = {"seed": _fixture(skill="seed")}

    for shape in (fixtures, Success(fixtures), IOSuccess(fixtures)):
        monkeypatch.setattr(cli_e2e, "discover_fixtures", _returning(shape=shape))

        assert (
            _discovered_fixtures(fixtures_root=tmp_path) == fixtures
        ), f"shape {type(shape).__name__} must normalize to the bare mapping"


def test_discovered_fixtures_fails_loudly_on_an_unreadable_tree(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure track must FAIL, never degrade to "no fixtures".

    The positive control, and the half that carries the value. Without it,
    wiring that quietly returned `{}` on the failure track would satisfy every
    assertion above while feeding an EMPTY fixture set to the fail-closed
    coverage gate — which then computes `discovered - fixtured - exempt` over
    nothing and PASSES. That is this epic's exact subject: a gate reporting
    success because the thing it measures never happened.
    """
    for shape in (Failure("unreadable"), IOFailure("unreadable")):
        monkeypatch.setattr(cli_e2e, "discover_fixtures", _returning(shape=shape))

        with pytest.raises(AssertionError):
            _ = _discovered_fixtures(fixtures_root=tmp_path)
