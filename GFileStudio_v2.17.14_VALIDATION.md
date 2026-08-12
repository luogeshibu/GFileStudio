# G File Studio v2.17.14 验证报告

## 修复内容

问题发生在“馈线图合并 -> 合并主母线为一条”开启时：多余 Bus 已删除，且 XML 中的 `node_area/link/p_FatherObjId` 已成功改接到保留 Bus，但 `required_target_ids` 仍保留合并前的 Bus ID，导致最终完整性校验把合法删除误判为引用失效。

本版本修复：

1. `merge_aligned_top_buses()` 返回 `removed_id_map`，记录 `旧 Bus ID -> 保留 Bus ID`。
2. 删除 Bus 前继续全图重写引用。
3. 主母线合并完成后，将 `required_target_ids` 使用同一映射同步更新。
4. 最终 `validate_final_layer()` 只要求保留后的真实目标存在。

## 回归验证

- 主母线合并单元测试：通过。
- 删除 Bus 后 required target 重映射测试：通过。
- merge engine 相关测试：通过。
- 全量自动化测试：151 passed。

## 行为保持

- 保留第一条顶部水平 Bus 的 ID。
- 其余对齐的顶部 Bus 删除。
- 所有馈线引用改接到保留 Bus。
- BusDis 不参与主母线删除。
- ID 规则模板、环网柜识别及其他模块逻辑未修改。
