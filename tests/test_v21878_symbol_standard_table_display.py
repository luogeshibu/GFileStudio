from pathlib import Path


def test_symbol_standard_table_shows_file_name_only_and_uses_exact_dense_profile():
    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    layout = Path("g_file_studio/ui/table_layout.py").read_text(encoding="utf-8")
    i18n = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")

    assert '"标准图元文件"' in page
    assert 'combo.addItem(filename, devref)' in page
    assert 'combo.addItem(f"{filename}  |  {devref}", devref)' not in page
    assert 'QTableWidget#symbolStandardTable { padding: 0px; }' in page
    assert 'headers=("检查范围", "设备角色", "XML 元素", "标准图元文件"' in layout
    assert '"标准图元文件": "Standard Symbol File"' in i18n
    assert 'source_item.setText("用户上传"' in page
