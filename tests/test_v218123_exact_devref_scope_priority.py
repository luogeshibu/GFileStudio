from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.services.site_profile_service import SiteSmartProfile
from g_file_studio.services.symbol_inventory_service import extract_file_inventory


def _profile() -> SiteSmartProfile:
    devref = "#Fuse_NON_SMART.zwk.icn.g:Fuse_NON_SMART"
    return SiteSmartProfile(
        profile_name="scope-exact-test",
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        custom_symbols=[{
            "uid": "fuse-normal",
            "scope": "NORMAL",
            "role": "Fuse",
            "device_type": "Fuse",
            "device_subtype": "",
            "device_level": "独立设备",
            "symbol_usage": "设备",
            "element_tag": "CBreakerDis",
            "standard_devref": devref,
            "match_attr": "XML元素",
            "match_value": "",
            "source_file": "Fuse_NON_SMART.zwk.icn.g",
        }],
        symbol_catalog={
            devref: {
                "devref": devref,
                "element_tag": "CBreakerDis",
                "element_id": "Fuse_NON_SMART",
                "source_file": "Fuse_NON_SMART.zwk.icn.g",
            }
        },
    )


def _business_g(path: Path) -> None:
    root = ET.Element("G", {"facID": "AJWD", "facName": "AJWD-30"})
    layer = ET.SubElement(root, "Layer")
    # Deliberately outside any RMU frame.  The exact configured devref + XML type
    # must still identify the symbol even though its standard scope is NORMAL.
    ET.SubElement(layer, "CBreakerDis", {
        "id": "117000355",
        "x": "2020",
        "y": "4196",
        "w": "48",
        "h": "32",
        "devref": "#Fuse_NON_SMART.zwk.icn.g:Fuse_NON_SMART",
    })
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_exact_devref_and_xml_override_missing_rmu_scope_context(tmp_path: Path):
    source = tmp_path / "JED-CTL-AJWD-30.sln.pic.g"
    _business_g(source)

    symbols, devices, unmapped, warnings = extract_file_inventory(source, _profile())

    assert not warnings
    assert not unmapped
    assert len(symbols) == 1
    assert len(devices) == 1
    row = symbols[0]
    assert row["设备类型"] == "Fuse"
    assert row["标准检查范围"] == "NORMAL"
    assert row["实际devref"] == row["标准devref"]
    assert row["匹配来源"] == "exact-devref"
    assert row["标准校验"] == "PASS"
    assert row["w"] == 48.0
    assert row["h"] == 32.0
