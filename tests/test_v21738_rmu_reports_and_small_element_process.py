
from pathlib import Path

from g_file_studio.engines.small_element_engine import SmallElementIssue, write_reports


def test_rmu_page_has_linked_report_buttons():
    source = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("打开图元处理报告")' in source
    assert 'QPushButton("打开 RMU 汇总报告")' in source
    assert 'QPushButton("打开台账对比报告")' in source
    assert '"rmu-graphic-processing-report.html"' in source
    assert '"rmu-summary-report.html"' in source
    assert '"rmu-ledger-comparison.html"' in source
    assert 'self._refresh_report_buttons()' in source


def test_basic_processor_writes_fixed_rmu_reports():
    source = Path("g_file_studio/processors/basic_processor.py").read_text(encoding="utf-8")
    ledger_source = Path("g_file_studio/services/rmu_ledger_service.py").read_text(encoding="utf-8")
    assert '"rmu-graphic-processing-report.html"' in source
    assert '"rmu-summary-report.html"' in source
    assert '"rmu-ledger-comparison.html"' in ledger_source


def test_small_element_process_report_identifies_deleted_rows(tmp_path):
    issue = SmallElementIssue(
        file_path=tmp_path / "a.sln.pic.g",
        file_name="a.sln.pic.g",
        element_type="ConnectLine",
        xml_id="34000001",
        ordinal=1,
        x="10", y="10", w="6", h="6", keyid="",
    )
    csv_path, html_path = write_reports(tmp_path, [issue], 10, report_kind="process")
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    html_text = html_path.read_text(encoding="utf-8")
    assert "ProcessResult" in csv_text
    assert "已删除" in csv_text
    assert "已删除：1" in html_text
    assert "未处理：0" in html_text
