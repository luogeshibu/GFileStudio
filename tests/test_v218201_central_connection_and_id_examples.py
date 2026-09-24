from __future__ import annotations

import json
from pathlib import Path

from g_file_studio.services.classification_registry_service import ClassificationRegistryService
from g_file_studio.services.id_rule_service import IdRule, IdRuleService


def test_connection_page_explicitly_names_database_and_file_server() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("中央配置（Oracle 数据库 + 文件服务器）")' in source
    assert 'setText("从中央同步数据库和文件服务器")' in source
    assert 'setText("发布数据库和文件服务器到中央")' in source
    assert "Oracle 数据库 + 文件服务器（SSH/SFTP）" in source
    assert "database.json（Oracle 数据库）" in source
    assert "file_server.json（文件服务器）" in source
    assert "中央同步/发布内容：Oracle 数据库 + 文件服务器（SSH/SFTP）" in source


def test_id_rule_json_persists_valid_example(tmp_path: Path) -> None:
    path = tmp_path / "id_rules.json"
    service = IdRuleService(path)
    service.save_rules([IdRule("Bus", "30", 8), IdRule("CBreaker", "100", 9)])
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] >= 7
    rows = {row["tag"]: row for row in payload["rules"]}
    assert rows["Bus"]["valid_example"] == "30000001"
    assert rows["CBreaker"]["valid_example"] == "100000001"


def test_export_and_central_validation_keep_valid_example(tmp_path: Path) -> None:
    service = IdRuleService(tmp_path / "id_rules.json")
    service.save_rules([IdRule("Text", "8", 7)])
    payload = service.export_payload()
    exported = {row["tag"]: row for row in payload["rules"]}
    assert exported["Text"]["valid_example"] == "8000001"
    validated = ClassificationRegistryService._validate_id_rules_config(payload)
    assert validated["version"] >= 7
    validated_rows = {row["tag"]: row for row in validated["rules"]}
    assert validated_rows["Text"]["valid_example"] == "8000001"
