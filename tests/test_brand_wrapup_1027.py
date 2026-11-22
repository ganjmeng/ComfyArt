"""Brand closing text: success order, failed finals, duplicate lists, turn cleanup.

Both model loops use the same three calls: accept_assistant_text, release_wrapup
after tools, end_turn when the turn ends. No WaveSpeed call.
"""
from __future__ import annotations

from pathlib import Path

from ComfyArt.api import brand_identity as brand
from ComfyArt.api.bot_asks import validate_spec
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.skill_output import apply_generate

ROOT = Path(__file__).resolve().parents[1]
SUCCESS = "本次交付清单：规范卡、外带杯与杯套、纸袋、门店门头。"
OTHER = "下一步可以做一张菜单板。"


def setup_function():
    brand.reset_for_tests()
    BOT_CHAT_ID.set("wrap-1027")


def teardown_function():
    brand.reset_for_tests()
    BOT_CHAT_ID.set("")


def _card1():
    return validate_spec({"questions": [
        {"id": "bi_delivery", "prompt": "这次「基础品牌视觉系统」要交付哪些物料？", "options": [{"id": "A", "label": "x"}]},
        {"id": "bi_color", "prompt": "色彩方向选哪一种？", "options": [{"id": "A", "label": "x"}]},
        {"id": "bi_mark", "prompt": "Logo 的构成方向偏好？", "options": [{"id": "A", "label": "x"}]},
        {"id": "bi_source", "prompt": "门店与产品素材怎么处理？", "options": [{"id": "A", "label": "x"}]},
    ], "page_count": 4})


def _reach_finals():
    brand.record_card_answer(_card1(), {"bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
                                         "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]}})
    mood = apply_generate({"skill": brand.SKILL, "prompt": "board"}, brand.SKILL)
    brand.record_submitted(mood, {"ids": ["h-mood"]})
    brand.record_wait({"results": [{"id": "h-mood", "shapes": ["shape:mood"], "urls": ["/m.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
                       "options": [{"id": "A", "label": "就这版，通过"}]}],
    }), {"bi_moodboard": {"selected": ["A"]}})
    for slot in ("logo_a", "logo_b", "logo_c"):
        logo = apply_generate({"skill": brand.SKILL, "prompt": slot}, brand.SKILL)
        brand.record_submitted(logo, {"ids": [f"h-{slot}"]})
        brand.record_wait({"results": [{"id": f"h-{slot}", "shapes": [f"shape:{slot}"], "urls": [f"/{slot}.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_direction", "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
                       "options": [{"id": "A", "label": "方向 A"}]}],
    }), {"bi_direction": {"selected": ["A"]}})


def _submit_finals():
    slots = []
    for name in ("spec", "cup", "bag", "store"):
        final = apply_generate({"skill": brand.SKILL, "prompt": name}, brand.SKILL)
        brand.record_submitted(final, {"ids": [f"h-{final['brand_slot']}"]})
        slots.append(final["brand_slot"])
    return slots


def _place(slot):
    brand.record_wait({"results": [{"id": f"h-{slot}", "status": "done", "shapes": [f"shape:{slot}"],
                                    "urls": [f"/{slot}.png"]}]})


def _fail(slot):
    brand.record_wait({"results": [{"id": f"h-{slot}", "status": "error", "shapes": [], "error": "generation failed"}]})


def test_both_pathways_flush_when_the_turn_ends():
    agent = (ROOT / "bot/agent_loop.py").read_text(encoding="utf-8")
    local = (ROOT / "bot/local_llm.py").read_text(encoding="utf-8")
    for name, text in (("agent_loop", agent), ("local_llm", local)):
        assert "accept_assistant_text(" in text, name
        assert "release_wrapup(" in text, name
        assert "end_turn(" in text, name
    finish_at = agent.index("async def finish")
    assert agent.index("end_turn(", finish_at) < agent.index('t="run_stop"', finish_at)
    send_at = local.index("async def send")
    assert local.index("end_turn(", send_at) < local.index("reset_llm_project(project_token)", send_at)


def test_agent_loop_success_releases_after_the_four_images_and_not_before():
    """agent_loop: hold the closing, release it after the wait tools, then end the turn."""
    _reach_finals()
    assert brand.accept_assistant_text(SUCCESS) == ""
    slots = _submit_finals()
    for slot in slots[:-1]:
        _place(slot)
        assert brand.release_wrapup("zh") == ""
    _place(slots[-1])
    assert brand.release_wrapup("zh") == SUCCESS
    assert brand.end_turn("zh") == ""


def test_local_llm_success_same_order_when_the_finally_also_runs():
    """local_llm: release after tools, then the send finally calls end_turn and must not repeat it."""
    _reach_finals()
    assert brand.accept_assistant_text(SUCCESS) == ""
    for slot in _submit_finals():
        _place(slot)
    assert brand.release_wrapup("zh") == SUCCESS
    assert brand.end_turn("zh") == ""


def test_one_failed_final_names_that_material_and_drops_the_success_list():
    _reach_finals()
    assert brand.accept_assistant_text(SUCCESS) == ""
    slots = _submit_finals()
    for slot in slots:
        if slot == "cup":
            _fail(slot)
        else:
            _place(slot)
    # agent_loop releases after the wait tool. local_llm does the same, then finally end_turn.
    released = brand.release_wrapup("zh")
    assert "外带杯与杯套" in released
    assert "规范卡" not in released and "纸袋" not in released and "门店门头" not in released
    assert "本次交付清单" not in released
    assert brand.end_turn("zh") == ""


def test_all_failed_finals_are_named_on_both_pathways():
    _reach_finals()
    assert brand.accept_assistant_text(SUCCESS) == ""
    for slot in _submit_finals():
        _fail(slot)
    released = brand.release_wrapup("en")
    for name in ("Guideline card", "Takeaway cup", "Paper bag", "Storefront"):
        assert name in released
    assert "delivery list" not in released.casefold()
    assert "本次交付清单" not in released
    assert brand.end_turn("en") == ""


def test_local_llm_no_tool_return_still_flushes_the_failure():
    """The legacy loop returns as soon as the model sends text and no tools. The finally must flush."""
    _reach_finals()
    slots = _submit_finals()
    for slot in slots:
        if slot == "bag":
            _fail(slot)
        else:
            _place(slot)
    assert brand.accept_assistant_text(SUCCESS) == ""
    flushed = brand.end_turn("zh")
    assert "纸袋" in flushed
    assert "本次交付清单" not in flushed


def test_consecutive_closing_lists_collapse_to_one_and_other_text_stays():
    _reach_finals()
    assert brand.accept_assistant_text(SUCCESS) == ""
    assert brand.accept_assistant_text("本次交付清单：第二份。") == ""
    for slot in _submit_finals():
        _place(slot)
    assert brand.release_wrapup("zh") == SUCCESS
    assert brand.accept_assistant_text("本次交付清单：又一份。") == ""
    assert brand.accept_assistant_text(OTHER) == OTHER
    assert brand.end_turn("zh") == ""


def test_running_wait_does_not_finalize_and_a_later_done_releases_the_list():
    _reach_finals()
    slots = _submit_finals()
    assert brand.accept_assistant_text(SUCCESS) == ""
    brand.record_wait({"status": "running", "results": [
        {"id": f"h-{slot}", "status": "running"} for slot in slots]})
    assert brand.release_wrapup("zh") == ""
    assert "cup" not in (brand._progress().get("failed") or [])
    for slot in slots:
        _place(slot)
    assert brand.release_wrapup("zh") == SUCCESS


def test_mixed_message_keeps_links_and_drops_only_the_list_line():
    _reach_finals()
    shown = brand.accept_assistant_text(
        "进度正常。\n本次交付清单：规范卡。\n下载：https://example.com/spec.png")
    assert "进度正常" in shown and "https://example.com/spec.png" in shown
    assert "本次交付清单" not in shown
    for slot in _submit_finals():
        _place(slot)
    assert brand.release_wrapup("zh") == "本次交付清单：规范卡。"
    again = brand.accept_assistant_text(
        "补充说明。\n本次交付清单：又一份。\n下载：https://example.com/b.png")
    assert "补充说明" in again and "https://example.com/b.png" in again
    assert "又一份" not in again


def test_a_question_that_only_mentions_the_words_is_kept():
    _reach_finals()
    for slot in _submit_finals():
        _place(slot)
    question = "你问“交付清单”是什么意思：它是文件列表，不含商标注册服务。"
    assert brand.accept_assistant_text(question) == question
    shown = brand.accept_assistant_text("本次交付清单：四张。")
    assert "本次交付清单" in shown
    kept = brand.accept_assistant_text(
        "本次交付清单：四张。\n你问的文件下载地址是 /download/qimu.zip，请用这个链接。")
    assert "/download/qimu.zip" in kept
    assert "请用这个链接" in kept
    assert "本次交付清单" not in kept


def test_progress_does_not_take_the_closing_slot():
    _reach_finals()
    assert brand.accept_assistant_text("正在生成四份成品，请稍候。") == "正在生成四份成品，请稍候。"
    assert brand.accept_assistant_text("本次交付清单：四张完成。") == ""
    for slot in _submit_finals():
        _place(slot)
    assert brand.release_wrapup("zh") == "本次交付清单：四张完成。"


def test_cancel_names_what_is_still_generating():
    _reach_finals()
    slots = _submit_finals()
    brand.accept_assistant_text(SUCCESS)
    brand.record_wait({"status": "running", "results": [
        {"id": f"h-{slot}", "status": "running"} for slot in slots]})
    note = brand.end_turn("zh")
    assert "仍在生成" in note
    assert "规范卡" in note and "外带杯与杯套" in note
    assert "没有落图" not in note
    assert "本次交付清单" not in note
    assert brand.end_turn("zh") == ""


def test_end_turn_clears_deferred_text_for_the_next_turn_and_other_chats():
    _reach_finals()
    brand.accept_assistant_text(SUCCESS)
    slots = _submit_finals()
    _fail(slots[0])
    for slot in slots[1:]:
        _place(slot)
    first = brand.end_turn("zh")
    assert "规范卡" in first and "本次交付清单" not in first
    assert brand.release_wrapup("zh") == ""
    assert brand.end_turn("zh") == ""
    token = BOT_CHAT_ID.set("wrap-other")
    try:
        assert brand.accept_assistant_text("普通说明") == "普通说明"
        assert brand.release_wrapup("zh") == ""
    finally:
        BOT_CHAT_ID.reset(token)
