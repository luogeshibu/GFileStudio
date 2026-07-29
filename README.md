# G File Studio v2.3.0

G File Studio 是一个基于 **PySide6** 的 Windows 桌面程序，用于处理 XML 格式的 `.g` / `.sln.pic.g` 图形文件。

## 主要功能

- 基础处理：按元素标签、属性名和属性值替换属性或删除匹配元素。
- G 文件合并：可从扫描列表删除不需要的文件，只合并保留项，并自由定义顺序；支持 Bus 对齐、无 Bus 最高图元对齐、ID 和引用处理。
- 图形边距调整：主体图形距离画布左、上、右、下默认各 500。
- 添加图框：支持内置模板和客户自定义模板。
- 一键处理：自动串联基础处理、合并、图形边距调整和添加图框。
- 完整路径记忆：输入模式、完整输入路径、输出目录和客户模板路径都会跨启动恢复。
- 临时文件自动管理：中间文件保存在 AppData 缓存，任务开始、程序关闭和下次启动时自动清理。

## 路径记忆

用户设置保存到独立 INI 文件：

```text
C:\Users\<用户名>\AppData\Local\NARI\GFileStudio\Config\user_settings.ini
```

以下操作都会保存路径：

- 点击“浏览”选择文件或目录；
- 手动输入或粘贴路径后离开输入框；
- 切换单文件/目录模式；
- 点击开始执行且路径有效；
- 正常关闭程序。

如果上次路径已经不存在，程序会提示用户、清除失效记录，并在下次浏览时回退到最近仍存在的父目录或 Windows 文档目录。

## 合并文件筛选

扫描输入目录后，可以在表格中选择一个或多个文件并点击“删除所选”：

- 支持 `Ctrl` 或 `Shift` 多选；
- 删除仅从本次合并列表排除，不会删除磁盘上的源文件；
- 合并引擎只处理表格中剩余的文件，并严格使用当前显示顺序；
- 点击“扫描 / 检查”会保留当前排除项和手动顺序；
- 点击“恢复全部并排序”会重新加入已排除文件并按文件名自然排序。

该功能同时适用于独立“G 文件合并”页面和“一键处理”中的合并阶段。

## 图形边距调整

默认参数：

```text
左边距：500
上边距：500
右边距：500
下边距：500
```

处理规则：

1. 识别 Layer 中主体图形的实际边界；
2. 仅当图框可确认是 G File Studio 内置图框时，精确排除内置图框组件；
3. 整体平移主体图形，使其达到指定四边距；
4. 重新计算 `G.w/G.width` 和 `G.h/G.height`；
5. 内置图框保留原四边距，外框线动态拉伸，标题区与签字栏按锚点同步移动；
6. 不修改内置图框中的标题、Draw、Approve、Issue、日期、字体、颜色、线宽和表格内容；
7. 检测到客户图框或来源无法确认的图框时，停止处理并提示先删除图框。

## 一键处理顺序

```text
基础处理
→ G 文件合并
→ 图形边距调整
→ 添加图框
```

如果图形边距调整阶段确认文件包含 G File Studio 内置图框，则保留并同步适配该图框，后续自动跳过重复添加图框。其他图框会提示先删除。

## 安装开发环境

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1 -Dev
```

启动：

```powershell
.\run_dev.ps1
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 打包

```powershell
.\build_exe.ps1
```

生成：

```text
dist\GFileStudio\GFileStudio.exe
release\GFileStudio_v2.3.0_Windows_x64.zip
```

分享给客户时发送 `release` 目录中的 ZIP。客户完整解压后运行 `GFileStudio.exe`，不需要安装 Python。

## 图标

项目内置绿色图标：

```text
resources/icons/app.ico
resources/icons/app.png
```

`app.ico` 用于 PyInstaller 生成 EXE 图标，`app.png/app.ico` 用于窗口和任务栏图标。
