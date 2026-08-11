from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g_file_studio.engines.icon_upgrade_engine import analyze_icon_pairs


class IconUpgradeEditor(QWidget):
    """管理本次升级所需的新旧图元 G 文件，按文件名强制一一配对。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._old: dict[str, Path] = {}
        self._new: dict[str, Path] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        actions = QHBoxLayout()
        self.add_old = QPushButton("添加旧图元 G…")
        self.add_new = QPushButton("添加新图元 G…")
        self.remove = QPushButton("移除选中")
        self.clear = QPushButton("清空")
        self.analyze = QPushButton("检查配对与参数")
        for button in (self.add_old, self.add_new, self.remove, self.clear, self.analyze):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["图元文件", "旧图元", "新图元", "状态"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(150)
        layout.addWidget(self.table)

        self.summary = QLabel("尚未添加图元。旧、新图元必须按相同文件名一一对应。")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("mutedText")
        layout.addWidget(self.summary)

        self.add_old.clicked.connect(lambda: self._choose("old"))
        self.add_new.clicked.connect(lambda: self._choose("new"))
        self.remove.clicked.connect(self._remove_selected)
        self.clear.clicked.connect(self._clear)
        self.analyze.clicked.connect(self._show_analysis)

    def old_paths(self) -> list[Path]:
        return list(self._old.values())

    def new_paths(self) -> list[Path]:
        return list(self._new.values())

    def _choose(self, side: str) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择旧图元 G 文件" if side == "old" else "选择新图元 G 文件",
            "",
            "G Files (*.g);;All Files (*)",
        )
        target = self._old if side == "old" else self._new
        for name in files:
            path = Path(name)
            target[path.name] = path
        self._refresh()

    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            key_item = self.table.item(row, 0)
            if key_item is None:
                continue
            key = key_item.text()
            self._old.pop(key, None)
            self._new.pop(key, None)
        self._refresh()

    def _clear(self) -> None:
        self._old.clear()
        self._new.clear()
        self._refresh()

    def _refresh(self) -> None:
        names = sorted(set(self._old) | set(self._new))
        self.table.setRowCount(len(names))
        for row, name in enumerate(names):
            old = self._old.get(name)
            new = self._new.get(name)
            status = "待检查" if old and new else ("缺少新图元" if old else "缺少旧图元")
            values = [name, str(old) if old else "—", str(new) if new else "—", status]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        paired = len(set(self._old) & set(self._new))
        missing = len(names) - paired
        self.summary.setText(f"已添加 {len(names)} 种图元；完整配对 {paired} 种，缺失配对 {missing} 种。")

    def analysis(self):
        return analyze_icon_pairs(self.old_paths(), self.new_paths())

    def validate_for_run(self) -> tuple[bool, str]:
        if not self._old and not self._new:
            return False, "已勾选图元版本升级适配，但尚未添加旧图元和新图元 G 文件。"
        try:
            analysis = self.analysis()
        except Exception as exc:
            return False, str(exc)
        problems: list[str] = []
        if analysis.missing_old:
            problems.append("缺少旧图元：" + ", ".join(analysis.missing_old))
        if analysis.missing_new:
            problems.append("缺少新图元：" + ", ".join(analysis.missing_new))
        if analysis.incompatible:
            problems.append("不兼容：\n" + "\n".join(analysis.incompatible))
        if problems:
            return False, "\n".join(problems)
        return True, f"图元配对检查通过，共 {len(analysis.rules)} 种。"

    def _show_analysis(self) -> None:
        ok, message = self.validate_for_run()
        try:
            analysis = self.analysis()
        except Exception:
            analysis = None
        if analysis is not None:
            by_name = analysis.rules
            names = sorted(set(self._old) | set(self._new))
            for row, name in enumerate(names):
                rule = by_name.get(name)
                if rule:
                    status = (
                        f"✓ {rule.old.width:g}×{rule.old.height:g} → {rule.new.width:g}×{rule.new.height:g}；"
                        f"AC {rule.old.align_center} → {rule.new.align_center}；Pins {len(rule.old.pins)}"
                    )
                    self.table.setItem(row, 3, QTableWidgetItem(status))
        self.summary.setText(message)
        if ok:
            QMessageBox.information(self, "图元配对检查", message)
        else:
            QMessageBox.warning(self, "图元配对检查未通过", message)
