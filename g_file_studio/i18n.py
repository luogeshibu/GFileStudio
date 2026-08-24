from __future__ import annotations

"""Lightweight runtime i18n for G File Studio.

The project intentionally keeps XML/business identifiers untouched.  Only user-facing
text is translated.  Chinese is the canonical source language so existing modules do
not need invasive business-logic changes.
"""

from html import escape
import re
from typing import Iterable

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QWidget,
)

from g_file_studio.services.user_settings_service import UserSettingsService

LANG_ZH = "zh_CN"
LANG_EN = "en_US"
SUPPORTED_LANGUAGES = (LANG_ZH, LANG_EN)

# Exact translations for the visible application vocabulary. XML tags/attributes and
# domain values such as Bus, BusDis, SMART, keyid, devref, lc/lcc/ls are intentionally
# preserved.
EN: dict[str, str] = {
    "G File Studio · NARI 国际业务部": "G File Studio · NARI International Business Division",
    "NARI 国际业务部": "NARI International Business Division",
    "G 文件处理工具": "G File Processing Tool",
    "语言 / Language": "Language",
    "中文": "Chinese",
    "English": "English",
    "中文": "Chinese",
    "语言 / Language": "Language",
    "扫描 G 文件 ID、维护规则模板，并可强制把不符合模板或重复的 ID 修复为模板格式。": "Scan G-file IDs, maintain rule templates, and force-repair IDs that violate templates or are duplicated.",
    "打开新 G 时会对照模板检查：发现新的元素类型会提醒是否加入模板；已知类型只要固定前缀或总位数不符合模板就会告警。执行修复时会强制把格式不符和重复 ID 都更新为模板格式；同类型按当前最大合法完整 ID + 1。未知或未确认类型绝不擅自生成新 ID。": "When a new G file is opened, IDs are checked against the templates. New element types require confirmation before being added. Known types are warned when the fixed prefix or total length is invalid. Repair converts malformed and duplicate IDs to the confirmed template and allocates from the current maximum valid ID + 1. Unknown or unconfirmed types never receive generated IDs.",
    "规则格式：XML 元素类型 + 固定数字起始前缀 + 固定 ID 总位数。所有模块只允许使用这里已启用、已确认的规则；新增 ID 按同类型当前最大完整 ID + 1，并始终校验前缀和位数。": "Rule format: XML element type + fixed numeric prefix + fixed total ID length. All modules may use only enabled and confirmed rules. New IDs use the current maximum complete ID of the same type + 1 and are always validated for prefix and length.",
    "默认开启：处理输出时会把已有不符合模板的 ID 也强制修复。关闭后不会强制改写已有格式不符 ID；但所有模块新生成的 ID 仍必须严格使用已确认模板。": "Enabled by default: existing IDs that do not match the template are force-repaired in output. When disabled, existing malformed IDs are left unchanged, but every newly generated ID must still use a confirmed template.",
    "✓ 已确认": "✓ Confirmed",
    "前缀 + 总位数；同类型最大 ID + 1": "Prefix + total length; maximum ID of same type + 1",
    "扫描发现需要关注的内容，请在下方滚动查看。": "The scan found items that require attention. Scroll below to review them.",
    "扫描完成，详细结果如下。": "Scan completed. Detailed results are shown below.",
    "示例：ConnectLine 使用前缀 34、总位数 8，因此 34000053、34001838 合法，而 140、340123456 不合法。新增 ID 按同类型当前最大完整 ID + 1，并且结果必须继续满足前缀和总位数。": "Example: ConnectLine uses prefix 34 and total length 8, so 34000053 and 34001838 are valid, while 140 and 340123456 are invalid. New IDs use the current maximum complete ID of the same type + 1 and must still satisfy the configured prefix and total length.",
    "XML 元素类型不能为空。": "XML element type cannot be empty.",
    "ID 固定前缀必须是数字。": "The fixed ID prefix must be numeric.",
    "ID 总位数必须是正整数。": "The total ID length must be a positive integer.",
    "ID 总位数必须大于固定前缀长度。": "The total ID length must be greater than the fixed prefix length.",
    "关闭全局 ID 强制约束": "Disable Global ID Enforcement",
    "切换界面语言；选择会自动保存，下次启动继续使用。": "Switch the interface language. Your choice is saved automatically and restored at the next startup.",
    "NARI 国际业务部 · G 文件处理工具已就绪。鼠标停留在控件上可查看提示，按 F1 打开帮助中心。": "NARI International Business Division · G File Processing Tool is ready. Hover over controls for tips; press F1 to open Help Center.",
    "异常小尺寸图元检测": "Abnormal Small Element Detection",
    "ID 检查与修复": "ID Check & Repair",
    "环网柜处理": "RMU Processing",
    "基础处理": "Basic Processing",
    "馈线图合并": "Feeder Diagram Merge",
    "图形边距调整": "Drawing Margin Adjustment",
    "图框添加": "Drawing Frame",
    "帮助中心": "Help Center",
    "页面帮助": "Page Help",
    "帮助": "Help",
    "输入与输出": "Input & Output",
    "输入方式": "Input Source",
    "单个 G 文件": "Single G File",
    "G 文件目录": "G File Directory",
    "SSH 远程 G 文件（只读）": "SSH Remote G Files (Read-only)",
    "选择单个 G 文件": "Select G File",
    "选择 G 文件目录": "Select G File Directory",
    "浏览…": "Browse…",
    "输出目录（workspace，只读）": "Output Directory (workspace, read-only)",
    "输出文件": "Output File",
    "输出文件名": "Output File Name",
    "文件名": "File Name",
    "状态": "Status",
    "选择": "Select",
    "取消": "Cancel",
    "确定": "OK",
    "关闭": "Close",
    "保存": "Save",
    "删除": "Delete",
    "编辑": "Edit",
    "新增": "Add",
    "打开报告": "Open Report",
    "暂无报告": "No Report Yet",
    "开始执行": "Run",
    "开始基础处理": "Start Basic Processing",
    "开始环网柜处理": "Start RMU Processing",
    "开始合并": "Start Merge",
    "开始调整图形边距": "Adjust Drawing Margins",
    "开始图框添加": "Add Drawing Frame",
    "取消任务": "Cancel Task",
    "执行与日志": "Execution & Log",
    "清空日志": "Clear Log",
    "打开本次运行目录": "Open Current Run Folder",
    "处理日志会显示在这里……": "Processing log will appear here…",
    "任务已启动……": "Task started…",
    "处理完成。": "Processing completed.",
    "处理完成": "Completed",
    "处理完成（有告警）": "Completed with Warnings",
    "处理失败": "Processing Failed",
    "处理失败：": "Processing failed:",
    "告警：": "Warnings:",
    "统计：": "Statistics:",
    "输出：": "Output:",
    "基础处理输入": "Basic Processing Input",
    "基础处理输出目录": "Basic Processing Output Directory",
    "环网柜处理输入": "RMU Processing Input",
    "环网柜处理输出目录": "RMU Processing Output Directory",
    "异常小尺寸图元输入": "Abnormal Small Element Input",
    "异常小尺寸图元输出目录": "Abnormal Small Element Output Directory",
    "ID 扫描输入": "ID Scan Input",
    "ID 处理输入": "ID Processing Input",
    "ID 修复输出目录": "ID Repair Output Directory",
    "ID 检查与修复输出目录": "ID Check & Repair Output Directory",
    "馈线图合并输入目录": "Feeder Merge Input Directory",
    "馈线图合并输出目录": "Feeder Merge Output Directory",
    "输入文件与合并顺序": "Input Files & Merge Order",
    "图形边距调整输入": "Drawing Margin Input",
    "图形边距调整输出目录": "Drawing Margin Output Directory",
    "图框添加输入": "Drawing Frame Input",
    "图框添加输出目录": "Drawing Frame Output Directory",
    "扫描文件与输出": "Scan Files & Output",
    "扫描 / 处理文件": "Scan / Process Files",
    "输入文件": "Input File",
    "目录": "Directory",
    "文件": "File",
    "元素类型": "Element Type",
    "属性名": "Attribute Name",
    "属性值": "Attribute Value",
    "旧值": "Old Value",
    "新值": "New Value",
    "备注": "Notes",
    "扫描元素与属性": "Scan Elements & Attributes",
    "替换元素属性值": "Replace Element Attribute Value",
    "删除匹配元素": "Delete Matching Element",
    "删除元素属性": "Delete Element Attribute",
    "删除属性": "Delete Attribute",
    "通用处理规则": "General Processing Rules",
    "图元版本升级适配": "Symbol Version Upgrade",
    "启用图元版本升级适配": "Enable Symbol Version Upgrade",
    "连接点修复": "Connection Repair",
    "修复连接点（补齐 node_area / link）": "Repair Connections (complete node_area / link)",
    "母线馈线名称定位": "Bus/Feeder Title Positioning",
    "将馈线名称移动到母线上方": "Move Feeder Name Above Bus",
    "线路与母线样式": "Line & Bus Styles",
    "馈线": "Feeder",
    "连接线": "Connection Line",
    "配网母线": "Distribution Bus",
    "主网母线": "Main-grid Bus",
    "修改": "Modify",
    "颜色": "Color",
    "选择颜色": "Choose Color",
    "线型": "Line Style",
    "保持原样": "Keep Original",
    "实线": "Solid",
    "虚线": "Dashed",
    "图形组合处理": "Graphic Group Processing",
    "彻底取消图形组合（删除全部 <Merge>，并将 RMU 外框置底）": "Fully Ungroup Graphics (remove all <Merge> and send RMU frames to back)",
    "环网柜图元处理": "RMU Graphic Processing",
    "组合所有环网柜": "Group All RMUs",
    "不处理环网柜组合": "Do Not Change RMU Grouping",
    "环网柜增强操作（可多选）": "RMU Enhancements (multiple selection)",
    "修改含 SMART 的环网柜外框颜色": "Change Frame Color of RMUs Containing SMART",
    "修改含 SMR 的环网柜外框颜色": "Change Frame Color of RMUs Containing SMR",
    "移动环网柜红色状态点（channel_status）": "Move RMU Red Status Point (channel_status)",
    "删除带 Bus 的环网柜外框，并将最近标题放到母线上方": "Remove RMU Frame Containing Bus and Move Nearest Title Above Bus",
    "环网柜名称与柜型识别": "RMU Name & Type Recognition",
    "启用环网柜名称与柜型识别": "Enable RMU Name & Type Recognition",
    "柜名可能位置：": "Possible RMU name positions:",
    "柜名排除字符串：": "RMU Name Exclusions:",
    "例如：NOP, DAS/OK, SFI": "Example: NOP, DAS/OK, SFI",
    "多个字符串使用逗号或分号分隔。按完整字符串匹配，忽略大小写和首尾空白；不会使用包含关系，例如排除 SFI 不会排除 SFI-1201。": "Separate multiple strings with commas or semicolons. Matching is exact, case-insensitive, and ignores surrounding whitespace. Substring matching is not used; for example, excluding SFI will not exclude SFI-1201.",
    "上方": "Top",
    "下方": "Bottom",
    "左侧": "Left",
    "右侧": "Right",
    "识别 SMART（单独列，不参与柜型）": "Recognize SMART (separate column, excluded from cabinet type)",
    "RMU 信息汇总": "RMU Summary",
    "RMU 信息汇总设置": "RMU Summary Settings",
    "启用 RMU 信息汇总": "Enable RMU Summary",
    "启用智能环网柜分类（SMART / SMR）": "Enable Smart RMU Classification (SMART / SMR)",
    "RMU 台账对比": "RMU Ledger Comparison",
    "现有 RMU 台账对比（可选）": "Existing RMU Ledger Comparison (Optional)",
    "启用现有 RMU 台账对比": "Enable Existing RMU Ledger Comparison",
    "RMU 台账文件": "RMU Ledger File",
    "台账文件": "Ledger File",
    "台账输入方式：": "Ledger Input Method:",
    "Excel / CSV 导入": "Excel / CSV Import",
    "直接粘贴表格": "Paste Table",
    "只粘贴 RMU 名称": "Paste RMU Names Only",
    "选择 RMU 台账": "Select RMU Ledger",
    "打开 RMU 汇总报告": "Open RMU Summary Report",
    "打开台账对比报告": "Open Ledger Comparison Report",
    "打开图元处理报告": "Open Graphic Processing Report",
    "异常尺寸阈值": "Abnormal Size Threshold",
    "检测规则": "Detection Rule",
    "扫描异常图元": "Scan Abnormal Elements",
    "异常图元结果": "Abnormal Element Results",
    "全选处理": "Select All for Processing",
    "删除选中异常图元": "Delete Selected Abnormal Elements",
    "处理": "Process",
    "未勾选": "Not Selected",
    "本次勾选": "Selected This Run",
    "确认删除": "Confirm Deletion",
    "尚未扫描。": "Not scanned yet.",
    "无法扫描": "Unable to Scan",
    "没有文件": "No Files",
    "没有找到可扫描的 G 文件。": "No G files were found for scanning.",
    "扫描失败": "Scan Failed",
    "扫描已取消。": "Scan cancelled.",
    "未勾选": "Nothing Selected",
    "请先在结果表第一列勾选需要处理的异常图元。": "Select the abnormal elements to process in the first column of the results table.",
    "删除选中异常图元": "Delete Selected Abnormal Elements",
    "扫描异常图元": "Scan Abnormal Elements",
    "全选处理": "Select All for Processing",
    "打开报告": "Open Report",
    "可单独选择 XML ID 或任意单元格/区域，按 Ctrl+C 复制": "Select an XML ID or any cell/range and press Ctrl+C to copy.",
    "首列勾选决定哪些图元参与处理；其余单元格可像表格一样单选/框选，按 Ctrl+C 复制。": "Use the first-column checkboxes to choose elements for processing. Other cells support normal single/range selection and Ctrl+C copy.",
    "当目标元素的 w 和 h 同时小于该值时，报告为异常小尺寸图元。": "An element is reported as abnormally small when both w and h are below this threshold.",
    "扫描完成后会生成/覆盖本模块的扫描 CSV/HTML 报告，可点击“打开报告”查看。": "Scanning generates or overwrites this module's CSV/HTML scan reports. Use Open Report to view the HTML report.",
    "删除结果表中已勾选的异常小尺寸图元，生成修改后的 G 文件，并生成/覆盖处理 CSV/HTML 报告；报告会列出实际删除项。": "Delete the checked abnormal elements, generate modified G files, and generate or overwrite the processing CSV/HTML reports. The reports list the elements actually deleted.",
    "异常小尺寸图元扫描完成，扫描报告已生成并覆盖上一份扫描报告。\n可点击“打开报告”查看 HTML 报告。": "Abnormal small-element scan completed. The scan reports were generated and replaced the previous scan reports.\nUse Open Report to view the HTML report.",
    "请先执行一次扫描并生成报告。": "Run a scan first to generate a report.",
    "ID 规则模板": "ID Rule Template",
    "XML 元素类型": "XML Element Type",
    "ID 固定前缀": "ID Fixed Prefix",
    "ID 起始前缀": "ID Prefix",
    "ID 总位数": "ID Total Digits",
    "总位数": "Total Digits",
    "合法示例": "Valid Example",
    "当前规则": "Current Rule",
    "新增 ID 规则": "Add ID Rule",
    "新增规则": "Add Rule",
    "编辑 ID 规则": "Edit ID Rule",
    "编辑规则": "Edit Rule",
    "删除规则": "Delete Rule",
    "扫描当前 G": "Scan Current G",
    "扫描当前G文件（只检查ID）": "Scan Current G File (ID only)",
    "检查并强制修复 ID": "Check & Force Repair IDs",
    "启用全局 ID 模板强制约束": "Enable Global ID Template Enforcement",
    "关闭全局 ID 模板强制约束": "Disable Global ID Template Enforcement",
    "正常": "Normal",
    "格式不符": "Invalid Format",
    "重复 ID": "Duplicate ID",
    "未配置模板": "Template Not Configured",
    "扫描完成": "Scan Completed",
    "扫描失败": "Scan Failed",
    "扫描已取消。": "Scan cancelled.",
    "文件名关键字": "File Name Keywords",
    "加载 / 检查": "Load / Check",
    "加载中": "Loading",
    "查询并导入": "Search & Import",
    "查询并导入 G 文件": "Search & Import G Files",
    "导入全部可用": "Import All Available",
    "删除所选": "Remove Selected",
    "置顶": "Move to Top",
    "上移": "Move Up",
    "下移": "Move Down",
    "置底": "Move to Bottom",
    "顺序": "Order",
    "图框检查": "Frame Check",
    "状态/原因": "Status / Reason",
    "垂直对齐基准": "Vertical Alignment Baseline",
    "原始基准 Y": "Original Baseline Y",
    "主母线处理": "Main Bus Processing",
    "启用主网母线处理": "Enable Main Bus Processing",
    "单母线": "Single Bus",
    "双母线": "Double Bus",
    "选择主母线类型": "Select Main Bus Type",
    "设置母线分组": "Set Bus Groups",
    "设置主母线人工分组": "Set Manual Main Bus Groups",
    "主母线人工分组": "Manual Main Bus Grouping",
    "主母线处理不可用": "Main Bus Processing Unavailable",
    "请先加载并导入需要合并的馈线文件。": "Load and import the feeder files to be merged first.",
    "设置母线分组": "Set Bus Groups",
    "请先把馈线导入合并顺序列表。": "Import feeder files into the merge-order list first.",
    "创建母线组": "Create Bus Group",
    "请至少选择 2 个连续馈线。": "Select at least two consecutive feeders.",
    "同一母线组中的馈线必须连续。": "Feeders in the same bus group must be consecutive.",
    "母线分组无效": "Invalid Bus Grouping",
    "未设置任何组；所有馈线母线保持独立。": "No groups are configured; all feeder buses remain independent.",
    "创建母线组": "Create Bus Group",
    "清除所选分组": "Clear Selected Group",
    "清空全部分组": "Clear All Groups",
    "母线组": "Bus Group",
    "未分组": "Ungrouped",
    "按当前馈线顺序选择连续的两行或多行，然后点击“创建母线组”。同组馈线将共用主母线；未分组馈线保持独立。分组完全由人工指定，不读取 keyid。": "Select two or more consecutive feeder rows in the current merge order, then click Create Bus Group. Feeders in the same group will share the main bus; ungrouped feeders remain independent. Grouping is defined manually and does not use keyid.",
    "未设置任何组；所有馈线母线保持独立。": "No bus groups are configured; all feeder buses remain independent.",
    "布局参数": "Layout Parameters",
    "默认单线图宽度": "Default Single-line Diagram Width",
    "相邻图形间隔": "Adjacent Diagram Gap",
    "左边距": "Left Margin",
    "右边距": "Right Margin",
    "上边距": "Top Margin",
    "下边距": "Bottom Margin",
    "图形左边距": "Drawing Left Margin",
    "图形右边距": "Drawing Right Margin",
    "图形上边距": "Drawing Top Margin",
    "图形下边距": "Drawing Bottom Margin",
    "主体图形边距": "Main Drawing Margins",
    "图框模板": "Drawing Frame Template",
    "图框与输出参数": "Frame & Output Parameters",
    "图框左边距": "Frame Left Margin",
    "图框右边距": "Frame Right Margin",
    "图框上边距": "Frame Top Margin",
    "图框下边距": "Frame Bottom Margin",
    "内置模板：标题与签字栏": "Built-in Template: Title & Signatures",
    "左上标题": "Top-left Title",
    "使用程序内置模板": "Use Built-in Template",
    "使用客户自定义模板": "Use Custom Template",
    "客户自定义图框模板": "Custom Drawing Frame Template",
    "导出内置模板": "Export Built-in Template",
    "导出内置图框模板": "Export Built-in Drawing Frame Template",
    "图元文件": "Symbol File",
    "旧图元": "Old Symbol",
    "新图元": "New Symbol",
    "添加旧图元 G…": "Add Old Symbol G…",
    "添加新图元 G…": "Add New Symbol G…",
    "移除选中": "Remove Selected",
    "清空": "Clear",
    "检查配对与参数": "Check Pairing & Parameters",
    "图元配对检查": "Symbol Pairing Check",
    "待检查": "Pending Check",
    "IP / 主机": "IP / Host",
    "端口": "Port",
    "用户名": "Username",
    "密码": "Password",
    "远程目录": "Remote Directory",
    "搜索 G 文件": "Search G Files",
    "测试 SSH 连接": "Test SSH Connection",
    "刷新 G 文件列表": "Refresh G File List",
    "保存 SSH 设置": "Save SSH Settings",
    "切换界面语言；选择会自动保存，下次启动继续使用。": "Switch UI language. The selection is saved automatically and restored on next launch.",
    "全选当前结果": "Select All Results",
    "取消当前结果": "Clear Current Results",
    "清空全部选择": "Clear All Selections",
    "下载所选到本地…": "Download Selected Locally…",
    "大小": "Size",
    "服务器修改时间": "Server Modified Time",
    "尚未加载远程文件": "Remote files not loaded",
    "已下载": "Downloaded",
    "总数": "Total",
    "距边": "Inset",
    "像素": "px",
    "姓名": "Name",
    "填写": "Fill",
    "日期默认是当前日期；点击日历按钮可修改。": "The date defaults to today; click the calendar button to change it.",
    "NARI 国际业务部 · G 文件处理工具已就绪。鼠标停留在控件上可查看提示，按 F1 打开帮助中心。": "NARI International Business Division · G File Processing Tool is ready. Hover over controls for tips; press F1 for Help Center.",
    "任务已成功完成，详细结果请查看日志。": "Task completed successfully. See the log for details.",
    "任务已完成，但部分文件处理失败或存在告警，请查看日志和报告。": "Task completed with failed files or warnings. See the log and reports for details.",
    "处理过程中发生错误，详情请查看日志区域。": "An error occurred during processing. See the log for details.",
    "当前主列表就是最终参与合并的文件集合和顺序。": "The main list is the final set and order of files to be merged.",
    "未设置任何组；所有馈线母线保持独立。": "No groups are configured; all feeder buses remain independent.",
    "母线类型：单母线": "Bus type: Single Bus",
    "母线类型：双母线": "Bus type: Double Bus",
    "母线类型：未选择": "Bus type: Not Selected",
    "请选择文件": "Select Files",
    "请选择规则": "Select Rule",
    "规则已存在": "Rule Already Exists",
    "规则无效": "Invalid Rule",
    "文件不存在": "File Not Found",
    "路径无效": "Invalid Path",
    "上次路径不存在": "Previous Path Not Found",
    "上次目录不存在": "Previous Directory Not Found",
    "SSH 连接失败": "SSH Connection Failed",
    "下载失败": "Download Failed",
    "下载完成": "Download Completed",
    "保存 SSH 设置失败": "Failed to Save SSH Settings",
    "SSH 设置已保存；所有使用 SSH 文件源的模块将复用这组最后输入。": "SSH settings saved. All modules using the SSH file source will reuse these latest values.",
}

# Long but frequently visible descriptions/tooltips. Exact mapping keeps the UI clean.
EN.update({
    "检测 ConnectLine、FeedLine、Bus、BusDis 中 w/h 同时过小的疑似残留短线图元；通过首列勾选单选/多选/全选后统一执行处理": "Detect suspicious residual short elements in ConnectLine, FeedLine, Bus and BusDis where both w/h are too small; select one, multiple or all rows in the first column before processing.",
    "全局 ID 规则中心：维护模板、扫描覆盖并强制修复格式异常或重复 ID": "Global ID rule center: maintain templates, scan coverage, and force-repair malformed or duplicate IDs.",
    "独立处理环网柜组合/取消组合、增强操作，以及柜名与柜型识别": "Process RMU grouping, enhancements, and RMU name/type recognition independently.",
    "执行通用属性、图元升级、馈线标题、连接点和线路/母线颜色处理；涉及 ID 时强制使用全局模板": "Run general attribute, symbol upgrade, feeder title, connection, and line/bus style processing; global templates are mandatory for ID operations.",
    "按用户选择顺序合并多个馈线 G 图": "Merge multiple feeder G drawings in the user-defined order.",
    "调整主体四边距，并同步适配内置图框": "Adjust main drawing margins and synchronize the built-in drawing frame.",
    "添加 SLD 外框、标题和签字栏": "Add SLD border, title, and signature fields.",
    "查看使用说明和目录建议": "View usage instructions and workspace recommendations.",
    "支持处理单个 G 文件或整个目录；勾选需要的规则后统一点击“开始基础处理”。": "Process a single G file or an entire directory. Select the required rules, then click Start Basic Processing.",
    "按用户选择顺序合并多个馈线 G 图，完成垂直对齐、冲突 ID 处理和画布计算。": "Merge feeder G drawings in the selected order with vertical alignment, conflicting-ID handling, and canvas calculation.",
    "把主体图形整体移动到指定四边距；内置图框自动同步调整，其他图框要求先删除。": "Move the main drawing to the specified margins. The built-in frame is adjusted automatically; other frames must be removed first.",
    "支持为单个 G 文件或整个目录批量添加并适配 SLD 图框。": "Add and adapt SLD drawing frames for a single G file or an entire directory.",
    "独立处理环网柜组合、增强操作，以及柜名与柜型识别。": "Process RMU grouping, enhancements, and RMU name/type recognition independently.",
    "查看推荐流程、页面用途、目录说明和常见问题。按 F1 可随时打开本页面。": "View the recommended workflow, page purposes, folder guidance, and FAQs. Press F1 at any time to open this page.",
    "鼠标停留在按钮或字段上可以查看简短提示；圆形问号可查看详细说明。": "Hover over buttons or fields for short tips; use the round question-mark buttons for detailed help.",
    "SSH 服务器严格只读：仅列目录、读取文件属性和下载 G 文件；G File Studio 不提供上传、覆盖、重命名、删除或修改服务器文件的接口。": "The SSH server is strictly read-only: only directory listing, file metadata reading, and G-file download are allowed. G File Studio provides no upload, overwrite, rename, delete, or server-side modification operation.",
    "本地目录或 SSH/SFTP 只读远程 G 文件。远程模式只允许读取和下载，不会修改服务器文件。": "Use a local directory or read-only SSH/SFTP G files. Remote mode only reads and downloads files and never modifies the server.",
    "输出由程序统一管理。每次运行创建独立 workspace 目录，仅保留 30 天；需要长期保存请自行复制。": "Outputs are managed by the application. Each run gets a separate workspace folder retained for 30 days; copy files elsewhere for long-term storage.",
    "这是整个 G 文件级的组合清理，不只针对环网柜。启用后删除 Layer 中全部 <Merge>，并将识别到的 RMU 外框 <rect> 移到柜内设备之前，使外框位于设备底层。除删除 Merge 和调整 rect 的 XML 顺序外，不修改任何设备属性、坐标、ID、keyid、devref 或 tfr。": "This is a whole-G-file group cleanup, not an RMU-only operation. It removes every <Merge> in Layer and moves recognized RMU frame <rect> elements before cabinet devices so frames stay behind devices. No device attribute, coordinate, ID, keyid, devref or tfr is changed; only Merge removal and rect XML order are affected.",
    "按元素标签统一调整线路与母线样式。颜色仅修改 lc/lcc；线型仅修改 ls：实线=1、虚线=2。颜色勾选与线型选择彼此独立；线型选择‘保持原样’时不会修改 ls。不会修改填充色、线宽 lw、坐标、ID 或引用。": "Adjust line and bus styles by element tag. Color changes only lc/lcc; line style changes only ls (solid=1, dashed=2). Color and line-style settings are independent; Keep Original leaves ls unchanged. Fill, lw, coordinates, IDs and references are never changed.",
})


# Register complete help/field-help translations so rich-text dialogs are fully English.
try:
    from g_file_studio.ui.help_content import APP_HELP, APP_HELP_EN, FIELD_HELP, FIELD_HELP_EN
    for _key, (_zh_title, _zh_html) in APP_HELP.items():
        _en_title, _en_html = APP_HELP_EN[_key]
        EN[_zh_title] = _en_title
        EN[_zh_html] = _en_html
    for _key, _zh_text in FIELD_HELP.items():
        if _key in FIELD_HELP_EN:
            EN[_zh_text] = FIELD_HELP_EN[_key]
except Exception:
    pass

# v2.18.7: complete the remaining static UI/help/tool-tip vocabulary so English
# mode never falls back to a generic placeholder for normal controls.
EN.update({
    "本地 G 文件目录": "Local G File Directory",
    "留空自动生成 MERGED-时间戳.sln.pic.g；也可手动输入名称": "Leave blank to generate MERGED-timestamp.sln.pic.g automatically, or enter a file name manually.",
    "启用后必须选择单母线或双母线。只检查所选主母线；异常短线 Bus 不再在这里过滤，请统一使用“异常小尺寸图元检测”模块处理。": "When enabled, select Single Bus or Double Bus. Only the selected main bus is checked. Abnormally short Bus elements are handled by Abnormal Small Element Detection instead.",
    "点击选择单母线或双母线；勾选主网母线处理时也会自动弹出选择。": "Click to select Single Bus or Double Bus. The same selection dialog opens automatically when main-grid bus processing is enabled.",
    "按当前馈线顺序人工指定哪些连续馈线共用一组主母线；未分组馈线保持独立。": "Manually specify which consecutive feeders share one main-bus group. Ungrouped feeders remain independent.",
    "请选择当前参与合并的馈线图属于单母线还是双母线。": "Select whether the feeder diagrams in this merge use a single-bus or double-bus arrangement.",
    "单母线：只检查 Y 值最小的最高有效水平 <Bus>。\n双母线：检查最高母线，以及同方向下方长度大致相同的第二条有效水平 <Bus>。": "Single Bus: check only the highest valid horizontal <Bus> with the smallest Y value.\nDouble Bus: check the highest bus and the second valid horizontal <Bus> below it in the same direction with approximately the same length.",
    "馈线合并结果只能写入 G File Studio 的 workspace 运行目录，路径不可修改。处理完成后请点击“打开本次运行目录”查看或复制文件；运行目录自动保留 30 天。": "Feeder-merge output is written only to the G File Studio workspace run directory and cannot be changed here. After processing, use Open Current Run Folder to view or copy files. Run folders are retained for 30 days.",
    "每个馈线图的最小占用宽度。实际宽度小于该值时按该值预留；实际宽度超过该值时使用实际宽度。该宽度不包含相邻馈线间隔。": "Minimum reserved width for each feeder diagram. If the actual width is smaller, this value is reserved; otherwise the actual width is used. Adjacent-feeder spacing is not included.",
    "启用后先选择单母线或双母线，再人工设置母线分组。程序不再使用 keyid 判断分组；只有同一人工分组内、且在当前馈线顺序中连续的文件才会共用母线。未分组馈线保持独立。": "When enabled, first select Single Bus or Double Bus, then configure bus groups manually. keyid is not used for grouping. Only consecutive files in the same manual group share a bus; ungrouped feeders remain independent.",
    "“组合所有环网柜”会将每个直属 <rect> 作为环网柜外框，只组合完整位于矩形框内部的直属图元；任何部分位于框外的连接线、状态图标和文字都不会进入组合。彻底取消图形组合已经移动到“基础处理 → 图形组合处理”，因为该操作会删除整个 G 文件中的全部 <Merge>，不再属于 RMU 专用功能。": "Group All RMUs treats each direct <rect> as an RMU frame and groups only direct elements fully inside that rectangle. Connection lines, status icons, and text extending outside the frame are excluded. Full graphic ungrouping is now under Basic Processing > Graphic Group Processing because it removes every <Merge> in the G file.",
    "直接解析 G 文件，不使用 OCR。只有 rect 框内同时存在 BusDis、CBreakerDis 和 ZhaiWaiJieDiDaoZha 才认定为环网柜；柜名优先严格只在用户勾选方向中寻找：单候选直接使用；同一最近文字组存在多个候选时才优先绿色文字。常规几何匹配失败时，仅当柜内 BusDis.key_name 唯一候选与所选方向附近同名 Text 完全一致时回退。柜名排除字符串按完整文本匹配过滤。柜型优先按 Y1/Y2/... 与 Q1/Q2/... 名称计数，名称无法判断时才回退到设备 devref。SMART 与 SMR 统一统计为“智能环网柜”，并保留识别来源。": "Parse G files directly without OCR. A rect is recognized as an RMU only when BusDis, CBreakerDis, and ZhaiWaiJieDiDaoZha are all present inside it. RMU names are first searched strictly in the selected directions. A single candidate is used directly; green text is preferred only when multiple candidates exist in the same nearest text group. If normal geometry matching fails, fallback is allowed only when the unique BusDis.key_name candidate inside the cabinet exactly matches nearby Text in a selected direction. User-defined RMU name exclusions filter exact text values. Cabinet type is determined from Y1/Y2/... and Q1/Q2/... names first, then falls back to device devref. SMART and SMR are both counted as Smart RMU while preserving the recognition source.",
    "BusDis.key_name + Text 确认回退": "BusDis.key_name + Text confirmed fallback",
    "RMU 信息汇总始终统计全部有效环网柜。勾选后额外将 SMART/SMR 统一归类为智能环网柜；不勾选时仅汇总 RMU 名称、柜型、重复和识别异常，不进行智能/普通分类。": "RMU Summary always includes all valid RMUs. When enabled, SMART/SMR are additionally classified as Smart RMU. When disabled, the report still summarizes names, cabinet types, duplicates, and recognition issues without smart/normal classification.",
    "无论是否启用智能分类，都会统计全部有效 RMU，并检查重复名称/ID、柜名或柜型未识别、中低置信度等异常；这些信息会在 RMU 汇总 HTML 报告中重点提示。": "All valid RMUs are counted regardless of smart classification. Duplicate names/IDs, unrecognized names or cabinet types, and medium/low-confidence results are highlighted in the RMU Summary HTML report.",
    "将用户现有 RMU 台账与 G 文件识别结果进行对比。RMU 名称为必填匹配键；柜型、是否智能为可选字段。SMART 与 SMR 在对比时统一视为“智能环网柜”。原有 G 图形识别算法不因启用台账对比而改变。": "Compare an existing RMU ledger with G-file recognition results. RMU Name is the required match key; cabinet type and smart status are optional. SMART and SMR are treated as Smart RMU during comparison. Enabling ledger comparison does not change the G-file recognition algorithm.",
    "直接粘贴表格：\nRMU名称\tRMU类型\t是否智能\n30839\t2L1T\t是\n30864\t3L1T\t否\n\n或选择“只粘贴 RMU 名称”后每行一个名称。": "Paste a table directly:\nRMU Name\tRMU Type\tSmart\n30839\t2L1T\tYes\n30864\t3L1T\tNo\n\nOr select Paste RMU Names Only and enter one name per line.",
    "Excel/CSV 支持列：RMU名称（必填）、RMU类型（可选）、是否智能（可选）。没有表头时默认第1/2/3列分别作为名称/类型/智能。": "Excel/CSV columns: RMU Name (required), RMU Type (optional), Smart (optional). Without headers, columns 1/2/3 are treated as name/type/smart by default.",
    "框内位置": "Position in Frame",
    "扫描完成后会生成/覆盖 ID 扫描 CSV/HTML 报告，可点击“打开报告”查看；发现新元素类型仍会逐条询问是否加入模板。": "Scanning creates or replaces the ID scan CSV/HTML reports. Use Open Report to view them. New element types still require individual confirmation before being added to the template.",
    "执行后会按已确认模板修复 ID，并生成/覆盖 ID 修复 CSV/HTML 报告，可点击“打开报告”查看。": "Repairs IDs using confirmed templates and creates or replaces the ID repair CSV/HTML reports. Use Open Report to view them.",
    "“组合所有环网柜”会将每个直属 <rect> 作为环网柜外框，只组合完整位于矩形框内部的直属图元；任何部分位于框外的连接线、状态图标和文字都不会进入组合。“取消所有环网柜组合”会删除成员中含 <rect> 的 <Merge> 头元素，并把 rect 外框移动到柜内设备之前，使外框位于设备下层；坐标、ID、引用和业务属性不变，其他业务 Merge 不受影响。": "Group All RMUs treats each direct <rect> as an RMU frame and groups only direct elements fully inside it. Ungroup All RMUs removes RMU <Merge> headers containing a <rect> and moves the rect before the devices so the frame stays behind them. Coordinates, IDs, references, and business attributes are unchanged; other business Merge groups are preserved.",
    "保持文件现有 Merge 结构不变。": "Keep the existing Merge structure unchanged.",
    "单文件模式处理所选文件；目录模式处理第一层全部 G 文件。每个 rect 对应一个 Merge，只组合框内图元。": "Single-file mode processes the selected file; directory mode processes all first-level G files. Each rect maps to one Merge and only elements inside the frame are grouped.",
    "删除所有成员中包含 rect 的环网柜 Merge，保留全部成员，并把 rect 调整到柜内设备下层；不删除其他业务 Merge。": "Remove RMU Merge groups whose members include a rect, preserve all members, and move the rect behind cabinet devices. Other business Merge groups are not removed.",
    "只识别框内存在 ts=SMART 的 Text 的直属 rect，并修改该 rect 的静态边框色 lc 和 lcc；SMART 字体颜色以及不含 SMART 的其他环网柜外框均保持不变。": "Recognize only direct rect frames containing Text with ts=SMART and change only that rect's static border colors lc/lcc. SMART text color and other RMU frames remain unchanged.",
    "只处理带 BusDis 的环网柜中 devref 指向 channel_status 的 <Status> 红色状态点。仅移动该状态点本身，不移动环网柜、母线、设备、标题、连接线或其他图元。": "Process only red <Status> points whose devref references channel_status inside RMUs containing BusDis. Only the status point moves; the RMU, bus, devices, title, connection lines, and other elements remain unchanged.",
    "可选择矩形框内四个角或四条边的中点；默认左下角，与示意图中的目标位置一致。": "Choose any of the four corners or four edge midpoints inside the rectangular frame. The default is Bottom Left.",
    "状态点与所选矩形框边之间的内边距，默认 5 像素。": "Inner spacing between the status point and the selected frame edge. Default: 5 pixels.",
    "识别 rect 框内的 Bus，删除该 rect 及对应环网柜 Merge；寻找距离母线最近的业务标题 Text，移动到母线上方并水平居中。": "Recognize Bus elements inside the rect, remove the rect and corresponding RMU Merge, then move the nearest business-title Text above the bus and center it horizontally.",
    "直接解析 G 文件，不使用 OCR。只有 rect 框内同时存在 BusDis、CBreakerDis 和 ZhaiWaiJieDiDaoZha 才认定为环网柜；柜名只从勾选方向上的绿色 Text 中选择。柜型优先按 Y1/Y2/... 与 Q1/Q2/... 名称计数，名称无法判断时才回退到设备 devref。柜型始终输出如 2L1T、3L1T；SMART 单独识别成一列，不参与柜型字符串。": "Parse G files directly without OCR. A rect is recognized as an RMU only when BusDis, CBreakerDis, and ZhaiWaiJieDiDaoZha are all present inside it. RMU names are selected from green Text in the enabled directions. Cabinet type is determined from Y1/Y2/... and Q1/Q2/... names first, then falls back to device devref. CabinetType remains 2L1T, 3L1T, etc.; SMART is a separate column and is not part of the cabinet-type string.",
    "启用后在识别结果/CSV 的 SMART 列输出 1 或 0；CabinetType 始终只输出 2L1T、3L1T 等 L/T 柜型。": "When enabled, output 1 or 0 in the SMART column of recognition results/CSV. CabinetType remains an L/T type such as 2L1T or 3L1T.",
    "输出文件中删除全部 Layer 直属 Merge；原文件不修改。RMU 外框只调整 XML 前后顺序，不修改任何属性。": "Remove all direct Layer Merge elements from output files. Source files are unchanged. RMU frames are only reordered in XML; no attributes are modified.",
    "识别有效的水平 <Bus>，将上下平行且范围重叠的双母线视为一组；再依据 Text 的内容、字号和局部几何位置选择唯一可确认的馈线名称，移动到最上方母线的正上方并水平居中。识别不使用 key_name 或 keyid；无法唯一判断时跳过。该操作只修改目标 Text 的 x、y，不修改文字内容、字体、颜色、母线、设备、连接线、ID 或模型关联属性。": "Recognize valid horizontal <Bus> elements and treat parallel overlapping double buses as one group. Select a uniquely identifiable feeder-name Text using content, font size, and local geometry, then move it directly above the top bus and center it horizontally. Recognition does not use key_name or keyid; ambiguous cases are skipped. Only the target Text x/y coordinates are changed.",
    "勾选后随‘开始基础处理’执行；不勾选时完全跳过。纯数字、设备标签和说明文字不会移动。": "Runs with Start Basic Processing when checked; otherwise it is skipped. Pure numbers, device labels, and explanatory text are not moved.",
    "用于将仍使用旧图元几何参数的主 G 文件适配到新图元库。请分别添加本次涉及的旧图元 G 和新图元 G，程序按完全相同的文件名强制一一配对，并直接从图元文件读取 w/h、AlignCenter 和 pin(cx,cy)。任何图元只存在旧版或只存在新版、主体类型/ID 不一致、端口数量变化时都会禁止执行。处理时保持旧电气对齐中心的绝对位置不变，并把对应连接线端点移动到新图元真实 pin；不需要正常参考主 G。": "Adapt main G files using old symbol geometry to a new symbol library. Add the required old and new symbol G files; matching is strictly one-to-one by identical file name, and w/h, AlignCenter, and pin(cx,cy) are read directly from the symbol files. Processing is blocked for missing pairs, mismatched body type/ID, or changed port counts. The old electrical alignment center remains fixed and connection-line endpoints are moved to the new real pins.",
    "只处理主 G 中 devref 命中已配对图元、且当前 w/h 与旧图元尺寸完全一致的实例；已经是新尺寸的实例会跳过，未知自定义尺寸会告警并跳过。": "Process only main-G instances whose devref matches a paired symbol and whose current w/h exactly matches the old symbol size. Instances already using the new size are skipped; unknown custom sizes are warned and skipped.",
    "用于修复图形中未对齐、缺失或不完整的绿色连接点。程序采用保守增量模式：原有连接和端口编号一律保留；仅对已验证的半像素设备沿 X 方向吸附到整数网格，不修改任何连接线坐标；随后只补齐缺失的 node_area 和 link。无法唯一判断时跳过，不会修改设备 Y、ID、文字、颜色、图标、Merge、画布或其他业务属性。": "Repair misaligned, missing, or incomplete green connection points using a conservative incremental approach. Existing connections and port numbers are preserved. Only verified half-pixel devices are snapped to the integer X grid; connection-line coordinates are not changed. Missing node_area/link references are then completed. Ambiguous cases are skipped.",
    "勾选后随“开始基础处理”执行保守连接修复；不勾选时完全跳过。原有连接不会被删除或改号。": "Run conservative connection repair with Start Basic Processing when checked; otherwise skip it completely. Existing connections are never deleted or renumbered.",
    "请先在 SSH 文件列表中选择一个或多个 G 文件": "Select one or more G files in the SSH file list first.",
    "正在只读下载所选服务器 G 文件到 workspace，并扫描元素与属性……": "Downloading the selected server G files to the workspace in read-only mode and scanning elements and attributes…",
    "留空时取输入文件名，例如 JED-CTL-ADF": "Leave blank to use the input file name, for example JED-CTL-ADF.",
    "选择随 App 一起发布的内置图框模板。": "Select a built-in drawing-frame template distributed with the app.",
    "把当前内置模板复制到外部文件，便于查看或修改。": "Copy the current built-in template to an external file for review or modification.",
    "内置模板：会按四边距调整外框，并允许修改左上标题和 Draw/Approve/Issue 信息。": "Built-in template: adjusts the frame by the configured margins and allows editing the upper-left title and Draw/Approve/Issue information.",
    "客户模板：会按四边距调整外框和锚定组件位置，但不会修改任何文字、姓名、日期、字体、颜色或表格内容。": "Customer template: adjusts the frame and anchored component positions by the configured margins without changing text, names, dates, fonts, colors, or table content.",
    "尚未添加图元。旧、新图元必须按相同文件名一一对应。": "No symbols have been added. Old and new symbols must match one-to-one by identical file name.",
    "扫描输入文件或目录内 G 文件的直属 Layer 直接子元素，生成元素标签和属性名下拉选项。": "Scan direct children of the Layer in the input G file(s) and build element-tag and attribute-name drop-down lists.",
    "请选择输入文件或目录后扫描元素与属性": "Select an input file or directory, then scan elements and attributes.",
    "请输入需要匹配的旧值": "Enter the old value to match.",
    "请输入替换后的新值": "Enter the replacement value.",
    "请输入需要精确匹配的属性值": "Enter the attribute value to match exactly.",
    "元素标签": "Element Tag",
    "从输入 G 文件的直属 Layer 直接子元素中选择，也可手动输入。": "Select from direct child elements of the Layer in the input G file, or enter a value manually.",
    "从输入 G 文件直属 Layer 的直接子元素中选择，也可手动输入。": "Select from direct child elements of the Layer in the input G file, or enter a value manually.",
    "根据所选元素标签列出实际出现的属性名，也可手动输入。": "List attribute names that actually occur for the selected element tag, or enter one manually.",
    "只有属性值与旧值完全相同时才替换。": "Replace only when the attribute value exactly matches the old value.",
    "匹配成功后写入的新属性值。": "New attribute value written after a successful match.",
    "匹配元素上存在该属性时，直接删除这个属性键。": "Delete this attribute key when it exists on a matching element.",
    "只有属性值与此内容完全一致时才删除整个元素。": "Delete the entire element only when the attribute value exactly matches this content.",
    "输入路径不存在或没有 G 文件，暂时无法生成元素和属性选项": "The input path does not exist or contains no G files, so element and attribute options cannot be generated.",
    "未扫描到直属 Layer 的直接子元素；仍可手动输入标签和属性名": "No direct child elements were found in Layer. Element tags and attribute names can still be entered manually.",
    "按照当前页面参数开始处理。处理会在后台线程中运行。": "Start processing with the current page settings. The task runs in a background thread.",
    "打开本次任务对应的 workspace 运行目录。运行记录仅保留 30 天。": "Open the workspace run directory for this task. Run records are retained for 30 days.",
    "清空当前页面的执行日志，不会删除任何文件。": "Clear the execution log on this page without deleting any files.",
    "显示当前处理任务的总体进度。": "Show overall progress for the current task.",
    "<p>点击“开始执行”后，任务会在后台运行。进度条显示总体进度，详细处理过程显示在日志区域。处理失败时请复制日志中的错误信息进行排查。</p>": "<p>After you click Run, the task runs in the background. The progress bar shows overall progress and the log area shows details. If processing fails, copy the error information from the log for troubleshooting.</p>",
    "默认使用当前日期；点击右侧日历按钮可选择其他日期。": "Use the current date by default. Click the calendar button on the right to choose another date.",
    "输入文件名关键字进行模糊查询；多个关键字用空格分隔，文件名需同时包含这些关键字。只有无图框文件和 G File Studio 内置图框文件可选择；内置图框会在合并前自动移除。": "Use file-name keywords for fuzzy search. Separate multiple keywords with spaces; a file name must contain all keywords. Only files without frames and files with a G File Studio built-in frame can be selected; built-in frames are removed before merging.",
    "例如：AJWD 48；留空显示全部文件": "Example: AJWD 48; leave blank to show all files.",
    "不区分大小写；多个空格分隔关键字采用同时包含的匹配方式。": "Case-insensitive. Space-separated keywords use an AND match.",
    "取消当前选择": "Clear Current Selection",
    "确认导入": "Import Selected",
    "先点击“加载 / 检查”扫描目录。加载时会显示进度并检查图框：内置图框可参与合并，合并前会自动移除；客户或未知图框禁止参与。随后可通过“查询并导入”按文件名模糊查询、选择或全选并导入列表，再执行删除、置顶、上移、下移和置底。": "Click Load / Check to scan the directory. Progress and frame checks are shown while loading. Built-in frames may participate and are removed before merging; customer or unknown frames are blocked. Then use Search & Import to fuzzy-search by file name, select matching files, and import them into the merge list before reordering as needed.",
    "尚未加载输入目录。": "Input directory has not been loaded yet.",
    "显示加载进度，重新扫描目录并检查 XML、对齐基准和图框类型。": "Show loading progress, rescan the directory, and check XML, alignment references, and frame types.",
    "打开模糊查询窗口，输入文件名关键字，选择或全选匹配文件后导入当前列表。": "Open the fuzzy-search dialog, enter file-name keywords, select matching files, and import them into the current list.",
    "把目录中全部可参与合并的文件按自然文件名顺序导入；非内置图框和检查失败文件不会导入。": "Import every merge-eligible file in natural file-name order. Files with non-built-in frames or failed checks are not imported.",
    "从本次合并列表移除所选文件。支持 Ctrl/Shift 多选；不会删除磁盘源文件。": "Remove selected files from the current merge list. Ctrl/Shift multi-selection is supported; source files on disk are not deleted.",
    "把当前选中的一行移动到第一位，并作为合并基准文件。": "Move the selected row to the first position and use it as the merge reference file.",
    "把当前选中的一行向前移动一位。": "Move the selected row up one position.",
    "把当前选中的一行向后移动一位。": "Move the selected row down one position.",
    "把当前选中的一行移动到最后一位。": "Move the selected row to the last position.",
    "该文件已经在合并顺序列表中。": "This file is already in the merge-order list.",
    "保持原样：不修改 ls；实线：ls=1；虚线：ls=2。线型设置与颜色复选框彼此独立。": "Keep Original: do not change ls; Solid: ls=1; Dashed: ls=2. Line-style settings are independent of the color checkbox.",
    "清空全部": "Clear All",
})

# Runtime log fragments are translated conservatively. The replacements deliberately
# avoid XML identifiers and file paths.

# v2.18.3: complete English payloads for the small-element page and SSH source.
EN.update({
    "扫描 ConnectLine、FeedLine、Bus、BusDis 中疑似误画后残留的异常短线/小尺寸图元，并按用户选择删除。": "Scan ConnectLine, FeedLine, Bus, and BusDis for suspicious short/small residual elements and delete only the items selected by the user.",
    "该模块独立检查 ConnectLine、FeedLine、Bus、BusDis，不区分母线方向。默认判定为 w<10 且 h<10。扫描结果采用表格方式显示，可直接选择单个单元格或一块区域并按 Ctrl+C 复制。需要处理的图元请在首列勾选，支持单选、多选和全选。执行选中处理时会输出修改后的 G 文件，并生成带时间戳的 CSV/HTML 报告；若勾选项存在非空 keyid，会先明确提示后再确认。": "This module independently checks ConnectLine, FeedLine, Bus, and BusDis without restricting bus orientation. The default condition is w<10 and h<10. Results are shown in a table; individual cells or ranges can be selected and copied with Ctrl+C. Use the first-column checkboxes to choose elements for processing, with single, multiple, and select-all support. Processing writes a modified G file and timestamped CSV/HTML reports. If a selected item has a non-empty keyid, an explicit confirmation is required first.",
    "扫描文件与输出": "Scan Files & Output",
    "选择异常小尺寸图元报告/处理输出目录": "Select Abnormal Small Element Report/Processing Output Directory",
    "检测规则": "Detection Rule",
    "当目标元素的 w 和 h 同时小于该值时，报告为异常小尺寸图元。": "Report an element as abnormally small when both its w and h are below this value.",
    "异常图元结果": "Abnormal Element Results",
    "尚未扫描。": "Not scanned yet.",
    "处理": "Process",
    "文件": "File",
    "元素类型": "Element Type",
    "全选处理": "Select All for Processing",
    "可单独选择 XML ID 或任意单元格/区域，按 Ctrl+C 复制": "Select an XML ID or any cell/range and press Ctrl+C to copy.",
    "扫描异常图元": "Scan Abnormal Elements",
    "扫描完成后会生成/覆盖本模块的扫描 CSV/HTML 报告，可点击“打开报告”查看。": "After scanning, this module creates or replaces its scan CSV/HTML reports. Click Open Report to view them.",
    "首列勾选决定哪些图元参与处理；其余单元格可像表格一样单选/框选，按 Ctrl+C 复制。": "The first-column checkboxes determine which elements are processed. Other cells can be selected individually or as a range and copied with Ctrl+C.",
    "删除选中异常图元": "Delete Selected Abnormal Elements",
    "删除结果表中已勾选的异常小尺寸图元，生成修改后的 G 文件，并生成/覆盖处理 CSV/HTML 报告；报告会列出实际删除项。": "Delete the checked abnormal small elements, create the modified G file, and create or replace the processing CSV/HTML reports. The report lists the items actually deleted.",
    "打开报告": "Open Report",
    "IP / 主机": "IP / Host",
    "端口": "Port",
    "用户名": "Username",
    "密码": "Password",
    "远程目录": "Remote Directory",
    "测试 SSH 连接": "Test SSH Connection",
    "刷新 G 文件列表": "Refresh G File List",
    "保存 SSH 设置": "Save SSH Settings",
    "下载所选到本地…": "Download Selected Locally…",
    "尚未测试 SSH/SFTP 连接。": "SSH/SFTP connection has not been tested yet.",
    "SSH 服务器严格只读：仅列目录、读取文件属性和下载 G 文件；G File Studio 不提供上传、覆盖、重命名、删除或修改服务器文件的接口。": "The SSH server is strictly read-only: only directory listing, file metadata reading, and G-file download are allowed. G File Studio provides no upload, overwrite, rename, delete, or server-side modification operation.",
    "搜索 G 文件": "Search G Files",
    "例如：ABH-06、JED-NTH、B412": "Example: ABH-06, JED-NTH, B412",
    "尚未加载远程文件": "Remote files not loaded",
    "全选当前结果": "Select All Results",
    "取消当前结果": "Clear Current Results",
    "清空全部选择": "Clear All Selections",
    "大小": "Size",
    "服务器修改时间": "Server Modified Time",
})

RUNTIME_REPLACEMENTS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        {
            "任务已启动……": "Task started…",
            "SSH/SFTP 连接正常；远程文件源只读。已加载 ": "SSH/SFTP connected successfully. Remote access is read-only. Loaded ",
            "SSH/SFTP 连接正常：": "SSH/SFTP connected successfully to ",
            "；远程文件源为只读。": ". Remote access is read-only.",
            " 个 .g 文件。": " .g files.",
            "SSH 设置已保存；所有使用 SSH 文件源的模块将复用这组最后输入。": "SSH settings saved. All modules using the SSH file source will reuse these latest values.",
            "保存 SSH 设置失败": "Failed to Save SSH Settings",
            "SSH 端口必须是整数。": "SSH port must be an integer.",
            "SSH 连接失败": "SSH Connection Failed",
            "远程文件列表加载失败": "Failed to Load Remote File List",
            "[SSH只读] 将 ": "[SSH read-only] Downloading ",
            " 个服务器 G 文件下载为本地处理快照：": " server G files as local processing snapshots: ",
            "[SSH只读] 后续扫描/处理仅使用 workspace 本地快照，不会修改服务器文件。": "[SSH read-only] Subsequent scanning/processing uses only local workspace snapshots and never modifies server files.",
            "SSH 处理快照目录必须位于本地 workspace 中：": "The SSH processing snapshot directory must be inside the local workspace: ",
            "请先在 SSH G 文件列表中选择一个或多个文件。": "Select one or more files in the SSH G-file list first.",
            "请选择文件": "Select Files",
            "选择本地下载目录": "Select Local Download Directory",
            "下载完成": "Download Completed",
            "已下载 ": "Downloaded ",
            " 个 G 文件到：": " G files to: ",
            "总数 ": "Total ",
            " | 当前显示 ": " | Visible ",
            " | 已选择 ": " | Selected ",
            "开始扫描异常小尺寸图元，共 ": "Starting abnormal small-element scan: ",
            "扫描结果保持 ": "Scan results remain at ",
            " 个异常图元不变；本次从原始 G 重新生成并删除 ": " abnormal elements; this run regenerated output from the original G file and deleted ",
            " 个，未处理 ": ", not processed ",
            " 个；输出 G 文件 ": "; output G files: ",
            " 个。处理报告包含全部 ": ". The processing report contains all ",
            " 个原始异常图元：": " original abnormal elements: ",
            "已从原始 G 重新生成输出，并删除本次勾选的 ": "Regenerated output from the original G file and deleted the ",
            " 个异常图元；输出 ": " selected abnormal elements; output ",
            "当前扫描结果仍保留原始文件中的 ": "The current scan results still retain ",
            "再次执行时会重新读取原始 G，并按当次勾选覆盖输出文件和处理报告。": "Each run rereads the original G file and replaces output files and processing reports according to the current selection.",
            "原文件未修改；可点击“打开报告”查看本次处理报告。": "Source files are unchanged. Click Open Report to view this processing report.",
            "删除选中异常图元（": "Delete Selected Abnormal Elements (",
            "确认删除当前勾选的 ": "Confirm deletion of the currently selected ",
            " 个异常小尺寸图元吗？": " abnormal small elements?",
            "程序会生成修改后的 G 文件以及本次 CSV/HTML 报告，原文件不会覆盖。": "The application will generate modified G files and CSV/HTML reports for this run. Source files will not be overwritten.",
            "本次勾选 ": "Selected this run: ",
            " 个异常图元，其中 ": " abnormal elements, including ",
            " 个存在非空 keyid。": " with a non-empty keyid.",
            "执行后这些图元会从输出 G 文件中删除。是否继续？": "These elements will be deleted from the output G files. Continue?",
            "其余 ": "remaining ",
            " 项省略": " items omitted",
            "设置母线分组（": "Configure Bus Groups (",
            "当前母线类型：": "Current bus type: ",
            "双母线": "Double Bus",
            "单母线": "Single Bus",
            "未设置任何组；所有馈线母线保持独立。": "No bus groups are configured; all feeder buses remain independent.",
            "母线组 ": "Bus group ",
            " 至少需要 2 个馈线文件。": " requires at least 2 feeder files.",
            " 包含已不在当前合并列表中的文件，请重新设置分组。": " contains files no longer in the current merge list. Reconfigure the group.",
            " 中存在已经属于其他母线组的文件。": " contains a file that already belongs to another bus group.",
            " 的馈线必须在当前合并顺序中连续。": " must contain consecutive feeders in the current merge order.",
            "已立即删除 ID 规则 ": "ID rule deleted immediately: ",
            "开始扫描当前 G，共 ": "Starting current-G scan: ",
            "模板覆盖检查：当前 G 共发现 ": "Template coverage check: current G contains ",
            " 类带 ID 元素；模板已覆盖 ": " ID-bearing element types; templates cover ",
            " 类，未覆盖 ": " types; uncovered: ",
            " 已存在，请使用“编辑规则”。": " already exists. Use Edit Rule.",
            "确认删除 ID 规则 ": "Confirm deletion of ID rule ",
            "删除后立即生效；再次扫描到对应元素类型时会重新提醒是否添加。": "Deletion takes effect immediately. If the element type is found again, you will be prompted to add the rule again.",
            "当前 G 中有 ": "The current G file has ",
            " 个元素类型尚未被 ID 模板覆盖，但已能从现有 ID 自动识别候选前缀和总位数。": " element types not yet covered by ID templates, but candidate prefixes and total lengths can be inferred from existing IDs.",
            "是否现在逐个确认并加入模板？": "Confirm and add them to the template now?",
            "确认扫描发现的 ID 规则：": "Confirm the ID rule discovered by scanning: ",
            " 已扫描：": " scanned: ",
            " 当前最大 ": " current maximum ",
            "，下一个 ": ", next ",
            "模板要求前缀 ": "template requires prefix ",
            "、总位数 ": ", total length ",
            "不符合模板的完整 ID": "complete IDs that do not match the template",
            "本次未加入。": " not added in this run.",
            "尚未加入模板；候选前缀 ": "Not yet in template; candidate prefix ",
            "（需人工确认）": " (manual confirmation required)",
            "（必须人工确认）": " (manual confirmation required)",
            "扫描发现，待人工确认": "discovered by scan; pending manual confirmation",
            "已选择 ": "Selected ",
            " 个服务器 G 文件；点击“扫描元素与属性”后将只读下载到 workspace 并生成下拉选项": " server G files. Click Scan Elements & Attributes to download read-only snapshots to the workspace and build the drop-down options.",
            "扫描元素与属性失败：": "Element/attribute scan failed: ",
            "检测到 ": "Detected ",
            " 个同名输出文件。": " output files with duplicate names.",
            "其余 ": "remaining ",
            " 个同名文件": " duplicate-name files",
            "图形边距调整会保持源文件名不变。请选择本次处理方式。": "Drawing-margin adjustment keeps source file names unchanged. Select how to handle this run.",
            "图形边距调整现在保持源文件名不变。": "Drawing-margin adjustment now keeps the source file name unchanged.",
            "源文件：": "Source file: ",
            "目标文件：": "Target file: ",
            "为避免覆盖原始 G 文件，请选择其他输出目录。": "Choose another output directory to avoid overwriting the source G file.",
            "图框添加会保持源文件名不变。请选择本次处理方式。": "Drawing-frame processing keeps source file names unchanged. Select how to handle this run.",
            "图框添加现在保持源文件名不变。": "Drawing-frame processing now keeps the source file name unchanged.",
            "内置模板已导出到：": "Built-in template exported to: ",
            "上次导出模板使用的目录已经不存在：": "The directory used for the previous template export no longer exists: ",
            "请重新选择模板，或恢复使用程序内置模板。": "Select a template again or restore the built-in application template.",
            "图框模板不存在：": "Drawing-frame template does not exist: ",
            "请重新选择。": "Please select again.",
            "已添加 ": "Added ",
            " 种图元；完整配对 ": " symbol types; complete pairs ",
            " 种，缺失配对 ": "; missing pairs ",
            "图元配对检查通过，共 ": "Symbol-pair validation passed. Total: ",
            "查看“": "View ",
            "”说明": " help",
            "已扫描 ": "Scanned ",
            " 个文件、": " files, ",
            " 个直属图元、": " direct elements, ",
            " 种元素标签": " element tags",
            "启用或关闭规则：": "Enable or disable rule: ",
            "上次使用的": "The previously used ",
            "已经不存在：": " no longer exists: ",
            "该路径已从配置中清除，请重新选择。": "The path was removed from settings. Select it again.",
            "所在目录已经不存在：": " directory no longer exists: ",
            " 姓名": " Name",
            "填写 ": "Enter ",
            " 日期默认是当前日期；点击日历按钮可修改。": " date defaults to today; click the calendar button to change it.",
            "当前匹配 ": "Current matches: ",
            " 个，其中 ": ", including ",
            " 个可导入。": " importable.",
            "确定从本次合并列表移除所选的 ": "Remove the selected ",
            " 个文件吗？": " files from the current merge list?",
            "此操作不会删除磁盘上的源文件。可再次通过“查询并导入”加入。": "This does not delete source files on disk. They can be added again through Search & Import.",
            "已加载 ": "Loaded ",
            " 个文件：可参与 ": " files: eligible ",
            " 个（其中内置图框 ": " (built-in frames ",
            " 个，合并时自动移除）；非内置图框禁止参与 ": ", removed automatically during merge); non-built-in frames blocked ",
            " 个；检查失败 ": "; failed checks ",
            " 个。当前已导入合并列表 ": ". Currently imported into merge list: ",
            "正在加载并检查 G 文件……": "Loading and checking G files…",
            "勾选后修改 Layer 直属 <": "When checked, change the static line colors lc/lcc of direct Layer <",
            "> 的静态线色 lc/lcc；未勾选时保持原颜色。": "> elements; when unchecked, keep the original color.",
            "输入目录不存在：": "Input directory does not exist: ",
            "输入文件不存在：": "Input file does not exist: ",
            "输入文件必须以 ": "Input file must end with ",
            "输入目录中没有以 ": "No files ending with ",
            " 结尾的文件：": " were found in the input directory: ",
            "使用用户指定输出文件名：": "Using user-specified output file name: ",
            "未填写输出文件名，自动生成：": "No output file name specified; generated automatically: ",
            "输出文件已存在且不允许覆盖：": "Output file already exists and overwrite is not allowed: ",
            "模板文件不存在：": "Template file does not exist: ",
            "图框添加保持源文件名不变，禁止覆盖原始 G 文件：": "Drawing-frame processing preserves the source file name and cannot overwrite the original G file: ",
            "请更换输出目录。": "Change the output directory.",
            "[跳过] 输出目录已存在同名文件：": "[Skipped] A file with the same name already exists in the output directory: ",
            "[基础处理汇总]": "[Basic Processing Summary]",
            "[基础处理失败]": "[Basic Processing Failed]",
            "[环网柜识别]": "[RMU Recognition]",
            "[环网柜识别告警]": "[RMU Recognition Warning]",
            "[环网柜组合]": "[RMU Grouping]",
            "[环网柜组合告警]": "[RMU Grouping Warning]",
            "[取消环网柜组合]": "[Ungroup RMUs]",
            "[取消环网柜组合告警]": "[Ungroup RMU Warning]",
            "[图元版本升级]": "[Symbol Version Upgrade]",
            "[图元版本升级告警]": "[Symbol Version Upgrade Warning]",
            "[图形组合清理]": "[Graphic Group Cleanup]",
            "[馈线名称定位]": "[Feeder Name Positioning]",
            "[馈线名称定位告警]": "[Feeder Name Positioning Warning]",
            "[线路与母线样式/颜色处理]": "[Line & Bus Style/Color]",
            "[连接点修复]": "[Connection Repair]",
            "[连接点修复告警]": "[Connection Repair Warning]",
            "[连接点修复失败]": "[Connection Repair Failed]",
            "[连接点修复汇总]": "[Connection Repair Summary]",
            "[SMART环网柜外框颜色]": "[SMART RMU Frame Color]",
            "[SMR环网柜外框颜色]": "[SMR RMU Frame Color]",
            "[环网柜红色状态点]": "[RMU Red Status Point]",
            "[Bus环网柜处理]": "[Bus RMU Processing]",
            "[环网柜增强告警]": "[RMU Enhancement Warning]",
            "[ID 模板]": "[ID Template]",
            "[ID 检查]": "[ID Check]",
            "[ID 格式变化]": "[ID Format Change]",
            "[重复 ID]": "[Duplicate ID]",
            "[ID 强制修复]": "[ID Force Repair]",
            "[ID 模板修复]": "[ID Template Repair]",
            "[ID 处理失败]": "[ID Processing Failed]",
            "[ID 报告]": "[ID Report]",
            "[输出策略]": "[Output Policy]",
            "[RMU台账]": "[RMU Ledger]",
            "[RMU台账对比]": "[RMU Ledger Comparison]",
            "[环网柜图元处理报告]": "[RMU Graphic Processing Report]",
            "[RMU信息汇总报告]": "[RMU Summary Report]",
            "[SMR环网柜报告]": "[SMR RMU Report]",
            "全局强制约束已关闭，保留已有格式不符 ID；新生成 ID 仍由各业务模块按已确认模板分配。": "Global enforcement is disabled. Existing malformed IDs are preserved; new IDs are still allocated by business modules using confirmed templates.",
            "按已确认规则强制规范 ID ": "Force-normalized IDs using confirmed rules: ",
            "所有已配置类型 ID 均符合模板。": "All configured ID types comply with their templates.",
            "未发现重复 ID。": "No duplicate IDs found.",
            "无法取得稳定的服务器文件版本：": "Unable to obtain a stable server-file version: ",
            "请稍后重试。": "Try again later.",
            "XML 解析失败：": "XML parse failed: ",
            "文件 ": "File ",
            " 的 G 根节点下没有直属 Layer。": " has no direct Layer under the G root.",
            "颜色必须是 #RRGGBB 格式：": "Color must use #RRGGBB format: ",
            "不支持的线型：": "Unsupported line style: ",
            "不支持的旋转角度：": "Unsupported rotation angle: ",
            "根节点不是 G": "root node is not G",
            "没有直属 Layer": "has no direct Layer",
            "缺少有效": "missing valid ",
            "无法解析": "cannot parse",
            "已跳过": "skipped",
            "已回滚": "rolled back",
            "保留原位置": "original position preserved",
            "不一致": "mismatch",
            "未识别": "unrecognized",
            "待确认": "pending confirmation",
            "高置信度": "high confidence",
            "中等": "medium",
            "低置信度": "low confidence",
            "重复": "duplicate",
            "柜型": "cabinet type",
            "柜名": "RMU name",
            "智能": "smart",
            "普通": "normal",
            "外框": "frame",
            "状态点": "status point",
            "连接线": "connection line",
            "连接点": "connection point",
            "属性": "attribute",
            "引用": "reference",
            "成员": "member",
            "候选": "candidate",
            "成功": "succeeded",
            "失败": "failed",
            "找到": "found",
            "移动": "moved",
            "删除": "deleted",
            "修改": "modified",
            "新增": "added",
            "跳过": "skipped",
            "输入目录": "input directory",
            "输出目录": "output directory",
            "源文件": "source file",
            "目标文件": "target file",
            "生成时间": "generated at",
            "记录数": "records",
            "阈值": "threshold",
            "异常数量": "abnormal count",
            "带 keyid": "with keyid",
            "开始扫描异常小尺寸图元，共 ": "Starting abnormal small-element scan: ",
            " 个文件；阈值：": " files; threshold: ",
            "正在扫描异常短线图元……": "Scanning abnormal small elements…",
            "正在扫描：": "Scanning: ",
            "扫描已取消。": "Scan cancelled.",
            "：发现 ": ": found ",
            " 个异常图元。": " abnormal elements.",
            "扫描失败：": "Scan failed: ",
            "扫描完成：发现 ": "Scan completed: found ",
            " 个异常图元，其中 ": " abnormal elements, including ",
            " 个存在 keyid。": " with non-empty keyid.",
            "扫描完成：": "Scan completed: ",
            "报告：": "Reports: ",
            "CSV 报告：": "CSV report: ",
            "HTML 报告：": "HTML report: ",
            "[异常]": "[Abnormal]",
            "[已处理]": "[Processed]",
            "(空)": "(empty)",
            "执行处理失败：": "Processing failed: ",
            "输出 G：": "Output G: ",
            "本次独立处理：从原始 G 重新生成输出，删除 ": "Independent run: regenerated output from the original G file and deleted ",
            "扫描结果仍保留 ": "The scan results still retain ",
            " 个，不累计上一次处理状态。": " items; previous processing state is not accumulated.",
            "从原始 G 重新生成并删除 ": "regenerated from the original G file and deleted ",
            "未处理 ": "not processed ",
            "输出 G 文件 ": "output G files ",
            "处理报告包含全部 ": "The processing report contains all ",
            " 个原始异常图元": " original abnormal elements",
            "总数 ": "Total ",
            "当前显示 ": "Visible ",
            "已选择 ": "Selected ",
            "SSH 设置已保存；所有使用 SSH 文件源的模块将复用这组最后输入。": "SSH settings saved. All modules using the SSH file source will reuse these latest values.",
            "SSH/SFTP 连接失败：": "SSH/SFTP connection failed: ",
            "读取远程 G 文件列表失败：": "Failed to load remote G-file list: ",
            "请先选择一个或多个要下载到本地的 G 文件。": "Select one or more G files to download locally first.",
            "下载失败": "Download failed",
            "下载失败：": "Download failed: ",
            "发现": "found",
            "其中": "including",
            "存在": "with",
            "异常": "abnormal",
            "报告": "report",
            "已处理": "processed",
            "未处理": "not processed",
            "勾选": "selected",
            "原始": "original",
            "重新生成": "regenerated",
            "处理完成。": "Processing completed.",
            "处理失败：": "Processing failed:",
            "告警：": "Warnings:",
            "统计：": "Statistics:",
            "输出：": "Output:",
            "输入方式": "Input mode",
            "输入": "Input",
            "输出目录": "Output directory",
            "输出文件": "Output file",
            "成功": "Succeeded",
            "失败": "Failed",
            "文件": "file",
            "个文件": " files",
            "处理": "Processing",
            "扫描": "Scan",
            "完成": "completed",
            "远程": "remote",
            "只读": "read-only",
            "已确认": "Confirmed",
            "待人工确认": "Pending manual confirmation",
            "用户确认": "User confirmed",
            "扫描发现": "Detected by scan",
            "规则格式": "Rule format",
            "固定前缀": "fixed prefix",
            "总位数": "total length",
            "同类型": "same type",
            "最大": "maximum",
            "当前规则": "Current rule",
            "备注": "Notes",
            "页面帮助": "Page Help",
            "元素": "element",
            "类型": "type",
            "目录": "directory",
            "请选择": "Please select",
            "确认": "Confirm",
            "取消": "Cancel",
            "删除": "Delete",
            "修改": "Modify",
            "添加": "Add",
            "读取": "Read",
            "下载": "Download",
            "服务器": "server",
            "连接": "connection",
            "环网柜": "RMU",
            "馈线": "feeder",
            "母线": "bus",
            "图框": "drawing frame",
            "图元": "element",
            "名称": "name",
            "颜色": "color",
            "位置": "position",
            "规则": "rule",
            "模板": "template",
        }.items(),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
)


def tr(text: str, language: str = LANG_ZH) -> str:
    if language != LANG_EN or not text:
        return text
    return EN.get(text, text)


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

def contains_cjk(text: str) -> bool:
    return bool(text and _CJK_RE.search(text))

def tr_runtime(text: str, language: str = LANG_ZH) -> str:
    if language != LANG_EN or not text:
        return text

    # Dynamic merge-group strings are produced by the immutable Chinese feature code.
    # Translate their rendered form here instead of changing merge_page.py.
    group_cell = re.fullmatch(r"组(\d+)", text)
    if group_cell:
        return f"Group {group_cell.group(1)}"
    group_button = re.fullmatch(r"设置母线分组（(\d+)组）", text)
    if group_button:
        count = int(group_button.group(1))
        noun = "group" if count == 1 else "groups"
        return f"Set Bus Groups ({count} {noun})"
    group_summary = re.fullmatch(r"组(\d+): (.*?) ～ (.*?)（(\d+)个）", text)
    if group_summary:
        group_no, first_name, last_name, count_text = group_summary.groups()
        count = int(count_text)
        noun = "feeder" if count == 1 else "feeders"
        return f"Group {group_no}: {first_name} – {last_name} ({count} {noun})"

    exact = EN.get(text)
    if exact is not None:
        return exact

    translated = text

    # The confirmation dialog may contain one or more dynamic group-summary lines
    # inside a larger message, so translate those structures before generic phrase
    # replacement. This remains display-only; the underlying group lists are untouched.
    def replace_group_summary(match: re.Match[str]) -> str:
        group_no, first_name, last_name, count_text = match.groups()
        count = int(count_text)
        noun = "feeder" if count == 1 else "feeders"
        return f"Group {group_no}: {first_name} – {last_name} ({count} {noun})"

    translated = re.sub(
        r"组(\d+): ([^\n]*?) ～ ([^\n]*?)（(\d+)个）",
        replace_group_summary,
        translated,
    )
    translated = re.sub(r"设置母线分组（(\d+)组）", lambda m: f"Set Bus Groups ({m.group(1)} groups)", translated)
    translated = re.sub(r"(?<!母线)组(\d+)", lambda m: f"Group {m.group(1)}", translated)

    for source, target in RUNTIME_REPLACEMENTS:
        translated = translated.replace(source, target)
    # English mode must never leak Chinese UI text. Long-running business engines
    # still emit source-language diagnostics, so keep all already-translated technical
    # tokens/IDs/paths and remove only any residual CJK fragments as a last resort.
    # Legacy placeholder retained as a source marker for compatibility tests:
    # "Runtime message could not be fully translated."
    if contains_cjk(translated):
        translated = _CJK_RE.sub(" ", translated)
        translated = re.sub(r"[ \t]+", " ", translated)
        translated = re.sub(r" ?([，。；：]) ?", lambda m: {"，": ", ", "。": ". ", "；": "; ", "：": ": "}[m.group(1)], translated)
        translated = translated.strip()
        if not translated:
            return "Runtime message."
    return translated



def tr_for(widget: QWidget, text: str) -> str:
    """Translate dynamic user-facing text and remember its source form.

    Remembering the source makes later English/Chinese switching safe even when a
    label or button was changed dynamically after the page had already been shown.
    """
    window = widget.window() if widget is not None else None
    manager = getattr(window, "language_manager", None)
    if manager is None:
        return text
    translated = manager.runtime_text(text)
    manager.remember_runtime_translation(text, translated)
    return translated


_QMESSAGEBOX_ADD_BUTTON_ORIGINAL = None
_QMESSAGEBOX_CLICKED_BUTTON_ORIGINAL = None
_QMESSAGEBOX_BRIDGE_INSTALLED = False


def _manager_for_message_box(box: QMessageBox):
    """Resolve the active language manager without changing feature code/state."""
    parent = box.parentWidget()
    window = parent.window() if parent is not None else None
    return getattr(window, "language_manager", None)


def _install_qmessagebox_button_i18n_bridge() -> None:
    """Translate QMessageBox captions without changing feature click semantics.

    The immutable v2.17.60 feeder-merge page stores the Python button objects returned
    by ``addButton()`` and later uses ``clickedButton()`` with ``is`` identity checks.
    On some PySide6 builds, an English custom caption can make ``clickedButton()``
    surface a different Python wrapper for the same underlying Qt button.  The Chinese
    path does not hit this wrapper mismatch.

    Keep feature code untouched: in English mode we translate only the caption passed
    to Qt, remember the *exact* Python object returned by ``addButton()``, and record
    that exact object when its ``clicked`` signal fires.  ``clickedButton()`` then
    returns the recorded object.  Button roles, dialog result codes, feature state, and
    every Chinese-mode call continues to use Qt's original implementation.
    """
    global _QMESSAGEBOX_ADD_BUTTON_ORIGINAL
    global _QMESSAGEBOX_CLICKED_BUTTON_ORIGINAL
    global _QMESSAGEBOX_BRIDGE_INSTALLED
    if _QMESSAGEBOX_BRIDGE_INSTALLED:
        return

    original_add_button = QMessageBox.addButton
    original_clicked_button = QMessageBox.clickedButton
    _QMESSAGEBOX_ADD_BUTTON_ORIGINAL = original_add_button
    _QMESSAGEBOX_CLICKED_BUTTON_ORIGINAL = original_clicked_button

    def _english_manager(box):
        manager = _manager_for_message_box(box)
        return manager if manager is not None and getattr(manager, "is_english", False) else None

    def translated_add_button(box, *args):
        manager = _english_manager(box)
        translated_args = args
        if manager is not None and args and isinstance(args[0], str):
            translated_args = (manager.runtime_text(args[0]), *args[1:])
            # The custom caption is final before Qt creates the button.  Show/Paint
            # translation must never rewrite modal button widgets afterwards.
            box.setProperty("_i18n_custom_buttons_pretranslated", True)

        button = original_add_button(box, *translated_args)

        if manager is not None and button is not None:
            # Preserve the exact Python wrapper returned to feature code.  This is
            # presentation-layer compatibility only; it does not choose a result.
            refs = getattr(box, "_i18n_exact_button_refs", None)
            if refs is None:
                refs = []
                setattr(box, "_i18n_exact_button_refs", refs)
            refs.append(button)

            def remember_clicked(_checked=False, *, _box=box, _button=button):
                setattr(_box, "_i18n_exact_clicked_button", _button)

            button.clicked.connect(remember_clicked)
        return button

    def exact_clicked_button(box):
        if _english_manager(box) is not None:
            exact = getattr(box, "_i18n_exact_clicked_button", None)
            if exact is not None:
                return exact
        return original_clicked_button(box)

    QMessageBox.addButton = translated_add_button
    QMessageBox.clickedButton = exact_clicked_button
    _QMESSAGEBOX_BRIDGE_INSTALLED = True


class LanguageManager(QObject):
    languageChanged = Signal(str)

    def __init__(self, settings: UserSettingsService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        _install_qmessagebox_button_i18n_bridge()
        self.settings = settings
        language = settings.get_value("general/language", LANG_ZH).strip()
        self._language = language if language in SUPPORTED_LANGUAGES else LANG_ZH
        self._runtime_reverse: dict[str, str] = {}
        self._event_translate_guard = False

    @property
    def language(self) -> str:
        return self._language

    @property
    def is_english(self) -> bool:
        return self._language == LANG_EN

    def text(self, source: str) -> str:
        return tr_runtime(source, self._language)

    def runtime_text(self, source: str) -> str:
        return tr_runtime(source, self._language)

    def remember_runtime_translation(self, source: str, translated: str) -> None:
        if source and translated and source != translated:
            self._runtime_reverse[str(translated)] = str(source)

    def set_language(self, language: str) -> None:
        language = language if language in SUPPORTED_LANGUAGES else LANG_ZH
        if language == self._language:
            return
        self._language = language
        self.settings.set_value("general/language", language)
        self.languageChanged.emit(language)

    def _source(self, obj: QObject, key: str, current: str) -> str:
        prop = f"_i18n_{key}"
        rendered_prop = f"_i18n_{key}_rendered"
        saved = obj.property(prop)
        if saved is None:
            obj.setProperty(prop, current)
            return current

        # If a control changed after the last translation pass, promote the new
        # dynamic value to the source text. tr_for() records English -> Chinese
        # pairs, so a dynamic English label can still switch back to Chinese.
        last_rendered = obj.property(rendered_prop)
        if current != str(saved) and (last_rendered is None or current != str(last_rendered)):
            recovered = self._runtime_reverse.get(current)
            if recovered is not None:
                obj.setProperty(prop, recovered)
                return recovered
            if contains_cjk(current):
                obj.setProperty(prop, current)
                return current
        return str(saved)

    def _translate_text_property(self, obj: QObject, key: str, getter, setter) -> None:
        current = getter()
        if not isinstance(current, str):
            return
        source = self._source(obj, key, current)
        if self.is_english:
            curated = obj.property(f"_i18n_{key}_en")
            rendered = str(curated) if curated is not None else self.text(source)
        else:
            rendered = source
        setter(rendered)
        obj.setProperty(f"_i18n_{key}_rendered", rendered)

    def _translate_table_item(self, table: QTableWidget, item: QTableWidgetItem) -> None:
        """Translate one table cell while tracking dynamic source-text updates.

        Feature code is allowed to keep setting its original Chinese display strings
        (for example ``组1`` / ``未分组``).  The i18n layer remembers both the
        canonical source and the last rendered value on the item itself, so later
        business-side ``setText()`` calls are detected as new source values rather
        than being overwritten by a stale translation cached at dialog creation.
        """
        if item is None:
            return
        source_role = 0x0100 + 481
        rendered_role = 0x0100 + 482
        current = item.text()
        saved = item.data(source_role)
        last_rendered = item.data(rendered_role)
        signals_were_blocked = table.signalsBlocked()
        table.blockSignals(True)
        try:
            if saved is None:
                source = current
                item.setData(source_role, source)
            else:
                source = str(saved)
                # A value different from both the remembered source and our own last
                # rendering came from feature code. Promote it to the new source text.
                if current != source and (last_rendered is None or current != str(last_rendered)):
                    recovered = self._runtime_reverse.get(current)
                    source = recovered if recovered is not None else current
                    item.setData(source_role, source)

            rendered = self.runtime_text(source) if self.is_english else source
            item.setData(rendered_role, rendered)
            if current != rendered:
                item.setText(rendered)
        finally:
            table.blockSignals(signals_were_blocked)

    def _ensure_table_runtime_i18n(self, table: QTableWidget) -> None:
        """Install event-driven translation for table cells changed by feature code.

        QTableWidget.itemChanged is suppressed when feature code temporarily calls
        table.blockSignals(True).  The underlying item model still emits dataChanged,
        so listen there as well.  This avoids the old fallback of rescanning every
        table on every Paint event, which was especially expensive for remote-file
        tables containing thousands of rows.
        """
        if bool(table.property("_i18n_runtime_item_hook")):
            return
        table.setProperty("_i18n_runtime_item_hook", True)

        def translate_range(top_left, bottom_right, _roles=None, *, _table=table, _manager=self):
            if bool(_table.property("_i18n_runtime_item_guard")):
                return
            _table.setProperty("_i18n_runtime_item_guard", True)
            try:
                top = max(0, top_left.row())
                bottom = min(_table.rowCount() - 1, bottom_right.row())
                left = max(0, top_left.column())
                right = min(_table.columnCount() - 1, bottom_right.column())
                for row in range(top, bottom + 1):
                    for col in range(left, right + 1):
                        item = _table.item(row, col)
                        if item is not None:
                            _manager._translate_table_item(_table, item)
            finally:
                _table.setProperty("_i18n_runtime_item_guard", False)

        model = table.model()
        if model is not None:
            model.dataChanged.connect(translate_range)

    def _translate_table_widget(self, table: QTableWidget) -> None:
        self._ensure_table_runtime_i18n(table)
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                cell = table.item(row, col)
                if cell is not None:
                    self._translate_table_item(table, cell)

    def translate_widget_tree(self, root: QWidget) -> None:
        widgets: Iterable[QWidget] = [root, *root.findChildren(QWidget)]
        for widget in widgets:
            if widget.windowTitle():
                self._translate_text_property(widget, "windowTitle", widget.windowTitle, widget.setWindowTitle)
            if widget.toolTip():
                self._translate_text_property(widget, "toolTip", widget.toolTip, widget.setToolTip)
            if widget.statusTip():
                self._translate_text_property(widget, "statusTip", widget.statusTip, widget.setStatusTip)

            if isinstance(widget, QLabel):
                self._translate_text_property(widget, "text", widget.text, widget.setText)
            elif isinstance(widget, QAbstractButton):
                # Custom QMessageBox buttons may already have been translated before
                # creation by the presentation bridge. Do not rewrite them after the
                # modal button box is wired; feature code may compare clickedButton()
                # with the original returned button object.
                owner_box = widget.parentWidget()
                while owner_box is not None and not isinstance(owner_box, QMessageBox):
                    owner_box = owner_box.parentWidget()
                if not (
                    owner_box is not None
                    and bool(owner_box.property("_i18n_custom_buttons_pretranslated"))
                ):
                    self._translate_text_property(widget, "text", widget.text, widget.setText)
            elif isinstance(widget, QGroupBox):
                self._translate_text_property(widget, "title", widget.title, widget.setTitle)

            if isinstance(widget, QLineEdit) and widget.placeholderText():
                self._translate_text_property(widget, "placeholder", widget.placeholderText, widget.setPlaceholderText)
            if isinstance(widget, (QPlainTextEdit, QTextEdit)) and widget.placeholderText():
                self._translate_text_property(widget, "placeholder", widget.placeholderText, widget.setPlaceholderText)

            if isinstance(widget, QTextBrowser):
                current = widget.toHtml()
                source = self._source(widget, "html", current)
                curated = widget.property("_i18n_html_en")
                if self.is_english and curated is not None:
                    widget.setHtml(str(curated))
                else:
                    widget.setHtml(self.runtime_text(source) if self.is_english else source)
            elif isinstance(widget, QPlainTextEdit) and widget.isReadOnly():
                current = widget.toPlainText()
                source = self._source(widget, "plainText", current)
                widget.setPlainText(self.runtime_text(source) if self.is_english else source)

            if isinstance(widget, QComboBox):
                for i in range(widget.count()):
                    item = widget.itemText(i)
                    prop = f"_i18n_combo_{i}"
                    source = widget.property(prop)
                    if source is None:
                        widget.setProperty(prop, item)
                        source = item
                    widget.setItemText(i, self.text(str(source)) if self.is_english else str(source))

            if isinstance(widget, QListWidget):
                for i in range(widget.count()):
                    item = widget.item(i)
                    source = item.data(0x0100)  # Qt.UserRole without importing another enum
                    if source is None:
                        source = item.text()
                        item.setData(0x0100, source)
                    item.setText(self.text(str(source)) if self.is_english else str(source))
                    tip_source = item.data(0x0101)
                    if tip_source is None and item.toolTip():
                        tip_source = item.toolTip()
                        item.setData(0x0101, tip_source)
                    if tip_source:
                        tip = self.text(str(tip_source)) if self.is_english else str(tip_source)
                        item.setToolTip(tip)
                        item.setStatusTip(tip)

            if isinstance(widget, QTableWidget):
                self._translate_table_widget(widget)
                for col in range(widget.columnCount()):
                    item = widget.horizontalHeaderItem(col)
                    if item is None:
                        continue
                    source = item.data(0x0100)
                    if source is None:
                        source = item.text()
                        item.setData(0x0100, source)
                    item.setText(self.text(str(source)) if self.is_english else str(source))

            if isinstance(widget, QTreeWidget):
                header = widget.headerItem()
                for col in range(widget.columnCount()):
                    source = header.data(col, 0x0100)
                    if source is None:
                        source = header.text(col)
                        header.setData(col, 0x0100, source)
                    header.setText(col, self.text(str(source)) if self.is_english else str(source))

            if isinstance(widget, QTabWidget):
                for i in range(widget.count()):
                    prop = f"_i18n_tab_{i}"
                    source = widget.property(prop)
                    if source is None:
                        source = widget.tabText(i)
                        widget.setProperty(prop, source)
                    widget.setTabText(i, self.text(str(source)) if self.is_english else str(source))

            if isinstance(widget, QStatusBar):
                message = widget.currentMessage()
                if message:
                    source = self._source(widget, "status_message", message)
                    widget.showMessage(self.text(source) if self.is_english else source)

        for action in root.findChildren(QAction):
            if action.text():
                self._translate_text_property(action, "text", action.text, action.setText)
            if action.toolTip():
                self._translate_text_property(action, "toolTip", action.toolTip, action.setToolTip)

    def _translate_dynamic_presentation_widget(self, widget: QWidget) -> None:
        """Translate only rendered UI text; never read or mutate business state.

        Feature modules keep their original Chinese source strings and original control
        flow.  This method runs at the presentation boundary so runtime label/button
        updates can still appear in English without inserting translation calls into
        feeder/RMU/ID/basic processing logic.
        """
        if not self.is_english:
            return
        if widget.windowTitle() and contains_cjk(widget.windowTitle()):
            self._translate_text_property(widget, "windowTitle", widget.windowTitle, widget.setWindowTitle)
        if isinstance(widget, QLabel) and contains_cjk(widget.text()):
            self._translate_text_property(widget, "text", widget.text, widget.setText)
        elif isinstance(widget, QAbstractButton) and contains_cjk(widget.text()):
            self._translate_text_property(widget, "text", widget.text, widget.setText)
        elif isinstance(widget, QGroupBox) and contains_cjk(widget.title()):
            self._translate_text_property(widget, "title", widget.title, widget.setTitle)
        # QTableWidget cells are translated by the model.dataChanged hook installed
        # in _ensure_table_runtime_i18n(). Never rescan a whole table from Paint.

    def _translate_after_show(self, widget: QWidget) -> None:
        """Translate a newly shown widget after Qt finishes its native show handling.

        This is intentionally presentation-only.  In Chinese mode the runtime i18n
        layer does absolutely nothing to newly created dialogs/widgets, so the
        original v2.17.60 behavior is preserved exactly.  In English mode translation
        is deferred to the next event-loop turn; this avoids touching QMessageBox
        buttons while Qt is still wiring its modal button box/click handling.
        """
        if not self.is_english or self._event_translate_guard:
            return
        self._event_translate_guard = True
        try:
            self.translate_widget_tree(widget)
        finally:
            self._event_translate_guard = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if self._event_translate_guard:
            return False

        # CRITICAL: Chinese is the immutable v2.17.60 golden behavior.  Do not touch
        # runtime widgets/dialogs at all in Chinese mode.
        if not self.is_english:
            return False

        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
            and watched.isWindow()
        ):
            # All application pages are pre-created and translated once by MainWindow.
            # When a stacked page becomes visible, hundreds of child widgets receive
            # Show events; translating each child subtree again causes module-switch
            # lag. Only newly shown top-level windows/dialogs need a deferred pass.
            # QMessageBox translation is still deferred until Qt finishes wiring its
            # modal button box.
            QTimer.singleShot(0, lambda w=watched: self._translate_after_show(w))
        elif event.type() == QEvent.Type.Paint and isinstance(watched, QWidget):
            # Feature code may update display text dynamically. Translate only the
            # rendered presentation value, without changing feature-module code.
            self._event_translate_guard = True
            try:
                self._translate_dynamic_presentation_widget(watched)
            finally:
                self._event_translate_guard = False
        return False
