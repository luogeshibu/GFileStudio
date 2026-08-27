# G File Studio v2.18.46 Validation

## 本次调整
- 左侧导航顺序：`异常小尺寸图元检测 → ID 检查与修复 → 图元标准检查 → 环网柜处理 → ...`。
- `图元标准检查` 改为严格只读：只检查、告警、生成 CSV/HTML 报告，不再存在“检查并升级”动作，也不生成 `final` G。
- 图元标准检查的 workspace 输出目录移动到 G 文件输入区域下方。
- 检测到 ACTIVE 标准不一致时，界面弹出 `图元标准不一致` 告警；日志列出当前/期望 devref，并单独提示几何不一致。
- `基础处理 → 通用图元升级` 更名为 `基础处理 → 同类图元版本升级`；只处理同一设备语义/同一 XML 类型的 OLD → NEW 版本变化。
- SMART 图元误用到 NORMAL、NORMAL 图元误用到 SMART 被明确归类为“图元类型/变体使用错误”，不是“图元版本升级”。
- 吉达固定流程相关文案同步改为“图元类型/变体纠正”，业务算法未改。

## 安全边界
- 图元标准检查继续复用原 ACTIVE Profile 比较引擎，但只在内存 XML 树中执行比较，不写源文件。
- 同类图元版本升级的 OLD/NEW 配对、旋转、pin、AlignCenter、ConnectLine 锚点保护算法未改变；本版仅调整模块边界、只读约束与用户可见术语。
- 设备 ID、keyid、node_area 和拓扑关系相关业务逻辑未改。

## 验证
- `python -m compileall -q g_file_studio app.py`：通过。
- `pytest -q`：`367 passed, 2 skipped`。
