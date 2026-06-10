---
name: critique
description: Critique an existing livespec specification or a pending proposed change, surfacing ambiguities, contradictions, and missing rules as findings the user can act on. Invoked by /livespec:critique, "critique the livespec spec", or "find issues in the spec".
allowed-tools: Bash, Read, Write
---

# critique — Claude Code Driver binding

This file is the thin Claude Code binding for the `critique` operation,
shipped by the **livespec-driver-claude** Driver plugin (plugin name
`livespec`, so the surface stays `/livespec:*`). The complete
harness-neutral driving prose is livespec CORE's artifact at
`<core-root>/prose/critique.md`. FIRST resolve `<core-root>` (next
section), THEN read that prose file in full, then execute it
end-to-end, binding its harness-neutral vocabulary to this runtime as
follows.


## Resolving livespec core (`<core-root>`)

This Driver plugin ships ONLY bindings. The harness-neutral prose and
the reference spec-side CLIs ship with **livespec core** — the
`livespec` plugin from the `thewoolleyman/livespec` marketplace, which
must be installed alongside this Driver. The plugin-root placeholder
of THIS plugin resolves to the Driver's own root, which carries no
`prose/` and no `scripts/` — NEVER use it for core paths. Resolve
`<core-root>` once, in this order:

1. If the `LIVESPEC_CORE_PLUGIN_ROOT` environment variable is set and
   non-empty, use its value (explicit override; covers nonstandard
   dev setups, e.g. driving a sibling checkout's core).
2. If `<project-root>/.claude-plugin/prose/critique.md` exists — the
   governed project IS the livespec core repo itself (`--plugin-dir .`
   dev mode / dogfooding) — use `<project-root>/.claude-plugin`.
3. Otherwise use the installed `livespec@livespec` plugin's flattened
   cache root, read from `~/.claude/plugins/installed_plugins.json`.

Canonical Bash form (`<project-root>` defaults to the cwd):

```bash
LIVESPEC_CORE_ROOT="$LIVESPEC_CORE_PLUGIN_ROOT"
if [ -z "$LIVESPEC_CORE_ROOT" ] && [ -d "./.claude-plugin/prose" ]; then
  LIVESPEC_CORE_ROOT="$(pwd)/.claude-plugin"
fi
if [ -z "$LIVESPEC_CORE_ROOT" ]; then
  LIVESPEC_CORE_ROOT="$(python3 -c 'import json, pathlib; entries = json.loads((pathlib.Path.home() / ".claude" / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))["plugins"]["livespec@livespec"]; print(entries[0]["installPath"])' 2>/dev/null || true)"
fi
if [ -z "$LIVESPEC_CORE_ROOT" ] || [ ! -d "$LIVESPEC_CORE_ROOT/prose" ]; then
  echo "livespec core not found. Install it first:" >&2
  echo "  claude plugin marketplace add thewoolleyman/livespec" >&2
  echo "  claude plugin install livespec@livespec" >&2
  exit 1
fi
echo "$LIVESPEC_CORE_ROOT"
```

If resolution fails, STOP and surface those install instructions to
the user instead of improvising paths.

## Config-named CLI dispatch

Per livespec core's contract (its `contracts.md` §"Spec-side CLI
contract"), every spec-side operation is named in the governed
project's `.livespec.jsonc` under `spec_clis.critique` as an argv-form
array, pre-populated with core's reference default and individually
overridable. To "run the critique CLI named in config":

1. Read `<project-root>/.livespec.jsonc` (JSONC — tolerate `//`
   comments). If the file, the `spec_clis` section, or the
   `spec_clis.critique` key is absent, use core's reference default
   argv: `python3 <core-root>/scripts/bin/critique.py`.
2. If the configured argv contains the literal plugin-root
   substitution token (the `CLAUDE_PLUGIN_ROOT` placeholder, written
   as a `$`-brace expansion in config), expand it to `<core-root>` —
   core's schema defines that token as "the installed livespec plugin
   root", which is CORE's root, never this Driver's.
3. Append the operation's flags and invoke via the Bash tool.

With the default config this collapses to:

```bash
python3 "$LIVESPEC_CORE_ROOT/scripts/bin/critique.py" --findings-json <path> [--author <id>] [--spec-target <path>] [--project-root <path>]
```

## Runtime bindings

- **"run the critique CLI named in config" / "invoke the critique
  CLI"** — dispatch per §"Config-named CLI dispatch" above; with the
  default config:

  ```bash
  python3 "$LIVESPEC_CORE_ROOT/scripts/bin/critique.py" --findings-json <path> [--author <id>] [--spec-target <path>] [--project-root <path>]
  ```

- **"run the template-resolution CLI"** — via the Bash tool:

  ```bash
  python3 "$LIVESPEC_CORE_ROOT/scripts/bin/resolve_template.py"
  ```

- **"ask the user" / "confirm with the user" / "surface" /
  "narrate"** — conversational turns in this session (the
  AskUserQuestion tool or plain narration, as appropriate).
- **"read `<file>`"** — the Read tool. **"write `<file>`"** — the
  Write tool.
- **"the revise / propose-change operation"** — the
  `/livespec:revise`, `/livespec:propose-change` skills in this
  Driver plugin.
- **"the doctor prose (`prose/doctor.md`)"** — read
  `$LIVESPEC_CORE_ROOT/prose/doctor.md` and follow it (the
  LLM-driven post-step phase runs under this Driver plugin's
  `doctor` binding).
- **"core's `livespec/schemas/` package"** — resolves at runtime to
  `$LIVESPEC_CORE_ROOT/scripts/livespec/schemas/`.
