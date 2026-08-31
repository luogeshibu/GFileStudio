from pathlib import Path


def test_build_script_uses_runtime_version():
    text = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "g_file_studio.__version__" in text
    assert "GFileStudio_v2.17.1_Windows_x64.zip" not in text
    assert '$ZipName = "GFileStudio_v" + $Version + "_Windows_x64.zip"' in text


def test_project_versions_are_synced():
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "2.18.97"' in init_text
    assert 'version = "2.18.97"' in pyproject


def test_compact_branding():
    text = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert 'G File Studio · NARI 国际业务部' in text
    assert 'subtitle = QLabel("NARI 国际业务部")' in text
    assert 'grid_badge = QLabel("G 文件处理工具")' in text
    assert 'NARI 国际业务 XML 图形处理工具' not in text
