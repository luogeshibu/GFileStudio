from pathlib import Path


def test_symbol_standard_page_uses_compact_operator_copy():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "维护服务器图元标准版本并检查业务 G 的标准一致性" in source
    assert "用户点击按钮读取服务器 element 图元目录" in source
    assert "GLOBAL 仅手动切换；保存新的 ACTIVE 不会改变全局版本。" in source
    assert "历史版本和图元文件冻结在本地版本库" in source
    assert "业务单线图永远只作为被检查对象，不能反向学习成标准" not in source
    assert "这里不再分成“当前标准列表”和“标准定义”两个表格" not in source


def test_main_window_restores_last_business_module_by_stable_id():
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert 'LAST_BUSINESS_PAGE_KEY = "navigation/last_business_page"' in source
    assert '1: "small_elements"' in source
    assert '3: "symbol_standard"' in source
    assert '4: "rmu"' in source
    assert '10: "jeddah_batch"' in source
    assert 'self._restore_last_business_page()' in source
    assert 'self._remember_business_page(page_index)' in source
    assert 'self._select_page(3)' in source  # first-launch fallback
    # Utility pages are intentionally excluded so Help/Connections do not replace
    # the operator's last real working module.
    business_map = source.split('BUSINESS_PAGE_IDS = {', 1)[1].split('}', 1)[0]
    business_lines = {line.strip() for line in business_map.splitlines() if ':' in line}
    assert not any(line.startswith('0:') for line in business_lines)
    assert not any(line.startswith('12:') for line in business_lines)


def test_release_version_is_218121():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
