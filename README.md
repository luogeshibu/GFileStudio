# G File Studio v2.8.0

G File Studio 是用于批量处理 XML 格式 `.sln.pic.g` 文件的 PySide6 桌面工具。本版本以 v2.7.0 为基线，修复图形边距调整对线状图元宽高的误判，并将 ID 操作和图框模板模式改为更醒目的复选框式互斥选择。

## 主要模块

- 一键处理：串联基础处理、馈线图合并、图形边距调整和图框添加。
- 基础处理：精确替换直属 Layer 图元属性、删除匹配图元、按选择检查/修复重复 ID，并可组合全部环网柜。
- 馈线图合并：模糊查询并导入指定文件，按用户列表顺序对齐和合并。
- 图形边距调整：将主体图形调整到指定画布四边距，默认均为 500。
- 图框添加：使用内置或客户模板添加 SLD 图框。

## v2.8.0 更新

### 图形边距严格按用户输入值计算

图形边距调整现在按真实可见几何边界计算主体范围。对于 `ConnectLine`、`Line`、`Bus`、`BusDis`、`FeedLine` 等线状图元，优先使用 `d` 路径或 `x1/y1/x2/y2` 端点，不再把绘图工具内部的 `w`/`h` 参数当作可见尺寸。

例如某些 `ConnectLine` 带有 `w="5000"`，但实际路径只有几十像素。旧逻辑会把画布错误扩大到 7784；新逻辑会根据真实路径计算，并严格验证：

```text
主体左边距 = 用户输入左边距
主体上边距 = 用户输入上边距
主体右边距 = 用户输入右边距
主体下边距 = 用户输入下边距
```

用户提供的 `test-test-test.sln.pic.g` 使用四边 500 处理后：

```text
原画布：2445 × 2668
新画布：2865 × 3111
实际边距：左 500、上 500、右 500、下 500
```

输出写入前和写入临时文件后都会再次解析验证四边距，验证失败时不生成最终文件。

### 选择控件改为醒目的复选框样式

以下互斥选择不再使用不明显的小圆点：

- 基础处理的“不处理 ID / 检查重复 ID / 检查并修复重复 ID”；
- 图框添加的“使用程序内置模板 / 使用客户自定义模板”。

现在使用互斥复选框，并增加更大的勾选框、蓝色选中边框和浅蓝背景。用户仍然只能选择其中一个选项。

## v2.7.0 更新

### 基础处理统一执行模式

“ID 校验与修复”不再使用两个独立执行按钮，而改为单选模式：

```text
不处理 ID
检查重复 ID
检查并修复重复 ID
```

用户选择后统一点击“开始基础处理”。检查与修复结果只输出到当前任务日志，不再生成 CSV 报告。单文件模式处理所选文件，目录模式逐个处理目录第一层全部 G 文件；不同文件之间不比较 ID。

重复 ID 修复继续遵循：

- 第一处 ID 保留；
- 后续重复项参考当前文件同类 XML 元素的主流前缀和固定总位数；
- ID 模型为 `前缀 + 固定宽度顺序号`；
- 无法推断同类格式时回退到原 ID 向上递增方式；
- 原有重复 ID 引用继续指向第一处，不猜测性改写引用归属。

### 环网柜图元组合

基础处理新增可选项：

```text
组合文件中的所有环网柜
```

处理规则：

1. 只识别 G 根节点直属 Layer 下的直属 `<rect>`；每个 `<rect>` 代表一个环网柜矩形框。
2. 每个 `<rect>` 对应一个直属 `<Merge>`。
3. 只把**完整边界位于该 rect 框内**的直属图元放入 Merge。
4. 任何部分位于框外的连接线、状态图标、标题文字或其他图元都不组合。
5. 文件中已有 Merge 会被移除并按同一严格规则重建，避免历史组合包含框外图元。
6. Merge 后连续的 `mergesize` 个直属元素就是组合成员；`mergesize` 会与实际成员数保持一致。
7. 原有 Merge 可复用 ID 和样式；新 Merge 使用当前文件的唯一 ID 分配逻辑。
8. 单文件处理一个文件；目录模式处理目录第一层全部 G 文件。

使用提供的 `$combine-test-20260730.sln.pic.g` 回归样本验证：

```text
处理前：2 个 rect，1 个 Merge
处理后：2 个 rect，2 个 Merge
每个 Merge：23 个框内直属图元
框外连接线、状态图标和 35092 标题：均未组合
```

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
release\GFileStudio_v2.8.0_Windows_x64.zip
```

分享时必须发送完整 ZIP，不能只发送 EXE。

## 配置与缓存

- 最近路径：`AppData\Local\NARI\GFileStudio\Config\user_settings.ini`
- 一键处理中间缓存：`AppData\Local\NARI\GFileStudio\Cache`
- 内置模板：`resources\templates\SLD-Drawing-Frame-Template.sln.pic.g`
- 程序图标：`resources\icons\app.ico`、`app.png`
