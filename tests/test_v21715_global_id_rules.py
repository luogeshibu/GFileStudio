import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from g_file_studio.services.id_rule_service import IdRuleService, IdRule
from g_file_studio.engines.id_rule_engine import scan_tree_against_rules


def test_delete_rule_persists_immediately(tmp_path):
    cfg = tmp_path / 'id_rules.json'
    service = IdRuleService(cfg)
    assert 'ConnectLine' in service.load_rules()
    service.remove('ConnectLine')
    assert 'ConnectLine' not in service.load_rules()
    data = json.loads(cfg.read_text(encoding='utf-8'))
    assert 'ConnectLine' in data['deleted_tags']


def test_scan_exposes_missing_type_candidate(tmp_path):
    root = ET.fromstring('<G><Layer><Foo id="52000123"/><Foo id="52000124"/></Layer></G>')
    tree = ET.ElementTree(root)
    scan = scan_tree_against_rules(tree, tmp_path/'x.g', {})
    assert 'Foo' in scan.observed
    assert scan.new_rule_candidates or scan.unknown_uninferable


def test_rule_prefix_and_total_length_strict():
    r = IdRule('ConnectLine','34',8)
    assert r.matches('34001838')
    assert not r.matches('140')
    assert not r.matches('340123456')
