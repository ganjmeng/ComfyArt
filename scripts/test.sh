#!/usr/bin/env sh
# #131: install the node deps the frontend tests need (once), then run pytest. Extra args go to pytest.
set -e
cd "$(dirname "$0")/.."
[ -x node_modules/.bin/rolldown ] || npm ci --no-audit --no-fund
exec python3 -m pytest "$@"
