from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QDateEdit, QHBoxLayout, QLineEdit, QWidget


class OptionalDateEdit(QDateEdit):
    """支持日历选择并允许保持为空的日期输入框。"""

    EMPTY_DATE = QDate(1900, 1, 1)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setMinimumDate(self.EMPTY_DATE)
        self.setMaximumDate(QDate(2999, 12, 31))
        self.setSpecialValueText("选择日期")
        self.setDate(self.EMPTY_DATE)
        self.setToolTip("点击右侧日历按钮选择日期；显示“选择日期”时表示未填写。")

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        """忽略鼠标滚轮，避免滚动页面时意外改变日期。"""
        event.ignore()

    def text_value(self) -> str:
        if self.date() == self.EMPTY_DATE:
            return ""
        return self.date().toString("yyyy-MM-dd")

    def set_text_value(self, value: str) -> None:
        text = (value or "").strip()
        if not text:
            self.setDate(self.EMPTY_DATE)
            return

        parsed = QDate.fromString(text, "yyyy-MM-dd")
        if not parsed.isValid():
            # 兼容早期配置中可能使用的 yyyy-M-d 格式。
            parsed = QDate.fromString(text, "yyyy-M-d")
        self.setDate(parsed if parsed.isValid() else self.EMPTY_DATE)


class PersonEditor(QWidget):
    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name_edit = QLineEdit()
        self.date_edit = OptionalDateEdit()
        self.name_edit.setPlaceholderText(f"{role} 姓名")
        self.name_edit.setToolTip(f"填写 {role} 姓名")
        self.date_edit.setToolTip(f"选择 {role} 日期；未选择时保持为空。")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.name_edit, 2)
        layout.addWidget(self.date_edit, 1)

    def name(self) -> str:
        return self.name_edit.text().strip()

    def date(self) -> str:
        return self.date_edit.text_value()

    def set_values(self, name: str, date: str) -> None:
        self.name_edit.setText(name)
        self.date_edit.set_text_value(date)
