"""#95 tester: list_models must only ever be the backend's paged version (4000-char cap), never forwarded to the page."""
from pathlib import Path

from ComfyArt.api.mcp_tools import canvas

ROOT = Path(__file__).resolve().parent.parent


def test_list_models_handled_by_backend():
    assert canvas.TOOLS["list_models"]["handler"] is canvas._list_models


def test_no_frontend_list_models_handler():
    src = (ROOT / "src" / "botCommands.ts").read_text()
    assert "list_models: (" not in src and "list_models:(" not in src
