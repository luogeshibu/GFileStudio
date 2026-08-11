from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _tree(name_texts):
    extra = []
    tid = 20
    for x,y,w,h,ts,lc,lcc in name_texts:
        extra.append(f'<Text id="80000{tid}" x="{x}" y="{y}" w="{w}" h="{h}" ts="{ts}" lc="{lc}" lcc="{lcc}"/>')
        tid += 1
    xml = f'''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220" ls="2"/>
    {''.join(extra)}
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


def test_single_near_name_does_not_need_green():
    tree = _tree([(160, 60, 90, 30, '19362', '255,255,255', '#ffffff')])
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == '19362'
    assert item.name_position == 'top'


def test_multiple_near_names_prefer_green():
    tree = _tree([
        (155, 63, 95, 22, 'K-01954', '255,170,0', '#ffaa00'),
        (155, 36, 95, 22, 'AK-500251', '0,255,0', '#00ff00'),
    ])
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == 'AK-500251'
    assert any('绿色优先' in w for w in item.warnings)


def test_far_text_is_not_taken_as_name():
    tree = _tree([(160, -300, 90, 30, 'FAR-001', '0,255,0', '#00ff00')])
    item = identify_rmus(tree, Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == ''
