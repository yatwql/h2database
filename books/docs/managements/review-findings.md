# 自我审查问题记录

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**问题台账**——发现了什么、怎么修、修到哪；不记设计决策（看
> `technical.md`），不复述变更清单（看 `changelog.md`）。
> **编号源**：`rf-next = 15`（新增问题提出后取此编号，写入后更新为 +1；已用最大 rf-14，
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
| `src/python/render/to_html.py` 811 行 | 占比 90%，触线前拆：目录构建、正文渲染、样式段各自独立文件 |
| `src/python/ingest/chapters.py` 665 行 | 占比 74%，按「骨架生成 / 模板填充 / 语言适配调用」三段拆 |
| `src/python/audit/style.py` 641 行 | 占比 71%，句式规则按规则族拆（单调 / 重复 / 段落），共享解析上提 |

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

### 归档

本项目不按版本切分问题归档文件：已修条目在下一次发布时摘要进 `changelog.md` 对应
版本段，历史由 git 保留。
