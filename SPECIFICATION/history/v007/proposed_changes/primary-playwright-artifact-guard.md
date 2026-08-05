---
topic: primary-playwright-artifact-guard
author: gpt-5.6
created_at: 2026-08-05T22:51:17Z
---

## Proposal: Realize the primary-checkout Playwright guard in the Claude Driver

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Extend the Driver-owned hook-bundle wiring to ship and register the primary-checkout Playwright guard ratified by livespec core, with an integration-tier scenario mapping to the Driver hook tests.

### Motivation

A Claude Code browser_take_screenshot call used a relative filename while running from the livespec-dev-tooling primary checkout and created install-livespec-pr-bot.png there. The same MCP server left ignored .playwright-mcp artifacts in several fleet and adopter primary checkouts. The existing Bash-only repository guard cannot intercept MCP tool calls, so the fleet needs the upstream-ratified guard realized once in the project-enabled Claude Driver.

### Proposed Changes

In contracts.md section 'Hook bundle', change the required bundle count from three to four and add the Driver-owned primary_checkout_playwright_guard.py wiring: hooks.json registers it for every mcp__playwright__* PreToolUse call, and tests/hooks/ owns its executable behavior coverage. Preserve upstream ownership of its behavior and posture. In scenarios.md, add a Driver-realization scenario proving an installed hook denies a Playwright call at a livespec-governed primary checkout before artifacts are created while allowing the same call from a linked worktree. Map that scenario and the Hook bundle heading to an integration-tier test in tests/heading-coverage.json. The implementation must remain standard-library-only and fail open unless the cwd positively resolves to a governed primary checkout.
