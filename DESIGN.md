# G File Studio v2.2.0 设计说明

## 架构

```text
PySide6 UI
    ↓
Processor 业务层
    ↓
Engine XML 算法层
    ↓
ElementTree
```

UI 不直接修改 XML。所有处理逻辑均可由界面、测试或后续命令行入口复用。

## 核心模块

```text
g_file_studio/
├── engines/
│   ├── merge_engine.py
│   ├── frame_engine.py
│   └── margin_engine.py
├── processors/
│   ├── basic_processor.py
│   ├── merge_processor.py
│   ├── margin_processor.py
│   ├── frame_processor.py
│   └── pipeline_processor.py
├── services/
│   ├── user_settings_service.py
│   ├── temp_workspace_service.py
│   ├── template_service.py
│   └── paths.py
└── ui/
    ├── pages/
    └── widgets/
```

## 独立 INI 设置

`UserSettingsService` 使用 `configparser` 和 `platformdirs`，不依赖程序安装目录或临时 QSettings 注册表配置。

配置路径：

```text
AppData/Local/NARI/GFileStudio/Config/user_settings.ini
```

路径控件同时保存：

- 完整文件路径；
- 完整目录路径；
- 最近浏览目录；
- 当前输入模式；
- 模板模式和客户模板路径。

## 图形边距算法

1. 读取 G 画布尺寸和直属 Layer；
2. 尝试识别由四条长 `line` 构成、覆盖画布大部分区域的矩形外框；
3. 以外框线为种子，通过几何邻接识别标题栏、签字栏等图框组件；
4. 图框组件从主体图形边界计算中排除；
5. 计算主体图形子树边界，包含 `x/y/w/h`、端点、圆心半径和 `d` 坐标；
6. 平移主体到用户指定左、上边距；
7. 根据主体宽高和右、下边距计算新画布；
8. 已有图框保持原四边距，外框线拉伸，组件按最近边或角锚定平移；
9. 原子写出并重新解析验证。

## 一键流程已有图框策略

- 图形边距调整检测到旧图框：保留并适配；
- 添加图框阶段：跳过这些文件，避免重复图框；
- 未检测到旧图框：正常使用内置或客户模板添加图框。

## 合并文件子集与顺序

`FileOrderEditor` 维护两个集合：

- `_rows`：当前保留、实际参与合并的文件及顺序；
- `_excluded_names`：用户从本次合并列表排除的文件名。

“删除所选”只修改这两个内存集合，不执行文件系统删除。重新扫描时保留排除集合和用户顺序，新发现文件追加到末尾；“恢复全部并排序”清空排除集合。

`merge_engine.discover_files(..., allow_subset=True)` 允许有序列表只包含输入目录中的文件子集，同时继续校验：

- 顺序项必须只是文件名；
- 后缀必须是 `.sln.pic.g`；
- 不允许重复；
- 所选文件必须真实存在。

`merge_processor` 在用户提供有序列表时启用子集模式，因此最终合并集合与界面剩余行完全一致。
