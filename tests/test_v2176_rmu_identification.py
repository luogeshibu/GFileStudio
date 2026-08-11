from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _tree(extra='', name='AK-500250', green=True, include_ground=True):
    color = 'lc="0,255,0" lcc="#00ff00"' if green else 'lc="255,170,0" lcc="#ffaa00"'
    ground = '<ZhaiWaiJieDiDaoZha id="188000009" x="120" y="180" w="42" h="28"/>' if include_ground else ''
    xml = f'''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220" ls="2"/>
    <Text id="8000002" x="160" y="60" w="90" h="30" ts="{name}" {color}/>
    <Text id="8000003" x="130" y="150" w="20" h="20" ts="Y1"/>
    <Text id="8000004" x="130" y="220" w="20" h="20" ts="Y2"/>
    <Text id="8000005" x="240" y="150" w="20" h="20" ts="Y3"/>
    <Text id="8000006" x="210" y="235" w="20" h="20" ts="Q1"/>
    <Text id="8000007" x="190" y="105" w="60" h="20" ts="SMART"/>
    <BusDis id="3800004" x="205" y="140" w="6" h="140"/>
    <CBreakerDis id="117000005" x="130" y="150" w="40" h="40" p_NameString="Y1" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000006" x="130" y="220" w="40" h="40" p_NameString="Y2" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000007" x="240" y="150" w="40" h="40" p_NameString="Y3" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000008" x="210" y="230" w="34" h="38" p_NameString="Q1" devref="#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"/>
    {ground}{extra}</Layer></G>'''
    return ET.ElementTree(ET.fromstring(xml))


def test_requires_all_three_mandatory_element_types():
    result = identify_rmus(_tree(include_ground=False), Path('x.g'), name_positions=('top',), smart_in_type=True)
    assert result.cabinet_count == 0


def test_green_name_yq_primary_and_smart_separate():
    result = identify_rmus(_tree(), Path('x.g'), name_positions=('top',), smart_in_type=True)
    item = result.items[0]
    assert item.name == 'AK-500250'
    assert item.rmu_type == '3L1T'
    assert item.l_count == 3 and item.t_count == 1
    assert item.smart_count == 1
    assert 'S' not in item.rmu_type


def test_non_green_single_name_is_selected_when_it_is_the_only_near_candidate():
    result = identify_rmus(_tree(green=False), Path('x.g'), name_positions=('top',), smart_in_type=False)
    assert result.items[0].name == 'AK-500250'


def test_device_fallback_when_yq_text_missing():
    tree = _tree()
    layer = next(iter(tree.getroot()))
    for node in list(layer):
        if node.tag == 'Text' and (node.get('ts') or '').startswith(('Y','Q')):
            layer.remove(node)
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',), smart_in_type=False).items[0]
    assert item.rmu_type == '3L1T'
    assert any('回退' in w for w in item.warnings)
