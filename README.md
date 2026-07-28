# G File Studio 1.9.0

G File Studio 是一个基于 **PySide6** 的 Windows 桌面应用，用于处理 XML 格式的 `.g` / `.sln.pic.g` 文件。

## 主要功能

- 基础处理：支持单个文件或目录，按元素标签、属性名和属性值替换属性或删除直属 Layer 图元。
- G 文件合并：用户自由调整顺序，按最上方 `<Bus>` 或最高图元对齐。
- 添加图框：支持单个文件或目录，支持 App 内置模板和客户自定义模板。
- 一键处理：支持单个文件或目录，只选择原始输入和最终输出。
- 隐藏中间目录：中间结果自动保存在 Windows AppData 缓存中并自动清理。

## 下拉选择框防误操作

程序中的输入方式、元素标签、属性名和内置模板等下拉选择框均采用防滚轮控件：

- 下拉框收起时，鼠标滚轮只滚动页面，不会改变已经选中的值；
- 只有主动展开下拉列表后，滚轮才用于浏览列表；
- 可编辑下拉框仍可直接输入新的元素标签或属性名。


## 三个独立模块的输入方式

### 基础处理

可以选择：

```text
单个 G 文件
或
G 文件目录
```

- 单文件模式只处理用户选择的一个文件；
- 目录模式批量处理目录第一层中的所有 `.g` 文件；
- 输出统一写入用户选择的输出目录；
- 原始文件不在程序内部直接修改。

### G 文件合并

合并仍然使用目录输入，因为合并至少需要组织多个文件，并允许用户调整合并顺序。参与合并的文件名必须以 `.sln.pic.g` 结尾。

### 添加图框

可以选择：

```text
单个 G 文件
或
G 文件目录
```

- 单文件模式只给所选文件添加图框；
- 目录模式批量给目录第一层中的所有 `.g` 文件添加图框；
- 每个输出文件保持原文件名，或者按设置增加输出后缀。

## 模板模式

### 程序内置模板

源码位置：

```text
resources/templates/
├── templates.json
└── SLD-Drawing-Frame-Template.sln.pic.g
```

内置模板会：

- 根据目标 G 画布和四边距调整外框；
- 移动左上标题块和右下签字栏；
- 修改左上标题；
- 修改 Draw、Approve、Issue 姓名和日期；
- 重新分配模板图元 ID。

后续修改内置模板时，替换上述 `.g` 文件、更新 `templates.json` 版本并重新打包即可。

### 客户自定义模板

客户模板会：

- 根据目标画布和左、上、右、下边距调整四条外框线；
- 将非外框组件按最近的外框边缘锚定并平移；
- 保持模板中所有文字、姓名、日期、字体、颜色、线宽和表格内容不变；
- 仅执行必要的 ID 重分配与引用同步。

客户模板必须包含由四条轴对齐 `line` 构成的完整矩形外框。

## 一键处理

一键处理支持：

```text
单个 G 文件
或
包含多个 .sln.pic.g 文件的目录
```

单文件模式自动跳过合并。目录模式可以合并，也可以关闭合并后逐个处理。

中间目录位于类似：

```text
C:\Users\用户名\AppData\Local\NARI\GFileStudio\Cache\session_xxx
```

程序会在以下时机自动清理：

- App 启动时清理上次残留；
- 每次开始新的一键任务前；
- App 正常关闭时；
- 上次异常退出后，下次启动时。

最终输出只写入用户选择的输出目录。

## 开发运行

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1 -Dev
.\run_dev.ps1
```

也可以：

```powershell
.\.venv\Scripts\python.exe .\app.py
```

## 自动测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前版本包含 25 项核心自动测试。

## 打包

```powershell
.\build_exe.ps1
```

结果：

```text
dist\GFileStudio\
├── GFileStudio.exe
└── _internal\
```

同时生成：

```text
release\GFileStudio_v1.9.0_Windows_x64.zip
```

分享给别人时，请发送完整 ZIP，不能只发送 `GFileStudio.exe`。

## 项目结构

```text
GFileStudio/
├── app.py
├── g_file_studio/
│   ├── engines/
│   ├── processors/
│   ├── services/
│   └── ui/
├── resources/
│   ├── icons/
│   └── templates/
├── config/
├── tests/
├── workspace/
├── setup_env.ps1
├── run_dev.ps1
└── build_exe.ps1
```
