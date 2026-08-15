from pathlib import Path

from openpyxl import Workbook

from g_file_studio.services.rmu_ledger_service import (
    GraphicRmuRow,
    compare_ledger,
    load_ledger_file,
    parse_name_list,
    parse_pasted_table,
    write_comparison_reports,
)


def _graphic(name: str, rmu_type: str = "2L1T", intelligent: str = "YES") -> GraphicRmuRow:
    return GraphicRmuRow(
        file_name="a.g", name=name, rmu_type=rmu_type, intelligent=intelligent,
        intelligent_source="SMART", confidence="高", duplicate="NO", rect_id="2000001",
        rect_x="1", rect_y="2", rect_w="220", rect_h="220", warnings="",
    )


def test_parse_pasted_table_with_optional_fields():
    rows = parse_pasted_table("RMU名称\tRMU类型\t是否智能\n30839\t2L1T\t是\n30840\t3L1T\t否")
    assert [(r.name, r.rmu_type, r.intelligent) for r in rows] == [
        ("30839", "2L1T", "YES"), ("30840", "3L1T", "NO")
    ]


def test_parse_name_list():
    rows = parse_name_list("30839\n30840\n")
    assert [r.name for r in rows] == ["30839", "30840"]
    assert all(not r.rmu_type and not r.intelligent for r in rows)


def test_load_xlsx(tmp_path: Path):
    path = tmp_path / "ledger.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["RMU名称", "RMU类型", "是否智能"])
    ws.append(["30839", "2L1T", "是"])
    wb.save(path)
    rows = load_ledger_file(path)
    assert len(rows) == 1
    assert rows[0].name == "30839"
    assert rows[0].intelligent == "YES"


def test_compare_and_reports_overwrite(tmp_path: Path):
    ledger = parse_pasted_table("RMU名称\tRMU类型\t是否智能\nA\t2L1T\t是\nB\t3L1T\t否\nC\t2L1T\t是")
    graphics = [_graphic("A"), _graphic("B", "2L1T", "NO"), _graphic("D", "2L1T", "NO")]
    rows, stats = compare_ledger(ledger, graphics)
    assert stats["matched_count"] == 1
    assert stats["type_mismatch_count"] == 1
    assert stats["graphic_missing_count"] == 1
    assert stats["ledger_missing_count"] == 1
    csv_path, html_path = write_comparison_reports(tmp_path, rows, stats)
    assert csv_path.name == "rmu-ledger-comparison.csv"
    assert html_path.name == "rmu-ledger-comparison.html"
    first = html_path.read_text(encoding="utf-8")
    write_comparison_reports(tmp_path, rows[:1], {**stats, "ledger_count": 1, "graphic_count": 1})
    second = html_path.read_text(encoding="utf-8")
    assert first != second


def test_rmu_page_source_exposes_three_ledger_inputs():
    source = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert "Excel / CSV 导入" in source
    assert "直接粘贴表格" in source
    assert "只粘贴 RMU 名称" in source
    assert "compare_rmu_ledger" in source
