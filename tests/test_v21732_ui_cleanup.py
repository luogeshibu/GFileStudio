from pathlib import Path


def test_id_rule_detected_button_removed_and_scan_still_auto_confirms():
    source = Path("g_file_studio/ui/pages/id_page.py").read_text(encoding="utf-8")
    assert "加入扫描发现的规则" not in source
    assert "是否现在逐个确认并加入模板？" in source
    assert "_confirm_detected_rules()" in source
    assert 'QPushButton("扫描当前G文件（只检查ID）")' in source
    assert 'QPushButton("打开报告")' in source


def test_small_element_scan_button_is_in_result_section_and_name_restored():
    source = Path("g_file_studio/ui/pages/small_element_page.py").read_text(encoding="utf-8")
    assert '"异常小尺寸图元检测"' in source
    assert 'self.scan_button = QPushButton("扫描异常图元")' in source
    assert 'result_actions.addWidget(self.scan_button)' in source
    assert 'self.task.run_button.hide()' in source
