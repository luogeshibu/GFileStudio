from __future__ import annotations

import re
from pathlib import Path

from g_file_studio.engines.small_element_engine import SmallElementIssue, write_reports
from g_file_studio.processors.basic_processor import _write_rmu_summary_reports
from g_file_studio.processors.id_processor import _write_id_reports
from g_file_studio.services import report_i18n
from g_file_studio.services.rmu_ledger_service import GraphicRmuRow


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def test_english_reports_use_english_presentation_without_changing_source_values(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(report_i18n, "report_language", lambda: "en_US")

    row = GraphicRmuRow(
        file_name="a.g", name="38995", rmu_type="2L1T", intelligent="NO",
        intelligent_source="", confidence="高", duplicate="NO", rect_id="1",
        rect_x="1", rect_y="2", rect_w="220", rect_h="220",
        warnings="柜内 Y 标签不是从 Y1 开始连续递增",
    )
    _, rmu_html = _write_rmu_summary_reports(tmp_path, [row])
    rmu_text = rmu_html.read_text(encoding="utf-8")
    assert "RMU Summary Report" in rmu_text
    assert "High" in rmu_text
    assert not _has_cjk(rmu_text)
    assert row.confidence == "高"
    assert row.warnings == "柜内 Y 标签不是从 Y1 开始连续递增"

    _, id_html = _write_id_reports(
        tmp_path,
        [{"File":"a.g","Category":"未配置模板","ElementType":"Bus","OriginalID":"1","NewID":"","Detail":"尚未加入模板；候选前缀 34（需人工确认）"}],
        "2026-08-24",
        report_kind="scan",
    )
    assert not _has_cjk(id_html.read_text(encoding="utf-8"))

    issue = SmallElementIssue(tmp_path/"a.g", "a.g", "Bus", "1", 1, "0", "0", "1", "1", "")
    _, small_html = write_reports(tmp_path, [issue], 10, "2026-08-24", report_kind="process", processed_keys=set())
    assert not _has_cjk(small_html.read_text(encoding="utf-8"))


def test_chinese_report_mode_is_preserved(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(report_i18n, "report_language", lambda: "zh_CN")
    row = GraphicRmuRow(
        file_name="a.g", name="38995", rmu_type="2L1T", intelligent="NO",
        intelligent_source="", confidence="高", duplicate="NO", rect_id="1",
        rect_x="1", rect_y="2", rect_w="220", rect_h="220", warnings="",
    )
    _, html_path = _write_rmu_summary_reports(tmp_path, [row])
    text = html_path.read_text(encoding="utf-8")
    assert "RMU 信息汇总报告" in text
    assert "高" in text
