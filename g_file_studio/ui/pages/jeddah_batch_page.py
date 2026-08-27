from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from g_file_studio.jeddah import JeddahBatchSettings, process_jeddah_batch
from g_file_studio.services.id_rule_service import IdRuleService
from g_file_studio.services.site_profile_service import SiteProfileService
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.run_history import begin_managed_run, configure_managed_output
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_input_source
from g_file_studio.ui.widgets import (
    InfoBanner,
    InputSourceSelector,
    IntegerInput,
    PathRow,
    TaskPanel,
    TemplateSelector,
    WheelSafeComboBox,
)


class JeddahBatchPage(BasePage):
    """Jeddah-only one-click feeder cleanup page.

    The page does not replace or alter any existing module.  It only invokes the
    existing processors/engines in a fixed Jeddah workflow and owns its site-specific
    parameters under the ``jeddah_batch`` settings namespace.
    """

    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["jeddah_batch"]
        super().__init__(
            "吉达馈线批处理",
            "面向吉达现场的单馈线图一键标准化：批量输入多个 G 文件，逐张完成固定处理并输出最终单馈线图。",
            help_title,
            help_html,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "本模块是 Jeddah 专用批处理入口，不修改现有异常元素、RMU、基础处理或 ID 模块的业务逻辑。"
                "程序按固定顺序调用已有处理能力；原始输入文件不会覆盖，最终结果写入本次 workspace 运行目录。"
            )
        )

        io_box = QGroupBox("输入与输出")
        io_layout = QVBoxLayout(io_box)
        io_layout.setContentsMargins(12, 18, 12, 12)
        io_layout.setSpacing(10)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            directory_tooltip="选择包含需要执行吉达批处理的单馈线 G 文件目录。",
            file_tooltip="也可只选择一张单馈线 G 文件进行吉达标准处理。",
            settings_prefix="jeddah_batch",
            settings_service=self.user_settings,
        )
        io_layout.addWidget(self.source)

        self.output_path = PathRow(
            directory=True,
            dialog_title="吉达批处理输出目录",
            recent_directory_key="recent_paths/jeddah_batch/output_directory",
            persistent_path_key="jeddah_batch/output_directory",
            default_path=default_workspace() / "runs" / "jeddah-batch",
            location_name="吉达批处理输出目录",
            settings_service=self.user_settings,
        )
        configure_managed_output(self.output_path, "jeddah-batch")
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("输出目录（workspace，只读）"))
        output_row.addWidget(self.output_path, 1)
        io_layout.addLayout(output_row)
        self.layout.addWidget(io_box)

        pipeline_box = QGroupBox("Jeddah 固定处理流程")
        pipeline_layout = QVBoxLayout(pipeline_box)
        pipeline_layout.setContentsMargins(16, 18, 16, 14)
        pipeline_layout.setSpacing(8)
        for text in (
            "✓ 1. 彻底取消图形组合（删除全部 <Merge>，并将 RMU 外框置底）",
            "✓ 2. 删除异常小尺寸元素",
            "✓ 3. 已识别 RMU 名称统一改白、字号 50，并在环网柜上边框上方 10 距离处水平居中",
            "✓ 4. SMART 环网柜外框统一刷成红色",
            "✓ 5. SMART 图元检查：凡柜内已有 SMART，Y1/Y2/Y3 的 LBS 与 Q1 Circuit Breaker 必须使用 SMART devref",
            "✓ 6. SMR 环网柜外框统一刷成红色",
            "✓ 7. SMR 条件转换 SMART：已有 SMART 时删除外部 SMR并保持原 SMART；没有 SMART 时生成顶部居中 SMART（字号 20）；外框强制红色",
            "✓ 8. SMR 转换后再次执行 SMART 图元检查，确保 LBS / Circuit Breaker devref 正确",
            "✓ 9. 使用“图元标准检查”中的当前 ACTIVE 标准执行 SMART/NORMAL 图元类型/变体纠正：LBS、Circuit Breaker、<ZhaiWaiJieDiDaoZha> 接地刀闸按 Profile 纠正错误变体，并保持电气连接锚点位置不变",
            "✓ 10. 删除 RMU 红色状态点（channel_status），沿用现有状态点识别/归属规则",
            "✓ 11. 删除带 Bus 的环网柜矩形框，并将对应标题移动到母线上方",
            "✓ 12. 将馈线名称移动到母线上方",
            "✓ 13. 将所有 FeedLine 馈线统一改成实线（ls=1）",
            "✓ 14. 删除精确 H.T 文字标识",
            "✓ 15. 检查所有已识别配网 RMU；同一柜内存在多个 SMART 时仅保留原有第一个，删除重复项",
            "✓ 16. 仅当 2000.00 与 UPDATED_MEASURMENT 两个 Text 同行且相邻时成对删除",
            "✓ 17. 使用全局 ID 模板执行 ID 检查与修复",
            "✓ 18. 调整主体图形四边距（默认 500）",
            "✓ 19. 添加图框",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            pipeline_layout.addWidget(label)
        note = QLabel("以上步骤为吉达固定流程，本页不复制或重写现有模块算法。")
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        pipeline_layout.addWidget(note)
        self.layout.addWidget(pipeline_box)

        settings_box = QGroupBox("吉达参数")
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setContentsMargins(16, 18, 16, 14)
        settings_layout.setSpacing(10)

        profile_form = QFormLayout()
        self.rmu_profile = WheelSafeComboBox()
        self.rmu_profile.setMinimumContentsLength(50)
        saved_profile = self.user_settings.get_value("jeddah_batch/rmu_profile_name", "")
        profiles = SiteProfileService().load_profiles()
        for name, profile in sorted(profiles.items(), key=lambda row: row[0].casefold()):
            site_key = profile.site_name.strip().upper()
            if not (site_key.startswith("JED") or "JEDDAH" in site_key):
                continue
            label = (
                f"{profile.site_name} / {profile.profile_name} / V{profile.profile_version} ACTIVE · "
                f"SMART/NORMAL LBS+Q+接地"
            )
            self.rmu_profile.addItem(label, name)
        if saved_profile:
            index = self.rmu_profile.findData(saved_profile)
            if index >= 0:
                self.rmu_profile.setCurrentIndex(index)
        self.rmu_profile.setToolTip(
            "吉达批处理使用“图元标准检查”中的此 ACTIVE 标准执行 SMART/NORMAL 图元类型/变体一致性纠正；这属于标准替换/纠正，不属于图元版本升级。"
        )
        profile_form.addRow("吉达 RMU 图元 Profile", self.rmu_profile)
        settings_layout.addLayout(profile_form)

        threshold_form = QFormLayout()
        self.threshold = IntegerInput(
            value=self.user_settings.get_int("jeddah_batch/small_element_threshold", 10),
            minimum=1,
            maximum=100000,
        )
        self.threshold.setToolTip("当目标元素的 w 和 h 同时小于该值时，吉达批处理自动删除该异常小尺寸元素。")
        threshold_form.addRow("异常小尺寸阈值", self.threshold)
        settings_layout.addLayout(threshold_form)

        position_row = QHBoxLayout()
        position_row.addWidget(QLabel("RMU 柜名可能位置："))
        self.name_top = QCheckBox("上方")
        self.name_bottom = QCheckBox("下方")
        self.name_left = QCheckBox("左侧")
        self.name_right = QCheckBox("右侧")
        self.name_top.setChecked(self.user_settings.get_bool("jeddah_batch/rmu_name_top", True))
        self.name_bottom.setChecked(self.user_settings.get_bool("jeddah_batch/rmu_name_bottom", False))
        self.name_left.setChecked(self.user_settings.get_bool("jeddah_batch/rmu_name_left", False))
        self.name_right.setChecked(self.user_settings.get_bool("jeddah_batch/rmu_name_right", False))
        for item in (self.name_top, self.name_bottom, self.name_left, self.name_right):
            item.setProperty("optionChoice", True)
            position_row.addWidget(item)
        position_row.addStretch(1)
        settings_layout.addLayout(position_row)

        exclusion_row = QHBoxLayout()
        exclusion_row.addWidget(QLabel("RMU 柜名排除字符串："))
        self.name_exclusions = QLineEdit(
            self.user_settings.get_value("jeddah_batch/rmu_name_exclusions", "NOP, DAS/OK, SFI")
        )
        self.name_exclusions.setPlaceholderText("例如：NOP, DAS/OK, SFI")
        self.name_exclusions.setToolTip(
            "使用逗号、分号或换行分隔；按完整字符串匹配并忽略大小写，不使用包含匹配。"
        )
        exclusion_row.addWidget(self.name_exclusions, 1)
        settings_layout.addLayout(exclusion_row)

        color_note = QLabel(
            "吉达固定样式：SMART/SMR 外框 = 红色 #FF0000；只要 SMART Text 的中心位于 RMU 框内，就检查并校正 Y1/Y2/Y3 的 Load_Breaker_Switch 与 Q1 Circuit_Breaker 的 CBreakerDis devref（兼容 Circuit_Breaker_NO-SMART 与 Circuit_Breaker_NON-SMART 两种源图元）；若 SMR 柜内已有 SMART，只删除外部 SMR并保留原 SMART；若柜内没有 SMART，则生成顶部居中 SMART（字号 20）；SMR 处理后再次执行 SMART 图元复检；已识别 RMU 柜名 Text = 白色 #FFFFFF、字号 50，并与环网柜上边框保持 10 距离且水平居中；RMU channel_status 红色状态点直接删除；所有 FeedLine 馈线 = 实线 ls=1；精确 H.T Text = 删除；所有已识别配网 RMU 都检查重复 SMART，同柜多个时保留 XML 中原有第一个并删除后续重复；2000.00 与 UPDATED_MEASURMENT 只有在同行且相邻（水平间距不超过 10）时才成对删除。"
        )
        color_note.setObjectName("mutedText")
        color_note.setWordWrap(True)
        settings_layout.addWidget(color_note)
        self.layout.addWidget(settings_box)

        margin_box = QGroupBox("吉达图形边距")
        margin_form = QFormLayout(margin_box)
        margin_form.setHorizontalSpacing(16)
        margin_form.setVerticalSpacing(10)
        self.margin_left = IntegerInput(
            value=self.user_settings.get_int("jeddah_batch/margin_left", 500),
            minimum=0,
            maximum=100000,
        )
        self.margin_top = IntegerInput(
            value=self.user_settings.get_int("jeddah_batch/margin_top", 500),
            minimum=0,
            maximum=100000,
        )
        self.margin_right = IntegerInput(
            value=self.user_settings.get_int("jeddah_batch/margin_right", 500),
            minimum=0,
            maximum=100000,
        )
        self.margin_bottom = IntegerInput(
            value=self.user_settings.get_int("jeddah_batch/margin_bottom", 500),
            minimum=0,
            maximum=100000,
        )
        margin_form.addRow("图形左边距", self.margin_left)
        margin_form.addRow("图形上边距", self.margin_top)
        margin_form.addRow("图形右边距", self.margin_right)
        margin_form.addRow("图形下边距", self.margin_bottom)
        self.layout.addWidget(margin_box)

        frame_box = QGroupBox("吉达图框")
        frame_layout = QVBoxLayout(frame_box)
        frame_layout.setContentsMargins(12, 18, 12, 12)
        frame_layout.setSpacing(9)
        frame_note = QLabel(
            "图形边距调整完成后，直接调用现有“图框添加”处理能力。默认使用程序内置模板；"
            "内置模板标题留空时自动使用输入文件名。"
        )
        frame_note.setObjectName("mutedText")
        frame_note.setWordWrap(True)
        frame_layout.addWidget(frame_note)
        self.template_selector = TemplateSelector(
            settings_prefix="jeddah_batch/frame",
            settings_service=self.user_settings,
        )
        frame_layout.addWidget(self.template_selector)
        self.layout.addWidget(frame_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始吉达批处理")
        self.task.run_button.setToolTip("按上方固定 Jeddah 流程批量处理所选单馈线 G 文件。")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    def _persist(self) -> None:
        self.source.persist_all_text()
        self.user_settings.set_value("jeddah_batch/rmu_profile_name", str(self.rmu_profile.currentData() or ""))
        self.user_settings.set_value("jeddah_batch/small_element_threshold", self.threshold.value())
        self.user_settings.set_value("jeddah_batch/rmu_name_top", self.name_top.isChecked())
        self.user_settings.set_value("jeddah_batch/rmu_name_bottom", self.name_bottom.isChecked())
        self.user_settings.set_value("jeddah_batch/rmu_name_left", self.name_left.isChecked())
        self.user_settings.set_value("jeddah_batch/rmu_name_right", self.name_right.isChecked())
        self.user_settings.set_value("jeddah_batch/rmu_name_exclusions", self.name_exclusions.text().strip())
        self.user_settings.set_value("jeddah_batch/margin_left", self.margin_left.value())
        self.user_settings.set_value("jeddah_batch/margin_top", self.margin_top.value())
        self.user_settings.set_value("jeddah_batch/margin_right", self.margin_right.value())
        self.user_settings.set_value("jeddah_batch/margin_bottom", self.margin_bottom.value())
        self.template_selector.persist_current()

    def run(self) -> None:
        if not validate_input_source(
            self,
            self.source,
            display_name="吉达批处理输入",
            log=self.task.append_log,
        ):
            return
        if not any((self.name_top.isChecked(), self.name_bottom.isChecked(), self.name_left.isChecked(), self.name_right.isChecked())):
            QMessageBox.warning(self, "吉达 RMU 柜名设置", "RMU 柜名位置至少选择上方、下方、左侧或右侧中的一个。")
            return
        if not self.template_selector.validate_selection():
            return
        if not IdRuleService().load_rules():
            QMessageBox.warning(
                self,
                "全局 ID 模板未配置",
                "吉达批处理的 ID 处理阶段必须使用全局 ID 模板。请先在“ID 检查与修复”模块中确认 ID 规则。",
            )
            return
        profile_name = str(self.rmu_profile.currentData() or "").strip()
        if not profile_name:
            QMessageBox.warning(
                self,
                "吉达 RMU 图元 Profile 未选择",
                "吉达批处理现在会全面校验 SMART/NORMAL 的 LBS、Circuit Breaker 与接地刀闸。请先在“图元标准检查”中扫描标准 G 文件并保存 Jeddah ACTIVE 标准，然后在此选择。",
            )
            return
        active_profile = SiteProfileService().load_profiles().get(profile_name)
        if active_profile is None:
            QMessageBox.warning(self, "Profile 不存在", f"未找到当前 ACTIVE Profile：{profile_name}")
            return
        if not active_profile.smart_ready or not active_profile.normal_ready or not active_profile.ground_ready:
            QMessageBox.warning(
                self,
                "Profile 学习不完整",
                f"{active_profile.profile_name} V{active_profile.profile_version} 尚未完整学习 SMART/NORMAL 的 LBS、Circuit Breaker 和 <ZhaiWaiJieDiDaoZha> 接地刀闸。请用确认过的标准 G 文件重新扫描并保存新 ACTIVE 版本。",
            )
            return

        self._persist()
        run_dir = begin_managed_run(self.output_path, "jeddah-batch", "process")
        settings = JeddahBatchSettings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=run_dir,
            small_element_threshold=self.threshold.value(),
            rmu_name_top=self.name_top.isChecked(),
            rmu_name_bottom=self.name_bottom.isChecked(),
            rmu_name_left=self.name_left.isChecked(),
            rmu_name_right=self.name_right.isChecked(),
            rmu_name_exclusions=self.name_exclusions.text().strip(),
            margin_left=self.margin_left.value(),
            margin_top=self.margin_top.value(),
            margin_right=self.margin_right.value(),
            margin_bottom=self.margin_bottom.value(),
            frame_template_file=self.template_selector.resolved_template_path(),
            frame_template_mode=self.template_selector.mode(),
            frame_builtin_template_id=self.template_selector.builtin_template_id(),
            rmu_profile_name=profile_name,
        )
        self.task.start(
            lambda log, progress: process_jeddah_batch(settings, log, progress),
            run_dir,
        )

    def save_state(self) -> None:
        self._persist()
        self.output_path.persist_current_text()
