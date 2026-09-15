from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.services.database_service import TopologyFeederAnchorContext
from g_file_studio.services.symbol_inventory_service import (
    _discover_feeder_root_branches,
    _feeder_anchor_keyids_for_db,
    _infer_feeder_membership,
)


def _ctx(table: str, device_id: str) -> TopologyFeederAnchorContext:
    return TopologyFeederAnchorContext(
        table_name=table,
        device_id=device_id,
        device_name="",
        bay_id="6001",
        station_name="AJWD",
        feeder_name="AH310",
    )


def _row(element_id: str, name: str, dtype: str = "TRANSFORMER") -> dict[str, object]:
    return {
        "图元用途": "设备",
        "设备类型": dtype,
        "迁移设备类型": dtype,
        "设备层级": "独立设备",
        "实例名称": name,
        "所属RMU": "",
        "ElementID": element_id,
        "x": 0,
        "y": 0,
        "w": 20,
        "h": 20,
    }


def _fixture():
    # Common Bus is only the start boundary.
    bus = ET.Element("Bus", id="100", node_area="0,0,11")
    l11 = ET.Element("ConnectLine", id="11", link="0,0,100;1,0,2")

    # Only this nearest triplet is allowed to query DB.
    d = ET.Element("Disconnector", id="2", keyid="top-d", node_area="0,0,11;1,0,12")
    l12 = ET.Element("ConnectLine", id="12", link="0,0,2;1,0,1")
    b = ET.Element("CBreaker", id="1", keyid="top-b", node_area="0,0,12;1,0,13")
    l13 = ET.Element("ConnectLine", id="13", link="0,0,1;1,0,3")
    g = ET.Element("GroundDisconnector", id="3", keyid="top-g", node_area="0,0,13;1,0,14")

    # Downstream topology: FeedLine -> BusDis -> devices.  A downstream CBreaker
    # deliberately has an unrelated keyid and must NOT be sent to Oracle.
    feed = ET.Element("FeedLine", id="14", link="0,0,3;1,0,20")
    busdis = ET.Element("BusDis", id="20", node_area="0,0,14;1,0,21")
    l21 = ET.Element("ConnectLine", id="21", link="0,0,20;1,0,30")
    t1 = ET.Element("TransformerDis", id="30", node_area="0,0,21;1,0,31")
    l31 = ET.Element("ConnectLine", id="31", link="0,0,30;1,0,40")
    downstream_breaker = ET.Element("CBreaker", id="40", keyid="downstream-b", node_area="0,0,31;1,0,41")
    l41 = ET.Element("ConnectLine", id="41", link="0,0,40;1,0,50")
    t2 = ET.Element("TransformerDis", id="50", node_area="0,0,41")

    return [bus, l11, d, l12, b, l13, g, feed, busdis, l21, t1, l31, downstream_breaker, l41, t2]


def test_db_lookup_uses_only_nearest_bus_head_triplet_not_downstream_keyids():
    elements = _fixture()
    branches = _discover_feeder_root_branches(elements)
    assert len(branches) == 1
    branch = branches[0]
    assert branch.anchor_keyids == {
        "BREAKER": "top-b",
        "DISCONNECTOR": "top-d",
        "GROUNDDISCONNECTOR": "top-g",
    }

    ids = _feeder_anchor_keyids_for_db(elements)
    assert ids == {
        "BREAKER": ["top-b"],
        "DISCONNECTOR": ["top-d"],
        "GROUNDDISCONNECTOR": ["top-g"],
    }
    assert "downstream-b" not in ids["BREAKER"]


def test_valid_head_triplet_colours_entire_downstream_component_to_terminal():
    elements = _fixture()
    branches = _discover_feeder_root_branches(elements)
    rows = [
        _row("30", "T1"),
        _row("40", "DOWNSTREAM-CB", "CB"),
        _row("50", "T2"),
    ]
    stats = _infer_feeder_membership(
        elements=elements,
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "top-b"): _ctx("BREAKER", "7001"),
            ("DISCONNECTOR", "top-d"): _ctx("DISCONNECTOR", "8001"),
            ("GROUNDDISCONNECTOR", "top-g"): _ctx("GROUNDDISCONNECTOR", "9001"),
        },
        # No DB record is supplied for downstream-b on purpose.
        anchor_issues={("BREAKER", "downstream-b"): "must never be consulted"},
        database_lookup_enabled=True,
        feeder_root_branches=branches,
    )

    assert [row["所属馈线"] for row in rows] == ["AJWD AH310"] * 3
    assert all(row["馈线判断来源"] == "DB_TRIPLE_TOPOLOGY" for row in rows)
    assert stats["primary_resolved"] == 3
    assert stats["anchor_total"] == 3
    assert stats["anchor_unresolved"] == 0


def test_missing_one_head_db_association_still_uses_consistent_remaining_anchors():
    elements = _fixture()
    branches = _discover_feeder_root_branches(elements)
    rows = [_row("30", "T1"), _row("50", "T2")]
    stats = _infer_feeder_membership(
        elements=elements,
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "top-b"): _ctx("BREAKER", "7001"),
            ("DISCONNECTOR", "top-d"): _ctx("DISCONNECTOR", "8001"),
        },
        anchor_issues={("GROUNDDISCONNECTOR", "top-g"): "BAY_ID为空"},
        database_lookup_enabled=True,
        feeder_root_branches=branches,
    )
    assert [row["所属馈线"] for row in rows] == ["AJWD AH310", "AJWD AH310"]
    assert stats["primary_resolved"] == 2
    assert stats["anchor_unresolved"] == 1
    assert any("2/3" in warning for warning in stats["warnings"])


def test_release_version_218144():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
