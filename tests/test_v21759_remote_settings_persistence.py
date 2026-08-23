from pathlib import Path


def test_remote_widget_has_explicit_save_and_last_input_persistence():
    text = Path("g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    assert 'self.save_button = QPushButton("保存 SSH 设置")' in text
    assert 'self.save_button.clicked.connect(self.save_settings)' in text
    assert 'editor.editingFinished.connect(self._persist_silently)' in text
    assert 'def save_settings(self) -> None:' in text
    assert 'def _restore_shared_settings(self) -> None:' in text
    assert 'def showEvent(self, event) -> None:' in text


def test_remote_settings_are_shared_across_all_modules():
    text = Path("g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    # Intentionally global rather than settings_prefix-specific: every module reuses
    # the user's most recent SSH host/port/user/password/remote directory.
    assert 'return f"remote_g_source/{suffix}"' in text

    selector = Path("g_file_studio/ui/widgets/input_source_selector.py").read_text(encoding="utf-8")
    assert 'self.remote = RemoteGSourceWidget(' in selector
    merge = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    assert 'self.remote_source = RemoteGSourceWidget(' in merge


def test_remote_read_only_contract_is_unchanged():
    text = Path("g_file_studio/services/remote_g_source.py").read_text(encoding="utf-8")
    assert 'self._sftp.get(str(remote_path), str(local_path))' in text
    for forbidden in ('self._sftp.put(', 'self._sftp.remove(', 'self._sftp.rename(', 'self._sftp.mkdir('):
        assert forbidden not in text
