from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.batch_processor import JeddahBatchSettings
from g_file_studio.jeddah.style_engine import apply_jeddah_rmu_name_standard


def _write_single_right_name(path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="220", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="155", y="150", w="8", h="120", key_name="AB8822_BUS")
    ET.SubElement(layer, "CBreakerDis", id="117000001", x="190", y="180", w="40", h="40", p_NameString="Y1", devref="Load_Breaker")
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="250", y="180", w="40", h="40")
    ET.SubElement(
        layer,
        "Text",
        id="8000001",
        ts="AB8822",
        x="350",
        y="175",
        w="120",
        h="50",
        fs="50",
        p_FontWidth="50",
        p_FontHeight="50",
        lc="0,255,0",
        lcc="#00ff00",
        fc="0,255,0",
        fcc="#00ff00",
    )
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_jeddah_single_rmu_uses_auto_cluster_fallback_without_direction_setting(tmp_path: Path):
    source = tmp_path / "input.g"
    output = tmp_path / "output.g"
    _write_single_right_name(source)

    result = apply_jeddah_rmu_name_standard(
        source,
        output,
        name_exclusions="NOP, DAS/OK, SFI",
        font_size=50,
        top_gap=10,
    )

    assert result.identified_rmu_count == 1
    assert result.named_rmu_count == 1
    assert result.matched_name_text_count == 1
    text = next(e for e in ET.parse(output).getroot().iter("Text") if e.get("ts") == "AB8822")
    # Jeddah presentation remains unchanged after auto recognition: final title is
    # centered 10 units above the RMU top frame and made white.
    assert text.get("fc") == "255,255,255"
    assert abs(float(text.get("y")) + float(text.get("h")) - 90.0) < 1e-6


def test_jeddah_batch_removes_manual_name_direction_controls_only():
    page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    batch = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    style = Path("g_file_studio/jeddah/style_engine.py").read_text(encoding="utf-8")
    shared = Path("g_file_studio/engines/rmu_identification_engine.py").read_text(encoding="utf-8")
    standalone_rmu_page = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")

    assert "RMU 柜名可能位置：" not in page
    assert "self.name_top" not in page
    assert "jeddah_batch/rmu_name_top" not in page
    assert "rmu_name_top:" not in batch
    assert "RMU 柜名位置至少选择" not in batch
    assert 'name_resolution_mode="auto_cluster"' in style

    # Public/shared default remains legacy.  v2.18.139 separately opts the
    # standalone RMU page into auto_cluster without changing that default.
    assert 'name_resolution_mode: str = "selected_direction"' in shared
    assert 'rmu_name_resolution_mode="auto_cluster"' in standalone_rmu_page


def test_jeddah_batch_settings_no_longer_exposes_name_direction_fields():
    fields = JeddahBatchSettings.__dataclass_fields__
    for name in ("rmu_name_top", "rmu_name_bottom", "rmu_name_left", "rmu_name_right"):
        assert name not in fields
