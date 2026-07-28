# G File Studio 设计说明（v1.4.0）

## 1. 总体目标

项目把 G 文件算法整理为可测试、可复用、可扩展的处理模块，再由 PySide6 界面调用。

```text
PySide6 UI
    ↓
Processor 业务层
    ↓
Engine 核心算法层
    ↓
ElementTree / 文件系统
```

## 2. 分层职责

### UI 层

负责文件选择、参数输入、帮助说明、输入预检查、后台任务启动、进度和日志显示，不放置大型 XML 算法。

### Processor 层

负责输入校验、参数组合、调用 Engine、统一输出 `ProcessingResult`，以及日志和进度回调。

### Engine 层

负责坐标、ID、引用、合并布局和图框处理等纯算法。

## 3. 基础规则设计

基础处理页和一键处理页共同使用：

```text
g_file_studio/ui/widgets/basic_rules_editor.py
```

当前只保留两条通用规则：

1. 替换元素属性值；
2. 删除匹配元素。

不再为 `ConnectLine w=137` 等具体业务条件写专用逻辑。所有具体元素都通过统一的“标签 + 属性名 + 属性值”规则配置。

### 3.1 替换元素属性值

精确匹配：

```text
元素标签 == replace_target_tag
元素[属性名] == replace_old_value
```

匹配后：

```text
元素[属性名] = replace_new_value
```

### 3.2 删除匹配元素

精确匹配：

```text
元素标签 == delete_target_tag
元素[属性名] == delete_target_value
```

匹配后删除整个元素子树，并收集元素及其后代 ID。

### 3.3 作用范围

所有基础规则只匹配 G 根节点直属 Layer 的直接子元素：

```text
G
├── Theme                 不处理
└── Layer
    ├── 直接子元素         处理
    └── Group
        └── 嵌套子元素     不处理
```

不会处理 G、Theme、Layer 本身或 Layer 外内容。

删除完成后，仅在当前 Layer 范围内清理：

- `link`；
- `node_area`；
- `p_FatherObjId`。

只有确实已不存在于保留元素中的 ID 才被视为真正删除，避免源文件重复 ID 导致误清理。

## 4. 合并输入设计

### 文件命名

合并模块不承担业务归属检查：

- 不解析站点；
- 不解析馈线号；
- 不判断同站；
- 只校验 `.sln.pic.g` 后缀。

App 使用 `FileOrderEditor` 管理顺序。首次扫描采用自然排序，用户可通过置顶、上移、下移、置底自由调整。运行时把完整文件名顺序写入 `MergeSettings.ordered_file_names`；引擎校验顺序没有重复、遗漏或不存在的文件。

### 对齐策略

每个输入文件计算一个 `alignment_y` 和 `alignment_mode`：

```text
存在有效水平 Bus  → 最顶部水平 Bus Y
不存在水平 Bus     → 全图最高图元 Y
```

用户顺序中的第一个文件提供统一目标 Y，并完整作为输出基准。后续输入的 Bus 或最高图元都移动到该目标 Y。

### 外框限制

参与合并的输入不能包含外框架图。外框识别支持：

- 接近画布边缘、覆盖大部分画布的四条边框线；
- 接近画布边缘、覆盖大部分画布的大矩形。

检测到后拒绝处理，避免把已经加框的图再次并入新画布。

## 5. 用户顺序组件

`g_file_studio/ui/widgets/file_order_editor.py` 被合并页面和一键处理页面共同复用，负责扫描、预检查、显示对齐基准以及顺序移动。

## 6. 复选框样式

Qt 样式中明确设置：

- 未选中边框；
- 悬停边框；
- 选中蓝色背景；
- 白色 SVG 勾号；
- 禁用状态。

`build_app_style()` 在运行时把 `resources/icons/check.svg` 转为绝对路径，兼容开发目录和 PyInstaller 发行目录。

## 7. 后台任务

使用：

```text
QThreadPool + QRunnable + Signal
```

主线程只负责 UI，XML 处理在线程池中运行。

## 8. 文件安全

- 不直接修改输入文件；
- 基础处理先写 `.tmp` 并重新解析，再原子替换输出；
- 合并和图框处理执行最终 XML 校验；
- 一键流程可清理阶段目录，防止旧文件混入。

## 9. 后续扩展

建议继续增加：

- 支持多条动态删除/替换规则；
- 规则配置保存与载入；
- G 文件最终验证页面；
- 设备关联检查；
- 未接线和重复关联检查；
- HTML/CSV 报告；
- QGraphicsView 图形预览；
- 项目配置和最近项目；
- 可追溯操作日志。
