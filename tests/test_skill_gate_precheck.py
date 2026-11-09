"""Pre-check helpers of scripts/gate_lib.sh (gate hardening)."""
import os
import socket
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "scripts" / "gate_lib.sh"
ROOT = Path(__file__).resolve().parents[1]


def _run(fn: str, *args: str, env=None):
    q = " ".join(f"'{a}'" for a in args)
    return subprocess.run(["bash", "-c", f". '{LIB}'; {fn} {q}"], capture_output=True, text=True, env=env)


def test_rejects_hyphen_worktree(tmp_path):
    d = tmp_path / "wt_foo-bar"; d.mkdir()
    r = _run("gate_check_wt_name", str(d))
    assert r.returncode == 1 and "contains '-'" in r.stderr and "use e.g. wt_foobar " in r.stderr
    q = tmp_path / "qa-711h"; q.mkdir()
    assert "use e.g. wt_qa711h " in _run("gate_check_wt_name", str(q)).stderr
    ok = tmp_path / "wt_foobar"; ok.mkdir()
    assert _run("gate_check_wt_name", str(ok)).returncode == 0


def test_node_modules_exists_fails(tmp_path):
    assert _run("gate_check_no_node_modules", str(tmp_path)).returncode == 0
    (tmp_path / "node_modules").mkdir()
    r = _run("gate_check_no_node_modules", str(tmp_path))
    assert r.returncode == 1 and "already exists" in r.stderr


def test_busy_port_detected():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1)
    port = s.getsockname()[1]
    try:
        r = _run("gate_check_ports_free", str(port))
        assert r.returncode == 1 and "busy" in r.stderr
    finally:
        s.close()
    assert _run("gate_check_ports_free", str(port)).returncode == 0


def test_running_pytest_detected():
    # Real default pattern (no GATE_PYTEST_PATTERN override): a process whose cmdline is "python ... -m pytest".
    import os, sys, time
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "-m", "pytest"])
    try:
        time.sleep(0.2)
        env = {k: v for k, v in os.environ.items() if k != "GATE_PYTEST_PATTERN"}
        r = _run("gate_check_no_pytest", env=env)
        assert r.returncode == 1 and "another pytest" in r.stderr and str(p.pid) in r.stderr
    finally:
        p.kill()


def test_log_error_lines(tmp_path):
    good = tmp_path / "g.log"; good.write_text("....\n12 passed in 1.0s\n")
    assert _run("gate_check_log_errors", str(good)).returncode == 0
    bad = tmp_path / "b.log"; bad.write_text("ERROR tests/test_x.py - ImportError\n1 error in 0.1s\n")
    r = _run("gate_check_log_errors", str(bad))
    assert r.returncode == 1 and "error lines" in r.stderr


GATE = LIB.parent / "gate.sh"


def _gate_env(tmp_path, wt):
    import os
    return {**os.environ, "GATE_WT": str(wt), "GATE_MAIN": str(tmp_path / "main"),
            "GATE_PY": "/bin/false", "PATH": os.environ["PATH"]}


def test_rejected_worktree_keeps_sentinel_node_modules(tmp_path):
    wt = tmp_path / "wt_sent"; (wt / "node_modules").mkdir(parents=True)
    (wt / "node_modules" / "SENTINEL").write_text("keep")
    r = subprocess.run(["bash", str(GATE), "sent"], capture_output=True, text=True, env=_gate_env(tmp_path, wt))
    assert r.returncode == 2 and "already exists" in r.stderr
    assert (wt / "node_modules" / "SENTINEL").read_text() == "keep"
    assert not (wt / ".gate_owned").exists()


def test_unowned_interrupted_run_keeps_sentinel(tmp_path):
    # Stale marker from another run (not ours): gate must refuse and must not clean anything.
    import signal, time
    wt = tmp_path / "wt_unowned"; wt.mkdir()
    (wt / ".gate_owned").write_text("999999")
    (wt / "dist").mkdir(); (wt / "dist" / "SENTINEL").write_text("keep")
    r = subprocess.run(["bash", str(GATE), "unowned"], capture_output=True, text=True, env=_gate_env(tmp_path, wt))
    assert r.returncode == 2 and ".gate_owned exists" in r.stderr
    assert (wt / "dist" / "SENTINEL").exists() and (wt / ".gate_owned").read_text() == "999999"
    # Interrupt (SIGTERM) a run that is rejected before owning: sentinel node_modules survives.
    wt2 = tmp_path / "wt_intr"; (wt2 / "node_modules").mkdir(parents=True)
    (wt2 / "node_modules" / "SENTINEL").write_text("keep")
    p = subprocess.Popen(["bash", str(GATE), "intr"], env=_gate_env(tmp_path, wt2),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(0.05); p.send_signal(signal.SIGTERM); p.wait(10)
    assert (wt2 / "node_modules" / "SENTINEL").read_text() == "keep"
    assert not (wt2 / ".gate_owned").exists()


def test_collection_error_prints_no_count(tmp_path):
    # A broken collection must report COLLECTION_ERROR, never a misleading collected=N.
    src = (LIB.parent / "gate.sh").read_text()
    assert "collected=COLLECTION_ERROR" in src
    i_err, i_cnt = src.index("collected=COLLECTION_ERROR"), src.index('collected=${cnt:-?}')
    assert i_err < i_cnt and "return" in src[i_err:i_cnt]


def test_concurrency_checks_run_before_unit():
    src = (LIB.parent / "gate.sh").read_text()
    unit = src.index('stage UNIT')
    assert src.index("gate_check_no_pytest") < unit and src.index("gate_check_ports_free") < unit
    assert src.index("gate_check_no_pytest", unit) < src.index('stage E2E')


def test_collection_error_tail_drops_pytest_count_line(tmp_path):
    log = tmp_path / "u.collect.log"
    log.write_text("ERROR tests/test_bad.py - SyntaxError\n"
                   "345/3075 tests collected (2730 deselected), 1 error in 2.10s\n"
                   "1 test collected, 1 error in 0.1s\n")
    r = _run("gate_collect_err_tail", str(log))
    assert r.returncode == 0
    assert "SyntaxError" in r.stdout and "collected" not in r.stdout
    assert "gate_collect_err_tail" in (LIB.parent / "gate.sh").read_text()


# --- #712: UNIT runs the whole unit suite; only gate_skip tests (with reason + issue) drop out ---
def test_gate_unit_stage_runs_all_unit_tests():
    sh = (ROOT / "scripts" / "gate.sh").read_text()
    assert 'stage UNIT "not e2e"' in sh
    assert sh.count('-m "not gate_skip"') == 3  # #724 preflight collection + collect + run


def test_gate_skip_marker_registered():
    assert "gate_skip(reason)" in (ROOT / "pyproject.toml").read_text()


def test_every_gate_skip_names_reason_and_issue():
    """#712: every remaining gate_skip names a reason and an issue.

    #731/#802 cleared the marks on the failures that were fixed, so an empty set is valid.
    """
    import re
    hits = []
    for p in (ROOT / "tests").glob("test_*.py"):
        for m in re.finditer(r"@pytest\.mark\.gate_skip\((.*?)\)\n", p.read_text()):
            hits.append((p.name, m.group(1)))
    for name, args in hits:
        assert 'reason="' in args and re.search(r"#\d+", args), (name, args)


# --- #712 no-spend: gate stages unset paid keys and block outbound network ---
def test_gate_stages_unset_paid_keys_and_enable_guard():
    sh = (ROOT / "scripts" / "gate.sh").read_text()
    # #712 no-spend: every pytest invocation unsets the paid keys and runs with GATE=1. #724 added the node-unit
    # preflight collection, so there are three: preflight, stage collect, stage run.
    lines = [ln for ln in sh.splitlines() if "env -u WAVESPEED_API_KEY -u KIE_API_KEY" in ln]
    assert len(lines) == 3 and all("GATE=1" in ln for ln in lines), lines
    assert "duration=" in sh


def test_gate_guard_blocks_outbound_allows_localhost():
    code = (
        "import os, socket, sys; os.environ['WAVESPEED_API_KEY']='x'; os.environ['GATE']='1';"
        "sys.path.insert(0, 'tests'); import conftest;"
        "assert 'WAVESPEED_API_KEY' not in os.environ;"
        "s=socket.socket(); s.settimeout(1)\n"
        "try:\n s.connect(('8.8.8.8', 443)); print('OPEN')\n"
        "except conftest.GateNetworkBlocked: print('BLOCKED')\n"
        "try:\n socket.getaddrinfo('api.wavespeed.ai', 443); print('DNS')\n"
        "except conftest.GateNetworkBlocked: print('DNSBLOCKED')\n"
        "srv=socket.socket(); srv.bind(('127.0.0.1',0)); srv.listen(1);"
        "c=socket.socket(); c.connect(srv.getsockname()); print('LOCAL')"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.stdout.split() == ["BLOCKED", "DNSBLOCKED", "LOCAL"], out.stderr[-800:]


# --- #724: node-unit tests are counted, and a missing node/node_modules is never a pass ---
def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    return port


def _stub_py(tmp_path, total: int = 22):
    """Fake GATE_PY: answers the gate's --co collection with a node-unit report and a pytest-ish summary line."""
    p = tmp_path / "stubpy"
    p.write_text(f'''#!/usr/bin/env bash
case "$*" in
  *--co*)
    printf '%s\\n' '{{"ready": true, "total": {total}, "items": []}}' > "$GATE_NODE_UNIT_JSON"
    echo "{total} tests collected in 0.01s" ;;
  *) echo "{total} passed in 0.01s" ;;
esac
''')
    p.chmod(0o755)
    return p


def _gate_env_724(tmp_path, wt, py, *, path=None, extra=None):
    """Env for a real gate.sh run against a throwaway worktree: no inherited GATE flag, no real pytest pre-check."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("GATE", "GATE_PORTS", "GATE_PYTEST_PATTERN", "COMFYART_SKIP_NODE_TESTS")}
    env.update({"GATE_WT": str(wt), "GATE_MAIN": str(tmp_path / "main"), "GATE_PY": str(py),
                "GATE_PORTS": str(_free_port()), "GATE_PYTEST_PATTERN": "comfyart-no-such-pytest-724"})
    (tmp_path / "main").mkdir(exist_ok=True)
    if path:
        env["PATH"] = path
    if extra:
        env.update(extra)
    return env


def _fake_npx(tmp_path):
    """PATH with a no-op npx so tsc/vite build do not run for real in the gate.sh tests."""
    import shutil
    binp = tmp_path / "bin"; binp.mkdir(exist_ok=True)
    npx = binp / "npx"
    npx.write_text("#!/bin/sh\nexit 0\n"); npx.chmod(0o755)
    return str(binp) + os.pathsep + os.environ["PATH"], shutil


def test_gate_node_ready_needs_node_modules_rolldown(tmp_path):
    r = _run("gate_node_ready", str(tmp_path))
    assert r.returncode == 1 and "rolldown" in r.stderr and "npm ci" in r.stderr


def test_gate_node_ready_accepts_node_and_rolldown(tmp_path):
    import shutil
    if not shutil.which("node"):
        pytest.skip("node is not installed here")
    b = tmp_path / "node_modules" / ".bin" / "rolldown"
    b.parent.mkdir(parents=True); b.write_text("#!/bin/sh\n"); b.chmod(0o755)
    assert _run("gate_node_ready", str(tmp_path)).returncode == 0


def test_gate_node_unit_total_reads_report(tmp_path):
    j = tmp_path / "node-unit.json"
    assert _run("gate_node_unit_total", str(j)).returncode == 1
    j.write_text('{"ready": true, "total": 22, "items": ["tests/x.py::t"]}')
    r = _run("gate_node_unit_total", str(j))
    assert r.returncode == 0 and r.stdout.strip() == "22"


def test_gate_node_unit_ready_reads_report(tmp_path):
    j = tmp_path / "node-unit.json"
    assert _run("gate_node_unit_ready", str(j)).returncode == 1
    j.write_text('{"ready": false, "total": 22, "items": []}')
    assert _run("gate_node_unit_ready", str(j)).returncode == 1
    j.write_text('{"ready": true, "total": 22, "items": []}')
    assert _run("gate_node_unit_ready", str(j)).returncode == 0


def test_conftest_writes_node_unit_report(tmp_path):
    """conftest counts the node tests of the *selected* collection (#724) and reports 0 for a Python-only file."""
    import json
    for target, want in (("tests/test_skill_modal_541.py", 6), ("tests/test_brand_399.py", 0)):
        rep = tmp_path / (want and "node.json" or "py.json")
        env = {k: v for k, v in os.environ.items() if k != "WAVESPEED_API_KEY"}
        env["GATE_NODE_UNIT_JSON"] = str(rep)
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--co", target],
                           cwd=ROOT, capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
        data = json.loads(rep.read_text())
        assert data["total"] == want and data["ready"] is True, (target, data)


def test_gate_without_node_modules_fails_loudly(tmp_path):
    """Removing node_modules must never be a green gate: loud SKIPPED + count + non-zero exit."""
    wt = tmp_path / "wt_nonode"; wt.mkdir()
    py = _stub_py(tmp_path, 22)
    r = subprocess.run(["bash", str(GATE), "nonode"], capture_output=True, text=True,
                       env=_gate_env_724(tmp_path, wt, py))
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "node-unit: SKIPPED 22 tests" in r.stdout, r.stdout
    assert "GATE_FAIL: node-unit" in r.stdout, r.stdout
    assert "GATE_EXIT=1" in r.stdout, r.stdout


def test_gate_allow_missing_node_is_loud_but_not_fatal(tmp_path):
    """--allow-missing-node is the deliberate Python-only local mode: SKIPPED is printed, the parse of the count stays."""
    wt = tmp_path / "wt_allow"; wt.mkdir()
    py = _stub_py(tmp_path, 22)
    path, _ = _fake_npx(tmp_path)
    r = subprocess.run(["bash", str(GATE), "allow", "--allow-missing-node"], capture_output=True, text=True,
                       env=_gate_env_724(tmp_path, wt, py, path=path))
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "node-unit: SKIPPED 22 tests" in r.stdout and "GATE_EXIT=0" in r.stdout, r.stdout


def test_gate_env_gate_1_forces_strict_even_with_allow(tmp_path):
    """GATE=1 in the caller env is strict (#724): a missing node is fatal even with --allow-missing-node."""
    wt = tmp_path / "wt_strict"; wt.mkdir()
    py = _stub_py(tmp_path, 22)
    r = subprocess.run(["bash", str(GATE), "strict", "--allow-missing-node"], capture_output=True, text=True,
                       env=_gate_env_724(tmp_path, wt, py, extra={"GATE": "1"}))
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "node-unit: SKIPPED 22 tests" in r.stdout and "GATE_EXIT=1" in r.stdout, r.stdout


def test_gate_prints_node_unit_count_when_node_ready(tmp_path):
    """When node is available the gate prints how many node unit tests the UNIT stage selected."""
    import shutil
    if not shutil.which("node"):
        pytest.skip("node is not installed here")
    wt = tmp_path / "wt_ready"; wt.mkdir()
    ro = tmp_path / "main" / "node_modules" / ".bin" / "rolldown"
    ro.parent.mkdir(parents=True); ro.write_text("#!/bin/sh\nexit 0\n"); ro.chmod(0o755)
    py = _stub_py(tmp_path, 22)
    path, _ = _fake_npx(tmp_path)
    r = subprocess.run(["bash", str(GATE), "ready"], capture_output=True, text=True,
                       env=_gate_env_724(tmp_path, wt, py, path=path))
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "UNIT: collected=22" in r.stdout, r.stdout
    assert "UNIT node-unit: 22 tests" in r.stdout, r.stdout
    assert "GATE_EXIT=0" in r.stdout, r.stdout


def test_gate_node_unit_preflight_runs_before_tsc():
    sh = (ROOT / "scripts" / "gate.sh").read_text()
    assert sh.index("gate_node_ready") < sh.index("npx tsc")
    assert "node-unit: SKIPPED" in sh and "--allow-missing-node" in sh and "--require-node" in sh
    assert "-u COMFYART_SKIP_NODE_TESTS" in sh  # an inherited skip flag cannot fake a green gate
