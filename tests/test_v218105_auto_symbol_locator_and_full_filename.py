from pathlib import Path

from g_file_studio.services.site_profile_service import _normalize_custom_symbols
from g_file_studio.services.symbol_discovery_service import _devref_file


def test_v218105_symbol_standard_ui_removes_manual_locator_columns():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "self.standard_table = QTableWidget(0, 17)" in source
    assert '"扫描图元 G 文件全名"' in source
    assert '"图元定位规则", "定位条件"' not in source
    assert "match_combo = WheelSafeComboBox()" not in source
    assert '"match_attr": "devref"' in source


def test_v218105_scanned_symbol_g_filename_is_full_devref_filename():
    devref = "#External_grounddisconnector_new.zwjddz.icn.g:External_grounddisconnector_new"
    assert _devref_file(devref) == "External_grounddisconnector_new.zwjddz.icn.g"
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "def _observed_symbol_g_filename(devref: str) -> str:" in source
    assert ".split(\":\", 1)[0].strip()" in source


def test_v218105_new_rows_auto_derive_locator_from_observed_devref():
    observed = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
    standard = "#Load_Breaker_Switch_V2.zwk.icn.g:Load_Breaker_Switch_V2"
    rows = _normalize_custom_symbols([{
        "uid": "lbs",
        "scope": "SMART",
        "role": "LBS",
        "element_tag": "CBreakerDis",
        "standard_devref": standard,
        "observed_devref": observed,
        "symbol_usage": "设备组成图元",
        "device_level": "设备内部部件",
    }])
    assert len(rows) == 1
    assert rows[0]["match_attr"] == "devref"
    assert rows[0]["match_value"] == observed


def test_v218105_symbol_standard_columns_fit_content_without_eliding():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "table.resizeColumnsToContents()" in source
    assert "header.setTextElideMode(Qt.TextElideMode.ElideNone)" in source
    assert "self.standard_table.setTextElideMode(Qt.TextElideMode.ElideNone)" in source
    assert "self.standard_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)" in source
    assert "QHeaderView.ResizeMode.ResizeToContents" in source
    assert "max(table.columnWidth(column), header.sectionSizeHint(column), 72)" in source


def test_v218105_legacy_non_devref_match_is_not_displayed_as_scanned_g_filename():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'if not observed_devref and legacy_match_attr == "devref":' in source
    assert 'observed_devref = str(entry.get("match_value", "")).strip()' in source
