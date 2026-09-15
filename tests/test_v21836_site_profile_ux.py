from pathlib import Path


def test_site_profile_core_actions_are_consolidated_and_standard_rows_are_table_driven():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("主操作")' not in source
    assert 'self.scan_action = self.profile_menu.addAction("为选中图元上传标准图元 G")' in source
    assert 'QPushButton("检查图元标准")' in source
    assert 'QPushButton("检查并升级")' not in source
    assert 'QPushButton("标准管理")' in source
    assert 'QGroupBox("图元标准")' in source
    assert 'self.profile_selector = WheelSafeComboBox()' in source
    assert 'self.profile_table' not in source
    assert 'QTableWidget(0, 17)' in source
    assert 'self._standard_specs = []' in source
    assert '"检查范围", "业务类型 / 设备类型", "检查对象 XML", "标准图元文件"' in source
    assert '"扫描图元 G 文件全名",' in source
    assert '"图形 G 发现 devref", "发现次数", "样本位置"' in source
    assert '"图元定位规则", "定位条件"' not in source
    assert '("SMART", "接地刀闸", "ZhaiWaiJieDiDaoZha", self.ground_combo' not in source
    assert '图形 G 图元发现（只发现候选，不生成标准）' in source


def test_site_profile_results_keep_report_and_anchor_safe_upgrade_language():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("图元标准检查")' in source
    assert 'QPushButton("查看检查报告")' in source
    assert "检查图元标准”不修改 G" in source
    assert 'self.correct_button = QPushButton("纠正标准问题")' in source
    assert "图元标准不一致" in source
