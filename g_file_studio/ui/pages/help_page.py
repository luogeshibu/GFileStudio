from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser

from g_file_studio.ui.help_content import APP_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import InfoBanner


class HelpPage(BasePage):
    def __init__(self, parent=None) -> None:
        help_title, help_html = APP_HELP["help"]
        super().__init__(
            "帮助中心",
            "查看推荐流程、页面用途、目录说明和常见问题。按 F1 可随时打开本页面。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner("鼠标停留在按钮或字段上可以查看简短提示；圆形问号可查看详细说明。")
        )

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMinimumHeight(560)
        browser.setHtml(
            """
<h2>G File Studio 使用说明</h2>
<h3>1. 基础处理</h3>
<p>包含通用属性替换、元素删除、重复 ID 检查与修复、环网柜图元处理，以及线路和母线颜色修改。所有规则只作用于 G 根节点直属 Layer 的直接子元素。</p>
<p>含 SMART 的环网柜着色只修改对应 rect 外框，不修改 SMART 字体或其他环网柜。</p>
<h3>2. 馈线图合并</h3>
<p>把待合并文件放入任意目录即可。文件名无需包含站点或馈线号，但必须以 <b>.sln.pic.g</b> 结尾。</p>
<ul>
<li>扫描后可使用上移、下移、置顶、置底自由定义顺序；未调整时使用自然排序。</li>
<li>有顶部水平母线时按母线对齐。</li>
<li>没有母线时按最高图元对齐。</li>
<li>G File Studio 内置图框会在内存副本中移除后参与合并；客户或未知图框禁止参与。</li>
</ul>
<h3>3. 图形边距调整</h3>
<p>主体图形默认距离画布四边各 500；G File Studio 内置图框会保留并同步调整，不修改其文字和签字内容。客户图框或来源不明的图框需先删除。</p>
<h3>4. 图框添加</h3>
<p>适合给没有图框的文件添加 SLD 图框、标题和签字信息；默认输出名包含 -WITH-FRAME-时间戳。</p>
<h3>目录建议</h3>
<pre>
workspace/input      原始输入
workspace/processed  基础处理结果
workspace/merged     合并结果
workspace/adjusted   图形边距调整结果
workspace/output     最终输出
workspace/logs       日志
</pre>
<h3>文件安全</h3>
<ul>
<li>输入文件不会被直接覆盖。</li>
<li>输出写入临时文件后会重新解析 XML，验证通过再保存。</li>
<li>建议使用 Git 管理源码，不要提交 .venv 和 workspace 中的业务文件。</li>
</ul>
<h3>路径记忆</h3>
<p>完整路径保存在 AppData 下的独立 user_settings.ini。程序会恢复单文件/目录模式、输入路径、输出目录和客户模板路径；失效路径会提示并清除。</p>
<h3>未来扩展</h3>
<p>新的 G 文件规则优先集成到基础处理页，通过统一的“开始基础处理”按钮执行。</p>
"""
        )
        self.layout.addWidget(browser, 1)
