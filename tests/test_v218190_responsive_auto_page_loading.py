from __future__ import annotations

from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def test_all_pages_still_load_automatically_without_user_click() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    constructor = _slice(source, "def __init__", "def _resolved_last_business_page_index")
    assert "self._startup_page_order" in constructor
    assert "range(self.PAGE_COUNT)" in constructor

    loader = _slice(source, "def _load_next_startup_page", "def _finish_startup_page_loading")
    assert "self._ensure_page(page_index)" in loader
    assert "QTimer.singleShot(0, self._load_next_startup_page)" in loader


def test_startup_no_longer_constructs_all_pages_in_one_blocking_loop() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "def _initialize_all_pages_once" not in source
    loader = _slice(source, "def _load_next_startup_page", "def _finish_startup_page_loading")
    assert "for page_index in range(self.PAGE_COUNT)" not in loader


def test_remembered_page_is_created_first_and_becomes_usable_early() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    constructor = _slice(source, "def __init__", "def _resolved_last_business_page_index")
    assert "self._startup_target_page" in constructor
    assert "self._startup_page_order = [" in constructor
    assert "self._startup_target_page," in constructor

    loader = _slice(source, "def _load_next_startup_page", "def _finish_startup_page_loading")
    assert "if page_index == self._startup_target_page" in loader
    assert "self._select_page(page_index)" in loader


def test_startup_page_creation_remains_local_only() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    startup = (
        _slice(source, "def __init__", "def _resolved_last_business_page_index")
        + _slice(source, "def showEvent", "def _clear_legacy_managed_output_paths")
    )
    for forbidden in (
        "fetch_connection_configs(",
        "fetch_classification(",
        "fetch_id_rules(",
        "ReadOnlySshClient(",
        "oracledb.connect(",
    ):
        assert forbidden not in startup


def test_application_version_is_consistent() -> None:
    import re
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
