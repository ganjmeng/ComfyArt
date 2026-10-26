"""#318: shared FieldSelect replaces remaining native <select> surfaces."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SURFACES = [
    "src/ui/AudioDialog.tsx",
    "src/ui/BotSettings.tsx",
    "src/ui/StyleToolbars.tsx",
    "src/ui/KitEditor.tsx",
    "src/ui/WorkflowsDialog.tsx",
]


def test_field_select_component_exists():
    src = (ROOT / "src/ui/FieldSelect.tsx").read_text()
    assert "export function FieldSelect" in src
    assert "Popover" in src
    assert "<select" not in src  # no JSX select tag
    assert "ca-fieldselect" in src
    assert "ca-menu__item" in src


def test_surfaces_import_field_select_and_have_no_native_select():
    for rel in SURFACES:
        text = (ROOT / rel).read_text()
        assert "FieldSelect" in text, rel
        assert "from './FieldSelect'" in text or 'from "./FieldSelect"' in text, rel
        assert "<select" not in text, f"{rel} still has <select"


def test_field_select_css_tokens():
    css = (ROOT / "src/styles/shell.css").read_text()
    assert "#318" in css
    assert ".ca-fieldselect" in css
    block = css.split(".ca-fieldselect {")[1].split("}")[0]
    assert "height: 32px" in block
    assert "var(--ca-field)" in block
    assert "var(--ca-border)" in block
    assert "border-radius: 8px" in block
    assert ".ca-fieldselect__menu" in css
    assert "max-width: 320px" in css.split(".ca-fieldselect__menu")[1].split("}")[0]


def test_kit_role_is_button_trigger_styles():
    kit = (ROOT / "src/styles/kit.css").read_text()
    assert ".ca-kit__role" in kit
    assert "ca-kit__role" in (ROOT / "src/ui/KitEditor.tsx").read_text()
    assert "<select" not in (ROOT / "src/ui/KitEditor.tsx").read_text()
    assert 'triggerClassName="ca-kit__role"' in (ROOT / "src/ui/KitEditor.tsx").read_text()
