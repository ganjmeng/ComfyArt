"""Run the brand confirmation tests with the network guard installed first.

Usage (from the repo root):
    python3 tests/run_brand_confirm_isolated.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.brand_confirm_guard import ALLOW, install, self_check

os.environ["WAVESPEED_API_KEY"] = "isolated-dummy-not-a-real-key"
os.environ["WAVESPEED_BASE_URL"] = "http://127.0.0.1:9"
os.environ.pop("COMFYART_SKIP_KEY_CHECK", None)
os.environ["COMFYART_SKIP_NODE_TESTS"] = "1"
os.environ["BRAND_CONFIRM_ISOLATED"] = "1"
os.environ["COMFYART_AGENT_BUDGET_LOOP"] = "0"

install()
report = self_check()
if not report["ok"]:
    print(report)
    raise SystemExit(1)
ALLOW["loopback"] = True

import pytest

raise SystemExit(pytest.main(["-q", "tests/test_brand_confirm_grant.py"]))
