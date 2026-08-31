from pathlib import Path


def test_poke_is_a_standalone_page_with_database_driven_naming():
    rmu_source = Path('g_file_studio/ui/pages/rmu_page.py').read_text(encoding='utf-8')
    poke_source = Path('g_file_studio/ui/pages/poke_page.py').read_text(encoding='utf-8')
    main_source = Path('g_file_studio/ui/main_window.py').read_text(encoding='utf-8')
    assert 'self._build_rmu_identification_options()' in rmu_source
    assert '_build_rmu_poke_options' not in rmu_source
    assert 'Poke 跳转处理' in rmu_source
    assert 'class PokePage' in poke_source
    assert 'OracleDatabaseService(user_settings)' in poke_source
    assert 'SUBSTATION.NAME' in poke_source
    assert 'SUBCONTROLAREA.NAME' in poke_source
    assert 'GRAPH_NAME 不参与' in poke_source
    assert 'PokePage(self.user_settings)' in main_source
    assert 'ahref 文件名模板' not in poke_source
