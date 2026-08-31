from pathlib import Path


def test_rmu_base_identification_is_first_and_mandatory():
    source = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert source.index("self._build_rmu_identification_options()") < source.index("self._build_rmu_options()")
    assert "self._build_rmu_poke_options()" not in source
    assert "Poke 跳转处理" in source
    assert 'QGroupBox("RMU 基础识别与汇总（必需）")' in source
    assert '识别范围（固定）' not in source
    assert '智能 / 非智能分类（固定开启）' not in source
    assert '每次运行固定识别全部有效 RMU' in source


def test_rmu_page_always_requests_summary_and_classification():
    source = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert 'identify_rmu_name_and_type=True' in source
    assert 'rmu_smart_in_type=True' in source
    assert 'export_rmu_identification_csv=True' in source
    assert '(self.rmu_summary_report_button, True, "rmu-summary-report.html")' in source
    assert 'self.user_settings.set_value("basic/rmu/identify_name_type", True)' in source
    assert 'self.user_settings.set_value("basic/rmu/smart_in_type", True)' in source


def test_foundation_exposes_marker_and_name_exclusion_configuration():
    source = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert '智能 RMU 标记字符：' in source
    assert 'SMART, SMR, NEWSMART, SMART-SE' in source
    assert '柜名排除字符串：' in source
    assert '你指定的字符绝不会作为 RMU 柜名候选' in source
