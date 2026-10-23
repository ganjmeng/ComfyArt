"""#133 Auto model choice: when the user names no model, pick one by task type from api/auto_models.json
(product table v1). Deterministic: same prompt -> same category -> same model. User-named models win."""
import json
import logging
from pathlib import Path

log = logging.getLogger("comfyart")
TABLE = Path(__file__).with_name("auto_models.json")


def load_table() -> dict:
    with open(TABLE, encoding="utf-8") as f:
        return json.load(f)["features"]


def tool_feature(tool: str) -> str | None:
    return next((f for f, spec in load_table().items() if spec["tool"] == tool), None)


def choose(feature: str, prompt: str, named: str | None, catalog: dict) -> dict:
    """catalog: load_config() result. Returns {model, auto, category, reason: {zh, en}}."""
    cfg = catalog["features"][feature]
    if named:
        return {"model": named, "auto": False, "category": "user",
                "reason": {"zh": "你指定了这个模型", "en": "you named this model"}}
    spec = load_table()[feature]
    text = (prompt or "").lower()
    cat = next((c for c in spec["categories"] if any(k.lower() in text for k in c["keywords"])), None)
    ids = {m["id"] for m in cfg["models"]}
    if cat and cat["model"] not in ids:
        log.warning("auto model %s for %s/%s not in catalog; falling back to %s", cat["model"], feature, cat["id"], cfg["default"])
        return {"model": cfg["default"], "auto": True, "category": cat["id"], "fallback": cat["model"],
                "reason": {"zh": f"{cat['zh']}，但 {cat['model']} 当前不可用，改用默认模型",
                           "en": f"{cat['en']}, but {cat['model']} is unavailable, so the default model"}}
    if cat:
        return {"model": cat["model"], "auto": True, "category": cat["id"], "reason": {"zh": cat["zh"], "en": cat["en"]}}
    return {"model": cfg["default"], "auto": True, "category": "default", "reason": dict(spec["default"])}


def note(choice: dict) -> str:
    """One line the agent repeats in its reply: 用了 X，因为 Y / used X because Y."""
    m, r = choice["model"], choice["reason"]
    return f"用了 {m}，因为{r['zh']}。 / Used {m} because {r['en']}."
