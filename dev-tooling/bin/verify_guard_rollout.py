#!/usr/bin/env python3
"""Verify the shipped GitHub rate-limit guard is IN FORCE in every governed repo.

"Merged to master" is not "in force". The Driver plugin reaches a governed repo
only through a release plus that repo's `ensure-plugins` picking up the new
cache ref, so a hook fix stops the bleeding nowhere until the rollout is
confirmed per repo.

The confirmation is POSITIVE, never inferred. Per livespec
`SPECIFICATION/contracts.md` section "Install verification", a command's exit
status MUST NOT be read as proof of a correct install state -- and
`livespec_dev_tooling.fleet.ensure_plugins` states the same rule from the other
side: "a zero exit from a scoped plugin command does not establish which
project's record it touched, so provisioning is confirmed against the record
itself". So this verifier never asks whether `claude plugin update` succeeded.
It reads `~/.claude/plugins/installed_plugins.json` -- the install RECORD --
takes each record's own `installPath`, and replays the committed regression
corpus through the hook body that path actually carries. A project is IN FORCE
only when every corpus vector returns its recorded verdict from THAT body.

Reading the body is not enough either: a body can be present and still be the
pre-fix build, or a later build with the decision logic switched off. Replaying
the corpus settles both, because the corpus carries the true positives as
controls alongside the false-positive vectors.

Fail-closed on absence. A plugin with no install record, an unreadable record,
or an `installPath` carrying no hook body all report as NOT in force. Absence of
evidence is not evidence that the fix is in force, and this verifier exists
precisely because the cheap inference was wrong.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

__all__: list[str] = [
    "HookRunner",
    "ProjectVerdict",
    "ReplayVector",
    "exit_status",
    "main",
    "subprocess_hook_runner",
    "verify_rollout",
]

_LOGGER = logging.getLogger(__name__)

# The path the guard occupies INSIDE an installed plugin cache. A cache
# directory is the `.claude-plugin/` content itself -- it is the directory an
# install record's `installPath` names and the one carrying `plugin.json` --
# so the bundle's `.claude-plugin/hooks/<name>` is `hooks/<name>` here.
_HOOK_RELPATH = "hooks/github_rate_limit_guard.py"

_DEFAULT_PLUGIN = "livespec@livespec-driver-claude"
_DEFAULT_RECORD = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
_DEFAULT_CORPUS = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "hooks"
    / "fixtures"
    / "github_rate_limit_guard_replay_corpus.json"
)

# The hook's deny contract: exit 2 denies the tool call, every other status
# allows it. Reading the verdict off the boundary rather than off the decision
# function is deliberate -- a deny that never reaches exit 2 is not a deny.
_DENY_STATUS = 2


class HookRunner(Protocol):
    """Callable seam replaying one command through one installed hook body."""

    def __call__(self, *, hook_path: Path, command: str) -> int: ...


@dataclass(frozen=True, kw_only=True)
class ReplayVector:
    """One corpus command paired with the verdict a fixed body must return."""

    identifier: str
    command: str
    expected_verdict: str


@dataclass(frozen=True, kw_only=True)
class ProjectVerdict:
    """What one governed project's install record proved about the rollout."""

    project_path: str
    install_path: str
    vectors: int
    disagreements: tuple[str, ...]

    @property
    def in_force(self) -> bool:
        """True only when a body was found AND every vector agreed with it."""
        return self.vectors > 0 and not self.disagreements


def _mapping(*, value: object) -> dict[str, object]:
    """`value` as a mapping, or an empty one when it is not an object."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _text(*, mapping: dict[str, object], key: str) -> str:
    """A string field of `mapping`, or the empty string when it is absent."""
    value = mapping.get(key)
    return value if isinstance(value, str) else ""


def _install_records(*, registry_text: str, plugin: str) -> tuple[dict[str, object], ...]:
    """Every install record the registry holds for one plugin key.

    An unreadable registry yields no records rather than an error: the caller
    reports "nothing verified", which is already a failure, and a malformed
    registry must not read as a rollout that succeeded.
    """
    try:
        parsed = json.loads(registry_text)
    except json.JSONDecodeError:
        return ()
    entries = _mapping(value=_mapping(value=parsed).get("plugins")).get(plugin)
    if not isinstance(entries, list):
        return ()
    return tuple(
        cast("dict[str, object]", entry)
        for entry in cast("list[object]", entries)
        if isinstance(entry, dict)
    )


def _replay_vectors(*, corpus_text: str) -> tuple[ReplayVector, ...]:
    """The committed corpus as replay vectors."""
    raw = _mapping(value=json.loads(corpus_text)).get("vectors")
    entries = cast("list[object]", raw) if isinstance(raw, list) else []
    return tuple(
        ReplayVector(
            identifier=_text(mapping=vector, key="id"),
            command=_text(mapping=vector, key="command"),
            expected_verdict=_text(mapping=vector, key="expected_verdict"),
        )
        for vector in (_mapping(value=entry) for entry in entries)
    )


def _observed_verdict(*, status: int) -> str:
    """The verdict an installed hook body reported, named from its exit status."""
    return "deny" if status == _DENY_STATUS else "allow"


def _project_verdict(
    *,
    record: dict[str, object],
    vectors: tuple[ReplayVector, ...],
    run_hook: HookRunner,
) -> ProjectVerdict:
    """Replay every vector through the body one install record names."""
    project_path = _text(mapping=record, key="projectPath")
    install_path = _text(mapping=record, key="installPath")
    hook_path = Path(install_path) / _HOOK_RELPATH if install_path else None
    if hook_path is None or not hook_path.is_file():
        return ProjectVerdict(
            project_path=project_path,
            install_path=install_path,
            vectors=0,
            disagreements=(f"installPath {install_path!r} carries no hook body {_HOOK_RELPATH}",),
        )
    disagreements: list[str] = []
    for vector in vectors:
        observed = _observed_verdict(status=run_hook(hook_path=hook_path, command=vector.command))
        if observed != vector.expected_verdict:
            disagreements.append(
                f"{vector.identifier}: expected {vector.expected_verdict}, "
                f"installed body returned {observed}"
            )
    return ProjectVerdict(
        project_path=project_path,
        install_path=install_path,
        vectors=len(vectors),
        disagreements=tuple(disagreements),
    )


def verify_rollout(
    *,
    registry_text: str,
    corpus_text: str,
    plugin: str,
    run_hook: HookRunner,
) -> tuple[ProjectVerdict, ...]:
    """One verdict per install record the registry holds for `plugin`.

    An empty result means NOTHING was verified, which `exit_status` reports as
    a failure. It is never a pass: a project with no record is a project the
    fix has not reached.
    """
    vectors = _replay_vectors(corpus_text=corpus_text)
    return tuple(
        _project_verdict(record=record, vectors=vectors, run_hook=run_hook)
        for record in _install_records(registry_text=registry_text, plugin=plugin)
    )


def exit_status(*, verdicts: tuple[ProjectVerdict, ...]) -> int:
    """0 only when at least one project was verified and every one is in force."""
    if not verdicts:
        return 1
    return 0 if all(verdict.in_force for verdict in verdicts) else 1


def subprocess_hook_runner(*, hook_path: Path, command: str) -> int:
    """Run one command through an installed hook body over its real boundary.

    The hook protocol is hook-input JSON on stdin and the decision in the exit
    status, so the installed body is exercised exactly as Claude Code exercises
    it rather than through an import that could bypass its `main()`. The
    interpreter is the bare system `python3` the bundle's `hooks.json` names,
    not this process's interpreter: an installed body that only runs under a
    virtualenv is not in force in a governed repo either.
    """
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    completed = subprocess.run(
        ["python3", str(hook_path)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode


def _parse_args(*, argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-record", default=str(_DEFAULT_RECORD))
    parser.add_argument("--corpus", default=str(_DEFAULT_CORPUS))
    parser.add_argument("--plugin", default=_DEFAULT_PLUGIN)
    return parser.parse_args(list(argv))


def _report(*, verdicts: tuple[ProjectVerdict, ...]) -> None:
    for verdict in verdicts:
        _LOGGER.info(
            json.dumps(
                {
                    "check_id": "github-rate-limit-guard-rollout",
                    "projectPath": verdict.project_path,
                    "installPath": verdict.install_path,
                    "vectors": verdict.vectors,
                    "in_force": verdict.in_force,
                    "disagreements": list(verdict.disagreements),
                },
                sort_keys=True,
            )
        )


def main() -> int:
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    args = _parse_args(argv=tuple(sys.argv[1:]))
    record_path = Path(str(args.install_record))
    if not record_path.is_file():
        _LOGGER.error("install record %s is not readable; nothing verified", record_path)
        return 1
    verdicts = verify_rollout(
        registry_text=record_path.read_text(encoding="utf-8"),
        corpus_text=Path(str(args.corpus)).read_text(encoding="utf-8"),
        plugin=str(args.plugin),
        run_hook=subprocess_hook_runner,
    )
    _report(verdicts=verdicts)
    if not verdicts:
        _LOGGER.error("%s has no install record in %s; nothing verified", args.plugin, record_path)
    return exit_status(verdicts=verdicts)


if __name__ == "__main__":
    raise SystemExit(main())
