from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_group_engine import enhance_rmu_tree


def test_authoritative_smart_rect_ids_color_frame_even_when_label_crosses_by_one_px():
    # SMART text right edge is x=161, while rect right edge is x=160.
    # The old full-containment check intentionally misses it; authoritative
    # RMU identification can still confirm the cabinet as SMART.
    tree = ET.ElementTree(ET.fromstring('''
    <root><Layer>
      <rect id="2001" x="100" y="100" w="60" h="60" lc="255,255,255" lcc="#ffffff"/>
      <Text id="8001" ts="SMART" x="141" y="120" w="20" h="10"/>
    </Layer></root>
    '''))
    result = enhance_rmu_tree(
        tree,
        Path('sample.g'),
        change_smart_frame_color=True,
        smart_frame_color='#FF0000',
        smart_rmu_rect_ids={'2001'},
    )
    rect = next(e for e in tree.getroot().iter() if e.tag == 'rect')
    assert result.smart_rmu_rect_count == 1
    assert result.smart_frame_color_changed == 1
    assert rect.get('lc') == '255,0,0'
    assert rect.get('lcc') == '#FF0000'


def test_legacy_fallback_is_unchanged_without_authoritative_ids():
    tree = ET.ElementTree(ET.fromstring('''
    <root><Layer>
      <rect id="2001" x="100" y="100" w="60" h="60" lc="255,255,255" lcc="#ffffff"/>
      <Text id="8001" ts="SMART" x="141" y="120" w="20" h="10"/>
    </Layer></root>
    '''))
    result = enhance_rmu_tree(
        tree,
        Path('sample.g'),
        change_smart_frame_color=True,
        smart_frame_color='#FF0000',
    )
    rect = next(e for e in tree.getroot().iter() if e.tag == 'rect')
    assert result.smart_rmu_rect_count == 0
    assert result.smart_frame_color_changed == 0
    assert rect.get('lc') == '255,255,255'
