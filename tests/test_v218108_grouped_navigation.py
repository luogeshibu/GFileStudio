from pathlib import Path


def test_sidebar_is_grouped_collapsible_and_help_is_fixed():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    i18n = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")

    for label in ("检查与标准", "图形处理", "现场批处理"):
        assert f'"{label}"' in main
        assert f'"{label}"' in i18n

    assert '"G 图形内容解析"' not in main
    assert '"数据与分析"' not in main
    assert '("数据库",' not in main
    assert 'self.connection_button = QPushButton("连接与环境")' in main
    assert '("通用基础处理",' in main
    assert '("吉达馈线批处理",' in main
    assert 'section_button.setCheckable(True)' in main
    assert '_set_navigation_section_expanded' in main
    assert 'item.setHidden(not expanded)' in main
    assert 'self.help_button = QPushButton("帮助中心")' in main
    assert 'side_layout.addWidget(self.nav, 1)' in main
    assert 'side_layout.addWidget(self.help_button)' in main
    assert 'section_button.setObjectName("navSectionButton")' in main
    assert 'self.help_button.setObjectName("sidebarHelpButton")' in main


def test_general_processing_visible_name_and_default_landing_page():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    basic = Path("g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    help_content = Path("g_file_studio/ui/help_content.py").read_text(encoding="utf-8")

    assert 'self._select_page(3)' in main
    assert 'basic_title.setText("通用基础处理")' in main
    assert '"基础处理"' in basic
    assert '"通用基础处理帮助"' in help_content
    assert '“通用基础处理 → 图形组合处理”' in help_content
