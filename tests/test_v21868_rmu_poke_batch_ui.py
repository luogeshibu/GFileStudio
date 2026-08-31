from pathlib import Path


def test_rmu_page_no_longer_exposes_legacy_poke_naming_ui():
    rmu_source = Path('g_file_studio/ui/pages/rmu_page.py').read_text(encoding='utf-8')
    poke_source = Path('g_file_studio/ui/pages/poke_page.py').read_text(encoding='utf-8')
    assert 'QRadioButton("自动按每个主图文件名生成（推荐）")' not in rmu_source
    assert 'QRadioButton("自定义模板")' not in rmu_source
    assert 'QGroupBox("智能环网柜 Poke 跳转")' not in rmu_source
    assert 'class PokePage' in poke_source
