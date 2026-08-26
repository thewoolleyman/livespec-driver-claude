"""Unit tests for the shipped guard-verdict OTLP exporter.

The module under test does not exist until the Green leg, so it is imported
INSIDE each test via `importlib` rather than at module top: a top-level import
would make the Red leg a collection error, which proves unimportability rather
than unimplemented behaviour.
"""

from __future__ import annotations

import importlib
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType, TracebackType
from typing import cast

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
_MODULE_PATH = _HOOKS_DIR / "_guard_telemetry.py"
_ENDPOINT_ENV = "LIVESPEC_SANDBOX_OTEL_ENDPOINT"
_SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


class _FakeResponse:
    """The context-manager shape `urlopen` returns, recording that it was read."""

    def __init__(self) -> None:
        self.read_count = 0

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def read(self) -> bytes:
        self.read_count += 1
        return b""


def _load_telemetry() -> ModuleType:
    # The Red anchor: a genuine assertion that fails before any import runs.
    assert _MODULE_PATH.is_file(), f"{_MODULE_PATH} is not shipped beside the guard"
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("_guard_telemetry", None)
    return importlib.import_module("_guard_telemetry")


def _attributes(*, payload: dict[str, object]) -> dict[str, object]:
    """Flatten the one span's OTLP attribute list into a plain mapping."""
    resource_spans = cast("list[dict[str, object]]", payload["resourceSpans"])
    scope_spans = cast("list[dict[str, object]]", resource_spans[0]["scopeSpans"])
    spans = cast("list[dict[str, object]]", scope_spans[0]["spans"])
    raw = cast("list[dict[str, object]]", spans[0]["attributes"])
    out: dict[str, object] = {}
    for attribute in raw:
        value = cast("dict[str, object]", attribute["value"])
        out[cast("str", attribute["key"])] = next(iter(value.values()))
    return out


def _span(*, payload: dict[str, object]) -> dict[str, object]:
    resource_spans = cast("list[dict[str, object]]", payload["resourceSpans"])
    scope_spans = cast("list[dict[str, object]]", resource_spans[0]["scopeSpans"])
    spans = cast("list[dict[str, object]]", scope_spans[0]["spans"])
    return spans[0]


def _build(
    *,
    telemetry: ModuleType,
    matched_rule: str | None = "loop+read",
    gh_cached: bool = False,
    gh_at_command_position: bool = True,
    session_id: str | None = None,
) -> dict[str, object]:
    payload = telemetry.build_verdict_payload(
        matched_rule=matched_rule,
        gh_cached=gh_cached,
        gh_at_command_position=gh_at_command_position,
        session_id=session_id,
        now_ns=1_700_000_000_000_000_000,
    )
    return cast("dict[str, object]", payload)


def test_the_exporter_ships_beside_the_guard_in_the_plugin_bundle() -> None:
    telemetry = _load_telemetry()

    assert telemetry.DATASET
    assert telemetry.DEFAULT_ENDPOINT.startswith("http")


def test_the_span_routes_to_its_honeycomb_dataset_by_service_name() -> None:
    telemetry = _load_telemetry()

    payload = _build(telemetry=telemetry)

    resource_spans = cast("list[dict[str, object]]", payload["resourceSpans"])
    resource = cast("dict[str, object]", resource_spans[0]["resource"])
    attributes = cast("list[dict[str, object]]", resource["attributes"])
    routed = {
        cast("str", attribute["key"]): cast("dict[str, str]", attribute["value"])["stringValue"]
        for attribute in attributes
    }
    assert routed["service.name"] == telemetry.DATASET


def test_a_deny_verdict_carries_the_rule_that_convicted_it() -> None:
    telemetry = _load_telemetry()

    attributes = _attributes(
        payload=_build(
            telemetry=telemetry,
            matched_rule="loop+mutation",
            gh_cached=False,
            gh_at_command_position=True,
        )
    )

    assert attributes["verdict"] == "rate_limited"
    assert attributes["matched_rule"] == "loop+mutation"
    assert attributes["gh_cached"] is False
    assert attributes["gh_at_command_position"] is True


def test_an_allow_verdict_still_carries_matched_rule_as_a_populated_column() -> None:
    """`matched_rule` is never absent: an omitted column cannot be grouped on."""
    telemetry = _load_telemetry()

    attributes = _attributes(
        payload=_build(
            telemetry=telemetry,
            matched_rule=None,
            gh_cached=True,
            gh_at_command_position=False,
        )
    )

    assert attributes["verdict"] == "allowed"
    assert attributes["matched_rule"] == "none"
    assert attributes["gh_cached"] is True
    assert attributes["gh_at_command_position"] is False


def test_the_span_is_a_zero_duration_point_event() -> None:
    telemetry = _load_telemetry()

    span = _span(payload=_build(telemetry=telemetry))

    assert span["startTimeUnixNano"] == span["endTimeUnixNano"]
    assert span["startTimeUnixNano"] == "1700000000000000000"


def test_the_span_carries_the_session_id_when_the_harness_supplies_one() -> None:
    telemetry = _load_telemetry()

    attributes = _attributes(payload=_build(telemetry=telemetry, session_id="abc-123"))

    assert attributes["session_id"] == "abc-123"


def test_the_span_omits_the_session_id_when_the_harness_supplies_none() -> None:
    telemetry = _load_telemetry()

    attributes = _attributes(payload=_build(telemetry=telemetry, session_id=None))

    assert "session_id" not in attributes


def test_no_command_text_ever_reaches_the_wire() -> None:
    """The record classifies the command; it never carries the command itself.

    Pinned as a CLOSED attribute set rather than as an absence: a substring
    search cannot express this (`gh_at_command_position` legitimately spells
    "command"), and the leak this guards against is a future field added for
    triage convenience, which an absence test would never see coming.
    """
    telemetry = _load_telemetry()

    payload = _build(telemetry=telemetry, session_id="abc-123")

    assert set(_attributes(payload=payload)) == {
        "verdict",
        "matched_rule",
        "gh_cached",
        "gh_at_command_position",
        "check_id",
        "session_id",
    }


def test_emit_posts_the_verdict_to_the_endpoint_named_in_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry = _load_telemetry()
    posted: list[tuple[str, dict[str, object]]] = []

    def _record(*, endpoint: str, payload: dict[str, object]) -> None:
        posted.append((endpoint, payload))

    monkeypatch.setattr(telemetry, "post_span", _record)
    monkeypatch.setenv(_ENDPOINT_ENV, "http://collector.invalid:4318")
    monkeypatch.setenv(_SESSION_ENV, "session-9")

    telemetry.emit_verdict(matched_rule="sleep+read", gh_cached=False, gh_at_command_position=True)

    assert len(posted) == 1
    endpoint, payload = posted[0]
    assert endpoint == "http://collector.invalid:4318"
    assert _attributes(payload=payload)["session_id"] == "session-9"


def test_emit_falls_back_to_the_default_endpoint_when_the_environment_is_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry = _load_telemetry()
    posted: list[str] = []

    def _record(*, endpoint: str, payload: dict[str, object]) -> None:
        assert payload
        posted.append(endpoint)

    monkeypatch.setattr(telemetry, "post_span", _record)
    monkeypatch.setenv(_ENDPOINT_ENV, "   ")
    monkeypatch.delenv(_SESSION_ENV, raising=False)

    telemetry.emit_verdict(matched_rule=None, gh_cached=False, gh_at_command_position=False)

    assert posted == [telemetry.DEFAULT_ENDPOINT]


def test_post_span_targets_the_traces_signal_of_the_receiver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry = _load_telemetry()
    seen: list[urllib.request.Request] = []
    response = _FakeResponse()

    def _fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        assert timeout > 0
        seen.append(request)
        return response

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    telemetry.post_span(endpoint="http://receiver:4318", payload=_build(telemetry=telemetry))

    assert len(seen) == 1
    assert seen[0].full_url == "http://receiver:4318/v1/traces"
    assert seen[0].get_method() == "POST"
    assert response.read_count == 1


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionRefusedError("no receiver"),
        urllib.error.URLError("unreachable"),
        ValueError("unknown url type"),
    ],
    ids=["refused", "unreachable", "malformed-endpoint"],
)
def test_post_span_swallows_every_telemetry_failure(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    telemetry = _load_telemetry()

    def _fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        assert request is not None
        assert timeout > 0
        raise failure

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    telemetry.post_span(endpoint="http://receiver:4318", payload=_build(telemetry=telemetry))


def test_the_transport_decision_is_recorded_beside_the_measurement() -> None:
    """The chosen transport, and why the rejected candidates lost, are written down."""
    telemetry = _load_telemetry()
    docstring = telemetry.__doc__

    assert docstring is not None
    assert "/v1/traces" in docstring
    assert "/v1/logs" in docstring
    assert "filelog" in docstring
