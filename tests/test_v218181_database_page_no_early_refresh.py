from pathlib import Path

def test_database_page_does_not_refresh_before_status_widget_exists():
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    init_start = source.index("def __init__")
    next_method = source.index("    @staticmethod", init_start)
    ctor = source[init_start:next_method]
    widget = ctor.index("self.central_config_status = QLabel")
    refresh = ctor.index("self._refresh_local_cache_source_status()")
    assert widget < refresh
    assert "_refresh_local_cache_source_status()" not in ctor[:widget]

def test_refresh_uses_safe_getattr_guard():
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    start = source.index("def _refresh_local_cache_source_status")
    end = source.index("def _mark_local_connection_custom", start)
    method = source[start:end]
    assert 'getattr(self, "central_config_status", None)' in method
    assert "if status_label is None:" in method
