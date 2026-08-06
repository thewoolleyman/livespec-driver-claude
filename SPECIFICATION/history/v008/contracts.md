# contracts.md — livespec-driver-claude

The contracts in this file are the Driver-owned seam: the shapes and
disciplines that must hold at the boundary between Claude Code, this
Driver plugin, and livespec core. Each one is mechanically enforced by
`dev-tooling/check_plugin_structure.py` unless noted otherwise. Where a
contract has an upstream owner, this file cites it rather than restating
it.

## Plugin manifest and marketplace

The Driver plugin is declared by `.claude-plugin/plugin.json` and listed
in the marketplace catalog `.claude-plugin/marketplace.json`. The
following invariants hold (enforced by `check_plugin_structure`):

- `plugin.json` and `marketplace.json` MUST parse as JSON.
- The plugin `name` MUST be `livespec` — preserving the established
  `/livespec:*` command surface. The marketplace `name` MUST be
  `livespec-driver-claude`.
- `marketplace.json` MUST list exactly ONE plugin entry. That entry's
  `name` MUST be `livespec`, its `source` MUST be `./.claude-plugin`, and
  its `description` MUST duplicate `plugin.json`'s `description` verbatim.
  `plugin.json` is the source of truth for the description.

This is the Driver-local realization of livespec core's
`contracts.md`, which owns the cross-cutting rule
that plugin and marketplace share the value `livespec` by deliberate
choice (renaming either flows through a core propose-change cycle). Note
that core's contract leaves description-equality un-enforced at v1 ("v1
does NOT enforce equality mechanically; future revise cycles MAY add a
doctor static check"); this Driver enforces it verbatim for its own
bundle, which is stricter than — and consistent with — the upstream
contract.

## Skill-binding set

The bundle MUST ship exactly the eight bindings, one per spec-side
operation: `seed`, `propose-change`, `critique`, `revise`, `doctor`,
`prune-history`, `next`, `help`. For each:

- a directory `.claude-plugin/skills/<name>/` MUST exist;
- it MUST contain a `SKILL.md`;
- that `SKILL.md`'s frontmatter `name` MUST equal `<name>`.

No extra skill directories may exist, and none of the eight may be
missing. The operation *set* is a core contract
(`livespec/SPECIFICATION/spec.md`); this contract governs the Driver-local
binding directories that realize it.

## Core-root resolution

Every binding resolves `<core-root>` — the livespec core plugin root from
which it reads operation prose and dispatches the spec-side CLIs — by the
following ordered algorithm, surfaced to shell as `$LIVESPEC_CORE_ROOT`:

1. the `LIVESPEC_CORE_PLUGIN_ROOT` environment variable, when set
   (explicit operator override);
2. else `<project-root>/.claude-plugin/` when the governed project IS the
   livespec core repo — the `--plugin-dir .` dev / dogfooding path;
3. else the `livespec@livespec` install record in
   `~/.claude/plugins/installed_plugins.json` **whose `projectPath` equals
   the project root**, resolved to that record's `installPath`.

This resolution order is load-bearing and Driver-owned: livespec core is
agnostic to how a Driver finds it. A binding MUST NOT hardcode a core
path and MUST NOT assume a single installation shape.

The registry key holds an ARRAY of install records — one per project that
has installed the plugin. Selecting by POSITION, including the first,
resolves whichever project on the host installed core earliest, which
bears no relation to the project the binding is running in. Selection is
BY `projectPath`, never by position. This realizes livespec core's
`contracts.md` §"Plugin distribution" (its "Install verification." paragraph), which owns the rule that a project
is correctly provisioned only when the registry holds an entry for the
plugin "whose `projectPath` equals the project root".

Step 3 MUST distinguish the following outcomes and MUST NOT collapse them
onto a single diagnostic:

- **registry absent** — core is installed for no project. The install
  instructions are the correct and complete remedy.
- **registry present but unreadable or unparseable** — a NON-ANSWER, which
  establishes nothing about whether core is installed. The diagnostic MUST
  NOT tell the operator to install core, and MUST NOT be reported as a
  resolution the operator can fix by installing.
- **`livespec@livespec` absent from a readable registry** — definitive:
  core is installed for no project. Install instructions apply.
- **records present, but none whose `projectPath` is the project root** —
  the defective state core's §"Plugin distribution" requires be "detected
  and reported loudly". The binding MUST name the `projectPath` mismatch AS
  SUCH, MUST report which project roots DO hold records, and MUST NOT fall
  through to another project's record. The remedy is an install scoped to
  THIS project.
- **matching record carrying no usable `installPath`** — a malformed
  record; a distinct diagnostic naming the record it found.

A resolution failure MUST NOT be reported as a STALENESS failure. When a
correctly-selected record is stale, core's own plugin-currency gate reports
it and prescribes `claude plugin update livespec@livespec --scope project`.
That remedy is coherent only when the binding reads the same record the
command writes — which is precisely what `projectPath` selection
guarantees. Under positional selection the operator loops forever: the
command updates a record that is already current, the binding keeps reading
a different project's, and the identical error recurs. Core's
§"Plugin distribution" already records the mechanism, noting that
`claude plugin update <plugin> -s project` "issued from a project holding
no install record of its own, has been observed to act on ANOTHER project's
record and report success".

A binding that exhausts the ordered list without resolving `<core-root>`
MUST surface a clear diagnostic rather than dispatch against an unresolved
path.

The algorithm is realized ONCE, by a Driver-owned script the bundle ships
at `.claude-plugin/lib/resolve_core_root.py`, invoked through the
Driver's own plugin-root placeholder. Every binding calls that script; no
binding restates the algorithm. Eight independently-maintained copies of a
resolution rule are kept in agreement only by copying, which is how all
eight came to carry the same positional defect. The Driver's own
plugin-root placeholder is correct here for the same reason it is correct
for the hook bundle: the script is Driver-owned and lives in the Driver
bundle. It is NOT a core wrapper, so §"Fenced-invocation discipline" does
not reach it.

⛔ The directory is `lib/` and MUST NOT be renamed to `scripts/`. The
fleet-wide `check-skill-invocation-paths` auto-detects which of two
MUTUALLY CONTRADICTORY plugin models a repo is held to, purely from
whether `.claude-plugin/scripts/` exists — a bare directory-presence
test, with no config key and no diagnostic naming the choice. A Driver
that ships its own `scripts/` directory is therefore silently
reclassified as a core-carrying plugin, after which that check demands
`${CLAUDE_PLUGIN_ROOT}` for CORE wrapper invocations while
§"Fenced-invocation discipline" and `check_plugin_structure` forbid
exactly that — a state in which no set of bindings can satisfy both
checks at once. Measured, not predicted: naming this directory
`scripts/` turned every `$LIVESPEC_CORE_ROOT` wrapper line in the
bindings into a violation while the bindings themselves were unchanged.
The Driver owns a `lib/`; only livespec core owns a `scripts/`.

## Fenced-invocation discipline

Within any `SKILL.md`, every fenced command line that invokes a core
wrapper CLI (a `bin/<name>.py` invocation) MUST resolve the wrapper
through `$LIVESPEC_CORE_ROOT`, and MUST NOT:

- use `uv run` (the installer flattens `.claude-plugin/` and omits the
  `uv` project files; the wrappers run under bare `python3`);
- use a literal `.claude-plugin/scripts` path (the binding must resolve
  the script through the core-root variable, not a fixed relative path);
- use the Driver's own plugin-root placeholder (`CLAUDE_PLUGIN_ROOT`),
  which resolves to the DRIVER root — the Driver bundle carries no core
  `bin/` wrappers, so this would resolve to a path with no wrapper. The
  Driver's own plugin-root placeholder remains CORRECT for Driver-owned
  bundle assets — the hook bundle, and the core-root resolver of
  §"Core-root resolution" — and this prohibition does not reach them.

The blessed form is `python3 "$LIVESPEC_CORE_ROOT/scripts/bin/<name>.py" …`.
`check_plugin_structure` walks every `SKILL.md`, tracks fenced regions,
and emits one violation per offending invocation line.

## Hook bundle

The Driver SHIPS a Claude Code hook bundle at `.claude-plugin/hooks/`:
a `hooks.json` registration plus one fail-open script per hook. Every hook is a Python script invoked by the harness as
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`; the cross-Driver
no-shadow-ledger hook (`no_shadow_ledger.py`) is the declared neutral
shared body and ships byte-identically in both Drivers' bundles (per
`livespec/SPECIFICATION/contracts.md`, cross-Driver single-sourcing).
The Driver's own plugin-root placeholder IS correct — the hooks are
Driver-owned and live in the Driver bundle. The bundle's *existence and wiring* are this repo's
contract; the hooks' *behavioral disciplines and postures* (the
fail-open requirement, block-vs-warn, the gating predicates) are owned
upstream by `livespec/SPECIFICATION/contracts.md`, which this repo
realizes. The script implementations and their
unit tests live in THIS repo (`tests/hooks/`).

The bundle carries four upstream-required hooks:

- a **PreToolUse** hook on `Write` that intercepts auto-memory writes
  (`Write(**/memory/*.md)`) in livespec-governed projects and
  intent-routes the would-be write by what it IS: trackable work to the
  active impl-plugin's `/<plugin>:capture-work-item` skill (resolved from
  `.livespec.jsonc` `implementation.plugin`); spec-level rules to
  `/livespec:propose-change`; durable agent guidance, learned preferences,
  and conventions to `AGENTS.md` or a referenced `.ai/<topic>.md` file;
  and only genuinely session-only notes may be dropped. A no-op
  pass-through when the project is not livespec-governed;
- a **PreToolUse** primary-checkout Playwright guard
  (`primary_checkout_playwright_guard.py`) registered in `hooks.json`
  for every `mcp__playwright__*` tool. Its behavioral discipline and
  posture are owned by livespec core's Driver-shipped-hooks contract;
  this Driver owns the Python entry point, its registration, and its
  executable coverage under `tests/hooks/`;
- a **Stop** plan-persistence hook that warns when the last assistant
  turn carried substantial planning artifacts (headings / table rows /
  list items above thresholds) with no persisting tool call in the
  window; WARN-only, always exit 0;
- a **Stop** no-shadow-ledger hook (`no_shadow_ledger.py`) that warns
  when the last turn PERSISTED a planning artifact — a handoff, or any
  markdown file under a `plan/` or `prompts/` directory — whose written
  content carries markdown checkbox task-list items (`[ ]` / `[x]`) at or
  above a mechanical threshold, directing the agent to derive status from
  the work-item ledger instead of embedding a parallel work queue
  (`livespec/SPECIFICATION/non-functional-requirements.md`); WARN-only,
  always exit 0, never auto-edits. Its detection body is single-sourced
  and ships
  BYTE-IDENTICALLY in both Drivers' bundles per
  `livespec/SPECIFICATION/contracts.md`, cross-Driver single-sourcing.

Adding or removing a hook, renaming a hook surface, or changing a hook's
posture requires a propose-change cycle against the upstream
Driver-shipped hooks contract; the mechanical detection internals
(matcher predicates, artifact thresholds) are Driver implementation
detail and MAY be tuned without a spec cycle, provided the postures hold.

## Versioning

`plugin.json.version` is the single source of truth for the shipped
Driver plugin's version and is auto-managed by `release-please` from
per-commit Conventional Commits. `marketplace.json` MUST NOT carry a
`version` field. This mirrors livespec core's `contracts.md`;
the Driver follows the same release mechanism for
its own plugin artifact.

## CLI end-to-end harness contract

This Driver's slash-command surface MUST be covered by a top-of-pyramid,
user-surface end-to-end test whose sole interaction surface is the `claude` CLI
binary. The harness installs livespec core plus this Driver
(`livespec-driver-claude`), then drives the Driver's slash-command bindings
end-to-end over core's prose and wrapper CLIs. This tier is a sibling to core's
wrapper-chain tier (`livespec/SPECIFICATION/contracts.md`): it adds a
higher tier, replaces neither, and both coexist in CI.
Codex and future Drivers need their own equivalent user-surface proof when they
claim a distributed Driver surface.

1. **Sole entry point is the `claude` CLI binary.** Setup MUST pre-populate a
   tmp `HOME` with `~/.claude/settings.json` declaring the core, Claude Driver,
   and orchestrator-plugin marketplaces and enabled plugins (or run `claude -p
   "/plugin install …"` as the first step). Every workflow step MUST be a
   `claude -p` subprocess invocation issuing a slash command, multi-turn via
   `--continue` / `--resume <id>`. The harness MUST NOT reach around to wrapper
   Python files and MUST NOT depend on core cache layout. The claude-agent-sdk
   programmatic surface MUST NOT be used here — the SDK is the wrapper-chain
   tier, not this tier.

2. **Core-and-Driver scope.** Orchestrator-side end-to-end coverage is owned by
   each orchestrator's own repository and specification. This harness MAY
   exercise the cross-boundary seam only through the three config-named
   orchestrator CLIs per `livespec/SPECIFICATION/contracts.md` (e.g.
   against a stub orchestrator
   fixture); it MUST NOT exercise that seam through plugin installation or skill
   enumeration.

3. **Structural Driver-skill discovery.** Skill enumeration MUST walk
   `<installed-driver-plugin>/skills/*/SKILL.md` in the installed
   `livespec-driver-claude` plugin's location, and the plugin slash-command
   prefix MUST be read from the Driver plugin's `plugin.json` `name` field.
   There MUST be no parallel manifest file; the Driver plugin directory
   structure is the canonical source of truth for this Claude-specific e2e
   tier. Core's installed plugin cache MUST NOT be expected to contain a
   `skills/` tree.

4. **Per-skill fixtures as a parallel filesystem convention.** A fixtures
   directory (suggested `tests/e2e-cli/fixtures/<skill>/`) MUST hold a
   `prompt.md` (text piped to `claude -p`) and an `expected_files.txt`
   (paths that MUST exist afterward) per skill. Discovery walks the same way:
   directory present == fixture exists.

5. **Time-bomb coverage gate (fail-closed).** The harness MUST assert that every
   discovered skill has a fixture — i.e. the set difference
   `discovered_skills − fixtured_skills` is empty — and MUST fail the run
   otherwise. A new skill added to the plugin trips the gate until either
   (a) a fixture directory is added, or (b) the skill is explicitly listed in an
   `EXEMPT_SKILLS` table with a written justification.

6. **Single canonical implementation in `livespec-dev-tooling`.** The harness
   itself (driver, fixtures loader, discovery, coverage gate, step orchestrator)
   MUST ship from `livespec-dev-tooling` and be consumed via the existing
   pin-bump dependency flow; the consuming repo wires the imported test function
   into its own pytest collection.
