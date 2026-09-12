#!/usr/bin/env python3
"""
Fleet host-set resolution for `fleet_host_guard`: read the inventory, never hardcode.

The guard's question "is this a fleet-managed host?" has one authoritative
answer — the Ansible inventory under `livespec-dev-tooling/ansible/inventory/`,
which is the committed provisioning model the discipline says to read before
any host action. So the host set is READ, in this order:

1. the governed project's own `ansible/inventory/*.yml` (a project that carries
   a provisioning tree is its own authority);
2. a sibling `livespec-dev-tooling` clone's inventory, resolved as a PEER of
   `CLAUDE_PROJECT_DIR` — the fleet keeps its first-class clones side by side
   under one parent (`/data/projects/<repo>`), so the provisioning repository
   sits next to whichever governed repository the session is in;
3. the documented fallback: the four pre-Talos Ubuntu machines the legacy
   inventory carried on 2026-09-12. It exists so the guard still holds on a
   host with no inventory in reach; it is NOT the source of truth, and a host
   added to the inventory is guarded without a code change.

Every host name AND every `ansible_host` alias is collected, so `ssh <alias>`
is judged the same as `ssh <name>`. The parse is a deliberately small reading
of the inventory's indentation structure — the standard library has no YAML
parser, and an inventory is the one shape the Ansible docs fix: a `hosts:` key,
one key per host beneath it, each optionally carrying `ansible_host`. Anything
else is ignored rather than modelled. An unreadable file is skipped; a file
with no hosts falls through to the next source.

The source that answered travels with the set so telemetry can say how often
the fallback is in force — a name, never.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__: list[str] = ["FALLBACK_HOSTS", "FleetHosts", "resolve_fleet_hosts"]

FALLBACK_HOSTS = frozenset({"vps", "poweredge-xubuntu", "gmktec-xubuntu", "hp-xubuntu"})
_INVENTORY_DIR = Path("ansible") / "inventory"
_SIBLING_REPO = "livespec-dev-tooling"


@dataclass(frozen=True, kw_only=True)
class FleetHosts:
    """The host set in force and where it came from (for telemetry, never a name)."""

    hosts: frozenset[str]
    source: str


def _parse_inventory_hosts(*, text: str) -> set[str]:
    """Host names and `ansible_host` aliases under every `hosts:` key, lower-cased."""
    hosts: set[str] = set()
    hosts_indent = -1
    entry_indent = -1
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = line.strip().partition(":")
        if hosts_indent >= 0 and indent <= hosts_indent:
            hosts_indent = -1
            entry_indent = -1
        if hosts_indent < 0:
            if key == "hosts" and not value.strip():
                hosts_indent = indent
            continue
        if entry_indent < 0:
            entry_indent = indent
        if indent == entry_indent:
            hosts.add(key.lower())
        elif key == "ansible_host" and value.strip():
            hosts.add(value.strip().strip("'\"").lower())
    return hosts


def _inventory_hosts(*, inventory_dir: Path) -> frozenset[str]:
    found: set[str] = set()
    for path in sorted(inventory_dir.glob("*.yml")) + sorted(inventory_dir.glob("*.yaml")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        found.update(_parse_inventory_hosts(text=text))
    return frozenset(found)


def resolve_fleet_hosts(*, project_dir: str | None) -> FleetHosts:
    """The fleet host set: project inventory, else sibling provisioning repo, else fallback."""
    if project_dir:
        root = Path(project_dir)
        candidates = (
            ("project-inventory", root / _INVENTORY_DIR),
            ("sibling-inventory", root.parent / _SIBLING_REPO / _INVENTORY_DIR),
        )
        for source, inventory_dir in candidates:
            hosts = _inventory_hosts(inventory_dir=inventory_dir)
            if hosts:
                return FleetHosts(hosts=hosts, source=source)
    return FleetHosts(hosts=FALLBACK_HOSTS, source="fallback")
