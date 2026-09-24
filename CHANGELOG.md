# Changelog

## 2.18.205

- 服务器图元同步管理表格参考“ID 检查与修复”表格重新做响应式列宽：7 个可见字段在有空间时自动铺满整个表格，不再在右侧留下大块空白。
- 本地图元缓存完成后只对 7 个可见字段做一次轻量文本宽度测量；文件名、w×h、AlignCenter、Pins、标准来源、状态、分类标记按实际内容保留自然宽度，窗口不足时使用表格自己的横向滚动条，不再压缩到看不全。
- 增加 table viewport Resize/Show 监听；Qt 布局后二次改变表格 viewport 宽度时会复用已缓存的自然列宽重新铺满，不扫描 200 行数据，避免恢复启动卡顿。
- 分类标记编辑为更长文本时仅增量扩展该列宽，不触发整表重测；业务解析、同步、分类和中央仓库逻辑不变。

## 2.18.204

- 删除 Poke 页面冗余的“仅处理 AR/LBS/SEC Poke”按钮。
- AR/LBS/SEC Poke 继续通过“跳转类型”中的独立勾选项控制；处理逻辑、红色名称/上方或右侧/300 距离约束、数据库与 ahref 逻辑均不变。

## 2.18.202 — 2026-09-24

- 将 AR/LBS/SEC 设备 Poke 从 RMU Poke 开关中独立抽离，新增独立勾选项和“仅处理 AR/LBS/SEC Poke”执行按钮。
- AR/LBS/SEC 名称识别改为硬约束：名称 Text 必须为红色（lc=255,0,0 或 lcc=#FF0000），并且只能位于设备上方或右侧，距离不得超过 300。
- 保留原有设备识别来源、Text ID 一对一分配、Oracle 所属馈线查询、目标 ahref 命名和 Poke 写入逻辑；只改变 AR/LBS/SEC 名称候选规则。
- 仅运行 AR/LBS/SEC 时不再执行 RMU identify_rmus() 扫描，真正与 RMU 分支解耦。
- 使用用户提供的 JED-STH-ADEL-06 样本验证：正确识别 AR2240、LBS1115、LBS1197、SEC2369，并排除白色 96566 误匹配。

## 2.18.201 — 2026-09-24

- 连接与环境页明确标注中央同步/发布同时包含 Oracle 数据库与文件服务器（SSH/SFTP）配置。
- `id_rules.json` 升级为 schema v7，每条规则写入 `valid_example` 合法示例；中央校验/发布同样保留该字段。

## 2.18.200 — 2026-09-24

- Startup/performance: true lazy page construction; only the remembered page is built at startup, and the native shell paints first.
- Server Symbol Sync Management: public mode no longer constructs the retired business-G discovery/source/task panels.
- Local cache restore: removed legacy Profile repository reads from the public catalog action-state path; local snapshot parsing stays off the GUI thread and visible rows render in 100-row batches.
- Table performance: only the seven visible inventory columns are materialized; no whole-table content auto-sizing or synthetic 200-row vertical-header item creation. Column widths are calculated from the viewport and header text so all fields, including 分类标记, remain visible.
- Server interaction: start/result/finish action-state refresh no longer hydrates historical Profile data, eliminating UI stalls around otherwise-background SSH operations.
- Classification cache: cell edits update memory instantly and are debounced to a background worker; multiple edits are persisted with one manifest/marker/snapshot batch instead of rewriting three JSON files per row.
- Local/central contract unchanged: normal work is local-first; explicit central pull overwrites local cache; only Admin may publish central configuration.
- JSON schema 2 remains in force: `element_id` is preserved; XML element-tag fields stay excluded.

## 2.18.199

- 深入修复 SSH/服务器交互导致 GUI 卡死：通用远程 G 文件列表刷新、连接测试、手工下载全部移入 `FunctionWorker/QThreadPool`，不再在主线程执行 Paramiko/SFTP。
- 所有使用 `RemoteGSourceWidget` 的业务模块新增“模块独立、本地优先”服务器文件列表缓存；启动只读本机 AppData，手动刷新服务器成功后原子覆盖该模块本地缓存，服务器失败时保留原缓存。
- 远程处理快照增加本地版本清单；所选文件的路径、size、mtime 未变化时直接复用本地快照，不再重复访问 SSH。确需下载时在工作线程执行，并通过 Qt 事件循环保持窗口绘制和响应。
- 服务器文件表取消 `resizeColumnsToContents()` 全表扫描，改为固定/可调列宽与批量填充，降低大列表刷新后的 UI 开销。
- 启动阶段给原生窗口完整首帧绘制时间，并拉开各页面构造间隔，减少启动时整窗白屏/假死。
- 中央配置/ID/图元分类的短操作不再强制立即弹出 `QProgressDialog`；超过 800ms 才显示，修复“一闪而过的框”。
- 分类 JSON schema 2 新增 `element_id`（主体 ID），继续彻底排除 `element_tag/xml_tag/target_xml`；旧 schema 1 本地分类缓存会从图元 manifest 自动补齐 ID。
- 手工导入分类 JSON 改为权威覆盖本地分类缓存，不再与旧数据静默合并；中央拉取仍保持覆盖语义。

## 2.18.197

- 修复“服务器图元同步管理”启动后状态显示已从本机 AppData 恢复约 200 个图元，但图元信息表仍为 0 行的问题。
- 根因：启动时本地图元缓存先恢复，随后 0ms 延迟执行的 Profile 选择逻辑在 `load_catalog=False` 分支又清空了独立的服务器图元缓存和表格。
- 现在 `load_catalog=False` 只表示跳过旧 Profile catalog 装载，不再清空独立的服务器图元目录、解析记录和已恢复的可见表格。
- 不改变服务器同步、分类 JSON、Admin/中央仓库及其他图形处理业务逻辑。

## 2.18.196

- 恢复“服务器图元同步管理”的图元信息表格；v2.18.194/195 误删的是整张表，本版改为只移除用户要求的 XML 元素标签字段。
- 表格参考 Distribution Model Manager v4.1.52 的紧凑设计，显示图元定义文件（服务器相对路径）、w×h、AlignCenter、Pins、标准来源、分类标记和状态；XML 元素类型仅保留为内部兼容数据，不再展示。
- 启动从本地缓存恢复时继续使用轻量 QTableWidgetItem 批量渲染和固定列宽，不恢复旧的 Profile/ComboBox 重型行，避免 200 行左右图元表再次造成明显卡顿。
- “导出 JSON”及中央 `symbol_classification.json` 升级为 schema 2，只保存相对路径、文件名、devref 和分类标记；不导出/传播 `element_tag`、`xml_tag`、`target_xml` 等 XML 元素标签字段。
- Admin、中央仓库、服务器只读同步、图元解析及其他内部业务处理逻辑保持不变。

## 2.18.195

- 修复“服务器图元同步管理”在移除服务器图元大列表后出现的大面积纵向空白。
- 仅调整该页面布局：页面头和“服务器图元与分类”区域按内容高度顶端紧凑排列，剩余空间留在页面底部。
- 不修改服务器图元同步、图元解析、分类、Admin/中央仓库或其他业务处理逻辑。

## 2.18.194

- Removed the large server-symbol inventory/search table from the visible Server Symbol Sync Management page.
- Local cache restore and normal manual symbol sync no longer build the 200-row QTableWidget; the parsed server catalog and physical inventory remain in memory/cache for downstream logic.
- Existing local classification marker JSON is preserved in tableless mode and is never cleared because the compatibility table is empty.
- Central Admin behavior now follows Distribution Model Manager v4.1.52: any client may explicitly take over Admin without an application-level Admin password; takeover changes only Admin ownership and never auto-syncs/publishes business configuration.
- Added `admin_epoch` ownership generation to prevent stale Admin sessions from publishing after another takeover.
- While this process is Admin, it checks only the tiny central `instance.json` every 10 seconds and automatically downgrades if ownership changes; no database/file-server/ID/symbol configuration is auto-synced.
- Closing G File Studio no longer releases central Admin ownership; release is explicit, or another client can take over. Startup remains strictly local-only.
- Ordinary clients remain free to edit/save local configuration and manually pull central configuration; central publish operations still require the current Admin.

## 2.18.193

- Reworked local server-symbol cache rendering for startup performance.
- Reading the local JSON was not the bottleneck; the old code rebuilt hidden legacy
  Profile/editor rows, created many QComboBox widgets, and repeatedly auto-sized the
  complete QTableWidget.
- Cached restore now renders one lightweight physical-file inventory row per cached G
  file using QTableWidgetItem only.
- Table updates/signals are suspended during the batch render and fixed operator
  column widths are used instead of resizeColumnsToContents scans.
- Cached classification markers are consumed from the already-merged snapshot and
  are not read/matched a second time.
- Status now explicitly states that data came from local AppData and the server was
  not accessed.

## 2.18.192

- Server Symbol Sync Management now restores existing local AppData cache immediately
  when the page is constructed; local cache is the default source.
- Removed the extra end-of-startup delayed catalog restore from MainWindow.
- Added compatibility discovery for older local SymbolLibrary cache directories by
  reading cached host/root metadata from sync_snapshot.json or manifest.json.
- If no local cache exists, the page stays empty and explicitly does not contact SSH
  or the central repository.
- Existing classification-marker restore and Admin fixes from v2.18.191 are retained.

## 2.18.191

- Restored the missing `_admin_lease_config()` helper used by explicit Admin password/lease operations.
- Admin actions now read the already-saved local SSH configuration and no longer fail with an AttributeError.
- Fixed local classification markers disappearing after restart even though the server-symbol catalog snapshot was restored.
- `classification_markers.json` is now treated as the authoritative local classification layer and merged with `manifest.json`.
- Local server-symbol snapshot restore explicitly reapplies the local classification layer after the table is rebuilt.
- Startup remains local-only and does not read central configuration, SSH or Oracle automatically.

## 2.18.190

- Fixed Windows "Not Responding" during startup caused by constructing all 13 Qt pages
  synchronously in one GUI-thread loop.
- All pages are still created automatically without user clicks, but page construction
  now yields to the Qt event loop after each page.
- The last-used business page is created first so the operator can use it immediately
  while the remaining pages continue automatic local initialization.
- Central configuration, SSH and Oracle remain completely excluded from startup.
- Existing AppData caches are still local-first; server-symbol cache restore remains local-only.

## 2.18.189

- Fixed local server-symbol cache restore being incorrectly gated by legacy Site/Profile selection.
- Server Symbol Sync Management now automatically restores the existing local AppData catalog even when no Profile exists.
- `保存到本地` now persists both classification markers and the current visible server-symbol catalog snapshot.
- Local-cache restore remains strictly local-only and never contacts SSH or the central configuration repository.
- Added explicit status text when a cached server-symbol inventory is restored.

## 2.18.188

- Added non-blocking progress dialogs for manual central connection-config and symbol-classification synchronization/publishing.
- Central network operations remain on FunctionWorker/QThreadPool background workers.
- Optimized classification-table refresh by indexing cached server records by remote path.
- Added `id_rules.json` to the central configuration repository.
- ID page now provides manual `从中央同步规则` (ordinary users) and `发布规则到中央` (current admin) actions.
- Manual central ID-rule sync overwrites the local AppData ID-rule cache.
- Central `instance.json.files` now records `id_rules.json`; publishing ID rules increments `config_version`.
- Startup remains local-only and never reads any central file.

## 2.18.187

- Missing paths under the disposable `workspace` tree no longer show startup/browse warnings.
- Stale remembered workspace run paths are silently ignored and pages fall back to their managed runtime path.
- Managed output modules no longer require an old workspace output directory to exist before execution.
- `begin_managed_run()` recreates `workspace/runs/<module>` automatically when the workspace was deleted.
- Missing non-workspace user/business paths still keep their normal warning behavior.

## 2.18.186

- Startup/read paths are now side-effect free for local persistent state.
- Missing local configuration/cache stays missing; startup does not manufacture empty/default cache files.
- User settings writes are temporarily disabled while all pages are automatically constructed.
- ID rules use built-in defaults in memory when no local `id_rules.json` exists, without creating the file.
- Remote symbol-library reads no longer create `Cache/SymbolLibrary/...` directories; directories are created only by explicit sync/save/import operations.
- Site profile and symbol repository constructors no longer create AppData directories just by opening the application.
- SSH/Oracle fields no longer pretend unsaved factory values are a local configuration.
- Machine ID is created only when an explicit administrator/publish action actually needs it.
- Central configuration remains manual-only and is never pulled because local state is missing.

## 2.18.185

- Changed startup page construction from timer-per-page staging to one-shot full page creation.
- The lightweight main window is shown first; one startup callback then constructs all 13 pages.
- No user click is required and all pages exist after that single initialization pass.
- Heavy local server-symbol catalog/table hydration remains deferred until after page creation.
- Startup remains strictly local-only: no central repository, SSH, or Oracle access.
- Persistent configuration/cache remains under AppData; workspace remains disposable runtime data.

## 2.18.184

- Reworked startup to eliminate the native white-window stall while still automatically
  loading every business page on every launch.
- MainWindow now renders the shell first, then eagerly constructs all 13 pages one per
  event-loop turn; no user click is required.
- Server-symbol local catalog restore remains automatic but runs after the shell/pages
  exist and reads only the local AppData cache.
- Central configuration, SSH and Oracle remain strictly manual/no-network during startup.
- UserSettingsService no longer rewrites the INI when values are unchanged and batches
  legacy disposable-workspace key cleanup into one disk write.
- Persistent configuration/cache remains under AppData; workspace remains disposable.

## 2.18.183

- Restored the original eager page lifecycle: every business page is created at startup and restores its local cached state immediately.
- Central configuration is strictly manual-only on every launch, including first initialization and missing-local-config cases.
- Startup/page construction never reads central `instance.json`, `symbol_classification.json`, `database.json`, or `file_server.json`, and never tests SSH/Oracle connectivity.
- Local workstation configuration remains authoritative until the operator explicitly chooses central sync; central sync overwrites the corresponding local caches.
- Persistent local state (database/file-server settings, symbol classifications, ID rules, symbol standards, user/navigation habits and other settings) remains under per-user AppData roots, never under `workspace`.
- `workspace` remains disposable runtime/business input, intermediate and output data only.

## 2.18.182

- Fixed the startup white-screen bottleneck without reintroducing lazy business pages.
- MainWindow still creates the established business pages and restores the last-used page.
- The heavy local server-symbol table is no longer rebuilt inside MainWindow construction.
  Its AppData snapshot is restored after the selected page has painted.
- Removed `workspace/runs` retention scanning from MainWindow startup; run cleanup remains
  available when run records are actually created/listed.
- Central configuration, SSH and Oracle remain strictly manual/on-demand.

## 2.18.181

- Hardened `DatabasePage` initialization against stale/early status refresh calls.
- `central_config_status` is now accessed through a defensive `getattr` guard.
- Added regression coverage that forbids `_refresh_local_cache_source_status()` before the status widget exists.
- No central configuration is read automatically at startup.

## 2.18.180

- Fixed `连接与环境` page construction failure caused by refreshing local-cache
  source status before `central_config_status` was created.
- The page now builds all widgets first, restores local SSH/Oracle settings, and
  only then refreshes local cache provenance.
- Added a defensive initialization guard so status refresh can never blank the page.
- Keeps v2.18.179 normal page startup behavior and manual-only central configuration access.

## 2.18.179

- Restored the established pre-v2.18.176 main-window startup/page-loading lifecycle.
- Business pages are created normally at startup again and the last-used business page is restored.
- Kept the manual-only central-configuration rule: startup never pulls central configuration.
- Kept all persistent configuration/cache/state under the per-user AppData roots, outside `workspace`.
- `workspace` remains disposable business input/intermediate/output data only.

## 2.18.178
- Consolidated per-version UPDATE_NOTES files into CHANGELOG.md; future releases no longer create one UPDATE_NOTES file per version.
- Formalized workspace as disposable business/runtime data only. Persistent configuration, symbol cache/classification markers, and standard repositories live under the user AppData directories.
- Added centralized persistent path helpers and regression guards preventing persistent configuration/cache services from using workspace.

## 2.18.177
- Enforce local-first configuration caches; central configuration is never auto-pulled, including when local configuration is missing. Manual sync overwrites local cache.


## 2.18.176
- Fast local-only startup: lazy-load business pages, defer local symbol-catalog restoration, and remove automatic SSH/Oracle/central/server-symbol checks.

## 2.18.175
- Fix station Poke recognition: station Text + colored background only; remove device-classification exclusion; adjacent RMU locateLabel <= 300.
## 2.18.174 - 2026-09-22

- Central configuration is now strictly manual: application startup and opening the server-symbol page never read remote `instance.json`, `symbol_classification.json`, `database.json`, or `file_server.json`.
- Removed the dormant automatic central-classification sync helpers so future startup code cannot accidentally re-enable silent remote synchronization.
- Central reads now happen only after explicit operator actions such as **从中央同步**, central publish/admin operations, or the global configuration-access dialog.

## v2.18.172

- Simplified Connection & Environment by removing the redundant multi-environment Profile UI.
- Workstations now directly edit one shared local SSH/Oracle configuration while retaining central sync/publish.

## v2.18.171

- Moved central configuration administrator control to a persistent sidebar entry.
- Simplified Server Symbol Sync Management by removing its visible admin controls.
- Kept central `instance.json` ownership semantics and local-workstation configuration behavior unchanged.

## 2.18.170

- Central configuration moved to `/home/up8000/nari-international/gfilestudio/config/` with `instance.json`, `symbol_classification.json`, `database.json`, and `file_server.json`.
- `instance.json` now owns the single Admin machine/IP and global config version; Admin persists until explicitly released.
- Ordinary workstations can keep local custom configuration and explicitly sync from central to overwrite it.
- Database/file-server configuration now supports central publish/sync.
- Server-symbol page wording/layout simplified.

## 2.18.169

- Added a server-wide single-administrator lease (`classification_registry/admin_lock.json`) recording workstation name and SSH source IP.
- Ordinary workstations auto-sync the administrator-published `symbol_classification.json` and cannot edit while another workstation owns admin mode.
- Added explicit administrator release plus heartbeat/expiry recovery, and simplified the Server Symbol Sync page.

## v2.18.168
- Renamed the single server classification file to `/home/up8000/nari-international/gfilestudio/classification_registry/symbol_classification.json`.
- Redesigned classification actions into explicit local/server operations: `保存到本地`, `导出本地 JSON`, `导入本地 JSON`, `从服务器同步`, and `上传到服务器`.
- Upload always saves the visible classification table locally first, then atomically replaces the one server `symbol_classification.json`.
- Server synchronization warns before overwriting local classification markers and treats the server file as authoritative.
- No numbered history files are created; the server keeps only the single `symbol_classification.json`.

## v2.18.167
- Added a single SSH/SFTP central classification configuration at `/home/up8000/nari-international/gfilestudio/classification_registry/admin.json`.
- `admin.json` is the only authoritative central file; no numbered classification history files are created.
- Ordinary mode can synchronize from the central file; administrator mode can publish/replace it.
- The server element symbol tree remains read-only.

# v2.18.166

- 服务器图元同步管理新增“普通模式 / 管理员模式”；程序每次启动固定从普通模式开始。
- 普通模式允许连接设置、服务器图元同步/查看、本地缓存查看和分类 JSON 导出；分类标记为只读，禁止载入和保存分类修改。
- 首次部署没有管理员密码时仍可完成环境配置与首次同步；维护人员可在页面执行一次“初始化管理员”。
- 管理员密码使用 PBKDF2-SHA256 + 随机盐保存校验值，不保存明文；管理员模式可修改、载入、保存分类标记，并可修改管理员密码。
- 分类标记的写入入口增加权限二次校验，避免仅依赖按钮禁用。

# v2.18.165

- 吉达馈线批处理严格使用服务器图元同步管理中本地保存的四个分类标记作为目标图元：`CIRCUIT_BREAKER_SMART`、`LOAD_BREAKER_SWITCH_SMART`、`CIRCUIT_BREAKER_NO_SMART`、`LOAD_BREAKER_SWITCH_NO_SMART`。
- RMU 内设备类型以当前元素原始 `devref` / 图元文件名为准：包含 `Circuit_Breaker` 按 Circuit Breaker，包含 `Load_Breaker_Switch` 按 LBS；Y/Q 显示名称不覆盖原图元类型。
- 柜内存在 `SMART` 文字时使用两个 SMART 标记目标；不存在 `SMART` 时使用两个 NO_SMART 标记目标，RMU 外框继续分别强制红色/白色。
- 取消 v2.18.164 的“参考同图其他 NORMAL 柜选择图元版本”行为；同图其他柜不会覆盖人工分类标记。
- 吉达运行时只读取本地已保存分类标记，不因批处理重新连接或修改服务器图元库。

# v2.18.162

- Poke 站点跳转读取服务器图元同步管理的本地分类标记；FUSE、LBS、AR、SEC、Transformer_OH 图元周边 300 以内的站点名称直接排除。
- 站点跳转相邻环网柜名称距离统一限制为 200 以内，超过 200 不再写入 locateLabel。

# v2.18.161

- 同步管理表格隐藏“来源”“主体 ID”“图形 G 发现 devref”三列，保留内部字段供缓存和后续程序使用。
- 搜索提示改为面向图元文件、XML、分类标记和服务器相对路径。

# v2.18.160

- 首次部署且没有本地同步缓存时仍要求手动同步；后续启动自动恢复本地缓存表格，不再每次显示空表。
- 恢复本地缓存只读取本机文件，不会在启动时连接服务器；服务器读取仍按首次手动同步及每日后台同步执行。

# v2.18.159

- 同步时继续按文件名沿用本地图元和分类标记，但额外提示服务器文件的最新修改时间。
- 表格路径提示和同步结果会显示更新文件、相对路径及 UTC 修改时间。
- 内容变化不触发重新下载或重新解析，避免影响分类并保持同步速度。

# v2.18.158

- 启动时不再加载本地图元表或恢复服务器图元缓存，首次读取改为手动同步。
- 已有同步记录每天自动后台同步一次，首次同步完成后开始计算 24 小时周期。
- 图元同步按文件名复用缓存；服务器图元内容、大小或修改时间变化不会清除分类标记。

# v2.18.157

- 优化程序启动速度：窗口先显示，再恢复本地图元目录和分类标记。
- 缓存恢复优先使用服务器图元快照，避免启动时重复构建同一张表格。
- Profile 配置在一次页面刷新期间复用解析结果，减少重复读取和规范化配置文件。

# v2.18.156

- 修复程序启动恢复服务器图元表格时，把自动填充分类标记误判为用户编辑的问题。
- 启动恢复不再逐行写入分类 JSON、同步快照和本地缓存，减少启动等待时间。
- 只有用户手动编辑或点击“保存分类标记”时才会写入分类记录。

# v2.18.155

- 服务器图元同步管理增加“保存分类标记”按钮。
- 分类标记可一次性明确保存到本机缓存，并显示保存成功或失败数量。

# v2.18.154

- 修复 ID 规则表首次打开时最后一列不填充剩余宽度的问题。
- 保持窗口缩放和表格内容变化时的自适应布局。

# v2.18.153

- 修复服务器图元同步管理重启后分类标记未从本地标记记录恢复的问题。
- 分类标记保存时同步更新本地快照；缓存恢复、服务器同步和表格刷新都会继续沿用已有标记。
- 分类标记仍按服务器相对路径优先匹配，服务器文件内容和服务器目录保持只读。

# v2.18.152

- 优化服务器图元同步：未变化的 `.g` 只做元数据复用，不重新下载或解析。
- 同步结果未变化时不再重建整张图元表格，只更新同步状态和统计信息。
- 只有新增、删除、元数据变化或解析状态变化时才刷新表格。

## v2.18.151

- 严格按最终扩展名为 `.g` 的规则统计服务器图元，`.g.png` 等预览文件不会进入清单。
- 打开旧缓存时同步过滤非 `.g` 文件，避免历史缓存污染表格数量。

## v2.18.150

- 修复服务器图元同步管理重启后只显示可解析图元数量的问题。
- 同步时保存完整服务器 `.g` 文件清单；下次打开恢复全部物理文件，解析失败和同名冲突文件继续保留并显示状态。
- 服务器图元同步页面继续保持只读，不修改服务器内容。

## v2.18.149

- 发布版本号升级至 `2.18.149`。
- 修复源码运行 `python app.py` 时页面初始化导致的 Qt 启动崩溃。
- 保留图元库存旧名称分配接口，兼容既有调用和回归测试。

## v2.18.148

- Repository hygiene hotfix: protect runtime/build/release outputs from Git tracking.
- Explicitly ignore `workspace/runs/` and `release/`, including the large generated content-analysis report that can exceed GitHub's 100 MB hard limit.
- Business algorithms are unchanged from v2.18.147.

## v2.18.112

- 图元标准表左侧显示连续序号 1..N，并在表格上方实时汇总总图元数、当前显示、已上传标准、待上传标准以及业务 G 扫描实例总数。
- “扫描图形 G 发现图元”的进度条移动到扫描按钮正下方，点击后立即进入可见工作状态。
- SSH 远程扫描不再在 UI 线程同步执行 SFTP 下载；远程文件快照下载进入 FunctionWorker 后台线程，下载阶段显示 busy 动画，完成后切换为图元 XML 解析的 0~100% 百分比进度。
- 保持 SSH 严格只读和标准来源规则不变；未修改受保护的远程下载服务及既有 G 业务处理算法。

## v2.18.111

- 修复侧栏分组大标题在高 DPI / Windows 显示缩放下被裁切、下边框显示不全的问题。
- 分组标题行高调整为 74px，标题按钮保持 40px；移除分组容器额外垂直 margin，避免与 QListWidget item padding 重复占用高度。
- 分组标题字号提升到 14px，导航间距调整为 2px。
- 顶部“G 文件处理工具”固定 32px 高并提升显示字号。
- 仅修改侧栏展示，不改变任何页面索引、折叠状态、业务处理器或黄金基线逻辑。

# v2.17.60

- 将“彻底取消图形组合”从 RMU 专用语义调整为基础处理中的通用“图形组合处理”。
- 启用后删除当前 G 文件 Layer 中全部 `<Merge>`，不再区分 RMU Merge / 其他业务 Merge。
- 删除 Merge 后，按 BusDis + CBreakerDis + ZhaiWaiJieDiDaoZha 硬条件识别 RMU 外框，并仅调整 `<rect>` 的 XML 顺序使其位于设备底层。
- 除删除 `<Merge>` 和调整 RMU `<rect>` 顺序外，不修改任何设备属性、坐标、ID、keyid、devref、tfr 或业务关联。
- RMU 页面不再提供“取消所有环网柜组合”，避免把全图 Merge 清理误解为 RMU 专用操作。

## v2.17.59

- SSH/SFTP 只读文件源新增“保存 SSH 设置”按钮，可保存 IP/主机、端口、用户名、密码和远程目录。
- SSH 参数在字段结束编辑时自动保存为最后一次输入，不再要求先测试连接或刷新列表才能记住。
- SSH 参数继续采用全局共享配置；异常小尺寸、ID、RMU、基础处理、馈线合并、边距调整、图框添加等所有使用远程 G 文件源的模块都会复用并同步最近一次保存的参数。
- 远程访问安全边界不变：仍然只允许 list/stat/SFTP GET 下载，不新增上传、覆盖、删除、重命名或远程建目录能力。

## v2.17.58

- 基础处理“线路与母线颜色”升级为“线路与母线样式”。
- FeedLine / ConnectLine / BusDis / Bus 均可独立选择线型：保持原样、实线、虚线。
- 线型仅修改 XML 属性 ls：实线=1，虚线=2；保持原样不修改 ls。
- 颜色修改与线型修改彼此独立；只改线型时不会改动 lc/lcc。
- 不修改 lw、填充色、坐标、ID、引用或拓扑。

## v2.17.57

- 修复点击“设置母线分组”时因 `QHeaderView` 未导入导致的 NameError；人工分组业务逻辑不变。

## v2.17.56
- 主母线人工分组弹窗去除重复“顺序”列；顺序完全沿用馈线合并主列表，文件名列自适应拉伸并完整显示。

- 修复“基础处理”使用 SSH 远程 G 文件时，“扫描元素与属性”无法加载元素标签/属性名的问题。
- SSH 模式点击扫描时，先通过严格只读 SFTP GET 将当前勾选 G 文件下载到 `workspace/remote_input/basic` 本地快照，再由现有 schema 扫描器读取；业务规则编辑器不直接操作服务器路径。
- 远程文件勾选发生变化时提示重新扫描，避免使用旧缓存结果；本地文件/目录扫描逻辑保持不变。
- 服务器仍无上传、覆盖、重命名、删除或修改接口。

## v2.17.54

- 优化“设置主母线人工分组”弹窗按钮对比度：创建、清除所选、清空全部分别使用更深的绿色、灰绿色和红色，浅色背景与禁用状态下文字仍清晰可见。
- 仅调整该弹窗按钮视觉样式，不修改人工母线分组、单/双母线和馈线合并业务逻辑。

## 2.17.52

- 修复本地 G 文件/目录输入时路径选择行偶发被压缩的问题。
- `InputSourceSelector` 与 `PathRow` 显式使用横向 Expanding 策略，并移除切换输入源时会触发收缩的 `adjustSize()`。
- 仅调整通用输入组件布局，不修改业务处理逻辑。

# v2.17.51

- 移除左侧“操作历史”页面；30 天 workspace 运行目录自动清理机制继续保留。
- 馈线图合并输出目录继续强制使用 `workspace/runs/merge` 管理目录，界面只读、不可浏览修改；处理完成通过“打开本次运行目录”查看/复制结果。
- 修复本地输入模式下 SSH 远程文件表仍参与布局尺寸计算导致的大面积空白；统一输入组件和馈线合并页面均改为仅让当前输入源参与布局。
- 不修改馈线合并、主母线、ID、RMU 等业务算法。

# v2.17.50

- 修复“操作历史”页面 BasePage 导入路径错误，解决 app.py 启动时 ModuleNotFoundError。
- 增加启动级静态导入路径回归检查，确保 g_file_studio 内部模块引用均可解析到实际文件。
- 其他业务逻辑不变。

# v2.17.49

- 统一 G 输出命名：所有“一份源 G → 一份处理后 G”的模块严格保持源文件名，不再追加时间戳、模块标记或其他后缀。
- 覆盖异常小尺寸图元处理、ID 修复、RMU 图元处理、基础处理、连接点处理、图形边距调整、图框添加等一对一输出链路。
- 运行批次仍由 `workspace/runs/<module>/<run>/` 隔离，因此同名 G 文件不会跨运行互相覆盖。
- 馈线合并属于“多源 → 单一新 G”，没有唯一源文件名，继续使用独立的合并输出名。

## v2.17.48

- 新增全局“操作历史”：所有业务模块每次运行创建独立 `workspace/runs/<模块>/<时间_操作>` 目录，并记录 `run.json` 状态。
- 运行记录默认保留 30 天；程序启动、创建新任务和打开历史页时会自动清理超期目录。需要长期保留的结果请自行复制。
- 异常小尺寸图元检测、ID 检查与修复、环网柜处理、基础处理、馈线图合并、图形边距调整、图框添加的输出目录统一由程序管理，界面仍显示路径但改为只读，禁止用户修改。
- 每个模块“执行与日志”中的目录按钮统一改为“打开本次运行目录”，直接定位本次 G/CSV/HTML/日志相关文件所在目录。
- 新增“操作历史”页面，可查看最近 30 天任务的时间、模块、操作、状态与目录，并一键打开历史运行目录。
- SSH 远程 G 文件仍严格只读：远程文件只下载到 workspace 本地快照，所有处理结果仅写入 workspace/runs，不增加任何服务器写接口。
- 其他 G 文件处理、ID、RMU、馈线合并和图框算法不变。

## v2.17.47

- 修复“异常小尺寸图元检测”使用 SSH 远程 G 文件时因遗漏 `validate_input_source` 导入导致的 NameError。
- SSH 业务处理继续采用严格只读架构：远程端仅 SFTP GET/目录读取/属性读取；所选 G 文件先下载到 `workspace/remote_input/<模块>` 本地快照，再交给原业务引擎处理。
- 增加处理快照目录保护，自动处理快照必须位于本地 workspace 下；日志明确显示“服务器只读 → workspace 本地快照 → 业务处理”。
- 不增加任何服务器上传、覆盖、删除、重命名或修改接口。
- 其他业务逻辑不变。

## v2.17.46

- 修复统一输入源在本地模式下被 SSH 文件列表 sizeHint 撑出大块空白的问题；仅当前输入方式决定页面高度。
- 馈线合并主母线处理：第一条顶部主母线仍作为整图对齐绝对基准；同 keyid 的后续主母线采用多数 Y 自动归一化，少数偏移 Bus 自动移动并同步拉伸直接连接线端点后再合并。
- 其他业务逻辑不变。

## v2.17.45

- 参考 Distribution Model Manager v4.0.9 的只读 SSH/SFTP 文件源实现，为所有 G 文件输入模块增加统一远程输入。
- 默认服务器参数：172.16.21.27:22 / up8000 / `/home/up8000/data/graph/display/sln`。
- 支持远程 G 文件搜索、单选、多选、当前结果全选/取消、文件大小和修改时间查看。
- 支持独立“下载所选到本地”操作；该操作不会清理用户目标目录中的其他 G 文件。
- 业务执行使用本地只读快照，服务器端无上传、删除、重命名、覆盖或目录写入 API。
- 馈线合并增加本地目录/SSH 远程输入切换，远程选择下载后继续复用原检查、导入、排序和母线处理逻辑。
- PyInstaller 构建增加 paramiko/cryptography 收集，requirements 增加 paramiko。

# Changelog

## 2.18.201 — 2026-09-24

- 连接与环境页明确标注中央同步/发布同时包含 Oracle 数据库与文件服务器（SSH/SFTP）配置。
- `id_rules.json` 升级为 schema v7，每条规则写入 `valid_example` 合法示例；中央校验/发布同样保留该字段。

## v2.17.44

- 馈线合并：主网母线 keyid 排序阻断告警增加具体 G 文件名、合并顺序、上/下母线、Bus XML ID、Y 坐标和中间阻断文件，便于快速定位。
- 仅增强主网母线预检查错误信息，不修改母线筛选、keyid 连续性、单/双母线或实际合并逻辑。

## 2.17.43

- 图形边距调整取消“输出标记”，输出文件固定保持源文件名。
- 输出目录存在同名文件时提供“覆盖 / 跳过 / 取消”选择。
- 禁止图形边距调整结果直接覆盖源文件。
- 其他业务逻辑不变。

## v2.17.42

- 图框添加移除“输出标记”，输出文件固定保持源文件名。
- 输出目录存在同名文件时可选择覆盖、跳过或取消。
- 禁止将同名图框结果直接写回源文件位置，避免误覆盖原始 G。
- 其他业务逻辑不变。

## v2.17.41（RMU 柜型双源交叉校验增强）

- RMU 柜型第一来源：柜内 Y1/Y2/... 与 Q1/Q2/... 文本，Y 数量=L、Q 数量=T，并检查编号是否从 1 连续递增。
- RMU 柜型第二来源：CBreakerDis.devref 图元文件名，Load_Breaker*=L、Circuit_Breaker*=T。
- 两种来源同时存在时进行交叉校验；不一致或 Y/Q 序号异常时报告 FAIL 并红色标记。
- RMU 报告新增 TypeSource、TextYQType、DevrefType、TypeCrossCheck、TypeValidationStatus、TypeCrossNote 字段及汇总统计。
- 柜名继续采用全局一对一分配：所有有效 RMU 同时参与名称归属，但仍严格只搜索用户勾选的方向；单候选直接采用，多候选绿色优先。
- 未修改既有 RMU 组合/取消组合、SMART/SMR 外框处理、台账对比和其他模块逻辑。

# Changelog

## 2.18.201 — 2026-09-24

- 连接与环境页明确标注中央同步/发布同时包含 Oracle 数据库与文件服务器（SSH/SFTP）配置。
- `id_rules.json` 升级为 schema v7，每条规则写入 `valid_example` 合法示例；中央校验/发布同样保留该字段。


## v2.17.40

- 异常小尺寸图元处理报告改为包含本次扫描发现的全部异常图元，并区分“已删除 / 未处理”；已删除行绿色显示。
- 每次删除仍严格从原始 G 重新生成输出，不累计上一次处理状态；扫描结果表保持原始扫描快照不变。
- RMU 信息汇总始终统计全部有效 RMU；“智能环网柜”改为可选分类维度，SMART/SMR 统一归类。
- RMU 汇总界面和 HTML 报告新增重复、名称/柜型未识别及中低置信度异常提示。

## v2.17.39

- 异常小尺寸图元处理改为完全无累计状态：每次“删除选中异常图元”都重新读取原始 G，只按本次勾选项生成输出，并覆盖上一次同名输出 G 与处理报告。
- 执行处理后不再从“异常图元结果”表移除已处理行；扫描结果始终表示原始 G 的检测快照，直到用户重新扫描或更换输入。
- 每次处理完成后仅清空本次勾选，不记忆此前处理选择。
- 异常小尺寸处理 HTML 中“已删除”结果改为绿色渲染；扫描报告仍以红色系表示异常发现。
- 其他模块与业务算法不修改。


## v2.17.38

- 环网柜处理页新增三个联动 HTML 报告按钮：图元处理、RMU 信息汇总、RMU 台账对比；仅在对应小模块启用时显示，报告生成后自动可用。
- 新增固定覆盖式 `rmu-graphic-processing-report.*` 和 `rmu-summary-report.*`，台账对比继续使用 `rmu-ledger-comparison.*`。
- 异常小尺寸图元处理按钮改为“删除选中异常图元”，明确处理语义。
- 异常小尺寸图元处理 HTML/CSV 报告新增处理结果字段与“已删除/未删除”汇总，和扫描报告明确区分。
- 其他 RMU 识别、组合/取消组合、SMART/SMR、ID、馈线合并等业务逻辑未调整。

## v2.17.37
- 所有程序生成的 HTML 业务报告统一在明细表第一列增加可多选复选框。
- 表头支持一键全选/取消全选；选中行会高亮，并显示当前已选择行数，便于人工查看宽表时防止串行。
- 该功能只影响 HTML 报告查看，不改变 CSV 内容、G 文件处理结果或任何业务算法。

## v2.17.35 - 2026-08-12

- “环网柜名称与柜型识别”更名为“RMU 信息汇总”。
- RMU 汇总统计层将 SMART 与 SMR 统一归类为“智能环网柜”；同一 RMU 同时命中 SMART/SMR 只统计 1 个。
- CSV/HTML 新增 IntelligentRMU 与 IntelligentSource，来源保留 SMART、SMR 或 SMART + SMR。
- 原环网柜组合/取消组合、SMART/SMR 外框改色、柜名与柜型识别算法不修改。

## v2.17.34 - 2026-08-12

- 环网柜处理新增“修改含 SMR 的环网柜外框颜色”，只匹配直属 `Text[ts=SMR]` 到最近的有效 RMU `rect`。
- 有效 RMU 外框仍按既有硬条件筛选：框内同时存在 `BusDis`、`CBreakerDis`、`ZhaiWaiJieDiDaoZha`；不修改 SMR Text。
- SMR 外框默认目标颜色为红色 `#FF0000`，可与 SMART、channel_status、Bus 外框等增强操作多选组合。
- 新增覆盖式 `rmu-smr-frame-report.csv/html`，每次执行覆盖上一份同类报告。
- 环网柜组合/取消组合、SMART 外框、channel_status、Bus 外框、柜名与柜型识别算法未修改。

## v2.17.33 - 2026-08-12

- 报告按钮统一简化为“打开报告”。
- 异常小尺寸图元检测：扫描报告固定覆盖 `small-element-scan-report.csv/html`，执行处理报告固定覆盖 `small-element-process-report.csv/html`，不再持续累积历史报告；扫描和执行按钮增加报告提示。
- ID 检查与修复：扫描报告固定覆盖 `id-scan-report.csv/html`，强制修复报告固定覆盖 `id-repair-report.csv/html`；扫描与修复按钮增加报告提示，扫描发现新元素类型后逐条人工确认加入模板的逻辑保持不变。
- 新增独立“环网柜处理”页面，位于“ID 检查与修复”之后、“基础处理”之前；将原基础处理中的“环网柜图元处理”和“环网柜名称与柜型识别”完整迁移到该页面，底层仍调用既有 RMU 引擎，识别/组合算法不变。
- 基础处理页面不再展示环网柜相关控件，聚焦通用属性、图元升级、馈线标题、连接点及线路/母线颜色。

## v2.17.32

- ID 检查与修复：将扫描按钮文案调整为“扫描当前G文件（只检查ID）”，报告按钮简化为“打开报告”。
- ID 规则模板：移除“加入扫描发现的规则”按钮；扫描发现可推断的新元素类型后仍按原流程主动询问用户，并逐条确认是否加入模板，用户可取消。
- 异常图元模块恢复名称为“异常小尺寸图元检测”。
- “扫描异常图元”按钮移动到“异常图元结果”区域；执行与日志区域不再重复放扫描按钮。
- 其他业务逻辑不变。

# Changelog

## 2.18.201 — 2026-09-24

- 连接与环境页明确标注中央同步/发布同时包含 Oracle 数据库与文件服务器（SSH/SFTP）配置。
- `id_rules.json` 升级为 schema v7，每条规则写入 `valid_example` 合法示例；中央校验/发布同样保留该字段。

## v2.17.31
- 异常短线图元结果表改为普通表格单元格/区域选择，可直接复制单个 XML ID 或任意选中区域。
- 结果表第一列新增“处理”复选框，支持单选、多选及“全选处理”；移除“删除选中异常图元 / 删除全部异常图元”按钮。
- 新增统一“执行选中处理”动作：仅处理勾选项，输出修改后的 G 文件和带时间戳的 CSV/HTML 报告。
- 处理成功后，对应异常图元立即从当前结果表移除；同一次扫描中分批执行时会累计已处理项，避免后续输出恢复前一次已删除图元。
- keyid 二次确认、安全删除引用、异常检测规则及其他模块逻辑不变。

## v2.17.30
- ID 检查与修复：移除模板下方重复扫描详情；扫描结果统一进入可复制的“执行与日志”。
- ID 检查与修复：将“扫描当前 G（只检查 ID）”和“检查并强制修复 ID”改为两个独立执行按钮；扫描发现新类型后的逐条人工确认逻辑保持不变。
- ID 扫描：每次扫描同样生成带时间戳且不覆盖历史的 CSV/HTML 报告，并可直接打开本次 HTML。
- 异常短线图元检测：结果表支持 Ctrl+C 复制选中数据；删除选中/删除全部放在结果区，执行区仅保留扫描、报告、输出目录和日志操作。

# v2.17.27

- 基础处理的环网柜识别 CSV 新增 Duplicate 列，用于标记重复柜名/环网柜 ID。
- 环网柜识别同时导出 .rmu.html 报告；高置信度绿色、中等/待确认黄色、未识别和重复项红色，并保留原有全部字段与汇总统计。
- ID 检查与修复页面仅调整 ID 操作单选按钮布局，避免高 DPI 下第二个单选按钮指示器遮挡前一个“ID”文字。
- 其他业务逻辑不变。

# Changelog

## 2.18.201 — 2026-09-24

- 连接与环境页明确标注中央同步/发布同时包含 Oracle 数据库与文件服务器（SSH/SFTP）配置。
- `id_rules.json` 升级为 schema v7，每条规则写入 `valid_example` 合法示例；中央校验/发布同样保留该字段。

## 2.17.29

- 独立“异常小尺寸图元检测”更名为“异常短线图元检测”，检测范围与删除规则不变。
- 异常短线扫描每次生成带时间戳的 CSV/HTML 报告，并新增“打开本次 HTML 报告”和“删除全部异常图元”；保留“删除选中异常图元”。
- 异常短线扫描详细结果统一写入可复制的“执行与日志”。
- ID 检查与修复的“扫描当前 G”按钮移动到“执行与日志”区域，扫描结果写入可复制日志。
- ID 检查/修复每次生成独立带时间戳的 CSV/HTML 汇总报告，并新增“打开本次 HTML 报告”；历史报告不覆盖。
- 其他模块与业务处理逻辑不变。

## v2.17.26

- ID 检查与修复：ID 规则模板恢复单行高亮选择，移除首列复选框；编辑/删除仅作用于当前选中规则，删除一次一条。
- ID 检查与修复：ID 操作两个单选项增加固定间距，避免选中指示器与前一项文字视觉挤压。
- 其他模块与业务处理逻辑不变。

## v2.17.25

- 修复 Windows `build_exe.ps1` 发布包文件名生成语句，改用 PowerShell 原生字符串插值，避免 `_` 被错误转义后导致 ParserError。
- 打包版本继续自动读取 `g_file_studio.__version__`，不再硬编码版本号。
- 业务功能不变。

## v2.17.24

- 修复 `build_exe.ps1` 发布 ZIP 文件名长期硬编码为 v2.17.1 的问题；发布版本号现在自动读取 `g_file_studio.__version__`。
- 同步项目版本为 2.17.24。
- 界面品牌文案精简：侧栏副标题改为“NARI 国际业务部”，模式标签改为“G 文件处理工具”，窗口标题改为“G File Studio · NARI 国际业务部”。
- 其他业务功能不变。

# v2.17.20


## v2.17.23

- 主母线处理新增“单母线 / 双母线”选择；启用时弹窗选择，亦可通过旁边按钮重新选择。
- 单母线只检查每个馈线文件 Y 最小的最高有效水平 `<Bus>`；其他 Bus 不参与 keyid 校验。
- 双母线检查最高母线以及同方向下方、长度大致相同且水平投影重叠的第二条有效水平 `<Bus>`；两条母线必须分别具有独立非空 keyid。
- 主母线处理完全忽略 XML `w < 10` 的 `<Bus>`。
- 继续强制检查：所选 Bus 的 keyid、同 keyid 馈线连续性、合并后同一水平线；不同 keyid 永不互连。
- 移除 facID/facName 硬性判断；文件名仅作人工警告。
- ID 检查与修复“扫描当前 G”新增可见扫描进度窗口，逐文件更新进度。
- 除上述两块外不修改其他业务功能。

## v2.17.22

- 主母线合并取消 facID/facName 厂站硬校验；文件名/厂站仅作为人工确认提醒，不阻止启用。
- 主母线合并强制检查每个有效水平 `<Bus>` 的 `keyid`；缺失属性或空值时禁止启用。
- 支持单母线和双母线文件：一个文件可存在两个不同 keyid，两个母线分别独立处理，绝不跨 keyid 合并。
- 同一 keyid 在馈线排序中必须连续；出现 A/B/A 式阻断时拒绝执行。
- 真正合并前强制检查同 keyid Bus 在对齐后是否处于同一水平线；不同水平线禁止合并。
- 其他业务功能不变。

## v2.17.21

- 馈线图合并的主母线处理升级为按顶部 `<Bus keyid>` 分组。
- 启用前要求所有参与馈线的顶部主母线都有非空 keyid；任一未关联则禁止启用。
- 只合并用户排序中相邻且 keyid 完全相同的馈线；不同 keyid 始终保留为不同母线。
- 若同一 keyid 出现 A-B-A 这类被其他 keyid 阻断的排序，直接拒绝并提示“馈线排序不准确，母线 keyid 被阻断”。
- G 根节点 facID/facName 可用时自动拒绝已知跨厂站输入；不通过文件名猜测厂站。
- 母线删除后的引用重写、ID 完整性校验及其他馈线合并逻辑保持不变。

- 将用户提供的 `SLD-Drawing-Frame-Template.sln.pic(2).g` 替换为新的内置图框模板，并存放于 `resources/templates/SLD-Drawing-Frame-Template.sln.pic.g`。
- ID 检查与修复页面移除 Alias 相关说明；ID 规则、扫描、修复和其他业务逻辑保持不变。

# v2.17.19

- 馈线图合并：勾选“合并主母线为一条”时立即弹出警告，要求确认参与合并的所有馈线 G 文件必须来自同一厂站。
- 取消勾选不弹提示；母线合并、ID、布局与其他业务逻辑不变。

## 2.17.16

- ID 规则模板第一列改为“选择”复选框，仅用于批量选择删除；规则本身始终启用。
- 删除规则支持一次勾选一条或多条，并在确认后立即持久化删除。
- “启用全局 ID 模板强制约束”默认开启但允许关闭；关闭时明确警告：已有格式不符 ID 不再被强制改写，新生成 ID 仍优先使用已确认模板。
- 馈线合并、图框添加、基础处理中的新 ID 分配继续优先使用全局已确认 ID 模板，并按同类型当前最大合法完整 ID + 1。
- 馈线合并“输出文件名”从顶部输入输出区域移动到“执行与日志”之前。
- 版本验证报告统一移动到 `docs/validation/`，避免项目根目录随版本增长堆积。

## 2.17.14

- 修复合并主母线后 `required_target_ids` 仍保留已删除 Bus ID 导致最终校验失败。
- 主母线合并返回删除 Bus 到保留 Bus 的映射，并同步最终引用校验目标。
- 新增回归测试，确保删除 Bus 后引用完整性校验通过。

## 2.17.13

- 馈线图合并新增“合并主母线为一条”选项。
- 仅合并各馈线已对齐的顶部非零长度水平 <Bus>，BusDis 和其他 Bus 不受影响。
- 保留第一条主母线 ID，将母线从第一张馈线连续延伸到最后一张馈线，并删除其余顶部主母线。
- 被删除 Bus 的 node_area/link/p_FatherObjId 引用统一改接到保留 Bus，保留 Bus 汇总所有馈线连接关系。
- 合并输出继续执行“ID 检查与修复”中已确认的 ID 模板强制规范。

## 2.17.12

- 馈线图合并新增“默认单线图宽度”，默认 1000。每张馈线实际宽度小于该值时按该值预留占用宽度，超过则按实际宽度；用户设置的相邻馈线间隔始终额外计算，不包含在默认宽度内。
- ID 检查与修复：删除规则改为立即持久化删除，内置默认规则删除后不会在刷新或重启时自动恢复；用户重新新增/确认后才恢复。
- 扫描当前 G 时先做模板覆盖检查，列出未覆盖元素类型；可自动识别候选前缀和总位数，并逐条打开预填好的规则确认窗口，由用户最终确认是否加入模板。
- 已有规则出现前缀/总位数不一致时继续单独提示格式变化，不自动改模板。
- 其他基础处理、环网柜识别、ID 强制修复、图形边距、图框添加等逻辑保持不变。

## 2.17.11

- 环网柜柜名识别继续严格限制用户勾选方向，未选方向不参与 Text 搜索。
- 指定方向无法分配独立柜名 Text 时，允许使用柜内唯一 BusDis.key_name（如 30864_BUS）作为元数据回退，避免抢占相邻环网柜名称。
- JED-NTH-ABH.sln.pic.g 在仅选择“上方”时由 337/340 提升为 340/340。
- 其他柜型、SMART、ID 与基础处理逻辑不变。

## 2.17.10

- 环网柜柜名改为用户指定方向内的全局一对一匹配。
- 未勾选方向不再参与任何兜底。
- 相邻环网柜不能重复占用同一个 Text。
- 多候选仍按绿色优先，单候选直接使用。

## 2.17.9

- 环网柜柜名方向匹配改为严格使用用户勾选方向；支持一次多选多个方向。
- 上/下/左/右允许少量文字包围盒与柜框边缘重叠，避免视觉上贴边的柜名被漏识别。
- 每个选中方向先独立建立最近文字组，再在选中方向之间按真实边距选择最近方向。
- 单候选直接使用；最近组多候选时才使用绿色文字消歧。
- 未选方向永不参与兜底搜索。

# Changelog

## 2.18.201 — 2026-09-24

- 连接与环境页明确标注中央同步/发布同时包含 Oracle 数据库与文件服务器（SSH/SFTP）配置。
- `id_rules.json` 升级为 schema v7，每条规则写入 `valid_example` 合法示例；中央校验/发布同样保留该字段。

## 2.17.8

- 将“ID 规则模板”页面重命名为“ID 检查与修复”，同时保留可人工维护的 ID 规则模板。
- ID 修复改为强制模板模式：已配置类型只要前缀或总位数不符合模板，就自动分配同类型下一个合法 ID；重复 ID 同样按模板修复。
- 唯一旧 ID 被改写时，同步更新 `link`、`node_area`、`p_FatherObjId` 引用。
- ID 检查与修复页面明确标注“输出目录”，检查和修复均把报告写入该目录；“打开输出目录”打开的就是该路径。
- 基础处理的环网柜识别 CSV 继续输出到基础处理选择的输出目录。
- 基础处理、馈线图合并、图形边距调整、图框添加在生成输出 G 后统一执行已确认 ID 模板规范化，避免各模块自行生成不符合规则的 ID。
- 未配置模板的未知类型不擅自生成新 ID；若未知类型出现重复 ID，则要求先在“ID 检查与修复”中建立并确认规则。

## v2.17.7（环网柜柜名最近文字组识别）

- 仅调整环网柜柜名匹配逻辑，其他处理逻辑保持 v2.17.6 不变。
- 柜名不再强制要求绿色：指定方向内最近文字组只有一个候选时直接使用。
- 最近文字组存在多个候选时才优先绿色文字；无绿色时按距离与中心轴偏差选择。
- 仍限制最大近邻距离，远离环网柜的文字不会被识别为柜名。

## v2.17.6（环网柜识别规则收紧）

- 仅当环网柜 rect 内同时存在 `BusDis`、`CBreakerDis`、`ZhaiWaiJieDiDaoZha` 时才认定为环网柜。
- 柜名严格从用户选择方向上的绿色 `Text` 中匹配；橙色等其它文本不参与柜名候选。
- 柜型优先按柜内 `Y1/Y2/...` 与 `Q1/Q2/...` 名称计数；某类名称缺失时才回退到 `CBreakerDis devref/p_NameString`。
- `CabinetType` 始终只输出 `2L1T`、`3L1T`、`2L2T` 等；SMART 独立列输出 0/1，不再追加到柜型。
- 其它功能逻辑保持 v2.17.5 不变。

## v2.17.6（ID 格式锁定 + 环网柜名称/柜型识别）

- ID 规则恢复并锁定总位数：模板由 `tag + prefix + total_length` 组成，只管理 `id`，不处理 Alias。
- 已确认规则示例：ConnectLine=34/8位、Text=8/7位、CBreakerDis=117/9位、rect=2/7位。
- 扫描时前缀或位数任一不匹配均作为“ID 格式变化”提醒；真实样本中的 ConnectLine `140/141/142/143` 会被准确标记为异常。
- 重复 ID 分配继续采用“同类型最大合法完整 ID + 1”，且新值必须仍满足模板。
- 基础处理新增“环网柜名称与柜型识别”：柜名可选上/下/左/右多方向；L/T 基于柜内 CBreakerDis 的 devref/p_NameString 识别。
- SMART 可选参与柜型编码，开启后追加 `0S/1S`。
- 识别结果导出 `.rmu.csv`，同时在任务日志逐柜输出柜名、类型、L/T/SMART 计数和置信度。
- 使用 JED-NTH-ABH-08 实测识别 8 个环网柜、8 个柜名，全部高置信度；10689 识别为 `3L1T1S`。

## v2.17.4（ID 前缀规则简化）

- ID 模板只规定元素类型的起始前缀，不再限制“流水位数”或 ID 总长度。
- 已确认默认前缀：ConnectLine=34、FeedLine=35、Bus=30、BusDis=38、CBreaker=10、CBreakerDis=117、Disconnector=101、GroundDisconnector=111、Merge=20、Status=126、Text=8、ZhaiWaiJieDiDaoZha=188、pwbh=182、rect=2。
- 新 ID 按同类型当前最大完整 ID + 1，不补历史空号，不再使用跨类型全局流水。
- 扫描只有在元素 ID 不以模板前缀开头时才提示“格式变化”。

## v2.17.3（ID 全局流水规则校正）

- 按用户最新 G 文件确认 ID 结构：各元素类型使用固定前缀，尾部统一为 3 位全局共享流水号。
- ID 分配改为读取整张 G 所有受管类型的最大流水号 + 1。
- 更新默认 ID 规则，并对 v2.17.2 旧内置模板做安全迁移；人工修改规则不覆盖。
- 新增 Merge、CBreaker、Disconnector、GroundDisconnector 等规则。
- 短 ConnectLine ID（如 140~143）作为格式异常提醒，不自动视为合法模板。

## v2.17.2（ID 规则模板独立模块）

- 从基础处理移除 ID 检查/修复。
- 新增独立“ID 规则模板”页面。
- 持久化规则：XML Tag、ID 前缀、总位数、启用/确认状态与备注。
- 扫描 G 时识别新元素类型和已有类型的 ID 格式变化。
- 新候选规则必须由用户确认后加入；格式变化只告警，不自动覆盖模板。
- 重复 ID 修复只允许使用已确认模板；Alias 完全不参与。
- 内置首批规则由用户提供的 JED-CTL-AJWD-05.sln.pic.g 中具有足够真实样本的类型归纳。

# 更新记录

## v2.17.1（馈线名称移动到母线上方）

- 基础处理新增“将馈线名称移动到母线上方”复选框，状态保存到 `basic/move_feeder_titles_above_bus`。
- 新增 `BasicSettings.move_feeder_titles_above_bus`，默认关闭。
- 只识别有效水平 `<Bus>`；平行、相近且重叠的双母线自动分组。
- 识别完全基于 Bus/Text 几何和文字特征，不读取 `key_name`、`keyid`。
- 排除数字、单位、设备标签、SMART/SMR 和说明文字；候选不唯一时跳过。
- 只修改目标 Text 的 `x/y`，并增加文字冲突避让、幂等性及最小修改范围验证。
- 使用 ABS-36 和 ABH-22 两类真实文件回归验证。
- 自动化测试增加到 116 项。

## v2.16.1（连接点保守增量修复）

- 修复 v2.16.0 可能交换刀闸端口 0/1、把断路器两个连接合并到同一端口的问题。
- 冻结全部原有 `node_area/link` 三元组：不删除、不改号、不重新排序。
- 动态端口学习保留原 `own_port`，设备签名增加宽高，避免不同模板混用。
- 只补齐缺失的双向引用；多个候选或端口冲突时跳过。
- 水平对齐只处理验证通过的正半像素 X，并且只移动设备，不再修改连接线坐标。
- 增加逐设备验证和输出前原连接完整性硬校验。
- 使用 MODE-ZZZ 回归确认原端口修改 0 处、删除 0 处；重复执行保持幂等。
- 自动化测试增加到 112 项。

## v2.16.0（设备端口水平对齐）

- “修复连接点”复选框新增设备端口吸附：先对齐端口，再修复连接引用。
- 根据真实编辑器参考文件验证刀闸、负荷开关和断路器的内部端口偏移。
- 对半像素设备只沿 X 方向归一，不修改设备 Y。
- 同步调整直接连接的 ConnectLine/FeedLine 首尾端点，并重算 `d/x/y/w/h`。
- 清理已验证设备周边错误的 `node_area/link`，避免大外框把接地刀闸误连到整个线段交汇点。
- 未知单个 GIcon 不再根据外框盲目新增设备连接；重复设备可学习稳定端口模板。
- 保持复选框工作流和 `basic/repair_connection_points` 配置兼容。
- 使用 AJWD-06 问题/参考文件验证：对齐设备 50 个、调整连接线端点 66 个；设备 x 和连接线 d 与参考一致。
- 新增端口对齐、最小修改范围、处理器统计和幂等回归测试。

## v2.15.1（连接点修复复选框）

- 将基础处理页面的独立“修复连接点”按钮改为复选框。
- 勾选后随“开始基础处理”统一执行，不勾选时完全跳过。
- 新增 `BasicSettings.repair_connection_points`，默认 `False`。
- 复选框状态保存到 `basic/repair_connection_points`。
- 连接修复引擎继续只处理 `node_area` 和 `link`；坐标、ID、文字、颜色、图标、Merge 和其他业务属性保持不变。
- 连接修复放在颜色处理之后、重复 ID 检查/修复之前执行，便于删除或环网柜处理后的最终图元结构统一重建连接引用。
- 更新 UI、帮助、文档和回归测试。

## v2.15.0（连接点修复按钮）

- 基础处理页面新增独立“修复连接点”按钮。
- 连接点修复只处理 `node_area` 和 `link`，不会执行页面中其他已勾选规则。
- 根据 ConnectLine/FeedLine 端点与母线、设备、其他连接线的几何接触关系推断连接。
- 双向补齐或修正连接线、设备和母线的连接引用。
- 支持 Q1/Q2 断路器、接地刀闸、负荷开关、BusDis/Bus 和连接线交汇点。
- 保留坐标、ID、文字、颜色、图标、Merge、画布及其他业务属性。
- 使用用户提供的问题/正常 G 文件完成真实回归；问题文件新增 24 处连接引用，14 个图元恢复连接点。
- 新增幂等性、仅连接属性变化、处理器输出和 UI 按钮回归测试。

## v2.14.0（channel_status 状态点定位）

- 删除“统一带 BusDis 的环网柜垂直间距”界面、配置和整体 Y 平移处理。
- 新增“移动环网柜红色状态点（channel_status）”。
- 仅识别带 BusDis 环网柜内 `devref` 包含 `channel_status.zt.icn.g:channel_status` 的 `<Status>`。
- 支持框内四角和四边中点共 8 个位置，默认左下角。
- 新增可配置框内边距，默认 5 像素。
- 只移动 Status 本身，环网柜、母线、设备、标题、连接线、Merge 和画布均不移动。
- 增加真实 MAK 文件及八锚点回归测试。

## v2.13.2（BusDis 环网柜垂直间距）

- 基于 v2.13.1 更新。
- 将“统一带 BusDis 的环网柜高度”改为“统一带 BusDis 的环网柜垂直间距”。
- 用户输入值表示相邻环网柜顶部 Y 坐标之差，默认 300 像素。
- 每个竖直馈线列以最上方环网柜为基准，后续环网柜依次排列。
- 环网柜外框、柜内设备、柜外标题、状态图标及周边元素整体沿 Y 方向移动。
- 柜间 ConnectLine/FeedLine 根据两端柜体新位置自动平移或伸缩。
- 环网柜高度、宽度和所有 X 坐标保持不变。
- 增加真实 ADF-16 文件及多列环网柜回归测试。
- 互斥单选框样式和其他业务逻辑保持 v2.13.1 不变。

## v2.13.1（单选圆点视觉优化）

- 基于 v2.13.0，仅优化互斥单选框的选中样式。
- 选中后圆形指示器整体填充电网绿色，中心保留一个小白点。
- ID 操作、环网柜组合操作及所有业务处理逻辑保持不变。

# CHANGELOG

## v2.17.1（图元版本升级适配）

- 基于 v2.17.0 新增独立图元升级模块。
- 新旧图元 G 按同名文件强制配对，可添加、移除、清空和检查。
- 自动解析 w/h、AlignCenter、pin，并按 pin id 解决新旧端口顺序变化。
- 按 devref、rotate、node_area 更新主 G 图元位置/尺寸与对应连接线端点。
- 任一侧缺失、主体不一致或端口数量变化时禁止执行。


## v2.13.0（基于 v2.12.0 重建）

- 统一带 BusDis 的环网柜高度支持用户输入明确目标值，默认 220。
- 目标高度控件使用防滚轮、防方向键的 IntegerInput。
- 环网柜增强操作改为竖列布局，仍可独立多选。
- ID 操作及环网柜组合动作保持互斥，并改为圆形 QRadioButton。
- 其余功能、处理顺序和配置语义保持 v2.12.0 不变。
- 版本升级到 2.13.0，并覆盖此前生成的 v2.13.0。

## v2.12.0

- 将“SMART 字样改色 + 全部环网柜外框改色”合并为“修改含 SMART 的环网柜外框颜色”。
- 只修改框内存在 `Text[ts=SMART]` 的对应 `rect` 的 `lc/lcc`。
- SMART 字体、框外 SMART 以及不含 SMART 的其他环网柜均保持不变。
- 删除一键处理导航、页面、处理器、模型、临时缓存服务和相关测试。
- 程序默认进入基础处理，F1 帮助索引同步调整。
- 版本升级到 2.12.0。

## v2.11.0

- 基于 v2.10.0 增强“环网柜图元处理”。
- 仅识别 rect 框内 ts=SMART 的 Text 并支持指定颜色；框外 SMART 不处理。
- 支持独立指定环网柜 rect 边框颜色。
- 支持统一带 BusDis 的环网柜高度，只调整 Y 轴相关属性，不修改任何 X 坐标。
- 支持删除带 Bus 的环网柜外框及对应 Merge，并将距离母线最近的业务标题移到母线上方居中。
- 环网柜增强选项可多选，并统一通过“开始基础处理”执行。
- 延续电网绿色工作台主题并统一增强选项视觉样式。

# 更新记录

## v2.11.0

- 基于 v2.9.1 更新。
- 根据用户提供的 `aaaaddd` / `bbbvvv` 图层顺序样本确认：Layer 中越靠后的图元在编辑器中显示层级越高。
- 取消环网柜组合时，除删除对应 Merge 外，还会把被释放的 `<rect>` 移到其框内设备之前，使环网柜外框位于断路器、文字和连接线下层。
- 外框下移只调整 Layer 直属元素顺序，不修改坐标、ID、引用、颜色或业务属性。
- 根据用户提供的通用组合/未组合样本重新确认：新编辑器 Merge 的 `mergesize` 等于实际成员数量。
- 新建环网柜 Merge 改为写入成员数量，不再固定写入“成员数 + 1”。
- Merge 读取兼容“成员数量”和“Merge 头 + 成员总数”两种历史格式。
- Merge 成员识别改为以 `mergex/mergey/w/h` 几何范围为主，`mergesize` 仅用于兼容和告警。
- 取消使用历史 Merge 连续区间重叠作为阻断错误，解决大型馈线文件中的误报。
- 环网柜 Merge 改为通过 Merge 与 `<rect>` 的几何对应关系识别，取消组合更稳定。
- 无 Merge 几何时仅在第一个连续成员为 `<rect>` 时采用顺序兜底，降低误删业务 Merge 的风险。
- 使用 AJWD-22 实际文件验证：14 个历史环网柜 Merge 可全部取消，15 个 rect 可全部重新组合。
- 新增通用 Merge 样本、混合 mergesize、错误 mergesize 几何兜底等回归测试。
- UI 更新为电网图形工作台主题：深海军蓝侧栏、电网绿主操作、青绿提示和统一卡片控件。
- 窗口标题与侧栏副标题更新为电网 XML 图形处理工作台。
- 自动测试 86 项通过。

## v2.9.1

- 修复 Merge `mergesize` 语义：该值包含 Merge 头元素自身，实际成员数为 `mergesize - 1`。
- 修复连续环网柜 Merge 被误报为成员区间重叠的问题。
- 修复取消环网柜组合时部分 Merge 未被识别、删除后仍报含 `<rect>` Merge 的问题。
- 新建环网柜组合时，`mergesize` 改为“成员数量 + 1”，与图形编辑器格式一致。
- 增加多 Merge 连续排列及真实 AJWD-22 文件回归测试。

# Changelog

## 2.18.201 — 2026-09-24

- 连接与环境页明确标注中央同步/发布同时包含 Oracle 数据库与文件服务器（SSH/SFTP）配置。
- `id_rules.json` 升级为 schema v7，每条规则写入 `valid_example` 合法示例；中央校验/发布同样保留该字段。

## v2.9.0

- 基于 v2.8.0 更新，保留严格四边距、环网柜框内组合、重复 ID 处理及既有业务功能。
- 基础处理的环网柜模块改为互斥选择：不处理、组合所有、取消所有。
- 新增取消环网柜组合：只删除成员中含 `<rect>` 的 Merge 头元素，成员内容与顺序保持不变。
- 组合和取消组合均保留不含 `<rect>` 的其他业务 Merge。
- 新建 Merge 几何与图形编辑器手工组合一致：相对 rect 左、上各外扩 1，右、下边界保持一致。
- 新建 Merge ID 优先使用当前文件的 `20 + 固定宽度顺序号` 格式，并沿用最大图元顺序号。
- 使用用户提供的 `no-combine`、`combine`、`cancel-combine` 文件完成组合、取消组合回归验证。
- 基础处理新增 FeedLine、ConnectLine、BusDis、Bus 静态线色修改；同步写入 `lc` 和 `lcc`。
- 动态颜色图元会记录日志告警，但不修改动态颜色开关。
- 输入输出路径相同或目标同名文件已存在时，新增时间戳、安全覆盖、取消三种处理方式。
- 安全覆盖通过临时文件重解析后原子替换，避免处理中断损坏源文件。
- ID、环网柜、图框模板和颜色选项统一使用醒目的卡片式复选框样式。
- 检查、修复、组合、取消组合和颜色结果全部写入任务日志，不生成 CSV。
- 自动测试 78 项通过。

## v2.8.0

- 基于 v2.7.0 更新，保留环网柜组合、ID 选择模式和既有业务功能。
- 修复 `ConnectLine w="5000"` 等线状图元内部尺寸参数导致画布宽度异常放大的问题。
- `ConnectLine`、`Line`、`Bus`、`BusDis`、`FeedLine` 等线状图元优先使用 `d` 路径或端点计算真实可见边界。
- 图形边距调整改为使用整数像素外包边界，严格保证用户设置的左、上、右、下边距。
- 临时文件写出后重新解析并再次验证四边距，验证失败不生成最终文件。
- 基础处理 ID 操作由单选圆点改为互斥复选框。
- 图框模板模式由单选圆点改为互斥复选框。
- 互斥选择项增加 20px 勾选框、2px 蓝色选中边框和浅蓝背景，选中状态更醒目。
- 使用真实 `test-test-test.sln.pic.g` 验证：画布由错误的 7784×3111 修正为 2865×3111，四边距均为 500。
- 自动测试 71 项通过。

## v2.7.0

- 严格基于 v2.6.0 更新，其他模块业务逻辑不变。
- 基础处理的 ID 校验与修复改为单选模式：不处理、只检查、检查并修复。
- ID 选项与通用规则统一通过“开始基础处理”执行。
- 取消 ID 检查/修复 CSV 报告，全部结果写入当前任务日志。
- 基础处理新增“组合文件中的所有环网柜”选项。
- 直属 `<rect>` 作为环网柜边框，每个 rect 重建一个 `<Merge>`。
- 只组合完整位于 rect 框内的直属图元，框外连接线、状态图标和标题文字均不组合。
- 已有 Merge 同样按严格框内规则重建，并尽量复用原 Merge ID 与样式。
- 支持单文件和目录第一层全部 G 文件。
- 新增真实组合样本、严格边界、目录批量和 UI 选择模式测试；自动测试 68 项通过。

## v2.6.0

- 基于 v2.5.0 rebased（v2.4.0 业务基线）继续升级。
- “G 文件合并”改名为“馈线图合并”。
- “添加图框”改名为“图框添加”。
- 馈线图合并留空输出名时生成 `MERGED-yyyyMMdd_HHmmss.sln.pic.g`。
- 图形边距调整默认生成 `-ADJUSTED-时间戳` 文件名。
- 图框添加默认生成 `-WITH-FRAME-时间戳` 文件名。
- 同一批目录任务共享一个时间戳。
- 基础处理新增“ID 校验与修复”，支持单文件和目录。
- 重复 ID 的新编号优先参考当前 G 文件同类元素的前缀与固定总位数。
- ID 检查和修复生成 CSV 报告；修复文件使用 `-ID-FIXED-时间戳`。
- 模板图元 ID 优先参考目标文件相同标签格式。
- 保留内置图框右边框错位修复和闭合校验。
- 所有功能区标题保持卡片内统一样式。

## v2.5.0

- 本版本严格以 v2.4.0 为代码基线，不包含后续试验版本的 ID 配置页面和全流程 ID 扫描。
- 合并产生新 ID 时，优先从当前单个 G 文件的同类 XML 元素中推断主流“类型前缀 + 固定宽度顺序号”格式。
- 新生成的元素 ID 必须保持同类元素的主流前缀和固定总位数；无法可靠推断时才沿用 v2.4.0 的原 ID 递增逻辑。
- 保留 v2.4.0 的 ID 命名空间、虚拟拓扑 ID、引用重映射和最终唯一性校验机制。
- 修复内置模板在特定窄画布下右边框被签字栏逻辑二次移动的问题。
- 内置图框在原始模板坐标中先固定识别组件，四条外框线最后单独设置，并增加闭合和越界校验。
- 输出内置图框增加 `gfs_frame_role` 角色标记，明确区分四边框、标题区和签字栏。
- 删除“添加图框”页面中多余的“内置模板内容配置 / 载入 JSON / 保存 JSON”。
- 所有功能区标题统一显示在白色卡片内部，不再压在边框线上。
- 新增同类 ID 格式、短 ID 重复修复、固定总位数和 AJWD-14 右边框回归测试；自动测试 54 项通过。

## v2.4.0

- G 文件合并加载目录时新增“加载中”进度窗口，显示当前检查文件和总进度，并支持取消。
- 新增“查询并导入”窗口，可按文件名关键字模糊查询；多个关键字采用同时包含匹配。
- 查询结果支持选择、全选当前结果、取消选择和确认导入。
- 已在主列表中的文件在查询窗口中置灰，避免重复导入。
- 非内置图框和检查失败文件在查询窗口中不可勾选，不能参与合并。
- 新增“导入全部可用”，按自然顺序导入所有通过检查的文件。
- 内置图框不再阻止合并：合并前从内存副本自动移除图框组件，再使用剩余主体图形参与 Bus 对齐和排列。
- 内置图框移除后清理 `link`、`node_area`、`p_FatherObjId` 中指向已移除图框 ID 的引用，并清除图框身份标记。
- 旧版内置图框识别改为纯几何结构指纹，不读取标题、Draw、Approve、Issue、姓名或日期文字内容。
- 客户图框、未知图框、大矩形外框和损坏图框明确标记为不可合并；合并执行前再次检查，防止绕过 UI。
- 使用用户提供的旧版内置图框文件完成实际合并验证。
- 自动测试增加到 48 项。

## v2.3.0

- 修复图形边距调整中“主体图形未找到”的误判。
- 移除从外框开始的几何连通扩散识别，避免馈线连接到图框时把全部主体元素误归为图框。
- 新增内置图框身份标记：根节点和图框直属元素保存 `gfs_frame_type`、`gfs_frame_template`、`gfs_frame_component`。
- 对旧版未带标记的内置模板增加严格结构指纹兼容，可识别用户提供的旧版内置图框文件。
- 仅对确认的 G File Studio 内置图框自动调整：主体排除图框后计算四边距，最后动态拉伸外框并锚定移动标题区和签字栏。
- 客户图框或来源不明的图框不再尝试自动调整，直接提示先删除图框。
- 错误弹窗现在直接显示用户可读原因，完整 Traceback 继续保留在日志中。
- 新增内置图框标记、旧版指纹、客户图框拒绝和一键流程回归测试。

## v2.2.0

- G 文件合并列表新增“删除所选”按钮。
- 表格支持 Ctrl/Shift 多选，可一次排除多个 G 文件。
- 删除仅影响本次合并列表，不删除磁盘上的源文件。
- 最终只合并列表中保留的文件，并严格使用当前显示顺序。
- “扫描 / 检查”保留排除项和手动顺序，新发现文件追加到末尾。
- “恢复全部并排序”重新加入已排除文件并恢复自然排序。
- 独立合并页面和一键处理合并阶段共用相同筛选能力。
- 合并引擎新增受控子集模式，并继续校验重复项、缺失文件和后缀。
- 新增子集合并与 UI 功能覆盖测试。

## v2.1.0

- 使用独立 `user_settings.ini` 保存完整路径，不再只记住浏览目录。
- 支持手动输入、粘贴、浏览选择、运行前和关闭时保存路径。
- 启动时恢复单文件/目录模式、完整输入路径、输出目录和客户模板路径。
- 失效路径会提示用户并从配置中清除。
- 新增“图形边距调整”独立页面，支持单文件和目录批量处理。
- 主体图形四边距默认均为 500。
- 已有外框采用“保留并同步调整”策略。
- 外框不参与主体边界计算，保持原四边距并同步拉伸、移动附属组件。
- 外框文字、签字信息、日期、字体、颜色、线宽和表格内容保持不变。
- 一键流程新增图形边距调整阶段。
- 一键流程检测到已有外框后自动跳过重复添加图框。
- 测试增加路径持久化、失效路径和图形边距/外框适配覆盖。

## v2.0.0

- 增加绿色程序图标。
- 初步增加最近目录记录。

## 2.17.15
- 将“ID 检查与修复”提升到左侧导航首位，作为全局 ID 规则中心，基础处理及其他业务模块位于其后。
- ID 规则模板表格新增“启用”复选框列，勾选状态即时持久化；停用规则立即停止参与后续强制规范。
- ID 规则模板顶部新增“启用全局 ID 模板强制约束”状态提示，明确基础处理、馈线合并、图形边距调整、图框添加统一使用该模板。
- 保留并强化“扫描当前 G → 检查模板覆盖 → 自动识别候选前缀/总位数 → 用户逐条确认添加”的工作流。
- 删除规则后立即写入 deleted_tags，刷新和重启均不自动恢复；再次扫描对应类型时会作为未覆盖类型重新提示。
- 已有已配置类型的格式异常/重复 ID 继续强制按模板修复；所有后续处理输出继续统一执行已确认模板规范化。

## 2.17.17
- ID 模板扫描结果改为固定尺寸可滚动对话框，避免扫描内容过长导致弹窗超出屏幕。
- 工作台展示名称更新为“NARI 国际业务 XML 图形处理工具”。

## 2.17.28
- 新增独立“异常小尺寸图元检测”模块，置于“ID 检查与修复”之前。
- 扫描 ConnectLine / FeedLine / Bus / BusDis，默认 w<10 且 h<10 时报告异常；Bus 不区分方向。
- 输出 CSV + HTML，包含文件、元素类型、XML ID、位置、w/h、keyid。
- 删除必须由用户在扫描结果中选择；存在 keyid 时明确提示文件、元素、ID、keyid 并二次确认。
- 馈线合并的主母线处理移除 w<10 特殊过滤，异常小尺寸 Bus 统一由新模块处理。

## v2.17.36
- RMU 信息汇总新增“现有 RMU 台账对比（可选）”。
- 支持 3 种台账输入：Excel/CSV、直接粘贴表格、只粘贴 RMU 名称。
- RMU 名称为匹配键；RMU 类型、是否智能为可选字段。
- SMART / SMR 在对比层统一视为智能环网柜，同时保留 IntelligentSource。
- 输出覆盖式 `rmu-ledger-comparison.csv/html`，统计完全一致、柜型不一致、智能属性不一致、图形缺失、台账缺失及重复项。
- 原有 RMU 柜名方向匹配、单候选/绿色优先、柜型 Y/Q 识别及图元处理算法未修改。

## v2.17.54
- 馈线合并的“主网母线处理”改为人工母线分组，不再依据 Bus.keyid 决定哪些馈线共母线。
- 新增“设置母线分组”弹窗：按当前馈线顺序选择连续的两条或多条馈线创建母线组；未分组馈线保持独立。
- 单母线/双母线识别规则保留；双母线分别按上母线、下母线独立合并，禁止互相折叠。
- 同组母线在合并前自动按多数/中位 Y 对齐，少数母线同步拉伸直接连接线端点。
- 保留 Bus 的原有属性；keyid 仅作为普通属性保留，不参与分组决策。

# Consolidated detailed release notes

The following detailed notes were consolidated from the former per-version `UPDATE_NOTES_v*.md` files. New releases are recorded directly in this single changelog.

<!-- consolidated from UPDATE_NOTES_v2.18.163.md -->
# G File Studio v2.18.163

Base: GitHub `master` v2.18.162, commit `f79ab1ee61ec4e7906cdaec530753b283c597fd4`.

Changes in v2.18.163:

- Fix Windows packaging flow where `Compress-Archive` could fail on a locked `dist\\GFileStudio\\_internal\\base_library.zip` while the script still printed a share-package success message.
- Detect a running `GFileStudio.exe` before build/package and fail with a clear instruction instead of creating a broken/incomplete ZIP.
- Wait for files under `dist\\GFileStudio` to become exclusively readable before starting ZIP creation.
- Use `Compress-Archive -ErrorAction Stop`, remove any partial ZIP on failure, and verify the resulting ZIP can be opened and contains entries before reporting success.
- Add `-PackageOnly` mode. When the EXE was already built successfully and only ZIP creation failed, close GFileStudio and run `./build_exe.ps1 -PackageOnly` to recreate the package without rebuilding the EXE.
- Version bumped from 2.18.162 to 2.18.163.

No GitHub branch/ref was modified by this local update package.

---

<!-- consolidated from UPDATE_NOTES_v2.18.164.md -->
# G File Studio v2.18.164

## Jeddah feeder batch: NORMAL RMU enforcement

- A recognized RMU whose cabinet contains no `SMART` Text is treated as NORMAL in the final Jeddah visual pass.
- NORMAL RMU frame line color is forced to white (`lc=255,255,255`, `lcc=#FFFFFF`).
- SMART RMU frame line color remains red (`lc=255,0,0`, `lcc=#FF0000`).
- Jeddah SMART/NORMAL profile correction continues to normalize Y/LBS and Q/Circuit Breaker symbols.
- NORMAL target selection can learn the unique dominant NORMAL devref from peer NORMAL RMUs in the same drawing, but only when that devref exists in the authoritative server standard catalog. A tie keeps the explicit GLOBAL role binding.
- Ground-disconnector replacement behavior is unchanged: Jeddah batch does not replace `ZhaiWaiJieDiDaoZha`.
- No GitHub push is included in this delivery.

---

<!-- consolidated from UPDATE_NOTES_v2.18.165.md -->
# G File Studio v2.18.165

本版本收紧“吉达馈线批处理”的 RMU 图元标准化规则。

## 最终规则

1. 先识别有效 RMU。
2. 设备类别以原图元 `devref` / 图元文件名为准：
   - 名称含 `Circuit_Breaker` -> Circuit Breaker。
   - 名称含 `Load_Breaker_Switch` -> Load Breaker Switch。
   - 其他图元不参与本次替换。
3. Y/Q (`p_NameString` / `key_name`) 不再覆盖上述原图元类别。
4. 柜内存在 `SMART` Text：
   - Circuit Breaker -> 分类标记 `CIRCUIT_BREAKER_SMART` 对应图元。
   - Load Breaker Switch -> 分类标记 `LOAD_BREAKER_SWITCH_SMART` 对应图元。
   - RMU 外框 -> 红色。
5. 柜内不存在 `SMART` Text：
   - Circuit Breaker -> 分类标记 `CIRCUIT_BREAKER_NO_SMART` 对应图元。
   - Load Breaker Switch -> 分类标记 `LOAD_BREAKER_SWITCH_NO_SMART` 对应图元。
   - RMU 外框 -> 白色。
6. 四个目标只读取“服务器图元同步管理”中本地保存的分类标记，不再从同图其他 RMU 学习/猜测目标版本。
7. 如果同一必需分类标记对应多个图元、缺失、没有 devref，或目标不在当前已应用服务器标准中，UI 会阻止执行并提示用户修正。
8. `ZhaiWaiJieDiDaoZha` 接地刀闸继续不替换。

GitHub 默认不推送；等待用户明确要求后再推送 master。

---

<!-- consolidated from UPDATE_NOTES_v2.18.166.md -->
# G File Studio v2.18.166

## 新增：普通模式 / 管理员模式

- 应用每次启动默认普通模式。
- 普通模式：可做连接设置、同步/查看服务器图元、打开本地缓存、导出分类标记；不能编辑、载入或保存分类标记。
- 首次部署：无需先初始化管理员即可配置环境和完成首次同步；需要维护分类时点击“初始化管理员”，两次输入密码完成初始化。
- 管理员模式：可编辑、载入、保存分类标记，并可修改管理员密码。
- 管理员密码使用 PBKDF2-SHA256 + 32 字节随机盐，仅保存校验值；不保存明文。
- 退出管理员模式或重启程序后恢复普通模式。

> 当前访问控制针对本机 GFileStudio 管理界面。未来中央分类库落到 SSH 服务器后，可在此基础上进一步做中央管理员身份/发布权限。

---

<!-- consolidated from UPDATE_NOTES_v2.18.167.md -->
# GFileStudio v2.18.167

## Central administrator classification configuration

- Added one SSH/SFTP central classification source of truth:
  `/home/up8000/nari-international/gfilestudio/classification_registry/admin.json`
- No numbered `V000001` / `V000002` history files are created. `admin.json` is the only persistent authoritative central classification file.
- Ordinary mode may read/synchronize `admin.json` into the local classification cache.
- Administrator mode may publish the current locally saved classifications to `admin.json`.
- Publishing writes a temporary file, verifies it, then replaces `admin.json`; the temporary file is removed and is not a second persistent version.
- First deployment is supported: if `admin.json` does not exist, synchronization reports that an administrator must publish it once.
- Central synchronization is authoritative: classifications removed from `admin.json` are removed from the local classification layer as well.
- The server `element` symbol directory remains strictly read-only; the only remote write path introduced by this feature is the dedicated `classification_registry/admin.json` file.
- Admin mode/session/password behavior from v2.18.166 is unchanged.

---

<!-- consolidated from UPDATE_NOTES_v2.18.168.md -->
# G File Studio v2.18.168

- Central SSH classification filename changed from `admin.json` to `symbol_classification.json`.
- The only authoritative server file is:
  `/home/up8000/nari-international/gfilestudio/classification_registry/symbol_classification.json`
- UI actions now clearly separate local and server destinations.
- `保存到本地` writes the current classification markers to the local `classification_markers.json` cache only.
- `上传到服务器` is administrator-only, saves locally first, then uploads the one authoritative server JSON.
- `从服务器同步` is available in ordinary/admin mode and warns that the server configuration will overwrite the local classification layer.
- Local JSON export/import remain explicit migration tools and do not implicitly upload to the server.
- The server `element` directory remains read-only.

---

<!-- consolidated from UPDATE_NOTES_v2.18.169.md -->
# G File Studio v2.18.169

## Server-wide single administrator

- Added a server-side administrator lease at `classification_registry/admin_lock.json`.
- Only one workstation can own administrator mode at a time.
- The lease records machine name, the workstation IP used for the SSH connection, SSH user, acquire time, heartbeat time and expiry time.
- Administrator lease heartbeat: every 45 seconds; lease timeout: 180 seconds.
- Explicit **Release administrator** removes the lock. A crash/network loss falls back to lease expiry so the lock cannot remain forever.
- `symbol_classification.json` upload is accepted only while the publishing workstation still owns the matching administrator lease.
- Published classification metadata records the publishing machine name and IP.

## Ordinary workstation synchronization

- Every process still starts in ordinary mode.
- Ordinary workstations automatically attempt to sync `symbol_classification.json` on page startup and again after server-symbol synchronization.
- Ordinary mode is read/sync only; classification maintenance buttons are hidden until this workstation owns administrator mode.

## UI simplification

- Removed the repeated multi-line explanations from the main server-symbol page.
- Main page now emphasizes only current mode, current administrator machine/IP, symbol sync, classification sync and administrator actions.
- Detailed behavior remains in Page Help.

---

<!-- consolidated from UPDATE_NOTES_v2.18.170.md -->
# GFileStudio v2.18.170

## Central configuration model

- Replaced the temporary `classification_registry/admin_lock.json` model with the same server-side configuration pattern used by Distribution Model Manager.
- Central directory is now:
  `/home/up8000/nari-international/gfilestudio/config/`
- Central files:
  - `instance.json` — current Admin machine ID/name/IP and global `config_version`
  - `symbol_classification.json` — authoritative published symbol classification
  - `database.json` — authoritative published Oracle connection configuration
  - `file_server.json` — authoritative published SSH/file-server configuration
- Only the machine recorded as active Admin in `instance.json` may publish central files.
- Admin ownership is persistent until explicitly released; closing GFileStudio does not silently release it.

## Local configuration remains independent

- Every workstation may edit and save its own local symbol classifications, database configuration and file-server configuration.
- Central configuration is never forced over local settings at application startup.
- “从服务器同步 / 从中央同步” explicitly replaces the corresponding local settings only after user confirmation.
- Local symbol classification editing/import/export remains available in ordinary mode; Admin only controls central publishing.

## UI

- Simplified the server-symbol page and moved detailed explanations into Page Help.
- Added concise central configuration controls to the “连接与环境” page:
  - `从中央同步`
  - `发布到中央`

## Validation

- Added v2.18.170 central configuration regression coverage.
- Relevant connection/admin/classification/Jeddah regression set: 46 passed.

---

<!-- consolidated from UPDATE_NOTES_v2.18.171.md -->
# GFileStudio v2.18.171

## Global configuration-access entry

- Move the central configuration administrator entry from the Server Symbol Sync page to the persistent left sidebar.
- The sidebar button shows Standard / Admin / Admin In Use status.
- Clicking the global button shows the current administrator machine/IP and allows initialize, enter, change password, or release according to the current state.
- Remove the visible administrator control row from Server Symbol Sync Management; the existing SSH/instance.json administrator workflow remains unchanged.
- Keep administrator scope limited to publishing central configuration. Every workstation may still maintain local classification/database/file-server settings.
- Update Connections & Environment guidance to point users to the left-side Configuration Access entry.

---

<!-- consolidated from UPDATE_NOTES_v2.18.172.md -->
# GFileStudio v2.18.172

- Removed the obsolete multi-environment Profile selector from Connection & Environment.
- The page now directly manages one workstation shared SSH/SFTP + Oracle configuration.
- Central config sync/publish remains unchanged.
- Business modules now label the source as “共享连接配置” instead of “当前环境”.
- Existing legacy connection-environment service is retained only for backward compatibility and is no longer exposed in the UI.

---

<!-- consolidated from UPDATE_NOTES_v2.18.173.md -->
# GFileStudio v2.18.173 Update Notes

## Central configuration administrator

- No periodic administrator heartbeat or polling is used.
- `config/instance.json` stores the central administrator password only as PBKDF2-SHA256 metadata (`salt`, `password_hash`, `iterations`); plaintext is never written.
- A workstation that knows the central password can take over the central Admin role.
- If the password is forgotten, `强制设置管理员密码` uses the already configured SSH/SFTP write credentials as recovery authority, sets a new central password, and makes the current workstation Admin.
- Central publish operations re-read/validate `instance.json`; an old Admin loses write authority after another workstation takes over.
- Local workstation classification editing/saving/import/export stays available without Admin.

## AR / LBS / SEC Poke

- The Poke module reads only exact saved classification markers `AR`, `LBS`, and `SEC` to locate target graphic elements.
- Only those classified device instances participate; the rest of the drawing is not treated as a target-device search space.
- Device-name Text candidates must be in the same Layer and within 300 graphic units of the target device.
- Each target device gets at most one name. Each concrete Text ID/instance can be assigned to at most one device.
- Two Text elements with the same `ts` content remain separate candidates when their XML Text IDs differ, so identical displayed names can be assigned to different device instances.
- The detail jump reuses the RMU database lookup and target naming rule: `{area}-{substation}-{feeder}-{device}.com.pic.g`.
- RMU Pokes, station Pokes and AR/LBS/SEC device Pokes are protected from cross-conversion during existing-Poke repair.

## Version

- Package version: `2.18.173`.
- GitHub is not changed by this local delivery.

---

<!-- consolidated from UPDATE_NOTES_v2.18.174.md -->
# GFileStudio v2.18.174

## Central configuration startup rule

- Startup uses local configuration only.
- Opening the server-symbol page does not read central configuration.
- No automatic `instance.json` / `symbol_classification.json` / `database.json` / `file_server.json` fetch is allowed.
- Remote central configuration is accessed only after an explicit user action.
- Existing local settings remain untouched until the user chooses a central synchronization action.

---

<!-- consolidated from UPDATE_NOTES_v2.18.175.md -->
# GFileStudio v2.18.175

- Corrected station-jump Poke recognition.
- Station-jump candidates are identified only from station Text format + explicit colored background.
- AR/LBS/SEC/FUSE/Transformer_OH classification markers no longer exclude station-jump candidates.
- Adjacent parenthesized RMU locateLabel distance increased from 200 to 300 G units.
- AR/LBS/SEC device Poke classification logic remains unchanged.
- Poke report no longer shows the obsolete station-classification-exclusion column/card.

---

<!-- consolidated from UPDATE_NOTES_v2.18.176.md -->
# GFileStudio v2.18.176

- Startup is now strictly local and lightweight: no central configuration, SSH/SFTP, Oracle, administrator status, or remote symbol-library request is made automatically.
- MainWindow no longer imports or constructs all business pages at startup. Pages are imported and created only when the operator clicks them.
- Startup no longer scans/cleans run-history directories; cleanup remains on-demand when run-history functionality is used.
- The server-symbol page defers rebuilding its local cached catalog/table until that page is actually opened.
- Removed the automatic daily server-symbol refresh scheduling. Server symbol synchronization is manual only.
- Oracle and SSH connectivity are tested only by explicit user actions or when a business operation actually requires them.

---

<!-- consolidated from UPDATE_NOTES_v2.18.177.md -->
# GFileStudio v2.18.177

- Enforces local-first configuration behavior.
- Startup, repeat launch, page opening, and missing local configuration never trigger central configuration downloads.
- Local symbol classifications, file-server settings, and Oracle settings remain persistent local caches.
- User edits save locally only.
- Manual central sync explicitly overwrites the corresponding local cache and records its local provenance.
- Central publish remains an explicit administrator action.

## 2.18.203 - 2026-09-24
- 修复服务器图元同步管理首次打开/恢复本地缓存时短暂闪现空白框的问题：懒加载页保留已绘制占位内容直到真实页面构造完成，再原子替换。
- 本地图元缓存恢复期间不再先显示空 QTableWidget；使用无边框状态文本，200 条常规缓存隐藏完成填充和列宽计算后一次显示。
- 自动本地缓存恢复路径明确不创建 QMessageBox / QProgressDialog，也不会显示服务器同步进度控件；仍然只读 AppData，不访问 SSH/Oracle/中央仓库。
- 200 条级别缓存一次隐藏批量渲染；超大清单继续分批，避免 GUI 长时间阻塞。
