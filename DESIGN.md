# G File Studio v2.8.0 设计说明

## 1. 基线与范围

本版本基于 v2.7.0，保留 ID 选择模式和环网柜组合，仅新增两类修复：

- 图形边距调整按真实可见几何边界严格计算四边距；
- ID 操作和图框模板模式使用更醒目的互斥复选框。

## 2. 线状图元边界规则

以下标签视为线状图元：

```text
ConnectLine、Line、Bus、BusDis、FeedLine、FlowLine、Polyline、LWPolyline
```

边界优先级：

```text
1. d 路径中的全部坐标点
2. x1/y1/x2/y2 端点
3. 仅使用 x/y 作为退化点
```

禁止使用 `x + w`、`y + h` 计算线状图元的真实范围，以避免 `ConnectLine w="5000"` 等内部参数扩大画布。

## 3. 严格四边距验证

主体边界采用整数像素外包矩形：

```text
left=floor(真实左边界)
top=floor(真实上边界)
right=ceil(真实右边界)
bottom=ceil(真实下边界)
```

平移和画布计算后必须满足：

```text
主体 left = 用户左边距
主体 top = 用户上边距
画布宽度 - 主体 right = 用户右边距
画布高度 - 主体 bottom = 用户下边距
```

验证执行两次：内存处理完成后一次，临时 XML 写出并重新解析后一次。

## 4. 互斥复选框

`QButtonGroup.setExclusive(True)` 管理复选框，使其保留单选行为。带 `optionChoice=true` 属性的复选框使用独立卡片样式，选中时显示蓝色边框、浅蓝背景和清晰勾选图标。

## 5. 基础处理执行顺序

每个输入文件按以下顺序处理：

```text
属性替换与匹配元素删除
→ 环网柜组合（若启用）
→ 重复 ID 检查或修复（按选择）
→ XML 重解析验证
→ 输出文件
```

目录模式中每个文件独立执行。

## 6. ID 选择模式

`BasicSettings.id_action`：

```text
none   不处理
check  只检查并写日志
repair 检查并修复，写日志
```

不生成 CSV。修复规则沿用 v2.6.0：只修复单个文件直属 Layer 的重复 ID，保留第一处，后续重复项参考同标签元素的主流前缀和固定总位数生成唯一 ID。

## 7. 环网柜识别

检查范围：

```text
G → 直属 Layer → 直属 <rect>
```

每个 `<rect>` 都视为一个环网柜边框。只处理标签严格等于 `rect` 的元素，不把 `Rectangle` 或其他矩形标签视为环网柜。

## 8. 严格框内成员规则

对每个直属图元计算完整可见边界，包括：

- `x/y/w/h`；
- `x1/y1/x2/y2`；
- `cx/cy/rx/ry`；
- `mergex/mergey/w/h`；
- `d` 中坐标；
- 图元子树的综合边界。

仅当图元的完整边界满足：

```text
left   >= rect.left
right  <= rect.right
top    >= rect.top
bottom <= rect.bottom
```

才归入该 rect 的 Merge。允许 0.5 坐标单位容差。中心点在框内但有任何部分伸出框外的图元不会组合。

## 9. Merge 重建

为保证旧文件也满足严格规则，处理时会：

1. 解析旧 Merge 的 `mergesize` 和成员区间，用于复用对应 rect 的 Merge ID 与样式；
2. 从 Layer 中移除全部旧 Merge 标记；
3. 按 rect 完整包含关系重新计算成员；
4. 在该组第一个成员前插入 Merge；
5. 将组内成员整理为连续区间，保持成员原相对顺序；
6. 设置 `mergex/mergey/w/h` 为 rect 的精确边界；
7. 设置 `mergesize` 为实际成员数量；
8. 框外图元保持非组合状态和原相对顺序。

若一个图元完整位于两个同尺寸重叠 rect 内，程序停止该文件处理，不猜测归属。

## 10. 验证

输出前验证：

- 每个 rect 恰好属于一个 Merge；
- 每个 Merge 恰好包含一个 rect；
- `mergesize` 与实际连续成员数一致；
- Merge 区间不越界、不重叠；
- 每个成员完整位于所属 rect 框内；
- XML 可重新解析。

## 11. 回归样本

`tests/data/combine-test-20260730.sln.pic.g`：

- 2 个 rect；
- 原有 1 个 Merge；
- 严格重建后 2 个 Merge；
- 每组 23 个成员；
- 左右伸出连接线、柜外 Status 和上方 `35092` Text 均在 Merge 外。
