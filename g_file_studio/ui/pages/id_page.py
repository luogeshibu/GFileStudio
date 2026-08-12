from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
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
from g_file_studio.engines.id_rule_engine import scan_file_against_rules
from g_file_studio.models import BasicOutputConflictAction, IdAction, IdSettings
from g_file_studio.processors.common import discover_g_inputs
from g_file_studio.processors.id_processor import _write_id_reports, process_ids
from g_file_studio.services.id_rule_service import IdRule, IdRuleService
from g_file_studio.services.output_naming import make_task_timestamp
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, PathRow, TaskPanel
from g_file_studio.ui.widgets.help_widgets import set_secondary


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


class IdPage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.rule_service = IdRuleService()
        self._last_scan_candidates: dict[str, IdRule] = {}
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
            "打开新 G 时会对照模板检查：发现新的元素类型会提醒是否加入模板；"
            "已知类型只要固定前缀或总位数不符合模板就会告警。执行修复时会强制把格式不符和重复 ID 都更新为模板格式；同类型按当前最大合法完整 ID + 1。未知或未确认类型绝不擅自生成新 ID。"
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
        output_row = QHBoxLayout()
        output_label = QLabel("输出目录")
        output_label.setMinimumWidth(72)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_path, 1)
        io_layout.addLayout(output_row)
        self.layout.addWidget(io_box)

        template_box = QGroupBox("ID 规则模板")
        template_layout = QVBoxLayout(template_box)
        intro = QLabel("规则格式：XML 元素类型 + 固定数字起始前缀 + 固定 ID 总位数。所有模块只允许使用这里已启用、已确认的规则；新增 ID 按同类型当前最大完整 ID + 1，并始终校验前缀和位数。")
        intro.setWordWrap(True)
        intro.setObjectName("mutedText")
        template_layout.addWidget(intro)

        self.global_strict = QCheckBox("启用全局 ID 模板强制约束")
        self.global_strict.setChecked(self.user_settings.get_bool("id_rules/global_strict", True))
        self.global_strict.setToolTip(
            "默认开启：处理输出时会把已有不符合模板的 ID 也强制修复。关闭后不会强制改写已有格式不符 ID；"
            "但所有模块新生成的 ID 仍必须严格使用已确认模板。"
        )
        self.global_strict.toggled.connect(self._global_strict_toggled)
        template_layout.addWidget(self.global_strict)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("新增规则")
        self.edit_button = QPushButton("编辑规则")
        self.delete_button = QPushButton("删除规则")
        for button in (self.add_button, self.edit_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        template_layout.addLayout(buttons)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["状态", "元素类型", "ID 起始前缀", "总位数", "合法示例", "当前规则", "备注"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        template_layout.addWidget(self.table)
        self.layout.addWidget(template_box)

        self.task = TaskPanel()
        self.scan_button = QPushButton("扫描当前G文件（只检查ID）")
        self.scan_button.setToolTip("扫描完成后会生成/覆盖 ID 扫描 CSV/HTML 报告，可点击“打开报告”查看；发现新元素类型仍会逐条询问是否加入模板。")
        self.task.run_button.setText("检查并强制修复 ID")
        self.task.run_button.setToolTip("执行后会按已确认模板修复 ID，并生成/覆盖 ID 修复 CSV/HTML 报告，可点击“打开报告”查看。")
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
        self.task.run_button.clicked.connect(self.run)
        self.report_button.clicked.connect(self.open_last_report)
        self.task.resultReceived.connect(self._task_result)
        self._refresh_table()

    def _refresh_table(self) -> None:
        rules = self.rule_service.load_rules()
        self.table.setRowCount(0)
        for rule in sorted(rules.values(), key=lambda item: item.tag.lower()):
            row = self.table.rowCount()
            self.table.insertRow(row)
            example = rule.build(1)
            values = [
                "✓ 已确认",
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

    def _global_strict_toggled(self, checked: bool) -> None:
        if not checked:
            answer = QMessageBox.warning(
                self,
                "关闭全局 ID 强制约束",
                "关闭后，后续处理不会再强制改写 G 文件中已有但不符合模板的 ID。\n\n"
                "注意：所有模块新生成的 ID 仍会严格按照 ID 规则模板生成。\n\n"
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

    def scan_current(self) -> None:
        if not validate_input_source(self, self.source, display_name="ID 扫描输入"):
            return
        files = discover_g_inputs(self.source.path(), self.source.mode())
        rules = self.rule_service.load_rules()
        self.task.log_view.clear()
        self.task.progress.setValue(0)
        self.task.append_log(f"开始扫描当前 G，共 {len(files)} 个文件。")
        candidates: dict[str, IdRule] = {}
        new_messages: list[str] = []
        changed_messages: list[str] = []
        invalid_ids_by_tag: dict[str, list[str]] = {}
        matched: set[str] = set()
        observed_all: set[str] = set()
        uninferable: set[str] = set()
        type_max_ids: dict[str, int] = {}
        progress_dialog = QProgressDialog("正在扫描当前 G 文件并检查 ID 规则……", "取消", 0, max(len(files), 1), self)
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
                                note=f"由 {path.name} 扫描发现，待人工确认",
                            )
                            new_messages.append(
                                f"<{item.tag}>：候选前缀 {item.prefix}、总位数 {item.total_length}（必须人工确认）；"
                                f"样本 {', '.join(item.sample_ids[:3])}"
                            )
                for item in scan.unknown_uninferable:
                    uninferable.add(item.tag)
                for item in scan.changed_formats:
                    bucket = invalid_ids_by_tag.setdefault(item.tag, [])
                    for value in item.sample_ids:
                        if value not in bucket:
                            bucket.append(value)
                progress_dialog.setValue(index)
                self.task.progress.setValue(round(index * 100 / max(len(files), 1)))
                self.task.append_log(f"[{index}/{len(files)}] 已扫描：{path.name}")
                QApplication.processEvents()
        except Exception as exc:
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
                        f"尚未加入模板；候选前缀 {item.prefix}、总位数 {item.total_length}（需人工确认）"
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
        output_dir = self.output_path.path()
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = make_task_timestamp()
        csv_path, html_path = _write_id_reports(output_dir, report_rows, timestamp, report_kind="scan")
        self.last_html_report = html_path
        self.report_button.setEnabled(True)
        self.task._output_dir = output_dir
        self.task.open_button.setEnabled(True)
        self.task.append_log(f"CSV 报告：{csv_path}")
        self.task.append_log(f"HTML 报告：{html_path}")
        self.task.progress.setValue(100)
        QMessageBox.information(
            self,
            "扫描完成",
            "ID 扫描完成，扫描报告已生成并覆盖上一份扫描报告。\n可点击“打开报告”查看 HTML 报告。",
        )

        # 发现可推断的新类型时，主动询问是否逐条打开“新增 ID 规则”窗口。
        # 前缀和总位数由扫描结果预填，最终必须由用户逐条确认。
        if candidates:
            answer = QMessageBox.question(
                self,
                "发现未覆盖的 ID 类型",
                f"当前 G 中有 {len(candidates)} 个元素类型尚未被 ID 模板覆盖，但已能从现有 ID 自动识别候选前缀和总位数。\n\n是否现在逐个确认并加入模板？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._confirm_detected_rules()

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
        output_dir = self.output_path.path()
        if not validate_existing_directory(self, output_dir, "ID 检查与修复输出目录"):
            return
        self.source.persist_current()
        self.output_path.persist_valid_path()
        timestamp = make_task_timestamp()
        conflict_action = BasicOutputConflictAction.OVERWRITE
        if action == IdAction.REPAIR:
            files = discover_g_inputs(self.source.path(), self.source.mode())
            conflicts = [p for p in files if (output_dir / p.name).exists() or self._same_path(p, output_dir / p.name)]
            if conflicts:
                answer = QMessageBox.question(
                    self,
                    "输出文件冲突",
                    f"检测到 {len(conflicts)} 个目标文件已存在或与源文件相同。是否自动添加时间戳后输出？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                conflict_action = BasicOutputConflictAction.TIMESTAMP
        settings = IdSettings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=output_dir,
            action=action,
            output_conflict_action=conflict_action,
            task_timestamp=timestamp,
        )
        self.task.start(lambda log, progress: process_ids(settings, log, progress), output_dir)
