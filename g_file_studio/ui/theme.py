from __future__ import annotations

APP_STYLE = r"""
QMainWindow, QDialog {
    background: #eef2f7;
}

QWidget {
    color: #1f2937;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
}

QLabel, QCheckBox {
    background: transparent;
}

QWidget#contentRoot,
QScrollArea#pageScroll,
QScrollArea#pageScroll > QWidget > QWidget {
    background: #f5f7fb;
}

QWidget#sidebar {
    background: #172033;
    border: none;
}

QFrame#brandBadge {
    background: #2563eb;
    border-radius: 10px;
}

QLabel#brandLetter {
    color: white;
    font-size: 20px;
    font-weight: 800;
}

QLabel#brandTitle {
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
}

QLabel#brandSubtitle {
    color: #9fb0c8;
    font-size: 12px;
}

QLabel#sidebarVersion {
    color: #78889f;
    font-size: 11px;
}

QListWidget#navigation {
    background: transparent;
    border: none;
    color: #d7dfeb;
    outline: none;
    padding: 0;
}

QListWidget#navigation::item {
    background: transparent;
    border: none;
    border-radius: 9px;
    margin: 3px 0;
    padding: 13px 16px;
}

QListWidget#navigation::item:hover {
    background: #22304a;
    color: #ffffff;
}

QListWidget#navigation::item:selected {
    background: #2f6be8;
    color: #ffffff;
}

QLabel#pageTitle {
    color: #111827;
    font-size: 24px;
    font-weight: 750;
}

QLabel#pageDescription {
    color: #64748b;
    font-size: 13px;
}

QFrame#infoBanner {
    background: #eef6ff;
    border: 1px solid #cfe3ff;
    border-radius: 9px;
}

QLabel#infoIcon {
    background: #2563eb;
    color: white;
    border-radius: 10px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    font-weight: 700;
}

QLabel#infoText {
    color: #365271;
}

QGroupBox {
    background: #ffffff;
    border: 1px solid #dce4ee;
    border-radius: 11px;
    margin-top: 0;
    padding: 38px 16px 14px 16px;
    font-weight: 650;
    color: #162033;
}

QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 16px;
    top: 12px;
    padding: 0;
    color: #162033;
    background: transparent;
}

QLabel#fieldLabel {
    color: #334155;
    font-weight: 550;
}

QLabel#mutedText {
    color: #6b7280;
}

QLineEdit,
QSpinBox,
QDateEdit,
QComboBox,
QPlainTextEdit,
QTextEdit,
QTableWidget,
QTreeWidget {
    background: #ffffff;
    border: 1px solid #cfd9e6;
    border-radius: 7px;
    padding: 7px 9px;
    selection-background-color: #dce9ff;
    selection-color: #172033;
}

QLineEdit:hover,
QSpinBox:hover,
QDateEdit:hover,
QComboBox:hover {
    border-color: #9eb4d0;
}

QLineEdit:focus,
QSpinBox:focus,
QDateEdit:focus,
QComboBox:focus,
QPlainTextEdit:focus,
QTextEdit:focus {
    border: 1px solid #2f6be8;
}

QLineEdit:disabled,
QSpinBox:disabled,
QDateEdit:disabled,
QComboBox:disabled {
    background: #f1f4f8;
    color: #8a96a8;
}

QSpinBox::up-button,
QSpinBox::down-button {
    width: 24px;
    background: #f8fafc;
    border-left: 1px solid #d5deea;
}

QCheckBox {
    color: #263449;
    spacing: 8px;
    padding: 2px 0;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    background: #ffffff;
    border: 2px solid #71849c;
    border-radius: 5px;
}

QCheckBox::indicator:hover {
    border-color: #2f6be8;
    background: #f4f8ff;
}

QCheckBox::indicator:checked {
    background: #2f6be8;
    border: 1px solid #2f6be8;
    image: url("__CHECK_ICON__");
}

QCheckBox::indicator:disabled {
    background: #edf1f6;
    border-color: #c1cad6;
}


QCheckBox[optionChoice="true"] {
    background: #f8fafc;
    border: 1px solid #cad6e4;
    border-radius: 8px;
    padding: 8px 12px;
    color: #263449;
    font-weight: 600;
}

QCheckBox[optionChoice="true"]:hover {
    background: #f0f6ff;
    border-color: #8fb2ec;
}

QCheckBox[optionChoice="true"]:checked {
    background: #e8f1ff;
    border: 2px solid #2f6be8;
    color: #174ea6;
}

QCheckBox[optionChoice="true"]:disabled {
    background: #f1f4f8;
    border-color: #d5dde8;
    color: #8a96a8;
}

QPushButton {
    background: #2f6be8;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 8px 16px;
    min-height: 20px;
    font-weight: 650;
}

QPushButton:hover {
    background: #245ed0;
}

QPushButton:pressed {
    background: #1f52ba;
}

QPushButton:disabled {
    background: #aeb8c7;
    color: #eef2f7;
}

QPushButton[secondary="true"] {
    background: #e9eef5;
    color: #334155;
    border: 1px solid #d3dce8;
}

QPushButton[secondary="true"]:hover {
    background: #dde5ef;
}

QPushButton[danger="true"] {
    background: #dc4c5b;
}

QToolButton#helpButton {
    background: #eef3f9;
    color: #45607e;
    border: 1px solid #cad6e4;
    border-radius: 10px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    padding: 0;
    font-weight: 750;
}

QToolButton#helpButton:hover {
    background: #dfeaff;
    color: #245ed0;
    border-color: #94b5ee;
}

QToolButton#pageHelpButton {
    background: #ffffff;
    color: #2f6be8;
    border: 1px solid #b9cdf2;
    border-radius: 7px;
    padding: 7px 12px;
    font-weight: 650;
}

QToolButton#pageHelpButton:hover {
    background: #eef5ff;
}

QFrame#ruleCard {
    background: #ffffff;
    border: 1px solid #dce4ee;
    border-radius: 10px;
}

QFrame#ruleCard[enabledRule="false"] {
    background: #f6f8fb;
}

QLabel#ruleTitle {
    color: #172033;
    font-size: 14px;
    font-weight: 700;
}

QLabel#ruleDescription {
    color: #68778d;
    font-size: 12px;
}

QFrame#taskPanel {
    background: #ffffff;
    border: 1px solid #dce4ee;
    border-radius: 11px;
}

QLabel#panelTitle {
    color: #172033;
    font-size: 14px;
    font-weight: 700;
}

QProgressBar {
    background: #eef2f7;
    border: 1px solid #d4dde8;
    border-radius: 6px;
    text-align: center;
    color: #334155;
    min-height: 16px;
}

QProgressBar::chunk {
    background: #2f6be8;
    border-radius: 5px;
}

QHeaderView::section {
    background: #edf2f7;
    color: #334155;
    border: none;
    border-right: 1px solid #d8e0ea;
    border-bottom: 1px solid #d8e0ea;
    padding: 7px;
    font-weight: 650;
}

QTableWidget {
    gridline-color: #e2e8f0;
    alternate-background-color: #f8fafc;
}

QTableWidget::item {
    padding: 5px;
}

QTableWidget::item:selected {
    background: #dce9ff;
    color: #172033;
}

QScrollArea {
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 11px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #bdc8d6;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #9baabc;
}

QStatusBar {
    background: #ffffff;
    border-top: 1px solid #dce4ee;
    color: #526276;
}
"""


def build_app_style() -> str:
    """生成带绝对资源路径的样式，确保开发运行和打包后都能显示复选框勾选图标。"""
    from g_file_studio.services.paths import resource_root

    check_icon = (resource_root() / "resources" / "icons" / "check.svg").as_posix()
    return APP_STYLE.replace("__CHECK_ICON__", check_icon)
