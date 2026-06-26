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
And the governed project IS the livespec core repo loaded with --plugin-dir .
When a binding resolves <core-root>
Then it uses <project-root>/.claude-plugin/
```

## Scenario: core-root resolution falls back to the installed cache

```gherkin
Given LIVESPEC_CORE_PLUGIN_ROOT is unset
And the governed project is not the livespec core repo
When a binding resolves <core-root>
Then it uses the installed livespec@livespec plugin's flattened cache root
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

## Scenario: auto-memory write in a governed project is redirected to capture-work-item

```gherkin
Given a governed project whose .livespec.jsonc declares an implementation.plugin
When an agent attempts Write to a path matching **/memory/*.md
Then the PreToolUse hook blocks the write
And the block reason names the active impl-plugin's capture-work-item skill
```

## Scenario: plan-artifact persistence warning on a bare assistant turn

```gherkin
Given the last assistant turn carried substantial planning artifacts above the thresholds
And no persisting tool call fired in the window
When the Stop hook runs
Then it emits a WARN
And it exits 0 without blocking
```

## Scenario: commit at the primary checkout is refused

```gherkin
Given the current checkout's toplevel equals the configured livespec.primaryPath
When a commit or push is attempted
Then the commit-refuse hook exits 1
And it directs the contributor to use a worktree
```
