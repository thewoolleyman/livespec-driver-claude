# tests/e2e-cli/

The CLI end-to-end harness CONSUMER for this Driver repo, relocated
from livespec core together with the `/livespec:*` skill bindings (W4
Driver extraction). The harness itself ships from
`livespec-dev-tooling` (`livespec_dev_tooling.testing.cli_e2e`, pinned
in pyproject.toml); this directory only wires it into pytest.

- `test_cli_e2e.py` — the consumer: mock-tier full round-trip
  (real structural discovery against `.claude-plugin/`, real fixture
  loading, the real fail-closed coverage gate, mocked `claude -p`
  runner) plus the red-baseline proving the gate fails closed.
- `fixtures/<skill>/prompt.md` (+ optional `expected_files.txt`) —
  one fixture per discovered skill. A skill added to
  `.claude-plugin/skills/` without a fixture here trips the
  fail-closed coverage gate.
- `conftest.py` — sys.path setup, `GIT_*` env scrubbing, and the
  `mock_only` auto-skip under `LIVESPEC_E2E_HARNESS=real`.

Run via `just check-e2e-cli` (mock tier; part of `just check` and the
CI matrix).
