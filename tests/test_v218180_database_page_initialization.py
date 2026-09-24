from __future__ import annotations

from pathlib import Path
import re


def test_database_page_initialization_order_is_safe() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    init_start = source.index("def __init__")
    next_method = source.index("    @staticmethod", init_start)
    constructor = source[init_start:next_method]

    # The status widget must exist before any refresh call.
    widget_pos = constructor.index("self.central_config_status = QLabel")
    load_pos = constructor.index("self._load_shared_connection_config()")
    refresh_pos = constructor.index("self._refresh_local_cache_source_status()", load_pos)
    assert widget_pos < load_pos < refresh_pos

    # The old premature call before super()/widget construction must not exist.
    prefix = constructor[:widget_pos]
    assert "_refresh_local_cache_source_status()" not in prefix


def test_cache_status_refresh_has_defensive_widget_guard() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    method_start = source.index("def _refresh_local_cache_source_status")
    method_end = source.index("def _mark_local_connection_custom", method_start)
    method = source[method_start:method_end]
    assert 'getattr(self, "central_config_status", None)' in method
    assert "if status_label is None:" in method
    assert "return" in method


def test_application_version_is_consistent() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    import re
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
