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

This Driver plugin ships ONLY the bindings plus the small resolver named
below. The harness-neutral prose and the reference spec-side CLIs ship
with **livespec core** — the `livespec` plugin from the
`thewoolleyman/livespec` marketplace, which must be installed alongside
this Driver. The plugin-root placeholder of THIS plugin resolves to the
Driver's own root, which carries no `prose/` and no core `bin/` wrappers
— NEVER use it for core paths.

The ordered algorithm is realized ONCE, by the Driver-owned
`lib/resolve_core_root.py` in this plugin's own bundle. Do NOT
restate it inline. Eight byte-identical inline copies are exactly how one
defect — selecting an install record by POSITION instead of by
`projectPath` — came to live in all eight bindings simultaneously, and
made every spec-side operation from an affected project hard-stop before
doing any work.

1. `LIVESPEC_CORE_PLUGIN_ROOT`, when set and non-empty (explicit
   operator override; covers nonstandard dev setups, e.g. driving a
   sibling checkout's core).
2. Else `<project-root>/.claude-plugin/` when it carries `prose/` — the
   governed project IS the livespec core repo itself (`--plugin-dir .`
   dev mode / dogfooding).
3. Else the `livespec@livespec` install record in
   `~/.claude/plugins/installed_plugins.json` **whose `projectPath` is
   the project root**. That key holds an ARRAY of records, one per
   project that installed the plugin; taking the first resolves
   whichever project on this host installed core earliest, which bears
   no relation to this one.

Canonical Bash form (`<project-root>` defaults to the cwd):

```bash
LIVESPEC_CORE_ROOT="$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/resolve_core_root.py" --project-root .)" || exit 1
if [ ! -d "$LIVESPEC_CORE_ROOT/prose" ]; then
  echo "resolved livespec core root carries no prose/: $LIVESPEC_CORE_ROOT" >&2
  exit 1
fi
echo "$LIVESPEC_CORE_ROOT"
```

The resolver writes its OWN diagnostic to stderr and exits non-zero. That
diagnostic distinguishes core being genuinely absent from a registry that
could not be READ, and from core being installed for OTHER projects but
not this one — which is a provisioning defect, NOT a stale plugin. If
resolution fails, STOP and surface the resolver's diagnostic verbatim.
Do not improvise a path, and do not run an install or update command the
diagnostic did not ask for.
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
