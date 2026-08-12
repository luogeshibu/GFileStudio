from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.merge_engine import inspect_main_bus_metadata
from g_file_studio.engines.small_element_engine import delete_issues_to_output, scan_file


def test_scan_any_bus_direction_and_target_types(tmp_path: Path) -> None:
    p = tmp_path / 'a.g'
    p.write_text('''<G><Layer>
<Bus id="1" x="0" y="0" w="6" h="6" keyid="K"/>
<Bus id="2" x="0" y="0" w="6" h="100"/>
<ConnectLine id="3" x="1" y="2" w="4" h="5"/>
<FeedLine id="4" x="1" y="2" w="9" h="9"/>
<BusDis id="5" x="1" y="2" w="2" h="3"/>
<Text id="6" x="1" y="2" w="1" h="1"/>
</Layer></G>''', encoding='utf-8')
    issues = scan_file(p, 10)
    assert {(x.element_type, x.xml_id) for x in issues} == {('Bus','1'),('ConnectLine','3'),('FeedLine','4'),('BusDis','5')}
    assert next(x for x in issues if x.xml_id == '1').keyid == 'K'


def test_delete_selected_writes_copy_and_removes_references(tmp_path: Path) -> None:
    src = tmp_path / 'a.g'; out = tmp_path / 'out'
    src.write_text('''<G><Layer>
<Bus id="1" x="0" y="0" w="6" h="6" keyid="K"/>
<ConnectLine id="3" x="1" y="2" w="4" h="5" node_area="0,0,1"/>
</Layer></G>''', encoding='utf-8')
    issue = scan_file(src, 10)[0]
    outputs = delete_issues_to_output([issue], out)
    assert src.read_text(encoding='utf-8').find('id="1"') >= 0
    root = ET.parse(outputs[0]).getroot()
    assert not any(e.get('id') == '1' for e in root.iter())
    line = next(e for e in root.iter() if e.get('id') == '3')
    assert line.get('node_area') == ''


def test_main_bus_no_longer_ignores_w_less_than_10(tmp_path: Path) -> None:
    p = tmp_path / 'a.g'
    p.write_text('''<G><Layer>
<Bus id="1" keyid="SMALL" x="0" y="10" w="6" h="6" x1="0" y1="10" x2="6" y2="10" d="0,10 6,10"/>
<Bus id="2" keyid="REAL" x="0" y="30" w="100" h="6" x1="0" y1="30" x2="100" y2="30" d="0,30 100,30"/>
</Layer></G>''', encoding='utf-8')
    item = inspect_main_bus_metadata(p, 'single')
    assert item['keyids'] == ['SMALL']
