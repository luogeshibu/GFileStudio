from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g_file_studio.engines import merge_engine
from g_file_studio.ui.widgets.help_widgets import set_secondary


class FileOrderEditor(QWidget):
    """扫描合并输入文件，并允许用户通过按钮自由调整合并顺序。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._input_dir = Path()
        self._rows: list[dict[str, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(9)

        note = QLabel(
            "首行文件将作为合并基准。点击“扫描/检查”读取目录，再用上移、下移、置顶、置底自由定义顺序。"
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        root.addWidget(note)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.refresh_button = QPushButton("扫描 / 检查")
        self.natural_button = QPushButton("恢复自然排序")
        self.top_button = QPushButton("置顶")
        self.up_button = QPushButton("上移")
        self.down_button = QPushButton("下移")
        self.bottom_button = QPushButton("置底")

        for button in (
            self.refresh_button,
            self.natural_button,
            self.top_button,
            self.up_button,
            self.down_button,
            self.bottom_button,
        ):
            set_secondary(button)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["顺序", "文件名", "垂直对齐基准", "原始基准 Y", "状态"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(230)
        root.addWidget(self.table)

        self.refresh_button.setToolTip(
            "扫描输入目录。已有手动顺序会尽量保留，新发现的文件追加到末尾，同时检查后缀、外框和对齐基准。"
        )
        self.natural_button.setToolTip("按文件名自然排序重新排列，例如 file2 位于 file10 前面。")
        self.top_button.setToolTip("把当前选中的文件移动到第一位，并作为合并基准文件。")
        self.up_button.setToolTip("把当前选中的文件向前移动一位。")
        self.down_button.setToolTip("把当前选中的文件向后移动一位。")
        self.bottom_button.setToolTip("把当前选中的文件移动到最后一位。")

        self.refresh_button.clicked.connect(lambda: self.refresh())
        self.natural_button.clicked.connect(lambda: self.reset_natural_order())
        self.top_button.clicked.connect(lambda: self.move_top())
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.bottom_button.clicked.connect(lambda: self.move_bottom())

    def set_input_dir(self, path: Path | str) -> None:
        new_path = Path(path)
        if str(new_path) != str(self._input_dir):
            self._input_dir = new_path
            self.clear()

    def input_dir(self) -> Path:
        return self._input_dir

    def clear(self) -> None:
        self._rows.clear()
        self.table.setRowCount(0)

    def ordered_file_names(self) -> list[str]:
        return [row["file_name"] for row in self._rows]

    def refresh(self, preserve_order: bool = True, show_errors: bool = True) -> bool:
        try:
            natural_infos = merge_engine.discover_files(self._input_dir)
            natural_names = [info.path.name for info in natural_infos]

            if preserve_order and self._rows:
                existing = self.ordered_file_names()
                existing_set = {name.casefold() for name in natural_names}
                order = [name for name in existing if name.casefold() in existing_set]
                order_keys = {name.casefold() for name in order}
                order.extend(name for name in natural_names if name.casefold() not in order_keys)
            else:
                order = natural_names

            infos = merge_engine.discover_files(
                self._input_dir,
                ordered_file_names=order,
            )
        except Exception as exc:
            self.clear()
            if show_errors:
                QMessageBox.warning(self, "输入文件检查失败", str(exc))
            return False

        rows: list[dict[str, str]] = []
        errors: list[str] = []
        for info in infos:
            alignment_mode = ""
            alignment_y = ""
            status = "正常"
            try:
                parsed = merge_engine.parse_g_file(info)
                alignment_mode = parsed.alignment_mode
                alignment_y = merge_engine.format_integer(parsed.alignment_y)
            except Exception as exc:
                status = "失败"
                errors.append(f"{info.path.name}：{exc}")

            rows.append(
                {
                    "file_name": info.path.name,
                    "alignment_mode": alignment_mode,
                    "alignment_y": alignment_y,
                    "status": status,
                }
            )

        self._rows = rows
        self._rebuild_table()

        if errors:
            if show_errors:
                QMessageBox.warning(
                    self,
                    "输入检查未通过",
                    "以下文件不能参与合并：\n\n" + "\n\n".join(errors),
                )
            return False
        return True

    def ensure_ready(self) -> bool:
        """运行前重新扫描并验证，同时保留用户当前定义的顺序。"""
        return self.refresh(preserve_order=True, show_errors=True)

    def reset_natural_order(self) -> None:
        self.refresh(preserve_order=False, show_errors=True)

    def move_selected(self, offset: int) -> None:
        row = self.table.currentRow()
        if row < 0 or not self._rows:
            return
        target = max(0, min(len(self._rows) - 1, row + offset))
        if target == row:
            return
        item = self._rows.pop(row)
        self._rows.insert(target, item)
        self._rebuild_table()
        self.table.selectRow(target)

    def move_top(self) -> None:
        row = self.table.currentRow()
        if row <= 0:
            return
        item = self._rows.pop(row)
        self._rows.insert(0, item)
        self._rebuild_table()
        self.table.selectRow(0)

    def move_bottom(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows) - 1:
            return
        item = self._rows.pop(row)
        self._rows.append(item)
        self._rebuild_table()
        self.table.selectRow(len(self._rows) - 1)

    def _rebuild_table(self) -> None:
        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            values = [
                str(row_index + 1),
                row["file_name"],
                row["alignment_mode"],
                row["alignment_y"],
                row["status"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (0, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
