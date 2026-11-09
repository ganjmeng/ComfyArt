"""Merge regression: provider confirmation token and GIF facts must coexist. No paid calls."""
import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed


@pytest.mark.parametrize("price", [None, 0.05])
def test_response_keeps_token_and_gif_facts(price):
    gif = {"frame_count": 16, "frame_duration_ms": 20}
    err = wavespeed.WaveSpeedError("confirm", status=409, confirm=price, unpriced=price is None,
                                   model="openai/gpt-image-2.6-flare", gif=gif)
    err.confirm_token = "local-test-token"
    response = wavespeed._respond_error(err)
    body = json.loads(response.text)["error"]
    assert response.status == 409
    assert body["confirm_token"] == "local-test-token"
    assert body["model"] == "openai/gpt-image-2.6-flare"
    assert body["gif"] == gif
    assert body["confirm_usd"] == price


def test_frontend_keeps_token_with_gif_confirmation():
    # Static merge guard complements runtime server/token and bundled sentence tests.
    source = (Path(__file__).resolve().parents[1] / "src/comfy.ts").read_text()
    assert "openEnded: confirmToken.length > 0" in source
    assert "confirm_token: confirmToken" in source
    assert "const note = [routed, asked, gifNote]" in source
    assert "...(gif ? { gif } : {})" in source
