from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.models import InputMode
from g_file_studio.processors.smart_profile_processor import (
    SmartProfileProcessingSettings,
    process_smart_profile_correction,
)
from g_file_studio.services.site_profile_service import SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
OLD_FUSE = "#Fuse_Old.icn.g:Fuse_Old"
NEW_FUSE = "#Fuse_Standard.icn.g:Fuse_Standard"


def _source(path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(
        layer,
        "ConnectLine",
        id="34000001",
        d="110,100 75,100",
        x="75",
        y="97",
        w="35",
        h="6",
    )
    ET.SubElement(
        layer,
        "FuseDevice",
        id="99000001",
        x="100",
        y="95",
        w="10",
        h="10",
        rotate="0",
        tfr="rotate(0) scale(1,1)",
        devref=OLD_FUSE,
        p_NameString="F1",
        node_area="0,0,34000001",
    )
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _profile() -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="Generic Standard",
        site_name="General",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        geometry_templates={
            NEW_FUSE: [
                {
                    "rotation": 0,
                    "width": 20.0,
                    "height": 20.0,
                    "anchor_offsets": [[20.0, 10.0]],
                }
            ]
        },
        custom_symbols=[
            {
                "enabled": True,
                "scope": "ANY",
                "role": "Fuse",
                "element_tag": "FuseDevice",
                "standard_devref": NEW_FUSE,
                "match_attr": "devref",
                "match_value": OLD_FUSE,
            }
        ],
    )


def test_standard_correction_writes_copy_and_preserves_connectline_anchor(tmp_path: Path):
    source = tmp_path / "source.g"
    _source(source)
    before = source.read_bytes()
    out = tmp_path / "run"

    result = process_smart_profile_correction(
        SmartProfileProcessingSettings(source, InputMode.SINGLE_FILE, out, _profile()),
        log=lambda _msg: None,
    )

    # Source is immutable; correction is a managed workspace copy.
    assert source.read_bytes() == before
    corrected = out / "corrected" / "source.g"
    assert corrected.exists()

    tree = ET.parse(corrected)
    layer = list(tree.getroot())[0]
    line = next(item for item in layer if item.tag == "ConnectLine")
    fuse = next(item for item in layer if item.tag == "FuseDevice")

    # The electrical endpoint remains 110,100.  Standard pin offset 20,10 therefore
    # places the 20x20 symbol at 90,90.
    assert line.get("d") == "110,100 75,100"
    assert fuse.get("devref") == NEW_FUSE
    assert (fuse.get("x"), fuse.get("y"), fuse.get("w"), fuse.get("h")) == ("90", "90", "20", "20")

    assert result.statistics["Mode"] == "CORRECT"
    assert result.statistics["Corrected Elements"] == 1
    assert result.statistics["Geometry Corrections"] == 1
    assert result.statistics["Remaining Nonstandard Symbols"] == 0
    assert (out / "post-check" / "reports" / "symbol-standard-check.html").exists()


def test_site_profile_ui_exposes_explicit_correction_without_touching_jeddah_pipeline():
    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    processor = Path("g_file_studio/processors/smart_profile_processor.py").read_text(encoding="utf-8")
    assert 'self.correct_button = QPushButton("纠正标准问题")' in page
    assert "process_smart_profile_correction" in page
    assert 'corrected_dir = output_root / "corrected"' in processor
    assert "Jeddah batch processing does not call this function" in processor


def test_connected_symbol_without_safe_target_geometry_is_not_devref_swapped(tmp_path: Path):
    source = tmp_path / "unsafe.g"
    _source(source)
    before_tree = ET.parse(source)
    before_fuse = next(item for item in list(before_tree.getroot())[0] if item.tag == "FuseDevice")
    assert before_fuse.get("devref") == OLD_FUSE

    profile = SiteSmartProfile(
        profile_name="Generic Standard",
        site_name="General",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        # No NEW_FUSE geometry template on purpose.
        custom_symbols=[
            {
                "enabled": True,
                "scope": "ANY",
                "role": "Fuse",
                "element_tag": "FuseDevice",
                "standard_devref": NEW_FUSE,
                "match_attr": "devref",
                "match_value": OLD_FUSE,
            }
        ],
    )
    out = tmp_path / "run"
    result = process_smart_profile_correction(
        SmartProfileProcessingSettings(source, InputMode.SINGLE_FILE, out, profile),
        log=lambda _msg: None,
    )
    corrected = ET.parse(out / "corrected" / "unsafe.g")
    fuse = next(item for item in list(corrected.getroot())[0] if item.tag == "FuseDevice")
    assert fuse.get("devref") == OLD_FUSE
    assert (fuse.get("x"), fuse.get("y"), fuse.get("w"), fuse.get("h")) == ("100", "95", "10", "10")
    assert result.statistics["Corrected Elements"] == 0
    assert result.statistics["Remaining Nonstandard Symbols"] == 1
    assert any("没有可安全拟合的目标 pin/几何模板" in warning for warning in result.warnings)
