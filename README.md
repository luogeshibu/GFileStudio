# G File Studio

G File Studio 是一个基于 **PySide6** 的 Windows 桌面应用，用于批量处理 XML 格式的 G 图形文件。

当前版本：**1.6.0**

## v1.6.0 核心更新

### 1. 日期默认使用当前日期

Draw、Approve、Issue 日期选择框启动时直接显示运行当天日期，打开日历时也定位到当前日期。

- 点击日历按钮可选择其他日期；
- 输出格式统一为 `yyyy-MM-dd`；
- 鼠标滚轮不会改变日期；
- 载入配置时，配置日期为空或无效会回退到当前日期。

### 2. 元素标签和属性名可从实际 G 文件选择

基础处理页和一键处理页新增“扫描元素与属性”：

1. 扫描输入目录中的 `.g` 文件；
2. 只读取 `G → 直属 Layer → 直接子元素`；
3. 元素标签显示为可编辑下拉框；
4. 选择元素标签后，属性名下拉框只显示该标签实际出现的属性；
5. 旧值、新值和删除匹配值仍由用户手动输入；
6. 下拉框保持可编辑，允许手动填写未扫描到的标签或属性。

扫描只用于生成选项，不会修改任何 G 文件。

### 3. 扫描范围与实际处理范围一致

标签和属性选项不会读取：

- `Theme` 中的元素；
- `Layer` 外元素；
- Layer 图元内部嵌套的子元素。

因此用户在下拉框中看到的内容，就是基础处理实际能够匹配的直属 Layer 图元范围。

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
