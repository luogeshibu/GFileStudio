from __future__ import annotations

import inspect
import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines import feeder_title_engine
from g_file_studio.engines.feeder_title_engine import move_feeder_titles_above_buses


def _tree(layer_content: str) -> ET.ElementTree:
    return ET.ElementTree(
        ET.fromstring(
            f'''<?xml version="1.0" encoding="utf-8"?>
<G w="2000" h="1200"><Layer>{layer_content}</Layer></G>'''
        )
    )


def test_single_bus_moves_unique_title_and_ignores_numeric_and_description(tmp_path: Path) -> None:
    tree = _tree(
        '''
<Bus id="30000001" x="100" y="200" w="130" h="6" x1="103" y1="203" x2="227" y2="203" d="103,203 227,203"/>
<Text id="80000001" ts="ABH-22" x="210" y="220" w="110" h="45" fs="41" p_FontHeight="41"/>
<Text id="80000002" ts="2000.00" x="95" y="300" w="65" h="21" fs="20" p_FontHeight="20"/>
<Text id="80000003" ts="UPDATED_MEASURMENT" x="170" y="290" w="300" h="28" fs="27" p_FontHeight="27"/>
'''
    )
    layer = tree.getroot().find("Layer")
    assert layer is not None
    before = {element.get("id"): dict(element.attrib) for element in list(layer)}

    result = move_feeder_titles_above_buses(tree, tmp_path / "sample.g")

    assert result.moved_count == 1
    title = next(element for element in list(layer) if element.get("id") == "80000001")
    assert title.get("x") == "110"
    assert title.get("y") == "140"
    for element in list(layer):
        old = before[element.get("id")]
        changed = {
            key
            for key in set(old) | set(element.attrib)
            if old.get(key) != element.attrib.get(key)
        }
        if element.get("id") == "80000001":
            assert changed == {"x", "y"}
        else:
            assert not changed


def test_double_bus_is_one_group_and_title_is_centered_above_top_bus(tmp_path: Path) -> None:
    tree = _tree(
        '''
<Bus id="30000013" x="500" y="420" w="133" h="6" x1="503" y1="423" x2="630" y2="423" d="503,423 630,423"/>
<Bus id="30000022" x="500" y="399" w="133" h="6" x1="503" y1="402" x2="630" y2="402" d="503,402 630,402"/>
<Text id="80000012" ts="ABS-36" x="620" y="440" w="93" h="32" fs="30" p_FontHeight="30"/>
'''
    )
    result = move_feeder_titles_above_buses(tree, tmp_path / "double.g")
    title = tree.getroot().find("Layer/Text")
    assert result.bus_segment_count == 2
    assert result.bus_group_count == 1
    assert result.moved_count == 1
    assert title is not None
    assert title.get("x") == "520"
    assert title.get("y") == "352"


def test_ambiguous_candidates_are_skipped(tmp_path: Path) -> None:
    tree = _tree(
        '''
<Bus id="30000001" x="100" y="200" w="130" h="6" x1="103" y1="203" x2="227" y2="203" d="103,203 227,203"/>
<Text id="80000001" ts="AAA-11" x="120" y="220" w="90" h="32" fs="30" p_FontHeight="30"/>
<Text id="80000002" ts="BBB-22" x="122" y="222" w="90" h="32" fs="30" p_FontHeight="30"/>
'''
    )
    layer = tree.getroot().find("Layer")
    assert layer is not None
    before = [dict(element.attrib) for element in list(layer)]
    result = move_feeder_titles_above_buses(tree, tmp_path / "ambiguous.g")
    assert result.moved_count == 0
    assert result.skipped_ambiguous_count == 1
    assert before == [dict(element.attrib) for element in list(layer)]


def test_operation_is_idempotent_and_does_not_use_model_binding_fields(tmp_path: Path) -> None:
    source = inspect.getsource(feeder_title_engine)
    assert "key_name" not in source
    assert "keyid" not in source

    tree = _tree(
        '''
<Bus id="30000001" x="100" y="200" w="130" h="6" x1="103" y1="203" x2="227" y2="203" d="103,203 227,203" key_name="" keyid=""/>
<Text id="80000001" ts="ABH-22" x="210" y="220" w="110" h="45" fs="41" p_FontHeight="41" key_name="" keyid=""/>
'''
    )
    first = move_feeder_titles_above_buses(tree, tmp_path / "first.g")
    second = move_feeder_titles_above_buses(tree, tmp_path / "second.g")
    assert first.moved_count == 1
    assert second.moved_count == 0
    assert second.unchanged_count == 1
