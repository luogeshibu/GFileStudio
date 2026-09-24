import re
from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


def test_site_profile_startup_never_reads_central_configuration() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    finish = _slice(source, "def _finish_initial_load", "def _toggle_admin_mode")
    show = _slice(source, "def showEvent", "def hideEvent")

    forbidden = (
        "_refresh_admin_lease_status",
        "_sync_central_classification",
        "_start_central_classification_sync",
        "fetch_admin_lease",
        "ClassificationRegistryService().fetch",
    )
    for token in forbidden:
        assert token not in finish
        assert token not in show

    assert "def _auto_sync_central_classification_once" not in source
    assert "def _auto_sync_central_classification(" not in source


def test_connection_page_central_read_is_button_driven_only() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    constructor = _slice(source, "def __init__", "def _field_label")
    assert "fetch_connection_configs" not in constructor
    assert 'self.central_sync_button.clicked.connect(self._sync_central_connection_config)' in constructor

    sync = _slice(source, "def _sync_central_connection_config", "def _on_central_connection_sync_result")
    assert "fetch_connection_configs" in sync
    assert "将覆盖当前本机连接配置" in sync


def test_manual_classification_sync_remains_explicit() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'self.central_sync_button.clicked.connect(self._sync_central_classification)' in source
    manual = _slice(source, "def _sync_central_classification", "def _start_central_classification_sync")
    assert "self._start_central_classification_sync()" in manual
    start = _slice(source, "def _start_central_classification_sync", "def _on_central_publish_result")
    assert "QMessageBox.question" in start
    assert "quiet" not in start
    assert "confirm" not in start


def test_application_version_is_consistent() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    pyproject_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None
    assert pyproject_match is not None
    assert init_match.group(1) == pyproject_match.group(1)
