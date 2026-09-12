#!/usr/bin/env python3
"""
fleet_host_guard - PreToolUse hook denying hand mutation of fleet-managed hosts.

Declared in hooks.json on the `Bash` tool. This hook denies a command that
would change a fleet-managed host BY HAND, outside the committed provisioning:

- a mutating `ssh` / `scp` / `rsync` / `sftp` whose target is a fleet host
  (a `sudo`, `install`, `tee`, `chmod`, a `cp` into `/etc`, a
  `systemctl restart`, an upload, …);
- a cluster-mutating `kubectl`/`helm` (`apply`, `patch`, `taint`, `delete`,
  `cordon`, `drain`, `label`, `edit`, `scale`, `create`, `rollout`, … — every
  verb that is not a read);
- an ad hoc `ansible --become`, or a playbook run from outside the committed
  tree.

The sanctioned path stays allowed and is THE answer the deny reason gives:
`just ansible-drift <playbook>` reports, `just ansible-apply <playbook>`
converges, from the control node over committed source. Read-only reaches
(`ssh <host> 'kubectl get nodes'`, `journalctl`, `systemctl status`, `cat`)
stay allowed, as does anything aimed at a host that is not in the fleet set.

This module owns the hook BOUNDARY only — reading the PreToolUse payload from
stdin, resolving the governed project's fleet host set and its
`.ai/gitops-deployment*.md` topic, emitting the deny decision and the verdict
record, and always exiting 0. The verdict itself comes from the sibling
`_host_mutation` module, whose docstring documents the deny matrix, the allow
list, the wrapper-prefix scan, and the known limits; `_fleet_inventory`
documents how the host set is read from the provisioning inventory rather
than hardcoded.

Fail-closed safety: ANY parsing or main-loop failure on a command that carries
the hazard hints (a remote-shell head together with a fleet host name, or
`kubectl` together with a mutating verb) emits a deny decision. Commands
without those hints fail open silently with exit 0 — the guard acts only on
POSITIVE identification, per the Driver-shipped-hooks footgun discipline.

Telemetry: every IN-SCOPE command (one whose lexed tokens carry a remote-shell
or cluster head, or that looks like a fleet-host mutation) publishes one
verdict record through `_guard_telemetry`, on the allow path as well as the
deny path, so "how often does this guard convict a read-only reach" is a
dataset query. The record carries the rule and where the host set came from —
never the command, never a host name. Emission happens AFTER the decision has
been written to stdout, so a raising exporter cannot change the verdict: the
boundary sees the verdict is already settled and writes nothing more.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from _fleet_inventory import FALLBACK_HOSTS, resolve_fleet_hosts
from _guard_telemetry import emit_guard_verdict
from _host_mutation import classify, hazard_hint, in_scope

__all__: list[str] = []

_GUARD = "fleet_host_guard"
_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
_TOPIC_GLOB = "gitops-deployment*.md"
_GENERIC_TOPIC = (
    "the governed project's `.ai/gitops-deployment*.md` topic (fleet-canonical "
    "statement: livespec `.ai/gitops-deployment-discipline.md`)"
)


@dataclass(frozen=True, kw_only=True)
class _Verdict:
    """What the guard decided and what, if anything, telemetry should record."""

    decision: str | None
    rule: str | None
    host_source: str | None


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    """Narrow an arbitrary JSON value to a string-keyed dict, else None."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _project_dir() -> str:
    return os.environ.get(_PROJECT_DIR_ENV, "").strip()


def _topic_reference(*, project_dir: str) -> str:
    """Name the project's own GitOps topic file when it has one, else the generic route."""
    if project_dir:
        matches = sorted((Path(project_dir) / ".ai").glob(_TOPIC_GLOB))
        if matches:
            return f"`.ai/{matches[0].name}`"
    return _GENERIC_TOPIC


def _deny_reason(*, rule: str, topic: str) -> str:
    return (
        f"BLOCKED by fleet_host_guard.py ({rule}): this command would change a "
        "fleet-managed host BY HAND. No live host is changed by hand — a deploy is a "
        "git change plus the committed apply, run from the control node over committed "
        "source: `just ansible-drift <playbook>` reports the drift, `just ansible-apply "
        "<playbook>` converges (livespec-dev-tooling/ansible/). If the committed "
        "automation cannot do what you need, that is a gap in the role or playbook to "
        "FIX, never a reason to do it by hand and never a task for the maintainer. "
        "Read-only reaches (`ssh <host> 'kubectl get nodes'`, `systemctl status`, "
        f"`journalctl`, `cat`) stay allowed. Read {topic} before any host or infra action."
    )


def _deny_decision(*, rule: str, topic: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": _deny_reason(rule=rule, topic=topic),
            }
        }
    )


def _bash_command(*, raw: str) -> str | None:
    payload = _as_object_dict(value=json.loads(raw))
    if payload is None or payload.get("tool_name") != "Bash":
        return None
    tool_input = _as_object_dict(value=payload.get("tool_input"))
    if tool_input is None:
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None
    return command


def _verdict(*, raw: str) -> _Verdict:
    """Decide; `host_source` is set only when the command is in scope for telemetry."""
    command = _bash_command(raw=raw)
    if command is None:
        return _Verdict(decision=None, rule=None, host_source=None)
    project_dir = _project_dir()
    fleet = resolve_fleet_hosts(project_dir=project_dir or None)
    rule = classify(command=command, hosts=fleet.hosts)
    decision = (
        None
        if rule is None
        else _deny_decision(rule=rule, topic=_topic_reference(project_dir=project_dir))
    )
    counted = rule is not None or in_scope(command=command, hosts=fleet.hosts)
    return _Verdict(decision=decision, rule=rule, host_source=fleet.source if counted else None)


def _has_hazard_hint(*, raw: str) -> bool:
    """The fail-closed trigger, judged against the fallback set — resolution may be what failed."""
    return hazard_hint(command=raw, hosts=FALLBACK_HOSTS)


def main() -> int:
    """Guard entry point: deny hinted hazards even when classification fails; exit 0."""
    raw = ""
    settled = False
    try:
        raw = sys.stdin.read()
        verdict = _verdict(raw=raw)
        if verdict.decision is not None:
            _ = sys.stdout.write(verdict.decision + "\n")
        settled = True
        # Only now, with the verdict on the wire: a failure here costs the record.
        if verdict.host_source is not None:
            emit_guard_verdict(
                guard=_GUARD,
                matched_rule=verdict.rule,
                attributes={"host_source": verdict.host_source},
            )
    except Exception:  # noqa: BLE001 — sole fail-closed guard boundary: deny per policy, exit 0
        if not settled and _has_hazard_hint(raw=raw):
            with contextlib.suppress(OSError):
                decision = _deny_decision(rule="classification-failure", topic=_GENERIC_TOPIC)
                _ = sys.stdout.write(decision + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
