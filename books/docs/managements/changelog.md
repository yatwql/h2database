# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1-dev
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
- **`templates.toml` 的无效查找去掉**：`chapters.py` 原来对每一条深读要点都调 `tpl('deep_dive_item', …)`，
  而模板文件里只有 `deep_dive` 列表（`deep_dive_item` 从未定义）——等于每次都走回退分支。
  现改为直接对条目做占位符替换，行为与产物哈希不变（`13f8976f…`）；膨胀登记同步到 755 行。
- **`case-studies.toml` 改为可选**：它只服务 `manuscript/case_studies.py`（按需生成附录 A 大纲），
  而 `core/scaffold.py` 建新书时并不生成本文件——原实现在**导入期**读它并 `SystemExit`，等于
  一本没有案例研究的书连模块都进不去。现在缺失即视为「未配置」（`load_scenarios()` 返回空表），
  TOML 写错仍判红，并补一条用例钉住。`folder.md` 同步写明它是按书可选的内容数据。
- **本书专属文件搬到 `data/` 顶层**：`book.toml` 与 `case-studies.toml` 直接放在 `data/` 下，
  `data/tmpl/` 只留 `templates.toml` 这类叙述模板。这两份是每天要看的书身份与案例，藏在
  `config/` 的子目录里等于让读者多翻两层；`[paths].book` 的缺省值随之改为 `data`。原先两类东西混放在
  一起（一是「换一本书整份替换」的身份/案例，一是生成时套用的模板），看目录分不出哪份能复用到
  别的书。`_config` 新增 `book_dir()`/`book_path()`，`book.toml [paths]` 增加 `book` 键，
  scaffold、traces、case_studies、fixture 与用户文档同步改指向。
- **配置从常量改为按书解析的对象**：`lib/_config.py` 原来在导入期算死 `BOOK_ROOT`、
  `MANUSCRIPT_DIR`、`POLICY`、`THRESHOLDS` 等十余个模块常量，一个进程只能读一本书，
  测试要换书只能 `sys.modules.pop('lib._config')` 重导入。现在这些值属于 `Config(root)`，
  模块级名字改为转发到活动书（PEP 562 `__getattr__`），新增 `current()` / `use()` /
  `for_root()`；调用形式与取值全部不变（渲染文本哈希 `13f8976f…` 未变），新增 8 条用例
  钉住两本书互不串值、`use()` 异常也还原、未知名字仍报错。
- **书籍配置文件的落点**：`data/book/book.toml` 与 `data/book/case-studies.toml` 就摆在 `data/` 第一层，
  与 `manuscript/`、`config/`、`tmpl/` 并列；`data/config/` 恢复为「工具链策略」专用
  （base/style/llm_*）。`Config.book_toml`、scaffold 写入位置、注释痕迹扫描面、fixture、
  用户文档与 20 处路径引用同步改指向。
- **多书并行维护立档**：配置已能按书解析，但入口、派生状态与基线仍是单份，第二本书一进来就会
  互相覆盖。新增 `docs/plan/multi-book/` 记录目标形态（先一仓多书、条件成熟再让工具链独立成包）、
  按书隔离与共享的边界、配置三层与手稿 edition 轴，并把 `plan-11` 列为当前待办；
  `technical.md` §10 的「不做多书合一构建」仍然有效——一本书一份产物。
- **多书设计与计划定稿**：两轮以上逐条复核后改掉的事实错误与不可实施处——`PATH_LITERALS`
  是禁止表而非耦合点、日志隔离靠书根而非文件名、edition 子目录会破坏单书等价条件、
  `[editions].default` 与同名版本冲突（改顶层 `default_edition`）、覆盖三层第 2 层落到
  `shared/base.json`、`data/snapshots/` 归书且不引入跨书快照、`use()` 是进程级状态
  而 Web 用多线程服务（一进程一书的边界写进设计）。能力同时登记为需求 IR-10，判据载体
  在 `testplan.md` §2.4；四步的验收改成可机检，并各自给出回滚方式。
- **多书设计二轮复核**：补上被漏掉的语义并去掉越界表述——章节清单归书、版本可用
  `[editions.<id>.chapters]` 覆盖且不重排图号章号；版本基线改成与原状态同形的
  `baselines/<edition>/`；合并规则只指向 `technical.md` §3.1，不在设计里重述；新增
  「非功能需求怎么适用」（体积预算按书、可移植覆盖向上查找、不做跨书汇总）；写明
  `[paths]` 不得越出书根的校验、旧布局不猜位置、自举与 CI 的边界、删 `[editions]` 后的
  残留处理；与 `quality-model.md` §4「只比一份」对齐为「每版本只比自己那份」。
- **源目录绑定进多书设计**：源是被分析对象，属于书的输入——声明在书级 `[sources]`，不在
  运行期切换（NFR-02 可复现、体量基线是评审结论）；一棵树不够时用 `roots[]` 带 `label`，
  单根 `src_main` 保持兼容；体量基线写入 `source{label, version, digest}`，换源后要求复核。
  同时点出一处真实阻塞：`source_refs`、`content_depth`、`chapters` 在导入期就冻结源根，
  `Config` 切书对它们无效，列为步骤二的前置。能力登记为 IR-11，多根源列为按需的步骤五。
- **多书设计三轮复核**：修掉自相矛盾与两处会踩坑的沉默行为——设计原写「章号不重排」，
  而 `structure.py` 要求 `1..N` 连续，删节版留空洞必红，改为版本重编号并记录原章号映射；
  多版本共用 `merged_name` 会互相覆盖，改为缺省 `<merged_name>-<edition>`；`_DEFAULT` 在
  导入期构造，`--book` 尚未解析就会按兜底根读盘，改为惰性并与「源根解冻」并列为步骤二前置。
  新增「与语言包计划的关系」（语言是资源、版本是内容是两件事）、五份管理文档的改动面清单，
  并把 `scripts/bookctl` 透传与 `settings set` 的写入目标写进步骤二。
- **版本归档落地**：新增 `docs/archive/v<major>.<minor>/`，装该版本的三份台账
  （`archived_changelog` / `archived_plan` / `archived_review-findings`）与已完成的迭代设计目录；
  `core/docs_archive.py` 做机械迁移——纯文本变换加目录搬迁、幂等、`--dry-run` 先看动作，
  哪些迭代算完成由人用 `--topic` 指定，脚本不猜；`audit/doc_archive.py` 把布局变成门禁
  （版本目录名、三份文件与头行、索引链接可打开、已归档版本不得留在主文档、迭代目录名不含
  追踪编号），空归档视为通过。规则写在 `docs/archive/README.md`，归属写进 `folder.md` §3，
  能力登记为 IR-12；用例按层拆成 `test_core_docs_archive.py` 与 `test_audit_doc_archive.py`。
- **计划管理补上双向覆盖**：`docs/plan/figure-chapter-plumbing/` 这一完成态迭代没有认领它的
  计划项，`plan-11`（多书并行维护）的条目在 `plan.md` 里丢失——概述仍写「在办 3 项」而正文
  只剩两项。恢复 `plan-11` 全条，并在 `plan.md` 新增「待归档」节：已完成的迭代在这里列名
  并给出结论出处，发布时由 `core/docs_archive.py` 整体移入版本归档。新增门禁
  `audit/plan_coverage.py`：每个 `docs/plan/<主题>/` 恰好被一个计划项或待归档行认领、计划项
  的四段齐备且有序、`plan-N` 唯一、`plan-next` 等于最大编号 + 1、概述的在办项数与分档数字
  与实际一致——这类漂移以后跑 `make.py check` 就会当场判红。
- **多书设计四轮复盘**：修掉与既有需求的冲突和几处「改了也没用」的方案——「不引入跨书快照」
  与 NFR-07 冲突，改为按书只读、允许人工放入他书稿；只把 `_config` 改惰性不解决问题，
  消费方在模块顶层取配置仍会冻结，立为规则并加 `check_architecture.py` 机检（登记存量、
  只挡新增）；重编号会连带跨章引用、术语与索引，`index_xrefs.py` 的 1-12 硬编码列为必须
  一并整改的债务；补多根源的类型兼容契约（`versions()['source']` 单根字符串 / 多根映射）、
  `default_edition` 在多版本下必填、嵌套书根取最近一本、`--edition` 与 `--book` 同等的
  子进程传播、以及「这几步明确不做」四条。
- **多书设计五轮复盘**：补上「多版本时哪些目录按版本、哪些不按」——状态与基线按版本、
  日志按书、数据归档目录带版本、快照账本记版本；重编号映射落 `state/<edition>/renumber.json`；
  入口写明有两个（`app/cli.py` 与 `make.py`，含 `bookctl make` 透传）；`check_runner` 的改动
  分档跟随活动书，他书改动不得当 infra 触发全量；包化必须携带默认 `book.toml` 模板、
  `templates.toml` 与 `language/*.json`。复盘还查出一处管理缺陷：IR-12 从未真正写进需求表
  （登记脚本没命中也不报错），已补 IR-12 与 IR-13；`requirement_trace` 新增编号空洞检查，
  以后漏写一行编号就会被判红。
- **多书设计补上三个渠道与两套界面**：CLI 与 `make.py` 用全局参数；Web 改为顶部「书 / 版本」
  下拉框 + `/api/books` 候选，服务端把动作执行放进全局锁并在锁内 `use(Config(book))`，
  两个并发请求不会串书；TUI 沿用 `DESIGN-TUI.md` 七段分区，对象行多书时补书根，
  「切换书籍」放进「配置与状态」二级屏（数字直选、`0` 返回、执行中拒绝切换、切换后清空
  结果与摘要）。两界面都不记忆上次选择，避免「为什么跑的是那本」难以解释。
  相应验收写进步骤二：`/api/books` 列候选、并发不串书、切换清屏、执行中拒绝。
- **多书设计与计划只留当前状态**：清掉评审过程措辞（「改回」「已完成」「既有债务」「真正缺的」
  这类指向前一版的表述），改成直述当前设计与动作；`plan-coverage` 的检查面不受影响。
  同时把会话复盘记录移出仓库并存进忽略清单——过程记录留在本地，仓库里只放结论。
- **多书选定：按书解析与三个渠道的选书入口**（plan-11 步骤二）：`lib/_config` 新增
  `find_book_root()`/`resolve_book_root()`/`candidate_books()`，导入时记下书根、`Config`
  首次使用时构造，`[paths]` 越出书根的条目直接判 `ConfigError`；选择经 `BOOK_ROOT` /
  `BOOK_EDITION` 传给子进程，`core/actions.py` 的 `_run`/`_make` 统一带上，状态与设置类
  轻动作包在 `use(Config(book))` 上下文里。CLI 加 `--book`/`--edition`（缺 book.toml 退 2），
  `make.py` 同名参数导出给每个步骤，`bookctl` 原样透传；Web 加「书 / 版本」选择器与
  `/api/books`，请求携带选择、服务端按请求执行；TUI 加同名参数，会话内选定一本书。
  测试 13 条钉住解析优先级、向上查找、越界拒绝与候选发现。
- **TUI 的「书籍」屏**（plan-11 步骤二收尾）：`core/menu.py` 新增 `books` 屏，挂在
  「配置与状态」下（选书是偶尔动作，不占主菜单数字键）；行来自 `_config.candidate_books()`，
  当前一本以 ● 起首，数字键选定、`0` 返回；`_config.reset()` 让切换对进程持续生效，
  并用 `BOOK_ROOT` 同步给随后启动的子进程。契约写进 `DESIGN-TUI.md` §3.1，用例 4 条。
- **CI 红因：没装 pandoc 的机器上 EPUB 用例仍照跑**：`ToEpubTest` 的构建用例没有守卫，
  在 runner（无 pandoc）上直接失败，`make.py test` 与三平台 job 全红。加 `HAS_PANDOC` 守卫
  后与既有的「无 pandoc 时应说明安装方式」用例成对：有工具才验证构建，没工具验证提示。
- **手稿版本轴进入配置层**（plan-11 步骤三首批）：`book.toml [editions]` 与顶层
  `default_edition` 被 `Config` 读取；未声明即单版本、行为与目录形态不变；声明后手稿在
  `data/manuscript/<edition>/`，派生状态与体量基线落到 `state/<edition>/`、
  `baselines/<edition>/`，产物名缺省 `<merged_name>-<edition>`。版本来源优先级为显式
  参数 → `BOOK_EDITION` → `default_edition` → 唯一版本；多版本未给缺省、或指向未声明
  版本时报 `ConfigError` 并列出已声明版本。CLI/Web/make/TUI 已把选择带进同进程上下文，
  子进程照旧读环境变量。用例 5 条钉住单版本不变、隐式选中、多版本必填、未声明拒绝、
  环境变量选择。
- **版本感知的三处**（plan-11 步骤三第二批）：`[editions.<id>]` 可以是表，带 `display`、
  `merged_name` 与 `[editions.<id>.chapters]` 覆盖（files/numbering/titles/packages/coverage
  逐键覆盖书级表）；`index_xrefs.py` 的子条目章号不再硬编码 1-12，改按本书声明的覆盖章号集
  判定；数据归档目录与快照账本记录版本（`<slug>-<edition>`、`manifest.edition`），两份手稿
  归档不再互相覆盖。单版本时三处行为与目录形态不变。
- **版本章号重编号与引用改写**（plan-11 步骤三收尾）：新增 `manuscript/renumber.py`——按书级与
  版本的 `[chapters.numbering]` 差异算出 `原章号 → 新章号`，写进 `state/<edition>/renumber.json`，
  并据它改写 `详见第X章《…》`、裸 `第X章` 引用（术语与索引里的章号同一条规则）；`--write`
  只落映射、`--apply` 才改正文、`--dry-run` 只报数量；未选版本时直接拒绝。构建清单加入
  `edition` 与 `language` 两个字段，两份手稿的合并稿可自证来源。用例 8 条覆盖映射与改写。
- **多根源的声明与解析**（plan-11 步骤五首批）：`[sources]` 支持 `roots[]`（`label`、`path`、
  `language`、`version`），`label` 必填且唯一；单根写法照旧，`source_tree('src_main')`
  等于首根，其它键按 `label` 解析。`versions()['source']` 单根仍是字符串、多根改为
  `label → 版本` 映射；`source_versions()` 给出逐根版本。用例 4 条钉住标签、解析与两种拒绝
  （重复 label、缺 path）。
- **多根源逐根摘要与源指纹**（plan-11 步骤五收尾）：`digest.py` 在声明多个根时逐根分析并
  合并——包按 `<label>:<包名>` 记账、各根总量进 `by_root`，单根时输出与之前逐字相同；
  体量基线的 `reviewed` 增加 `source{roots, versions, inventory_sha256}`，比对时若指纹
  不同即报「基线来自另一个源，先复核再下调下限」，不再静默通过。
- **CI 红因：TUI 切换用例把 `BOOK_ROOT` 留给后续套件**：`switch_book()` 会为子进程写
  `BOOK_ROOT`，用例没有还原，于是之后启动子进程的慢档用例（`order_dependence`）指向已被
  删除的临时书根，报 `ConfigError: missing config`。用例改为 `addCleanup` 还原环境变量；
  全量套件（含慢档）**1249 passed / 14 skipped**。同批的两次 cancelled 是并发取消，不是失败。
- **TUI 每次重绘先清屏**：主循环原来只是把下一帧写到上一帧下面，按一次键就多一整屏，
  菜单被顶出可视区。新增 `clear_screen()`（`\033[H\033[2J`），仅在终端且启用颜色时发出——
  管道与测试捕获到的仍是纯文本。契约写进 `DESIGN-TUI.md` §2 的屏幕分区说明，用例 3 条：
  终端清屏、非终端不发转义、主循环每帧清一次。
- **用量行改成绝对差额**：`+14%` 会被读成「增长了 14%」，实际是「离下限还有多少」。`headroom()`
  增加 `above`，界面显示 `体量 40,097 行（下限 35,048，尚余 5,049 行）`——下限 = 已评审
  基线 36,893 行 × `floor_ratio` 0.95；`?` 帮助补一句口径说明，`DESIGN-TUI.md` 的用量行
  同步，并加一条「不得出现百分比」的断言防回退。
- **多书设计第 1 节对齐现状**：删掉「维护第二本书只能再检出一次工具链」的说法——`--book`
  已能指向任意目录，实测仓外书目录 `cli.py status --book …` 正常；缺口改写为「工具链自己的
  交付形态」：默认配置仍是每书一份、`bookctl` 仍是仓内脚本，这才是步骤四要解决的东西。
- **用量行改为说后果**：`体量 40,097 行（下限 35,048，尚余 5,049 行）` 三个词都是门禁内部
  术语，读者仍要问「这是什么」。改为 `手稿 40,097 行（再少 5,049 行即判「内容变薄」）`：
  先说测的是什么，再说越过之后会发生什么；`?` 帮助补一句下限的算法，`DESIGN-TUI.md`
  同步，用例断言改为「不得出现百分比与『下限』字样」防回退。
- **架构债：两个库模块在导入期绑死书路径**：`_baseline.py` 的 `BASELINE_DIR`、`_llm.py` 的
  `PROVIDER_PATH`/`SETTINGS_PATH` 在 import 时取一次，于是 `--book` 换书后基线写入与 LLM
  配置仍指向导入时那本书——库被 `app/` 同进程引用，这是真实缺陷而不是风格问题。改为
  `baseline_dir()` / `provider_path()` / `settings_path()` 逐次解析，并加一条用例：切书后
  三个路径都跟着变。审计还扫了 39 处模块级配置读取，全部位于以子进程运行的脚本里，
  在「动作走子进程」的模型下无害，已在设计里写明该边界。
- **打包骨架与实测到阻塞**（plan-11 步骤四首片）：新增 `books/pyproject.toml`——`src/python`
  下七个顶层包以 `package-dir` 声明、零运行时依赖，可离线 `pip install --target` 装出可导入的
  包。安装后实测 `bookwright status --book <书>` 失败：`lib/_log.py`、`check_runner.py`、
  `make.py` 在**导入期**读配置，`--book` 尚未解析，书根退化成 `/`。因此暂不提供控制台命令，
  先把这三处改为调用时读取——与先前在 `_baseline`/`_llm` 修的是同一类缺陷。
- **安装形态的导入期读配置逐处拆除**（plan-11 步骤四）：`make.py`、`check_runner.py` 的
  `BOOK_ROOT`/`REPO_ROOT` 常量改为 `book_root()`/`repo_root()` 逐次解析；`core/actions.py`
  的 `REPO_ROOT` 同为函数；`lib/_log.py` 在书尚未解析时只输出到控制台，选定书后再挂文件
  处理器。实测安装后导入仍差最后一处：`core/settings.py` 的 `SPEC` 表在导入期拼路径，
  需改成惰性构建；控制台命令待那一处改完再打开。
- **安装形态可导入；配置读写不再依赖导入期路径**（plan-11 步骤四）：`core/settings.py` 的
  `SPEC` 表与四个路径常量改为 `spec_table()` / `book_toml()` / `provider_json()` 等逐次解析，
  `_reload()` 在重导入后按**当前书**重新绑定（否则重导入会把活动书换回进程默认）。修掉
  一个真实写入缺陷：`[llm]` 段已存在但缺该键时，写入会追加第二个 `[llm]` 段，文件直接变成
  非法 TOML——现在插到既有段内。安装后 `import app.cli` 通过，控制台命令待补。
- **被分析的源树归书声明**：`src_main`/`pom_root`/`version` 从 `data/config/base.json [sources]`
  移入 `data/book/book.toml [sources]`——「这本书读哪棵树」是书的身份，不是工具链策略；
  `base.json [sources]` 只保留分析口径（`languages`、`suffixes`、`package_prefix`），两处按
  书级覆盖共享合并。这样在安装形态（步骤四）下，默认配置随包分发时不会把某本书的源树
  带成所有书的默认值。归属写进 `folder.md` §3 与 `technical.md` §3.1，多书设计的源章节同步。
- **书目目录成为配置项**：`book.toml [paths].library` 声明「其他书放在哪」，缺省为本书的父级；
  `candidate_books()` 在该目录下只认带 `data/book/book.toml` 的目录，TUI 的「书籍」屏与
  Web 的 `/api/books` 共用这份发现逻辑。此前多书候选实际依赖「书根同父目录」的目录布局
  约定——没有任何配置项表达这件事，换一种排布就看不出第二本书。用例 2 条：缺省值、声明后
  候选随之改变；`folder.md`、`technical.md` §3.1、多书设计的渠道章节同步。
- **书目发现支持两种配置布局，选择界面带目录名**：`config_file_of()` 同时接受
  `<书根>/data/book/book.toml` 与 `<书根>/book.toml`，`find_book_root()`、候选扫描与
  `Config` 都走同一判定，因此一个书目目录里可以既有根上的一本、也有子目录里的多本；
  TUI「书籍」屏与 `/api/books` 在书名旁显示目录名，同名书不再混淆（`/api/books` 增加
  `config` 字段）。设计里记下第 4 点取舍：每本书本就是独立书根，`dist`/`manuscript` 不再
  按书嵌套。
- **TUI：切换书籍提到主菜单**：`6 切换书籍` 从「配置与状态」二级屏移到第一级（配置屏恢复
  `1–6` + `0`）。多书并行时切书的频次与构建同级，藏在二级等于每次多按两下；
  `DESIGN-TUI.md` §3.1 的菜单树与分级说明同步，用例改为断言主菜单含 `@open:books`。
- **多书文档与目录编号对齐**：多书设计里出现两个 `## 13.`（重编号为 1–17）；`folder.md` §3 与
  `technical.md` §3.1 补上「书身份文件两种布局都认」——`<书根>/data/book/book.toml` 与
  `<书根>/book.toml` 等价，判定只看能否读到 `book.toml`，产物与手稿仍在各自书根下。
- **用户文档补上多书能力**：CLI／TUI／Web 三份手册此前完全没有「选书与选版本」——
  分别新增：`--book`/`--edition` 的优先级与退出码、主菜单 `6` 的「书籍」屏（含拒绝切换与
  清屏规则）、Web 顶部下拉框与 `/api/books`。`how-to-config.md` §1 修正过期的
  `book = "data/config/book"`（实际是 `data/book`），并补 `[paths].library`、`[sources]`
  （已归书）、`[editions]`、两种书身份布局；FAQ 增加三个高频问题（多书并存、两个 toml
  谁算数、源码路径在哪配）。示例统一用占位名，`versions` 门禁要求工具文档不点名具体书。
- **书目目录可显式覆盖**：新增 `--books-dir` 与 `BOOKS_DIR`，优先级为「命令行／环境变量 >
  `book.toml [paths].library` > 书的父目录」。只给目录不给书时：唯一一本直接用、多本把
  「书名 [目录名] + 路径」列出来并退 2（不猜）、空目录退 2。`books_in()` 提供目录枚举，
  `library_dir()` 读覆盖值。用户文档、`technical.md` §3.1、多书设计 §14 同步，用例 4 条。
- **包内默认配置（按需启用）**：`lib/_defaults/` 内置 `base.json`、`style.json`、
  `templates.toml` 与 `language/zh.json`；book.toml 写 `[book] defaults = true` 时按**键级**
  合并（书里的值优先，缺的键取包内默认），不写则保持原语义——整份文件缺失＝空策略／最小骨架包。
  这样新书不必抄一份完整配置，而既有书与最小书的行为一个字都不变。用例 3 条：不启用时策略为空、
  启用后拿到默认值、书内同名键覆盖默认。
- **配置审计：删掉一个无读者的键**：`style.json [quality]._duplicate_ratio_note` 是说明性文本，
  代码从不读取，留在配置里只会被当成可调参数——删除。审计同时列出其余候选（`path.tools`、
  `base.json paths.state/baselines` 与 `book.toml [paths]` 重复、`language/zh.json [style]`、
  `style.json [sections].per_chapter` 与 `book.toml [sections]` 并存），待逐条确认后再动。
- **配置去重：同一事实只留一个所有者**（按审计结论执行）：
  - `style.json [sections]` 删除——章节骨架与必备段落只由 `book.toml [sections]` 声明；
    `style_schema` 不再要求该键，也不再把它列为已知顶层键（重复声明会判为未知键）。
  - `base.json [paths].state/baselines` 删除——路径由 `book.toml [paths]` 唯一给出，
    `snapshots` 仍留在 `base.json`（`excluded_dirs()` 读它）。
  - `book.toml [paths].tools` 删除——没有任何代码读取，工具目录由脚本位置推导。
  文档（`how-to-config.md` 示例与表格、`technical.md` 配置归属）同步修订；`version` 的
  三处（书版本、源码版本、样式 schema 版本）语义不同，保留。
- **句末标点归语言包**：`language/zh.json [style].sentence_endings` 此前没有任何读者，而四处判据把
  `。！？；` 直接写在正则里（`style.py` 两处、`book_quality.py`、`prose_quality.py`）。新增
  `_config.sentence_endings()`（默认 `。！？；`），四处改为按语言包构建匹配集——第二语种不会
  再被中文标点判。`fullwidth_punctuation` 没有任何规则可喂，删除。附带后果：`style.py` 增到
  642 行，膨胀登记同步。
- **`_config.py` 的拆分登记为存量债**：该文件已达 852 行（提醒线 700、硬线 900）。整体抽取
  试过一版：`_IMPORT_ROOT` 由发现逻辑算出、`ConfigError` 两侧共用、`candidate_books()` 反转
  依赖 `Config`，直接切块导致 14 个用例导入失败，已回退且未留残件。拆分方向与这三处依赖
  写进 `review-findings.md` 的膨胀登记，下一次按「先下沉发现与加载、`candidate_books` 留门面」
  的顺序做。`style.py` 的登记行同步到实测 642 行。
- **文档核对（管理 + 用户）**：TUI 手册的示例屏仍写着旧的 `行数余量 +14%`，改为现在的
  `手稿 40,097 行（再少 5,049 行即判「内容变薄」）`；`technical.md` 模块表补四个新模块
  （`core/docs_archive`、`audit/doc_archive`、`audit/plan_coverage`、`manuscript/renumber`）；
  `scripts-and-reference.md` 新增「按需执行的工具脚本」一节，说明这三个工具何时用、怎么用。
- **代码体检：去掉重复导入与一处重复计算**：`core/actions.py`、`core/menu.py`、`core/settings.py`
  都在 `sys.path.insert` 前后各写一遍 `import os`/`sys`，第二份是多余的；`app/web.py` 的
  候选项把 `config` 字段算了两次（第一次的算法对嵌套布局还是错的），改为构建一次、
  语义唯一（书所在目录名）。四道形态门禁（架构、脚本契约、文件长度、类型）与快档用例全绿。
- **分支模型**：设立 `dev` 为开发分支（日常提交在此，版本号带 `-dev`），`master` 只接收发布
  合并——发布时 `dev` → `master`、去掉 `-dev`、打标签，台账与已完成的迭代设计由
  `core/docs_archive.py` 迁出。版本唯一来源仍是 `lib/_version.py`。
- **版本号进入开发形态**：`lib/_version.py` 的 `TOOL_VERSION` 改为 `0.1-dev`，14 份管理文档的
  `> 版本：` 头随之更新。`version_consistency.py` 的两处版本解析（文档头、封面）原先只认
  `[\d.]+`，`v0.1-dev` 会被截成 `0.1` 而判红——现在接受可选 `-dev` 后缀，判据不变。
  发布时按 `CLAUDE.md` 的流程：`dev` → `master`、去 `-dev`、打标签、`docs_archive.py` 迁台账。
- **源码仓库可克隆到 `data/srcref/`**：`[sources].repo`（可选 `ref`）声明 GitHub 等项目后，
  新增的 `core/fetch_source.py` 把仓库浅克隆到 `books/data/srcref/<owner>__<name>/` 再展开分析；
  已存在的目录不加 `--update` 不覆盖，`--dry-run` 只打印 git 命令，失败保留现场并给出原因。
  `_config` 增加 `srcref_dir()/source_repo()/source_ref()/clone_target()`，`source_tree()` 在
  声明了仓库但尚未克隆时直接报错并指路。目录内容不入库（只保留 README），`how-to-config`、
  `folder.md` 同步；用例 8 条（命令构造、目标推导、不覆盖、dry-run、未克隆即报错）。
- **TUI 新增书籍（`n`）**：主菜单增加「新增书籍」，依次询问书名与源码（目录或 git 地址）。
  `core/scaffold.py` 新增 `create_book()`/`set_source()`/`is_repository()`：新书建在**当前书的
  `data/book/<书名>/`** 下（选书屏立刻能看到），目录源记 `src_main`、仓库源记 `repo` 并调用
  `fetch_source` 克隆到 `books/data/srcref/`。失败只报原因、不留半本书；建完不自动切换。
  菜单与屏幕树（`DESIGN-TUI.md`）、用户手册同步，用例 2 条。
- **主菜单字母快捷键**：每项除数字外增加字母键（`1/s`、`2/m`、`3/p`、`4/t`、`5/c`、`6/b`，
  大小写不敏感），行内以 `[1/S]` 形式同时显示两种键。`core/menu.py` 增加 `LETTER_ALIASES`
  与 `resolve()`/`display_key()`，按键先经别名再匹配；原先 `c` 直跳配置屏的特例取消——
  现在 `C` 等价于 `5 配置与状态`，语义统一。`DESIGN-TUI.md` 键位表与屏幕树、用户手册同步，
  用例 3 条（别名解析、行内显示、按字母等于按数字）。
- **主菜单定版为 1–8 + 字母键**：`1/m`、`2/b`、`3/p`、`4/t`、`5/c`、`6/s`、`7/n`、`8/l`
  （大小写不敏感）——`8` 收编原来的 `l`（LLM 润色），`7` 收编原来的 `n`（新增书籍），
  行内以 `[1/M]` 形式同时显示两种键。`DESIGN-TUI.md` 屏幕树与键位表、用户手册同步。
- **主菜单再定版为 1–8 + `a/l/b/p/t/c/s/n`**：LLM 变体紧随主流程排在 `2`（原 `8`），
  构建及其后各项依次后移一位（构建 `3`、交付 `4`、质量 `5`、配置 `6`、切换书籍 `7`、
  新增书籍 `8`）；默认光标仍落在构建（现在是 `3`）。`DESIGN-TUI.md` 屏幕树与键位表、
  用户手册、5 条用例同步。
- **键位显示：字母统一大写并单独着色**：主菜单行内显示为 `[1/A]`…`[8/N]`，字母用调色板新增的
  `shortcut`（亮青）渲染，数字仍用键位色；`menu.display_key()` 统一转大写，`tui._key()` 支持
  「数字/字母」双色渲染。用例补一条：双色渲染时字母颜色码出现在输出里。
- **键位显示补齐两处**：LLM 行（`2`）此前只显示数字，现在同样显示 `[2/L]`；退出项增加
  `[0/Q]`（`q` 本来就是退出键，现在在菜单上写明）。`DESIGN-TUI.md` 屏幕树与用户手册键位表
  同步，用例补 `0/Q` 与「2 显示 L」两条断言。
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
