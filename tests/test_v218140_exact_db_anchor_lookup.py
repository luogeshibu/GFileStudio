from pathlib import Path

from g_file_studio.services.database_service import OracleDatabaseService
from g_file_studio.services.user_settings_service import UserSettingsService


def test_feeder_anchor_lookup_decodes_keyid_before_equipment_lookup(tmp_path, monkeypatch):
    settings = UserSettingsService(tmp_path / "settings.ini")
    service = OracleDatabaseService(settings)
    seen = []

    def fake_query(sql, params=None, **kwargs):
        sql_u = sql.upper()
        seen.append((sql_u, dict(params or {})))
        if "LONG2_TO_LONG1" in sql_u:
            values = sorted(int(v) for k, v in (params or {}).items() if k.startswith("key_"))
            mapping = {
                1001: (7001, 407, 30),
                1002: (8001, 408, 30),
                1003: (9001, 409, 30),
            }
            return ["KEY_ID", "DEVICE_ID", "TAB_NO", "COL_NO"], [
                (value, *mapping[value]) for value in values
            ]
        if "FROM SYS_TABLE_INFO" in sql_u:
            return ["TABLE_ID", "TABLE_NAME_ENG"], [
                (407, "breaker"), (408, "disconnector"), (409, "grounddisconnector")
            ]
        if "FROM BREAKER" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [("7001", "B303", "5001", "6001")]
        if "FROM DISCONNECTOR" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [("8001", "D303", "5001", "6001")]
        if "FROM GROUNDDISCONNECTOR" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], [("9001", "K303", "5001", "6001")]
        if "FROM BAY" in sql_u:
            return ["ID", "NAME", "ST_ID"], [("6001", "AH303", "5001")]
        if "FROM SUBSTATION" in sql_u:
            return ["ID", "NAME"], [("5001", "ABH")]
        raise AssertionError(sql)

    monkeypatch.setattr(service, "query", fake_query)
    resolved, issues = service.resolve_topology_feeder_anchors(
        {"BREAKER": ["1001"], "DISCONNECTOR": ["1002"], "GROUNDDISCONNECTOR": ["1003"]}
    )

    assert not issues
    assert len(resolved) == 3
    assert resolved[("BREAKER", "1001")].device_id == "7001"
    assert resolved[("BREAKER", "1001")].feeder_name == "AH303"
    assert resolved[("BREAKER", "1001")].station_name == "ABH"
    assert service.last_topology_feeder_lookup_stats["BREAKER"]["requested"] == 1
    assert service.last_topology_feeder_lookup_stats["BREAKER"]["decoded"] == 1
    assert service.last_topology_feeder_lookup_stats["BREAKER"]["resolved"] == 1
    assert any("LONG2_TO_LONG1" in sql for sql, _ in seen)
    assert any("SYS_TABLE_INFO" in sql for sql, _ in seen)


def test_lookup_stats_expose_invalid_and_unresolved_keyids(tmp_path, monkeypatch):
    settings = UserSettingsService(tmp_path / "settings.ini")
    service = OracleDatabaseService(settings)

    def fake_query(sql, params=None, **kwargs):
        sql_u = sql.upper()
        if "LONG2_TO_LONG1" in sql_u:
            return ["KEY_ID", "DEVICE_ID", "TAB_NO", "COL_NO"], [(1001, 7001, 407, 30)]
        if "FROM SYS_TABLE_INFO" in sql_u:
            return ["TABLE_ID", "TABLE_NAME_ENG"], [(407, "breaker")]
        if "FROM BREAKER" in sql_u:
            return ["ID", "NAME", "ST_ID", "BAY_ID"], []
        raise AssertionError(sql)

    monkeypatch.setattr(service, "query", fake_query)
    resolved, issues = service.resolve_topology_feeder_anchors(
        {"BREAKER": ["1001", "not-a-number"], "DISCONNECTOR": [], "GROUNDDISCONNECTOR": []}
    )

    assert not resolved
    assert ("BREAKER", "1001") in issues
    assert ("BREAKER", "not-a-number") in issues
    stat = service.last_topology_feeder_lookup_stats["BREAKER"]
    assert stat["requested"] == 2
    assert stat["decoded"] == 1
    assert stat["decode_failed"] == 1
    assert stat["resolved"] == 0
    assert stat["unmatched"] == 2
    assert set(stat["sample_unmatched"]) == {"1001", "not-a-number"}


def test_release_version_218141_from_former_140_regression():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
