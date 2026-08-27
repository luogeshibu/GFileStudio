from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import apply_jeddah_feedline_solid


def test_jeddah_feedline_solid_changes_only_feedline_ls(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    feed_a = ET.SubElement(layer, "FeedLine", id="1", ls="2", lc="1,2,3", lcc="#010203", lw="5", x="10", y="20")
    feed_b = ET.SubElement(layer, "FeedLine", id="2", lc="9,8,7", lcc="#090807", lw="6")
    connect = ET.SubElement(layer, "ConnectLine", id="3", ls="2")
    bus = ET.SubElement(layer, "Bus", id="4", ls="2")
    tree = ET.ElementTree(root)

    result = apply_jeddah_feedline_solid(tree, tmp_path / "fixture.g")

    assert feed_a.get("ls") == "1"
    assert feed_b.get("ls") == "1"
    assert feed_a.get("lc") == "1,2,3"
    assert feed_a.get("lcc") == "#010203"
    assert feed_a.get("lw") == "5"
    assert feed_a.get("x") == "10"
    assert feed_a.get("y") == "20"
    assert connect.get("ls") == "2"
    assert bus.get("ls") == "2"
    assert result.style_changed_by_tag.get("FeedLine") == 2
    assert result.color_changed_by_tag.get("FeedLine", 0) == 0


def test_jeddah_batch_calls_feedline_solid_without_changing_existing_modules():
    source = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "apply_jeddah_feedline_solid" in source
    assert "feedline_solid_applied_count" in source
    assert "process_basic" not in source
