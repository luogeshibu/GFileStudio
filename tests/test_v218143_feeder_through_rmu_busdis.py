from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.services.database_service import TopologyFeederAnchorContext
from g_file_studio.services.symbol_inventory_service import _infer_feeder_membership


def _ctx(table: str, device: str) -> TopologyFeederAnchorContext:
    return TopologyFeederAnchorContext(
        table_name=table,
        device_id=device,
        device_name="",
        bay_id="6001",
        station_name="AJWD",
        feeder_name="AH310",
    )


def _row(element_id: str, name: str) -> dict[str, object]:
    return {
        "图元用途": "设备",
        "设备类型": "Transformer",
        "迁移设备类型": "TRANSFORMER",
        "设备层级": "独立设备",
        "实例名称": name,
        "所属RMU": "",
        "ElementID": element_id,
        "x": 0,
        "y": 0,
        "w": 20,
        "h": 20,
    }


def test_validated_feeder_propagates_through_rmu_busdis_to_downstream_devices():
    # Station bus is upstream and remains a hard boundary.
    station_bus = ET.Element("Bus", id="100", node_area="0,0,101")
    up = ET.Element("ConnectLine", id="101", link="0,0,100;1,0,1")

    # The only DB-queried feeder anchors: 407/408/409, all same BAY_ID.
    brk = ET.Element("CBreaker", id="1", keyid="b", node_area="0,0,101;1,0,11")
    dsc = ET.Element("Disconnector", id="2", keyid="d", node_area="0,0,12;1,0,13")
    gds = ET.Element("GroundDisconnector", id="3", keyid="g", node_area="0,0,13")
    l11 = ET.Element("ConnectLine", id="11", link="0,0,1;1,0,2")
    l12 = ET.Element("ConnectLine", id="12", link="0,0,2;1,0,3")
    l13 = ET.Element("ConnectLine", id="13", link="0,0,3;1,0,21")

    # First RMU.  BusDis is an internal electrical bus, not a feeder boundary.
    y2a = ET.Element("CBreakerDis", id="21", node_area="0,0,13;1,0,22")
    l22 = ET.Element("ConnectLine", id="22", link="0,0,21;1,0,23")
    rmu_bus_a = ET.Element("BusDis", id="23", node_area="0,0,22;1,0,24")
    l24 = ET.Element("ConnectLine", id="24", link="0,0,23;1,0,25")
    y1a = ET.Element("CBreakerDis", id="25", node_area="0,0,24;1,0,26")
    feed = ET.Element("FeedLine", id="26", link="0,0,25;1,0,31")

    # Second RMU / downstream target, only reachable by traversing the first BusDis.
    y2b = ET.Element("CBreakerDis", id="31", node_area="0,0,26;1,0,32")
    l32 = ET.Element("ConnectLine", id="32", link="0,0,31;1,0,33")
    rmu_bus_b = ET.Element("BusDis", id="33", node_area="0,0,32;1,0,34")
    l34 = ET.Element("ConnectLine", id="34", link="0,0,33;1,0,40")
    target = ET.Element("TransformerDis", id="40", node_area="0,0,34")

    rows = [_row("40", "DOWNSTREAM")]
    stats = _infer_feeder_membership(
        elements=[
            station_bus, up, brk, dsc, gds, l11, l12, l13,
            y2a, l22, rmu_bus_a, l24, y1a, feed,
            y2b, l32, rmu_bus_b, l34, target,
        ],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "b"): _ctx("BREAKER", "7001"),
            ("DISCONNECTOR", "d"): _ctx("DISCONNECTOR", "8001"),
            ("GROUNDDISCONNECTOR", "g"): _ctx("GROUNDDISCONNECTOR", "9001"),
        },
        database_lookup_enabled=True,
    )

    assert rows[0]["所属馈线"] == "AJWD AH310"
    assert rows[0]["馈线判断来源"] == "DB_TRIPLE_TOPOLOGY"
    assert stats["validated_bay_count"] == 1
    assert stats["primary_resolved"] == 1


def test_release_version_218143():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
