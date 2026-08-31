from pathlib import Path

from g_file_studio.engines.small_element_engine import SmallElementIssue, write_reports


def _issue(tmp_path: Path, xml_id: str, ordinal: int):
    return SmallElementIssue(tmp_path / 'a.g', 'a.g', 'ConnectLine', xml_id, ordinal, '1', '2', '6', '6', '')


def test_process_report_contains_all_original_issues_and_marks_selected(tmp_path):
    a = _issue(tmp_path, '34000001', 1)
    b = _issue(tmp_path, '34000002', 2)
    key = {(str(a.file_path), a.element_type, a.ordinal, a.xml_id)}
    csv_path, html_path = write_reports(tmp_path, [a, b], 10, report_kind='process', processed_keys=key)
    csv_text = csv_path.read_text(encoding='utf-8-sig')
    html_text = html_path.read_text(encoding='utf-8')
    assert '34000001' in csv_text and '34000002' in csv_text
    assert '已删除' in csv_text and '未处理' in csv_text
    assert '原始异常图元：2' in html_text
    assert '本次选择：1' in html_text
    assert '未处理：1' in html_text
    assert 'class=\'processed\'' in html_text
    assert 'class=\'unprocessed\'' in html_text


def test_rmu_ui_uses_mandatory_foundation_and_configurable_markers():
    source = Path('g_file_studio/ui/pages/rmu_page.py').read_text(encoding='utf-8')
    assert 'RMU 基础识别与汇总（必需）' in source
    assert '每次运行固定识别全部有效 RMU' in source
    assert '智能 RMU 标记字符：' in source
    assert '柜名排除字符串：' in source
    assert '智能 / 非智能分类（固定开启）' not in source


def test_version_21740():
    assert '__version__ = "2.18.97"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.97"' in Path('pyproject.toml').read_text(encoding='utf-8')
