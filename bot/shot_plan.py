"""#710 plan card for multi-shot portrait skills (angle rules #708).

Chinese plan lines are what the question card shows. English prompts keep the
same cut / angle° / focal / light strings so a generate_image call can be
traced back to its line. A single image never opens the card.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

# Display names (compose_provider_text) and the skill id.
PLAN_SKILLS = frozenset({
    "pose-fission",
    "电商同场景角色姿势裂变",
    "Same-Scene Pose Fission",
})
SKILL_ID = "pose-fission"
QUESTION = "是否生成这 {n} 张？"
REFUSE = (
    "Plan not confirmed. Do not call generate_image until the user picks "
    "A 开始生成 or skips the plan card."
)
_COUNT = re.compile(r"(\d+)\s*(?:张|幅|images?|photos?)", re.I)
# Bare framing words the card must not use as the shot description.
BARE = ("full body", "waist-up", "半身", "全身")

# Eight pairwise-distinct angles. Batches of 4 take a window; at most the
# one 0° entry is frontal eye-level, and its composition is off-center.
_POOL: list[dict] = [
    dict(cut="画面下边缘切在腰线/肚脐，头顶留白",
         angle="45° 四分之三侧，远侧眼可见", height="平视",
         pose="站立微侧身，手自然垂下", comp="主体在左三分线，右侧留白，不居中",
         focal="50mm f/2", light="45° 侧逆光 + 轮廓光，硬阴影", frontal=False),
    dict(cut="画面下边缘切在胸口/锁骨，腰部不入画",
         angle="90° 正侧面，看不到对侧眼睛", height="腰位低机位，略微仰拍",
         pose="站立，手臂自然下垂", comp="主体在右三分线，左侧留白，不居中",
         focal="85mm f/1.8", light="侧光从相机左侧，硬阴影", frontal=False),
    dict(cut="头顶留白，双脚完整入画，地面在脚下可见",
         angle="回头 90°，下巴越过肩线", height="略高",
         pose="回头看向镜头", comp="主体在左三分线，不居中",
         focal="35mm f/2.8", light="轮廓光从相机后方，软阴影", frontal=False),
    dict(cut="画面下边缘切在锁骨，胸口不入画",
         angle="0° 正面平视", height="平视",
         pose="站立，目光略偏向一侧", comp="主体在右三分线，不居中",
         focal="50mm f/2", light="顺光软光，从相机正面偏左", frontal=True),
    dict(cut="头顶留白，双脚完整入画",
         angle="180° 背对镜头，脸不入画", height="略高",
         pose="背对镜头站立", comp="主体在左三分线，右侧留白，不居中",
         focal="35mm f/2.8", light="逆光从相机后方，硬轮廓", frontal=False),
    dict(cut="画面下边缘切在腰线/肚脐，髋部不入画",
         angle="45° 四分之三侧朝右，远侧眼可见", height="腰位低机位，略微仰拍",
         pose="行走中微侧身", comp="主体在右三分线，左侧留白，不居中",
         focal="50mm f/2", light="侧逆光从相机右侧，硬阴影", frontal=False),
    dict(cut="画面下边缘切在胸口，腰部不入画",
         angle="90° 正侧面朝右，看不到对侧眼睛", height="平视",
         pose="坐姿微侧", comp="主体在左三分线，右侧留白，不居中",
         focal="85mm f/1.8", light="侧光从相机右侧，软阴影", frontal=False),
    dict(cut="画面下边缘切在锁骨下方，胸口以下不入画",
         angle="回头 90° 朝右，下巴越过肩线", height="略高",
         pose="拨发回头", comp="主体在右三分线，不居中",
         focal="85mm f/1.8", light="轮廓光从相机左后方，硬阴影", frontal=False),
]


@dataclass
class Shot:
    index: int
    cut: str
    angle: str
    height: str
    pose: str
    composition: str
    focal: str
    light: str
    scene: str
    grade: str = "Kodak Portra 400，细颗粒，真实皮肤"
    ratio: str = "3:4 单张"
    frontal: bool = False
    prompt_en: str = ""
    refs: list = field(default_factory=list)

    def zh(self) -> str:
        return (
            f"{self.index}. 景别：{self.cut}；角度：{self.angle}；机位：{self.height}；"
            f"姿态：{self.pose}；构图：{self.composition}；焦段：{self.focal}；"
            f"光：{self.light}；场景：{self.scene}；调色：{self.grade}；画幅：{self.ratio}"
        )


def is_plan_skill(name: str) -> bool:
    return (name or "").strip() in PLAN_SKILLS


def count_of(text: str) -> int:
    """User-named image count, else 4. Clamped so a batch stays inside the angle pool."""
    m = _COUNT.search(text or "")
    n = int(m.group(1)) if m else 4
    return max(1, min(len(_POOL), n))


def scene_of(text: str) -> str:
    raw = text or ""
    if "街景" in raw:
        return "同参考图街景，背景压暗"
    if "棚" in raw:
        return "同参考图棚拍，背景压暗"
    return "同参考图场景，背景压暗"


def _prompt(shot: Shot) -> str:
    # Chinese fragments stay in the English prompt so each call traces to its line.
    return (
        "Edit the reference photo. Single 3:4 photorealistic editorial fashion photograph, "
        "one frame only, not a collage, grid or contact sheet. "
        f"景别：{shot.cut}. 角度：{shot.angle}. 机位：{shot.height}. "
        f"姿态：{shot.pose}. 构图：{shot.composition}. 焦段：{shot.focal}. "
        f"光：{shot.light}. 场景：{shot.scene}. 调色：{shot.grade}. 画幅：{shot.ratio}."
    )


def build_shots(n: int, variant: int = 0, scene: str = "", note: str = "") -> list[Shot]:
    """N plan lines. Angles in one batch are pairwise distinct; ≤1 frontal 0° and that one is off-center."""
    n = max(1, min(len(_POOL), int(n)))
    start = (int(variant) * 4) % len(_POOL)
    scene_text = scene or "同参考图场景，背景压暗"
    if note:
        scene_text = f"{scene_text}；用户补充：{note}"
    shots: list[Shot] = []
    for i in range(n):
        src = _POOL[(start + i) % len(_POOL)]
        shot = Shot(
            index=i + 1, cut=src["cut"], angle=src["angle"], height=src["height"],
            pose=src["pose"], composition=src["comp"], focal=src["focal"], light=src["light"],
            scene=scene_text, frontal=bool(src["frontal"]),
        )
        shot.prompt_en = _prompt(shot)
        shots.append(shot)
    _check_pool(shots)
    return shots


def _check_pool(shots: list[Shot]) -> None:
    angles = [s.angle for s in shots]
    if len(angles) != len(set(angles)):
        raise RuntimeError("shot plan angles are not pairwise distinct")
    fronts = [s for s in shots if s.frontal or s.angle.startswith("0°")]
    if len(fronts) > 1:
        raise RuntimeError("shot plan has more than one 0° frontal")
    for s in fronts:
        if "三分" not in s.composition or "不居中" not in s.composition:
            raise RuntimeError("0° frontal plan is centered")
    for s in shots:
        line = s.zh()
        for bare in BARE:
            if bare in line:
                raise RuntimeError(f"shot plan uses bare framing {bare!r}")
        for token in ("景别：", "角度：", "机位：", "姿态：", "构图：", "焦段：", "光：", "场景：", "°", "mm", "三分", "不居中"):
            if token not in line:
                raise RuntimeError(f"shot plan missing {token}")


def question(n: int) -> str:
    return QUESTION.format(n=n)


def ask_spec(shots: list[Shot]) -> dict:
    prompt = "\n".join([s.zh() for s in shots] + [question(len(shots))])
    return {
        "prompt": prompt,
        "options": [
            {"id": "generate", "label": "开始生成"},
            {"id": "regenerate", "label": "换一组方案"},
        ],
        "min_selections": 1,
        "max_selections": 1,
        "allow_other": True,
        "allow_skip": True,
    }


def _flat(outcome: dict) -> tuple[list[str], str]:
    selected = [str(s) for s in (outcome.get("selected") or [])]
    other = str(outcome.get("other_text") or "")
    answers = outcome.get("answers") or {}
    if isinstance(answers, dict):
        for item in answers.values():
            if not isinstance(item, dict):
                continue
            if item.get("selected"):
                selected = [str(s) for s in item["selected"]]
            if item.get("other_text"):
                other = str(item["other_text"])
    return selected, other.strip()


def choice_of(outcome: dict) -> str:
    """A (start or skip), B (new plans only), C (free text)."""
    selected, other = _flat(outcome)
    if "regenerate" in selected:
        return "B"
    if other and "generate" not in selected:
        return "C"
    return "A"


def other_of(outcome: dict) -> str:
    return _flat(outcome)[1]


def bind_generate(run, args: dict, *, consume: bool) -> tuple[dict, str | None]:
    """Refuse generate_image before the plan is confirmed. After confirm, bind the next line's prompt."""
    if run is None or not getattr(run, "plan_gate_active", False):
        return args, None
    if not getattr(run, "shot_confirmed", False):
        return args, REFUSE
    shots = list(getattr(run, "shots", None) or [])
    cursor = int(getattr(run, "shot_cursor", 0) or 0)
    if cursor >= len(shots):
        return args, None
    shot = shots[cursor]
    if consume:
        run.shot_cursor = cursor + 1
    out = dict(args or {})
    out["prompt"] = shot.prompt_en
    out["skill"] = SKILL_ID
    if shot.refs:
        out["refs"] = list(shot.refs)
    return out, None


def trace_ok(prompt: str, shot: Shot) -> bool:
    text = prompt or ""
    return all(part in text for part in (shot.cut, shot.angle, shot.focal.split()[0], shot.light))


# Touched on every run so a single-image skill plans internally and must not raise.
internal_calls = 0


def touch_internal(n: int = 1, scene: str = "") -> list[Shot]:
    global internal_calls
    internal_calls += 1
    return build_shots(n, 0, scene or "同参考图场景，背景压暗")


def _refs_of(text: str) -> list[str]:
    return re.findall(r"shape:[^\s,\]\)\"']+", text or "")


async def _ask(chat_id: str, state, spec: dict, handle) -> dict:
    from ..api import bot_asks
    from ..api.mcp_tools.bot_tools import _await_ask
    task = asyncio.create_task(_await_ask(chat_id, state, spec, wait_forever=True))
    while not task.done():
        if handle.stop_requested:
            bot_asks.cancel_chat_asks(chat_id)
            break
        await asyncio.sleep(0.05)
    if not task.done():
        task.cancel()
        return {"status": "cancelled"}
    try:
        return task.result()
    except asyncio.CancelledError:
        return {"status": "cancelled"}


async def run_plan_card(ctx, turn, handle, messages: list) -> str | None:
    """Show the plan card when this run needs one. Returns 'stopped', else None.

    Single-image skills (and a plan skill asked for 1 image) only run the internal
    planner — no card, no error, generate_image stays ungated.
    """
    goal = turn.goal_text or ""
    user = turn.user_text or ""
    blob = goal or user
    # Every run plans at least one frame internally. A single image must not raise and must not open a card.
    touch_internal(1, scene_of(blob))
    skill = getattr(ctx, "current_skill", "") or ""
    if not is_plan_skill(skill):
        return None
    n = count_of(goal or user)
    if n <= 1 or (turn.run_mode or "") == "unattended":
        return None
    from ..api.bot_turns import ACTIVE_TURNS
    state = ACTIVE_TURNS.get(turn.chat_id)
    if state is None:
        return None  # scripted runs with no chat panel keep the old path
    ctx.plan_gate_active = True
    ctx.shot_confirmed = False
    ctx.shots = []
    ctx.shot_cursor = 0
    scene = scene_of(goal or user)
    refs = _refs_of(user)
    variant = 0
    note = ""
    while True:
        if handle.stop_requested:
            return "stopped"
        shots = build_shots(n, variant, scene, note)
        for s in shots:
            s.refs = refs
        outcome = await _ask(turn.chat_id, state, ask_spec(shots), handle)
        if handle.stop_requested or outcome.get("status") != "answered":
            return "stopped"
        kind = choice_of(outcome)
        if kind == "B":
            variant += 1
            note = ""
            continue
        if kind == "C":
            note = other_of(outcome)
            variant += 1
            continue
        ctx.shot_confirmed = True
        ctx.shots = shots
        ctx.shot_cursor = 0
        body = "\n".join(f"{s.index}. {s.prompt_en}" for s in shots)
        messages.append({
            "role": "user",
            "content": (
                "The user confirmed the shot plan (A 开始生成, or skip which means the same). "
                f"Call generate_image exactly {len(shots)} times now, one per line, "
                "with skill pose-fission. The server binds each call to that line's prompt. "
                "Do not ask again.\n" + body
            ),
        })
        return None
