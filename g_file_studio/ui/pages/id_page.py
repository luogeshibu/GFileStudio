from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QThreadPool, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from g_file_studio.engines.id_engine import inspect_tree_ids
from g_file_studio.engines.id_rule_engine import (
    ServerIdRuleCandidate,
    ServerIdRuleSyncResult,
    infer_server_id_rules,
    scan_file_against_rules,
)
from g_file_studio.models import BasicOutputConflictAction, IdAction, IdSettings, InputMode
from g_file_studio.processors.common import discover_g_inputs
from g_file_studio.processors.id_processor import _write_id_reports, process_ids
from g_file_studio.services.id_rule_service import IdRule, IdRuleService
from g_file_studio.services.output_naming import make_task_timestamp
from g_file_studio.services.remote_g_source import ReadOnlySshClient, download_stable_files
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.run_history import begin_managed_run, configure_managed_output, update_run_status
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.table_layout import configure_responsive_table
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, PathRow, TaskPanel
from g_file_studio.ui.widgets.help_widgets import set_secondary
from g_file_studio.workers import FunctionWorker


class ScanResultDialog(QDialog):
    """固定尺寸的扫描结果窗口，长内容通过滚动条查看。"""

    def __init__(self, parent, title: str, text: str, *, warning: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 560)
        self.setMinimumSize(640, 420)

        header = QLabel(
            "扫描发现需要关注的内容，请在下方滚动查看。"
            if warning
            else "扫描完成，详细结果如下。"
        )
        header.setWordWrap(True)
        if warning:
            header.setObjectName("warningText")

        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(text)
        viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        viewer.setMinimumHeight(320)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(viewer, 1)
        layout.addWidget(buttons)


class RuleDialog(QDialog):
    def __init__(self, parent=None, rule: IdRule | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑 ID 规则" if rule else "新增 ID 规则")
        self.tag = QLineEdit(rule.tag if rule else "")
        self.prefix = QLineEdit(rule.prefix if rule else "")
        self.total_length = QLineEdit(str(rule.total_length) if rule else "")
        self.note = QLineEdit(rule.note if rule else "")
        form = QFormLayout()
        form.addRow("XML 元素类型", self.tag)
        form.addRow("ID 固定前缀", self.prefix)
        form.addRow("ID 总位数", self.total_length)
        form.addRow("备注", self.note)
        hint = QLabel("示例：ConnectLine 使用前缀 34、总位数 8，因此 34000053、34001838 合法，而 140、340123456 不合法。新增 ID 按同类型当前最大完整 ID + 1，并且结果必须继续满足前缀和总位数。")
        hint.setWordWrap(True)
        hint.setObjectName("mutedText")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def value(self) -> IdRule:
        tag = self.tag.text().strip()
        prefix = self.prefix.text().strip()
        if not tag:
            raise ValueError("XML 元素类型不能为空。")
        if not prefix.isdigit():
            raise ValueError("ID 固定前缀必须是数字。")
        try:
            total_length = int(self.total_length.text().strip())
        except ValueError:
            raise ValueError("ID 总位数必须是正整数。")
        if total_length <= len(prefix):
            raise ValueError("ID 总位数必须大于固定前缀长度。")
        return IdRule(tag=tag, prefix=prefix, total_length=total_length, enabled=True, verified=True, note=self.note.text().strip())


class ServerRuleReviewDialog(QDialog):
    """展示服务器全量统计，并让用户逐类确认要固化的候选规则。"""

    def __init__(
        self,
        parent,
        result: ServerIdRuleSyncResult,
        existing_rules: dict[str, IdRule],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("确认服务器 ID 规范")
        self.resize(1050, 620)
        self.setMinimumSize(820, 460)
        self._tags: list[str] = []

        intro = QLabel(
            "以下是服务器 G 文件的全量统计结果。候选规则按同类元素的主流前缀和总位数生成；"
            "勾选表示认可并固化，取消勾选表示保留当前规则或暂不建立。右侧会显示少数格式，供你判断服务器样本是否混入错误。"
        )
        intro.setWordWrap(True)
        intro.setObjectName("mutedText")

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "固化",
            "元素类型",
            "服务器主流规则",
            "主流次数 / 总次数",
            "出现文件数",
            "其他格式统计",
            "当前规则",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        configure_responsive_table(self.table)
        # The responsive helper configures interactive columns; keep the final
        # "当前规则" column stretched so the table fills the dialog on first show.
        self.table.horizontalHeader().setStretchLastSection(True)

        for tag, candidate in sorted(result.candidates.items()):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._tags.append(tag)
            select = QTableWidgetItem("")
            select.setFlags(select.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            select.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, select)
            self.table.setItem(row, 1, QTableWidgetItem(f"<{tag}>"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{candidate.prefix} + {candidate.total_length} 位"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{candidate.count} / {candidate.total_ids}"))
            self.table.setItem(row, 4, QTableWidgetItem(str(candidate.file_count)))
            others = "; ".join(f"{key}: {count}" for key, count in candidate.other_formats.items()) or "无"
            self.table.setItem(row, 5, QTableWidgetItem(others))
            current = existing_rules.get(tag)
            current_text = f"{current.prefix} + {current.total_length} 位" if current else "未建立"
            self.table.setItem(row, 6, QTableWidgetItem(current_text))
        self.table.resizeColumnsToContents()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("固化选中规则版本")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)

    def selected_candidates(self, result: ServerIdRuleSyncResult) -> list[ServerIdRuleCandidate]:
        selected: list[ServerIdRuleCandidate] = []
        for row, tag in enumerate(self._tags):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked and tag in result.candidates:
                selected.append(result.candidates[tag])
        return selected


class IdPage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.rule_service = IdRuleService()
        self._last_scan_candidates: dict[str, IdRule] = {}
        self._server_sync_worker: FunctionWorker | None = None
        self.last_html_report: Path | None = None
        help_title, help_html = APP_HELP["id_rules"]
        super().__init__(
            "ID 检查与修复",
            "扫描 G 文件 ID、维护规则模板，并可强制把不符合模板或重复的 ID 修复为模板格式。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(InfoBanner(
            "ID 规则以服务器 G 图形中的实际 ID 分布为依据，但服务器文件可能存在人为错误。"
            "读取服务器 G 后会汇总每种格式的出现次数，由你逐类确认并固化版本；"
            "服务器样本不足的类型只告警，不擅自猜测。执行修复时只使用最近一次固化的规则。"
        ))

        io_box = QGroupBox("扫描 / 处理文件")
        io_layout = QVBoxLayout(io_box)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择需要检查 ID 的 G 文件。",
            directory_tooltip="选择包含待检查 G 文件的目录；程序扫描目录第一层。",
            settings_prefix="id_rules",
            settings_service=self.user_settings,
        )
        io_layout.addWidget(self.source)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择 ID 修复输出目录",
            recent_directory_key="recent_paths/id_rules/output_directory",
            persistent_path_key="id_rules/output_directory",
            default_path=default_workspace() / "processed",
            location_name="ID 修复输出目录",
            settings_service=self.user_settings,
        )
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        configure_managed_output(self.output_path, "id")
        output_row = QHBoxLayout()
        output_label = QLabel("输出目录（workspace，只读）")
        output_label.setMinimumWidth(72)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_path, 1)
        io_layout.addLayout(output_row)
        self.layout.addWidget(io_box)

        template_box = QGroupBox("ID 规则模板")
        template_layout = QVBoxLayout(template_box)
        intro = QLabel("规则格式：XML 元素类型 + 固定数字起始前缀 + 固定 ID 总位数。服务器 G 图形用于全量统计，确认后才更新当前规则版本。新增 ID 按同类型当前最大完整 ID + 1，并始终校验前缀和位数。")
        intro.setWordWrap(True)
        intro.setObjectName("mutedText")
        template_layout.addWidget(intro)
        self.server_version_label = QLabel()
        self.server_version_label.setObjectName("mutedText")
        template_layout.addWidget(self.server_version_label)

        self.global_strict = QCheckBox("启用全局 ID 模板强制约束")
        self.global_strict.setChecked(self.user_settings.get_bool("id_rules/global_strict", True))
        self.global_strict.setToolTip(
            "默认开启：处理输出时会把已有不符合模板的 ID 也强制修复。关闭后不会强制改写已有格式不符 ID；"
            "但所有模块新生成的 ID 仍必须严格使用当前模板。"
        )
        self.global_strict.toggled.connect(self._global_strict_toggled)
        template_layout.addWidget(self.global_strict)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("新增规则")
        self.edit_button = QPushButton("编辑规则")
        self.delete_button = QPushButton("删除规则")
        self.server_sync_button = QPushButton("扫描服务器全部 ID 规范")
        self.server_sync_button.setToolTip(
            "后台读取当前 SSH 配置中的服务器 G 根目录，统计全部 G 文件的 ID 出现次数后，再由你确认哪些规则固化。"
        )
        for button in (self.add_button, self.edit_button, self.delete_button, self.server_sync_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        template_layout.addLayout(buttons)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["状态", "元素类型", "ID 起始前缀", "总位数", "合法示例", "当前规则", "备注"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        configure_responsive_table(self.table)
        # The responsive helper intentionally disables this by default for wide
        # tables.  ID rules are short enough that the last remarks column should
        # fill the remaining page width when the page opens or is resized.
        self.table.horizontalHeader().setStretchLastSection(True)
        template_layout.addWidget(self.table)
        self.layout.addWidget(template_box)

        self.task = TaskPanel()
        self.scan_button = QPushButton("扫描当前G文件（只检查ID）")
        self.scan_button.setToolTip("扫描完成后会生成/覆盖 ID 扫描 CSV/HTML 报告；规则使用最近一次已固化的服务器版本。服务器规则请单独扫描并确认。")
        self.task.run_button.setText("检查并强制修复 ID")
        self.task.run_button.setToolTip("执行后会按服务器已同步或手动维护的当前模板修复 ID，并生成/覆盖 ID 修复 CSV/HTML 报告，可点击“打开报告”查看。")
        self.report_button = QPushButton("打开报告")
        self.report_button.setEnabled(False)
        set_secondary(self.report_button)
        # ID 页面只保留两个明确动作：扫描/检查，以及强制修复。
        # 报告、输出目录、清空日志均集中在“执行与日志”。
        self.task.buttons_layout.insertWidget(0, self.scan_button)
        self.task.buttons_layout.insertWidget(2, self.report_button)
        self.layout.addWidget(self.task, 1)

        self.scan_button.clicked.connect(self.scan_current)
        self.add_button.clicked.connect(self.add_rule)
        self.edit_button.clicked.connect(self.edit_rule)
        self.delete_button.clicked.connect(self.delete_rule)
        self.server_sync_button.clicked.connect(self.sync_server_rules)
        self.task.run_button.clicked.connect(self.run)
        self.report_button.clicked.connect(self.open_last_report)
        self.task.resultReceived.connect(self._task_result)
        self._refresh_table()
        self._refresh_server_version_label()

    def _refresh_table(self) -> None:
        rules = self.rule_service.load_rules()
        self.table.setRowCount(0)
        for rule in sorted(rules.values(), key=lambda item: item.tag.lower()):
            row = self.table.rowCount()
            self.table.insertRow(row)
            example = rule.build(1)
            values = [
                "✓ 服务器已同步" if rule.note.startswith("服务器 G 图形自动读取") else "✓ 已确认",
                rule.tag,
                rule.prefix,
                str(rule.total_length),
                example,
                "前缀 + 总位数；同类型最大 ID + 1",
                rule.note,
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 1:
                    item.setData(Qt.ItemDataRole.UserRole, rule.tag)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def _refresh_server_version_label(self) -> None:
        snapshot = self.rule_service.load_server_snapshot()
        version = str(snapshot.get("version", "")).strip()
        if not version:
            self.server_version_label.setText("服务器 ID 规范版本：尚未固化；当前表格为本地已有规则")
            return
        self.server_version_label.setText(
            "服务器 ID 规范版本："
            f"{version} · 文件 {snapshot.get('file_count', 0)} · "
            f"图元 {snapshot.get('element_count', 0)} · 已固化类型 {snapshot.get('selected_rule_count', 0)}"
        )

    def _global_strict_toggled(self, checked: bool) -> None:
        if not checked:
            answer = QMessageBox.warning(
                self,
                "关闭全局 ID 强制约束",
                "关闭后，后续处理不会再强制改写 G 文件中已有但不符合模板的 ID。\n\n"
                "注意：所有模块新生成的 ID 仍会严格按照当前 ID 规则模板生成。\n\n"
                "确认关闭全局 ID 模板强制约束吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.global_strict.blockSignals(True)
                self.global_strict.setChecked(True)
                self.global_strict.blockSignals(False)
                return
        self.user_settings.set_value("id_rules/global_strict", "true" if checked else "false")
        self.task.append_log(
            "全局 ID 模板强制约束已开启：已有格式不符 ID 会在处理输出时按模板修复。"
            if checked
            else "全局 ID 模板强制约束已关闭：已有格式不符 ID 保持不变；新生成 ID 仍严格使用模板。"
        )

    def _selected_tag(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def add_rule(self) -> None:
        dialog = RuleDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            rule = dialog.value()
        except ValueError as exc:
            QMessageBox.warning(self, "规则无效", str(exc))
            return
        rules = self.rule_service.load_rules()
        if rule.tag in rules:
            QMessageBox.warning(self, "规则已存在", f"<{rule.tag}> 已存在，请使用“编辑规则”。")
            return
        self.rule_service.upsert(rule)
        self._refresh_table()

    def edit_rule(self) -> None:
        tag = self._selected_tag()
        if not tag:
            QMessageBox.information(self, "请选择规则", "请先选择要编辑的规则。")
            return
        old = self.rule_service.load_rules()[tag]
        dialog = RuleDialog(self, old)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            new = dialog.value()
        except ValueError as exc:
            QMessageBox.warning(self, "规则无效", str(exc))
            return
        if new.tag != old.tag:
            self.rule_service.remove(old.tag)
        self.rule_service.upsert(new)
        self._refresh_table()

    def delete_rule(self) -> None:
        tag = self._selected_tag()
        if not tag:
            QMessageBox.information(self, "请选择规则", "请先在表格中选中一条要删除的规则。")
            return
        if QMessageBox.question(
            self,
            "删除规则",
            f"确认删除 ID 规则 <{tag}>？\n\n删除后立即生效；再次扫描到对应元素类型时会重新提醒是否添加。",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.rule_service.remove(tag)
        self._last_scan_candidates.pop(tag, None)
        self._refresh_table()
        self.task.append_log(f"已立即删除 ID 规则 <{tag}>。")

    def _scan_server_rules_from_files(
        self,
        files: list[Path],
        *,
        log=None,
        progress=None,
    ) -> ServerIdRuleSyncResult:
        """扫描服务器 G 快照并返回统计候选；此处不修改当前规则。"""
        if not files:
            raise ValueError("没有找到可读取 ID 规范的服务器 G 文件。")
        log = log or self.task.append_log
        progress = progress or (lambda value: self.task.set_progress(70 + round(value * 0.25)))
        result = infer_server_id_rules(
            files,
            self.rule_service.load_rules(),
            progress=progress,
        )
        log(
            f"[服务器 ID 规范] 已读取 {result.file_count} 个 G 文件、{result.element_count} 个直接图元；"
            f"候选 {len(result.candidates)} 类，当前新增 {len(result.added)} 类，"
            f"当前变化 {len(result.updated)} 类，保持 {len(result.unchanged)} 类。"
        )
        for tag, candidate in sorted(result.candidates.items()):
            other = "; ".join(f"{key}×{count}" for key, count in candidate.other_formats.items()) or "无其他格式"
            log(
                f"  <{tag}> 主流 {candidate.prefix}+{candidate.total_length}位："
                f"{candidate.count}/{candidate.total_ids} 次，涉及 {candidate.file_count} 个文件；其他：{other}"
            )
        if result.unresolved:
            log(
                "  服务器样本不足，未自动猜测：" + ", ".join(f"<{tag}>" for tag in result.unresolved)
            )
        return result

    def _review_and_apply_server_rules(self, result: ServerIdRuleSyncResult) -> bool:
        """让用户按统计证据逐类确认，并固化一份服务器规则版本。"""
        if not result.candidates:
            QMessageBox.information(self, "服务器 ID 规范扫描完成", "没有足够样本形成可确认的主流 ID 规则。")
            return False
        existing = self.rule_service.load_rules()
        dialog = ServerRuleReviewDialog(self, result, existing)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.task.append_log("服务器 ID 规范扫描完成，但本次未固化任何规则。")
            return False
        selected = dialog.selected_candidates(result)
        if not selected:
            self.task.append_log("已取消全部候选；当前服务器 ID 规则版本保持不变。")
            return False
        rules = dict(existing)
        for candidate in selected:
            rules[candidate.tag] = IdRule(
                tag=candidate.tag,
                prefix=candidate.prefix,
                total_length=candidate.total_length,
                enabled=True,
                verified=True,
                note=(
                    "服务器 G 图形统计后人工确认；主流 "
                    f"{candidate.count}/{candidate.total_ids} 次，涉及 {candidate.file_count} 个文件"
                ),
            )
        version = make_task_timestamp()
        candidate_statistics = {
            tag: {
                "prefix": candidate.prefix,
                "total_length": candidate.total_length,
                "count": candidate.count,
                "total_ids": candidate.total_ids,
                "file_count": candidate.file_count,
                "other_formats": candidate.other_formats,
            }
            for tag, candidate in result.candidates.items()
        }
        self.rule_service.save_server_snapshot(
            rules.values(),
            version=version,
            file_count=result.file_count,
            element_count=result.element_count,
            selected_rule_count=len(selected),
            candidate_statistics=candidate_statistics,
        )
        self._refresh_table()
        self._refresh_server_version_label()
        self.task.append_log(
            f"服务器 ID 规范已固化为版本 {version}；本次确认 {len(selected)} 类。"
        )
        return True

    def _set_server_sync_busy(self, busy: bool) -> None:
        """锁定会影响服务器扫描输入或规则版本的 UI 操作。"""
        controls = (
            self.source,
            self.add_button,
            self.edit_button,
            self.delete_button,
            self.server_sync_button,
            self.scan_button,
            self.task.run_button,
        )
        for control in controls:
            control.setEnabled(not busy)
        self.server_sync_button.setText("后台扫描服务器 ID 规范…" if busy else "扫描服务器全部 ID 规范")

    @staticmethod
    def _server_candidate_statistics(result: ServerIdRuleSyncResult) -> dict[str, dict[str, object]]:
        return {
            tag: {
                "prefix": candidate.prefix,
                "total_length": candidate.total_length,
                "count": candidate.count,
                "total_ids": candidate.total_ids,
                "file_count": candidate.file_count,
                "other_formats": candidate.other_formats,
            }
            for tag, candidate in result.candidates.items()
        }

    def _finish_server_rule_review(self, result: ServerIdRuleSyncResult) -> None:
        """在主线程中处理扫描结果，弹出版本变化和规则固化确认。"""
        self.task.set_progress(95)
        previous = self.rule_service.load_server_snapshot()
        current_statistics = self._server_candidate_statistics(result)
        has_updates = (
            not previous
            or int(previous.get("file_count", -1)) != result.file_count
            or int(previous.get("element_count", -1)) != result.element_count
            or previous.get("candidate_statistics") != current_statistics
        )
        if previous and not has_updates:
            self.task.append_log(
                f"服务器扫描完成：与已固化版本 {previous.get('version', '-')} 的统计结果一致，无需更新。"
            )
            self.task.set_progress(100)
            QMessageBox.information(self, "服务器 ID 规范无变化", "本次全量扫描与当前固化版本一致，无需更新。")
            return
        if previous and has_updates:
            answer = QMessageBox.question(
                self,
                "发现服务器 ID 规范变化",
                "本次全量扫描发现服务器统计结果与当前固化版本存在新增或变化。\n\n"
                "是否打开统计明细，确认需要更新的规则？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.task.append_log("发现服务器 ID 规范变化，但用户选择暂不更新当前版本。")
                self.task.set_progress(100)
                return
        self.task.append_log("[阶段 4/4] 全量统计完成，等待你确认需要固化的规则。")
        applied = self._review_and_apply_server_rules(result)
        self.task.set_progress(100)
        self.task.append_log("[阶段 4/4] 规则确认流程完成。")
        if applied:
            QMessageBox.information(self, "服务器 ID 规范已固化", "已按你的勾选固化新的服务器 ID 规则版本。")

    def _server_sync_error(self, details: str) -> None:
        self.task.append_log("服务器 ID 规范后台扫描失败：" + details)
        message = details.split("\n\n---TRACEBACK---", 1)[0].strip() or details
        QMessageBox.warning(self, "读取服务器 ID 规范失败", message)

    def _server_sync_finished(self) -> None:
        self._server_sync_worker = None
        self._set_server_sync_busy(False)

    def sync_server_rules(self) -> None:
        """后台读取服务器全部 G 文件，统计后由主线程让用户确认是否固化。"""
        if self.source.mode() != InputMode.REMOTE_SSH:
            QMessageBox.information(
                self,
                "请使用服务器 G 文件",
                "请先把输入方式切换为“SSH 远程 G 文件（只读）”，然后扫描服务器全部 ID 规范。",
            )
            return
        if self._server_sync_worker is not None:
            return
        self.task.log_view_clear()
        self.task.set_progress(0)
        self._set_server_sync_busy(True)
        self.task.append_log("服务器 ID 规范后台扫描已启动；界面仍可响应。")

        try:
            self.source.remote._restore_shared_settings()
            cfg = dict(self.source.remote.config())
            remote_directory = str(cfg["remote_directory"])
            snapshot_dir = self.source.remote._processing_snapshot_dir()
            existing_rules = self.rule_service.load_rules()

            def run_server_scan(*, log, progress):
                log(f"[阶段 1/4] 正在读取服务器 G 文件目录：{remote_directory}")
                with ReadOnlySshClient(
                    str(cfg["host"]),
                    int(cfg["port"]),
                    str(cfg["username"]),
                    str(cfg["password"]),
                ) as client:
                    remote_files = client.list_g_files(remote_directory)
                if not remote_files:
                    raise ValueError(f"服务器目录没有找到 G 文件：{remote_directory}")
                progress(5)
                log(f"[阶段 2/4] 已发现 {len(remote_files)} 个服务器 G 文件，开始下载只读快照。")

                last_download_progress = -1

                def download_progress(value: int) -> None:
                    nonlocal last_download_progress
                    mapped = 5 + round(value * 0.65)
                    if mapped != last_download_progress:
                        last_download_progress = mapped
                        progress(mapped)

                def download_log(message: str) -> None:
                    # 全量服务器目录可能包含数千个文件；只把首个、末个和每 100 个文件的
                    # 下载日志送到界面，避免日志控件本身因高频刷新拖慢主线程。
                    if message.startswith("[SSH "):
                        marker = message.split("]", 1)[0]
                        try:
                            current, total = marker[5:].split("/", 1)
                            index = int(current)
                            total_count = int(total)
                        except (ValueError, IndexError):
                            log(message)
                            return
                        if index not in {1, total_count} and index % 100 != 0:
                            return
                    elif message.lstrip().startswith("完成："):
                        return
                    log(message)

                downloaded = download_stable_files(
                    host=str(cfg["host"]),
                    port=int(cfg["port"]),
                    username=str(cfg["username"]),
                    password=str(cfg["password"]),
                    selected_files=remote_files,
                    target_dir=snapshot_dir,
                    log=download_log,
                    progress=download_progress,
                )
                log("[阶段 3/4] 服务器 G 快照下载完成，开始逐文件解析并统计 ID。")
                result = infer_server_id_rules(
                    downloaded,
                    existing_rules,
                    progress=lambda value: progress(70 + round(value * 0.25)),
                )
                progress(95)
                log(
                    f"[服务器 ID 规范] 已读取 {result.file_count} 个 G 文件、"
                    f"{result.element_count} 个直接图元；候选 {len(result.candidates)} 类。"
                )
                for tag, candidate in sorted(result.candidates.items()):
                    other = "; ".join(
                        f"{key}×{count}" for key, count in candidate.other_formats.items()
                    ) or "无其他格式"
                    log(
                        f"  <{tag}> 主流 {candidate.prefix}+{candidate.total_length}位："
                        f"{candidate.count}/{candidate.total_ids} 次，涉及 {candidate.file_count} 个文件；其他：{other}"
                    )
                if result.unresolved:
                    log("  服务器样本不足，未自动猜测：" + ", ".join(f"<{tag}>" for tag in result.unresolved))
                return result

            worker = FunctionWorker(run_server_scan)
            self._server_sync_worker = worker
            worker.signals.log.connect(self.task.append_log)
            worker.signals.progress.connect(self.task.set_progress)
            worker.signals.result.connect(self._finish_server_rule_review)
            worker.signals.error.connect(self._server_sync_error)
            worker.signals.finished.connect(self._server_sync_finished)
            QTimer.singleShot(0, lambda current=worker: QThreadPool.globalInstance().start(current))
        except Exception as exc:
            self._set_server_sync_busy(False)
            QMessageBox.warning(self, "读取服务器 ID 规范失败", str(exc))

    def scan_current(self) -> None:
        if not validate_input_source(self, self.source, display_name="ID 扫描输入"):
            return
        files = discover_g_inputs(self.source.path(), self.source.mode())
        self.task.log_view.clear()
        self.task.set_progress(0)
        # 远程 G 只在用户点击“扫描服务器 ID 规范”时生成候选并进入确认流程；
        # 普通 ID 检查始终使用最近一次已固化的规则版本。
        rules = self.rule_service.load_rules()
        self.task.append_log(
            f"开始扫描当前 G，共 {len(files)} 个文件。"
            + (" 规则来源：服务器 G 图形。" if self.source.mode() == InputMode.REMOTE_SSH else "")
        )
        output_dir = begin_managed_run(self.output_path, "id", "scan")
        candidates: dict[str, IdRule] = {}
        new_messages: list[str] = []
        changed_messages: list[str] = []
        invalid_ids_by_tag: dict[str, list[str]] = {}
        matched: set[str] = set()
        observed_all: set[str] = set()
        uninferable: set[str] = set()
        type_max_ids: dict[str, int] = {}
        progress_dialog = QProgressDialog("正在扫描当前 G 文件并检查 ID 规则……", "取消", 0, 100, self)
        progress_dialog.setWindowTitle("扫描当前 G")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.setValue(0)
        progress_dialog.show()
        QApplication.processEvents()
        try:
            for index, path in enumerate(files, start=1):
                if progress_dialog.wasCanceled():
                    update_run_status(output_dir, "CANCELLED") if "output_dir" in locals() else None
                    self.task.append_log("扫描已取消。")
                    return
                progress_dialog.setLabelText(f"正在扫描：{path.name}  （{index}/{len(files)}）")
                QApplication.processEvents()
                scan = scan_file_against_rules(path, rules)
                observed_all.update(scan.observed)
                matched.update(scan.matched_tags)
                for tag, value in scan.type_max_ids.items():
                    type_max_ids[tag] = max(type_max_ids.get(tag, 0), int(value))
                for item in scan.new_rule_candidates:
                    if item.prefix is not None:
                        if item.total_length is not None and item.total_length > len(item.prefix):
                            candidates[item.tag] = IdRule(
                                item.tag, item.prefix, item.total_length, enabled=True, verified=True,
                                note=f"由 {path.name} 扫描发现；服务器规范未同步时仅作为检查候选",
                            )
                            new_messages.append(
                                f"<{item.tag}>：候选前缀 {item.prefix}、总位数 {item.total_length}（仅作检查候选）；"
                                f"样本 {', '.join(item.sample_ids[:3])}"
                            )
                for item in scan.unknown_uninferable:
                    uninferable.add(item.tag)
                for item in scan.changed_formats:
                    bucket = invalid_ids_by_tag.setdefault(item.tag, [])
                    for value in item.sample_ids:
                        if value not in bucket:
                            bucket.append(value)
                pct = round(index * 100 / max(len(files), 1))
                progress_dialog.setValue(pct)
                self.task.set_progress(pct)
                self.task.append_log(f"[{index}/{len(files)}] 已扫描：{path.name}")
                QApplication.processEvents()
        except Exception as exc:
            update_run_status(output_dir, "FAILED", note=str(exc))
            QMessageBox.warning(self, "扫描失败", str(exc))
            return
        finally:
            progress_dialog.close()
        self._last_scan_candidates = candidates
        covered_tags = observed_all & set(rules)
        missing_tags = observed_all - set(rules)
        parts = [f"模板覆盖检查：当前 G 共发现 {len(observed_all)} 类带 ID 元素；模板已覆盖 {len(covered_tags)} 类，未覆盖 {len(missing_tags)} 类。"]
        if missing_tags:
            parts.append("未覆盖类型：" + ", ".join(f"<{tag}>" for tag in sorted(missing_tags)))
        if type_max_ids:
            preview = []
            for tag in sorted(type_max_ids):
                current = type_max_ids[tag]
                preview.append(f"<{tag}> 当前最大 {current}，下一个 {current + 1}")
            parts.append("同类型 ID 递增预览：\n" + "\n".join(preview[:16]))
        if new_messages:
            parts.append("发现新元素类型：\n" + "\n".join(new_messages))
        if uninferable:
            parts.append("样本不足、不能自动推断：" + ", ".join(sorted(uninferable)) + "。请人工新增规则。")
        if invalid_ids_by_tag:
            for tag in sorted(invalid_ids_by_tag):
                rule = rules.get(tag)
                values = invalid_ids_by_tag[tag]
                changed_messages.append(
                    f"<{tag}>：模板要求前缀 {rule.prefix}、总位数 {rule.total_length}；"
                    f"不符合模板的完整 ID（{len(values)} 个）：{', '.join(values)}"
                )
            parts.append(
                "发现已有类型 ID 不符合模板：\n"
                + "\n".join(changed_messages)
                + "\n以上数字均为 XML 中实际存在的完整 ID，不是前缀。模板不会自动修改。"
            )
        scan_text = "\n".join(parts)
        self.task.append_log("\nID 模板扫描结果：")
        self.task.append_log(scan_text)

        # “扫描当前 G（只检查 ID）”同样生成独立 CSV/HTML 报告。
        # 报告只记录实际发现的问题；无问题文件记录为“正常”。
        report_rows: list[dict[str, str]] = []
        for path in files:
            try:
                scan = scan_file_against_rules(path, rules)
                file_rows = 0
                for item in scan.new_rule_candidates:
                    detail = (
                        f"尚未加入模板；候选前缀 {item.prefix}、总位数 {item.total_length}（请先读取服务器规范）"
                        if item.prefix is not None and item.total_length is not None
                        else "尚未加入模板"
                    )
                    for value in item.sample_ids or [""]:
                        report_rows.append({"File": path.name, "Category": "未配置模板", "ElementType": item.tag, "OriginalID": value, "NewID": "", "Detail": detail})
                        file_rows += 1
                for item in scan.unknown_uninferable:
                    for value in item.sample_ids or [""]:
                        report_rows.append({"File": path.name, "Category": "未配置模板", "ElementType": item.tag, "OriginalID": value, "NewID": "", "Detail": "样本不足，不能可靠推断 ID 模板"})
                        file_rows += 1
                for item in scan.changed_formats:
                    rule = rules.get(item.tag)
                    detail = f"模板要求前缀 {rule.prefix}、总位数 {rule.total_length}" if rule else "不符合当前模板"
                    for value in item.sample_ids:
                        report_rows.append({"File": path.name, "Category": "格式不符", "ElementType": item.tag, "OriginalID": value, "NewID": "", "Detail": detail})
                        file_rows += 1
                inspection = inspect_tree_ids(ET.parse(path), path)
                for group in inspection.duplicate_groups:
                    report_rows.append({"File": path.name, "Category": "重复 ID", "ElementType": ", ".join(group.tags), "OriginalID": group.value, "NewID": "", "Detail": f"出现 {group.count} 次"})
                    file_rows += 1
                if file_rows == 0:
                    report_rows.append({"File": path.name, "Category": "正常", "ElementType": "", "OriginalID": "", "NewID": "", "Detail": "未发现模板格式异常或重复 ID"})
            except Exception as exc:
                report_rows.append({"File": path.name, "Category": "处理失败", "ElementType": "", "OriginalID": "", "NewID": "", "Detail": str(exc)})
        timestamp = make_task_timestamp()
        csv_path, html_path = _write_id_reports(output_dir, report_rows, timestamp, report_kind="scan")
        self.last_html_report = html_path
        self.report_button.setEnabled(True)
        self.task._output_dir = output_dir
        self.task.open_button.setEnabled(True)
        self.task.append_log(f"CSV 报告：{csv_path}")
        self.task.append_log(f"HTML 报告：{html_path}")
        self.task.set_progress(100)
        update_run_status(output_dir, "SUCCESS")
        QMessageBox.information(
            self,
            "扫描完成",
            "ID 扫描完成，扫描报告已生成并覆盖上一份扫描报告。\n可点击“打开报告”查看 HTML 报告。",
        )

        if candidates:
            self.task.append_log(
                "当前检查文件发现未配置类型；规则不会从业务文件自动加入，"
                "请先读取服务器 G 规范，或使用“新增规则”手动维护。"
            )

    def _confirm_detected_rules(self) -> None:
        if not self._last_scan_candidates:
            return
        added: list[str] = []
        skipped: list[str] = []
        for tag in sorted(list(self._last_scan_candidates)):
            candidate = self._last_scan_candidates[tag]
            dialog = RuleDialog(self, candidate)
            dialog.setWindowTitle(f"确认扫描发现的 ID 规则：{tag}")
            if dialog.exec() != QDialog.DialogCode.Accepted:
                skipped.append(tag)
                continue
            try:
                confirmed = dialog.value()
            except ValueError as exc:
                QMessageBox.warning(self, "规则无效", str(exc))
                skipped.append(tag)
                continue
            existing = self.rule_service.load_rules()
            if confirmed.tag in existing and confirmed.tag != tag:
                QMessageBox.warning(self, "规则已存在", f"<{confirmed.tag}> 已存在，本次未加入。")
                skipped.append(tag)
                continue
            confirmed = IdRule(
                tag=confirmed.tag, prefix=confirmed.prefix, total_length=confirmed.total_length,
                enabled=True, verified=True,
                note=confirmed.note or "由当前 G 扫描自动识别参数，经用户确认",
            )
            self.rule_service.upsert(confirmed)
            added.append(confirmed.tag)
            self._last_scan_candidates.pop(tag, None)
        self._refresh_table()
        pieces = []
        if added:
            pieces.append("已确认加入：" + ", ".join(f"<{tag}>" for tag in added))
        if skipped:
            pieces.append("暂未加入：" + ", ".join(f"<{tag}>" for tag in skipped))
        if pieces:
            self.task.append_log("；".join(pieces) + "。")

    def add_detected_rules(self) -> None:
        self._confirm_detected_rules()

    def _task_result(self, result) -> None:
        path_text = str(result.statistics.get("html_report_path", "")) if getattr(result, "statistics", None) else ""
        if path_text:
            self.last_html_report = Path(path_text)
            self.report_button.setEnabled(self.last_html_report.exists())
            QMessageBox.information(
                self,
                "ID 修复完成",
                "ID 检查与强制修复已完成，修复报告已生成并覆盖上一份修复报告。\n可点击“打开报告”查看 HTML 报告。",
            )

    def open_last_report(self) -> None:
        if not self.last_html_report or not self.last_html_report.exists():
            QMessageBox.information(self, "暂无报告", "请先执行一次 ID 检查或修复。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_html_report.resolve())))

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()

    def _same_path(self, left: Path, right: Path) -> bool:
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(str(right.resolve(strict=False)))

    def run(self) -> None:
        if not validate_input_source(self, self.source, display_name="ID 处理输入"):
            return
        action = IdAction.REPAIR
        if not validate_existing_directory(self, self.output_path.path(), "ID 检查与修复输出目录"):
            return
        self.source.persist_current()
        output_dir = begin_managed_run(self.output_path, "id", "repair")
        timestamp = make_task_timestamp()
        # 每次修复都进入独立运行目录，处理后的 G 文件严格保持源文件名。
        conflict_action = BasicOutputConflictAction.OVERWRITE
        settings = IdSettings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=output_dir,
            action=action,
            output_conflict_action=conflict_action,
            task_timestamp=timestamp,
        )
        self.task.start(lambda log, progress: process_ids(settings, log, progress), output_dir)
