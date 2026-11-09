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
    """消息内主钮文案走 jobs.confirmOk（继续生成），不用 Start/Confirm 硬编码。"""
    assert "okLabel={t('jobs.confirmOk')}" in CHAT or 'okLabel={t("jobs.confirmOk")}' in CHAT
    assert CHAT.count("okLabel={t('jobs.confirmOk')}") + CHAT.count('okLabel={t("jobs.confirmOk")}') >= 2
    assert "okLabel={copy.confirm}" not in CHAT
    assert "okLabel={startLabel" not in CHAT
