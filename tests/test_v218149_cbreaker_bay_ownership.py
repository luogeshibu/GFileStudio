from __future__ import annotations

import xml.etree.ElementTree as ET

from g_file_studio.services.database_service import TopologyFeederAnchorContext
from g_file_studio.services.symbol_inventory_service import (
    _discover_feeder_root_branches,
    _feeder_anchor_keyids_for_db,
    _infer_feeder_membership,
    extract_file_content_inventory,
)


def _ctx() -> TopologyFeederAnchorContext:
    return TopologyFeederAnchorContext(
        table_name="BREAKER",
        device_id="7001",
        device_name="",
        bay_id="6001",
        station_name="AJWD",
        feeder_name="AH313",
    )


def _elements() -> list[ET.Element]:
    bus = ET.Element("Bus", id="100", node_area="0,0,11")
    line_up = ET.Element("ConnectLine", id="11", link="0,0,100;1,0,1")
    breaker = ET.Element("CBreaker", id="1", keyid="cb-key", node_area="0,0,11;1,0,12")
    line_down = ET.Element("ConnectLine", id="12", link="0,0,1;1,0,20")
    busdis = ET.Element("BusDis", id="20", node_area="0,0,12;1,0,30")
    transformer = ET.Element("TransformerDis", id="30", node_area="0,0,20")
    return [bus, line_up, breaker, line_down, busdis, transformer]


def test_cbreaker_is_the_only_required_and_queried_feeder_root():
    elements = _elements()
    branches = _discover_feeder_root_branches(elements)

    assert len(branches) == 1
    assert branches[0].anchor_nodes == {"BREAKER": "1"}
    assert _feeder_anchor_keyids_for_db(elements) == {
        "BREAKER": ["cb-key"],
        "DISCONNECTOR": [],
        "GROUNDDISCONNECTOR": [],
    }


def test_every_non_bus_topology_object_inherits_cbreaker_bay():
    elements = _elements()
    rows = [{
        "图元用途": "设备",
        "设备类型": "Transformer",
        "迁移设备类型": "TRANSFORMER",
        "设备层级": "独立设备",
        "实例名称": "T1",
        "所属RMU": "",
        "ElementID": "30",
        "x": 0,
        "y": 0,
        "w": 20,
        "h": 20,
    }]
    assignments: dict[tuple[str, str], TopologyFeederAnchorContext] = {
        ("BREAKER", "cb-key"): _ctx(),
    }
    result = _infer_feeder_membership(
        elements=elements,
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts=assignments,
        database_lookup_enabled=True,
    )

    assert rows[0]["馈线BayID"] == "6001"
    assert rows[0]["馈线判断来源"] == "DB_CBREAKER_TOPOLOGY"
    assert set(result["element_feeder_fields"]) == {"1", "11", "12", "20", "30"}
    assert "100" not in result["element_feeder_fields"]


def test_complete_content_inventory_keeps_bus_blank_and_assigns_other_objects(tmp_path):
    source = tmp_path / "content.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    for element in _elements():
        layer.append(element)
    ET.ElementTree(root).write(source, encoding="utf-8")

    fields = {
        element_id: {"所属馈线": "AJWD AH313", "馈线站名": "AJWD", "馈线BayID": "6001"}
        for element_id in ("1", "11", "12", "20", "30")
    }
    rows, _summary = extract_file_content_inventory(source, [], [], [], fields)
    by_tag = {row["XML元素"] + ":" + row["ElementID"]: row for row in rows}

    assert by_tag["Bus:100"]["馈线BayID"] == ""
    assert by_tag["Bus:100"]["设备类型"] == "Bus"
    assert by_tag["Bus:100"]["内容分类"] == "连接/拓扑"
    assert by_tag["BusDis:20"]["馈线BayID"] == "6001"
    assert by_tag["ConnectLine:12"]["馈线BayID"] == "6001"


def test_isolated_device_component_uses_unique_compact_feeder_identity():
    elements = _elements()
    elements.extend([
        ET.Element(
            "TransformerDis",
            id="31",
            key_name1="dms_tr_device JED-CTL AJWD AH330 99959 id",
        ),
        ET.Element("ConnectLine", id="32", link="0,0,31"),
    ])
    rows = [{
        "图元用途": "设备",
        "设备类型": "Transformer",
        "迁移设备类型": "TRANSFORMER",
        "设备层级": "独立设备",
        "实例名称": "99959",
        "所属RMU": "",
        "ElementID": "31",
        "x": 0,
        "y": 0,
        "w": 20,
        "h": 20,
    }]
    result = _infer_feeder_membership(
        elements=elements,
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "cb-key"): TopologyFeederAnchorContext(
                table_name="BREAKER",
                device_id="7001",
                device_name="",
                bay_id="6001",
                station_name="AJWD",
                feeder_name="AH330",
            ),
        },
        database_lookup_enabled=True,
    )

    assert rows[0]["馈线BayID"] == "6001"
    assert rows[0]["馈线判断来源"] == "DB_CBREAKER_FEEDER_IDENTITY"
    assert rows[0]["馈线置信度"] == "MEDIUM"
    assert result["element_feeder_fields"]["31"]["馈线BayID"] == "6001"
