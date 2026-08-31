from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = PROJECT_ROOT / "g_file_studio" / "ui" / "main_window.py"


def test_language_selector_uses_wheel_safe_combo_box() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")
    assert "from g_file_studio.ui.widgets import WheelSafeComboBox" in source
    assert "self.language_combo = WheelSafeComboBox()" in source
    assert "self.language_combo = QComboBox()" not in source

