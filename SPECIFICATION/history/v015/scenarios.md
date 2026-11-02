# scenarios.md — livespec-driver-claude

Gherkin scenarios for each Driver-owned contract path in `contracts.md`.
These are the worked examples the structural gate, the hook bundle, and
the resolution algorithm are checked against.

## Scenario: installed Driver exposes the eight /livespec:* commands

```gherkin
Given a project that enables livespec core and the livespec-driver-claude plugin
When the Claude Code runtime loads the Driver plugin
Then the eight slash commands /livespec:seed, /livespec:propose-change,
  /livespec:critique, /livespec:revise, /livespec:doctor,
  /livespec:prune-history, /livespec:next, and /livespec:help are available
And they are namespaced under the plugin name "livespec"
```

## Scenario: core-root resolution via operator override

```gherkin
Given the environment variable LIVESPEC_CORE_PLUGIN_ROOT is set to a core checkout
When a binding resolves <core-root>
Then it uses the override path
And it does not consult the governed-project or installed-cache fallbacks
```

## Scenario: core-root resolution falls back to the governed-project checkout

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And <project-root>/.claude-plugin/prose/ carries the complete core operation
    prose set — the dev / dogfooding case, loaded with --plugin-dir .
When a binding resolves <core-root>
Then it uses <project-root>/.claude-plugin/
```

## Scenario: core-root resolution rejects a non-core project checkout

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project ships its OWN plugin carrying a prose/ directory
And that prose/ does NOT hold the livespec core operation prose
And installed_plugins.json holds a livespec@livespec record whose projectPath
    equals the project root
When a binding resolves <core-root>
Then it does NOT use <project-root>/.claude-plugin/
And it uses that record's installPath
```

## Scenario: an incomplete core checkout fails rather than falling back

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And <project-root>/.claude-plugin/prose/ holds CORE-EXCLUSIVE operation prose
    but NOT the complete core operation prose set
And installed_plugins.json holds a livespec@livespec record whose projectPath
    equals the project root
When a binding resolves <core-root>
Then resolution FAILS and names the missing prose files
And it does NOT fall through to that record's installPath
```

## Scenario: the incomplete-checkout diagnostic names the recovery

```gherkin
Given resolution has failed because the core prose set is incomplete
When the diagnostic is emitted
Then it names LIVESPEC_CORE_PLUGIN_ROOT
And it states that the override is consulted BEFORE the completeness check
```

## Scenario: core-root resolution selects the install record for this project

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project is not the livespec core repo
And installed_plugins.json holds livespec@livespec records for SEVERAL projects
And the FIRST record in that array belongs to a DIFFERENT project
And one record's projectPath equals the project root
When a binding resolves <core-root>
Then it uses that record's installPath
And it does not use the first record's installPath
```

## Scenario: core-root resolution reports a projectPath mismatch as such

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project is not the livespec core repo
And installed_plugins.json holds livespec@livespec records
And no record's projectPath equals the project root
When a binding resolves <core-root>
Then it does not resolve <core-root>
And it reports that no install record exists for this project root
And it names the project roots that DO hold records
And it does not fall through to another project's record
And it does not report the condition as plugin staleness
```

## Scenario: an unreadable registry is not reported as core being uninstalled

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project is not the livespec core repo
And installed_plugins.json exists but cannot be read or parsed
When a binding resolves <core-root>
Then it does not resolve <core-root>
And it reports that the registry could not be read
And it does not instruct the operator to install livespec core
```

## Scenario: an absent registry yields the install instructions

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project is not the livespec core repo
And installed_plugins.json does not exist
When a binding resolves <core-root>
Then it does not resolve <core-root>
And it surfaces the livespec core install instructions
```

## Scenario: structural check rejects a SKILL.md invoking uv run

```gherkin
Given a SKILL.md whose fenced wrapper invocation uses "uv run"
When check_plugin_structure runs
Then it exits non-zero
And it emits a violation naming the file and line
```

## Scenario: structural check rejects the Driver's own plugin-root placeholder for core scripts

```gherkin
Given a SKILL.md whose fenced wrapper invocation resolves a bin/<name>.py
  through the Driver's own plugin-root placeholder
When check_plugin_structure runs
Then it exits non-zero
And it reports that the placeholder resolves to the Driver root, which has no scripts/
```

## Scenario: structural check rejects an extra or missing skill directory

```gherkin
Given the skills/ directory is missing one of the eight bindings, or carries an extra directory
When check_plugin_structure runs
Then it exits non-zero
And it names the missing or unexpected skill directory
```

## Scenario: marketplace description drift is rejected

```gherkin
Given marketplace.json's single plugin entry description differs from plugin.json's description
When check_plugin_structure runs
Then it exits non-zero
And it reports that the marketplace description must duplicate plugin.json's verbatim
```

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

## Scenario: one Bash tool call starts one Python process for the Driver's PreToolUse guards

```gherkin
Given the Driver plugin is installed and enabled in a Claude Code session
When the agent makes one Bash tool call
Then the Driver's hooks.json starts exactly one Python process for its Bash-matched PreToolUse guards
And every Bash-matched guard the bundle carries is evaluated against that call's payload
```

## Scenario: a crashing fail-open guard inside the PreToolUse dispatcher disables neither the other guards nor the tool call

```gherkin
Given one fail-open Bash-matched PreToolUse guard of the Driver raises an exception on a payload
When the agent makes a Bash tool call with that payload
Then every other Bash-matched guard is still evaluated against the call
And a refusal from any other guard still refuses the call with that guard's own reason
And when no other guard refuses, the call is allowed
```

## Scenario: a dispatcher that fails before evaluating its guards falls back to the standalone guards

```gherkin
Given the PreToolUse dispatcher fails before it has evaluated every Bash-matched guard
When the agent makes a Bash tool call
Then each not-yet-evaluated Bash-matched guard runs as its own standalone process against that call's payload
And the call is refused exactly when one of the standalone guards refuses it, with that guard's own reason
```

## Scenario: a crashing fail-closed guard inside the PreToolUse dispatcher still refuses the call

```gherkin
Given a Bash-matched PreToolUse guard that the upstream contract declares fail-closed raises an exception on a payload
When the agent makes a Bash tool call with that payload
Then the dispatcher refuses the call with that guard's own fail-closed refusal
And every other Bash-matched guard is still evaluated against the call
```

## Scenario: plan-artifact persistence warning on a bare assistant turn

```gherkin
Given the last assistant turn carried substantial planning artifacts above the thresholds
And no persisting tool call fired in the window
When the Stop hook runs
Then it emits a WARN
And it exits 0 without blocking
```

## Scenario: installed Driver refuses Playwright calls from a governed primary checkout

```gherkin
Given the Driver is installed in a livespec-governed Git repository
And the hook input cwd resolves to that repository's primary checkout
When any mcp__playwright__* tool is requested
Then the Driver's PreToolUse hook denies the call before Playwright runs
And no Playwright artifact is created in the primary checkout
But the same tool call from a linked worktree is allowed
```

## Scenario: commit at the primary checkout is refused

```gherkin
Given the current checkout's toplevel equals the configured livespec.primaryPath
When a commit or push is attempted
Then the commit-refuse hook exits 1
And it directs the contributor to use a worktree
```

## Scenario: a delegating host's push gates on the remote executor and refuses on no verdict

Given this repository's version-controlled configuration opts it in to delegating its pre-push gate

And the pushing host holds the credential to submit to the remote executor

When a git push of a new tree runs the pre-push gate

Then the pre-push path MUST run the delegation client instead of running `just check` on the pushing host

And the push MUST complete only on a passing verdict from the executor

And the push MUST be refused when the executor returns no verdict
