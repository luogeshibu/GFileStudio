from pathlib import Path


def test_gitignore_excludes_runtime_runs_and_release_artifacts():
    text = Path('.gitignore').read_text(encoding='utf-8')
    required = {
        'workspace/runs/',
        'release/',
        'build/',
        'dist/',
        '**/g-content-analysis-report.html',
        'GFileStudio_v*_Windows_x64.zip',
    }
    missing = sorted(rule for rule in required if rule not in text)
    assert not missing, f'Missing protected generated-artifact rules: {missing}'


def test_release_version_v218148():
    assert '__version__ = "2.18.148"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.148"' in Path('pyproject.toml').read_text(encoding='utf-8')
