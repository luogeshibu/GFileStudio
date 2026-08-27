from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import apply_rmu_name_white


def _write_rmu_fixture(path: Path, name: str = "38995") -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="220", h="220", lc="0,255,0", lcc="#00ff00")
    ET.SubElement(layer, "BusDis", id="38000001", x="160", y="150", w="6", h="120", key_name=f"{name}_BUS")
    ET.SubElement(layer, "CBreakerDis", id="117000001", x="190", y="180", w="40", h="40", p_NameString="Y1", devref="Load_Breaker")
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="250", y="180", w="40", h="40")
    ET.SubElement(layer, "Text", id="8000001", ts=name, x="145", y="45", w="130", h="90", lc="0,255,0", lcc="#00ff00", fc="0,255,0", fcc="#00ff00")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_jeddah_rmu_name_white_uses_existing_recognition(tmp_path: Path):
    source = tmp_path / "input.g"
    output = tmp_path / "output.g"
    _write_rmu_fixture(source)

    result = apply_rmu_name_white(
        source,
        output,
        name_positions=("top",),
        name_exclusions="NOP, DAS/OK, SFI",
    )

    assert result.identified_rmu_count == 1
    assert result.named_rmu_count == 1
    assert result.matched_name_text_count == 1
    assert result.changed_name_text_count == 1
    text = next(e for e in ET.parse(output).getroot().iter() if e.tag == "Text")
    assert text.get("lc") == "255,255,255"
    assert text.get("lcc") == "#ffffff"
    assert text.get("fc") == "255,255,255"
    assert text.get("fcc") == "#ffffff"


def test_jeddah_name_exclusion_prevents_name_recolor(tmp_path: Path):
    source = tmp_path / "input.g"
    output = tmp_path / "output.g"
    _write_rmu_fixture(source, name="NOP")

    result = apply_rmu_name_white(
        source,
        output,
        name_positions=("top",),
        name_exclusions="NOP, DAS/OK, SFI",
    )

    assert result.named_rmu_count == 0
    assert result.changed_name_text_count == 0
    text = next(e for e in ET.parse(output).getroot().iter() if e.tag == "Text")
    assert text.get("fc") == "0,255,0"


def test_jeddah_batch_is_new_orchestration_only():
    source = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "scan_file" in source
    assert "delete_issues_to_output" in source
    assert "enhance_rmu_tree" in source
    assert "move_feeder_titles_above_buses" in source
    assert "process_basic" not in source
    assert "process_ids" in source
    assert "change_smart_frame_color=False" in source
    assert "ensure_jeddah_smart_rmu_frames_red" in source
    assert "smart_frame_color=JEDDAH_RED" in source
    assert "change_smr_frame_color=True" in source
    assert "smr_frame_color=JEDDAH_RED" in source
    assert "remove_bus_frame_and_reposition_title=True" in source


def test_main_window_adds_jeddah_page_without_changing_existing_pages_package():
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "JeddahBatchPage" in source
    assert "吉达馈线批处理" in source
