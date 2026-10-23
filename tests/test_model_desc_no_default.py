"""#136 design/product: model descriptions never say 默认 / default."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_model_descriptions_never_say_default():
    data = json.loads((ROOT / "api/model_display.json").read_text(encoding="utf-8"))
    bad = []
    def walk(o):
        if isinstance(o, list) and len(o) >= 4 and all(isinstance(x, str) for x in o[:4]):
            for d in o[2:4]:
                if "默认" in d or re.search(r"\bdefault\b", d, re.I):
                    bad.append((o[0], d))
        elif isinstance(o, list):
            for x in o: walk(x)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k != "_comment": walk(v)
    walk(data)
    assert not bad, bad
