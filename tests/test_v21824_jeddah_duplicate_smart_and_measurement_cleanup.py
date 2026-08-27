from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import (
    remove_duplicate_smart_labels_in_rmus,
    remove_jeddah_adjacent_measurement_texts,
)


def _rmu_tree_with_duplicate_smart() -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="220", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="205", y="145", w="8", h="130", key_name="10689_BUS")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="155", y="180", w="28", h="30",
        p_NameString="Y1", key_name="Y1-10689",
        devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART",
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="250", y="180", w="30", h="30")
    ET.SubElement(layer, "Text", id="8000001", ts="10689", x="150", y="45", w="120", h="50")
    # Original SMART comes first in XML and must be preserved exactly.
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="178", y="100", w="63", h="21", fs="20")
    # Later duplicate from a prior run.
    ET.SubElement(layer, "Text", id="8000003", ts="SMART", x="178.5", y="100", w="63", h="21", fs="20")
    return ET.ElementTree(root)


def test_duplicate_smart_cleanup_scans_rmu_and_keeps_original_first_text(tmp_path: Path):
    tree = _rmu_tree_with_duplicate_smart()
    result = remove_duplicate_smart_labels_in_rmus(tree, tmp_path / "duplicate-smart.g")

    smart = [
        e for e in tree.getroot().iter("Text")
        if (e.get("ts") or "").strip().upper() == "SMART"
    ]
    assert result.scanned_rmu_count == 1
    assert result.duplicate_rmu_count == 1
    assert result.smart_text_removed_count == 1
    assert [e.get("id") for e in smart] == ["8000002"]
    assert smart[0].get("x") == "178"  # existing SMART was not rewritten/repositioned


def test_adjacent_measurement_pair_removed_but_distant_same_strings_are_kept(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    # Adjacent pair: 2000.00 right edge = 165, UPDATED starts at 166 (gap 1).
    ET.SubElement(layer, "Text", id="8000101", ts="2000.00", x="100", y="200", w="65", h="21")
    ET.SubElement(layer, "Text", id="8000102", ts="UPDATED_MEASURMENT", x="166", y="196", w="309", h="28")
    # Same exact strings but not adjacent: must remain.
    ET.SubElement(layer, "Text", id="8000103", ts="2000.00", x="100", y="500", w="65", h="21")
    ET.SubElement(layer, "Text", id="8000104", ts="UPDATED_MEASURMENT", x="500", y="500", w="309", h="28")
    tree = ET.ElementTree(root)

    result = remove_jeddah_adjacent_measurement_texts(tree, tmp_path / "measurement.g")
    remaining = {e.get("id") for e in layer if e.tag == "Text"}

    assert result.value_text_count == 2
    assert result.measurement_text_count == 2
    assert result.adjacent_pair_count == 1
    assert result.removed_text_count == 2
    assert "8000101" not in remaining
    assert "8000102" not in remaining
    assert "8000103" in remaining
    assert "8000104" in remaining


def test_uploaded_abha_08_sample_duplicate_smart_and_adjacent_measurement_pair():
    sample = Path("/mnt/data/JED-NTH-ABH-08.sln.pic(2).g")
    if not sample.exists():
        return
    tree = ET.parse(sample)
    smart_result = remove_duplicate_smart_labels_in_rmus(tree, sample)
    measurement_result = remove_jeddah_adjacent_measurement_texts(tree, sample)

    assert smart_result.scanned_rmu_count == 8
    assert smart_result.duplicate_rmu_count == 3
    assert smart_result.smart_text_removed_count == 3
    assert measurement_result.adjacent_pair_count == 1
    assert measurement_result.removed_text_count == 2

    remaining_smart_ids = {
        e.get("id") for e in tree.getroot().iter()
        if e.tag.endswith("Text") and (e.get("ts") or "").strip().upper() == "SMART"
    }
    # Preserve the three pre-existing/original SMART labels from the source G.
    assert {"8000044", "8000076", "8000170"}.issubset(remaining_smart_ids)
    assert not any(
        e.tag.endswith("Text")
        and (e.get("ts") or "").strip().upper() in {"2000.00", "UPDATED_MEASURMENT"}
        for e in tree.getroot().iter()
    )
