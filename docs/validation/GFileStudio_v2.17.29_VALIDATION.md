# G File Studio v2.17.29 验证记录

## 本次范围

仅更新“异常短线图元检测”和“ID 检查与修复”的报告/交互体验；其他业务模块未修改。

### 异常短线图元检测
- 原“异常小尺寸图元检测”更名为“异常短线图元检测”。
- 检测对象仍为 ConnectLine、FeedLine、Bus、BusDis，检测规则仍为 w 与 h 同时小于用户阈值。
- 扫描按钮放在“执行与日志”区域；逐文件扫描结果及每条异常记录写入可复制的 QPlainTextEdit 日志。
- 每次扫描生成独立 CSV + HTML：`short-line-anomalies-YYYYMMDD_HHMMSS.csv/html`。
- 同一秒重复生成时自动追加 `-01/-02...`，不会覆盖上一次报告。
- 新增“打开本次 HTML 报告”。
- 保留“删除选中异常图元”，新增“删除全部异常图元”。
- 删除范围内只要存在非空 keyid，仍会逐项列出文件、元素类型、XML ID、keyid 并二次确认。

### ID 检查与修复
- “扫描当前 G”从 ID 规则模板按钮区移动到“执行与日志”区域。
- 扫描进度继续显示，并把逐文件进度、模板覆盖、完整异常 ID 等结果输出到可复制日志。
- ID 检查/修复任务每次生成独立 CSV + HTML：`id-check-report-YYYYMMDD_HHMMSS.csv/html`。
- 同一秒重复生成时自动追加 `-01/-02...`，不会覆盖历史报告。
- 新增“打开本次 HTML 报告”。
- ID 模板、强制修复、新 ID 分配规则不变。

## 验证
- `pytest -q`：190 passed。
- `small_element_engine.write_reports()` 烟测：CSV/HTML 可正常生成。
- `process_ids()` CHECK 模式烟测：可正常生成时间戳 CSV/HTML 报告。
- `python -m py_compile`：本次修改的 Python 源码编译通过。

## 版本
- `g_file_studio.__version__ = 2.17.29`
- `pyproject.toml = 2.17.29`
