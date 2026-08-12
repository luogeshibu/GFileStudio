# G File Studio v2.17.17 Validation

## Changes
- ID 模板扫描结果弹窗改为固定尺寸可滚动窗口，长内容不再撑高窗口。
- 应用展示名称更新为“G File Studio · NARI 国际业务 XML 图形处理工具”。
- 左侧品牌副标题更新为“NARI 国际业务 XML 图形处理工具”。

## Verification
- `python -m compileall -q g_file_studio`: passed
- `pytest -q`: 158 passed

## Scope
- 未修改 ID 规则、ID 修复、馈线合并、基础处理、图框、环网柜等业务逻辑。
