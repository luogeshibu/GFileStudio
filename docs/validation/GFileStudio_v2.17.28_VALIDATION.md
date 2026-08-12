# G File Studio v2.17.28 验证记录

## 本版本范围

仅新增/调整以下内容：

1. 新增独立“异常小尺寸图元检测”模块，并放在“ID 检查与修复”之前。
2. 检测对象：`ConnectLine`、`FeedLine`、`Bus`、`BusDis`；默认阈值 10，`w < 阈值` 且 `h < 阈值` 时报告异常。`Bus` 不区分方向。
3. 扫描输出 CSV + HTML，字段包含文件名、元素类型、XML ID、x/y/w/h、keyid、异常原因。
4. 删除必须由用户在扫描结果表中选择；存在非空 keyid 时，删除前再次列出文件、元素类型、XML ID、keyid 并要求确认。输出修改副本，不覆盖原文件。
5. 馈线合并“主母线处理”移除原 `w < 10` 特殊过滤；异常小尺寸 Bus 统一交给新模块处理。

## 自动化测试

执行：`python -m pytest -q`

结果：**188 passed**。

新增覆盖：
- 任意方向 Bus 的异常小尺寸检测；
- ConnectLine / FeedLine / Bus / BusDis 四类目标元素；
- 非目标 Text 不进入报告；
- 删除选中图元时输出副本并清理指向被删 ID 的引用；
- 主母线处理不再按 `w < 10` 过滤。

## 版本一致性

- `g_file_studio.__version__ = 2.17.28`
- `pyproject.toml = 2.17.28`
- `build_exe.ps1` 继续自动读取程序版本生成发布 ZIP 文件名。
