from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WIDGETS_ROOT = PROJECT_ROOT / "g_file_studio" / "ui" / "widgets"


def test_business_widgets_do_not_instantiate_raw_qcombobox() -> None:
    """业务界面应统一使用防滚轮下拉框。"""
    offenders: list[str] = []
    for path in WIDGETS_ROOT.glob("*.py"):
        if path.name == "wheel_safe_combo_box.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "QComboBox()" in text:
            offenders.append(path.name)
    assert offenders == []


def test_wheel_safe_combo_ignores_closed_wheel_events() -> None:
    source = (WIDGETS_ROOT / "wheel_safe_combo_box.py").read_text(encoding="utf-8")
    assert "self.view().isVisible()" in source
    assert "event.ignore()" in source
