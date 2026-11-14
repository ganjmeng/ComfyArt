"""#909: 「一张主图，再加几张…」 is one image of the set, not the set's total.

`requested_count()` feeds the paid-guard cap. The old parser took the max of
every "N 张 / N images" match, so the taobao-product message's 「一张」 became
count=1 and the four-image plan stopped after the first submit.

The pure cases lock the split between a whole-group total ("做 3 张"), a lone
item request ("做一张主图" = 1), and a parallel item list with no total
("一张主图，两张场景图" = 0, follow the plan). The e2e replays the real built-in
agent path with a scripted LLM (mock MCP handlers, no LLM, no WaveSpeed). $0.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.api import mcp, paid_guard
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.guide import PAID_TOOLS
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest

TAOBAO_ZH = (
    "帮我用这张商品图做一组淘宝商品图：一张干净的主图，再加几张模特上身和场景图，"
    "整组风格统一。不要编品牌名、价格和功效数字。"
)
TAOBAO_EN = (
    "Use this product photo to make a Taobao product set: one clean main image, "
    "plus a few model and scene shots, one consistent style. Do not invent a "
    "brand, price or efficacy numbers."
)
MODEL = "test/group-plan-909"
UNIT = 0.14  # 14 credits per image
THRESHOLD = 0.50  # 50-credit confirm line
PLAN = [
    ("干净主图 1:1", "Taobao main image, clean studio background"),
    ("模特全身 3:4", "Taobao model full-body shot"),
    ("模特半身 3:4", "Taobao model half-body detail shot"),
    ("生活场景 3:4", "Taobao lifestyle scene shot"),
]


@pytest.mark.parametrize("text,want", [
    (TAOBAO_ZH, 0),                      # AC2: item list, no total
    ("一张干净的主图，再加几张模特上身和场景图", 0),
    # A lone item request is still one image (product HOLD).
    ("做一张主图", 1),
    ("帮我做一张淘宝主图", 1),
    ("就要一张主图", 1),
    ("一张主图", 1),
    ("主图一张", 1),
    ("一张干净的主图", 1),
    ("做一张干净的主图", 1),
    # A parallel item list with no whole-group total: follow the plan.
    ("一张主图，两张场景图", 0),
    ("帮我做一张主图，两张场景图", 0),
    ("一张主图，再做三张场景图", 0),
    ("帮我做三张主图，两张场景图", 0),
    ("主图一张，场景图两张", 0),
    ("一张主图一张场景", 0),
    ("一张主图，几张场景图", 0),
    ("再做两张主图，另外一张场景图", 0),
    ("帮我做三张主图，几张场景图", 0),
    # An explicit total still wins over the list.
    ("两张图，一张主图一张场景", 2),
    ("做 3 张", 3),
    ("一共 2 张", 2),
    ("总共四张", 4),
    ("做五张", 5),
    ("就要 1 张", 1),
    ("只做 1 张", 1),
    ("做 3 张主图", 3),                   # one item, no list
    ("一共 4 张：一张主图，再加两张场景图", 4),
    ("一张主图，两张场景图，共 4 张", 4),
    ("做 3 张，一张主图两张场景图", 3),
    ("做 3 张：一张主图，再做两张场景图", 3),
    ("画 6 张猫的插画", 6),
    ("做 12 张商品图", 12),
    ("做一张猫的海报", 1),                # #142 regression: one image stays one
    ("做一张海报 1:1", 1),
    ("第二张图再亮一点", 0),              # ordinal: refers to one image
    ("几张", 0),                          # vague quantities are not totals
    ("若干", 0),
    ("再加几张场景图", 0),
    ("做若干张", 0),
    ("用这张商品图做一组淘宝商品图，风格统一", 0),
])
def test_requested_count_zh(text, want):
    assert paid_guard.requested_count(text) == want


@pytest.mark.parametrize("text,want", [
    ("just one hero image", 1),
    ("one clean hero image", 1),
    ("just one clean hero image", 1),
    ("make one clean main image", 1),
    ("one clean single hero image", 1),
    ("one clean image", 1),
    ("one of the images", 0),
    ("one of the two clean hero images", 0),
    ("one image, two scenes", 0),
    ("one image", 1),
    ("two pictures", 2),
    ("make 3 images", 3),
    ("3 images total", 3),
    ("a set of 5 images", 5),
    (TAOBAO_EN, 0),  # item + "plus": the parts are not a total
    ("1 main image, plus a few model and scene shots", 0),
    ("one clean hero image, plus a few model and scene shots", 0),
    ("one main image, two scene shots", 0),
    ("1 image, 2 scene shots", 0),
    ("2 images, one main image and one scene shot", 2),
    ("several images", 0),
    ("a few photos", 0),
    ("make the set", 0),
])
def test_requested_count_en(text, want):
    assert paid_guard.requested_count(text) == want


def test_vague_quantities_never_inflate_the_cap():
    for text in ("几张", "再加几张", "若干张", "a few images", "several photos"):
        assert paid_guard.requested_count(text) == 0


def test_group_description_gets_the_default_cap():
    paid_guard.TURNS.clear()
    try:
        guard = paid_guard.begin_turn("c909-cap", text=TAOBAO_ZH,
                                      provider_text=TAOBAO_ZH, lang="zh")
        assert guard.cap == paid_guard.DEFAULT_CAP
        assert guard.user_count == 0
    finally:
        paid_guard.TURNS.clear()


def test_plan_cap_follows_the_plan_only_without_an_explicit_total():
    """AC2: no user total -> a 6-image plan may set the cap to 6.
    AC1: "做 3 张" stays exactly 3 even if the model planned 6."""
    paid_guard.TURNS.clear()
    try:
        guard = paid_guard.begin_turn("c909-plan", text=TAOBAO_ZH,
                                      provider_text="", lang="zh")
        paid_guard.allow_planned_cap("c909-plan", 6)
        assert guard.cap == 6
        paid_guard.TURNS.clear()

        guard = paid_guard.begin_turn("c909-explicit", text="做 3 张",
                                      provider_text="", lang="zh")
        paid_guard.allow_planned_cap("c909-explicit", 6)
        assert guard.cap == 3
    finally:
        paid_guard.TURNS.clear()


# ---- end-to-end mock: quote card says 4 images, then 4 submits are allowed ----------------

def _tc(i: int, name: str, args: dict) -> dict:
    return {"id": f"t{i}", "function": {"name": name,
                                        "arguments": json.dumps(args, ensure_ascii=False)}}


def _reply(*calls: tuple[str, dict]) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        _tc(i, name, args) for i, (name, args) in enumerate(calls)]}}]}


def _arguments(i: int, plan=PLAN) -> dict:
    return {"prompt": plan[i][1], "model": MODEL,
            "ratio": "1:1" if i == 0 else "3:4"}


def _quote_steps(plan=PLAN) -> list[dict]:
    return [{"text": plan[i][0], "tool": "generate_image", "model": MODEL,
             "arguments": _arguments(i, plan)} for i in range(len(plan))]


def _update_plan(plan=PLAN) -> dict:
    return {"steps": [{"text": plan[i][0],
                       "status": "active" if i == 0 else "pending"}
                      for i in range(len(plan))]}


def _responses(plan=PLAN) -> list[dict]:
    out = [_reply(("update_plan", _update_plan(plan)),
                  ("quote_plan", {"steps": _quote_steps(plan)}))]
    for i in range(len(plan)):
        out.append(_reply(("generate_image", _arguments(i, plan))))
    out.append({"choices": [{"message": {"content": f"整组 {len(plan)} 张已出。",
                                        "tool_calls": []}}]})
    return out


async def _run_taobao_plan(monkeypatch, *, plan=PLAN, user_text=TAOBAO_ZH):
    chat_id = "c909-e2e"
    paid: list[dict] = []
    specs: list[dict] = []
    paid_before_confirm: list[int] = []
    events: list[BotEvent] = []

    def fake_tool(name: str):
        async def handler(args):
            if name in PAID_TOOLS:
                paid.append(dict(args))
                return {"ids": [f"gen:{len(paid)}"]}
            return {"ok": True}
        return handler

    for name in ("generate_image", "update_plan"):
        monkeypatch.setitem(mcp.TOOLS, name, {**mcp.TOOLS[name],
                                              "handler": fake_tool(name),
                                              "_paid_guarded": False})
    mcp._install_paid_handler_guards()

    provider = LocalLlmProvider(base_url=lambda: "http://fake-llm/v1")
    responses = _responses(plan)

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if str(url).endswith("/chat/completions"):
            return responses.pop(0)
        return {"result": {"tools": [{"name": n} for n in ("generate_image", "update_plan")]}}

    async def fake_call(session, endpoint, name, arguments):
        token = BOT_CHAT_ID.set(chat_id)
        try:
            out = await mcp._tools_call({"name": name, "arguments": arguments})
        finally:
            BOT_CHAT_ID.reset(token)
        text = out["content"][0]["text"]
        return ("[tool error] " + text if out["isError"] else text), []

    async def fake_price(model, inputs):
        return UNIT

    async def fake_models(feature):
        return [("test/dearest-909", UNIT)]

    async def fake_price_call(name, args):
        return UNIT

    async def fake_confirm(spec, turn, handle, **_kw):
        paid_before_confirm.append(len(paid))
        specs.append(spec)
        return "start"

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    monkeypatch.setattr(provider, "_price_one", fake_price)
    monkeypatch.setattr(provider, "_models_for", fake_models)
    monkeypatch.setattr(provider, "_price_call", fake_price_call)
    monkeypatch.setattr(provider, "_quote_route", lambda tool, args, position=0: None)
    monkeypatch.setattr(provider, "_threshold", lambda: THRESHOLD)
    monkeypatch.setattr(provider, "_confirm_plan", fake_confirm)

    async def emit(ev: BotEvent):
        events.append(ev)

    paid_guard.TURNS.clear()
    paid_guard.begin_turn(chat_id, text=user_text, provider_text=user_text, lang="zh")
    try:
        result = await provider.send(
            TurnRequest(chat_id=chat_id, user_text=user_text, lang="zh",
                        mcp_endpoint="http://x/mcp", model="m1"),
            emit, TurnHandle())
        stop = paid_guard.end_turn(chat_id)
    finally:
        paid_guard.TURNS.clear()
    return result, stop, specs, paid, events, paid_before_confirm


async def test_taobao_plan_quote_shows_four_images_and_all_four_submit(monkeypatch):
    result, stop, specs, paid, events, before = await _run_taobao_plan(monkeypatch)

    # AC3: the confirm card priced the four planned images before any submit.
    assert len(specs) == 1
    spec = specs[0]
    assert spec["kind"] == "plan_quote"
    assert len(spec["lines"]) == 4, spec["lines"]
    assert spec["total"] == "56 积分", spec  # 4 x 14 credits
    assert spec["total_label"] == "总价"
    assert [ln["price"] for ln in spec["lines"]] == ["14 积分"] * 4, spec["lines"]
    assert "共 4 步" in spec["prompt"] and "56" in spec["prompt"], spec["prompt"]
    assert before == [0], "nothing may be submitted before the card is confirmed"

    # AC2: confirming the four-image plan lets all four paid submits through.
    assert stop == "" and result.error == ""
    assert [args["prompt"] for args in paid] == [p for _t, p in PLAN]
    rows = [e for e in events
            if e.t == "tool_result" and e.name == "generate_image"]
    assert len(rows) == 4 and not any(r.is_error for r in rows), rows
    assert all("ids" in (r.text or "") for r in rows), rows


NO_TOTAL_ZH = "用这张商品图做一套淘宝商品图，风格统一。"
PLAN6 = PLAN + [
    ("细节特写 3:4", "Taobao fabric detail close-up"),
    ("卖点模块 3:4", "Taobao selling-point detail module"),
]


async def test_a_six_image_plan_without_a_user_total_is_not_capped_at_four(monkeypatch):
    """AC2: the cap follows the model's planned set, not DEFAULT_CAP."""
    result, stop, specs, paid, _events, _before = await _run_taobao_plan(
        monkeypatch, plan=PLAN6, user_text=NO_TOTAL_ZH)
    assert len(specs) == 1 and len(specs[0]["lines"]) == 6, specs
    assert specs[0]["total"] == "84 积分", specs[0]
    assert stop == "" and result.error == ""
    assert [args["prompt"] for args in paid] == [p for _t, p in PLAN6]


def _plan(n: int) -> list[tuple[str, str]]:
    return [(f"规划图 {i + 1}", f"planned image {i + 1}") for i in range(n)]


@pytest.mark.parametrize("text", [
    "做一张主图", "帮我做一张淘宝主图", "就要一张主图", "just one hero image",
    "one clean hero image", "just one clean hero image",
    "make one clean main image", "做一张干净的主图",
])
async def test_lone_item_request_submits_one_of_a_four_image_plan(monkeypatch, text):
    """Product HOLD: a lone item request is 1, not 0 (which would release all 4)."""
    result, stop, specs, paid, _events, before = await _run_taobao_plan(
        monkeypatch, plan=_plan(4), user_text=text)
    assert len(specs) == 1 and before == [0], specs
    assert len(paid) == 1, paid
    assert stop.startswith("已生成 1 张"), stop


@pytest.mark.parametrize("text,want", [("做 3 张", 3), ("就要 1 张", 1), ("只做 1 张", 1)])
async def test_stated_total_caps_the_four_image_plan(monkeypatch, text, want):
    _result, stop, _specs, paid, _events, _before = await _run_taobao_plan(
        monkeypatch, plan=_plan(4), user_text=text)
    assert len(paid) == want, paid
    assert stop.startswith(f"已生成 {want} 张"), stop


@pytest.mark.parametrize("text,n", [
    ("帮我做一张主图，两张场景图", 3),
    ("帮我做一张主图，两张场景图", 4),
    ("帮我做三张主图，两张场景图", 5),
    ("一张主图，再做三张场景图", 4),
    ("主图一张，场景图两张", 3),
    ("one image, two scenes", 3),
])
async def test_parallel_item_list_follows_the_planned_count(monkeypatch, text, n):
    """QA HOLD: no whole-group total -> all n planned images submit, not the part count."""
    plan = _plan(n)
    result, stop, specs, paid, events, before = await _run_taobao_plan(
        monkeypatch, plan=plan, user_text=text)
    assert stop == "" and result.error == "", stop
    assert [args["prompt"] for args in paid] == [p for _t, p in plan], paid
    if n * UNIT >= THRESHOLD:
        assert len(specs) == 1 and len(specs[0]["lines"]) == n, specs
        assert specs[0]["total"] == f"{n * 14} 积分", specs[0]
        assert before == [0]
    else:
        assert specs == []
    rows = [e for e in events
            if e.t == "tool_result" and e.name == "generate_image"]
    assert len(rows) == n and not any(r.is_error for r in rows), rows


async def test_one_of_the_images_is_not_a_single_image_total(monkeypatch):
    """Ownership ("one of the images") must not cap a 4-image plan at 1."""
    result, stop, specs, paid, _events, before = await _run_taobao_plan(
        monkeypatch, plan=_plan(4), user_text="one of the images")
    assert stop == "" and result.error == "", stop
    assert len(paid) == 4, paid
    assert len(specs) == 1 and len(specs[0]["lines"]) == 4, specs
    assert before == [0]
