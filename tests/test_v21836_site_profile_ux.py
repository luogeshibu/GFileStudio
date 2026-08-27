from pathlib import Path


def test_site_profile_core_actions_are_consolidated_and_standard_rows_are_table_driven():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("主操作")' not in source
    assert 'self.scan_action = self.profile_menu.addAction("扫描标准样本 / 创建标准")' in source
    assert 'QPushButton("检查图元标准")' in source
    assert 'QPushButton("检查并升级")' not in source
    assert 'QPushButton("标准管理")' in source
    assert 'QTableWidget(6, 12)' in source
    assert '["范围", "设备角色", "XML 元素", "标准图元 devref", "主体 ID", "w×h", "AlignCenter", "Pins", "匹配属性", "当前/旧图元匹配值", "置信度", "状态"]' in source
    assert '("SMART", "接地刀闸", "ZhaiWaiJieDiDaoZha", self.ground_combo' in source
    assert '("NORMAL", "接地刀闸", "ZhaiWaiJieDiDaoZha", self.normal_ground_combo' in source


def test_site_profile_results_keep_report_and_anchor_safe_upgrade_language():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("图元标准检查")' in source
    assert 'QPushButton("查看检查报告")' in source
    assert "只检查和告警，不修改 G" in source
    assert "图元标准不一致" in source
