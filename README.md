# G File Studio 2.0.0

G File Studio 是一个基于 PySide6 的 Windows 桌面应用，用于处理 XML 格式的 `.g` / `.sln.pic.g` 文件。

## 主要功能

- 基础处理：支持单个文件或目录，只处理 G 根节点直属 `Layer` 的直接子元素。
- G 文件合并：用户自定义顺序，按最上方有效 `<Bus>` 或最高图元对齐。
- 添加图框：支持单个文件或目录，支持内置模板和客户自定义模板。
- 一键处理：只选择原始输入和最终输出，中间文件由 App 自动管理并清理。
- 所有下拉框在收起状态下均不会被鼠标滚轮误切换。
- 每个页面分别记住最近使用的输入、输出和模板目录。
- 内置绿色程序图标同时用于 EXE、窗口标题栏和 Windows 任务栏。

## 最近目录记忆

程序使用 `QSettings` 保存最近目录，并按页面、用途和输入方式分别记录：

```text
基础处理
├── 单文件所在目录
├── G 文件输入目录
└── 输出目录

G 文件合并
├── 输入目录
└── 输出目录

添加图框
├── 单文件所在目录
├── G 文件输入目录
├── 输出目录
├── 客户自定义模板所在目录
├── 内置模板导出目录
└── JSON 配置目录

一键处理
├── 单文件所在目录
├── G 文件输入目录
├── 最终输出目录
├── 客户自定义模板所在目录
└── 内置模板导出目录
```

下次点击“浏览”时会从该用途上次选择的目录打开。

若上次目录已经被删除、移动或磁盘不可用，程序会显示：

```text
上次使用的目录已经不存在，请重新选择。
```

随后回退到当前有效路径、用户文档目录或用户主目录。

每次点击开始处理前，程序还会再次检查输入文件、输入目录、输出目录和自定义模板是否存在。

## 绿色程序图标

项目已包含：

```text
resources/icons/app.ico
resources/icons/app.png
```

- `app.ico`：PyInstaller 打包 EXE、快捷方式和资源管理器图标。
- `app.png`：PySide6 窗口图标的备用资源。

`build_exe.ps1` 已包含：

```powershell
--icon "resources\icons\app.ico"
```

程序启动时也会调用：

```python
app.setWindowIcon(icon)
window.setWindowIcon(icon)
```

因此 EXE、窗口左上角和任务栏使用同一套绿色图标。

后续替换图标时，只需替换这两个文件并重新运行 `build_exe.ps1`。

建议 `.ico` 内包含以下尺寸：

```text
16×16
24×24
32×32
48×48
64×64
128×128
256×256
```

Windows 可能缓存旧图标。重新打包后若仍显示旧图标，可修改输出版本名、删除旧 `dist/build` 后重新打包，或重启 Windows 文件资源管理器。

## 输入模式

### 基础处理

可选择：

```text
单个 G 文件
G 文件目录
```

### G 文件合并

合并模块固定使用目录输入，因为需要读取多个 `.sln.pic.g` 文件并由用户调整顺序。

### 添加图框

可选择：

```text
单个 G 文件
G 文件目录
```

### 一键处理

可选择：

```text
单个 G 文件
G 文件目录
```

单文件模式自动跳过合并；目录模式可按用户顺序合并。

## 模板模式

### 程序内置模板

源码位置：

```text
resources/templates/
├── templates.json
└── SLD-Drawing-Frame-Template.sln.pic.g
```

内置模板会调整外框尺寸和位置，并允许修改：

- 左上标题；
- Draw 姓名和日期；
- Approve 姓名和日期；
- Issue 姓名和日期。

### 客户自定义模板

客户模板会根据目标画布和四边距：

- 调整外框四条边；
- 移动左上、右下及其他锚定组件；
- 重新分配模板图元 ID。

不会修改：

- 文字内容；
- Draw / Approve / Issue；
- 姓名和日期；
- 字体、颜色、线宽和表格内容。

## 创建环境

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1 -Dev
```

## 开发运行

```powershell
.\run_dev.ps1
```

## 自动测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前版本测试结果：

```text
33 passed
```

## 打包

```powershell
.\build_exe.ps1
```

生成：

```text
dist\GFileStudio\GFileStudio.exe
release\GFileStudio_v2.0.0_Windows_x64.zip
```

分享时发送 `release` 下的 ZIP，不能只发送 EXE。
