# justfile — livespec-driver-claude task runner.
#
# Family conventions, scaled to this repo's content (thin SKILL.md
# bindings + plugin manifests + the e2e-cli harness consumer):
#
# Authority: livespec/SPECIFICATION/non-functional-requirements.md
#   §"Enforcement-suite invocation" — `just` is the canonical entry
#   point for every dev-tooling invocation. Lefthook and CI MUST
#   delegate to `just <target>`; direct tool invocations in hook/CI
#   configs are banned.
#
# Authority: livespec/SPECIFICATION/contracts.md
#   §"Pre-commit step ordering" — the gates wired here mirror the
#   spec-required ordering: 00-lint-autofix-staged, 01-commit-pairs-
#   source-and-test, 02-check-pre-commit at pre-commit;
#   no-commit-on-master + red-green-replay at commit-msg.
#
# Red-green-replay is ENFORCED here per epic livespec-gcp2 (maintainer
# directive 2026-06-25): red-green-replay is enforced fleet+adopter-
# wide regardless of any "no product Python" self-classification. A
# feat:/fix: commit with staged `.py` (the repo-local structural check
# plus the test suite) follows the Red->Green ritual; the gate is a
# no-op on commits with no staged `.py`, so a `ci:`/`docs:`/`chore:`
# commit passes it freely.

# Default to listing targets when no recipe is invoked.
default:
    @just --list

# ---------------------------------------------------------------
# First-time setup.
# ---------------------------------------------------------------

bootstrap:
    # Idempotent `livespec.primaryPath` on the primary checkout's
    # git-common-dir config (family-wide invariant per livespec/
    # SPECIFICATION/non-functional-requirements.md §"Primary-checkout
    # commit-refuse hook" / §"Commit-refuse hook bootstrap procedure").
    # The commit-refuse hook reads this config value to recognize the
    # primary checkout and refuse commits/pushes there, forcing every
    # edit through `git worktree add`.
    git config --file "$(git rev-parse --git-common-dir)/config" livespec.primaryPath "$(realpath "$(dirname "$(git rev-parse --git-common-dir)")")"
    # Install the consolidated git-hook-wrapper.sh as the pre-commit,
    # pre-push, AND commit-msg hooks. The single file carries BOTH the
    # canonical commit-refuse fingerprint (refuses at the primary
    # checkout) and the mise-managed lefthook delegation (fires the
    # per-hook gates at secondary worktrees), so one script satisfies the
    # refuse-at-primary contract and the gate-delegation everywhere. Uses
    # the git-common-dir hooks dir so the install is worktree-safe: from a
    # secondary worktree `.git` is a file and `mkdir -p .git/hooks` would
    # fail, whereas git-common-dir resolves to the shared hooks dir from
    # both the primary checkout and any worktree.
    mkdir -p "$(git rev-parse --git-common-dir)/hooks"
    cp dev-tooling/git-hook-wrapper.sh "$(git rev-parse --git-common-dir)/hooks/pre-commit"
    cp dev-tooling/git-hook-wrapper.sh "$(git rev-parse --git-common-dir)/hooks/pre-push"
    cp dev-tooling/git-hook-wrapper.sh "$(git rev-parse --git-common-dir)/hooks/commit-msg"
    chmod +x "$(git rev-parse --git-common-dir)/hooks/pre-commit" "$(git rev-parse --git-common-dir)/hooks/pre-push" "$(git rev-parse --git-common-dir)/hooks/commit-msg"
    # Harden the beads tenant-pointer dir to owner-only on first-touch (bd
    # recommends 0700; only the owning user's bd reads it — the Dolt server
    # connects over TCP and never reads this dir). Guarded: repos with no beads
    # tenant have no .beads.
    [ -d "$(dirname "$(git rev-parse --git-common-dir)")/.beads" ] && chmod 700 "$(dirname "$(git rev-parse --git-common-dir)")/.beads" || true
    # Idempotent worktree-root + mise-trust setup. Every git worktree in
    # the fleet lives under a single per-user root, ~/.worktrees/<repo>/
    # <branch> (per livespec/SPECIFICATION/non-functional-requirements.md
    # §"Worktree root and mise trust"). Registering that root as one of
    # mise's trusted_config_paths makes each freshly created worktree's
    # .mise.toml auto-trusted, so the first `mise exec` inside it never
    # stops on the "config not trusted" prompt — the failure that
    # otherwise wastes a tool round-trip on every new worktree. The grep
    # guard keeps the global ~/.config/mise/config.toml entry single on
    # repeated bootstraps; the value is the absolute $HOME-rooted path so
    # it resolves identically from any invocation site.
    mkdir -p "${HOME}/.worktrees"
    if ! mise settings get trusted_config_paths 2>/dev/null | grep -qF "${HOME}/.worktrees"; then mise settings add trusted_config_paths "${HOME}/.worktrees"; fi
    just ensure-plugins
    just ensure-codex-plugins

# Idempotent: `claude plugin marketplace add` / `install` / `update`
# all exit 0 when the target is already present. Core MUST be
# installed alongside this Driver — the bindings resolve core's
# prose/ and scripts/ from the installed livespec@livespec cache.
ensure-plugins:
    claude plugin marketplace add --scope project thewoolleyman/livespec
    claude plugin marketplace add --scope project thewoolleyman/livespec-driver-claude
    claude plugin install -s project livespec@livespec
    claude plugin install -s project livespec@livespec-driver-claude
    claude plugin update -s project livespec@livespec
    claude plugin update -s project livespec@livespec-driver-claude

# Idempotent host-wide Codex plugin provisioning. Codex does not support
# project-scoped plugin enablement, so these registrations intentionally land in
# the user's default CODEX_HOME and are visible to every repo on the host. Codex
# is an optional dogfooding runtime; bootstrap skips this target when the CLI is
# absent but fails on real install errors when Codex is present.
ensure-codex-plugins:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v codex >/dev/null 2>&1; then
        echo "codex CLI not found; skipping host-wide Codex plugin install." >&2
        exit 0
    fi
    codex plugin marketplace add thewoolleyman/livespec
    codex plugin marketplace add thewoolleyman/livespec-driver-codex
    codex plugin marketplace add thewoolleyman/livespec-orchestrator-beads-fabro
    codex plugin marketplace upgrade livespec
    codex plugin marketplace upgrade livespec-driver-codex
    codex plugin marketplace upgrade livespec-orchestrator-beads-fabro
    codex plugin add livespec@livespec
    codex plugin add livespec@livespec-driver-codex
    codex plugin add livespec-orchestrator-beads-fabro@livespec-orchestrator-beads-fabro

# ---------------------------------------------------------------
# Enforcement aggregate.
# ---------------------------------------------------------------

check:
    #!/usr/bin/env bash
    set -uo pipefail
    targets=(
        check-plugin-structure
        check-lint
        check-format
        check-hooks
        check-e2e-cli
        check-heading-coverage
    )
    failed=()
    for target in "${targets[@]}"; do
        echo "=== just ${target} ==="
        if ! just "${target}"; then
            failed+=("${target}")
        fi
    done
    if [ "${#failed[@]}" -gt 0 ]; then
        echo "FAILED targets: ${failed[*]}" >&2
        exit 1
    fi
    # Advisory-local green token — keyed on the current HEAD tree-hash so
    # check-pre-push can skip the full aggregate on a clean, unchanged tree.
    # || true: a write failure must never abort a successful check aggregate.
    # STRICTLY advisory-local; CI remains authoritative.
    uv run python -m livespec_dev_tooling.green_token write || true

# Structural gate for the plugin bundle: manifest validity, the
# 8-skill set, frontmatter names, and the fenced-invocation rules
# (must use $LIVESPEC_CORE_ROOT; never `uv run`, never a literal
# .claude-plugin/scripts path, never the Driver's own plugin-root
# placeholder). Stdlib-only — runs under bare python3.
check-plugin-structure:
    python3 dev-tooling/check_plugin_structure.py

check-lint:
    uv run ruff check .

check-format:
    uv run ruff format --check .

# Plugin-shipped Claude Code hook scripts (.claude-plugin/hooks/) —
# unit-tested as subprocesses with a mocked CLAUDE_PROJECT_DIR plus
# tmp_path fixture projects (work-item livespec-driver-claude-e1s).
check-hooks:
    uv run pytest tests/hooks/

# CLI end-to-end harness consumer (mock tier) — relocated from
# livespec core together with the bindings. Real structural skill
# discovery against .claude-plugin/, real fixture loading, the real
# fail-closed coverage gate; only the `claude -p` subprocess is
# mocked. Harness ships from livespec-dev-tooling per livespec/
# SPECIFICATION/contracts.md §"CLI end-to-end harness contract".
check-e2e-cli:
    LIVESPEC_E2E_HARNESS=mock uv run pytest tests/e2e-cli/

# Spec heading-coverage gate (shipped by livespec-dev-tooling): every
# `## ` H2 in each SPECIFICATION/ NLSpec file MUST have an entry in
# tests/heading-coverage.json. This keeps the coverage map in lockstep
# with the spec — adding or renaming a spec H2 without updating the
# registry fails the check. TODO entries (no per-heading test yet) warn
# locally and fail only when LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST
# is set; this binding repo leaves it UNSET (its H2s are guarded by
# check-plugin-structure / the hook tests / the e2e-cli harness rather
# than per-heading unit tests), so the gate enforces registration drift,
# not test-mapping completeness. The livespec doctor static phase stays
# on-demand via /livespec:doctor (no family repo wires it into CI).
check-heading-coverage:
    uv run python -m livespec_dev_tooling.checks.heading_coverage

# Commit-pair gate (shipped by livespec-dev-tooling): every commit
# touching source files also touches tests. Lefthook pre-commit is the
# load-bearing per-commit invocation (step 01); wired into the full
# aggregate too so the gate runs at pre-push + CI.
check-commit-pairs-source-and-test:
    uv run python -m livespec_dev_tooling.checks.commit_pairs_source_and_test

# Trailer-based Red->Green replay verification (hard gate; shipped by
# livespec-dev-tooling). Enforced here per epic livespec-gcp2. Invoked
# by the lefthook commit-msg stage with the commit-message file path as
# argv[1] (the load-bearing per-commit verifier). The canonical
# aggregate / `just check` invokes this with NO msg_path; the module
# then DERIVES the message from HEAD and validates the branch range.
check-red-green-replay *args:
    uv run python -m livespec_dev_tooling.checks.red_green_replay {{args}}

# Fast pre-commit subset (no test run; pre-push runs the full
# aggregate).
check-pre-commit:
    just check-plugin-structure
    just check-lint
    just check-format

check-pre-push:
    #!/usr/bin/env bash
    set -uo pipefail
    # Advisory-local green-token short-circuit: if the current HEAD tree was
    # already verified clean by a successful full `just check` run, skip the
    # full aggregate. The token is invalidated by any new commit (tree-hash
    # change) or an uncommitted worktree modification. STRICTLY advisory-local;
    # CI is authoritative — a token match never bypasses the remote gate.
    if uv run python -m livespec_dev_tooling.green_token check 2>&1; then
        echo ":: pre-push: green token matched — tree byte-identical to last green check; skipping full aggregate (CI is authoritative)"
        exit 0
    fi
    just check

# ---------------------------------------------------------------
# Pre-commit auxiliary gates.
# ---------------------------------------------------------------

# Ruff fix + format on staged .py files BEFORE the rest of the
# pre-commit gate runs. Non-blocking — unfixable issues fall through
# to check-lint / check-format inside `just check` later. Re-stages
# post-autofix bytes.
lint-autofix-staged:
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM | grep -E '\.py$' || true)
    if [[ -z "$staged" ]]; then
        exit 0
    fi
    echo "$staged" | xargs uv run ruff check --fix --exit-zero
    echo "$staged" | xargs uv run ruff format
    echo "$staged" | xargs git add
