from pathlib import Path


def test_small_element_processing_is_stateless_from_original_g():
    source = Path('g_file_studio/ui/pages/small_element_page.py').read_text(encoding='utf-8')
    assert 'delete_issues_to_output(selected, output_dir)' in source
    assert 'cumulative_map' not in source
    assert 'processed_issues' not in source
    assert 'self.issues = [x for x in self.issues' not in source
    assert '扫描结果仍保留' in source


def test_process_report_uses_green_success_style():
    source = Path('g_file_studio/engines/small_element_engine.py').read_text(encoding='utf-8')
    assert 'row_class = "processed" if was_processed' in source
    assert '.processed{background:#e8f7ee}' in source
    assert 'td:last-child{color:#087443' in source


def test_version_21739():
    assert '__version__ = "2.18.55"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.55"' in Path('pyproject.toml').read_text(encoding='utf-8')
