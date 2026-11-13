---
topic: fleet-route-guard-refuse-tailscale
author: claude-fable-5-2:homelab-k8s-worker-nodes
created_at: 2026-11-12T19:07:43Z
---

## Proposal: Bind the fleet route guard into the Driver's hook bundle as a Bash-matched guard in the one dispatcher

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Add the fleet route guard to the Driver's hook bundle as a fifth upstream-required hook. This proposal states only the Driver's binding: the guard is a Bash-matched PreToolUse guard, the one dispatcher evaluates it in-process, its module is `fleet_route_guard.py`, and its tests live under `tests/hooks/`. The guard's behaviour (what it refuses, what it allows, what each refusal names, its telemetry and its fail-open posture) is stated by livespec core in `livespec/SPECIFICATION/contracts.md` §"Driver-shipped hooks", paragraph "Fleet route guard (required)", which livespec#3191 (topic `driver-fleet-route-guard`) proposes. This proposal cites that paragraph and does not restate it.

### Motivation

Maintainer direction, 2026-11-12, relayed through plan homelab-k8s-worker-nodes (livespec-dev-tooling epic livespec-dev-tooling-ko26ez): "update the hooks to catch this, do it now as part of your plan". Work item livespec-driver-claude-bmacrp carries the implementation. Its pre-dispatch screen placed it at the spec-change tier, because §"Hook bundle" lists the hooks the bundle carries and no ratified clause names this guard.

What happened. On 2026-11-12 a session on one fleet host tried to reach another fleet machine with a bare `ssh <machine>` and with a `tailscale ssh <account>@<machine>`. The first logs in under the calling host's own account name, which is not an account on the target. The second fails, because the target cannot host a Tailscale SSH server. The session recorded that no agent route to the machine existed, and a host-side plan step sat blocked for about eight hours. The documented route was in the `tailscale-admin` repository's machine table throughout. The maintainer rejected a managed `~/.ssh/config` as the fix, so a guard has to teach the right command at the moment the wrong one is typed.

Order of ratification. Core's §"Driver-shipped hooks" closes with: "Adding or removing a hook in the Driver bundle, renaming a hook surface, or changing a hook's posture (block vs. warn) requires a propose-change cycle against this section." This repository's §"Hook bundle" repeats that rule and says the hooks' behavioural disciplines and postures are owned upstream. So core ratifies livespec#3191 first, and this proposal's revise follows it. If the core paragraph changes at its revise, this proposal needs no change, because it cites the paragraph and copies none of it.

Ports. livespec#3191 makes the Codex and pi ports REQUIRED, each in its own Driver. They are separate work in the livespec-driver-codex and livespec-driver-pi repositories and are not part of this proposal.

Why a separate guard and not a rule of `fleet_host_guard.py`. Core's fleet-host mutation guard paragraph says that guard "acts only on a POSITIVE identification of one of the denials stated above" and that "A read-only reach MUST NOT be denied". A wrong-route `ssh <machine> true` is a read-only reach, so that guard cannot refuse it. The mutation guard is also declared fail-closed; the route guard is fail-open. Inside the dispatcher the two therefore have different failure boundaries, which is a Driver wiring fact and is stated below.

One process. The guard adds no HOOK process to a Bash tool call: the dispatcher evaluates it in-process. The guard itself runs `ssh -G <host>` as a child process when it has to read the SSH client's resolved configuration (core's rule 2), so "no process" would be wrong.

Three guards the bundle already ships (`github_rate_limit_guard.py`, `tmux_fleet_guard.py`, `block_raw_bd_create.py`) appear in neither this section's list nor core's; that existing drift is out of this proposal's scope.

### Proposed Changes

All clause changes are in `SPECIFICATION/contracts.md` §"Hook bundle". The dispatcher sentences are unchanged: they already cover every Bash-matched guard and already give a fail-open guard's failure as an allow for that guard alone.

**Change 1.** Replace the sentence

> The bundle carries four upstream-required hooks:

with:

> The bundle carries five upstream-required hooks:

**Change 2.** Insert this list item after the primary-checkout Playwright guard item and before the plan-persistence item:

> - a **PreToolUse** fleet route guard (`fleet_route_guard.py`), a
>   Bash-matched guard with no other matcher. Its behavioral discipline
>   and posture (the wrong SSH routes it refuses, what each refusal
>   names, its allowances, its telemetry record and its advisory
>   fail-open posture) are owned by livespec core's Driver-shipped-hooks
>   contract, paragraph "Fleet route guard (required)"; this Driver owns
>   the Python module, its membership of the dispatcher, and its
>   executable coverage under `tests/hooks/`. The dispatcher MUST
>   evaluate it in-process with the other Bash-matched guards, so it adds
>   no hook process to a Bash tool call, and inside the dispatcher its
>   failure is an allow for this guard alone. It is a separate module
>   from the fleet-host mutation guard (`fleet_host_guard.py`) and MUST
>   NOT share that guard's refusal reason;

**Change 3.** In the closing paragraph of §"Hook bundle", replace the sentence

> The dispatch order and the membership of the dispatcher, among the hooks the bundle already carries, are Driver implementation detail under that same rule, provided the one-process and per-guard failure-posture properties above hold.

with:

> The dispatch order and the membership of the dispatcher, among the hooks the bundle already carries, are Driver implementation detail under that same rule, provided the one-process and per-guard failure-posture properties above hold. The fleet route guard is the stated exception on membership: the dispatcher MUST evaluate it.

**Change 4.** In `SPECIFICATION/scenarios.md`, add these two scenarios after "## Scenario: a crashing fail-closed guard inside the PreToolUse dispatcher still refuses the call". They state Driver wiring only; the behaviour scenarios are core's. The machine, account and domain are placeholders.

## Scenario: the fleet route guard refuses a wrong route through the one PreToolUse dispatcher

```gherkin
Given a livespec-governed project whose installed Driver bundle registers one PreToolUse entry point on the Bash matcher
And a tailnet record that documents machine "examplehost" with SSH account "opsuser", an OpenSSH server and no Tailscale SSH server
And a local Tailscale client that reports the tailnet domain "example-tailnet.ts.net"
When the agent makes a Bash tool call running "tailscale ssh opsuser@examplehost true"
Then the dispatcher refuses the call before the command runs
And the refusal reason is byte-identical to the reason `fleet_route_guard.py` gives when run standalone against the same payload
And no hook process other than the dispatcher was started for the call
```

## Scenario: a crashing fleet route guard inside the PreToolUse dispatcher does not refuse the call

```gherkin
Given a livespec-governed project whose installed Driver bundle registers one PreToolUse entry point on the Bash matcher
And the fleet route guard raises while it evaluates the call
When the agent makes a Bash tool call that no other guard refuses
Then the dispatcher allows the call
And every other Bash-matched guard's decision is unchanged
```

**Co-edit owed at revise.** The revise that accepts this proposal MUST add one `tests/heading-coverage.json` entry per new scenario heading in the same commit (`spec_file: "scenarios.md"`, `test: "TODO"`, `work_item: "livespec-driver-claude-bmacrp"`, and a `reason` that names the tier the owed test runs at and that work item, for example "A real test at the integration tier (hook boundary) is owed for this heading; livespec-driver-claude-bmacrp owns it."), and MUST regenerate `tests/heading-coverage-debt.json`.
