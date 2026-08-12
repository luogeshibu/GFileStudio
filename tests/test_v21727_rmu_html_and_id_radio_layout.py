from pathlib import Path
from types import SimpleNamespace

from g_file_studio.processors.basic_processor import _write_rmu_csv, _write_rmu_html


def _item(name, confidence="高", rect_id="1"):
    return SimpleNamespace(
        name=name, rmu_type="2L1T", l_count=2, t_count=1, smart_count=0,
        name_position="top", confidence=confidence, rect_id=rect_id,
        rect_x=1.0, rect_y=2.0, rect_w=220.0, rect_h=220.0, warnings=[]
    )


def test_rmu_csv_marks_duplicate_and_html_colors(tmp_path: Path):
    out = tmp_path / "sample.sln.pic.g"
    identification = SimpleNamespace(
        items=[_item("30839", "高", "a"), _item("30839", "高", "b"), _item("30911", "中", "c"), _item("", "未识别", "d")],
        named_count=3, typed_count=4,
    )
    csv_path = _write_rmu_csv(out, identification)
    html_path = _write_rmu_html(out, identification)
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    html_text = html_path.read_text(encoding="utf-8")
    assert "Duplicate" in csv_text
    assert csv_text.count("30839") == 2
    assert csv_text.count("YES") == 2
    assert "重复柜名/ID" in html_text
    assert 'class="bad"' in html_text
    assert 'class="medium"' in html_text
    assert "30839 × 2" in html_text


def test_id_radio_layout_reserves_space():
    source = Path("g_file_studio/ui/pages/id_page.py").read_text(encoding="utf-8")
    assert "self.check_only.setMinimumWidth(138)" in source
    assert "self.repair.setMinimumWidth(300)" in source
