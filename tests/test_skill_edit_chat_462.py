"""#462 Edit in chat (reference behavior): new project titled 「修改X Skill」/"Edit X Skill", one auto-sent turn
(skill chip + 「我想修改这个 Skill」), mock agent reads/lists/asks, by-name save overwrites the original.
Harness: tests/js/skill_edit_chat_462.ts (in-memory user files, no LLM, no paid API)."""
from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
BOT = (ROOT / "src/botLayout.ts").read_text()
CSS = (ROOT / "src/styles/shell.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("e462") / "skill_edit_chat_462.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_edit_chat_462.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_dialog_opens_one_new_project_for_that_skill(got: dict) -> None:
    assert got["urls"] == 1
    assert got["params"] == {"project": True, "new": "1", "editSkill": "cafe1", "createSkill": None}


def test_new_project_title(got: dict) -> None:
    assert got["zh"]["titles"] == ["修改早安咖啡店海报生成器 Skill"]
    assert got["en"]["titles"] == ["Edit 早安咖啡店海报生成器 Skill"]


def test_exactly_one_auto_sent_message_with_skill_chip(got: dict) -> None:
    for lang, text in (("zh", "我想修改这个 Skill"), ("en", "I want to edit this Skill")):
        sends = got[lang]["sends"]
        assert len(sends) == 1
        assert sends[0]["text"] == text and sends[0]["skill"] == "早安咖啡店海报生成器"


def _bubble() -> str:
    # the user turn's bubble element, from its opening tag to its closing </div>
    i = CHAT.index('data-testid="user-bubble">')
    return CHAT[i:CHAT.index("</div>", i)]


def test_chip_is_name_only_icon_left_truncated_no_close() -> None:
    bubble = _bubble()
    # chip is a child of the bubble, not a sibling box above it; it comes before the text on the same line
    assert CHAT.count('data-testid="user-skill-chip"') == 1 and 'data-testid="user-skill-chip"' in bubble
    assert bubble.index('data-testid="user-skill-chip"') < bubble.index("{text}")
    chip = bubble[bubble.index("<span"):bubble.index("</span>)}") + 9]
    # icon left, then name only; no × and no 编辑 · / Edit · prefix
    assert '<span className="ca-icon">{PROCESS_ICONS.skill}</span><span className="ca-chip__name">{b.name}</span>' in chip
    assert "<button" not in chip and "t(" not in chip
    assert "text-overflow: ellipsis" in CSS[CSS.index(".ca-chip__name"):]
    # chip gives way first: it shrinks (huge flex-shrink, min-width) and truncates; the text keeps its line
    assert re.search(r"\.ca-chat__bubble--skill \{[^}]*display: flex", CSS)
    assert re.search(r"\.ca-chat__bubble--skill > \.ca-chip--skill \{[^}]*flex: 0 999 auto;[^}]*white-space: nowrap", CSS)
    assert re.search(r"\.ca-chat__bubble--skill > \.ca-chat__text \{[^}]*flex: 0 0 auto", CSS)


def test_chip_icon_is_the_process_line_skill_icon() -> None:
    # same component as the 技能加载完成 row: PROCESS_ICONS.skill (Icons.scrollText), not the file-shaped Icons.skill
    assert "  skill: Icons.scrollText," in CHAT[CHAT.index("const PROCESS_ICONS"):]
    assert "{Icons.skill}" not in _bubble()


def test_mock_agent_flow_reads_lists_then_asks(got: dict) -> None:
    kinds = [b["type"] for b in got["mockReply"]]
    assert kinds == ["thinking", "tool_use", "tool_result", "text"]
    assert got["mockReply"][1] == {"type": "tool_use", "name": "skill", "input": {"action": "read", "id": "cafe1"}}
    assert got["contextIds"] == {"readId": "cafe1", "saveId": "cafe1", "hasNameAddr": False}
    reply = got["mockReply"][3]["text"]
    assert "old rules" in reply and "notes.md" in reply and reply.rstrip().endswith("？")
    # process line: thinking → 思考完成, skill read → 技能加载完成
    assert "if (b.type === 'thinking') return 'thought'" in CHAT
    assert "if (n === 'skill' || n === 'Skill') return skillActionIsFileRead(b.input) ? 'skill_file_read' : 'skill'" in CHAT
    # the mock read has no path, so it is a skill load, not a file read
    assert "(action === 'read' && !!input?.path)" in CHAT and "path" not in got["mockReply"][1]["input"]
    assert ZH["chatMessage.thought"] == "思考完成" and ZH["chatMessage.skillReady"] == "技能加载完成"


def test_save_by_id_overwrites_original(got: dict) -> None:
    # #463: the agent skill tool (src/skills.ts skillTool, wired in botLayout) saves by the id from the context
    assert "skill: async (_editor, args) => skillTool(args)" in BOT
    assert got["reusedId"] == "cafe1"
    assert got["countBefore"] == got["countAfter"] == 2
    assert got["ids"] == ["cafe1", "other"]
    assert got["cafe"]["instructions"] == "new rules 9:16"
    assert got["cafe"]["description"] == "d" and got["cafe"]["files"] == {"notes.md": "n"}
