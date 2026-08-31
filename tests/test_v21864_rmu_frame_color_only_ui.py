from pathlib import Path


def test_rmu_page_hides_unused_frame_line_style_controls():
    text = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert "self.rmu_smart_frame_color.line_style_label.hide()" in text
    assert "self.rmu_smart_frame_color.line_style_combo.hide()" in text
    assert "self.rmu_smr_frame_color.line_style_label.hide()" in text
    assert "self.rmu_smr_frame_color.line_style_combo.hide()" in text


def test_basic_page_line_style_feature_remains_available():
    text = Path("g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    assert "feedline_line_style" in text
    assert "connectline_line_style" in text
    assert "busdis_line_style" in text
    assert "bus_line_style" in text
