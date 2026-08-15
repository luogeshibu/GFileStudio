# G File Studio v2.17.35 验证报告

日期：2026-08-12

## 本次变更

- “环网柜名称与柜型识别”更名为“RMU 信息汇总”。
- 仅在 RMU 信息汇总统计层，将 SMART 与 SMR 统一归类为“智能环网柜”。
- 同一个 RMU 同时命中 SMART 与 SMR 时，智能环网柜数量只计 1 个。
- 报告新增 `IntelligentRMU` 与 `IntelligentSource`：来源可为 `SMART`、`SMR`、`SMART + SMR`。
- 原环网柜组合/取消组合、SMART/SMR 外框改色、柜名方向匹配、柜型识别算法未修改。

## 自动化测试

- `pytest -q`
- 结果：`202 passed`

## 实际 G 文件验证

使用用户提供的 `JED-NTH-ABH.sln.pic(2).g`，启用上方+下方柜名方向并统计智能环网柜：

- 有效 RMU：341
- 柜名识别：341
- 柜型识别：341
- 智能环网柜：93
- 普通环网柜：248
- 智能来源：SMART=66，SMR=17，SMART+SMR=10

注：SMART+SMR 的 10 个 RMU 在“智能环网柜”总数中各只计 1 个。
