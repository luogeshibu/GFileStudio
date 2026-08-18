from pathlib import Path


def test_basic_rules_editor_uses_external_scan_request():
    text = Path('g_file_studio/ui/widgets/basic_rules_editor.py').read_text(encoding='utf-8')
    assert 'scanRequested = Signal()' in text
    assert 'self.scan_button.clicked.connect(self.scanRequested.emit)' in text


def test_basic_page_prepares_remote_snapshot_before_schema_scan():
    text = Path('g_file_studio/ui/pages/basic_page.py').read_text(encoding='utf-8')
    assert 'self.rules_editor.scanRequested.connect(self._scan_rules_schema)' in text
    assert 'local_snapshot = self.source.prepare_for_processing()' in text
    assert 'self.rules_editor.set_input_dir(local_snapshot)' in text
    assert 'self.rules_editor.refresh_schema()' in text
    assert 'SFTP GET' in text
