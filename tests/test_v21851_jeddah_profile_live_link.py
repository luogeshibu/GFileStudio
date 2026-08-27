from pathlib import Path


def test_jeddah_profile_combo_reloads_shared_active_standard():
    source = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    assert 'def refresh_profiles(self, preferred_name: str = "")' in source
    assert "def on_page_activated(self)" in source
    assert "self.refresh_profiles()" in source
    assert "self.profile_service.load_profiles().get(profile_name)" in source
    assert "当前 ACTIVE 图元标准" in source
    assert "连接锚点位置偏移" in source
    assert "profiles = SiteProfileService().load_profiles()" not in source


def test_symbol_standard_changes_notify_jeddah_page_immediately():
    profile_source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    main_source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "activeProfileChanged = Signal(str)" in profile_source
    assert "self.activeProfileChanged.emit(profile.profile_name)" in profile_source
    assert "self.activeProfileChanged.emit(restored.profile_name)" in profile_source
    assert 'self.activeProfileChanged.emit("")' in profile_source
    assert "self.site_profile_page.activeProfileChanged.connect(self.jeddah_batch_page.refresh_profiles)" in main_source
    assert 'getattr(page, "on_page_activated", None)' in main_source
