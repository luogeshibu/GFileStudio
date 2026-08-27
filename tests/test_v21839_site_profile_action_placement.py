from pathlib import Path


def test_site_profile_keeps_daily_upgrade_action_in_results_and_scan_in_profile_menu():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'self.scan_action = self.profile_menu.addAction("扫描标准样本 / 创建标准")' in source
    assert 'self.scan_action.triggered.connect(self._scan_samples)' in source
    assert 'QGroupBox("主操作")' not in source
    assert 'self.check_button = QPushButton("只检查标准")' in source
    assert "self.execute_button" not in source
    assert 'self.task.buttons_layout.insertWidget(0, self.check_button)' in source
    assert 'self.scan_progress.setVisible(False)' in source
