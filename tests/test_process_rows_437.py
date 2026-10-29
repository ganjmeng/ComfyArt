"""#437 (#430 D): chat process rows follow the reference wording."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
ZH = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
PANEL = (ROOT / "src/ui/AgentPanel.tsx").read_text(encoding="utf-8")


def test_thought_done_row() -> None:
    assert ZH["chatMessage.thought"] == "思考完成"
    assert EN["chatMessage.thought"] == "Thought"
    assert "已思考" not in json.dumps(ZH, ensure_ascii=False)


def test_thinking_row_behind_one_flag_and_key() -> None:
    assert ZH["chatMessage.thinking"] == "思考中…" and EN["chatMessage.thinking"] == "Thinking…"
    assert "export const SHOW_THINKING_ROW = true" in CHAT
    assert "SHOW_THINKING_ROW ? t('chatMessage.thinking') : t('chatMessage.outputting')" in CHAT
    assert CHAT.count("t('chatMessage.thinking')") == 1
    for k in ("agentPanel.thinking",):
        assert k not in ZH and k not in EN and k not in PANEL


def test_plain_text_reply_only_outputting() -> None:
    assert ZH["chatMessage.outputting"] == "输出中…"
    assert "t('chatMessage.outputting')" in PANEL
    assert "b.type !== 'text' && b.type !== 'thinking'" in PANEL  # reasoning: the Thought row carries 输出中…, no second label


def test_generation_row_is_model_name() -> None:
    for blob in (EN, ZH):
        assert "chatMessage.imagesGenerated" not in blob
        assert "chatMessage.videoGenerated" not in blob
    assert "已生成图片" not in json.dumps(ZH, ensure_ascii=False)
    assert "if (opts?.model) return opts.model" in CHAT


def test_skill_and_search_rows() -> None:
    assert (ZH["chatMessage.skillReady"], EN["chatMessage.skillReady"]) == ("技能加载完成", "Skill ready")
    assert (ZH["chatMessage.webSearchDone"], EN["chatMessage.webSearchDone"]) == ("联网搜索结果", "Web search results")


def test_no_tidy_memory_row() -> None:
    assert "整理记忆" not in json.dumps(ZH, ensure_ascii=False)
