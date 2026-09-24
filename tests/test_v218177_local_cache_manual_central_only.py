import re
from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def test_startup_and_page_opening_never_auto_pull_central_business_config() -> None:
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    constructor = _slice(main, "def __init__", "def _clear_legacy_managed_output_paths")
    assert "ClassificationRegistryService" not in constructor
    assert "fetch_connection_configs" not in constructor
    assert "symbol_classification.json" not in constructor
    assert "fetch_connection_configs" not in constructor
    assert "_sync_central_classification" not in constructor

    db = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    db_constructor = _slice(db, "def __init__", "def _field_label")
    assert "fetch_connection_configs" not in db_constructor
    assert "_sync_central_connection_config()" not in db_constructor
    assert "self._load_shared_connection_config()" in db_constructor

    symbols = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    finish = _slice(symbols, "def _finish_initial_load", "def _toggle_admin_mode")
    assert "ClassificationRegistryService().fetch" not in finish
    assert "_start_central_classification_sync" not in finish


def test_local_connection_saves_never_publish_or_pull_central() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    ssh_save = _slice(source, "def _save_file_server_config", "def _save_environment")
    db_save = _slice(source, "def _save_database_config", "def _save_config")
    for block in (ssh_save, db_save):
        assert "ClassificationRegistryService" not in block
        assert "fetch_connection_configs" not in block
        assert "publish_connection_configs" not in block
    assert "本机缓存" in source
    assert 'local_cache/file_server_source' in source
    assert 'local_cache/database_source' in source


def test_manual_connection_sync_overwrites_and_persists_local_cache() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    sync = _slice(source, "def _sync_central_connection_config", "def _on_central_connection_sync_result")
    result = _slice(source, "def _on_central_connection_sync_result", "def _publish_central_connection_config")
    assert "fetch_connection_configs" in sync
    assert "将覆盖当前本机连接配置" in sync
    assert "self._save_environment(show_message=False)" in result
    assert 'local_cache/file_server_source", "central"' in result
    assert 'local_cache/database_source", "central"' in result


def test_classification_is_local_cache_and_central_sync_is_manual_overwrite_only() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    save = _slice(source, "def _save_classification_markers", "def _central_registry_config")
    manual = _slice(source, "def _sync_central_classification", "def _on_central_publish_result")
    handler = _slice(source, "def _on_central_sync_result", "def _on_central_registry_error")

    assert "ClassificationRegistryService" not in save
    assert '_mark_local_classification_source("custom")' in save
    assert 'self.central_sync_button.clicked.connect(self._sync_central_classification)' in source
    assert "QMessageBox.question" in manual
    assert "ClassificationRegistryService().fetch" in manual
    assert "replace_classification_marker_payload" in manual
    assert "quiet" not in manual
    assert '_mark_local_classification_source("central"' in handler
    assert "中央配置已覆盖本机分类缓存" in handler


def test_application_version_is_consistent() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
