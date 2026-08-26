"""Best-effort OTLP export of one `github_rate_limit_guard` verdict per Bash call.

WHY THIS EXISTS. The guard's measured 40.5% false-positive rate
(`plan/github-rate-limit-guard-false-positives/research/001-measurement-and-architecture.md`)
could only be obtained by replaying the live decision function over a week of
local transcripts. `_log_event` writes structured JSON with a `check_id`, but
only on DENY, only to stderr, and stderr on a PreToolUse exit-0 is discarded;
the `agent-activity`/`claude-code` dataset carries `hook_name` and
`num_blocking` but no per-guard verdict. Nothing off the machine could answer
"how often does this guard convict a command that never ran `gh`".

This module makes the verdict itself the telemetry event, so the
false-positive SIGNATURE -- a `rate_limited` verdict whose
`gh_at_command_position` is false -- is a Honeycomb query rather than an
investigation:

    COUNT WHERE verdict = "rate_limited" AND gh_at_command_position = false
      / COUNT WHERE verdict = "rate_limited"

TRANSPORT DECISION. Three candidates; the live receiver settled it.

- **PreToolUse stderr.** Rejected outright. The harness discards a hook's
  stderr on exit 0, which is exactly the ALLOW half this work exists to add.
- **A local JSONL the otel collector tails.** Rejected. It needs a `filelog`
  receiver in the host collector's pipeline, and that config is host
  infrastructure no change in this repo can reach -- the records would accrue
  in a file nothing reads. It also drags in a path convention, rotation and
  cleanup for a signal the receiver can already take directly.
- **OTLP over HTTP to the host receiver.** CHOSEN. `livespec-step-timer`
  (`livespec_dev_tooling.otel_step_timer`) already exports this way from
  stdlib-only, no-virtualenv code, and the receiver routes a payload to its
  Honeycomb dataset by `service.name`, so no per-emitter provisioning is
  needed. Probing the live receiver also settled the SIGNAL: `POST /v1/traces`
  answers 200 and `POST /v1/logs` answers 404 -- there is no logs pipeline --
  so a verdict rides as a zero-duration SPAN rather than as an OTLP log record.

NO COMMAND TEXT. The record carries the CLASSIFICATION of a command, never the
command itself. A Bash command line routinely holds tokens, hostnames and
private paths; the replay corpus beside the tests is scrubbed for exactly those
and is scanned for leaks by its own test. The structured fields are what the
false-positive query needs -- `matched_rule` names the conjunction that
convicted, `gh_at_command_position` says whether there was a real `gh`
invocation to convict -- so shipping the text would buy triage detail at the
price of exporting secrets to a shared surface.

FAIL-OPEN, AND NEVER A CHANGED VERDICT. The guard computes its exit code BEFORE
calling here, so this module cannot move a verdict by returning. It cannot move
one by raising either: every input is an already-typed primitive, so the payload
shaping has no failure mode, and the one surface that can fail -- the network --
is narrowly suppressed in `post_span` (`OSError` covers connection-refused, DNS
and timeout; `URLError` and `ValueError` cover an unusable endpoint). A host
with no receiver refuses the connection immediately and the guard proceeds
unchanged. The timeout is deliberately far below the step timer's, because this
runs on the critical path of EVERY Bash tool call rather than once per sandbox
prepare step.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is from the standard library.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping

# Only the names that cross a module boundary. `build_verdict_payload` and
# `post_span` are internal seams of this exporter -- the guard calls
# `emit_verdict` and nothing else; the constants are named so a consumer can
# assert what the record routes to without restating the strings.
__all__: list[str] = [
    "DATASET",
    "DEFAULT_ENDPOINT",
    "emit_verdict",
]

# The receiver routes by `service.name`, so this string IS the Honeycomb
# dataset the verdicts land in. Kept separate from `agent-activity`: that
# dataset is the harness's own export and is not this hook's to shape.
DATASET = "agent-hooks"
DEFAULT_ENDPOINT = "http://172.17.0.1:4318"
_ENDPOINT_ENV = "LIVESPEC_SANDBOX_OTEL_ENDPOINT"
_SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
_SCOPE_NAME = "github_rate_limit_guard"
_SPAN_NAME = "github_rate_limit_guard.verdict"
_CHECK_ID = "github-rate-limit-guard-verdict"
# Half a second, against the step timer's two. This is on the critical path of
# every Bash tool call, so the ceiling is what an operator would tolerate as
# added latency on a host whose receiver has gone silent, not what a generous
# export would like.
_POST_TIMEOUT_S = 0.5
# The ALLOW half writes `"none"` rather than omitting the attribute. An absent
# attribute is an absent COLUMN in the dataset, and a column that only exists on
# denials cannot carry a `GROUP BY matched_rule` across the whole population --
# which is the query the allow half was added to make possible.
_NO_RULE = "none"


def build_verdict_payload(
    *,
    matched_rule: str | None,
    gh_cached: bool,
    gh_at_command_position: bool,
    session_id: str | None,
    now_ns: int,
) -> dict[str, object]:
    """Shape one verdict as a single-span OTLP/HTTP-JSON trace request.

    The span is zero-duration: a verdict is a point event, not an interval.
    int64 fields are JSON strings per the proto3-JSON mapping Honeycomb
    expects, and the trace/span ids are freshly random (an independent,
    un-parented span -- the harness's own trace is not reachable from a hook).
    """
    attributes: list[dict[str, object]] = [
        {
            "key": "verdict",
            "value": {"stringValue": "allowed" if matched_rule is None else "rate_limited"},
        },
        {"key": "matched_rule", "value": {"stringValue": matched_rule or _NO_RULE}},
        {"key": "gh_cached", "value": {"boolValue": gh_cached}},
        {"key": "gh_at_command_position", "value": {"boolValue": gh_at_command_position}},
        {"key": "check_id", "value": {"stringValue": _CHECK_ID}},
    ]
    if session_id:
        attributes.append({"key": "session_id", "value": {"stringValue": session_id}})
    span: dict[str, object] = {
        "traceId": os.urandom(16).hex(),
        "spanId": os.urandom(8).hex(),
        "name": _SPAN_NAME,
        "kind": 1,
        "startTimeUnixNano": str(now_ns),
        "endTimeUnixNano": str(now_ns),
        "attributes": attributes,
        "status": {"code": 1},
    }
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": DATASET}},
                    ],
                },
                "scopeSpans": [{"scope": {"name": _SCOPE_NAME}, "spans": [span]}],
            },
        ],
    }


def post_span(
    *, endpoint: str, payload: dict[str, object], timeout: float = _POST_TIMEOUT_S
) -> None:
    """Best-effort POST the OTLP payload to ``<endpoint>/v1/traces``.

    Swallows every expected network/URL failure so a telemetry outage can never
    surface into the guard's verdict: `OSError` covers connection-refused, DNS
    and timeout, `URLError` its urllib wrapper, and `ValueError` a malformed
    endpoint. On success or failure it returns None.
    """
    # The endpoint is a fixed http(s) receiver URL taken from the environment,
    # never a caller-supplied scheme, so no non-http handler is reachable here.
    request = urllib.request.Request(
        url=f"{endpoint}/v1/traces",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with (
        contextlib.suppress(urllib.error.URLError, OSError, ValueError),
        urllib.request.urlopen(request, timeout=timeout) as response,
    ):
        _ = response.read()


def emit_verdict(
    *,
    matched_rule: str | None,
    gh_cached: bool,
    gh_at_command_position: bool,
    environ: Mapping[str, str] = os.environ,
) -> None:
    """Publish one verdict record. `matched_rule` None IS the allow verdict."""
    payload = build_verdict_payload(
        matched_rule=matched_rule,
        gh_cached=gh_cached,
        gh_at_command_position=gh_at_command_position,
        session_id=environ.get(_SESSION_ENV) or None,
        now_ns=time.time_ns(),
    )
    endpoint = (environ.get(_ENDPOINT_ENV) or "").strip() or DEFAULT_ENDPOINT
    post_span(endpoint=endpoint, payload=payload)
