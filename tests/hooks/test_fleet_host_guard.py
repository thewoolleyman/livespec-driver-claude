"""Unit tests for `.claude-plugin/hooks/fleet_host_guard.py`.

The hook body is exercised IN-PROCESS via its importable `main() -> int`
(swapped `sys.stdin`, stdout/stderr via `redirect_stdout`/`redirect_stderr`)
for real per-file coverage, plus ONE retained subprocess smoke that proves
the shipped script still speaks the PreToolUse stdin/stdout protocol.

Contract under test (work-item livespec-ggs36t, livespec
`plan/gitops-deployment-discipline/research/000-…` section 3):

- DENY a positively-identified mutating `ssh`/`scp`/`rsync`/`sftp` to a fleet
  host, and a cluster-mutating `kubectl`, with a reason that routes to the
  governed project's `.ai/gitops-deployment*.md` topic and names the
  sanctioned `just ansible-drift` / `just ansible-apply` path.
- ALLOW the sanctioned apply, read-only reaches, non-fleet targets, and quoted
  mentions; the host set comes from the project's inventory, never from code.
- FAIL CLOSED when a raw command carries the hazard hints but classification
  raises; otherwise fail open silently.
- Emit one telemetry verdict per IN-SCOPE command, after the decision.

Every command below is INERT DATA fed to the hook on stdin. Nothing here runs
`ssh`, `scp`, `rsync`, `sftp`, or `kubectl`, and nothing may be changed to do so.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
_HOOK_SCRIPT = _HOOKS_DIR / "fleet_host_guard.py"
_ENDPOINT_ENV = "LIVESPEC_SANDBOX_OTEL_ENDPOINT"
_MUTATION = "ssh poweredge-xubuntu 'sudo systemctl restart k3s'"
_READ = "ssh poweredge-xubuntu 'kubectl get nodes'"


@dataclass(frozen=True, kw_only=True)
class HookResult:
    returncode: int
    stdout: str
    stderr: str


def _load_hook() -> ModuleType:
    assert _HOOK_SCRIPT.is_file()
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("fleet_host_guard", None)
    return importlib.import_module("fleet_host_guard")


def _bash_input(*, command: str, tool_name: str = "Bash") -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})


def _run_loaded(*, hook: ModuleType, stdin: str) -> HookResult:
    old_stdin = sys.stdin
    stdout = StringIO()
    stderr = StringIO()
    try:
        sys.stdin = StringIO(stdin)
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = hook.main()
    finally:
        sys.stdin = old_stdin
    return HookResult(returncode=returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def _run(*, stdin: str) -> HookResult:
    return _run_loaded(hook=_load_hook(), stdin=stdin)


def _run_hook_subprocess(*, stdin: str) -> subprocess.CompletedProcess[str]:
    # The offline telemetry endpoint the autouse fixture pins MUST travel into
    # the child, or the smoke publishes a synthetic verdict to the live receiver.
    return subprocess.run(
        ["python3", str(_HOOK_SCRIPT)],
        input=stdin,
        env={"PATH": os.environ["PATH"], _ENDPOINT_ENV: os.environ[_ENDPOINT_ENV]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _reason(*, result: HookResult | subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    decision = payload["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert result.stderr == ""
    reason = decision["permissionDecisionReason"]
    assert isinstance(reason, str)
    return reason


def _assert_denied(*, result: HookResult | subprocess.CompletedProcess[str]) -> None:
    reason = _reason(result=result)
    assert "BLOCKED by fleet_host_guard.py" in reason
    assert "just ansible-drift <playbook>" in reason
    assert "just ansible-apply <playbook>" in reason
    assert "gitops-deployment" in reason


def _assert_silent(*, result: HookResult | subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.fixture(name="no_project")
def no_project_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


@pytest.mark.usefixtures("no_project")
@pytest.mark.parametrize(
    "command",
    [
        _MUTATION,
        "ssh poweredge-xubuntu sudo systemctl restart k3s",
        "timeout 30 ssh cwoolley@gmktec-xubuntu 'sudo apt-get install -y x'",
        "mise exec -- ssh hp-xubuntu 'echo x | sudo tee /etc/y'",
        "scp ./unit poweredge-xubuntu:/etc/systemd/system/x.service",
        "rsync -av --delete ./x gmktec-xubuntu:/opt/x",
        "sftp poweredge-xubuntu <<'EOF'\nput unit.service /etc/systemd/system/\nEOF",
        "kubectl delete node gmktec-xubuntu",
        "kubectl -n kube-system apply -f x.yaml",
        "bash -c \"ssh poweredge-xubuntu 'sudo systemctl restart k3s'\"",
        "ssh poweredge-xubuntu bash -s <<'EOF'\nsudo systemctl restart k3s\nEOF",
        "ssh poweredge-xubuntu 'sudo systemctl restart k3s",
        # The head is found on lexed tokens, not on raw text: no regex prefilter to evade.
        "s''sh poweredge-xubuntu 'sudo systemctl restart k3s'",
        "SSH poweredge-xubuntu 'sudo systemctl restart k3s'",
        "H=poweredge-xubuntu; ssh $H 'sudo systemctl restart k3s'",
    ],
)
def test_denies_hand_mutation_of_a_fleet_host(command: str) -> None:
    _assert_denied(result=_run(stdin=_bash_input(command=command)))


@pytest.mark.usefixtures("no_project")
@pytest.mark.parametrize(
    "command",
    [
        _READ,
        "ssh gmktec-xubuntu 'sudo journalctl -u k3s-agent -n 50'",
        "ssh hp-xubuntu 'systemctl status k3s'",
        "ssh poweredge-xubuntu",
        "scp poweredge-xubuntu:/var/log/syslog ./",
        "ssh ubuntu@203.0.113.4 'sudo systemctl restart nginx'",
        "kubectl get nodes",
        "kubectl delete pod x --dry-run=client",
        "just ansible-apply ansible/ci-pool.yml",
        "just ansible-drift ansible/ci-pool.yml",
        "uvx --from ansible-core==2.21.4 ansible-playbook --check -i inv ansible/ci-pool.yml",
        "echo 'ssh poweredge-xubuntu sudo systemctl restart k3s'",
        "git commit -m 'deny ssh poweredge-xubuntu sudo systemctl restart k3s'",
        "cat > /tmp/x <<'EOF'\nkubectl delete node x\nEOF",
        "git status",
        "echo 'unterminated",
        "git status # next: ssh poweredge-xubuntu sudo systemctl restart k3s",
        "ssh poweredge-xubuntu 'sudo journalctl -u k3s -n 50'",
    ],
)
def test_allows_reads_the_sanctioned_apply_and_quoted_mentions(command: str) -> None:
    _assert_silent(result=_run(stdin=_bash_input(command=command)))


def test_subprocess_smoke_denies_a_mutating_ssh() -> None:
    """The shipped script path still speaks the PreToolUse hook protocol."""
    _assert_denied(result=_run_hook_subprocess(stdin=_bash_input(command=_MUTATION)))


def test_hook_manifest_loads_guard_for_bash_pre_tool_use() -> None:
    manifest = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    bash_entries = [
        entry for entry in manifest["hooks"]["PreToolUse"] if entry.get("matcher") == "Bash"
    ]
    assert len(bash_entries) == 1
    commands = [hook["command"] for hook in bash_entries[0]["hooks"]]
    assert 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/fleet_host_guard.py"' in commands


# --- The deny reason routes to the project's GitOps topic ---------------------


def test_reason_names_the_projects_own_gitops_topic_when_it_has_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = tmp_path / "governed"
    (project / ".ai").mkdir(parents=True)
    _ = (project / ".ai" / "gitops-deployment.md").write_text("# topic\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))

    reason = _reason(result=_run(stdin=_bash_input(command=_MUTATION)))

    assert "Read `.ai/gitops-deployment.md` before any host or infra action" in reason


def test_reason_falls_back_to_the_fleet_canonical_topic_when_the_project_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = tmp_path / "governed"
    project.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))

    reason = _reason(result=_run(stdin=_bash_input(command=_MUTATION)))

    assert "`.ai/gitops-deployment*.md`" in reason
    assert "livespec `.ai/gitops-deployment-discipline.md`" in reason


def test_reason_names_the_rule_that_convicted() -> None:
    reason = _reason(result=_run(stdin=_bash_input(command="kubectl drain x")))
    assert "(kubectl+drain)" in reason


# --- The host set is read from the inventory ---------------------------------


def test_host_set_comes_from_the_projects_inventory_not_from_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = tmp_path / "governed"
    (project / "ansible" / "inventory").mkdir(parents=True)
    inventory = "all:\n  hosts:\n    node-alpha:\n      ansible_host: 100.64.0.42\n"
    _ = (project / "ansible" / "inventory" / "legacy.yml").write_text(inventory, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))

    _assert_denied(result=_run(stdin=_bash_input(command="ssh node-alpha 'sudo reboot'")))
    _assert_denied(result=_run(stdin=_bash_input(command="ssh 100.64.0.42 'sudo reboot'")))
    # A fallback-only name is NOT a fleet host once a real inventory is in force.
    _assert_silent(result=_run(stdin=_bash_input(command=_MUTATION)))


# --- Telemetry: one record per in-scope command, after the decision ------------


@dataclass(frozen=True, kw_only=True)
class _Emitted:
    guard: str
    matched_rule: str | None
    attributes: dict[str, str | bool]


def _capture_telemetry(*, hook: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[_Emitted]:
    emitted: list[_Emitted] = []

    def _record(*, guard: str, matched_rule: str | None, attributes: dict[str, str | bool]) -> None:
        emitted.append(_Emitted(guard=guard, matched_rule=matched_rule, attributes=attributes))

    monkeypatch.setattr(hook, "emit_guard_verdict", _record)
    return emitted


@pytest.mark.usefixtures("no_project")
def test_a_deny_emits_the_rule_and_the_host_source(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    emitted = _capture_telemetry(hook=hook, monkeypatch=monkeypatch)

    _assert_denied(result=_run_loaded(hook=hook, stdin=_bash_input(command=_MUTATION)))

    assert emitted == [
        _Emitted(
            guard="fleet_host_guard",
            matched_rule="ssh+systemctl+restart",
            attributes={"host_source": "fallback"},
        )
    ]


@pytest.mark.usefixtures("no_project")
def test_an_in_scope_allow_emits_a_none_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    emitted = _capture_telemetry(hook=hook, monkeypatch=monkeypatch)

    _assert_silent(result=_run_loaded(hook=hook, stdin=_bash_input(command=_READ)))

    assert [record.matched_rule for record in emitted] == [None]


@pytest.mark.usefixtures("no_project")
@pytest.mark.parametrize(
    "command",
    ["git status", "git status # ssh poweredge-xubuntu", "echo 'ssh x'"],
)
def test_an_out_of_scope_command_emits_nothing(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    """`git status` pays no POST: nothing could convict it, so nothing is counted."""
    hook = _load_hook()
    emitted = _capture_telemetry(hook=hook, monkeypatch=monkeypatch)

    _assert_silent(result=_run_loaded(hook=hook, stdin=_bash_input(command=command)))

    assert emitted == []


@pytest.mark.usefixtures("no_project")
def test_a_quote_split_head_is_still_in_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    emitted = _capture_telemetry(hook=hook, monkeypatch=monkeypatch)

    _assert_silent(result=_run_loaded(hook=hook, stdin=_bash_input(command="s''sh -G build-box")))

    assert [record.matched_rule for record in emitted] == [None]


@pytest.mark.usefixtures("no_project")
@pytest.mark.parametrize(("command", "denied"), [(_MUTATION, True), (_READ, False)])
def test_a_telemetry_failure_never_flips_the_verdict(
    monkeypatch: pytest.MonkeyPatch, command: str, denied: bool
) -> None:
    """The verdict is settled before emission; a raising exporter costs the record only."""
    hook = _load_hook()

    def _broken(*, guard: str, matched_rule: str | None, attributes: dict[str, str | bool]) -> None:
        raise RuntimeError(f"{guard} {matched_rule} {attributes}")

    monkeypatch.setattr(hook, "emit_guard_verdict", _broken)
    result = _run_loaded(hook=hook, stdin=_bash_input(command=command))
    if denied:
        _assert_denied(result=result)
    else:
        _assert_silent(result=result)


# --- Boundary: pass-through shapes and the fail-closed rule -------------------


def test_ignores_non_bash_tool() -> None:
    _assert_silent(result=_run(stdin=_bash_input(command=_MUTATION, tool_name="Write")))


def test_silent_on_empty_stdin() -> None:
    _assert_silent(result=_run(stdin=""))


def test_silent_on_malformed_json() -> None:
    _assert_silent(result=_run(stdin="{not valid json"))


def test_allows_non_mapping_payload() -> None:
    _assert_silent(result=_run(stdin="[]"))


def test_allows_missing_tool_input() -> None:
    _assert_silent(result=_run(stdin=json.dumps({"tool_name": "Bash"})))


def test_allows_missing_command() -> None:
    _assert_silent(result=_run(stdin=json.dumps({"tool_name": "Bash", "tool_input": {}})))


def test_fail_closes_when_classify_raises_with_hazard_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()

    def broken_classify(*, command: str, hosts: frozenset[str]) -> str | None:
        raise ValueError(f"{command} {sorted(hosts)}")

    monkeypatch.setattr(hook, "classify", broken_classify)
    reason = _reason(result=_run_loaded(hook=hook, stdin=_bash_input(command=_MUTATION)))
    assert "(classification-failure)" in reason


def test_fails_open_when_classify_raises_without_hazard_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = _load_hook()

    def broken_classify(*, command: str, hosts: frozenset[str]) -> str | None:
        raise ValueError(f"{command} {sorted(hosts)}")

    monkeypatch.setattr(hook, "classify", broken_classify)
    _assert_silent(result=_run_loaded(hook=hook, stdin=_bash_input(command="kubectl get nodes")))


def test_fail_closes_when_host_resolution_raises_with_hazard_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolution may be what failed, so the hint is judged against the fallback set."""
    hook = _load_hook()

    def broken_resolve(*, project_dir: str | None) -> object:
        raise OSError(project_dir)

    monkeypatch.setattr(hook, "resolve_fleet_hosts", broken_resolve)
    _assert_denied(result=_run_loaded(hook=hook, stdin=_bash_input(command=_MUTATION)))


def test_main_fails_open_when_decision_raises_without_hazard_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = _load_hook()

    def broken_verdict(*, raw: str) -> object:
        raise ValueError(raw)

    monkeypatch.setattr(hook, "_verdict", broken_verdict)
    _assert_silent(result=_run_loaded(hook=hook, stdin=_bash_input(command="git status")))
