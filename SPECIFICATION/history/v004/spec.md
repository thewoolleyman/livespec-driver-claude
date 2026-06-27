# spec.md — livespec-driver-claude

This is the natural-language specification for `livespec-driver-claude`,
the reference **Claude Code Driver** for the livespec family. The Driver
dogfoods `livespec` — this `SPECIFICATION/` tree evolves through
`/livespec:seed` / `propose-change` / `revise` / `doctor` /
`prune-history` / `critique`, exactly the same lifecycle every consumer
project uses.

Throughout this spec, the token "v1" refers to the Driver plugin's first
MAJOR release line (semver `1.x.x`). Pre-1.0 `0.x` releases are bootstrap
territory and do not satisfy any rule scoped to "v1". Rules without a
"v1" qualifier are unconditional and bind every release.

## Purpose

A **Driver** is the thin, agent-runtime-specific wrapper through which a
human drives the livespec spec lifecycle interactively. `livespec-driver-claude`
is the first reference Driver under livespec's contract-plus-reference-
implementations architecture (per `livespec/SPECIFICATION/spec.md`).
It binds livespec
core's harness-neutral material to ONE tool runtime — Claude Code.

This repo ships exactly three things, all Claude-runtime mechanics:

1. **The eight thin SKILL.md bindings** under `.claude-plugin/skills/<name>/`,
   one per spec-side operation (`seed`, `propose-change`, `critique`,
   `revise`, `doctor`, `prune-history`, `next`, `help`). Each binding
   resolves livespec core at runtime, reads core's operation prose, and
   dispatches the config-named spec-side CLI.
2. **A plugin-shipped hook bundle** under `.claude-plugin/hooks/` —
   `hooks.json` plus fail-open POSIX shell scripts. This is Driver-owned
   runtime surface (unlike the prose and CLIs, which are core's).
3. **A structural gate** (`dev-tooling/check_plugin_structure.py`) that
   mechanically enforces the manifest, skill-set, and invocation
   invariants this spec codifies.

Everything substantive stays in livespec core: the harness-neutral
operation prose (`prose/<name>.md`), the reference spec-side CLIs
(`scripts/bin/<name>.py`), the JSON schemas, and the built-in templates.
The Driver carries none of those; it resolves them from core at runtime.

## Scope boundary

This spec governs the Driver's own seam — the surface this repo owns and
that nothing upstream governs:

- the plugin and marketplace manifest shape (§`contracts.md` §"Plugin
  manifest and marketplace");
- the eight-skill binding set and its frontmatter discipline;
- the **core-root resolution algorithm** and its fail-modes;
- the **fenced-invocation discipline** by which a SKILL.md invokes core's
  wrapper CLIs;
- the **hook-bundle wiring** (existence, registration, and the home for
  the scripts and their tests).

Out of scope — these are core-owned and this tree references them, never
restates them: the operation prose contents; the wrapper-CLI surfaces,
exit codes, and wire contracts; the JSON schemas; the built-in templates;
the eight slash-command *names* and any rename (those require a core
propose-change cycle); and the hook *disciplines and postures* (fail-open
contract, block-vs-warn) — those live in `livespec/SPECIFICATION/contracts.md`.
The family-standard primary-checkout commit-refuse
hook is likewise core-owned (`livespec/SPECIFICATION/non-functional-requirements.md`);
this repo carries the scaffold but
does not re-specify it.

Upstream-wins: when a rule here conflicts with livespec core's
`SPECIFICATION/`, the upstream rule wins.

## Terminology

The family vocabulary is defined upstream in `livespec/SPECIFICATION/spec.md`
§"Terminology";
this tree uses it without redefinition. The terms that recur here:

- **Driver** — the thin, agent-runtime-specific wrapper (this repo, for
  Claude Code). Core is agnostic to it.
- **core-root** (`<core-root>`) — the resolved livespec core plugin root
  from which a binding reads prose and dispatches CLIs. Surfaced to the
  bindings as the `$LIVESPEC_CORE_ROOT` shell variable.
- **Binding** — a single `.claude-plugin/skills/<name>/SKILL.md` that
  binds one core operation to Claude Code.
- **Thin-transport binding** — a binding (e.g. `next`) whose whole job is
  to invoke its backing wrapper and present the structured output
  verbatim, with no ranking or judgment in the binding.

## Public surface

The Driver's public, user-facing surface is the eight slash commands,
namespaced under the Driver plugin name: `/livespec:seed`,
`/livespec:propose-change`, `/livespec:critique`, `/livespec:revise`,
`/livespec:doctor`, `/livespec:prune-history`, `/livespec:next`,
`/livespec:help`. The command *names* are a core v1 contract; the
*runtime mechanics* that expose them are this repo's.

The plugin is deliberately NAMED `livespec` (not `livespec-driver-claude`)
so the established `/livespec:*` surface is preserved; the marketplace
catalog is named `livespec-driver-claude`. The hook bundle is the second
public surface: plugin-shipped Claude Code hooks that fire automatically
when the plugin is enabled in a governed project.

## Lifecycle and evolution

This `SPECIFICATION/` tree is the live spec for the Driver seam and
evolves through the standard livespec loop. The Driver's *behavior* —
what each operation does — is owned by core's operation prose; edits to
behavior happen in livespec core, not here. This repo's spec changes when
the Driver-local seam changes: the manifest shape, the resolution
algorithm, the invocation discipline, the hook bundle's wiring, or the
structural gate. Renaming the plugin or marketplace names, adding or
removing a binding, or changing a hook's posture requires a
propose-change cycle (against this tree for Driver-local mechanics, or
against core for the corresponding upstream contract).
