from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.rmu_name_style_engine import apply_rmu_name_white_to_tree
from g_file_studio.jeddah.style_engine import replace_jeddah_smr_with_smart


def _valid_rmu_tree(*, marker: str = "SMR", include_smart_reference: bool = True) -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(
        layer,
        "rect",
        id="2000001",
        x="100",
        y="100",
        w="220",
        h="220",
        lc="0,255,0",
        lcc="#00FF00",
    )
    ET.SubElement(layer, "BusDis", id="38000001", x="155", y="150", w="8", h="120", key_name="38995_BUS")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="190",
        y="180",
        w="40",
        h="40",
        p_NameString="Y1",
        devref="Load_Breaker",
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="250", y="180", w="40", h="40")
    ET.SubElement(
        layer,
        "Text",
        id="8000001",
        ts="38995",
        x="145",
        y="45",
        w="130",
        h="90",
        lc="0,255,0",
        lcc="#00ff00",
        fc="0,255,0",
        fcc="#00ff00",
    )
    ET.SubElement(
        layer,
        "Text",
        id="8000002",
        ts=marker,
        x="190",
        y="75",
        w="45",
        h="20",
        fs="14",
        ff="Calibri",
        lc="0,0,0",
        lcc="#000000",
        fc="255,255,255",
    )
    if include_smart_reference:
        ET.SubElement(
            layer,
            "Text",
            id="8000099",
            ts="SMART",
            x="500",
            y="500",
            w="63",
            h="21",
            fs="20",
            p_FontWidth="20",
            p_FontHeight="20",
            ff="Arial",
            bold="false",
            italic="false",
            lc="255,0,0",
            lcc="#ff0000",
            fc="0,255,0",
            horizontal="1",
            wm="1",
            lw="1",
            ls="1",
        )
    return ET.ElementTree(root)


def test_rmu_name_white_can_run_as_standalone_tree_operation(tmp_path: Path):
    tree = _valid_rmu_tree(marker="SMR")
    result = apply_rmu_name_white_to_tree(
        tree,
        tmp_path / "fixture.g",
        name_positions=("top",),
        name_exclusions="NOP, DAS/OK, SFI",
    )
    assert result.named_rmu_count == 1
    assert result.matched_name_text_count == 1
    assert result.changed_name_text_count == 1
    name = next(e for e in tree.getroot().iter("Text") if (e.get("ts") or "") == "38995")
    assert name.get("lc") == "255,255,255"
    assert name.get("lcc") == "#ffffff"
    assert name.get("fc") == "255,255,255"
    assert name.get("fcc") == "#ffffff"


def test_jeddah_smr_is_replaced_with_top_centered_smart_and_frame_red(tmp_path: Path):
    tree = _valid_rmu_tree(marker="SMR")
    result = replace_jeddah_smr_with_smart(tree, tmp_path / "fixture.g")
    assert result.smr_text_count == 1
    assert result.matched_rmu_count == 1
    assert result.replaced_count == 1

    layer = next(e for e in tree.getroot() if e.tag == "Layer")
    rect = next(e for e in layer if e.tag == "rect" and e.get("id") == "2000001")
    assert rect.get("lc") == "255,0,0"
    assert rect.get("lcc") == "#FF0000"

    assert not any(e.tag == "Text" and (e.get("ts") or "").strip().upper() == "SMR" for e in layer)
    replaced = next(e for e in layer if e.tag == "Text" and e.get("id") == "8000002")
    assert replaced.get("ts") == "SMART"
    assert replaced.get("fs") == "20"
    assert replaced.get("p_FontWidth") == "20"
    assert replaced.get("p_FontHeight") == "20"
    assert replaced.get("ff") == "Arial"
    assert replaced.get("w") == "63"
    assert replaced.get("h") == "21"
    # 220-wide frame at x=100; SMART width 63 => x = 178.5. y sits on the top band/edge.
    assert replaced.get("x") == "178.5"
    assert replaced.get("y") == "100"


def test_rmu_page_exposes_white_name_as_independent_option():
    source = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert "将已识别的环网柜名称统一改成白色" in source
    assert 'set_rmu_name_text_white=self.rmu_name_white.isChecked()' in source
    assert 'get_bool("basic/rmu/name_text_white", False)' in source


def test_jeddah_batch_calls_smr_to_smart_adapter_and_keeps_site_specific():
    batch = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    assert "replace_jeddah_smr_with_smart" in batch
    assert "SMR→SMART" in batch
    assert "字号 20" in page
    assert "外框强制红色" in page
