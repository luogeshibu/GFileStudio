from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.services.database_service import TopologyFeederAnchorContext
from g_file_studio.services.symbol_inventory_service import _infer_feeder_membership


def _ctx(table: str, bay: str, feeder: str) -> TopologyFeederAnchorContext:
    return TopologyFeederAnchorContext(
        table_name=table,
        device_id=f"dev-{table}",
        device_name="",
        bay_id=bay,
        station_name="AJWD",
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


def _branched_fixture() -> list[ET.Element]:
    # Station bus -> disconnector -> breaker.  The ground disconnector is a side
    # branch below the breaker, matching the real AJWD feeder-head layout.
    bus = ET.Element("Bus", id="100", node_area="0,0,11")
    l11 = ET.Element("ConnectLine", id="11", link="0,0,100;1,0,2")
    d = ET.Element("Disconnector", id="2", keyid="top-d", node_area="0,0,11;1,0,12")
    l12 = ET.Element("ConnectLine", id="12", link="0,0,2;1,0,1")
    b = ET.Element("CBreaker", id="1", keyid="top-b", node_area="0,0,12;1,0,13")
    l13 = ET.Element("ConnectLine", id="13", link="0,0,1;1,0,14;1,0,15")
    g = ET.Element("GroundDisconnector", id="3", keyid="top-g", node_area="0,0,14")
    lg = ET.Element("ConnectLine", id="14", link="0,0,13;1,0,3")

    # Multi-branch downstream topology.  None of these devices has a usable DB
    # feeder association; they must inherit solely from the breaker root.
    trunk = ET.Element("FeedLine", id="15", link="0,0,13;1,0,20")
    busdis = ET.Element("BusDis", id="20", node_area="0,0,15;1,0,21;1,0,22")
    l21 = ET.Element("ConnectLine", id="21", link="0,0,20;1,0,30")
    l22 = ET.Element("FeedLine", id="22", link="0,0,20;1,0,40")
    t1 = ET.Element("TransformerDis", id="30", node_area="0,0,21")
    t2 = ET.Element("TransformerDis", id="40", node_area="0,0,22;1,0,23")
    l23 = ET.Element("ConnectLine", id="23", link="0,0,40;1,0,50")
    downstream_cb = ET.Element("CBreaker", id="50", keyid="must-not-query", node_area="0,0,23;1,0,24")
    terminal = ET.Element("FeedLine", id="24", link="0,0,50;1,0,60")
    t3 = ET.Element("TransformerDis", id="60", node_area="0,0,24")
    return [bus, l11, d, l12, b, l13, g, lg, trunk, busdis, l21, l22, t1, t2, l23, downstream_cb, terminal, t3]


def test_cbreaker_bay_is_authoritative_even_if_other_head_devices_have_stale_bays():
    rows = [_row("30", "T1"), _row("40", "T2"), _row("50", "DOWNSTREAM-CB"), _row("60", "T3")]
    stats = _infer_feeder_membership(
        elements=_branched_fixture(),
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "top-b"): _ctx("BREAKER", "313", "AH313"),
            ("DISCONNECTOR", "top-d"): _ctx("DISCONNECTOR", "999", "OLD-D"),
            ("GROUNDDISCONNECTOR", "top-g"): _ctx("GROUNDDISCONNECTOR", "998", "OLD-G"),
        },
        database_lookup_enabled=True,
    )
    assert [row["所属馈线"] for row in rows] == ["AJWD AH313"] * 4
    assert stats["primary_resolved"] == 4
    assert any("CBreaker(407)" in warning and "仅告警" in warning for warning in stats["warnings"])


def test_downstream_devices_never_need_their_own_database_association():
    rows = [_row("30", "T1"), _row("40", "T2"), _row("50", "DOWNSTREAM-CB"), _row("60", "T3")]
    stats = _infer_feeder_membership(
        elements=_branched_fixture(),
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={("BREAKER", "top-b"): _ctx("BREAKER", "313", "AH313")},
        anchor_issues={
            ("DISCONNECTOR", "top-d"): "未关联",
            ("GROUNDDISCONNECTOR", "top-g"): "未关联",
            ("BREAKER", "must-not-query"): "downstream keyid must never be consulted",
        },
        database_lookup_enabled=True,
    )
    assert [row["所属馈线"] for row in rows] == ["AJWD AH313"] * 4
    assert all(row["馈线判断来源"] == "DB_ANCHOR_TOPOLOGY" for row in rows)
    assert stats["primary_resolved"] == 4


def test_release_version_218146():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
