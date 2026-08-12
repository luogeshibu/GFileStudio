from pathlib import Path


def test_id_scan_and_repair_are_separate_actions_and_scan_writes_report():
    source = Path("g_file_studio/ui/pages/id_page.py").read_text(encoding="utf-8")
    assert 'self.scan_button = QPushButton("扫描当前G文件（只检查ID）")' in source
    assert 'self.task.run_button.setText("检查并强制修复 ID")' in source
    assert 'action = IdAction.REPAIR' in source
    assert '_write_id_reports(output_dir, report_rows, timestamp, report_kind="scan")' in source
    assert 'self.report_button.setEnabled(True)' in source
    assert 'self.scan_summary' not in source
    assert 'self._confirm_detected_rules()' in source


def test_small_element_result_table_is_copyable_and_result_actions_are_grouped():
    source = Path("g_file_studio/ui/pages/small_element_page.py").read_text(encoding="utf-8")
    assert 'class CopyableResultTable(QTableWidget)' in source
    assert 'QKeySequence.StandardKey.Copy' in source
    assert 'QApplication.clipboard().setText' in source
    assert '可单独选择 XML ID 或任意单元格/区域，按 Ctrl+C 复制' in source
    assert 'self.select_all_box = QCheckBox("全选处理")' in source
    assert 'self.process_button = QPushButton("执行选中处理")' in source
    assert 'self.task.buttons_layout.insertWidget(1, self.process_button)' in source
    assert '删除选中异常图元' not in source
    assert '删除全部异常图元' not in source
