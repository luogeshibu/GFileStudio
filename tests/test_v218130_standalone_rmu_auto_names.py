from pathlib import Path

from g_file_studio.models import BasicSettings
from g_file_studio.processors.basic_processor import _validate_rules


def test_standalone_rmu_page_removes_manual_direction_controls_and_uses_auto_cluster():
    page = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")

    assert "柜名可能位置：" not in page
    assert 'QCheckBox("上方")' not in page
    assert 'QCheckBox("下方")' not in page
    assert 'QCheckBox("左侧")' not in page
    assert 'QCheckBox("右侧")' not in page
    assert 'get_bool("basic/rmu/name_top"' not in page
    assert 'set_value("basic/rmu/name_top"' not in page
    assert "柜名位置至少选择" not in page
    assert 'rmu_name_resolution_mode="auto_cluster"' in page
    assert "柜名排除字符串：" in page
    assert "智能 RMU 标记字符：" in page


def test_auto_cluster_basic_settings_do_not_require_manual_name_directions(tmp_path: Path):
    settings = BasicSettings(
        source_path=tmp_path / "input.g",
        output_dir=tmp_path / "out",
        identify_rmu_name_and_type=True,
        rmu_name_resolution_mode="auto_cluster",
        rmu_name_top=False,
        rmu_name_bottom=False,
        rmu_name_left=False,
        rmu_name_right=False,
    )
    _validate_rules(settings)


def test_shared_default_and_general_basic_page_keep_legacy_direction_contract():
    models = Path("g_file_studio/models.py").read_text(encoding="utf-8")
    engine = Path("g_file_studio/engines/rmu_identification_engine.py").read_text(encoding="utf-8")
    basic_page = Path("g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")

    assert 'rmu_name_resolution_mode: str = "selected_direction"' in models
    assert 'name_resolution_mode: str = "selected_direction"' in engine
    assert 'QCheckBox("上方")' in basic_page
