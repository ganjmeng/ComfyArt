"""Ask-card preselection after the brand badge-only change.

The client selects only an explicit defaults list. The server still copies a
recommended flag into defaults, except where a skill normalizer strips it.
Brand card 3 keeps the badge and clears defaults. Historical answers stay the
user's choice. No WaveSpeed call.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ComfyArt.api import bot_asks, brand_identity, portrait_studio, product_packaging
from ComfyArt.api.multi_angle import SOURCE, normalize_card

ROOT = Path(__file__).resolve().parents[1]


def _selected(spec: dict) -> list[str]:
    """What qDefaults would select: explicit defaults only, never a bare recommended flag."""
    q = (spec.get("questions") or [spec])[0]
    return list(q.get("defaults") or spec.get("defaults") or [])


def test_generic_ask_user_preselects_the_recommended_option():
    spec = bot_asks.validate_spec({
        "prompt": "which direction?",
        "options": [
            {"id": "a", "label": "A", "recommended": True},
            {"id": "b", "label": "B"},
        ],
    })
    assert spec["defaults"] == ["a"]
    assert spec["options"][0]["recommended"] is True
    assert _selected(spec) == ["a"]


def test_multi_angle_recommended_word_is_not_a_preselect():
    raw = normalize_card({"questions": [{
        "id": SOURCE, "prompt": "产品参考图怎么提供？",
        "options": [{"id": "multiple", "label": "上传多角度产品图"}],
    }]})
    spec = bot_asks.validate_spec(raw)
    assert [q["id"] for q in spec["questions"]] == ["ma_source", "ma_aspect"]
    for q in spec["questions"]:
        assert "defaults" not in q
        assert not any(o.get("recommended") for o in q["options"])
        assert _selected({"questions": [q]}) == []
    aspect = spec["questions"][1]
    assert any("推荐" in o["label"] for o in aspect["options"])


def test_portrait_and_packaging_cards_ship_with_nothing_selected():
    for spec in (portrait_studio.card_spec("zh"), product_packaging.card_spec(None, "en")):
        got = bot_asks.validate_spec(spec)
        assert "defaults" not in got
        for q in got["questions"]:
            assert "defaults" not in q
            assert not any(o.get("recommended") for o in q["options"])


def test_clothing_swap_strips_a_recommended_default():
    spec = bot_asks.validate_spec({
        "questions": [{
            "id": "upper_body_swap",
            "prompt": "How should I replace the upper-body garment?",
            "options": [
                {"id": "a", "label": "Keep the collar", "recommended": True},
                {"id": "b", "label": "Replace the whole top"},
            ],
            "defaults": ["a"],
            "allow_other": True,
        }],
        "page_count": 1,
    })
    assert "defaults" not in spec
    assert not any(o.get("recommended") for o in spec["questions"][0]["options"])
    assert _selected(spec) == []


def test_studio_model_preselects_only_when_the_model_sent_recommended():
    bare = bot_asks.validate_spec({
        "questions": [{
            "id": "studio_direction",
            "prompt": "选一个棚拍方向继续生成：",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "allow_other": True,
        }],
        "page_count": 1,
    })
    assert "defaults" not in bare["questions"][0]
    marked = bot_asks.validate_spec({
        "questions": [{
            "id": "studio_direction",
            "prompt": "选一个棚拍方向继续生成：",
            "options": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B", "recommended": True},
            ],
            "allow_other": True,
        }],
        "page_count": 1,
    })
    assert marked["questions"][0]["defaults"] == ["b"]
    assert marked["questions"][0]["options"][1]["recommended"] is True


def test_ai_model_shipped_card_has_no_preselect():
    from test_ai_model_ask_911 import Q1_LABELS, Q1_OTHER, Q1_PROMPT, Q2_LABELS, Q2_OTHER, Q2_PROMPT, Q3_LABELS, Q3_OTHER, Q3_PROMPT

    def opts(*labels: str):
        return [{"id": letter, "label": label} for letter, label in zip("ABC", labels)]

    spec = bot_asks.validate_spec({
        "questions": [
            {"id": "look", "prompt": Q1_PROMPT, "options": opts(*Q1_LABELS), "allow_other": True, "placeholder": Q1_OTHER, "page": 1},
            {"id": "backdrop", "prompt": Q2_PROMPT, "options": opts(*Q2_LABELS), "allow_other": True, "placeholder": Q2_OTHER, "page": 1},
            {"id": "output", "prompt": Q3_PROMPT, "options": opts(*Q3_LABELS), "allow_other": True, "placeholder": Q3_OTHER, "page": 1},
        ],
        "page_count": 3,
        "allow_skip": True,
    })
    assert "defaults" not in spec
    for q in spec["questions"]:
        assert "defaults" not in q
        assert not any(o.get("recommended") for o in q["options"])


def test_youtube_banner_cards_do_not_preselect_either_language():
    for lang in ("zh", "en"):
        for qid in ("yt_delivery", "yt_direction"):
            spec = bot_asks.validate_spec(bot_asks.normalize_youtube_banner_card({
                "questions": [{
                    "id": qid,
                    "prompt": "x",
                    "options": [
                        {"id": "A", "label": "A", "recommended": True, "description": "(Recommended) top"},
                        {"id": "B", "label": "B"},
                    ],
                    "defaults": ["A"],
                }],
            }, lang))
            assert "defaults" not in spec
            for q in spec["questions"]:
                assert "defaults" not in q
                assert not any(o.get("recommended") for o in q["options"])
                assert _selected({"questions": [q]}) == []


def test_brand_card3_keeps_the_badge_and_clears_the_default():
    brand_identity.reset_for_tests()
    try:
        for slot in ("logo_a", "logo_b", "logo_c"):
            brand_identity.record_submitted({"brand_slot": slot}, {"ids": [f"holder-{slot}"]})
            brand_identity.record_wait({"results": [{
                "id": f"holder-{slot}",
                "shapes": [f"shape:{slot}"],
                "urls": [f"/view?f={slot}.png"],
            }]})
        spec = bot_asks.validate_spec({"questions": [{
            "id": "bi_direction",
            "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
            "options": [
                {"id": "A", "label": "方向 A", "recommended": True},
                {"id": "B", "label": "方向 B"},
                {"id": "C", "label": "方向 C"},
            ],
        }]})
        assert "defaults" not in spec["questions"][0]
        assert spec["questions"][0]["options"][0]["recommended"] is True
        assert _selected(spec) == []
    finally:
        brand_identity.reset_for_tests()


def test_client_qdefaults_ignores_a_bare_recommended_flag():
    text = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    start = text.index("function qDefaults")
    body = text[start:text.index("function initQStates")]
    body = body.replace("(q: AskQuestion): string[]", "(q)")
    assert "recommended" not in body
    script = body + r"""
const cases = [
  [{ defaults: ['a'], options: [{id:'a'},{id:'b'}], max_selections: 1 }, ['a']],
  [{ options: [{id:'a', recommended: true},{id:'b'}] }, []],
  [{ defaults: [], options: [{id:'a', recommended: true}] }, []],
  [{ defaults: ['a','b'], max_selections: 1, options: [{id:'a'},{id:'b'}] }, ['a']],
];
for (const [q, want] of cases) {
  const got = qDefaults(q);
  if (JSON.stringify(got) !== JSON.stringify(want)) {
    console.error(JSON.stringify({q, got, want}));
    process.exit(1);
  }
}
console.log('ok');
"""
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, (run.stdout, run.stderr)


async def test_historical_card_replays_the_users_answer(bot_client, fake_provider):
    """An answered card keeps the choice the user made, not the recommended default."""
    from ComfyArt.api import chat_store

    spec = bot_asks.validate_spec({
        "prompt": "which direction?",
        "options": [
            {"id": "a", "label": "A", "recommended": True},
            {"id": "b", "label": "B"},
        ],
    })
    assert spec["defaults"] == ["a"]
    chat = (await (await bot_client.post(
        "/comfyart/bot/chats", json={"project": "p", "provider": "fake-test"})).json())["chat"]
    msg = chat_store.create_message(
        chat_id=chat["id"], role="assistant",
        blocks=[{"type": "ask", "ask_id": "pending", "status": "pending", **spec}],
        status="streaming",
    )
    ask = bot_asks.create_ask(chat["id"], msg["id"], spec)
    chat_store.update_message(chat["id"], msg["id"], blocks=[
        {"type": "ask", "ask_id": ask.id, "status": "pending", **spec},
    ])
    bot_asks.PENDING.clear()
    assert bot_asks.reload_pending_from_store() == 1
    ok = await bot_client.post(
        f"/comfyart/bot/chats/{chat['id']}/asks/{ask.id}/answer",
        json={"selected": ["b"], "other_text": ""},
    )
    assert ok.status == 202, await ok.text()
    block = next(b for m in chat_store.list_messages(chat["id"]) for b in m["blocks"] if b.get("type") == "ask")
    assert block["status"] == "answered"
    assert block["selected"] == ["b"]
    assert block["defaults"] == ["a"]
    assert block["options"][0]["recommended"] is True
