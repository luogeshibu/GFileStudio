from pathlib import Path


def test_v218106_upload_rejects_filename_mismatch_before_binding():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'expected_symbol_file = observed_file_item.text().strip()' in source
    assert 'actual_symbol_file = path.name' in source
    assert 'if expected_symbol_file and not self._same_symbol_g_filename(expected_symbol_file, actual_symbol_file):' in source
    assert '"禁止上传：图元文件名不匹配"' in source
    guard_pos = source.index('if expected_symbol_file and not self._same_symbol_g_filename')
    parse_pos = source.index('record = dict(self.service.prepare_standard_file_records([path])[0])', guard_pos)
    bind_pos = source.index('self._set_standard_file_cell(row, devref)', guard_pos)
    assert guard_pos < parse_pos < bind_pos


def test_v218106_filename_match_is_exact_basename_case_insensitive():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'expected_name = Path(str(expected or "").strip()).name' in source
    assert 'actual_name = Path(str(actual or "").strip()).name' in source
    assert 'expected_name.casefold() == actual_name.casefold()' in source


def test_v218106_version_bumped():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
