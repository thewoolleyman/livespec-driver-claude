---
name: doctor
description: Run the doctor checks against a livespec spec tree — the static phase (structural failures) plus the LLM-driven objective and subjective phases — surfacing findings as JSON or as a per-finding user dialogue. Invoked by /livespec:doctor, "run livespec doctor", or "check the spec for invariants", and as the post-step LLM-driven phase from every wrapper-having sub-command.
allowed-tools: Bash, Read
---

# doctor — Claude Code Driver binding

This file is the thin Claude Code binding for the `doctor` operation,
shipped by the **livespec-driver-claude** Driver plugin (plugin name
`livespec`, so the surface stays `/livespec:*`). The complete
harness-neutral driving prose is livespec CORE's artifact at
`<core-root>/prose/doctor.md`. FIRST resolve `<core-root>` (next
section), THEN read that prose file in full, then execute it
end-to-end, binding its harness-neutral vocabulary to this runtime as
follows.

When another `/livespec:*` skill delegates here for the post-step
LLM-driven phase only, follow the prose's "Post-CLI" section: skip
the static-phase Steps 1-4 and proceed from Step 5.


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
2. If `<project-root>/.claude-plugin/prose/doctor.md` exists — the
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

Per livespec core's contract (its `contracts.md`), every spec-side
operation is named in the governed
project's `.livespec.jsonc` under `spec_clis.doctor` as an argv-form
array, pre-populated with core's reference default and individually
overridable. To "run the doctor CLI named in config":

1. Read `<project-root>/.livespec.jsonc` (JSONC — tolerate `//`
   comments). If the file, the `spec_clis` section, or the
   `spec_clis.doctor` key is absent, use core's reference default
   argv: `python3 <core-root>/scripts/bin/doctor_static.py`.
2. If the configured argv contains the literal plugin-root
   substitution token (the `CLAUDE_PLUGIN_ROOT` placeholder, written
   as a `$`-brace expansion in config), expand it to `<core-root>` —
   core's schema defines that token as "the installed livespec plugin
   root", which is CORE's root, never this Driver's.
3. Append the operation's flags and invoke via the Bash tool.

With the default config this collapses to:

```bash
python3 "$LIVESPEC_CORE_ROOT/scripts/bin/doctor_static.py" [--project-root <path>]
```

## Runtime bindings

- **"run the doctor CLI named in config" / "invoke the doctor
  CLI"** — dispatch per the Config-named CLI dispatch section above; with the
  default config:

  ```bash
  python3 "$LIVESPEC_CORE_ROOT/scripts/bin/doctor_static.py" [--project-root <path>]
  ```

- **"run the template-resolution CLI"** — via the Bash tool:

  ```bash
  python3 "$LIVESPEC_CORE_ROOT/scripts/bin/resolve_template.py" --template <name>
  ```

- **"ask the user" / "prompt the user" / "surface" / "narrate" /
  the per-finding dialogue** — conversational turns in this session
  (the AskUserQuestion tool or plain narration, as appropriate).
- **"read `<file>`" / "inspect the stdout JSON"** — the Read tool
  (or Bash `cat` for captured output).
- **"invoke the critique operation"** — the `/livespec:critique`
  skill in this Driver plugin.
- **"the calling operation's prose"** — the delegating
  `/livespec:*` skill's binding + its `<core-root>/prose/<name>.md`
  artifact.
