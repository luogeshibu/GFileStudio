# G File Studio v2.9.0

G File Studio 是用于处理 XML 格式 `.sln.pic.g` / `.g` 文件的 PySide6 桌面工具。本版本以 v2.8.0 为基线，保留严格四边距、馈线图合并、图框添加、重复 ID 处理和环网柜框内组合，并新增环网柜取消组合、线路/母线颜色修改以及安全的输出冲突处理。

## 主要模块

- 一键处理：串联基础处理、馈线图合并、图形边距调整和图框添加。
- 基础处理：属性替换、元素删除、重复 ID 检查/修复、环网柜组合/取消组合、线路与母线颜色修改。
- 馈线图合并：从候选目录查询并导入指定文件，按用户列表顺序对齐和合并。
- 图形边距调整：严格将主体图形调整到用户指定的画布四边距。
- 图框添加：使用程序内置模板或客户自定义模板添加 SLD 图框。

## v2.9.0 更新

### 1. 环网柜组合与取消组合

基础处理的“环网柜组合处理”提供三个互斥选项：

```text
不处理环网柜组合
组合所有环网柜
取消所有环网柜组合
```

统一点击“开始基础处理”执行，支持单文件和目录第一层全部 G 文件。

组合规则：

1. 只识别 G 根节点直属 `Layer` 下的直属 `<rect>`。
2. 每个 `<rect>` 对应一个 `<Merge>`。
3. 只有完整可见边界位于该矩形框内部的直属图元才进入组合。
4. 框外连接线、状态图标、标题文字和任何部分伸出框外的图元均不组合。
5. 已有环网柜 Merge 会按同样规则重建；不含 `<rect>` 的其他业务 Merge 完整保留。
6. 新建 Merge 模拟图形编辑器格式：左、上相对 rect 各外扩 1，右、下边界保持一致。
7. 新 Merge ID 优先复现当前文件的 `20 + 固定宽度顺序号` 格式，并沿用文件中的最大图元顺序号。

使用 `no-combine.sln.pic.g` 验证：

```text
rect：1
新 Merge ID：20000028
mergesize：23
mergex/mergey/w/h：524 / 411 / 221 / 221
```

该结果与用户提供的 `combine.sln.pic.g` 手工组合格式一致。

取消组合规则：

- 只删除成员范围中包含 `<rect>` 的 Merge 头元素；
- 原成员、坐标、ID、引用、属性和顺序全部保持不变；
- 不含 `<rect>` 的其他业务 Merge 不删除；
- `combine.sln.pic.g` 取消组合后的 Layer 图元结构与用户提供的 `cancel-combine.sln.pic.g` 一致。

### 2. 线路与母线颜色

基础处理新增四类可独立启用的颜色规则：

```text
馈线       <FeedLine>
连接线     <ConnectLine>
配网母线   <BusDis>
主网母线   <Bus>
```

通过颜色选择器设置颜色。程序只同步修改：

```text
lc  = R,G,B
lcc = #RRGGBB
```

不修改填充色、线宽、坐标、ID、`link`、`node_area` 或 `p_FatherObjId`。若图元启用了动态颜色，日志会提示运行时颜色可能被动态规则覆盖。

### 3. 基础处理输出冲突保护

当输入和输出路径相同，或输出目录中已经存在同名文件时，程序不再静默覆盖，而是提示选择：

```text
自动添加时间戳（推荐）
覆盖原文件/已有文件
取消任务
```

- 自动添加时间戳：同一批任务统一生成 `原文件名-yyyyMMdd_HHmmss.sln.pic.g`。
- 安全覆盖：先写入同目录临时文件，重新解析验证成功后再原子替换。
- 取消任务：不修改任何文件。

### 4. 选择控件样式统一

以下互斥选项统一使用相同的卡片式复选框样式：

- ID 校验与修复；
- 环网柜组合处理；
- 图框内置/客户模板选择；
- 线路与母线颜色启用项。

选中时显示蓝色勾选框、蓝色边框和浅蓝背景，未选中和禁用状态也采用统一尺寸、间距和字体。

### 5. v2.8.0 严格四边距修复继续保留

线状图元 `ConnectLine`、`Line`、`Bus`、`BusDis`、`FeedLine` 等优先使用 `d` 路径或端点计算真实可见边界，不把 `w="5000"` 等内部参数当作真实宽度。用户输入四边距均为 500 时，输出会强制验证左、上、右、下实际边距均为 500。

## 基础处理执行顺序

每个文件按以下顺序执行：

```text
属性替换和匹配元素删除
→ 环网柜组合或取消组合
→ 线路与母线颜色修改
→ 重复 ID 检查或修复
→ 写入临时 XML 并重新解析验证
→ 输出文件
```

所有处理结果只写入当前任务日志，不生成额外 CSV。

## 运行

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Get-ChildItem -Path . -Recurse -File | Unblock-File

.\setup_env.ps1 -Dev
.\run_dev.ps1
```

## 打包

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_exe.ps1
```

生成：

```text
dist\GFileStudio\GFileStudio.exe
release\GFileStudio_v2.9.0_Windows_x64.zip
```

分享给客户时必须发送完整 ZIP，不能只发送 EXE。

## 配置与缓存

- 用户设置：`AppData\Local\NARI\GFileStudio\Config\user_settings.ini`
- 一键处理中间缓存：`AppData\Local\NARI\GFileStudio\Cache`
- 内置模板：`resources\templates\SLD-Drawing-Frame-Template.sln.pic.g`
- 程序图标：`resources\icons\app.ico`、`app.png`
