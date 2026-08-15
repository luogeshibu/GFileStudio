# G File Studio v2.17.41 验证报告

## 本次范围
仅增强 RMU 信息汇总中的柜型识别/交叉校验；未修改 RMU 组合/取消组合、SMART/SMR 外框处理、台账对比、ID、馈线合并等其他业务逻辑。

## 柜型双源规则
1. Y/Q 文字源：柜内 `Y1/Y2/...` 数量计为 L，`Q1/Q2/...` 数量计为 T，并检查编号是否从 1 连续递增。
2. devref 图元源：`CBreakerDis.devref` 中 `Load_Breaker*` 计为 L，`Circuit_Breaker*` 计为 T。
3. 两种来源同时存在时交叉校验：一致=PASS；类型不一致或 Y/Q 序号不连续=FAIL；只有单一来源/需要回退=WARN。
4. 最终柜型仍保持 Y/Q 优先；某一类 Y/Q 完全缺失时才用 devref 对应类别回退。

## 柜名匹配
继续采用全局一对一名称分配：所有有效 RMU 同时参与 Text 归属；仍严格只使用用户勾选的上/下/左/右方向，未选方向不参与；单候选直接采用，多候选绿色优先。

## 报告新增字段
`TypeSource`、`TextYQType`、`DevrefType`、`TypeCrossCheck`、`TypeValidationStatus`、`TypeCrossNote`；HTML 同步显示中文列名和 PASS/WARN/FAIL 汇总。

## 实际文件验证
文件：`JED-NTH-ABH-03.sln.pic.g`
- 有效 RMU：17
- 柜名识别：17/17
- 柜型识别：17/17
- Y/Q 与 devref 交叉校验 PASS：17
- WARN：0
- FAIL：0

## 自动化测试
`223 passed`

## 源码检查
`python -m compileall -q g_file_studio`：通过。
