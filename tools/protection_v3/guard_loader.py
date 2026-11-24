"""Load the frozen price guard after checking its bytes. Does not modify the file."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from tools.protection_v3.constants import FROZEN_GUARD_SHA256

_REPO = Path(__file__).resolve().parents[2]
FROZEN_GUARD_PATH = _REPO / "docs/integrate/protection-v3/frozen/wavespeed_price_guard.py"


class GuardHashMismatch(RuntimeError):
    pass


def load_frozen_guard(path: Path | None = None):
    """Return the frozen module. A hash miss raises and does not exec the file."""
    target = Path(path) if path is not None else FROZEN_GUARD_PATH
    data = target.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != FROZEN_GUARD_SHA256:
        raise GuardHashMismatch(digest)
    spec = importlib.util.spec_from_file_location("wavespeed_price_guard_frozen", target)
    if spec is None or spec.loader is None:
        raise GuardHashMismatch("unreadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
