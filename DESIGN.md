# G File Studio v2.17.1 设计说明

## 馈线名称定位引擎

配置字段：

```text
BasicSettings.move_feeder_titles_above_bus
```

默认 `False`，由基础处理页面复选框控制。

### 模型无关识别

引擎不读取 `key_name`、`keyid` 或任何数据库关联信息。输入可以是尚未关联模型的原始 G 文件。可用信息仅包括：

```text
Bus: tag、x1/y1/x2/y2 或 d
Text: ts、x/y/w/h、fs、p_FontHeight、rotate
rect: 仅用于降低框内设备文字的候选优先级
```

### Bus 过滤与分组

- 仅处理 Layer 直属、标签严格为 `<Bus>` 的图元；
- 水平误差不超过 1.5 像素；
- 长度不少于 40 像素；
- 双母线分组要求 Y 距离不超过 35 像素、短边重叠率不少于 65%、长度比例不少于 65%，且中心 X 足够接近。

### Text 候选评分

硬排除：纯数字/小数/括号数字、单位、Y/Q/D/K 编号、SMART、SMR、N.O.P、旋转文字和小字号文字。

剩余候选按下列因素评分：

- 与母线的垂直距离；
- 与母线中心的水平距离；
- 字号；
- 是否同时含字母、数字和分隔符；
- 下划线及 UPDATED/MEASUREMENT/STATUS 等说明文字惩罚；
- 文字宽度是否远大于母线；
- 是否位于 rect 内。

候选必须是该母线组的最佳候选，同时该 Text 也必须以该母线组为最佳归属；第一、第二候选分差不足 45 时跳过。

### 目标坐标与安全约束

```text
new_x = bus_group_center_x - text_width / 2
new_y = top_bus_y - text_height - gap
```

默认 gap 为 18 像素。若目标与其他 Text 明显重叠，依次尝试 30、42、54、66、78、90 像素间距。仍冲突则跳过。

处理前后逐属性比较，允许变化的属性严格限定为 `x` 和 `y`；发现其他属性变化时立即回滚该 Text。

---

# G File Studio v2.16.1 设计说明

## 连接点修复引擎

### 核心不变量

`BasicSettings.repair_connection_points` 仍由基础处理复选框控制。v2.16.1 将下列条件作为输出前硬校验：

```text
原文件中的每一个 node_area/link 三元组必须在输出中原样存在
```

因此引擎不再调用全量替换逻辑，也不会清理或重建已有设备连接。任何原连接缺失或端口编号变化都会抛出错误并阻止该文件输出。

### 端口模板

模板签名为：

```text
tag + devref + rotate + width + height
```

动态学习只使用设备与连接线双向一致的引用样本，并保留设备已有 `own_port`。这避免 v2.16.0 按端口坐标排序后把端口 0、1 交换的问题。实际文件学习模板优先于内置模板。

### 水平吸附

- 只处理正半像素 X，例如 `2111.5 → 2111`；
- 不移动整数坐标设备，不自动处理大于 0.5 像素的偏差；
- 不修改连接线首尾端点或路径；
- 移动前使用所有可建模的原连接进行验证；
- 任一原连接在候选位置无法落入容差时，当前设备跳过，其他设备继续。

### 引用修复顺序

1. 设备已有引用 → 补连接线 `node_area/link`；
2. 连接线已有引用 → 补设备 `node_area`；
3. 对未占用端点执行唯一几何匹配；
4. 补母线和连接线交汇点的缺失反向引用；
5. 输出前检查原引用集合完整保留。

所有写入均采用“目标不存在才追加”的 add-only 语义。若目标已存在，无论端口值是否与推断结果不同，都保留原值并不覆盖。

### 允许修改范围

```text
设备：x、node_area
ConnectLine / FeedLine：node_area、link
Bus / BusDis：node_area
```

连接线 `d/x/y/w/h/x1/y1/x2/y2` 在本版本中被冻结。

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

- 连接点复选框：`修复连接点（补齐 node_area / link）`，默认不选；
- 复选框：`移动环网柜红色状态点（channel_status）`；
- 位置：防滚轮 `WheelSafeComboBox`，提供八个锚点；
- 距边：防滚轮 `IntegerInput`，默认 5，范围 0～1000；
- 默认选择“左下角”，对应用户示意图中的目标位置。
