# constraints.md — livespec-driver-claude

Architecture-level constraints the Driver bindings, hook bundle, and
structural gate honor. Contracts (`contracts.md`) say what the seam must
look like; these constraints say what the implementation may and may not
do to realize it.

## Inherited from livespec

Every constraint in `livespec/SPECIFICATION/constraints.md` that applies
to a Driver binding applies here unmodified; this tree does not relax or
restate them. Where an inherited constraint and a Driver-local one appear
to conflict, the upstream constraint wins.

## Binding constraints

- A binding is **thin**: it carries no behavior of its own beyond
  resolving `<core-root>`, reading core's operation prose, and
  dispatching the config-named CLI. All dialogue capture, content
  generation, and structured-finding interpretation are dictated by
  core's prose, not invented in the binding.
- Each `SKILL.md` is self-contained and follows the family's three-part
  binding shape; a binding MUST NOT depend on another binding's files.
- A thin-transport binding (e.g. `next`) MUST NOT accrete ranking,
  filtering, formatting, a confirmation dialogue, or an opt-in flag — all
  such logic lives in the backing core wrapper.
- The Driver bundle ships NO `scripts/` tree and NO wrapper CLIs: those
  are core-owned and resolved at runtime. The bundle ships bindings,
  hooks, and the manifest only.

## Resolution-substrate constraints

- The core-root resolution order (`contracts.md` §"Core-root resolution")
  is fixed; a binding MUST walk it in order and MUST NOT short-circuit to
  a hardcoded path.
- A binding MUST NOT use the Driver's own plugin-root placeholder to reach
  core scripts (it resolves to the Driver root, which has no `scripts/`).
- A binding MUST NOT assume a single installation shape (dev-mode
  checkout vs. installed cache vs. operator override are all valid).

## Structural-check constraints

- `dev-tooling/check_plugin_structure.py` MUST be stdlib-only: it runs
  under bare `python3` with no virtualenv, so it can gate commits and CI
  before any environment is provisioned.
- The check is **fail-closed**: it exits non-zero with one diagnostic per
  violation on stderr, and exits zero only when every assertion holds.

## Forbidden patterns

- `uv run`, a literal `.claude-plugin/scripts` path, or the Driver's own
  plugin-root placeholder in any fenced wrapper invocation inside a
  `SKILL.md`.
- An extra skill directory, a missing binding, or a `SKILL.md` whose
  frontmatter `name` disagrees with its directory.
- Renaming the plugin name (`livespec`) or the marketplace name
  (`livespec-driver-claude`) without a propose-change cycle.
- Committing or pushing at the primary checkout; passing `--no-verify`;
  editing tracked files outside a dedicated worktree (see
  `non-functional-requirements.md` §"Inherited from livespec").
