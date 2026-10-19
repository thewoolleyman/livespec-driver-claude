## The maintainer's statement of what done means

There's supposed to be a hook that prevents agent memories from being written and instead forces them to be written to Small discoverable entries in agents.md and the .ai The directory contains the main content. [...] Yes file the complete fix and start working on it. [...] get this fixed. Also migrate all of the memories that made it past it into appropriate AI entries.

## Definition of Done assertions derived from that statement

- In a livespec-governed project, a Claude Code Edit or MultiEdit of a file named *.md directly under a memory directory is refused with the intent-routing reason.
- In a livespec-governed project, a Claude Code Bash command that writes into an agent memory directory, by redirect, tee, sed -i, cp, mv, a here-document or an inline interpreter write, is refused with the same reason, while a command that only reads that directory runs.
- The deny reason routes durable agent guidance to a short discoverable AGENTS.md entry that points at a .ai/<topic>.md file holding the content.
- In a livespec-governed project, a Codex shell command that writes into an agent memory directory is refused with the intent-routing reason.
- None of the five governed projects that held memories on this host (livespec-orchestrator-beads-fabro, livespec-dev-tooling, dolt-server, livespec-runtime, livespec-driver-pi) still holds a memory note, and each of the 52 notes is either carried by an AGENTS.md entry plus a .ai/ file on that repository's master or recorded with its reason as already covered or no longer true.
- A fresh agent session using the released Claude and Codex driver builds, installed through the normal plugin path, refuses each of the write routes above.

# 001 — Why the auto-memory guard let memories through (2026-10-18)

## The observed bypass

On 2026-10-18 the `petri-factory-on-gmktec` session (project
`livespec-orchestrator-beads-fabro`, a livespec-governed project) wrote two
notes into `~/.claude/projects/-data-projects-livespec-orchestrator-beads-fabro/memory/`
with shell commands (`cat >>` and `sed`). No guard refused either write. When
the maintainer said a hook forbids memory writes, that session searched the
settings files and the repo hook directory, found nothing, and concluded no
such hook exists. The hook exists; the search could not have found it,
because it ships inside the Claude Driver plugin rather than in any settings
file.

## Where the guard lives and what it covers

- Claude Driver: `livespec-driver-claude/.claude-plugin/hooks/block_auto_memory.py`,
  registered in `.claude-plugin/hooks/hooks.json` on exactly ONE matcher,
  `Write`. Installed build measured: cache `d8c9b69ad88e` (v0.10.0).
- Codex Driver: `livespec-driver-codex/livespec/hooks/block_auto_memory.py`,
  registered on `Write`, `Edit` and `apply_patch`, plus a Stop-time
  `codex_background_memory_audit.py` that reads `~/.codex/memories_1.sqlite`.
  No shell coverage.
- homelab carries its own project-level copy (`homelab/.claude/hooks/`), out
  of scope here because homelab is not one of the five governed projects
  holding memories.

Control run, 2026-10-18: feeding the installed hook a `Write` payload whose
target is this project's memory directory, with `CLAUDE_PROJECT_DIR` set to
the orchestrator repo, printed the block decision. Feeding the SAME script an
`Edit` payload printed nothing — `_block_decision` returns early when
`tool_name != "Write"` — and the harness never calls it for `Edit` anyway,
because `hooks.json` registers it on `Write` only.

## Routes that reach a memory file without the guard firing

1. `Edit` (and `MultiEdit`) on an existing `memory/*.md` file — the most
   natural way to amend `MEMORY.md` or an existing note.
2. Any `Bash` command that writes the file: redirect (`>`, `>>`), `tee`,
   `sed -i`, `cp`/`mv`/`install` into the directory, a here-document, or an
   interpreter one-liner (`python3 -c "open(...).write(...)"`).
3. Codex: a shell command writing into `~/.codex/memories/` or into the
   Claude memory directory.

## Why the earlier repair did not catch this

`livespec-driver-claude-vxy7io` ("Verify and repair Claude Driver auto-memory
guard", closed 2026-07-14) verified the hook against the ratified contract,
whose text pins the registration: livespec core
`SPECIFICATION/contracts.md` §"Driver-shipped hooks" says "Registered on the
`Write` tool; the effective matcher is `Write(**/memory/*.md)`", and the
driver's own `SPECIFICATION/contracts.md` and `scenarios.md` repeat it. So the
item correctly found "no repair needed" against a contract that is itself too
narrow. The same core file's §"Fleet agent-instruction core" says the
memory store "is NEVER the home for durable guidance in a livespec-governed
member", which is the intent the widened guard enforces.

Consequence for routing: widening the registration is a SPEC change in
livespec core (and the driver spec that restates it), so it goes through
`/livespec:propose-change` before the driver implementation lands. That is
the conformance-versus-ratification line in the fleet decision rules: the
change makes the check assert something the ratified hook clause does not.

## The memories that got past the guard

Governed projects (hook would block) holding memory notes on this host,
measured 2026-10-18 with the hook's own `resolve_impl_plugin`:

| Project | Notes |
| --- | --- |
| livespec-orchestrator-beads-fabro | 39 |
| livespec-dev-tooling | 8 |
| dolt-server | 3 |
| livespec-runtime | 1 |
| livespec-driver-pi | 1 |

Eight further projects hold notes but are NOT governed (vps-info,
1password-env-wrapper, local-llm, beads, kilroy, herdr-info,
gmktec-xubuntu-info, and a personal-knowledge-base rig), so the guard never
applied to them and they are out of scope. `livespec-impl-plaintext` holds 7
notes but its repository no longer exists at `/data/projects/`, so it is also
out of scope.

Prior art for the migration: epic `livespec-xei45t` in the livespec core
tenant ran the earlier cloud-local memory cleanup
(`livespec-driver-claude-vx6gmo` migrated this driver's own notes into
`.ai/beads-tenant.md`; deletion was the separate slice `livespec-eclobt`).
These 52 notes accumulated after that cleanup.

The migration target, per the maintainer: a short discoverable entry in
`AGENTS.md` that points at a `.ai/<topic>.md` file holding the content.
