"""Source contract: Agent PlanQuote/OverQuote stay in-message (no confirmAtom modal)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
INLINE = (ROOT / "src/ui/ChatInlineConfirm.tsx").read_text(encoding="utf-8")


def test_plan_over_quote_use_inline_card():
    assert "ChatInlineConfirm" in CHAT
    assert "testId=\"chat-inline-planquote\"" in CHAT or 'testId="chat-inline-planquote"' in CHAT
    assert "testId=\"chat-inline-overquote\"" in CHAT or 'testId="chat-inline-overquote"' in CHAT


def test_no_confirm_atom_from_quotes():
    # Quotes must not open the external modal path.
    assert "confirmAtom" not in CHAT


def test_inline_card_has_no_modal_scrim():
    assert "Modal" not in INLINE
    assert "createPortal" not in INLINE
    assert "ca-chat-confirm" in INLINE
