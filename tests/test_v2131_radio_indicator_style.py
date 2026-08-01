from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_checked_radio_uses_green_fill_with_white_center_dot_icon():
    theme = (ROOT / "g_file_studio/ui/theme.py").read_text(encoding="utf-8")
    icon = (ROOT / "resources/icons/radio_checked.svg").read_text(encoding="utf-8")

    assert 'image: url("__RADIO_CHECKED_ICON__")' in theme
    assert '.replace("__RADIO_CHECKED_ICON__", radio_checked_icon)' in theme
    assert 'fill="#0B7A5A"' in icon
    assert 'fill="#FFFFFF"' in icon
    assert 'r="3"' in icon
