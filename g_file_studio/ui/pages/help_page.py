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
<h3>1. 一键处理</h3>
<p>适合从原始 G 文件直接生成最终交付文件。可自由关闭不需要的阶段。</p>
<h3>2. 基础处理</h3>
<p>当前包含两个通用规则：按标签/属性名/旧值替换属性，以及按标签/属性名/属性值删除整个匹配元素。删除和替换只作用于 G 根节点直属 Layer 的直接子元素，其他 XML 内容保持不变。</p>
<h3>3. G 文件合并</h3>
<p>把待合并文件放入任意目录即可。文件名无需包含站点或馈线号，但必须以 <b>.sln.pic.g</b> 结尾。</p>
<ul>
<li>扫描后可使用上移、下移、置顶、置底自由定义顺序；未调整时使用自然排序。</li>
<li>有顶部水平母线时按母线对齐。</li>
<li>没有母线时按最高图元对齐。</li>
<li>输入文件不能包含外框架图，外框必须在合并后统一添加。</li>
</ul>
<h3>4. 添加图框</h3>
<p>适合给已经合并完成的文件添加 SLD 图框、标题和签字信息。</p>
<h3>目录建议</h3>
<pre>
workspace/input      原始输入
workspace/processed  基础处理结果
workspace/merged     合并结果
workspace/work       一键流程中间文件
workspace/output     最终输出
workspace/logs       日志
</pre>
<h3>文件安全</h3>
<ul>
<li>输入文件不会被直接覆盖。</li>
<li>输出写入临时文件后会重新解析 XML，验证通过再保存。</li>
<li>建议使用 Git 管理源码，不要提交 .venv 和 workspace 中的业务文件。</li>
</ul>
<h3>未来扩展</h3>
<p>基础处理页和一键处理页复用同一个规则编辑组件。新增基础规则时只需扩展该组件、设置模型和 Processor。</p>
"""
        )
        self.layout.addWidget(browser, 1)
