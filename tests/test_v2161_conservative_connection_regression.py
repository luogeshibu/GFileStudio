from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.connection_engine import repair_tree_connections


def _groups(value: str | None) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for raw in (value or "").split(";"):
        parts = tuple(part.strip() for part in raw.split(",", 2))
        if len(parts) == 3 and parts[2]:
            result.append(parts)
    return result


def test_existing_breaker_and_disconnector_port_numbers_are_frozen():
    xml = '''<?xml version="1.0" encoding="utf-8"?>
<G id="root" x="0" y="0" w="500" h="500">
  <Layer name="0">
    <ConnectLine id="34005608" d="0,100 100,100" x="-3" y="97" w="106" h="6"
      node_area="0,1,101005612" link="0,1,101005612"/>
    <ConnectLine id="34005609" d="100,100 200,100" x="97" y="97" w="106" h="6"
      node_area="0,0,101005612;1,0,100005611" link="0,0,101005612;1,0,100005611"/>
    <ConnectLine id="34005610" d="230,100 330,100" x="227" y="97" w="106" h="6"
      node_area="0,1,100005611" link="0,1,100005611"/>
    <Disconnector id="101005612" x="90" y="85" w="20" h="30" rotate="0"
      devref="#test.disconnector" composeType="GIcon"
      node_area="0,0,34005609;1,0,34005608"/>
    <CBreaker id="100005611" x="200" y="85" w="30" h="30" rotate="0"
      devref="#test.breaker" composeType="GIcon"
      node_area="0,1,34005609;1,0,34005610"/>
  </Layer>
</G>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    layer = tree.getroot().find("Layer")
    before = {
        element.get("id"): {
            attribute: _groups(element.get(attribute))
            for attribute in ("node_area", "link")
        }
        for element in list(layer)
        if element.get("id")
    }

    result = repair_tree_connections(tree, Path("MODE-ZZZ-regression.g"))
    after = {element.get("id"): element for element in list(layer) if element.get("id")}

    assert result.updated_reference_count == 0
    assert result.removed_reference_count == 0
    for element_id, attributes in before.items():
        for attribute, original_groups in attributes.items():
            current = _groups(after[element_id].get(attribute))
            for group in original_groups:
                assert group in current

    assert _groups(after["100005611"].get("node_area")) == [
        ("0", "1", "34005609"),
        ("1", "0", "34005610"),
    ]
    assert _groups(after["101005612"].get("node_area")) == [
        ("0", "0", "34005609"),
        ("1", "0", "34005608"),
    ]
