# G File Studio v2.17.24 Validation

## 修改范围

仅处理版本发布编号与界面品牌文案，不修改业务处理逻辑。

## 修复

- `build_exe.ps1` 不再硬编码 `GFileStudio_v2.17.1_Windows_x64.zip`。
- 打包脚本自动读取 `g_file_studio.__version__` 并生成 `GFileStudio_v<version>_Windows_x64.zip`。
- `g_file_studio.__version__` 与 `pyproject.toml` 同步为 2.17.24。
- 窗口标题：`G File Studio · NARI 国际业务部`。
- 左侧副标题：`NARI 国际业务部`。
- 模式标签：`G 文件处理工具`。

## 回归测试

执行 `python -m pytest -q`。

结果：**183 passed**。
