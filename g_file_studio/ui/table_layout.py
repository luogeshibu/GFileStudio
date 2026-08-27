from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget


@dataclass(frozen=True)
class _DenseTableProfile:
    headers: tuple[str, ...]
    minimum_widths: tuple[int, ...]
    maximum_widths: tuple[int | None, ...]
    minimum_row_height: int = 36


# Canonical source labels are Chinese because feature pages keep Chinese as their
# source-language strings and the i18n presentation layer translates at runtime.
_DENSE_TABLE_PROFILES: tuple[_DenseTableProfile, ...] = (
    _DenseTableProfile(
        headers=("状态", "元素类型", "ID 起始前缀", "总位数", "合法示例", "当前规则", "备注"),
        minimum_widths=(92, 150, 118, 86, 145, 260, 280),
        maximum_widths=(120, 240, 150, 100, 220, 380, 560),
        minimum_row_height=38,
    ),
    _DenseTableProfile(
        headers=("现场", "Profile 名称", "版本", "状态", "SMART LBS", "SMART CB", "SMART 接地刀闸", "NORMAL LBS", "NORMAL CB", "NORMAL 接地刀闸", "样本", "置信度", "Profile 状态"),
        minimum_widths=(120, 155, 76, 96, 185, 180, 220, 185, 180, 220, 68, 86, 130),
        maximum_widths=(190, 240, 90, 120, 280, 280, 320, 280, 280, 320, 82, 100, 170),
        minimum_row_height=38,
    ),
    _DenseTableProfile(
        headers=("RMU 类型", "设备角色", "标准图元", "置信度", "状态"),
        minimum_widths=(96, 150, 560, 88, 96),
        maximum_widths=(120, 190, 980, 105, 120),
        minimum_row_height=46,
    ),
    _DenseTableProfile(
        headers=("适用范围", "标准名称", "版本", "状态", "内置 RMU 标准", "自定义设备图元", "样本", "置信度", "标准状态"),
        minimum_widths=(120, 155, 76, 96, 125, 130, 68, 86, 125),
        maximum_widths=(190, 240, 90, 120, 180, 200, 82, 100, 170),
        minimum_row_height=38,
    ),
    _DenseTableProfile(
        headers=("范围", "设备角色", "XML 元素", "标准图元 devref", "主体 ID", "w×h", "AlignCenter", "Pins", "匹配属性", "当前/旧图元匹配值", "置信度", "状态"),
        minimum_widths=(90, 145, 170, 420, 180, 90, 120, 230, 120, 300, 90, 100),
        maximum_widths=(110, 220, 260, 720, 300, 120, 170, 420, 150, 560, 110, 130),
        minimum_row_height=46,
    ),
)


def _canonical_headers(table: QTableWidget) -> tuple[str, ...]:
    result: list[str] = []
    for column in range(table.columnCount()):
        item = table.horizontalHeaderItem(column)
        if item is None:
            result.append("")
            continue
        # The language manager stores the canonical source text in Qt.UserRole.
        source = item.data(int(Qt.ItemDataRole.UserRole))
        result.append(str(source) if source is not None else item.text())
    return tuple(result)


def _profile_for(table: QTableWidget) -> _DenseTableProfile | None:
    headers = _canonical_headers(table)
    for profile in _DENSE_TABLE_PROFILES:
        if headers == profile.headers:
            return profile
    return None


def configure_known_dense_table(table: QTableWidget) -> bool:
    """Apply readable dense-table behavior to known engineering tables.

    This is intentionally presentation-only. It does not alter table data,
    selection, editability, sorting, or any feature/business logic.
    """
    profile = _profile_for(table)
    if profile is None:
        return False

    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionsMovable(False)
    header.setMinimumSectionSize(48)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setTextElideMode(Qt.TextElideMode.ElideRight)

    # Give every dense table its own explicit left/right scrollbar.  The page-level
    # vertical scrollbar remains independent, so users do not need to drag the
    # whole page horizontally just to inspect a long devref or note.
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)

    fit_known_dense_table(table)
    return True


def fit_known_dense_table(table: QTableWidget) -> bool:
    profile = _profile_for(table)
    if profile is None:
        return False

    # ResizeToContents is useful for short engineering values, but long devrefs and
    # notes can become thousands of pixels wide. Fit first, then clamp each column
    # to a readable range. Users can still drag headers manually afterwards.
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):
        width = table.columnWidth(column)
        if column < len(profile.minimum_widths):
            width = max(width, profile.minimum_widths[column])
        if column < len(profile.maximum_widths):
            maximum = profile.maximum_widths[column]
            if maximum is not None:
                width = min(width, maximum)
        table.setColumnWidth(column, width)

    # QTableWidget does not automatically reserve enough vertical space for a
    # cellWidget.  With the application stylesheet a QComboBox needs more height
    # than the default table row; otherwise its text/frame is visibly clipped.
    # Keep this entirely in the presentation helper so feature pages and business
    # logic remain untouched.
    for row in range(table.rowCount()):
        row_height = profile.minimum_row_height
        for column in range(table.columnCount()):
            cell_widget = table.cellWidget(row, column)
            if cell_widget is None:
                continue
            row_height = max(
                row_height,
                cell_widget.sizeHint().height() + 8,
                cell_widget.minimumSizeHint().height() + 8,
            )
        table.setRowHeight(row, row_height)
    return True


def schedule_fit_known_dense_table(table: QTableWidget) -> None:
    """Coalesce multiple cell updates into one post-update column fit."""
    if _profile_for(table) is None:
        return
    if bool(table.property("_dense_table_fit_pending")):
        return
    table.setProperty("_dense_table_fit_pending", True)

    def _fit() -> None:
        table.setProperty("_dense_table_fit_pending", False)
        fit_known_dense_table(table)

    QTimer.singleShot(0, _fit)
