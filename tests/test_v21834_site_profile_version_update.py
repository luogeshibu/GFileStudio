from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_icon_geometry import (
    SmartIconGeometryTemplate,
    apply_devref_preserving_anchors,
    connected_anchor_points,
)
from g_file_studio.engines.smart_profile_engine import scan_smart_profile_samples
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile

SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
NORMAL_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"
NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
NEW_SMART_CB = "#RMU_BRK_S.zwk.icn.g:RMU_BRK_S"


def _profile(*, smart_cb: str = SMART_CB, geometry=None) -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="Jeddah",
        site_name="Jeddah",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=smart_cb,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
        geometry_templates=geometry or {},
    )


def test_profile_versions_are_archived_and_can_be_restored_as_new_active(tmp_path: Path):
    service = SiteProfileService(tmp_path / "profiles.json")
    v1 = service.upsert(_profile())
    v2 = service.upsert(_profile(smart_cb=NEW_SMART_CB))

    versions = service.load_profile_versions("Jeddah")
    assert [item.profile_version for item in versions] == [1, 2]
    assert v1.profile_version == 1
    assert v2.profile_version == 2
    assert versions[0].smart_breaker_devref == SMART_CB
    assert versions[1].smart_breaker_devref == NEW_SMART_CB

    restored = service.restore_version("Jeddah", 1)
    assert restored.profile_version == 3
    assert restored.smart_breaker_devref == SMART_CB
    assert service.load_profiles()["Jeddah"].profile_version == 3
    assert [item.profile_version for item in service.load_profile_versions("Jeddah")] == [1, 2, 3]


def test_same_devref_can_be_restandardized_when_profile_geometry_changes():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    top = ET.SubElement(layer, "ConnectLine", id="1", d="22,14 22,0", x="22", y="0", w="1", h="14")
    bottom = ET.SubElement(layer, "ConnectLine", id="2", d="22,34 22,50", x="22", y="34", w="1", h="16")
    q = ET.SubElement(
        layer,
        "CBreakerDis",
        id="3",
        x="10",
        y="10",
        w="28",
        h="28",
        rotate="0",
        tfr="rotate(0) scale(1,1)",
        devref=SMART_CB,
        node_area="0,0,1;1,0,2",
    )
    elements = list(root.iter())
    by_id = {element.get("id"): element for element in elements if element.get("id")}
    before = connected_anchor_points(q, by_id)
    template = SmartIconGeometryTemplate(
        devref=SMART_CB,
        rotation=0,
        width=30.0,
        height=30.0,
        anchor_offsets=((18.0, 6.0), (18.0, 26.0)),
    )

    result = apply_devref_preserving_anchors(
        q,
        SMART_CB,
        elements=elements,
        templates={(SMART_CB, 0): [template]},
    )

    assert result.devref_changed is False
    assert result.geometry_changed is True
    assert result.template_used is True
    assert (q.get("x"), q.get("y"), q.get("w"), q.get("h")) == ("4", "8", "30", "30")
    assert connected_anchor_points(q, by_id) == before == ((22.0, 14.0), (22.0, 34.0))


def test_scan_reports_progress(tmp_path: Path):
    path = tmp_path / "sample.g"
    root = ET.Element("G")
    ET.SubElement(root, "Layer")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    values: list[int] = []
    scan_smart_profile_samples([path], progress=values.append)
    assert values[0] == 0
    assert values[-1] == 100
    assert any(0 < value < 100 for value in values)


def test_site_profile_ui_has_wheel_safe_candidates_progress_and_active_versions():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert source.count("WheelSafeComboBox()") >= 4
    assert "self.scan_progress = QProgressBar()" in source
    assert "self.service.prepare_standard_file_records([path])" in source
    assert "业务单线图不会参与 devref、尺寸、AlignCenter 或 pin 标准的生成" in source
    assert '"ACTIVE" if is_active else "ARCHIVED"' in source
    assert 'self.restore_action = self.profile_menu.addAction("恢复此版本")' in source
    assert "_confirm_rescan_target" not in source
    assert "图元几何（大小/端口）" in source
