from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_profile_engine import apply_smart_profile_to_tree
from g_file_studio.services.site_profile_service import resolve_jeddah_classification_marker_roles

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
NORMAL_CB = "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"
TARGET_NORMAL_LBS = "#Load_Breaker_Switch_NO-SMART.zwk.icn.g:Load_Breaker_Switch_NO-SMART"
TARGET_NORMAL_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"


def _add_rmu(layer: ET.Element, *, x: int, smart: bool, lbs_devref: str, cb_devref: str):
    ET.SubElement(layer, "rect", id=str(2_000_000 + x), x=str(x), y="100", w="240", h="220", lc="255,0,0", lcc="#FF0000")
    ET.SubElement(layer, "BusDis", id=str(38_000_000 + x), x=str(x + 115), y="145", w="8", h="130", key_name=f"RMU_{x}_BUS")
    # Keep one canonical Y and Q so the protected RMU recognizer has the ordinary
    # 2L2T shape, then deliberately reverse the other pair.  The *replacement*
    # role must still come from each element's ORIGINAL icon/devref name.
    ET.SubElement(layer, "CBreakerDis", id=str(11_700_000 + x), x=str(x + 20), y="150", w="28", h="30", p_NameString="Y1", devref=lbs_devref)
    lbs = ET.SubElement(layer, "CBreakerDis", id=str(11_701_000 + x), x=str(x + 65), y="150", w="28", h="30", p_NameString="Q99", devref=lbs_devref)
    ET.SubElement(layer, "CBreakerDis", id=str(11_710_000 + x), x=str(x + 135), y="205", w="30", h="30", p_NameString="Q1", devref=cb_devref)
    cb = ET.SubElement(layer, "CBreakerDis", id=str(11_711_000 + x), x=str(x + 180), y="205", w="30", h="30", p_NameString="Y99", devref=cb_devref)
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id=str(18_800_000 + x), x=str(x + 185), y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id=str(8_000_000 + x), ts=str(22500 + x), x=str(x + 55), y="45", w="120", h="50")
    if smart:
        ET.SubElement(layer, "Text", id=str(8_100_000 + x), ts="SMART", x=str(x + 85), y="103", w="70", h="22", fs="20")
    return lbs, cb


def test_classification_markers_resolve_exact_four_jeddah_targets():
    entries = (
        ("Circuit_Breaker_SMART.zwk.icn.g", SMART_CB, "CIRCUIT_BREAKER_SMART"),
        ("Load_Breaker_Switch_SMART.zwk.icn.g", SMART_LBS, "LOAD_BREAKER_SWITCH_SMART"),
        ("Circuit_Breaker_NO-SMART.zwk.icn.g", TARGET_NORMAL_CB, "CIRCUIT_BREAKER_NO_SMART"),
        ("Load_Breaker_Switch_NON-SMART.zwk.icn.g", TARGET_NORMAL_LBS, "LOAD_BREAKER_SWITCH_NO_SMART"),
        ("Fuse_NON_SMART.zwk.icn.g", "#Fuse_NON_SMART.zwk.icn.g:Fuse", "FUSE"),
    )
    roles, issues = resolve_jeddah_classification_marker_roles(entries)
    assert issues == []
    assert roles["smart_breaker"] == SMART_CB
    assert roles["smart_lbs"] == SMART_LBS
    assert roles["normal_breaker"] == TARGET_NORMAL_CB
    assert roles["normal_lbs"] == TARGET_NORMAL_LBS


def test_duplicate_required_marker_is_rejected_instead_of_guessed():
    entries = (
        ("a.g", SMART_CB, "CIRCUIT_BREAKER_SMART"),
        ("b.g", "#Other.g:Other", "CIRCUIT_BREAKER_SMART"),
        ("lbs-smart.g", SMART_LBS, "LOAD_BREAKER_SWITCH_SMART"),
        ("cb-normal.g", TARGET_NORMAL_CB, "CIRCUIT_BREAKER_NO_SMART"),
        ("lbs-normal.g", TARGET_NORMAL_LBS, "LOAD_BREAKER_SWITCH_NO_SMART"),
    )
    roles, issues = resolve_jeddah_classification_marker_roles(entries)
    assert roles["smart_breaker"] == ""
    assert any("CIRCUIT_BREAKER_SMART" in item and "多个图元" in item for item in issues)


def test_smart_cabinet_uses_original_icon_name_not_y_q_label(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    lbs, cb = _add_rmu(layer, x=100, smart=True, lbs_devref=NORMAL_LBS, cb_devref=NORMAL_CB)
    tree = ET.ElementTree(root)

    result = apply_smart_profile_to_tree(
        tree,
        tmp_path / "JED.g",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=TARGET_NORMAL_LBS,
        normal_breaker_devref=TARGET_NORMAL_CB,
        authoritative_standard_devrefs={SMART_LBS, SMART_CB, TARGET_NORMAL_LBS, TARGET_NORMAL_CB},
        profile_geometry_templates={},
        allow_source_geometry_fallback=False,
        jeddah_variant_only=True,
        jeddah_strict_marker_targets=True,
    )

    # LBS has a misleading Q99 label but must remain LBS by original icon name.
    assert lbs.get("devref") == SMART_LBS
    # Circuit Breaker has a misleading Y99 label but must remain Circuit Breaker.
    assert cb.get("devref") == SMART_CB
    assert result.lbs_changed_count == 2
    assert result.breaker_changed_count == 2


def test_no_smart_cabinet_uses_explicit_no_smart_marker_targets_not_peer_guess(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    # A peer cabinet uses the historical NON-SMART revision. Strict marker mode must
    # NOT learn/keep that peer revision; the operator-marked NO-SMART target wins.
    _add_rmu(layer, x=100, smart=False, lbs_devref=NORMAL_LBS, cb_devref=NORMAL_CB)
    lbs, cb = _add_rmu(layer, x=500, smart=False, lbs_devref=SMART_LBS, cb_devref=SMART_CB)
    tree = ET.ElementTree(root)

    result = apply_smart_profile_to_tree(
        tree,
        tmp_path / "JED.g",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=TARGET_NORMAL_LBS,
        normal_breaker_devref=TARGET_NORMAL_CB,
        authoritative_standard_devrefs={SMART_LBS, SMART_CB, TARGET_NORMAL_LBS, TARGET_NORMAL_CB},
        profile_geometry_templates={},
        allow_source_geometry_fallback=False,
        jeddah_variant_only=True,
        jeddah_strict_marker_targets=True,
    )

    assert lbs.get("devref") == TARGET_NORMAL_LBS
    assert cb.get("devref") == TARGET_NORMAL_CB
    assert result.normal_lbs_changed_count >= 1
    assert result.normal_breaker_changed_count >= 1


def test_jeddah_ui_reads_local_markers_and_batch_enables_strict_marker_mode():
    page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    batch = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "load_classification_marker_entries" in page
    assert "classification_marker_entries=classification_marker_entries" in page
    for marker in (
        "CIRCUIT_BREAKER_SMART",
        "LOAD_BREAKER_SWITCH_SMART",
        "CIRCUIT_BREAKER_NO_SMART",
        "LOAD_BREAKER_SWITCH_NO_SMART",
    ):
        assert marker in page
    assert "jeddah_strict_marker_targets=bool(settings.classification_marker_entries)" in batch
