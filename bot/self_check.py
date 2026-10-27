"""#383: post-run goal self-check. A run may only report "done" when the requested deliverables
were really generated, the count is right and they landed on the canvas. Otherwise the reply
must say what is missing and deliver what exists (never an empty / text-only "done")."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_EN_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a couple of": 2, "several": 3}
_KINDS = {
    "image": (r"张|幅|图|图片|图像|海报|插画|照片", r"images?|pictures?|photos?|posters?|illustrations?|renders?"),
    "video": (r"个视频|段视频|条视频|视频", r"videos?|clips?|animations?"),
    "text": (r"条文案|段文案|个文案|文案|标语", r"captions?|slogans?|copies|copy|headlines?"),
}
_GEN_VERB = re.compile(r"生成|画|做|出图|出一|出两|出几|制作|创作|设计|generate|create|make|draw|render|design|produce|写", re.I)
_DONE_CLAIM = re.compile(r"(已完成|全部完成|完成了|完成！|完成。|(?-i:Done)(?!(?-i:[a-z]))|\ball done\b|\bcompleted\b|\bfinished\b)", re.I)


@dataclass
class Goal:
    kind: str
    count: int


@dataclass
class SelfCheck:
    goal: Optional[Goal]
    generated: int = 0
    placed: int = 0
    failures: list = field(default_factory=list)
    placed_ids: list = field(default_factory=list)
    cancelled: bool = False      # the user declined the paid confirm: nothing to check against
    canvas_checked: bool = False  # placed shapes were verified against a live get_canvas read

    @property
    def applies(self) -> bool:
        return self.goal is not None and not self.cancelled

    @property
    def passed(self) -> bool:
        if not self.goal:
            return True
        return self.generated >= self.goal.count and self.placed >= self.goal.count

    @property
    def missing(self) -> int:
        if not self.goal:
            return 0
        return max(0, self.goal.count - min(self.generated, self.placed))

    def to_dict(self) -> dict:
        if not self.goal:
            return {"self_check": "skip"}
        if self.cancelled:
            return {"self_check": "skip", "reason": "user_cancelled"}
        return {"self_check": "pass" if self.passed else "fail", "kind": self.goal.kind,
                "expected": self.goal.count, "generated": self.generated, "placed": self.placed,
                "missing": self.missing, "placed_ids": list(self.placed_ids)}


def _num(tok: str) -> int:
    tok = tok.strip().lower()
    if tok.isdigit():
        return int(tok)
    if tok in _EN_NUM:
        return _EN_NUM[tok]
    if tok in _CN_NUM:
        return _CN_NUM[tok]
    if len(tok) == 2 and tok[0] == "十" and tok[1] in _CN_NUM:
        return 10 + _CN_NUM[tok[1]]
    return 0


def parse_goal(text: str) -> Optional[Goal]:
    """Deliverable kind + count from the user's request. None for chat / Q&A (no check)."""
    t = text or ""
    if not _GEN_VERB.search(t):
        return None
    for kind, (zh, en) in _KINDS.items():
        m = re.search(rf"(\d+|[一两二三四五六七八九十]{{1,2}})\s*(?:张|幅|个|段|条|组)?\s*(?:{zh})", t)
        if m and _num(m.group(1)):
            return Goal(kind, _num(m.group(1)))
        m = re.search(rf"\b(\d+|a couple of|an?|one|two|three|four|five|six|seven|eight|nine|ten|several)\s+"
                      rf"(?:[\w-]+\s+){{0,3}}?(?:{en})\b", t, re.I)
        if m and _num(m.group(1)):
            return Goal(kind, _num(m.group(1)))
    for kind in ("video", "image"):  # "让选中的图动起来做成视频": the deliverable is the video
        zh, en = _KINDS[kind]
        if re.search(zh, t) or re.search(rf"\b(?:{en})\b", t, re.I):
            return Goal(kind, 1)
    return None


def check(goal_text: str, blocks: list[dict], canvas_ids: Optional[set] = None) -> SelfCheck:
    """Count successful generations and shapes placed on the canvas (from tool results). When
    `canvas_ids` is given, a placed shape must also still exist on the canvas."""
    from .local_llm import _json_obj, _shape_ids, _tool_base, turn_result_from_blocks
    goal = parse_goal(goal_text)
    sc = SelfCheck(goal)
    if not goal:
        return sc
    generated = 0
    text_out = 0
    for b in blocks or []:
        if not isinstance(b, dict) or b.get("type") != "tool_result":
            continue
        name = _tool_base(str(b.get("name") or ""))
        data = _json_obj(str(b.get("text") or ""))
        if isinstance(data, dict) and name != "wait_generation" and \
                (data.get("cancelled") is True or data.get("status") == "declined"):
            sc.cancelled = True
        if b.get("status") in ("error", "cancelled"):
            continue
        if not isinstance(data, dict):
            continue
        if name == "wait_generation":
            for r in data.get("results") or []:
                if isinstance(r, dict) and not r.get("error") and not r.get("cancelled") and \
                        r.get("status") not in ("error", "declined", "cancelled", "running"):
                    generated += max(1, len(_shape_ids(r.get("shapes"))))  # one job may hold N outputs
        elif name == "add_text" and goal.kind == "text" and data.get("id"):
            text_out += 1
    rec = turn_result_from_blocks(blocks) or {"shapes": [], "failures": []}
    want = {"image": {"image"}, "video": {"video"}, "text": {"text"}}[goal.kind]
    ids = [s["id"] for s in rec["shapes"] if s.get("type") in want]
    if canvas_ids is not None:
        ids = [i for i in ids if i in canvas_ids]
        sc.canvas_checked = True
    sc.placed_ids = ids
    sc.placed = len(ids)
    sc.generated = text_out if goal.kind == "text" else generated
    sc.failures = rec["failures"]
    return sc


_MISSING_TEXT = {
    "zh": "目标核对未通过：要 {exp} {unit}{kind}，已生成 {gen} {unit}，画布上 {placed} {unit}，缺 {miss} {unit}。已生成的部分保留在画布上。",
    "en": "Goal check failed: {exp} {kind} requested, {gen} generated, {placed} on the canvas, {miss} missing. "
          "What was generated is kept on the canvas.",
}
_KIND_LABEL = {"zh": {"image": "图", "video": "视频", "text": "文案"},
               "en": {"image": "image(s)", "video": "video(s)", "text": "text item(s)"}}
_FAIL_TEXT = {"zh": "失败原因：{r}", "en": "Failure reason: {r}"}


def missing_note(sc: SelfCheck, lang: str) -> str:
    lk = "zh" if lang == "zh" else "en"
    assert sc.goal
    unit = {"image": "张", "video": "段", "text": "条"}[sc.goal.kind]
    text = _MISSING_TEXT[lk].format(exp=sc.goal.count, kind=_KIND_LABEL[lk][sc.goal.kind], unit=unit,
                                    gen=sc.generated, placed=sc.placed, miss=sc.missing)
    if sc.failures:
        text += " " + _FAIL_TEXT[lk].format(r="; ".join(str(f.get("reason") or "") for f in sc.failures[:3]))
    return text


_STEP_LIST = (("已完成：", "已做步骤："), ("Done so far:", "Steps taken:"))


def scrub_done_claims(text: str) -> str:
    """Remove '完成 / Done' claims from a reply whose goal check failed (no 完成 / Done may remain)."""
    for a, b in _STEP_LIST:
        text = text.replace(a, b)
    text = _DONE_CLAIM.sub(lambda m: "尚未全部交付" if re.search(r"[\u4e00-\u9fff]", m.group(0))
                           else "not fully delivered", text)
    # truthful negations ("仍未完成" / "not done") stay; any other 完成 is a claim
    return re.sub(r"(?<![未没])完成", "交付", text)


def apply_to_blocks(goal_text: str, blocks: list[dict], lang: str,
                    canvas_ids: Optional[set] = None, *, note: bool = True) -> tuple[list[dict], dict]:
    """Turn-level gate (all providers): on fail, rewrite done-claims and append the missing note
    (note=False when the turn error already carries it)."""
    sc = check(goal_text, blocks, canvas_ids)
    if not sc.applies or sc.passed:
        return blocks, sc.to_dict()
    out = [({**b, "text": scrub_done_claims(str(b.get("text") or ""))} if b.get("type") == "text" else b)
           for b in blocks]
    if note:
        out.append({"type": "notice", "level": "warn", "text": missing_note(sc, lang),
                    "self_check": sc.to_dict()})
    return out, sc.to_dict()
