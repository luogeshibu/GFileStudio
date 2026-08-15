# G File Studio v2.17.36 Validation

## Scope
本版本只在 RMU 信息汇总层新增“现有 RMU 台账对比”，未修改既有 RMU 图形识别和图元处理算法。

## New behavior
- 台账输入方式：Excel/CSV、直接粘贴表格、只粘贴 RMU 名称。
- 名称必填；柜型、是否智能可选。
- SMART / SMR 统一归类为智能环网柜进行台账比较，并保留来源字段。
- 对比输出：`rmu-ledger-comparison.csv`、`rmu-ledger-comparison.html`；同类报告覆盖上一份。
- 对比状态：完全一致、柜型不一致、智能属性不一致、图形缺失、台账缺失、图形名称重复、台账名称重复、图形柜名未识别。

## Verification
- `python -m py_compile`：models、RMU ledger service、basic processor、RMU page 均通过。
- `pytest -q`：**207 passed**。
- 新增单元测试覆盖：粘贴表格、仅名称、Excel 读取、差异比较、报告覆盖、3 种 UI 输入方式源码检查。

## Compatibility
原有柜名方向限定、单候选直接采用、多候选绿色优先、Y/Q 柜型识别、RMU 组合/取消组合、SMART/SMR 外框处理均未改动。
