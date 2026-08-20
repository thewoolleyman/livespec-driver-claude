---
name: help
description: Explain what livespec does and route the user to the right sub-command (seed, propose-change, critique, revise, doctor, prune-history). Invoked by /livespec:help, "what can livespec do", or when the user asks for an overview of livespec capabilities.
allowed-tools: Bash, Read
---

# help — Claude Code Driver binding

This file is the thin Claude Code binding for the `help` operation,
shipped by the **livespec-driver-claude** Driver plugin (plugin name
`livespec`, so the surface stays `/livespec:*`). The complete
harness-neutral driving prose is livespec CORE's artifact at
`<core-root>/prose/help.md`. FIRST resolve `<core-root>` (next
section), THEN read that prose file in full, then execute it
end-to-end, binding its harness-neutral vocabulary to this runtime as
follows.


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
2. Else `<project-root>/.claude-plugin/` when its `prose/` carries the
   COMPLETE core operation-prose set — the governed project IS the
   livespec core repo itself (`--plugin-dir .` dev mode / dogfooding).
   A `prose/` directory alone is NOT the test: every plugin in this
   family ships its own, so testing the directory matches any consumer
   and pre-empts step 3, which holds that consumer's correct answer.
   Between "is core" and "is not core" lies a third state: a checkout
   carrying CORE-EXCLUSIVE operation prose — names no non-core plugin
   has reason to own — yet not the complete set. That is a core checkout
   mid-rename or mid-fetch, and it is an ERROR naming the missing files,
   not a decline: falling through there would resolve it to its own
   installed cache and serve the OLD released prose while you edit its
   replacement. Which names are core-exclusive is the resolver's to
   define; the rule is that the error arms on evidence of core, not on
   the mere absence of completeness.
3. Else the `livespec@livespec` install record in
   `~/.claude/plugins/installed_plugins.json` **whose `projectPath` is
   the project root**. That key holds an ARRAY of records, one per
   project that installed the plugin; taking the first resolves
   whichever project on this host installed core earliest, which bears
   no relation to this one.

Canonical Bash form (`<project-root>` defaults to the cwd):

```bash
LIVESPEC_CORE_ROOT="$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/resolve_core_root.py" --project-root .)" || exit 1
for op in critique doctor help next propose-change prune-history revise seed; do
  [ -f "$LIVESPEC_CORE_ROOT/prose/$op.md" ] && continue
  echo "resolved root is not livespec core: no prose/$op.md in $LIVESPEC_CORE_ROOT" >&2
  exit 1
done
echo "$LIVESPEC_CORE_ROOT"
```

The resolver writes its OWN diagnostic to stderr and exits non-zero. That
diagnostic distinguishes core being genuinely absent from a registry that
could not be READ, and from core being installed for OTHER projects but
not this one — which is a provisioning defect, NOT a stale plugin. If
resolution fails, STOP and surface the resolver's diagnostic verbatim.
Do not improvise a path, and do not run an install or update command the
diagnostic did not ask for.
## Runtime bindings

- **"the seed / propose-change / critique / revise / doctor /
  prune-history / next operation"** — the corresponding
  `/livespec:<name>` skill in this Driver plugin; route the user to
  the slash command by that name.
- **"running the seed CLI named in config with `--help`"** — e.g.
  `python3 "$LIVESPEC_CORE_ROOT/scripts/bin/seed.py" --help` via the
  Bash tool (same pattern for every other operation's wrapper under
  `$LIVESPEC_CORE_ROOT/scripts/bin/`).
