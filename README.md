# livespec-driver-claude

The **Claude Code Driver** for [livespec](https://github.com/thewoolleyman/livespec)
— the first reference Driver under livespec's contract + reference
implementations architecture (per livespec `SPECIFICATION/spec.md`
§"Contract + reference implementations architecture").

A **Driver** is the thin, agent-runtime-specific wrapper through which
a human drives the spec lifecycle interactively. This repo ships ONLY
the thin Claude Code SKILL.md bindings for the eight spec-side
operations. Everything substantive stays in livespec core:

| Artifact | Ships with |
|---|---|
| Harness-neutral driving prose (`prose/<name>.md`) | livespec core |
| Reference spec-side CLIs (`scripts/bin/<name>.py`) | livespec core |
| JSON schemas, templates | livespec core |
| Thin `/livespec:*` Claude Code bindings | **this repo** |

The Driver binds core's prose and config-named CLIs only. It has ZERO
dependencies on any orchestrator (the load-bearing Driver ↔
orchestrator zero-dependency invariant).

## Install

Both plugins are required — core carries the prose and CLIs, this
Driver carries the `/livespec:*` commands:

```
/plugin marketplace add thewoolleyman/livespec
/plugin install livespec@livespec
/plugin marketplace add thewoolleyman/livespec-driver-claude
/plugin install livespec@livespec-driver-claude
```

After install, restart Claude Code (or run `/reload-plugins`). The
eight slash commands become available with the `livespec:` namespace
prefix (the Driver plugin is deliberately NAMED `livespec` so the
established `/livespec:*` surface is preserved):

- `/livespec:seed` — author the initial natural-language spec
- `/livespec:propose-change` — file a proposed change against the spec
- `/livespec:critique` — surface issues in the spec
- `/livespec:revise` — accept or reject pending proposed changes
- `/livespec:doctor` — run static + LLM-driven validation
- `/livespec:prune-history` — collapse old `history/vNNN/` entries
- `/livespec:next` — rank the next spec-side action
- `/livespec:help` — overview + routing to the right sub-command

## How the bindings find livespec core

Each SKILL.md resolves the livespec core plugin root (`<core-root>`)
at runtime, in order:

1. the `LIVESPEC_CORE_PLUGIN_ROOT` environment variable (explicit
   override);
2. `<project-root>/.claude-plugin/prose/` when the governed project
   IS the livespec core repo (`--plugin-dir .` dev mode /
   dogfooding);
3. the installed `livespec@livespec` plugin's flattened cache root,
   read from `~/.claude/plugins/installed_plugins.json`.

It then reads `<core-root>/prose/<name>.md` (the harness-neutral
driving prose) and dispatches the operation's CLI as named in the
governed project's `.livespec.jsonc` `spec_clis` section (argv-form,
pre-populated with core's reference defaults, individually
overridable per livespec `contracts.md` §"Spec-side CLI contract").

## Development

```
just bootstrap   # one-time: primary-checkout guard hooks + lefthook + plugins
just check       # full enforcement aggregate (manifests, skills, lint, e2e)
```

The repo follows the livespec-family conventions: `.mise.toml` pins
the non-Python binaries (uv, just, lefthook), the justfile is the
single entry point for every check, lefthook delegates to `just`, and
the primary checkout refuses direct commits (work happens in
`git worktree add` secondaries).

## Backlog

This repo's initial backlog (relocated from the livespec tenant
pending this repo's own work-item tenant provisioning) lives in
[BACKLOG.md](BACKLOG.md).
