from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import apply_jeddah_rmu_name_standard


def _write_fixture(path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="200", w="220", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="155", y="250", w="8", h="120", key_name="6703_BUS")
    ET.SubElement(layer, "CBreakerDis", id="117000001", x="190", y="280", w="40", h="40", p_NameString="Y1", devref="Load_Breaker")
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="250", y="280", w="40", h="40")
    ET.SubElement(
        layer,
        "Text",
        id="8000001",
        ts="6703",
        x="145",
        y="120",
        w="130",
        h="60",
        fs="60",
        p_FontWidth="60",
        p_FontHeight="60",
        lc="0,255,0",
        lcc="#00ff00",
        fc="0,255,0",
        fcc="#00ff00",
    )
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_jeddah_rmu_name_is_white_size_50_and_centered_10_above_frame(tmp_path: Path):
    source = tmp_path / "input.g"
    output = tmp_path / "output.g"
    _write_fixture(source)

    result = apply_jeddah_rmu_name_standard(
        source,
        output,
        name_positions=("top",),
        name_exclusions="NOP, DAS/OK, SFI",
        font_size=50,
        top_gap=10,
    )

    assert result.named_rmu_count == 1
    assert result.matched_name_text_count == 1
    assert result.changed_name_text_count == 1
    assert result.font_size_changed_count == 1
    assert result.position_changed_count == 1

    tree = ET.parse(output)
    text = next(e for e in tree.getroot().iter("Text") if e.get("ts") == "6703")
    assert text.get("lc") == "255,255,255"
    assert text.get("lcc") == "#ffffff"
    assert text.get("fc") == "255,255,255"
    assert text.get("fcc") == "#ffffff"
    assert text.get("fs") == "50"
    assert text.get("p_FontWidth") == "50"
    assert text.get("p_FontHeight") == "50"

    # Old box 130x60 at fs=60 scales to 108.333333 x 50 at fs=50.
    # RMU frame center is x=210; the scaled text is centered on that x.
    assert text.get("w") == "108.333333"
    assert text.get("h") == "50"
    assert abs(float(text.get("x")) + float(text.get("w")) / 2.0 - 210.0) < 1e-6
    # The text bottom is exactly 10 units above rect.top=200.
    assert abs(float(text.get("y")) + float(text.get("h")) - 190.0) < 1e-6


def test_jeddah_name_layout_is_not_added_to_shared_rmu_engine():
    shared = Path("g_file_studio/engines/rmu_name_style_engine.py").read_text(encoding="utf-8")
    batch = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "font_size=50" not in shared
    assert "top_gap=10" not in shared
    assert "apply_jeddah_rmu_name_standard" in batch
    assert "font_size=50" in batch
    assert "top_gap=10" in batch
