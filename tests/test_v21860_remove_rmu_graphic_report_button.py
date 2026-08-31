from pathlib import Path


def test_rmu_graphic_report_open_button_removed_but_report_generation_kept():
    page = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    processor = Path("g_file_studio/processors/basic_processor.py").read_text(encoding="utf-8")

    assert 'QPushButton("打开图元处理报告")' not in page
    assert "self.rmu_graphic_report_button" not in page
    assert 'QPushButton("打开 RMU 汇总报告")' in page
    assert 'QPushButton("打开台账对比报告")' in page
    assert '"rmu-graphic-processing-report.html"' in processor
    assert '"rmu-graphic-processing-report.csv"' in processor
