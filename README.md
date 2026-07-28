# G File Studio

G File Studio 是一个基于 **PySide6** 的 Windows 桌面应用，用于批量处理 XML 格式的 G 图形文件。

当前版本：**1.5.0**

## v1.5.0 核心更新

### 1. 属性替换规则默认关闭

“替换元素属性值”规则默认不启用，标签、属性名、旧值和新值均为空，仅显示填写提示。

只有用户主动勾选并填写条件后，程序才会执行替换。匹配范围仍严格限制为：

```text
G 根节点
└── 直属 Layer
    └── 直接子元素
```

不会修改 `G`、`Theme`、`Layer` 本身、Layer 外内容或图元内部嵌套元素。

### 2. 数值输入不受鼠标滚轮影响

馈线间隔、合并上下左右边距、图框上下左右边距等整数参数：

- 默认显示当前数值；
- 只允许直接键盘输入；
- 不显示高亮的上下调节按钮；
- 鼠标滚轮不会改变数值；
- 上下方向键和 PageUp/PageDown 不会增减数值。

这样滚动页面时不会误改布局参数。

### 3. 日期改为日历选择

Draw、Approve、Issue 日期使用日历选择框：

- 点击右侧日历按钮选择日期；
- 未选择时保持为空；
- 输出格式统一为 `yyyy-MM-dd`；
- 鼠标滚轮不会意外修改日期。

### 4. Bus 对齐规则明确化

合并时只识别标签名严格等于 **`<Bus>`** 的母线，**`<BusDis>` 不会被当作 Bus**。

对齐规则：

1. 在每个 G 文件中查找有效、非零长度、水平的 `<Bus>`；
2. 如果存在多个，选择线坐标 Y 最小的最上方 `<Bus>`；
3. 如果文件没有有效水平 `<Bus>`，使用该文件所有位置坐标中的最小 Y，也就是最高图元；
4. 用户顺序中的第一张图提供统一目标 Y；
5. 后续文件的顶部 `<Bus>` 或最高图元都移动到该统一 Y。

因此，无论后续文件有无 `<Bus>`，最终都会在同一水平基准上排列。

## 已实现功能

### 一键处理

可组合执行：

1. 基础处理；
2. G 文件合并；
3. 添加图框。

支持关闭任意阶段，也支持运行前清理中间目录。

### 基础处理

当前保留两条通用规则，且均默认关闭：

- **替换元素属性值**：元素标签、属性名、旧值全部精确匹配后写入新值；
- **删除匹配元素**：元素标签、属性名、属性值全部精确匹配后删除整个元素子树。

两条规则都只处理 G 根节点直属 Layer 的直接子元素。

需要删除 `ConnectLine w="137"` 时，可使用通用删除规则：

```text
元素标签：ConnectLine
属性名：w
属性值：137
```

删除后，程序会在当前 Layer 范围内清理指向已删除真实 ID 的：

- `link`；
- `node_area`；
- `p_FatherObjId`。

### G 文件合并

- 输入文件名可以任意；
- 只要求后缀为 `.sln.pic.g`；
- 不解析站点和馈线号；
- 不检查文件是否属于同一个站；
- 用户可在 App 中自由调整合并顺序；
- 第一行文件完整作为合并基准；
- 检查并拒绝已经包含外框架的输入；
- 清理负坐标元素及相关引用；
- 按顶部有效水平 `<Bus>` 或最高图元进行垂直对齐；
- 严格保持相邻图形水平间隔；
- 处理重复 ID 和虚拟拓扑 ID；
- 同步更新 `link`、`node_area`、`p_FatherObjId`；
- 坐标统一取整；
- 计算四周边距和最终画布尺寸；
- 输出后重新解析 XML 验证合法性。

> 参与合并的 G 文件不能包含最外层框架、左上标题块或右下签字栏。外框必须在合并完成后统一添加。

### 添加图框

- 从固定 SLD 模板读取图框；
- 根据目标 G 画布大小调整外框；
- 左上标题默认取输入文件名；
- 写入 Draw、Approve、Issue 姓名和日期；
- 日期支持日历选择；
- 支持载入和保存 JSON 配置；
- 自动重新分配模板图元 ID；
- 输出到独立目录，不修改输入文件。

## 项目结构

```text
GFileStudio/
├── app.py
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── setup_env.ps1
├── run_dev.ps1
├── build_exe.ps1
├── .gitignore
│
├── g_file_studio/
│   ├── app.py
│   ├── models.py
│   ├── workers.py
│   ├── engines/
│   │   ├── merge_engine.py
│   │   └── frame_engine.py
│   ├── processors/
│   ├── services/
│   └── ui/
│       ├── main_window.py
│       ├── theme.py
│       ├── help_content.py
│       ├── pages/
│       └── widgets/
│           ├── basic_rules_editor.py
│           ├── file_order_editor.py
│           ├── integer_input.py
│           ├── person_editor.py
│           ├── rule_card.py
│           └── ...
│
├── resources/
│   ├── templates/
│   │   └── SLD-Drawing-Frame-Template.sln.pic.g
│   └── icons/
│       └── check.svg
│
├── config/
├── workspace/
└── tests/
```

## Python 版本

推荐 Python 3.11 或 3.12。

## 第一次安装

```powershell
cd D:\Workspace\Python\GFileStudio
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1 -Dev
```

## 启动应用

```powershell
.\run_dev.ps1
```

或者：

```powershell
.\.venv\Scripts\python.exe .\app.py
```

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 打包 Windows 程序

```powershell
.\build_exe.ps1
```

生成：

```text
dist/
└── GFileStudio/
    ├── GFileStudio.exe
    └── _internal/
```

分享给其他人时，应压缩并发送整个 `dist\GFileStudio` 文件夹，不能只发送 EXE。
