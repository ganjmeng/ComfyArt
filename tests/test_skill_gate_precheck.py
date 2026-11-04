"""Pre-check helpers of scripts/gate_lib.sh (gate hardening)."""
import socket
import subprocess
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "scripts" / "gate_lib.sh"


def _run(fn: str, *args: str, env=None):
    q = " ".join(f"'{a}'" for a in args)
    return subprocess.run(["bash", "-c", f". '{LIB}'; {fn} {q}"], capture_output=True, text=True, env=env)


def test_rejects_hyphen_worktree(tmp_path):
    d = tmp_path / "wt_foo-bar"; d.mkdir()
    r = _run("gate_check_wt_name", str(d))
    assert r.returncode == 1 and "contains '-'" in r.stderr
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
    p = subprocess.Popen(["bash", "-c", "exec -a gatefakeproc sleep 30"])
    try:
        import os
        env = {**os.environ, "GATE_PYTEST_PATTERN": "gatefakeproc"}
        r = _run("gate_check_no_pytest", env=env)
        assert r.returncode == 1 and "another pytest" in r.stderr
    finally:
        p.kill()


def test_log_error_lines(tmp_path):
    good = tmp_path / "g.log"; good.write_text("....\n12 passed in 1.0s\n")
    assert _run("gate_check_log_errors", str(good)).returncode == 0
    bad = tmp_path / "b.log"; bad.write_text("ERROR tests/test_x.py - ImportError\n1 error in 0.1s\n")
    r = _run("gate_check_log_errors", str(bad))
    assert r.returncode == 1 and "error lines" in r.stderr
