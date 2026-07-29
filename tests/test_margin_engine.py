from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from g_file_studio.engines.frame_engine import (
    GFS_FRAME_COMPONENT_ATTRIBUTE,
    GFS_FRAME_TEMPLATE_ATTRIBUTE,
    GFS_FRAME_TYPE_ATTRIBUTE,
    process_one_file,
)
from g_file_studio.engines.margin_engine import (
    UnsupportedExistingFrameError,
    adjust_one_file,
    detect_existing_frame,
)


def _write_plain(path: Path) -> None:
    path.write_text(
        '<G w="1000" width="1000" h="800" height="800">'
        '<Layer>'
        '<Text id="1" x="200" y="200" w="100" h="50" ts="BODY" />'
        '</Layer>'
        '</G>',
        encoding="utf-8",
    )


def _write_custom_frame(path: Path) -> None:
    path.write_text(
        '<G w="1000" width="1000" h="800" height="800">'
        '<Layer>'
        '<line id="10" x="50" y="50" w="906" h="6" x1="50" y1="50" x2="950" y2="50" d="50,50 950,50" />'
        '<line id="11" x="950" y="50" w="6" h="706" x1="950" y1="50" x2="950" y2="750" d="950,50 950,750" />'
        '<line id="12" x="50" y="750" w="906" h="6" x1="950" y1="750" x2="50" y2="750" d="950,750 50,750" />'
        '<line id="13" x="50" y="50" w="6" h="706" x1="50" y1="750" x2="50" y2="50" d="50,750 50,50" />'
        '<rect id="20" x="60" y="60" w="120" h="40" />'
        '<Text id="21" x="70" y="68" w="100" h="20" ts="CUSTOM FRAME" />'
        '<Text id="1" x="200" y="200" w="100" h="50" ts="BODY" />'
        '</Layer>'
        '</G>',
        encoding="utf-8",
    )


def _layer(root: ET.Element) -> ET.Element:
    return next(child for child in root if child.tag == "Layer")


def _builtin_config() -> dict[str, object]:
    return {
        "default": {
            "title": "",
            "draw": {"name": "", "date": ""},
            "approve": {"name": "", "date": ""},
            "issue": {"name": "", "date": ""},
        },
        "files": {},
    }


def _add_builtin_frame(source: Path, output: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    template_path = project_root / "resources" / "templates" / "SLD-Drawing-Frame-Template.sln.pic.g"
    process_one_file(
        source,
        output,
        ET.parse(template_path),
        _builtin_config(),
        edit_content=True,
    )


def _strip_gfs_frame_markers(path: Path) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    for name in (GFS_FRAME_TYPE_ATTRIBUTE, GFS_FRAME_TEMPLATE_ATTRIBUTE):
        root.attrib.pop(name, None)
    for element in _layer(root):
        element.attrib.pop(GFS_FRAME_TYPE_ATTRIBUTE, None)
        element.attrib.pop(GFS_FRAME_COMPONENT_ATTRIBUTE, None)
    tree.write(path, encoding="utf-8", xml_declaration=True)


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
    body = next(item for item in _layer(root).findall("Text") if item.get("ts") == "BODY")
    assert body.get("x") == "500"
    assert body.get("y") == "500"
    assert root.get("w") == root.get("width") == "1100"
    assert root.get("h") == root.get("height") == "1050"


def test_marked_builtin_frame_is_preserved_and_resized(tmp_path: Path) -> None:
    plain = tmp_path / "plain.sln.pic.g"
    source = tmp_path / "framed.sln.pic.g"
    output = tmp_path / "framed-adjusted.sln.pic.g"
    _write_plain(plain)
    _add_builtin_frame(plain, source)

    before_root = ET.parse(source).getroot()
    frame = detect_existing_frame(_layer(before_root), 1000, 800)
    assert frame is not None
    assert frame.detection_mode == "marker"
    assert len(frame.components) >= 25

    result = adjust_one_file(source, output)
    assert result.had_existing_frame is True
    assert result.frame_detection_mode == "marker"
    assert (
        result.frame_left_margin,
        result.frame_top_margin,
        result.frame_right_margin,
        result.frame_bottom_margin,
    ) == (50, 50, 50, 50)

    root = ET.parse(output).getroot()
    body = next(item for item in _layer(root).findall("Text") if item.get("ts") == "BODY")
    assert body.get("x") == "500"
    assert body.get("y") == "500"


def test_legacy_unmarked_builtin_frame_uses_strict_fingerprint(tmp_path: Path) -> None:
    plain = tmp_path / "plain.sln.pic.g"
    source = tmp_path / "legacy-framed.sln.pic.g"
    output = tmp_path / "legacy-framed-adjusted.sln.pic.g"
    _write_plain(plain)
    _add_builtin_frame(plain, source)
    _strip_gfs_frame_markers(source)

    before_root = ET.parse(source).getroot()
    frame = detect_existing_frame(_layer(before_root), 1000, 800)
    assert frame is not None
    assert frame.detection_mode == "legacy_builtin_fingerprint"
    assert len(frame.components) in {25, 30}

    result = adjust_one_file(source, output)
    assert result.had_existing_frame is True
    assert result.frame_detection_mode == "legacy_builtin_fingerprint"

    root = ET.parse(output).getroot()
    body = next(item for item in _layer(root).findall("Text") if item.get("ts") == "BODY")
    assert body.get("x") == "500"
    assert body.get("y") == "500"


def test_unknown_or_customer_frame_requires_manual_removal(tmp_path: Path) -> None:
    source = tmp_path / "custom-framed.sln.pic.g"
    output = tmp_path / "custom-framed-adjusted.sln.pic.g"
    _write_custom_frame(source)

    with pytest.raises(UnsupportedExistingFrameError) as exc_info:
        adjust_one_file(source, output)

    message = str(exc_info.value)
    assert "不是 G File Studio 内置图框" in message
    assert "请先在图形编辑器中删除现有图框" in message
    assert not output.exists()
