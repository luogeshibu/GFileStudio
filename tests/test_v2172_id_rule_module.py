from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_rule_engine import scan_file_against_rules
from g_file_studio.services.id_rule_service import IdRule, IdRuleService


def test_rule_service_persists_only_id_rules(tmp_path: Path):
    service = IdRuleService(tmp_path / "rules.json")
    service.save_rules([IdRule("ConnectLine", "34", 8)])
    rule = service.load_rules()["ConnectLine"]
    assert rule.build(147) == "34000147"
    text = (tmp_path / "rules.json").read_text(encoding="utf-8")
    assert "Alias" not in text


def test_scan_reports_new_type_and_format_change(tmp_path: Path):
    path = tmp_path / "a.g"
    path.write_text(
        '<G><Layer>'
        '<ConnectLine id="35000001"/><ConnectLine id="35000002"/>'
        '<NewThing id="52000001"/><NewThing id="52000002"/>'
        '</Layer></G>', encoding="utf-8")
    rules = {"ConnectLine": IdRule("ConnectLine", "34", 8)}
    scan = scan_file_against_rules(path, rules)
    assert [x.tag for x in scan.changed_formats] == ["ConnectLine"]
    assert [x.tag for x in scan.new_rule_candidates] == ["NewThing"]
    assert scan.new_rule_candidates[0].prefix == "52"
    assert scan.new_rule_candidates[0].total_length == 8


def test_v2175_default_rules_use_prefix_and_total_length(tmp_path: Path):
    service = IdRuleService(tmp_path / "rules.json")
    rules = service.load_rules()
    assert rules["ConnectLine"].prefix == "34"
    assert rules["Text"].prefix == "8"
    assert rules["CBreakerDis"].prefix == "117"
    assert rules["Merge"].prefix == "20"
    assert rules["ConnectLine"].total_length == 8
    assert rules["ConnectLine"].matches("34001838")
    assert not rules["ConnectLine"].matches("340123456")
    assert not rules["ConnectLine"].matches("140")
    assert not rules["ConnectLine"].matches("45001838")


def test_v2173_scan_flags_short_connector_ids_as_format_change(tmp_path: Path):
    path = tmp_path / "short.g"
    path.write_text(
        '<G><Layer>'
        '<ConnectLine id="34000138"/><ConnectLine id="140"/>'
        '<Text id="8000144"/><Text id="8000145"/>'
        '</Layer></G>', encoding="utf-8")
    service = IdRuleService(tmp_path / "rules.json")
    scan = scan_file_against_rules(path, service.load_rules())
    assert [x.tag for x in scan.changed_formats] == ["ConnectLine"]
    assert scan.changed_formats[0].sample_ids == ("140",)
