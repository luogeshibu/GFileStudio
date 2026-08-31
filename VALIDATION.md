## v2.18.97

- 验证存在 `Pos=2 + gfs_frame_*` 的图框/标题栏 Poke 时，新建 RMU Poke 不再继承其属性。
- 验证新建 RMU Poke 使用专用标准属性：`Pos=0`、`RectStyle/p_RectStyle=0`、蓝色 `lc/lcc`，并包含 `app/domain`。
- 验证对 v2.18.96 已污染的 RMU Poke 再运行时可自动清除 `gfs_frame_role/gfs_frame_component/gfs_frame_type` 并恢复 `Pos=0`，同时保留 RMU 的 id/几何/ahref。

## v2.18.96

- 验证 Poke 处理在根节点无 `facID` 时仍可执行。
- 验证 RMU 16781/15953 可由 `DMS_COMBINED_DEVICE.NAME` 分别解析到不同 `FEEDER_ID` 与不同馈线完整业务名。
- 验证一个 G 文件中不同智能 RMU 生成不同馈线前缀的 ahref。
- 验证站点跳转不依赖 facID。
- 验证 `JED-CTL-AJWD-16.sln.pic.g` 内 `AJWD-16` 这种本地站/馈线标题不会被新增为对端站点跳转。

## v2.18.95

- UI 已统一显示：`站点跳转 Poke：跳转到对端变电站馈线总图`。
- 中文帮助明确 `*.sln.pic.g` 站点目标为对端变电站馈线总图；英文 i18n 同步为 `Remote Substation Feeder Overview`。
- 站点识别算法、Oracle 唯一匹配、JM2-J2 参考属性模板均未修改。
- 新增回归测试防止“对端变电站单线图”旧文案回归。

## v2.18.94

- 使用用户提供的 `JED-CTL-AJWD-15.sln.pic(2).g` 读取 `JM2-J2` 对应 Poke（id=17001493）全部 95 个属性；其中排除动态 `id/x/y/w/h` 后，90 个非几何参考属性写入代码模板。
- 真实样例回归确认 5 个站点跳转 Poke：`JM2-J2 / 5MR-23 / FEL 03 / BWD2-49 / SALAB-12` 均识别为候选并成功套用参考属性模板。
- 5 个样例 Poke 的动态位置/尺寸保持各自原值；所有 90 个非几何参考属性与 JM2-J2 参考对象逐项一致。
- 确认站点跳转模板关键值：`fc=100,100,100`、`fcc=#646464`、`lc=0,0,0`、`lcc=#000000`、`RectStyle=1`、`p_RectStyle=1`、`fm=1`、`ls=1`。
- RMU Poke 仍保持既有蓝色/Invisible 规则，不受站点跳转模板影响。
- 报告/UI/帮助中不再使用“站点条状”术语，统一显示“站点跳转 Poke”。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**505 passed, 2 skipped**。

## v2.18.93

- 使用用户提供的 `JED-NTH-ABH-03.sln.pic(10).g` 样例确认 Invisible 映射：`RectStyle=0`、`p_RectStyle=0`；样例同时使用蓝色 `lc=0,0,255` / `lcc=#0000ff`。
- 验证复用已有 RMU Poke 时，即使原 `RectStyle/p_RectStyle` 为可见值，也会统一改为 `0/0`。
- 验证复用已有站点条状 Poke 时同样统一为 Invisible。
- 验证从已有模板复制新增 Poke 时，即使模板 RectStyle 不是 0，也会覆盖为 Invisible。
- 验证 v2.18.92 的 5 个 AJWD 站点条状候选识别逻辑保持不变。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**502 passed, 2 skipped**。

## v2.18.92

- 验证站点条状关键字解析：`JM2-J2 → JM2`、`5MR-23 → 5MR`、`FEL 03 → FEL`、`BWD2-49 → BWD2`、`SALAB-12 → SALAB`。
- 验证 `V2-W-J-H-0017` 不再作为站点条状标签候选。
- 使用用户提供的 AJWD G 文件进行真实结构回归，5 个已有非 RMU Poke 覆盖标签全部识别，候选数为 5；Poke Line Color 仍统一为蓝色。
- 验证既有 RMU Poke、Oracle 业务命名、Poke 报告和重复 Poke 清理逻辑保持不变。

## v2.18.91（继承）

- 验证 Poke 跳转处理每次成功执行会生成 `poke-processing-report.csv` 与 `poke-processing-report.html`。
- 验证报告包含公共 RMU 识别总数、智能 RMU 数、RMU Poke 新增/更新/跳过数量、站点条状候选/成功解析/新增/更新/跳过数量及重复 Poke 清理数量。
- 验证明细记录 RMU 柜名或条状原文、站名关键字、数据库解析业务名、Poke ID、实际 ahref、识别依据/置信度和处理动作。
- 验证所有未加跳转候选均记录明确原因；数据库未找到站点、结构支撑不足等不会静默丢失。
- 验证 AJWD 样例中 `FEL 03 / BWD2-49 / SALAB-12` 可作为站点条状候选，类似 `V2-W-J-H-0017` 的误候选因数据库无法解析会在报告中明确标记未加跳转。
- `python -m py_compile`：通过。
- 完整 `pytest -q`：**499 passed, 2 skipped**。

## v2.18.86

- 验证本版本从 v2.18.85 直接派生，并保留 `test_v21885_smooth_symbol_progress.py`。
- 验证新增数据库页面、共享 Oracle 服务、默认非敏感连接参数和只读 SQL 门禁。
- 验证数据库密码未硬编码到源码，Windows 保存采用当前用户 DPAPI。
- 验证数据库模块不依赖图元标准检测引擎，图元标准能力边界保持不变。

## v2.18.85

- 验证基线为 v2.18.82，且不包含后续服务器自动图元发现逻辑。
- 验证图元标准检查/纠正始终使用 0~100% 确定型进度条。
- 验证密集或乱序的后台 progress 信号不会使显示进度倒退或闪烁。
- 验证平滑进度为 opt-in，仅在图元标准检查页面启用。

## v2.18.82

- 验证图元标准检查/纠正页面禁用 indeterminate busy fallback，运行期间始终保持 0~100% / %p% 的确定型样式。
- 验证 v2.18.81 的单文件细粒度进度回调仍保持单调递增并最终到 100%。

# Validation

## v2.18.82

- 验证单文件“检查图元标准”会产生 0~100 的多阶段细粒度、单调递增进度，不再只有文件完成后的单次跳变。
- 验证“纠正标准问题”从纠正副本阶段连续进入 post-check 自动复查阶段，62% 之后仍持续产生中间进度并最终到 100%。
- 验证 TaskPanel 在启用实时进度模式后，长时间没有精确回调会临时切换为 Qt 动态 busy 状态，下一条真实百分比会恢复 determinate 模式。
- 验证受黄金基线保护的 `rmu_identification_engine.py` 未改动，黄金基线锁测试通过。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**467 passed, 2 skipped**。

# G File Studio 验证记录

## v2.18.79

- 验证 ACTIVE 图元标准可锁定/解锁，锁定状态持久化且不增加 Profile 版本号。
- 验证已锁定标准在服务层拒绝标准内容更新、删除和历史版本恢复，必须先显式解锁。
- 验证锁定后 UI 禁止表格修改、上传/替换标准 G、SMART/NORMAL 共用切换、保存及标准删除；检查业务 G 仍可执行。
- 验证用户选中的设备角色为标准绑定唯一权威来源；上传 G 的 XML 元素或文件名与默认角色提示不一致时不再硬阻断，界面只显示参考差异。
- 验证 SMART/NORMAL 同一设备继续允许共用一个用户上传标准 G，managed standard file 只保存一份。
- 验证图元标准检查处理器不再调用业务单线图 symbol catalog 收集逻辑；业务 G 不生成待确认/学习候选，不参与 devref、尺寸、AlignCenter 或 pin 标准生成。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**464 passed, 2 skipped**。

## v2.18.76

- 验证一个 `Circuit_Breaker_NON-SMART` 上传文件只绑定 `NORMAL / Circuit Breaker`，不会自动复制到另外 3 个 `CBreakerDis` 角色。
- 验证 SMART/NORMAL 与 LBS/Circuit Breaker 的强文件名识别保护；角色不匹配时拒绝绑定。
- 验证标准上传为单文件选择流程，无上传前额外确认窗口。
- 验证只配置一个 NORMAL Circuit Breaker 标准也可通过权威标准校验，并且检查引擎只检查该角色、跳过未配置 LBS/SMART/接地刀闸。
- 验证用户上传图元 G 仍是 devref、尺寸、AlignCenter、pin/连接锚点的唯一标准来源，业务 G 不参与标准生成。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**458 passed, 2 skipped**。

## v2.18.75

- 验证用户上传的图元定义 G 会覆盖旧 Profile 中同 devref 的业务扫描目录与旧几何模板；标准 w/h、AlignCenter、pins、pin id/index 均以上传文件为准。
- 验证权威标准几何可从上传图元确定性生成 0/90/180/270 度模板，检查路径在存在 managed standard files 时关闭业务 G 几何回退。
- 验证标准编辑 UI 提供“上传 / 更新标准图元 G”，标准表使用“标准来源”而不是“置信度”，且业务 G 不再参与标准学习。
- 验证旧 NOT READY Profile 的历史学习 devref 不会作为可选权威标准显示；6 个 RMU 基础角色必须绑定实际上传/已持久化的标准图元后才能 READY。
- 验证单角色更新可与当前 ACTIVE 已持久化标准合并，不要求每次重新上传全部标准图元。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**454 passed, 2 skipped**。

## v2.18.74

- 验证业务单线图不能作为权威标准文件；只有可解析的图元定义 G 才允许上传到标准库。
- 验证标准图元保存后复制到版本独立的用户数据目录；删除原始上传文件后，已保存 ACTIVE 标准仍可通过完整性校验。
- 验证同一 devref 的两个不同文件版本不能同时进入一个 ACTIVE 标准；历史版本通过 Profile 版本机制保留。
- 验证 6 个 RMU 基础角色必须全部绑定且每个角色只能解析到一个标准图元；标准文件 SHA256/整体标准指纹不一致时阻止 UI 执行。
- 验证业务 G 输入与标准上传入口彻底分离；“待检查 G 文件”只用于检查/纠正，标准维护使用独立多文件上传。
- 验证最后使用的 ACTIVE Profile 会持久化并在下次打开页面时优先恢复。
- 验证检查报告记录 Standard Fingerprint；workspace 运行结果继续沿用原 30 天临时保留机制，持久标准库不受影响。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**450 passed, 2 skipped**。

## v2.18.73

- 验证基础识别 UI 不再显示智能/非智能范围选择，仅保留柜名方向、智能标记字符、柜名排除字符串。
- 验证自定义智能标记 `NEWSMART` 可全图唯一归属 RMU，并自动从柜名候选中排除。
- 验证用户柜名排除字符串仍为严格完整文本排除。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**447 passed, 2 skipped**。


## v2.18.72

- 验证 RMU 基础识别模块位于环网柜处理页面所有功能之前。
- 验证 RMU 基础识别固定启用且不可关闭，智能与非智能 RMU 范围均固定选中，SMART / SMR 分类固定开启。
- 验证环网柜处理构造的 BasicSettings 始终使用 `identify_rmu_name_and_type=True` 与 `rmu_smart_in_type=True`，并始终显示 RMU 汇总报告入口。
- 用户真实 `JED-NTH-ABH-12.sln.pic(9).g` 验证：基础识别得到 38 个 RMU、柜名 38、柜型 38；汇总 CSV 共 38 行，`IntelligentRMU` 同时包含 `YES` 与 `NO`，证明智能与非智能 RMU 均纳入固定汇总范围。
- 同一真实文件验证每次处理都会生成 `rmu-summary-report.csv` 与 `rmu-summary-report.html`。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**443 passed, 2 skipped**。


## v2.18.71

- 新 ahref 模板验证：`JED-NTH-ABH-{FACNAME}-{RMU}-JED.sln.pic.g` 在 `facName=AH303`、RMU=`34661` 时生成 `JED-NTH-ABH-AH303-34661-JED.sln.pic.g`。
- 占位符位置验证：`{FACNAME}` / `{RMU}` 可位于文件名任意位置，并兼容独立字段 `FACNAME` / `RMU`；除这两个变量外的内容完全由用户指定。
- 单文件固定 facName 验证：模板可直接写 `JED-NTH-ABH-AH303-{RMU}-JED.sln.pic.g`，不依赖源 G 文件名，也不要求读取 facName。
- 批处理验证：使用相同模板处理任意命名的源 G 文件时，不解析源文件名；分别读取各文件根节点 `facName`（AH303 / AH304 / MD112）并生成各自目标。
- 缺失 facName 验证：仅当模板实际包含 `{FACNAME}` / `FACNAME` 时要求根节点 facName；缺失时只跳过当前文件 Poke 并返回告警。
- 用户真实 `JED-NTH-ABH-03.sln.pic(6).g` 验证：根节点 `facName=AH303`，5 个智能 RMU 分别生成 `JED-NTH-ABH-AH303-<RMU>-JED.sln.pic.g`；即使传入完全不规范的源文件名也不影响 ahref 生成。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**436 passed, 2 skipped**。

## v2.18.69

- UI 结构验证：`智能环网柜 Poke 跳转` 已从 `环网柜图元处理` 中拆出，作为 RMU 页面独立模块，并位于环网柜图元处理与 RMU 信息汇总之间。
- 单文件固定规则验证：使用非规范源名 `ANY_MAIN_FILE.g` / `NOT_A_STANDARD_MAIN_FILE.g` 时，不读取也不校验源文件名；规则 `JED-NTH-ABH-AH303-RMU.sln.pic.g`、`JED-NTH-ABH-AH303-{RMU}.sln.pic.g`、真实样例 `JED-NTH-ABH-AH303-34661.sln.pic.g` 以及固定前缀 `JED-NTH-ABH-AH303` 均可生成当前智能 RMU 的正确 ahref。
- 批处理固定部分验证：规则 `JED-NTH-ABH-AH3` 配合 `JED-NTH-ABH-03.sln.pic.g` / `...-04.sln.pic.g` 分别生成 `AH303-<RMU>` / `AH304-<RMU>`；FEEDER 仅取 `.sln.pic.g` 前最后一个纯数字段。
- 批处理自定义规则验证：支持 `{FEEDER}` / `{RMU}`（大小写不敏感），例如其他现场规则 `OTHER-SITE-X{FEEDER}-{RMU}.sln.pic.g` 可按每个源文件分别生成目标。
- 批处理异常文件验证：`JED-NTH-ABH-F04.sln.pic.g` 无法提取纯数字 FEEDER 时，当前文件智能 RMU Poke 全部跳过并返回单一明确命名告警；不会产生部分 Poke，也不会抛出整批异常。
- 用户真实 `JED-NTH-ABH-03.sln.pic(6).g` 验证：识别智能 RMU `22545 / 16781 / 34661 / 40597 / 22522`；单文件真实样例规则和批处理固定规则均正确生成 5 个 `JED-NTH-ABH-AH303-<RMU>.sln.pic.g`，模拟 `...-04` 时正确切换为 `AH304-<RMU>`。
- `python -m compileall -q g_file_studio app.py`：通过。
- 完整 `pytest -q`：**430 passed, 2 skipped**。

## v2.18.68

- 批处理自动命名验证：同一批次中的 `JED-NTH-ABH-03.sln.pic.g`、`...-07...`、`...-12...` 分别生成 `AH303`、`AH307`、`AH312` 的独立智能 RMU Poke 目标。
- 文件级容错验证：不规范文件名（如 `JED-NTH-ABH-F03.sln.pic.g`）不会抛出整文件处理异常；仅该文件的智能 RMU Poke 被跳过并告警，树中不产生部分 Poke。
- 自定义模板验证：支持 `{region1}/{region2}/{station}/{feeder}/{rmu}`，并可对不同馈线文件分别渲染；UI 强制模板包含 `{rmu}`。
- 静态站点前缀 + `{rmu}` 的模板可用于非标准主图命名的特殊现场，不要求从主文件名提取区域字段。
- 用户真实 `JED-NTH-ABH-03.sln.pic(6).g` 验证：识别 5 个智能 RMU，已有 34661/40597 Poke 复用更新 2 个，其余新增 3 个；5 个目标均为 `JED-NTH-ABH-AH303-<RMU>.sln.pic.g`。
- 将同一真实图逻辑模拟为 `JED-NTH-ABH-12.sln.pic.g` 时，34661 自动生成 `JED-NTH-ABH-AH312-34661.sln.pic.g`，证明批处理中不同馈线不会共享固定前缀。
- 将同一真实图模拟为不规范 `JED-NTH-ABH-F03.sln.pic.g` 时：智能 RMU 5 个全部仅跳过 Poke，XML 树保持完全不变并返回明确命名告警。
- 执行 `python -m compileall -q g_file_studio app.py`：通过。
- 执行完整 `pytest -q`：**423 passed, 2 skipped**。

## v2.18.67

- 自动命名验证：`JED-NTH-ABH-03.sln.pic.g` → `JED-NTH-ABH-AH303`；`JED-NTH-ABH-12.sln.pic(9).g` → `JED-NTH-ABH-AH312`。
- 验证 G 根节点 `facName` 不再参与 Poke `ahref` 命名。
- 验证不规范主图文件名在未提供人工覆盖时抛出明确错误，不生成错误目标。
- 验证人工覆盖可接受 `JED-NTH-ABH-AH303` 前缀以及 `JED-NTH-ABH-AH303-22522.sln.pic.g` 完整样例文件名。
- 验证一个主图含多个智能 RMU 时，单个样例前缀会分别生成各 RMU 自己的目标文件名。
- 用户真实 `JED-NTH-ABH-03.sln.pic(6).g` 验证：5 个智能 RMU 分别生成 22545、16781、34661、40597、22522 对应的 `JED-NTH-ABH-AH303-<RMU>.sln.pic.g`。
- 执行 `python -m compileall -q g_file_studio app.py`：通过。
- 执行完整 `pytest -q`：**418 passed, 2 skipped**。

## v2.18.66

- 新增 SMART/SMR 全局唯一归属回归测试：标记位于柜框外但靠近某个 RMU 时仍能识别为智能 RMU。
- 新增相邻/重叠 RMU 场景回归测试：同一个 SMART 标记只能使 1 个 RMU 进入智能状态，不能同时归属两个柜；几何完全等距时告警跳过而不是猜测。
- 用户真实 `JED-NTH-ABH-12.sln.pic(9).g` 验证：38 个 RMU 中 10 个 SMART RMU 仍全部正确识别，30834 保持智能柜识别。
- 执行 `python -m compileall -q g_file_studio app.py`：通过。
- 执行完整 `pytest -q`：**414 passed, 2 skipped**。

## v2.18.65

- 修复独立 RMU 处理的 SMART 外框改色漏判：外框改色复用 RMU 信息汇总识别结果。
- 真实样本 `JED-NTH-ABH-12.sln.pic(9).g`：RMU 30834 / rect 2000643 被 identify_rmus() 识别为 SMART；其 SMART Text 右边界比 rect 右边界多 1 px，旧“完全包含”判断漏判；新逻辑按识别结果正确将该 rect 改为目标颜色。

> 发布包统一验证文档。以后每个版本的验证结果都追加到本文件中，不再新增 `VALIDATION_v*.md`。最新版本位于最上方。

## v2.18.63

- 解析用户真实主图 `JED-NTH-ABH-03.sln.pic(6).g`：现有 RMU 信息汇总识别 17 个 RMU，其中智能 RMU 5 个；Poke 功能直接消费该识别结果，不新增 RMU 判定规则。
- 验证用户手工示例：34661 → `JED-NTH-ABH-AH303-34661.sln.pic.g`，40597 → `JED-NTH-ABH-AH303-40597.sln.pic.g`；目标命名由主图前缀、根节点 `facName=AH303` 与 RMU 名称生成。
- 真实主图 Poke-only 验证：原有 34661/40597 Poke 更新 2 个，新建 22545/16781/22522 Poke 3 个，跳过 0；点击范围均覆盖“柜名 + RMU 外框”。
- 真实主图与“组合所有环网柜”同时验证：RMU Merge 重建 17 个，智能 Poke 5 个均保留在 Layer 后层，输出 G 可重新解析。
- 新增 Poke 幂等、非智能 RMU 不处理、上传副本文件名 `(n)` 不进入 `ahref` 的回归测试。
- 执行 `python -m compileall -q g_file_studio app.py`：通过。
- 执行完整 `pytest -q`：**406 passed, 2 skipped**。

## v2.18.61

- 验证“环网柜处理”页面不再创建、恢复、保存或执行“删除带 Bus 的环网柜外框，并将最近标题放到母线上方”选项。
- 验证“基础处理”中的同名能力和吉达馈线批处理 Bus 处理代码仍保留。
- 执行 `python -m compileall -q g_file_studio app.py`：通过。
- 执行完整 `pytest -q`：**403 passed, 2 skipped**。

## v2.18.60

- 验证“环网柜处理”页面不再创建、插入、连接或刷新“打开图元处理报告”按钮。
- 验证 RMU 汇总报告和台账对比报告按钮保持原样。
- 验证 `basic_processor.py` 仍生成 `rmu-graphic-processing-report.csv/html`，本次只移除 UI 打开入口。
- 执行 `python -m compileall -q g_file_studio app.py`：通过。
- 执行完整 `pytest -q`：**401 passed, 2 skipped**。

## v2.18.59

- 独立“环网柜处理 → 组合所有环网柜”直接调用 `identify_rmus()`，并把其 `items[].rect_id` 作为组合和预清理的唯一 RMU 外框集合。
- 新增回归测试：强制让旧 `_valid_rmu_rects_for_smr()` 私有判断函数抛异常，独立 RMU 组合仍能通过，证明当前路径未再调用私有柜体猜测，而是使用 RMU 信息汇总结果。
- 验证旧 Merge 预清理和重新组合共用同一个 RMU rect ID 集合；图框/信息栏辅助 rect 不会成为 Merge owner。
- 用户真实 `JED-NTH-ABH-12.sln.pic(8).g`：`identify_rmus()` 识别 38 个 RMU / 38 个有效 rect ID，`process_basic()` 重建 38 个 RMU Merge，失败 0，实际输出 G 文件 1 个。
- 执行 `python -m compileall -q g_file_studio app.py`：通过。
- 执行完整 `pytest -q`：**400 passed, 2 skipped**。


## v2.18.58

- 复现用户真实失败：`JED-NTH-ABH-12.sln.pic(7).g` 中 Text ID `8001589` 位于 4 个完全重叠的 `350×97` 内置 info-block rect 内；v2.18.57 会抛出“同时完整位于两个同尺寸 rect 内，无法唯一确定组合归属”。
- 严格 RMU 模式下只认同时包含 `BusDis + CBreakerDis + ZhaiWaiJieDiDaoZha` 的真实柜体 rect，实际样本识别并重建 **38 个 RMU Merge**，不再把 8 个图框 title/info 辅助 rect 当成柜体。
- 用 `process_basic()` 对该真实 G 运行独立 RMU 组合路径：成功 1、失败 0，并实际写出新的 G 文件。
- 新增重叠辅助 rect 回归测试，并验证通用 `group_rmu_tree()` 默认行为保持兼容。
- 执行 `python -m compileall -q g_file_studio app.py`。
- 执行完整 `pytest -q` 回归：**398 passed, 2 skipped**。


## v2.18.57

- 验证独立“环网柜处理 → 组合所有环网柜”在输入文件已有 Merge 时先调用现有 `remove_all_graphic_merges()`，确认旧 Merge 全部删除后再执行 `group_rmu_tree()`。
- 验证真实历史组合样本：原有 1 个 Merge 先删除，随后按当前几何重建 2 个 RMU Merge；`graphic_merge_removed_count=1`，重建组合数为 2。
- 验证无 Merge 文件不会触发预清理日志或额外取消组合，只直接执行原组合逻辑。
- 验证该开关默认 `False`，且“基础处理”页面未设置该开关，因此其他调用路径行为保持不变。
- 执行 `python -m compileall -q g_file_studio app.py`。
- 执行完整 `pytest -q` 回归：**395 passed, 2 skipped**。


## v2.18.56

- 验证基础处理 UI 不再创建“连接点修复”分组、复选框或 `repair_connection_points` 设置入口。
- 保留旧 connection engine / processor 的单元测试，确认此次只移除 UI/执行入口而未重构底层历史逻辑。
- 验证同类图元版本升级、图元标准检查、吉达馈线批处理相关文件未因本次删除入口而被改写。
- 执行 `python -m compileall -q g_file_studio app.py`。
- 执行完整 `pytest -q` 回归：**392 passed, 2 skipped**。

## v2.18.55

### 修改目标

修复旧 `Circuit_Breaker_NON-SMART` 28×28 升级到新 `Circuit_Breaker_NO-SMART` 34×38 时，因 pin index 与 pin id 同时重编号而被误判“不兼容”的问题。

### 实现

- 端口映射顺序保持：唯一 index → 完整唯一 id → 严格几何方向 fallback。
- 几何 fallback 以 `AlignCenter` 为原点，将 pin 分类到 8 个方向扇区，只在每个方向唯一且 OLD/NEW 方向集合完全一致时自动对应。
- 真实 CB 建立 `TOP→TOP / BOTTOM→BOTTOM`，避免把部分重复的 XML id `18000003` 错当成同一电气端口。
- 多 pin 同侧等几何歧义仍继续阻断。
- 吉达批处理核心文件哈希保持不变。

### 验证

- 用户真实 OLD/NEW 图元：兼容分析 `valid=True`。
- 用户真实主 G：25 个旧 NORMAL CB 可处理，50 条连接关系，0 skipped / 0 warnings。
- 新增几何 fallback 与歧义阻断回归测试。
- `python -m compileall -q g_file_studio app.py`：通过。
- `pytest -q`：392 passed，2 skipped。


## v2.18.54
- 验证真实场景：旧 NORMAL CB pin ids 为 18000002/18000003，新 NO-SMART CB 为 18000003/18000004，但 pin index 均为 2/3，允许安全配对。
- 验证新图元 XML pin 顺序反转时仍按 pin index 恢复逻辑顺序。
- 验证 pin index 与 pin id 都无法对应时继续阻断。

## v2.18.53

### 修改目标

在通用“图元标准检查”模块增加按 ACTIVE 标准生成安全纠正副本的能力，同时严格保持吉达馈线批处理 v2.18.52 流程不变。

### 实现

- 新增“纠正标准问题”按钮；检查与纠正两个动作明确分离。
- 纠正结果只写入 workspace 本次运行目录的 `corrected` 子目录，不覆盖源 G。
- ACTIVE 标准中的内置及自定义图元都复用 pin/ConnectLine 锚点保持算法。
- 纠正后自动执行一次只读复查，报告剩余无法安全自动处理的问题。
- 未纳入标准的新图元继续只进入待确认队列，不自动修改。
- 吉达批处理 `batch_processor.py` 与 `jeddah_batch_page.py` 文件哈希保持与 v2.18.52 一致。

### 验证

- 新增任意自定义 `FuseDevice` 单 pin 图元回归：标准图元尺寸变化时，ConnectLine 端点保持不动，图元 x/y/w/h 正确反算。
- 校验源 G 字节不变，纠正副本和自动复查报告正确生成。
- `pytest -q`：386 passed，2 skipped。

---

## v2.18.52

### 修改目标

修复吉达馈线批处理中 NORMAL Circuit Breaker 从旧 `Circuit_Breaker_NON-SMART` 纠正为新 `Circuit_Breaker_NO-SMART` 后，devref 已更新但图元主体未同步到新图元 pin 几何，导致 Q1 与原 ConnectLine 锚点错位的问题。

### 实现

- 图元标准 Profile 现在会把 `symbol_catalog` 中真实 `*.icn.g` 的 `w/h + pin(cx,cy)` 自动绑定为有效几何模板；已有 Profile 加载时也会自动补全，不要求重新创建标准。
- 当标准图元只在当前 G 中存在某一个旋转方向时，可从该正确实例反推 rotation=0 的原始 pin，再生成 0/90/180/270 四个方向的模板。
- 吉达批处理继续保持 ConnectLine 绝对端点不动，只调整图元主体的 `x/y/w/h`。
- 实际 30815 Q1：旧图元 `(x=1442,y=2541,w=28,h=28)`、连接点 `(1454,2545)/(1454,2565)`；新 NO-SMART 图元 pin 为 `(18,6)/(18,26)`，正确结果为 `(x=1436,y=2539,w=30,h=30)`，连接点完全不变。

### 验证

- 新增 v2.18.52 图元定义绑定与跨旋转几何回归测试。
- 使用用户提供的 `JED-NTH-ABH-12.sln.pic(5).g` 与 `Circuit_Breaker_NO-SMART...icn.g` 验证 30815 Q1 可正确原位纠正。

---

## v2.18.51

### 修改目标

修复图元标准已在“图元标准检查”中更新，但“吉达馈线批处理”仍显示启动时旧 Profile 的跨页面缓存问题。

### 实现

- `SiteProfilePage` 新增 ACTIVE 标准变化信号；保存、恢复、删除以及确认新自定义标准后通知吉达页。
- `JeddahBatchPage` 新增 `refresh_profiles()`，每次都从共享 `SiteProfileService` 重新读取 Jeddah ACTIVE 标准。
- 页面切入与批处理执行前均强制刷新，旧 Profile 被删除/改名后自动修复选择。
- 固定流程第 9 步说明补充连接锚点位置偏移纠正。

### 验证

- `python -m compileall -q g_file_studio app.py`：通过。
- `pytest -q`：379 passed，2 skipped。

---

## v2.18.50

### 修改目标

精简发布包根目录的验证文档：不再每个版本生成一个 `VALIDATION_vX.Y.Z.md`，统一维护单一 `VALIDATION.md`。

### 实现

- 将现有 v2.18.42、v2.18.44～v2.18.49 验证记录合并到本文件，按版本倒序保留。
- 删除发布包根目录全部 `VALIDATION_v*.md` 分散文件。
- 新增发布结构回归测试，要求根目录只能存在一个 `VALIDATION.md`，防止后续版本再次产生多个验证文档。
- 本次只整理发布文档与版本信息，不修改任何 G 文件业务处理算法、规则、默认值或 UI 行为。

### 验证

- `python -m compileall -q g_file_studio app.py`：通过。
- `pytest -q`：377 passed，2 skipped。

---

## v2.18.49

### 修改目标

移除由历史 workspace run 目录不存在产生的无意义启动弹窗。

### 实现

- 在主窗口创建业务页面前清除所有程序托管输出目录的旧设置。
- 各页面随后继续由 `configure_managed_output` 使用当前 workspace 根目录。
- 不修改受黄金基线保护的业务文件。

### 预期行为

- 历史托管输出路径不存在：不弹窗，直接使用当前 workspace。
- 用户手工输入路径不存在：原有提示仍保留。
- G 文件处理算法不变。

---

## v2.18.48

### 基线
- 直接基于 v2.18.47 更新。
- 图元标准检查继续严格只读，不修改源 G。
- 基础处理中的同类图元版本升级、v2.18.43 的旋转/锚点修复、v2.18.47 的详细检查报告均保留。

### 本次修改
- 图元标准检查页面简化为“待检查 G → ACTIVE 标准 → 检查图元标准 → 查看检查报告”。
- 标准定义默认收起，通过“编辑标准”按需展开；执行日志默认收起。
- “检查图元标准”与“查看检查报告”相邻放置；结果目录按钮简化为“打开结果目录”。
- 新 devref 发现采用一次提醒机制：首次进入待确认队列，后续检查不重复弹窗。
- 待确认图元支持逐个“加入当前标准 / 不纳入此标准 / 剩余稍后处理”。
- 忽略状态持久化，可从标准管理恢复；待确认/忽略元数据不产生新的标准版本。
- 已经属于不符合标准明细的当前 devref 不再重复作为“新图元”提示。

### 自动化验证
- `python -m compileall -q g_file_studio app.py`：通过。
- `python -m pytest -q`：372 passed，2 skipped。
- 真实 `JED-NTH-ABH-12.sln.pic(4).g` 验证：
  - 首次检查发现 9 种未纳入标准图元：New=9，Pending=0；
  - 将 9 种标记为 pending 后再次检查：New=0，Pending=9，验证不会重复提示；
  - 将其中 1 种标记 ignored 后再次检查：候选剩余 8，验证忽略状态生效。

### 环境限制
- 当前容器未安装 PySide6，因此无法实际启动 Qt 主窗口进行像素级界面截图验证。
- 页面结构、按钮顺序、隐藏/展开状态已由静态回归测试覆盖。

---

## v2.18.47

### 基线
- 基于 v2.18.46。
- 不修改原有 RMU 识别、ID、馈线、基础处理、SMART/NORMAL 分类与图元升级算法。

### 本次修改
- 图元标准检查 HTML 报告新增逐元素不符合明细。
- 每条明细包含当前值、标准值、具体原因、元素 ID/RMU/关联线等定位信息。
- 新增 `symbol-standard-check-details.csv`。
- 汇总 HTML 精简为文件级关键指标，避免超宽纯数字表。
- 不符合总数按唯一元素计数。

### 自动化验证
- `pytest -q`：369 passed，2 skipped。
- 新增 `tests/test_v21847_symbol_standard_report_details.py`，验证 SMART/NORMAL 变体错误会在 HTML/CSV 中明确输出原因、当前 devref、标准 devref 和元素 ID。

### 只读边界
- 图元标准检查仍不写回、不覆盖、不生成 final G。

---

## v2.18.46

### 本次调整
- 左侧导航顺序：`异常小尺寸图元检测 → ID 检查与修复 → 图元标准检查 → 环网柜处理 → ...`。
- `图元标准检查` 改为严格只读：只检查、告警、生成 CSV/HTML 报告，不再存在“检查并升级”动作，也不生成 `final` G。
- 图元标准检查的 workspace 输出目录移动到 G 文件输入区域下方。
- 检测到 ACTIVE 标准不一致时，界面弹出 `图元标准不一致` 告警；日志列出当前/期望 devref，并单独提示几何不一致。
- `基础处理 → 通用图元升级` 更名为 `基础处理 → 同类图元版本升级`；只处理同一设备语义/同一 XML 类型的 OLD → NEW 版本变化。
- SMART 图元误用到 NORMAL、NORMAL 图元误用到 SMART 被明确归类为“图元类型/变体使用错误”，不是“图元版本升级”。
- 吉达固定流程相关文案同步改为“图元类型/变体纠正”，业务算法未改。

### 安全边界
- 图元标准检查继续复用原 ACTIVE Profile 比较引擎，但只在内存 XML 树中执行比较，不写源文件。
- 同类图元版本升级的 OLD/NEW 配对、旋转、pin、AlignCenter、ConnectLine 锚点保护算法未改变；本版仅调整模块边界、只读约束与用户可见术语。
- 设备 ID、keyid、node_area 和拓扑关系相关业务逻辑未改。

### 验证
- `python -m compileall -q g_file_studio app.py`：通过。
- `pytest -q`：`367 passed, 2 skipped`。

---

## v2.18.45

### Manual OLD → NEW pairing UX

- Universal Symbol Upgrade no longer implies that OLD and NEW filenames must match.
- Added an explicit `手动配对…` workflow. The user may select an OLD row (or no row) and choose any uploaded OLD and NEW symbol from two combo boxes.
- The dialog previews parsed XML element type, body ID, w/h, AlignCenter, and pins for both files before confirmation.
- Manual pairing may use completely different filenames and body IDs. XML element type and electrical pin topology are still validated for safety.
- Manual mappings are marked `手动确认` and take precedence over automatic suggestions.
- One NEW symbol may be manually used by more than one legacy OLD symbol, supporting legacy aliases converging on one current standard symbol.
- Unpairing/removing an OLD mapping correctly returns a NEW symbol to the unmatched pool only when no other mapping still uses it.
- Existing exact-name and unique `XML type + body ID` auto-pairing behavior is retained.

### Regression

- Retains v2.18.43 centered rotation / connection-anchor fixes.
- Retains v2.18.44 generic symbol standard template enhancements.

---

## v2.18.44

### Baseline
- Based directly on v2.18.43.
- Keeps v2.18.43 batch OLD/NEW pairing and zenon-centered 90/270-degree rectangular-symbol rotation.
- Keeps the v2.18.41 orthogonal-wire safety guard.

### Generic symbol-standard customization
- The six existing SMART/NORMAL RMU roles remain protected built-in rules.
- Users may add/delete additional custom device-symbol standards.
- Custom rows persist scope, role, XML element tag, standard devref and the selected business-element matcher.
- Supported matchers: exact old/current devref, XML element type, exact p_NameString, exact key_name.
- Built-in rules are applied first; custom rules cannot double-modify an already handled built-in RMU device.
- Ambiguous custom-rule matches are skipped with warnings.

### G element/property catalog
- Standard main-G scanning records XML tag, devref body ID, w/h, rotations, p_NameString/key_name examples and occurrence counts.
- Raw icon-definition G scanning records body XML type/ID, w/h, AlignCenter, pin coordinates and pin IDs.
- GBK/GB18030 raw icon definitions are parsed through the existing safe decoder even when ElementTree cannot parse them directly.
- Raw icon definitions generate rotation-specific geometry templates for 0/90/180/270 degrees.

### Generic anchor-preserving geometry
- Geometry-template learning now supports arbitrary devref elements with verifiable ConnectLine anchors, not only the three built-in RMU device tags.
- Custom standards reuse the same anchor-preserving replacement engine.
- If no safe geometry template is available, replacement falls back to devref-only and does not move wiring.
- Geometry-only adjustments are now written even when the target devref string is unchanged.

### Supplied-file verification
- `JED-NTH-ABH-12.sln.pic(4).g` plus the supplied raw symbol-definition G files were scanned successfully.
- Main-G catalog found the existing RMU devrefs and their element properties.
- Raw symbol G metadata including AlignCenter/pins was parsed successfully despite multibyte XML declarations.
- No regression was introduced into the previous RMU 30907 grounding-switch and horizontal/vertical connection-line fixes.

### Automated validation
- Python compile checks: PASS.
- Full pytest suite: `364 passed, 2 skipped`.

---

## v2.18.42

### Baseline
- Based directly on v2.18.41.
- Keeps the v2.18.41 rotated-icon orthogonal ConnectLine preservation fix.

### Symbol Standard Check
- Sidebar module renamed from `现场 RMU 图元 Profile` to `图元标准检查`.
- Existing saved SiteSmartProfile data and ACTIVE/ARCHIVED version workflow remain compatible.
- New read-only `只检查标准` action uses the same RMU/device/geometry engine as upgrade but never writes source G files and does not create a `final` output directory.
- Existing upgrade workflow is retained as `检查并升级`.
- Read-only report: `symbol-standard-check.csv/html`.
- Upgrade report: `symbol-standard-upgrade.csv/html`.
- Standard scope remains SMART/NORMAL RMU LBS, Circuit Breaker, ZhaiWaiJieDiDaoZha and learned geometry; SMR remains site-specific and is skipped by the generic standard engine.
- Jeddah batch continues to consume the selected ACTIVE standard; only user-facing naming/help text changed.

### Validation
- `python -m compileall -q g_file_studio app.py`: PASS
- `pytest -q`: `355 passed, 2 skipped`
- Added regression tests proving check-only mode leaves source bytes unchanged and creates no `final` folder.

- 复核智能 RMU Poke 逻辑：仅围绕 RMU 柜名 Text 建立/复用 Poke；不会再把整个 RMU 外框纳入点击区域；同一智能 RMU 若已有多个相关 Poke，会自动删除多余项，仅保留 1 个。
## v2.18.64

- RMU 页面 SMART/SMR 外框只保留颜色选择，已移除无效的线型下拉控件。
- 基础处理的线路/母线线型功能未修改。


- 智能 RMU Poke 跳转补充：单文件若模板未使用 {FACNAME}，则完全不读取/依赖 facName；即使源 G 没有 facName，只要识别到智能 RMU 也可正常生成 ahref。仅当模板显式包含 {FACNAME} 时，才为当前文件读取 facName。

## v2.18.88
- 验证空白用户配置加载项目默认 Oracle 连接参数与密码。
- 验证存在用户保存配置时不会回退或覆盖为项目默认配置。
- 验证 v2.18.86/v2.18.87 遗留数据库配置字段仍会被识别为用户配置。


## v2.18.89
- 验证 `facID → DMS_FEEDER_DEVICE → SUBSTATION → SUBCONTROLAREA` 查询链只使用业务 NAME 字段生成完整站/馈线名称，不依赖 `GRAPH_NAME`。
- 验证数据库上下文 `JED-NTH + ABH + AH303` 生成 `JED-NTH-ABH-AH303`。
- 验证数据库 Poke 命名生成 `JED-NTH-ABH-AH303-34661.sln.pic.g`。
- 验证空 `facID` 被拒绝并提示先关联馈线。
- 使用用户提供的真实 `JED-NTH-ABH-03.sln.pic.g` 与模拟数据库上下文回归，5 个智能 RMU Poke 均生成/保持为 `JED-NTH-ABH-AH303-{RMU}.sln.pic.g`。
- Full pytest: `489 passed, 2 skipped`（最终打包前再次执行）。
