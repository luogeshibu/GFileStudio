from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_rule_engine import repair_tree_duplicates_strict, scan_file_against_rules
from g_file_studio.services.id_rule_service import IdRuleService


def test_duplicate_repair_uses_same_type_max_full_id(tmp_path: Path):
    xml = (
        '<G><Layer>'
        '<Text id="8000161"/>'
        '<FeedLine id="35000162"/>'
        '<ConnectLine id="34000138"/>'
        '<ConnectLine id="34000138"/>'
        '</Layer></G>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    rules = IdRuleService(tmp_path / "rules.json").load_rules()
    result = repair_tree_duplicates_strict(tree, tmp_path / "a.g", rules)
    ids = [e.get("id") for e in list(tree.getroot()[0])]
    assert result.changed_element_ids == 1
    assert "34000139" in ids


def test_scan_rejects_connectline_total_length_change(tmp_path: Path):
    path = tmp_path / "prefix.g"
    path.write_text(
        '<G><Layer>'
        '<ConnectLine id="34000053"/>'
        '<ConnectLine id="34001838"/>'
        '<ConnectLine id="340123456"/>'
        '<Text id="8000144"/>'
        '</Layer></G>', encoding="utf-8")
    rules = IdRuleService(tmp_path / "rules2.json").load_rules()
    scan = scan_file_against_rules(path, rules)
    assert scan.type_max_ids["ConnectLine"] == "34001838"
    assert len(scan.changed_formats) == 1
    assert "340123456" in scan.changed_formats[0].sample_ids
