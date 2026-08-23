from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.color_engine import ColorRule, apply_line_colors
from g_file_studio.models import BasicSettings, InputMode
from g_file_studio.processors.basic_processor import _color_rules


def test_line_style_solid_and_dashed_do_not_require_color_change():
    tree = ET.ElementTree(ET.fromstring(
        '<G><Layer>'
        '<FeedLine id="1" lc="1,2,3" lcc="#010203" ls="2" lw="3"/>'
        '<ConnectLine id="2" lc="4,5,6" lcc="#040506" ls="1" lw="4"/>'
        '</Layer></G>'
    ))
    result = apply_line_colors(tree, Path('x.g'), [
        ColorRule('FeedLine', '馈线', '#FF0000', line_style='solid', change_color=False),
        ColorRule('ConnectLine', '连接线', '#00FF00', line_style='dashed', change_color=False),
    ])
    layer = list(tree.getroot())[0]
    feed, conn = list(layer)
    assert feed.get('ls') == '1'
    assert feed.get('lc') == '1,2,3'
    assert feed.get('lcc') == '#010203'
    assert feed.get('lw') == '3'
    assert conn.get('ls') == '2'
    assert conn.get('lc') == '4,5,6'
    assert conn.get('lw') == '4'
    assert result.total_style_changed == 2


def test_keep_line_style_leaves_ls_untouched_while_color_changes():
    tree = ET.ElementTree(ET.fromstring('<G><Layer><Bus id="1" lc="0,0,0" ls="7"/></Layer></G>'))
    apply_line_colors(tree, Path('x.g'), [
        ColorRule('Bus', '主网母线', '#112233', line_style='keep', change_color=True)
    ])
    bus = list(list(tree.getroot())[0])[0]
    assert bus.get('ls') == '7'
    assert bus.get('lc') == '17,34,51'
    assert bus.get('lcc') == '#112233'


def test_basic_rules_include_style_only_change(tmp_path):
    settings = BasicSettings(
        source_path=tmp_path, input_mode=InputMode.DIRECTORY, output_dir=tmp_path,
        change_feedline_color=False, feedline_line_style='dashed',
    )
    rules = _color_rules(settings)
    assert len(rules) == 1
    assert rules[0].element_tag == 'FeedLine'
    assert rules[0].line_style == 'dashed'
    assert rules[0].change_color is False
