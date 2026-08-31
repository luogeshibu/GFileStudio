from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import (
    identify_rmus,
    parse_intelligent_markers,
)


def _device(tag: str, elem_id: str, x: int, y: int, devref: str = '') -> str:
    dev = f' devref="{devref}"' if devref else ''
    return f'<{tag} id="{elem_id}" x="{x}" y="{y}" w="20" h="20"{dev}/>'


def test_custom_intelligent_marker_is_global_unique_and_excluded_from_name():
    xml = f'''<root><Layer id="L1">
      <rect id="2001" x="0" y="100" w="200" h="200"/>
      {_device('BusDis', '2101', 80, 180)}
      {_device('CBreakerDis', '2201', 80, 210, 'Circuit_Breaker_NON-SMART')}
      {_device('ZhaiWaiJieDiDaoZha', '2301', 80, 240)}
      <Text id="2401" ts="30834" x="65" y="45" w="70" h="30"/>
      <!-- Closer to the frame than the actual cabinet name; must never become the name. -->
      <Text id="8001" ts="NEWSMART" x="65" y="72" w="70" h="25"/>
    </Layer></root>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(
        tree,
        Path('sample.g'),
        name_positions=('top',),
        smart_in_type=True,
        intelligent_marker_values=('SMART', 'SMR', 'NEWSMART', 'SMART-SE'),
    )
    assert result.cabinet_count == 1
    item = result.items[0]
    assert item.name == '30834'
    assert item.smart_count == 1
    assert item.smart_source == 'NEWSMART'


def test_custom_name_exclusion_remains_authoritative():
    xml = f'''<root><Layer id="L1">
      <rect id="2001" x="0" y="100" w="200" h="200"/>
      {_device('BusDis', '2101', 80, 180)}
      {_device('CBreakerDis', '2201', 80, 210, 'Circuit_Breaker_NON-SMART')}
      {_device('ZhaiWaiJieDiDaoZha', '2301', 80, 240)}
      <Text id="2401" ts="30834" x="65" y="45" w="70" h="30"/>
      <Text id="2402" ts="IGNOREME" x="65" y="72" w="70" h="25"/>
    </Layer></root>'''
    tree = ET.ElementTree(ET.fromstring(xml))
    result = identify_rmus(
        tree,
        Path('sample.g'),
        name_positions=('top',),
        excluded_name_values=('IGNOREME',),
        smart_in_type=True,
        intelligent_marker_values=('SMART', 'SMR'),
    )
    assert result.items[0].name == '30834'


def test_marker_parser_supports_site_extensions_and_defaults():
    assert parse_intelligent_markers('SMART, SMR; NEWSMART\nSMART-SE') == (
        'SMART', 'SMR', 'NEWSMART', 'SMART-SE'
    )
    assert parse_intelligent_markers('') == ('SMART', 'SMR')


def test_rmu_foundation_ui_is_simplified_and_keeps_required_inputs():
    source = Path('g_file_studio/ui/pages/rmu_page.py').read_text(encoding='utf-8')
    assert 'QGroupBox("RMU 基础识别与汇总（必需）")' in source
    assert '识别范围（固定）' not in source
    assert 'QCheckBox("智能环网柜（SMART / SMR）")' not in source
    assert 'QCheckBox("非智能环网柜")' not in source
    assert '智能 / 非智能分类（固定开启）' not in source
    assert 'QLabel("智能 RMU 标记字符：")' in source
    assert 'self.rmu_intelligent_markers' in source
    assert 'QLabel("柜名排除字符串：")' in source
    assert 'identify_rmu_name_and_type=True' in source
    assert 'export_rmu_identification_csv=True' in source
