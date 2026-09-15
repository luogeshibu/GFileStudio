from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _cabinet(rect_id: int, x: int, y: int, base: int) -> str:
    return f'''
    <rect id="{rect_id}" x="{x}" y="{y}" w="220" h="220" ls="2"/>
    <Text id="{base+1}" x="{x+30}" y="{y+50}" w="25" h="20" ts="Y1"/>
    <Text id="{base+2}" x="{x+30}" y="{y+130}" w="25" h="20" ts="Y2"/>
    <Text id="{base+3}" x="{x+130}" y="{y+120}" w="25" h="20" ts="Q1"/>
    <BusDis id="{base+4}" x="{x+105}" y="{y+40}" w="6" h="140" key_name=""/>
    <CBreakerDis id="{base+5}" x="{x+30}" y="{y+50}" w="40" h="40" p_NameString="Y1" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="{base+6}" x="{x+30}" y="{y+130}" w="40" h="40" p_NameString="Y2" devref="#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"/>
    <CBreakerDis id="{base+7}" x="{x+130}" y="{y+115}" w="34" h="38" p_NameString="Q1" devref="#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"/>
    <ZhaiWaiJieDiDaoZha id="{base+8}" x="{x+20}" y="{y+90}" w="42" h="28"/>
    '''


def test_auto_cluster_learns_top_and_green_ak_style_over_closer_annotations():
    parts = ['<G><Layer>']
    expected = {}
    for idx, x in enumerate((100, 450, 800), start=1):
        rect_id = 2000000 + idx
        parts.append(_cabinet(rect_id, x, 300, 8100000 + idx * 100))
        # True cabinet name is the repeated GREEN AK-* style, deliberately farther
        # away than two competing annotation rows.
        parts.append(f'<Text id="9000{idx}1" x="{x+45}" y="190" w="125" h="30" ts="AK-{900000+idx}" lcc="#00ff00" lc="0,255,0"/>')
        parts.append(f'<Text id="9000{idx}2" x="{x+55}" y="230" w="110" h="30" ts="K-{idx:05d}" lcc="#ffff00" lc="255,255,0"/>')
        parts.append(f'<Text id="9000{idx}3" x="{x+70}" y="260" w="70" h="25" ts="A-{idx}" lcc="#ffffff" lc="255,255,255"/>')
        expected[str(rect_id)] = f'AK-{900000+idx}'
    parts.append('</Layer></G>')
    tree = ET.ElementTree(ET.fromstring(''.join(parts)))

    result = identify_rmus(
        tree,
        Path('abha.g'),
        name_positions=('top', 'bottom', 'left', 'right'),
        name_resolution_mode='auto_cluster',
        smart_in_type=True,
    )
    by_id = {item.rect_id: item for item in result.items}
    assert {rid: by_id[rid].name for rid in expected} == expected
    assert {by_id[rid].name_position for rid in expected} == {'top'}
    assert not any('指定方向内存在多个柜名候选' in warning for warning in result.warnings)


def test_auto_cluster_real_jed_sample_learns_top_layout():
    source = Path('/mnt/data/JED-STH-ADEL-22.sln.pic.g')
    if not source.exists():
        return
    result = identify_rmus(
        ET.parse(source), source,
        name_positions=('top', 'bottom', 'left', 'right'),
        name_resolution_mode='auto_cluster',
        smart_in_type=True,
    )
    assert result.cabinet_count == 9
    assert result.named_count == 9
    assert {item.name_position for item in result.items} == {'top'}
    names = {item.name for item in result.items}
    assert {'29521', '29520', '26660', '26661', '29499', '8755', '43316', '8754', '29749'} <= names
    assert not any('指定方向' in warning for warning in result.warnings)


def test_auto_cluster_real_mak_sample_learns_right_layout():
    source = Path('/mnt/data/MAK-XXX-OSLA-08-MNA2-35-MNA4-32-MNA3-29-MNA4-12-ARF2-07-MNA2-22-WDJL-03-MNA2-32.sln.pic(2).g')
    if not source.exists():
        return
    result = identify_rmus(
        ET.parse(source), source,
        name_positions=('top', 'bottom', 'left', 'right'),
        name_resolution_mode='auto_cluster',
        smart_in_type=True,
    )
    assert result.cabinet_count == 84
    assert result.named_count == 84
    assert {item.name_position for item in result.items} == {'right'}
    by_id = {item.rect_id: item.name for item in result.items}
    assert by_id['2000089'] == '7436'
    assert by_id['2000120'] == '17297'
    assert by_id['2000151'] == '33149'
    assert by_id['2000637'] == '17296'
    assert by_id['2001306'] == '18608'
    assert not any('指定方向' in warning for warning in result.warnings)
