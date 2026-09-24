from __future__ import annotations

from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def test_cached_restore_renders_lightweight_inventory_table() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    apply_method = _slice(source, "def _apply_server_library_payload", "def _create_next_version_from_server")
    assert 'cached_restore = bool(payload.get("cached_restore"))' in apply_method
    assert "self._server_inventory_table_enabled" in apply_method
    assert "should_rebuild_table = bool(" in apply_method


def test_visible_inventory_renderer_uses_lightweight_fixed_width_path() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    fast = _slice(source, "def _restore_cached_inventory_table_fast", "def _refresh_standard_table_overview")
    assert "not self._server_inventory_table_enabled" in fast
    assert "self._append_server_inventory_row(inventory, row=row)" in fast
    assert "_apply_fast_inventory_column_widths" in fast
    assert "_fit_standard_table_columns" not in fast


def test_cached_restore_skips_final_expensive_content_fit() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    apply_method = _slice(source, "def _apply_server_library_payload", "def _create_next_version_from_server")
    assert "if should_rebuild_table and not cached_restore:" in apply_method


def test_cached_snapshot_does_not_reload_marker_files_twice_in_page_restore() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    restore = _slice(source, "def _restore_cached_server_sync", "def _persist_server_library_settings")
    assert "load_cached_sync_snapshot(" in restore
    assert "self._refresh_local_classification_markers()" not in restore


def test_local_restore_status_explicitly_says_no_server_access() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "已从本机 AppData 缓存恢复" in source
    assert "未访问服务器" in source


def test_version_is_v218196() -> None:
    assert '__version__ = "2.18.198"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.198"' in Path("pyproject.toml").read_text(encoding="utf-8")
