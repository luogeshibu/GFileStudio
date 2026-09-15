from pathlib import Path


def _source() -> str:
    return Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")


def test_symbol_standard_table_has_no_precreated_system_rows():
    source = _source()
    assert 'self.standard_table = QTableWidget(0, 17)' in source
    assert 'self._standard_specs = []' in source
    assert '("SMART", "LBS", "CBreakerDis"' not in source
    assert '前 6 行是现有 RMU 系统标准' not in source
    assert '为选中图元上传 / 更新标准 G' in source


def test_graphic_discovery_never_routes_candidates_to_builtin_rows():
    source = _source()
    assert 'def _builtin_row_for_discovery' not in source
    assert 'new_row = self._insert_custom_standard_row(self._discovery_entry(meta))' in source
    assert 'observed ``XML + devref`` is represented as the same kind of candidate row' in source


def test_legacy_fixed_roles_are_converted_to_generic_rows_for_compatibility():
    source = _source()
    assert 'def _profile_standard_rows(profile: SiteSmartProfile)' in source
    assert '("legacy-smart-lbs", "SMART", "LBS", "CBreakerDis", profile.smart_lbs_devref)' in source
    assert '("legacy-normal-lbs", "NORMAL", "LBS", "CBreakerDis", profile.normal_lbs_devref)' in source
    assert 'existing["scope"] = "ANY"' in source
    assert '"symbol_usage": "设备组成图元"' in source
    assert '"device_level": "设备内部部件"' in source


def test_new_save_path_persists_generic_rows_not_legacy_fixed_slots():
    source = _source()
    assert 'lbs = breaker = normal_lbs = normal_breaker = ground = normal_ground = ""' in source
    assert '请先扫描图形 G 发现图元候选' in source
    assert 'for entry in custom_symbols' in source
    assert 'role_errors.append(f"图元 {label}: 必须且只能绑定 1 个用户上传的标准图元 G。")' in source
