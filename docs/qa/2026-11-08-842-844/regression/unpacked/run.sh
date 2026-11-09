#!/bin/sh
# Safe replay helper. This file does not run the probe by itself.
# Set QA844_TIP to a checkout you intend to test, then run this script.
# It copies the original probe in, runs pytest under GATE=1, then deletes the copy.
# Do not commit the copy. Do not point this at a vendor. Do not drop GATE or the guard.
set -eu
PACK=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
if [ -z "${QA844_TIP:-}" ]; then
  echo "Refusing to run: set QA844_TIP to the checkout under test." >&2
  echo "Required: GATE=1, PYTHONPATH includes ${PACK}/guard, no WAVESPEED_API_KEY, no real secret paths." >&2
  echo "This pack was not executed against a new tip when it was built." >&2
  exit 2
fi
if [ ! -d "$QA844_TIP/tests/fixtures/svg826" ]; then
  echo "Refusing to run: $QA844_TIP has no tests/fixtures/svg826." >&2
  exit 2
fi
export GATE=1
export PYTHONPATH="${PACK}/guard${PYTHONPATH:+:$PYTHONPATH}"
unset WAVESPEED_API_KEY || true
unset KIE_API_KEY || true
cp "$PACK/tests/test_qa844_readonly_probe.py" "$QA844_TIP/tests/test_qa844_readonly_probe.py"
status=0
(
  cd "$QA844_TIP"
  python -m pytest -q --tb=short tests/test_qa844_readonly_probe.py
) || status=$?
rm -f "$QA844_TIP/tests/test_qa844_readonly_probe.py"
exit "$status"
