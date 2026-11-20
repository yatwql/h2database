# 质量标准与测试计划

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1

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
python books/src/python/make.py deliver    # build + to_pdf + pdf_toc_links + verify_pdf + to_epub + verify_epub
```

PDF 生成较慢；日常编辑只要求 `make.py check` + `make.py build` 通过。CI（`.github/workflows/book.yml`）自动执行 lint + 单元测试 + 门禁 + 构建 + 幂等性校验。

## 1.2 交付分档

同一套门禁按"什么时候跑"分三档，本地脚本与 CI 一致（`.github/workflows/book.yml`）。
档位由 check_runner.py 的 `--mode` 给出（`fast`/`full`/`release` 是 `p0`/`p1`/`p2` 的
alias），与 §2.1 的**门禁级别**是两个轴：档位决定跑多少，级别决定某一项检查是否阻塞。

| 档 | 触发 | 内容 | 本地命令 |
| --- | --- | --- | --- |
| fast | 每次提交 / PR（`pre-commit` 钩子） | ruff + 结构门禁 + 单元套件（约 16s） | `scripts/check-fast.sh` |
| full | 合入 master / 发布前（`pre-push` 钩子） | 全部门禁（`make.py check --keep-going`） | `scripts/check-full.sh` |
| release | 打版本标签 | full + 慢档（chromium/pandoc）+ 顺序依赖探测 + `make.py deliver` 出产物 | `scripts/check-release.sh` |

度量类单独命名：`scripts/eval-score.sh`（六维评分）、`scripts/test-eval-coverage.sh`
（覆盖率棘轮）。分档只决定"跑到哪一步"，判据本身不分档。

## 2. 质量门禁

### 2.1 门禁分级

`structure.py` 的检查项按"阻塞级别"分为 P0 / P1 / P2 三档（级别只有这三档；报告类不计级别）：

| 级别 | 含义 | 阻塞级别 |
| --- | --- | --- |
| **P0** | 基础完整性 + 渲染正确性 | 任何交付（含日常） |
| **P1** | 内容质量 + 工具可用性 | 正式发布 |
| **P2** | "叙事质量"门禁，按 P2 口径运行 | 可选；当前已全部通过 |

`structure.py` 命令行控制：

```bash
python books/src/python/audit/structure.py                  # 默认 p2 = 全量
python books/src/python/audit/structure.py --gate-level p1  # p0 + p1
python books/src/python/audit/structure.py --gate-level p0  # 仅 p0
```

级别只在 §2.1 的分级表与 §2.2 的检查项表里声明，别处不重复。新增检查从 P2 起步，误报率与
修复成本可接受后升 P1；P0/P1 阻塞，P2 只报告。

### 2.2 各检查项及其级别

| 类别 | 通过标准 | 验证方式 | 级别 |
| --- | --- | --- | --- |
| 章节结构 | 12 章节槽 + 2 附录文件齐全，H1/H2/H3/H4 层级连续；配置的必备段落齐备 | `structure.py`（heading hierarchy / required sections） | P0 |
| 图号与图引用 | 每章图号唯一且完整；正文图号引用可解析；允许历史补号导致非严格位置顺序 | `structure.py`（figure numbering）、`figures.py` | P0 |
| 图表覆盖 | 内容型 `###` 小节 ≥ 2 图；模板型小节 ≥ 1 图 | `smart.py` | P0 |
| 代码围栏与合并稿 | 所有围栏成对；源文件总行数与合并稿一致；合并顺序与前后件齐备 | `structure.py`（code fence balance）、`render/merge.py` | P0 |
| 跨章引用 | 章节互引 ≥ 1，且 `详见第X章《…》` 与真实 H1 一致 | `structure.py`（cross-references）、`crossrefs.py` | P0 |
| HTML 目录与渲染钩子 | TOC 与内容标题 1:1、零断链；`to_html.py` 含 9 项关键 CSS 标记；锚点与侧边栏/印刷目录齐备 | `structure.py`（HTML TOC / CSS style checks）、`render/to_html.py` | P0 |
| 编码 | 合并稿与 HTML 均为有效 UTF-8 | `structure.py`（UTF-8 encoding） | P0 |
| 链接与锚点 | 所有相对链接指向存在的文件；`#anchor` 命中真实标题；代码围栏内不检查 | `links.py` | P0 |
| 配置结构 | `book.toml` 各章节键都在阅读顺序里、列出的章节都存在且无重复；`style.json` 只含已知顶层键、阈值区间合理 | `doc_drift.py`（CONFIG）、`style_schema.py`、`test_config` 用例 | P0 |
| 构建幂等 | 连续两次 `make.py build` 的 HTML 哈希一致 | `.github/workflows/book.yml` | P0 |
| 索引完整性 | 索引 ≥ 120 条；每章 ≥ 5 条；主条目 ≥ 150、子条目 ≥ 50、see-also ≥ 30 且全部解析、子条目章节 ∈ 1-12 | `structure.py`、`index_xrefs.py` | P1 |
| 术语完整性 | 术语 ≥ 60 条；每条有对应章节引用；引用章节号 ∈ 1-12 | `structure.py`（glossary content） | P1 |
| 工具脚本可用性 | 术语表与索引生成脚本语法有效 | `structure.py`（builder checks） | P1 |
| 图注动宾结构 | 全书图注以批准动词起首；长度 ∈ [8, 30] 字；无模糊后缀；strict 阈值下违规 = 0 | `captions.py --threshold strict` | P2 |
| 图簇桥接 | 3+ 张图在 ≤ 40 行内连续出现的"图簇"，前置一句桥接叙事点名所有图 | `figure_clusters.py`（`--window 40 --needs-bridge`，应输出空清单） | P2 |
| 延伸思考 | 12 章全部含 `## N.X 延伸思考`；每章 ≥ 3 题；每题含难度/题型 emoji + 提示行 + 含锚点的回顾行；全书 ≥ 50 题 | `structure.py`、`exercises.py` | P2 |
| 写作风格 | 每章 WARN 计数为 0 | `style.py` | P2 |
| 版本一致 | 工具/源码/书籍三版本可解析且各有唯一事实位；管理文档头齐全且取软件版本；封面版本回写自 `book.toml`；合并稿 manifest 与三者一致 | `version_consistency.py`、`manuscript/cover.py` | P0 |
| 源码坐标 | `Class.java:行号` 可解析、行号在文件长度内、方法存在、摘录与源码一致；已知漂移进基线，仅"新增漂移"阻塞 | `source_refs.py`、`content_depth.py`、`books/data/baselines/source-symbol-baseline.json` | P1 |
| PDF 渲染与 TOC 链接注入 | HTML → PDF 成功、页面数据可读；每个印刷 TOC 条目在对应页上加一条 link annotation，目标页按 outline 位置映射 | `render/to_pdf.py`、`render/pdf_toc_links.py` | P1 |
| PDF 交付 | PDF 重新生成自当前 HTML；A4（595×842±2）、无旋转；字体全部嵌入；outline 与 HTML 标题逐一对应；印刷 TOC 链接按序且在页内；体积 ≤ `pdf_max_mb` | `render/verify_pdf.py`（`--require-toc-links`） | P1 |
| EPUB 结构 | mimetype 首条且未压缩；container/OPF/manifest/spine/nav 全部可解析、导航链接全部命中；元数据齐备；体积 ≤ `epub_max_mb` | `render/verify_epub.py` | P1 |
| EPUB 生成 | pandoc 可用时生成 EPUB（在 `deliver` 组内，生成后由 `verify_epub.py` 校验） | `render/to_epub.py` | P1 |
| 可读性 | 长句、宽 ASCII 图、框线闭合、图注质量 | `readability.py` | P1 |
| 术语与排版规则 | 同一概念不混用两种写法；标题无尾标点；链接文字可读；中英之间留空格；列表标点一致；段落 ≤ 上限（已知项走基线） | `style_rules.py` | P1 |
| 内容深度 | 前向引用须点名主责章节；高频类型须入术语表；练习题须指向本章类型或 §锚点 | `content_depth.py` | P1 |
| ASCII 图质量 | 图宽 ≤ `ascii_max_cols`（CJK 记 2 列）；无行尾空格/制表符；单图不混用框线与 ASCII 边框；已知项走基线 | `diagrams.py`、`books/data/baselines/ascii-baseline.json` | P1 |
| LLM 边界 | LLM 只用于散文生成/评审场景；门禁与事实链路不得调用；密钥文件不入库 | `llm_policy.py` | P1 |
| 发布评分 | 六维评分（功能/稳定/交互/代码/文档风格/文档质量）作为整改视图 | `make.py report` | 报告类（不计级别） |
| 历史快照完整性 | 快照文件与 manifest 记录的哈希一致；快照不参与构建、不被门禁扫描 | `manuscript/snapshot.py verify` | P1 |
| 架构约束 | 分层依赖方向、门禁只读、不硬编码路径、命名不遮蔽标准库、入口脚本均接入 make.py 步骤 | `check_architecture.py` | P0 |
| 章节均衡 | 每章行数/图数/坐标分布 | `balance.py` | P2 |
| 类型检查 | pyright 可用时检查工具链类型（缺失则跳过） | `typecheck.py` | P1 |
| 门禁追溯 | make.py 的每个门禁都在 testplan 登记，反之亦然 | `gate_trace.py` | P0 |
| 需求追溯 | `requirements.md` 的每条 FR/IR/NFR 在 §2.4 有且只有一条判据行，判据点名的载体在仓库里存在 | `requirement_trace.py` | P0 |
| 内容体积 | 每个章节的字节数与行数不低于基线（floor 0.95）、手稿总量不缩水、交付 PDF 页数 ≥ 基线 90%、EPUB 体积 ≥ 基线 85%；新增文件允许，删除须同步 `book.toml` 并重设基线 | `content_volume.py`、`books/data/baselines/content-volume.json` | P0 |
| 文件长度 | 源码 ≤900 行、测试 ≤1200 行、文档 ≤1200 行（手稿附录 ≤2000） | `file_length.py` | P0 |
| 脚本契约 | 每个入口脚本有模块说明、可执行入口、必要时说明退出码与 `--json` | `script_contract.py` | P0 |
| 文档一致性 | 文档与配置的引用对象存在（路径、脚本、章节名、管理目录与索引/目录树、编号源）；同一事实只声明一次（章节键、门禁级别）；引用的交付链路与脚本名前缀清单等于 `make.py` / `check_architecture.py` 里的声明 | `doc_drift.py` | P0 |
| 网络隔离 | 测试全程零出站连接：`_netguard` 在 `_fixture` 导入时接管 socket，只允许回环；LLM 一律 mock，Playwright 用假引擎 | `src/test/_netguard.py`、`src/test/test_no_network.py` | P0 |
| 覆盖率 | 分支覆盖率不低于 `base.json [toolchain].coverage_fail_under` | `make.py cover` | P1 |
| 历史痕迹 | 文档、代码注释、脚本/钩子/CI 注释与配置 `_note` 只描述当前状态 | `traces.py` | P0 |
| 多入口一致 | CLI/TUI/Web 三个渠道共用 `core/actions.py`，`status` 与 `llm-ask` 均可运行 | `src/test/test_llm.py` | P1 |
| LLM 配置 | provider 路由按 章节>书籍>场景 优先级解析；密钥只读环境变量；默认 mock 离线可跑 | `src/test/test_llm.py`、`data/config/llm_*.json` | P1 |
| 运行日志 | 日志写 `books/logs/`，按天回滚；级别 `BOOK_LOG_LEVEL` > 配置 > INFO | `src/test/test_logging.py` | P1 |
| 工具链测试 | 单元 + 集成测试全绿：`make.py test` | `books/src/test/` | P0 |

`structure.py` 默认（`--gate-level p2`）必须达到全部检查通过。

## 2.3 一道门禁一个目的

每道门禁只回答一个问题；出现第二个问题时拆新门禁，不叠加。`gate_trace.py`
校验"`make.py` 里的步骤 ↔ 本节"双向一致。

| 门禁 | 唯一目的 | 相邻门禁的分界 |
| --- | --- | --- |
| `structure.py` | 章节结构与图号/围栏/标题层级是否成立 | 只管"骨架"，不管文字好坏 |
| `links.py` | 链接与锚点能否解析 | 只验可达性，不验内容 |
| `crossrefs.py` | `详见第X章《…》` 是否指向真实章节 | 只验跨章引用，不验链接语法 |
| `doc_drift.py` | 文档与配置的引用对象存在；同一事实只声明一次 | 只验"引用成立、声明唯一"，不验可达性 |
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
| `requirement_trace.py` | 每条需求是否有判据载体 | 只管追溯，不评判据本身是否够强 |
| `portability.py` | 移植性：文本 `open()` 均显式 encoding；ASCII locale 下入口可运行 | 只管环境适配，不评判内容 |
| `test_redundancy.py` | 测试套件卫生：重复用例体、无断言用例、非 TestCase 内的 test_*、同名遮蔽 | 只管测试代码，不判业务 |
| `perf_baseline.py` | 交付速度：各步骤耗时与历史中位数对比，超阈值提示（默认 advisory） | 只管速度退化，不判正确性 |
| 顺序依赖探测（order_dependence，人工触发） | 正序/逆序各跑一次，结果不同即报；不进 `check`，慢档执行 | 只管顺序敏感性，不判正确性 |
| `typecheck.py` | pyright 静态类型检查 | 只管类型 |

合并原则：目的相同且扫描面重叠 → 合并（`traces.py` 用一个脚本覆盖文档与代码两个范围）；
目的不同只是对象相近 → 保持独立（`captions`/`figures`/`diagrams` 都看图，但判据互不重叠）。

报告类（不是门禁，不进 `make.py check`，因此不写入上表）：六维计分卡（`make.py
report` / `eval-score.sh`）、`balance` 的计量输出（`--json`），以及计分卡使用的
文档风格度量（prose_quality，句长/列表/坐标密度），它出分不拦截。

### 2.4 需求判据对照

`requirements.md` 声明“要什么”，本表声明“怎么判”。两者用编号对齐且一一对应：
一条需求只有一行，一行只指向一条需求；载体可以是一个门禁、一个测试文件、一个
工作流，也可以写 `人工复核`（无单文能证明）。`requirement_trace.py` 双向比对
两边编号，并确认点名的载体在仓库里真实存在。

| 需求 | 判据要点 | 判据载体 |
| --- | --- | --- |
| FR-01 | 12 章 H1 唯一、顺序稳定、层级连续 | `structure.py` |
| FR-02 | 每小节图数达标，图号唯一且有图注 | `smart.py`、`figures.py` |
| FR-03 | 源码引用写成 `org/h2/...` 且可解析 | `source_refs.py` |
| FR-04 | 章间引用指向真实章节 | `crossrefs.py` |
| FR-05 | 术语表覆盖高频术语并有章节指引 | `src/python/manuscript/glossary.py` |
| FR-06 | 索引三档条目均指回真实章节 | `index_xrefs.py` |
| FR-07 | 章末四段齐备且顺序固定 | `structure.py` |
| FR-08 | 每章题量、难度、提示行、回顾锚点齐备 | `exercises.py` |
| FR-09 | ASCII 图宽度、框线一致、无行尾空白 | `diagrams.py` |
| FR-10 | 图注动宾起首、长度在区间、图簇有桥接句 | `captions.py`、`figure_clusters.py` |
| FR-11 | 附录 A 三条端到端链路可追到源码坐标 | `src/python/manuscript/case_studies.py`、人工复核 |
| FR-12 | 附录 B 说明相邻版本的影响 | 人工复核 |
| FR-13 | HTML 侧边栏与印刷目录两级与标题一一对应 | `structure.py`、`links.py` |
| FR-14 | PDF 为 A4、字体嵌入、大纲与目录可点击 | `verify_pdf.py` |
| FR-15 | EPUB 容器、清单、阅读顺序、导航齐备 | `verify_epub.py` |
| FR-16 | 封面统计与正文实际内容一致 | `cover.py`、`structure.py` |
| FR-17 | 术语与排版统一，无新增违规 | `style_rules.py` |
| FR-18 | 代码摘录与源码当前版本一致 | `content_depth.py`、`source_refs.py` |
| IR-01 | 单一入口跑完一次完整检查 | `make.py` |
| IR-02 | 按改动域分档，编辑期单次检查 ≤ 5 秒 | `src/python/check_runner.py`、`perf_baseline.py` |
| IR-03 | 分档不改判据，提交/发布跑全集 | `src/python/check_runner.py` |
| IR-04 | 失败给出文件与行号，退出码非 0 即失败 | `script_contract.py` |
| IR-05 | 检查与构建离线完成 | `src/test/_netguard.py`、`src/test/test_no_network.py` |
| IR-06 | 三入口共享同一份动作与状态 | `src/test/test_llm.py`、`src/test/test_app_web.py` |
| IR-07 | 状态摘要一屏，含阶段与最近一次结果 | `src/test/test_app_tui_interaction.py` |
| IR-08 | 耗时步骤打印阶段，失败不吞掉已有结果 | `src/python/check_runner.py`、`src/test/test_logging.py` |
| IR-09 | 已接受问题可读，消失条目提示收缩 | `src/python/lib/_baseline.py` |
| NFR-01 | 逐章体量与交付页数不低于基线 | `content_volume.py` |
| NFR-02 | 连续两次构建的 HTML 逐字节一致 | `.github/workflows/book.yml` |
| NFR-03 | 依赖版本固定，交付只用项目解释器 | `make.py`、`bootstrap.sh` |
| NFR-04 | 存量入基线，新增同类问题失败 | `src/python/lib/_baseline.py` |
| NFR-05 | 四档耗时在预算内 | `perf_baseline.py` |
| NFR-06 | PDF ≤ 12 MB、EPUB ≤ 10 MB | `verify_pdf.py`、`verify_epub.py` |
| NFR-07 | 历史稿只读，不入构建与扫描 | `src/python/manuscript/snapshot.py` |
| NFR-08 | 阈值与路径全部读配置，不内联 | `check_architecture.py`、`style_schema.py` |
| NFR-09 | 三平台一致：显式编码、无绝对路径 | `portability.py` |
| NFR-10 | 检查与构建阶段零出站连接 | `src/test/test_no_network.py` |
| NFR-11 | 源文件与文档长度受预算约束 | `file_length.py` |
| NFR-12 | 文档与注释只描述当前状态 | `traces.py` |

## 3. 格式规范

- 图注格式：`**图 X-Y: Title**`，独立成行，不放入代码围栏。
- ASCII 图围栏：使用 ` ```text `。
- Java 代码围栏：使用 ` ```java `；SQL 使用 ` ```sql `。
- 源码路径：使用 `org/h2/...`，不使用 `h2/src/main/...` 前缀。
- 源码引用：使用 `ClassName.java:行号`，但不得放入章节标题或 PDF Outline 标题。
- 跨章引用：使用 `详见第X章《实际 H1 标题》`。

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
python books/src/python/render/to_pdf.py
python books/src/python/render/pdf_toc_links.py
python books/src/python/render/verify_pdf.py
```

### 4.2 印刷级 PDF（可选交付）

印刷级 PDF 是日常 PDF 的并行产出，用于实体印刷或正式归档场景。要求：

- 印刷级 PDF 与日常 PDF 文件分离（`h2-source-code-analysis.pdf` 与 `h2-source-code-analysis-print.pdf`），互不覆盖
- 每章 H1 在印刷级 PDF 上独占一页（chapter cover），含装饰性渐变条与底分隔线
- 目录页每条 TOC 条目以"标题 ………… 页码"虚线对齐渲染
- 页眉居中含配置给出的页眉标识（`book.toml [project].running_head`），页脚居中含"第 N 页 / 共 M 页"
- 所有 H1-H4 在 PDF Outline 中可点击跳转
- 印刷级 PDF 文件大小 ≤ 标准 PDF 1.5 倍

验证命令：

```bash
python books/src/python/render/print_pdf.py
```

印刷级 PDF 由独立工具生成：它不在 `make.py` 的步骤表里，而在 `deliver` 之后按需单独调用。

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
python books/src/python/render/to_epub.py
```

视觉验证：在 Apple Books / Calibre / Readium 中至少查看一章正文 + 一个代码块 + 一张 ASCII 图 + 目录导航是否正常。

EPUB 的自动校验由 `verify_epub.py` 承担（§2.2「EPUB 结构」，P1），`structure.py` 不参与；
样式或模板变更时仍建议按上面的清单人工看一遍。

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
- 新发现的已知问题登记到 `data/baselines/`，经评审后固化；版本级变更才写 `changelog.md`。
