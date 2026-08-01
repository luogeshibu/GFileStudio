from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_group_engine import enhance_rmu_tree
from g_file_studio.models import BasicSettings, InputMode

ROOT = Path(__file__).resolve().parents[1]


def test_busdis_spacing_accepts_explicit_value_without_changing_x_or_size():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    first = ET.SubElement(layer, "rect", id="20000001", x="100", y="100", w="220", h="220")
    ET.SubElement(
        layer, "BusDis", id="38000001", x="200", y="120", w="6", h="160",
        x1="203", y1="120", x2="203", y2="280", d="203,120 203,280"
    )
    second = ET.SubElement(layer, "rect", id="20000002", x="100", y="440", w="220", h="220")
    bus = ET.SubElement(
        layer, "BusDis", id="38000002", x="200", y="460", w="6", h="160",
        x1="203", y1="460", x2="203", y2="620", d="203,460 203,620"
    )
    original_x = (second.get("x"), second.get("w"), bus.get("x"), bus.get("x1"), bus.get("x2"))

    result = enhance_rmu_tree(
        ET.ElementTree(root), Path("sample.g"),
        normalize_busdis_spacing=True, busdis_vertical_spacing=300,
    )

    assert result.busdis_target_spacing == 300
    assert result.busdis_spacing_changed == 1
    assert first.get("y") == "100"
    assert second.get("y") == "400"
    assert second.get("h") == "220"
    assert original_x == (second.get("x"), second.get("w"), bus.get("x"), bus.get("x1"), bus.get("x2"))
    assert all(point.split(",")[0] == "203" for point in bus.get("d").split())


def test_model_has_vertical_spacing_but_keeps_v212_mutually_exclusive_actions():
    settings = BasicSettings(
        source_path=Path("in.g"), input_mode=InputMode.SINGLE_FILE,
        output_dir=Path("out"), normalize_busdis_rmu_spacing=True,
        busdis_rmu_vertical_spacing=350,
    )
    assert settings.busdis_rmu_vertical_spacing == 350


def test_ui_uses_radio_buttons_and_vertical_spacing_input():
    source = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    theme = (ROOT / "g_file_studio/ui/theme.py").read_text(encoding="utf-8")
    assert 'QRadioButton("不处理 ID")' in source
    assert 'QRadioButton("组合所有环网柜")' in source
    assert 'QRadioButton("取消所有环网柜组合")' in source
    assert 'IntegerInput(300, 1, 100000)' in source
    assert '"basic/rmu/busdis_vertical_spacing"' in source
    assert '相邻柜顶 Y 间距' in source
    assert 'layout.addWidget(self.rmu_remove_bus_frame)' in source
    assert 'QRadioButton::indicator' in theme
    assert 'border-radius: 10px' in theme
