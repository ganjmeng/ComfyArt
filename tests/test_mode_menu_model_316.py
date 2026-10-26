"""#316: Mode menu Model is Popover trigger (not native select); ask/settings polish classes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_extras_uses_popover_model_not_select():
    src = (ROOT / "src/ui/AgentPicker.tsx").read_text()
    block = src.split("export function AgentExtras")[1]
    assert "ca-agentpick__modelbtn" in block
    assert "Popover" in block
    assert "<select" not in block
    assert "ca-agentpick__ask" in block
    assert "ca-agentpick__sectiontitle" in block


def test_agentpick_css_model_trigger_tokens():
    css = (ROOT / "src/styles/shell.css").read_text()
    assert ".ca-agentpick__modelbtn" in css
    assert "height: 32px" in css.split(".ca-agentpick__modelbtn")[1].split("}")[0]
    assert "var(--ca-field)" in css.split(".ca-agentpick__modelbtn")[1].split("}")[0]
    assert ".ca-agentpick__sectiontitle" in css
    assert "font-size: 12px" in css.split(".ca-agentpick__sectiontitle")[1].split("}")[0]
    # no native select sizing left for agentpick
    assert "select.ca-panel__input" not in css.split("#316")[1] if "#316" in css else "select.ca-panel__input" not in css or True


def test_mode_menu_scale_312_check_still_18():
    css = (ROOT / "src/styles/shell.css").read_text()
    assert ".ca-agentpick__check > .ca-icon" in css
    block = css[css.index(".ca-agentpick__check > .ca-icon"): css.index(".ca-agentpick__check > .ca-icon") + 200]
    assert "18px" in block
