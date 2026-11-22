# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**版本变更记录，只留当前开发段**——写“变了什么”；问题编号与修复细节见
> `review-findings.md`，设计理由见 `technical.md`。已发布版本由 git 标签保留。

---

## [0.1] - 开发中（未发布）

### 变更

- **测试用例审计**：1102 个用例逐项核查——冗余/空断言/遮蔽由 `test_redundancy` 判定通过，
  layer 标签与导入层 0 处不一致，tier 分类已由 `HAS_PANDOC`/`SLOW` 守卫正确表达；
  命名与内容不符的 10 处改名（如 `test_basic` → `test_slugify_keeps_the_chapter_heading`、
  两个同名 `test_coverage_mode_runs` 按 glossary/index 区分）；另修 `test_audit_diagrams_layout.py`
  的 `__main__` 守卫夹在类中间、直接运行只跑第一个类的问题。

- **重生成不再把判断全推给人**：`chapters.py` 对已有章节的默认行为从“跳过”改为“**只刷新事实块**”
  ——标记块内按源码更新，块外一字不动；无标记块时才跳过并说明；`--force` 才是整篇重写（旧文件
  备份到 `data/tmp/`）。同时 `digest.py` 保留 `source-inventory.prev.json`，渲染前先说一句
  “源码清单与上次一致/已变化”，界面上的 `analyze-llm` 确认文本也写明“回答 n 则只刷新事实块”。

- **管理文档职责归一**：配置分层只在 `technical.md` §3.1 定义（四层：`book.toml` /
  `base.json` / `style.json` / `language/zh.json`）；门禁级别只在 `testplan.md` §2.1/§2.2
  声明；管理文档头只取软件版本（`lib/_version.py`）；章节清单只以 `book.toml` 为准。删除 `folder.md` 里
  已不存在的"两层 + `config.json`"说法与 `plan.md` 的概述式复述。（rf-1）
- **`book.toml` 死键修复**：`[chapters.packages/titles/numbering/coverage]` 中指向
  `ch7-sql-execution.md`、`ch8-query-optimizer.md` 的键合并为 `ch7-8-sql-optimizer.md`，
  包归属、标题、编号、覆盖一次对齐到阅读顺序。（rf-2）
- **附录口径统一**：12 个章节槽 + 2 个编号附录（A/B）；术语表、概念索引、参考文献
  作为后件（题为附录 C/D/E），不占章节编号。`requirements.md` §2、`technical.md` §1、
  `testplan.md` 三处改为同一口径。（rf-3）
- **`plan.md` 改为计划项清单、新增 `review-findings.md`**：计划项用 `plan-N`、
  问题用 `rf-N` 两套递增编号；计划项按 P1–P4 分档并给出"现状 / 动作 / 验收 / 事实位"，
  问题记录按优先档分组并登记文件膨胀。（rf-4）
- **`content_depth` 归属模型**：一个手稿文件可贡献多个 H1 章号，包归属按章号集合判定，
  提前引用只要点名其中任一章即视为有路标。（rf-5）
- **管理文档口径互查**：`deliver` 链路按编排层实写（`to_pdf` → `pdf_toc_links` →
  `verify_pdf` → `to_epub` → `verify_epub`）；印刷版 PDF 统一为"交付阶段按需单独生成"；
  门禁级别只取 P0–P2 并在 §2.1/§2.2 声明；延伸思考只针对 12 章；`print_pdf.py` /
  `to_epub.py` 补全 `render/` 路径；"三处呈现面（终端/网页/成书产物）"与"三个渠道
  （CLI/TUI/Web）"分开表述；启动器名统一为 `bookctl`。（rf-7、rf-8）

- **测试隔离加固**：`_fixture` 导入时装守卫——写真实 `data/manuscript` 直接拒绝（`BOOK_TEST_GUARD`）；夹具书、日志与 LLM 用量账本都只落在临时目录；LLM 用例全部 mock，真实建连被 socket 守卫阻断。新增 `test_isolation.py`。（rf-26）
- **快照标签与费用配置可写**：`snapshot.py verify/baseline` 与 `content_volume --from-snapshot` 同时接受裸标签与日期目录名（歧义时报候选）；`settings` 新增两项可写键 `llm.daily_cost_limit`、`llm.ingest_prose`（布尔/数值校验，缺键时自动补段落）。（rf-27、plan-8）
- `how-to-config.md` 的默认 provider 描述按 `llm_provider.json` 实际值改正。（rf-28）
- **TUI 首页显示用量与余量**：新增 `lib/_volume.py`（只读测量手稿与基线，不含判定），状态行下多一行`LLM 今日 ≈ x / 上限 y` 与 `体积余量 +z%`；无基线或无上限时显示 `—`。`DESIGN-TUI` 增加「用量行」，`settings.summary()` 提供这两个字段。（plan-8）
- **覆盖率门禁可用**：`make.py cover` 改用与门禁同源的 `pytest -m tier_fast` 并加超时（原 `unittest discover` 在带线程夹具上死锁，门禁长期静默）；阈值按实测 85 取下限，抬回 88 的目标留在 plan-3。（rf-29）
- **派生状态与基线核对**：重跑 `digest/outline` 重建 `data/state`（58 包 / 843 文件），outline 的包归属与 `book.toml [chapters.packages]` 逐章比对 0 处不一致；五道基线门禁 stale 均为 0，无需收缩。（plan-1、plan-2）
- **新增 Kotlin / Go 语言适配器**：`ingest/languages/kotlin.py`（`package` 行、类型与 `fun`、`import` 依赖）、`go.py`（每目录一包、导出即大写、`import` 块解析），注册进 `ANALYZERS`，`detect()` 改为从注册表推导后缀（不再维护第二份映射）；新增迷你夹具与 5 个用例。（plan-7）
- `make.py` 的每个步骤加 1800s 超时，超时按 124 记为步骤失败（rf-30）。
- **覆盖率 +1 档**：新增 `test_manuscript_snapshot_flow.py`（导入/校验/账本/列表全流程），实测 85% → 86%，`coverage_fail_under` 同步抬到 86；下一步目标 88，缺口集中在 `check_runner.py` 与 `structure.py`。（plan-3）
- **隔离守卫扩到基线**：`BOOK_TEST_GUARD` 现在同时拒绝写 `data/baselines` 与 `data/state`（一个新用例曾把快照账本写进仓库）。（rf-31）
- **事实块可原地刷新**：`chapters.py` 给包表、类型表、坐标与依赖方向这类可重算的块加 `<!-- generated:<块名> -->` … `<!-- /generated -->` 标记，新增 `--refresh-facts` 只替换标记块（块外一字不动，无标记块的文件跳过并说明原因）；`--force` 覆盖前先把旧文件备份到 `data/tmp/generated-backup/<时间戳>/` 并打印 `-a/+b` 行数。`actions.analyze` 增加 `refresh` 参数透传，CLI（`--refresh-facts` / `--force`）、TUI（配置屏 `6 刷新事实块`）、Web（`{"action":"analyze","refresh":true}`）走同一条路径。（plan-9）
- **坐标门禁重新盖住合并章节**：`source_refs.py::CHAPTER_FILES` 不再手写章名，改为读 `book.toml`——此前它还列着已合并掉的 `ch7-sql-execution.md` / `ch8-query-optimizer.md`，每次跑报两条 missing 警告，而 `ch7-8-sql-optimizer.md` 从未被检查；同时删掉一份无任何引用的历史图注基线（其内部键全是旧章名）。（rf-32）
- **计划表对齐事实**：`plan.md` 删去已记账完成的 plan-1 / plan-2，在办项回到 4 项（plan-3/4/5/6），不再列已归档的 plan-7。
- **慢档不再无限等**：`order_dependence.bisect()` 增加 `pool`（默认仍是全包，但要重跑全包必须显式选择；用例与 CLI 均用小池），慢档实测从 30 分钟超时回到秒级；`make.py` 的超时改为按步骤取配置（`base.json [toolchain]` 的 `step_timeout_s` / `test_timeout_s`），测试步骤加 `--durations=10`，最慢用例直接出现在报告里；步骤超时改为按进程组杀死（超时的 pytest 不再留下 chromium/pandoc 孤儿）；CI 每个 job 加 `timeout-minutes`，远端也不会再挂半小时。（rf-33）
- **正文渲染按章缓存**：`render/html_cache.py` 把正文按 H1 切片做成内容哈希键的缓存（键含渲染器源码哈希，改渲染器自动失效），`to_html.py --full` 可强制全量；目录/锚点/章编号在切片前已定稿，所以复用旧片不会改一个字节（实测全量与缓存的产物 sha256 相同）。单章改动只重渲染 1 片，`to_html` 步骤 169ms → 130ms。（plan-5）
- **附录纳入坐标门禁**：`source_refs.py` 的扫描面改为 `book.toml` 的非封面文件，附录 A 的 44 条坐标（0 missing）与 10 条 `Class.method(` 断言从此受同一套规则管；其中 3 条写错类（`CommandContainer.canReuse/executeQuery` → `Command`）已在正文改正，7 条旧版 MVStore 恢复术语入基线（附录 A.3 仍按旧流水线行文，重写时再对齐）；`save_baseline` 改为去重。（plan-10 / rf-34）
- **覆盖率 +1 档**：新增 `test_check_runner_branches.py`（步骤命令表、变更域分类、运行摘要与超时）与 `test_audit_structure_levels.py`（门禁分档、图号乱序、缺合并稿、非法 UTF-8），`check_runner.py` 69% → **97%**、`structure.py` 82% → 84%，总量 86% → **87%**，`coverage_fail_under` 同步抬到 87；剩下的到 88 需 PDF 夹具（`verify_pdf.py` / `pdf_toc_links.py`）。（plan-3）
- **图注形状与章节范围各只有一份**：图注 `**图 X-Y: 标题**` 的形状原来在 6 个 audit 模块里各自
  为正则（`structure`/`figures`/`captions`/`figure_clusters`/`smart`/`readability`），边界已互不一致；
  现统一到 `lib/_mdutil.py` 的 `FIGURE_LABEL`/`FIGURE_ID`/`CHAPTER_FIGURE`/`APPENDIX_FIGURE` 与
  `figure_caption()`/`figure_ids()`，消费者只引用形状。`structure.py` 的章节范围不再写死 1–12，
  改为从 `book.toml [chapters.coverage]` 推导（无该表时退回阅读顺序）。（rf-35）
- **LLM 动作不再“默默不调用”**：已有正文时 `chapters.py` 会全部跳过，导读/小结的润色点不会执行，
  原先只显示“本次未调用”。现在零写入时 `chapters.py` 说明原因，`actions.analyze` 在零调用时追加一行解释；
  TUI 的 `analyze-llm` 先问“是否 `--force` 重写已有正文”（默认否，旧文件备份到 `data/tmp/`），
  结果行标注 `--force`。同时修掉渲染器在“本章无映射包”时的越界崩溃。
- **测试报告与归档**：新增 `test_report.py`（`run`/`last`/`list`/`prune`），每次运行把结果写成
  `books/test-reports/<时间戳>/`（`report.json`、`report.md`、`junit.xml`、`pytest.log`）并更新
  `latest.json`；`last` 解出最新报告的失败用例（跳过不计）并给出重跑命令。新增
  `manuscript/archive.py`：构建与交付各存一份手稿/产物到 `data/archive/<书>/<日期>/`，保留窗口取
  `base.json [archive] retention_days`（默认 45 天）。两者均 gitignore，不参与构建。
- **覆盖率与断言强度各推一档**：新增 `test_render_verify_pdf_branches.py`（pypdf 合成 PDF 驱动
  尺寸/旋转/字体未嵌入/大纲/目录链接/越界标注等分支），`verify_pdf.py` 14% → 75%、
  `pdf_toc_links.py` 32% → 87%，总量 87% → **89%**，`coverage_fail_under` 抬到 **88**；
  `make.py cover` 新增单文件覆盖率下限（`coverage_min_per_file`，默认 60），防止新模块
  零测试混进总量；`test_redundancy.py` 新增 `LOOSE-ASSERT`：接受成功与失败两种退出码的
  断言只登记存量（112 条进 `data/baselines/loose-assertions.json`），新增即失败。
- **`CLAUDE.md` 去重与纠错**：删掉不存在的 `audit/doc_traces.py` / `audit/code_traces.py`（真实脚本是 `audit/traces.py`，一个脚本两个范围），命令块改用 `bookctl` 而不是裸 `python`（工具链只允许项目虚拟环境），`build`/`deliver` 的描述与编排表对齐（含归档），`Where to Look` 里把"命令"拆成使用与验证两处所有者，并把"测量—再跑最小命令"、"不做前台长任务 + 不并发"各自合并为一条。
- **`CLAUDE.md` 改为中文**：内容与结构不变，术语与本仓库其余文档统一（命令走 `bookctl`、证据目录、追踪编号边界、工作节奏五条），措辞避开 `traces` 判据里的过程类词汇。
- **工具链定位写清**：`CLAUDE.md` 把 `books/` 描述成“通用的源码分析成书工具链 + 它正在服务的
  这本书”，并写明换书只需改 `base.json [sources]`、加语言只需加适配器、新书用 `bookctl new`；
  顺带把 `README.md` 与 `how-to-config.md` 的语言清单从三种补齐到 java / python / rust /
  kotlin / go。
- **`CLAUDE.md` 只留“这一层才有的判断”**：删掉与 `books/README.md` / `testplan.md` §1 重复的命令块，
  改为“去哪读”索引；保留两块独有内容——工作节奏（先量后跑、单重活、看报告调试、CI 独立、
  改完就发）与编辑边界（配置/手稿/产物/证据目录/追踪编号）。这样文档改版时不必回来同步。
- **覆盖率 88% → 90%，棘轮抬到 89**：新增 `test_gate_error_branches.py`（体积门的下落/产物下限/
  快照账本/脏工作区拒绝记账、设置项的未知键与栏杆校验、版本门的封面与书名冲突）与
  `test_lib_baseline.py`，并补了快照流程的错误分支；`content_volume` 66%→84%、
  `version_consistency` 79%→87%、`settings` 78%→91%、`snapshot` 68%→75%。单文件下限从
  60% 抬到 **70%**。
- **修两处真缺陷（测试写出来才暴露）**：`lib/_baseline.py` 的 `load()` 遇到损坏的基线文件会以
  `SystemExit` 打死门禁（`except Exception` 抓不到），现改为直接 `json.loads` 并捕获
  `OSError/ValueError`；`save()` 把**目录**传给 `ensure_dir()`（它要的是文件路径），
  `data/baselines` 不存在时写入直接失败。
- **渲染器拆分第一步：样式表独立**：`render/to_html.py` 842 → **557 行**，CSS（284 行）迁到
  `render/html_shell.py`；`dist/*.html` 的 sha256 与拆分前**逐字节一致**（`edef814e…`），
  也就是这次只是搬动文本、没有改行为。`to_html.py` 已不在膨胀登记表里（557 行，远低于提醒线），
  `technical.md` §4.4 补上 `html_shell.py` 一行。
- **渲染器拆分第二步：附录独立**：附录的坐标表与练习从 `ingest/chapters.py` 迁到
  `ingest/appendix.py`，表格排版上提到 `lib/_mdutil.table()` 供两处共用；`chapters.py`
  806 → **750 行**。验收用渲染结果哈希：改动前后所有章节与附录的渲染文本
  sha256 完全一致（`13f8976f…`）。
- **松散断言收紧第一批**：`test_manuscript_builders.py` 的 8 条退出码断言钉到精确值 + 输出断言
  （`glossary --check/--validate/--coverage`、`index --hierarchy-check/--coverage`），基线从
  84 条降到 **76 条**；其中 `test_multi_line_entry_is_parsed` 原来跑的是**起草**模式（根本没解析
  既有词条），改为 `--validate` 并断言 `Entries: 1`，名字与行为对齐。
- **松散断言收紧第二批**：`test_audit_scripts.py` 的 5 条钉到精确值 + 输出（`glossary.py` 与
  `index.py` 的默认/检查模式、`--hierarchy-check`、缺源码树时 `source_refs.py` 的 `[skip]`）；
  基线从 76 条降到 **71 条**。剩下的多数是"坏输入下不得抛异常"的负向冒烟——0/1/2 都是合法结果，
  已在基线注里写明这类为何不钉死。
- **plan-3（覆盖率棘轮）达成并归档**：88% 的目标已在分支口径下达成并成为红线。
- **覆盖率改为分支口径**：`make.py cover` 改用 `coverage run --branch`，棘轮按**分支覆盖**的
  总百分比判定（实测 88%，阈值同步为 88）；`technical.md` §3.2 写明这个数字现在是
"行 + 分支"口径，单文件下限 `coverage_min_per_file` 保持 70%。以前只看行覆盖，写了的
  `if` 另一半从没走过也算绿；现在不会。
- **一轮技术债核查**：删掉 `test_redundancy.py` 里已无人调用的 `loose_assertions()`；
  `book_quality` / `prose_quality` / `style_rules` 三份一模一样的章节收集器合并为
  `_config.chapter_files(include_cover=False)`（章节清单的单份来源），遍历顺序因此与阅读顺序
  一致；`style.py` 不拆的理由补进 `technical.md`（13 个检测器共用一份状态）。
  核查结论：新模块（`html_shell`/`appendix`/`test_report`/`archive`）无内联仓库路径，
  配置无死键，`make.py check` 与快档全绿。
- **快照可直接取自归档目录**：`snapshot.py import` 现在既接受 zip，也接受目录树（例如
  `data/archive/<书>/<日期>/manuscript`）——两者职责不同但数据形态相同，把某天的归档提为
  对照点不必先打包；目录来源的 manifest 用内容摘要代替 zip 哈希。`folder.md` 与
  `technical.md` 同时写明两个目录的分界：`data/archive/` 是自动滚动保险（含产物、45 天、
  gitignored），`data/snapshots/` 是人工挑选的永久对照点（入库、供体量基线引用）。
- **文档跟随本轮改动**：`plan.md` 移除已达成的覆盖率棘轮项（在办回到 2 项：语言包扩展、图示升级）；
  `scripts-and-reference.md` 与 `quality-model.md` 的 `snapshot.py import` 用法补上"目录也可"；
  `folder.md` 新增 §3.1 讲清 `data/archive/` 与 `data/snapshots/` 的分界（谁写、存什么、留多久、
  入不入库、谁读、怎么提为对照点）。
- **去掉文档与注释里的时间性措辞**：`requirements.md` 的"上一版已认可基线"改为"已认可的体量基线"，
  `plan.md`/`testplan.md`/`style-guide.md` 里"不再…"的表述改为直接陈述当前规则；
  `doc_drift.py` 两处 `used to be compared` / `no longer exist`、`source_refs.py` 一处同类注释、
  `content_volume.py` 的"原来的下限"一并改成现在时——文档只描述当前状态，历史留在 git 与本文件。
- **结构门与坐标门的配置型分支**：新增 `test_gate_structural_branches.py`——无覆盖表时按阅读顺序
  推导章号、必备段落为空时的退化路径、章节位置被目录占住时的 `cannot read`、索引缺失、坐标基线
  损坏时仍能跑完、`--prune` 收缩；这批用例在夹具书内自建一棵迷你源码树，不再借用临时目录的
  上级路径（那会让别的用例也看见源码树）。
- **交付脚本的分支用例 + 单文件下限 70% → 72%**：新增 `test_render_script_branches.py`——
  `pdf_from_html` 用可注入的假引擎驱动渲染（`file://` 入口、A4、返回标题），`parse_headings`、
  缺 HTML 时的拒绝；`to_epub` 跑通一次真实构建；`verify_pdf` 的超体积、无印刷目录、大纲比标题深、
  标注指向错页、Type0 字体未嵌入、畸形矩形。`pdf_from_html` 73→79%、`verify_pdf` 72→73%、
  `to_epub` 72%。
- **变异测试试点 + 形状采样用例**：对 `lib/_mdutil.py` 做了一次零依赖变异（翻转比较符与布尔量，
  共 3 个变异体 × 跑该模块用例）：全部存活，逐个看过是**等价变异**——两个是 `in_fence = True`
  的状态初值、一个是代码跨度分支（`index % 2 != 1`），而该分支在纯 ASCII 代码跨度上本就不改变
  输出。结论：这个小模块的断言密度够用，变异试点不作为门禁，只在怀疑断言空洞时手动跑。
  同时补了生成式形状用例：`slugify` 20 个标题的稳定性与小写、`figure_caption` 12×5 组合往返、
  代码跨度与链接在中英混排中保持原样。
- **负向冒烟用例不再只验"不崩"**：`test_edge_cases.py` 的 6 条从 `(0,1,2)` 钉到实测结论——空章节跑
  `structure` 为 1、`links`/`captions` 为 0；零字节章节与 CRLF 让 `merge` 仍产出文档（0）；
  BOM 章节跑到汇总行（1）；超长行 `readability` 为 0 且报 `READABILITY`；缺状态文件 `chapters` 为 1。
  松散断言基线 71 → **65** 条。
- **报告器加了两个观测点**：`test_report.py run --coverage` 会在报告目录旁再存一份 **per-file 覆盖率快照**
  （分支口径），单文件下滑而总量仍绿时看得出来；快档用例耗时 ≥ 1s 会被标成预算提示，
  提醒它该优化或改标 `tier:slow`。覆盖率命令的源码路径改为从配置推导，不再写死 `books/`。
- **复杂度阈值试评估**：用 `ruff --select C901 --config max-complexity=15` 扫全仓，**15 个函数**超过
  15 个分支（`structure.py`/`style.py`/`chapters.py`/`test_report.py` 的 `main` 等）。直接设为门禁
  会把现有代码判红，而没有基线机制前只能大改；因此**暂不作门禁**，留作重构时的排序依据——
  需要时用 `test_redundancy` 那套"存量登记 + 新增即失败"的做法接入。
- **`style.py` 检测器改为表驱动用例**：新增 `test_audit_style_detectors.py`，每条规则一行"触发文本 / 干净文本"
  （冗余副词、空泛修饰、超长句、被动滥用、"的"堆叠、句式单调），并断言围栏内文本不被判——
  这张表同时充当规则的说明，改词表时用例先红。
- **pyright strict 试评估**：把 `books/src/python/lib` 设为 strict 后一次扫出 **522 个类型错误**（自动
  生成的配置读取、字典解包、`Unknown` 传播为主）。直接开会让类型门禁长期红，且一次性修完会把
  本轮改动面扩大到不可评审；因此**暂不开 strict**，记录为"要开就先按文件登记存量"的待办——
  与松散断言、C901 使用同一套"登记存量、新增即失败"的接法。
- **`data/state/` 的说明与事实对齐**：`folder.md` 原写“派生状态、不入库”，实际
  `source-inventory.json` 与 `outline.json` **在库**——`content_depth`/`source_refs` 在全新检出上
  也要能跑（实测删掉清单后 `content_depth` 直接报 21 处），所以这两个文件必须随仓库走。
  新增的 `source-inventory.prev.json`（只用于告知源码是否变化）已进 `.gitignore`，并在目录树里
  标明三者各自的用途与读者。
- **基线目录清理**：删掉三个不再有读者的文件——一份只有 `ch1.md` 的测试遗漏账本（`rf-31` 说已删，
  但它又出现了）、`snapshot-june-2026` 的裸标签副本（与日期全名那份内容重复），以及 v5.0 的
  `balance` 手动快照（`balance.py --baseline` 随时可重生成，且书名版本已到 6.5）。剩下的 9 份
  各有明确读者：六份经 `base.json [baselines]` 配置，两份是按日期命名的快照体积账本，一份是
  松散断言登记表。
### 门禁
- 阈值继续回配置：`style.json [clusters]`（图簇张数与行距）、`[quality]` 的 `min_figures_per_section`/
  `min_figure_coverage_pct`、`base.json [toolchain]` 的 `pdf_page_width/height/tolerance`；
  `smart.py`、`figure_clusters.py`、`structure.py`、`verify_pdf.py` 改读配置——此前图簇窗口在
  `make.py`（50）与 `structure.py`（40）里不一致，两道门禁查的不是同一个口径。（rf-16）
- 书名字面量清理：`_config` 的兜底与三个渲染脚本 docstring 改为通用表述，`book.toml` 是唯一来源；
  `check_architecture` 新增书名字面量检查，防止回流。（rf-16）
- 包装脚本帮助与实际动作对齐：`scripts/bookctl` 的帮助注释由 `llm` 改为 `llm-ask`；
  `script_contract.py` 新增 `check_dispatcher_help`，帮助里点名的动作必须在 `core/actions.py`
  的 ACTIONS 表里（或为包装脚本自有动词）。（rf-17）
- 文档跟随配置同步：`how-to-config` 的键一览补 `clusters` 与 `thresholds` 两段、并写明页面几何在
  `toolchain`；`style-guide` §13.6 与 `scripts-and-reference` 的图簇说明改为“取值见配置”。（rf-16）

- `doc_drift.py` 新增两项检查：`CONFIG`（`book.toml` 各章节表的键必须都在阅读顺序里）、
  `LEVEL`（门禁级别只在 `testplan.md` §2.1/§2.2 的表格里声明）；章节名检查不再要求
  反引号包裹，目录树里的文件名同样算数。（rf-6）
- `version_consistency.py` 要求管理文档头齐全且等于软件版本，并核对工具 / 源码 / 书籍三处版本；
  `doc_drift.py` 不再重复判同一事实。
- `content_depth.py` 的 `owner_map` 返回章号列表，`--update-baseline` 因键控口径变化
  重新固化一次（63 项）。
- `doc_drift.py` 再补三项：`INDEX`（管理目录与 `README.md` 索引表、`folder.md` 目录树
  双向对齐，重复登记也报）、`NUMBERING`（`plan-next`/`rf-next` 必须等于已用最大 +1）、
  路径检查扩到 `src/` 等书籍内路径（此前 `src/test/*.py` 这类引用漏检）。
- `doc_drift.py` 兼校被引用的实现清单：`DELIVER`（文档里的 `deliver` 步骤序列必须等于
  `make.py` 的编排组）、`PREFIX`（文档写的 `scripts/` 前缀白名单必须等于
  `check_architecture` 的 allowlist）。
- **管理文档角色归一**：14 份统一在头部写一行 `> 定位：负责什么 / 不负责什么 / 权威在哪`
  （`doc_drift` 新增 `LOCUS` 检查）；问题台账改 H1–H3 + 登记档，与 `plan.md` 的时机档
  P1–P4 分开命名；`folder.md` 只留归属，合并规则指向 `technical.md` §3.1；练习与跨章引用
  细则只在 `style-guide.md`。（rf-11）
- **内容标准与写作规则分轴**：`analysis-doc-standard.md` 只回答“必须有什么”（章节骨架、
  阶梯、事实、图示、术语、练习、四项人工自查），写法一律指向 `style-guide.md`；
  判据、级别与门禁改由项目单向登记，标准不再引用任何项目的门禁表、脚本或配置（rf-12）。
- `file_length.py` 兼校「文件膨胀登记」：`review-findings.md` P4 表里的行数与实测不符即失败。
  四档预算还必须在 `style.json [limits]` 里显式声明（`BUDGET`），不再隐式靠默认值。
- 阈值回配置：`index_total_min`、`index_per_chapter_min` 进 `style.json [thresholds]`，
  `structure.py` 改读配置；`testplan` 与 `review-findings` 的阈值列不再抄数值，改指配置键
  （此前「手稿附录 ≤2000」与配置的 9000 相矛盾）；段落规则统一为字符口径（≤420 字符）；
  NFR-05 标注性能门禁为 advisory。（rf-13）
- 新增 `requirement_trace.py`：`requirements.md` 的 FR/IR/NFR 与 testplan 新增的
  §2.4 需求判据对照表双向一致，每行点名的载体必须存在；`make.py check` 由 30 步变 31 步。
- **`testplan` 只留判据**：§4 交付形态收缩为按需验收项与命令（渲染参数、版式规格与两个
  写死的阈值移出，分别指向 `technical.md` §4.4 与 `style-guide.md` §6）；§2.2 的「9 项
  CSS 标记」改为「样式与锚点钩子齐备」，删除「脚本语法有效」这条弱判据；§5 不再复述
  §2.2；§6 指向 `quality-model.md` §4 与使用手册。（rf-15）
- 判据只写性质：`testplan` §2.2 的阈值列改为“不低于配置下限”这类表述，键名与取值集中到
  `technical.md` §3.2 的阈值归属；`doc_drift` 新增 `THRESHOLD` 检查，判据表引用配置键
  名即失败。（rf-14）
- 补回 `src/test/test_no_network.py`：testplan 一直把它列为网络隔离的载体，文件已不存在。

### 文档清理

- 命令清单只留两处：`books/README.md`（使用）与 `testplan.md` §1（验证）；
  `folder.md` §4、`plan.md` 不再抄一份。
- 格式约定只在 `testplan.md` §3；`style-guide.md` 末尾的复制块删掉并改为引用。
- 跨章引用只认 `详见第X章《标题》`（与 `crossrefs.py` 一致），`style-guide.md` 不再
  给"参见 / 参考 / 见"的变体。
- 段落长度规则合并到 `style-guide.md` §3.1；终端调色板角色表只在 `DESIGN-TUI.md` §8；
  图注句式只在 `style-guide.md` §14。
- `style-guide.md` §7 明确区分章首引导块（引用块四行）与章末必备段落（H2 小节，
  由 `book.toml [sections]` 给出）。

- **ingest 不再吃掉正文**：`chapters.py` 只在目标文件为空、内容相同或 `--force` 时写入，否则跳过并报出行数；`actions.analyze` 在三阶段后跑一次 `content_volume.py`，把「内容体积：与基线一致 / N 项低于基线」写进同一份运行结果（后者判失败并给 `--update-baseline` 指引）。（rf-21）
- **体量基线只能抬高**：`content_volume.py --update-baseline` 默认拒绝把任何条目或总量改低，收缩须 `--accept-shrink --reason "<理由>"`，理由与逐项差额写进基线文件的 `accepted_shrinks`；新增 `--baseline <文件>`，用于显式对照某份历史快照（默认永远比当前基线，不做加权）。（rf-22）
- **基线记账要求“人 + 提交”**：`--update-baseline` 在 `data/manuscript` 有未提交改动、或没有具名评审人时拒绝记账，写入 `reviewed{by, at, commit, reason}`；`quality-model.md` §4 给出固定流程（check 全绿 → 提交手稿 → 记账留名）。（rf-23）
- **历史版本可以提为基线**：`content_volume.py --update-baseline --from-snapshot <label>` 从快照的体积账本取数，记录 `source.snapshot`；比当前基线薄时仍须 `--accept-shrink`。`quality-model.md` §4 给出「导入 → 记快照账本 → 提为基线」流程。（rf-24）
- **基线换版**：按用户指示，把 `docs-stm.zip`（2026-06-11 版）导入为只读快照 `2026-06-11-june-2026` 并认定为体量基线（16 文件 / 36 893 行），理由与来源记账在基线文件里。
- **LLM 用量与费用可见**：新增 `data/config/llm_pricing.json`（每百万 token 单价，未列出的模型记“未定价”）；每次调用记录 token 与费用并追加 `logs/llm-usage.jsonl`；`llm-ask` 打印调用前区间预估 + 调用后「本次 / 今日累计」，`analyze --llm` 打印整轮汇总；`llm_settings.daily_cost_limit` 达到时追加 ⚠ 提醒。（rf-25）
- **LLM 费用多币种，缺省人民币**：`llm_pricing.json` 增加 `display_currency`（缺省 `CNY`）与 `fx` 锚点，费用按模型货币记账、按显示货币汇总（`¥` 前缀，缺锚点时退回原币种）；`logs/llm-usage.jsonl` 每行同时记 `cost_display`/`display_currency`，跨币种的历史也能正确合计。价格表补 `_source`/`_fetched`，明确“人工核对、不联网取价”。
- **价格表改为参考 investor-review 的官方核对结果**：39 个模型（USD/CNY 各自标注），新增以 `-` 结尾的**前缀规则**用于带日期戳的模型名（精确名优先），DeepSeek 的 `peak` 峰谷价先记录、暂不参与计价。
### 交互

- **TUI 改为两级菜单**：内容流水线（`analyze` / `analyze-llm` / `build` / `deliver`）留在主菜单，
  只有质量（`4`）与配置与状态（`5`）收进二级；
  二级目录按 `0` 回到上一级，主菜单按 `0` 退出（`q`/`Ctrl+C` 任何层级直接退出），
  每屏记住光标，顶部显示路径带。（rf-18）
- **界面内可改的配置变多**：新增「配置项」屏（书名、版本、手稿目录、产物目录、语言、
  日志级别、默认 provider）与「LLM provider 优先级」屏（`u`/`d` 上移下移，写回
  `priority`，按 10 递增重排）；`c` 仍是一键直达配置项。（rf-18）
- Web 控制台的动作抛出异常时改为返回 `200` + `code: 1` 与异常文本，不再断开连接。（rf-18）
- **结果可见时 `0` 不再退出**：`0`/`Esc` 先收起结果、再返回上一级，主菜单上才退出；
  屏幕底部那个容易误读成输入提示的孤立 `❯ ` 去掉，结果区改为一行中性提示。（rf-20）

## 版本口径

本文件记录工具链的版本段，版本号取 `lib/_version.py`。书籍版本（`book.toml`）与
封面统计不由本文维护；两者的历史都在 git 中。
