from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFormLayout, QLineEdit, QVBoxLayout, QWidget

from g_file_studio.models import BasicSettings
from g_file_studio.ui.widgets.help_widgets import HelpLabel
from g_file_studio.ui.widgets.rule_card import RuleCard


class BasicRulesEditor(QWidget):
    """基础处理规则编辑器。

    基础处理页面和一键处理页面复用同一个组件，确保新增规则时只需维护一处 UI。
    当前只保留两个通用规则：属性替换和匹配元素删除。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.replace_attribute_rule = RuleCard(
            "替换元素属性值",
            "只在直属 Layer 的直接子元素中精确匹配并替换属性值。",
            """
<p>匹配条件为：元素标签、属性名和旧值全部一致。</p>
<p>只处理 G 根节点直属 Layer 的直接子元素；不会修改 G、Theme、Layer 外内容，也不会递归修改图元内部子元素。</p>
<p>例如：把直属 ZhaiWaiJieDiDaoZha 的 p_NameString 从 YcccD 替换为 Q1D。</p>
""",
        )
        replace_form = QFormLayout()
        replace_form.setHorizontalSpacing(16)
        replace_form.setVerticalSpacing(8)
        self.replace_tag = QLineEdit("ZhaiWaiJieDiDaoZha")
        self.replace_attribute_name = QLineEdit("p_NameString")
        self.replace_old_value = QLineEdit("YcccD")
        self.replace_new_value = QLineEdit("Q1D")
        replace_form.addRow(HelpLabel("元素标签", "需要匹配的 XML 元素标签名。"), self.replace_tag)
        replace_form.addRow(
            HelpLabel("属性名", "需要检查并修改的 XML 属性名。"),
            self.replace_attribute_name,
        )
        replace_form.addRow(HelpLabel("旧值", "只有属性值与旧值完全相同时才替换。"), self.replace_old_value)
        replace_form.addRow(HelpLabel("新值", "匹配成功后写入的新属性值。"), self.replace_new_value)
        self.replace_attribute_rule.options_layout.addLayout(replace_form)

        self.delete_element_rule = RuleCard(
            "删除匹配元素",
            "只在直属 Layer 的直接子元素中匹配；命中后删除整个元素子树。",
            """
<p>匹配条件为：元素标签、属性名和属性值全部一致。</p>
<p>该规则不是只删除一个属性，而是删除整个匹配元素及其内部子树。</p>
<p>只检查 G 根节点直属 Layer 的直接子元素；不会删除 Theme、Layer 外元素或其他位置的同名元素。</p>
<p>程序会在当前 Layer 范围内清理 link、node_area、p_FatherObjId 中指向已删除真实图元的引用。</p>
""",
        )
        self.delete_element_rule.enabled.setChecked(False)
        delete_form = QFormLayout()
        delete_form.setHorizontalSpacing(16)
        delete_form.setVerticalSpacing(8)
        self.delete_tag = QLineEdit()
        self.delete_tag.setPlaceholderText("例如 ConnectLine 或 Disconnector")
        self.delete_attribute = QLineEdit()
        self.delete_attribute.setPlaceholderText("例如 w 或 p_NameString")
        self.delete_value = QLineEdit()
        self.delete_value.setPlaceholderText("例如 137 或 D1001")
        delete_form.addRow(HelpLabel("元素标签", "要删除的 XML 元素标签，必须填写。"), self.delete_tag)
        delete_form.addRow(HelpLabel("属性名", "用于精确匹配的 XML 属性名，必须填写。"), self.delete_attribute)
        delete_form.addRow(HelpLabel("属性值", "只有属性值与此内容完全一致时才删除。"), self.delete_value)
        self.delete_element_rule.options_layout.addLayout(delete_form)

        root.addWidget(self.replace_attribute_rule)
        root.addWidget(self.delete_element_rule)

    def build_settings(self, input_dir: Path, output_dir: Path) -> BasicSettings:
        return BasicSettings(
            input_dir=input_dir,
            output_dir=output_dir,
            replace_attribute=self.replace_attribute_rule.enabled.isChecked(),
            replace_target_tag=self.replace_tag.text().strip(),
            replace_target_attribute=self.replace_attribute_name.text().strip(),
            replace_old_value=self.replace_old_value.text(),
            replace_new_value=self.replace_new_value.text(),
            delete_matching_element=self.delete_element_rule.enabled.isChecked(),
            delete_target_tag=self.delete_tag.text().strip(),
            delete_target_attribute=self.delete_attribute.text().strip(),
            delete_target_value=self.delete_value.text(),
        )
