from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_rmu_page_removes_bus_frame_option_and_runtime_parameter():
    source = (ROOT / "g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert "self.rmu_remove_bus_frame" not in source
    assert "删除带 Bus 的环网柜外框，并将最近标题放到母线上方" not in source
    assert "remove_bus_rmu_frame_and_reposition_title=" not in source
    assert "basic/rmu/remove_bus_frame" not in source


def test_other_modules_keep_existing_bus_processing_logic():
    basic = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    jeddah = (ROOT / "g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "删除带 Bus 的环网柜外框，并将最近标题放到母线上方" in basic
    assert "bus_rmu_frame_removed_count" in jeddah
