from __future__ import annotations

from pathlib import Path

from g_file_studio.services.paths import app_cache_root, app_config_root, app_data_root


def test_main_window_automatically_constructs_all_business_pages() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "def showEvent(" in source
    assert "QTimer.singleShot(0, self._load_next_startup_page)" in source
    loader_start = source.index("def _load_next_startup_page")
    loader_end = source.index("def _finish_startup_page_loading", loader_start)
    loader = source[loader_start:loader_end]
    assert "self._ensure_page(page_index)" in loader
    assert "QTimer.singleShot(0, self._load_next_startup_page)" in loader

def test_startup_does_not_automatically_pull_central_configuration() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    database = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    site = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")

    # Central access remains user initiated.
    assert "_sync_from_central" not in source
    assert "_publish_to_central" not in source
    assert "self.central_sync_button.clicked.connect" in database
    assert "self.central_publish_button.clicked.connect" in database
    assert "self.central_sync_button.clicked.connect(self._sync_central_classification)" in site
    assert "self.central_publish_button.clicked.connect(self._publish_central_classification)" in site


def test_persistent_roots_are_outside_workspace() -> None:
    roots = (app_config_root(), app_cache_root(), app_data_root())
    for root in roots:
        assert "workspace" not in {part.casefold() for part in root.parts}


def test_workspace_is_not_used_for_persistent_settings_or_rules() -> None:
    files = (
        Path("g_file_studio/services/user_settings_service.py"),
        Path("g_file_studio/services/id_rule_service.py"),
        Path("g_file_studio/services/remote_symbol_library.py"),
        Path("g_file_studio/services/site_profile_service.py"),
    )
    for path in files:
        source = path.read_text(encoding="utf-8").casefold()
        assert "workspace/" not in source
        assert "workspace\\" not in source


def test_application_version_is_consistent() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = __import__("re").search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = __import__("re").search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None
    assert project_match is not None
    assert init_match.group(1) == project_match.group(1)
