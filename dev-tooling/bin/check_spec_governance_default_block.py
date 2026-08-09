"""Verify this repo's commented spec_governance defaults block."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from livespec_runtime.spec_governance import verify_livespec_jsonc_default_block
from returns.result import Success

__all__: list[str] = ["main"]

_LOGGER = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    result = verify_livespec_jsonc_default_block(path=Path(".livespec.jsonc"))
    if isinstance(result, Success):
        _LOGGER.info(json.dumps(result.unwrap(), sort_keys=True))
        return 0
    _LOGGER.error(result.failure())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
