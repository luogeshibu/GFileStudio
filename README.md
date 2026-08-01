# G File Studio v2.13.2

G File Studio 是用于处理 XML 格式 `.sln.pic.g` / `.g` 文件的 PySide6 桌面工具。本版基于 v2.13.1，只重新定义“带 BusDis 环网柜统一”功能：由调整柜高改为统一相邻环网柜的垂直 Y 间距。其他业务逻辑保持不变。

## v2.13.2 更新

### BusDis 环网柜垂直间距

启用：

```text
统一带 BusDis 的环网柜垂直间距（仅整体移动 Y）
```

后，可输入“相邻柜顶 Y 间距”，默认 300 像素。该数值表示：

```text
后一个环网柜顶部 Y = 前一个环网柜顶部 Y + 用户输入值
```

处理规则：

- 只处理外框内存在 `<BusDis>` 的环网柜；
- 按 X 位置识别不同竖直馈线列，各列独立处理；
- 每列按外框 Y 从小到大排序；
- 每列最上方环网柜保持原位置不动；
- 后续环网柜按指定间距依次向下排列；
- 环网柜外框、柜内设备、柜外标题、状态图标、H.T/SMR 等周边图元整体沿 Y 方向移动；
- 柜间连接线根据两端柜体的新位置自动平移或伸缩；
- 不压缩、不拉伸环网柜，不修改柜高、柜宽及任何 X 坐标。

输入框使用防滚轮 `IntegerInput`，鼠标滚轮、上下方向键和 PageUp/PageDown 不会误改数值。

### 保留功能

- ID 操作和环网柜组合操作仍使用互斥圆形单选框；选中后为绿色实心圆并保留中心白点；
- 环网柜增强操作仍按竖列展示并支持多选；
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
release\GFileStudio_v2.13.2_Windows_x64.zip
```
