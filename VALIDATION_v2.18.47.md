# G File Studio v2.18.47 验证报告

## 基线
- 基于 v2.18.46。
- 不修改原有 RMU 识别、ID、馈线、基础处理、SMART/NORMAL 分类与图元升级算法。

## 本次修改
- 图元标准检查 HTML 报告新增逐元素不符合明细。
- 每条明细包含当前值、标准值、具体原因、元素 ID/RMU/关联线等定位信息。
- 新增 `symbol-standard-check-details.csv`。
- 汇总 HTML 精简为文件级关键指标，避免超宽纯数字表。
- 不符合总数按唯一元素计数。

## 自动化验证
- `pytest -q`：369 passed，2 skipped。
- 新增 `tests/test_v21847_symbol_standard_report_details.py`，验证 SMART/NORMAL 变体错误会在 HTML/CSV 中明确输出原因、当前 devref、标准 devref 和元素 ID。

## 只读边界
- 图元标准检查仍不写回、不覆盖、不生成 final G。
