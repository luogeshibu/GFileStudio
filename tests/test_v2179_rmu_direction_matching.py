from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _tree(extra_texts: str):
    xml = f'''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220" ls="2"/>
    {extra_texts}
    <Text id="8000003" x="130" y="150" w="20" h="20" ts="Y1"/>
    <Text id="8000004" x="130" y="220" w="20" h="20" ts="Y2"/>
    <Text id="8000006" x="210" y="235" w="20" h="20" ts="Q1"/>
    <BusDis id="3800004" x="205" y="140" w="6" h="140"/>
    <CBreakerDis id="117000005" x="130" y="150" w="40" h="40" p_NameString="Y1" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="117000006" x="130" y="220" w="40" h="40" p_NameString="Y2" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="117000008" x="210" y="230" w="34" h="38" p_NameString="Q1" devref="#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"/>
    <ZhaiWaiJieDiDaoZha id="188000009" x="120" y="180" w="42" h="28"/>
    </Layer></G>'''
    return ET.ElementTree(ET.fromstring(xml))


def test_top_allows_small_bbox_overlap_with_frame():
    tree = _tree('<Text id="8000020" x="160" y="66" w="90" h="38" ts="30839"/>')
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == '30839'
    assert item.name_position == 'top'


def test_unselected_direction_is_never_used():
    tree = _tree('<Text id="8000020" x="160" y="330" w="90" h="30" ts="BOTTOM-NAME"/>')
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == ''


def test_multiple_selected_directions_choose_nearest_selected_only():
    tree = _tree('''
    <Text id="8000020" x="160" y="50" w="90" h="30" ts="TOP-NAME"/>
    <Text id="8000021" x="330" y="190" w="90" h="30" ts="RIGHT-NAME"/>
    ''')
    item = identify_rmus(tree, Path('x.g'), name_positions=('top','right')).items[0]
    assert item.name == 'RIGHT-NAME'
    assert item.name_position == 'right'
