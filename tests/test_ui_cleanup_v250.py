from pathlib import Path


def test_frame_page_no_longer_contains_template_content_json_buttons():
    source = (
        Path(__file__).parents[1]
        / "g_file_studio"
        / "ui"
        / "pages"
        / "frame_page.py"
    ).read_text(encoding="utf-8")
    assert "内置模板内容配置" not in source
    assert "载入 JSON" not in source
    assert "保存 JSON" not in source


def test_group_box_titles_are_positioned_inside_cards():
    source = (
        Path(__file__).parents[1]
        / "g_file_studio"
        / "ui"
        / "theme.py"
    ).read_text(encoding="utf-8")
    assert "subcontrol-origin: padding" in source
    assert "top: 12px" in source
