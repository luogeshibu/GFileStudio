# v2.14.0 验证结果

## 自动化测试

- `pytest -q`：100 项全部通过。
- 覆盖 channel_status 八个框内锚点、模型配置、UI 控件、真实 MAK G 文件回归，以及原有基础处理、环网柜组合、合并、边距和图框功能。

## 用户提供 G 文件回归

输入：`MAK-XXX-ARF2-14-GVCM-22-ARF4X-318.sln.pic.g`

配置：

- 启用“移动环网柜红色状态点（channel_status）”；
- 位置：左下角；
- 距边：5 像素。

结果：

- 识别带 BusDis 的环网柜：17 个；
- 找到 channel_status 红色状态点：17 个；
- 实际移动：17 个；
- 未找到：0 个；
- XML 对比显示只有这 17 个 `<Status>` 发生变化；
- 变化属性仅为 `x` 和 `y`；
- 所有 `rect`、`BusDis`、设备、文字、连接线、Merge、ID、devref、宽高和画布属性保持不变。
