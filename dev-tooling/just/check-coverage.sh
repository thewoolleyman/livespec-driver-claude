#!/usr/bin/env bash
set -euo pipefail

if [[ -f .coverage ]]; then
    echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
    env -u COVERAGE_FILE uv run coverage report --fail-under=100
else
    echo ":: check-coverage: no .coverage data file (CI standalone job); running the suite"
    env -u COVERAGE_FILE uv run pytest tests/hooks/ --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
fi

status=0
env -u COVERAGE_FILE uv run python -m livespec_dev_tooling.checks.per_file_coverage || status=$?
# Consume-once (livespec-dev-tooling-yilyxr.8): all reads done; deleting the
# data file means no later standalone run can report from stale coverage.
rm -f .coverage
exit "$status"
