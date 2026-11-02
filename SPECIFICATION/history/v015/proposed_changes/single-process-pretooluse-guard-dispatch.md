---
topic: single-process-pretooluse-guard-dispatch
author: claude-opus-5-5:anthropic-burn-mitigation
created_at: 2026-11-02T00:47:52Z
---

## Proposal: Run the Bash-matched PreToolUse guards in one fail-open-per-guard dispatcher process

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md
- tests/heading-coverage.json

### Summary

Replace the one-Python-process-per-guard invocation form for the Driver's Bash-matched PreToolUse guards with one dispatcher entry point. It evaluates every guard in-process, each inside its own fail-open boundary. The refuse-iff-any-refuses decision and each refusing guard's reason stay unchanged.

### Motivation

Measured on the shared dev host (vmi3006760, 18 vCPU) on 2026-11-02, plan anthropic-burn-mitigation (livespec-orchestrator-beads-fabro epic bd-ib-b2jzxw, coordinator priority 5: decrease dev-host load). A 60 s bpftrace joined each exiting process's execve argv to its sum_exec_runtime. The bundle's Bash-matched guards each start their own python3, at 0.17-0.30 CPU-s per start under host load. In that minute they spent github_rate_limit_guard 4.4 s, fleet_host_guard 4.3 s, block_raw_bd_create 3.5 s, block_auto_memory 3.2 s and tmux_fleet_guard 2.6 s of CPU, about 18 CPU-s per minute, or 0.3 cores, for interpreter start-up that does no guard work. One process per Bash call saves about 0.8-1.0 CPU-s per call. The dev host makes several hundred Bash calls an hour across its interactive seats, and these orphaned short-lived python3 processes were the largest unattributed class in the host's load attribution. The fail-open-per-guard rule keeps today's property that one broken guard can never wedge every tool call, now inside one process instead of by process isolation.

### Proposed Changes

In `SPECIFICATION/contracts.md` §"Hook bundle", replace the sentence

> Every hook is a Python script invoked by the harness as `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`;

with:

> Every hook is a Python module in the bundle. The harness MUST start every PreToolUse guard registered on the `Bash` matcher through ONE dispatcher entry point, `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse_dispatch.py"`, so one Bash tool call starts one Python process for the Driver's PreToolUse guards rather than one per guard. The dispatcher imports each guard module and evaluates every guard in-process against the same PreToolUse payload. Each guard runs inside its OWN fail-open boundary: a guard that raises, times out or returns a malformed result is treated as an allow for that guard alone and MUST NOT suppress, reorder or alter any other guard's decision, nor turn the tool call into a refusal. The dispatcher refuses the call iff at least one guard refuses it, and its refusal reason is the reason of the first refusing guard in registration order, byte-identical to that guard's reason when run standalone. A guard on any other matcher MAY remain its own entry point `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`, and each guard module MUST remain runnable standalone by that form with unchanged behaviour.

Append to the closing paragraph of §"Hook bundle" (after "...provided the postures hold."):

> Which guards the dispatcher evaluates, and in what order, is Driver implementation detail under that same rule, provided the one-process and per-guard fail-open properties above hold.

In `SPECIFICATION/scenarios.md`, add after "## Scenario: reading or removing a memory note is not refused by the block-auto-memory hook":

## Scenario: one Bash tool call starts one Python process for the Driver's PreToolUse guards

```gherkin
Given the Driver plugin is installed and enabled in a Claude Code session
When the agent makes one Bash tool call
Then the Driver's hooks.json starts exactly one Python process for its Bash-matched PreToolUse guards
And every guard the bundle registers on the Bash matcher is evaluated against that call's payload
```

## Scenario: a crashing guard inside the PreToolUse dispatcher disables neither the other guards nor the tool call

```gherkin
Given one Bash-matched PreToolUse guard of the Driver raises an exception on a payload
When the agent makes a Bash tool call with that payload
Then every other Bash-matched guard is still evaluated against the call
And a refusal from any other guard still refuses the call with that guard's own reason
And when no other guard refuses, the call is allowed
```

Co-edit `tests/heading-coverage.json`: add one entry per new scenario heading (`spec_file: "scenarios.md"`, `test: "TODO"`, `reason: "Realized by the PreToolUse dispatcher implementation item filed after this revise; the dispatcher's tests under tests/hooks/ will replace this TODO."`).
