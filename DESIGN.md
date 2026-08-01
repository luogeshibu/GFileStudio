# G File Studio v2.10.0 设计说明

## 1. 版本目标

v2.10.0 基于 v2.9.1，保持现有业务流程不变，主要完成：

1. 从用户提供的组合/未组合样本中重新学习 Merge 格式；
2. 兼容历史 G 文件中不同的 `mergesize` 语义；
3. 用几何关系替代脆弱的固定区间算法；
4. 提升组合和取消组合在大型馈线文件中的稳定性；
5. 将 UI 统一为电网图形工作台主题。

## 2. Merge 格式观察

### 2.1 编辑器标准样本

`$combine-test.sln.pic.g` 中：

```xml
<Merge mergesize="2" mergex="760" mergey="437" w="150" h="60" />
<CBreaker x="760" y="437" w="40" h="40" />
<CBreaker x="870" y="457" w="40" h="40" />
```

观察结论：

- `mergesize=2`，等于两个实际成员数量；
- Merge 几何是成员可见边界的并集；
- `tfr` 中的缩放值等于 `w/h × 100`；
- Merge ID 继续使用 20 前缀编号。

### 2.2 历史项目文件

AJWD-22 中同时出现：

```text
mergesize = 几何成员数量
mergesize = 几何成员数量 + 1
```

因此读取逻辑不能把一种语义写死。

## 3. Merge 扫描算法

对每个直属 Merge：

1. 读取 `mergex、mergey、w、h`；
2. 找到它与下一个 Merge 之间的直属元素；
3. 计算每个元素真实可见边界；
4. 选择完整位于 Merge 几何范围内的元素作为几何成员；
5. 比较几何成员数与 `mergesize`：
   - 相等：成员数量语义；
   - 差 1：兼容头+成员语义；
   - 其他：记录告警，仍以几何范围为准；
6. Merge 缺少有效几何时才使用顺序兜底。

不再使用“不同 Merge 区间不能重叠”作为读取历史文件的阻断条件。

## 4. 环网柜 Merge 识别

一个 Merge 被视为环网柜 Merge，需满足：

- Merge 几何完整包含一个直属 `<rect>`；
- Merge 与 rect 中心偏差在合理范围；
- Merge 面积不超过 rect 面积的 4 倍；
- 无几何的旧文件，仅在第一个连续成员就是 rect 时使用顺序兜底。

这样可避免把后续无关 rect 或大型业务组合误判成环网柜。

## 5. 组合

1. 识别并移除已有环网柜 Merge 头；
2. 保留其他业务 Merge，并保护其几何成员；
3. 对每个 rect 收集完整边界位于框内的直属元素；
4. 将成员整理为连续区间；
5. 在成员前插入 Merge；
6. 新建 Merge 使用：

```text
mergex = rect.left - 1
mergey = rect.top - 1
w      = rect.width + 1
h      = rect.height + 1
mergesize = 实际成员数量
```

7. 输出后验证每个 rect 对应一个 Merge，成员均完整位于 rect 内。

## 6. 取消组合

取消操作不依赖 `mergesize` 单一语义，而是通过 Merge 与 rect 的几何关系识别环网柜 Merge。

图形编辑器的 Layer 直属元素按 XML 顺序绘制，越靠后的元素层级越高。用户提供的对照样本表明：

```text
CBreaker
CBreaker
rect
```

会让 rect 外框覆盖在设备上；正确顺序应为：

```text
rect
CBreaker
CBreaker
```

因此取消组合按以下步骤处理：

1. 删除对应环网柜 Merge 头；
2. 找到该 rect 内完整包含的直属设备图元；
3. 若 rect 位于任一柜内设备之后，则把 rect 移到最早柜内设备之前；
4. 仅调整 Layer 顺序，不修改坐标、ID、引用、颜色和业务属性；
5. 剩余非环网柜 Merge 保持不变。

## 7. ID 与引用

- 组合不会修改原成员 ID；
- 新 Merge ID 优先参考已有 Merge 的同类格式；
- 无现有 Merge 时参考当前文件的 20 前缀对象；
- 所有新 ID 必须在 Layer ID 和引用 token 命名空间中唯一；
- 取消组合不修改 `link`、`node_area`、`p_FatherObjId`。

## 8. 电网工作台主题

主色体系：

```text
运行区深色：#0A1F29
电网主绿：#0B7A5A
拓扑青绿：#1BA39C
工作区背景：#F3F7F6
卡片边框：#CFDFDA
告警红：#C94F50
```

设计原则：

- 侧边栏用于运行导航，深色降低长时间使用疲劳；
- 绿色仅用于主操作、当前页面、进度和选中状态；
- 功能区保持白色卡片和高对比输入控件；
- 互斥选项继续使用统一卡片式 QCheckBox；
- 不绑定任何具体企业品牌。

## 9. 回归样本

- `generic-combine-test.sln.pic.g`：验证标准 `mergesize=成员数量`。
- `combine.sln.pic.g` / `no-combine.sln.pic.g`：验证环网柜 23 个框内成员。
- `JED-CTL-AJWD-22.sln.pic.g`：验证混合 mergesize 历史格式可取消并重建。
- `rmu-frame-on-top.g` / `rmu-devices-on-top.g`：验证取消组合后 rect 自动下移到设备下层且坐标不变。
- 其他现有合并、边距、图框、颜色和 ID 测试继续执行。
