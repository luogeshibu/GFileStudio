from __future__ import annotations

import xml.etree.ElementTree as ET

from g_file_studio.services.database_service import TopologyFeederAnchorContext
from g_file_studio.services.symbol_inventory_service import _infer_feeder_membership


def _row(element_id: str, *, name: str = "D") -> dict[str, object]:
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


def _ctx(table: str, device_id: str, station: str, feeder: str, bay_id: str):
    return TopologyFeederAnchorContext(
        table_name=table,
        device_id=device_id,
        device_name="",
        bay_id=bay_id,
        station_name=station,
        feeder_name=feeder,
    )


def test_three_anchor_types_same_bay_propagate_downstream_and_station_bus_blocks_sideways():
    bus = ET.Element("Bus", id="100", node_area="0,0,11;1,0,21")

    b1 = ET.Element("CBreaker", id="1", keyid="40701", node_area="0,0,11;1,0,12")
    d1 = ET.Element("Disconnector", id="5", keyid="40801", node_area="0,0,12;1,0,13")
    g1 = ET.Element("GroundDisconnector", id="6", keyid="40901", node_area="0,0,13;1,0,14")
    l11 = ET.Element("ConnectLine", id="11", link="0,0,100;1,0,1")
    l12 = ET.Element("ConnectLine", id="12", link="0,0,1;1,0,5")
    l13 = ET.Element("ConnectLine", id="13", link="0,0,5;1,0,6")
    l14 = ET.Element("ConnectLine", id="14", link="0,0,6;1,0,2")
    t1 = ET.Element("TransformerDis", id="2", link="0,0,14")

    b2 = ET.Element("CBreaker", id="3", keyid="40702", node_area="0,0,21;1,0,22")
    d2 = ET.Element("Disconnector", id="7", keyid="40802", node_area="0,0,22;1,0,23")
    g2 = ET.Element("GroundDisconnector", id="8", keyid="40902", node_area="0,0,23;1,0,24")
    l21 = ET.Element("ConnectLine", id="21", link="0,0,100;1,0,3")
    l22 = ET.Element("ConnectLine", id="22", link="0,0,3;1,0,7")
    l23 = ET.Element("ConnectLine", id="23", link="0,0,7;1,0,8")
    l24 = ET.Element("ConnectLine", id="24", link="0,0,8;1,0,4")
    t2 = ET.Element("TransformerDis", id="4", link="0,0,24")

    rows = [_row("2", name="T1"), _row("4", name="T2")]
    stats = _infer_feeder_membership(
        elements=[bus, b1, d1, g1, l11, l12, l13, l14, t1, b2, d2, g2, l21, l22, l23, l24, t2],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "40701"): _ctx("BREAKER", "7001", "AJWD", "AH327", "6001"),
            ("DISCONNECTOR", "40801"): _ctx("DISCONNECTOR", "8001", "AJWD", "AH327", "6001"),
            ("GROUNDDISCONNECTOR", "40901"): _ctx("GROUNDDISCONNECTOR", "9001", "AJWD", "AH327", "6001"),
            ("BREAKER", "40702"): _ctx("BREAKER", "7002", "AJWD", "AH328", "6002"),
            ("DISCONNECTOR", "40802"): _ctx("DISCONNECTOR", "8002", "AJWD", "AH328", "6002"),
            ("GROUNDDISCONNECTOR", "40902"): _ctx("GROUNDDISCONNECTOR", "9002", "AJWD", "AH328", "6002"),
        },
        database_lookup_enabled=True,
    )

    assert rows[0]["所属馈线"] == "AJWD AH327"
    assert rows[0]["馈线站名"] == "AJWD"
    assert rows[0]["馈线判断来源"] == "DB_TRIPLE_TOPOLOGY"
    assert rows[1]["所属馈线"] == "AJWD AH328"
    assert rows[1]["馈线站名"] == "AJWD"
    assert stats["primary_resolved"] == 2
    assert stats["feeder_count"] == 2
    assert stats["validated_bay_count"] == 2


def test_single_resolved_breaker_is_not_enough_to_assign_feeder():
    brk = ET.Element("CBreaker", id="1", keyid="40701", node_area="0,0,10")
    line = ET.Element("ConnectLine", id="10", link="0,0,1;1,0,2")
    target = ET.Element("TransformerDis", id="2", link="0,0,10")
    rows = [_row("2", name="T")]

    stats = _infer_feeder_membership(
        elements=[brk, line, target],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "40701"): _ctx("BREAKER", "7001", "AJWD", "AD505_TR2_29", "6001"),
        },
        database_lookup_enabled=True,
    )

    assert rows[0]["所属馈线"] == ""
    assert rows[0]["馈线判断来源"] == "NO_DB_TRIPLE_ANCHOR"
    assert stats["validated_bay_count"] == 0
    assert stats["primary_resolved"] == 0


def test_unassociated_407_408_409_anchor_is_hard_barrier_for_downstream():
    resolved = ET.Element("CBreaker", id="1", keyid="40701", node_area="0,0,10")
    line_a = ET.Element("ConnectLine", id="10", link="0,0,1;1,0,20")
    unresolved = ET.Element("Disconnector", id="20", keyid="40899", node_area="0,0,10;1,0,30")
    line_b = ET.Element("ConnectLine", id="30", link="0,0,20;1,0,2")
    target = ET.Element("TransformerDis", id="2", link="0,0,30")
    rows = [_row("2", name="T")]

    stats = _infer_feeder_membership(
        elements=[resolved, line_a, unresolved, line_b, target],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={
            ("BREAKER", "40701"): _ctx("BREAKER", "40701", "AJWD", "AH327", "JED-CTL AJWD 13.8kV AH327"),
        },
        anchor_issues={("DISCONNECTOR", "40899"): "BAY_ID empty"},
        database_lookup_enabled=True,
    )

    assert rows[0]["所属馈线"] == ""
    assert rows[0]["馈线判断来源"] == "NO_DB_TRIPLE_ANCHOR"
    assert stats["warnings"]
    assert "入口三设备" in stats["warnings"][0]


def test_when_all_three_anchor_types_have_no_valid_db_association_stop_feeder_analysis_with_warning():
    brk = ET.Element("CBreaker", id="1", keyid="40701", node_area="0,0,10")
    line = ET.Element("ConnectLine", id="10", link="0,0,1;1,0,2")
    target = ET.Element("TransformerDis", id="2", link="0,0,10")
    rows = [_row("2", name="T")]

    stats = _infer_feeder_membership(
        elements=[brk, line, target],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={},
        anchor_issues={("BREAKER", "40701"): "not found"},
        database_lookup_enabled=True,
    )

    assert rows[0]["所属馈线"] == ""
    assert rows[0]["馈线判断来源"] == "NO_DB_TRIPLE_ANCHOR"
    assert stats["primary_resolved"] == 0
    assert stats["warnings"]
    assert "请优先" in stats["warnings"][0]


def test_no_spatial_or_feedline_text_fallback_without_db_anchor():
    feed = ET.Element("FeedLine", id="10", key_name="dms_section_device AJWD 27 AJWD_27_SEC001 id", link="0,0,2")
    target = ET.Element("TransformerDis", id="2", link="0,0,10", x="100", y="100")
    rows = [_row("2", name="T")]
    _infer_feeder_membership(
        elements=[feed, target],
        contexts=[],
        device_rows=rows,
        symbol_rows=[],
        anchor_contexts={},
        database_lookup_enabled=True,
    )
    assert rows[0]["所属馈线"] == ""
    assert rows[0]["馈线冲突"] == ""


def test_database_anchor_resolver_queries_only_407_408_409_tables_and_follows_keyid_chain(tmp_path, monkeypatch):
    from g_file_studio.services.database_service import OracleDatabaseService
    from g_file_studio.services.user_settings_service import UserSettingsService

    settings = UserSettingsService(tmp_path / "settings.ini")
    service = OracleDatabaseService(settings)
    seen_sql: list[str] = []

    decoded = {
        1001: (7001, 407, 30),
        1002: (8001, 408, 30),
        1003: (9001, 409, 30),
    }

    def fake_query(sql, params=None, **kwargs):
        sql_u = sql.upper()
        seen_sql.append(sql_u)
        params = dict(params or {})
        if "LONG2_TO_LONG1" in sql_u:
            rows = []
            for key in sorted(params):
                keyid = int(params[key])
                if key.startswith("key_"):
                    device_id, tab_no, col_no = decoded[keyid]
                    rows.append((keyid, device_id, tab_no, col_no))
            return ["KEY_ID", "DEVICE_ID", "TAB_NO", "COL_NO"], rows
        if "FROM SYS_TABLE_INFO" in sql_u:
            return ["TABLE_ID", "TABLE_NAME_ENG"], [
                (407, "breaker"), (408, "disconnector"), (409, "grounddisconnector")
            ]
        if "FROM BREAKER" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [("7001", "B303", "5001", "6001")]
        if "FROM DISCONNECTOR" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [("8001", "D343", "5001", "6002")]
        if "FROM GROUNDDISCONNECTOR" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [("9001", "K309", "5001", "6003")]
        if "FROM BAY" in sql_u:
            return ["ID", "NAME", "ST_ID"], [
                ("6001", "AH303", "5001"),
                ("6002", "AH343", "5001"),
                ("6003", "AH309", "5001"),
            ]
        if "FROM SUBSTATION" in sql_u:
            return ["ID", "NAME"], [("5001", "ABH")]
        raise AssertionError(sql)

    monkeypatch.setattr(service, "query", fake_query)
    resolved, issues = service.resolve_topology_feeder_anchors({
        "BREAKER": ["1001"],
        "DISCONNECTOR": ["1002"],
        "GROUNDDISCONNECTOR": ["1003"],
    })

    assert not issues
    assert resolved[("BREAKER", "1001")].device_id == "7001"
    assert resolved[("BREAKER", "1001")].station_name == "ABH"
    assert resolved[("BREAKER", "1001")].feeder_name == "AH303"
    assert resolved[("DISCONNECTOR", "1002")].feeder_name == "AH343"
    assert resolved[("GROUNDDISCONNECTOR", "1003")].feeder_name == "AH309"
    assert any("LONG2_TO_LONG1" in sql for sql in seen_sql)
    assert any("FROM SYS_TABLE_INFO" in sql for sql in seen_sql)
    assert any("FROM BAY" in sql for sql in seen_sql)
    assert any("FROM SUBSTATION" in sql for sql in seen_sql)
    assert all(any(f"FROM {name}" in sql for name in ("BREAKER", "DISCONNECTOR", "GROUNDDISCONNECTOR")) for sql in seen_sql if "SELECT TO_CHAR(ID), NAME, TO_CHAR(ST_ID), TO_CHAR(BAY_ID)" in sql)
