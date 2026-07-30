from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from g_file_studio.services.output_naming import normalize_merge_output_name


MERGED_FILE_SUFFIX = ".sln.pic.g"


class TemplateMode(str, Enum):
    """图框模板来源。"""

    BUILTIN = "builtin"
    CUSTOM = "custom"


class InputMode(str, Enum):
    """G 文件输入类型。"""

    SINGLE_FILE = "single_file"
    DIRECTORY = "directory"


class BasicIdAction(str, Enum):
    """基础处理中的重复 ID 操作方式。"""

    NONE = "none"
    CHECK = "check"
    REPAIR = "repair"


# 向后兼容旧代码和已有配置。
PipelineInputMode = InputMode


class BasicSettings(BaseModel):
    """基础处理参数。

    输入既可以是单个 G 文件，也可以是包含多个 G 文件的目录。

    所有规则都只作用于 G 根节点直属 Layer 的直接子元素：
    - 属性替换：元素标签、属性名、旧值全部精确匹配后写入新值；
    - 元素删除：元素标签、属性名、属性值全部精确匹配后删除整个元素子树。

    G、Theme、Layer 本身、Layer 外内容，以及 Layer 图元内部的嵌套子元素均保持不变。
    """

    source_path: Path
    input_mode: InputMode = InputMode.DIRECTORY
    output_dir: Path

    replace_attribute: bool = False
    replace_target_tag: str = ""
    replace_target_attribute: str = ""
    replace_old_value: str = ""
    replace_new_value: str = ""

    delete_matching_element: bool = False
    delete_target_tag: str = ""
    delete_target_attribute: str = ""
    delete_target_value: str = ""

    # 这些选项都由统一的“开始基础处理”按钮执行。
    id_action: BasicIdAction = BasicIdAction.NONE
    group_rmu_elements: bool = False


class MergeSettings(BaseModel):
    input_dir: Path
    output_dir: Path
    output_name: str = ""
    # App 中由用户定义的合并顺序；为空时由引擎按文件名自然排序。
    ordered_file_names: list[str] = Field(default_factory=list)
    feeder_gap: int = Field(default=300, ge=0)
    left_margin: int = Field(default=300, ge=0)
    top_margin: int = Field(default=300, ge=0)
    right_margin: int = Field(default=300, ge=0)
    bottom_margin: int = Field(default=300, ge=0)

    @field_validator("output_name")
    @classmethod
    def normalize_output_name(cls, value: str) -> str:
        """合并结果统一使用 .sln.pic.g 后缀。"""
        return normalize_merge_output_name(value)


class MarginSettings(BaseModel):
    """主体图形四边距调整参数。

    仅可确认的 G File Studio 内置图框会被排除在主体边界计算之外，并在新画布上
    保留原四边距、同步拉伸外框和移动附属组件；其他图框要求用户先删除。
    """

    source_path: Path
    input_mode: InputMode = InputMode.DIRECTORY
    output_dir: Path
    left_margin: int = Field(default=500, ge=0)
    top_margin: int = Field(default=500, ge=0)
    right_margin: int = Field(default=500, ge=0)
    bottom_margin: int = Field(default=500, ge=0)
    preserve_existing_frame: bool = True
    output_suffix: str = "-ADJUSTED"
    append_timestamp: bool = True
    task_timestamp: str = ""
    overwrite: bool = True


class PersonSettings(BaseModel):
    name: str = ""
    date: str = ""


class FrameSettings(BaseModel):
    """图框添加参数。

    输入既可以是单个 G 文件，也可以是包含多个 G 文件的目录。
    输出始终写入 output_dir，原始文件不会被覆盖。
    """

    source_path: Path
    input_mode: InputMode = InputMode.DIRECTORY
    output_dir: Path
    template_file: Path
    template_mode: TemplateMode = TemplateMode.BUILTIN
    builtin_template_id: str = "default_sld_frame"
    title: str = ""
    draw: PersonSettings = Field(default_factory=PersonSettings)
    approve: PersonSettings = Field(default_factory=PersonSettings)
    issue: PersonSettings = Field(default_factory=PersonSettings)
    frame_left: int = Field(default=50, ge=0)
    frame_top: int = Field(default=50, ge=0)
    frame_right: int = Field(default=50, ge=0)
    frame_bottom: int = Field(default=50, ge=0)
    output_suffix: str = "-WITH-FRAME"
    append_timestamp: bool = True
    task_timestamp: str = ""
    overwrite: bool = True

    @property
    def edit_builtin_content(self) -> bool:
        """仅内置模板允许替换标题、姓名与日期。"""
        return self.template_mode == TemplateMode.BUILTIN

    def config_dict(self) -> dict[str, Any]:
        """生成内置模板的标题与签字栏配置。

        自定义模板模式不会使用这些配置，但保留同一数据结构，便于 UI 和配置文件复用。
        """
        return {
            "default": {
                "title": self.title,
                "draw": self.draw.model_dump(),
                "approve": self.approve.model_dump(),
                "issue": self.issue.model_dump(),
            },
            "files": {},
        }


class PipelineSettings(BaseModel):
    source_path: Path
    input_mode: InputMode = InputMode.DIRECTORY
    temp_work_dir: Path
    output_dir: Path
    run_basic: bool = True
    run_merge: bool = True
    run_margin: bool = True
    run_frame: bool = True
    basic: BasicSettings
    merge: MergeSettings
    margin: MarginSettings
    frame: FrameSettings


class ProcessingResult(BaseModel):
    success: bool
    output_files: list[Path] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
