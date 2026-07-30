# G File Studio v2.9.0 设计说明

## 1. 版本基线

v2.9.0 基于 v2.8.0。图形边距、馈线图合并、图框添加和重复 ID 逻辑保持不变，本版集中新增：

- 环网柜取消组合；
- 非环网柜 Merge 保护；
- FeedLine / ConnectLine / BusDis / Bus 颜色修改；
- 基础处理输出冲突策略；
- 互斥选择控件统一样式。

## 2. 基础处理数据模型

`BasicSettings` 新增：

```text
rmu_action: none | group | ungroup
change_feedline_color / feedline_color
change_connectline_color / connectline_color
change_busdis_color / busdis_color
change_bus_color / bus_color
output_conflict_action: overwrite | timestamp
task_timestamp
```

保留旧字段 `group_rmu_elements` 作为 v2.7/v2.8 兼容入口。当 `rmu_action=none` 且该旧字段为 true 时按 group 执行。

## 3. Merge 连续成员模型

G 文件中的组合不是 XML 嵌套，而是：

```xml
<Merge mergesize="N" />
<成员1 />
...
<成员N />
```

扫描时校验：

- `mergesize` 必须是正整数；
- 成员范围不得超出 Layer；
- 不同 Merge 成员区间不得重叠。

成员范围中包含 `<rect>` 的 Merge 视为环网柜 Merge；不包含 `<rect>` 的 Merge 视为其他业务 Merge。

## 4. 环网柜组合

识别范围：

```text
G → 直属 Layer → 直属 <rect>
```

成员判定采用完整边界包含：

```text
member.left   >= rect.left
member.top    >= rect.top
member.right  <= rect.right
member.bottom <= rect.bottom
```

允许 0.5 坐标单位容差。只看中心点不够，任何部分伸出框外的图元都不组合。

处理旧 Merge：

- 环网柜 Merge 头先移除，再按严格框内规则重建；
- 对应同一个 rect 的合法旧 Merge 尽量复用 ID 和样式；
- 不含 rect 的其他业务 Merge 及其成员完整保留，并从环网柜成员候选中排除。

新 Merge 几何复现用户提供的手工组合文件：

```text
mergex = rect.left - 1
mergey = rect.top - 1
w      = rect.width + 1
h      = rect.height + 1
```

右、下边界与 rect 保持一致。

## 5. 新 Merge ID

优先级：

1. 当前文件已有 Merge 的主流 ID 格式；
2. 当前文件中 20 前缀对象的固定总位数；
3. 从各同类元素主流格式提取文件最大顺序号；
4. 通用唯一 ID 兜底。

用户样本中图元顺序号最大为 27，因此新 Merge 为 `20000028`。

## 6. 取消环网柜组合

取消操作只删除合法 Merge 块中成员包含 `<rect>` 的 Merge 头：

```text
删除：<Merge ... />
保留：其后的全部成员
```

不修改：

- 成员排列顺序；
- ID；
- 坐标和 d；
- link / node_area / p_FatherObjId；
- 颜色、字体、线宽和业务属性。

不含 `<rect>` 的其他业务 Merge 保留。无法可靠解析 `mergesize` 的异常 Merge 不猜测删除，只记录日志告警。

## 7. 颜色处理

严格处理直属 Layer 的：

```text
FeedLine
ConnectLine
BusDis
Bus
```

每个启用规则只修改：

```text
lcc = #RRGGBB
lc  = R,G,B
```

颜色输入经过 `#RRGGBB` 校验和标准化。不修改 `fc`、`fcc`、`lw`、`ls`、坐标、ID 或引用。

## 8. 输出冲突

UI 在启动任务前枚举本次全部输入文件，并比较目标路径。以下情况视为冲突：

- 输入文件路径与输出文件路径相同；
- 输出目录已经存在同名目标文件。

处理策略：

- `timestamp`：本批全部输出统一添加任务时间戳；若时间戳名称仍存在，追加 `-2`、`-3`。
- `overwrite`：写 `.tmp` 文件，重新解析成功后使用 `os.replace` 原子替换。
- 取消：不启动任务。

## 9. UI 选择样式

互斥选择使用 `QCheckBox + QButtonGroup(exclusive=True)`。所有选项设置 `optionChoice=true`，共享：

- 20px 指示器；
- 统一卡片内边距和最小高度；
- 选中蓝色边框、浅蓝背景；
- 统一 hover、disabled 状态。

## 10. 处理顺序

```text
通用属性规则
→ 环网柜组合/取消组合
→ 线路与母线颜色
→ 重复 ID 检查/修复
→ XML 临时写出与重解析
→ 安全输出
```

## 11. 回归样本

- `tests/data/no-combine.sln.pic.g`：组合后生成 `Merge 20000028`，`mergesize=23`。
- `tests/data/combine.sln.pic.g`：取消组合后所有 28 个原成员保留。
- 用户提供的 `cancel-combine.sln.pic.g`：与取消组合结果的 Layer 标签、属性和顺序一致。
- 颜色引擎测试验证只修改 `lc/lcc`。
- 时间戳冲突测试验证源文件不被覆盖。
