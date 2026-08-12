from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_rule_engine import scan_tree_against_rules
from g_file_studio.processors.basic_processor import _process_layer
from g_file_studio.models import BasicSettings, InputMode
from g_file_studio.services.id_rule_service import IdRule
from g_file_studio.engines.rmu_identification_engine import identify_rmus


def test_scan_returns_all_complete_invalid_ids_not_only_samples(tmp_path):
    ids = [str(i) for i in range(1, 13)]
    xml = '<G><Layer>' + ''.join(f'<ConnectLine id="{v}"/>' for v in ids) + '</Layer></G>'
    tree = ET.ElementTree(ET.fromstring(xml))
    rules = {'ConnectLine': IdRule('ConnectLine', '34', 8, enabled=True, verified=True)}
    result = scan_tree_against_rules(tree, tmp_path / 'x.g', rules)
    assert len(result.changed_formats) == 1
    assert list(result.changed_formats[0].sample_ids) == ids


def test_delete_element_attribute_removes_key_not_element(tmp_path):
    tree = ET.ElementTree(ET.fromstring('<G><Layer><Text id="8000001" ts="A" foo="bar"/><Text id="8000002" ts="B" foo="baz"/></Layer></G>'))
    layer = next(iter(tree.getroot()))
    settings = BasicSettings(
        source_path=tmp_path / 'x.g', input_mode=InputMode.SINGLE_FILE, output_dir=tmp_path,
        delete_attribute=True, delete_attribute_target_tag='Text', delete_attribute_name='foo',
    )
    replaced, deleted_attrs, removed_elements, removed_ids = _process_layer(layer, settings)
    assert replaced == 0
    assert deleted_attrs == 2
    assert removed_elements == 0
    assert not removed_ids
    texts = list(layer)
    assert len(texts) == 2
    assert all('foo' not in text.attrib for text in texts)
    assert [text.get('ts') for text in texts] == ['A', 'B']


def _rmu_tree(name_nodes: str):
    xml = f'''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220"/>
    {name_nodes}
    <Text id="8000101" x="130" y="150" w="20" h="20" ts="Y1"/>
    <Text id="8000102" x="130" y="220" w="20" h="20" ts="Y2"/>
    <Text id="8000103" x="210" y="235" w="20" h="20" ts="Q1"/>
    <BusDis id="38000001" x="205" y="140" w="6" h="140" key_name="WRONG_BUS"/>
    <CBreakerDis id="117000001" x="130" y="150" w="40" h="40" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:x"/>
    <CBreakerDis id="117000002" x="130" y="220" w="40" h="40" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:x"/>
    <CBreakerDis id="117000003" x="210" y="230" w="34" h="38" devref="#Circuit_Breaker_NO-SMART.zwk.icn.g:x"/>
    <ZhaiWaiJieDiDaoZha id="188000001" x="120" y="180" w="42" h="28"/>
    </Layer></G>'''
    return ET.ElementTree(ET.fromstring(xml))


def test_rmu_selected_direction_only_and_dtext_supported():
    tree = _rmu_tree('''
      <DText id="3300001" x="150" y="65" w="90" h="25" ts="TOP-DTEXT"/>
      <Text id="8000202" x="150" y="325" w="90" h="25" ts="BOTTOM-TEXT" lcc="#00ff00"/>
    ''')
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == 'TOP-DTEXT'
    assert item.name_position == 'top'


def test_rmu_no_selected_direction_candidate_means_unrecognized_no_metadata_fallback():
    tree = _rmu_tree('<Text id="8000202" x="150" y="325" w="90" h="25" ts="BOTTOM-TEXT"/>')
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == ''
    assert item.name_position == ''
