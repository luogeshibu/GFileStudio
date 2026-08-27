from pathlib import Path


def test_dense_table_layout_is_presentation_only_and_reused():
    helper = Path('g_file_studio/ui/table_layout.py').read_text(encoding='utf-8')
    site = Path('g_file_studio/ui/pages/site_profile_page.py').read_text(encoding='utf-8')
    i18n = Path('g_file_studio/i18n.py').read_text(encoding='utf-8')
    id_page = Path('g_file_studio/ui/pages/id_page.py').read_text(encoding='utf-8')

    assert 'ScrollBarAlwaysOn' in helper
    assert 'resizeColumnsToContents' in helper
    assert 'configure_known_dense_table(self.profile_table)' in site
    assert 'configure_known_dense_table(self.standard_table)' in site
    assert 'configure_known_dense_table(widget)' in i18n
    # Golden/protected ID feature source remains the legacy table implementation.
    assert 'self.table = QTableWidget(0, 7)' in id_page


def test_release_version_21837():
    assert '__version__ = "2.18.55"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.55"' in Path('pyproject.toml').read_text(encoding='utf-8')
