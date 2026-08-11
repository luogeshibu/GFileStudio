from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def test_rmu_name_type_and_smart_column():
    xml = '''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220" ls="2"/>
    <Text id="8000002" x="160" y="60" w="90" h="30" ts="RMU-A12" lc="0,255,0" lcc="#00ff00"/>
    <Text id="8000003" x="190" y="105" w="60" h="20" ts="SMART"/>
    <Text id="8000010" x="130" y="150" w="20" h="20" ts="Y1"/>
    <Text id="8000011" x="130" y="220" w="20" h="20" ts="Y2"/>
    <Text id="8000012" x="240" y="150" w="20" h="20" ts="Y3"/>
    <Text id="8000013" x="210" y="230" w="20" h="20" ts="Q1"/>
    <BusDis id="3800004" x="205" y="140" w="6" h="140"/>
    <ZhaiWaiJieDiDaoZha id="188000009" x="120" y="180" w="42" h="28"/>
    <CBreakerDis id="117000005" x="130" y="150" w="40" h="40" p_NameString="Y1" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000006" x="130" y="220" w="40" h="40" p_NameString="Y2" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000007" x="240" y="150" w="40" h="40" p_NameString="Y3" devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>
    <CBreakerDis id="117000008" x="210" y="230" w="34" h="38" p_NameString="Q1" devref="#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"/>
    </Layer></G>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(tree, Path("x.g"), name_positions=("top",), smart_in_type=True)
    assert result.cabinet_count == 1
    item = result.items[0]
    assert item.name == "RMU-A12"
    assert item.name_position == "top"
    assert item.l_count == 3
    assert item.t_count == 1
    assert item.smart_count == 1
    assert item.rmu_type == "3L1T"


def test_rmu_name_can_be_right_side_and_smart_optional():
    xml = '''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220" ls="2"/>
    <Text id="8000002" x="330" y="180" w="80" h="30" ts="4726" lc="0,255,0" lcc="#00ff00"/>
    <Text id="8000010" x="130" y="150" w="20" h="20" ts="Y1"/>
    <Text id="8000011" x="130" y="220" w="20" h="20" ts="Y2"/>
    <Text id="8000013" x="210" y="230" w="20" h="20" ts="Q1"/>
    <BusDis id="3800004" x="205" y="140" w="6" h="140"/>
    <ZhaiWaiJieDiDaoZha id="188000009" x="120" y="180" w="42" h="28"/>
    <CBreakerDis id="117000005" x="130" y="150" w="40" h="40" p_NameString="Y1" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="117000006" x="130" y="220" w="40" h="40" p_NameString="Y2" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="117000008" x="210" y="230" w="34" h="38" p_NameString="Q1" devref="#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"/>
    </Layer></G>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(tree, Path("x.g"), name_positions=("right",), smart_in_type=False)
    item = result.items[0]
    assert item.name == "4726"
    assert item.rmu_type == "2L1T"
    assert item.smart_count == 0
