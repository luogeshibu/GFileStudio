from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    a = text.index(start)
    b = text.index(end, a)
    return text[a:b]


def test_lazy_host_keeps_placeholder_until_page_is_constructed() -> None:
    source = Path('g_file_studio/ui/main_window.py').read_text(encoding='utf-8')
    body = _slice(source, 'def _ensure_page', 'def _wire_page')
    assert body.index('page = self._create_page(page_index)') < body.index('while layout.count()')
    assert 'Construct first, then swap the widgets atomically' in body


def test_local_catalog_uses_borderless_loading_state_then_atomic_table_reveal() -> None:
    source = Path('g_file_studio/ui/pages/site_profile_page.py').read_text(encoding='utf-8')
    assert 'self.standard_table_loading = QLabel("正在加载本地图元缓存…")' in source
    assert 'self.standard_table.setVisible(not self._defer_catalog_restore)' in source
    assert 'self.standard_table_loading.setMinimumHeight(380)' in source
    assert 'self._restore_cached_inventory_table_fast(atomic_reveal=cached_restore)' in source
    assert 'self._restore_cached_inventory_table_fast(atomic_reveal=True)' in source
    finish = _slice(source, 'def _finish_inventory_table_render', 'def _refresh_standard_table_overview')
    assert 'self._set_local_catalog_loading_state(False)' in finish


def test_automatic_local_restore_has_no_modal_or_progress_dialog() -> None:
    source = Path('g_file_studio/ui/pages/site_profile_page.py').read_text(encoding='utf-8')
    restore = _slice(source, 'def _restore_catalog_after_activation', 'def _finish_initial_load')
    assert 'QMessageBox.' not in restore
    assert 'QProgressDialog(' not in restore
    assert 'server_library_progress.setVisible(True)' not in restore


def test_normal_200_row_cache_is_rendered_in_one_hidden_batch() -> None:
    source = Path('g_file_studio/ui/pages/site_profile_page.py').read_text(encoding='utf-8')
    assert 'self._inventory_render_batch_size = 500' in source
    render = _slice(source, 'def _render_next_inventory_batch', 'def _finish_inventory_table_render')
    assert 'len(rows) <= 500' in render
    assert '_inventory_atomic_reveal' in render


def test_version_is_218203() -> None:
    assert '__version__ = "2.18.203"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
