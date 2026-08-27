from pathlib import Path


def test_site_profile_uses_one_shared_g_input_and_has_report_button():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    # One InputSourceSelector instance is shared by profile learning and processing.
    assert source.count("self.source = InputSourceSelector(") == 1
    assert "self.sample_source" not in source
    assert "self.apply_source" not in source
    assert "待检查 G 文件" in source
    assert "扫描标准样本 / 创建标准" in source
    assert "检查并升级" not in source
    assert 'QPushButton("查看检查报告")' in source
    assert "_on_processing_result" in source
    assert source.index("self.output_path = PathRow(") > source.index("self.source = InputSourceSelector(")
    assert source.index("self.output_path = PathRow(") < source.index("apply_box = QGroupBox")


def test_site_profile_shared_source_is_used_for_scan_and_processing():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'validate_input_source(self, self.source, display_name="图元标准样本")' in source
    assert 'validate_input_source(self, self.source, display_name="图元标准检查输入"' in source
    assert 'source_path=self.source.path()' in source
    assert 'input_mode=self.source.mode()' in source
