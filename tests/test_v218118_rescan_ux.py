from pathlib import Path


def test_full_rescan_action_sits_beside_ordinary_scan_and_starts_immediately():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("扫描当前版本候选")' in source
    assert 'QPushButton("全量重新扫描 → 新版本草稿")' in source
    assert 'discovery_actions.addWidget(self.discovery_scan_button)' in source
    assert 'discovery_actions.addWidget(self.rescan_new_version_button)' in source
    assert 'QTimer.singleShot(0, self._scan_graphic_symbol_candidates)' in source


def test_ordinary_scan_explains_ignored_candidates_and_new_version_path():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'ignored_count = sum(' in source
    assert '当前版本还保留 {ignored_count} 个“已忽略”候选决定' in source
    assert '全量重新扫描 → 新版本草稿' in source
