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


def test_inline_primary_uses_jobs_confirm_ok():
    """Plan-quote title, Generate, and Cancel follow the UI language.
    The after-cancel suffix is chatMessage.canceled (已取消 / Canceled), not a
    hardcoded English word. Over-quote still uses jobs.confirmOk too."""
    assert "okLabel={t('jobs.confirmOk')}" in CHAT or 'okLabel={t("jobs.confirmOk")}' in CHAT
    assert "okLabel={copy.confirm}" not in CHAT
    assert "okLabel={startLabel" not in CHAT
    assert "function planQuoteChrome()" in CHAT
    assert "t('jobs.confirmTitle')" in CHAT and "t('common.cancel')" in CHAT
    assert "t('chatMessage.canceled')" in CHAT
    assert 'title="Confirm cost"' not in CHAT and "title='Confirm cost'" not in CHAT
    assert ">Generate<" not in CHAT and ">Cancel<" not in CHAT and ">Canceled<" not in CHAT
