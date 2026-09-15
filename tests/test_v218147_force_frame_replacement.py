from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines import frame_engine
from g_file_studio.engines.margin_engine import adjust_one_file


def _template_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "templates"
        / "SLD-Drawing-Frame-Template.sln.pic.g"
    )


def _config(title: str = "") -> dict[str, object]:
    return {
        "default": {
            "title": title,
            "draw": {"name": "", "date": ""},
            "approve": {"name": "", "date": ""},
            "issue": {"name": "", "date": ""},
        },
        "files": {},
    }


def _write_plain(path: Path) -> None:
    path.write_text(
        '<G w="1000" width="1000" h="800" height="800">'
        '<Layer><Text id="1" x="200" y="200" w="100" h="50" ts="BODY" /></Layer>'
        '</G>',
        encoding="utf-8",
    )


def _write_unknown_frame(path: Path) -> None:
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
        '</Layer></G>',
        encoding="utf-8",
    )


def _layer(root: ET.Element) -> ET.Element:
    return next(child for child in root if child.tag == "Layer")


def test_frame_add_replaces_existing_marked_builtin_instead_of_appending(tmp_path: Path) -> None:
    source = tmp_path / "plain.g"
    first = tmp_path / "first.g"
    second = tmp_path / "second.g"
    _write_plain(source)
    template = ET.parse(_template_path())

    frame_engine.process_one_file(source, first, template, _config("FIRST"), edit_content=True)
    frame_engine.process_one_file(first, second, template, _config("SECOND"), edit_content=True)

    root = ET.parse(second).getroot()
    layer = _layer(root)
    marked = [
        element
        for element in list(layer)
        if element.get(frame_engine.GFS_FRAME_TYPE_ATTRIBUTE) == frame_engine.GFS_FRAME_TYPE_BUILTIN
    ]
    template_count = len(list(_layer(ET.parse(_template_path()).getroot())))
    assert len(marked) == template_count
    assert sum(1 for element in layer.findall("Text") if element.get("ts") == "BODY") == 1
    assert any(element.get("ts") == "SECOND" for element in layer.findall("Text"))
    assert not any(element.get("ts") == "FIRST" for element in layer.findall("Text"))


def test_frame_add_force_replaces_unmarked_unknown_frame(tmp_path: Path) -> None:
    source = tmp_path / "unknown.g"
    output = tmp_path / "replaced.g"
    _write_unknown_frame(source)

    frame_engine.process_one_file(
        source,
        output,
        ET.parse(_template_path()),
        _config("AUTHORITATIVE"),
        edit_content=True,
    )

    root = ET.parse(output).getroot()
    layer = _layer(root)
    texts = [element.get("ts") for element in layer.findall("Text")]
    assert "BODY" in texts
    assert "CUSTOM FRAME" not in texts
    assert "AUTHORITATIVE" in texts
    assert root.get(frame_engine.GFS_FRAME_TYPE_ATTRIBUTE) == frame_engine.GFS_FRAME_TYPE_BUILTIN


def test_jeddah_margin_path_can_remove_unknown_frame_without_manual_block(tmp_path: Path) -> None:
    source = tmp_path / "unknown.g"
    output = tmp_path / "margin.g"
    _write_unknown_frame(source)

    result = adjust_one_file(
        source,
        output,
        left_margin=500,
        top_margin=500,
        right_margin=500,
        bottom_margin=500,
        preserve_existing_frame=True,
        force_remove_existing_frame=True,
    )

    assert result.removed_existing_frame_count == 6
    assert "unknown_outer_lines" in result.removed_existing_frame_modes
    assert (result.body_left_margin, result.body_top_margin) == (500, 500)
    root = ET.parse(output).getroot()
    texts = [element.get("ts") for element in _layer(root).findall("Text")]
    assert texts == ["BODY"]


def test_jeddah_pipeline_explicitly_enables_force_frame_removal() -> None:
    source = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "force_remove_existing_frame=True" in source
    assert "current template selection as authoritative" in source
