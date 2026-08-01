# G File Studio v2.10.0

G File Studio 是一个用于处理 XML 格式 `.sln.pic.g` / `.g` 文件的 PySide6 桌面工具。v2.10.0 基于 v2.9.1，重点增强环网柜 Merge 兼容性，并将整个桌面界面调整为电网图形工作台风格。

## 主要模块

- 一键处理：串联基础处理、馈线图合并、图形边距调整和图框添加。
- 基础处理：属性替换、元素删除、重复 ID 检查/修复、环网柜组合/取消组合、线路与母线颜色修改。
- 馈线图合并：按用户导入列表和顺序完成垂直对齐、ID 冲突处理和画布合并。
- 图形边距调整：严格按照用户设置保持主体图形到画布四边的距离。
- 图框添加：使用内置模板或客户模板添加 SLD 图框。

## v2.10.0 更新

### 1. 环网柜组合兼容性增强

用户提供的编辑器样本证明，不同 G 文件中 `Merge.mergesize` 存在两种历史写法：

```text
mergesize = 成员数量
mergesize = Merge 头 + 成员总数
```

因此 v2.10.0 不再用一个固定公式切分 Merge 成员，也不再因为历史文件的连续区间看似重叠而直接失败。

新的识别顺序：

```text
Merge 的 mergex / mergey / w / h 几何范围
→ Merge 后、下一个 Merge 前的几何成员
→ 兼容 mergesize 两种历史语义
→ 无有效几何时才使用顺序兜底
```

环网柜 Merge 通过以下关系识别：

- Merge 几何范围包含一个直属 `<rect>`；
- Merge 与 rect 的中心位置接近；
- Merge 面积不会远大于 rect，避免把覆盖整张图的业务组合误判为环网柜。

这解决了：

- AJWD-22 文件中 14 个历史 Merge 的 `mergesize` 写法不完全一致；
- 取消组合后仍提示存在包含 `<rect>` 的 Merge；
- 多个 Merge 被误报为连续成员区间重叠；
- 旧组合成员数量与几何范围不一致时无法处理。

### 2. 新建 Merge 使用编辑器标准成员数

用户新增的 `$combine-test.sln.pic.g` 明确显示：

```xml
<Merge mergesize="2" />
<CBreaker />
<CBreaker />
```

因此本版本新建环网柜 Merge 时统一写入：

```text
mergesize = 实际成员数量
```

程序仍可读取旧文件中的 `成员数量 + 1` 写法，但新输出统一采用编辑器对照样本确认的格式。

### 3. 组合与取消组合规则

组合时：

1. 只识别 G 根节点直属 `Layer` 下的直属 `<rect>`；
2. 每个 rect 创建一个 Merge；
3. 只有完整边界位于 rect 内部的直属图元进入组合；
4. 框外连接线、状态图标和标题文字保持在 Merge 外；
5. 原有环网柜 Merge 通过几何关系识别并重建；
6. 不含 rect 的其他业务 Merge 保持不变；
7. 新 Merge ID 继续使用当前文件同类 20 前缀及固定位数规则。

取消组合时：

- 只删除几何范围对应 rect 的 Merge 头元素；
- 保留所有成员、坐标、ID、引用、颜色和业务属性；
- 自动把被释放的 `<rect>` 移到其框内设备之前，使外框在编辑器中处于断路器、文字和连接线的下层；
- 已经位于设备下层的 rect 不重复移动；
- 不删除与 rect 无关的普通业务 Merge。

### 4. 电网专用界面风格

界面改为统一的“电网图形工作台”视觉体系：

- 深海军蓝侧边运行区；
- 电网绿作为主操作、选中状态和进度颜色；
- 青绿色用于连接、提示和悬停状态；
- 暖黄色仅用于告警；
- 白色功能卡片配合浅灰绿色工作区；
- 表格、输入框、复选框、帮助按钮和状态栏统一配色；
- 侧栏增加 `GRID GRAPHICS · 电网图形` 标识；
- 窗口标题改为 `G File Studio · 电网图形处理`。

该主题采用类似电网行业控制软件的绿色视觉语言，但不使用任何具体企业商标或专有标识，可用于不同项目交付。

### 5. 现有功能继续保留

- 严格四边距及 `ConnectLine w="5000"` 边界修复；
- FeedLine、ConnectLine、BusDis、Bus 静态线色修改；
- ID 检查和同类格式修复；
- 输入输出同路径的时间戳、安全覆盖和取消策略；
- 内置图框右边框错位修复；
- 最近目录和完整路径记忆。

## 基础处理执行顺序

```text
属性替换和匹配元素删除
→ 环网柜组合或取消组合
→ 线路与母线颜色修改
→ 重复 ID 检查或修复
→ 临时写出并重新解析验证
→ 安全输出
```

检查和处理结果写入当前任务日志，不生成额外 CSV。

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
release\GFileStudio_v2.10.0_Windows_x64.zip
```

分享给客户时必须发送完整 ZIP，不能只发送 EXE。

## 配置与缓存

- 用户设置：`AppData\Local\NARI\GFileStudio\Config\user_settings.ini`
- 一键处理中间缓存：`AppData\Local\NARI\GFileStudio\Cache`
- 内置模板：`resources\templates\SLD-Drawing-Frame-Template.sln.pic.g`
- 程序图标：`resources\icons\app.ico`、`app.png`
