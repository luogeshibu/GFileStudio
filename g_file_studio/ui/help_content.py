from __future__ import annotations

APP_HELP: dict[str, tuple[str, str]] = {
    "jeddah_batch": (
        "吉达馈线批处理说明",
        """
<h3>用途</h3>
<p>仅用于吉达现场的批量单馈线标准化。每张输入 G 文件独立处理并独立输出，不执行馈线合并。</p>
<h3>固定流程</h3>
<ol>
<li>首先复用“基础处理 → 图形组合处理”的“彻底取消图形组合”能力：删除全部 &lt;Merge&gt;，并将识别到的 RMU 外框置于设备底层；</li>
<li>删除异常小尺寸 ConnectLine / FeedLine / Bus / BusDis；</li>
<li>将已识别的 RMU 柜名文字统一改为白色、字号固定为 50，并移动到所属环网柜上边框正中间上方，文字下边缘与上边框保持 10 个图形单位净间距；</li>
<li>将 SMART 与 SMR 环网柜外框统一改为红色；</li>
<li>SMART 图元检查覆盖整个 RMU 框内：只要 SMART Text 中心位于柜框内，就校正 Y 类 Load_Breaker_Switch 与 Q 类 Circuit_Breaker 的 SMART devref；Q 图元兼容 Circuit_Breaker_NO-SMART 和 Circuit_Breaker_NON-SMART 两种源引用。</li>
<li>对精确 SMR 标识做吉达专用智能处理：若对应柜内已经存在 SMART，只删除外部 SMR 并将外框保持红色；若柜内没有 SMART，则将 SMR 转为顶部居中的 SMART（字号固定 20）；之后再次执行 SMART 图元检查。</li>
<li>删除带 Bus 的环网柜矩形框，并将对应标题移动到母线上方；</li>
<li>将馈线名称移动到母线上方；</li>
<li>将所有 &lt;FeedLine&gt; 馈线线型统一设为实线（ls=1），不修改颜色、线宽、坐标、ID 或引用；</li>
<li>删除带 BusDis 的 RMU 所属 channel_status 红色 Status 点；归属判断直接复用现有“移动环网柜红色状态点”规则，只把最终动作从移动改为删除；</li>
<li>删除精确匹配的 H.T 文字标识（忽略大小写和首尾空白，不做子串删除）；</li>
<li>对现有 RMU 识别引擎识别出的全部配网环网柜检查 SMART 标识；同一柜内有多个 SMART 时保留 XML 中原有第一个，删除后续重复项，不移动或重写保留项；</li>
<li>仅当两个独立 Text 分别精确为 2000.00 与 UPDATED_MEASURMENT，且位于同一视觉行并水平相邻（间距不超过 10）时才成对删除；距离不相邻时不处理；</li>
<li>使用全局已确认 ID 模板执行 ID 检查与修复；</li>
<li>调用现有图形边距调整能力，默认将主体图形左、上、右、下边距设为 500；</li>
<li>最后调用现有图框添加能力，为每张处理后的单馈线图添加所选图框模板。</li>
</ol>
<h3>设计原则</h3>
<p>本页面仅编排已有处理能力，不替换或改写现有异常元素、RMU、馈线名称或 ID 模块的算法。吉达专用参数使用独立配置，不覆盖其他模块设置。</p>
""",
    ),
    "site_profile": (
        "图元标准检查帮助",
        """
<h3>用途</h3>
<p>这是独立的通用图元标准检查与安全纠正模块，不依赖吉达或其他现场批处理。标准来源与业务 G 完全分离：用户必须先上传真实图元定义 G 文件建立 ACTIVE 标准，然后才能检查业务单线图。界面只保留一张图元标准表；SMART / NORMAL 表示检查适用范围，不代表必须使用两套不同图元。同一种设备可以分别绑定不同标准，也可以让 SMART 与 NORMAL 共用同一个标准图元文件；例如没有智能/非智能区分的接地刀闸可直接共用。</p>
<h3>权威标准图元库</h3>
<p>先在图元标准表中选中设备角色，再点击“为选中角色上传 / 更新标准 G”，一次选择一个真实图元定义 G。设备角色由用户当前选中的表格行明确绑定；程序只从上传 G 中解析 devref、主体、w/h、AlignCenter 与 pin 等标准属性。文件名、SMART/NORMAL 字样和解析到的 XML 元素都只作为参考，不再阻止人工绑定。如果同一设备在 SMART / NORMAL 中共用一个图元，可勾选“SMART / NORMAL 共用此标准”，一次上传同时绑定两个检查范围。保存后标准文件会复制到 Windows 用户数据目录中的 G File Studio 标准库，和程序安装目录、workspace 运行结果完全分离，因此升级或重新解压新版程序不会丢失。Profile 记录标准文件 SHA256 与整体标准指纹；文件被篡改或丢失时会阻止检查。</p>
<h3>版本与角色</h3>
<p>同一设备可以通过 Profile 历史版本保存多个标准图元版本，但当前 ACTIVE 版本中一个设备角色只能使用一个图元文件。更换标准图元后创建新的 ACTIVE Profile 版本，旧版本保留为 ARCHIVED。保存确认后可点击“锁定当前版本”：锁定期间不能修改表格、上传/替换标准 G、删除标准或恢复历史版本；检查业务 G 仍可执行。需要调整标准时先显式解锁。下次打开软件会默认恢复上次使用的 ACTIVE 标准及其锁定状态。</p>
<h3>标准来源边界</h3>
<p>业务单线图只用于定位设备实例并与已保存标准比较，不再扫描生成候选标准、待确认图元或学习数据。若要新增设备角色或更换标准，必须回到上方表格，由用户明确选择角色并上传对应的真实图元定义 G。这样业务图中的错误 devref、错误尺寸或历史图元不会反向污染标准。</p>
<h3>标准检查</h3>
<p>“检查图元标准”是完全只读模式：源 G 文件不会被修改。程序比较图元类型/变体、devref、w/h、AlignCenter 与 pin 锚点等标准信息，并生成 CSV/HTML 图元标准检查报告；发现差异时界面会明确告警。</p><h3>按标准纠正</h3><p>点击“纠正标准问题”后，程序只处理当前 ACTIVE 标准已经定义的图元，并把结果写到本次 workspace 运行目录的 corrected 文件夹。对于带电气 pin 且能从 node_area/link 与 ConnectLine 可靠取得连接端点的图元，会保持连接线绝对坐标不动，根据标准 w/h、旋转与 pin 几何反算图元 x/y；图元 XML 类型不限于 LBS、Circuit Breaker 或接地刀闸，自定义设备标准也使用同一套锚点内核。若端口数量、连接关系或几何模板无法可靠对应，则跳过自动移动并在复查报告中保留问题，不做猜测。纠正完成后自动对 corrected 副本再执行一次只读标准检查。</p>
<h3>与图元版本升级的边界</h3>
<p>同一设备语义的 OLD → NEW 图元版本升级统一放在“基础处理 → 同类图元版本升级”。例如旧版 LBS → 新版 LBS 属于版本升级；SMART 图元误用到 NORMAL、NORMAL 图元误用到 SMART，以及已定义标准图元的连接锚点位置偏移，属于标准一致性问题，可在本模块检查并按 ACTIVE 标准纠正。吉达馈线批处理仍保持原有独立流程，本次新增纠正能力不会改变其步骤或算法。</p>
<h3>运行结果与安全</h3>
<p>标准图元/Profile 属于长期资产，保存于版本独立的用户数据目录；workspace/runs 中的处理 G、HTML/CSV 报告和日志属于临时运行结果，现有机制自动清理超过 30 天的运行记录。清理运行结果不会删除标准图元或 Profile。</p>
""",
    ),
    "small_elements": (
        "异常小尺寸图元检测帮助",
        """
<h3>用途</h3>
<p>独立扫描 &lt;ConnectLine&gt;、&lt;FeedLine&gt;、&lt;Bus&gt;、&lt;BusDis&gt;。当 w 和 h 同时小于用户阈值（默认 10）时，作为疑似误画后残留的小尺寸图元输出报告。Bus 不区分水平、垂直或其他方向。</p>
<h3>报告与删除</h3>
<p>每次扫描都会输出带时间戳的 CSV 和 HTML，并列出文件名、元素类型、XML ID、x/y/w/h、keyid，不覆盖历史报告。结果表按普通表格方式支持单元格/区域选择和 Ctrl+C 复制；需要处理的异常图元通过首列复选框单选、多选或全选，再统一执行。执行后会生成修改后的 G 文件和本次处理报告，原文件不覆盖。</p>
<p>如果选中元素存在非空 keyid，删除前必须再次确认，并明确显示所在文件、元素类型、XML ID 与 keyid。</p>
<h3>与馈线合并的关系</h3>
<p>主母线合并不再使用 w&lt;10 的特殊过滤条件。所有异常短线 Bus 统一在本模块发现和清理。</p>
""",
    ),
    "rmu": (
        "环网柜处理帮助",
        """
<h3>RMU 基础识别与汇总（必需）</h3>
<p>RMU 基础识别是本页面所有后续功能的共同前置能力，固定识别全部有效 RMU 且不可关闭，并强制生成 RMU 汇总 CSV / HTML 报告。界面不再提供“智能/非智能识别范围”开关；用户只需要配置柜名可能位置、柜名排除字符串，以及“智能 RMU 标记字符”。智能标记默认 SMART / SMR，可扩展 NEWSMART、SMART-SE 等任意完整 Text；程序全图扫描这些标记并唯一归属最近的有效 RMU，同时自动把这些标记从柜名候选中排除。</p>
<h3>环网柜图元处理</h3>
<p>环网柜页面可选择“不处理”或“组合所有环网柜”。彻底取消图形组合已移动到“基础处理 → 图形组合处理”：该操作删除整个 G 文件 Layer 中全部 &lt;Merge&gt;，并将识别到的 RMU 外框置于设备底层；除 XML 顺序外不修改设备属性、坐标、ID 或引用。</p>
<p>SMART/SMR 外框改色和 channel_status 状态点位置均沿用原基础处理中的既有算法；另外可单独启用“将已识别的环网柜名称统一改成白色”。Poke 跳转已经从本页面完全抽离到左侧独立“Poke 跳转处理”模块；该模块仍直接调用这里同一个 identify_rmus() 识别器和同一组柜名方向、排除项、智能标记设置，因此后续公共 RMU 识别规则升级会自动同步到 Poke。</p>
<p>“图元标准检查”是独立通用工具：检查模式只读；需要时可按 ACTIVE 标准在 workspace 生成纠正副本，用于纠正标准中已定义图元的变体/devref及可可靠拟合的连接锚点位置。SMR 等现场特殊柜不参与通用 NORMAL 学习；该工具不改变原“开始环网柜处理”流程。</p>
<h3>RMU 识别规则</h3>
<p>直接解析 G 文件，不使用 OCR。柜名可多选“上方/下方/左侧/右侧”搜索；所选方向为硬约束，未勾选方向绝不参与兜底。单候选直接使用，最近组存在多个候选时才优先绿色文字。柜型优先按 Y/Q 名称统计，必要时回退设备 devref；用户配置的智能标记统一归类为智能环网柜：默认 SMART / SMR，也可扩展 NEWSMART、SMART-SE 等；全图扫描标记并归属到最近的有效 RMU，每个标记只允许属于一个 RMU，且标记无需完全位于柜框内部；同时保留识别来源。识别结果导出 .rmu.csv 与 .rmu.html。</p>
""",
    ),
    "basic": (
        "基础处理帮助",
        """
<h3>输入方式</h3>
<p>基础处理支持单个 G 文件和 G 文件目录。单文件模式只处理所选文件；目录模式批量处理目录第一层中的所有 .g 文件。</p>
<h3>规则化处理</h3>
<p>“替换元素属性值”和“删除匹配元素”默认关闭。点击“扫描元素与属性”可从当前单个输入文件或输入目录中生成元素标签和属性名下拉选项。</p>
<p><b>处理范围：</b>只处理 G 根节点直属 Layer 的直接子元素，不修改 G、Theme、Layer 外内容，也不递归修改图元内部子元素。</p>
<ul>
<li>属性替换：元素标签、属性名、旧值全部精确匹配后写入新值。</li>
<li>元素删除：元素标签、属性名、属性值全部精确匹配后删除整个元素子树。</li>
</ul>
<p>删除后会在当前 Layer 范围内清理 link、node_area 和 p_FatherObjId 中指向已删除真实图元的引用。</p>
<p><b>ID 功能：</b>已从基础处理抽离到独立“ID 检查与修复”页面。</p>
<h3>馈线名称定位（复选框）</h3>
<p>勾选“将馈线名称移动到母线上方”后，程序只根据有效水平 &lt;Bus&gt; 的几何、&lt;Text&gt; 的内容、字号和局部位置识别馈线名称；不读取 key_name 或 keyid。上下平行且范围重叠的双母线按一组处理。纯数字、括号数字、Y1/Q1/SMART 等设备标签、单位和说明文字会被排除；候选不唯一时跳过。识别成功后只修改目标 Text 的 x、y，使其位于最上方母线正上方并水平居中。</p>
<h3>同类图元版本升级</h3>
<p>用于同一设备语义、同一主体 XML 类型的旧版图元 → 新版图元升级。OLD/NEW 文件名可以不同，可自动配对或手工指定；程序读取 w/h、AlignCenter、pin 并保持电气锚点绝对位置。SMART/NORMAL 用错等“图元类型/变体使用错误”不属于版本升级，应先由“图元标准检查”发现并告警，再走对应纠正流程。</p>
<h3>线路与母线样式</h3>
<p>可分别调整 &lt;FeedLine&gt;、&lt;ConnectLine&gt;、&lt;BusDis&gt; 和 &lt;Bus&gt; 的颜色与线型。颜色同步写入 lc/lcc；线型使用 ls：实线=1、虚线=2，选择“保持原样”时不修改 ls。颜色与线型可独立设置，不修改填充色、线宽 lw、坐标、ID 或引用。</p>
<h3>输出冲突</h3>
<p>当输入输出路径相同，或输出目录中已存在同名文件时，程序会提示选择：自动添加统一时间戳（推荐）、安全覆盖或取消任务。安全覆盖先写临时文件并重新解析验证，成功后才替换原文件。</p>
""",
    ),
    "id_rules": (
        "元素 ID 规则模板帮助",
        """
<h3>唯一规则来源</h3>
<p>本模块管理 XML 元素的 ID 规则。每一种元素类型只能使用人工确认的“固定数字前缀 + 固定总位数”规则。</p>
<h3>扫描当前 G</h3>
<p>发现模板中不存在的新元素类型时，程序会显示真实样本并给出候选规则；必须由用户点击确认后才加入模板。已知类型出现模板之外的 ID 格式时会告警，不会自动更新模板或改写既有 ID。</p>
<h3>重复 ID 修复</h3>
<p>修复时保留第一处重复 ID，后续重复元素只允许按照该元素类型的已确认模板，从当前同类最大流水号继续分配；不补历史空号。未知、禁用或未确认类型禁止生成新 ID。</p>
""",
    ),
    "merge": (
        "馈线图合并帮助",
        """
<h3>文件与顺序</h3>
<ul>
<li>文件名任意，但后缀必须是 <b>.sln.pic.g</b>。</li>
<li>不解析站点、馈线号，也不判断是否属于同一站。</li>
<li>点击“加载 / 检查”时显示加载进度，并检查 XML、对齐基准和图框类型。</li>
<li>点击“查询并导入”，可按文件名关键字模糊查询，选择或全选匹配文件后导入列表。</li>
<li>支持 Ctrl/Shift 多选并点击“删除所选”，只保留需要合并的文件；此操作不会删除磁盘文件。</li>
<li>使用上移、下移、置顶、置底自由定义剩余文件顺序，第一行作为基准。</li>
<li>点击“导入全部可用”可把全部通过检查的文件按自然顺序导入。</li>
<li>G File Studio 内置图框会在合并前从内存副本中自动移除；客户或来源不明图框禁止参与合并。</li>
<li>图框识别不读取标题、Draw、Approve、Issue、姓名或日期文字内容。</li>
</ul>
<h3>垂直对齐</h3>
<ul>
<li>只识别标签严格等于 <b>&lt;Bus&gt;</b> 的非零长度水平母线，&lt;BusDis&gt; 不参与。</li>
<li>存在 Bus 时选择 Y 最小的最上方 Bus；同一 Y 时优先最长 Bus。</li>
<li>没有 Bus 时使用该文件位置坐标中的最小 Y，也就是最高图元。</li>
<li>所有后续文件都与第一张基准文件的统一 Y 对齐。</li>
</ul>
<h3>主母线合并</h3>
<ul>
<li>启用“主网母线处理”后先选择单母线或双母线。单母线只检查 Y 最小的最高有效水平 &lt;Bus&gt;；双母线检查最高母线和同方向下方长度大致相同的第二条有效水平 &lt;Bus&gt;。小尺寸 Bus 不再在本模块特殊过滤，由“异常小尺寸图元检测”统一处理。只有被选中的主母线必须有非空 keyid；不同 keyid 永远不会互相连接。同一 keyid 必须在馈线排序中连续，并且合并后必须处在同一水平线上，否则拒绝执行。文件名只作人工提醒，不作为硬性拦截条件。</li>
<li>保留第一条 Bus，从第一张馈线母线起点连续延伸到最后一张馈线母线终点；其余顶部主母线删除。</li>
<li>所有原馈线连接关系同步改接到保留 Bus；&lt;BusDis&gt; 和非顶部 Bus 不处理。</li>
<li>输出后继续按“ID 检查与修复”中用户确认的 ID 规则强制检查和规范。</li>
</ul>
""",
    ),
    "margin": (
        "图形边距调整帮助",
        """
<h3>主体图形边距</h3>
<p>程序识别 Layer 中的主体图形边界，整体平移后使主体距离画布左、上、右、下达到用户设置值，默认均为 500。</p>
<h3>已有图框</h3>
<p>只有可确认的 G File Studio 内置图框会自动处理：图框及其标题栏、签字栏不参与主体边界计算，新画布生成后保持原图框四边距，拉伸外框线，并按锚点移动附属组件。</p><p>检测到客户图框或无法确认来源的图框时，程序会停止并提示先在图形编辑器中删除图框。</p>
<p>标题、Draw、Approve、Issue、日期、字体、颜色、线宽和表格内容都不会被修改。</p>
<h3>输入方式</h3>
<p>支持单个 G 文件和目录批量处理。输出保持源文件名不变并写入独立输出目录，不覆盖原文件。</p>
""",
    ),
    "frame": (
        "图框添加帮助",
        """
<h3>输入方式</h3>
<p>图框添加支持单个 G 文件和 G 文件目录。单文件模式只处理所选文件；目录模式批量处理目录第一层中的所有 .g 文件。</p>
<h3>程序内置模板</h3>
<p>内置模板随 App 一起打包，不依赖开发电脑路径。程序会按四边距调整外框，移动左上和右下组件，并修改标题、Draw、Approve、Issue 和日期。</p>
<h3>客户自定义模板</h3>
<p>程序同样按四边距调整外框线长度，并让模板组件保持相对于最近外框边缘的位置；但不会修改任何 Text 内容、姓名、日期、字体、颜色、线宽或表格内容。</p>
<h3>模板升级</h3>
<p>内置模板是 resources/templates 中独立的 .g 文件，并在 templates.json 中记录版本。以后替换模板文件并重新打包即可发布新版。</p>
<p>两种模式都会重新分配模板图元 ID，避免与目标图中的 ID 冲突。</p>
""",
    ),
    "help": (
        "帮助中心",
        """
<h3>推荐流程</h3>
<ol>
<li>先使用“异常小尺寸图元检测”发现并按需清理疑似残留图元，再在“ID 检查与修复”中确认元素 ID 规则并按需检查/修复重复 ID；需要环网柜处理时进入独立“环网柜处理”，之后再进入“基础处理”。</li>
<li>需要多张馈线图时，再使用“馈线图合并”。</li>
<li>按需执行“图形边距调整”和“图框添加”。</li>
</ol>
<p>各页面独立执行、独立选择输入与输出，便于检查每一步结果。</p>
<h3>最近目录</h3>
<p>每个页面会分别记住单文件、目录输入、输出目录以及客户模板目录。下次点击浏览时会从上次目录打开；若目录已被删除或移动，程序会提示并要求重新选择。</p>
<h3>程序图标与发布</h3>
<p>项目内置绿色 app.ico/app.png。PyInstaller 打包脚本使用 app.ico 设置 EXE 图标，App 启动时使用同一图标设置窗口和任务栏图标。</p>
<p>文件夹模式打包后，需要把 dist/GFileStudio 整个目录压缩成 ZIP 分享，不能只发送 GFileStudio.exe。</p>
""",
    ),
}

FIELD_HELP: dict[str, str] = {
    "input_dir": "选择单个待处理 G 文件或包含多个 G 文件的目录。",
    "merge_input_dir": "选择包含 .sln.pic.g 文件的目录。内置图框可自动移除；非内置图框不会参与合并。",
    "output_dir": "输出由程序统一写入 workspace/runs 的本次运行目录。路径只读、不可修改；运行记录仅保留 30 天，需要长期保存请自行复制。",
    "template": "默认使用 App 内置模板，也可以选择客户自定义 .sln.pic.g 模板。",
    "feeder_gap": "相邻两张图真实坐标边界之间的水平距离，默认 300。",
    "merge_margin": "合并图形距离画布四边的距离。数值框不响应鼠标滚轮。",
    "frame_margin": "图框外边线距离目标 G 画布边缘的距离。内置和自定义模板均使用此参数。",
    "content_margin": "主体图形距离 G 画布对应边缘的距离，默认 500。仅 G File Studio 内置图框会被排除并同步调整；其他图框需先删除。",
    "title": "仅内置模板使用；留空时自动取输入文件名去掉 .sln.pic.g 后的内容。",
    "output_name": "合并输出统一使用 .sln.pic.g 后缀；留空生成 MERGED-时间戳.sln.pic.g。",
    "output_suffix": "所有一对一 G 文件处理均固定保持源文件名；不同运行批次由 workspace 运行目录隔离。",
    "draw": "仅内置模板使用。日期默认当前日期，可点击日历按钮修改。",
    "approve": "仅内置模板使用。日期默认当前日期，可点击日历按钮修改。",
    "issue": "仅内置模板使用。日期默认当前日期，可点击日历按钮修改。",
}


APP_HELP_EN: dict[str, tuple[str, str]] = {
    "jeddah_batch": (
        "Jeddah Feeder Batch Processing Help",
        """
<h3>Purpose</h3>
<p>For Jeddah-only batch standardization of single-feeder diagrams. Each input G file is processed and output independently; feeder diagrams are not merged.</p>
<h3>Fixed workflow</h3>
<ol>
<li>First reuse Basic Processing &gt; Graphic Group Processing &gt; Fully Ungroup Graphics: remove every &lt;Merge&gt; and send recognized RMU frames behind devices.</li>
<li>Remove abnormal small ConnectLine / FeedLine / Bus / BusDis elements.</li>
<li>Set recognized RMU name text to white at font size 50, centered above its RMU top frame with a 10-unit clear gap between the text bottom and the frame.</li>
<li>Set SMART and SMR RMU frames to red.</li>
<li>SMART device validation covers the whole RMU frame: whenever a SMART Text center lies inside the frame, normalize Y Load_Breaker_Switch and Q Circuit_Breaker devrefs to SMART. Q devices support both Circuit_Breaker_NO-SMART and Circuit_Breaker_NON-SMART source references.</li>
<li>Apply conditional SMR handling: when SMART already exists inside the matched RMU, remove only the external SMR and keep the existing SMART label unchanged; otherwise convert SMR to a top-centered SMART label at font size 20, then run the SMART device validation again.</li>
<li>Remove RMU rectangles containing Bus and move the corresponding title above the bus.</li>
<li>Move feeder names above buses.</li>
<li>Set every &lt;FeedLine&gt; to solid line style (ls=1) without changing color, line width, coordinates, IDs, or references.</li>
<li>Remove RMU channel_status red Status points. Association reuses the existing RMU red-status positioning rule; only the final action changes from repositioning to deletion.</li>
<li>Remove exact H.T Text markers (case-insensitive after trimming; no substring matching).</li>
<li>Check every distribution RMU recognized by the existing RMU engine for duplicate SMART labels. If one cabinet contains multiple SMART Texts, preserve the first/original XML label and remove only later duplicates without moving or restyling the preserved label.</li>
<li>Remove the exact Text pair 2000.00 + UPDATED_MEASURMENT only when the two separate Text elements are on the same visual line and horizontally adjacent (gap no greater than 10). Distant matches are preserved.</li>
<li>Run ID check and repair using the globally confirmed ID templates.</li>
<li>Reuse Drawing Margin Adjustment with default body margins of 500 on all four sides.</li>
<li>Finally reuse Drawing Frame to add the selected frame template to every processed feeder diagram.</li>
</ol>
<h3>Design principle</h3>
<p>This page only orchestrates existing processing capabilities. It does not replace or rewrite the algorithms of the existing Small Element, RMU, feeder-title, or ID modules. Jeddah-specific parameters use a separate settings namespace and do not overwrite other module settings.</p>
""",
    ),
    "site_profile": ("Symbol Standard Check Help", """<h3>Purpose</h3><p>The standard source and business G files are fully separated. Users must first upload real symbol-definition G files and build a complete ACTIVE standard before business drawings can be checked.</p><h3>Authoritative standard library</h3><p>Use Standard Management → Upload Standard Symbol G to select one or more icon-definition G files. Every file must expose a valid symbol body, size, AlignCenter and pin definition. Business SLD G files are rejected as standards. Saved standard files are copied into the version-independent user data directory, so application upgrades do not remove them. SHA256 hashes and a Profile standard fingerprint are stored and checked before execution.</p><h3>Versions and roles</h3><p>The six built-in RMU roles must all be assigned. One ACTIVE Profile version can bind only one standard file per device role. Replacing a symbol creates a new ACTIVE version while the previous version remains archived. The last ACTIVE Profile is restored on the next application start.</p><h3>Business drawings</h3><p>Business G files are check targets only. Newly discovered devrefs may be reported or ignored, but they cannot be promoted directly into the standard; the corresponding real symbol G must be uploaded first.</p><h3>Check and correct</h3><p>Check Symbol Standard is read-only. Correct Standard Issues creates corrected copies only under the managed workspace and never overwrites source G. Reports/logs under workspace/runs are disposable runtime output and are automatically expired by the existing retention mechanism; persistent standards are stored elsewhere and are never deleted by run cleanup.</p>"""),
    "small_elements": ("Abnormal Small Element Detection Help", """<h3>Purpose</h3><p>Scans &lt;ConnectLine&gt;, &lt;FeedLine&gt;, &lt;Bus&gt; and &lt;BusDis&gt; independently. An element is reported when both w and h are below the user threshold (default 10). Bus orientation is not restricted.</p><h3>Reports and deletion</h3><p>Each scan exports CSV and HTML details including file, element type, XML ID, x/y/w/h and keyid. Select one or more findings using the first-column checkboxes, then process them together. If a selected element has a non-empty keyid, deletion requires explicit confirmation.</p><h3>Relation to feeder merge</h3><p>Main-bus merge no longer applies a special w&lt;10 filter. Suspicious short Bus elements are handled in this module.</p>"""),
    "rmu": ("RMU Processing Help", """<h3>RMU graphic processing</h3><p>The RMU page can leave grouping unchanged or group all recognized RMUs. Whole-file ungrouping is available under Basic Processing → Graphic Group Processing; it removes every &lt;Merge&gt; and sends recognized RMU frames behind devices without changing device attributes, coordinates, IDs or references.</p><p>Poke jump processing has been removed from this page and moved to the standalone Poke Jump Processing module. That module still calls the exact same identify_rmus() engine and reads the same RMU name-direction, exclusion and smart-marker settings, so future shared RMU-recognition updates are inherited automatically.</p><p>Site RMU Device Profile is an independent tool: the user assigns standard samples to a site, scans them to learn SMART LBS / Circuit Breaker devrefs, saves the profile, and can then run a standalone SMART-device consistency check. It does not participate in the existing Start RMU Processing flow.</p><h3>RMU summary</h3><p>G files are parsed directly without OCR. Name search directions are strict constraints. Cabinet type is primarily derived from Y/Q names with devref as fallback when required. SMART and SMR are classified as intelligent RMUs while preserving the recognition source.</p>"""),
    "basic": ("Basic Processing Help", """<h3>Input</h3><p>Basic Processing supports one G file or a directory of G files.</p><h3>Rule-based processing</h3><p>General attribute replacement and element deletion operate only on direct children of the root Layer. They do not recursively modify internal symbol children.</p><h3>Feeder title positioning</h3><p>When enabled, feeder titles are identified from valid horizontal &lt;Bus&gt; geometry and nearby &lt;Text&gt; content. key_name and keyid are not used. Only the target Text x/y position is changed.</p><h3>Connection repair</h3><p>Uses conservative incremental repair. Existing port numbers and references are preserved; ambiguous or invalid candidates are skipped.</p><h3>Line and bus styles</h3><p>Color changes only lc/lcc. Line style changes only ls: solid=1 and dashed=2. Fill, lw, coordinates, IDs and references are not modified.</p><h3>Output conflicts</h3><p>Safe overwrite writes to a temporary file and validates it before replacing the destination.</p>"""),
    "id_rules": ("Element ID Rule Template Help", """<h3>Single source of rules</h3><p>This module manages XML element ID rules. Each element type uses a manually confirmed fixed numeric prefix and fixed total length.</p><h3>Scan current G</h3><p>New element types require explicit user confirmation before a candidate rule is added. Existing types with nonconforming IDs produce warnings and do not silently change templates.</p><h3>Duplicate ID repair</h3><p>The first duplicate ID is preserved. Later duplicates receive IDs from the confirmed template, starting after the current maximum valid ID of the same type. Historical gaps are not filled. Unknown, disabled or unconfirmed types cannot generate new IDs.</p>"""),
    "merge": ("Feeder Diagram Merge Help", """<h3>Files and order</h3><p>Input files must end with .sln.pic.g. The user-defined list order is the merge order; the first row is the baseline. Built-in G File Studio frames are removed from in-memory copies before merge, while unknown/customer frames are blocked.</p><h3>Vertical alignment</h3><p>Only non-zero horizontal &lt;Bus&gt; elements are used. &lt;BusDis&gt; does not participate. The topmost Bus is selected; if no Bus exists, the highest graphic element is used.</p><h3>Main-bus processing</h3><p>Supports single- and double-bus processing with manual bus groups. Files in one group must be contiguous. Upper and lower buses remain separate in double-bus mode. Output IDs are validated against confirmed global ID templates.</p>"""),
    "margin": ("Drawing Margin Adjustment Help", """<h3>Main drawing margins</h3><p>The main drawing is translated so its left, top, right and bottom margins match the configured values.</p><h3>Existing frames</h3><p>Only confirmed G File Studio built-in frames are adjusted automatically. Customer or unknown frames stop processing and must be removed first.</p><h3>Input</h3><p>Supports one G file or directory batch processing. Output keeps the original source filename.</p>"""),
    "frame": ("Drawing Frame Help", """<h3>Input</h3><p>Supports one G file or a directory of G files.</p><h3>Built-in template</h3><p>The bundled template is adjusted to the configured margins. Title and signature fields are updated only for the built-in template.</p><h3>Custom template</h3><p>Custom frame geometry is adapted without changing Text content, names, dates, fonts, colors, line widths or table content.</p><h3>Template upgrades</h3><p>The built-in template is packaged under resources/templates and versioned in templates.json.</p>"""),
    "help": ("Help Center", """<h3>Recommended workflow</h3><ol><li>Detect abnormal small elements, then check/repair IDs, process RMUs when needed, and run Basic Processing.</li><li>Use Feeder Diagram Merge when multiple feeder drawings must be combined.</li><li>Run Drawing Margin Adjustment and Drawing Frame as required.</li></ol><h3>Recent folders</h3><p>Each page remembers its own recent input and output locations.</p><h3>Packaging</h3><p>The packaged dist/GFileStudio folder must be distributed as a complete folder or ZIP, not as the EXE alone.</p>"""),
}

FIELD_HELP_EN: dict[str, str] = {
    "input_dir": "Select one G file or a directory containing G files.",
    "merge_input_dir": "Select a directory containing .sln.pic.g files. Built-in frames may be removed automatically; unknown frames are blocked.",
    "output_dir": "Output is written to the managed workspace/runs directory. The path is read-only and run data is retained for 30 days.",
    "template": "Use the built-in template or select a custom .sln.pic.g template.",
    "feeder_gap": "Horizontal gap between adjacent drawing coordinate bounds. Default: 300.",
    "merge_margin": "Margins around the merged drawing. Mouse-wheel changes are disabled.",
    "frame_margin": "Distance between the drawing-frame border and the target G canvas edge.",
    "content_margin": "Distance from the main drawing to the corresponding G canvas edge. Default: 500.",
    "title": "Built-in template only. If empty, the input filename without .sln.pic.g is used.",
    "output_name": "Merged output always uses .sln.pic.g. If empty, a timestamped MERGED filename is generated.",
    "output_suffix": "One-to-one G-file processing always preserves the source filename; run folders isolate separate executions.",
    "draw": "Built-in template only. The date defaults to today and can be changed with the calendar button.",
    "approve": "Built-in template only. The date defaults to today and can be changed with the calendar button.",
    "issue": "Built-in template only. The date defaults to today and can be changed with the calendar button.",
}

# v2.18.90 standalone Poke processing help.
APP_HELP["poke"] = (
    "Poke 跳转处理帮助",
    """
<h3>用途</h3>
<p>Poke 跳转已从“环网柜处理”独立出来，统一复用公共 Oracle 数据库和公共 RMU 识别能力。</p>
<h3>前置条件</h3>
<p>不再要求 G 根节点 facID。facID 为空也可以执行两类 Poke；它只作为报告中的可选源文件信息保留。</p>
<h3>RMU Poke</h3>
<p>严格调用与“环网柜处理”相同的 identify_rmus()，并读取同一组柜名方向、名称排除项和智能标记设置。识别出智能 RMU 柜名后，数据库按 DMS_COMBINED_DEVICE.NAME → FEEDER_ID → DMS_FEEDER_DEVICE.NAME/ST_ID → SUBSTATION.NAME/SUBAREA_ID → SUBCONTROLAREA.NAME，为每个 RMU 独立得到所属馈线完整业务名，再追加该 RMU 名。因此同一张变电站馈线总图即使包含多条馈线，也不会被根节点 facID 限制。GRAPH_NAME 不参与命名。</p>
<h3>站点跳转 Poke</h3>
<p>例如 DHN-40 只提取 DHN；40 以及附近的 (14858) 等数字都不参与目标。程序按 SUBSTATION.NAME=DHN → SUBAREA_ID → SUBCONTROLAREA.NAME 得到 JED-CTL-DHN，并生成 JED-CTL-DHN.sln.pic.g；该目标图定义为“对端变电站馈线总图”，即对端变电站下多条馈线集中展示的站级总图。</p>
<p>识别不依赖固定背景色：优先复用覆盖标签的既有非 RMU Poke；没有 Poke 时结合 FeedLine/ConnectLine 末端位置或紧凑背景图形兜底。任何候选都必须通过数据库唯一匹配才允许修改。多个相关 Poke 删除多余项仅保留一个；没有则新增。</p>
<h3>样式</h3>
<p>RMU Poke 继续使用既有蓝色/Invisible 属性规则。站点跳转 Poke 则统一使用用户提供的 JM2-J2 参考 Poke 属性模板：除每个对象自己的 id、x/y/w/h、ahref 及 G File Studio 跟踪元数据外，其余 Poke 属性完全复制参考对象；已有站点 Poke 也会按该模板规范化。</p>
<h3>处理报告</h3>
<p>每次成功执行都会在本次运行目录生成 CSV/HTML Poke 报告。报告汇总公共 RMU 识别数量、智能 RMU 数、新增/更新 RMU Poke、站点跳转候选与成功解析数量、新增/更新站点跳转 Poke、重复 Poke 清理数量；明细会记录实际写入的 ahref，以及每个未加跳转候选的具体原因。</p>
""",
)
APP_HELP_EN["poke"] = (
    "Poke Jump Processing Help",
    """
<h3>Purpose</h3>
<p>Poke jump processing is independent from RMU Processing and reuses the shared Oracle service and shared RMU recognition engine.</p>
<h3>Requirement</h3>
<p>A root facID is no longer required. Blank facID does not block either Poke branch; it is kept only as optional source metadata in the report.</p>
<h3>RMU Poke</h3>
<p>The module calls the same identify_rmus() used by RMU Processing and reads the same name-direction, exclusion and smart-marker settings. Each recognized smart RMU name independently resolves DMS_COMBINED_DEVICE.NAME → FEEDER_ID → DMS_FEEDER_DEVICE.NAME/ST_ID → SUBSTATION.NAME/SUBAREA_ID → SUBCONTROLAREA.NAME. This allows one station overview drawing to contain RMUs from multiple feeders without relying on the root facID. GRAPH_NAME is not used.</p>
<h3>Station-jump Poke</h3>
<p>For DHN-40 only DHN is used. The suffix 40 and nearby values such as (14858) are ignored. SUBSTATION.NAME=DHN → SUBAREA_ID → SUBCONTROLAREA.NAME produces JED-CTL-DHN and therefore JED-CTL-DHN.sln.pic.g. This target is the remote substation feeder overview, i.e. the station-level drawing that brings multiple feeders of that substation together.</p>
<p>Recognition does not require a fixed background color. Existing overlapping non-RMU Pokes are preferred; otherwise nearby FeedLine/ConnectLine endpoints or compact background geometry are fallback structural cues. Every candidate must resolve uniquely in Oracle. Duplicate related Pokes are removed, and a missing Poke is created.</p>
<h3>Style</h3>
<p>RMU Pokes keep the existing blue/Invisible property rule. Station-jump Pokes use the user-provided JM2-J2 reference Poke as their canonical property template: every non-geometric Poke property is copied from the reference, while id, x/y/w/h, ahref and G File Studio tracking metadata remain target-specific.</p>
<h3>Processing Report</h3>
<p>Each successful run writes CSV/HTML Poke reports to the run directory. The report summarizes shared RMU recognition, smart RMUs, added/updated RMU Pokes, station-jump candidates/resolutions, added/updated station Pokes, duplicate cleanup, the exact written ahref, and the specific reason for every candidate whose jump was not added.</p>
""",
)
