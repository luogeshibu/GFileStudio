from pathlib import Path


def test_input_source_selector_expands_and_does_not_adjust_size():
    text = Path('g_file_studio/ui/widgets/input_source_selector.py').read_text(encoding='utf-8')
    assert 'QSizePolicy.Policy.Expanding' in text
    assert 'self.source_container.adjustSize()' not in text
    assert 'self.source_container.updateGeometry()' in text


def test_path_row_expands_horizontally():
    text = Path('g_file_studio/ui/widgets/path_row.py').read_text(encoding='utf-8')
    assert 'self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)' in text
    assert 'self.edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)' in text


def test_version_21752():
    assert '__version__ = "2.18.52"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
