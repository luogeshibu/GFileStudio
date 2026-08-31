from pathlib import Path


def test_standard_symbol_file_column_uses_real_table_cells_not_white_combo_widgets():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")

    assert 'self.standard_table.setShowGrid(True)' in source
    assert 'self.standard_table.setAlternatingRowColors(True)' in source
    assert 'self._set_readonly_cell(row, 3, "-")' in source
    assert 'def _set_standard_file_cell(self, row: int, devref: str)' in source
    assert 'item.setData(Qt.ItemDataRole.UserRole, devref)' in source
    assert 'self.standard_table.setCellWidget(row, 3, combo)' not in source
    assert 'self.standard_table.setCellWidget(row, 3, devref_combo)' not in source
    assert 'self.standard_table.cellWidget(row, 3)' not in source
