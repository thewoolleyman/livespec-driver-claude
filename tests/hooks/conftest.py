"""Shared fixtures for the plugin-shipped hook tests.

The shipped hooks publish best-effort OTLP verdict spans through
`.claude-plugin/hooks/_guard_telemetry.py`, whose default endpoint is the real
host receiver — reachable from a Fabro sandbox and from the maintainer's host
alike. An unpinned test run would therefore publish thousands of synthetic
verdicts into the live Honeycomb dataset, from fixture commands that never ran.

Pinning the endpoint at a port nothing listens on keeps the suite off the wire.
It is not a mock: the hooks still build a real payload and still attempt a real
POST, so every test in this tree exercises the SAME fail-open path an operator
gets on a host with no receiver — the connection is refused immediately, the
failure is swallowed, and the verdict is unchanged.
"""

from __future__ import annotations

import pytest

__all__: list[str] = []

_ENDPOINT_ENV = "LIVESPEC_SANDBOX_OTEL_ENDPOINT"
_UNSERVED_ENDPOINT = "http://127.0.0.1:1"


@pytest.fixture(autouse=True)
def _offline_guard_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENDPOINT_ENV, _UNSERVED_ENDPOINT)
