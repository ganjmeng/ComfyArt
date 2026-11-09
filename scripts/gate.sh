#!/usr/bin/env bash
# ComfyArt merge gate. Usage: scripts/gate.sh <slug> [--require-node | --allow-missing-node]
#   (worktree = $GATE_ROOT/wt_<slug without '-'>)
# Env: GATE_ROOT (/workspace), GATE_MAIN (/workspace/ComfyArt, node_modules source),
#      GATE_PY (/workspace/ca-venv/bin/python), GATE_PORTS ("9392", e2e mock ports),
#      GATE=1 (caller-side gate mode: a missing node is fatal, same as --require-node)
# #724: node-unit = the frontend unit tests that bundle src/ with rolldown and run it in node. The gate prints how
# many of them the selected stages contain, and when node/node_modules is missing it prints SKIPPED <n> and fails:
# a missing node is never a pass. --allow-missing-node is only for a deliberate Python-only local check.
set -u -o pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$HERE/gate_lib.sh"
REQUIRE_NODE=1   # #724: default strict — the gate needs node for tsc + vite build anyway
S=""
for a in "$@"; do
  case "$a" in
    --require-node) REQUIRE_NODE=1 ;;
    --allow-missing-node) REQUIRE_NODE=0 ;;
    -*) echo "gate.sh: unknown option '$a' (usage: gate.sh <slug> [--require-node|--allow-missing-node])" >&2; exit 2 ;;
    *) [ -z "$S" ] || { echo "gate.sh: unexpected argument '$a' (usage: gate.sh <slug> [--require-node|--allow-missing-node])" >&2; exit 2; }; S=$a ;;
  esac
done
[ "${GATE:-0}" = 1 ] && REQUIRE_NODE=1   # #724: GATE=1 in the caller env is strict even with --allow-missing-node
S=${S:?usage: gate.sh <slug> [--require-node|--allow-missing-node]}
ROOT=${GATE_ROOT:-/workspace}; MAIN=${GATE_MAIN:-$ROOT/ComfyArt}; PY=${GATE_PY:-$ROOT/ca-venv/bin/python}
W=${GATE_WT:-$ROOT/wt_${S//-/}}
LOGDIR=$(mktemp -d "/tmp/gate_${S//-/}_XXXX"); RC=0
fail() { RC=1; echo "$S GATE_FAIL: $*"; }
archive() {
  [ "$RC" = 0 ] && return
  local a="$LOGDIR.failure.tar.gz"; tar -czf "$a" -C "$LOGDIR" . 2>/dev/null
  echo "$S FAILURE_LOGS: $a (tracebacks in $LOGDIR)"
}
cleanup() {
  # Only touch the worktree if this run owns it (marker written after pre-checks passed).
  if [ -f "$W/.gate_owned" ] && [ "$(cat "$W/.gate_owned" 2>/dev/null)" = "$$" ]; then
    cd "$W" && { git checkout -q -- dist 2>/dev/null; git clean -fdq dist; rm -rf node_modules; rm -f .gate_owned; git status --porcelain | head -2; }
  fi
  archive; echo "$S GATE_EXIT=$RC"; exit $RC; }
trap cleanup EXIT
trap 'RC=130; exit 130' INT TERM

gate_check_wt_name "$W" || { RC=2; exit 2; }
gate_check_no_node_modules "$W" || { RC=2; exit 2; }
[ -e "$W/.gate_owned" ] && { echo "GATE_FAIL: $W/.gate_owned exists (another gate run, or stale marker: remove it)" >&2; RC=2; exit 2; }
# concurrency pre-checks before ANY pytest stage (repeated before E2E)
gate_check_no_pytest || { RC=2; exit 2; }
# shellcheck disable=SC2086
gate_check_ports_free ${GATE_PORTS:-9392} || { RC=2; exit 2; }
cd "$W"; echo "$$" > .gate_owned; cp -al "$MAIN/node_modules" node_modules

# --- #724: node-unit preflight — count the frontend unit tests and never skip them silently ---
NODE_READY=0
NODE_SKIP_ENV=""
if gate_node_ready "$W" 2>"$LOGDIR/node-ready.err"; then
  NODE_READY=1
else
  cat "$LOGDIR/node-ready.err" >&2
  # Count what cannot run: collect with the node tests forced to skip; conftest writes the report. An unrelated
  # import error must not cost the SKIPPED count, hence --continue-on-collection-errors.
  env -u WAVESPEED_API_KEY -u KIE_API_KEY GATE=1 COMFYART_SKIP_NODE_TESTS=1 \
    GATE_NODE_UNIT_JSON="$LOGDIR/node-unit.json" \
    "$PY" -m pytest -q -p no:cacheprovider --co --continue-on-collection-errors \
    tests -k "not e2e" -m "not gate_skip" >"$LOGDIR/node-unit.collect.log" 2>&1
  NODE_UNIT_N=$(gate_node_unit_total "$LOGDIR/node-unit.json") || NODE_UNIT_N="?"
  echo "$S node-unit: SKIPPED $NODE_UNIT_N tests (node/node_modules missing; npm ci in $MAIN)"
  if [ "$REQUIRE_NODE" = 1 ]; then
    fail "node-unit: $NODE_UNIT_N node tests cannot run; install node + npm ci (or --allow-missing-node for a Python-only check)"
    exit 1
  fi
  NODE_SKIP_ENV="COMFYART_SKIP_NODE_TESTS=1"
fi

npx tsc --noEmit -p . >"$LOGDIR/tsc.log" 2>&1 && echo "$S TSC_OK" || fail "tsc (see $LOGDIR/tsc.log)"

stage() { # name, -k expr  (#712: every stage also drops @pytest.mark.gate_skip tests; each carries a reason + issue)
  local n=$1 k=$2 co
  # #724: the node-unit report counts the node tests the stage really selected; -u COMFYART_SKIP_NODE_TESTS keeps
  # an inherited "skip the frontend tests" flag from turning a gate run green.
  # shellcheck disable=SC2086
  env -u WAVESPEED_API_KEY -u KIE_API_KEY -u COMFYART_SKIP_NODE_TESTS GATE=1 $NODE_SKIP_ENV \
    GATE_NODE_UNIT_JSON="$LOGDIR/$n.node-unit.json" \
    "$PY" -m pytest -q -p no:cacheprovider --co tests -k "$k" -m "not gate_skip" >"$LOGDIR/$n.collect.log" 2>&1; co=$?
  if [ "$co" != 0 ]; then   # no count on a broken collection (pytest's partial N would mislead)
    echo "$S $n: collected=COLLECTION_ERROR collect_exit=$co"; gate_collect_err_tail "$LOGDIR/$n.collect.log"
    fail "$n collection exit $co"; return
  fi
  local cnt; cnt=$(grep -oE '^[0-9]+(/[0-9]+)? tests? (collected|selected)' "$LOGDIR/$n.collect.log" | grep -oE '^[0-9]+' | head -1)
  echo "$S $n: collected=${cnt:-?} collect_exit=$co"
  if [ "$n" = UNIT ] && [ "$NODE_READY" = 1 ]; then
    local nn
    if nn=$(gate_node_unit_total "$LOGDIR/$n.node-unit.json") && [ "$nn" -gt 0 ]; then
      gate_node_unit_ready "$LOGDIR/$n.node-unit.json" || fail "$n node-unit: conftest reports node not ready; $nn node tests would skip"
      echo "$S $n node-unit: $nn tests (node $(node -v 2>/dev/null || echo '?'))"
    else
      fail "$n node-unit: no node tests counted although node is ready (report $LOGDIR/$n.node-unit.json)"
    fi
  fi
  local t0=$SECONDS
  # #712 no-spend: paid keys unset, GATE=1 turns on the conftest socket guard (localhost only)
  # shellcheck disable=SC2086
  env -u WAVESPEED_API_KEY -u KIE_API_KEY -u COMFYART_SKIP_NODE_TESTS GATE=1 no_proxy='*' $NODE_SKIP_ENV \
    "$PY" -m pytest -q -rs -p no:cacheprovider tests -k "$k" -m "not gate_skip" >"$LOGDIR/$n.log" 2>&1; local ec=$?
  echo "$S $n: duration=$((SECONDS - t0))s"
  grep -E "^FAILED|^ERROR|passed|failed" "$LOGDIR/$n.log" | sed "s/^/$S $n: /"
  echo "$S $n: exit=$ec"
  [ "$ec" = 0 ] || fail "$n pytest exit $ec"
  gate_check_log_errors "$LOGDIR/$n.log" || fail "$n has error lines"
}
stage UNIT "not e2e"  # #712: the whole unit suite, not only names containing "skill"
npx vite build >"$LOGDIR/build.log" 2>&1 && echo "$S BUILD_OK(local, not committed)" || fail "vite build"
gate_check_no_pytest || { fail "pytest already running"; exit; }
# shellcheck disable=SC2086
gate_check_ports_free ${GATE_PORTS:-9392} || { fail "ports busy"; exit; }
stage E2E "(skill and e2e) or 650 or creator or (e2e and 712)"
