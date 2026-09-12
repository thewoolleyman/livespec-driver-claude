"""Unit tests for `.claude-plugin/hooks/_fleet_inventory.py`.

The guard's host set is READ from the provisioning inventory, never hardcoded;
these pin the resolution order (project inventory, the linked worktree's
primary checkout, a sibling `livespec-dev-tooling` clone, the documented
fallback), the `ansible_host` alias collection from inventory files AND
`host_vars/`, and the small YAML reading the parse relies on. Every inventory
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
    _parse_inventory_hosts,
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


def _write_host_vars(*, repo_root: Path, host: str, text: str) -> None:
    host_vars = repo_root / "ansible" / "inventory" / "host_vars"
    host_vars.mkdir(parents=True, exist_ok=True)
    _ = (host_vars / f"{host}.yml").write_text(text, encoding="utf-8")


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


def test_host_vars_supply_the_tailscale_address_of_an_inventory_host(tmp_path: Path) -> None:
    """The reviewer's E72: vps's `ansible_host` lives in `host_vars/vps.yml`, not the inventory."""
    project = tmp_path / "governed"
    _write_inventory(repo_root=project)
    _write_host_vars(
        repo_root=project,
        host="vps",
        text="# vps\nansible_host: 100.89.189.118  # tailnet\nsome_var: 1\n",
    )
    _write_host_vars(repo_root=project, host="Node-Delta", text="foo: bar\n")

    fleet = resolve_fleet_hosts(project_dir=str(project))

    assert {"100.89.189.118", "node-delta"} <= fleet.hosts
    assert (
        classify(command="ssh 100.89.189.118 'sudo systemctl restart k3s'", hosts=fleet.hosts)
        is not None
    )


def test_an_unreadable_host_vars_entry_is_skipped(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    _write_inventory(repo_root=project)
    _write_host_vars(repo_root=project, host="vps", text="ansible_host: 100.89.189.118\n")
    (project / "ansible" / "inventory" / "host_vars" / "broken.yml").mkdir()

    assert "100.89.189.118" in resolve_fleet_hosts(project_dir=str(project)).hosts


def test_host_vars_alone_do_not_make_an_inventory(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    _write_host_vars(repo_root=project, host="vps", text="ansible_host: 100.89.189.118\n")

    assert resolve_fleet_hosts(project_dir=str(project)).source == "fallback"


def test_sibling_provisioning_clone_supplies_the_hosts_when_the_project_has_none(
    tmp_path: Path,
) -> None:
    project = tmp_path / "projects" / "some-governed-repo"
    project.mkdir(parents=True)
    _write_inventory(repo_root=tmp_path / "projects" / "livespec-dev-tooling", name="legacy.yaml")

    fleet = resolve_fleet_hosts(project_dir=str(project))

    assert fleet.source == "sibling-inventory"
    assert "node-alpha" in fleet.hosts


def test_a_linked_worktree_resolves_through_its_primary_checkout(tmp_path: Path) -> None:
    """`~/.worktrees/<repo>/<branch>` has no sibling clone; its `.git` file names the primary."""
    primary = tmp_path / "projects" / "some-governed-repo"
    worktree = tmp_path / "worktrees" / "some-governed-repo" / "feature"
    worktree.mkdir(parents=True)
    _ = (worktree / ".git").write_text(
        f"gitdir: {primary}/.git/worktrees/feature\n", encoding="utf-8"
    )
    _write_inventory(repo_root=tmp_path / "projects" / "livespec-dev-tooling")

    assert resolve_fleet_hosts(project_dir=str(worktree)).source == "sibling-inventory"

    _write_inventory(repo_root=primary, text="all:\n  hosts:\n    node-primary:\n")
    fleet = resolve_fleet_hosts(project_dir=str(worktree))
    assert fleet == FleetHosts(hosts=frozenset({"node-primary"}), source="project-inventory")


def test_a_git_pointer_that_is_not_a_worktree_is_ignored(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    project.mkdir()
    _ = (project / ".git").write_text("gitdir: /somewhere/else\n", encoding="utf-8")

    assert resolve_fleet_hosts(project_dir=str(project)).source == "fallback"


def test_an_unreadable_git_pointer_is_ignored(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    project.mkdir()
    _ = (project / ".git").write_bytes(b"\xff\xfe")

    assert resolve_fleet_hosts(project_dir=str(project)).source == "fallback"


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


@pytest.mark.parametrize(
    ("text", "hosts"),
    [
        ('all:\n  hosts:\n    "node-q":\n      x: 1\n', {"node-q"}),
        ("all:\n  hosts: {node-i: {}, 'node-j': {x: 1}}\n", {"node-i", "node-j"}),
        ('all:\n  hosts:\n    n:\n      ansible_host: "10.0.0.1#x"\n', {"n", "10.0.0.1#x"}),
        ("all:\n  hosts:\n    n:\n      ansible_host: 10.0.0.1 # tailnet\n", {"n", "10.0.0.1"}),
        ("all:\n  hosts:\n    n:\n      ansible_host:\n", {"n"}),
    ],
)
def test_the_yaml_reading_handles_quotes_inline_maps_and_comments(
    text: str, hosts: set[str]
) -> None:
    assert _parse_inventory_hosts(text=text) == hosts


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
