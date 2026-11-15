"""#994: a narrow own-error boundary, not a raw provider-error passthrough.

Keep machine packets inside the relay/normalizer. Give chat/LLM only our own
current-language sentence. Unknown packets or strings retain existing policy.
"""
import json
import re
from pathlib import Path

from .skill_output import TYPED_USER_RATIOS_994, ratio_refusal_994


def ratio_refusal_display(text: str, lang: str) -> str | None:
    lk = "zh" if lang == "zh" else "en"
    raw = text.strip()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, dict) and data.get("kind") == "userRatioUnsupported":
        # Match the complete OWN packet before extracting a numeric value. A
        # forged kind/user_message must never open arbitrary raw-text display.
        match = re.search(r"Requested ratio ([\d.]+\s*[:：]\s*[\d.]+) is not supported", str(data.get("error") or ""))
        if match and data == ratio_refusal_994(match.group(1)):
            ratio = re.sub(r"\s+", "", match.group(1)).replace("：", ":")
            options = ", ".join(TYPED_USER_RATIOS_994)
            if lk == "zh":
                return f"不支持你指定的比例 {ratio}，未提交。可选比例：{options}。所选模型仍须支持该比例；也可明确选择其它模型。"
            return (f"Requested ratio {ratio} is not supported. Nothing submitted. "
                    f"Available app ratios: {options}. The selected model must support the ratio; "
                    "you may explicitly choose another model.")
    # The page already maps this OWN backend kind to localized safe copy. MCP
    # adds ValueError around page errors; remove it ONLY on exact-copy match.
    loc = Path(__file__).resolve().parents[1] / "src" / "locales"
    copies = {lg: json.loads((loc / f"{lg}.json").read_text(encoding="utf-8"))["wsErr.userRatioUnsupported"]
              for lg in ("zh", "en")}
    for prefix in ("[tool error] ", "[error] "):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if raw.startswith("ValueError: "):
        raw = raw[len("ValueError: "):]
    return copies[lk] if raw in copies.values() else None
