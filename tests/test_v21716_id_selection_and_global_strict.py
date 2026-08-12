import json
import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.id_rule_engine import normalize_tree_ids_strict
from g_file_studio.services.id_rule_service import IdRule, IdRuleService


def test_existing_invalid_id_can_be_preserved_when_global_strict_is_off(tmp_path):
    tree = ET.ElementTree(ET.fromstring('<G><Layer><ConnectLine id="140"/><ConnectLine id="34000010"/></Layer></G>'))
    rules = {'ConnectLine': IdRule('ConnectLine', '34', 8)}
    result = normalize_tree_ids_strict(tree, tmp_path / 'x.g', rules, repair_invalid_formats=False)
    ids = [e.get('id') for e in tree.getroot().find('Layer')]
    assert ids == ['140', '34000010']
    assert result.format_fixed_count == 0


def test_rule_service_forces_loaded_rules_enabled(tmp_path):
    cfg = tmp_path / 'id_rules.json'
    cfg.write_text(json.dumps({
        'version': 6,
        'rules': [{'tag': 'Foo', 'prefix': '52', 'total_length': 8, 'enabled': False, 'verified': True, 'note': ''}],
        'deleted_tags': [],
    }), encoding='utf-8')
    rule = IdRuleService(cfg).load_rules()['Foo']
    assert rule.enabled is True


def test_id_page_first_column_is_selection_not_enable():
    source = Path('g_file_studio/ui/pages/id_page.py').read_text(encoding='utf-8')
    assert '["选择", "状态", "元素类型"' in source
    assert 'def _checked_tags' in source
    assert '一个或多个要删除的规则' in source
    assert 'self.global_strict.setEnabled(False)' not in source


def test_merge_output_name_is_placed_after_layout_and_before_task_panel():
    source = Path('g_file_studio/ui/pages/merge_page.py').read_text(encoding='utf-8')
    layout_pos = source.index('self.layout.addWidget(settings_box)')
    output_pos = source.index('output_name_box = QGroupBox("输出文件")')
    task_pos = source.index('self.task = TaskPanel()')
    assert layout_pos < output_pos < task_pos
