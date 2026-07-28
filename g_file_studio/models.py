from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


MERGED_FILE_SUFFIX = ".sln.pic.g"


class BasicSettings(BaseModel):
    """基础处理参数。

    所有规则都只作用于 G 根节点直属 Layer 的直接子元素：
    - 属性替换：元素标签、属性名、旧值全部精确匹配后写入新值；
    - 元素删除：元素标签、属性名、属性值全部精确匹配后删除整个元素子树。

    G、Theme、Layer 本身、Layer 外内容，以及 Layer 图元内部的嵌套子元素均保持不变。
    """

    input_dir: Path
    output_dir: Path

    # 规则 1：替换匹配元素的属性值。
    replace_attribute: bool = True
    replace_target_tag: str = "ZhaiWaiJieDiDaoZha"
    replace_target_attribute: str = "p_NameString"
    replace_old_value: str = "YcccD"
    replace_new_value: str = "Q1D"

    # 规则 2：标签、属性名、属性值全部匹配时，删除整个直属图元子树。
    delete_matching_element: bool = False
    delete_target_tag: str = ""
    delete_target_attribute: str = ""
    delete_target_value: str = ""


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
        value = value.strip()
        if not value:
            return ""

        lower = value.lower()
        if lower.endswith(MERGED_FILE_SUFFIX):
            return value
        if lower.endswith(".sln.pic"):
            return value + ".g"
        if lower.endswith(".g"):
            value = value[:-2]
        return value + MERGED_FILE_SUFFIX


class PersonSettings(BaseModel):
    name: str = ""
    date: str = ""


class FrameSettings(BaseModel):
    input_dir: Path
    output_dir: Path
    template_file: Path
    title: str = ""
    draw: PersonSettings = Field(default_factory=PersonSettings)
    approve: PersonSettings = Field(default_factory=PersonSettings)
    issue: PersonSettings = Field(default_factory=PersonSettings)
    frame_left: int = Field(default=50, ge=0)
    frame_top: int = Field(default=50, ge=0)
    frame_right: int = Field(default=50, ge=0)
    frame_bottom: int = Field(default=50, ge=0)
    output_suffix: str = ""
    overwrite: bool = True

    def config_dict(self) -> dict[str, Any]:
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
    source_dir: Path
    work_dir: Path
    output_dir: Path
    template_file: Path
    run_basic: bool = True
    run_merge: bool = True
    run_frame: bool = True
    clear_work_dirs: bool = True
    basic: BasicSettings
    merge: MergeSettings
    frame: FrameSettings


class ProcessingResult(BaseModel):
    success: bool
    output_files: list[Path] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
