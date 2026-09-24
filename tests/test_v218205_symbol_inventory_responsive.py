from pathlib import Path


def _source() -> str:
    return Path('g_file_studio/ui/pages/site_profile_page.py').read_text(encoding='utf-8')


def test_inventory_uses_visible_only_natural_width_cache_and_fills_viewport() -> None:
    source = _source()
    assert 'self._inventory_visible_columns = (3, 5, 6, 7, 8, 9, 18)' in source
    assert 'self._inventory_natural_widths: dict[int, int] = {}' in source
    start = source.index('def _measure_inventory_natural_widths')
    end = source.index('def _restore_cached_inventory_table_fast', start)
    body = source[start:end]
    assert 'resizeColumnsToContents' not in body
    assert 'for column in self._inventory_visible_columns' in body
    assert 'for row in range(table.rowCount())' in body
    assert 'if available > total:' in body
    assert 'table.setColumnWidth' in body
    assert 'ScrollBarAlwaysOn' in source


def test_inventory_refits_on_real_viewport_resize_without_rescanning_rows() -> None:
    source = _source()
    assert 'self.standard_table.viewport().installEventFilter(self)' in source
    event_start = source.index('def eventFilter')
    event_end = source.index('def _ensure_machine_id', event_start)
    event_body = source[event_start:event_end]
    assert 'watched is self.standard_table.viewport()' in event_body
    assert 'QEvent.Type.Resize' in event_body
    assert 'self._schedule_inventory_width_update()' in event_body
    schedule_start = source.index('def _schedule_inventory_width_update')
    schedule_end = source.index('def resizeEvent', schedule_start)
    schedule_body = source[schedule_start:schedule_end]
    assert '_apply_fast_inventory_column_widths()' in schedule_body
    assert 'rowCount' not in schedule_body


def test_inventory_final_reveal_measures_content_once() -> None:
    source = _source()
    start = source.index('def _finish_inventory_table_render')
    end = source.index('def _refresh_standard_table_overview', start)
    body = source[start:end]
    assert '_apply_fast_inventory_column_widths(recompute_content=True)' in body


def test_version_218205() -> None:
    assert '__version__ = "2.18.205"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.205"' in Path('pyproject.toml').read_text(encoding='utf-8')
