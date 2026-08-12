from pathlib import Path


def test_small_element_reports_are_timestamped_and_page_has_bulk_and_html_actions():
    engine = Path('g_file_studio/engines/small_element_engine.py').read_text(encoding='utf-8')
    page = Path('g_file_studio/ui/pages/small_element_page.py').read_text(encoding='utf-8')
    assert 'small-element-scan-report' in engine and 'small-element-process-report' in engine
    assert '异常小尺寸图元检测' in page
    assert 'self.select_all_box = QCheckBox("全选处理")' in page
    assert '打开报告' in page
    assert 'self.task.append_log' in page


def test_id_reports_are_timestamped_html_csv_and_scan_button_is_in_task_panel():
    processor = Path('g_file_studio/processors/id_processor.py').read_text(encoding='utf-8')
    page = Path('g_file_studio/ui/pages/id_page.py').read_text(encoding='utf-8')
    assert 'id-scan-report' in processor and 'id-repair-report' in processor
    assert 'self.task.buttons_layout.insertWidget(0, self.scan_button)' in page
    assert '打开报告' in page
    assert 'self.task.append_log(scan_text)' in page
    assert 'self.scan_summary' not in page
