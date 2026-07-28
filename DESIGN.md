# G File Studio 1.9.0 设计说明

## 1. 分层

```text
PySide6 UI
   ↓
Processor 业务编排
   ↓
Engine XML 算法
   ↓
ElementTree
```

UI 不直接修改 XML。独立页面和一键处理调用同一套 Processor 与 Engine。

## 2. 统一输入模型

`InputMode` 提供两种输入形式：

- `single_file`：只处理用户选择的一个 G 文件；
- `directory`：扫描目录第一层中的 G 文件并批量处理。

目前使用该输入模型的模块：

```text
基础处理
添加图框
一键处理
```

基础处理和添加图框的 Processor 都通过 `discover_g_inputs()` 统一发现文件，避免 UI 和业务层各自实现一套扫描规则。

G 文件合并仍然使用目录输入，并通过顺序编辑器管理多个文件的实际合并顺序。

## 3. 一键处理工作区

用户界面不显示中间目录。`TempWorkspaceService` 使用 `platformdirs.user_cache_dir()` 创建会话目录：

```text
Cache/session_UUID/
├── 00_source/
├── 01_basic_processed/
└── 02_merged/
```

生命周期：

```text
App 启动 → 清理旧缓存 → 创建会话
新任务 → 重置会话目录
App 关闭 → 清理会话
异常退出 → 下次启动清理
```

## 4. 模板模型

`TemplateMode`：

- `builtin`：使用打包资源，并允许修改模板业务内容；
- `custom`：使用客户文件，不修改任何业务内容。

内置模板由 `resources/templates/templates.json` 管理，可扩展多套内置模板。

## 5. 外框适配

程序自动识别模板中跨度最大的两条水平线和两条垂直线，形成旧外框：

```text
old_left, old_top, old_right, old_bottom
```

目标外框：

```text
new_left   = frame_left
new_top    = frame_top
new_right  = target_width  - frame_right
new_bottom = target_height - frame_bottom
```

### 内置模板

- 拉伸四条外框线；
- 左上标题块保持相对左上角距离；
- 右下签字栏保持相对右下角距离；
- 更新标题、姓名和日期。

### 客户模板

- 拉伸四条外框线；
- 每个非外框组件选择距离最近的水平边和垂直边作为锚点；
- 只平移组件，不缩放组件；
- 不改 Text、颜色、字体、线宽、尺寸和业务属性。

## 6. XML 安全

- 不在原始文件上直接写入；
- 输出写入指定输出目录；
- 写出后重新解析 XML；
- 模板图元 ID 统一重分配；
- 同步更新 `link`、`node_area`、`p_FatherObjId`。

## 7. 内置模板升级

普通样式变化只需：

1. 替换 `resources/templates/*.sln.pic.g`；
2. 更新 `templates.json` 中的版本；
3. 运行 `build_exe.ps1`；
4. 发布新的完整 ZIP。

若模板不再使用四条 `line` 构成外框，或签字栏结构发生根本变化，则需要同步升级识别算法。


## 下拉框交互规范

所有业务下拉框必须使用 `WheelSafeComboBox`，不得直接实例化 `QComboBox`。
收起状态的滚轮事件必须 `ignore()`，以便父级滚动页面继续响应；展开下拉列表后才允许滚轮浏览选项。
这样可以避免用户滚动长页面时意外修改元素标签、属性名、输入模式或模板选择。
