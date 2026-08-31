from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.models import InputMode
from g_file_studio.processors.smart_profile_processor import (
    SmartProfileProcessingSettings,
    process_smart_profile_consistency,
    process_smart_profile_correction,
)
from g_file_studio.services.site_profile_service import SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
WRONG_LBS = "#Legacy_LBS.zwk.icn.g:Legacy_LBS"


def _source(path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="1001_BUS")
    for index in range(1, 5):
        ET.SubElement(
            layer,
            "CBreakerDis",
            id=str(117000000 + index),
            x=str(130 + index * 25),
            y=str(145 + index * 20),
            w="28" if index < 4 else "30",
            h="30",
            p_NameString=f"Y{index}" if index < 4 else "Q1",
            devref=WRONG_LBS if index < 4 else SMART_CB,
        )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="1001", x="155", y="45", w="120", h="50")
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="185", y="103", w="70", h="22", fs="20")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _profile() -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="Progress Standard",
        site_name="General",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
    )


def _assert_realtime(values: list[int]) -> None:
    assert values
    assert values[0] == 0
    assert values[-1] == 100
    assert values == sorted(values)
    # A single G file must expose real internal work, not stay at 0/70 and jump to 100.
    assert len(set(values)) >= 12
    assert any(10 <= value <= 40 for value in values)
    assert any(41 <= value <= 80 for value in values)
    assert any(81 <= value < 100 for value in values)


def test_single_file_standard_check_reports_granular_progress(tmp_path: Path):
    source = tmp_path / "target.g"
    _source(source)
    values: list[int] = []
    process_smart_profile_consistency(
        SmartProfileProcessingSettings(source, InputMode.SINGLE_FILE, tmp_path / "check", _profile()),
        log=lambda _msg: None,
        progress=values.append,
    )
    _assert_realtime(values)


def test_single_file_correction_continues_progress_through_post_check(tmp_path: Path):
    source = tmp_path / "target.g"
    _source(source)
    values: list[int] = []
    process_smart_profile_correction(
        SmartProfileProcessingSettings(source, InputMode.SINGLE_FILE, tmp_path / "correct", _profile()),
        log=lambda _msg: None,
        progress=values.append,
    )
    _assert_realtime(values)
    # Regression for v2.18.80: correction used to park at 70% while the full post-check ran.
    assert any(63 <= value <= 90 for value in values)
    assert any(91 <= value < 100 for value in values)
