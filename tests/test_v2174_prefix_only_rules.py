from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_rule_engine import repair_tree_duplicates_strict, scan_file_against_rules
from g_file_studio.services.id_rule_service import IdRuleService


def test_connectline_prefix_and_length_accepts_valid_eight_digit_ids(tmp_path: Path):
    path = tmp_path / "a.g"
    path.write_text(
        '<G><Layer>'
        '<ConnectLine id="34001835"/><ConnectLine id="34001836"/>'
        '<ConnectLine id="34001837"/><ConnectLine id="34001838"/>'
        '</Layer></G>', encoding="utf-8")
    rules = IdRuleService(tmp_path / "rules.json").load_rules()
    scan = scan_file_against_rules(path, rules)
    assert scan.changed_formats == []
    assert scan.type_max_ids["ConnectLine"] == "34001838"


def test_duplicate_connectline_uses_max_full_id_plus_one(tmp_path: Path):
    tree = ET.ElementTree(ET.fromstring(
        '<G><Layer>'
        '<ConnectLine id="34001835"/><ConnectLine id="34001838"/>'
        '<ConnectLine id="34001835"/>'
        '</Layer></G>'
    ))
    rules = IdRuleService(tmp_path / "rules.json").load_rules()
    result = repair_tree_duplicates_strict(tree, tmp_path / "a.g", rules)
    ids = [e.get("id") for e in tree.getroot().find("Layer")]
    assert result.changed_element_ids == 1
    assert ids[-1] == "34001839"


def test_connectline_wrong_length_is_reported(tmp_path: Path):
    path = tmp_path / "bad.g"
    path.write_text(
        '<G><Layer><ConnectLine id="34001835"/><ConnectLine id="140"/></Layer></G>',
        encoding="utf-8",
    )
    rules = IdRuleService(tmp_path / "rules.json").load_rules()
    scan = scan_file_against_rules(path, rules)
    assert len(scan.changed_formats) == 1
    assert "140" in scan.changed_formats[0].sample_ids
