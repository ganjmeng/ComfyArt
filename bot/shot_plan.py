"""#710 plan card for multi-shot portrait skills (angle rules #708, #707 gold light/pose).

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
# #971: the plan card is a real question (questions[]) so the Full App QuestionCard's
# answers[] payload validates; one stable id keeps the stored answer readable.
QUESTION_ID = "plan"
QUESTION = "是否生成这 {n} 张？"
REFUSE = (
    "Plan not confirmed. Do not call generate_image until the user picks "
    "A 开始生成 or skips the plan card."
)
_COUNT = re.compile(r"(\d+)\s*(?:张|幅|images?|photos?)", re.I)
# Bare framing words the card must not use as the shot description.
BARE = ("full body", "waist-up", "半身", "全身")

# Eight pairwise-distinct poses/angles. Batches of 4 take a window.
# Default window (0-3) follows the gold family: look-back, side profile,
# head-down, and one near-frontal full-length standing frame that may be
# relatively centered. All lights stay hard and dappled, never soft fill.
HARD_LIGHT = "沿用参考硬侧逆光，斑驳树影落在脸和衣服上"
SCENE_STREET = "同参考图街景，街道和建筑完整可读，背景保持明亮可读"
SCENE_STUDIO = "同参考图棚拍，场景完整可读，背景保持明亮可读"
SCENE_DEFAULT = "同参考图场景，街道和建筑完整可读，背景保持明亮可读"

_POOL: list[dict] = [
    dict(cut="头顶留白，双脚完整入画，地面在脚下可见",
         angle="回头 90°，下巴越过肩线", height="平视",
         pose="过街行走，头转向肩后看向镜头", comp="主体在左三分线，右侧留白",
         focal="35mm f/2.8", light=HARD_LIGHT, frontal=False),
    dict(cut="头顶留白，双脚完整入画，地面在脚下可见",
         angle="90° 正侧面，看不到对侧眼睛", height="平视",
         pose="倚柱侧脸，双手自然", comp="主体在右三分线，左侧留白",
         focal="35mm f/2.8", light=HARD_LIGHT, frontal=False),
    dict(cut="画面下边缘切在腰线/肚脐，髋部不入画",
         angle="低头约 30°，下颌内收，目光向下", height="略高",
         pose="低头，下颌内收", comp="主体在左三分线，右侧留白",
         focal="50mm f/2", light=HARD_LIGHT, frontal=False),
    dict(cut="头顶留白，双脚完整入画，地面在脚下可见",
         angle="0° 正面平视", height="平视",
         pose="近正面站立，一手插袋", comp="相对居中的站姿，允许居中",
         focal="35mm f/2.8", light=HARD_LIGHT, frontal=True),
    dict(cut="头顶留白，双脚完整入画",
         angle="180° 背对镜头，脸不入画", height="略高",
         pose="背对镜头站立", comp="主体在左三分线，右侧留白",
         focal="35mm f/2.8", light=HARD_LIGHT, frontal=False),
    dict(cut="画面下边缘切在腰线/肚脐，髋部不入画",
         angle="45° 四分之三侧朝右，远侧眼可见", height="腰位低机位，略微仰拍",
         pose="行走中微侧身", comp="主体在右三分线，左侧留白",
         focal="50mm f/2", light=HARD_LIGHT, frontal=False),
    dict(cut="画面下边缘切在胸口，腰部不入画",
         angle="90° 正侧面朝右，看不到对侧眼睛", height="平视",
         pose="倚柱微侧", comp="主体在左三分线，右侧留白",
         focal="85mm f/1.8", light=HARD_LIGHT, frontal=False),
    dict(cut="画面下边缘切在锁骨下方，胸口以下不入画",
         angle="回头 90° 朝右，下巴越过肩线", height="略高",
         pose="拨发回头", comp="主体在右三分线，左侧留白",
         focal="85mm f/1.8", light=HARD_LIGHT, frontal=False),
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
        return SCENE_STREET
    if "棚" in raw:
        return SCENE_STUDIO
    return SCENE_DEFAULT


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
    """N plan lines. Poses/angles in one batch are pairwise distinct; ≤1 frontal 0°, which may be relatively centered."""
    n = max(1, min(len(_POOL), int(n)))
    start = (int(variant) * 4) % len(_POOL)
    scene_text = scene or SCENE_DEFAULT
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
    # A near-frontal full-length standing frame may be relatively centered (gold ex-01).
    for s in shots:
        line = s.zh()
        for bare in BARE:
            if bare in line:
                raise RuntimeError(f"shot plan uses bare framing {bare!r}")
        for token in ("景别：", "角度：", "机位：", "姿态：", "构图：", "焦段：", "光：", "场景：", "°", "mm"):
            if token not in line:
                raise RuntimeError(f"shot plan missing {token}")
        if "软阴影" in s.light or "顺光软光" in s.light:
            raise RuntimeError("shot plan light is soft, gold uses hard dappled light")
        if "压暗" in s.scene:
            raise RuntimeError("shot plan darkens the background, gold street must stay readable")


def question(n: int) -> str:
    return QUESTION.format(n=n)


def ask_spec(shots: list[Shot]) -> dict:
    """The #710 plan card, as a real question spec (questions[]), never legacy prompt+options.

    #971: the Full App QuestionCard always posts answers[], while bot_asks.validate_answer
    refuses answers for a spec without questions[] (422 "answers require questions[] in the
    spec"). The plan card is a question like any other, so it is normalized at the source and
    then goes through bot_asks.validate_spec (run_plan_card's _ask) exactly like ask_user.
    """
    prompt = "\n".join([s.zh() for s in shots] + [question(len(shots))])
    return {
        "questions": [{
            "id": QUESTION_ID,
            "prompt": prompt,
            "options": [
                {"id": "generate", "label": "开始生成"},
                {"id": "regenerate", "label": "换一组方案"},
            ],
            "min_selections": 1,
            "max_selections": 1,
            "allow_other": True,
            "page": 1,
        }],
        "page_count": 1,
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
    """A (start), B (new plans only), C (free text), S (explicit skip: no answer at all).

    #971: an empty answer is a skip, never a silent A — the caller branches on S and records
    it as a skip (the current plan still runs, the transcript says the user skipped the card).
    """
    selected, other = _flat(outcome)
    if "regenerate" in selected:
        return "B"
    if other and "generate" not in selected:
        return "C"
    if "generate" in selected:
        return "A"
    return "S"


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
    return build_shots(n, 0, scene or SCENE_DEFAULT)


def _refs_of(text: str) -> list[str]:
    return re.findall(r"shape:[^\s,\]\)\"']+", text or "")


async def _ask(chat_id: str, state, spec: dict, handle) -> dict:
    from ..api import bot_asks
    from ..api.mcp_tools.bot_tools import _await_ask
    # #971: run_plan_card used to hand its spec straight to create_ask, so a legacy
    # prompt+options spec skipped validation and every Full App Submit got a 422. The plan
    # card now goes through the same validate_spec as ask_user: the stored spec always has
    # questions[] (and ask_spec itself already emits that shape).
    spec = bot_asks.validate_spec(spec)
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
    ctx.plan_skipped = False
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
        # kind is "A" (开始生成) or "S" (skip). A skip is never recorded as an A answer: the
        # ask keeps its empty answers (the UI shows a skip bubble), the run notes the skip and
        # the model is told the user did not pick an option — the shown plan still runs.
        ctx.shot_confirmed = True
        ctx.plan_skipped = kind == "S"
        ctx.shots = shots
        ctx.shot_cursor = 0
        body = "\n".join(f"{s.index}. {s.prompt_en}" for s in shots)
        if ctx.plan_skipped:
            lead = (
                "The user skipped the shot plan card without picking any option (not A 开始生成, "
                "not B 换一组方案, not C other). The plan below is what they were shown and it "
                f"stays as is. Call generate_image exactly {len(shots)} times now, one per line, "
            )
        else:
            lead = (
                "The user confirmed the shot plan (A 开始生成). "
                f"Call generate_image exactly {len(shots)} times now, one per line, "
            )
        messages.append({
            "role": "user",
            "content": (
                lead
                + "with skill pose-fission. The server binds each call to that line's prompt. "
                "Do not ask again.\n" + body
            ),
        })
        return None
