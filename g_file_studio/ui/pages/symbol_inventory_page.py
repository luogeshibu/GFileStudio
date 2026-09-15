from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QMessageBox, QPushButton, QVBoxLayout

from g_file_studio.services.database_service import OracleDatabaseService
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.run_history import begin_managed_run, configure_managed_output
from g_file_studio.services.site_profile_service import SiteProfileService
from g_file_studio.services.symbol_inventory_service import process_symbol_inventory
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_input_source
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, PathRow, TaskPanel, WheelSafeComboBox
from g_file_studio.ui.widgets.help_widgets import set_secondary


_HELP = """
<h2>G 图形内容解析</h2>
<p>本模块对业务 G 做全量内容解析：RMU 组合设备和 TRANSFORMER、LBS、FUSE、REC、SFI、CB 等独立/内部设备都会进入统一 ADMS-SLD 设备明细，并同时生成多 Sheet Excel 与 HTML 报告。</p>
<ul>
<li>解析对象不限于“设备”：设备、设备组成图元、状态图元、测量/信号、标签/辅助图元、Poke/跳转及其他已配置图元都会统一纳入结果。</li>
<li>设备汇总不再局限于 RMU：变压器、LBS、Fuse、Recloser、SFI、CB 及后续标准库新增设备都会进入 ADMS-SLD 设备明细；原始图元类型仍保留用于审计。</li>
<li>Excel 固定提供 ADMS-SLD设备明细、ADMS-SLD主设备、RMU、TRANSFORMER、LBS、FUSE、REC、SFI、CB、RMU内部设备、未命名设备等 Sheet，便于数据迁移按 Sheet/字段映射直接读取。</li>
<li>RMU 继续复用公共 identify_rmus()，但本模块启用自动柜名模式：按 RMU 重复排列自动分 Cluster，分别学习 TOP/RIGHT/BOTTOM/LEFT 名称布局与主导文字风格，再做整组一对一分配；无需人工指定现场方向。只要 ParentRMU 非空，该实例仍强制视为 RMU 内部设备，不进入 ADMS-SLD主设备和主设备类型统计。</li>
<li>除 RMU 外，独立设备名称统一按全图最近文字识别：不限定上/下/左/右方向、不使用方向加权；优先以设备连接线端点作为视觉锚点，从全图 Text/DText 中按真实几何距离做一对一分配。F、F.C、N.O.P、Y1/Q1、SMART/SMR 等明确注释不参与设备名称候选。</li>
<li>所属馈线以 Bus 仅作为上游边界，并按真实 link/node_area 拓扑识别每个馈线分支；每个分支只查询顶部 CBreaker / Disconnector / GroundDisconnector 三类入口设备 keyid。keyid 通过 long2_to_long1/get_tab_no 解码并校验 407/408/409，再查询 BAY.ID → BAY.NAME/ST_ID → SUBSTATION.NAME。CBreaker(407) 是馈线权威根：只要 CBreaker 取得有效 BAY，就从其非 Bus 一侧沿 ConnectLine / FeedLine / BusDis / 设备节点一直遍历到真实拓扑终点，所有下游设备直接继承同一馈线，不再查询任何下游设备 keyid 或关联状态。Disconnector/GroundDisconnector 只做一致性/回退证据，其未关联或旧 BAY 只告警，不会抹掉有效 CBreaker 馈线；不使用 facID/facName、FeedLine 文字或空间距离补猜。</li>
<li>标准校验复用当前全局执行图元标准，只读执行，不修改源 G 文件。</li>
<li>业务 G 中存在 devref 但尚未映射到标准的对象会进入“未定义图元”，不会静默丢失，便于后续继续补充分类和标准。</li>
</ul>
"""


class SymbolInventoryPage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.profile_service = SiteProfileService()
        self.last_excel: Path | None = None
        self.last_html: Path | None = None
        super().__init__(
            "G 图形内容解析",
            "全量解析业务 G：RMU 与全设备明细、图元、文本、拓扑和 XML；输出 ADMS-SLD 多 Sheet Excel + HTML。",
            "G 图形内容解析帮助",
            _HELP,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "使用当前 GLOBAL 图元标准识别并校验全部业务 G 内容；RMU、TRANSFORMER、LBS、FUSE、REC、SFI、CB 等统一汇总，"
                "并输出面向数据迁移的 ADMS-SLD 多 Sheet Excel 与完整 XML/对象结构清单。"
            )
        )

        standard_box = QGroupBox("标准与分类")
        standard_form = QFormLayout(standard_box)
        self.profile_combo = WheelSafeComboBox()
        self.profile_combo.setMinimumContentsLength(46)
        self.profile_combo.setToolTip("使用“图元标准检查”中由用户明确设置的全局执行版本；本页不自动切换到最新版本。")
        standard_form.addRow("当前全局图元标准", self.profile_combo)
        note = QLabel(
            "设备与图元分类以 GLOBAL 标准为准；全部 XML 对象仍会进入完整内容清单，不因未配置标准而丢失。"
        )
        note.setWordWrap(True)
        note.setObjectName("mutedText")
        standard_form.addRow("说明", note)
        self.layout.addWidget(standard_box)

        io_box = QGroupBox("输入与输出")
        io_layout = QVBoxLayout(io_box)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一个需要分析图形内容的业务 G 文件。",
            directory_tooltip="选择包含多个业务 G 文件的目录；程序批量解析目录第一层中的 G 文件。",
            settings_prefix="symbol_inventory",
            settings_service=self.user_settings,
        )
        io_layout.addWidget(self.source)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择图形内容解析输出目录",
            recent_directory_key="recent_paths/symbol_inventory/output_directory",
            persistent_path_key="symbol_inventory/output_directory",
            default_path=default_workspace() / "symbol-inventory",
            location_name="图形内容解析输出目录",
            settings_service=self.user_settings,
        )
        configure_managed_output(self.output_path, "symbol-inventory")
        io_layout.addWidget(self.output_path)
        self.layout.addWidget(io_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始解析")
        self.task.run_button.clicked.connect(self.run)
        self.excel_button = QPushButton("打开详细 Excel")
        set_secondary(self.excel_button)
        self.excel_button.setEnabled(False)
        self.excel_button.clicked.connect(self.open_excel)
        self.task.buttons_layout.insertWidget(1, self.excel_button)
        self.html_button = QPushButton("打开 HTML 报告")
        set_secondary(self.html_button)
        self.html_button.setEnabled(False)
        self.html_button.clicked.connect(self.open_html)
        self.task.buttons_layout.insertWidget(2, self.html_button)
        self.task.set_smooth_progress_enabled(True)
        self.task.resultReceived.connect(self._on_result)
        self.layout.addWidget(self.task, 1)

        self.refresh_profiles(self.user_settings.get_value("symbol_inventory/profile_name", ""))

    def refresh_profiles(self, preferred_name: str = "") -> None:
        del preferred_name  # kept for existing cross-page signal compatibility
        name, version = self.profile_service.get_global_profile_selection()
        profile = self.profile_service.get_profile_version(name, version) if name and version is not None else None
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        if profile is None:
            self.profile_combo.addItem("尚未设置全局图元标准，请到“图元标准检查”选择版本并设为全局", ("", None))
        else:
            count = profile.configured_builtin_role_count + sum(
                1 for row in profile.custom_symbols
                if bool(row.get("enabled", True)) and str(row.get("standard_devref", "")).strip()
            )
            lock_text = " · LOCKED" if profile.locked else ""
            self.profile_combo.addItem(
                f"{profile.site_name} / {profile.profile_name} / V{profile.profile_version} · GLOBAL · {count} 项标准{lock_text}",
                (profile.profile_name, profile.profile_version),
            )
        self.profile_combo.setCurrentIndex(0)
        self.profile_combo.setEnabled(False)
        self.profile_combo.blockSignals(False)

    def _selected_profile(self):
        data = self.profile_combo.currentData()
        if not isinstance(data, (tuple, list)) or len(data) < 2:
            return "", None
        name = str(data[0] or "").strip()
        try:
            version = int(data[1]) if data[1] is not None else None
        except (TypeError, ValueError):
            version = None
        return name, self.profile_service.get_profile_version(name, version) if name and version is not None else None

    def run(self) -> None:
        self.refresh_profiles()
        name, profile = self._selected_profile()
        if not name or profile is None:
            QMessageBox.warning(self, "请选择标准", "请先在“图元标准检查”中选择一个已保存版本并设为全局执行标准。")
            return
        if not profile.authoritative_ready:
            QMessageBox.warning(self, "标准未就绪", "当前全局标准还没有任何有效标准图元。")
            return
        if not validate_input_source(self, self.source, display_name="G 图形内容解析输入"):
            return

        self.source.persist_current()
        output_dir = begin_managed_run(self.output_path, "symbol-inventory", "extract")
        prepared_source = self.source.prepare_for_processing(log=self.task.append_log)
        input_mode = self.source.mode()
        self.last_excel = None
        self.last_html = None
        self.excel_button.setEnabled(False)
        self.html_button.setEnabled(False)
        self.task.start(
            lambda log, progress: process_symbol_inventory(
                prepared_source,
                input_mode,
                output_dir,
                profile,
                log,
                progress,
                OracleDatabaseService(self.user_settings),
            ),
            output_dir,
        )

    def _on_result(self, result) -> None:
        self.last_excel = None
        self.last_html = None
        stats = result.statistics if getattr(result, "statistics", None) else {}
        excel_text = str(stats.get("excel_path", ""))
        html_text = str(stats.get("html_path", ""))
        if excel_text:
            path = Path(excel_text)
            if path.exists():
                self.last_excel = path
        if html_text:
            path = Path(html_text)
            if path.exists():
                self.last_html = path
        self.excel_button.setEnabled(self.last_excel is not None)
        self.html_button.setEnabled(self.last_html is not None)
        if self.last_excel or self.last_html:
            self.task.append_log(
                "[解析结果] 已生成 ADMS-SLD 多 Sheet 设备明细：主设备、RMU/TRANSFORMER/LBS/FUSE/REC/SFI/CB、RMU内部设备、未命名设备，以及完整图元/XML审计。"
            )

    def open_excel(self) -> None:
        if not self.last_excel or not self.last_excel.exists():
            QMessageBox.information(self, "暂无 Excel", "请先执行一次图形内容解析。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_excel.resolve())))

    def open_html(self) -> None:
        if not self.last_html or not self.last_html.exists():
            QMessageBox.information(self, "暂无 HTML 报告", "请先执行一次图形内容解析。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_html.resolve())))

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()
