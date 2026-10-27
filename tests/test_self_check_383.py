"""#383 goal self-check before reporting done (unit level; the e2e cases live in agent_regression)."""
from __future__ import annotations

import json

import pytest

from ComfyArt.bot.self_check import apply_to_blocks, check, parse_goal, scrub_done_claims

DONE_WORDS = ("完成", "已完成", "Done")


def gen_blocks(n_jobs: int, shapes_per_job: int = 1, fail: bool = False):
    blocks = []
    for j in range(n_jobs):
        blocks += [{"type": "tool_use", "name": "generate_image", "input": {"prompt": f"cat {j}", "model": "m"}},
                   {"type": "tool_result", "name": "generate_image", "text": json.dumps({"ids": [f"j{j}"]})}]
    results = []
    for j in range(n_jobs):
        if fail:
            results.append({"id": f"j{j}", "status": "error", "error": "content filter"})
        else:
            results.append({"id": f"j{j}", "status": "done",
                            "shapes": [{"id": f"shape:{j}-{k}"} for k in range(shapes_per_job)]})
    blocks += [{"type": "tool_use", "name": "wait_generation", "input": {"ids": [f"j{j}" for j in range(n_jobs)]}},
               {"type": "tool_result", "name": "wait_generation", "status": "error" if fail else "ok",
                "text": json.dumps({"results": results})}]
    return blocks


def ids(n):
    return {f"shape:{j}-0" for j in range(n)}


@pytest.mark.parametrize("text,kind,count", [("画 4 张猫", "image", 4), ("Make 4 cat images", "image", 4),
                                             ("生成两段视频", "video", 2), ("让选中的图动起来做成视频", "video", 1)])
def test_parse_goal(text, kind, count):
    g = parse_goal(text)
    assert (g.kind, g.count) == (kind, count)


@pytest.mark.parametrize("text", ["什么是 LoRA？", "What is a seed?"])
def test_pure_qa_is_not_checked(text):
    sc = check(text, [{"type": "text", "text": "A seed is ..."}])
    assert not sc.applies and sc.to_dict()["self_check"] == "skip"


@pytest.mark.parametrize("lang,text", [("zh", "画 4 张猫"), ("en", "Make 4 cat images")])
def test_four_on_canvas_passes(lang, text):
    sc = check(text, gen_blocks(4), canvas_ids=ids(4))
    assert sc.passed and sc.to_dict()["self_check"] == "pass"


def test_one_job_with_four_outputs_counts_four():
    sc = check("画 4 张猫", gen_blocks(1, shapes_per_job=4))
    assert sc.generated == 4 and sc.placed == 4 and sc.passed


@pytest.mark.parametrize("lang,text,claim", [("zh", "画 4 张猫", "已完成 4 张！完成。"),
                                             ("en", "Make 4 cat images", "Done! All done, 4 images completed.")])
def test_four_generated_two_on_canvas_fails(lang, text, claim):
    blocks = gen_blocks(4) + [{"type": "text", "text": claim}]
    out, sc = apply_to_blocks(text, blocks, lang, canvas_ids=ids(2))
    assert sc["self_check"] == "fail" and sc["missing"] == 2 and sc["placed"] == 2 and sc["generated"] == 4
    reply = " ".join(b["text"] for b in out if b["type"] == "text")
    assert not any(w in reply for w in DONE_WORDS)
    note = out[-1]["text"]
    assert ("缺 2 张" in note) if lang == "zh" else ("2 missing" in note)
    assert not any(w in note for w in ("已完成", "Done"))


def test_placed_must_reach_expected_not_just_positive():
    sc = check("画 4 张猫", gen_blocks(4), canvas_ids=ids(1))
    assert sc.placed == 1 and not sc.passed


def test_tool_success_alone_is_not_enough():
    sc = check("画 4 张猫", gen_blocks(4), canvas_ids=set())
    assert sc.generated == 4 and sc.placed == 0 and not sc.passed


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_all_failed_reports_reason_no_done(lang):
    blocks = gen_blocks(4, fail=True) + [{"type": "text", "text": "已完成！" if lang == "zh" else "Done!"}]
    out, sc = apply_to_blocks("画 4 张猫", blocks, lang)
    assert sc["self_check"] == "fail" and sc["missing"] == 4
    assert not any(w in " ".join(b.get("text", "") for b in out if b["type"] == "text") for w in DONE_WORDS)


@pytest.mark.parametrize("lang,text,claim", [("zh", "画 4 张猫", "已完成 4 张"),
                                             ("en", "Make 4 cat images", "Done, 4 images are on the canvas.")])
def test_claim_without_any_tool_call_is_rewritten(lang, text, claim):
    out, sc = apply_to_blocks(text, [{"type": "text", "text": claim}], lang)
    assert sc["self_check"] == "fail" and sc["missing"] == 4
    assert out[0]["text"] != claim and not any(w in out[0]["text"] for w in DONE_WORDS)


def test_scrub_keeps_negations_and_words():
    assert "未完成" in scrub_done_claims("仍未完成")
    assert scrub_done_claims("not done yet") == "not done yet"
    assert "Done" not in scrub_done_claims("4 imagesDone")


def test_user_cancel_is_skip():
    blocks = [{"type": "tool_use", "name": "generate_image", "input": {"prompt": "x"}},
              {"type": "tool_result", "name": "generate_image", "text": json.dumps({"cancelled": True})}]
    d = check("画 4 张猫", blocks).to_dict()
    assert d["self_check"] == "skip" and d["reason"] == "user_cancelled"
