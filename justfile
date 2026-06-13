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
# This repo carries NO product Python (the only .py files are the
# repo-local structural check and the test suite), so the
# red-green-replay ritual and the full canonical check inventory do
# not apply here.

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
    # Install the commit-refuse hook (vendored from livespec-dev-
    # tooling — see dev-tooling/livespec-commit-refuse-hook.sh) at
    # pre-commit AND pre-push. Refuses at the primary checkout;
    # delegates to lefthook at secondary worktrees via mise.
    mkdir -p .git/hooks
    cp dev-tooling/livespec-commit-refuse-hook.sh .git/hooks/pre-commit
    cp dev-tooling/livespec-commit-refuse-hook.sh .git/hooks/pre-push
    cp dev-tooling/git-hook-wrapper.sh .git/hooks/commit-msg
    chmod +x .git/hooks/pre-commit .git/hooks/pre-push .git/hooks/commit-msg
    just ensure-plugins

# Idempotent: `claude plugin marketplace add` / `install` / `update`
# all exit 0 when the target is already present. Core MUST be
# installed alongside this Driver — the bindings resolve core's
# prose/ and scripts/ from the installed livespec@livespec cache.
ensure-plugins:
    claude plugin marketplace add thewoolleyman/livespec
    claude plugin marketplace add thewoolleyman/livespec-driver-claude
    claude plugin install livespec@livespec
    claude plugin install livespec@livespec-driver-claude
    claude plugin update livespec@livespec
    claude plugin update livespec@livespec-driver-claude

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
