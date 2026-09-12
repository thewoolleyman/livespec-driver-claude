"""Unit tests for `.claude-plugin/hooks/_fleet_inventory.py`.

The guard's host set is READ from the provisioning inventory, never hardcoded;
these pin the three-step resolution (project inventory, sibling
`livespec-dev-tooling` clone, documented fallback), the `ansible_host` alias
collection, and the small YAML reading the parse relies on. Every inventory
here is written under `tmp_path`; no real inventory is read, and the
classifier is driven only to prove the resolved set is what it judges by.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _fleet_inventory import (  # noqa: E402 — path-dependent import after sys.path insert.
    FALLBACK_HOSTS,
    FleetHosts,
    resolve_fleet_hosts,
)
from _host_mutation import classify  # noqa: E402 — path-dependent import after sys.path insert.

__all__: list[str] = []

_INVENTORY = """\
# LEGACY-ONLY inventory — comments and blank lines are ignored.
all:
  children:
    legacy:
      children:
        dev_hosts:
          hosts:
            vps:
              ansible_connection: local
        ci_pool:
          hosts:
            Node-Alpha:   # a host the fallback set has never heard of
              ansible_user: cwoolley
              ansible_host: "100.64.0.42"
              cluster_role: server
            node-beta: {}
        sandbox_hosts:
          hosts:
            node-gamma:
              ansible_host: '100.64.0.43'
"""


def _write_inventory(*, repo_root: Path, text: str = _INVENTORY, name: str = "legacy.yml") -> None:
    inventory_dir = repo_root / "ansible" / "inventory"
    inventory_dir.mkdir(parents=True, exist_ok=True)
    _ = (inventory_dir / name).write_text(text, encoding="utf-8")


def test_project_inventory_supplies_host_names_and_ansible_host_aliases(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    _write_inventory(repo_root=project)

    fleet = resolve_fleet_hosts(project_dir=str(project))

    assert fleet == FleetHosts(
        hosts=frozenset(
            {"vps", "node-alpha", "100.64.0.42", "node-beta", "node-gamma", "100.64.0.43"}
        ),
        source="project-inventory",
    )
    assert classify(command="ssh node-alpha 'sudo reboot'", hosts=fleet.hosts) is not None
    assert classify(command="ssh 100.64.0.43 'sudo reboot'", hosts=fleet.hosts) is not None
    assert classify(command="ssh poweredge-xubuntu 'sudo reboot'", hosts=fleet.hosts) is None


def test_sibling_provisioning_clone_supplies_the_hosts_when_the_project_has_none(
    tmp_path: Path,
) -> None:
    project = tmp_path / "projects" / "some-governed-repo"
    project.mkdir(parents=True)
    _write_inventory(repo_root=tmp_path / "projects" / "livespec-dev-tooling", name="legacy.yaml")

    fleet = resolve_fleet_hosts(project_dir=str(project))

    assert fleet.source == "sibling-inventory"
    assert "node-alpha" in fleet.hosts


def test_every_inventory_file_in_the_directory_contributes(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    _write_inventory(repo_root=project)
    _write_inventory(
        repo_root=project, name="extra.yml", text="extra:\n  hosts:\n    node-delta:\n"
    )

    fleet = resolve_fleet_hosts(project_dir=str(project))

    assert {"node-alpha", "node-delta"} <= fleet.hosts


def test_an_inventory_without_hosts_falls_through_to_the_next_source(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "governed"
    _write_inventory(repo_root=project, text="all:\n  children:\n    legacy: {}\n")
    _write_inventory(repo_root=tmp_path / "projects" / "livespec-dev-tooling")

    assert resolve_fleet_hosts(project_dir=str(project)).source == "sibling-inventory"


def test_an_unreadable_inventory_entry_is_skipped(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    _write_inventory(repo_root=project)
    # A directory whose name ends in `.yml` is matched by the glob but cannot be read.
    (project / "ansible" / "inventory" / "broken.yml").mkdir()

    fleet = resolve_fleet_hosts(project_dir=str(project))

    assert fleet.source == "project-inventory"
    assert "node-alpha" in fleet.hosts


def test_a_second_hosts_block_at_a_shallower_indent_resets_the_walk(tmp_path: Path) -> None:
    text = "a:\n  hosts:\n    node-one:\n      x: 1\nb:\n  hosts:\n    node-two:\n"
    project = tmp_path / "governed"
    _write_inventory(repo_root=project, text=text)

    assert resolve_fleet_hosts(project_dir=str(project)).hosts == frozenset(
        {"node-one", "node-two"}
    )


@pytest.mark.parametrize("project_dir", [None, ""])
def test_no_project_dir_yields_the_documented_fallback(project_dir: str | None) -> None:
    assert resolve_fleet_hosts(project_dir=project_dir) == FleetHosts(
        hosts=FALLBACK_HOSTS, source="fallback"
    )


def test_a_project_with_no_inventory_in_reach_yields_the_documented_fallback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "alone"
    project.mkdir()

    assert resolve_fleet_hosts(project_dir=str(project)).source == "fallback"


def test_the_fallback_names_the_legacy_inventory_hosts_as_of_the_record_date() -> None:
    """If the fallback and the real inventory drift, this is the test that says so."""
    assert frozenset({"vps", "poweredge-xubuntu", "gmktec-xubuntu", "hp-xubuntu"}) == FALLBACK_HOSTS
