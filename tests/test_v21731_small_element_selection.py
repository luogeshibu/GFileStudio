from pathlib import Path


def test_small_element_table_uses_checkbox_processing_and_cell_copy():
    source = Path("g_file_studio/ui/pages/small_element_page.py").read_text(encoding="utf-8")
    assert 'self.table = CopyableResultTable(0, 9)' in source
    assert '["处理", "文件", "元素类型", "XML ID", "X", "Y", "W", "H", "keyid"]' in source
    assert 'SelectionBehavior.SelectItems' in source
    assert 'QKeySequence.StandardKey.Copy' in source
    assert 'self.select_all_box = QCheckBox("全选处理")' in source
    assert 'self.process_button = QPushButton("删除选中异常图元")' in source
    assert '删除全部异常图元' not in source


def test_processing_keeps_original_scan_snapshot_and_does_not_accumulate():
    source = Path("g_file_studio/ui/pages/small_element_page.py").read_text(encoding="utf-8")
    assert 'delete_issues_to_output(selected, output_dir)' in source
    assert 'processed_issues' not in source
    assert 'cumulative_map' not in source
    assert 'self.issues = [x for x in self.issues' not in source
    assert '扫描结果仍保留' in source
