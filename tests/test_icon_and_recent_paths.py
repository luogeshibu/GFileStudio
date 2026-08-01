from __future__ import annotations

from pathlib import Path

from g_file_studio.services.user_settings_service import UserSettingsService


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


def test_user_settings_uses_independent_ini_file(tmp_path: Path) -> None:
    ini = tmp_path / "Config" / "user_settings.ini"
    service = UserSettingsService(ini)
    service.set_value("basic/input_mode", "single_file")
    service.set_path("basic/single_file_path", tmp_path / "a.sln.pic.g")

    assert ini.is_file()
    second = UserSettingsService(ini)
    assert second.get_value("basic/input_mode") == "single_file"
    assert second.get_path("basic/single_file_path") == tmp_path / "a.sln.pic.g"


def test_invalid_full_path_is_cleared_but_parent_can_be_used(tmp_path: Path) -> None:
    ini = tmp_path / "settings.ini"
    service = UserSettingsService(ini)
    missing = tmp_path / "existing" / "missing.sln.pic.g"
    missing.parent.mkdir()
    service.set_path("basic/single_file_path", missing)

    result = service.restore_path("basic/single_file_path", expect="file")
    assert result.path is None
    assert result.missing_path == missing
    assert service.get_path("basic/single_file_path") is None
    assert service.closest_existing_directory(missing) == missing.parent


def test_pages_use_complete_path_keys() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "g_file_studio" / "ui" / "pages").glob("*.py")
    )
    for key in (
        "basic/output_directory",
        "merge/input_directory",
        "merge/output_directory",
        "margin/output_directory",
        "frame/output_directory",
    ):
        assert key in sources


def test_input_selector_separates_complete_file_and_directory_paths() -> None:
    source = (
        PROJECT_ROOT
        / "g_file_studio"
        / "ui"
        / "widgets"
        / "input_source_selector.py"
    ).read_text(encoding="utf-8")
    assert "single_file_path" in source
    assert "directory_path" in source
    assert "input_mode" in source
