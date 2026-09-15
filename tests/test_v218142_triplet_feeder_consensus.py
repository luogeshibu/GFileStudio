from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.services.database_service import TopologyFeederAnchorContext
from g_file_studio.services.symbol_inventory_service import _infer_feeder_membership


def _ctx(table: str, device: str, bay: str, station: str = "AJWD", feeder: str = "AH327"):
    return TopologyFeederAnchorContext(
        table_name=table,
        device_id=device,
        device_name="",
        bay_id=bay,
        station_name=station,
        feeder_name=feeder,
    )


def _row(element_id: str):
    return {
        "图元用途": "设备",
        "设备类型": "Transformer",
        "迁移设备类型": "TRANSFORMER",
        "设备层级": "独立设备",
        "实例名称": "97471",
        "所属RMU": "",
        "ElementID": element_id,
        "x": 0,
        "y": 0,
        "w": 20,
        "h": 20,
    }


def test_cbreaker_authoritative_bay_propagates_even_when_other_head_bays_conflict():
    b = ET.Element("CBreaker", id="1", keyid="b", node_area="0,0,11")
    d = ET.Element("Disconnector", id="2", keyid="d", node_area="0,0,11;1,0,12")
    g = ET.Element("GroundDisconnector", id="3", keyid="g", node_area="0,0,12;1,0,13")
    l1 = ET.Element("ConnectLine", id="11", link="0,0,1;1,0,2")
    l2 = ET.Element("ConnectLine", id="12", link="0,0,2;1,0,3")
    l3 = ET.Element("ConnectLine", id="13", link="0,0,3;1,0,4")
    t = ET.Element("TransformerDis", id="4", link="0,0,13")
    rows = [_row("4")]

    _infer_feeder_membership(
        elements=[b, d, g, l1, l2, l3, t],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "b"): _ctx("BREAKER", "7001", "6001"),
            ("DISCONNECTOR", "d"): _ctx("DISCONNECTOR", "8001", "6001"),
            ("GROUNDDISCONNECTOR", "g"): _ctx("GROUNDDISCONNECTOR", "9001", "6002", feeder="AH328"),
        },
        database_lookup_enabled=True,
    )

    assert rows[0]["所属馈线"] == "AJWD AH327"


def test_triplet_same_bay_outputs_station_plus_feeder_name():
    b = ET.Element("CBreaker", id="1", keyid="b", node_area="0,0,11")
    d = ET.Element("Disconnector", id="2", keyid="d", node_area="0,0,11;1,0,12")
    g = ET.Element("GroundDisconnector", id="3", keyid="g", node_area="0,0,12;1,0,13")
    l1 = ET.Element("ConnectLine", id="11", link="0,0,1;1,0,2")
    l2 = ET.Element("ConnectLine", id="12", link="0,0,2;1,0,3")
    l3 = ET.Element("ConnectLine", id="13", link="0,0,3;1,0,4")
    t = ET.Element("TransformerDis", id="4", link="0,0,13")
    rows = [_row("4")]

    stats = _infer_feeder_membership(
        elements=[b, d, g, l1, l2, l3, t],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "b"): _ctx("BREAKER", "7001", "6001"),
            ("DISCONNECTOR", "d"): _ctx("DISCONNECTOR", "8001", "6001"),
            ("GROUNDDISCONNECTOR", "g"): _ctx("GROUNDDISCONNECTOR", "9001", "6001"),
        },
        database_lookup_enabled=True,
    )

    assert rows[0]["所属馈线"] == "AJWD AH327"
    assert rows[0]["馈线判断来源"] == "DB_TRIPLE_TOPOLOGY"
    assert rows[0]["馈线证据设备数"] == 3
    assert stats["validated_bay_count"] == 1


def test_release_version_218142():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
