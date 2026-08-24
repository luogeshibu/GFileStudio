from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_group_engine import remove_all_graphic_merges


def _element_signature(element: ET.Element):
    return element.tag, tuple(sorted(element.attrib.items())), element.text, element.tail


def test_remove_all_merge_headers_and_preserve_non_merge_attributes(tmp_path):
    xml = '''<G><Layer>
      <Merge id="20000001" mergex="0" mergey="0" w="200" h="200" mergesize="4" />
      <rect id="2000001" x="0" y="0" w="200" h="200" keyid="KEEP_RECT" />
      <BusDis id="38000001" x="20" y="80" w="100" h="10" keyid="KEEP_BUS" />
      <CBreakerDis id="117000001" x="60" y="40" w="40" h="40" devref="KEEP_DEVREF" tfr="rotate(0) scale(1,1)" />
      <ZhaiWaiJieDiDaoZha id="188000001" x="100" y="40" w="40" h="40" keyid="KEEP_GROUND" />
      <Merge id="20000002" mergex="300" mergey="0" w="50" h="50" mergesize="1" />
      <Text id="8000001" x="305" y="5" w="30" h="20" ts="OTHER" keyid="KEEP_TEXT" />
    </Layer></G>'''
    path = tmp_path / 'sample.g'
    path.write_text(xml, encoding='utf-8')
    tree = ET.parse(path)
    layer = tree.getroot().find('Layer')
    before = {e.get('id'): _element_signature(e) for e in list(layer) if e.tag != 'Merge'}

    result = remove_all_graphic_merges(tree, path, lower_rmu_rects=True)
    after_layer = tree.getroot().find('Layer')
    after = {e.get('id'): _element_signature(e) for e in list(after_layer) if e.tag != 'Merge'}

    assert result.previous_merge_count == 2
    assert result.removed_merge_count == 2
    assert result.remaining_merge_count == 0
    assert not [e for e in list(after_layer) if e.tag == 'Merge']
    assert before == after
    assert [e.tag for e in list(after_layer)].index('rect') < [e.tag for e in list(after_layer)].index('BusDis')


def test_basic_page_exposes_global_merge_cleanup_and_rmu_page_does_not_offer_ungroup():
    basic = Path('g_file_studio/ui/pages/basic_page.py').read_text(encoding='utf-8')
    rmu = Path('g_file_studio/ui/pages/rmu_page.py').read_text(encoding='utf-8')
    assert 'QGroupBox("图形组合处理")' in basic
    assert '彻底取消图形组合（删除全部 <Merge>，并将 RMU 外框置底）' in basic
    assert '"remove_all_graphic_merges": self.remove_all_graphic_merges.isChecked()' in basic
    assert 'self.rmu_ungroup = QRadioButton' not in rmu
    assert '基础处理 → 图形组合处理' in rmu
