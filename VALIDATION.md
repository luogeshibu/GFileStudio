# G File Studio 验证记录

> 发布包统一验证文档。以后每个版本的验证结果都追加到本文件中，不再新增 `VALIDATION_v*.md`。最新版本位于最上方。

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
