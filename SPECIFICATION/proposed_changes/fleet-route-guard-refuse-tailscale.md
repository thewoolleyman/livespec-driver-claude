---
topic: fleet-route-guard-refuse-tailscale
author: claude-fable-5-2:homelab-k8s-worker-nodes
created_at: 2026-11-12T19:07:43Z
---

## Proposal: Add an advisory fleet route guard that refuses a wrong SSH route to a tailnet machine and names the documented one

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Add one Bash-matched PreToolUse guard to the Driver's hook bundle, the fleet route guard. It refuses a `tailscale ssh` to a machine the tailnet record documents with no Tailscale SSH server, and an `ssh`, `scp`, `rsync` or `sftp` to a recorded machine under an account other than the one the record documents. Each refusal names the documented command or account and the record. The guard is advisory and fail-open, has its own refusal text, and runs inside the one PreToolUse dispatcher process. The owning work item is livespec-driver-claude-bmacrp.

### Motivation

Maintainer direction, 2026-11-12, relayed through plan homelab-k8s-worker-nodes (livespec-dev-tooling epic livespec-dev-tooling-ko26ez): "update the hooks to catch this, do it now as part of your plan". Work item livespec-driver-claude-bmacrp carries the behaviour as six Definition-of-Done assertions. Its pre-dispatch screen held it at the spec-change tier, because §"Hook bundle" lists the hooks the bundle carries and no ratified clause states this guard. This proposal supplies that clause and states exactly the item's behaviour.

What happened. On 2026-11-12 a session on the VPS ran `ssh macbook-m4-max` and `tailscale ssh cwoolley@macbook-m4-max`. The first logs in under the VPS's own account name, which is not an account on that Mac. The second fails with "No ED25519 host key is known ... strict checking", because the macOS GUI Tailscale client cannot host a Tailscale SSH server. The session recorded "NO agent route to the macbook-m4-max host exists", a coordinator carried the ask to the maintainer, and a host-side plan step sat blocked for about eight hours. The working route, `ssh cwoolley@macbook-m4-max.perch-rudd.ts.net`, was in the `tailscale-admin` repository's machine table throughout. The maintainer rejected a managed `~/.ssh/config` as the fix ("We are not going to maintain manual ssh auth"), so the guard has to teach the right command at the moment the wrong one is typed. The companion agent guidance is `.ai/fleet-host-ssh-routes.md` in livespec-dev-tooling.

Why a separate guard and not a rule of `fleet_host_guard.py`. livespec core's fleet-host mutation guard paragraph says that guard "acts only on a POSITIVE identification of one of the denials stated above" and that "A read-only reach MUST NOT be denied". A wrong-route `ssh host true` is a read-only reach, so that guard cannot refuse it without breaking its own upstream contract. The mutation guard is also a declared fail-closed guard whose reason names the GitOps deployment discipline. A wrong route is not a hand mutation, and this rule fails open. So it is a separate guard with its own refusal text and its own failure posture.

A livespec core proposal is owed, and this proposal does not file it. Core's `contracts.md` §"Driver-shipped hooks" closes with: "Adding or removing a hook in the Driver bundle, renaming a hook surface, or changing a hook's posture (block vs. warn) requires a propose-change cycle against this section." This repository's §"Hook bundle" repeats that rule, and also says the hooks' behavioural disciplines and postures are owned upstream. This proposal adds a hook, so by both texts a core propose-change cycle against §"Driver-shipped hooks" is owed for the fleet route guard. The revise that decides this proposal has to weigh that: the text below states the guard's discipline in this repository and marks it as the one hook whose discipline this section states, so the Driver clause is complete on its own, and the core cycle then decides whether core takes the discipline over. Three guards the bundle already ships (`github_rate_limit_guard.py`, `tmux_fleet_guard.py`, `block_raw_bd_create.py`) appear in neither list; that existing drift is out of this proposal's scope.

Codex and pi ports are not owed by core's current text. Core requires a port only where a paragraph says so, as "Codex fleet-host mutation guard (required)" and "pi fleet-host mutation guard (required)" do for the mutation guard, and it says runtime-specific hooks "share behavior where their contracts say so, not bytes". No core paragraph names a route guard, so no port is required today. The wrong route is typed the same way from any runtime, so the owed core proposal is where ports get decided; they become owed only if that cycle requires them.

Project scope. Core's hook failure discipline says hooks "MUST NOT disturb non-livespec projects ... with the fleet-host mutation guard the one stated exception". This proposal claims no second exception, so the guard passes through outside a livespec-governed project. The item resolves the tailnet record as a sibling of the governed project, which fits.

The tailnet record is the `tailscale-admin` repository's `README.md` machine table (columns Machine, IP, OS, Tags, SSH account, SSH server, Role). The clause names no machine, account or tailnet; the guard reads them from the record. Machine names in the scenarios are examples.

### Proposed Changes

All clause changes are in `SPECIFICATION/contracts.md` §"Hook bundle". The paragraph "The bundle carries four upstream-required hooks:" and its four list items are unchanged: the new guard is not upstream-required, so it is stated in its own paragraph after the list. The dispatcher sentences are unchanged: they already cover every Bash-matched guard and already give a fail-open guard's failure as an allow for that guard alone.

**Change 1.** Replace the sentence

> The bundle's *existence and wiring* are this repo's contract; the hooks' *behavioral disciplines and postures* (the fail-open requirement, block-vs-warn, the gating predicates) are owned upstream by `livespec/SPECIFICATION/contracts.md`, which this repo realizes.

with:

> The bundle's *existence and wiring* are this repo's contract; the hooks' *behavioral disciplines and postures* (the fail-open requirement, block-vs-warn, the gating predicates) are owned upstream by `livespec/SPECIFICATION/contracts.md`, which this repo realizes. The one hook whose discipline this section states itself is the fleet route guard in the paragraph after the list below.

**Change 2.** Insert this paragraph after the list of four hooks and before the paragraph beginning "Adding or removing a hook":

> **Fleet route guard.** The bundle also carries a **PreToolUse** fleet route guard, a Bash-matched guard that refuses a wrong SSH route to a tailnet machine before the command runs and names the documented route. Work item livespec-driver-claude-bmacrp owns its implementation. The guard MUST be a Bash-matched guard with no other matcher, and the dispatcher MUST evaluate it in-process with the other Bash-matched guards, so it adds no process to a Bash tool call. It is a separate guard from the fleet-host mutation guard (`fleet_host_guard.py`): it has its own refusal reason, and that reason MUST NOT present a wrong route as a hand mutation or name the GitOps deployment discipline.
>
> *The tailnet record.* The guard reads the machine table of the `tailscale-admin` repository's `README.md`, which gives each machine's name, its SSH account and its SSH server. It MUST resolve that repository as a sibling clone of the governed project, or of the primary checkout when the session runs in a linked worktree. The guard MUST NOT hardcode any machine name, account name, tailnet name or tailnet domain; it MUST read each from the record. A **recorded machine** is a command target that equals, in full or by its first DNS label compared case-insensitively, a machine name in the table, and whose row gives the documented SSH account and SSH server the rule in question needs.
>
> *Rule 1, a `tailscale ssh` to a machine with no Tailscale SSH server.* The guard MUST deny a Bash `tailscale ssh` whose target is a recorded machine that the record documents with no Tailscale SSH server. The refusal reason MUST name the working command, `ssh <documented account>@<host>.<tailnet domain>`, filled in from the record.
>
> *Rule 2, a wrong login account.* The guard MUST deny a Bash `ssh`, `scp`, `rsync` or `sftp` to a recorded machine whose effective login account differs from the SSH account the record documents for that machine. The refusal reason MUST name the documented account. The effective login account MUST be read from an explicit `user@` on the target, else from `-l <user>`, else from the SSH client's own resolved configuration for that host (the `user` that `ssh -G <host>` prints locally, without connecting). A host that the caller's SSH configuration already maps to the documented account MUST therefore be allowed.
>
> *Allowed.* A command that reaches a recorded machine with its documented account and method MUST NOT be denied by this guard. A command whose target is not a recorded machine MUST NOT be denied by this guard.
>
> *Every refusal names the record.* Every refusal reason of this guard MUST name the tailnet record as the place where each machine's SSH account and SSH server are documented.
>
> *Posture: advisory and fail-open.* The guard acts only on a POSITIVE identification of rule 1 or rule 2. It MUST allow a command it cannot parse, a command whose effective login account it cannot determine, and a target whose record entry it cannot classify. When the tailnet record cannot be read (the sibling clone is absent, the file is unreadable, or no machine table can be read from it), the guard MUST deny nothing, and its verdict record for the command MUST state that no record answered. Any other failure of the guard is an allow under the default fail-open discipline, and inside the dispatcher it is an allow for this guard alone. Under upstream's rule that hooks do not disturb non-livespec projects, the guard MUST pass through when the project is not livespec-governed.
>
> How the guard reads a command (segments, wrapper prefixes, option grammar), how it classifies the wording of an SSH server entry, and its place in the dispatch order are Driver detection internals, provided the denials, allowances and posture stated here hold.

**Change 3.** In the closing paragraph of §"Hook bundle", replace the sentence

> The dispatch order and the membership of the dispatcher, among the hooks the bundle already carries, are Driver implementation detail under that same rule, provided the one-process and per-guard failure-posture properties above hold.

with:

> The dispatch order and the membership of the dispatcher, among the hooks the bundle already carries, are Driver implementation detail under that same rule, provided the one-process and per-guard failure-posture properties above hold. The fleet route guard is the stated exception on membership: the dispatcher MUST evaluate it.

**Change 4.** In `SPECIFICATION/scenarios.md`, add these five scenarios after "## Scenario: a crashing fail-closed guard inside the PreToolUse dispatcher still refuses the call". The machine, account and domain in them are examples read from the record, not rules.

## Scenario: a tailscale ssh to a machine with no Tailscale SSH server is refused with the working command

```gherkin
Given the tailnet record documents machine "macbook-m4-max" with SSH account "cwoolley" and an SSH server entry that lists no Tailscale SSH server
When the agent makes a Bash tool call running "tailscale ssh cwoolley@macbook-m4-max true"
Then the fleet route guard refuses the call before the command runs
And the refusal names the working command "ssh cwoolley@macbook-m4-max.perch-rudd.ts.net"
And the refusal names the tailnet record as the place where each machine's SSH account and SSH server are documented
```

## Scenario: an ssh to a recorded machine under the wrong account is refused with the documented account

```gherkin
Given the tailnet record documents machine "macbook-m4-max" with SSH account "cwoolley"
And the caller's SSH configuration resolves the login account for that host to "ubuntu"
When the agent makes a Bash tool call running "ssh macbook-m4-max true"
Then the fleet route guard refuses the call before the command runs
And the refusal names the documented account "cwoolley"
And the refusal names the tailnet record as the place where each machine's SSH account and SSH server are documented
```

## Scenario: an ssh to a recorded machine with its documented account is allowed

```gherkin
Given the tailnet record documents machine "macbook-m4-max" with SSH account "cwoolley" and an SSH server entry that lists no Tailscale SSH server
When the agent makes a Bash tool call running "ssh cwoolley@macbook-m4-max.perch-rudd.ts.net true"
Then the fleet route guard does not refuse the call
```

## Scenario: an ssh to a host the caller's SSH configuration maps to the documented account is allowed

```gherkin
Given the tailnet record documents machine "macbook-m4-max" with SSH account "cwoolley"
And the caller's SSH configuration resolves the login account for that host to "cwoolley"
When the agent makes a Bash tool call running "ssh macbook-m4-max true"
Then the fleet route guard does not refuse the call
```

## Scenario: an unreadable tailnet record makes the fleet route guard allow the call and record that no record answered

```gherkin
Given the tailnet record cannot be read
When the agent makes a Bash tool call running "tailscale ssh cwoolley@macbook-m4-max true"
Then the fleet route guard does not refuse the call
And the guard's verdict record for the call states that no record answered
```

**Co-edit owed at revise.** The revise that accepts this proposal MUST add one `tests/heading-coverage.json` entry per new scenario heading in the same commit (`spec_file: "scenarios.md"`, `test: "TODO"`, `work_item: "livespec-driver-claude-bmacrp"`, and a `reason` that names the tier the owed test runs at and that work item, for example "A real test at the integration tier (hook boundary) is owed for this heading; livespec-driver-claude-bmacrp owns it."), and MUST regenerate `tests/heading-coverage-debt.json`.
