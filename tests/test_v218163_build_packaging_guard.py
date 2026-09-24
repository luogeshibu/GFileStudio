from __future__ import annotations

from pathlib import Path


def test_project_versions_are_synced_after_packaging_fix() -> None:
    root = Path(__file__).resolve().parents[1]
    init_text = (root / "g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    init_version = init_text.split('__version__ = "', 1)[1].split('"', 1)[0]
    project_version = pyproject.split('version = "', 1)[1].split('"', 1)[0]
    assert init_version == project_version


def test_build_script_guards_locked_package_and_supports_package_only() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "build_exe.ps1").read_text(encoding="utf-8")
    assert "[switch]$PackageOnly" in script
    assert "Assert-GFileStudioNotRunning" in script
    assert "Wait-DirectoryFilesUnlocked" in script
    assert "-ErrorAction Stop" in script
    assert "Test-ZipArchive" in script
    assert "Share package verified" in script
    assert "No valid share package was produced" in script
