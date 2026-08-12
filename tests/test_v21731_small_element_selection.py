from pathlib import Path


def test_small_element_table_uses_checkbox_processing_and_cell_copy():
    source = Path("g_file_studio/ui/pages/small_element_page.py").read_text(encoding="utf-8")
    assert 'self.table = CopyableResultTable(0, 9)' in source
    assert '["处理", "文件", "元素类型", "XML ID", "X", "Y", "W", "H", "keyid"]' in source
    assert 'SelectionBehavior.SelectItems' in source
    assert 'QKeySequence.StandardKey.Copy' in source
    assert 'self.select_all_box = QCheckBox("全选处理")' in source
    assert 'self.process_button = QPushButton("执行选中处理")' in source
    assert '删除选中异常图元' not in source
    assert '删除全部异常图元' not in source


def test_processed_rows_are_removed_immediately_and_processing_is_cumulative():
    source = Path("g_file_studio/ui/pages/small_element_page.py").read_text(encoding="utf-8")
    assert 'self.processed_issues: list[SmallElementIssue] = []' in source
    assert 'cumulative_map = {self._issue_key(x): x for x in self.processed_issues}' in source
    assert 'outputs = delete_issues_to_output(cumulative, output_dir)' in source
    assert 'self.issues = [x for x in self.issues if self._issue_key(x) not in selected_keys]' in source
    assert 'self._fill_table()' in source
    assert 'write_reports(output_dir, selected, self.threshold.value(), timestamp, report_kind="process")' in source
