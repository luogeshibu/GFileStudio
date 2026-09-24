from __future__ import annotations

from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def test_main_window_paints_before_page_hydration() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "QTimer.singleShot(60, self._load_next_startup_page)" in source
    assert "QTimer.singleShot(12, self._load_next_startup_page)" in source
    assert "SiteProfilePage(self.user_settings, defer_catalog_restore=True)" in source


def test_inventory_header_never_uses_continuous_resize_to_contents() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    setup = _slice(source, "self.standard_table = QTableWidget", "standard_layout.addWidget(self.standard_table)")
    assert "QHeaderView.ResizeMode.Interactive" in setup
    assert "QHeaderView.ResizeMode.ResizeToContents" not in setup
    assert "configure_responsive_table(self.standard_table)" not in setup
    assert "header.moveSection" not in setup


def test_cached_inventory_allocates_rows_once_instead_of_insert_per_record() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    fast = _slice(source, "def _restore_cached_inventory_table_fast", "def _refresh_standard_table_overview")
    assert "table.setRowCount(len(self._server_file_inventory))" in fast
    assert "for row, inventory in enumerate(self._server_file_inventory):" in fast
    assert "self._append_server_inventory_row(inventory, row=row)" in fast
    assert "table.insertRow" not in fast


def test_hidden_profile_initializer_cannot_wipe_restored_inventory() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    method = _slice(source, "def _new_profile", "def _global_profile_summary")
    assert "if self._server_inventory_table_enabled and self._server_file_inventory:" in method
    assert "self._restore_cached_inventory_table_fast()" in method
    assert "else:" in method
    assert "self._clear_custom_standard_rows()" in method


def test_release_version_is_v218198() -> None:
    assert '__version__ = "2.18.198"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.198"' in Path("pyproject.toml").read_text(encoding="utf-8")
