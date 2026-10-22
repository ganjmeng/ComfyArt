from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _tags(node: dict) -> list[str]:
    return [w for w in re.split(r"[\s,]+", node.get("_meta", {}).get("title", "").lower()) if w.startswith("@")]


def test_workflow_titles_are_unique_and_name_the_output():
    for path in sorted((ROOT / "workflows").glob("*.api.json")):
        graph = json.loads(path.read_text(encoding="utf-8"))
        tags = [t for node in graph.values() for t in _tags(node)]
        assert len(tags) == len(set(tags)), path.name
        assert "@save" in tags, path.name
