"""Deny/allow corpus for `.claude-plugin/hooks/_host_mutation.py`.

A session ssh'd into two fleet-managed k3s nodes and reasoned about deploying to
them by hand, while the provisioning repository it had been editing states that
the control node is `vps` and `just ansible-apply <playbook>` converges from
committed source. This module pins the classifier that turns that discipline
into a PreToolUse denial, in-process, one case per rule and per evasion family,
plus the false-positive direction: a guard that blocks read-only reaches, the
sanctioned apply, or quoted mentions pushes agents into working around it.

The `R…` blocks are the independent reviewer's 138-probe attack on the first
draft (livespec-driver-claude#750 review, 2026-09-12), every probe kept as a
corpus case under its original label so the evasion it found stays closed.

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
    ("S4 sudo -u root rm", "ssh poweredge-xubuntu 'sudo -u root rm -rf /opt/x'"),
    ("S5 sudo non-read-only head", "ssh poweredge-xubuntu 'sudo reboot'"),
    ("S6 sudo absolute path head", "ssh poweredge-xubuntu 'sudo /usr/local/bin/install-node.sh'"),
    ("S7 sudo unknown wrapper", "ssh poweredge-xubuntu 'sudo nice -n 5 some-tool'"),
    ("S8 sudo sudo", "ssh poweredge-xubuntu 'sudo sudo reboot'"),
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
    ("W11 remote env -i wrapper", "ssh poweredge-xubuntu 'env -i systemctl restart k3s'"),
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
    ("K18 --dry-run bare then value none", "kubectl delete pod x --dry-run none"),
    # --- Parse-hostile but hazard-shaped: must fail CLOSED ----------------------
    ("X1 unbalanced quote to a fleet host", "ssh poweredge-xubuntu 'sudo systemctl restart k3s"),
    ("X2 unbalanced quote kubectl delete", "kubectl delete pod 'x"),
    ("X3 unbalanced quote inside remote payload", 'ssh poweredge-xubuntu "sh -c \'sudo x"'),
    ("X5 empty head token beside a fleet host", "'' ssh poweredge-xubuntu 'sudo reboot'"),
    (
        "X4 backtick target leaves an unresolvable remote head",
        "ssh `cat target` poweredge-xubuntu",
    ),
    ("X6 unresolvable target with no payload at all", "H=poweredge-xubuntu; ssh $H"),
    # --- Reviewer corpus: evasions (livespec-driver-claude#750, 2026-09-12) ------
    (
        "R-E01 for-loop var target",
        "for h in poweredge-xubuntu gmktec-xubuntu; do ssh $h 'sudo systemctl restart k3s'; done",
    ),
    ("R-E02 var target", "H=poweredge-xubuntu; ssh $H 'sudo systemctl restart k3s'"),
    ("R-E03 $(echo host)", "ssh $(echo poweredge-xubuntu) 'sudo systemctl restart k3s'"),
    (
        "R-E04 xargs -I{} host",
        "echo poweredge-xubuntu | xargs -I{} ssh {} 'sudo systemctl restart k3s'",
    ),
    ("R-E05 var head", "S=ssh; $S poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R-E06 quote-split head", "s''sh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R-E07 eval string", "eval \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\""),
    (
        "R-E08 here-string to bash",
        "bash <<< \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\"",
    ),
    ("R-E09 echo | bash", "echo \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\" | bash"),
    ("R-E10 $'...' remote payload", "ssh poweredge-xubuntu $'sudo systemctl restart k3s'"),
    (
        "R-E11 -o RemoteCommand",
        "ssh -o RemoteCommand='sudo systemctl restart k3s' poweredge-xubuntu",
    ),
    (
        "R-E12 -o Hostname= alias",
        "ssh -o Hostname=poweredge-xubuntu anyname 'sudo systemctl restart k3s'",
    ),
    ("R-E13 clustered -tp 22", "ssh -tp 22 poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R-E14 scp:// URI upload", "scp ./unit scp://poweredge-xubuntu/etc/systemd/system/x.service"),
    (
        "R-E15 rsync trailing -e value",
        "rsync -av ./unit poweredge-xubuntu:/etc/systemd/system/ -e 'ssh -p 22'",
    ),
    (
        "R-E16 rsync trailing --rsync-path value",
        "rsync -av ./x poweredge-xubuntu:/etc/x --rsync-path 'sudo rsync'",
    ),
    (
        "R-E17 rsync --remove-source-files download",
        "rsync -av --remove-source-files poweredge-xubuntu:/opt/x ./",
    ),
    (
        "R-E18 sftp -b - from pipe",
        "echo 'put unit.service /etc/systemd/system/' | sftp -b - poweredge-xubuntu",
    ),
    ("R-E19 sftp stdin from printf", "printf 'put x /etc/y\\n' | sftp poweredge-xubuntu"),
    ("R-E20 sftp -put batch", "sftp poweredge-xubuntu <<'EOF'\n-put x /etc/y\nEOF"),
    ("R-E21 sftp PUT uppercase", "sftp poweredge-xubuntu <<'EOF'\nPUT x /etc/y\nEOF"),
    ("R-E22 sftp reput", "sftp poweredge-xubuntu <<'EOF'\nreput x /etc/y\nEOF"),
    ("R-E23 systemctl reboot", "ssh poweredge-xubuntu 'sudo systemctl reboot'"),
    ("R-E24 systemctl poweroff", "ssh poweredge-xubuntu 'sudo systemctl poweroff'"),
    ("R-E25 systemctl kill", "ssh poweredge-xubuntu 'sudo systemctl kill k3s'"),
    ("R-E26 systemctl isolate", "ssh poweredge-xubuntu 'sudo systemctl isolate rescue.target'"),
    (
        "R-E27 systemctl set-property",
        "ssh poweredge-xubuntu 'sudo systemctl set-property k3s CPUQuota=10%'",
    ),
    ("R-E28 systemctl edit", "ssh poweredge-xubuntu 'sudo systemctl edit k3s'"),
    ("R-E29 systemctl revert", "ssh poweredge-xubuntu 'sudo systemctl revert k3s'"),
    ("R-E30 git -C pull", "ssh hp-xubuntu 'git -C /opt/x pull'"),
    ("R-E31 sudo git -C pull", "ssh hp-xubuntu 'sudo git -C /opt/x pull'"),
    ("R-E32 sudo git checkout", "ssh hp-xubuntu 'cd /opt/x && sudo git checkout v2'"),
    (
        "R-E33 sudo git reset --hard",
        "ssh hp-xubuntu 'cd /opt/x && sudo git reset --hard origin/master'",
    ),
    ("R-E34 sudo find -delete", "ssh poweredge-xubuntu 'sudo find /etc/rancher -name x -delete'"),
    (
        "R-E35 sudo find -exec rm",
        "ssh poweredge-xubuntu 'sudo find /var/lib/rancher -exec rm -rf {} +'",
    ),
    ("R-E36 sudo crictl rm", "ssh poweredge-xubuntu 'sudo crictl rm -a -f'"),
    ("R-E37 sudo crictl rmi", "ssh poweredge-xubuntu 'sudo crictl rmi --prune'"),
    ("R-E38 sudo ctr image rm", "ssh poweredge-xubuntu 'sudo ctr -n k8s.io image rm x'"),
    ("R-E39 sudo journalctl --vacuum", "ssh poweredge-xubuntu 'sudo journalctl --vacuum-time=1d'"),
    ("R-E40 sudo kubectl create", "ssh poweredge-xubuntu 'sudo kubectl create ns x'"),
    ("R-E41 kubectl create", "kubectl create ns x"),
    ("R-E42 kubectl replace", "kubectl replace -f x.yaml"),
    ("R-E43 kubectl annotate", "kubectl annotate node x k=v"),
    ("R-E44 kubectl set image", "kubectl set image deploy/x c=img"),
    ("R-E45 kubectl rollout restart", "kubectl rollout restart deploy/x"),
    ("R-E46 kubectl exec rm", "kubectl exec pod -- rm -rf /data"),
    ("R-E47 kubectl uncordon", "kubectl uncordon gmktec-xubuntu"),
    ("R-E48 kubectl run", "kubectl run x --image=busybox"),
    ("R-E49 kubectl expose", "kubectl expose deploy x --port 80"),
    ("R-E50 kubectl certificate approve", "kubectl certificate approve csr-x"),
    ("R-E51 kubectl cp into pod", "kubectl cp ./x pod:/etc/x"),
    (
        "R-E52 kubectl --dry-run twice, last wins none",
        "kubectl delete pod x --dry-run=client --dry-run=none",
    ),
    ("R-E53 helm upgrade", "helm upgrade --install x chart/"),
    ("R-E54 helm install", "helm install x chart/"),
    ("R-E55 sanction leak: rsync dir named ansible", "rsync -av ./ansible poweredge-xubuntu:/opt/"),
    ("R-E56 sanction leak: scp to /etc/ansible", "scp ./hosts poweredge-xubuntu:/etc/ansible"),
    ("R-E57 sanction leak: kubectl delete -f ansible", "kubectl delete -f ansible"),
    (
        "R-E58 sanction leak: extra token ansible",
        "ssh poweredge-xubuntu 'sudo systemctl restart k3s' ansible",
    ),
    (
        "R-E59 ansible ad hoc shell -b",
        "ansible poweredge-xubuntu -m shell -a 'systemctl restart k3s' -b",
    ),
    (
        "R-E60 ansible-playbook of an uncommitted /tmp playbook",
        "ansible-playbook -i inv /tmp/adhoc.yml",
    ),
    (
        "R-E61 fake heredoc marker in a string",
        "echo '<<EOF'\nssh poweredge-xubuntu 'sudo systemctl restart k3s'",
    ),
    (
        "R-E62 heredoc terminator with a dash",
        "cat <<'END-X'\nfoo\nEND-X\nssh poweredge-xubuntu 'sudo systemctl restart k3s'",
    ),
    (
        "R-E63 tmux new-session payload",
        "tmux new -d 'ssh poweredge-xubuntu sudo systemctl restart k3s'",
    ),
    (
        "R-E64 tmux send-keys payload",
        "tmux send-keys -t x 'ssh poweredge-xubuntu sudo systemctl restart k3s' Enter",
    ),
    ("R-E65 watch payload", "watch -n5 'kubectl delete pod x'"),
    (
        "R-E66 script -c payload",
        "script -qc \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\" /dev/null",
    ),
    ("R-E67 curl | sudo sh", "ssh poweredge-xubuntu 'curl -sfL https://get.k3s.io | sudo sh -'"),
    ("R-E68 curl | sh", "ssh poweredge-xubuntu 'curl -sfL https://get.k3s.io | sh -'"),
    ("R-E70 sudo bash -s < script", "ssh -t cwoolley@poweredge-xubuntu sudo bash -s < ./script.sh"),
    ("R-E71 pipeline tee", "echo x | ssh poweredge-xubuntu 'sudo tee /etc/x'"),
    ("R-E73 sudo -- rm", "ssh poweredge-xubuntu 'sudo -- rm -rf /opt/x'"),
    ("R-E74 sudo VAR=1 rm", "ssh poweredge-xubuntu 'sudo X=1 rm -rf /opt/x'"),
    (
        "R-E75 trailing comment hides nothing",
        "ssh poweredge-xubuntu 'sudo systemctl restart k3s' # restart",
    ),
    ("R-E76 mixed-case SSH head", "SSH poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R-E77 k3s-uninstall", "ssh poweredge-xubuntu 'sudo /usr/local/bin/k3s-uninstall.sh'"),
    ("R-E78 k3s-killall", "ssh poweredge-xubuntu 'sudo k3s-killall.sh'"),
    ("R-E79 kubectl apply -k", "kubectl apply -k ci-runner/k3s/"),
    ("R-E80 kubectl --kubeconfig delete", "kubectl --kubeconfig /x -n ns delete pod x"),
    ("R-E81 command prefix", "command ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R-E82 ssh host -- cmd", "ssh poweredge-xubuntu -- sudo systemctl restart k3s"),
    ("R-E83 sudo -E systemctl", "ssh poweredge-xubuntu 'sudo -E systemctl restart k3s'"),
    (
        "R-E84 backslash-newline inside remote",
        "ssh poweredge-xubuntu 'sudo \\\n systemctl restart k3s'",
    ),
    ("R-E85 $(which ssh) head", "$(which ssh) poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R-E86 sudo su -c", "ssh poweredge-xubuntu 'sudo su -c \"systemctl restart k3s\"'"),
    ("R-E87 sudo sh -c mutation", "ssh poweredge-xubuntu 'sudo sh -c \"systemctl restart k3s\"'"),
    ("R-E88 ssh host -l user cmd", "ssh poweredge-xubuntu -l cwoolley sudo systemctl restart k3s"),
    # --- Reviewer corpus, round two: evasions (livespec-driver-claude#750) ------
    (
        "R2-S01 sanctioned then mutation &&",
        "just ansible-apply ansible/ci-pool.yml && ssh poweredge-xubuntu 'sudo systemctl restart "
        "k3s'",
    ),
    (
        "R2-S02 sanctioned then mutation ;",
        "ansible-playbook -i inv ansible/ci-pool.yml; kubectl delete node x",
    ),
    (
        "R2-S03 sanctioned | mutation",
        "just ansible-drift x.yml | ssh poweredge-xubuntu 'sudo tee /etc/x'",
    ),
    (
        "R2-S04 sanctioned with $( ssh mutation )",
        "ansible-playbook site.yml -e \"x=$(ssh poweredge-xubuntu 'sudo systemctl restart k3s')\"",
    ),
    ("R2-S07 playbook ./../x", "ansible-playbook ./../x.yml"),
    ("R2-S08 playbook $PWD/..", "ansible-playbook $PWD/../x.yml"),
    ("R2-S09 playbook /tmp no ext", "ansible-playbook /tmp/adhoc"),
    ("R2-S13 ansible adhoc -bK", "ansible all -m command -a 'systemctl restart k3s' -bK"),
    ("R2-S14 ansible adhoc --become-user", "ansible all -m shell -a 'rm -rf /opt/x' --become"),
    (
        "R2-S17 ansible adhoc -m ansible.builtin.shell",
        "ansible all -m ansible.builtin.shell -a 'systemctl restart k3s' -b",
    ),
    ("R2-S18 ansible adhoc shell no become", "ansible all -m shell -a 'rm -rf ~/x'"),
    (
        "R2-S19 ansible adhoc -m systemd (no -b)",
        "ansible all -m systemd -a 'name=k3s state=restarted'",
    ),
    ("R2-V01 kubectl auth reconcile", "kubectl auth reconcile -f rbac.yaml"),
    (
        "R2-V08 git config write",
        "ssh hp-xubuntu 'sudo git -C /opt/x config receive.denyCurrentBranch ignore'",
    ),
    ("R2-V10 git stash", "ssh hp-xubuntu 'cd /opt/x && sudo git stash'"),
    ("R2-V11 docker exec", "ssh hp-xubuntu 'sudo docker exec c rm -rf /data'"),
    ("R2-V15 tailscale up", "ssh poweredge-xubuntu 'sudo tailscale up --ssh'"),
    ("R2-V16 tailscale set", "ssh poweredge-xubuntu 'sudo tailscale set --advertise-exit-node'"),
    (
        "R2-V22 yq -i in place",
        "ssh poweredge-xubuntu 'sudo yq -i \".x=1\" /etc/rancher/k3s/config.yaml'",
    ),
    ("R2-V23 awk -i inplace", "ssh poweredge-xubuntu 'sudo awk -i inplace 1 /etc/x'"),
    ("R2-V24 date -s", "ssh poweredge-xubuntu 'sudo date -s \"2030-01-01\"'"),
    ("R2-V25 hostname set", "ssh poweredge-xubuntu 'sudo hostname newname'"),
    ("R2-V26 ip netns exec", "ssh poweredge-xubuntu 'sudo ip netns exec x rm -rf /'"),
    ("R2-V27 sysctl --system", "ssh poweredge-xubuntu 'sudo sysctl --system'"),
    (
        "R2-V30 1> redirect inside sudo sh -c",
        "ssh poweredge-xubuntu 'sudo sh -c \"echo 1 1>/etc/sysctl.d/x.conf\"'",
    ),
    ("R2-V31 2> redirect protected", "ssh poweredge-xubuntu 'sudo sh -c \"ls 2>/etc/x\"'"),
    ("R2-V32 >| clobber", "ssh poweredge-xubuntu 'sudo sh -c \"echo 1 >|/etc/x\"'"),
    ("R2-V37 systemctl daemon-reexec", "ssh hp-xubuntu 'sudo systemctl daemon-reexec'"),
    (
        "R2-V40 kubectl delete --dry-run client then none",
        "kubectl delete pod x --dry-run=client --dry-run=none",
    ),
    ("R2-V42 kubectl -n ns apply", "kubectl -n kube-system apply -f x.yaml"),
    ("R2-C01 a#b executed", "env x#y=1 ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R2-C02 $# kept", "echo $#; ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R2-C03 ${#x} kept", "echo ${#x}\nssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    (
        "R2-C09 quoted # then newline",
        "echo '#'\nssh poweredge-xubuntu 'sudo systemctl restart k3s'",
    ),
    ("R2-C10 { #comment", "{ # x\nssh poweredge-xubuntu 'sudo systemctl restart k3s'; }"),
    (
        "R2-P01 cat heredoc | bash",
        "cat <<'EOF' | bash\nssh poweredge-xubuntu 'sudo systemctl restart k3s'\nEOF",
    ),
    (
        "R2-P02 cat heredoc | ssh bash -s",
        "cat <<'EOF' | ssh poweredge-xubuntu bash -s\nsudo systemctl restart k3s\nEOF",
    ),
    (
        "R2-P03 bash heredoc direct",
        "bash <<'EOF'\nssh poweredge-xubuntu 'sudo systemctl restart k3s'\nEOF",
    ),
    ("R2-P04 here-string bash", "bash <<< \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\""),
    ("R2-P05 echo | bash", "echo \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\" | bash"),
    ("R2-P06 printf | sftp", "printf 'put x /etc/y\\n' | sftp poweredge-xubuntu"),
    ("R2-P07 echo put | sftp -b -", "echo 'put x /etc/y' | sftp -b - poweredge-xubuntu"),
    ("R2-P10 echo quoted-split put", "echo 'pu''t x /etc/y' | sftp poweredge-xubuntu"),
    ("R2-P11 eval", "eval \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\""),
    (
        "R2-P12 tmux send-keys",
        "tmux send-keys -t x 'ssh poweredge-xubuntu sudo systemctl restart k3s' Enter",
    ),
    ("R2-P13 tmux new -d", "tmux new -d 'ssh poweredge-xubuntu sudo systemctl restart k3s'"),
    ("R2-P14 watch", "watch -n5 'kubectl delete pod x'"),
    (
        "R2-P15 script -qc",
        "script -qc \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\" /dev/null",
    ),
    ("R2-P18 remote curl | sh", "ssh poweredge-xubuntu 'curl -sfL https://get.k3s.io | sh -'"),
    ("R2-P19 remote cat script | bash (deny bias)", "ssh poweredge-xubuntu 'cat x | bash'"),
    ("R2-P20 xargs kubectl delete", "kubectl get pods -o name | xargs kubectl delete"),
    (
        "R2-P21 xargs -I{} ssh",
        "echo poweredge-xubuntu | xargs -I{} ssh {} 'sudo systemctl restart k3s'",
    ),
    (
        "R2-P22 for loop",
        "for h in poweredge-xubuntu gmktec-xubuntu; do ssh $h 'sudo systemctl restart k3s'; done",
    ),
    ("R2-P23 var head", "S=ssh; $S poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R2-P24 quote-split head", "s''sh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R2-P25 SSH uppercase", "SSH poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R2-X05 remote $CMD head (fail closed)", 'ssh poweredge-xubuntu "$CMD"'),
    ("R2-G01 -tp 22", "ssh -tp 22 poweredge-xubuntu 'sudo systemctl restart k3s'"),
    (
        "R2-G02 -o RemoteCommand",
        "ssh -o RemoteCommand='sudo systemctl restart k3s' poweredge-xubuntu",
    ),
    (
        "R2-G03 -oRemoteCommand=",
        "ssh -oRemoteCommand='sudo systemctl restart k3s' -oRequestTTY=yes poweredge-xubuntu",
    ),
    ("R2-G04 -o HostName", "ssh -o HostName=poweredge-xubuntu alias 'sudo systemctl restart k3s'"),
    (
        "R2-G05 -o hostname lowercase",
        "ssh -o hostname=poweredge-xubuntu alias sudo systemctl restart k3s",
    ),
    (
        "R2-G06 -o 'HostName poweredge-xubuntu' (space form)",
        "ssh -o 'HostName poweredge-xubuntu' alias sudo systemctl restart k3s",
    ),
    ("R2-G07 --  host", "ssh -i k -- poweredge-xubuntu sudo systemctl restart k3s"),
    ("R2-G10 scp:// upload", "scp ./unit scp://poweredge-xubuntu/etc/x"),
    (
        "R2-G11 scp -o after operands (getopt stops)",
        "scp ./x poweredge-xubuntu:/etc/x -o StrictHostKeyChecking=no",
    ),
    ("R2-G12 rsync trailing -e", "rsync -av ./x poweredge-xubuntu:/etc/x -e 'ssh -p 22'"),
    ("R2-G13 rsync -e ssh before", "rsync -e ssh -av ./x poweredge-xubuntu:/etc/x"),
    ("R2-G14 rsync --rsh=ssh", "rsync --rsh=ssh -av ./x poweredge-xubuntu:/etc/x"),
    ("R2-G17 rsync -en?", "rsync -en ./x poweredge-xubuntu:/opt/x"),
    (
        "R2-G18 rsync --remove-source-files download",
        "rsync -av --remove-source-files poweredge-xubuntu:/opt/x ./",
    ),
    ("R2-G19 rsync daemon ::", "rsync -av ./x poweredge-xubuntu::mod/"),
    (
        "R2-G20 rsync --files-from value",
        "rsync -av --files-from list.txt ./ poweredge-xubuntu:/opt/",
    ),
    ("R2-G21 rsync -f value", "rsync -av -f '- *.log' ./x poweredge-xubuntu:/opt/x"),
    ("R2-G23 scp multi source", "scp a b c poweredge-xubuntu:/tmp/"),
    ("R2-G25 scp -3 remote to fleet", "scp -3 other:/x poweredge-xubuntu:/etc/x"),
    ("R2-G26 sftp -put", "sftp poweredge-xubuntu <<'EOF'\n-put x /etc/y\nEOF"),
    ("R2-G27 sftp PUT", "sftp poweredge-xubuntu <<'EOF'\nPUT x /etc/y\nEOF"),
    ("R2-G29 sftp -b - with heredoc", "sftp -b - poweredge-xubuntu <<EOF\nrm /opt/x\nEOF"),
    ("R2-G30 sftp -oPort=22 host heredoc", "sftp -oPort=22 poweredge-xubuntu <<EOF\nput x\nEOF"),
    (
        "R2-G31 ssh ipv6-ish alias",
        "ssh cwoolley@POWEREDGE-XUBUNTU.perch-rudd.ts.net 'sudo systemctl restart k3s'",
    ),
    ("R2-G32 ssh alias ansible_host", "ssh 100.64.0.7 'sudo systemctl restart k3s'"),
    (
        "R2-H01 quoted <<EOF string",
        "echo '<<EOF'\nssh poweredge-xubuntu 'sudo systemctl restart k3s'",
    ),
    (
        "R2-H02 dashed terminator",
        "cat <<'END-X'\nfoo\nEND-X\nssh poweredge-xubuntu 'sudo systemctl restart k3s'",
    ),
    (
        "R2-H07 heredoc to ssh remote script",
        "ssh poweredge-xubuntu <<'EOF'\nsudo systemctl restart k3s\nEOF",
    ),
    (
        "R2-H09 two heredocs, second is remote",
        "cat <<A > /tmp/a\nx\nA\nssh poweredge-xubuntu bash -s <<B\nsudo systemctl restart k3s\nB",
    ),
    # --- Reviewer corpus, round three: evasions and held cases (#750) --------------
    (
        "R3-SC01 sub hides mutation in echo",
        "echo done $(ssh poweredge-xubuntu 'sudo systemctl restart k3s')",
    ),
    (
        "R3-SC02 backtick hides mutation",
        "echo `ssh poweredge-xubuntu 'sudo systemctl restart k3s'`",
    ),
    ("R3-SC03 nested $( $( ) )", "echo $(echo $(ssh poweredge-xubuntu 'sudo reboot'))"),
    (
        "R3-SC04 sub in playbook extra-var",
        "ansible-playbook site.yml -e \"x=$(ssh poweredge-xubuntu 'sudo systemctl restart k3s')\"",
    ),
    ("R3-SC05 sub in quoted arg", 'git commit -m "ran $(kubectl delete node gmktec-xubuntu)"'),
    (
        "R3-SC06 sub inside remote payload",
        'ssh poweredge-xubuntu "echo $(sudo systemctl restart k3s)"',
    ),
    (
        "R3-SC07 sub inside here-doc body to bash",
        "bash <<'EOF'\necho $(ssh poweredge-xubuntu 'sudo reboot')\nEOF",
    ),
    (
        "R3-SC12 unbalanced $( fail? hinted",
        "echo $(ssh poweredge-xubuntu 'sudo systemctl restart k3s'",
    ),
    (
        "R3-SC13 sub then sanctioned inside (mutation after ;)",
        "echo $(just ansible-apply x.yml; ssh poweredge-xubuntu 'sudo reboot')",
    ),
    (
        "R3-SC16 deep nested subs mutation",
        "echo $(echo $(echo $(echo $(ssh poweredge-xubuntu 'sudo reboot'))))",
    ),
    (
        "R3-SC18 sub feeding kubectl delete arg (read of names is fine)",
        "kubectl delete pod $(kubectl get pod -o name)",
    ),
    ("R3-KW01 mutation in for body", "for h in a b; do ssh poweredge-xubuntu 'sudo reboot'; done"),
    (
        "R3-KW02 mutation in case arm",
        "case $x in k3s) ssh poweredge-xubuntu 'sudo systemctl restart k3s';; esac",
    ),
    ("R3-KW03 mutation in if branch", "if true; then ssh poweredge-xubuntu 'sudo reboot'; fi"),
    ("R3-KW04 time ssh mutation", "time ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R3-KW05 ! ssh mutation", "! ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    (
        "R3-KW06 while read; do ssh mutation",
        "while read h; do ssh poweredge-xubuntu 'sudo reboot'; done < hosts",
    ),
    (
        "R3-KW09 remote for restart mutation",
        "ssh poweredge-xubuntu 'for u in k3s containerd; do sudo systemctl restart $u; done'",
    ),
    (
        "R3-KW10 case with data host names then mutation",
        "case $h in poweredge-xubuntu|gmktec-xubuntu) sudo true;; esac; ssh poweredge-xubuntu "
        "'sudo reboot'",
    ),
    (
        "R3-KW12 select menu then mutation",
        "select h in a b; do ssh poweredge-xubuntu 'sudo reboot'; done",
    ),
    ("R3-KW14 coproc", "coproc ssh poweredge-xubuntu 'sudo systemctl restart k3s'"),
    ("R3-GR04 fused subshell mutation", "(ssh poweredge-xubuntu 'sudo reboot')"),
    ("R3-GR05 brace group mutation", "{ ssh poweredge-xubuntu 'sudo reboot'; }"),
    ("R3-GR07 xargs -I{} ssh mutation", "echo poweredge-xubuntu | xargs -I{} ssh {} 'sudo reboot'"),
    ("R3-SA06 uncommitted playbook /tmp", "ansible-playbook /tmp/adhoc.yml"),
    ("R3-SA07 uncommitted playbook ~", "ansible-playbook ~/adhoc.yml"),
    ("R3-SA08 uncommitted .. ", "ansible-playbook ../adhoc.yml"),
    (
        "R3-SA09 sanctioned then ; mutation",
        "just ansible-apply ansible/ci-pool.yml; ssh poweredge-xubuntu 'sudo reboot'",
    ),
    (
        "R3-SA10 sanctioned && mutation",
        "ansible-playbook ansible/ci-pool.yml && kubectl delete node x",
    ),
    ("R3-SA15 uncommitted with $ in path", "ansible-playbook $HOME/adhoc.yml"),
    (
        "R3-CH01 cat heredoc | ssh bash -s",
        "cat <<'EOF' | ssh poweredge-xubuntu bash -s\nsudo systemctl restart k3s\nEOF",
    ),
    ("R3-CH02 cat heredoc | bash", "cat <<'EOF' | bash\nssh poweredge-xubuntu 'sudo reboot'\nEOF"),
    (
        "R3-CH03 cat - <<EOF | ssh",
        "cat - <<'EOF' | ssh poweredge-xubuntu bash -s\nsudo reboot\nEOF",
    ),
    (
        "R3-CH04 cat <<EOF | tee x | ssh bash -s",
        "cat <<'EOF' | tee /tmp/x | ssh poweredge-xubuntu bash -s\nsudo systemctl restart k3s\nEOF",
    ),
    (
        "R3-CH06 three heredocs second feeds ssh",
        "cat <<A > /tmp/a\nx\nA\nssh poweredge-xubuntu bash -s <<B\nsudo reboot\nB\ncat <<C\ny\nC",
    ),
    (
        "R3-SP01 scp upload trailing -o",
        "scp ./x poweredge-xubuntu:/etc/x -o StrictHostKeyChecking=no",
    ),
    ("R3-SP03 scp -P port upload", "scp -P 22 ./x poweredge-xubuntu:/etc/x"),
    ("R3-SP05 scp -r upload", "scp -r dir cwoolley@gmktec-xubuntu:/etc/"),
    ("R3-SP06 scp -3 remote to fleet", "scp -3 other:/x poweredge-xubuntu:/etc/x"),
    ("R3-SP07 scp:// upload", "scp ./x scp://poweredge-xubuntu/etc/x"),
    (
        "R3-SP08 scp -o then upload (leading)",
        "scp -o StrictHostKeyChecking=no ./x poweredge-xubuntu:/etc/x",
    ),
    ("R3-PS01 rm /etc/x", "ssh poweredge-xubuntu 'sudo rm /etc/rancher/x'"),
    (
        "R3-PS03 rm -rf /etc/../tmp/x (escapes protected)",
        "ssh poweredge-xubuntu 'sudo rm -rf /etc/../tmp/x'",
    ),
    ("R3-PS04 mkdir /var/lib/../tmp", "ssh poweredge-xubuntu 'sudo mkdir /var/lib/../tmp/x'"),
    (
        "R3-PS05 cd /etc && rm x (path not visible)",
        "ssh poweredge-xubuntu 'cd /etc && sudo rm k3s.conf'",
    ),
    ("R3-PS07 touch /etc/x", "ssh poweredge-xubuntu 'sudo touch /etc/x'"),
    (
        "R3-PS08 ln -s into /usr/local/bin",
        "ssh poweredge-xubuntu 'sudo ln -s /opt/x /usr/local/bin/x'",
    ),
    ("R3-PS10 dpkg -i", "ssh poweredge-xubuntu 'sudo dpkg -i /tmp/x.deb'"),
    ("R3-PS13 apt-get install", "ssh poweredge-xubuntu 'sudo apt-get install -y x'"),
    ("R3-PS16 apt install", "ssh poweredge-xubuntu 'sudo apt install x'"),
    ("R3-PS18 snap install", "ssh poweredge-xubuntu 'sudo snap install x'"),
    ("R3-PS20 pip install", "ssh hp-xubuntu 'sudo pip install x'"),
    ("R3-PS21 docker compose up", "ssh hp-xubuntu 'sudo docker compose up -d'"),
    ("R3-PS24 docker system prune", "ssh hp-xubuntu 'sudo docker system prune -f'"),
    ("R3-PS27 nft add rule", "ssh poweredge-xubuntu 'sudo nft add rule ip filter input drop'"),
    ("R3-PS28 nft -f file", "ssh poweredge-xubuntu 'sudo nft -f /etc/nftables.conf'"),
    ("R3-PS31 helm upgrade", "helm upgrade --install x chart/"),
    (
        "R3-PS33 k3s secrets-encrypt rotate",
        "ssh poweredge-xubuntu 'sudo k3s secrets-encrypt rotate'",
    ),
    ("R3-PS35 k3s etcd-snapshot save", "ssh poweredge-xubuntu 'sudo k3s etcd-snapshot save'"),
    ("R3-PS37 kubectl auth reconcile", "kubectl auth reconcile -f rbac.yaml"),
    (
        "R3-PS39 git config write",
        "ssh hp-xubuntu 'sudo git -C /opt/x config receive.denyCurrentBranch ignore'",
    ),
    ("R3-PS41 yq -i", "ssh poweredge-xubuntu 'sudo yq -i \".x=1\" /etc/rancher/k3s/config.yaml'"),
    ("R3-PS42 awk -i inplace", "ssh poweredge-xubuntu 'sudo awk -i inplace 1 /etc/x'"),
    ("R3-PS43 date -s", "ssh poweredge-xubuntu 'sudo date -s 2030-01-01'"),
    ("R3-PS45 hostname set", "ssh poweredge-xubuntu 'sudo hostname newname'"),
    ("R3-PS49 mount -a set", "ssh poweredge-xubuntu 'sudo mount -a'"),
    ("R3-PS50 mount device set", "ssh poweredge-xubuntu 'sudo mount /dev/sdb /mnt'"),
    ("R3-PS52 sysctl -w", "ssh poweredge-xubuntu 'sudo sysctl -w net.ipv4.ip_forward=1'"),
    ("R3-PS53 sysctl key=value", "ssh poweredge-xubuntu 'sudo sysctl net.ipv4.ip_forward=1'"),
    ("R3-PS54 sysctl --system", "ssh poweredge-xubuntu 'sudo sysctl --system'"),
    ("R3-PS56 ip route add", "ssh poweredge-xubuntu 'sudo ip route add default via 10.0.0.1'"),
    ("R3-PS57 ip netns exec rm", "ssh poweredge-xubuntu 'sudo ip netns exec x rm -rf /'"),
    ("R3-PS59 iptables -A", "ssh poweredge-xubuntu 'sudo iptables -A INPUT -j DROP'"),
    (
        "R3-RD01 1> into /etc",
        "ssh poweredge-xubuntu 'sudo sh -c \"echo 1 1>/etc/sysctl.d/x.conf\"'",
    ),
    ("R3-RD02 2>> into /etc", "ssh poweredge-xubuntu 'sudo sh -c \"cmd 2>>/etc/x\"'"),
    ("R3-RD03 >| clobber /etc", "ssh poweredge-xubuntu 'sudo sh -c \"echo 1 >|/etc/x\"'"),
    ("R3-RD04 &> /etc", "ssh poweredge-xubuntu 'sudo sh -c \"cmd &>/etc/x\"'"),
    ("R3-RD06 tee /etc via pipe", "ssh poweredge-xubuntu 'echo 1 | sudo tee /etc/x'"),
    ("T1 sudo tee into /etc via pipe", "ssh hp-xubuntu 'echo 1 | sudo tee /etc/x'"),
    ("T2 chown under /usr", "ssh hp-xubuntu 'chown root /usr/local/bin/x'"),
    ("T3 chmod under /etc", "ssh hp-xubuntu 'chmod 600 /etc/rancher/k3s/k3s.yaml'"),
    ("T4 chgrp under /opt", "ssh hp-xubuntu 'chgrp adm /opt/x'"),
    ("T5 nft -f loads a ruleset without a verb", "ssh hp-xubuntu 'sudo nft -f /etc/nftables.conf'"),
    ("T6 mount -a", "ssh hp-xubuntu 'sudo mount -a'"),
    ("T7 mount -o remount", "ssh hp-xubuntu 'sudo mount -o remount,rw /'"),
    (
        "T8 one-line case arm with a mutation",
        "case $x in k3s) ssh poweredge-xubuntu 'sudo systemctl restart k3s';; esac",
    ),
    (
        "T9 here-doc through tee into ssh",
        "cat <<'EOF' | tee /tmp/x | ssh poweredge-xubuntu bash -s\nsudo systemctl restart k3s\nEOF",
    ),
    (
        "T10 here-doc through cat into ssh",
        "cat <<'EOF' | cat | ssh poweredge-xubuntu bash -s\nsudo systemctl restart k3s\nEOF",
    ),
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
    ("R26 bare sudo prints usage", "ssh poweredge-xubuntu sudo"),
    ("R27 echo piped into a remote shell", "ssh poweredge-xubuntu 'echo ls | sh'"),
    ("R28 timeout wrapper around a read", "ssh poweredge-xubuntu 'timeout 5 systemctl status k3s'"),
    ("R29 k3s crictl ps", "ssh poweredge-xubuntu 'sudo k3s crictl ps'"),
    (
        "R30 case patterns are not commands",
        "ssh poweredge-xubuntu 'case $u in k3s) systemctl status k3s;; *) uptime;; esac'",
    ),
    (
        "R31 for-loop word list on the remote side",
        "ssh poweredge-xubuntu 'for u in k3s containerd; do systemctl status $u; done'",
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
    (
        "H7 substituted target with no fleet host named",
        "ssh $(cat target) 'sudo systemctl restart nginx'",
    ),
    ("H8 var target with no fleet host named", "ssh $H 'sudo systemctl restart nginx'"),
    (
        "H9 rsync --remove-source-files elsewhere",
        "rsync -av --remove-source-files otherhost:/opt/x ./",
    ),
    # --- Downloads are reads ------------------------------------------------------
    ("H10 unresolvable upload target with no fleet host named", "scp ./x $H:/etc/x"),
    ("D1 scp download", "scp poweredge-xubuntu:/var/log/syslog ./"),
    ("D2 rsync download", "rsync -av gmktec-xubuntu:/etc/rancher/ ./backup/"),
    ("D3 scp -r download user@host", "scp -r cwoolley@hp-xubuntu:/opt/x/ ./x/"),
    ("D4 rsync local only", "rsync -av ./a ./b"),
    ("D5 scp flags only", "scp -r"),
    ("D6 sftp interactive", "sftp poweredge-xubuntu"),
    ("D7 sftp -b file batch unreadable", "sftp -b batch.txt poweredge-xubuntu"),
    ("D8 sftp read-only heredoc", "sftp poweredge-xubuntu <<EOF\nls /opt\nget /opt/x ./x\n\nEOF"),
    ("D9 sftp flags only", "sftp -v"),
    (
        "D10 sftp -b file with a mutating heredoc it never reads",
        "sftp -b batch.txt poweredge-xubuntu <<EOF\nput x /etc/y\nEOF",
    ),
    # --- kubectl reads ----------------------------------------------------------
    ("G1 get nodes", "kubectl get nodes"),
    ("G2 describe", "kubectl describe node x"),
    ("G3 logs", "kubectl logs -n ns pod"),
    ("G4 piped to grep delete", "kubectl get pods -A | grep delete"),
    ("G5 --dry-run=client", "kubectl delete pod x --dry-run=client"),
    ("G6 apply --dry-run=server", "kubectl apply -f x.yaml --dry-run=server"),
    ("G7 selector value", "kubectl get pods -l app=delete"),
    ("G8 kubectl alone", "kubectl"),
    ("G9 bare --dry-run at the end", "kubectl apply -f x.yaml --dry-run"),
    ("G10 bare --dry-run before a flag", "kubectl apply --dry-run -f x.yaml"),
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
    ("P8 ansible ad hoc ping", "ansible poweredge-xubuntu -m ping"),
    (
        "P9 ansible-playbook --check of an uncommitted playbook is a report",
        "ansible-playbook --check -i inv /tmp/adhoc.yml",
    ),
    ("P10 just drift of an absolute path is still a report", "just ansible-drift /tmp/adhoc.yml"),
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
    (
        "Q10 unquoted echo operands are data",
        "echo ssh poweredge-xubuntu sudo systemctl restart k3s",
    ),
    (
        "Q11 comment line then a read",
        "# ssh poweredge-xubuntu 'sudo systemctl restart k3s' was denied\ngit status",
    ),
    (
        "Q12 trailing comment on a read",
        "git status # next: ssh poweredge-xubuntu sudo systemctl restart k3s",
    ),
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
    ("O11 eval with nothing", "eval"),
    ("O12 tmux without a command operand", "tmux new -d -s work"),
    ("O13 assignment-only segment", "KUBECONFIG=/x"),
    # --- Reviewer corpus: false positives (livespec-driver-claude#750) ------------
    ("R-F01 just ansible-apply", "just ansible-apply ansible/ci-pool.yml"),
    ("R-F02 just ansible-drift", "just ansible-drift ansible/ci-pool.yml"),
    (
        "R-F03 uvx ansible-playbook --check --diff",
        "uvx --from ansible-core==2.21.4 ansible-playbook -i ansible/inventory/legacy.yml "
        "--check --diff ansible/ci-pool.yml",
    ),
    (
        "R-F04 ansible-playbook -l host",
        "ansible-playbook -i ansible/inventory/legacy.yml ansible/ci-pool.yml -l gmktec-xubuntu",
    ),
    ("R-F05 sudo kubectl get -o yaml", "ssh poweredge-xubuntu 'sudo kubectl get nodes -o yaml'"),
    ("R-F06 sudo cat", "ssh poweredge-xubuntu 'sudo cat /etc/rancher/k3s/config.yaml'"),
    ("R-F07 sudo systemctl status", "ssh poweredge-xubuntu 'sudo systemctl status k3s'"),
    ("R-F08 sudo journalctl", "ssh poweredge-xubuntu 'sudo journalctl -u k3s -n 50'"),
    ("R-F09 scp download", "scp poweredge-xubuntu:/etc/x ./local"),
    (
        "R-F10 kubectl reads chained",
        "kubectl get nodes && kubectl describe node x && kubectl logs x && kubectl top nodes && "
        "kubectl version",
    ),
    (
        "R-F11 dry-run pipeline diff",
        "kubectl apply --dry-run=client -o yaml -f x.yaml | kubectl diff -f -",
    ),
    ("R-F12 commit message", "git commit -m 'ssh poweredge-xubuntu sudo systemctl restart k3s'"),
    ("R-F13 grep words", "grep -rn 'ssh poweredge-xubuntu sudo' ."),
    (
        "R-F14 heredoc contains words",
        "cat > /tmp/notes.md <<'EOF'\nssh poweredge-xubuntu 'sudo systemctl restart "
        "k3s'\nkubectl delete node x\nEOF",
    ),
    ("R-F15 unquoted echo", "echo ssh poweredge-xubuntu sudo systemctl restart k3s"),
    (
        "R-F16 comment line in multi-line",
        "# ssh poweredge-xubuntu 'sudo systemctl restart k3s' was denied\ngit status",
    ),
    (
        "R-F17 trailing comment",
        "git status # next: ssh poweredge-xubuntu sudo systemctl restart k3s",
    ),
    ("R-F18 sudo dmesg", "ssh poweredge-xubuntu 'sudo dmesg | tail'"),
    ("R-F19 sudo ss -tlnp", "ssh poweredge-xubuntu 'sudo ss -tlnp'"),
    ("R-F20 sudo iptables -S", "ssh poweredge-xubuntu 'sudo iptables -S'"),
    ("R-F21 sudo lsof -i", "ssh poweredge-xubuntu 'sudo lsof -i :6443'"),
    ("R-F22 sudo tailscale status", "ssh poweredge-xubuntu 'sudo tailscale status'"),
    ("R-F23 sudo docker ps", "ssh hp-xubuntu 'sudo docker ps'"),
    ("R-F24 sudo nvidia-smi", "ssh gmktec-xubuntu 'sudo nvidia-smi'"),
    ("R-F25 sudo -l", "ssh poweredge-xubuntu 'sudo -l'"),
    ("R-F26 sudo -n true", "ssh poweredge-xubuntu 'sudo -n true'"),
    (
        "R-F27 sudo bash -c read-only",
        "ssh poweredge-xubuntu 'sudo bash -c \"cat /etc/x; ls /root\"'",
    ),
    ("R-F28 sudo k3s certificate check", "ssh poweredge-xubuntu 'sudo k3s certificate check'"),
    ("R-F29 sudo less", "ssh poweredge-xubuntu 'sudo less /var/log/syslog'"),
    ("R-F30 sudo lsblk/df", "ssh poweredge-xubuntu 'sudo lsblk; sudo df -h'"),
    ("R-F31 kubectl get pod named delete", "kubectl get pods delete -n x"),
    ("R-F32 kubectl logs in namespace apply", "kubectl logs -n apply x"),
    ("R-F33 kubectl get --show-labels", "kubectl get nodes --show-labels"),
    ("R-F34 kubectl get -l scale=1", "kubectl get pods -l scale=1"),
    ("R-F35 gh pr body", "gh pr create --body 'we ran kubectl delete node x'"),
    ("R-F36 bd comment", 'bd comment add x -m "scp ./x poweredge-xubuntu:/etc/x was denied"'),
    ("R-F37 ssh -G", "ssh -G poweredge-xubuntu"),
    ("R-F38 rsync -n upload", "rsync -avn ./x poweredge-xubuntu:/opt/x"),
    ("R-F39 rsync --dry-run upload", "rsync -av --dry-run ./x poweredge-xubuntu:/opt/x"),
    ("R-F40 ssh vps read", "ssh vps 'systemctl status dolt'"),
    ("R-F41 sudo systemctl list-timers", "ssh vps 'sudo systemctl list-timers'"),
    ("R-F42 sudo systemctl show", "ssh vps 'sudo systemctl show k3s -p ActiveState'"),
    ("R-F43 sudo systemctl is-enabled", "ssh vps 'sudo systemctl is-enabled k3s'"),
    ("R-F44 sudo crictl ps", "ssh poweredge-xubuntu 'sudo crictl ps'"),
    (
        "R-F45 python string",
        "python3 -c \"print('ssh poweredge-xubuntu sudo systemctl restart k3s')\"",
    ),
    ("R-F46 sed of a file containing words", "sed -n '/ssh poweredge-xubuntu/p' notes.md"),
    ("R-F47 rg with fixed string", 'rg -F "scp ./x gmktec-xubuntu:/etc" .'),
    ("R-F48 ssh other host rm", "ssh build-box 'sudo rm -rf /opt/x'"),
    ("R-F49 kubectl explain", "kubectl explain pod.spec"),
    ("R-F50 kubectl auth can-i delete", "kubectl auth can-i delete pods"),
    # --- Known limits, documented in the module docstring: NOT convicted ----------
    (
        "L1 script assembled in another language",
        'python3 -c "import subprocess; '
        "subprocess.run(['ssh','poweredge-xubuntu','sudo','systemctl','restart','k3s'])\"",
    ),
    # --- Reviewer corpus, round two: false positives (livespec-driver-claude#750) ------
    ("R2-S05 bash -c sanctioned", "bash -c 'just ansible-apply ansible/ci-pool.yml'"),
    ("R2-S06 timeout just ansible-apply", "timeout 900 just ansible-apply ansible/ci-pool.yml"),
    (
        "R2-S10 absolute inventory, committed playbook (FP?)",
        "uvx --from ansible-core==2.21.4 ansible-playbook -i "
        "/data/projects/livespec-dev-tooling/ansible/inventory/legacy.yml ansible/ci-pool.yml",
    ),
    (
        "R2-S11 absolute path to committed playbook (FP?)",
        "ansible-playbook -i ansible/inventory/legacy.yml "
        "/data/projects/livespec-dev-tooling/ansible/ci-pool.yml",
    ),
    (
        "R2-S12 just ansible-apply abs committed playbook (FP?)",
        "just ansible-apply /data/projects/livespec-dev-tooling/ansible/ci-pool.yml",
    ),
    ("R2-S15 ansible adhoc setup (read)", "ansible poweredge-xubuntu -m setup"),
    ("R2-S16 ansible adhoc ping", "ansible all -m ping"),
    ("R2-V02 kubectl config set-context (local)", "kubectl config use-context k3s"),
    ("R2-V03 kubectl wait", "kubectl wait --for=condition=Ready node/x"),
    ("R2-V04 kubectl get --raw", "kubectl get --raw /healthz"),
    ("R2-V05 helm template", "helm template x chart/"),
    ("R2-V06 helm upgrade --dry-run (FP?)", "helm upgrade --install x chart/ --dry-run"),
    ("R2-V07 helm diff plugin (FP?)", "helm diff upgrade x chart/"),
    ("R2-V09 git config --get", "ssh hp-xubuntu 'git -C /opt/x config --get remote.origin.url'"),
    ("R2-V12 docker container ls (FP?)", "ssh hp-xubuntu 'sudo docker container ls'"),
    ("R2-V13 docker compose ps (FP?)", "ssh hp-xubuntu 'sudo docker compose ps'"),
    ("R2-V14 docker system df (FP?)", "ssh hp-xubuntu 'sudo docker system df'"),
    ("R2-V17 dpkg -l (FP?)", "ssh poweredge-xubuntu 'sudo dpkg -l | grep k3s'"),
    ("R2-V18 dpkg -s (FP?)", "ssh poweredge-xubuntu 'dpkg -s curl'"),
    ("R2-V19 apt list (FP?)", "ssh poweredge-xubuntu 'sudo apt list --installed'"),
    ("R2-V20 snap list (FP?)", "ssh poweredge-xubuntu 'snap list'"),
    ("R2-V21 mount listing (FP?)", "ssh poweredge-xubuntu 'mount | grep nfs'"),
    ("R2-V28 iptables-save (FP?)", "ssh poweredge-xubuntu 'sudo iptables-save'"),
    ("R2-V29 nft list ruleset (FP?)", "ssh poweredge-xubuntu 'sudo nft list ruleset'"),
    (
        "R2-V33 k3s secrets-encrypt status (FP?)",
        "ssh poweredge-xubuntu 'sudo k3s secrets-encrypt status'",
    ),
    ("R2-V34 k3s etcd-snapshot ls (FP?)", "ssh poweredge-xubuntu 'sudo k3s etcd-snapshot ls'"),
    ("R2-V35 crictl image (alias of images) (FP?)", "ssh poweredge-xubuntu 'sudo crictl image'"),
    ("R2-V36 systemctl --user status", "ssh hp-xubuntu 'systemctl --user status fabro-server'"),
    ("R2-V38 mkdir user scratch (design?)", "ssh hp-xubuntu 'mkdir -p /tmp/probe'"),
    ("R2-V39 pip list (FP?)", "ssh hp-xubuntu 'pip list'"),
    (
        "R2-V41 kubectl --dry-run none then client",
        "kubectl delete pod x --dry-run=none --dry-run=client",
    ),
    ("R2-V43 kubectl get pods delete", "kubectl get pods delete -n x"),
    ("R2-V44 kubectl logs -n apply", "kubectl logs -n apply x"),
    ("R2-V45 kubectl auth can-i delete", "kubectl auth can-i delete pods"),
    ("R2-V46 sudo journalctl -u k3s -n 50", "ssh poweredge-xubuntu 'sudo journalctl -u k3s -n 50'"),
    ("R2-V47 sudo grep -i", "ssh hp-xubuntu 'sudo grep -i error /var/log/syslog'"),
    ("R2-V48 sudo cat -s", "ssh hp-xubuntu 'sudo cat -s /etc/x'"),
    (
        "R2-C04 comment line",
        "# ssh poweredge-xubuntu 'sudo systemctl restart k3s' was denied\ngit status",
    ),
    (
        "R2-C05 trailing comment",
        "git status # next: ssh poweredge-xubuntu sudo systemctl restart k3s",
    ),
    ("R2-C06 comment after ;", "git status; # ssh poweredge-xubuntu sudo systemctl restart k3s"),
    ("R2-C07 grep ^#", "ssh hp-xubuntu 'grep -v ^# /etc/x'"),
    ("R2-C08 awk -F#", "ssh hp-xubuntu \"awk -F# '{print}' /etc/x\""),
    (
        "R2-C11 remote comment hides sudo (correct allow)",
        "ssh poweredge-xubuntu 'echo hi # ; sudo systemctl restart k3s'",
    ),
    ("R2-P08 echo ls | sftp (read)", "echo 'ls /opt' | sftp poweredge-xubuntu"),
    ("R2-P09 cat batch | sftp (unreadable)", "cat batch.txt | sftp poweredge-xubuntu"),
    (
        "R2-P16 tmux send-keys read-only",
        "tmux send-keys -t x 'ssh poweredge-xubuntu kubectl get nodes' Enter",
    ),
    ("R2-P17 tmux ls", "tmux -L x ls"),
    (
        "R2-P26 loop over unknown hosts (limit)",
        "for h in $(cat hosts); do ssh $h 'sudo systemctl restart k3s'; done",
    ),
    (
        "R2-X01 read ssh with $(date) in outer redirect (FP?)",
        "ssh poweredge-xubuntu 'kubectl get nodes' > /tmp/nodes-$(date +%s).txt",
    ),
    (
        "R2-X02 scp download with $(date) (FP?)",
        "scp poweredge-xubuntu:/var/log/syslog ./syslog-$(date +%F)",
    ),
    (
        "R2-X03 remote journalctl --since $(date) (FP?)",
        "ssh poweredge-xubuntu \"sudo journalctl -u k3s --since '$(date -d yesterday +%F)'\"",
    ),
    ("R2-X04 remote echo $HOME", "ssh poweredge-xubuntu 'echo $HOME; kubectl get pods -n $NS'"),
    ("R2-X06 backtick in read", "ssh poweredge-xubuntu 'ls `pwd`'"),
    ("R2-G08 ssh -G read", "ssh -G poweredge-xubuntu"),
    ("R2-G09 ssh -W", "ssh -W poweredge-xubuntu:22 vps"),
    ("R2-G15 rsync -n upload", "rsync -avn ./x poweredge-xubuntu:/opt/x"),
    ("R2-G16 rsync -e ssh -n (n after e cluster?)", "rsync -avne ssh ./x poweredge-xubuntu:/opt/x"),
    ("R2-G22 rsync --dry-run=? n/a", "rsync -av --dry-run ./x poweredge-xubuntu:/opt/x"),
    ("R2-G24 scp download multi", "scp poweredge-xubuntu:/a poweredge-xubuntu:/b ./"),
    ("R2-G28 sftp -b file", "sftp -b batch.txt poweredge-xubuntu"),
    (
        "R2-H03 heredoc body data",
        "cat > /tmp/x <<'EOF'\nssh poweredge-xubuntu 'sudo systemctl restart k3s'\nEOF",
    ),
    (
        "R2-H04 <<- tab terminator",
        "cat <<-EOF\n\tssh poweredge-xubuntu sudo systemctl restart k3s\n\tEOF",
    ),
    ("R2-H05 here-string not heredoc", "grep -c x <<< 'ssh poweredge-xubuntu'\ngit status"),
    (
        "R2-H06 dotted terminator (deny bias)",
        "cat <<'E.O.F'\nssh poweredge-xubuntu 'sudo systemctl restart k3s'\nE.O.F",
    ),
    (
        "R2-H08 heredoc to ssh read-only",
        "ssh poweredge-xubuntu <<'EOF'\nkubectl get nodes\ncat /etc/x\nEOF",
    ),
    # --- Reviewer corpus, round three: false positives and held cases (#750) ------
    (
        "R3-SC08 ${VAR} param expansion is NOT a sub (read)",
        'ssh poweredge-xubuntu "kubectl get pods -n ${NS}"',
    ),
    ("R3-SC09 $(date) benign", "kubectl get pods > /tmp/pods-$(date +%s).txt"),
    (
        "R3-SC10 backtick benign date",
        "ssh poweredge-xubuntu 'systemctl status k3s' > log-`date +%F`",
    ),
    (
        "R3-SC11 sub in single quotes is literal (bash)",
        "echo '$(ssh poweredge-xubuntu sudo reboot)'",
    ),
    ("R3-SC14 sub contains only sanctioned", "echo $(just ansible-apply ansible/ci-pool.yml)"),
    ("R3-SC15 sub with mutation, target var (fail closed?)", "echo $(ssh $H 'sudo reboot')"),
    (
        "R3-SC17 arithmetic $(( )) not a command",
        "echo $((1+2)); ssh poweredge-xubuntu kubectl get nodes",
    ),
    (
        "R3-KW07 for read-only over fleet",
        "for h in poweredge-xubuntu gmktec-xubuntu; do ssh $h 'systemctl status k3s'; done",
    ),
    (
        "R3-KW08 remote for status read",
        "ssh poweredge-xubuntu 'for u in k3s containerd; do systemctl status $u; done'",
    ),
    ("R3-KW11 for-in as a value word 'in'", "ssh poweredge-xubuntu 'kubectl get pods -n in'"),
    ("R3-KW13 keyword-named host? do=host (unlikely)", "ssh do 'sudo reboot'"),
    ("R3-GR01 fused subshell read", "(ssh poweredge-xubuntu 'kubectl get nodes')"),
    ("R3-GR02 spaced subshell read", "( ssh poweredge-xubuntu 'kubectl get nodes' )"),
    ("R3-GR03 brace group read", "{ ssh poweredge-xubuntu 'kubectl get nodes'; }"),
    ("R3-GR06 genuine empty literal head", "'' poweredge-xubuntu sudo reboot"),
    ("R3-GR08 xargs {} literal in read", "ssh poweredge-xubuntu 'find /tmp -name {} -print'"),
    ("R3-GR09 nested braces read", "{ { ssh poweredge-xubuntu 'kubectl get nodes'; }; }"),
    ("R3-GR10 subshell pipe read", "(ssh poweredge-xubuntu 'kubectl get nodes') | grep Ready"),
    (
        "R3-SA01 -i uncommitted inventory (playbook committed)",
        "ansible-playbook -i /tmp/hosts ansible/ci-pool.yml",
    ),
    ("R3-SA02 -e @/tmp/vars.yml", "ansible-playbook -e @/tmp/vars.yml ansible/ci-pool.yml"),
    (
        "R3-SA03 --extra-vars carrying playbook path",
        "ansible-playbook --extra-vars playbook=/tmp/x.yml ansible/ci-pool.yml",
    ),
    ("R3-SA04 -l host", "ansible-playbook ansible/ci-pool.yml -l poweredge-xubuntu"),
    ("R3-SA05 --limit host", "ansible-playbook ansible/ci-pool.yml --limit gmktec-xubuntu"),
    (
        "R3-SA11 abs committed playbook (into checkout)",
        "just ansible-apply /data/projects/livespec-dev-tooling/ansible/ci-pool.yml",
    ),
    (
        "R3-SA12 -i abs legacy.yml committed playbook",
        "uvx --from ansible-core==2.21.4 ansible-playbook -i "
        "/data/projects/livespec-dev-tooling/ansible/inventory/legacy.yml ansible/ci-pool.yml",
    ),
    ("R3-SA13 --check uncommitted (read)", "ansible-playbook --check /tmp/adhoc.yml"),
    ("R3-SA14 just ansible-drift", "just ansible-drift ansible/ci-pool.yml"),
    ("R3-SA16 -e non-file var ok", "ansible-playbook -e env=prod ansible/ci-pool.yml"),
    ("R3-CH05 cat FILE | ssh (unreadable)", "cat script.sh | ssh poweredge-xubuntu bash -s"),
    (
        "R3-CH07 cat heredoc read-only | ssh",
        "cat <<'EOF' | ssh poweredge-xubuntu bash -s\nkubectl get nodes\nEOF",
    ),
    (
        "R3-CH08 cat heredoc | ssh (read host non-fleet)",
        "cat <<'EOF' | ssh otherhost bash -s\nsudo reboot\nEOF",
    ),
    (
        "R3-SP02 scp download trailing -o",
        "scp poweredge-xubuntu:/etc/x ./local -o StrictHostKeyChecking=no",
    ),
    ("R3-SP04 scp download", "scp poweredge-xubuntu:/var/log/syslog ./"),
    ("R3-PS02 rm /tmp/x (scratch)", "ssh poweredge-xubuntu 'rm /tmp/x'"),
    ("R3-PS06 mkdir /tmp scratch", "ssh poweredge-xubuntu 'mkdir -p /tmp/probe'"),
    ("R3-PS09 rm $HOME/x no sudo", "ssh poweredge-xubuntu 'rm -rf ~/x'"),
    ("R3-PS11 dpkg -I info", "ssh poweredge-xubuntu 'dpkg -I /tmp/x.deb'"),
    ("R3-PS12 dpkg -l", "ssh poweredge-xubuntu 'sudo dpkg -l | grep k3s'"),
    ("R3-PS14 apt-cache show", "ssh poweredge-xubuntu 'apt-cache show curl'"),
    ("R3-PS15 apt list", "ssh poweredge-xubuntu 'sudo apt list --installed'"),
    ("R3-PS17 snap list", "ssh poweredge-xubuntu 'snap list'"),
    ("R3-PS19 pip list", "ssh hp-xubuntu 'pip list'"),
    ("R3-PS22 docker compose ps", "ssh hp-xubuntu 'sudo docker compose ps'"),
    ("R3-PS23 docker container ls", "ssh hp-xubuntu 'sudo docker container ls'"),
    ("R3-PS25 docker system df", "ssh hp-xubuntu 'sudo docker system df'"),
    ("R3-PS26 nft list ruleset", "ssh poweredge-xubuntu 'sudo nft list ruleset'"),
    ("R3-PS29 helm upgrade --dry-run", "helm upgrade --install x chart/ --dry-run"),
    ("R3-PS30 helm diff", "helm diff upgrade x chart/"),
    (
        "R3-PS32 k3s secrets-encrypt status",
        "ssh poweredge-xubuntu 'sudo k3s secrets-encrypt status'",
    ),
    ("R3-PS34 k3s etcd-snapshot ls", "ssh poweredge-xubuntu 'sudo k3s etcd-snapshot ls'"),
    ("R3-PS36 crictl image (bare lists)", "ssh poweredge-xubuntu 'sudo crictl image'"),
    ("R3-PS38 kubectl auth can-i", "kubectl auth can-i delete pods"),
    ("R3-PS40 git config --get", "ssh hp-xubuntu 'git -C /opt/x config --get remote.origin.url'"),
    ("R3-PS44 date read", "ssh poweredge-xubuntu 'date +%s'"),
    ("R3-PS46 hostname read", "ssh poweredge-xubuntu 'hostname'"),
    ("R3-PS47 hostname -I read", "ssh poweredge-xubuntu 'hostname -I'"),
    ("R3-PS48 mount listing (no operand)", "ssh poweredge-xubuntu 'mount | grep nfs'"),
    ("R3-PS51 sysctl read", "ssh poweredge-xubuntu 'sysctl net.ipv4.ip_forward'"),
    ("R3-PS55 ip addr read", "ssh poweredge-xubuntu 'ip addr show'"),
    ("R3-PS58 iptables -L read", "ssh poweredge-xubuntu 'sudo iptables -L'"),
    ("R3-PS60 iptables-save read", "ssh poweredge-xubuntu 'sudo iptables-save > /tmp/rules'"),
    ("R3-RD05 > /tmp scratch", "ssh poweredge-xubuntu 'echo 1 > /tmp/x'"),
    ("T11 tee into scratch", "ssh hp-xubuntu 'kubectl get nodes | tee /tmp/nodes.log'"),
    ("T12 chmod in scratch", "ssh hp-xubuntu 'chmod +x /tmp/probe.sh'"),
    ("T13 chown in home", "ssh hp-xubuntu 'chown cwoolley ~/x'"),
    (
        "T14 one-line case arm with a read",
        "case $x in k3s) ssh poweredge-xubuntu 'systemctl status k3s';; esac",
    ),
    ("T15 one-line case with no arm body", "case $x in k3s) ;; esac"),
    ("T16 mount listing by type", "ssh hp-xubuntu 'mount -t nfs'"),
    ("T17 nft list through -a", "ssh hp-xubuntu 'sudo nft -a list ruleset'"),
    ("T18 echo through cat into a remote read", "echo ls | cat | ssh poweredge-xubuntu bash -s"),
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
        ("ssh poweredge-xubuntu 'sudo reboot'", "ssh+reboot"),
        ("ssh poweredge-xubuntu 'sudo some-tool'", "ssh+sudo+some-tool"),
        ("ssh poweredge-xubuntu 'sudo -i'", "ssh+sudo+shell"),
        ("ssh poweredge-xubuntu 'echo 1 > /etc/x'", "ssh+redirect-into-protected-tree"),
        ("ssh poweredge-xubuntu 'cp x /etc/x'", "ssh+cp"),
        ("ssh poweredge-xubuntu 'cd /opt/x && git pull'", "ssh+git+pull"),
        ("ssh poweredge-xubuntu 'k3s etcd-snapshot save'", "ssh+k3s+etcd-snapshot+save"),
        ("ssh poweredge-xubuntu 'curl x | sh -'", "ssh+piped-shell"),
        ("scp ./x poweredge-xubuntu:/tmp/x", "scp+upload"),
        ("rsync -av ./x poweredge-xubuntu:/tmp/x", "rsync+upload"),
        (
            "rsync -av --remove-source-files poweredge-xubuntu:/opt/x ./",
            "rsync+remove-source-files",
        ),
        ("sftp poweredge-xubuntu <<EOF\nput x\nEOF", "sftp+batch"),
        ("kubectl -n ns delete pod x", "kubectl+delete"),
        ("helm upgrade --install x chart/", "helm+upgrade"),
        ("ansible poweredge-xubuntu -m shell -a x -b", "ansible+adhoc"),
        ("ansible-playbook -i inv /tmp/adhoc.yml", "ansible-playbook+uncommitted-playbook"),
        ("just ansible-apply ~/adhoc.yml", "ansible-apply+uncommitted-playbook"),
        ("ssh poweredge-xubuntu 'sudo systemctl restart k3s", "unparseable"),
        ('ssh poweredge-xubuntu "sh -c \'sudo x"', "ssh+unparseable-remote-command"),
        ("ssh $(echo poweredge-xubuntu) 'sudo x'", "unresolvable-target"),
        ("echo $(ssh poweredge-xubuntu 'sudo x')", "ssh+sudo+x"),
        (
            "ansible-playbook site.yml -e \"x=$(ssh poweredge-xubuntu 'sudo reboot')\"",
            "ssh+reboot",
        ),
        (
            "ssh poweredge-xubuntu 'for u in k3s containerd; do systemctl restart $u; done'",
            "ssh+systemctl+restart",
        ),
        (
            "ssh poweredge-xubuntu 'sudo sh -c \"echo 1 >|/etc/x\"'",
            "ssh+redirect-into-protected-tree",
        ),
        ("H=poweredge-xubuntu; ssh $H 'sudo x'", "unresolvable-target"),
        ("S=ssh; $S poweredge-xubuntu 'sudo x'", "unresolvable-command"),
        ("echo poweredge-xubuntu | xargs -I{} scp ./x {}:/etc/x", "unresolvable-target"),
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
        ("helm uninstall 'x", True),
        ("kubectl get pods 'x", False),
        ("ssh otherhost 'sudo x", False),
        ("git status", False),
        ("echo poweredge-xubuntu", False),
    ],
)
def test_hazard_hint_is_a_remote_head_with_a_fleet_host_or_a_cluster_head_with_a_mutation(
    command: str, hinted: bool
) -> None:
    assert hazard_hint(command=command, hosts=_HOSTS) is hinted
