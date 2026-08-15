from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _tree(*, q_devref: str = '#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART', labels: str = ''):
    if not labels:
        labels = '''
        <Text id="8000010" x="130" y="150" w="20" h="20" ts="Y1"/>
        <Text id="8000011" x="130" y="190" w="20" h="20" ts="Y2"/>
        <Text id="8000012" x="130" y="230" w="20" h="20" ts="Y3"/>
        <Text id="8000013" x="235" y="190" w="20" h="20" ts="Q1"/>
        '''
    xml = f'''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220" ls="2"/>
    <Text id="8000002" x="155" y="60" w="90" h="30" ts="33404" lc="0,255,0" lcc="#00ff00"/>
    {labels}
    <BusDis id="3800004" x="205" y="140" w="6" h="140"/>
    <ZhaiWaiJieDiDaoZha id="188000009" x="120" y="260" w="42" h="28"/>
    <CBreakerDis id="117000005" x="130" y="145" w="40" h="40" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000006" x="130" y="185" w="40" h="40" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000007" x="130" y="225" w="40" h="40" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000008" x="230" y="185" w="34" h="38" devref="{q_devref}"/>
    </Layer></G>'''
    return ET.ElementTree(ET.fromstring(xml))


def test_yq_and_devref_crosscheck_passes_when_types_match():
    item = identify_rmus(_tree(), Path('x.g'), name_positions=('top',)).items[0]
    assert item.name == '33404'
    assert item.rmu_type == '3L1T'
    assert item.text_yq_type == '3L1T'
    assert item.devref_type == '3L1T'
    assert item.type_source == 'TEXT_YQ'
    assert item.type_cross_check == 'YES'
    assert item.type_validation_status == 'PASS'


def test_crosscheck_fails_when_devref_type_disagrees_with_yq_text():
    item = identify_rmus(
        _tree(q_devref='#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART'),
        Path('x.g'), name_positions=('top',)
    ).items[0]
    assert item.rmu_type == '3L1T'  # final type remains Y/Q-primary
    assert item.text_yq_type == '3L1T'
    assert item.devref_type == '4L0T'
    assert item.type_cross_check == 'NO'
    assert item.type_validation_status == 'FAIL'
    assert '不一致' in item.type_cross_note


def test_yq_sequence_gap_is_reported_even_when_counts_match():
    labels = '''
    <Text id="8000010" x="130" y="150" w="20" h="20" ts="Y1"/>
    <Text id="8000011" x="130" y="190" w="20" h="20" ts="Y2"/>
    <Text id="8000012" x="130" y="230" w="20" h="20" ts="Y4"/>
    <Text id="8000013" x="235" y="190" w="20" h="20" ts="Q1"/>
    '''
    item = identify_rmus(_tree(labels=labels), Path('x.g'), name_positions=('top',)).items[0]
    assert item.text_yq_type == '3L1T'
    assert item.devref_type == '3L1T'
    assert item.type_validation_status == 'FAIL'
    assert '序号' in item.type_cross_note
