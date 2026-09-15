from pathlib import Path


def test_id_rule_dense_table_reserves_six_visible_rows_without_touching_id_business_page():
    helper = Path("g_file_studio/ui/table_layout.py").read_text(encoding="utf-8")
    id_page = Path("g_file_studio/ui/pages/id_page.py").read_text(encoding="utf-8")

    assert "minimum_visible_rows: int | None = None" in helper
    assert "minimum_visible_rows=6" in helper
    assert "profile.minimum_visible_rows * profile.minimum_row_height" in helper
    assert "table.setMinimumHeight(" in helper
    # Keep the protected feature page/business wiring unchanged; this release is presentation-only.
    assert 'self.table = QTableWidget(0, 7)' in id_page


def test_release_version_218132():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
