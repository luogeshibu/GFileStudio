from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.models import InputMode
from g_file_studio.processors.smart_profile_processor import (
    SmartProfileProcessingSettings,
    process_smart_profile_consistency,
)
from g_file_studio.services.site_profile_service import SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
NORMAL_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"
WRONG_LBS = "#Legacy_LBS.zwk.icn.g:Legacy_LBS"


def _target(path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="1001_BUS")
    line = ET.SubElement(layer, "ConnectLine", id="34000001", d="145,165 120,165", x="120", y="165", w="25", h="1")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="145",
        y="150",
        w="28",
        h="30",
        p_NameString="Y1",
        devref=WRONG_LBS,
        node_area=f"0,1,{line.get('id')}",
    )
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000002",
        x="245",
        y="205",
        w="30",
        h="30",
        p_NameString="Q1",
        devref=SMART_CB,
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="1001", x="155", y="45", w="120", h="50")
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="185", y="103", w="70", h="22", fs="20")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _profile() -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="General RMU Standard",
        site_name="General",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
    )


def test_check_only_is_read_only_and_reports_nonstandard(tmp_path: Path):
    source = tmp_path / "target.g"
    _target(source)
    before = source.read_bytes()
    out = tmp_path / "run"
    result = process_smart_profile_consistency(
        SmartProfileProcessingSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=out,
            profile=_profile(),
        ),
        log=lambda _msg: None,
    )
    assert source.read_bytes() == before
    assert not (out / "final").exists()
    assert result.statistics["Mode"] == "CHECK"
    assert result.statistics["SMART LBS Changed"] == 1
    assert result.statistics["Nonstandard Symbols"] >= 1
    assert (out / "reports" / "symbol-standard-check.csv").exists()
    html = out / "reports" / "symbol-standard-check.html"
    assert html.exists()
    assert "NON-STANDARD" in html.read_text(encoding="utf-8")


def test_standard_check_is_check_only_and_emits_mismatch_warning(tmp_path: Path):
    source = tmp_path / "target.g"
    _target(source)
    before = source.read_bytes()
    out = tmp_path / "run"
    result = process_smart_profile_consistency(
        SmartProfileProcessingSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=out,
            profile=_profile(),
        ),
        log=lambda _msg: None,
    )
    assert source.read_bytes() == before
    assert not (out / "final").exists()
    assert result.statistics["Mode"] == "CHECK"
    assert result.statistics["Nonstandard Symbols"] >= 1
    assert any("本模块只告警和生成报告" in warning for warning in result.warnings)
    assert any("图元变体不符合标准" in warning for warning in result.warnings)
    assert (out / "reports" / "symbol-standard-check.html").exists()


def test_generic_module_is_check_only_and_moved_below_id_check():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    help_text = Path("g_file_studio/ui/help_content.py").read_text(encoding="utf-8")
    assert '("图元标准检查", "通用图元标准检查' in main
    assert 'super().__init__(\n            "图元标准检查"' in page
    assert 'self.check_button = QPushButton("检查图元标准")' in page
    assert 'self.execute_button' not in page
    assert 'apply_changes' not in page
    nav_id = main.index('("ID 检查与修复"')
    nav_check = main.index('("图元标准检查"')
    nav_rmu = main.index('("环网柜处理"')
    assert nav_id < nav_check < nav_rmu
    assert '"图元标准检查帮助"' in help_text
