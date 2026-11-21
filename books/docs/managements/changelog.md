# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**版本变更记录，只留当前开发段**——写“变了什么”；问题编号与修复细节见
> `review-findings.md`，设计理由见 `technical.md`。已发布版本由 git 标签保留。

---

## [0.1] - 开发中（未发布）

### 变更

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
