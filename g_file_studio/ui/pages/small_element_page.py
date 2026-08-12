from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from g_file_studio.engines.small_element_engine import (
    SmallElementIssue,
    delete_issues_to_output,
    scan_file,
    write_reports,
)
from g_file_studio.processors.common import discover_g_inputs
from g_file_studio.services.output_naming import make_task_timestamp
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, IntegerInput, PathRow, TaskPanel
from g_file_studio.ui.widgets.help_widgets import set_secondary


class CopyableResultTable(QTableWidget):
    """结果表按普通表格方式选择单元格/区域，并支持 Ctrl+C 复制。"""

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            indexes = self.selectedIndexes()
            if indexes:
                rows = sorted({idx.row() for idx in indexes})
                cols = sorted({idx.column() for idx in indexes})
                lines: list[str] = []
                # 复制时带表头，粘贴到 Excel/文本编辑器都能直接使用。
                lines.append("\t".join(self.horizontalHeaderItem(c).text() for c in cols))
                for row in rows:
                    values = []
                    for col in cols:
                        item = self.item(row, col)
                        values.append(item.text() if item else "")
                    lines.append("\t".join(values))
                QApplication.clipboard().setText("\n".join(lines))
                event.accept()
                return
        super().keyPressEvent(event)


class SmallElementPage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.issues: list[SmallElementIssue] = []
        self.all_issues: list[SmallElementIssue] = []
        self.processed_issues: list[SmallElementIssue] = []
        self.last_html_report: Path | None = None
        self.last_csv_report: Path | None = None
        help_title, help_html = APP_HELP["small_elements"]
        super().__init__(
            "异常小尺寸图元检测",
            "扫描 ConnectLine、FeedLine、Bus、BusDis 中疑似误画后残留的异常短线/小尺寸图元，并按用户选择删除。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(InfoBanner(
            "该模块独立检查 ConnectLine、FeedLine、Bus、BusDis，不区分母线方向。默认判定为 w<10 且 h<10。"
            "扫描结果采用表格方式显示，可直接选择单个单元格或一块区域并按 Ctrl+C 复制。需要处理的图元请在首列勾选，支持单选、多选和全选。"
            "执行选中处理时会输出修改后的 G 文件，并生成带时间戳的 CSV/HTML 报告；若勾选项存在非空 keyid，会先明确提示后再确认。"
        ))

        io_box = QGroupBox("扫描文件与输出")
        io_layout = QVBoxLayout(io_box)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            settings_prefix="small_elements",
            settings_service=self.user_settings,
        )
        io_layout.addWidget(self.source)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择异常小尺寸图元报告/处理输出目录",
            recent_directory_key="recent_paths/small_elements/output_directory",
            persistent_path_key="small_elements/output_directory",
            default_path=default_workspace() / "short-lines",
            location_name="异常小尺寸图元输出目录",
            settings_service=self.user_settings,
        )
        output_row = QHBoxLayout()
        label = QLabel("输出目录")
        label.setMinimumWidth(72)
        output_row.addWidget(label)
        output_row.addWidget(self.output_path, 1)
        io_layout.addLayout(output_row)
        self.layout.addWidget(io_box)

        settings_box = QGroupBox("检测规则")
        form = QFormLayout(settings_box)
        self.threshold = IntegerInput(value=self.user_settings.get_int("small_elements/threshold", 10), minimum=1, maximum=100000)
        self.threshold.setToolTip("当目标元素的 w 和 h 同时小于该值时，报告为异常小尺寸图元。")
        form.addRow("异常尺寸阈值", self.threshold)
        self.layout.addWidget(settings_box)

        result_box = QGroupBox("异常图元结果")
        result_layout = QVBoxLayout(result_box)
        self.summary = QLabel("尚未扫描。")
        self.summary.setObjectName("mutedText")
        result_layout.addWidget(self.summary)
        self.table = CopyableResultTable(0, 9)
        self.table.setHorizontalHeaderLabels(["处理", "文件", "元素类型", "XML ID", "X", "Y", "W", "H", "keyid"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(260)
        self.table.setToolTip("首列勾选决定哪些图元参与处理；其余单元格可像表格一样单选/框选，按 Ctrl+C 复制。")
        result_layout.addWidget(self.table)
        result_actions = QHBoxLayout()
        self.scan_button = QPushButton("扫描异常图元")
        self.scan_button.setToolTip("扫描完成后会生成/覆盖本模块的扫描 CSV/HTML 报告，可点击“打开报告”查看。")
        self.select_all_box = QCheckBox("全选处理")
        result_actions.addWidget(self.scan_button)
        self.copy_hint = QLabel("可单独选择 XML ID 或任意单元格/区域，按 Ctrl+C 复制")
        self.copy_hint.setObjectName("mutedText")
        result_actions.addWidget(self.select_all_box)
        result_actions.addStretch(1)
        result_actions.addWidget(self.copy_hint)
        result_layout.addLayout(result_actions)
        self.layout.addWidget(result_box)

        self.task = TaskPanel()
        self.task.run_button.hide()
        self.process_button = QPushButton("执行选中处理")
        self.process_button.setToolTip("执行完成后会生成修改后的 G 文件，并生成/覆盖本模块的处理 CSV/HTML 报告，可点击“打开报告”查看。")
        self.process_button.setEnabled(False)
        self.report_button = QPushButton("打开报告")
        self.report_button.setEnabled(False)
        set_secondary(self.report_button)
        self.task.buttons_layout.insertWidget(1, self.process_button)
        self.task.buttons_layout.insertWidget(2, self.report_button)
        self.layout.addWidget(self.task, 1)

        self.scan_button.clicked.connect(self.scan)
        self.process_button.clicked.connect(self.process_checked)
        self.report_button.clicked.connect(self.open_last_report)
        self.select_all_box.toggled.connect(self._toggle_all_checks)
        self.table.itemChanged.connect(self._on_check_changed)

    def _inputs(self) -> list[Path]:
        return discover_g_inputs(self.source.path(), self.source.mode())

    def scan(self) -> None:
        try:
            paths = self._inputs()
        except Exception as exc:
            QMessageBox.warning(self, "无法扫描", str(exc))
            return
        if not paths:
            QMessageBox.information(self, "没有文件", "没有找到可扫描的 G 文件。")
            return
        output_dir = self.output_path.path()
        output_dir.mkdir(parents=True, exist_ok=True)
        threshold = self.threshold.value()
        self.task.log_view.clear()
        self.task.progress.setValue(0)
        self.task.append_log(f"开始扫描异常小尺寸图元，共 {len(paths)} 个文件；阈值：w<{threshold} 且 h<{threshold}。")
        progress = QProgressDialog("正在扫描异常短线图元……", "取消", 0, len(paths), self)
        progress.setWindowTitle("异常小尺寸图元检测")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        issues: list[SmallElementIssue] = []
        for index, path in enumerate(paths, 1):
            progress.setLabelText(f"正在扫描：{path.name}\n{index}/{len(paths)}")
            QApplication.processEvents()
            if progress.wasCanceled():
                self.task.append_log("扫描已取消。")
                return
            try:
                found = scan_file(path, threshold)
                issues.extend(found)
                self.task.append_log(f"[{index}/{len(paths)}] {path.name}：发现 {len(found)} 个异常图元。")
            except Exception as exc:
                progress.close()
                self.task.append_log(f"扫描失败：{path.name}：{exc}")
                QMessageBox.critical(self, "扫描失败", f"{path.name}\n{exc}")
                return
            pct = round(index * 100 / len(paths))
            self.task.progress.setValue(pct)
            progress.setValue(index)
        progress.close()
        self.issues = list(issues)
        self.all_issues = list(issues)
        self.processed_issues = []
        self.select_all_box.blockSignals(True)
        self.select_all_box.setChecked(False)
        self.select_all_box.blockSignals(False)
        self._fill_table()
        timestamp = make_task_timestamp()
        csv_path, html_path = write_reports(output_dir, issues, threshold, timestamp, report_kind="scan")
        self.last_csv_report = csv_path
        self.last_html_report = html_path
        self.report_button.setEnabled(True)
        self.process_button.setEnabled(False)
        self.summary.setText(
            f"扫描完成：{len(paths)} 个文件，发现 {len(issues)} 个异常图元，其中 {sum(1 for x in issues if x.keyid)} 个存在 keyid。"
            f"报告：{csv_path.name} / {html_path.name}"
        )
        self.task.append_log(f"扫描完成：发现 {len(issues)} 个异常图元，其中 {sum(1 for x in issues if x.keyid)} 个存在 keyid。")
        for item in issues:
            self.task.append_log(
                f"[异常] {item.file_name} | <{item.element_type}> | id={item.xml_id or '(空)'} | "
                f"x={item.x or '-'}, y={item.y or '-'}, w={item.w or '-'}, h={item.h or '-'} | keyid={item.keyid or '(空)'}"
            )
        self.task.append_log(f"CSV 报告：{csv_path}")
        self.task.append_log(f"HTML 报告：{html_path}")
        self.task.open_button.setEnabled(True)
        self.task._output_dir = output_dir
        QMessageBox.information(
            self,
            "扫描完成",
            "异常小尺寸图元扫描完成，扫描报告已生成并覆盖上一份扫描报告。\n可点击“打开报告”查看 HTML 报告。",
        )
        self.user_settings.set_value("small_elements/threshold", threshold)

    def _fill_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in self.issues:
            row = self.table.rowCount()
            self.table.insertRow(row)
            check_item = QTableWidgetItem("")
            check_item.setFlags((check_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled) & ~Qt.ItemFlag.ItemIsEditable)
            check_item.setCheckState(Qt.CheckState.Unchecked)
            check_item.setData(Qt.ItemDataRole.UserRole, item)
            self.table.setItem(row, 0, check_item)
            values = [item.file_name, item.element_type, item.xml_id, item.x, item.y, item.w, item.h, item.keyid]
            for col, value in enumerate(values, 1):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item)
                self.table.setItem(row, col, cell)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self._update_process_state()

    def _checked_issues(self) -> list[SmallElementIssue]:
        result: list[SmallElementIssue] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                issue = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(issue, SmallElementIssue):
                    result.append(issue)
        return result

    def _toggle_all_checks(self, checked: bool) -> None:
        self.table.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(state)
        self.table.blockSignals(False)
        self._update_process_state()

    def _on_check_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        checked_count = len(self._checked_issues())
        total = self.table.rowCount()
        self.select_all_box.blockSignals(True)
        self.select_all_box.setChecked(total > 0 and checked_count == total)
        self.select_all_box.blockSignals(False)
        self._update_process_state()

    def _update_process_state(self) -> None:
        count = len(self._checked_issues())
        self.process_button.setEnabled(count > 0)
        self.process_button.setText(f"执行选中处理（{count}）" if count else "执行选中处理")

    def _confirm_process(self, selected: list[SmallElementIssue]) -> bool:
        keyed = [x for x in selected if x.keyid]
        if keyed:
            details = "\n".join(
                f"{x.file_name} | <{x.element_type}> | id={x.xml_id or '(空)'} | keyid={x.keyid}"
                for x in keyed[:50]
            )
            if len(keyed) > 50:
                details += f"\n……其余 {len(keyed)-50} 项省略"
            answer = QMessageBox.warning(
                self,
                "待处理元素已关联 keyid",
                f"本次勾选 {len(selected)} 个异常图元，其中 {len(keyed)} 个存在非空 keyid。\n"
                "执行后这些图元会从输出 G 文件中删除。是否继续？\n\n" + details,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        else:
            answer = QMessageBox.question(
                self,
                "确认执行",
                f"确认处理当前勾选的 {len(selected)} 个异常图元吗？\n"
                "程序会生成修改后的 G 文件以及本次 CSV/HTML 报告，原文件不会覆盖。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        return answer == QMessageBox.StandardButton.Yes

    @staticmethod
    def _issue_key(item: SmallElementIssue) -> tuple[str, str, int, str]:
        return (str(item.file_path), item.element_type, item.ordinal, item.xml_id)

    def process_checked(self) -> None:
        selected = self._checked_issues()
        if not selected:
            QMessageBox.information(self, "未勾选", "请先在结果表第一列勾选需要处理的异常图元。")
            return
        if not self._confirm_process(selected):
            return
        output_dir = self.output_path.path()
        cumulative_map = {self._issue_key(x): x for x in self.processed_issues}
        for item in selected:
            cumulative_map[self._issue_key(item)] = item
        cumulative = list(cumulative_map.values())
        try:
            outputs = delete_issues_to_output(cumulative, output_dir)
            timestamp = make_task_timestamp()
            csv_path, html_path = write_reports(output_dir, selected, self.threshold.value(), timestamp, report_kind="process")
        except Exception as exc:
            self.task.append_log(f"执行处理失败：{exc}")
            QMessageBox.critical(self, "处理失败", str(exc))
            return

        self.processed_issues = cumulative
        selected_keys = {self._issue_key(x) for x in selected}
        self.issues = [x for x in self.issues if self._issue_key(x) not in selected_keys]
        self.last_csv_report = csv_path
        self.last_html_report = html_path
        self.report_button.setEnabled(True)
        self._fill_table()
        self.select_all_box.blockSignals(True)
        self.select_all_box.setChecked(False)
        self.select_all_box.blockSignals(False)
        self.summary.setText(
            f"本次已处理 {len(selected)} 个异常图元，当前结果表剩余 {len(self.issues)} 个；"
            f"输出 G 文件 {len(outputs)} 个。报告：{csv_path.name} / {html_path.name}"
        )
        self.task.append_log(f"本次处理异常图元 {len(selected)} 个；累计处理 {len(self.processed_issues)} 个；当前剩余 {len(self.issues)} 个。")
        for item in selected:
            self.task.append_log(
                f"[已处理] {item.file_name} | <{item.element_type}> | id={item.xml_id or '(空)'} | "
                f"x={item.x or '-'}, y={item.y or '-'}, w={item.w or '-'}, h={item.h or '-'} | keyid={item.keyid or '(空)'}"
            )
        for path in outputs:
            self.task.append_log(f"输出 G：{path}")
        self.task.append_log(f"CSV 报告：{csv_path}")
        self.task.append_log(f"HTML 报告：{html_path}")
        self.task.open_button.setEnabled(True)
        self.task._output_dir = output_dir
        QMessageBox.information(
            self,
            "处理完成",
            f"已处理 {len(selected)} 个异常图元，输出 {len(outputs)} 个 G 文件。\n"
            f"当前列表剩余 {len(self.issues)} 个异常图元。\n原文件未修改。\n\n处理报告已生成并覆盖上一份处理报告，可点击“打开报告”查看。",
        )

    def open_last_report(self) -> None:
        if not self.last_html_report or not self.last_html_report.exists():
            QMessageBox.information(self, "暂无报告", "请先执行一次扫描并生成报告。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_html_report.resolve())))

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()
        self.user_settings.set_value("small_elements/threshold", self.threshold.value())
