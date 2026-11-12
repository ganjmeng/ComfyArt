#!/usr/bin/env python3
"""Official-route $0 chat-turn capture for #911 studio-model (PR #914).

Set CAPTURE_REPO / CAPTURE_OUT. generate_image is stubbed; no WaveSpeed predict.
Card 1 is auto-answered female/color/asian to match the Lovart same-input (Lovart selling point was 「皇家蓝高饱和纯色」; pick our live colour option by label). studio_direction picks option C (light beige, side-on, hand on hem); if live options differ, pick the closest warm/light beige + side-on and record all labels.

Official DeepSeek path; WAVESPEED_API_KEY is not loaded into this process.
The garment reference from review-assets 87857c35 is attached.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
import types
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(os.environ.get("CAPTURE_REPO", "/tmp/gate911-studio/ComfyArt"))
OUT = Path(os.environ.get("CAPTURE_OUT", "/workspace/911-studio-capture/out"))
SECRETS = Path("/home/box/.secrets/comfyart-test.env")
TZ = ZoneInfo("Asia/Shanghai")

# PR #920 $0 routing capture. TURN env selects clothing-swap or studio-model.
MSG_PATH = Path("/workspace/911-studio-capture/input/msg.txt")
EXPECTED_MSG_MD5 = "a3370c695be7bdf88d42357fb4488394"
CS_IN = Path("/workspace/911-clothing-capture/main-d3f5ca4b/input")
ST_GARMENT = Path("/workspace/911-studio-capture/input/garment-input.png")
EXPECTED_SHA = {
    str(CS_IN / "person-input.png"): "008150f530fce6a6d2d7f956d93afae2b4d1c190150b734a43379f20a1cd1dc4",
    str(CS_IN / "garment-input.png"): "fc5b929f447fd698f7496913d63a37ce614589888d50186fd3d410bfcc181165",
    str(ST_GARMENT): "fc5b929f447fd698f7496913d63a37ce614589888d50186fd3d410bfcc181165",
}
ALL_TURNS = {
    "clothing-swap": {
        "id": "clothing-swap", "skill": "clothing-swap", "text": "", "lang": "zh", "locale": "zh",
        "refs": [
            {"path": CS_IN / "person-input.png", "filename": "person-input.png", "shape_id": "shape:clothing-swap-person", "width": 1776, "height": 2368},
            {"path": CS_IN / "garment-input.png", "filename": "garment-input.png", "shape_id": "shape:clothing-swap-garment", "width": 960, "height": 970},
        ],
        # exact labels only (brief); no semantic pick
        "targets": {"整体换成图2的蓝色T恤"},
    },
    "studio-model": {
        "id": "studio-model", "skill": "studio-model",
        "text": MSG_PATH.read_text(encoding="utf-8").replace("\r\n", "\n").removesuffix("\n"),
        "lang": "zh", "locale": "zh",
        "refs": [
            {"path": ST_GARMENT, "filename": "garment-input.png", "shape_id": "shape:studio-model-garment", "width": 512, "height": 512},
        ],
        # chosen labels of PASS pred 9ff4f680 (main-dbed74e1-optC-color ask-user-specs.json)
        "targets": {"女模特", "宝蓝色纯色衣身与整体版型", "亚洲人", "浅米色背景 + 侧身三分之四角度半身，一手轻拉衣摆"},
    },
}
TURN_ID = os.environ["TURN"]
TURNS = [ALL_TURNS[TURN_ID]]
USER_TEXT = TURNS[0]["text"]
STOP = {"stopped": False, "card": None, "parked": False}
PARK_S = float(os.environ.get("PARK_S", "5400"))
CARDS: list[dict] = []


class StopAtCard(Exception):
    pass


BLOCKED_PREDICT: list[dict] = []
COMMAND_LOG: list[dict] = []
GEN_CAPTURES: dict[str, list[dict]] = {TURN_ID: []}
CURRENT_TURN = {"id": ""}
IMAGE_PART_LOG: list[dict] = []
ASK_LOG: list[dict] = []


def now_iso() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


ALLOWED_ENV = {"DEEPSEEK_API_KEY"}
BLOCKED_ENV = {"WAVESPEED_API_KEY", "KIE_API_KEY", "REPLICATE_API_TOKEN"}
BALANCE_HELPER = Path("/workspace/911-studio-capture/read_ws_balance.py")


def current_tip() -> str:
    import subprocess
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


TIP = current_tip()
HTTP_HOSTS: list[dict] = []
CONFIRM_LOG: list[dict] = []


def load_env(path: Path) -> list[str]:
    """Load only DEEPSEEK_API_KEY. Never put WaveSpeed / Kie / Replicate keys in this process."""
    for blocked in BLOCKED_ENV:
        os.environ.pop(blocked, None)
    loaded = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key in BLOCKED_ENV:
            continue
        if key in ALLOWED_ENV and key and key not in os.environ:
            os.environ[key] = val
            loaded.append(key)
    for blocked in BLOCKED_ENV:
        os.environ.pop(blocked, None)
    return loaded


def wavespeed_balance() -> float:
    """Read balance in a child process that alone holds WAVESPEED_API_KEY."""
    import subprocess
    r = subprocess.run(
        [sys.executable, str(BALANCE_HELPER)],
        check=True,
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k not in BLOCKED_ENV},
    )
    return float(r.stdout.strip())


def _unescape_ts_string(s: str) -> str:
    return (
        s.replace("\\", "\0")
        .replace("\0n", "\n")
        .replace("\0'", "'")
        .replace("\0t", "\t")
        .replace("\0", "\\")
    )


def _portrait_shots_708(text: str) -> str:
    m = re.search(
        r"const PORTRAIT_SHOTS_708 = ((?:'(?:\\.|[^'\\])*'(?:\s*\+\s*)?)+)",
        text,
    )
    if not m:
        return ""
    parts = re.findall(r"'((?:\\.|[^'\\])*)'", m.group(1))
    return "".join(_unescape_ts_string(p) for p in parts)


def parse_skills(skills_ts: Path, locales: dict[str, dict]) -> dict:
    text = skills_ts.read_text(encoding="utf-8")
    out_m = re.search(r"export const SKILL_OUTPUT: Record<string, \{[^}]+\}> = \{([^}]+)\}", text)
    output = {}
    if out_m:
        for mid, w, h, rest in re.findall(
            r"'([^']+)': \{ width: (\d+), height: (\d+)([^}]*)\}", out_m.group(1)
        ):
            rec = {"width": int(w), "height": int(h), "images": 1}
            rm = re.search(r"ratio: '([^']+)'", rest)
            im = re.search(r"images: (\d+)", rest)
            if im:
                rec["images"] = int(im.group(1))
            if rm:
                rec["ratio"] = rm.group(1)
            output[mid] = rec

    portrait_708 = _portrait_shots_708(text)
    skills = {}
    for m in re.finditer(
        r"\{ id: '([^']+)', name: t\('([^']+)'\), instructions: '((?:\\.|[^'\\])*)'",
        text,
    ):
        sid, tkey, instr = m.group(1), m.group(2), m.group(3)
        instr = _unescape_ts_string(instr)
        rest = text[m.end():]
        appends_708 = bool(re.match(r"\s*\+\s*PORTRAIT_SHOTS_708", rest))
        if portrait_708 and appends_708:
            instr = instr + portrait_708
        skills[sid] = {
            "id": sid,
            "tkey": tkey,
            "instructions": instr,
            "output": output.get(sid),
            "appends_portrait_shots_708": appends_708,
        }
    return skills
def skill_name(skill: dict, locale: str, locales: dict) -> str:
    table = locales.get(locale) or locales.get("en") or {}
    return table.get(skill["tkey"]) or skill["id"]


def _install_stubs(base: Path) -> None:
    state = {"base": str(base)}

    def _annotated_filepath(name: str) -> str:
        kind = "input"
        for t in ("input", "output", "temp"):
            if name.endswith(f" [{t}]"):
                name, kind = name[: -len(t) - 3], t
        return str(base / kind / name)

    def _save_image_path(prefix: str, root: str):
        subfolder, _, name = prefix.rpartition("/")
        folder = os.path.join(root, subfolder)
        os.makedirs(folder, exist_ok=True)
        return folder, name, 1, subfolder, prefix

    def user_dir() -> str:
        return str(base / "user")

    def _make_module(name: str, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

    _make_module(
        "folder_paths",
        STATE=state,
        SYSTEM_USER_PREFIX="__",
        get_user_directory=user_dir,
        get_system_user_directory=lambda name="system": os.path.join(user_dir(), f"__{name}"),
        get_public_user_directory=lambda user: None if user.startswith("__") else os.path.join(user_dir(), user),
        get_input_directory=lambda: str(base / "input"),
        get_output_directory=lambda: str(base / "output"),
        get_temp_directory=lambda: str(base / "temp"),
        get_annotated_filepath=_annotated_filepath,
        get_save_image_path=_save_image_path,
        get_directory_by_type=lambda t: str(base / t) if t in ("input", "output", "temp") else None,
        get_filename_list=lambda kind: [],
        get_full_path_or_raise=lambda kind, name: name,
    )
    comfy = _make_module("comfy")
    comfy.ops = _make_module("comfy.ops", manual_cast=object)
    comfy.sd = _make_module("comfy.sd", load_diffusion_model=lambda *a, **k: None)
    comfy.utils = _make_module("comfy.utils", ProgressBar=lambda total: types.SimpleNamespace(update=lambda n: None))
    comfy.model_management = _make_module("comfy.model_management", throw_exception_if_processing_interrupted=lambda: None)
    comfy.cli_args = _make_module("comfy.cli_args", args=types.SimpleNamespace(tls_keyfile=None, tls_certfile=None))

    from aiohttp import web

    class _UserManager:
        users = {"default", "alice"}

        def get_request_user_id(self, request):
            user = request.headers.get("comfy-user", "default")
            if user not in self.users:
                raise KeyError("Unknown user: " + user)
            return user

        def get_request_user_filepath(self, request, file, create_dir=True):
            root = os.path.join(user_dir(), self.get_request_user_id(request))
            path = os.path.abspath(os.path.join(root, file))
            return path if os.path.commonpath((root, path)) == root else None

    class _Queue:
        def get_tasks_remaining(self):
            return 0

    class _PromptServer:
        instance = None

    ps = _PromptServer()
    ps.routes = web.RouteTableDef()
    ps.address = "127.0.0.1"
    ps.port = 8188
    ps.user_manager = _UserManager()
    ps.prompt_queue = _Queue()
    ps.sockets = {}
    ps.send_sync = lambda event, data, sid=None: None
    _PromptServer.instance = ps
    _make_module("server", PromptServer=_PromptServer)


def bind_comfyart() -> None:
    if str(REPO.parent) not in sys.path:
        sys.path.insert(0, str(REPO.parent))
    import importlib.util as ilu
    for k in [k for k in sys.modules if k == "ComfyArt" or k.startswith("ComfyArt.")]:
        del sys.modules[k]
    spec = ilu.spec_from_file_location("ComfyArt", REPO / "__init__.py", submodule_search_locations=[str(REPO)])
    mod = ilu.module_from_spec(spec)
    sys.modules["ComfyArt"] = mod
    spec.loader.exec_module(mod)


def _opt_text(o) -> str:
    if not isinstance(o, dict):
        return str(o or "")
    return " ".join(str(o.get(k) or "") for k in ("id", "label", "title", "text", "zh", "en", "value"))


def _option_highlighted(o: dict) -> bool:
    """A chip is highlighted if the product marks it recommended/default/selected."""
    if o.get("recommended") or o.get("highlighted") or o.get("selected"):
        return True
    d = o.get("default")
    return d is True


def first_unhighlighted_id(opts: list[dict]) -> str | None:
    un = [o for o in opts if not _option_highlighted(o)]
    pool = un or opts
    return str(pool[0]["id"]) if pool else None


def choose_ask_selection(ask) -> tuple[list[str], str]:
    """Answer from the user message when it already specifies something.

    Same method as the Lovart ai-model run: if a required chip is unspecified,
    take the first unhighlighted option. Do not invent a brand, a reference
    image, or extra styling the user did not ask for.
    """
    spec = getattr(ask, "spec", None) or {}
    kind = str(getattr(ask, "kind", None) or spec.get("kind") or "")
    prompt = str(getattr(ask, "prompt", None) or spec.get("prompt") or "")
    questions = spec.get("questions") or ([spec] if spec else [])
    selected: list[str] = []
    reasons: list[str] = []
    all_opts: list[str] = []

    for q in questions:
        if not isinstance(q, dict):
            continue
        qtext = str(q.get("prompt") or q.get("question") or q.get("title") or prompt or "")
        opts = [o for o in (q.get("options") or []) if isinstance(o, dict) and o.get("id")]
        ids = [str(o["id"]) for o in opts]
        all_opts.extend(ids)
        texts = {str(o["id"]): _opt_text(o) + " " + qtext for o in opts}
        joined = " ".join(texts.values()) + " " + qtext
        first_un = first_unhighlighted_id(opts)

        def pick(*needles: str) -> str | None:
            for oid, t in texts.items():
                tl = t.lower()
                if any(n.lower() in tl for n in needles):
                    return oid
            return None

        if any(k in kind.lower() for k in ("plan_quote", "run_approval", "approval", "quote", "cost")) or "start" in ids or "confirm" in ids:
            if "start" in ids:
                selected.append("start")
                reasons.append("cost/start card -> start")
            elif "confirm" in ids:
                selected.append("confirm")
                reasons.append("cost/start card -> confirm")
            elif ids:
                selected.append(ids[0])
                reasons.append("cost-like card, first option")
            continue

        # User message already states: one 3:4 head-and-shoulders PDP base, no brand/price/numbers.
        if any(w in joined.lower() for w in ("比例", "画幅", "ratio", "aspect", "竖版", "3:4", "3：4")):
            hit = pick("3:4", "3：4", "竖版")
            if hit:
                selected.append(hit)
                reasons.append(f"ratio -> {hit} (from user message: 3:4竖版)")
                continue
        if any(w in joined for w in ("几张", "张数", "输出几", "how many", "出图方式", "候选", "candidate", "成品", "count")):
            hit = pick("直接出 1 张", "直接出一张", "1 张 3:4", "一张成品", "一张", "1 张", "one image", "1 image", "single")
            # Avoid a 4-candidate option if both "1" and "4" could match loosely.
            if hit and any(s in texts[hit] for s in ("4 张", "四张", "4张", "四 张", "候选")) and "1" not in texts[hit] and "一" not in texts[hit]:
                hit = None
                for oid, t in texts.items():
                    if any(s in t for s in ("直接出 1", "直接出一", "1 张", "一张")) and not any(s in t for s in ("4 张", "四张", "候选")):
                        hit = oid
                        break
            if hit:
                selected.append(hit)
                reasons.append(f"count/output -> {hit} (from user message: 一张 / one 3:4竖版)")
                continue
        if any(w in joined for w in ("用途", "头肩", "底图", "详情页", "电商", "use case", "head-and-shoulder", "head and shoulder", "base shot", "PDP")):
            hit = pick("头肩", "底图", "详情页", "电商", "head-and-shoulder", "head and shoulder", "PDP", "e-commerce")
            if hit:
                selected.append(hit)
                reasons.append(f"use case -> {hit} (from user message: 电商详情页用的模特头肩底图)")
                continue
        if any(w in joined for w in ("品牌", "价格", "数字", "文字", "brand", "price", "number", "watermark", "水印")):
            hit = pick("不要", "无文字", "无品牌", "不编", "没有", "不需要", "none", "no brand", "no text", "no numbers")
            if hit:
                selected.append(hit)
                reasons.append(f"no-text -> {hit} (from user message: 不要编品牌名、价格和数字)")
                continue
        if any(w in joined for w in ("参考图", "reference image", "上传文件", "upload a file", "upload an image")):
            hit = pick("不需要", "暂不", "无参考", "没有", "不上传", "none", "skip", "no reference", "不必")
            if hit:
                selected.append(hit)
                reasons.append(f"reference -> {hit} (user message is text-only; do not invent a reference)")
                continue

        if first_un:
            selected.append(first_un)
            lab = texts.get(first_un, first_un).strip()
            reasons.append(
                f"unspecified in user message; first unhighlighted option {first_un} ({lab[:80]})"
            )
        elif ids:
            selected.append(ids[0])
            reasons.append(f"unspecified; no unhighlighted option, first option {ids[0]}")

    if not selected:
        if "start" in all_opts:
            selected = ["start"]
            reasons.append("fallback start")
        elif "confirm" in all_opts:
            selected = ["confirm"]
            reasons.append("fallback confirm")
        elif all_opts:
            selected = [all_opts[0]]
            reasons.append("fallback first option")
        else:
            selected = ["start"]
            reasons.append("no options, send start")
    return selected, "; ".join(reasons) or "default"


def is_cost_or_quote_ask(ask) -> bool:
    spec = getattr(ask, "spec", None) or {}
    kind = str(getattr(ask, "kind", None) or spec.get("kind") or "")
    questions = spec.get("questions") or ([spec] if spec else [])
    ids = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        for o in (q.get("options") or []):
            if isinstance(o, dict) and o.get("id"):
                ids.append(str(o["id"]))
    return bool(
        any(k in kind.lower() for k in ("plan_quote", "run_approval", "approval", "quote", "cost"))
        or "start" in ids or "confirm" in ids
    )


TARGET_DIRECTION_C = "浅米色无缝背景，侧身微转半身，一手轻扶衣摆"
CARD1_PICKS = {
    "gender": "female",
    "selling_points": "color",
    "ethnicity": "asian",
}
# Prefer these when the live card uses A/B/C ids instead of female/color/asian.
# Colour/solid-body option (Lovart 「皇家蓝高饱和纯色」); never match a print/印花 chip.
CARD1_LABEL_NEEDLES = {
    "gender": ("女模特", "female"),
    "selling_points": ("皇家蓝高饱和纯色", "宝蓝色", "纯色衣身", "整体配色", "高饱和纯色", "纯色", "royal blue", "colour", "color"),
    "ethnicity": ("亚洲人", "asian"),
}


def _opt_label(o: dict) -> str:
    return str(o.get("label") or o.get("title") or o.get("text") or o.get("zh") or "")


def _is_beige(label: str) -> bool:
    t = (label or "").lower()
    return any(w in (label or "") for w in ("浅米色", "暖米色", "米色", "米白", "浅咖", "卡其")) or "beige" in t


def _is_side_on(label: str) -> bool:
    t = (label or "").lower()
    return any(w in (label or "") for w in ("侧身", "侧转", "微侧", "3/4侧")) or any(
        w in t for w in ("side-on", "side on", "turned", "three-quarter", "3/4")
    )


def _direction_score(label: str) -> int:
    """Higher is closer to warm/light beige + side-on pose.

    Beige backdrop outranks side-on on a non-beige (e.g. white/grey) backdrop,
    because the comparison target is Lovart A / our usual C (light/warm beige + side-on).
    An option with both still wins.
    """
    t = (label or "").lower()
    score = 0
    beige = _is_beige(label)
    side = _is_side_on(label)
    if beige and side:
        score += 100
    elif beige:
        score += 70
    elif side:
        score += 40
    elif any(w in (label or "") for w in ("浅咖", "卡其", "暖灰", "暖色")) or "warm" in t:
        score += 20
    if "浅" in (label or "") or "light" in t:
        score += 5
    if "暖" in (label or "") or "warm" in t:
        score += 8
    if "侧" in (label or "") or "side" in t or "angle" in t:
        if not side:
            score += 10
    if any(w in (label or "") for w in ("正面", "正对")) or "front" in t or "facing straight" in t:
        score -= 25
    return score


def pick_studio_direction(opts: list[dict]) -> tuple[str | None, str, list[dict]]:
    """Prefer exact option C label; otherwise the closest warm/light beige + side-on option."""
    live = [{"id": str(o.get("id")), "label": _opt_label(o)} for o in opts]
    exact = next((o for o in opts if _opt_label(o) == TARGET_DIRECTION_C), None)
    if exact is not None:
        return str(exact["id"]), "exact label match for option C", live
    # id "c" whose label is already beige + side-on
    by_id = next((o for o in opts if str(o.get("id")) == "c"), None)
    if by_id is not None and _is_beige(_opt_label(by_id)) and _is_side_on(_opt_label(by_id)):
        return str(by_id["id"]), "id=c with beige+side-on label", live
    if not opts:
        return None, "no direction options", live
    ranked = sorted(opts, key=lambda o: _direction_score(_opt_label(o)), reverse=True)
    best = ranked[0]
    lab = _opt_label(best)
    why = f"closest beige+side-on (score={_direction_score(lab)}; beige={_is_beige(lab)}, side_on={_is_side_on(lab)})"
    return str(best["id"]), why, live


def card_record(ask) -> dict:
    spec = getattr(ask, "spec", None) or {}
    qs = spec.get("questions") or [spec]
    return {
        "ask_id": getattr(ask, "id", None), "kind": getattr(ask, "kind", None),
        "prompt": getattr(ask, "prompt", None),
        "questions": [{"id": q.get("id"), "prompt": q.get("prompt"), "placeholder": q.get("placeholder"),
                       "allow_other": q.get("allow_other"),
                       "options": [{"id": o.get("id"), "label": _opt_label(o)} for o in (q.get("options") or []) if isinstance(o, dict)]}
                      for q in qs if isinstance(q, dict)],
        "spec": spec,
    }


def choose_ask_payload(ask, targets=None) -> tuple[list, dict | None, str]:
    """EXACT label only. Any question without exactly one exact match -> StopAtCard."""
    targets = set(targets if targets is not None else TURNS[0]["targets"])
    spec = getattr(ask, "spec", None) or {}
    questions = [q for q in (spec.get("questions") or []) if isinstance(q, dict) and q.get("id")]
    if is_cost_or_quote_ask(ask):
        raise StopAtCard("cost/quote/approval card: no exact-label rule; stopped")
    if questions:
        answers, reasons = {}, []
        for q in questions:
            opts = [o for o in (q.get("options") or []) if isinstance(o, dict) and o.get("id")]
            hits = [o for o in opts if _opt_label(o).strip() in targets]
            if len(hits) != 1:
                raise StopAtCard(f"question {q.get('id')!r}: {len(hits)} exact label match(es)")
            answers[str(q["id"])] = {"selected": [str(hits[0]["id"])]}
            reasons.append(f"{q['id']}->{hits[0]['id']} exact {_opt_label(hits[0])!r}")
        return [], answers, "exact label: " + ", ".join(reasons)
    opts = [o for o in (spec.get("options") or []) if isinstance(o, dict) and o.get("id")]
    hits = [o for o in opts if _opt_label(o).strip() in targets]
    if len(hits) != 1:
        raise StopAtCard(f"single-question card: {len(hits)} exact label match(es)")
    return [str(hits[0]["id"])], None, f"exact {_opt_label(hits[0])!r}"


def answer_body(selected: list, answers: dict | None) -> dict:
    body: dict = {"selected": selected}
    if answers is not None:
        body["answers"] = answers
    return body


async def main() -> int:

    OUT.mkdir(parents=True, exist_ok=True)
    started = now_iso()
    if not MSG_PATH.is_file():
        print(json.dumps({"event": "abort", "reason": "missing msg.txt"}, ensure_ascii=False), flush=True)
        return 2
    import hashlib
    msg_md5 = hashlib.md5(MSG_PATH.read_bytes()).hexdigest()
    ref_md5 = None
    loaded = load_env(SECRETS)
    official_key_present = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    print(json.dumps({
        "event": "env",
        "ts": started,
        "loaded_key_names": loaded,
        "official_deepseek_key_present": official_key_present,
        "wavespeed_key_present": bool(os.environ.get("WAVESPEED_API_KEY", "").strip()),
        "msg_md5": msg_md5,
        "expected_msg_md5": EXPECTED_MSG_MD5,
        "ref": None,
        "user_text": USER_TEXT,
        "tip": TIP,
    }, ensure_ascii=False), flush=True)

    locales = {
        "zh": json.loads((REPO / "src/locales/zh.json").read_text(encoding="utf-8")),
        "en": json.loads((REPO / "src/locales/en.json").read_text(encoding="utf-8")),
    }
    skills = parse_skills(REPO / "src/skills.ts", locales)
    assert "studio-model" in skills, sorted(skills)[:8]
    (OUT / "parsed-skills-meta.json").write_text(json.dumps({
        "count": len(skills),
        "studio-model_output": skills["studio-model"].get("output"),
        "studio-model_instructions_len": len(skills["studio-model"]["instructions"]),
        "appends_portrait_shots_708": skills["studio-model"].get("appends_portrait_shots_708"),
        "instructions_has_708_slot_list": "Shot rules (#708)" in skills["studio-model"]["instructions"],
        "instructions_default_1": "Default output is 1 image" in skills["studio-model"]["instructions"],
        "tip": TIP,
        "repo": str(REPO),
        "out": str(OUT),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "studio-model.user-message.txt").write_text(USER_TEXT, encoding="utf-8")
    (OUT / "studio-model.instructions.txt").write_text(skills["studio-model"]["instructions"], encoding="utf-8")

    base = Path(tempfile.mkdtemp(prefix="comfyart-chat-capture-911-studio-"))
    for sub in ("input", "output", "temp", "user"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("COMFYART_SKIP_KEY_CHECK", "1")
    _install_stubs(base)
    bind_comfyart()

    from server import PromptServer
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    from ComfyArt import api  # noqa: F401
    from ComfyArt.api import bot_asks, chat_store, mcp_commands, settings, wavespeed
    from ComfyArt.api.bot_turns import ACTIVE_TURNS, QUEUED
    from ComfyArt.api.provider_admin import install, llm_route, llm_source, reset_runtime
    from ComfyArt.api.settings import official_llm_ready
    from ComfyArt.api.settings import OFFICIAL_LLM_DISPLAY_NAME, OFFICIAL_LLM_MODEL

    def _install_http_host_logger() -> None:
        try:
            import aiohttp
        except ImportError:
            return
        orig = aiohttp.ClientSession._request

        async def _logged(self, method, url, *a, **k):
            try:
                from yarl import URL
                u = URL(str(url))
                rec = {"ts": now_iso(), "method": str(method), "host": u.host, "path": u.path}
            except Exception:
                rec = {"ts": now_iso(), "method": str(method), "host": "unparsed", "path": ""}
            HTTP_HOSTS.append(rec)
            return await orig(self, method, url, *a, **k)

        aiohttp.ClientSession._request = _logged

    _install_http_host_logger()
    reset_runtime()
    settings.write_json(settings.app_path("settings.json"), {
        **settings.all_settings(),
        "enable-mcp": True,
        "enable-bot": True,
        "llm_mode": "",
        "bot-local-llm-url": "https://llm.wavespeed.ai/v1",
        "bot-model-local-llm": "deepseek/deepseek-v4.1-flash-1017",
        "bot-enable-comfy-mcp": False,
        "bot-enable-review": True,
        "memory-enabled": True,
        "proactive-memory": False,
        "proactive-skills": False,
        "proactive-review": False,
    })
    install()

    async def blocked_submit(inputs):
        BLOCKED_PREDICT.append({"ts": now_iso(), "via": "wavespeed.submit", "keys": sorted((inputs or {}).keys()) if isinstance(inputs, dict) else type(inputs).__name__})
        raise RuntimeError("chat-capture stub: wavespeed.submit blocked; no predict was sent")

    wavespeed.submit = blocked_submit

    import shutil
    cat_path = OUT / "ws-catalog.json"
    shared_cat = Path("/workspace/911-ask-capture/ws-catalog.json")
    if shared_cat.is_file():
        if cat_path.resolve() != shared_cat.resolve():
            shutil.copy2(shared_cat, cat_path)
    else:
        import subprocess
        helper = Path("/workspace/911-ask-capture/fetch_ws_catalog.py")
        subprocess.run([sys.executable, str(helper), str(REPO), str(cat_path)], check=True,
                       capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k not in BLOCKED_ENV})
    _real_catalog = json.loads(cat_path.read_text(encoding="utf-8"))

    async def keyed_catalog(refresh: bool = False):
        return _real_catalog

    wavespeed.catalog = keyed_catalog

    from ComfyArt.bot import local_llm as _ll
    _uc_orig = _ll._user_content

    def logged_user_content(text, attachments):
        out = _uc_orig(text, attachments)
        parts = out if isinstance(out, list) else []
        IMAGE_PART_LOG.append({"ts": now_iso(), "turn": CURRENT_TURN["id"],
                               "image_parts": sum(1 for p in parts if isinstance(p, dict) and p.get("type") == "image_url"),
                               "attachments": len(attachments or [])})
        return out

    _ll._user_content = logged_user_content

    bal_before = wavespeed_balance()
    route = llm_route()
    route_url = str((route or {}).get("base_url") or "")
    ready = official_llm_ready()
    proof = {
        "event": "route",
        "ts": now_iso(),
        "tip": TIP,
        "llm_source": llm_source(),
        "llm_mode": settings.get_setting("llm_mode"),
        "llm_route": route,
        "official_llm_ready": ready,
        "official_llm_model": OFFICIAL_LLM_MODEL,
        "official_llm_display_name": OFFICIAL_LLM_DISPLAY_NAME,
        "official_key_present": official_key_present,
        "resolved_base_url": route_url,
        "wavespeed_key_in_process": bool(os.environ.get("WAVESPEED_API_KEY", "").strip()),
        "balance_before": bal_before,
        "msg_md5": msg_md5,
        "ref": None,
        "expected_msg_md5": EXPECTED_MSG_MD5,
        "input_matches_lovart": msg_md5 == EXPECTED_MSG_MD5,
    }
    print(json.dumps(proof, ensure_ascii=False, default=str), flush=True)
    (OUT / "route-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    src = llm_source()
    mode = settings.get_setting("llm_mode")
    model = str((route or {}).get("model") or "")
    reasons = []
    if src != "default":
        reasons.append(f"llm_source={src!r} (want default)")
    if mode not in ("", None, "official"):
        reasons.append(f"llm_mode={mode!r} (want unset or official)")
    if not ready:
        reasons.append("official_llm_ready is false")
    if "api.deepseek.com" not in route_url:
        reasons.append(f"base_url={route_url!r} (want https://api.deepseek.com)")
    if model != "deepseek-flash" or OFFICIAL_LLM_MODEL != "deepseek-flash":
        reasons.append(f"model={model!r} official={OFFICIAL_LLM_MODEL!r} (want deepseek-flash)")
    if os.environ.get("WAVESPEED_API_KEY", "").strip():
        reasons.append("WAVESPEED_API_KEY unexpectedly present in chat process")
    if not proof["input_matches_lovart"]:
        reasons.append("input md5 mismatch vs locked studio-model msg.txt")
    if reasons:
        print(json.dumps({"event": "abort", "reasons": reasons, "proof": {k: proof[k] for k in proof if k != "llm_route"}}, ensure_ascii=False, default=str), flush=True)
        return 2

    canvas_state: dict = {"shapes": []}

    def handle_command(action: str, args: dict) -> dict:
        args = args or {}
        tid = CURRENT_TURN["id"]
        COMMAND_LOG.append({"ts": now_iso(), "turn": tid, "action": action, "args": deepcopy(args)})
        if action == "skill":
            act = str(args.get("action") or "").lower()
            locale = "zh"
            for t in TURNS:
                if t["id"] == tid:
                    locale = t["locale"]
                    break
            if act == "list":
                listed = []
                for sid, s in skills.items():
                    listed.append({
                        "id": sid,
                        "name": skill_name(s, locale, locales),
                        "description": "",
                        "custom": False,
                    })
                return {"skills": listed}
            if act == "read":
                keys = [str(args.get("id") or "").strip(), str(args.get("name") or "").strip()]
                keys = [k for k in keys if k]
                if not keys:
                    raise ValueError("[non-retryable] skill read needs a non-empty id or name")
                norm = lambda v: v.strip().lower()
                skill = None
                for s in skills.values():
                    names = {s["id"], skill_name(s, "zh", locales), skill_name(s, "en", locales)}
                    if any(k in names or norm(k) in {norm(n) for n in names} for k in keys):
                        skill = s
                        break
                if not skill:
                    raise ValueError(f"unknown skill {keys}")
                rec = {
                    "id": skill["id"],
                    "name": skill_name(skill, locale, locales),
                    "description": "",
                    "instructions": skill["instructions"],
                    "files": [],
                    "images": [],
                }
                if skill.get("output"):
                    rec["output"] = skill["output"]
                return rec
            raise ValueError("action must be list, read or save")

        if action == "get_canvas":
            return {
                "project": "local",
                "pages": [{"id": "page:page", "name": "Page 1", "current": True}],
                "page": "page:page",
                "shapes": list(canvas_state["shapes"]),
                "selection": [s["id"] for s in canvas_state["shapes"]],
                "brand_kit": None,
            }
        if action == "memory":
            return {"memories": []} if str(args.get("action") or "list") == "list" else {"ok": True}
        if action == "update_plan":
            return {"ok": True}
        if action == "focus":
            return {"ok": True}
        if action in ("update_shapes", "delete_shapes", "add_text", "add_shape", "create_frame"):
            return {"ok": True, "stub": True}

        if action == "generate_image":
            rec = {"ts": now_iso(), "args": deepcopy(args)}
            rec["size_args"] = {k: args.get(k) for k in ("model", "edit_model", "auto_model", "width", "height", "ratio", "resolution", "edit_resolution", "size_lock", "size_candidates", "count")}
            rec["model_choice_model"] = (args.get("model_choice") or {}).get("model")
            rec["model_choice_category"] = (args.get("model_choice") or {}).get("category")
            GEN_CAPTURES.setdefault(tid, []).append(rec)
            w = args.get("width")
            h = args.get("height")
            mc = args.get("model_choice") or {}
            model = args.get("edit_model") or args.get("model") or mc.get("model") or ""
            sid = f"shape:stub-{tid}-{len(GEN_CAPTURES.get(tid, []))}"
            canvas_state["shapes"].append({
                "id": sid,
                "type": "image",
                "name": f"{tid}-{len(GEN_CAPTURES.get(tid, []))}.png",
                "url": f"https://example.invalid/chat-capture-stub-{len(GEN_CAPTURES.get(tid, []))}.webp",
                "x": 200 * len(GEN_CAPTURES.get(tid, [])),
                "y": 0,
                "width": w or 1024,
                "height": h or 1024,
            })
            print(json.dumps({
                "event": "generate_image_stubbed",
                "turn": tid,
                "n": len(GEN_CAPTURES.get(tid, [])),
                "skill": args.get("skill"),
                "ratio": args.get("ratio"),
                "width": w,
                "height": h,
                "count": args.get("count"),
                "prompt_chars": len(str(args.get("prompt") or "")),
                "refs": args.get("refs"),
                "size_args": rec["size_args"],
            }, ensure_ascii=False), flush=True)
            return {
                "ids": [sid],
                "model": model,
                **({"width": w} if w else {}),
                **({"height": h} if h else {}),
                "note": "call wait_generation with these ids",
                "stubbed": True,
                "submitted": False,
            }
        if action == "wait_generation":
            ids = [str(i) for i in (args.get("ids") or [])]
            return {
                "status": "done",
                "results": [
                    {"id": i, "status": "done", "urls": ["https://example.invalid/chat-capture-stub.webp"], "shapes": [i]}
                    for i in ids
                ],
                "stubbed": True,
            }
        if action == "view_canvas":
            raise ValueError("view_canvas is stubbed empty in chat-capture; use the attached reference image")
        raise ValueError(f"unknown command {action}")

    orig_send_sync = PromptServer.instance.send_sync

    def send_sync(event, data, sid=None):
        try:
            orig_send_sync(event, data, sid)
        except Exception:
            pass
        if event != mcp_commands.COMMAND_EVENT:
            return
        command_id = (data or {}).get("id")
        action = (data or {}).get("action")
        args = (data or {}).get("args") or {}

        def fulfill():
            fut = mcp_commands._pending.get(str(command_id or ""))
            if fut is None or fut.done():
                return
            try:
                result = handle_command(str(action), args if isinstance(args, dict) else {})
                fut.set_result(result if isinstance(result, dict) else {"result": result})
            except Exception as e:
                fut.set_exception(ValueError(str(e)))

        loop = asyncio.get_running_loop()
        loop.call_soon(fulfill)

    PromptServer.instance.send_sync = send_sync
    mcp_commands._pages["capture-client"] = "local"
    PromptServer.instance.sockets["capture-client"] = object()

    ACTIVE_TURNS.clear()
    QUEUED.clear()
    bot_asks.PENDING.clear()
    bot_asks.ANSWERED_RUN_APPROVALS.clear()
    from ComfyArt.api.ask_store import set_store
    set_store(None)

    app = web.Application()
    app.router.add_routes(PromptServer.instance.routes)
    client = TestClient(TestServer(app, host="127.0.0.1"))
    await client.start_server()
    PromptServer.instance.port = client.server.port
    PromptServer.instance.address = "127.0.0.1"
    print(json.dumps({"event": "server_up", "port": client.server.port, "ts": now_iso()}, ensure_ascii=False), flush=True)

    confirm_stop = asyncio.Event()

    async def confirm_plan_quotes(port: int) -> None:
        import aiohttp
        base_url = f"http://127.0.0.1:{port}"
        seen: set[str] = set()
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while not confirm_stop.is_set():
                try:
                    async with session.get(f"{base_url}/comfyart/bot/chats", headers={"comfy-user": "default"}) as r:
                        listing = await r.json()
                except Exception:
                    listing = {}
                chats = []
                for c in (listing.get("chats") or []):
                    if isinstance(c, dict) and c.get("id"):
                        chats.append(c["id"])
                for row in list(COMMAND_LOG):
                    if row.get("chat_id"):
                        chats.append(row["chat_id"])
                for cid in dict.fromkeys(chats):
                    try:
                        async with session.get(
                            f"{base_url}/comfyart/bot/chats/{cid}/asks",
                            headers={"comfy-user": "default"},
                        ) as r:
                            data = await r.json()
                    except Exception:
                        continue
                    for a in data.get("asks") or []:
                        aid = a.get("ask_id") or a.get("id")
                        if not aid or aid in seen or a.get("status") not in (None, "pending"):
                            continue
                        # Prefer the in-process chooser if we can find the ask object
                        selected = ["start"]
                        answers = None
                        reason = "http-poll fallback start"
                        match = None
                        try:
                            pending = bot_asks.list_pending_for_chat(cid)
                            match = next((x for x in pending if str(getattr(x, "id", "")) == str(aid)), None)
                            if match is not None:
                                selected, answers, reason = choose_ask_payload(match)
                        except Exception as e:
                            reason = f"chooser error {type(e).__name__}; start"
                        try:
                            async with session.post(
                                f"{base_url}/comfyart/bot/chats/{cid}/asks/{aid}/answer",
                                json=answer_body(selected, answers),
                                headers={"comfy-user": "default"},
                            ) as r:
                                body = await r.json()
                                rec = {
                                    "ts": now_iso(),
                                    "chat_id": cid,
                                    "ask_id": aid,
                                    "kind": a.get("kind"),
                                    "prompt": a.get("prompt"),
                                    "spec": (getattr(match, "spec", None) if match is not None else a),
                                    "http": r.status,
                                    "ok": body.get("ok"),
                                    "selected": selected,
                                    "answers": answers,
                                    "reason": reason,
                                    "via": "separate_session",
                                }
                                CONFIRM_LOG.append(rec)
                                ASK_LOG.append(rec)
                                seen.add(aid)
                                print(json.dumps({"event": "ask_answered", **rec}, ensure_ascii=False), flush=True)
                        except Exception as e:
                            rec = {"ts": now_iso(), "chat_id": cid, "ask_id": aid, "error": type(e).__name__, "via": "separate_session"}
                            CONFIRM_LOG.append(rec)
                            print(json.dumps({"event": "ask_answer_error", **rec}, ensure_ascii=False), flush=True)
                try:
                    await asyncio.wait_for(confirm_stop.wait(), timeout=0.4)
                except asyncio.TimeoutError:
                    pass

    confirm_task = asyncio.create_task(asyncio.sleep(0))  # poller disabled: exact-label answers only

    answered_ids: set = set()

    async def snapshot(chat_id: str, n: int, pending) -> None:
        resp = await client.get(f"/comfyart/bot/chats/{chat_id}")
        data = await resp.json()
        msgs = data.get("messages") or []
        user = next((m for m in msgs if m.get("role") == "user"), None)
        assistant = next((m for m in reversed(msgs) if m.get("role") == "assistant"), None)
        d = OUT / f"{TURN_ID}-card{n}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ui-before-answer.ui-fixture.json").write_text(json.dumps({
            "user": user, "assistant": assistant,
            "pending_asks": [card_record(a) for a in pending], "name": f"{TURN_ID}-card{n}", "lang": "zh",
        }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    async def answer_asks(chat_id: str):
        try:
            await _answer_asks(chat_id)
        except Exception:
            print(json.dumps({"event": "answer_asks_crashed", "tb": traceback.format_exc()}, ensure_ascii=False), flush=True)
            STOP["stopped"] = True

    async def _answer_asks(chat_id: str):
        seen_active = False
        t0 = time.monotonic()
        while True:
            if STOP["stopped"]:
                return
            if chat_id in ACTIVE_TURNS:
                seen_active = True
            if (seen_active or time.monotonic() - t0 > 30) and chat_id not in ACTIVE_TURNS and not bot_asks.list_pending_for_chat(chat_id):
                return
            asks = bot_asks.list_pending_for_chat(chat_id)
            for ask in asks:
                if ask.id in answered_ids:
                    continue
                card = card_record(ask)
                n = len(CARDS) + 1
                card["n"] = n
                CARDS.append(card)
                await snapshot(chat_id, n, [ask])
                try:
                    selected, answers, reason = choose_ask_payload(ask)
                except StopAtCard as e:
                    card["stopped"] = True
                    card["stop_reason"] = str(e)
                    STOP["card"] = n
                    STOP["parked"] = True
                    (OUT / f"PARKED_card{n}.json").write_text(json.dumps(card | {"spec": None, "ts": now_iso(), "answer_file": str(OUT / f"answer-card{n}.json"), "format": {"labels": ["<exact option label per question>"]}}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                    print(json.dumps({"event": "STOP_AT_CARD_PARKED", "card": n, "reason": str(e), "questions": card["questions"]}, ensure_ascii=False, default=str), flush=True)
                    deadline = time.monotonic() + PARK_S
                    picked = None
                    while time.monotonic() < deadline:
                        f = OUT / f"answer-card{n}.json"
                        if f.is_file():
                            try:
                                labels = json.loads(f.read_text(encoding="utf-8"))["labels"]
                                picked = choose_ask_payload(ask, targets=labels)
                                card["named_labels"] = labels
                                break
                            except Exception as e2:
                                print(json.dumps({"event": "answer_file_rejected", "card": n, "error": str(e2)}, ensure_ascii=False), flush=True)
                                f.rename(f.with_suffix(f".rejected-{int(time.time())}.json"))
                        await asyncio.sleep(1.0)
                    STOP["parked"] = False
                    if picked is None:
                        STOP["stopped"] = True
                        print(json.dumps({"event": "PARK_EXPIRED_STOP", "card": n}, ensure_ascii=False), flush=True)
                        return
                    selected, answers, reason = picked
                    reason = "named label (answer file): " + reason
                answered_ids.add(ask.id)
                r = await client.post(
                    f"/comfyart/bot/chats/{chat_id}/asks/{ask.id}/answer",
                    json=answer_body(selected, answers),
                )
                card.update({"submitted": True, "selected": selected, "answers": answers, "reason": reason, "http": r.status})
                rec = {"ts": now_iso(), "turn": CURRENT_TURN["id"], "action": "_answer_ask", "ask_id": ask.id,
                       "selected": selected, "answers": answers, "reason": reason, "kind": getattr(ask, "kind", None),
                       "prompt": getattr(ask, "prompt", None), "spec": getattr(ask, "spec", None), "http": r.status}
                COMMAND_LOG.append(rec)
                ASK_LOG.append(rec)
                print(json.dumps({"event": "ask_answered_exact", "card": n, "answers": answers, "selected": selected, "reason": reason, "http": r.status}, ensure_ascii=False, default=str), flush=True)
            await asyncio.sleep(0.25)

    async def wait_done(chat_id: str, timeout: float = 720.0) -> dict:
        deadline = time.monotonic() + timeout
        last = {}
        while time.monotonic() < deadline:
            resp = await client.get(f"/comfyart/bot/chats/{chat_id}")
            last = await resp.json()
            msgs = last.get("messages") or []
            if msgs and all(m.get("status") != "streaming" for m in msgs):
                return last
            if STOP["stopped"]:
                last["stopped_at_card"] = STOP["card"]
                return last
            await asyncio.sleep(0.4)
        raise TimeoutError(f"turn did not finish within {timeout}s")

    # Attach the official Lovart garment reference (review-assets 87857c35).
    import hashlib as _h
    INPUT_SHA = {}
    for t in TURNS:
        for ref in t["refs"]:
            sha = _h.sha256(Path(ref["path"]).read_bytes()).hexdigest()
            if sha != EXPECTED_SHA[str(ref["path"])]:
                raise RuntimeError(f"input sha mismatch {ref['path']}")
            INPUT_SHA[ref["filename"]] = sha
            shutil.copy2(ref["path"], base / "input" / ref["filename"])

    results = []
    try:
        for t in TURNS:
            CURRENT_TURN["id"] = t["id"]
            refs, shapes = [], []
            for i, ref in enumerate(t["refs"]):
                src = f"/api/view?filename={ref['filename']}&type=input"
                refs.append({"src": src, "id": ref["shape_id"], "name": ref["filename"]})
                shapes.append({"id": ref["shape_id"], "type": "image", "name": ref["filename"], "url": src,
                               "x": 200 * i, "y": 0, "width": ref["width"], "height": ref["height"]})
            canvas_state["shapes"] = shapes
            cr = await client.post("/comfyart/bot/chats", json={
                "provider": "local-llm",
                "project": "local",
                "title": f"chat-capture {t['id']}",
                "run_mode": "auto",
            })
            body = await cr.json()
            if cr.status >= 400:
                results.append({"id": t["id"], "error": "create_chat_failed", "http": cr.status, "body": body})
                continue
            chat_id = body["chat"]["id"]
            from ComfyArt.api.bot_send import compose_provider_text
            from ComfyArt.bot.skill_output import run_hint
            provider_text = compose_provider_text(t["text"], skill_name=t["skill"], memory="", lines=[], review=True)
            ask_task = asyncio.create_task(answer_asks(chat_id))
            sr = await client.post(f"/comfyart/bot/chats/{chat_id}/send", json={
                "text": t["text"],
                "skill": t["skill"],
                "refs": refs,
                "lang": t["lang"],
                "run_mode": "interactive",
            })
            send_body = await sr.json()
            COMMAND_LOG.append({"ts": now_iso(), "turn": t["id"], "action": "_chat_created", "chat_id": chat_id})
            print(json.dumps({
                "event": "sent",
                "turn": t["id"],
                "ts": now_iso(),
                "http": sr.status,
                "chat_id": chat_id,
            }, ensure_ascii=False), flush=True)
            try:
                done = await wait_done(chat_id, timeout=720 + PARK_S)
            except Exception as e:
                done = {"error": str(e), "chat_id": chat_id}
            ask_task.cancel()
            try:
                await ask_task
            except (asyncio.CancelledError, Exception):
                pass

            usage = None
            status = None
            assistant = None
            for m in (done.get("messages") or []):
                if m.get("role") == "assistant":
                    assistant = m
                    usage = m.get("usage") or usage
                    status = m.get("status")
            gens = GEN_CAPTURES.get(t["id"]) or []
            prompt = ""
            if gens:
                prompt = str((gens[0].get("args") or {}).get("prompt") or "")
            import hashlib as _hashlib
            prompt_sha256 = _hashlib.sha256(prompt.encode("utf-8")).hexdigest() if prompt else ""
            rec = {
                "id": t["id"],
                "skill": t["skill"],
                "user_text": t["text"],
                "lang": t["lang"],
                "chat_id": chat_id,
                "send_http": sr.status,
                "send_body_keys": list(send_body) if isinstance(send_body, dict) else type(send_body).__name__,
                "status": status,
                "usage": usage,
                "provider_text": provider_text,
                "run_hint": run_hint(t["skill"]),
                "refs": refs, "input_sha256": INPUT_SHA, "cards": CARDS, "stopped_at_card": STOP["card"],
                "generate_image_calls": gens,
                "generate_image_count": len(gens),
                "captured_prompt": prompt,
                "captured_prompt_sha256": prompt_sha256,
                "appends_portrait_shots_708": bool((skills.get("studio-model") or {}).get("appends_portrait_shots_708")),
                "assistant_blocks": (assistant or {}).get("blocks"),
                "asks": ASK_LOG,
                "error": done.get("error"),
            }
            results.append(rec)
            (OUT / f"{t['id']}.turn.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            if prompt:
                (OUT / f"{t['id']}.captured-prompt.txt").write_text(prompt, encoding="utf-8")
            for i, g in enumerate(gens, 1):
                p = str((g.get("args") or {}).get("prompt") or "")
                (OUT / f"{t['id']}.captured-prompt-{i:02d}.txt").write_text(p, encoding="utf-8")
            (OUT / f"{t['id']}.provider-text.txt").write_text(provider_text, encoding="utf-8")
            print(json.dumps({
                "event": "turn_done",
                "turn": t["id"],
                "ts": now_iso(),
                "status": status,
                "usage": usage,
                "generate_image_count": len(gens),
                "prompt_chars": len(prompt),
                "asks": len(ASK_LOG),
            }, ensure_ascii=False), flush=True)
    finally:
        confirm_stop.set()
        try:
            await asyncio.wait_for(confirm_task, timeout=2)
        except Exception:
            confirm_task.cancel()
        bal_after = None
        try:
            bal_after = wavespeed_balance()
        except Exception as e:
            bal_after = f"error: {e}"
        summary = {
            "started": started,
            "ended": now_iso(),
            "tip": TIP,
            "llm_source": llm_source(),
            "llm_route": llm_route(),
            "official_llm_ready": official_llm_ready(),
            "official_key_present": official_key_present,
            "chat_endpoint": str((llm_route() or {}).get("base_url") or ""),
            "chat_model": str((llm_route() or {}).get("model") or OFFICIAL_LLM_MODEL),
            "chat_display": OFFICIAL_LLM_DISPLAY_NAME,
            "wavespeed_key_in_process": bool(os.environ.get("WAVESPEED_API_KEY", "").strip()),
            "balance_before": bal_before,
            "balance_after": bal_after,
            "balance_unchanged": bal_after == bal_before,
            "blocked_predict_attempts": BLOCKED_PREDICT,
            "llm_image_parts": IMAGE_PART_LOG,
            "command_log_count": len(COMMAND_LOG),
            "http_hosts": sorted({h.get("host") for h in HTTP_HOSTS if h.get("host")}),
            "http_host_log": HTTP_HOSTS,
            "http_hosts_all_deepseek": all((h.get("host") or "") == "api.deepseek.com" for h in HTTP_HOSTS) if HTTP_HOSTS else False,
            "http_touched_wavespeed": any("wavespeed" in str(h.get("host") or "").lower() for h in HTTP_HOSTS),
            "plan_quote_confirms": CONFIRM_LOG,
            "cards": CARDS,
            "stopped_at_card": STOP["card"],
            "turn": TURN_ID,
            "asks": ASK_LOG,
            "ask_user_specs": [
                {k: a.get(k) for k in ("ask_id", "kind", "prompt", "spec", "selected", "answers", "reason", "http")}
                for a in ASK_LOG
            ],
            "msg_md5": msg_md5,
            "appends_portrait_shots_708": bool((skills.get("studio-model") or {}).get("appends_portrait_shots_708")),
            "ref": None,
            "results": [
                {k: r.get(k) for k in (
                    "id", "skill", "status", "usage", "generate_image_count", "error",
                ) if k in r}
                | {"captured_prompt_chars": len(r.get("captured_prompt") or "")}
                for r in results
            ],
        }
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (OUT / "command-log.json").write_text(json.dumps(COMMAND_LOG, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (OUT / "ask-user-specs.json").write_text(json.dumps(summary["ask_user_specs"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        for r in results:
            prompt = r.get("captured_prompt") or ""
            sha = r.get("captured_prompt_sha256") or ""
            if sha:
                (OUT / f"{r['id']}.prompt.sha256").write_text(sha + "\n", encoding="utf-8")
            gens = r.get("generate_image_calls") or []
            (OUT / f"{r['id']}.generate_image_args.json").write_text(
                json.dumps(gens, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            quotes = []
            for a in ASK_LOG + CONFIRM_LOG:
                if "quote" in str(a.get("kind") or "").lower() or "plan_quote" in str(a.get("kind") or "").lower():
                    quotes.append(a)
                spec = a.get("spec") or {}
                if "quote" in json.dumps(spec, ensure_ascii=False, default=str).lower():
                    quotes.append(a)
            (OUT / "quotes.json").write_text(json.dumps({"plan_quote_confirms": CONFIRM_LOG, "quote_asks": quotes}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"event": "finished", "ts": now_iso(), "balance_before": bal_before, "balance_after": bal_after, "unchanged": bal_after == bal_before, "generate_image_count": sum(len(v) for v in GEN_CAPTURES.values())}, ensure_ascii=False, default=str), flush=True)
        await client.close()
        shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
