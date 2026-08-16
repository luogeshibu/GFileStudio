from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines import frame_engine


def _line(element_id: str, x1: int, y1: int, x2: int, y2: int) -> str:
    return (
        f'<line id="{element_id}" x="{min(x1, x2)}" y="{min(y1, y2)}" '
        f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'w="{abs(x2-x1)+6}" h="{abs(y2-y1)+6}" d="{x1},{y1} {x2},{y2}" />'
    )


def test_custom_template_resizes_frame_without_changing_text():
    xml = (
        '<G w="1000" width="1000" h="800" height="800"><Layer>'
        + _line("1", 50, 50, 950, 50)
        + _line("2", 950, 50, 950, 750)
        + _line("3", 950, 750, 50, 750)
        + _line("4", 50, 750, 50, 50)
        + '<Text id="5" x="60" y="60" w="100" h="20" ts="CUSTOM TITLE" />'
        + '<Text id="6" x="850" y="700" w="80" h="20" ts="CUSTOM SIGN" />'
        + '</Layer></G>'
    )
    root = ET.fromstring(xml)
    config = frame_engine.FileFrameConfig(
        title="SHOULD NOT BE USED",
        draw=frame_engine.PersonRow("X", "2026-01-01"),
        approve=frame_engine.PersonRow("Y", "2026-01-01"),
        issue=frame_engine.PersonRow("Z", "2026-01-01"),
    )
    frame_engine.FRAME_MARGIN_LEFT = 100
    frame_engine.FRAME_MARGIN_TOP = 120
    frame_engine.FRAME_MARGIN_RIGHT = 130
    frame_engine.FRAME_MARGIN_BOTTOM = 140

    elements = frame_engine.prepare_template_elements(
        root,
        target_width=2000,
        target_height=1200,
        config=config,
        edit_content=False,
    )
    lines, bounds = frame_engine.identify_outer_frame_lines(elements, 2000, 1200)
    assert bounds == frame_engine.Box(100, 120, 1870, 1060)
    assert len(lines) == 4

    texts = {element.get("ts"): element for element in elements if element.tag == "Text"}
    assert set(texts) == {"CUSTOM TITLE", "CUSTOM SIGN"}
    assert texts["CUSTOM TITLE"].get("x") == "110"
    assert texts["CUSTOM TITLE"].get("y") == "130"
    # 右下文字保持距原外框右/下边的相对距离。
    assert texts["CUSTOM SIGN"].get("x") == "1770"
    assert texts["CUSTOM SIGN"].get("y") == "1010"


def test_builtin_template_can_still_edit_title(tmp_path: Path):
    template = Path(__file__).parents[1] / "resources" / "templates" / "SLD-Drawing-Frame-Template.sln.pic.g"
    root = ET.parse(template).getroot()
    config = frame_engine.FileFrameConfig(
        title="NEW TITLE",
        draw=frame_engine.PersonRow("DRAWER", "2026-07-28"),
        approve=frame_engine.PersonRow("APPROVER", "2026-07-29"),
        issue=frame_engine.PersonRow("ISSUER", "2026-07-30"),
    )
    frame_engine.FRAME_MARGIN_LEFT = 50
    frame_engine.FRAME_MARGIN_TOP = 50
    frame_engine.FRAME_MARGIN_RIGHT = 50
    frame_engine.FRAME_MARGIN_BOTTOM = 50
    elements = frame_engine.prepare_template_elements(
        root,
        target_width=3000,
        target_height=2000,
        config=config,
        edit_content=True,
    )
    values = {element.get("ts") for element in elements if element.tag == "Text"}
    assert "NEW TITLE" in values
    assert "DRAWER" in values
    assert "APPROVER" in values
    assert "ISSUER" in values


def test_frame_processor_accepts_single_file_input(tmp_path: Path):
    from g_file_studio.models import FrameSettings, InputMode, TemplateMode
    from g_file_studio.processors.frame_processor import add_drawing_frames

    source = tmp_path / "single.sln.pic.g"
    output = tmp_path / "out"
    source.write_text(
        '<G w="1200" width="1200" h="900" height="900"><Layer>'
        '<Text id="1" x="300" y="300" w="50" h="20" ts="A" />'
        '</Layer></G>',
        encoding="utf-8",
    )
    template = (
        Path(__file__).parents[1]
        / "resources"
        / "templates"
        / "SLD-Drawing-Frame-Template.sln.pic.g"
    )

    result = add_drawing_frames(
        FrameSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=output,
            template_file=template,
            template_mode=TemplateMode.BUILTIN,
            task_timestamp="20260729_201509",
        ),
        log=lambda _line: None,
    )

    assert result.success
    assert result.statistics["input_mode"] == "single_file"
    target = output / "single.sln.pic.g"
    assert target.is_file()
    ET.parse(target)


def test_builtin_template_right_border_is_not_shifted_with_info_block():
    """回归：目标右边框 X=1511 时不能被签字栏逻辑二次移动。"""
    template = (
        Path(__file__).parents[1]
        / "resources"
        / "templates"
        / "SLD-Drawing-Frame-Template.sln.pic.g"
    )
    root = ET.parse(template).getroot()
    config = frame_engine.FileFrameConfig(
        title="JED-CTL-AJWD-14",
        draw=frame_engine.PersonRow("Shibu", "2026-07-29"),
        approve=frame_engine.PersonRow("Shibu", "2026-07-29"),
        issue=frame_engine.PersonRow("Shibu", "2026-07-29"),
    )
    frame_engine.FRAME_MARGIN_LEFT = 50
    frame_engine.FRAME_MARGIN_TOP = 50
    frame_engine.FRAME_MARGIN_RIGHT = 50
    frame_engine.FRAME_MARGIN_BOTTOM = 50

    elements = frame_engine.prepare_template_elements(
        root,
        target_width=1561,
        target_height=2863,
        config=config,
        edit_content=True,
    )
    outer, bounds = frame_engine.identify_outer_frame_lines(elements, 1561, 2863)

    assert bounds == frame_engine.Box(50, 50, 1511, 2813)
    assert frame_engine.line_endpoints(outer["right"]) == (1511, 50, 1511, 2813)
    assert outer["right"].get(frame_engine.GFS_FRAME_ROLE_ATTRIBUTE) == "outer_right"
