from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_visual_hierarchy_uses_larger_text_and_clear_section_cards() -> None:
    source = (ROOT / "g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "sidebar.setFixedWidth(270)" in source
    assert 'font-size: 14px; font-weight: 560' in source
    assert 'font-size: 14px; font-weight: 750' in source
    assert 'background: #0e2a34' in source
    assert 'header_item.setSizeHint(QSize(0, 74))' in source
    assert 'width = max(270, min(420, widest + 88))' in source


def test_database_all_editable_connection_fields_are_wheel_safe() -> None:
    source = (ROOT / "g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert "self.username = WheelSafeLineEdit()" in source
    assert "self.password = WheelSafeLineEdit()" in source
    assert "self.host = WheelSafeLineEdit()" in source
    assert "self.service_name = WheelSafeLineEdit()" in source
    assert "self.port = IntegerInput(value=1521, minimum=1, maximum=65535)" in source
    assert "self.port = QSpinBox()" not in source
    assert "QLineEdit()" not in source


def test_database_wheel_safe_text_input_ignores_wheel_and_fields_are_larger() -> None:
    widget_source = (ROOT / "g_file_studio/ui/widgets/wheel_safe_line_edit.py").read_text(encoding="utf-8")
    database_source = (ROOT / "g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert "def wheelEvent" in widget_source
    assert "event.ignore()" in widget_source
    assert 'field.setMinimumHeight(38)' in database_source
    assert 'field.setStyleSheet("font-size: 14px;")' in database_source
    assert 'label.setStyleSheet("color:#28474e; font-size:14px;' in database_source
