# G File Studio v2.14.0

G File Studio 是用于处理 XML 格式 `.sln.pic.g` / `.g` 文件的 PySide6 桌面工具。本版基于 v2.13.2，删除 BusDis 环网柜整体 Y 间距调整功能，新增环网柜红色 `channel_status` 状态点的框内定位功能。其他业务逻辑保持不变。

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
.un_dev.ps1
```

## 打包

```powershell
.uild_exe.ps1
```

输出：

```text
dist\GFileStudio\GFileStudio.exe
release\GFileStudio_v2.14.0_Windows_x64.zip
```
