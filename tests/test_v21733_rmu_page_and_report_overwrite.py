from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_rmu_is_a_dedicated_page_after_id():
    main = (ROOT / "g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    basic = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    rmu = (ROOT / "g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    assert "RmuPage(self.user_settings)" in main
    assert main.index("IdPage(self.user_settings)") < main.index("RmuPage(self.user_settings)") < main.index("BasicPage(self.user_settings)")
    assert "self._build_rmu_options()" not in basic.split("def __init__", 1)[1].split("def _build_rmu_options", 1)[0]
    assert 'QGroupBox("环网柜图元处理")' in rmu
    assert 'QGroupBox("RMU 基础识别与汇总（必需）")' in rmu


def test_reports_use_stable_overwrite_names_and_buttons_are_open_report():
    small_engine = (ROOT / "g_file_studio/engines/small_element_engine.py").read_text(encoding="utf-8")
    small_page = (ROOT / "g_file_studio/ui/pages/small_element_page.py").read_text(encoding="utf-8")
    id_processor = (ROOT / "g_file_studio/processors/id_processor.py").read_text(encoding="utf-8")
    id_page = (ROOT / "g_file_studio/ui/pages/id_page.py").read_text(encoding="utf-8")
    assert "small-element-scan-report" in small_engine
    assert "small-element-process-report" in small_engine
    assert "id-scan-report" in id_processor
    assert "id-repair-report" in id_processor
    assert 'QPushButton("打开报告")' in small_page
    assert 'QPushButton("打开报告")' in id_page
    assert "覆盖上一份扫描报告" in small_page
    assert "覆盖上一份修复报告" in id_page
