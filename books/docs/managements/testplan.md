# H2 Database 源码分析 — 质量标准与测试计划

> 版本：v6.5

---

## 1. 权威验证流程

日常只用一个入口，不再手工按顺序调用脚本：

```bash
python books/src/python/make.py check      # 全部门禁（不写产物）
python books/src/python/make.py build      # cover 统计 + 合并 md + HTML
python books/src/python/make.py test       # 工具链单元测试（books/src/test）
python books/src/python/make.py doctor     # 可选依赖检查（pandoc / playwright / pypdf）
```

常用参数：`--only NAME[,NAME]`、`--skip NAME[,NAME]`、`--timings`、`--keep-going`。

最终交付 PDF / EPUB 时：

```bash
python books/src/python/make.py deliver    # build + to_pdf + pdf_toc_links + verify_pdf + to_epub
```

PDF 生成较慢；日常编辑只要求 `make.py check` + `make.py build` 通过。CI（`.github/workflows/book.yml`）自动执行 lint + 单元测试 + 门禁 + 构建 + 幂等性校验。

## 1.2 交付分档

同一套门禁按"什么时候跑"分三档，本地脚本与 CI 一致（`.github/workflows/book.yml`）：

| 档（P 级） | 触发 | 内容 | 本地命令 |
| --- | --- | --- | --- |
| fast（P0，也由 `pre-commit` 钩子执行） | 每次提交 / PR | ruff + 结构门禁（architecture、script_contract、style_schema、llm_policy、versions、file_length）+ 单元套件（约 16s） | `scripts/check-fast.sh` |
| full（P1，也由 `pre-push` 钩子执行） | 合入 master / 发布前 | 全部门禁（`make.py check --keep-going`） | `scripts/check-full.sh` |
| release（P2） | 打版本标签 | full + 慢档（chromium/pandoc）+ 顺序依赖探测 + `make.py deliver` 出产物 | `scripts/check-release.sh` |

度量类单独命名：`scripts/eval-score.sh`（六维评分）、`scripts/test-eval-coverage.sh`
（覆盖率棘轮）。分档只决定"跑到哪一步"，判据本身不分档。

## 2. 质量门禁

### 2.1 门禁分级

`structure.py` 的检查项按"阻塞级别"分为 P0 / P1 / P2 三档：

| 级别 | 含义 | 阻塞级别 |
| --- | --- | --- |
| **P0** | 基础完整性 + 渲染正确性 | 任何交付（含日常） |
| **P1** | 内容质量 + 工具可用性 | 正式发布 |
| **P2** | "叙事质量"门禁，按 P2 口径运行 | 可选；当前已全部通过 |

`structure.py` 命令行控制：

```bash
python books/src/python/structure.py                  # 默认 p2 = 全量
python books/src/python/structure.py --gate-level p1  # p0 + p1
python books/src/python/structure.py --gate-level p0  # 仅 p0
```

### 2.2 各检查项及其级别

| 类别 | 通过标准 | 验证方式 | 级别 |
| --- | --- | --- | --- |
| 章节结构 | 12 章 + 5 附录齐全，H1/H2/H3/H4 层级连续 | `structure.py`（heading hierarchy） | P0 |
| 图号 | 每章图号唯一且完整；允许历史补号导致非严格位置顺序 | `structure.py`（figure numbering） | P0 |
| 图表覆盖 | 内容型 `###` 小节 ≥ 2 图；模板型小节 ≥ 1 图 | `smart.py` | P0 |
| 代码围栏 | 所有围栏成对；HTML `<pre><code>` 平衡 | `structure.py`（code fence balance / HTML TOC） | P0 |
| 跨章引用 | 章节互引 ≥ 1；前后件免检 | `structure.py`（cross-references） | P0 |
| HTML TOC | TOC 与内容标题 1:1，零断链 | `structure.py`（HTML TOC） | P0 |
| 合并文档 | 源文件总行数与合并文档一致 | `structure.py`（merged doc） | P0 |
| 编码 | Markdown 和 HTML 均为有效 UTF-8 | `structure.py`（UTF-8 encoding） | P0 |
| CSS 渲染钩子 | to_html.py 含 9 项关键 CSS 标记（h1 装饰、复制按钮、面包屑等） | `structure.py`（CSS style checks） | P0 |
| 索引完整性 | 索引 ≥ 120 条；每章 ≥ 5 条；章节引用对应实际内容 | `structure.py`（index integrity） | P1 |
| 索引层级 | 主条目 ≥ 150；子条目 ≥ 50；see-also ≥ 30；see-also 全部解析；子条目章节 ∈ 1-12 | `structure.py`、`index_xrefs.py` | P1 |
| 术语完整性 | 术语 ≥ 60 条；每条有对应章节引用；引用章节号 ∈ 1-12 | `structure.py`（glossary content） | P1 |
| 工具脚本可用性 | 术语表与索引生成脚本语法有效 | `structure.py`（builder checks） | P1 |
| 图注质量（预留） | 见下方图注动宾结构行 | `captions.py` | P2 |
| 章节互引 | `详见第X章《…》` 与真实 H1 一致 | `crossrefs.py` | P0 |
| 图注动宾结构 | 全书图注以批准动词起首；长度 ∈ [8, 30] 字；无模糊后缀；strict 阈值下违规 = 0 | `captions.py --threshold strict` | P2 |
| 图簇桥接 | 3+ 张图在 ≤ 40 行内连续出现的"图簇"，前置一句桥接叙事点名所有图 | `figure_clusters.py`（参数 `--window 40 --needs-bridge`，应输出空清单） | P2 |
| 延伸思考 | 14 章节槽全部含 `## N.X 延伸思考` 小节；每章 ≥ 3 题；每题含难度/题型 emoji + 提示行 + 含锚点的回顾行；全书 ≥ 50 题 | `structure.py`、`exercises.py` | P2 |
| 写作风格审计 | `style.py` 0 WARN | `structure.py`（style check） | P2 |
| 版本统计 | cover 统计先更新；管理文档版本一致 | `cover.py`, 人工核对 | P0 |
| 链接与锚点 | 所有相对链接指向存在的文件；`#anchor` 命中真实标题；代码围栏内不检查 | `links.py` | P0 |
| 配置一致性 | `books/data/tmpl/book.toml` 列出的章节全部存在、无重复、产物路径位于 `dist/` | `books/src/test/test_config.py` | P0 |
| 源码符号 | `Class.method(` 断言在对应 java 文件中存在；已知漂移记入基线，仅"新增漂移"阻塞。上游升级后：`--suggest` 取改名建议 → 复核 → `--update-baseline` | `source_refs.py`、`books/data/baselines/source-symbol-baseline.json` | P1 |
| 构建幂等 | 连续两次 `make.py build` 的 HTML 哈希一致 | `.github/workflows/book.yml` | P0 |
| 合并 Markdown | 合并结果按 book.toml 章节顺序拼接，front/back matter 齐备 | `render/merge.py` | P0 |
| HTML 渲染 | HTML 含标题锚点、侧边栏 TOC、印刷 TOC；未闭合围栏不吞正文 | `render/to_html.py` | P0 |
| PDF 渲染 | HTML → PDF 成功，页面数据可读 | `render/to_pdf.py` | P0 |
| 印刷 TOC 链接注入 | 每个印刷 TOC 条目在对应页上加一条 link annotation，目标页按 outline 位置映射 | `render/pdf_toc_links.py` | P1 |
| PDF 版式 | 页面为 A4（595×842±2）、无旋转 | `verify_pdf.py`（PAGE_SIZE / ROTATION） | P1 |
| EPUB 元数据 | dc:title/creator/language/identifier 齐备；配置了封面则必须在 manifest | `verify_epub.py`（METADATA / COVER） | P1 |
| PDF 交付校验 | outline 与标题一致、层级正确、TOC 链接可用、字体嵌入、体积达标 | `render/verify_pdf.py` | P1 |
| EPUB 结构校验 | mimetype/container/manifest/spine/nav 全部可解析 | `render/verify_epub.py` | P1 |
| 可读性 | 长句、宽 ASCII 图、框线闭合、图注质量 | `audit/readability.py` | P1 |
| 术语与排版规则 | 同一概念不混用两种写法；标题无尾标点；链接文字可读；中英之间留空格；列表标点一致；段落 ≤ 上限（已知项走基线） | `style_rules.py` | P1 |
| 内容深度 | 前向引用须点名主责章节；高频类型须入术语表；代码摘录与源码一致；练习题须指向本章类型或 §锚点 | `content_depth.py` | P1 |
| 写作风格 | 每章 WARN 计数为 0 | `audit/style.py` | P2 |
| 源码引用 | `Class.java:行号` 可解析、行号在文件长度内、方法存在 | `audit/source_refs.py` | P1 |
| ASCII 图质量 | 图宽 ≤ `ascii_max_cols`（CJK 记 2 列）；无行尾空格/制表符；单图不混用框线与 ASCII 边框；已知项走基线 | `diagrams.py`、`books/data/baselines/ascii-baseline.json` | P1 |
| EPUB 结构 | mimetype 首条且未压缩、container/OPF 可解析、manifest 与 spine 全部可解析、nav 链接全部命中、体积 ≤ `epub_max_mb` | `verify_epub.py` | P1 |
| PDF 交付 | outline 与 HTML 标题逐一对应、outline 层级跟随标题层级、印刷 TOC 链接按序且在页内、字体全部嵌入、体积 ≤ `pdf_max_mb` | `verify_pdf.py --require-toc-links` | P1 |
| LLM 边界 | LLM 只用于散文生成/评审场景；门禁与事实链路不得调用 | `llm_policy.py` | P1 |
| 发布评分 | 六维评分（功能/稳定/交互/代码/文档风格/文档质量）作为整改视图 | `make.py report` | 参考 |
| 版本一致 | 工具/源码/文档三版本可解析，管理文档头与合并稿 manifest 一致 | `version_consistency.py` | P0 |
| 历史快照完整性 | 快照文件与 manifest 记录的哈希一致；快照不参与构建、不被门禁扫描 | `manuscript/snapshot.py verify` | P1 |
| 架构约束 | 分层依赖方向、门禁只读、不硬编码路径、命名不遮蔽标准库、入口脚本均接入 make.py 步骤 | `audit/check_architecture.py` | P0 |
| 图号引用 | 图号唯一、正文引用可解析 | `figures.py` | P1 |
| 章节均衡 | 每章行数/图数/坐标分布 | `balance.py` | P2 |
| EPUB 生成 | pandoc 可用时生成 EPUB | `to_epub.py` | P3 |
| 类型检查 | pyright 可用时检查工具链类型（缺失则跳过） | `typecheck.py` | P1 |
| 门禁追溯 | make.py 的每个门禁都在 testplan 登记，反之亦然 | `gate_trace.py` | P0 |
| 配置结构 | `style.json` 只含已知顶层键、必备字段齐全、阈值区间合理（min<max、比例 0-100） | `style_schema.py` | P0 |
| 内容体积 | 每个章节的字节数与行数不低于基线（floor 0.95）、手稿总量不缩水、交付 PDF 页数 ≥ 基线 90%、EPUB 体积 ≥ 基线 85%；新增文件允许，删除须同步 `book.toml` 并重设基线 | `audit/content_volume.py`、`books/data/baselines/content-volume.json` | P0 |
| 文件长度 | 源码 ≤900 行、测试 ≤1200 行、文档 ≤1200 行（手稿附录 ≤2000） | `audit/file_length.py` | P0 |
| 脚本契约 | 每个入口脚本有模块说明、可执行入口、必要时说明退出码 | `audit/script_contract.py` | P0 |
| 文档一致性 | 文档中引用的路径、脚本、章节名、版本号与仓库实际一致 | `audit/doc_drift.py` | P0 |
| 网络隔离 | 测试全程零出站连接：`_netguard` 在 `_fixture` 导入时接管 socket，只允许回环；LLM 一律 mock（`mock` provider 或打桩 `_post_json`），Playwright 用假引擎 | `src/test/_netguard.py`、`src/test/test_no_network.py` | P0 |
| 覆盖率 | 分支覆盖率不低于 `base.json [toolchain].coverage_fail_under`（当前 77） | `make.py cover` | P1 |
| 历史痕迹 | 文档、代码注释、脚本/钩子/CI 注释与配置 `_note` 只描述当前状态，不含过程性记录（`--kind docs\|code` 选范围） | `audit/traces.py` | P0 |
| 多入口一致 | CLI/TUI/Web 三个渠道共用 `core/actions.py`，`status` 与 `llm-ask` 均可运行 | `books/src/test/test_llm.py` | P1 |
| LLM 配置 | provider 路由按 章节>书籍>场景 优先级解析；密钥只读环境变量；默认 mock 离线可跑 | `books/src/test/test_llm.py`、`data/config/llm_*.json` | P1 |
| 运行日志 | 日志写 `books/logs/`，按天回滚；级别 `BOOK_LOG_LEVEL` > 配置 > INFO；DEBUG 更详尽 | `books/src/test/test_logging.py` | P1 |
| 工具链测试 | 单元 + 集成测试全绿（109 例）：`make.py test` | `books/src/test/` | P0 |

`structure.py` 默认（`--gate-level p2`）必须达到全部检查通过。

## 2.3 一道门禁一个目的

每道门禁只回答一个问题；出现第二个问题时拆新门禁，不叠加。`gate_trace.py`
校验"`make.py` 里的步骤 ↔ 本节"双向一致。

| 门禁 | 唯一目的 | 相邻门禁的分界 |
| --- | --- | --- |
| `structure.py` | 章节结构与图号/围栏/标题层级是否成立 | 只管"骨架"，不管文字好坏 |
| `links.py` | 链接与锚点能否解析 | 只验可达性，不验内容 |
| `crossrefs.py` | `详见第X章《…》` 是否指向真实章节 | 只验跨章引用，不验链接语法 |
| `doc_drift.py` | 文档提到的路径/脚本/章节是否仍存在 | 只验"引用对象存在"，不验可达性 |
| `index_xrefs.py` | 索引条目/see-also 是否指回真实位置 | 只针对索引文件 |
| `captions.py` | 图注句式（动词开头、长度、含糊后缀） | 只管图注文字 |
| `figures.py` | 图号格式与正文引用是否配对 | 只管编号与引用计数 |
| `figure_clusters.py` | 图簇是否需要桥接句 | 只管多图成组的可读性 |
| `diagrams.py` | ASCII 图宽度与边框闭合 | 只管 ```text 图块 |
| `smart.py` | 图表覆盖密度（每章是否有足够图示） | 只出覆盖率，不评判单图 |
| `exercises.py` | 延伸思考的数量/难度/提示/锚点 | 只管练习段 |
| `style.py` | 写作硬规则（重复句、超长段、表格规模） | 只管结构化的文字规则 |
| `style_rules.py` | `style.json [style_rules]` 的词表与排版规则 | 配置驱动，改词表不动代码 |
| `style_schema.py` | `style.json` 结构是否合法、文档/配置是否混放 | 只验配置形状 |
| `content_depth.py` | 内容深度（前向引用、术语覆盖、摘录新鲜度、练习指向） | 只管"读者能不能跟上" |
| `source_refs.py` | 源码坐标与符号是否仍然有效 | 只验坐标，不验内容 |
| `version_consistency.py` | 工具/源码/文档三版本一致 | 只管版本号 |
| `check_architecture.py` | 分层、依赖矩阵、渠道纯净、命名、docstring | 只管结构约束 |
| `script_contract.py` | 每个脚本的入口契约（docstring/main/退出码/`--json`） | 只管脚本外形 |
| `llm_policy.py` | LLM 只允许出现在散文场景与允许的层；密钥文件不入库 | 只管 LLM 边界 |
| `traces.py` | 文档与代码注释不得有过程痕迹（`--kind docs\|code\|all`） | 一个门禁两个范围，一个目的 |
| `file_length.py` | 文件行数预算 | 只管规模 |
| `gate_trace.py` | 门禁表与实现的双向可追溯 | 只管登记一致性 |
| `portability.py` | 移植性：文本 `open()` 均显式 encoding；ASCII locale 下入口可运行 | 只管环境适配，不评判内容 |
| `test_redundancy.py` | 测试套件卫生：重复用例体、无断言用例、非 TestCase 内的 test_*、同名遮蔽 | 只管测试代码，不判业务 |
| `perf_baseline.py` | 交付速度：各步骤耗时与历史中位数对比，超阈值提示（默认 advisory） | 只管速度退化，不判正确性 |
| 顺序依赖探测（order_dependence，人工触发） | 正序/逆序各跑一次，结果不同即报；不进 `check`，慢档执行 | 只管顺序敏感性，不判正确性 |
| `typecheck.py` | pyright 静态类型检查 | 只管类型 |

合并原则：目的相同且扫描面重叠 → 合并（`traces.py` 合并了原 `doc_traces` 与
`code_traces`）；目的不同只是对象相近 → 保持独立（`captions`/`figures`/`diagrams`
都看图，但判据互不重叠）。

报告类（不是门禁，不进 `make.py check`，因此不写入上表）：六维计分卡（`make.py
report` / `eval-score.sh`）、`balance` 的计量输出（`--json`），以及计分卡使用的
文档风格度量（prose_quality，句长/列表/坐标密度），它出分不拦截。

## 3. 格式规范

- 图注格式：`**图 X-Y: Title**`，独立成行，不放入代码围栏。
- ASCII 图围栏：使用 ` ```text `。
- Java 代码围栏：使用 ` ```java `；SQL 使用 ` ```sql `。
- 源码路径：使用 `org/h2/...`，不使用 `h2/src/main/...` 前缀。
- 源码引用：使用 `ClassName.java:行号`，但不得放入章节标题或 PDF Outline 标题。
- 跨章引用：使用 `详见第X章《实际 H1 标题》`。
- 管理文档职责：需求、计划、测试、变更、审查问题分别维护，避免重复。

## 4. 交付形态专项门禁

本节列出"非日常"的可选交付形态门禁。所有这些产出都不在日常流水线内生成；按需在交付的最后阶段单独运行。

### 4.1 标准 PDF（日常交付）

正式 PDF 交付必须满足：

- PDF 文件重新生成自当前 HTML。
- PDF Document Outline 与 HTML 标题一致。
- 正文前目录条目可点击并指向有效页面。
- Outline 标题不得包含"代码片段"、源码文件名、源码位置或行号范围。

验证命令为：

```bash
python books/src/python/to_pdf.py
python books/src/python/pdf_toc_links.py
python books/src/python/verify_pdf.py
```

### 4.2 印刷级 PDF（可选交付）

印刷级 PDF 是日常 PDF 的并行产出，用于实体印刷或正式归档场景。要求：

- 印刷级 PDF 与日常 PDF 文件分离（`h2-source-code-analysis.pdf` 与 `h2-source-code-analysis-print.pdf`），互不覆盖
- 每章 H1 在印刷级 PDF 上独占一页（chapter cover），含装饰性渐变条与底分隔线
- 目录页每条 TOC 条目以"标题 ………… 页码"虚线对齐渲染
- 页眉左侧含"H2 Database 源码分析"，右侧含版本标识；页脚居中含"第 N 页 / 共 M 页"
- 所有 H1-H4 在 PDF Outline 中可点击跳转
- 印刷级 PDF 文件大小 ≤ 标准 PDF 1.5 倍

验证命令：

```bash
python books/src/python/print_pdf.py
```

视觉验证：在 Chrome / Adobe Reader 中检查 (a) 章首装饰条 (b) TOC 虚线对齐 (c) 页眉/页脚一致出现。

### 4.3 EPUB（可选交付）

EPUB 是面向电子阅读器（Apple Books / Kindle / Calibre / Readium 等）的可选交付形态，**只在交付的最后阶段按需输出**，不进入日常流水线。要求：

- EPUB 由 pandoc 从合并后的 `h2-source-code-analysis.md` 生成；运行前先调用 `merge.py` 保证源最新
- 输出路径：`books/dist/h2-source-code-analysis.epub`（与日常 PDF / 印刷级 PDF 互相独立）
- 元数据：`<dc:title>` / `<dc:creator>` / `<dc:date>` / `<dc:language>=zh-CN` 由 cover.md 自动提取（标题 / 副标题 / 版本 / 作者 / 出版日期）
- 每个 H1 章节在 EPUB 内部独立分卷（`--split-level=1`），便于阅读器分章导航
- 目录深度 H1-H3（`--toc --toc-depth=3`），与 HTML 侧边栏 TOC 层级一致
- 内嵌精简 CSS：等宽字体代码块 + 蓝色左竖条 + 表头蓝底白字 + 引用块浅蓝背景
- 文件大小：合理 EPUB 通常在 2-5 MB 范围；超过 10 MB 视为异常需人工排查

依赖：[pandoc](https://pandoc.org/)（不是日常依赖；只在出 EPUB 时需要）

验证命令：

```bash
python books/src/python/to_epub.py
```

视觉验证：在 Apple Books / Calibre / Readium 中至少查看一章正文 + 一个代码块 + 一张 ASCII 图 + 目录导航是否正常。

EPUB 不接入 `structure.py`（按需交付物均走人工视觉验证起步，与印刷级 PDF 一致）。

## 5. 拒绝标准

以下任一情况不得交付：

- 标准验证流程失败。
- 缺失核心章节、核心流程或核心算法。
- HTML TOC 存在断链或标题数量不一致。
- 代码围栏不平衡或导致正文大段进入代码块。
- 图注格式、源码路径格式或跨章引用出现系统性不一致。
- PDF 交付时未通过 PDF 三步验证。
- 管理文档之间存在版本、路径、流程或职责冲突。

## 6. 维护周期

- 每次文档变更后运行标准流程。
- 每次正式归档或发布前运行 PDF 验证。
- 每次发现新问题时登记到 `books/docs/managements/changelog.md`。

## 7. 门禁等级

每项检查在 `make.py check` 中都有固定级别：P0/P1 阻塞，P2 与 `style.py` 为
advisory（只报告、不阻塞）。新增检查从 P2 起步，误报率与修复成本可接受后升 P1。

| 级别 | 检查项 |
| --- | --- |
| P0 | 章节结构、图号、代码围栏、跨章引用、UTF-8、HTML TOC、合并文档、历史痕迹、图注结构 |
| P1 | 图表覆盖、索引完整性、术语完整性、脚本契约、内容深度、版本一致性、源码坐标 |
| P2 / advisory | 索引 see-also、图簇桥接、延伸思考、印刷级 PDF 视觉、EPUB 视觉、写作风格 |

级别与阈值的事实来源是 `make.py check` 的步骤表与 `data/config/style.json`；
本节只说明分级口径，不记录某项检查何时加入。
