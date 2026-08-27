from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import remove_jeddah_ht_texts


def test_jeddah_ht_cleanup_removes_exact_text_only(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "Text", id="8000001", ts="H.T", x="10", y="20", w="51", h="36")
    ET.SubElement(layer, "Text", id="8000002", ts="  h.t  ", x="20", y="30", w="51", h="36")
    ET.SubElement(layer, "Text", id="8000003", ts="H.T-1", x="30", y="40", w="60", h="36")
    ET.SubElement(layer, "Text", id="8000004", ts="OTHER H.T", x="40", y="50", w="100", h="36")
    tree = ET.ElementTree(root)

    result = remove_jeddah_ht_texts(tree, tmp_path / "ht.g")
    remaining = [(e.get("id"), e.get("ts")) for e in layer if e.tag == "Text"]

    assert result.matched_count == 2
    assert result.removed_count == 2
    assert ("8000001", "H.T") not in remaining
    assert ("8000002", "  h.t  ") not in remaining
    assert ("8000003", "H.T-1") in remaining
    assert ("8000004", "OTHER H.T") in remaining


def test_jeddah_ht_cleanup_matches_uploaded_abha_sample_shape():
    sample = Path("/mnt/data/JED-NTH-ABH.sln.pic(9).g")
    if not sample.exists():
        return
    tree = ET.parse(sample)
    before = [
        e for e in tree.getroot().iter()
        if e.tag.endswith("Text") and (e.get("ts") or "").strip().upper() == "H.T"
    ]
    result = remove_jeddah_ht_texts(tree, sample)
    after = [
        e for e in tree.getroot().iter()
        if e.tag.endswith("Text") and (e.get("ts") or "").strip().upper() == "H.T"
    ]
    assert len(before) == 1
    assert result.removed_count == 1
    assert after == []
