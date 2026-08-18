from pathlib import Path


def test_manual_bus_group_dialog_uses_two_columns_and_stretches_filename():
    text = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    assert 'QTableWidget(len(names), 2)' in text
    assert 'setHorizontalHeaderLabels(["文件名", "母线组"])' in text
    assert 'setHorizontalHeaderLabels(["顺序", "文件名", "母线组"])' not in text
    assert 'setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)' in text
    assert 'table.item(row, 1).setText' in text
