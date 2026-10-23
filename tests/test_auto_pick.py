"""#133: Auto picks a model by task type from api/auto_models.json (product table v1); user-named wins;
the tool result says which model and why (zh + en). All mocked: no page, no WaveSpeed call."""
import asyncio

import pytest

from ComfyArt.api import auto_models
from ComfyArt.api.mcp_tools import canvas

SENT = []


@pytest.fixture(autouse=True)
def mocked(monkeypatch):
    SENT.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": ["shape:g1"]}

    async def no_approval(label):
        return None
    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)


def run(tool, **args):
    return asyncio.run(canvas.TOOLS[tool]["handler"](args))


def default(feature):
    return canvas.load_config()["features"][feature]["default"]


def test_same_prompt_many_turns_same_model():
    picks = {run("generate_image", prompt="a cup of coffee on a table")["model_choice"]["model"] for _ in range(5)}
    assert picks == {default("text_to_image")} == {"openai/gpt-image-2.5-flare/text-to-image"}
    assert all("model" not in a for _, a in SENT)  # default path unchanged: page resolves Auto


@pytest.mark.parametrize("prompt,model", [
    ("Movie poster with the headline \"SUMMER\"", "openai/gpt-image-2.5-flare/text-to-image"),
    ("Photorealistic portrait of an old fisherman", "bytedance/seedream-v5.0-pro"),
    ("Anime girl under cherry blossoms", "midjourney/text-to-image"),
    ("一张写实人像", "bytedance/seedream-v5.0-pro"),
    ("Minimal logo for a tea brand", "recraft-ai/recraft-v3"),
])
def test_task_type_hits_table(prompt, model):
    choice = run("generate_image", prompt=prompt)["model_choice"]
    assert choice["model"] == model and choice["auto"]
    if model != default("text_to_image"):
        assert SENT[-1][1]["model"] == model


def test_user_named_model_wins():
    choice = run("generate_image", prompt="Anime poster", model="alibaba/qwen-image-3.0/text-to-image")["model_choice"]
    assert choice == {**choice, "model": "alibaba/qwen-image-3.0/text-to-image", "auto": False}
    assert SENT[-1][1]["model"] == "alibaba/qwen-image-3.0/text-to-image"


def test_reply_states_model_and_reason_zh_en():
    note = run("generate_image", prompt="Photorealistic portrait")["model_choice"]["note"]
    assert note.startswith("用了 bytedance/seedream-v5.0-pro，因为") and "Used bytedance/seedream-v5.0-pro because" in note
    assert "say in your reply" in __import__("ComfyArt.bot.guide", fromlist=["AGENT_GUIDE"]).AGENT_GUIDE


def test_missing_model_falls_back_to_default(monkeypatch, caplog):
    real = auto_models.load_table()
    real["text_to_image"]["categories"][0]["model"] = "nope/not-in-catalog"
    monkeypatch.setattr(auto_models, "load_table", lambda: real)
    choice = run("generate_image", prompt="logo for a cafe")["model_choice"]
    assert choice["model"] == default("text_to_image") and choice["fallback"] == "nope/not-in-catalog"
    assert "not in catalog" in caplog.text


def test_edit_table_and_refs():
    assert run("edit_image", id="shape:a", prompt="change the sign text")["model_choice"]["model"] == default("image_edit")
    assert run("edit_image", id="shape:a", prompt="new background, keep the same person")["model_choice"]["model"] == "google/nano-banana-2.1/edit"
    choice = run("generate_image", prompt="poster", refs=["shape:r"])["model_choice"]
    assert choice["model"] == default("image_edit") and choice["category"] == "references"


def test_table_models_are_in_catalog():
    cfg = canvas.load_config()["features"]
    for feature, spec in auto_models.load_table().items():
        ids = {m["id"] for m in cfg[feature]["models"]}
        assert all(c["model"] in ids for c in spec["categories"]), feature
