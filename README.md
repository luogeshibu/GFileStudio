# G File Studio v2.16.1

G File Studio 是用于处理 XML 格式 `.sln.pic.g` / `.g` 文件的 PySide6 桌面工具。本版修复 v2.16.0 连接点重建可能把原有断路器、刀闸端口编号交换或合并的问题。连接点修复改为“保守增量模式”：允许少修，禁止把原来正确的连接修坏。

## v2.16.1 更新

### 保守连接点修复

继续使用基础处理中的复选框：

```text
☐ 修复连接点（补齐 node_area / link）
```

勾选后点击“开始基础处理”，程序遵循以下强制规则：

1. 原文件中已有的 `node_area` / `link` 连接组原样冻结，不删除、不改号、不交换端口；
2. 先根据设备端和连接线端已有的单边引用补齐另一边缺失引用；
3. 只有连接线端点与设备真实端口唯一匹配时，才新增一组连接；存在多个等距候选时跳过并写入告警；
4. 端口模板学习保留设备原来的 `own_port` 编号，不再按坐标排序重新编号；
5. 设备签名包含 `tag + devref + rotate + w + h`，避免不同尺寸图标共用错误模板；
6. 设备位置只处理已验证的正半像素 X 偏移，例如 `2197.5 → 2197`；只改设备 `x`，不修改任何连接线坐标；
7. 每个设备移动前验证全部已知连接，验证失败立即跳过，相当于逐设备回滚；
8. 输出前再次检查所有原连接仍完整存在，任何原连接丢失或改号时该文件处理失败，不输出错误结果。

### 修改范围

允许修改：

```text
设备：仅 x（且只限验证通过的半像素吸附）、缺失的 node_area
ConnectLine / FeedLine：仅缺失的 node_area / link
Bus / BusDis：仅缺失的 node_area
```

明确禁止：

```text
删除或改写原 node_area/link
修改连接线 d/x/y/w/h
修改设备 y、宽高、旋转、ID、文字、颜色、devref
修改 Merge、rect、Status、画布或其他业务属性
```

### 回归验证

- 小型连接问题文件仍新增 24 处缺失引用，Q1/Q2 和四个接地刀闸连接恢复；
- AJWD-06 半像素样本保守吸附 41 个已验证设备，连接线坐标修改 0 个；
- MODE-ZZZ 原文件新增缺失引用，但原有端口编号修改 0 处、删除 0 处；
- 重复执行第二次无变化；
- 自动化测试 112 项通过。

## v2.15.1 更新

### “修复连接点”改为复选框

- 勾选后随“开始基础处理”统一执行；
- 不勾选时完全跳过；
- 选择状态保存到 `basic/repair_connection_points`。

## v2.14.0 更新

### 删除环网柜整体 Y 调整

基础处理页面不再提供“统一带 BusDis 的环网柜垂直间距”，处理引擎也不会再整体移动环网柜、柜内设备、柜外标题或柜间连接线。原 G 文件中的环网柜与线路 Y 坐标保持不变。

### 红色 channel_status 状态点定位

启用：

```text
移动环网柜红色状态点（channel_status）
```

后，程序只处理：

```xml
<Status devref="#channel_status.zt.icn.g:channel_status" ... />
```

定位规则：

- 只在外框内含 `<BusDis>` 的环网柜中查找对应红色状态点；
- 每个环网柜最多选择一个距离本柜 BusDis 最近的 `channel_status`；
- 可选择左上角、上边中点、右上角、左边中点、右边中点、左下角、下边中点、右下角；
- 默认位置为“左下角”，默认距边 5 像素；
- 只修改该 `<Status>` 的位置坐标；不移动或缩放 rect、BusDis、设备、文字、连接线、Merge 或画布；
- 状态点的 ID、devref、颜色、动态属性、宽高、旋转与缩放保持不变。

### 保留功能

- ID 操作和环网柜组合操作继续使用互斥圆形单选框；
- SMART 环网柜外框改色、带 Bus 外框删除及标题定位保持不变；
- 属性替换、元素删除、ID 修复、线路与母线改色、馈线图合并、图形边距调整和图框添加保持不变。

## 运行

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Get-ChildItem -Path . -Recurse -File | Unblock-File
.\setup_env.ps1 -Dev
.\run_dev.ps1
```

## 打包

```powershell
.\build_exe.ps1
```

输出：

```text
dist\GFileStudio\GFileStudio.exe
release\GFileStudio_v2.16.1_Windows_x64.zip
```
