from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_grid_theme_uses_green_operations_palette_and_grid_branding():
    theme = (ROOT / "g_file_studio" / "ui" / "theme.py").read_text(encoding="utf-8")
    main = (ROOT / "g_file_studio" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "#0b7a5a" in theme
    assert "#0a1f29" in theme
    assert 'QLabel#gridModeBadge' in theme
    assert "G 文件处理工具" in main
    assert "NARI 国际业务部" in main
    assert "G File Studio · NARI 国际业务部" in main
