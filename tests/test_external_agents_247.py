"""#247: external agent setup guide in the mode menu, Agent Settings and docs (static, $0)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
SETTINGS = (ROOT / "src/ui/BotSettings.tsx").read_text()
PICKER = (ROOT / "src/ui/AgentPicker.tsx").read_text()
DOCS = ROOT / "docs-site"
PROVIDERS = ("claude-code", "codex", "qwen-code", "deepseek-harness")
LINKS = (
    "https://docs.claude.com/en/docs/claude-code/overview",
    "https://developers.openai.com/codex/cli",
    "https://github.com/QwenLM/qwen-code",
    "https://www.npmjs.com/package/@deepseek-ai/dsh",
)


def test_copy_zh_en():
    assert ZH["agentSetup.title"] == "外部 Agent" and EN["agentSetup.title"] == "External agents"
    assert ZH["agentSetup.desc"] == "用你电脑上已安装的 Agent 来操作画布。"
    assert EN["agentSetup.desc"] == "Use an agent installed on your computer to work on the canvas."
    assert (ZH["agentSetup.setUp"], EN["agentSetup.setUp"]) == ("去配置", "Set up")
    assert (ZH["agentSetup.connected"], EN["agentSetup.connected"]) == ("已连接", "Connected")
    assert (ZH["agentSetup.copy"], EN["agentSetup.copy"]) == ("复制", "Copy")
    assert (ZH["agentSetup.checkAgain"], EN["agentSetup.checkAgain"]) == ("重新检测", "Check again")
    assert (ZH["agentSetup.viewGuide"], EN["agentSetup.viewGuide"]) == ("查看教程", "View guide")
    assert {k for k in ZH if k.startswith("agentSetup.")} == {k for k in EN if k.startswith("agentSetup.")}


def test_official_links_and_guide_path():
    for p, link in zip(PROVIDERS, LINKS):
        assert re.search(rf"'?{p}'?: '{re.escape(link)}'", SETTINGS), p
    assert "AGENT_GUIDE_PATH = '/guides/external-agents'" in SETTINGS
    assert "/comfyart/mcp" in SETTINGS


def test_undetected_row_opens_setup_not_switch():
    block = PICKER[PICKER.index("ca-agentpick__setup"):][:400]
    assert "agentSetupFocusAtom.set(p.id)" in block and "botSettingsOpenAtom.set(true)" in block
    assert "setAgent" not in block and "pick(" not in block


def test_docs_pages_nav_and_links():
    nav = json.loads((DOCS / "docs.json").read_text())
    flat = json.dumps(nav)
    assert '"guides/external-agents"' in flat and '"zh/guides/external-agents"' in flat
    for page, prefix in (("guides", ""), ("zh/guides", "/zh")):
        text = (DOCS / page / "external-agents.mdx").read_text()
        for link in LINKS:
            assert link in text
        assert "/comfyart/mcp" in text and "PORT" in text
        assert not re.search(r"ws_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{16,}", text)
        for img in re.findall(r'src="(/images/[^"]+)"', text):
            assert (DOCS / img.lstrip("/")).is_file(), img
        for other in ("agent.mdx", "mcp.mdx"):
            assert f"{prefix}/guides/external-agents" in (DOCS / page / other).read_text()


def test_settings_modal_wider_and_tab_hint_contrast():
    css = (ROOT / "src/styles/shell.css").read_text()
    assert ".ca-modal__card.ca-botsettings" in css and "560px" in css
    canvas = (ROOT / "src/styles/canvas.css").read_text()
    hint = re.search(r"\.ca-bar__hint \{[^}]*\}", canvas).group(0)
    assert "--ca-muted" not in hint


def test_dist_has_setup():
    js = "".join(p.read_text(errors="ignore") for p in (ROOT / "dist/assets").glob("*.js"))
    assert "external-agents" in js and "ca-agentsetup" in js
