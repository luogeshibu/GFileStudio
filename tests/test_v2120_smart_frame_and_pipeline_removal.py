from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_one_click_page_and_backend_are_removed():
    assert not (ROOT / "g_file_studio/ui/pages/pipeline_page.py").exists()
    assert not (ROOT / "g_file_studio/processors/pipeline_processor.py").exists()
    assert not (ROOT / "g_file_studio/services/temp_workspace_service.py").exists()
    main = (ROOT / "g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "PipelinePage" not in main
    assert "一键处理" not in main
    assert 'action.triggered.connect(lambda: self.nav.setCurrentRow(7))' in main


def test_basic_ui_only_exposes_smart_rmu_frame_color():
    source = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    assert "修改含 SMART 的环网柜外框颜色" in source
    assert "修改环网柜内 SMART 字样颜色" not in source
    assert "修改环网柜外框颜色" not in source
    assert "SMART 字体颜色以及不含 SMART 的其他环网柜外框均保持不变" in source


def test_basic_model_uses_targeted_smart_frame_fields():
    models = (ROOT / "g_file_studio/models.py").read_text(encoding="utf-8")
    assert "change_smart_rmu_frame_color" in models
    assert "smart_rmu_frame_color" in models
    assert "change_rmu_smart_color" not in models
    assert "change_rmu_frame_color" not in models
