"""Failed process rows show the user message, not the raw tool JSON or a model id."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_visible_tool_error_keeps_user_message_and_drops_the_model_id():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run(
        [node, "--experimental-strip-types", str(ROOT / "tests/js/tool_error_line_check.ts")],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert run.returncode == 0, (run.stdout, run.stderr)
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    assert "function toolErrorLine" in chat
    assert "visibleToolError(result?.text)" in chat
