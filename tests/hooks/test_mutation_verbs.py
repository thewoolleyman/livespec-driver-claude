"""Unit tests for `.claude-plugin/hooks/_mutation_verbs.py`.

The per-head verb logic over the `_verb_tables` data, pinned by shape:
always-mutating heads, path-scoped writes (protected trees only), inverted
subcommand heads (read-only verbs enumerated, everything else convicts, noun-
verb tools at the second level), flag-judged heads, the kubectl/helm
`--dry-run` last-wins rule, the `k3s kubectl …` delegation, `git config`'s
query flags, the redirection spellings, and what `sudo` may escalate. Every
argv here is inert data.
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
        ("/usr/bin/install", ["-m", "0755", "x", "/tmp/x"], "install"),
        ("reboot", [], "reboot"),
        ("useradd", ["x"], "useradd"),
        # Path-scoped: a write is a mutation only under a protected tree.
        ("rm", ["-rf", "/opt/x"], "rm"),
        ("/usr/bin/rm", ["-rf", "/etc/x"], "rm"),
        ("rm", ["-rf", "/tmp/x"], None),
        ("rm", ["-rf", "~/x"], None),
        ("mkdir", ["-p", "/tmp/probe"], None),
        ("mkdir", ["-p", "/etc/rancher/k3s"], "mkdir"),
        ("touch", ["/var/lib/x"], "touch"),
        ("ln", ["-s", "/opt/a", "/usr/local/bin/a"], "ln"),
        ("cp", ["x", "/etc/x"], "cp"),
        ("cp", ["x", "/etc"], "cp"),
        ("cp", ["x", "/etcetera/x"], None),
        ("cp", ["/etc/x", "/tmp/x"], None),
        ("mv", ["x", "/usr/local/bin/x"], "mv"),
        ("mv", ["/srv/a", "/tmp/b"], None),
        ("cp", ["-r"], None),
        ("tee", ["/tmp/x"], None),
        ("tee", ["-a", "/etc/x"], "tee"),
        ("sudo", [], None),
        ("CHMOD", ["+x", "/tmp/probe.sh"], None),
        ("chmod", ["600", "/etc/rancher/k3s/k3s.yaml"], "chmod"),
        ("chown", ["root", "/usr/local/bin/x"], "chown"),
        ("chown", ["cwoolley", "~/x"], None),
        ("chgrp", ["adm", "/opt/x"], "chgrp"),
        ("tee", ["-a", "~/.ssh/authorized_keys"], "tee"),
        ("cp", ["x", "$HOME/.ssh/config"], "cp"),
        ("tee", ["${HOME}/.ssh/rc"], "tee"),
        ("tee", ["/root/.ssh/authorized_keys"], "tee"),
        ("cp", ["x", "~/.config/systemd/user/fabro-server.service"], "cp"),
        ("tee", ["~/.fabro/config.toml"], "tee"),
        ("rm", ["-rf", "/home/cwoolley/.fabro-mi-homelab"], "rm"),
        ("rm", ["-rf", "~/.fabro"], "rm"),
        ("tee", ["~/notes.txt"], None),
        ("cp", ["x", "~/repos/y"], None),
        ("rm", ["-rf", "/home/cwoolley/.worktrees/x"], None),
        ("touch", ["~/.bash_history"], None),
        ("touch", ["~/.sshx/y"], None),
        ("touch", ["~"], None),
        ("touch", ["/homer/x/.ssh/y"], None),
        # Inverted subcommand heads.
        ("systemctl", ["restart", "k3s"], "systemctl+restart"),
        ("systemctl", ["status", "k3s"], None),
        ("systemctl", ["--user", "status", "fabro"], None),
        ("systemctl", ["show", "k3s", "-p", "ActiveState"], None),
        ("systemctl", ["daemon-reexec"], "systemctl+daemon-reexec"),
        ("systemctl", [], None),
        ("systemctl", ["-p", "ActiveState"], None),
        ("git", ["-C", "/x", "pull"], "git+pull"),
        ("git", ["-C", "/x", "status"], None),
        ("git", ["--git-dir=/x", "log"], None),
        ("git", ["--", "checkout"], "git+checkout"),
        ("git", ["stash"], "git+stash"),
        ("git", ["-C", "/x", "config", "--get", "remote.origin.url"], None),
        ("git", ["config", "-l"], None),
        ("git", ["-C", "/x", "config", "receive.denyCurrentBranch", "ignore"], "git+config"),
        ("k3s", ["check-config"], None),
        ("k3s", ["certificate", "check"], None),
        ("k3s", ["certificate", "rotate"], "k3s+certificate+rotate"),
        ("k3s", ["certificate"], "k3s+certificate+none"),
        ("k3s", ["etcd-snapshot", "ls"], None),
        ("k3s", ["etcd-snapshot", "save"], "k3s+etcd-snapshot+save"),
        ("k3s", ["secrets-encrypt", "status"], None),
        ("k3s", ["secrets-encrypt", "rotate"], "k3s+secrets-encrypt+rotate"),
        ("k3s", ["token", "list"], None),
        ("k3s", ["server"], "k3s+server"),
        ("k3s", ["kubectl", "delete", "pod", "x"], "kubectl+delete"),
        ("k3s", ["kubectl", "get", "pods"], None),
        ("k3s", ["crictl", "rmi", "--prune"], "crictl+rmi"),
        ("k3s", ["ctr", "-n", "k8s.io", "image", "rm", "x"], "ctr+image"),
        ("k3s", ["50"], None),
        ("k3s", ["ActiveState"], None),
        ("kubectl", ["get", "pods", "delete"], None),
        ("kubectl", ["logs", "-n", "apply", "x"], None),
        ("kubectl", ["auth", "can-i", "delete", "pods"], None),
        ("kubectl", ["auth", "whoami"], None),
        ("kubectl", ["auth", "reconcile", "-f", "rbac.yaml"], "kubectl+auth+reconcile"),
        ("kubectl", ["config", "use-context", "k3s"], None),
        ("kubectl", ["wait", "--for=condition=Ready", "node/x"], None),
        ("kubectl", ["-n", "ns", "delete", "pod", "x"], "kubectl+delete"),
        ("kubectl", ["--kubeconfig=/x", "apply", "-f", "x"], "kubectl+apply"),
        ("kubectl", ["delete", "pod", "x", "--dry-run=client"], None),
        ("kubectl", ["delete", "pod", "x", "--dry-run=client", "--dry-run=none"], "kubectl+delete"),
        ("kubectl", ["delete", "pod", "x", "--dry-run=none", "--dry-run=client"], None),
        ("kubectl", ["delete", "pod", "x", "--dry-run", "none"], "kubectl+delete"),
        ("kubectl", ["delete", "pod", "x", "--dry-run", "server"], None),
        ("kubectl", ["apply", "-f", "x", "--dry-run"], None),
        ("kubectl", ["apply", "--dry-run", "-f", "x"], None),
        ("kubectl", ["exec", "pod", "--", "cat", "x"], "kubectl+exec"),
        ("helm", ["upgrade", "--install", "x"], "helm+upgrade"),
        ("helm", ["upgrade", "--install", "x", "chart/", "--dry-run"], None),
        ("helm", ["diff", "upgrade", "x", "chart/"], None),
        ("helm", ["-n", "ns", "list"], None),
        ("crictl", ["ps"], None),
        ("crictl", ["rm", "-a"], "crictl+rm"),
        ("crictl", ["image"], None),
        ("crictl", ["image", "ls"], None),
        ("crictl", ["image", "rm", "x"], "crictl+image+rm"),
        ("ctr", ["-n", "k8s.io", "image", "ls"], None),
        ("ctr", ["-n", "k8s.io", "image", "rm", "x"], "ctr+image"),
        ("ctr", ["version"], None),
        ("docker", ["ps"], None),
        ("docker", ["rm", "x"], "docker+rm"),
        ("docker", ["exec", "c", "rm", "-rf", "/data"], "docker+exec"),
        ("docker", ["image", "ls"], None),
        ("docker", ["image", "rm", "x"], "docker+image+rm"),
        ("docker", ["container", "ls"], None),
        ("docker", ["container", "rm", "x"], "docker+container+rm"),
        ("docker", ["compose", "ps"], None),
        ("docker", ["compose", "up", "-d"], "docker+compose+up"),
        ("docker", ["system", "df"], None),
        ("docker", ["system", "prune"], "docker+system+prune"),
        ("tailscale", ["status"], None),
        ("tailscale", ["up", "--ssh"], "tailscale+up"),
        ("tailscale", ["set", "--advertise-exit-node"], "tailscale+set"),
        ("apt", ["list", "--installed"], None),
        ("apt", ["install", "-y", "x"], "apt+install"),
        ("apt-get", ["update"], "apt-get+update"),
        ("apt-cache", ["policy", "x"], None),
        ("snap", ["list"], None),
        ("snap", ["install", "x"], "snap+install"),
        ("pip", ["list"], None),
        ("pip3", ["install", "x"], "pip3+install"),
        ("npm", ["ls"], None),
        ("npm", ["install", "-g", "x"], "npm+install"),
        ("nft", ["list", "ruleset"], None),
        ("nft", ["flush", "ruleset"], "nft+flush"),
        ("nft", ["-f", "/etc/nftables.conf"], "nft+-f"),
        ("nft", ["-c", "-f", "/etc/nftables.conf"], None),
        ("nft", ["--check", "-f", "/etc/nftables.conf"], None),
        ("nft", ["-cf", "/etc/nftables.conf"], None),
        ("nft", ["--file=/etc/nftables.conf"], "nft+--file"),
        ("nft", ["-a", "list", "ruleset"], None),
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
        ("awk", ["-F#", "{print}", "f"], None),
        ("awk", ["-i", "inplace", "1", "/etc/x"], "awk+inplace"),
        ("awk", ["-i", "lib.awk", "1", "f"], None),
        ("yq", [".x", "f"], None),
        ("yq", ["-i", ".x=1", "/etc/x"], "yq+-i"),
        ("iptables", ["-S"], None),
        ("iptables", ["-A", "INPUT", "-j", "DROP"], "iptables+-A"),
        ("ip6tables", ["--flush"], "ip6tables+--flush"),
        ("iptables-save", [], None),
        ("ip", ["addr"], None),
        ("ip", ["link", "set", "eth0", "down"], "ip+set"),
        ("ip", ["netns", "exec", "x", "rm", "-rf", "/"], "ip+exec"),
        ("dmesg", ["-T"], None),
        ("dmesg", ["-C"], "dmesg+-C"),
        ("sysctl", ["net.ipv4.ip_forward"], None),
        ("sysctl", ["-w", "net.ipv4.ip_forward=1"], "sysctl+-w"),
        ("sysctl", ["--system"], "sysctl+--system"),
        ("sysctl", ["net.ipv4.ip_forward=1"], "sysctl+write"),
        ("date", ["+%F"], None),
        ("date", ["-s", "2030-01-01"], "date+-s"),
        ("hostname", ["-f"], None),
        ("hostname", ["newname"], "hostname+set"),
        ("mount", [], None),
        ("mount", ["/dev/sdb1", "/mnt"], "mount+set"),
        ("mount", ["-a"], "mount+-a"),
        ("mount", ["-o", "remount,rw", "/"], "mount+-o"),
        ("mount", ["-t", "nfs"], None),
        ("mount", ["-av"], "mount+-a"),
        ("mount", ["--source", "/dev/sdb1", "--target", "/mnt"], "mount+--source"),
        ("mount", ["-vt", "nfs"], None),
        ("date", ["-Iseconds"], None),
        ("date", ["-Is"], None),
        ("dpkg", ["-lv"], None),
        ("dmesg", ["-Tc"], "dmesg+-c"),
        ("dpkg", ["-l"], None),
        ("dpkg", ["-s", "curl"], None),
        ("dpkg", ["-i", "x.deb"], "dpkg+-i"),
        ("dpkg", ["--configure", "-a"], "dpkg+--configure"),
        ("ansible", ["all", "-m", "ping"], None),
        ("ansible", ["poweredge-xubuntu", "-m", "setup"], None),
        ("ansible", ["all", "-m", "shell", "-a", "x"], "ansible+adhoc"),
        ("ansible", ["all", "-m", "ansible.builtin.shell", "-a", "x"], "ansible+adhoc"),
        ("ansible", ["all", "--module-name", "apt", "-a", "x"], "ansible+adhoc"),
        ("ansible", ["all", "-m", "systemd", "-a", "name=k3s state=restarted"], "ansible+adhoc"),
        ("ansible", ["all", "-m", "setup", "-b"], "ansible+adhoc"),
        ("ansible", ["all", "-m", "setup", "-bK"], "ansible+adhoc"),
        ("ansible", ["all", "-m", "setup", "--become"], "ansible+adhoc"),
        ("ansible", ["all", "-bm", "setup"], "ansible+adhoc"),
        ("ansible", ["all", "-m"], None),
        # Unknown heads are not mutations on their own.
        ("some-tool", ["--flag"], None),
        ("cat", ["/etc/x"], None),
    ],
)
def test_mutation_of_convicts_by_head_verb_flag_or_path(
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
        ("dpkg", ["-l"], True),
        ("mount", [], True),
        ("mount", ["/dev/x", "/mnt"], False),
        ("iptables-save", [], True),
        ("nft", ["list", "ruleset"], True),
        ("cp", ["/etc/x", "/tmp/x"], False),
        ("rm", ["/tmp/x"], False),
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
        (["echo", "1", "1>/etc/sysctl.d/x.conf"], "redirect-into-protected-tree"),
        (["ls", "2>/etc/x"], "redirect-into-protected-tree"),
        (["echo", "1", ">|/etc/x"], "redirect-into-protected-tree"),
        (["echo", "1", "&>", "/opt/x"], "redirect-into-protected-tree"),
        (["echo", "1", ">", "/tmp/x"], None),
        (["cmd", "2>&1"], None),
        (["echo", "1", ">"], None),
        (["echo", "1"], None),
    ],
)
def test_redirect_rule_judges_every_output_spelling_by_target_tree(
    tokens: list[str], rule: str | None
) -> None:
    assert redirect_rule(tokens=tokens) == rule


def test_the_mutating_kubectl_verbs_feed_the_hazard_hint() -> None:
    assert {"apply", "delete", "create", "rollout", "exec"} <= MUTATING_KUBECTL_VERBS
