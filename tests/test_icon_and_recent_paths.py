from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_green_icon_resources_are_included() -> None:
    ico = PROJECT_ROOT / "resources" / "icons" / "app.ico"
    png = PROJECT_ROOT / "resources" / "icons" / "app.png"
    assert ico.is_file() and ico.read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert png.is_file() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pyinstaller_uses_custom_icon() -> None:
    script = (PROJECT_ROOT / "build_exe.ps1").read_text(encoding="utf-8")
    assert 'resources\\icons\\app.ico' in script
    assert '--icon "$IconPath"' in script
    assert '--add-data "resources;resources"' in script


def test_application_sets_window_icon() -> None:
    source = (PROJECT_ROOT / "g_file_studio" / "app.py").read_text(encoding="utf-8")
    assert "app.setWindowIcon(icon)" in source
    assert "window.setWindowIcon(icon)" in source
    assert "SetCurrentProcessExplicitAppUserModelID" in source


def test_recent_directory_service_uses_qsettings() -> None:
    source = (
        PROJECT_ROOT
        / "g_file_studio"
        / "services"
        / "user_settings_service.py"
    ).read_text(encoding="utf-8")
    assert "QSettings" in source
    assert "missing_saved_directory" in source
    assert "self._settings.sync()" in source


def test_pages_use_separate_recent_path_keys() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "g_file_studio" / "ui" / "pages").glob("*.py")
    )
    for key in (
        "recent_paths/basic/output_directory",
        "recent_paths/merge/input_directory",
        "recent_paths/merge/output_directory",
        "recent_paths/frame/output_directory",
        "recent_paths/pipeline/output_directory",
    ):
        assert key in sources


def test_input_selector_separates_file_and_directory_history() -> None:
    source = (
        PROJECT_ROOT
        / "g_file_studio"
        / "ui"
        / "widgets"
        / "input_source_selector.py"
    ).read_text(encoding="utf-8")
    assert "single_file_directory" in source
    assert "input_directory" in source
