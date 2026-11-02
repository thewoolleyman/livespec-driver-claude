#!/usr/bin/env bash
set -euo pipefail

just check-plugin-structure
just check-lint
just check-format
