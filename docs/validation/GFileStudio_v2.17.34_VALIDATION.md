# G File Studio v2.17.34 验证报告

## 本次范围

仅新增环网柜 SMR 外框改色能力及其报告；既有环网柜组合/取消组合、SMART、channel_status、Bus 外框、柜名/柜型识别逻辑未改。

## 实际文件验证

使用 `JED-NTH-ABH.sln.pic(2).g`：

- 直属 `Text[ts=SMR]`：27 个
- 成功匹配最近有效 RMU 外框：27 个
- 其中原本已为 `#FF0000`：4 个
- 实际需要改为红色：23 个
- SMR Text 本身不修改

## 自动化测试

`pytest -q`：**200 passed**。

## 报告

启用 SMR 外框处理时生成并覆盖：

- `rmu-smr-frame-report.csv`
- `rmu-smr-frame-report.html`
