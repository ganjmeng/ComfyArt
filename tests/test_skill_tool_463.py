"""#463 — agent skill tool: "Edit in chat" saves back by id; description set / change / round trip.

Builds the tests/js/import463 node harness itself (rolldown + node), like test_skill_desc_462.py, so CI runs it.
The edit-in-chat entry text itself lives in PR #484 (src/skillEdit.ts, not merged yet); this tests #463's side:
skillEditToolHint() + skillTool. See test_edit_chat_entry_uses_id_when_484_present for the #484 dependency.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"skilltool463-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/import463/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


def test_edit_chat_saves_same_id_and_leaves_namesake_byte_identical() -> None:
    r = report()["editChat"]
    assert r.get("ids") == ["poster-2", "poster-2"], r  # hint gives the agent the id for read and save
    assert r["hintHasName"] is False  # never tells the agent to address by name
    assert r["readId"] == "poster-2"
    assert r["saved"]["id"] == "poster-2"
    assert "EDITED IN CHAT" in r["x2"]
    assert r["xSame"] is True  # x (poster) sha256 unchanged
    assert r["dirs"] == ["poster", "poster-2"]  # no new skill created


def test_description_set_list_change_and_round_trip() -> None:
    r = report()["desc"]
    flat = 'Posters: "bold" titles second line: \'x\''  # #462 rule: newlines collapse to one space
    assert r.get("created") == {"saved": "Desc", "id": "desc", "description": flat}
    assert f"description: {json.dumps(flat)}\n" in r["md1"]
    assert r["md1"].split("---")[1].count("\n") == 3  # frontmatter stays name + description only
    assert r["list1"] == flat  # list returns the stored description, not instructions
    assert r["changed"]["description"] == 'New: "two"'
    assert r["read2"] == {**r["read2"], "description": 'New: "two"', "instructions": "Body"}  # instructions kept
    assert r["parsed"]["description"] == 'New: "two"' and r["parsed"]["name"] == "Desc"
    assert r["read3"]["description"] == 'New: "two"' and r["read3"]["instructions"] == "Body 2"  # description kept


def test_save_by_id_with_shared_name_updates_that_id() -> None:
    # Mutation m2 (id matched by name) trips this: the save lands on "poster", not "poster-2".
    r = report()["saveByIdShared"]
    assert "error" not in r, r
    assert r["savedId"] == "poster-2"
    assert r["x2"] is not None and "BY ID" in r["x2"]
    assert r["x1Same"] is True  # namesake "poster" byte-identical
    assert r["dirs"] == ["poster", "poster-2"]


def test_edit_tool_hint_addresses_by_id() -> None:
    # Mutation m7 (hint uses name="<name>") trips this.
    hint = report()["hint"]
    assert isinstance(hint, str), hint
    assert 'action="read", id="poster-2"' in hint
    assert 'action="save" with id="poster-2"' in hint
    assert 'name="Poster"' not in hint


def test_harness_did_not_crash() -> None:
    assert "fatal" not in report()


def test_mcp_schema_has_description_and_id() -> None:
    canvas = (ROOT / "api/mcp_tools/canvas.py").read_text()
    seg = canvas[canvas.index('"skill": _tool('):canvas.index('"custom_workflow"')]
    assert '"id": {"type": "string"}' in seg and '"description": {"type": "string"}' in seg


def test_edit_chat_entry_uses_id_when_484_present() -> None:
    # #484 is on main: its Edit-in-chat context must be built from skillEditToolHint (id="<id>"), never name="…".
    src = (ROOT / "src/skillEdit.ts").read_text()
    assert "${skillEditToolHint(skill)}" in src
    assert 'name="${skill.name}"' not in src and "exact same name" not in src
