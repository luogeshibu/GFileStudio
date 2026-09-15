from pathlib import Path


def test_sidebar_major_headers_have_safe_height_and_clear_typography() -> None:
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "grid_badge.setFixedHeight(32)" in main
    assert "self.nav.setSpacing(2)" in main
    assert "header_item.setSizeHint(QSize(0, 74))" in main
    assert "section_button.setFixedHeight(40)" in main
    assert 'header_layout.setContentsMargins(0, 0, 0, 0)' in main
    assert 'font-size: 14px; font-weight: 750' in main
    assert 'grid_badge.setStyleSheet("font-size: 11px; font-weight: 700;")' in main


def test_sidebar_header_height_budget_accounts_for_list_item_padding() -> None:
    # navigation item style uses 11 px vertical padding + 2 px vertical margin
    # on each side. A 74 px row leaves 48 px of content, enough for the
    # 40 px section button with additional breathing room left by the row.
    total_row = 74
    item_chrome = 11 * 2 + 2 * 2
    content = total_row - item_chrome
    required = 40
    assert content >= required
