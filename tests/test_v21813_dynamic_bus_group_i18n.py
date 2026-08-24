from pathlib import Path


def test_merge_business_code_stays_golden_and_i18n_owns_dynamic_group_display():
    merge = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    i18n = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")
    assert 'table.item(row, 1).setText(f"组{membership[name]}" if name in membership else "未分组")' in merge
    assert 'group_cell = re.fullmatch(r"组(\\d+)", text)' in i18n
    assert 'return f"Group {group_cell.group(1)}"' in i18n
    assert '_ensure_table_runtime_i18n' in i18n
    assert 'model.dataChanged.connect(translate_range)' in i18n


def test_manual_group_banner_has_curated_english_translation():
    i18n = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")
    assert 'Select two or more consecutive feeder rows in the current merge order' in i18n
