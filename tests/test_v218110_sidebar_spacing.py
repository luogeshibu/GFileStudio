from pathlib import Path


def test_group_headers_have_dedicated_vertical_spacing_and_do_not_overlap_children() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "self.nav.setSpacing(2)" in source
    assert "header_item.setSizeHint(QSize(0, 74))" in source
    assert 'section_button.setFixedHeight(40)' in source
    assert 'header_container.setObjectName("navSectionContainer")' in source
    assert 'header_layout.setContentsMargins(0, 0, 0, 0)' in source
    assert 'self.nav.setItemWidget(header_item, header_container)' in source


def test_child_navigation_titles_are_indented_after_translation_without_polluting_source_text() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "def _apply_navigation_child_indent" in source
    assert 'indent = "\\u2003\\u2003"' in source
    assert "self._apply_navigation_child_indent()" in source
    assert "item.data(self.NAV_PAGE_ROLE) is None" in source
    assert 'item.text().lstrip(" \\t\\u2002\\u2003")' in source
    assert 'source_text = item.data(int(Qt.ItemDataRole.UserRole))' in source
    assert 'width = max(270, min(420, widest + 88))' in source
