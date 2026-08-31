from pathlib import Path


def test_site_profile_separates_authoritative_standard_upload_from_business_input():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    # Business inspection still has one InputSourceSelector. Authoritative standards
    # are uploaded separately for the selected role and cannot reuse business G.
    assert source.count("self.source = InputSourceSelector(") == 1
    assert "待检查 G 文件" in source
    assert "为选中角色上传标准图元 G" in source
    assert 'QFileDialog.getOpenFileName(' in source
    assert 'prepare_standard_file_records([path])' in source
    assert 'QPushButton("查看检查报告")' in source
    assert "_on_processing_result" in source
    assert source.index("self.output_path = PathRow(") > source.index("self.source = InputSourceSelector(")
    assert source.index("self.output_path = PathRow(") < source.index("apply_box = QGroupBox")


def test_business_source_is_used_only_for_processing_not_standard_learning():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'validate_input_source(self, self.source, display_name="图元标准检查输入"' in source
    assert 'source_path=self.source.path()' in source
    assert 'input_mode=self.source.mode()' in source
    assert 'validate_input_source(self, self.source, display_name="图元标准样本")' not in source
