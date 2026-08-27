from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_profile_engine import (
    apply_smart_profile_to_tree,
    scan_smart_profile_samples,
)
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


def test_scan_catalog_exposes_main_g_element_properties_and_icon_definition(tmp_path: Path):
    main = tmp_path / "sample.sln.pic.g"
    main.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<G><Layer>
<FuseDevice id="99000001" devref="#Fuse_STD.icn.g:Fuse_STD" x="100" y="200" w="20" h="10"
 rotate="90" tfr="rotate(90) scale(1,1)" p_NameString="F1" key_name="Fuse F1"/>
</Layer></G>""",
        encoding="utf-8",
    )
    icon = tmp_path / "Fuse_STD.icn.g"
    icon.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<G><FuseDevice id="Fuse_STD" w="20" h="10" AlignCenter="10,5">
<Layer><pin id="P1" index="0" cx="0" cy="5"/><pin id="P2" index="1" cx="20" cy="5"/></Layer>
</FuseDevice></G>""",
        encoding="utf-8",
    )

    result = scan_smart_profile_samples([main, icon])
    meta = result.symbol_catalog["#Fuse_STD.icn.g:Fuse_STD"]
    assert meta["element_tag"] == "FuseDevice"
    assert meta["element_id"] == "Fuse_STD"
    assert meta["width"] == 20
    assert meta["height"] == 10
    assert meta["align_center"] == [10.0, 5.0]
    assert meta["pins"] == [[0.0, 5.0], [20.0, 5.0]]
    assert 90 in meta["rotations"]
    assert "#Fuse_STD.icn.g:Fuse_STD" in result.geometry_templates
    assert {row["rotation"] for row in result.geometry_templates["#Fuse_STD.icn.g:Fuse_STD"]} == {0, 90, 180, 270}


def test_custom_symbol_rule_can_upgrade_other_device_tag():
    root = ET.fromstring(
        """<G><Layer>
<FuseDevice id="99000001" devref="#Fuse_OLD.icn.g:Fuse_OLD" x="100" y="200" w="20" h="10"
 rotate="0" tfr="rotate(0) scale(1,1)" p_NameString="F1"/>
</Layer></G>"""
    )
    tree = ET.ElementTree(root)
    result = apply_smart_profile_to_tree(
        tree,
        Path("sample.g"),
        smart_lbs_devref="#dummy_lbs.g:dummy_lbs",
        smart_breaker_devref="#dummy_cb.g:dummy_cb",
        custom_symbols=[{
            "uid": "fuse",
            "scope": "ANY",
            "role": "Fuse",
            "element_tag": "FuseDevice",
            "standard_devref": "#Fuse_STD.icn.g:Fuse_STD",
            "match_attr": "devref",
            "match_value": "#Fuse_OLD.icn.g:Fuse_OLD",
            "enabled": True,
        }],
    )
    fuse = root.find("./Layer/FuseDevice")
    assert fuse is not None
    assert fuse.get("devref") == "#Fuse_STD.icn.g:Fuse_STD"
    assert result.custom_checked_count == 1
    assert result.custom_changed_count == 1


def test_profile_persists_custom_symbols_and_symbol_catalog(tmp_path: Path):
    service = SiteProfileService(tmp_path / "profiles.json")
    profile = service.upsert(SiteSmartProfile(
        profile_name="MAD-V1",
        site_name="MAD",
        smart_lbs_devref="#LBS.g:LBS",
        smart_breaker_devref="#CB.g:CB",
        custom_symbols=[{
            "uid": "fuse",
            "scope": "ANY",
            "role": "Fuse",
            "element_tag": "FuseDevice",
            "standard_devref": "#Fuse_STD.icn.g:Fuse_STD",
            "match_attr": "devref",
            "match_value": "#Fuse_OLD.icn.g:Fuse_OLD",
            "enabled": True,
        }],
        symbol_catalog={
            "#Fuse_STD.icn.g:Fuse_STD": {
                "element_tag": "FuseDevice",
                "element_id": "Fuse_STD",
                "width": 20,
                "height": 10,
                "align_center": [10, 5],
                "pins": [[0, 5], [20, 5]],
                "pin_ids": ["P1", "P2"],
                "rotations": [0, 90],
                "count": 3,
            }
        },
    ))
    assert profile.custom_symbols[0]["role"] == "Fuse"
    loaded = service.load_profiles()["MAD-V1"]
    assert loaded.custom_symbols[0]["element_tag"] == "FuseDevice"
    assert loaded.symbol_catalog["#Fuse_STD.icn.g:Fuse_STD"]["pins"] == [[0.0, 5.0], [20.0, 5.0]]



def test_custom_symbol_uses_raw_icon_geometry_without_moving_connectlines(tmp_path: Path):
    icon = tmp_path / "Fuse_STD.icn.g"
    icon.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<G><FuseDevice id="Fuse_STD" w="30" h="14" AlignCenter="15,7">
<Layer><pin id="P1" index="0" cx="5" cy="7"/><pin id="P2" index="1" cx="25" cy="7"/></Layer>
</FuseDevice></G>""",
        encoding="utf-8",
    )
    scan = scan_smart_profile_samples([icon])
    target = "#Fuse_STD.icn.g:Fuse_STD"

    root = ET.fromstring(
        """<G><Layer>
<FuseDevice id="99000001" devref="#Fuse_OLD.icn.g:Fuse_OLD" x="100" y="100" w="20" h="10"
 rotate="0" tfr="rotate(0) scale(1,1)" node_area="0,0,34000001;1,1,34000002"/>
<ConnectLine id="34000001" x="80" y="102" w="23" h="6" d="80,105 100,105" node_area="1,0,99000001"/>
<ConnectLine id="34000002" x="117" y="102" w="23" h="6" d="120,105 140,105" node_area="0,1,99000001"/>
</Layer></G>"""
    )
    tree = ET.ElementTree(root)
    before = [line.get("d") for line in root.findall("./Layer/ConnectLine")]
    result = apply_smart_profile_to_tree(
        tree,
        Path("sample.g"),
        smart_lbs_devref="#dummy_lbs.g:dummy_lbs",
        smart_breaker_devref="#dummy_cb.g:dummy_cb",
        profile_geometry_templates=scan.geometry_templates,
        custom_symbols=[{
            "uid": "fuse",
            "scope": "ANY",
            "role": "Fuse",
            "element_tag": "FuseDevice",
            "standard_devref": target,
            "match_attr": "devref",
            "match_value": "#Fuse_OLD.icn.g:Fuse_OLD",
            "enabled": True,
        }],
    )
    fuse = root.find("./Layer/FuseDevice")
    assert fuse is not None
    assert fuse.get("devref") == target
    assert fuse.get("w") == "30"
    assert fuse.get("h") == "14"
    assert fuse.get("x") == "95"
    assert fuse.get("y") == "98"
    assert [line.get("d") for line in root.findall("./Layer/ConnectLine")] == before
    assert result.custom_changed_count == 1
    assert result.geometry_adjusted_count == 1

def test_site_profile_page_exposes_custom_symbol_controls():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("添加设备图元")' in source
    assert 'QPushButton("添加扫描到的未映射图元")' in source
    assert 'QPushButton("删除选中自定义项")' in source
    assert '"XML 元素", "标准图元 devref", "主体 ID", "w×h", "AlignCenter", "Pins"' in source
    assert '"匹配属性", "当前/旧图元匹配值"' in source
