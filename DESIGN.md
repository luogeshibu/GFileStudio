# G File Studio v2.4.0 设计说明

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
│   ├── merge_frame_inspector.py
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
2. 优先读取图框身份标记：新版本添加图框时会在根节点和每个图框直属元素写入 `gfs_frame_type`、`gfs_frame_template` 与 `gfs_frame_component`；
3. 对旧版未带标记的内置图框，使用严格结构指纹识别：四条外框线、左上标题框、右下 12 个文字与 5 条分隔线等；
4. 禁止使用“从外框开始无限几何连通扩散”，避免馈线与图框接触时把主体全部误判为图框；
5. 只有确认属于内置图框的直属元素才从主体边界计算中排除；
6. 计算主体图形子树边界，包含 `x/y/w/h`、端点、圆心半径和 `d` 坐标；
7. 平移主体到用户指定左、上边距，并根据主体宽高与右、下边距计算新画布；
8. 内置图框保持原四边距，外框线动态拉伸，其他内置图框组件按最近边或角锚定平移；
9. 检测到客户图框或无法确认来源的图框时，抛出用户可读错误，要求先删除图框；
10. 原子写出并重新解析验证。

## 一键流程已有图框策略

- 确认是内置图框：保留并适配，添加图框阶段跳过该文件；
- 客户图框或来源不明：停止流程并提示先删除图框；
- 未检测到图框：正常使用内置或客户模板添加图框。

## 合并候选目录、模糊查询与顺序

`FileOrderEditor` 分为两个集合：

- `_catalog`：输入目录中全部候选文件的检查结果，包括可用文件、内置图框文件、非内置图框文件和检查失败文件；
- `_rows`：用户通过模糊查询对话框实际导入、最终参与合并的文件及顺序。

点击“加载 / 检查”时使用 `QProgressDialog` 显示当前文件和总进度。`merge_engine.inspect_merge_candidates()` 逐个解析候选文件，返回状态、对齐基准和图框分类。

`CandidateImportDialog` 提供：

- 文件名模糊查询；
- 多关键字同时包含匹配；
- 全选当前结果；
- 取消当前选择；
- 确认导入；
- 已导入文件置灰显示；
- 非内置图框和检查失败文件禁用勾选。

主列表继续支持删除、置顶、上移、下移和置底。`merge_engine.discover_files(..., allow_subset=True)` 只接收主列表中的文件名，因此最终合并集合与界面完全一致。

## 合并阶段图框识别与移除

`merge_frame_inspector.py` 专门负责合并输入图框分类：

1. 新版内置图框优先使用根节点和直属组件标记识别；
2. 旧版内置图框使用纯几何结构指纹识别：四条大外框线、左上标题矩形及 poke、右下信息矩形、2 条水平分隔线和 3 条垂直分隔线；
3. Text 的 `ts` 内容、标题、Draw、Approve、Issue、姓名和日期完全不参与识别；
4. 内置图框组件从内存中的 XML 树移除，不修改源文件；
5. 移除后清理指向图框真实 ID 的引用，并清除根节点图框身份标记；
6. 客户图框、未知外框、大矩形外框或损坏的内置图框均禁止参与合并；
7. 合并执行前会再次分类，即使 UI 列表状态过期也不会让非内置图框进入最终输出。

