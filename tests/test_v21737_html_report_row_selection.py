from pathlib import Path
from types import SimpleNamespace

from g_file_studio.engines.small_element_engine import SmallElementIssue, write_reports
from g_file_studio.processors.basic_processor import _write_rmu_html, _write_smr_frame_reports
from g_file_studio.processors.id_processor import _write_id_reports
from g_file_studio.services.rmu_ledger_service import GraphicRmuRow, compare_ledger, parse_name_list, write_comparison_reports


def _assert_selectable(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert 'id="reportSelectAll"' in text
    assert 'class="report-select report-row-select"' in text
    assert 'reportSelectionCount' in text
    assert 'report-row-selected' in text


def test_id_html_has_multiselect(tmp_path: Path):
    _, html = _write_id_reports(tmp_path, [{
        "File":"a.g", "Category":"正常", "ElementType":"Bus",
        "OriginalID":"30000001", "NewID":"", "Detail":"ok",
    }], "20260813_0934", "scan")
    _assert_selectable(html)


def test_small_element_html_has_multiselect(tmp_path: Path):
    issue = SmallElementIssue(
        file_path=tmp_path / "a.g", file_name="a.g", element_type="Bus", xml_id="30000001",
        ordinal=1, x="1", y="2", w="3", h="4", keyid="",
    )
    _, html = write_reports(tmp_path, [issue], 10, "20260813_0934", "scan")
    _assert_selectable(html)


def test_rmu_summary_and_smr_html_have_multiselect(tmp_path: Path):
    item = SimpleNamespace(
        name="30839", rmu_type="2L1T", l_count=2, t_count=1, smart_count=1, smart_source="SMR",
        name_position="top", confidence="高", rect_id="2000001", rect_x=1.0, rect_y=2.0,
        rect_w=220.0, rect_h=220.0, warnings=[],
    )
    identification = SimpleNamespace(items=[item], named_count=1, typed_count=1)
    _assert_selectable(_write_rmu_html(tmp_path / "a.sln.pic.g", identification))
    _, smr_html = _write_smr_frame_reports(tmp_path, [{
        "File":"a.g", "SMRTextID":"8000001", "SMRX":1, "SMRY":2, "RectID":"2000001",
        "RectX":1, "RectY":2, "RectW":220, "RectH":220, "Distance":3,
        "OldColor":"#FFFFFF", "NewColor":"#FF0000", "Result":"已修改",
    }])
    _assert_selectable(smr_html)


def test_ledger_comparison_html_has_multiselect(tmp_path: Path):
    ledger = parse_name_list("A")
    graphics = [GraphicRmuRow(
        file_name="a.g", name="A", rmu_type="2L1T", intelligent="YES", intelligent_source="SMART",
        confidence="高", duplicate="NO", rect_id="2000001", rect_x="1", rect_y="2",
        rect_w="220", rect_h="220", warnings="",
    )]
    rows, stats = compare_ledger(ledger, graphics)
    _, html = write_comparison_reports(tmp_path, rows, stats)
    _assert_selectable(html)
