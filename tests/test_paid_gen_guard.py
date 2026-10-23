"""#142: paid-generation guard and product-reference block (S8 replay), plus
list_models accepting tool names (#143). Mocks only: no LLM, MCP or WaveSpeed
traffic leaves the process."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ComfyArt.api import wavespeed
from ComfyArt.api.bot_send import compose_provider_text
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.guide import PAID_TOOLS
from ComfyArt.bot.local_llm import (LocalLlmProvider, _product_refs,
                                    _requested_count)
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest

S8_TEXT = compose_provider_text("用这张产品图做电商图（图片 id: shape:src）", skill_name="product")
ZH_STOP = "已生成 4 张仍未完成，已停止，未继续扣费，请告诉我怎么调整"
EN_STOP = ("Generated 4 images and still not done, so I stopped; no further "
           "charges. Tell me how to adjust.")


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name, "arguments": json.dumps(args)}}


def _s8_gen(i: int, **extra) -> tuple[str, dict]:
    # the real S8 calls: a new prompt each time, never the reference (args were {prompt})
    return ("generate_image", {"prompt": f"E-commerce shot {i}: the product from the reference image", **extra})


async def _run(monkeypatch, steps, user_text=S8_TEXT, lang=""):
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    responses = [{"choices": [{"message": {"content": "", "tool_calls": [_tc(i, n, a)]}}]}
                 for i, (n, a) in enumerate(steps)]
    responses.append({"choices": [{"message": {"content": "done", "tool_calls": []}}]})
    llm: list[int] = []
    submits: list[tuple[str, dict]] = []  # what would reach the canvas/WaveSpeed

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            llm.append(1)
            return responses.pop(0)
        return {"result": {"tools": [{"name": n} for n in ("skill", "generate_image", "update_plan", "wait_generation", "edit_image")]}}

    async def fake_call(session, endpoint, name, arguments):
        submits.append((name, dict(arguments)))
        return json.dumps({"ids": [f"gen:{len(submits)}"]} if name in PAID_TOOLS else {"ok": True}), []

    async def fake_wait(session, endpoint, args, model, handle):
        return json.dumps({"status": "done", "results": []})

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    monkeypatch.setattr(provider, "_wait_stage_done", fake_wait)
    events: list[BotEvent] = []

    async def emit(e):
        events.append(e)
    result = await provider.send(TurnRequest(chat_id="c", user_text=user_text, lang=lang,
                                             mcp_endpoint="http://x/mcp", model="m1"), emit, TurnHandle())
    return result, events, llm, submits


def _paid(submits):
    return [s for s in submits if s[0] in PAID_TOOLS]


# ---- rule 1: at most 4 paid generations per plan item -------------------------------------------

async def test_s8_replay_fifth_paid_submit_is_zero(monkeypatch):
    steps = [("skill", {"action": "read", "name": "product"})]
    for i in range(25):  # S8 asked for 25 generations
        steps += [_s8_gen(i, refs=["shape:src"]), ("wait_generation", {"ids": [f"gen:{i}"]})]
    result, events, llm, submits = await _run(monkeypatch, steps)
    assert len(_paid(submits)) == 4  # the 5th paid submit never happens
    assert result.error.startswith(ZH_STOP)
    assert "已完成：" in result.error and "生成图像 ×4" in result.error
    assert len(llm) == 10  # skill + 4×(gen, wait) + the stopped 5th gen; no LLM spend after
    assert not any(e.t == "tool_use" and e.name == "generate_image" and e.id == "t9" for e in events)


async def test_stop_text_follows_ui_language_en(monkeypatch):
    steps = [_s8_gen(i, refs=["shape:src"]) for i in range(6)]
    result, *_ = await _run(monkeypatch, steps, lang="en")
    assert result.error.startswith(EN_STOP)
    assert "Generate image ×4" in result.error


async def test_count_argument_counts_images(monkeypatch):
    steps = [_s8_gen(0, refs=["shape:src"], count=3), _s8_gen(1, refs=["shape:src"], count=2)]
    result, _, _, submits = await _run(monkeypatch, steps)
    assert len(_paid(submits)) == 1 and result.error.startswith(ZH_STOP)


async def test_user_asked_for_n_uses_n(monkeypatch):
    steps = [("generate_image", {"prompt": f"cat {i}"}) for i in range(8)]
    result, _, _, submits = await _run(monkeypatch, steps, user_text="画 6 张猫的插画")
    assert len(_paid(submits)) == 6
    assert result.error.startswith("已生成 6 张仍未完成")


async def test_each_plan_item_gets_its_own_four(monkeypatch):
    def plan(active):
        return ("update_plan", {"steps": [{"text": t, "status": "active" if t == active else "pending"}
                                          for t in ("hero", "lifestyle", "detail")]})
    steps = [plan("hero"), *[("generate_image", {"prompt": f"h{i}"}) for i in range(4)],
             plan("lifestyle"), *[("generate_image", {"prompt": f"l{i}"}) for i in range(4)],
             plan("detail"), ("generate_image", {"prompt": "d0"})]
    result, _, _, submits = await _run(monkeypatch, steps, user_text="poster set")
    assert len(_paid(submits)) == 9 and not result.error


async def test_declined_or_failed_runs_do_not_count(monkeypatch):
    provider_steps = [("generate_image", {"prompt": f"x{i}"}) for i in range(6)]
    calls = {"n": 0}
    result, events, llm, submits = None, None, None, None

    import ComfyArt.bot.local_llm as ll
    orig = ll._paid_ok

    def first_two_declined(text):
        calls["n"] += 1
        return calls["n"] > 2 and orig(text)
    monkeypatch.setattr(ll, "_paid_ok", first_two_declined)
    result, _, _, submits = await _run(monkeypatch, provider_steps, user_text="poster")
    assert len(_paid(submits)) == 6 and not result.error


def test_paid_ok_reads_cancel_and_errors():
    from ComfyArt.bot.local_llm import _paid_ok
    assert _paid_ok('{"ids": ["gen:1"]}')
    assert not _paid_ok('{"cancelled": true, "status": "declined"}')
    assert not _paid_ok("[tool error] boom")


def test_requested_count():
    assert _requested_count("做 6 张海报") == 6
    assert _requested_count("来三张") == 3
    assert _requested_count("make 2 images") == 2
    assert _requested_count("做一张海报 1:1") == 1
    assert _requested_count("电商图") == 0
    assert _requested_count(S8_TEXT) == 0  # skill hint text is not the user's ask


def test_paid_tools_match_wavespeed_tool_features():
    assert PAID_TOOLS == set(wavespeed.load_config()["tool_features"])


# ---- rule 2: the product reference must be passed -----------------------------------------------

async def test_generation_without_reference_is_blocked_before_submit(monkeypatch):
    steps = [_s8_gen(0), _s8_gen(1, refs=["shape:src"], ref_modes=["content"])]
    result, events, _, submits = await _run(monkeypatch, steps)
    assert [s[1].get("refs") for s in _paid(submits)] == [["shape:src"]]
    blocked = [e for e in events if e.t == "tool_result" and e.id == "t0"][0]
    assert blocked.is_error and "shape:src" in blocked.text and "refs" in blocked.text
    assert "nothing was charged" in blocked.text
    assert not result.error


async def test_blocked_calls_do_not_count_toward_cap(monkeypatch):
    steps = [_s8_gen(i) for i in range(6)] + [_s8_gen(9, refs=["shape:src"])]
    result, _, _, submits = await _run(monkeypatch, steps)
    assert len(_paid(submits)) == 1 and not result.error


async def test_base_or_attached_image_line_counts_as_reference(monkeypatch):
    text = compose_provider_text("做电商主图", skill_name="product", lines=[
        "[Attached image 1: shape id shape:abc — /view?x. Use the shape id with edit tools or as a generation ref.]"])
    assert _product_refs(text) == ["shape:abc"]
    steps = [("generate_image", {"prompt": "p", "base": "shape:abc"}),
             ("generate_image", {"prompt": "p", "refs": ["shape:other"]})]
    _, _, _, submits = await _run(monkeypatch, steps, user_text=text)
    assert len(_paid(submits)) == 1


async def test_no_block_without_product_reference(monkeypatch):
    # no supplied image, or not a product task: nothing to enforce
    assert _product_refs("画一张极简咖啡海报") == []
    assert _product_refs("把这张图背景换成海边（图片 id: shape:src）") == []
    _, _, _, submits = await _run(monkeypatch, [("generate_image", {"prompt": "p"})], user_text="画一张海报")
    assert len(_paid(submits)) == 1


async def test_edit_tools_are_not_ref_blocked(monkeypatch):
    _, _, _, submits = await _run(monkeypatch, [("edit_image", {"id": "shape:src", "prompt": "white bg"})])
    assert len(_paid(submits)) == 1


def test_product_skill_tells_the_agent_to_pass_refs():
    src = (Path(__file__).resolve().parent.parent / "src" / "skills.ts").read_text()
    line = next(l for l in src.splitlines() if "id: 'product'" in l)
    assert "refs" in line and "does not send the image" in line
    assert "only refs do" in canvas.TOOLS["generate_image"]["description"]


# ---- #143: list_models accepts tool names --------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json"


@pytest.fixture
def mock_catalog(monkeypatch):
    models = json.loads(FIXTURE.read_text())

    async def fake_catalog(refresh=False):
        return models
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    monkeypatch.setattr(canvas, "grouped_models", wavespeed.grouped_models)


@pytest.mark.parametrize("tool,feature", [("animate_image", "image_to_video"),
                                          ("generate_image", "text_to_image"),
                                          ("edit_image", "image_edit")])
async def test_list_models_tool_name_matches_feature(mock_catalog, tool, feature):
    for extra in ({}, {"all": True}):
        assert (await canvas._list_models({"type": tool, **extra})
                == await canvas._list_models({"type": feature, **extra}))


async def test_list_models_unknown_type_lists_valid_names(mock_catalog):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await canvas._list_models({"type": "bogus"})
    msg = str(e.value)
    for name in ("video", "image_to_video", "text_to_image", "animate_image", "generate_image"):
        assert name in msg
