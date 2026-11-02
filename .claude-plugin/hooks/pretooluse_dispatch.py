#!/usr/bin/env python3
"""Single entry point for the Driver's Bash-matched PreToolUse guards."""

from __future__ import annotations

__all__: list[str] = []

GUARD_MODULE_NAMES = (
    "tmux_fleet_guard",
    "github_rate_limit_guard",
    "block_raw_bd_create",
    "fleet_host_guard",
    "block_auto_memory",
)


def main() -> int:
    """Accept an empty dispatcher while the guard evaluation is introduced."""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
