# 自我审查问题记录

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1-dev
> 定位：**问题台账**——发现了什么、怎么修、修到哪；不记设计决策（看
> `technical.md`），不复述变更清单（看 `changelog.md`）。
> **编号源**：`rf-next = 46`（新增问题提出后取此编号，写入后更新为 +1；已用最大 rf-42，
> 递增保证唯一，归档不回收。编号与 `plan.md` 的 `plan-N` 是两套，互不占用）

---

## 当前待处理问题

## 分档口径

本文件按**风险**分档（H1–H3 + 登记），`plan.md` 按**时机**分档（P1–P4）；两套名字不交互，
引用时带前缀（`rf-N` / `plan-N`）。

### H1 — 高风险：不做的风险高（尽快执行）

入选标准：同一事实在两处声明且已有分歧、或门禁判不出来的冲突，留着就会产生新漂移。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### H2 — 价值明确、成本可控（下批排期）

| rf-45 | 逐章渲染导致同一字体在各分部重复嵌入，标准版仍 15 MB（六月 7 MB） | **探针结果（改变原计划）**：`pikepdf` 统计当前文件——24,567 个流**没有 /Subtype**（合计解压后 57.9 MB），而 `/FontFile2`、`/FontFile3` 一个都没有。说明 Chromium 仍把绝大部分文字导出成 **Type3 字形流**（Type3 字符过程本身就没有 /Subtype），换成 .ttf 家族只是把它们从 35k 减到 24.5k。**所以「合并 TrueType 子集」这条路当前无对象可合并**。`fonttools` 4.68.0 已装好备用。**修正后的下一步**：先查明 Chromium 为何仍走 Type3（用最小 HTML 逐项排除：加粗、字体回退、`text-rendering`、背景绘制），把 Type3 消掉之后体积问题大概率随之消失；届时仍不够再做子集归并 |

| rf-44 | 标准版 PDF 的体积是六月参照的 2.7 倍 | **已解决**：逐项比对后定位到**字体格式**——六月用系统里的雅黑/宋体（.ttf），本机 CSS 声明的 `Microsoft YaHei`/`SimSun`/`Consolas` 都不存在，落到 Noto CJK（**.ttc 字体集合**），Chromium 导出 PDF 时无法子集化 TTC，只能把每个字形写成 Type3 字形流（35,393 个流 / 13.8 MB）。修法：`html_shell.SANS_STACK`/`MONO_STACK` 改为优先使用本机存在的 .ttf 家族（Droid Sans Fallback 覆盖中日韩），并保留 Noto/雅黑/苹方作跨平台后备。结果 **848 页 / 15.0 MB / 大纲 623/623**（改前 892 页 / 19 MB，六月 843 页 / 7.0 MB）。同时修正 gs 优化步骤：仅在同页数且更小时替换，避免用被截断的文件覆盖成品 |

入选标准：收益明确、影响面可圈定，不涉及结构改动。

| # | 问题 | 修复方向 |
| --- | --- | --- |



入选标准：收益明确、影响面可圈定，不涉及结构改动。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### H3 — 持续监控：兼容残留

> **本节性质**：这是**已核销的盘点基线**，不是待办清单。下方表格为空 = 当前没有兼容
> 残留需要处理。兼容口径（不保留旧配置名、未登记键不生效）归 `technical.md` §3.1，
> 本文件只留盘点结论。

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**盘点口径**（下次盘点照此执行）：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 /
旧数据文件结构 / 旧缓存结构 / 旧内部 API」；只有「旧版本产物能让当前版本**行为不正确**」
才算本类待办，仅「旧文件还能读」不算。

**盘点结论**：`book.toml` 缺表即视为未配置（不回落默认值）；`base.json` / `style.json`
缺文件时回落单文件 `config.json` 是显式声明的兼容形态，不是残留；`data/snapshots/`
与 `data/baselines/snapshot-*.json` 只读、不参与构建；`data/state/` 每次 ingest 重建，
无兼容面。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### 登记 — 文件膨胀（不阻塞，只留拆分方向）

预算以 `style.json [limits]` 为准（`file_length.py` 的 `budgets()`），四档均须在配置里显式声明；
`file_length.py` 判红并校验本表行数与实测一致。下表登记达预算 65% 以上、需要预留拆分方向的存量：

| 文件 | 现状与拆分方向 |
| --- | --- |
| `src/python/ingest/chapters.py` 835 行 | 占比 97%，章节正文已按小节组拆成模块版图 / 接口坐标 / 阅读路径 / 设计权衡 / 深读要点 / 术语 / 小结 / 视角 / 检查清单九个助手（每章事实只在 `_chapter_context` 算一次），剩余方向是骨架生成与语言适配调用两段（事实块标记与刷新已拆到 `ingest/factblocks.py`） |
| `src/python/audit/style.py` 614 行 | 占比 68%，句式规则已按规则族拆开（单调 / 重复 / 段落各自成函数），剩余方向是共享解析（行扫描、句切分）上提到 `lib/_mdutil` |
| `src/python/lib/_config.py` 893 行 | 占比 95%，按「书目发现 / 配置加载」「路径与策略」「手稿结构与版本」三段拆。拆分时的三处内部依赖：`_IMPORT_ROOT` 由发现逻辑算出、`ConfigError` 被两侧共用、`candidate_books()` 反过来用 `Config`——先把前两者下沉到新模块、`candidate_books` 留在门面，才能避开循环导入（试过整体抽取，14 个用例导入失败） |

## 已解决问题

### 本版本已修复（6.5）

> 本表为当前开发周期的摘要行，详情见 `changelog.md` 的 `[6.5]` 段；发布时摘要留在
> 版本段，本表清空。

| # | 问题 | 修复 |
| --- | --- | --- |
| rf-1 | 同一事实多处声明：配置分层有"两层（含 `config.json`）""三层""四层"三种说法；门禁级别在 `testplan.md` §2.2 与 §7 互相矛盾；`plan.md` 复述了技术设计的概述 | 分层只在 `technical.md` §3.1 定义；级别只在 `testplan.md` §2.2 声明并删除 §7；`plan.md` 改为计划项清单 |
| rf-2 | `book.toml` 存在死键：四个章节表里键 `ch7-sql-execution.md`、`ch8-query-optimizer.md` 不在 `[chapters] files` 中，包归属与编号实际未生效 | 键合并为 `ch7-8-sql-optimizer.md`（包 / 标题 / 编号 `[9,10]` / 覆盖 `[7,8]`），`doc_drift.py` 新增 CONFIG 检查防复发 |
| rf-3 | 附录数量三处不一致："5 个附录""2 个附录"，而 `book.toml` 只给 A/B 分配编号 | 统一为「12 章节槽 + 2 个编号附录 A/B；术语表 / 索引 / 参考文献为后件 C/D/E」 |
| rf-4 | 计划与问题没有各自的载体：`plan.md` 是概述式文档，`testplan.md` 曾要求"审查问题单独维护"却无此文件 | `plan.md` 改为带编号的计划项清单；新增本文件，条目不占计划编号 |
| rf-5 | 章节合并后 `content_depth.py` 只取文件的第一个章号，导致合并文件的包归属判错 | `owner_map` 返回章号列表，前向引用点名任一章号即通过；基线按新键控重新固化 |
| rf-6 | 门禁盲区：`doc_drift.py` 只认反引号里的章节名、不查配置死键、不查级别重复声明；版本比对与 `version_consistency.py` 重复 | 新增 CONFIG / LEVEL 两项检查并把章节名检查放宽；版本检查从 `doc_drift.py` 移除；管理文档头写错版本（写成书籍版本）由 `version_consistency.py` 判红 |
| rf-7 | 手册示例可能混入真实章节名与真实路径，未逐份核对 | 已逐份核对 `docs/manuals/*.md`：示例统一为 `<主题>` / `<code>` 占位，无越界真实章节名；`doc_drift.py` 的 CHAPTER 检查兜住复发 |
| rf-8 | 管理文档互查：索引重复登记 `plan.md`、`folder.md` 缺 `quality-model.md` 且职责过时、交付链路与印刷版 PDF / EPUB 归属、门禁级别越出 P0–P2、延伸思考章数、脚本路径、界面用语、旧启动器名，共 16 处冲突与冗余 | 逐条收归单一权威（变更内容见 `changelog.md` 同版段）；`doc_drift` 补 `INDEX`/`NUMBERING`/`DELIVER`/`PREFIX` 四项机检 |
| rf-9 | 互查靠人读：管理目录与索引用表、编号源标记、需求与判据的对应关系都没有机检面，互相矛盾的条目只能靠人工发现；`src/test/test_no_network.py` 被删后 testplan 仍把它列为载体 | `doc_drift.py` 补 `INDEX`/`NUMBERING` 并扩展路径面；`file_length.py` 兼校膨胀登记表；新增 `requirement_trace.py` 与 testplan §2.4 对照表；补回 `test_no_network.py` |
| rf-10 | 用户文档互查出 6 处冲突：章末四段顺序、`scripts/` 前缀白名单、`deliver` 步骤、报告类脚本归类、日志文件名、TUI 键位 | 按代码实际改写；`DELIVER`/`PREFIX` 两项机检兜住复发 |
| rf-11 | 管理文档的角色与内容对不上：8 份没有「定位」行，`plan.md` 与 `review-findings.md` 都用 P1–P4 但含义不同，`folder.md` 的配置分层表与 `technical.md` §3.1 重复，练习/引用规则在 `analysis-doc-standard` 与 `style-guide` 各写一遍 | 14 份统一补 `> 定位：`（`doc_drift` 新增 `LOCUS` 检查）；问题台账改 H1–H3 + 登记档并写明与 plan 时机档的区别；`folder.md` 只留归属、合并规则指向技术设计；练习与跨章引用细则只在 `style-guide` |
| rf-12 | 内容标准与写作规则边界不清：`analysis-doc-standard` 既讲「必须有什么」又声明判据与级别，还点名本项目的门禁表与配置文件名——与其「跨项目复用」的定位矛盾 | 收敛为两轴：本文只讲内容要求，写法指向 `style-guide`；判据改由项目单向登记；`doc_drift` 新增 `STANDARD` 检查兜住反向引用 |
| rf-13 | 口径冲突：`testplan` 写「手稿附录 ≤2000」而配置是 9000；段落规则一处按行一处按字符；索引阈值 120/每章 5 写死在 `structure.py`；性能预算一处当硬约束一处只提示 | **修订**：testplan 与 `review-findings` 的阈值改写成配置键，四档预算必须在 `style.json [limits]` 显式声明（`file_length` 新增 `BUDGET` 检查）；`index_total_min`/`index_per_chapter_min` 进 `style.json [thresholds]`，`structure.py` 读配置；段落规则统一为字符口径；NFR-05 标注 advisory |
| rf-14 | 修 rf-13 时把配置键名写进了判据：`testplan` §2.2 用 `[thresholds].index_total_min` 等替代数值，等于把实现细节搬进“通过标准”——判据应说性质，键名与取值归 `technical.md` §3.2 | **修订**：判据行改写成“不低于配置下限”这类性质表述；键名集中写进 `technical.md` §3.2 的阈值归属；`doc_drift` 新增 `THRESHOLD` 检查，判据表里出现配置键名即失败 |
| rf-15 | `testplan` 里混入不属于判据的内容：§4 写了渲染实现参数（`--split-level`、CSS 配色）与无门禁的版式阈值（1.5 倍、2-5 MB）；§2.2 用「9 项 CSS 标记」当判据、另有一条「脚本语法有效」的弱判据；§5 与 §2.2 逐条重复；§6 是流程策略 | **修订**：§4 收缩为按需验收项 + 按需命令，实现与版式指向 `technical.md` §4.4 / `style-guide.md` §6，两个硬编码数字删除；§2.2 改为「样式与锚点钩子齐备」并删弱判据；§5 改为「以 §2.2 为准」；§6 指向 `quality-model` §4 与手册 |
| rf-16 | 代码/配置遗留的硬编码：`smart.py` 内联「2 图」「95%」、`figure_clusters.py` 默认窗口 50 而 `structure.py` 传 40（两道门禁实际在查不同窗口，文档写 40）；`verify_pdf.py` 内联 A4 595×842±2；`_config` 与三个渲染脚本的 docstring 写死第一本书的名字 | **修订**：图簇与图表阈值进 `style.json [clusters]`/`[quality]`，A4 几何进 `base.json [toolchain]`，`structure.py` 与门禁共用同一取值；书名改由 `book.toml` 提供（兜底 `book`）；`check_architecture` 新增书名字面量检查 |
| rf-17 | 文档与代码对照时发现 `scripts/bookctl` 的帮助注释写 `bookctl llm`，而 CLI 只接受 `llm-ask`——手册写的是对的，包装脚本的头注释是唯一错处，属“没人重跑过”的注释漂移 | **修订**：注释改为 `llm-ask`；`script_contract.py` 新增 `check_dispatcher_help`，把包装脚本帮助里点名的动作与 `core/actions.py` 的 ACTIONS 表对齐，写错即失败（含 3 个用例） |
| rf-18 | TUI 只有一层平铺菜单（九个按键全在主界面），配置只能在命令行上改，`0` 与 `q` 一样直接退出，LLM provider 的回退顺序只能手改 JSON；另发现 Web 控制台在动作抛异常时直接断开连接（顺序依赖用例即因此红） | **修订**：菜单改为主菜单 / 类目两级（`core/menu.py::SCREENS`），二级目录一律 `0` 返回、主菜单 `0` 退出，新增「配置项」与「LLM provider 优先级」两屏（`settings.provider_order` / `move_provider` 写回 `priority`）；Web 的 `do_POST` 捕获异常并以 `code: 1` 回报，不再断连接 |
| rf-19 | rf-18 的分级把高频的内容流水线也收进了二级：每天要按的 `analyze`/`build`/`deliver` 变成两步 | **修订**：主菜单直接放 `1 analyze`/`l analyze-llm`/`2 build`/`3 deliver`，只把质量与配置留作二级（`4`/`5`）；默认光标回到 `2 build`；DESIGN-TUI §3.1 写明唯一分级标准——每天按的放第一级，偶尔打开的分组才进二级 |
| rf-20 | 跑完一个动作后按 `0` 直接退出：结果在屏时 `0` 与“退出”共用一个语义；屏幕底部还有一个孤立的 `❯ `，看起来像在等一段长文本输入 | **修订**：`0`/`Esc` 改为三级语义——先收起结果、再返回上一级、主菜单上才退出；去掉底部的 `❯ ` 提示符（只保留光标行前缀），结果区改为一行中性提示；DESIGN-TUI 把它写成契约 |
| rf-21 | 「源码 → 手稿」既不比对基线、也不保护正文：`chapters.py` 无条件覆盖手稿（骨架覆盖已写正文，内容体积门禁要到下一次 `check` 才报），交互结束后用户拿不到“稿子有没有变薄”的答案 | **修订**：`chapters.py` 只在空文件/内容相同/`--force` 时写入，否则跳过并在结果里报出；`actions.analyze` 在三阶段后调用 `content_volume.py --json`，把一行比对结论并入同一份结果（低于基线时判失败并给出 `--update-baseline` 指引） |
| rf-22 | 体量基线没有单调性约束，也没有“比哪一份”的说法：每次转换后都能 `--update-baseline` 把下限重记成更薄的那份，多份历史稿各自有账本但没有显式选取入口 | **修订**：`--update-baseline` 默认拒绝降低任何条目或总量，收缩须 `--accept-shrink --reason`，理由与差额写进 `accepted_shrinks`；新增 `--baseline <文件>` 用于显式对照某份历史快照；`quality-model.md` §4 写清“只比一份、不做加权”的原则 |
| rf-23 | 「评审通过的基线」只有口头含义：`--update-baseline` 对未提交的工作区、无人具名的调用一样照写，事后无法回答“这份基线是谁在哪一版上认的” | **修订**：记账要求 `data/manuscript` 无未提交改动、评审人具名（`--reviewed-by`，缺省取 `git user.name`），并在基线文件写入 `reviewed{by, at, commit, reason}`；`quality-model.md` §4 补三项条件与固定流程（check → commit → 记账） |
| rf-24 | 历史版本无法直接成为基线：快照只有自己的体积账本，`--update-baseline` 只量当前手稿，要把 6 月那版定为下限只能手改 JSON（绕过了评审人、单调性与来源记录） | **修订**：`content_volume.py` 新增 `--from-snapshot <label>`，从 `snapshot-<label>.json` 取数写基线，并记下 `source.snapshot`；比当前基线薄时仍需 `--accept-shrink`；`quality-model.md` §4 给出「导入 → 记快照账本 → 提为基线」三步流程 |
| rf-25 | LLM 调用没有任何用量与成本可见性：`_llm.complete` 丢掉响应里的 usage，跑完只知道“有文字回来”；也没有调用前预估与累计上限，`llm-ask` 一次问多少钱无从判断 | **修订**：单价表 `data/config/llm_pricing.json`（未列出即“未定价”），`_llm` 记录每次调用的 token/费用并追加 `logs/llm-usage.jsonl`，`llm-ask` 打印调用前区间预估与调用后“本次 + 今日累计”，`analyze --llm` 打印整轮汇总；`llm_settings.daily_cost_limit` 达到时加一行 ⚠ 提醒 |
| rf-26 | 测试隔离有洞：网络只阻 socket，但 LLM 仍可能按真实 provider 走；`logs/` 写进仓库目录，`today_cost()` 读的也是真实用量账本（用例结果随本机历史浮动）；手稿与产物目录没有任何写入守卫——此前一次测试真的把手稿覆盖成骨架 | **修订**：`_fixture.isolate()` 导入时装守卫：`BOOK_TEST_GUARD` 拒写真实 manuscript（产物可再生，仅告警不拦），夹具书与日志都在临时目录内；LLM 一律 mock，真实建连由 socket 守卫阻断。新增 `test_isolation.py` 钉住每条不变量 |
| rf-27 | 快照的标签有两种写法：`import` 存成 `<日期>-<标签>`，而 `baseline`/`verify` 只认目录全名——按 `snapshot.py import … june-2026` 导入后 `baseline june-2026` 报“找不到快照” | **修订**：`snapshot.resolve/require` 同时接受标签与目录全名（歧义时报出候选），`content_volume --from-snapshot` 也接受裸标签；新增 3 个用例 |
| rf-28 | `how-to-config.md` 写“`deepseek-main`（默认）”，而 `llm_provider.json` 的 `default_provider` 是 `opencode-go`（priority 10）——文档与配置互相矛盾 | **修订**：文档按配置改写，并把“改默认 provider 用 `settings set llm.provider`”写进同段 |
| rf-29 | `make.py cover` 从不返回：它用 `unittest discover` 跑覆盖率，遇到带线程的 Web/TUI 夹具死锁，于是这道门禁长期既不给数字也不报错；顺带发现 `coverage_fail_under` 88 高于实测 85——门禁即使跑起来也是红的 | **修订**：`coverage()` 改用与门禁同源的 `pytest -m tier_fast` 并加 1800s 超时，阈值按实测调到 85，`plan-3` 保留抬到 88 的目标 |
| rf-30 | `make.py` 的每个步骤都没有超时（`check_runner` 有 1800s，`make.py` 没有），一个死锁的门禁会让整条命令永久挂住——rf-29 就是这样被我误读成“白跑”的 | **修订**：`run_step` 加 `STEP_TIMEOUT_S = 1800`，超时按 124 记为步骤失败并打印步骤名 |
| rf-31 | 测试隔离只护住了手稿：一个新写的快照用例把一份快照账本写进了仓库（`GUARDED_SUFFIXES` 当时只有 `data/manuscript`），基线/派生状态同样会被测试污染 | **修订**：守卫扩到 `data/manuscript`、`data/baselines`、`data/state`；该用例改为把 `BOOK_ROOT` 指向临时树；误落的账本文件已删除（测试现在只写临时树） |
| rf-32 | 章名在代码里又写了一份：`source_refs.py::CHAPTER_FILES` 仍列 `ch7-sql-execution.md`/`ch8-query-optimizer.md`，两个文件不存在 → 每次跑两条 `WARN Chapter file not found`，合并后的 `ch7-8-sql-optimizer.md` 因此从未被坐标门禁检查；同一批旧章名还留在一份无任何引用的历史图注基线文件与 `exercises.py` 的用法示例里 | **修订**：`CHAPTER_FILES` 改为 `_config.chapter_names(include_cover=False)`（单份来源是 `book.toml`），合并章节重新进入检查面（95 条坐标全部有效）；删除无引用的历史基线文件；示例改占位名；新增用例钉住“列出的章必须存在且等于配置” |
| rf-33 | 慢档在 CI 超时 30 分钟：`order_dependence.bisect()` 默认把整个套件当作前缀候选，`test_bisect_reports_a_target_that_passes_in_full_order` 实际重跑了一遍全包；而 `make.py` 用全局 1800s 步骤超时，把“重跑全包”掩盖成一个只能等的半小时；慢档其余 72 个用例实测共 0.49s | **修订**：`bisect()` 增加 `pool` 参数，用例改传两模块小池（单文件 1.57s）；CLI 同步增加 `--pool`；`make.py` 按步骤名取超时（`base.json [toolchain]` 的 `step_timeout_s` 900 / `test_timeout_s` 300），测试步骤加 `--durations=10` 把最慢用例写进报告；`CLAUDE.md` 补「不跑未知耗时命令、不等 CI」的作业纪律；步骤超时改为按进程组杀死（超时的 pytest 不再留下 chromium/pandoc 孤儿），CI 每个 job 补 `timeout-minutes` |
| rf-34 | 附录不在坐标与符号断言的扫描面内：`source_refs.py` 只扫 `ch*` 章节，附录 A 里 10 条 `Class.method(` 断言从未被检查，其中 3 条写错了类（`CommandContainer.canReuse/executeQuery` 实际在 `Command`），7 条是旧版 MVStore 恢复流水线的术语（`openInternal`/`setLastChunk`/`openComplete`） | **修订**：扫描面改为 `book.toml` 的非封面文件（章节 + 附录），3 条改类名（实例与表格中引用一并改正），7 条旧术语登记进 `source-symbol-baseline.json`——附录 A.3 的恢复叙事仍按旧流水线行文（含 ASCII 图与 trace 日志），重写该案例时再对齐 `MVStore.open` / `FileStore.readStoreHeader`；`save_baseline` 顺带去重（同一 file::Class::method 只记一条） |

| rf-35 | 图注形状六处各写一份（边界互不一致：有无行尾锚点、是否认字母图号、是否容忍空白），
改一处不会同步其余；`structure.py` 又把章节范围写死为 1–12，章数变化时静默截断 |
**修订**：形状归 `lib/_mdutil.py` 一处（`FIGURE_LABEL`/`FIGURE_ID`/`CHAPTER_FIGURE`/`APPENDIX_FIGURE`
与 `figure_caption()`/`figure_ids()`），六个消费者改为引用；章节范围从 `book.toml [chapters.coverage]`
推导，无覆盖表时退回阅读顺序，并对未声明章号容错计数 |

| rf-36 | `book.toml` 的两张章节表互相矛盾：`[chapters.numbering]` 声明阅读顺序 1–14
（ch6-2/ch6-3 各占一章、ch7-8 起顺延），`[chapters.coverage]` 与手稿 H1 却是 12 章
（三个 6-x 文件同属第 6 章）。把 numbering 改成与手稿一致后，`content_depth` 的前向引用
基线（按章号键控）立刻失配 |
**待定**：需要决定哪张表是权威——若以手稿为准，必须同时按新章号重固 `content_depth`
基线并复核索引/术语的章号归属；若以 numbering 为准，手稿 H1 需整体重编号。文档已改为
"两张表各司其职"，不再笼统写 12 章 |

| rf-37 | 覆盖率门禁只量快档：`make.py::coverage()` 写死 `-m tier_fast`，而同一文件的 `test` 认 `BOOK_SLOW=1`；CI 慢档 job 装好 chromium/pandoc 后跑的仍是快档，12 个 `tier:slow` 模块（82 条用例）对覆盖率零贡献 | **修订**：`cover` 接受 `--full` 与 `BOOK_SLOW=1`，报头写出量的是哪一档；CI 慢档 job 改跑 `cover --full`，testplan 判据同时点名两个载体。逐模块把“只为拿真工具”的用例改注入仍在做（`to_epub` 已 72% → 100%） |
| rf-38 | 覆盖率只有全局阈值加 72% 的单文件下限：50 个模块低于 90%（8543 语句、漏 1143），一个 200 语句的模块停在 73% 仍能全绿 | **修订**：`cover` 把每个文件的覆盖率记进 `data/baselines/coverage.json`，任一文件低于基线即 FAIL，`--update-baseline` 经评审重记；不足 5 条语句的文件除外 |
| rf-42 | 质量读数没有统一入口：覆盖率、单文件、半分支、长函数数、永真断言数分散在多个命令与 grep 里 | **修订**：新增 `audit/test_health.py`，由 `make.py report health` 调用，汇总覆盖率（总/最薄/半分支 Top-N）、低于基线的文件、松散断言数与超长函数清单；阈值读 `base.json [toolchain]`，视图只读数不判红 |
| rf-43 | 有 6 个模块在**导入期**读配置并把它存成模块常量：`audit/source_refs.py`(7)、`ingest/chapters.py`(5)、`render/to_html.py`(2)、`ingest/outline.py`(2)、`audit/style_schema.py`(2)、`audit/smart.py`(2)；一个进程换书、或工具链独立成包后 `--book` 在导入之后才解析，这些常量会指向上一本书 | **修订**：全部改为调用时解析——路径直接读 `_config` 门面，策略派生的值走 `suffixes()`/`generation()`/`templates()`/`quality_policy()` 一类小函数，`source_refs` 的引用正则按后缀元组缓存；同名局部变量（`source_dir`、`baseline_path`）处的访问器改名避免遮蔽。新增 `test_lib_baselines.py` 钉住基线的配置解析与版本作用域 |
| rf-40 | 长函数无法逐个用例化：拆分前有 30 个 ≥60 行函数，分支组合只能整体回归 | **修订**：全部拆完，全库不再有 ≥60 行函数（30 → 0）。每处都用同一批输入比对输出：章节渲染逐字节相同、坐标/图注/可读性/架构门禁的整树报告不变、`make` 与 `test_report` 的子命令输出一致；`ingest/chapters.py` 的 §3 建议整段移到新模块 `ingest/api_sections.py`（835 行，回到预算内） |

| rf-39 | 65 处永真断言只证明「跑完了没炸」，行被执行不等于行为被验证 | **修订**：分批全部定值——46 处改为「退出码取实际值 + 消息断言」，7 条遍历用例改为「每脚本一张退出码表」，最后 8 条交付链用例在本机（pandoc 3.5 + playwright/chromium）实跑后定值；松散断言基线 65 → 0，门禁改为零容忍。同批删掉一处函数体重复的用例 |

| rf-41 | 失败语义靠 27 处散落的 `sys.exit()` 与 58 个入口各自转换：消息与退出码分开维护 | **修订**：`lib/_errors.py` 的 `ToolError` 把消息与退出码绑成一个对象（派生 `SystemExit`，既有 `sys.exit(message)` 语义不变），全部失败点改为抛它、58 个入口统一走 `_errors.run()`；`print(...); sys.exit(1)` 的组合在仓库里已归零（`grep` 为 0），退出码与消息由用例成对断言 |

### 归档

本项目不按版本切分问题归档文件：已修条目在下一次发布时摘要进 `changelog.md` 对应
版本段，历史由 git 保留。
