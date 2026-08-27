from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.models import InputMode
from g_file_studio.processors.smart_profile_processor import SmartProfileProcessingSettings, process_smart_profile_consistency
from g_file_studio.services.site_profile_service import SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
NORMAL_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"


def _target(path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="30907_BUS")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="145", y="150", w="28", h="30",
        p_NameString="Y1",
        key_name="Y1-RMU30907",
        devref=NORMAL_LBS,  # wrong variant inside SMART RMU
    )
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000002",
        x="245", y="205", w="30", h="30",
        p_NameString="Q1",
        devref=SMART_CB,
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="30907", x="155", y="45", w="120", h="50")
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="185", y="103", w="70", h="22", fs="20")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _profile() -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="JED-V1",
        site_name="JED",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
    )


def test_html_report_explains_each_nonstandard_element(tmp_path: Path):
    source = tmp_path / "target.g"
    _target(source)
    out = tmp_path / "run"
    result = process_smart_profile_consistency(
        SmartProfileProcessingSettings(source, InputMode.SINGLE_FILE, out, _profile()),
        log=lambda _msg: None,
    )
    assert result.statistics["Nonstandard Symbols"] == 1
    html = (out / "reports" / "symbol-standard-check.html").read_text(encoding="utf-8")
    assert "不符合标准明细" in html
    assert "为什么不符合" in html
    assert "SMART/NORMAL 图元变体错误" in html
    assert "当前 RMU 为 SMART" in html
    assert NORMAL_LBS in html
    assert SMART_LBS in html
    assert "117000001" in html
    assert "Y1" in html
    assert "只负责检查、告警和报告" in html


def test_detail_csv_contains_current_expected_and_reason(tmp_path: Path):
    source = tmp_path / "target.g"
    _target(source)
    out = tmp_path / "run"
    process_smart_profile_consistency(
        SmartProfileProcessingSettings(source, InputMode.SINGLE_FILE, out, _profile()),
        log=lambda _msg: None,
    )
    detail = out / "reports" / "symbol-standard-check-details.csv"
    assert detail.exists()
    with detail.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    row = rows[0]
    assert row["元素ID"] == "117000001"
    assert "SMART/NORMAL" in row["问题类型"]
    assert "当前 RMU 为 SMART" in row["不符合原因"]
    assert row["当前devref"] == NORMAL_LBS
    assert row["标准devref"] == SMART_LBS
