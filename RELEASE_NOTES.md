# v2.18.162

## Poke 跳转分类排除与距离规则

- Poke 运行时仅读取服务器图元同步管理的本地分类标记，不额外连接服务器。
- FUSE、LBS、AR、SEC、Transformer_OH 图元周边 300 以内的站点名称不创建或更新站点跳转。
- 相邻环网柜名称距离站点超过 200 时不再作为站点跳转的 `locateLabel`。

---

# v2.18.161

## 精简同步管理表格

- 移除界面显示的“来源”“主体 ID”“图形 G 发现 devref”三列。
- 内部数据字段不删除，缓存、分类标记和后续程序仍可继续使用。

---

# v2.18.160

## 启动恢复本地图元缓存

- 新部署首次打开且没有同步记录时，表格保持空白，需手动点击同步。
- 完成过同步后，后续打开直接显示本地缓存和分类标记，不连接服务器。
- 服务器同步仍按照每日后台检查规则执行。

---

# v2.18.159

## 显示服务器文件更新时间

- 文件名不变时仍复用本地图元和分类标记。
- 同步结果会提醒哪些服务器文件发生了元数据更新时间变化，并显示相对路径和 UTC 时间。
- 内容变化只做提示，不重新下载或解析图元。

---

# v2.18.158

## 图元同步按需加载

- 启动只显示管理页面，不自动加载本地图元表，也不连接服务器。
- 第一次读取必须点击“同步服务器图元信息”；完成后每天自动后台同步一次。
- 只要图元文件名仍存在，服务器内容变化也继续沿用本地分类标记。

---

# v2.18.157

## 启动速度优化

- 窗口先显示，再恢复本地图元目录和分类标记，避免启动阶段长时间没有响应。
- 有本地快照时直接恢复服务器图元表，避免重复构建表格。
- 页面刷新期间复用已解析的 Profile 配置，减少重复读取本地配置文件。

---

# v2.18.156

## 启动速度优化

- 修复恢复服务器图元清单时逐行触发分类标记保存的问题。
- 自动恢复只更新界面，用户编辑或点击保存时才写入本地分类记录。

---

# v2.18.155

## 分类标记显式保存

- 增加“保存分类标记”按钮，统一保存当前表格中的分类标记。
- 保存结果会显示成功数量和失败数量，避免用户无法确认是否写入本地缓存。

---

# v2.18.154

## ID 规则表自适应布局

- ID 规则表打开时自动填充页面剩余宽度。
- 窗口缩放后继续保持最后一列自适应，不改变规则数据和处理逻辑。

---

# v2.18.153

## 分类标记持久化修复

- 修复关闭软件后重新打开，服务器图元分类标记没有自动显示的问题。
- 编辑分类标记后同时保存本地标记记录和同步快照。
- 缓存恢复时自动重新应用本地分类标记，不修改服务器内容。

---

# v2.18.152

## 服务器图元同步性能优化

- 未变化图元只复用本地缓存，不重新下载、不重新解析。
- 服务器清单没有变化时不重建 198 行表格，减少同步后的界面卡顿。
- 新增、删除、大小/修改时间变化和解析状态变化仍会触发表格刷新。

---

# v2.18.151

## 严格 `.g` 文件筛选

- 服务器图元同步只统计最终扩展名为 `.g` 的文件。
- `.g.png`、其他预览文件和非图元文件不会进入表格或数量统计。
- 旧同步缓存恢复时也执行同样的后缀过滤。

---

# v2.18.150

## 服务器图元同步清单持久化

- 修复关闭软件后服务器图元表格只恢复 187 条可解析记录、无法恢复完整服务器文件数量的问题。
- 新增本地同步快照，保存服务器目录中的全部 `.g` 文件；下次打开自动恢复完整清单。
- 同名冲突、读取/解析失败的文件继续以只读状态保留在表格中，不再被隐藏。
- 服务器仍保持严格只读，不上传、不覆盖、不删除服务器文件。

---

# v2.18.149

## 发布版本升级

- 发布版本号升级至 `2.18.149`。
- 修复源码运行 `python app.py` 时页面初始化导致的 Qt 启动崩溃。
- 保留图元库存旧名称分配接口，兼容既有调用和回归测试。

---

# v2.18.148

## Git / generated-artifact protection

- Fix `.gitignore` so `workspace/runs/` is never committed. This directory can contain very large generated G-content HTML/Excel analysis outputs.
- Ignore local packaging outputs: `release/`, `build/`, `dist/`, and `GFileStudio_v*_Windows_x64.zip`.
- Add defense-in-depth rules for generated G-content analysis reports.
- Add `GIT_LARGE_FILE_CLEANUP.md` with one-time repair commands for repositories that already tracked generated files.
- No G-file parsing, feeder/topology, Jeddah processing, drawing-frame, SSH, database, or UI business logic changed in this release.

---

# v2.18.147

## 吉达馈线处理 / 图框添加：当前模板强制覆盖已有图框

- “图框添加”现在把用户本次选择的模板视为唯一权威图框：处理前先删除可检测到的已有图框，再重新添加当前模板，不再把新图框叠加到旧图框上。
- 可自动替换的旧图框包括：G File Studio 已标记的内置/自定义图框、旧版本未带标记但可按严格指纹识别的内置图框，以及可确认位于画布外围的未标记图框。
- 对未标记外围图框的清理仅作用于通用绘图装饰元素（line/rect/Text/poke/image）；FeedLine、ConnectLine、BusDis 和设备类电气图元不进入该兜底删除集合，避免误删实时拓扑。
- 吉达固定馈线处理在“图形边距调整”前显式启用旧图框强制移除，因此即使输入 G 已经带有非内置或与当前模板不同的图框，也不会再被“请先人工删除图框”阻断；最终阶段统一使用吉达页面当前选择的模板重新添加。
- 独立“图形边距调整”模块默认行为不变：`force_remove_existing_frame=False`，仍保持原有保守识别/保护逻辑。只有吉达固定流程和“图框添加”的明确替换路径执行强制替换。
- 图框标题、Draw/Approve/Issue、四边距、ID 分配、输出文件名和输出同名文件处理逻辑均保持原有规则。

# v2.18.146

## G 图形内容解析：CBreaker 作为权威馈线根

- 所属馈线继续只允许顶部 `CBreaker(407)`、`Disconnector(408)`、`GroundDisconnector(409)` 三类设备查询 Oracle；下游任何设备均不查询 keyid/数据库关联。
- `CBreaker(407)` 现在是权威馈线根：其数据库 `BAY_ID -> BAY.NAME -> SUBSTATION.NAME` 有效后，直接确定该分支馈线。
- Disconnector/GroundDisconnector 仅作为一致性/回退证据；即使它们未关联或因历史数据指向旧 BAY，也只产生告警，不再清空已经由 CBreaker 确认的馈线。
- 从有效 CBreaker 的非 Bus 侧沿真实 `ConnectLine / FeedLine / BusDis / device link/node_area` 完整遍历，多分支全部纳入，直到自然拓扑终点；所有可达下游设备直接继承同一 `FeederName`。
- 仍禁止使用文件名、facID/facName、FeedLine 文字或空间距离补猜馈线。

# v2.18.145

## G 图形内容解析：入口锚点部分关联也可建立馈线，确认后全下游继承

- 所属馈线数据库查询仍然严格只允许每个 Bus 入口最近的三类设备：`CBreaker`→407 `breaker`、`Disconnector`→408 `disconnector`、`GroundDisconnector`→409 `grounddisconnector`。任何下游设备都不再查询 keyid 或数据库关联状态。
- 三个入口设备中，只要至少一个成功解析出 `BAY_ID -> BAY.NAME -> SUBSTATION.NAME`，即可作为该分支馈线锚点；如果另外一个或两个入口也成功解析，则所有已解析入口必须指向同一 `BAY_ID`。已解析入口 BAY 冲突时，为防止串馈线，整条分支 `FeederName` 留空并告警。
- 入口中一到两个设备未关联时仅告警，不再阻断已经由其他入口设备确认的馈线。只有三个入口设备全部未取得有效 BAY 时，该分支才保持空白并提示优先完成入口设备关联。
- 一旦入口馈线确认，程序沿真实 G 拓扑一直向下遍历 `ConnectLine / FeedLine / BusDis / 设备节点` 到自然终点；RMU、Transformer、LBS、下游 CB 等全部直接继承同一 `FeederName`，其自身 keyid/数据库是否关联完全不参与馈线判断。
- 保持 `Bus` 仅作为上游分支边界，不以 Bus 元数据判定馈线；不恢复文件名、facID/facName、标题文字或空间距离猜测。
- 馈线根发现顺序改为确定性排序，日志中的 branch 标识稳定，便于现场排查。
- 真实 `JED-CTL-AJWD.sln.pic(4).g` smoke：用户指出的 RMU `30640 / 30647 / 30652 / 30639 / 30641 / 30722 / 30629 / 30642 / 30666 / 30726 / 30643` 均处于同一 Bus-root 下游组件；仅提供该分支 CBreaker 一个有效数据库锚点时，11/11 均通过拓扑继承 `AJWD AH313`。

其余 G File Studio 业务逻辑保持 v2.18.144 不变。

# v2.18.144

## G 图形内容解析：Bus 入口三设备 + 全下游拓扑继承

- 所属馈线不再扫描整张 G 中所有 407/408/409 元素。程序先把站内 `Bus` 当作馈线起点边界，将 Bus 从电气图中移除，再按 `ConnectLine / FeedLine / BusDis / link / node_area` 识别每个 Bus 下游真实分支。
- 每个下游分支只选择距离 Bus 最近的一组 `<CBreaker>`、`<Disconnector>`、`<GroundDisconnector>` 作为馈线入口三设备；Oracle 只查询这三个入口 keyid。下游即使再次出现同类 XML 元素，也不再查询其 keyid 或数据库关联状态。
- 三个入口设备继续使用正式 DBI 链：`keyid -> long2_to_long1/get_tab_no/get_col_no -> SYS_TABLE_INFO -> 407/408/409 -> BAY -> SUBSTATION`。三个入口必须全部有效且指向同一个 `BAY_ID`，才建立该分支馈线。
- 一旦入口三设备同 BAY，该 Bus 下游连通分支一直到真实拓扑终点的全部设备直接继承 `SUBSTATION.NAME + BAY.NAME`，例如 `AJWD AH310`；RMU、Transformer、LBS、CB 以及其他下游设备均不再做数据库关联校验。
- `Bus` 只用于切分馈线入口、防止沿公共母线横向串到旁边馈线；`BusDis` 始终是可穿越的 RMU 内部拓扑节点。
- 拓扑构建在显式 `link/node_area` 之外增加保守几何补链：ConnectLine/FeedLine/ACLine 端点小间隙、端点到线段 T 连接、以及线端点落在电气设备边界内时补充连接。这样可覆盖现场总图中“视觉已连接但 reciprocal 引用缺失”的入口 CBreaker/GroundDisconnector。不会连接纯视觉对象，也不会把两条线的内部交叉点自动当电气连接。
- 同位置存在旧/新重叠入口图元时，优先选择具有 `keyid` 的数据库关联图元，避免空 keyid 的视觉副本阻断馈线入口。
- 如果入口三设备任一未关联或三者 BAY_ID 不一致，该分支 `FeederName` 留空并告警，但文件其他内容继续解析；仍禁止使用文件名、facID/facName、FeedLine 文字或空间距离猜馈线。

其余 G File Studio 业务逻辑保持 v2.18.143 不变。

# v2.18.142

## G 图形内容解析：三锚点同 BAY 后才允许拓扑传播

- 馈线数据库查询严格只读取 G 中 `<CBreaker>`、`<Disconnector>`、`<GroundDisconnector>` 三类元素的 `keyid`；其他设备（包括 Transformer、RMU、LBS 等）的 `keyid` 不参与馈线数据库查询。
- 三类 keyid 继续按 DBI 正式链路解析：`long2_to_long1 -> get_tab_no/get_col_no -> SYS_TABLE_INFO -> 407/408/409 设备表 -> BAY -> SUBSTATION`。
- 一个 BAY 只有同时存在 BREAKER(407)、DISCONNECTOR(408)、GROUNDDISCONNECTOR(409) 三类有效锚点，且三类锚点全部解析到同一 `BAY_ID`，才被认定为有效馈线根。单个 Breaker 或两类设备不再足以给下游赋馈线。
- 有效三锚点建立后，仅沿 G 的真实 `link/node_area` 拓扑传播给其下游设备。未关联的 407/408/409、不同 BAY 锚点、站母线和拓扑冲突均作为传播边界；没有可靠路径的设备直接留空。
- 主迁移表中的 `FeederName` 改为组合显示，如 `AJWD AH327`；删除主表中 FeederStation/FeederBayID/Confidence/Evidence/Anchor/Cluster/Conflict 等冗余馈线列，详细信息移到新的 `馈线关联审计` Sheet。
- 未满足三锚点同 BAY 时只警告并留空馈线字段，不影响 G 图元、设备、RMU、名称等其他解析结果。

其余 G File Studio 业务逻辑保持 v2.18.141 不变。

# v2.18.141

## G 图形内容解析：按 DBI keyid 解码链建立馈线锚点

- 所属馈线只处理业务 G 中 `<CBreaker>`、`<Disconnector>`、`<GroundDisconnector>` 三类元素；不查询其他设备类型。
- G `keyid` 不再直接与设备表 `ID` 比较。程序先执行 `long2_to_long1(keyid)` 得到真实 `device_id`，并读取 `get_tab_no(keyid)` / `get_col_no(keyid)`。
- `get_tab_no` 必须分别为 407/408/409，并通过 `SYS_TABLE_INFO.TABLE_NAME_ENG` 校验为 `breaker` / `disconnector` / `grounddisconnector` 后才允许作为馈线锚点。
- 使用解码后的 `device_id` 查询三张设备表，取得数值 `BAY_ID`；再查询 `BAY.ID`，以 `BAY.NAME` 作为馈线名称，并通过 `BAY.ST_ID -> SUBSTATION.ID` 取得厂站名称。
- 有效数据库锚点只沿 G 的真实 `link/node_area` 电气拓扑传播。未关联、解码失败、表号不匹配、设备不存在、BAY_ID 为空、BAY/SUBSTATION 缺失的 407/408/409 设备均成为拓扑硬阻断点，其下游所属馈线留空并提示用户优先完成关联。
- 整张 G 没有任何有效 407/408/409 锚点时，只停止本文件的“所属馈线分析”并告警；设备/图元/RMU/名称等其他 G 内容仍继续解析。
- 继续禁止用文件名、facID/facName、FeedLine 文字、顶部标题或空间距离猜测所属馈线。
- 运行日志新增 `keyid解码 / 表号校验 / 设备表匹配 / BAY_ID有效 / BAY匹配 / 厂站匹配 / 有效锚点 / 未解析` 逐阶段统计，并输出最多 3 条真实锚点链示例。

其余 G File Studio 业务逻辑保持 v2.18.140 不变。

# v2.18.140

## G 图形内容解析：407/408/409 精确 keyid 数据库查询修正

- 所属馈线数据库锚点严格只读取业务 G 中 `<CBreaker>`、`<Disconnector>`、`<GroundDisconnector>` 三类 XML 元素的 `keyid`。
- 固定映射为 `BREAKER`（DBI 407）、`DISCONNECTOR`（408）、`GROUNDDISCONNECTOR`（409），不查询其他设备表。
- 18 位及以上 keyid 不再转 Python 整数；SQL 改为 `TO_CHAR(ID)` 与字符串 keyid 精确匹配，避免 Oracle NUMBER/VARCHAR 或驱动类型转换导致 G 中明明有 keyid 但查询结果为 0。
- 每次文件解析在运行日志直接显示三张表各自的 `G keyid 数 / DB匹配数 / 有效 BAY_ID / 未匹配数 / BAY_ID无效数`；未匹配时额外显示最多 3 个实际 keyid，便于现场直接核对数据库。
- 只要三类设备查到有效 `BAY_ID`，其站/馈线身份作为唯一 DB Anchor，并沿 G 的真实 `link/node_area` 拓扑传播给下游设备。
- 三类设备自身没有 keyid、数据库无记录、或 BAY_ID 为空/无法解析时，该设备继续作为拓扑硬阻断点：给出警告，并停止分析其下游所属馈线；其他 G 内容解析、设备识别和报告生成不受阻断。
- 不恢复任何空间距离、文件名、facID/facName 或 FeedLine 文字猜测所属馈线的逻辑。

其余 G File Studio 业务逻辑保持 v2.18.139 不变。


## v2.18.143
- 修复设备所属馈线拓扑传播在 RMU 内部 `BusDis` 处被错误截断的问题。
- `Bus` / `BusbarSection` 仍作为站内公共母线边界，防止从一条馈线横向传播到其他馈线；`BusDis` 作为 RMU 内部母线现在参与真实 `link/node_area` 拓扑传播。
- 数据库仍只查询 `CBreaker`→407、`Disconnector`→408、`GroundDisconnector`→409；其他设备不查数据库，只继承已确认三锚点 BAY 的下游拓扑馈线。
