"""#826 child for untrusted SVG bytes.

Network isolation is a new user namespace plus a new network namespace, checked
by a connect that must fail unreachable. Filesystem isolation is Landlock with
no allow rules, checked by open() of /etc/passwd. Resource limits are separate
and are not treated as a substitute for either.

If either check fails, this process exits without importing the rasterizer and
without parsing or drawing.
"""
from __future__ import annotations

import base64
import errno
import importlib.util
import json
import os
import resource
import signal
import socket
import sys
from pathlib import Path

AS = 768 * 1024 * 1024
CPU = 3
ALARM = 3
FSIZE = 2 * 1024 * 1024
CLONE_NEWUSER = 0x10000000
CLONE_NEWNET = 0x40000000
UNREACHABLE = {errno.ENETUNREACH, errno.ENETDOWN, errno.EHOSTUNREACH}


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (AS, AS))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU, CPU))
    resource.setrlimit(resource.RLIMIT_FSIZE, (FSIZE, FSIZE))
    signal.alarm(ALARM)


def _libc():
    import ctypes
    import ctypes.util
    return ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


def _errno_name() -> str:
    return errno.errorcode.get(__import__("ctypes").get_errno(), "error")


def establish_network() -> dict:
    """Enter a network namespace. A reachable connect is a failure, not a warning."""
    uid, gid = os.getuid(), os.getgid()
    libc = _libc()
    if libc.unshare(CLONE_NEWUSER | CLONE_NEWNET) != 0:
        return {"ok": False, "network_isolated": False, "network_probe": _errno_name(), "filesystem_isolated": False}
    try:
        os.write(os.open("/proc/self/setgroups", os.O_WRONLY), b"deny\n")
        os.write(os.open("/proc/self/uid_map", os.O_WRONLY), f"0 {uid} 1\n".encode())
        os.write(os.open("/proc/self/gid_map", os.O_WRONLY), f"0 {gid} 1\n".encode())
    except OSError:
        return {"ok": False, "network_isolated": False, "network_probe": "map", "filesystem_isolated": False}
    probes = []
    for host in ("192.0.2.1", "127.0.0.1"):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            sock.connect((host, 9))
        except OSError as exc:
            probes.append(exc.errno)
        else:
            return {"ok": False, "network_isolated": False, "network_probe": "connect_succeeded", "filesystem_isolated": False}
        finally:
            if sock is not None:
                sock.close()
    if not probes or any(code not in UNREACHABLE for code in probes):
        name = errno.errorcode.get(probes[0], "error") if probes else "none"
        return {"ok": False, "network_isolated": False, "network_probe": name, "filesystem_isolated": False}
    return {"ok": True, "network_isolated": True, "network_probe": errno.errorcode.get(probes[0], "ENETUNREACH"), "filesystem_isolated": False}


def establish_filesystem() -> dict:
    """Deny further path opens. Must run only after libraries are already imported."""
    import ctypes
    libc = _libc()
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        return {"filesystem_isolated": False, "filesystem_probe": _errno_name()}

    class Attr(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    attr = Attr()
    attr.handled_access_fs = (1 << 13) - 1
    ruleset = libc.syscall(444, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if ruleset < 0 or libc.syscall(446, ruleset, 0) != 0:
        return {"filesystem_isolated": False, "filesystem_probe": _errno_name()}
    try:
        os.open("/etc/passwd", os.O_RDONLY)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EPERM):
            return {"filesystem_isolated": True, "filesystem_probe": errno.errorcode.get(exc.errno, "EACCES")}
        return {"filesystem_isolated": False, "filesystem_probe": errno.errorcode.get(exc.errno, "error")}
    return {"filesystem_isolated": False, "filesystem_probe": "open_succeeded"}


def _refuse(applied: dict) -> dict:
    return {
        "status": "rejected",
        "reason": "isolation_unavailable",
        "kind": "svgRejected",
        "message_zh": "渲染隔离没有建立，已拒绝，不会解析或提供下载。",
        "message_en": "Render isolation was not established. The file was rejected and was not parsed or offered for download.",
        "download": None,
        "preview": None,
        "rendered": False,
        "applied": applied,
    }


def _load_raster():
    path = Path(__file__).with_name("svg_raster.py")
    spec = importlib.util.spec_from_file_location("svg_raster", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["svg_raster"] = module
    spec.loader.exec_module(module)
    import PIL.Image
    import PIL.ImageDraw  # noqa: F401
    import PIL.PngImagePlugin  # noqa: F401
    # Image.save lazy-loads plugins from disk. Load them before Landlock.
    PIL.Image.init()
    return module


def _render(data: bytes, applied: dict) -> dict:
    module = _load_raster()
    fs = establish_filesystem()
    applied = {**applied, **fs, "ok": bool(fs.get("filesystem_isolated"))}
    if not fs.get("filesystem_isolated"):
        return _refuse(applied)
    try:
        verdict = module.admit(data)
    except Exception:
        refused = _refuse(applied)
        refused["reason"] = "resource_limit"
        return refused
    return {
        "status": verdict.status,
        "reason": verdict.reason,
        "kind": verdict.kind,
        "message_zh": verdict.message_zh,
        "message_en": verdict.message_en,
        "download": base64.b64encode(verdict.download).decode("ascii") if verdict.download else None,
        "preview": base64.b64encode(verdict.preview_png).decode("ascii") if verdict.preview_png else None,
        "rendered": True,
        "applied": {
            **applied,
            "rlimit_as": resource.getrlimit(resource.RLIMIT_AS)[0],
            "rlimit_cpu": resource.getrlimit(resource.RLIMIT_CPU)[0],
            "rlimit_fsize": resource.getrlimit(resource.RLIMIT_FSIZE)[0],
            "alarm_seconds": ALARM,
            "rlimit_is_network_isolation": False,
        },
    }


def run(data: bytes, establish_network=None, render=None) -> dict:
    """Parse and draw only after both isolations succeed."""
    net = (establish_network or establish_network_real)()
    if not net.get("ok"):
        return _refuse(net)
    return (render or _render)(data, net)


def establish_network_real() -> dict:
    return establish_network()


def main() -> None:
    _limits()
    data = sys.stdin.buffer.read(512 * 1024 + 1)
    sys.stdout.buffer.write(json.dumps(run(data)).encode("utf-8"))


if __name__ == "__main__":
    main()
