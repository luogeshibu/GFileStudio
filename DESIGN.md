# G File Studio v2.14.0 设计说明

## 基线与删除项

本版本以 v2.13.2 为基线，彻底移除 BusDis 环网柜垂直间距配置、界面控件、处理日志和整体 Y 平移引擎。旧配置键即使仍存在于用户设置中，也不会再被读取或执行。

## channel_status 状态点定位

配置字段：

```text
BasicSettings.reposition_channel_status
BasicSettings.channel_status_position
BasicSettings.channel_status_inner_margin
```

### 环网柜识别

程序只处理直属 `Layer` 下的 `rect`，且该 rect 内必须存在直属 `<BusDis>`。每个柜体按几何范围寻找 `devref` 包含 `channel_status.zt.icn.g:channel_status` 的直属 `<Status>`。

优先选择中心点位于 rect 内的状态点；为兼容旧图中状态点压在线框上的情况，也允许在 rect 外扩 40 像素范围内选择。候选超过一个时，选择距离本柜 BusDis 中心最近的状态点，并确保同一个 Status 不会分配给多个柜体。

### 八个框内锚点

支持：

```text
top_left      top_center      top_right
middle_left                   middle_right
bottom_left   bottom_center   bottom_right
```

目标坐标由 rect 边界、Status 实际宽高和用户内边距计算。默认 `bottom_left`，内边距 5 像素。

### 坐标修改范围

只对选中的 Status 做二维刚体平移：

```text
x / x1 / x2 / cx / mergex
y / y1 / y2 / cy / mergey
d 路径坐标（若存在）
```

不修改宽高、颜色、ID、devref、业务属性、旋转、缩放，也不修改 rect、BusDis、设备、文字、连接线、Merge 或画布。

## UI

- 复选框：`移动环网柜红色状态点（channel_status）`；
- 位置：防滚轮 `WheelSafeComboBox`，提供八个锚点；
- 距边：防滚轮 `IntegerInput`，默认 5，范围 0～1000；
- 默认选择“左下角”，对应用户示意图中的目标位置。
