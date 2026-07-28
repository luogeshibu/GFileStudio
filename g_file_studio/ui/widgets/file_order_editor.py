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
    """扫描合并输入文件，并允许用户筛选和自由调整实际合并顺序。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._input_dir = Path()
        self._rows: list[dict[str, str]] = []
        # 仅表示从“本次合并列表”排除，不会删除磁盘上的源文件。
        self._excluded_names: set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(9)

        note = QLabel(
            "首行文件将作为合并基准。扫描后可用 Ctrl/Shift 多选并删除不需要参与合并的文件，"
            "再通过上移、下移、置顶、置底定义最终顺序。删除只影响本次合并列表，不会删除磁盘文件。"
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        root.addWidget(note)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.refresh_button = QPushButton("扫描 / 检查")
        self.natural_button = QPushButton("恢复全部并排序")
        self.delete_button = QPushButton("删除所选")
        self.top_button = QPushButton("置顶")
        self.up_button = QPushButton("上移")
        self.down_button = QPushButton("下移")
        self.bottom_button = QPushButton("置底")

        for button in (
            self.refresh_button,
            self.natural_button,
            self.delete_button,
            self.top_button,
            self.up_button,
            self.down_button,
            self.bottom_button,
        ):
            set_secondary(button)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.summary_label = QLabel("尚未扫描输入目录。")
        self.summary_label.setObjectName("mutedText")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["顺序", "文件名", "垂直对齐基准", "原始基准 Y", "状态"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # 支持 Ctrl/Shift 一次选择多行并删除。
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(230)
        root.addWidget(self.table)

        self.refresh_button.setToolTip(
            "重新扫描输入目录。保留当前手动顺序和已排除文件；新发现的文件会追加到末尾。"
        )
        self.natural_button.setToolTip(
            "恢复目录中的全部 .sln.pic.g 文件，并按文件名自然排序；此前删除的列表项也会恢复。"
        )
        self.delete_button.setToolTip(
            "从本次合并列表移除所选文件。支持 Ctrl/Shift 多选；不会删除磁盘上的源文件。"
        )
        self.top_button.setToolTip("把当前选中的一行移动到第一位，并作为合并基准文件。")
        self.up_button.setToolTip("把当前选中的一行向前移动一位。")
        self.down_button.setToolTip("把当前选中的一行向后移动一位。")
        self.bottom_button.setToolTip("把当前选中的一行移动到最后一位。")

        self.refresh_button.clicked.connect(lambda: self.refresh())
        self.natural_button.clicked.connect(lambda: self.reset_natural_order())
        self.delete_button.clicked.connect(self.remove_selected)
        self.top_button.clicked.connect(lambda: self.move_top())
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.bottom_button.clicked.connect(lambda: self.move_bottom())

    def set_input_dir(self, path: Path | str) -> None:
        new_path = Path(path)
        if str(new_path) != str(self._input_dir):
            self._input_dir = new_path
            self.clear(reset_exclusions=True)

    def input_dir(self) -> Path:
        return self._input_dir

    def clear(self, *, reset_exclusions: bool = True) -> None:
        self._rows.clear()
        if reset_exclusions:
            self._excluded_names.clear()
        self.table.setRowCount(0)
        self._update_summary()

    def ordered_file_names(self) -> list[str]:
        """返回当前界面中保留的文件；该列表就是实际合并文件集合和顺序。"""
        return [row["file_name"] for row in self._rows]

    def excluded_file_names(self) -> list[str]:
        """返回已从本次合并列表排除的文件名，主要用于状态展示和测试。"""
        return sorted(self._excluded_names)

    def refresh(self, preserve_order: bool = True, show_errors: bool = True) -> bool:
        try:
            natural_infos = merge_engine.discover_files(self._input_dir)
            natural_names = [info.path.name for info in natural_infos]
            natural_key_map = {name.casefold(): name for name in natural_names}

            # 清理目录中已经不存在的排除项，避免状态长期积累无效名称。
            self._excluded_names.intersection_update(natural_key_map)

            if preserve_order and (self._rows or self._excluded_names):
                existing = self.ordered_file_names()
                available_keys = set(natural_key_map)
                order = [
                    natural_key_map[name.casefold()]
                    for name in existing
                    if name.casefold() in available_keys
                    and name.casefold() not in self._excluded_names
                ]
                order_keys = {name.casefold() for name in order}
                order.extend(
                    name
                    for name in natural_names
                    if name.casefold() not in order_keys
                    and name.casefold() not in self._excluded_names
                )
            else:
                order = natural_names

            if not order:
                self._rows = []
                self._rebuild_table()
                if show_errors:
                    QMessageBox.warning(
                        self,
                        "没有可合并文件",
                        "当前列表中没有保留任何 G 文件。请恢复全部文件，或重新扫描后至少保留一个文件。",
                    )
                return False

            infos = merge_engine.discover_files(
                self._input_dir,
                ordered_file_names=order,
                allow_subset=True,
            )
        except Exception as exc:
            self.clear(reset_exclusions=False)
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
                    "以下保留文件不能参与合并：\n\n" + "\n\n".join(errors),
                )
            return False
        return True

    def ensure_ready(self) -> bool:
        """运行前重新验证当前保留集合，并保持排除项与用户排序。"""
        if not self._rows and self._excluded_names:
            QMessageBox.warning(
                self,
                "没有可合并文件",
                "你已经从本次合并列表中移除了全部文件。请至少恢复或保留一个 G 文件。",
            )
            return False
        return self.refresh(preserve_order=True, show_errors=True)

    def reset_natural_order(self) -> None:
        """恢复目录中的全部候选文件并按自然顺序排列。"""
        self._excluded_names.clear()
        self.refresh(preserve_order=False, show_errors=True)

    def remove_selected(self) -> None:
        """从本次合并集合删除选中行，不删除磁盘文件。"""
        selection_model = self.table.selectionModel()
        selected_rows = sorted(
            {index.row() for index in selection_model.selectedRows()},
            reverse=True,
        )
        if not selected_rows:
            QMessageBox.information(
                self,
                "请选择文件",
                "请先在表格中选择一个或多个要从本次合并列表移除的文件。",
            )
            return

        names = [self._rows[row]["file_name"] for row in reversed(selected_rows)]
        answer = QMessageBox.question(
            self,
            "从本次合并列表移除",
            f"确定从本次合并列表移除所选的 {len(names)} 个文件吗？\n\n"
            "此操作不会删除磁盘上的源文件。可点击“恢复全部并排序”重新加入。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        first_removed_row = min(selected_rows)
        for row in selected_rows:
            item = self._rows.pop(row)
            self._excluded_names.add(item["file_name"].casefold())

        self._rebuild_table()
        if self._rows:
            self.table.selectRow(min(first_removed_row, len(self._rows) - 1))

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

    def _update_summary(self) -> None:
        kept = len(self._rows)
        excluded = len(self._excluded_names)
        if kept == 0 and excluded == 0:
            self.summary_label.setText("尚未扫描输入目录。")
            return
        self.summary_label.setText(
            f"当前保留 {kept} 个文件参与合并；已从本次列表排除 {excluded} 个文件。"
        )

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
        self._update_summary()
