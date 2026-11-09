"""QA guard used with the original probe. Refuse opens of host credential paths."""
import builtins
import os

_REAL_OPEN = builtins.open
_REAL_OS_OPEN = os.open


def _blocked(path) -> bool:
    try:
        text = os.fspath(path)
    except TypeError:
        return False
    low = str(text).lower()
    name = os.path.basename(low)
    return name in {"passwd", "shadow", ".env"} or low.endswith("/.env") or name.startswith("id_rsa")


def _open(path, *args, **kwargs):
    if _blocked(path):
        raise PermissionError("qa-guard refused sensitive open")
    return _REAL_OPEN(path, *args, **kwargs)


def _os_open(path, *args, **kwargs):
    if _blocked(path):
        raise PermissionError("qa-guard refused sensitive os.open")
    return _REAL_OS_OPEN(path, *args, **kwargs)


builtins.open = _open
os.open = _os_open
