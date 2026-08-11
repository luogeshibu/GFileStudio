from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _cabinet(rect_id: int, x: int, y: int, text_id_base: int) -> str:
    return f'''
    <rect id="{rect_id}" x="{x}" y="{y}" w="220" h="220" ls="2"/>
    <Text id="{text_id_base+1}" x="{x+30}" y="{y+50}" w="20" h="20" ts="Y1"/>
    <Text id="{text_id_base+2}" x="{x+30}" y="{y+120}" w="20" h="20" ts="Y2"/>
    <Text id="{text_id_base+3}" x="{x+120}" y="{y+120}" w="20" h="20" ts="Q1"/>
    <BusDis id="{380000000+rect_id}" x="{x+105}" y="{y+40}" w="6" h="140"/>
    <CBreakerDis id="{117000000+rect_id}" x="{x+30}" y="{y+50}" w="40" h="40" p_NameString="Y1" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="{117100000+rect_id}" x="{x+30}" y="{y+120}" w="40" h="40" p_NameString="Y2" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="{117200000+rect_id}" x="{x+120}" y="{y+115}" w="34" h="38" p_NameString="Q1" devref="#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"/>
    <ZhaiWaiJieDiDaoZha id="{188000000+rect_id}" x="{x+20}" y="{y+90}" w="42" h="28"/>
    '''


def test_global_one_to_one_prevents_neighbor_name_reuse():
    xml = '<G><Layer>'
    xml += _cabinet(2000001, 100, 200, 8000100)
    xml += _cabinet(2000002, 360, 200, 8000200)
    # Each name is above its own cabinet; first is slightly closer to both.
    xml += '<Text id="8000301" x="150" y="150" w="90" h="30" ts="CAB-A"/>'
    xml += '<Text id="8000302" x="410" y="145" w="90" h="30" ts="CAB-B"/>'
    xml += '</Layer></G>'
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(tree, Path('x.g'), name_positions=('top',))
    names = {item.rect_id: item.name for item in result.items}
    assert names['2000001'] == 'CAB-A'
    assert names['2000002'] == 'CAB-B'


def test_only_selected_direction_participates_even_when_other_is_closer():
    xml = '<G><Layer>' + _cabinet(2000001, 100, 200, 8000100)
    xml += '<Text id="8000301" x="150" y="120" w="90" h="30" ts="TOP-NAME"/>'
    xml += '<Text id="8000302" x="150" y="423" w="90" h="30" ts="BOTTOM-VERY-CLOSE"/>'
    xml += '</Layer></G>'
    tree = ET.ElementTree(ET.fromstring(xml))
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == 'TOP-NAME'
    assert item.name_position == 'top'


def test_multiple_selected_directions_still_never_use_unselected_direction():
    xml = '<G><Layer>' + _cabinet(2000001, 100, 200, 8000100)
    xml += '<Text id="8000301" x="150" y="120" w="90" h="30" ts="TOP-NAME"/>'
    xml += '<Text id="8000302" x="323" y="290" w="90" h="30" ts="RIGHT-NAME"/>'
    xml += '<Text id="8000303" x="150" y="423" w="90" h="30" ts="BOTTOM-NAME"/>'
    xml += '</Layer></G>'
    tree = ET.ElementTree(ET.fromstring(xml))
    item = identify_rmus(tree, Path('x.g'), name_positions=('top', 'right')).items[0]
    assert item.name in {'TOP-NAME', 'RIGHT-NAME'}
    assert item.name_position in {'top', 'right'}
    assert item.name != 'BOTTOM-NAME'
