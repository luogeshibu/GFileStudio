from pathlib import Path

from g_file_studio.services.database_service import OracleDatabaseService
from g_file_studio.services.user_settings_service import UserSettingsService


def test_realistic_disconnector_keyid_chain_resolves_bay_and_station(tmp_path, monkeypatch):
    settings = UserSettingsService(tmp_path / "settings.ini")
    service = OracleDatabaseService(settings)
    seen_sql: list[str] = []

    keyid = "114841919346967980"
    device_id = "114841790497949100"
    bay_id = "114278840544526337"
    station_id = "113997365567815681"

    def fake_query(sql, params=None, **kwargs):
        sql_u = sql.upper()
        seen_sql.append(sql_u)
        if "LONG2_TO_LONG1" in sql_u:
            assert int((params or {})["key_0"]) == int(keyid)
            return ["KEY_ID", "DEVICE_ID", "TAB_NO", "COL_NO"], [
                (keyid, device_id, 408, 30)
            ]
        if "FROM SYS_TABLE_INFO" in sql_u:
            return ["TABLE_ID", "TABLE_NAME_ENG"], [(408, "disconnector")]
        if "FROM DISCONNECTOR" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [
                (device_id, "D303", station_id, bay_id)
            ]
        if "FROM BAY" in sql_u:
            return ["ID", "NAME", "ST_ID"], [(bay_id, "AH303", station_id)]
        if "FROM SUBSTATION" in sql_u:
            return ["ID", "NAME"], [(station_id, "ABH")]
        raise AssertionError(sql)

    monkeypatch.setattr(service, "query", fake_query)
    resolved, issues = service.resolve_topology_feeder_anchors(
        {"BREAKER": [], "DISCONNECTOR": [keyid], "GROUNDDISCONNECTOR": []}
    )

    assert not issues
    ctx = resolved[("DISCONNECTOR", keyid)]
    assert ctx.device_id == device_id
    assert ctx.bay_id == bay_id
    assert ctx.feeder_name == "AH303"
    assert ctx.station_name == "ABH"
    stat = service.last_topology_feeder_lookup_stats["DISCONNECTOR"]
    assert stat["requested"] == 1
    assert stat["decoded"] == 1
    assert stat["table_valid"] == 1
    assert stat["device_matched"] == 1
    assert stat["valid_bay_id"] == 1
    assert stat["bay_matched"] == 1
    assert stat["station_matched"] == 1
    assert stat["resolved"] == 1
    assert "device_id=114841790497949100" in stat["sample_resolved"][0]
    assert "ABH/AH303" in stat["sample_resolved"][0]
    assert any("GET_TAB_NO" in sql for sql in seen_sql)
    assert any("SYS_TABLE_INFO" in sql for sql in seen_sql)
    assert any("FROM BAY" in sql for sql in seen_sql)
    assert any("FROM SUBSTATION" in sql for sql in seen_sql)


def test_table_number_mismatch_blocks_anchor_before_device_query(tmp_path, monkeypatch):
    settings = UserSettingsService(tmp_path / "settings.ini")
    service = OracleDatabaseService(settings)
    seen_sql: list[str] = []

    def fake_query(sql, params=None, **kwargs):
        sql_u = sql.upper()
        seen_sql.append(sql_u)
        if "LONG2_TO_LONG1" in sql_u:
            return ["KEY_ID", "DEVICE_ID", "TAB_NO", "COL_NO"], [(1001, 7001, 408, 30)]
        if "FROM SYS_TABLE_INFO" in sql_u:
            return ["TABLE_ID", "TABLE_NAME_ENG"], [(408, "disconnector")]
        raise AssertionError(f"unexpected DB query after mismatch: {sql}")

    monkeypatch.setattr(service, "query", fake_query)
    resolved, issues = service.resolve_topology_feeder_anchors(
        {"BREAKER": ["1001"], "DISCONNECTOR": [], "GROUNDDISCONNECTOR": []}
    )

    assert not resolved
    assert ("BREAKER", "1001") in issues
    assert "tab_no=408" in issues[("BREAKER", "1001")]
    assert service.last_topology_feeder_lookup_stats["BREAKER"]["table_mismatch"] == 1
    assert not any("FROM BREAKER" in sql for sql in seen_sql)


def test_missing_device_bay_or_substation_remains_unresolved(tmp_path, monkeypatch):
    settings = UserSettingsService(tmp_path / "settings.ini")
    service = OracleDatabaseService(settings)

    def fake_query(sql, params=None, **kwargs):
        sql_u = sql.upper()
        if "LONG2_TO_LONG1" in sql_u:
            return ["KEY_ID", "DEVICE_ID", "TAB_NO", "COL_NO"], [(1002, 8002, 408, 30)]
        if "FROM SYS_TABLE_INFO" in sql_u:
            return ["TABLE_ID", "TABLE_NAME_ENG"], [(408, "disconnector")]
        if "FROM DISCONNECTOR" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [("8002", "DXX", "5001", None)]
        raise AssertionError(sql)

    monkeypatch.setattr(service, "query", fake_query)
    resolved, issues = service.resolve_topology_feeder_anchors(
        {"BREAKER": [], "DISCONNECTOR": ["1002"], "GROUNDDISCONNECTOR": []}
    )

    assert not resolved
    assert "BAY_ID 为空" in issues[("DISCONNECTOR", "1002")]
    stat = service.last_topology_feeder_lookup_stats["DISCONNECTOR"]
    assert stat["device_matched"] == 1
    assert stat["resolved"] == 0
    assert stat["unmatched"] == 1


def test_release_version_218141():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
