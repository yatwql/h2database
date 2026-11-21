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

### 门禁

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

## 版本口径

本文件记录工具链的版本段，版本号取 `lib/_version.py`。书籍版本（`book.toml`）与
封面统计不由本文维护；两者的历史都在 git 中。
