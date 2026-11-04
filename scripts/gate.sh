#!/usr/bin/env bash
# ComfyArt merge gate. Usage: scripts/gate.sh <slug>   (worktree = $GATE_ROOT/wt_<slug without '-'>)
# Env: GATE_ROOT (/workspace), GATE_MAIN (/workspace/ComfyArt, node_modules source),
#      GATE_PY (/workspace/ca-venv/bin/python), GATE_PORTS ("9392", e2e mock ports)
set -u -o pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$HERE/gate_lib.sh"
S=${1:?usage: gate.sh <slug>}
ROOT=${GATE_ROOT:-/workspace}; MAIN=${GATE_MAIN:-$ROOT/ComfyArt}; PY=${GATE_PY:-$ROOT/ca-venv/bin/python}
W=${GATE_WT:-$ROOT/wt_${S//-/}}
LOGDIR=$(mktemp -d "/tmp/gate_${S//-/}_XXXX"); RC=0
fail() { RC=1; echo "$S GATE_FAIL: $*"; }
archive() {
  [ "$RC" = 0 ] && return
  local a="$LOGDIR.failure.tar.gz"; tar -czf "$a" -C "$LOGDIR" . 2>/dev/null
  echo "$S FAILURE_LOGS: $a (tracebacks in $LOGDIR)"
}
cleanup() { cd "$W" 2>/dev/null && { git checkout -q -- dist 2>/dev/null; git clean -fdq dist; rm -rf node_modules; git status --porcelain | head -2; }; archive; echo "$S GATE_EXIT=$RC"; exit $RC; }
trap cleanup EXIT

gate_check_wt_name "$W" || { RC=2; exit 2; }
gate_check_no_node_modules "$W" || { RC=2; W=/nonexistent; exit 2; }
cd "$W"; cp -al "$MAIN/node_modules" node_modules

npx tsc --noEmit -p . >"$LOGDIR/tsc.log" 2>&1 && echo "$S TSC_OK" || fail "tsc (see $LOGDIR/tsc.log)"

stage() { # name, -k expr
  local n=$1 k=$2 co
  "$PY" -m pytest -q -p no:cacheprovider --co tests -k "$k" >"$LOGDIR/$n.collect.log" 2>&1; co=$?
  local cnt; cnt=$(grep -oE '^[0-9]+(/[0-9]+)? tests? (collected|selected)' "$LOGDIR/$n.collect.log" | grep -oE '^[0-9]+' | head -1)
  echo "$S $n: collected=${cnt:-?} collect_exit=$co"
  [ "$co" = 0 ] || { fail "$n collection exit $co"; tail -20 "$LOGDIR/$n.collect.log"; }
  "$PY" -m pytest -q -p no:cacheprovider tests -k "$k" >"$LOGDIR/$n.log" 2>&1; local ec=$?
  grep -E "^FAILED|^ERROR|passed|failed" "$LOGDIR/$n.log" | sed "s/^/$S $n: /"
  echo "$S $n: exit=$ec"
  [ "$ec" = 0 ] || fail "$n pytest exit $ec"
  gate_check_log_errors "$LOGDIR/$n.log" || fail "$n has error lines"
}
stage UNIT "skill and not e2e"
npx vite build >"$LOGDIR/build.log" 2>&1 && echo "$S BUILD_OK(local, not committed)" || fail "vite build"
gate_check_no_pytest || { fail "pytest already running"; exit; }
# shellcheck disable=SC2086
gate_check_ports_free ${GATE_PORTS:-9392} || { fail "ports busy"; exit; }
stage E2E "(skill and e2e) or 650 or creator"
