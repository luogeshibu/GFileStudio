from pathlib import Path

from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


def _profile() -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="JED-V1",
        site_name="JED",
        smart_lbs_devref="#smart_lbs.g:smart_lbs",
        smart_breaker_devref="#smart_cb.g:smart_cb",
    )


def test_symbol_standard_page_is_check_first_and_uses_one_standard_table():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'self.check_button = QPushButton("检查图元标准")' in source
    assert 'self.open_report_button = QPushButton("查看检查报告")' in source
    assert 'self.task.buttons_layout.insertWidget(0, self.check_button)' in source
    assert 'self.task.buttons_layout.insertWidget(1, self.correct_button)' in source
    assert 'self.task.buttons_layout.insertWidget(2, self.open_report_button)' in source
    assert 'self.task.open_button.setText("打开结果目录")' in source
    assert 'QGroupBox("图元标准")' in source
    assert 'self.profile_selector = WheelSafeComboBox()' in source
    assert 'self.profile_table' not in source
    assert 'self.editor_box' not in source
    assert 'self.task.log_view.setVisible(False)' in source


def test_discovery_queue_is_persistent_without_version_bump(tmp_path):
    service = SiteProfileService(tmp_path / "profiles.json")
    saved = service.upsert(_profile())
    assert saved.profile_version == 1
    updated = service.update_discovery_metadata(
        "JED-V1",
        catalog={"#new.g:new": {"devref": "#new.g:new", "element_tag": "Fuse", "count": 3}},
        decisions={"#new.g:new": "pending"},
    )
    assert updated is not None
    assert updated.profile_version == 1
    loaded = service.load_profiles()["JED-V1"]
    assert loaded.discovery_decisions["#new.g:new"] == "pending"
    assert loaded.discovery_catalog["#new.g:new"]["element_tag"] == "Fuse"


def test_discovery_decisions_only_keep_pending_and_ignored(tmp_path):
    service = SiteProfileService(tmp_path / "profiles.json")
    service.upsert(_profile())
    service.update_discovery_metadata(
        "JED-V1",
        decisions={"#a:a": "pending", "#b:b": "ignored", "#c:c": "invalid"},
    )
    loaded = service.load_profiles()["JED-V1"]
    assert loaded.discovery_decisions == {"#a:a": "pending", "#b:b": "ignored"}
