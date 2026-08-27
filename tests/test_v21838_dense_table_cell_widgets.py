from pathlib import Path


def test_dense_table_reserves_height_for_embedded_widgets():
    helper = Path("g_file_studio/ui/table_layout.py").read_text(encoding="utf-8")
    site = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "minimum_row_height" in helper
    assert "cell_widget.sizeHint().height() + 8" in helper
    assert "cell_widget.minimumSizeHint().height() + 8" in helper
    assert "combo.setMinimumHeight(36)" in site
    assert "self.standard_table.setMinimumHeight(380)" in site
    assert "fit_known_dense_table(self.standard_table)" in site


def test_release_notes_are_consolidated():
    root = Path(".")
    assert (root / "RELEASE_NOTES.md").exists()
    assert not list(root.glob("RELEASE_NOTES_v*.md"))


def test_release_version_21838():
    assert '__version__ = "2.18.52"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.52"' in Path("pyproject.toml").read_text(encoding="utf-8")
