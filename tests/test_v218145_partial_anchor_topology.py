from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.services.database_service import TopologyFeederAnchorContext
from g_file_studio.services.symbol_inventory_service import _infer_feeder_membership


def _ctx(table: str, bay: str = "6001", station: str = "AJWD", feeder: str = "AH313") -> TopologyFeederAnchorContext:
    return TopologyFeederAnchorContext(
        table_name=table,
        device_id=f"dev-{table}",
        device_name="",
        bay_id=bay,
        station_name=station,
        feeder_name=feeder,
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


def _fixture() -> list[ET.Element]:
    bus = ET.Element("Bus", id="100", node_area="0,0,11")
    l11 = ET.Element("ConnectLine", id="11", link="0,0,100;1,0,2")
    d = ET.Element("Disconnector", id="2", keyid="top-d", node_area="0,0,11;1,0,12")
    l12 = ET.Element("ConnectLine", id="12", link="0,0,2;1,0,1")
    b = ET.Element("CBreaker", id="1", keyid="top-b", node_area="0,0,12;1,0,13")
    l13 = ET.Element("ConnectLine", id="13", link="0,0,1;1,0,3")
    g = ET.Element("GroundDisconnector", id="3", keyid="top-g", node_area="0,0,13;1,0,14")
    feed = ET.Element("FeedLine", id="14", link="0,0,3;1,0,20")
    busdis = ET.Element("BusDis", id="20", node_area="0,0,14;1,0,21")
    l21 = ET.Element("ConnectLine", id="21", link="0,0,20;1,0,30")
    t1 = ET.Element("TransformerDis", id="30", node_area="0,0,21;1,0,31")
    l31 = ET.Element("FeedLine", id="31", link="0,0,30;1,0,40")
    downstream_cb = ET.Element("CBreaker", id="40", keyid="downstream-must-not-query", node_area="0,0,31;1,0,41")
    l41 = ET.Element("ConnectLine", id="41", link="0,0,40;1,0,50")
    t2 = ET.Element("TransformerDis", id="50", node_area="0,0,41")
    return [bus, l11, d, l12, b, l13, g, feed, busdis, l21, t1, l31, downstream_cb, l41, t2]


def test_one_valid_head_anchor_colours_all_downstream_topology():
    rows = [_row("30", "T1"), _row("40", "DOWNSTREAM-CB"), _row("50", "T2")]
    stats = _infer_feeder_membership(
        elements=_fixture(),
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "top-b"): _ctx("BREAKER"),
        },
        anchor_issues={
            ("DISCONNECTOR", "top-d"): "数据库未关联",
            ("GROUNDDISCONNECTOR", "top-g"): "数据库未关联",
            ("BREAKER", "downstream-must-not-query"): "must never be consulted",
        },
        database_lookup_enabled=True,
    )
    assert [row["所属馈线"] for row in rows] == ["AJWD AH313"] * 3
    assert all(row["馈线判断来源"] == "DB_ANCHOR_TOPOLOGY" for row in rows)
    assert all(row["馈线证据设备数"] == 1 for row in rows)
    assert stats["primary_resolved"] == 3
    assert stats["direct_anchor_count"] == 1
    assert any("1/3" in warning for warning in stats["warnings"])


def test_two_resolved_head_anchors_same_bay_are_enough():
    rows = [_row("50", "T2")]
    stats = _infer_feeder_membership(
        elements=_fixture(),
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "top-b"): _ctx("BREAKER"),
            ("DISCONNECTOR", "top-d"): _ctx("DISCONNECTOR"),
        },
        anchor_issues={("GROUNDDISCONNECTOR", "top-g"): "BAY_ID为空"},
        database_lookup_enabled=True,
    )
    assert rows[0]["所属馈线"] == "AJWD AH313"
    assert rows[0]["馈线证据设备数"] == 2
    assert stats["primary_resolved"] == 1


def test_resolved_head_anchor_bay_conflict_keeps_authoritative_breaker_branch():
    rows = [_row("50", "T2")]
    stats = _infer_feeder_membership(
        elements=_fixture(),
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "top-b"): _ctx("BREAKER", bay="6001", feeder="AH313"),
            ("DISCONNECTOR", "top-d"): _ctx("DISCONNECTOR", bay="6002", feeder="AH314"),
        },
        database_lookup_enabled=True,
    )
    assert rows[0]["所属馈线"] == "AJWD AH313"
    assert stats["primary_resolved"] == 1
    assert any("CBreaker(407)" in warning and "仅告警" in warning for warning in stats["warnings"])


def test_no_head_anchor_keeps_branch_blank():
    rows = [_row("50", "T2")]
    stats = _infer_feeder_membership(
        elements=_fixture(),
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={},
        anchor_issues={
            ("BREAKER", "top-b"): "数据库未关联",
            ("DISCONNECTOR", "top-d"): "数据库未关联",
            ("GROUNDDISCONNECTOR", "top-g"): "数据库未关联",
        },
        database_lookup_enabled=True,
    )
    assert rows[0]["所属馈线"] == ""
    assert stats["primary_resolved"] == 0
    assert any("均未取得有效 BAY" in warning for warning in stats["warnings"])


def test_release_version_218145():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
