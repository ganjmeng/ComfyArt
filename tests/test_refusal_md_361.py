"""#361 Content refusal: chat polite refuse + exactly 3 markdown bullets; no pills/toast; 0 charge."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
GUIDE = (ROOT / "bot/guide.py").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
MARKDOWN = (ROOT / "src/ui/Markdown.tsx").read_text()
AGENT = (ROOT / "src/ui/AgentPanel.tsx").read_text()
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()


def _assigned_strings(mod: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in mod.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node.value
    return out


def _string_expr(node: ast.AST, assigned: dict[str, ast.AST]) -> str:
    """Join string constants, including ``+ NAME`` when NAME is also a string constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _string_expr(node.left, assigned) + _string_expr(node.right, assigned)
    if isinstance(node, ast.Name):
        target = assigned.get(node.id)
        if target is None:
            raise AssertionError(f"{node.id} is not a string assignment in bot/guide.py")
        return _string_expr(target, assigned)
    raise AssertionError(f"AGENT_GUIDE is not a string expression ({type(node).__name__})")


def _guide_joined() -> str:
    """AGENT_GUIDE text, including a concatenated IMAGE_PROMPT_RULES constant."""
    mod = ast.parse(GUIDE)
    assigned = _assigned_strings(mod)
    if "AGENT_GUIDE" not in assigned:
        raise AssertionError("AGENT_GUIDE not found")
    return _string_expr(assigned["AGENT_GUIDE"], assigned)


def test_guide_requires_chat_refuse_and_three_markdown_bullets() -> None:
    g = _guide_joined()
    assert "trademarked" in g
    assert "exactly three markdown unordered list bullets" in g
    assert "可以帮你做这些替代方案" in g
    assert "你倾向哪种" in g
    assert "0 charge" in g
    assert "red error toast" in g
    assert "do NOT call any paid generation tool" in g
    assert "media hero unchanged" in g


def test_guide_forbids_chips_and_toast_on_refuse() -> None:
    g = _guide_joined()
    assert "never offer clickable suggestion chips or pill buttons for alternatives" in g
    assert "never use a red error toast as the primary refuse path" in g
    assert "never call ask_user" in g


def test_assistant_text_uses_markdown_not_chips_for_refuse() -> None:
    """Refuse alternatives render via Markdown text path; no refuse chip row."""
    ab = CHAT.split("export function AssistantBlocks")[1].split("\nexport function ")[0]
    assert "Markdown" in ab
    assert "#361" in ab
    assert "NEVER suggestion chips" in ab
    assert "refusalAlternatives" not in ab
    assert "refuseChips" not in ab
    assert "ca-refuse__chips" not in ab
    assert "suggestionChips" not in ab
    assert "b.type === 'text'" in ab and "Markdown" in ab


def test_markdown_renders_unordered_list_bullets() -> None:
    assert "<ul" in MARKDOWN or "ul>" in MARKDOWN or "ul key" in MARKDOWN
    assert r"(?:[-*]|\d+\.)" in MARKDOWN


def test_overlays_document_refusal_md_not_pills() -> None:
    assert "#361 Content refusal" in OVERLAYS
    assert "NEVER pill/chip" in OVERLAYS
    assert ".ca-md ul" in OVERLAYS


def test_no_composer_refuse_alternative_chips() -> None:
    """Placement is chat message flow — not composer chips for refuse alternatives."""
    assert "refuseChips" not in AGENT
    assert "refuseSuggest" not in AGENT
    assert "refusalChips" not in COMPOSER
    assert "ca-refuse__chips" not in COMPOSER
    assert "ca-composer__refuse" not in AGENT


def test_done_path_360_untouched() -> None:
    """#361 must not regress #360 Done prose + thumbs."""
    assert "function DoneFeedback" in CHAT
    assert "isMediaDoneMessage" in CHAT
    assert "ca-chat__feedback" in CHAT
    assert "prose next-step" in GUIDE
    assert "下一步建议" in GUIDE


def test_media_hero_untouched() -> None:
    """#361 must not regress #356/#358 media hero."""
    assert "ca-media-hero" in CHAT
    assert "mediaHero" in CHAT
    hero = OVERLAYS.split(".ca-media-hero {")[1].split("}")[0]
    assert "calc(var(--ca-process-col)" not in hero


def test_at_menu_362_out_of_scope_no_refuse_at_menu() -> None:
    """#362 @ menu + capsules stay out of this tip — no refuse-related @ menu wiring."""
    assert "refuseAtMenu" not in AGENT
    assert "refusalCapsule" not in AGENT
    assert "ca-at-refuse" not in AGENT
