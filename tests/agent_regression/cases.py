"""#231: the tester's 15 tasks (+ the 80-step limit), each recorded for the zh and the en UI.
Each case is a scripted mock-LLM tool sequence plus what must come out of it."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from harness import Shape, Step

IMG = "shape:img1"
P1A = "P1-a #232"  # expectation flips when the LLM retry (P1-a) lands


def ids(last: dict) -> dict:
    return {"ids": last.get("ids") or []}


def done(zh: str, en: str) -> Step:
    return Step(reply={"zh": zh, "en": en})


@dataclass
class Case:
    id: str
    title: str
    turns: list[dict]                       # [{"zh": text, "en": text}] one per user turn
    script: list[Step]
    tools: list[str]                        # expected tool-call order (all turns)
    paid: int                               # expected mock WaveSpeed submits
    shapes: dict[str, int]                  # expected shape count by type at the end
    limit: int = 12                         # step limit for this task
    shapes_initial: list[Shape] = field(default_factory=list)
    selection: list[str] = field(default_factory=list)
    brand_kit: Optional[dict] = None
    decline: bool = False
    no_key: bool = False
    status: str = "done"                    # last turn status
    error: Optional[dict] = None            # expected notice text prefix per lang
    reply: Optional[dict] = None            # substring the final reply must contain per lang
    llm_requests: Optional[int] = None
    xfail: str = ""                         # known gap: expected to change (reason)
    baseline_for: str = ""                  # current behaviour recorded; flips in that PR
    note: str = ""                          # free-form note shown in the report
    extra: Optional[str] = None             # name of an extra check in the test module


def _img(**kw):
    return Shape(id=IMG, type="image", **kw)


BRAND = {"name": "Aurora", "fonts": [{"role": "heading", "family": "Inter"}],
         "colors": [{"role": "primary", "hex": "#FF5A1F"}, {"role": "background", "hex": "#1B1B3A"}]}


def _gen_then_reply(tool, args, zh, en):
    return [Step(calls=[(tool, args)]), Step(calls=[("wait_generation", ids)]), done(zh, en)]


def faults(kind):
    """LLM fault after one paid image: today the turn ends with the HTTP/timeout error at once (no retry)."""
    return Case(
        id=f"15-{kind}", title=f"fault injection: LLM {kind}",
        turns=[{"zh": "画一只猫", "en": "Draw a cat"}],
        script=[Step(calls=[("generate_image", {"prompt": "a cat"})]), Step(fault=kind),
                done("已完成", "Done")],
        tools=["generate_image"], paid=1, shapes={"image": 1}, status="error",
        error={"zh": "TimeoutError" if kind == "timeout" else f"HTTP {kind}",
               "en": "TimeoutError" if kind == "timeout" else f"HTTP {kind}"},
        llm_requests=2, baseline_for=P1A)


def faults_retry(kind):
    """What P1-a must do: retry the LLM call twice, then carry on; the paid tool is never re-run."""
    return Case(
        id=f"15-{kind}-retry", title=f"fault injection: LLM {kind} retried x2 (P1-a)",
        turns=[{"zh": "画一只猫", "en": "Draw a cat"}],
        script=[Step(calls=[("generate_image", {"prompt": "a cat"})]), Step(fault=kind), Step(fault=kind),
                Step(calls=[("wait_generation", ids)]), done("已完成", "Done")],
        tools=["generate_image", "wait_generation"], paid=1, shapes={"image": 1},
        llm_requests=5, xfail=P1A)


CASES: list[Case] = [
    Case("01", "t2i 1 image with size + style",
         [{"zh": "画一张水彩风格的猫，3:4 竖版", "en": "Draw a watercolor cat, 3:4 portrait"}],
         _gen_then_reply("generate_image", {"prompt": "a cat, watercolor style", "ratio": "3:4"}, "画好了", "Done"),
         ["generate_image", "wait_generation"], 1, {"image": 1}, extra="ratio"),
    Case("02", "t2i exactly 4 images",
         [{"zh": "画 4 张柯基插画", "en": "Draw 4 corgi illustrations"}],
         _gen_then_reply("generate_image", {"prompt": "corgi illustration", "count": 4}, "4 张画好了", "4 done"),
         ["generate_image", "wait_generation"], 4, {"image": 4}),
    Case("03", "selected image: change background to beach (image edit)",
         [{"zh": "把背景换成海边", "en": "Change the background to a beach"}],
         [Step(calls=[("get_canvas", {})]), *_gen_then_reply(
             "edit_image", lambda last: {"id": last["selection"][0], "prompt": "replace the background with a beach"},
             "背景换好了", "Background changed")],
         ["get_canvas", "edit_image", "wait_generation"], 1, {"image": 2},
         shapes_initial=[_img()], selection=[IMG], extra="edit_target"),
    Case("04", "t2v 5s",
         [{"zh": "生成一段 5 秒的海浪视频", "en": "Make a 5 second video of ocean waves"}],
         _gen_then_reply("generate_video", {"prompt": "ocean waves", "duration": 5}, "视频好了", "Video ready"),
         ["generate_video", "wait_generation"], 1, {"video": 1}, extra="t2v"),
    Case("05", "i2v from the selected image",
         [{"zh": "让选中的图动起来，做成视频", "en": "Turn the selected image into a video"}],
         [Step(calls=[("get_canvas", {})]), *_gen_then_reply(
             "generate_video", lambda last: {"prompt": "gentle camera push-in", "first_frame": last["selection"][0]},
             "视频好了", "Video ready")],
         ["get_canvas", "generate_video", "wait_generation"], 1, {"image": 1, "video": 1},
         shapes_initial=[_img()], selection=[IMG], extra="i2v"),
    Case("06", "15s upbeat music",
         [{"zh": "生成一段 15 秒的轻快音乐", "en": "Make 15 seconds of upbeat music"}],
         _gen_then_reply("generate_music", {"prompt": "upbeat cheerful pop instrumental", "duration": 15},
                         "音乐好了", "Music ready"),
         ["generate_music", "wait_generation"], 1, {"audio": 1}, extra="music"),
    Case("07", "SFX + voiceover as audio cards",
         [{"zh": "做一个开门音效，再配一句「欢迎光临」", "en": "Make a door-opening sound effect and a voiceover saying 'Welcome'"}],
         [Step(calls=[("generate_sound_effect", {"prompt": "door opening", "duration": 3})]),
          Step(calls=[("text_to_speech", {"text": "欢迎光临 / Welcome"})]),
          Step(calls=[("wait_generation", lambda last: {"ids": ["job:1", "job:2"]})]), done("音频好了", "Audio ready")],
         ["generate_sound_effect", "text_to_speech", "wait_generation"], 2, {"audio": 2}),
    Case("08", "edit elements, then title -> SALE",
         [{"zh": "把这张图拆成可编辑元素，标题改成「SALE」", "en": "Split this image into editable elements and change the title to 'SALE'"}],
         [Step(calls=[("edit_elements", {"id": IMG})]), Step(calls=[("wait_generation", ids)]),
          Step(calls=[("update_shapes", lambda last: {"updates": [{"id": last["results"][0]["shapes"][1], "text": "SALE"}]})]),
          done("标题已改成 SALE", "Title changed to SALE")],
         ["edit_elements", "wait_generation", "update_shapes"], 1, {"image": 2, "frame": 1, "text": 2},
         shapes_initial=[_img()], selection=[IMG], extra="sale"),
    Case("09", "single image to 3D",
         [{"zh": "把这张图转成 3D 模型", "en": "Turn this image into a 3D model"}],
         _gen_then_reply("image_to_3d", {"id": IMG}, "3D 模型好了", "3D model ready"),
         ["image_to_3d", "wait_generation"], 1, {"image": 1, "model3d": 1}, shapes_initial=[_img()], selection=[IMG]),
    Case("10", "poster with brand kit font + colors",
         [{"zh": "用品牌套件做一张促销海报", "en": "Make a promo poster with my brand kit"}],
         [Step(calls=[("brand_kits", {})]),
          Step(calls=[("generate_image", lambda last: {"prompt": "promo poster, colors " + ", ".join(c["hex"] for c in last["kits"][0]["colors"]), "ratio": "3:4"})]),
          Step(calls=[("wait_generation", ids)]),
          Step(calls=[("add_text", {"text": "BIG SALE", "font": "Inter", "color": "#FF5A1F", "font_size": 96})]),
          done("海报做好了", "Poster done")],
         ["brand_kits", "generate_image", "wait_generation", "add_text"], 1, {"image": 1, "text": 1},
         brand_kit=BRAND, extra="brand"),
    Case("11", "multi-turn 'brighter': 1 new image edited from the untouched original",
         [{"zh": "画一张咖啡店海报", "en": "Make a coffee shop poster"}, {"zh": "再亮一点", "en": "Make it brighter"}],
         [*_gen_then_reply("generate_image", {"prompt": "coffee shop poster"}, "海报好了", "Poster ready"),
          Step(calls=[("get_canvas", {})]),
          *_gen_then_reply("edit_image", lambda last: {"id": [s["id"] for s in last["shapes"] if s["type"] == "image"][0],
                                                      "prompt": "make it brighter"}, "调亮了", "Brighter now")],
         ["generate_image", "wait_generation", "get_canvas", "edit_image", "wait_generation"], 2, {"image": 2},
         extra="edit_original"),  # product ruling: 1 new edited image beside an untouched original
    Case("12", "PPTX deck, editable mode",
         [{"zh": "做一个 3 页的产品介绍 PPT，文字要可编辑", "en": "Make a 3-slide product deck with editable text"}],
         [Step(calls=[("create_slides", {"title": "Product", "slides": [
             {"title": "Intro", "bullets": ["What it is"]}, {"title": "Features", "bullets": ["Fast", "Simple"], "image": "product photo"},
             {"title": "Pricing", "bullets": ["$9/mo"]}]})]), Step(calls=[("wait_generation", ids)]),
          done("PPT 做好了，导出时选「可编辑文字」", "Deck ready; export with editable text")],
         ["create_slides", "wait_generation"], 1, {"frame": 3, "text": 7, "image": 1}, extra="slides"),
    Case("13", "over threshold -> Cancel: no charge, no retry",
         [{"zh": "画一张猫", "en": "Draw a cat"}],
         [Step(calls=[("generate_image", {"prompt": "a cat"})]),
          Step(calls=[("generate_image", {"prompt": "a cat, retry"})]),  # the model tries again: the guard refuses
          done("已取消该生成，未扣费。要怎么调整？", "Cancelled this generation; nothing was charged. How should I adjust?")],
         ["generate_image", "generate_image"], 0, {}, decline=True,
         note="refused retry step shows success: to fix in #232",
         reply={"zh": "已取消", "en": "Cancelled"}, extra="cancel"),
    Case("14", "no key: immediate message, no model call",
         [{"zh": "画一张猫", "en": "Draw a cat"}], [], [], 0, {}, no_key=True, status="error",
         error={"zh": "还没有设置 WaveSpeed Key", "en": "No WaveSpeed key yet"}, llm_requests=0),
    faults("timeout"), faults("429"), faults("500"),
    faults_retry("timeout"), faults_retry("429"), faults_retry("500"),
    Case("15-steps80", "80-step limit",
         [{"zh": "检查所有页面", "en": "Check every page"}],
         [Step(calls=[("get_canvas", {"page": f"p{i}"})]) for i in range(81)],
         ["get_canvas"] * 80, 0, {}, limit=80, status="error",
         error={"zh": "too many tool-call iterations", "en": "too many tool-call iterations"}, llm_requests=80),
]
