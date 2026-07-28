# G File Studio 2.0.0 设计说明

## 分层结构

```text
PySide6 UI
    ↓
Processors
    ↓
XML Engines
```

UI 负责参数收集、文件选择、路径记忆、输入校验、后台任务和日志展示；处理器与 XML 引擎不依赖界面控件。

## 程序图标

资源：

```text
resources/icons/app.ico
resources/icons/app.png
```

源码运行和 PyInstaller 打包运行均通过 `services.paths.resource_path()` 定位资源。

应用启动流程：

```text
设置 Windows AppUserModelID
→ 创建 QApplication
→ 设置组织名与应用名
→ 加载 app.ico / app.png
→ app.setWindowIcon
→ window.setWindowIcon
```

PyInstaller 使用 `--icon resources\icons\app.ico` 设置 EXE 图标，并使用 `--add-data resources;resources` 打包全部资源。

## 最近目录服务

文件：

```text
g_file_studio/services/user_settings_service.py
```

使用 `QSettings` 保存最近目录。目录 key 按模块和用途隔离，单文件与目录模式不会互相覆盖。

示例：

```text
recent_paths/basic/single_file_directory
recent_paths/basic/input_directory
recent_paths/basic/output_directory
recent_paths/frame/custom_template_directory
recent_paths/pipeline/output_directory
```

`PathRow` 在文件对话框打开前执行：

```text
读取最近目录
→ 存在：作为文件对话框初始目录
→ 不存在：清除失效记录并提示用户
→ 使用当前有效路径或系统文档目录作为回退
```

选择成功后：

```text
选择文件 → 保存文件所在目录
选择目录 → 保存所选目录
```

## 路径校验

文件：

```text
g_file_studio/ui/path_validation.py
```

每个处理页面在启动后台任务前检查：

- 单文件是否存在且为文件；
- 文件后缀是否合法；
- 输入目录是否存在且为目录；
- 输出目录是否存在且为目录；
- 自定义模板是否存在。

路径无效时在 UI 中直接提示，不启动后台任务。

## 默认工作目录

App 启动时调用 `ensure_default_workspace()` 创建：

```text
workspace/input
workspace/processed
workspace/merged
workspace/work
workspace/output
workspace/logs
```

这样首次运行时默认目录就是有效目录。

## 中间文件

一键处理的中间文件由 `TempWorkspaceService` 放入用户缓存目录：

```text
AppData/Local/NARI/GFileStudio/Cache/session_xxx
```

清理时机：

- App 启动；
- 新任务开始；
- 正常关闭；
- 异常退出后的下一次启动。

## 可扩展性

新增模块时应：

1. 新建 Processor；
2. 增加独立最近路径 key；
3. 使用 `PathRow` 或 `InputSourceSelector`；
4. 使用 `path_validation` 做执行前校验；
5. 使用后台 Worker 执行；
6. 增加自动测试。
