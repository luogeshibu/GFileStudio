from pathlib import Path

from g_file_studio.models import BasicSettings, InputMode, RmuStatusPosition

ROOT = Path(__file__).resolve().parents[1]


def test_model_keeps_mutually_exclusive_actions_and_new_status_fields():
    settings = BasicSettings(
        source_path=Path("in.g"), input_mode=InputMode.SINGLE_FILE,
        output_dir=Path("out"), reposition_channel_status=True,
        channel_status_position=RmuStatusPosition.BOTTOM_RIGHT,
        channel_status_inner_margin=12,
    )
    assert settings.channel_status_position.label == "右下角"
    assert settings.channel_status_inner_margin == 12


def test_ui_keeps_radio_buttons_and_uses_status_anchor_controls():
    source = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    theme = (ROOT / "g_file_studio/ui/theme.py").read_text(encoding="utf-8")
    assert 'QRadioButton("不处理 ID")' not in source
    assert 'QRadioButton("组合所有环网柜")' in source
    assert 'QRadioButton("取消所有环网柜组合")' in source
    assert 'WheelSafeComboBox()' in source
    assert 'IntegerInput(5, 0, 1000)' in source
    assert '移动环网柜红色状态点（channel_status）' in source
    assert 'layout.addWidget(self.rmu_remove_bus_frame)' in source
    assert 'QRadioButton::indicator' in theme
    assert 'border-radius: 10px' in theme
