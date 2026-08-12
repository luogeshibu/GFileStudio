# G File Studio v2.17.21 Validation

本版本仅升级“馈线图合并 -> 主母线处理”。

## 规则

1. 勾选“按 Bus keyid 合并主母线”前，读取每个参与 G 文件最顶部有效水平 `<Bus>` 的 `keyid`。
2. 任一文件顶部 Bus 没有非空 keyid，则该功能不可启用，也会在执行阶段再次拦截。
3. 用户排序中，相邻且 keyid 完全相同的馈线合并为一条 Bus；不同 keyid 保持独立。
4. 同一 keyid 必须连续出现。A-B-A 这类排序直接报错：`馈线排序不准确，母线 keyid 被阻断`。
5. G 根节点 facID/facName 均可用时，若检测到不同厂站则拒绝主母线合并；不根据文件名猜测厂站。
6. 每个 keyid 分组分别保留第一条 Bus ID，删除组内其余 Bus，并同步重写 link/node_area/p_FatherObjId 与最终 required_target_ids。

## 回归测试

`pytest -q`：166 passed。

新增覆盖：缺失 keyid、A-B-A 阻断、已知跨厂站、A-A-B-B-B-B 分组母线合并。
