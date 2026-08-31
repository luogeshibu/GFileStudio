from pathlib import Path


def test_station_jump_ui_uses_feeder_overview_wording() -> None:
    page = Path("g_file_studio/ui/pages/poke_page.py").read_text(encoding="utf-8")
    i18n = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")
    help_text = Path("g_file_studio/ui/help_content.py").read_text(encoding="utf-8")
    combined = page + i18n + help_text
    assert "站点跳转 Poke：跳转到对端变电站馈线总图" in combined
    assert "站点跳转 Poke：跳转到对端变电站单线图" not in combined
    assert "对端变电站馈线总图" in help_text
