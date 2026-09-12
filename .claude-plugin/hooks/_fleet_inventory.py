#!/usr/bin/env python3
"""
Fleet host-set resolution for `fleet_host_guard`: read the inventory, never hardcode.

The guard's question "is this a fleet-managed host?" has one authoritative
answer — the Ansible inventory under `livespec-dev-tooling/ansible/inventory/`,
which is the committed provisioning model the discipline says to read before
any host action. So the host set is READ, in this order:

1. the governed project's own `ansible/inventory/` (a project that carries a
   provisioning tree is its own authority);
2. a sibling `livespec-dev-tooling` clone's inventory, resolved as a PEER of
   the governed project — the fleet keeps its first-class clones side by side
   under one parent (`/data/projects/<repo>`), so the provisioning repository
   sits next to whichever governed repository the session is in. A session in
   a linked worktree (`~/.worktrees/<repo>/<branch>`) has no such peer, so its
   PRIMARY checkout is read off the worktree's `.git` file (`gitdir:
   <primary>/.git/worktrees/<name>`) and the peer is looked up beside that;
3. the documented fallback: the four pre-Talos Ubuntu machines the legacy
   inventory carried on 2026-09-12. It exists so the guard still holds on a
   host with no inventory in reach; it is NOT the source of truth, and a host
   added to the inventory is guarded without a code change.

Every host name AND every `ansible_host` alias is collected — from the
inventory files and from `host_vars/<host>.yml`, where a host's Tailscale
address usually lives — so `ssh <alias>` is judged the same as `ssh <name>`.
The parse is a deliberately small reading of the inventory's indentation
structure — the standard library has no YAML parser, and an inventory is the
one shape the Ansible docs fix: a `hosts:` key, one key per host beneath it
(block or `{inline: {}}` form), each optionally carrying `ansible_host`.
Comments are stripped as YAML strips them (a `#` at a word start); quotes on
keys and values are dropped. Anything else is ignored rather than modelled.
An unreadable file is skipped; a file with no hosts falls through to the next
source.

The source that answered travels with the set so telemetry can say how often
the fallback is in force — a name, never.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is standard library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__: list[str] = ["FALLBACK_HOSTS", "FleetHosts", "resolve_fleet_hosts"]

FALLBACK_HOSTS = frozenset({"vps", "poweredge-xubuntu", "gmktec-xubuntu", "hp-xubuntu"})
_INVENTORY_DIR = Path("ansible") / "inventory"
_SIBLING_REPO = "livespec-dev-tooling"
_COMMENT = re.compile(r"(?:^|\s)#.*$")
_GITDIR_WORKTREE = "/.git/worktrees/"


@dataclass(frozen=True, kw_only=True)
class FleetHosts:
    """The host set in force and where it came from (for telemetry, never a name)."""

    hosts: frozenset[str]
    source: str


def _unquoted(*, text: str) -> str:
    return text.strip().strip("'\"").lower()


def _parse_inventory_hosts(*, text: str) -> set[str]:
    """Host names and `ansible_host` aliases under every `hosts:` key, lower-cased."""
    hosts: set[str] = set()
    hosts_indent = -1
    entry_indent = -1
    for raw in text.splitlines():
        line = _COMMENT.sub("", raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = line.strip().partition(":")
        key = _unquoted(text=key)
        if hosts_indent >= 0 and indent <= hosts_indent:
            hosts_indent = -1
            entry_indent = -1
        if hosts_indent < 0:
            if key == "hosts" and value.strip().startswith("{"):
                hosts.update(_inline_keys(mapping=value))
            elif key == "hosts" and not value.strip():
                hosts_indent = indent
            continue
        if entry_indent < 0:
            entry_indent = indent
        if indent == entry_indent:
            hosts.add(key)
        elif key == "ansible_host" and value.strip():
            hosts.add(_unquoted(text=value))
    return hosts


def _parse_host_vars(*, path: Path, text: str) -> set[str]:
    """`host_vars/<host>.yml`: the file names a host; any `ansible_host:` is its alias."""
    found = {path.stem.lower()}
    for raw in text.splitlines():
        key, _, value = _COMMENT.sub("", raw).strip().partition(":")
        if _unquoted(text=key) == "ansible_host" and value.strip():
            found.add(_unquoted(text=value))
    return found


def _read_or_none(*, path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _inline_keys(*, mapping: str) -> list[str]:
    """The top-level keys of a `{a: {}, b: {x: 1}}` flow mapping, nested keys excluded."""
    keys: list[str] = []
    depth = 0
    current: list[str] = []
    for char in mapping:
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            continue
        if depth != 1:
            continue
        if char == ":":
            keys.append("".join(current))
            current = []
        elif char == ",":
            current = []
        else:
            current.append(char)
    return [_unquoted(text=key) for key in keys if key.strip()]


def _yaml_files(*, directory: Path) -> list[Path]:
    return sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))


def _inventory_hosts(*, inventory_dir: Path) -> frozenset[str]:
    found: set[str] = set()
    for path in _yaml_files(directory=inventory_dir):
        text = _read_or_none(path=path)
        if text is not None:
            found.update(_parse_inventory_hosts(text=text))
    if not found:
        return frozenset()
    for path in _yaml_files(directory=inventory_dir / "host_vars"):
        text = _read_or_none(path=path)
        if text is not None:
            found.update(_parse_host_vars(path=path, text=text))
    return frozenset(found)


def _primary_checkout(*, root: Path) -> Path | None:
    """The primary checkout of a linked worktree, read off its `.git` pointer file."""
    pointer = root / ".git"
    if not pointer.is_file():
        return None
    text = _read_or_none(path=pointer) or ""
    gitdir = text.partition("gitdir:")[2].strip()
    if _GITDIR_WORKTREE not in gitdir:
        return None
    return Path(gitdir.split(_GITDIR_WORKTREE, 1)[0])


def resolve_fleet_hosts(*, project_dir: str | None) -> FleetHosts:
    """The fleet host set: project inventory, else sibling provisioning repo, else fallback."""
    if project_dir:
        root = Path(project_dir)
        primary = _primary_checkout(root=root)
        candidates = [("project-inventory", root / _INVENTORY_DIR)]
        if primary is not None:
            candidates.append(("project-inventory", primary / _INVENTORY_DIR))
            candidates.append(
                ("sibling-inventory", primary.parent / _SIBLING_REPO / _INVENTORY_DIR)
            )
        candidates.append(("sibling-inventory", root.parent / _SIBLING_REPO / _INVENTORY_DIR))
        for source, inventory_dir in candidates:
            hosts = _inventory_hosts(inventory_dir=inventory_dir)
            if hosts:
                return FleetHosts(hosts=hosts, source=source)
    return FleetHosts(hosts=FALLBACK_HOSTS, source="fallback")
