from __future__ import annotations

from pathlib import Path


def test_main_window_keeps_original_eager_page_lifecycle() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "self.database_page = DatabasePage(self.user_settings)" in source
    assert "self.site_profile_page = SiteProfilePage(self.user_settings)" in source
    assert "defer_catalog_restore=True" not in source
    assert "self.pages = [" in source
    assert "self._restore_last_business_page()" in source
    assert "def _create_page(" not in source
    assert "def _ensure_page(" not in source


def test_symbol_catalog_restore_is_local_only() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    constructor = source[source.index("def __init__"):source.index("def on_page_activated")]
    assert "load_catalog=not self._defer_catalog_restore" in constructor
    cached = source[source.index("def _restore_cached_server_sync"):source.index("def _persist_server_library_settings")]
    assert "load_cached_sync_snapshot" in cached
    assert "RemoteSymbolLibraryService().sync(" not in cached
    assert "ReadOnlySshClient" not in cached
    assert "ClassificationRegistryService" not in cached


def test_central_config_remains_manual_only() -> None:
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    database = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    site = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    constructor = main[main.index("def __init__"):main.index("def _clear_legacy_managed_output_paths")]
    assert "fetch_connection_configs" not in constructor
    assert "ClassificationRegistryService" not in constructor
    assert "self.central_sync_button.clicked.connect" in database
    assert "self.central_sync_button.clicked.connect(self._sync_central_classification)" in site


def test_application_version_is_consistent() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    import re
    a = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    b = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert a is not None and b is not None
    assert a.group(1) == b.group(1)
