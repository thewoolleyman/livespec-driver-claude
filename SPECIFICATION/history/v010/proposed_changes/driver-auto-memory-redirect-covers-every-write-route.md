---
topic: driver-auto-memory-redirect-covers-every-write-route
author: claude-opus-5-5
created_at: 2026-10-18T16:39:41Z
---

## Proposal: Driver auto-memory redirect covers every write route

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Restate this Driver's auto-memory redirect to match livespec core v225: registered on Write, Edit, MultiEdit and Bash, refusing every write into an agent memory directory in a governed project while letting reads and rm through, with the durable-guidance route naming the short AGENTS.md entry plus .ai/<topic>.md shape. Widen the existing scenario's When line to the three file tools and add two scenarios for the shell route and the read/remove allowance.

### Motivation

livespec core v225 (livespec PR 2892) ratified auto-memory-guard-covers-every-write-route; this repository's contracts.md Hook bundle and scenarios.md still restate the Write-only registration, so they now contradict the upstream clause this repo realizes. Plan block-auto-memory-coverage (epic livespec-driver-claude-22yt6u); implementation item livespec-driver-claude-cb2mzo.

### Proposed Changes

In `SPECIFICATION/contracts.md` §"Hook bundle", the first bullet of "The bundle carries four upstream-required hooks" MUST be replaced with:

- a **PreToolUse** auto-memory redirect (`block_auto_memory.py`)
  registered on `Write`, `Edit`, `MultiEdit` and `Bash` that, in a
  livespec-governed project, refuses every write into an agent memory
  directory — a file tool targeting `**/memory/*.md` or a file under
  `~/.codex/memories/`, and a shell command it positively identifies as
  writing into either (redirection, `tee`, `sed -i`, `cp`/`mv`/`install`,
  a here-document, an inline interpreter write) — while letting reads
  and `rm` through. Its reason intent-routes the would-be write by what
  it IS: trackable work to the active impl-plugin's
  `/<plugin>:capture-work-item` skill (resolved from `.livespec.jsonc`
  `implementation.plugin`); spec-level rules to `/livespec:propose-change`;
  durable agent guidance, learned preferences and conventions to a short
  discoverable `AGENTS.md` entry pointing at a `.ai/<topic>.md` file that
  holds the content; and only genuinely session-only notes may be
  dropped. A no-op pass-through when the project is not
  livespec-governed;

In `SPECIFICATION/scenarios.md`, the scenario `## Scenario: auto-memory write in a governed project is intent-routed by the block-auto-memory hook` MUST keep its heading and MUST read:

## Scenario: auto-memory write in a governed project is intent-routed by the block-auto-memory hook

```gherkin
Given a governed project whose .livespec.jsonc declares an implementation.plugin
When an agent attempts Write, Edit or MultiEdit to a path matching **/memory/*.md
Then the PreToolUse hook blocks the write
And the block reason routes trackable work to the active impl-plugin's capture-work-item skill
And the block reason routes spec-level rules to /livespec:propose-change
And the block reason routes durable agent guidance and conventions to a short AGENTS.md entry pointing at a .ai/<topic>.md file
And only genuinely session-only notes may be dropped
```

and the following two scenarios MUST be added directly after it:

## Scenario: shell write into an agent memory directory in a governed project is refused by the block-auto-memory hook

```gherkin
Given a governed project whose .livespec.jsonc declares an implementation.plugin
When an agent runs a Bash command that writes a file into ~/.claude/projects/<slug>/memory/ or ~/.codex/memories/ by redirection, tee, sed -i, cp, mv, a here-document or an inline interpreter write
Then the PreToolUse hook blocks the command
And the block reason is the same intent-routing reason the file-tool route gives
```

## Scenario: reading or removing a memory note is not refused by the block-auto-memory hook

```gherkin
Given a governed project whose .livespec.jsonc declares an implementation.plugin
When an agent runs a Bash command that only reads a memory directory, or removes a note there with rm
Then the PreToolUse hook lets the command run
```

`tests/heading-coverage.json` MUST gain one row per new heading, `test: "TODO"`, owned by `livespec-driver-claude-cb2mzo`, whose reason names the owed integration-tier test.
