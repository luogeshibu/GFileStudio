# G File Studio

G File Studio 是一个基于 **PySide6** 的 Windows 桌面应用，用于批量处理 XML 格式的 G 图形文件。

当前版本：**1.4.0**

## v1.4.0 核心改动

### 基础处理只保留通用规则

删除了专用的“删除 `ConnectLine w=137`”规则。基础处理现在只保留两个可扩展的通用规则：

1. **替换元素属性值**：元素标签、属性名、旧值全部精确匹配后写入新值；
2. **删除匹配元素**：元素标签、属性名、属性值全部精确匹配后删除整个元素子树。

需要删除 `ConnectLine w="137"` 时，直接在“删除匹配元素”中填写：

```text
元素标签：ConnectLine
属性名：w
属性值：137
```

不再为某一种元素保留写死的专用逻辑。

### 基础处理作用范围

替换和删除只检查：

```text
G 根节点
└── 直属 Layer
    └── 直接子元素
```

不会修改：

- `G` 根节点属性；
- `Theme`；
- `Layer` 本身；
- `Layer` 外内容；
- Layer 图元内部嵌套的子元素。

删除直属图元后，会在当前 Layer 范围内清理指向已删除真实 ID 的 `link`、`node_area` 和 `p_FatherObjId`。

### 用户自定义合并顺序

- 合并页面和一键处理页面都提供文件顺序表格；
- 支持“扫描 / 检查、恢复自然排序、置顶、上移、下移、置底”；
- 表格第一行文件完整作为合并基准；
- 执行前会重新扫描目录并保留用户顺序；
- 顺序列表必须包含目录中全部 `.sln.pic.g` 文件，不能遗漏或重复。

## 已实现功能

### 一键处理

可组合执行：

1. 基础处理；
2. G 文件合并；
3. 添加图框。

支持关闭任意阶段，也支持运行前清理中间目录。

### 基础处理

当前包含两条可独立启用的通用规则：

- 根据元素标签、属性名和旧值替换属性内容；
- 根据元素标签、属性名和属性值删除整个匹配元素。

基础处理页面和一键处理页面复用同一个 `BasicRulesEditor`。

### G 文件合并

- 只要求输入文件以 `.sln.pic.g` 结尾；
- 不解析站点和馈线号，不检查是否属于同一个站；
- 支持用户自定义顺序，第一行作为基准；
- 检查并拒绝带外框架的输入；
- 清理负坐标元素及相关引用；
- 有有效水平 Bus 时按最上方 Bus 对齐；
- 没有 Bus 时使用最高图元 Y 作为对齐基准；
- 严格保持相邻图形间隔；
- 处理重复 ID 和虚拟拓扑 ID；
- 同步更新 `link`、`node_area`、`p_FatherObjId`；
- 坐标统一取整；
- 计算四周边距和最终画布尺寸；
- 输出后重新解析 XML 进行验证。

“输入文件与合并顺序”区域会显示：

- 实际合并顺序；
- 文件名；
- 使用的对齐基准；
- 原始基准 Y；
- 检查状态。

> 参与合并的 G 文件不能包含最外层框架、左上标题块或右下签字栏。外框必须在合并完成后统一添加。

### 添加图框

- 从固定 SLD 模板读取图框；
- 根据目标 G 画布大小调整外框；
- 左上标题默认取输入文件名；
- 写入 Draw、Approve、Issue 姓名和日期；
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

推荐使用 Python 3.11 或 3.12。

## 第一次安装

```powershell
cd D:\Workspace\Python\windows-app-repo\GFileStudio
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

## 打包 EXE

```powershell
.\build_exe.ps1
```

输出：

```text
dist\GFileStudio\GFileStudio.exe
```

`build_exe.ps1` 会把整个 `resources` 目录一并打包，因此复选框图标和默认图框模板都会包含在发行目录中。
