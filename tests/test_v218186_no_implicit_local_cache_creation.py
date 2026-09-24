from __future__ import annotations

from pathlib import Path

from g_file_studio.services.id_rule_service import DEFAULT_RULES, IdRuleService
from g_file_studio.services.remote_symbol_library import RemoteSymbolLibraryService
from g_file_studio.services.site_profile_service import SiteProfileService
from g_file_studio.services.symbol_standard_repository import SymbolStandardRepository
from g_file_studio.services.user_settings_service import UserSettingsService


def test_user_settings_read_does_not_create_file_or_parent(tmp_path: Path) -> None:
    ini = tmp_path / "Config" / "user_settings.ini"
    service = UserSettingsService(ini)
    assert service.get_value("missing/key", "") == ""
    assert not ini.exists()
    assert not ini.parent.exists()


def test_user_settings_write_suspension_does_not_create_cache(tmp_path: Path) -> None:
    ini = tmp_path / "Config" / "user_settings.ini"
    service = UserSettingsService(ini)
    service.set_writes_enabled(False)
    service.set_value("database/oracle_host", "127.0.0.1")
    service.clear("database/oracle_host")
    assert not ini.exists()
    assert not ini.parent.exists()

    service.set_writes_enabled(True)
    service.set_value("database/oracle_host", "127.0.0.1")
    assert ini.is_file()


def test_id_rules_use_in_memory_defaults_without_creating_json(tmp_path: Path) -> None:
    path = tmp_path / "Config" / "id_rules.json"
    service = IdRuleService(path)
    rules = service.load_rules()
    assert set(rules) >= {rule.tag for rule in DEFAULT_RULES}
    assert not path.exists()
    assert not path.parent.exists()


def test_remote_symbol_reads_do_not_create_cache_tree(tmp_path: Path) -> None:
    cache_root = tmp_path / "Cache" / "SymbolLibrary"
    service = RemoteSymbolLibraryService(cache_root=cache_root)
    library = service.library_dir("172.16.21.27", "/home/up8000/data/graph/element")
    assert not library.exists()
    snapshot = service.load_cached_sync_snapshot(
        host="172.16.21.27",
        root="/home/up8000/data/graph/element",
    )
    assert snapshot.get("server_file_records", []) == []
    assert not cache_root.exists()


def test_site_profile_read_does_not_create_profile_or_repository_tree(tmp_path: Path) -> None:
    profile_path = tmp_path / "Data" / "site_smart_profiles.json"
    service = SiteProfileService(profile_path)
    assert service.load_profiles() == {}
    assert not profile_path.exists()
    assert not profile_path.parent.exists()


def test_symbol_repository_constructor_is_side_effect_free(tmp_path: Path) -> None:
    root = tmp_path / "Data" / "SymbolRepository"
    repository = SymbolStandardRepository(root)
    assert repository.root == root
    assert not root.exists()


def test_startup_disables_local_persistence_while_pages_are_built() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    start = source.index("def _load_next_startup_page")
    end = source.index("def _finish_startup_page_loading", start)
    method = source[start:end]
    assert "self.user_settings.set_writes_enabled(False)" in method
    assert "self.user_settings.set_writes_enabled(True)" in method
    assert "self._ensure_page(page_index)" in method


def test_missing_connection_config_is_not_replaced_with_factory_values() -> None:
    database = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    widget = Path("g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    assert 'get_value("remote_g_source/host", "").strip()' in database
    assert 'get_value("remote_g_source/username", "").strip()' in database
    assert 'get_value("remote_g_source/password", "")' in database
    assert 'get_value("remote_g_source/remote_directory", "").strip()' in database
    assert 'self._saved("host", "")' in widget
    assert 'self._saved("username", "")' in widget
    assert 'self._saved("password", "")' in widget
    assert 'self._saved("remote_directory", "")' in widget


def test_machine_id_is_lazy_and_not_created_during_page_construction() -> None:
    database = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    site = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'self._machine_id = self.user_settings.get_value("access_control/machine_id", "").strip()' in database
    assert 'def _ensure_machine_id(self)' in database
    assert 'self._machine_id = self.user_settings.get_value("access_control/machine_id", "").strip()' in site
    assert 'def _ensure_machine_id(self)' in site


def test_application_version_is_consistent() -> None:
    import re
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
