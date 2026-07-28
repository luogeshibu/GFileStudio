from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget


class PersonEditor(QWidget):
    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name_edit = QLineEdit()
        self.date_edit = QLineEdit()
        self.name_edit.setPlaceholderText(f"{role} 姓名")
        self.date_edit.setPlaceholderText("YYYY-MM-DD")
        self.name_edit.setToolTip(f"填写 {role} 姓名")
        self.date_edit.setToolTip(f"填写 {role} 日期，格式由项目要求决定，例如 2026-07-28")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.name_edit, 2)
        layout.addWidget(self.date_edit, 1)

    def name(self) -> str:
        return self.name_edit.text().strip()

    def date(self) -> str:
        return self.date_edit.text().strip()

    def set_values(self, name: str, date: str) -> None:
        self.name_edit.setText(name)
        self.date_edit.setText(date)
