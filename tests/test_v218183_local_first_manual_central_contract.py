from __future__ import annotations

from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def test_every_business_page_is_created_automatically_at_startup() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    factory = _slice(source, "def _create_page", "def _ensure_page")
    loader = _slice(source, "def _load_next_startup_page", "def _finish_startup_page_loading")
    required = (
        "DatabasePage(self.user_settings)",
        "SmallElementPage(self.user_settings)",
        "IdPage(self.user_settings)",
        "SiteProfilePage(self.user_settings, defer_catalog_restore=False)",
        "RmuPage(self.user_settings)",
        "PokePage(self.user_settings)",
        "BasicPage(self.user_settings)",
        "MergePage(self.user_settings)",
        "MarginPage(self.user_settings)",
        "FramePage(self.user_settings)",
        "JeddahBatchPage(self.user_settings)",
        "OrthogonalizePage(self.user_settings)",
        "HelpPage()",
    )
    for expression in required:
        assert expression in factory
    assert "self._ensure_page(page_index)" in loader
    assert "QTimer.singleShot(0, self._load_next_startup_page)" in loader

def test_startup_never_reads_central_or_connects_remote_even_when_local_is_missing() -> None:
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    database = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    symbols = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")

    main_ctor = _slice(main, "def __init__", "def _clear_legacy_managed_output_paths")
    db_ctor = _slice(database, "def __init__", "def _field_label")
    symbol_ctor = _slice(symbols, "def __init__", "def on_page_activated")
    startup_blocks = (main_ctor, db_ctor, symbol_ctor)
    forbidden_calls = (
        "fetch_connection_configs(",
        "ClassificationRegistryService().fetch(",
        "fetch_admin_lease(",
        "_sync_central_connection_config()",
        "_sync_central_classification()",
        "ReadOnlySshClient(",
        ".test_connection()",
    )
    for block in startup_blocks:
        for call in forbidden_calls:
            assert call not in block

    # Remote server/catalog actions may be wired to visible buttons, but must not
    # be scheduled or invoked by page construction.
    assert "server_sync_button.clicked.connect" in symbol_ctor
    assert "QTimer.singleShot(0, self._start_server_symbol_sync" not in symbol_ctor
    assert "QTimer.singleShot(0, self._sync_central_classification" not in symbol_ctor


def test_manual_central_sync_is_the_only_overwrite_path() -> None:
    database = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    symbols = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")

    db_sync = _slice(database, "def _sync_central_connection_config", "def _on_central_connection_sync_result")
    db_result = _slice(database, "def _on_central_connection_sync_result", "def _publish_central_connection_config")
    assert "QMessageBox.question" in db_sync
    assert "fetch_connection_configs" in db_sync
    assert "将覆盖当前本机连接配置" in db_sync
    assert "self._save_environment(show_message=False)" in db_result

    class_sync = _slice(symbols, "def _start_central_classification_sync", "def _on_central_publish_result")
    class_result = _slice(symbols, "def _on_central_sync_result", "def _on_central_registry_error")
    assert "QMessageBox.question" in class_sync
    assert "ClassificationRegistryService().fetch" in class_sync
    assert "replace_classification_marker_payload" in class_sync
    assert "中央配置已覆盖本机分类缓存" in class_result


def test_persistent_state_roots_are_appdata_not_workspace() -> None:
    paths = Path("g_file_studio/services/paths.py").read_text(encoding="utf-8")
    settings = Path("g_file_studio/services/user_settings_service.py").read_text(encoding="utf-8")
    id_rules = Path("g_file_studio/services/id_rule_service.py").read_text(encoding="utf-8")
    symbols = Path("g_file_studio/services/remote_symbol_library.py").read_text(encoding="utf-8")
    profiles = Path("g_file_studio/services/site_profile_service.py").read_text(encoding="utf-8")
    repo = Path("g_file_studio/services/symbol_standard_repository.py").read_text(encoding="utf-8")

    assert "user_config_dir" in paths and "user_cache_dir" in paths and "user_data_dir" in paths
    assert "app_config_root" in settings
    assert "app_config_root" in id_rules
    assert "app_cache_root" in symbols
    assert "app_data_root" in profiles
    assert "app_data_root" in repo

    for source in (settings, id_rules, symbols, profiles, repo):
        lowered = source.casefold()
        assert "default_workspace" not in lowered
        assert "workspace/" not in lowered
        assert "workspace\\" not in lowered


def test_workspace_is_disposable_runtime_data_only() -> None:
    paths = Path("g_file_studio/services/paths.py").read_text(encoding="utf-8")
    assert 'for name in ("input", "remote_input", "processed", "merged", "adjusted", "work", "output", "runs")' in paths
    assert "Nothing persistent" in paths
    assert "workspace can be deleted safely" in paths


def test_user_habits_are_local_user_settings() -> None:
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert 'LAST_BUSINESS_PAGE_KEY = "navigation/last_business_page"' in main
    assert "self.user_settings.set_value(self.LAST_BUSINESS_PAGE_KEY" in main
    assert "self.user_settings.get_value(self.LAST_BUSINESS_PAGE_KEY" in main


def test_application_version_is_consistent() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    import re
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
