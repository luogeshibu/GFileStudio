from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.margin_engine import adjust_one_file, detect_existing_frame


def _write_plain(path: Path) -> None:
    path.write_text(
        '<G w="1000" width="1000" h="800" height="800">'
        '<Layer>'
        '<Text id="1" x="200" y="200" w="100" h="50" ts="BODY" />'
        '</Layer>'
        '</G>',
        encoding="utf-8",
    )


def _write_with_frame(path: Path) -> None:
    path.write_text(
        '<G w="1000" width="1000" h="800" height="800">'
        '<Layer>'
        '<line id="10" x="50" y="50" w="906" h="6" x1="50" y1="50" x2="950" y2="50" d="50,50 950,50" />'
        '<line id="11" x="950" y="50" w="6" h="706" x1="950" y1="50" x2="950" y2="750" d="950,50 950,750" />'
        '<line id="12" x="50" y="750" w="906" h="6" x1="950" y1="750" x2="50" y2="750" d="950,750 50,750" />'
        '<line id="13" x="50" y="50" w="6" h="706" x1="50" y1="750" x2="50" y2="50" d="50,750 50,50" />'
        '<rect id="20" x="60" y="60" w="120" h="40" />'
        '<Text id="21" x="70" y="68" w="100" h="20" ts="FRAME TITLE" />'
        '<rect id="30" x="760" y="660" w="180" h="80" />'
        '<Text id="31" x="770" y="670" w="120" h="20" ts="DO NOT CHANGE" />'
        '<Text id="1" x="200" y="200" w="100" h="50" ts="BODY" />'
        '</Layer>'
        '</G>',
        encoding="utf-8",
    )


def _layer(root: ET.Element) -> ET.Element:
    return next(child for child in root if child.tag == "Layer")


def test_adjust_plain_graph_to_500_margins(tmp_path: Path) -> None:
    source = tmp_path / "plain.sln.pic.g"
    output = tmp_path / "plain-adjusted.sln.pic.g"
    _write_plain(source)

    result = adjust_one_file(source, output)
    assert result.had_existing_frame is False
    assert (result.new_canvas_width, result.new_canvas_height) == (1100, 1050)
    assert (
        result.body_left_margin,
        result.body_top_margin,
        result.body_right_margin,
        result.body_bottom_margin,
    ) == (500, 500, 500, 500)

    root = ET.parse(output).getroot()
    body = _layer(root).find("Text")
    assert body is not None
    assert body.get("x") == "500"
    assert body.get("y") == "500"
    assert root.get("w") == root.get("width") == "1100"
    assert root.get("h") == root.get("height") == "1050"


def test_existing_frame_is_preserved_and_resized_without_text_changes(tmp_path: Path) -> None:
    source = tmp_path / "framed.sln.pic.g"
    output = tmp_path / "framed-adjusted.sln.pic.g"
    _write_with_frame(source)

    before_root = ET.parse(source).getroot()
    frame = detect_existing_frame(_layer(before_root), 1000, 800)
    assert frame is not None

    result = adjust_one_file(source, output)
    assert result.had_existing_frame is True
    assert (
        result.frame_left_margin,
        result.frame_top_margin,
        result.frame_right_margin,
        result.frame_bottom_margin,
    ) == (50, 50, 50, 50)

    root = ET.parse(output).getroot()
    layer = _layer(root)
    texts = {item.get("ts"): item for item in layer.findall("Text")}
    assert set(texts) == {"FRAME TITLE", "DO NOT CHANGE", "BODY"}
    assert texts["FRAME TITLE"].get("x") == "70"
    assert texts["FRAME TITLE"].get("y") == "68"
    assert texts["DO NOT CHANGE"].get("x") == "870"
    assert texts["DO NOT CHANGE"].get("y") == "920"
    assert texts["BODY"].get("x") == "500"
    assert texts["BODY"].get("y") == "500"

    lines = {item.get("id"): item for item in layer.findall("line")}
    assert lines["10"].get("x1") == "50"
    assert lines["10"].get("x2") == "1050"
    assert lines["11"].get("x1") == "1050"
    assert lines["11"].get("y2") == "1000"
    assert lines["12"].get("y1") == "1000"
    assert lines["13"].get("x1") == "50"
