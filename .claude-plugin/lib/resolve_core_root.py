#!/usr/bin/env python3
"""resolve_core_root - the single realization of the Driver's core-root resolution.

Every binding calls this script instead of restating the ordered algorithm.
Eight independently-maintained copies of a resolution rule are kept in
agreement only by copying, and that is exactly how one positional defect came
to live in all eight bindings at once.

Self-contained by contract: the Claude Code plugin installer copies ONLY
`.claude-plugin/` into the install cache (flattened to the plugin root) and
ships no `pyproject.toml`, no `uv.lock` and no virtualenv, so this file runs
under bare system `python3` with no third-party package importable. Every
import here is the standard library. The vendored `returns` railway at the
repo root is NOT reachable from the install cache, so the outcome travels as
the purpose-built discriminated union below rather than a Result container --
a module-scope third-party import would kill the process before any handler
could report anything.

The union exists because the ways resolution can fail are NOT interchangeable,
and collapsing them is the defect this module was written to remove:

- an ABSENT registry proves core is installed for no project, so the install
  instructions are the whole remedy;
- a registry that could not be READ proves nothing whatever, so telling the
  operator to install core would be an articulate wrong answer about a host
  where core may well be present;
- a registry holding records for OTHER projects but none for this one is
  neither. It is a defective provisioning state that must be named as such,
  and reporting it as plugin STALENESS sends the operator into a loop: the
  update command rewrites the record for this project, which a positional
  reader then still would not be reading.

Selection is BY `projectPath`, never by position. The plugin key holds an
ARRAY of install records, one per project that has installed the plugin;
taking the first resolves whichever project on the host installed core
earliest, which bears no relation to the project the binding runs in.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn, TypeAlias, cast

import _resolve_core_root_text as _text

__all__: list[str] = [
    "CoreRootOutcome",
    "CoreRootResolved",
    "CoreRootUnresolved",
    "main",
    "resolve_core_root",
]

_OVERRIDE_ENV = "LIVESPEC_CORE_PLUGIN_ROOT"
_PLUGIN_KEY = "livespec@livespec"
_REGISTRY_PARTS = (".claude", "plugins", "installed_plugins.json")


def assert_never(*, value: NoReturn) -> NoReturn:
    """Stdlib-only stand-in for `typing.assert_never`, which lands in 3.11.

    Defined here rather than imported for the same reason nothing else in this
    file is imported: `typing_extensions` is third-party and absent from the
    install cache, and the bundle must run under whatever bare `python3` the
    operator has -- which is NOT guaranteed to be 3.11+. Assuming a runtime
    version this file never verified is the same class of unchecked
    environment assumption that broke this fleet's release fan-out.

    Passing an exhausted union here is a type error exactly as with the real
    one: the parameter is `NoReturn`, so any inhabited type is rejected.
    """
    raise AssertionError(f"unhandled variant: {value!r}")  # pragma: no cover


UnresolvedKind: TypeAlias = Literal[
    "registry_absent",
    "registry_unreadable",
    "registry_malformed",
    "plugin_absent",
    "project_not_installed",
    "record_malformed",
]

ResolvedSource: TypeAlias = Literal["override", "project_checkout", "install_record"]


@dataclass(frozen=True)
class CoreRootResolved:
    """A usable core root, and which ordered step produced it."""

    path: Path
    source: ResolvedSource


@dataclass(frozen=True)
class CoreRootUnresolved:
    """Why the core root could not be resolved. `kind` is the discriminator."""

    kind: UnresolvedKind
    detail: str


CoreRootOutcome: TypeAlias = CoreRootResolved | CoreRootUnresolved


@dataclass(frozen=True)
class _PluginRecords:
    """The install records listed under the plugin key, unvalidated."""

    records: tuple[object, ...]


@dataclass(frozen=True)
class _NoRecords:
    """The registry yielded no record list, and why."""

    unresolved: CoreRootUnresolved


_RegistryRead: TypeAlias = _PluginRecords | _NoRecords


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    """Narrow an arbitrary JSON value to a string-keyed dict, else None."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _normalized(*, path: Path) -> Path:
    """A comparable spelling of `path` that never raises on a missing target."""
    return Path(os.path.realpath(path.expanduser()))


def _read_registry(*, registry_path: Path) -> _RegistryRead:
    """Read the plugin registry.

    The `FileNotFoundError` arm MUST come first: it IS an `OSError`, so
    catching the parent alone would sweep ABSENCE -- which definitively means
    core is installed for no project -- onto the says-nothing track, and the
    diagnostic would stop being able to recommend an install.
    """
    try:
        raw = registry_path.read_bytes()
    except FileNotFoundError:
        return _NoRecords(
            unresolved=CoreRootUnresolved(
                kind="registry_absent",
                detail=f"no plugin registry at {registry_path}",
            )
        )
    except OSError as unreadable:
        return _NoRecords(
            unresolved=CoreRootUnresolved(
                kind="registry_unreadable",
                detail=f"could not read {registry_path}: {unreadable}",
            )
        )
    return _records_from(raw=raw, registry_path=registry_path)


def _records_from(*, raw: bytes, registry_path: Path) -> _RegistryRead:
    """Parse registry bytes we HAVE. A parse failure here is DEFINITIVE."""
    try:
        parsed = cast("object", json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, ValueError) as invalid:
        return _NoRecords(
            unresolved=CoreRootUnresolved(
                kind="registry_malformed",
                detail=f"{registry_path} is not valid UTF-8 JSON: {invalid}",
            )
        )
    registry = _as_object_dict(value=parsed)
    if registry is None:
        return _NoRecords(
            unresolved=CoreRootUnresolved(
                kind="registry_malformed",
                detail=f"{registry_path} does not hold a JSON object at the top level",
            )
        )
    plugins = _as_object_dict(value=registry.get("plugins"))
    if plugins is None:
        return _NoRecords(
            unresolved=CoreRootUnresolved(
                kind="registry_malformed",
                detail=f"{registry_path} carries no 'plugins' object",
            )
        )
    if _PLUGIN_KEY not in plugins:
        return _NoRecords(
            unresolved=CoreRootUnresolved(
                kind="plugin_absent",
                detail=f"{registry_path} lists no '{_PLUGIN_KEY}' install",
            )
        )
    records = plugins[_PLUGIN_KEY]
    if not isinstance(records, list):
        return _NoRecords(
            unresolved=CoreRootUnresolved(
                kind="registry_malformed",
                detail=f"'{_PLUGIN_KEY}' in {registry_path} is not an array of install records",
            )
        )
    return _PluginRecords(records=tuple(cast("list[object]", records)))


def _record_for(*, records: tuple[object, ...], project_root: Path) -> CoreRootOutcome:
    """Select the record whose `projectPath` IS the project root -- never by position."""
    wanted = _normalized(path=project_root)
    installed_for: list[str] = []
    for record in records:
        entry = _as_object_dict(value=record)
        if entry is None:
            continue
        project_path = entry.get("projectPath")
        if not isinstance(project_path, str):
            continue
        installed_for.append(project_path)
        if _normalized(path=Path(project_path)) == wanted:
            return _resolved_from(entry=entry, project_root=project_root)
    return CoreRootUnresolved(
        kind="project_not_installed",
        detail=_text.mismatch_detail(project_root=project_root, installed_for=installed_for),
    )


def _resolved_from(*, entry: dict[str, object], project_root: Path) -> CoreRootOutcome:
    install_path = entry.get("installPath")
    if not isinstance(install_path, str) or not install_path:
        return CoreRootUnresolved(
            kind="record_malformed",
            detail=(
                f"the '{_PLUGIN_KEY}' install record for {project_root} "
                "carries no usable installPath"
            ),
        )
    return CoreRootResolved(path=Path(install_path), source="install_record")


def resolve_core_root(
    *, project_root: Path, home: Path, environ: Mapping[str, str]
) -> CoreRootOutcome:
    """Resolve the core root by the ordered algorithm: override, checkout, install record."""
    override = environ.get(_OVERRIDE_ENV, "")
    if override:
        return CoreRootResolved(path=Path(override), source="override")
    checkout = project_root / ".claude-plugin"
    if (checkout / "prose").is_dir():
        return CoreRootResolved(path=checkout, source="project_checkout")
    registry_path = home.joinpath(*_REGISTRY_PARTS)
    read = _read_registry(registry_path=registry_path)
    match read:
        case _NoRecords():
            return read.unresolved
        case _PluginRecords():
            return _record_for(records=read.records, project_root=project_root)
        case _:
            assert_never(value=read)


def _diagnostic(*, unresolved: CoreRootUnresolved) -> str:
    """The operator-facing text. Only DEFINITIVE absence recommends an install."""
    match unresolved.kind:
        case "registry_absent" | "plugin_absent":
            return (
                f"livespec core is not installed ({unresolved.detail}). Install it:\n"
                + _text.INSTALL_INSTRUCTIONS
            )
        case "registry_unreadable":
            return (
                f"livespec core could not be resolved: {unresolved.detail}\n"
                "This does NOT establish that core is missing -- the plugin registry "
                "could not be read, so nothing is known about what is installed. "
                "Fix the read failure and retry; do not reinstall on this evidence.\n"
            )
        case "registry_malformed":
            return (
                f"livespec core could not be resolved: {unresolved.detail}\n"
                "The plugin registry is present but structurally invalid, so what is "
                "installed cannot be determined from it.\n"
            )
        case "project_not_installed":
            return unresolved.detail
        case "record_malformed":
            return (
                f"livespec core could not be resolved: {unresolved.detail}\n"
                "The install record for this project exists but is unusable.\n"
            )
        case _:
            assert_never(value=unresolved.kind)


def _parse_args(*, argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="resolve_core_root")
    _ = parser.add_argument("--project-root", default=".")
    return parser.parse_args(argv)


def main(*, argv: Sequence[str] | None = None) -> int:
    """Print the resolved core root, or a kind-specific diagnostic on stderr."""
    args = _parse_args(argv=argv)
    project_root = Path(cast("str", args.project_root))
    outcome = resolve_core_root(project_root=project_root, home=Path.home(), environ=os.environ)
    match outcome:
        case CoreRootResolved():
            _ = sys.stdout.write(f"{outcome.path}\n")
            return 0
        case CoreRootUnresolved():
            _ = sys.stderr.write(_diagnostic(unresolved=outcome))
            return 1
        case _:
            assert_never(value=outcome)


if __name__ == "__main__":
    raise SystemExit(main())
