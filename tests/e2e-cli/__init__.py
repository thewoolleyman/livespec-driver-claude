"""CLI end-to-end test package — the top-of-pyramid tier.

Per livespec/SPECIFICATION/contracts.md §"CLI end-to-end harness
contract": this package wires the single canonical harness shipped
from `livespec-dev-tooling` (`livespec_dev_tooling.testing.cli_e2e`)
into this Driver repo's pytest collection. The consumer obligation
relocated here from livespec core together with the `/livespec:*`
skill bindings (W4 Driver extraction): the skills live in THIS repo's
`.claude-plugin/`, so the structural-discovery + fail-closed coverage
gate runs here. The `mock` tier (LIVESPEC_E2E_HARNESS=mock) runs in
`just check`/CI: real structural skill discovery + real fixture
loading + the real fail-closed coverage gate, with only the
`claude -p` subprocess mocked via an injected deterministic runner.
The `real` tier drives the actual `claude` CLI binary and is NOT part
of `just check`.
"""

__all__: list[str] = []
