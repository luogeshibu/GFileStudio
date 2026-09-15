from pathlib import Path


def test_poke_page_merges_target_filename_rules_into_jump_types():
    text = Path("g_file_studio/ui/pages/poke_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("跳转类型")' in text
    assert 'RMU Poke：环网柜明细图　目标：{区域}-{变电站}-{馈线}-{RMU}.sln.pic.g' in text
    assert '站点跳转 Poke：变电站馈线总图　目标：{区域}-{变电站}.sln.pic.g' in text
    assert 'QGroupBox("Poke 目标文件命名规则")' not in text


def test_poke_help_target_filename_section_remains_concise():
    text = Path("g_file_studio/ui/help_content.py").read_text(encoding="utf-8")
    assert '<h3>Poke 目标文件命名规则</h3>' in text
    assert '智能环网柜名字 Poke 目标文件' in text
    assert '站点跳转 Poke 目标文件' in text


def test_poke_merged_target_hint_is_bilingual():
    text = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")
    assert 'RMU Poke: RMU detail drawing  Target:' in text
    assert 'Station-Jump Poke: Substation feeder overview  Target:' in text
