# shellcheck shell=bash
# Pre-check helpers for scripts/gate.sh. Sourced by gate.sh and tests/test_skill_gate_precheck.py.

gate_die() { echo "GATE_FAIL: $*" >&2; return 1; }

# Reject worktree dirs whose basename has a hyphen (breaks python imports of the checkout).
gate_check_wt_name() {
  local base sug; base=$(basename "$1"); sug=${base//-/}
  case "$sug" in wt_*) ;; *) sug="wt_$sug";; esac
  case "$base" in *-*) gate_die "worktree name '$base' contains '-'; use e.g. $sug (hyphens break imports)"; return 1;; esac
  [ -d "$1" ] || { gate_die "worktree dir $1 not found"; return 1; }
}

# Fail if node_modules already exists in target (cp -al would nest/overwrite).
gate_check_no_node_modules() {
  if [ -e "$1/node_modules" ] || [ -L "$1/node_modules" ]; then
    gate_die "$1/node_modules already exists before cp -al; remove it (rm -rf $1/node_modules) and rerun"; return 1
  fi
}

# Fail if another pytest process is running (excluding ourselves).
gate_check_no_pytest() {
  local pids; pids=$(pgrep -f "${GATE_PYTEST_PATTERN:-python.* -m pytest}" | grep -vx "$$" || true)
  if [ -n "$pids" ]; then
    gate_die "another pytest is running (pids: $(echo $pids)); wait or kill it before running the gate"; return 1
  fi
}

# Fail if any listed TCP port is busy on 127.0.0.1.
gate_check_ports_free() {
  local p busy=""
  for p in "$@"; do
    if (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then busy="$busy $p"; fi
  done
  [ -z "$busy" ] || { gate_die "e2e port(s) busy:$busy; stop the old server (ss -ltnp | grep <port>)"; return 1; }
}

# Count "error" lines in a pytest log, ignoring pytest summary words like "0 errors" not present
# and test names. Prints matching lines; returns 1 if any.
gate_check_log_errors() {
  local hits
  hits=$(grep -nE '(^|[^A-Za-z_])(error|ERROR)([^A-Za-z_]|$)' "$1" | grep -vE '^[0-9]+:(PASSED|SKIPPED) ' || true)
  if [ -n "$hits" ]; then echo "$hits" | head -20 >&2; gate_die "error lines found in $1"; return 1; fi
}

# Tail of a failed --co log without pytest's own "N/M tests collected, K error" summary line
# (that partial N would contradict collected=COLLECTION_ERROR).
gate_collect_err_tail() {
  tail -20 "$1" | grep -vE '^[0-9]+(/[0-9]+)? tests? (collected|selected)'
  return 0
}

# --- #724: node-unit tests (tests/js/*.ts run through rolldown + node) ---
# Same readiness condition as tests/conftest.py node_ready(): a `node` binary and node_modules/.bin/rolldown.
# Without both, the frontend unit tests skip silently, so the gate must never count that run as green.
gate_node_ready() {
  local wt=${1:?usage: gate_node_ready <worktree>}
  command -v node >/dev/null 2>&1 || {
    gate_die "node-unit: node not found in PATH; install Node so the frontend unit tests can run"; return 1; }
  [ -x "$wt/node_modules/.bin/rolldown" ] || {
    gate_die "node-unit: $wt/node_modules/.bin/rolldown missing; run npm ci so the frontend unit tests can run"; return 1; }
  return 0
}

# True when the report written by tests/conftest.py says its node_ready() was true.
gate_node_unit_ready() {
  local json=${1:-}
  [ -n "$json" ] && [ -f "$json" ] || return 1
  grep -q '"ready"[[:space:]]*:[[:space:]]*true' "$json"
}

# Total written by tests/conftest.py (pytest_collection_finish) when GATE_NODE_UNIT_JSON is set.
# Prints the number; returns 1 with no output when the report is missing/unreadable.
gate_node_unit_total() {
  local json=${1:-} total
  [ -n "$json" ] && [ -f "$json" ] || return 1
  total=$(sed -n 's/.*"total"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$json" | head -1)
  [ -n "$total" ] || return 1
  printf '%s' "$total"
}
