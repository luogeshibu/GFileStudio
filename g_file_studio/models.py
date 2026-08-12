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


class IdAction(str, Enum):
    """独立 ID 模块操作。"""

    CHECK = "check"
    REPAIR = "repair"

class RmuAction(str, Enum):
    """基础处理中的环网柜组合操作。"""

    NONE = "none"
    GROUP = "group"
    UNGROUP = "ungroup"


class RmuStatusPosition(str, Enum):
    """环网柜 channel_status 红色状态点在矩形框内的锚点位置。"""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"

    @property
    def label(self) -> str:
        return {
            self.TOP_LEFT: "左上角",
            self.TOP_CENTER: "上边中点",
            self.TOP_RIGHT: "右上角",
            self.MIDDLE_LEFT: "左边中点",
            self.MIDDLE_RIGHT: "右边中点",
            self.BOTTOM_LEFT: "左下角",
            self.BOTTOM_CENTER: "下边中点",
            self.BOTTOM_RIGHT: "右下角",
        }[self]


class BasicOutputConflictAction(str, Enum):
    """基础处理输出文件发生冲突时的处理方式。"""

    OVERWRITE = "overwrite"
    TIMESTAMP = "timestamp"


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

    # 删除元素上的某个属性本身，不删除元素。
    delete_attribute: bool = False
    delete_attribute_target_tag: str = ""
    delete_attribute_name: str = ""

    delete_matching_element: bool = False
    delete_target_tag: str = ""
    delete_target_attribute: str = ""
    delete_target_value: str = ""

    # 图元版本升级适配：旧、新图元 G 必须按同名文件一一配对。
    upgrade_icon_geometry: bool = False
    old_icon_files: list[Path] = Field(default_factory=list)
    new_icon_files: list[Path] = Field(default_factory=list)

    # 勾选后仅做保守的设备半像素吸附，并补齐缺失的 node_area/link。
    repair_connection_points: bool = False
    # 仅依据 Bus/Text 几何和文字特征，将唯一可确认的馈线名称移到主母线正上方。
    move_feeder_titles_above_bus: bool = False
    rmu_action: RmuAction = RmuAction.NONE
    # 兼容 v2.7/v2.8 代码；为 True 且 rmu_action=NONE 时按 GROUP 处理。
    group_rmu_elements: bool = False

    # 线路与母线静态线色。颜色使用 #RRGGBB；仅启用的类型会被修改。
    change_feedline_color: bool = False
    feedline_color: str = "#0000FF"
    change_connectline_color: bool = False
    connectline_color: str = "#0000FF"
    change_busdis_color: bool = False
    busdis_color: str = "#0000FF"
    change_bus_color: bool = False
    bus_color: str = "#0000FF"

    # 环网柜增强处理。可与组合/取消组合同时启用。
    # 仅修改“框内存在 SMART Text”的环网柜外框颜色，不修改 SMART 字体。
    change_smart_rmu_frame_color: bool = False
    smart_rmu_frame_color: str = "#00A651"
    # 根据直属 Text[ts=SMR] 与最近有效环网柜 rect 的几何关系修改外框颜色；不修改 SMR Text。
    change_smr_rmu_frame_color: bool = False
    smr_rmu_frame_color: str = "#FF0000"
    # 将 BusDis 环网柜内 devref 指向 channel_status 的红色状态点移动到框内指定锚点。
    reposition_channel_status: bool = False
    channel_status_position: RmuStatusPosition = RmuStatusPosition.BOTTOM_LEFT
    channel_status_inner_margin: int = Field(default=5, ge=0, le=1000)
    remove_bus_rmu_frame_and_reposition_title: bool = False

    # 环网柜名称与柜型识别。只读取/统计，不修改 G 图元。
    identify_rmu_name_and_type: bool = False
    rmu_name_top: bool = True
    rmu_name_bottom: bool = False
    rmu_name_left: bool = False
    rmu_name_right: bool = False
    rmu_smart_in_type: bool = False
    export_rmu_identification_csv: bool = True

    output_conflict_action: BasicOutputConflictAction = BasicOutputConflictAction.OVERWRITE
    task_timestamp: str = ""




class IdSettings(BaseModel):
    """独立 ID 规则模板模块参数。"""

    source_path: Path
    input_mode: InputMode = InputMode.DIRECTORY
    output_dir: Path
    action: IdAction = IdAction.CHECK
    output_conflict_action: BasicOutputConflictAction = BasicOutputConflictAction.OVERWRITE
    task_timestamp: str = ""

class ConnectionRepairSettings(BaseModel):
    """连接点修复参数。

    该独立操作只允许修改 ``node_area`` 和 ``link``，其他图元属性保持不变。
    """

    source_path: Path
    input_mode: InputMode = InputMode.DIRECTORY
    output_dir: Path
    output_conflict_action: BasicOutputConflictAction = BasicOutputConflictAction.OVERWRITE
    task_timestamp: str = ""


class MergeSettings(BaseModel):
    input_dir: Path
    output_dir: Path
    output_name: str = ""
    # App 中由用户定义的合并顺序；为空时由引擎按文件名自然排序。
    ordered_file_names: list[str] = Field(default_factory=list)
    feeder_gap: int = Field(default=300, ge=0)
    feeder_min_width: int = Field(default=1000, ge=0)
    merge_main_bus: bool = False
    main_bus_mode: str = "single"
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



class ProcessingResult(BaseModel):
    success: bool
    output_files: list[Path] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
