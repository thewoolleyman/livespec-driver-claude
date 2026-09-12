"""Unit tests for `.claude-plugin/hooks/_mutation_verbs.py`.

The per-head verb tables, pinned by shape: always-mutating heads, inverted
subcommand heads (read-only verbs enumerated, everything else convicts),
flag-judged heads, the protected-tree copies and redirections, the kubectl
`--dry-run` last-wins rule, the `k3s kubectl …` delegation, and what `sudo`
may escalate. Every argv here is inert data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _mutation_verbs import (  # noqa: E402 — path-dependent import after sys.path insert.
    MUTATING_KUBECTL_VERBS,
    mutation_of,
    read_only,
    redirect_rule,
)

__all__: list[str] = []


@pytest.mark.parametrize(
    ("head", "arguments", "rule"),
    [
        # Always mutating: the head is the verb.
        ("tee", ["/etc/x"], "tee"),
        ("/usr/bin/rm", ["-rf", "x"], "rm"),
        ("APT", ["install", "x"], "apt"),
        ("reboot", [], "reboot"),
        # Inverted subcommand heads.
        ("systemctl", ["restart", "k3s"], "systemctl+restart"),
        ("systemctl", ["status", "k3s"], None),
        ("systemctl", ["show", "k3s", "-p", "ActiveState"], None),
        ("systemctl", ["kexec"], "systemctl+kexec"),
        ("systemctl", [], None),
        ("systemctl", ["-p", "ActiveState"], None),
        ("git", ["-C", "/x", "pull"], "git+pull"),
        ("git", ["-C", "/x", "status"], None),
        ("git", ["--git-dir=/x", "log"], None),
        ("git", ["--", "checkout"], "git+checkout"),
        ("k3s", ["check-config"], None),
        ("k3s", ["certificate", "check"], None),
        ("k3s", ["certificate", "rotate"], "k3s+certificate+rotate"),
        ("k3s", ["certificate"], "k3s+certificate+none"),
        ("k3s", ["etcd-snapshot", "save"], "k3s+etcd-snapshot"),
        ("k3s", ["kubectl", "delete", "pod", "x"], "kubectl+delete"),
        ("k3s", ["kubectl", "get", "pods"], None),
        ("k3s", ["crictl", "rmi", "--prune"], "crictl+rmi"),
        ("k3s", ["ctr", "-n", "k8s.io", "image", "rm", "x"], "ctr+image"),
        ("k3s", ["50"], None),
        ("k3s", ["ActiveState"], None),
        ("kubectl", ["get", "pods", "delete"], None),
        ("kubectl", ["logs", "-n", "apply", "x"], None),
        ("kubectl", ["auth", "can-i", "delete", "pods"], None),
        ("kubectl", ["-n", "ns", "delete", "pod", "x"], "kubectl+delete"),
        ("kubectl", ["--kubeconfig=/x", "apply", "-f", "x"], "kubectl+apply"),
        ("kubectl", ["delete", "pod", "x", "--dry-run=client"], None),
        ("kubectl", ["delete", "pod", "x", "--dry-run=client", "--dry-run=none"], "kubectl+delete"),
        ("kubectl", ["delete", "pod", "x", "--dry-run", "none"], "kubectl+delete"),
        ("kubectl", ["delete", "pod", "x", "--dry-run", "server"], None),
        ("kubectl", ["apply", "-f", "x", "--dry-run"], None),
        ("kubectl", ["apply", "--dry-run", "-f", "x"], None),
        ("kubectl", ["exec", "pod", "--", "cat", "x"], "kubectl+exec"),
        ("helm", ["upgrade", "--install", "x"], "helm+upgrade"),
        ("helm", ["-n", "ns", "list"], None),
        ("crictl", ["ps"], None),
        ("crictl", ["rm", "-a"], "crictl+rm"),
        ("crictl", ["image", "ls"], None),
        ("crictl", ["image", "rm", "x"], "crictl+image+rm"),
        ("ctr", ["-n", "k8s.io", "image", "ls"], None),
        ("ctr", ["-n", "k8s.io", "image", "rm", "x"], "ctr+image"),
        ("ctr", ["version"], None),
        ("docker", ["ps"], None),
        ("docker", ["rm", "x"], "docker+rm"),
        ("docker", ["image", "ls"], None),
        ("docker", ["image", "rm", "x"], "docker+image+rm"),
        ("tailscale", ["status"], None),
        ("tailscale", ["up"], "tailscale+up"),
        # Flag-judged heads.
        ("find", ["/etc", "-name", "x"], None),
        ("find", ["/etc", "-name", "x", "-delete"], "find+-delete"),
        ("find", ["/etc", "-exec", "rm", "{}", "+"], "find+-exec"),
        ("find", ["/etc", "-fprint", "/tmp/x"], "find+-fprint"),
        ("journalctl", ["-u", "k3s", "-n", "50"], None),
        ("journalctl", ["--vacuum-time=1d"], "journalctl+--vacuum-time"),
        ("journalctl", ["--rotate"], "journalctl+--rotate"),
        ("sed", ["-n", "/x/p", "f"], None),
        ("sed", ["-i", "s/a/b/", "f"], "sed+in-place"),
        ("sed", ["-ni", "s/a/b/", "f"], "sed+in-place"),
        ("sed", ["--in-place", "s/a/b/", "f"], "sed+in-place"),
        ("sed", ["--in-place=.bak", "s/a/b/", "f"], "sed+in-place"),
        ("iptables", ["-S"], None),
        ("iptables", ["-A", "INPUT", "-j", "DROP"], "iptables+-A"),
        ("ip6tables", ["--flush"], "ip6tables+--flush"),
        ("ip", ["addr"], None),
        ("ip", ["link", "set", "eth0", "down"], "ip+set"),
        ("dmesg", ["-T"], None),
        ("dmesg", ["-C"], "dmesg+clear"),
        ("sysctl", ["net.ipv4.ip_forward"], None),
        ("sysctl", ["-w", "net.ipv4.ip_forward=1"], "sysctl+write"),
        ("sysctl", ["net.ipv4.ip_forward=1"], "sysctl+write"),
        ("cp", ["x", "/etc/x"], "cp"),
        ("cp", ["x", "/etc"], "cp"),
        ("cp", ["x", "/etcetera/x"], None),
        ("mv", ["x", "/usr/local/bin/x"], "mv"),
        ("cp", ["/etc/x", "/tmp/x"], None),
        ("cp", ["-r"], None),
        ("ansible", ["all", "-m", "ping"], None),
        ("ansible", ["all", "-m", "shell", "-a", "x"], "ansible+adhoc"),
        ("ansible", ["all", "--module-name", "apt", "-a", "x"], "ansible+adhoc"),
        ("ansible", ["all", "-m", "setup", "-b"], "ansible+adhoc"),
        ("ansible", ["all", "-m", "setup", "--become"], "ansible+adhoc"),
        ("ansible", ["all", "-bm", "setup"], "ansible+adhoc"),
        ("ansible", ["all", "-m"], None),
        # Unknown heads are not mutations on their own.
        ("some-tool", ["--flag"], None),
        ("cat", ["/etc/x"], None),
    ],
)
def test_mutation_of_convicts_by_head_verb_or_flag(
    head: str, arguments: list[str], rule: str | None
) -> None:
    assert mutation_of(head=head, arguments=arguments) == rule


@pytest.mark.parametrize(
    ("head", "arguments", "read"),
    [
        ("cat", ["/etc/x"], True),
        ("/bin/ls", ["-la"], True),
        ("JOURNALCTL", ["-u", "k3s"], True),
        ("journalctl", ["--vacuum-time=1d"], False),
        ("systemctl", ["status", "k3s"], True),
        ("systemctl", ["restart", "k3s"], False),
        ("kubectl", ["get", "nodes"], True),
        ("k3s", ["certificate", "check"], True),
        ("cp", ["/etc/x", "/tmp/x"], False),
        ("some-tool", [], False),
        ("reboot", [], False),
    ],
)
def test_read_only_is_a_positive_identification(
    head: str, arguments: list[str], read: bool
) -> None:
    assert read_only(head=head, arguments=arguments) is read


@pytest.mark.parametrize(
    ("tokens", "rule"),
    [
        (["echo", "1", ">", "/etc/x"], "redirect-into-protected-tree"),
        (["echo", "1", ">/etc/x"], "redirect-into-protected-tree"),
        (["echo", "1", ">>", "/usr/local/etc/x"], "redirect-into-protected-tree"),
        (["echo", "1", ">", "/boot/x"], "redirect-into-protected-tree"),
        (["echo", "1", ">", "/tmp/x"], None),
        (["echo", "1", ">"], None),
        (["echo", "1"], None),
    ],
)
def test_redirect_rule_judges_the_target_tree(tokens: list[str], rule: str | None) -> None:
    assert redirect_rule(tokens=tokens) == rule


def test_the_mutating_kubectl_verbs_feed_the_hazard_hint() -> None:
    assert {"apply", "delete", "create", "rollout", "exec"} <= MUTATING_KUBECTL_VERBS
