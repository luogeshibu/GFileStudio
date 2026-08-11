from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from g_file_studio.engines.id_rule_engine import scan_file_against_rules
from g_file_studio.models import BasicOutputConflictAction, IdAction, IdSettings
from g_file_studio.processors.common import discover_g_inputs
from g_file_studio.processors.id_processor import process_ids
from g_file_studio.services.id_rule_service import IdRule, IdRuleService
from g_file_studio.services.output_naming import make_task_timestamp
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, PathRow, TaskPanel


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
        hint = QLabel("示例：ConnectLine 使用前缀 34、总位数 8，因此 34000053、34001838 合法，而 140、340123456 不合法。新增 ID 按同类型当前最大完整 ID + 1，并且结果必须继续满足前缀和总位数。只管理 id，不处理 Alias。")
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
        help_title, help_html = APP_HELP["id_rules"]
        super().__init__(
            "ID 检查与修复",
            "扫描 G 文件 ID、维护规则模板，并可强制把不符合模板或重复的 ID 修复为模板格式。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(InfoBanner(
            "本模块只管理元素 id，不读取或修改 Alias。打开新 G 时会对照模板检查：发现新的元素类型会提醒是否加入模板；"
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
        intro = QLabel("规则格式：XML 元素类型 + 固定数字起始前缀 + 固定 ID 总位数。新增 ID 按同类型当前最大完整 ID + 1，并始终校验前缀和位数。模板为人工确认后的唯一分配依据，不自动永久修改。")
        intro.setWordWrap(True)
        intro.setObjectName("mutedText")
        template_layout.addWidget(intro)

        buttons = QHBoxLayout()
        self.scan_button = QPushButton("扫描当前 G")
        self.add_button = QPushButton("新增规则")
        self.edit_button = QPushButton("编辑规则")
        self.delete_button = QPushButton("删除规则")
        self.add_detected_button = QPushButton("加入扫描发现的规则")
        self.add_detected_button.setEnabled(False)
        for button in (self.scan_button, self.add_button, self.edit_button, self.delete_button, self.add_detected_button):
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
        self.scan_summary = QLabel("尚未扫描 G 文件。")
        self.scan_summary.setWordWrap(True)
        self.scan_summary.setObjectName("mutedText")
        template_layout.addWidget(self.scan_summary)
        self.layout.addWidget(template_box)

        action_box = QGroupBox("ID 操作")
        action_layout = QHBoxLayout(action_box)
        self.check_only = QRadioButton("只检查 ID")
        self.repair = QRadioButton("检查并强制按模板修复 ID")
        self.check_only.setChecked(True)
        action_layout.addWidget(self.check_only)
        action_layout.addWidget(self.repair)
        action_layout.addStretch(1)
        self.layout.addWidget(action_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始 ID 处理")
        self.layout.addWidget(self.task, 1)

        self.scan_button.clicked.connect(self.scan_current)
        self.add_button.clicked.connect(self.add_rule)
        self.edit_button.clicked.connect(self.edit_rule)
        self.delete_button.clicked.connect(self.delete_rule)
        self.add_detected_button.clicked.connect(self.add_detected_rules)
        self.task.run_button.clicked.connect(self.run)
        self._refresh_table()

    def _refresh_table(self) -> None:
        rules = self.rule_service.load_rules()
        self.table.setRowCount(0)
        for rule in sorted(rules.values(), key=lambda item: item.tag.lower()):
            row = self.table.rowCount()
            self.table.insertRow(row)
            example = rule.build(1)
            values = [
                "✓ 已确认" if rule.verified and rule.enabled else "○ 未启用",
                rule.tag,
                rule.prefix,
                str(rule.total_length),
                example,
                "前缀 + 总位数；同类型最大 ID + 1",
                rule.note,
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 1:
                    item.setData(Qt.ItemDataRole.UserRole, rule.tag)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()

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
            QMessageBox.information(self, "请选择规则", "请先选择要删除的规则。")
            return
        if QMessageBox.question(self, "删除规则", f"确认删除 <{tag}> 的 ID 规则？删除后立即生效，后续扫描不会自动恢复该规则。") != QMessageBox.StandardButton.Yes:
            return
        self.rule_service.remove(tag)
        self._last_scan_candidates.pop(tag, None)
        self._refresh_table()
        self.scan_summary.setText(f"已立即删除 <{tag}> 的 ID 规则。再次扫描含该类型的 G 文件时，会作为未覆盖类型重新提醒你是否添加。")

    def scan_current(self) -> None:
        if not validate_input_source(self, self.source, display_name="ID 扫描输入"):
            return
        files = discover_g_inputs(self.source.path(), self.source.mode())
        rules = self.rule_service.load_rules()
        candidates: dict[str, IdRule] = {}
        new_messages: list[str] = []
        changed_messages: list[str] = []
        matched: set[str] = set()
        observed_all: set[str] = set()
        uninferable: set[str] = set()
        type_max_ids: dict[str, int] = {}
        try:
            for path in files:
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
                    rule = rules.get(item.tag)
                    changed_messages.append(
                        f"<{item.tag}>：模板要求前缀 {rule.prefix}、总位数 {rule.total_length}；"
                        f"发现 {', '.join(item.sample_ids[:4])}"
                    )
        except Exception as exc:
            QMessageBox.warning(self, "扫描失败", str(exc))
            return
        self._last_scan_candidates = candidates
        self.add_detected_button.setEnabled(bool(candidates))
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
        if changed_messages:
            parts.append("发现已有类型 ID 格式变化：\n" + "\n".join(changed_messages) + "\n请人工确认并更新模板，程序不会自动改模板。")
        self.scan_summary.setText("\n".join(parts))
        if new_messages or changed_messages or uninferable:
            QMessageBox.warning(self, "ID 模板扫描有发现", self.scan_summary.text())
        else:
            QMessageBox.information(self, "ID 模板扫描完成", self.scan_summary.text())

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
        self.add_detected_button.setEnabled(bool(self._last_scan_candidates))
        self._refresh_table()
        pieces = []
        if added:
            pieces.append("已确认加入：" + ", ".join(f"<{tag}>" for tag in added))
        if skipped:
            pieces.append("暂未加入：" + ", ".join(f"<{tag}>" for tag in skipped))
        if pieces:
            self.scan_summary.setText("；".join(pieces) + "。")

    def add_detected_rules(self) -> None:
        self._confirm_detected_rules()

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()

    def _same_path(self, left: Path, right: Path) -> bool:
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(str(right.resolve(strict=False)))

    def run(self) -> None:
        if not validate_input_source(self, self.source, display_name="ID 处理输入"):
            return
        action = IdAction.REPAIR if self.repair.isChecked() else IdAction.CHECK
        output_dir = self.output_path.path()
        if not validate_existing_directory(self, output_dir, "ID 检查与修复输出目录"):
            return
        self.source.persist_current()
        self.output_path.persist_valid_path()
        timestamp = ""
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
                timestamp = make_task_timestamp()
        settings = IdSettings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=output_dir,
            action=action,
            output_conflict_action=conflict_action,
            task_timestamp=timestamp,
        )
        self.task.start(lambda log, progress: process_ids(settings, log, progress), output_dir)
