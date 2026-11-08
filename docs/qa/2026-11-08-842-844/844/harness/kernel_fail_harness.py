"""Harness only. Does not modify product code. Not a monkeypatch of refuse()."""
from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import time
from pathlib import Path

TIP = Path("/tmp/qa844/tip40b")
PY = "/tmp/qa844/venv/bin/python"
WORKER = str(TIP / "api" / "svg_worker.py")
CANARY = Path("/tmp/qa844/canary-not-secret.txt")
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="4" height="4" fill="#00aa00"/></svg>'
ENV = {
    "PATH": os.environ.get("PATH", "/usr/bin"),
    "HOME": "/tmp",
    "GATE": "1",
    "LANG": "C",
}
# Do not pass API keys or the passwd-blocking guard into the child.

SECCOMP_RET_ALLOW = 0x7FFF0000
SECCOMP_RET_ERRNO = 0x00050000
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
BPF_LD_W_ABS = 0x20
BPF_JMP_JEQ_K = 0x15
BPF_RET_K = 0x06


class SockFilter(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_uint16),
        ("jt", ctypes.c_uint8),
        ("jf", ctypes.c_uint8),
        ("k", ctypes.c_uint32),
    ]


class SockFprog(ctypes.Structure):
    _fields_ = [
        ("len", ctypes.c_ushort),
        ("_pad", ctypes.c_char * 6),
        ("filter", ctypes.POINTER(SockFilter)),
    ]


def snapshot(label: str) -> list[str]:
    rows = []
    me = os.getpid()
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            stat = Path(f"/proc/{pid}/stat").read_text().split()
            ppid = int(stat[3])
            state = stat[2]
        except OSError:
            continue
        if "svg_worker.py" in cmd or ppid == me or pid == me:
            rows.append(f"{label} pid={pid} ppid={ppid} state={state} cmd={cmd[:160]}")
    return rows


def install_seccomp(block_nr: int) -> None:
    """Kernel errno for one syscall. Default policy is allow. This process only."""
    libc = ctypes.CDLL(None, use_errno=True)
    filt = (SockFilter * 4)(
        SockFilter(BPF_LD_W_ABS, 0, 0, 0),
        SockFilter(BPF_JMP_JEQ_K, 0, 1, block_nr),
        SockFilter(BPF_RET_K, 0, 0, SECCOMP_RET_ERRNO | 1),
        SockFilter(BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW),
    )
    prog = SockFprog(4, b"", filt)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "no_new_privs")
    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(prog)) != 0:
        raise OSError(ctypes.get_errno(), "seccomp")


def spawn(args: list[str], *, stdin: bytes | None, seccomp_nr: int | None, prlimit: list[str] | None, close_stdin: bool) -> dict:
    before = snapshot("before")
    cmd = (prlimit or []) + args
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=ENV,
        start_new_session=True,
        preexec_fn=(lambda: install_seccomp(seccomp_nr)) if seccomp_nr is not None else None,
    )
    started = snapshot("started")
    timed_out = False
    if stdin is not None and proc.stdin is not None:
        proc.stdin.write(stdin)
        proc.stdin.close()
        proc.stdin = None
        try:
            out, err = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate(timeout=3)
            timed_out = True
    else:
        # Leave stdin open so the product alarm can fire during read. Do not close it.
        # Drain stdout/stderr so python -v cannot fill the pipe and hide the signal.
        import threading
        chunks = {"out": b"", "err": b""}

        def drain(pipe, key):
            chunks[key] = pipe.read()

        threads = [
            threading.Thread(target=drain, args=(proc.stdout, "out")),
            threading.Thread(target=drain, args=(proc.stderr, "err")),
        ]
        for thread in threads:
            thread.start()
        deadline = time.time() + 8
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.05)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            timed_out = True
        proc.wait(timeout=3)
        for thread in threads:
            thread.join(timeout=3)
        out, err = chunks["out"], chunks["err"]
    after = snapshot("after")
    code = proc.returncode
    sig = -code if code is not None and code < 0 else None
    text = out.decode("utf-8", "replace")
    parsed = None
    if text.strip().startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {"_json_error": True}
    err_text = err.decode("utf-8", "replace")
    imported = [line for line in err_text.splitlines() if "svg_raster" in line or "PIL" in line or "Image" in line]
    return {
        "argv": cmd,
        "pid": proc.pid,
        "returncode": code,
        "signal": sig,
        "signal_name": signal.Signals(sig).name if sig else None,
        "timed_out_outer": timed_out,
        "stdout_len": len(out),
        "json": parsed,
        "download_present": bool(parsed and parsed.get("download")),
        "preview_present": bool(parsed and parsed.get("preview")),
        "rendered": None if not parsed else parsed.get("rendered"),
        "reason": None if not parsed else parsed.get("reason"),
        "network_probe": None if not isinstance(parsed, dict) else (parsed.get("applied") or {}).get("network_probe"),
        "filesystem_probe": None if not isinstance(parsed, dict) else (parsed.get("applied") or {}).get("filesystem_probe"),
        "import_lines": imported[:30],
        "stderr_tail": err_text[-800:],
        "before": before,
        "started": started,
        "after": after,
        "worker_after": [row for row in after if "svg_worker.py" in row],
    }


def main() -> None:
    CANARY.write_text("CANARY_NOT_A_SECRET\n", encoding="utf-8")
    print("tip", TIP)
    print("kernel", os.uname().release)
    print("harness_pid", os.getpid())
    print("strace", "absent")
    cases = [
        ("unshare_seccomp_eperm", dict(
            args=[PY, "-v", WORKER],
            stdin=SVG,
            seccomp_nr=272,
            prlimit=None,
            close_stdin=False,
        )),
        ("landlock_seccomp_eperm", dict(
            args=[PY, "-v", WORKER],
            stdin=SVG,
            seccomp_nr=444,
            prlimit=None,
            close_stdin=False,
        )),
        ("product_alarm_no_stdin", dict(
            args=[PY, "-v", WORKER],
            stdin=None,
            seccomp_nr=None,
            prlimit=None,
            close_stdin=False,
        )),
        ("harness_as_32mib", dict(
            args=[PY, WORKER],
            stdin=SVG,
            seccomp_nr=None,
            prlimit=["prlimit", "--as=33554432"],
            close_stdin=False,
        )),
    ]
    for name, kw in cases:
        print("\n====", name, "====")
        result = spawn(**kw)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    leftover = snapshot("final")
    print("\n==== final snapshot ====")
    print("\n".join(leftover) or "(no svg_worker)")


if __name__ == "__main__":
    main()
