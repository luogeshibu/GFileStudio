from pathlib import Path


def test_release_uses_one_validation_document():
    root = Path('.')
    validation = root / 'VALIDATION.md'
    assert validation.is_file(), 'Release root must contain VALIDATION.md'
    assert not list(root.glob('VALIDATION_v*.md')), 'Per-version VALIDATION_v*.md files must not be shipped'

    text = validation.read_text(encoding='utf-8')
    assert '## v2.18.52' in text
    assert '## v2.18.51' in text
    assert '## v2.18.49' in text
    assert '以后每个版本的验证结果都追加到本文件中' in text


def test_release_version_is_v21850():
    assert '__version__ = "2.18.97"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.97"' in Path('pyproject.toml').read_text(encoding='utf-8')
