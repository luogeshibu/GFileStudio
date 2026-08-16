from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_navigation_and_page_names_are_updated():
    main = _read("g_file_studio/ui/main_window.py")
    merge = _read("g_file_studio/ui/pages/merge_page.py")
    frame = _read("g_file_studio/ui/pages/frame_page.py")
    assert '("馈线图合并"' in main
    assert '("图框添加"' in main
    assert '"馈线图合并"' in merge
    assert '"图框添加"' in frame


def test_basic_page_uses_selection_mode_and_one_run_button():
    source = _read("g_file_studio/ui/pages/basic_page.py")
    assert 'QGroupBox("ID 校验与修复")' not in source
    id_page = _read("g_file_studio/ui/pages/id_page.py")
    assert 'ID 检查与修复' in id_page
    assert '检查并强制修复 ID' in id_page
    assert 'QGroupBox("环网柜图元处理")' in source
    assert 'QRadioButton("不处理环网柜组合")' in source
    assert 'QRadioButton("组合所有环网柜")' in source
    assert 'QRadioButton("取消所有环网柜组合")' in source
    assert 'QGroupBox("线路与母线颜色")' in source
    assert 'setText("开始基础处理")' in source
    assert "check_duplicate_ids" not in source
    assert "repair_duplicate_ids" not in source


def test_timestamp_naming_is_visible_in_pages():
    merge = _read("g_file_studio/ui/pages/merge_page.py")
    margin = _read("g_file_studio/ui/pages/margin_page.py")
    frame = _read("g_file_studio/ui/pages/frame_page.py")
    assert "MERGED-时间戳.sln.pic.g" in merge
    assert 'QLineEdit("-ADJUSTED")' not in margin
    assert 'HelpLabel("输出标记"' not in margin
    assert "输出文件保持源文件名不变" in margin
    assert 'QLineEdit("-WITH-FRAME")' not in frame
    assert 'HelpLabel("输出标记"' not in frame
    assert "输出保持源文件名不变" in frame


def test_choice_controls_use_visible_exclusive_radio_buttons_where_requested():
    basic = _read("g_file_studio/ui/pages/basic_page.py")
    selector = _read("g_file_studio/ui/widgets/template_selector.py")
    theme = _read("g_file_studio/ui/theme.py")
    assert "QRadioButton" in basic
    assert "QRadioButton" not in selector
    assert 'QCheckBox("使用程序内置模板")' in selector
    assert 'QCheckBox("使用客户自定义模板")' in selector
    assert 'setProperty("optionChoice", True)' in basic
    assert 'setProperty("optionChoice", True)' in selector
    assert 'QRadioButton[optionChoice="true"]:checked' in theme
    assert "border: 2px solid #0b7a5a" in theme
