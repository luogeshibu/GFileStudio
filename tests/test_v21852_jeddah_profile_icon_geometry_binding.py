from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_icon_geometry import (
    apply_devref_preserving_anchors,
    build_geometry_templates,
    connected_anchor_points,
)
from g_file_studio.engines.smart_profile_engine import apply_smart_profile_to_tree
from g_file_studio.services.site_profile_service import SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
OLD_NORMAL_CB = "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"
NEW_NORMAL_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"


def _profile_with_new_cb_icon_catalog() -> SiteSmartProfile:
    # Real target icon geometry supplied by the standard *.icn.g:
    # w/h 30x30, AlignCenter 18,16, electrical pins (18,6)/(18,26).
    return SiteSmartProfile(
        profile_name="RMU STANDARD V1",
        site_name="Jeddah",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NEW_NORMAL_CB,
        symbol_catalog={
            NEW_NORMAL_CB: {
                "devref": NEW_NORMAL_CB,
                "element_tag": "CBreakerDis",
                "element_id": "Circuit_Breaker_NO-SMART",
                "source_file": "Circuit_Breaker_NO-SMART.zwk.icn.g",
                "width": 30,
                "height": 30,
                "align_center": [18, 16],
                "pins": [[18, 6], [18, 26]],
                "pin_ids": ["18000003", "18000004"],
                "count": 0,
            }
        },
    ).normalized()


def _normal_rmu_with_legacy_q() -> tuple[ET.ElementTree, ET.Element]:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="1350", y="2400", w="220", h="220")
    ET.SubElement(layer, "BusDis", id="38000382", x="1400", y="2511", w="108", h="6", key_name="30815_BUS")
    q = ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000374",
        x="1442",
        y="2541",
        w="28",
        h="28",
        p_NameString="Q1",
        key_name="Q1",
        devref=OLD_NORMAL_CB,
        rotate="0",
        tfr="rotate(0) scale(1,1)",
        node_area="0,0,34000383;1,0,34000394",
    )
    ET.SubElement(
        layer,
        "ConnectLine",
        id="34000383",
        x="1451",
        y="2508",
        w="6",
        h="40",
        d="1454,2545 1454,2511",
    )
    ET.SubElement(
        layer,
        "ConnectLine",
        id="34000394",
        x="1451",
        y="2562",
        w="6",
        h="32",
        d="1454,2565 1454,2591",
    )
    ET.SubElement(layer, "Text", id="8000399", ts="30815", x="1393.5", y="2351", w="125", h="50")
    return ET.ElementTree(root), q


def test_profile_normalization_binds_raw_icon_pins_to_effective_geometry():
    profile = _profile_with_new_cb_icon_catalog()
    rows = profile.geometry_templates[NEW_NORMAL_CB]
    by_rotation = {int(row["rotation"]): row for row in rows}
    assert set(by_rotation) == {0, 90, 180, 270}
    assert by_rotation[0]["width"] == 30
    assert by_rotation[0]["height"] == 30
    assert by_rotation[0]["anchor_offsets"] == [[18.0, 6.0], [18.0, 26.0]]


def test_normal_q_devref_correction_also_moves_body_to_keep_existing_lines_fixed(tmp_path: Path):
    profile = _profile_with_new_cb_icon_catalog()
    tree, q = _normal_rmu_with_legacy_q()
    root = tree.getroot()
    elements = list(root.iter())
    by_id = {element.get("id"): element for element in elements if element.get("id")}
    before_anchors = connected_anchor_points(q, by_id)

    result = apply_devref_preserving_anchors(
        q,
        NEW_NORMAL_CB,
        elements=elements,
        templates=__import__(
            "g_file_studio.engines.smart_icon_geometry",
            fromlist=["deserialize_geometry_templates"],
        ).deserialize_geometry_templates(profile.geometry_templates),
    )

    # New icon pin offsets are +6 X / +2 Y compared with the legacy placed icon.
    # Therefore the body must move left 6 and up 2 while the two line endpoints stay fixed.
    assert q.get("devref") == NEW_NORMAL_CB
    assert (q.get("x"), q.get("y"), q.get("w"), q.get("h")) == ("1436", "2539", "30", "30")
    assert connected_anchor_points(q, by_id) == before_anchors == ((1454.0, 2545.0), (1454.0, 2565.0))
    assert result.devref_changed
    assert result.geometry_changed


def test_geometry_learned_from_270_degree_target_can_correct_0_degree_legacy_q():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")

    # Correct target icon exists only at 270°.  For a 30x30 target whose raw pins
    # are (18,6)/(18,26), the rotated local offsets are (6,12)/(26,12).
    target = ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="100",
        y="100",
        w="30",
        h="30",
        p_NameString="Q1",
        devref=NEW_NORMAL_CB,
        rotate="270",
        tfr="rotate(270) scale(1,1)",
        node_area="0,0,34000001;1,0,34000002",
    )
    ET.SubElement(layer, "ConnectLine", id="34000001", x="80", y="109", w="29", h="6", d="106,112 80,112")
    ET.SubElement(layer, "ConnectLine", id="34000002", x="123", y="109", w="30", h="6", d="126,112 150,112")

    tree, legacy = _normal_rmu_with_legacy_q()
    legacy_layer = next(iter(tree.getroot()))
    for child in list(legacy_layer):
        if child is legacy or child.get("id") in {"34000383", "34000394"}:
            layer.append(child)

    elements = list(root.iter())
    templates = build_geometry_templates(elements, {NEW_NORMAL_CB})
    assert (NEW_NORMAL_CB, 0) in templates

    result = apply_devref_preserving_anchors(
        legacy,
        NEW_NORMAL_CB,
        elements=elements,
        templates=templates,
    )
    assert result.template_used
    assert (legacy.get("x"), legacy.get("y"), legacy.get("w"), legacy.get("h")) == ("1436", "2539", "30", "30")


def test_real_uploaded_30815_case_is_corrected_when_fixture_is_available():
    source = Path("/mnt/data/JED-NTH-ABH-12.sln.pic(5).g")
    icon = Path("/mnt/data/Circuit_Breaker_NO-SMART.zwk.icn(3).g")
    if not source.exists() or not icon.exists():
        return

    from g_file_studio.engines.icon_upgrade_engine import parse_icon_definition

    definition = parse_icon_definition(icon)
    new_devref = f"#{definition.file_name}:{definition.element_id}"
    profile = SiteSmartProfile(
        profile_name="RMU STANDARD V1",
        site_name="Jeddah",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=new_devref,
        symbol_catalog={
            new_devref: {
                "devref": new_devref,
                "element_tag": definition.element_tag,
                "element_id": definition.element_id,
                "source_file": definition.file_name,
                "width": definition.width,
                "height": definition.height,
                "align_center": list(definition.align_center),
                "pins": [list(pin) for pin in definition.pins],
                "pin_ids": list(definition.pin_ids),
            }
        },
    ).normalized()

    tree = ET.parse(source)
    root = tree.getroot()
    by_id = {element.get("id"): element for element in root.iter() if element.get("id")}
    q = by_id["117000374"]
    before = connected_anchor_points(q, by_id)

    result = apply_smart_profile_to_tree(
        tree,
        source,
        smart_lbs_devref=profile.smart_lbs_devref,
        smart_breaker_devref=profile.smart_breaker_devref,
        normal_lbs_devref=profile.normal_lbs_devref,
        normal_breaker_devref=profile.normal_breaker_devref,
        smart_ground_devref=profile.smart_ground_devref,
        normal_ground_devref=profile.normal_ground_devref,
        profile_geometry_templates=profile.geometry_templates,
    )

    assert q.get("devref") == new_devref
    assert (q.get("x"), q.get("y"), q.get("w"), q.get("h")) == ("1436", "2539", "30", "30")
    assert connected_anchor_points(q, by_id) == before == ((1454.0, 2545.0), (1454.0, 2565.0))
    assert result.geometry_adjusted_count >= 1
