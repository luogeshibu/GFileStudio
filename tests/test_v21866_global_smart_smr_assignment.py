from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _device(tag: str, elem_id: str, x: int, y: int, devref: str = '') -> str:
    dev = f' devref="{devref}"' if devref else ''
    return f'<{tag} id="{elem_id}" x="{x}" y="{y}" w="20" h="20"{dev}/>'


def test_smart_and_smr_are_global_unique_nearest_rmu_markers():
    xml = f'''<root>
      <Layer id="L1">
        <rect id="2001" x="0" y="100" w="200" h="200"/>
        {_device('BusDis', '2101', 80, 180)}
        {_device('CBreakerDis', '2201', 80, 210, 'Circuit_Breaker_NON-SMART')}
        {_device('ZhaiWaiJieDiDaoZha', '2301', 80, 240)}
        <Text id="2401" ts="10001" x="65" y="50" w="70" h="30"/>

        <rect id="2002" x="260" y="100" w="200" h="200"/>
        {_device('BusDis', '2102', 340, 180)}
        {_device('CBreakerDis', '2202', 340, 210, 'Circuit_Breaker_NON-SMART')}
        {_device('ZhaiWaiJieDiDaoZha', '2302', 340, 240)}
        <Text id="2402" ts="10002" x="325" y="50" w="70" h="30"/>

        <!-- Outside both frames, but nearer to RMU 2001. -->
        <Text id="8001" ts="SMART" x="210" y="150" w="30" h="20"/>
        <!-- Outside RMU 2002 on the right; globally assigned to RMU 2002. -->
        <Text id="8002" ts="SMR" x="465" y="180" w="30" h="20"/>
      </Layer>
    </root>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(
        tree,
        Path('sample.g'),
        name_positions=('top',),
        smart_in_type=True,
    )

    assert result.cabinet_count == 2
    by_rect = {item.rect_id: item for item in result.items}
    assert by_rect['2001'].smart_count == 1
    assert by_rect['2001'].smart_source == 'SMART'
    assert by_rect['2002'].smart_count == 1
    assert by_rect['2002'].smart_source == 'SMR'


def test_one_smart_marker_never_marks_two_adjacent_rmus():
    xml = f'''<root>
      <Layer id="L1">
        <rect id="2001" x="0" y="100" w="220" h="220"/>
        {_device('BusDis', '2101', 80, 180)}
        {_device('CBreakerDis', '2201', 80, 210, 'Circuit_Breaker_NON-SMART')}
        {_device('ZhaiWaiJieDiDaoZha', '2301', 80, 240)}
        <Text id="2401" ts="10001" x="65" y="50" w="70" h="30"/>

        <rect id="2002" x="180" y="100" w="220" h="220"/>
        {_device('BusDis', '2102', 300, 180)}
        {_device('CBreakerDis', '2202', 300, 210, 'Circuit_Breaker_NON-SMART')}
        {_device('ZhaiWaiJieDiDaoZha', '2302', 300, 240)}
        <Text id="2402" ts="10002" x="285" y="50" w="70" h="30"/>

        <!-- Center lies inside both overlapping rects but is closer to RMU 2001 center. -->
        <Text id="8001" ts="SMART" x="175" y="150" w="10" h="20"/>
      </Layer>
    </root>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(tree, Path('sample.g'), name_positions=('top',), smart_in_type=True)
    assert result.cabinet_count == 2
    assert sum(item.smart_count for item in result.items) == 1
    assert sum('SMART' in item.smart_source for item in result.items) == 1


def test_exact_geometric_tie_is_skipped_not_double_assigned():
    xml = f'''<root><Layer id="L1">
      <rect id="2001" x="0" y="100" w="220" h="220"/>
      {_device('BusDis', '2101', 80, 180)}{_device('CBreakerDis', '2201', 80, 210, 'Circuit_Breaker_NON-SMART')}{_device('ZhaiWaiJieDiDaoZha', '2301', 80, 240)}
      <rect id="2002" x="180" y="100" w="220" h="220"/>
      {_device('BusDis', '2102', 300, 180)}{_device('CBreakerDis', '2202', 300, 210, 'Circuit_Breaker_NON-SMART')}{_device('ZhaiWaiJieDiDaoZha', '2302', 300, 240)}
      <Text id="8001" ts="SMART" x="195" y="150" w="10" h="20"/>
    </Layer></root>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(tree, Path('sample.g'), name_positions=('top',), smart_in_type=True)
    assert sum(item.smart_count for item in result.items) == 0
    assert any('无法唯一归属' in warning for warning in result.warnings)
