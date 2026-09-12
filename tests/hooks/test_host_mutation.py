"""Deny/allow corpus for `.claude-plugin/hooks/_host_mutation.py`.

A session ssh'd into two fleet-managed k3s nodes and reasoned about deploying to
them by hand, while the provisioning repository it had been editing states that
the control node is `vps` and `just ansible-apply <playbook>` converges from
committed source. This module pins the classifier that turns that discipline
into a PreToolUse denial, in-process, one case per rule and per evasion family,
plus the false-positive direction: a guard that blocks read-only reaches, the
sanctioned apply, or quoted mentions pushes agents into working around it.

Every command string below is INERT DATA handed to a pure classifier function.
`classify` reads a string and a host set and returns a rule name or None;
nothing in this module runs `ssh`, `scp`, `rsync`, `sftp`, or `kubectl`, and
nothing here may be changed to do so. Host-set RESOLUTION is pinned by the
sibling `test_fleet_inventory.py`; here the set is a fixed constant.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _host_mutation import (  # noqa: E402 — path-dependent import after sys.path insert.
    classify,
    hazard_hint,
)

__all__: list[str] = []

# The legacy inventory's four hosts plus one `ansible_host` alias, as the
# resolver would yield them. A fixed set so every case below is a pure
# function of text; resolution itself is pinned in `test_fleet_inventory.py`.
_HOSTS = frozenset({"vps", "poweredge-xubuntu", "gmktec-xubuntu", "hp-xubuntu", "100.64.0.7"})

# Every one of these changes a fleet-managed host by hand. DATA, never executed.
_DENY_CASES = (
    # --- The acceptance criterion and its spellings ---------------------------
    ("A1 quoted remote sudo restart", "ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("A2 unquoted remote operands", "ssh poweredge-xubuntu sudo systemctl restart k3s"),
    ("A3 user@host", "ssh cwoolley@gmktec-xubuntu 'sudo systemctl stop k3s-agent'"),
    (
        "A4 -l user and -p port consumed",
        "ssh -p 22 -l cwoolley hp-xubuntu 'sudo systemctl enable x'",
    ),
    ("A5 -J jump host consumed", "ssh -J vps poweredge-xubuntu 'sudo reboot'"),
    (
        "A6 -o option consumed",
        "ssh -o StrictHostKeyChecking=no poweredge-xubuntu 'sudo apt install -y x'",
    ),
    ("A7 fused -oOption", "ssh -oStrictHostKeyChecking=no poweredge-xubuntu 'sudo tee /etc/x'"),
    (
        "A8 ssh:// URI target",
        "ssh ssh://cwoolley@poweredge-xubuntu:22 'sudo systemctl restart k3s'",
    ),
    ("A9 case-insensitive host", "ssh POWEREDGE-XUBUNTU 'sudo systemctl restart k3s'"),
    ("A10 tailnet FQDN", "ssh poweredge-xubuntu.tail1234.ts.net 'sudo systemctl daemon-reload'"),
    ("A11 ansible_host alias", "ssh 100.64.0.7 'sudo systemctl restart k3s'"),
    ("A12 -- ends options", "ssh -i key poweredge-xubuntu -- sudo systemctl restart k3s"),
    # --- Mutation verbs on the remote side ------------------------------------
    ("V1 install", "ssh hp-xubuntu 'install -m 0755 x /usr/local/bin/x'"),
    ("V2 tee via pipe", "ssh hp-xubuntu 'echo x | sudo tee /etc/y'"),
    ("V3 cp into /etc", 'ssh poweredge-xubuntu "cp ./unit /etc/systemd/system/"'),
    ("V4 mv into /usr", "ssh poweredge-xubuntu 'mv ./x /usr/local/bin/x'"),
    ("V5 cp -r into /etc exact", "ssh poweredge-xubuntu 'cp -r ./tree /etc'"),
    ("V6 chmod", "ssh hp-xubuntu 'chmod +x /usr/local/bin/x'"),
    ("V7 chown", "ssh hp-xubuntu 'chown root:root /opt/x'"),
    ("V8 apt-get", "ssh gmktec-xubuntu 'apt-get update'"),
    ("V9 rm", "ssh gmktec-xubuntu 'rm -rf /opt/x'"),
    ("V10 systemctl start", "ssh gmktec-xubuntu 'systemctl start k3s-agent'"),
    ("V11 systemctl disable", "ssh gmktec-xubuntu 'systemctl disable --now k3s-agent'"),
    ("V12 systemctl mask", "ssh gmktec-xubuntu 'systemctl mask x'"),
    ("V13 git clone", "ssh hp-xubuntu 'git clone https://example.invalid/x /opt/x'"),
    ("V14 git pull after cd", "ssh hp-xubuntu 'cd /opt/x && git pull'"),
    ("V15 remote kubectl delete", "ssh poweredge-xubuntu 'kubectl delete node gmktec-xubuntu'"),
    ("V16 remote kubectl drain unquoted", "ssh poweredge-xubuntu kubectl drain gmktec-xubuntu"),
    ("V17 redirect into /etc", "ssh poweredge-xubuntu 'echo 1 > /etc/sysctl.d/x.conf'"),
    ("V18 fused redirect into /etc", "ssh poweredge-xubuntu 'echo 1 >/etc/sysctl.d/x.conf'"),
    ("V19 append into /usr", "ssh poweredge-xubuntu 'echo 1 >> /usr/local/etc/x'"),
    ("V20 k3s etcd-snapshot", "ssh poweredge-xubuntu 'k3s etcd-snapshot save'"),
    ("V21 sudo k3s kubectl delete", "ssh poweredge-xubuntu 'sudo k3s kubectl delete pod x'"),
    # --- sudo on its own -------------------------------------------------------
    ("S1 sudo root shell -i", "ssh poweredge-xubuntu 'sudo -i'"),
    ("S2 sudo root shell -s", "ssh poweredge-xubuntu 'sudo -s'"),
    ("S3 sudo bare", "ssh poweredge-xubuntu sudo"),
    ("S4 sudo -u root rm", "ssh poweredge-xubuntu 'sudo -u root rm -rf /opt/x'"),
    ("S5 sudo non-read-only head", "ssh poweredge-xubuntu 'sudo reboot'"),
    ("S6 sudo absolute path head", "ssh poweredge-xubuntu 'sudo /usr/local/bin/install-node.sh'"),
    # --- Nesting and wrappers --------------------------------------------------
    ("N1 remote bash -c", "ssh poweredge-xubuntu 'bash -c \"sudo systemctl restart k3s\"'"),
    ("N2 outer bash -c", "bash -c \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\""),
    ("N3 sh -lc", "sh -lc \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\""),
    ("N4 ssh hop through vps", "ssh vps ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    (
        "N5 heredoc is the remote script",
        "ssh poweredge-xubuntu bash -s <<'EOF'\nsudo systemctl restart k3s\nEOF",
    ),
    ("N6 heredoc with -T", "ssh -T gmktec-xubuntu <<EOF\nsudo apt-get install -y x\nEOF"),
    ("W1 timeout wrapper", "timeout 30 ssh poweredge-xubuntu 'sudo systemctl stop k3s'"),
    ("W2 mise exec --", "mise exec -- ssh poweredge-xubuntu 'sudo systemctl stop k3s'"),
    ("W3 env -i", "env -i ssh poweredge-xubuntu sudo systemctl stop k3s"),
    ("W4 chained after cd", "cd /tmp && ssh poweredge-xubuntu 'sudo systemctl stop k3s'"),
    ("W5 semicolon chain", "echo hi; ssh poweredge-xubuntu 'sudo systemctl stop k3s'"),
    ("W6 newline chain", "echo hi\nssh poweredge-xubuntu 'sudo systemctl stop k3s'"),
    ("W7 absolute ssh path", "/usr/bin/ssh poweredge-xubuntu 'sudo systemctl stop k3s'"),
    ("W8 subshell", "(ssh poweredge-xubuntu 'sudo systemctl stop k3s')"),
    ("W9 line continuation", "ssh poweredge-xubuntu \\\n 'sudo systemctl stop k3s'"),
    ("W10 nohup", "nohup ssh poweredge-xubuntu 'sudo systemctl stop k3s' &"),
    # --- Uploads -----------------------------------------------------------------
    ("U1 scp upload into /etc", "scp ./unit poweredge-xubuntu:/etc/systemd/system/x.service"),
    ("U2 scp -r upload user@host", "scp -r dir cwoolley@gmktec-xubuntu:/tmp/"),
    ("U3 scp with -P port", "scp -P 22 ./x hp-xubuntu:/opt/x"),
    ("U4 rsync upload", "rsync -av ./tree hp-xubuntu:/usr/local/lib/"),
    ("U5 rsync --delete upload", "rsync -av --delete ./x cwoolley@gmktec-xubuntu:/opt/x"),
    ("U6 rsync daemon URL", "rsync -av ./x rsync://poweredge-xubuntu/module/"),
    ("U7 rsync trailing flag", "rsync -av ./x gmktec-xubuntu:/opt/x --delete"),
    (
        "U8 sftp put batch",
        "sftp poweredge-xubuntu <<'EOF'\nput unit.service /etc/systemd/system/\nEOF",
    ),
    ("U9 sftp -b - rm batch", "sftp -b - cwoolley@gmktec-xubuntu <<EOF\nrm /opt/x\nEOF"),
    ("U10 sftp:// URI", "sftp sftp://hp-xubuntu <<EOF\nmkdir /opt/x\nEOF"),
    # --- kubectl from anywhere ------------------------------------------------
    ("K1 delete node", "kubectl delete node gmktec-xubuntu"),
    ("K2 -n before verb", "kubectl -n kube-system apply -f x.yaml"),
    ("K3 patch", "kubectl patch node x -p '{\"spec\":{}}'"),
    ("K4 taint", "kubectl taint nodes x key=v:NoSchedule"),
    ("K5 cordon", "kubectl cordon gmktec-xubuntu"),
    ("K6 drain", "kubectl drain gmktec-xubuntu --ignore-daemonsets"),
    ("K7 label", "kubectl label node x k=v"),
    ("K8 edit", "kubectl edit deploy x"),
    ("K9 scale", "kubectl scale deploy x --replicas=0"),
    ("K10 --context before verb", "kubectl --context k3s delete pod x"),
    ("K11 sudo kubectl", "sudo kubectl delete pod x"),
    ("K12 k3s kubectl", "k3s kubectl delete pod x"),
    ("K13 after a read", "kubectl get nodes && kubectl delete node x"),
    ("K14 --dry-run=none still mutates", "kubectl delete pod x --dry-run=none"),
    ("K15 nested", "bash -c 'kubectl delete pod x'"),
    ("K16 env assignment prefix", "KUBECONFIG=/x kubectl delete ns y"),
    ("K17 absolute path", "/usr/local/bin/kubectl apply -k ci-runner/k3s/"),
    # --- Parse-hostile but hazard-shaped: must fail CLOSED ----------------------
    ("X1 unbalanced quote to a fleet host", "ssh poweredge-xubuntu 'sudo systemctl restart k3s"),
    ("X2 unbalanced quote kubectl delete", "kubectl delete pod 'x"),
    ("X3 unbalanced quote inside remote payload", 'ssh poweredge-xubuntu "sh -c \'sudo x"'),
)

# Legitimate work the guard must NOT block. A false positive here pushes agents
# into working around the guard, which is how hosts get changed by hand anyway.
_ALLOW_CASES = (
    # --- The acceptance criterion's allow half and other read-only reaches ---
    ("R1 kubectl get over ssh", "ssh poweredge-xubuntu 'kubectl get nodes'"),
    ("R2 unquoted kubectl get", "ssh poweredge-xubuntu kubectl get nodes -o wide"),
    ("R3 kubectl describe", "ssh poweredge-xubuntu 'kubectl describe node gmktec-xubuntu'"),
    ("R4 kubectl logs", "ssh poweredge-xubuntu 'kubectl logs -n ns pod'"),
    ("R5 systemctl status", "ssh gmktec-xubuntu 'systemctl status k3s-agent'"),
    ("R6 sudo systemctl status", "ssh gmktec-xubuntu 'sudo systemctl status k3s-agent'"),
    ("R7 sudo journalctl", "ssh gmktec-xubuntu 'sudo journalctl -u k3s-agent -n 50'"),
    ("R8 cat", "ssh hp-xubuntu 'cat /etc/os-release'"),
    ("R9 ls unquoted", "ssh hp-xubuntu ls -la /usr/local/lib/ci-runner-k3s"),
    ("R10 stat", "ssh hp-xubuntu 'stat /usr/local/bin/x'"),
    ("R11 systemctl cat", "ssh hp-xubuntu 'systemctl cat k3s'"),
    ("R12 systemctl is-active", "ssh hp-xubuntu 'systemctl is-active k3s'"),
    ("R13 grep", "ssh hp-xubuntu 'grep -r foo /etc/x'"),
    ("R14 test", "ssh hp-xubuntu 'test -f /etc/x && echo yes'"),
    ("R15 sudo cat", "ssh hp-xubuntu 'sudo cat /etc/rancher/k3s/k3s.yaml'"),
    ("R16 sudo -u user cat", "ssh hp-xubuntu 'sudo -u root cat /etc/x'"),
    ("R17 sudo k3s kubectl get", "ssh poweredge-xubuntu 'sudo k3s kubectl get pods -A'"),
    ("R18 git status", "ssh poweredge-xubuntu 'git -C /opt/x status'"),
    ("R19 uptime after --", "ssh -i key poweredge-xubuntu -- uptime"),
    ("R20 cp out of /etc", "ssh hp-xubuntu 'cp /etc/x /tmp/x'"),
    ("R21 mv within /tmp", "ssh hp-xubuntu 'mv /tmp/a /tmp/b'"),
    ("R22 redirect into /tmp", "ssh hp-xubuntu 'echo x > /tmp/y'"),
    ("R23 k3s check-config", "ssh poweredge-xubuntu 'k3s check-config'"),
    ("R24 systemctl list-units", "ssh vps 'systemctl list-units --type=service'"),
    (
        "R25 heredoc read-only script",
        "ssh poweredge-xubuntu bash -s <<'EOF'\nkubectl get nodes\ncat /etc/x\nEOF",
    ),
    # --- ssh with nothing to judge ----------------------------------------------
    ("I1 interactive", "ssh poweredge-xubuntu"),
    ("I2 -G prints config", "ssh -G poweredge-xubuntu"),
    ("I3 -t only", "ssh -t poweredge-xubuntu"),
    ("I4 empty remote command", "ssh poweredge-xubuntu ''"),
    ("I5 ssh alone", "ssh"),
    ("I6 ssh flag without value", "ssh -p"),
    ("I7 ssh -- alone", "ssh --"),
    # --- Not a fleet host ------------------------------------------------------
    ("H1 other host sudo", "ssh ubuntu@203.0.113.4 'sudo systemctl restart nginx'"),
    ("H2 build box apt", "ssh build-box 'sudo apt install x'"),
    ("H3 github", "ssh -T git@github.com"),
    ("H4 scp upload elsewhere", "scp ./x ubuntu@203.0.113.4:/etc/x"),
    ("H5 rsync upload elsewhere", "rsync -av ./x otherhost:/usr/local/"),
    ("H6 sftp batch elsewhere", "sftp otherhost <<EOF\nput x /etc/x\nEOF"),
    ("H7 substituted target cannot be judged", "ssh $(cat target) 'sudo systemctl restart k3s'"),
    # --- Downloads are reads ------------------------------------------------------
    ("D1 scp download", "scp poweredge-xubuntu:/var/log/syslog ./"),
    ("D2 rsync download", "rsync -av gmktec-xubuntu:/etc/rancher/ ./backup/"),
    ("D3 scp -r download user@host", "scp -r cwoolley@hp-xubuntu:/opt/x/ ./x/"),
    ("D4 rsync local only", "rsync -av ./a ./b"),
    ("D5 scp flags only", "scp -r"),
    ("D6 sftp interactive", "sftp poweredge-xubuntu"),
    ("D7 sftp -b file batch unreadable", "sftp -b batch.txt poweredge-xubuntu"),
    ("D8 sftp read-only heredoc", "sftp poweredge-xubuntu <<EOF\nls /opt\nget /opt/x ./x\n\nEOF"),
    ("D9 sftp flags only", "sftp -v"),
    # --- kubectl reads ----------------------------------------------------------
    ("G1 get nodes", "kubectl get nodes"),
    ("G2 describe", "kubectl describe node x"),
    ("G3 logs", "kubectl logs -n ns pod"),
    ("G4 piped to grep delete", "kubectl get pods -A | grep delete"),
    ("G5 --dry-run=client", "kubectl delete pod x --dry-run=client"),
    ("G6 apply --dry-run=server", "kubectl apply -f x.yaml --dry-run=server"),
    ("G7 selector value", "kubectl get pods -l app=delete"),
    ("G8 kubectl alone", "kubectl"),
    # --- The sanctioned deploy path ----------------------------------------------
    ("P1 just ansible-apply", "just ansible-apply ansible/ci-pool.yml"),
    ("P2 just ansible-drift", "just ansible-drift ansible/ci-pool.yml"),
    ("P3 mise exec just ansible-apply", "mise exec -- just ansible-apply ansible/ci-pool.yml"),
    (
        "P4 uvx ansible-playbook",
        "uvx --from ansible-core==2.21.4 ansible-playbook -i ansible/inventory/legacy.yml "
        "ansible/ci-pool.yml",
    ),
    ("P5 ansible-playbook --check", "ansible-playbook --check --diff -i inv ansible/ci-pool.yml"),
    (
        "P6 apply limited to a fleet host",
        "just ansible-apply ansible/ci-pool.yml -l poweredge-xubuntu",
    ),
    (
        "P7 apply with an extra-var naming a verb",
        "just ansible-apply ansible/ci-pool.yml -e 'x=sudo systemctl restart k3s'",
    ),
    ("P8 ansible ad hoc", "ansible poweredge-xubuntu -m ping"),
    # --- Quoted data, never executed -------------------------------------------
    ("Q1 echo", "echo 'ssh poweredge-xubuntu sudo systemctl restart k3s'"),
    ("Q2 commit message", "git commit -m 'deny ssh poweredge-xubuntu sudo systemctl restart k3s'"),
    ("Q3 grep pattern", 'grep -rn "kubectl delete" .'),
    ("Q4 gh comment body", "gh pr comment 1 --body 'run kubectl delete node x'"),
    (
        "Q5 heredoc written to a file",
        "cat > /tmp/x <<'EOF'\nssh poweredge-xubuntu sudo systemctl restart k3s\nEOF",
    ),
    ("Q6 python string", "python3 -c \"print('kubectl drain x')\""),
    ("Q7 git log grep", "git log --grep='ssh poweredge-xubuntu'"),
    (
        "Q8 ledger comment",
        "bd comment add x -m \"ssh poweredge-xubuntu 'sudo systemctl restart k3s' was denied\"",
    ),
    ("Q9 scp mention in quotes", "echo 'scp x poweredge-xubuntu:/etc/x'"),
    # --- Out of scope by design ---------------------------------------------------
    ("O1 local sudo systemctl", "sudo systemctl restart foo"),
    ("O2 local apt", "sudo apt install x"),
    ("O3 git status", "git status --short"),
    ("O4 ls", "ls -la"),
    ("O5 empty", ""),
    ("O6 operator only", ";"),
    ("O7 unbalanced quote without a hazard hint", "echo 'unterminated"),
    ("O8 bash -c without payload", "bash -c"),
    ("O9 ssh config read", "cat ~/.ssh/config"),
    ("O10 unbalanced quote naming a non-fleet host", "ssh otherhost 'sudo x"),
)


@pytest.mark.parametrize(("label", "command"), _DENY_CASES)
def test_classifier_denies_every_hand_mutation_of_a_fleet_host(label: str, command: str) -> None:
    assert classify(command=command, hosts=_HOSTS) is not None, f"{label}: mutation not denied"


@pytest.mark.parametrize(("label", "command"), _ALLOW_CASES)
def test_classifier_allows_reads_the_sanctioned_apply_and_quoted_mentions(
    label: str, command: str
) -> None:
    assert classify(command=command, hosts=_HOSTS) is None, f"{label}: legitimate command blocked"


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("ssh poweredge-xubuntu 'sudo systemctl restart k3s'", "ssh+systemctl+restart"),
        ("ssh poweredge-xubuntu 'sudo reboot'", "ssh+sudo+reboot"),
        ("ssh poweredge-xubuntu 'sudo -i'", "ssh+sudo+shell"),
        ("ssh poweredge-xubuntu 'echo 1 > /etc/x'", "ssh+redirect-into-protected-tree"),
        ("ssh poweredge-xubuntu 'cp x /etc/x'", "ssh+cp"),
        ("ssh poweredge-xubuntu 'cd /opt/x && git pull'", "ssh+git+pull"),
        ("ssh poweredge-xubuntu 'k3s etcd-snapshot save'", "ssh+k3s+etcd-snapshot"),
        ("scp ./x poweredge-xubuntu:/tmp/x", "scp+upload"),
        ("rsync -av ./x poweredge-xubuntu:/tmp/x", "rsync+upload"),
        ("sftp poweredge-xubuntu <<EOF\nput x\nEOF", "sftp+batch"),
        ("kubectl -n ns delete pod x", "kubectl+delete"),
        ("ssh poweredge-xubuntu 'sudo systemctl restart k3s", "unparseable"),
        ('ssh poweredge-xubuntu "sh -c \'sudo x"', "ssh+unparseable-remote-command"),
    ],
)
def test_the_rule_name_says_which_conjunction_convicted(command: str, rule: str) -> None:
    """The rule is the telemetry column, so its spelling is part of the contract."""
    assert classify(command=command, hosts=_HOSTS) == rule


def test_deep_nesting_terminates_and_denies() -> None:
    """Nesting past the depth budget fails CLOSED: nothing legitimate nests that deep."""
    payload = "ssh poweredge-xubuntu 'sudo systemctl restart k3s'"
    for _ in range(8):
        payload = f"bash -c {shlex.quote(payload)}"
    assert classify(command=payload, hosts=_HOSTS) == "nesting-depth"


def test_depth_budget_exhaustion_denies() -> None:
    assert classify(command="anything at all", hosts=_HOSTS, depth=99) == "nesting-depth"


def test_remote_payload_depth_exhaustion_denies() -> None:
    """The remote-side scan has the same budget as the outer one."""
    payload = "sudo systemctl restart k3s"
    for _ in range(6):
        payload = f"bash -c {shlex.quote(payload)}"
    command = f"ssh poweredge-xubuntu {shlex.quote(payload)}"
    assert classify(command=command, hosts=_HOSTS) == "ssh+nesting-depth"


@pytest.mark.parametrize(
    ("command", "hinted"),
    [
        ("ssh poweredge-xubuntu 'sudo systemctl restart k3s", True),
        ("scp ./x GMKTEC-XUBUNTU:/etc/x", True),
        ("kubectl delete pod 'x", True),
        ("kubectl get pods 'x", False),
        ("ssh otherhost 'sudo x", False),
        ("git status", False),
        ("echo poweredge-xubuntu", False),
    ],
)
def test_hazard_hint_is_a_remote_head_with_a_fleet_host_or_kubectl_with_a_mutation(
    command: str, hinted: bool
) -> None:
    assert hazard_hint(command=command, hosts=_HOSTS) is hinted
