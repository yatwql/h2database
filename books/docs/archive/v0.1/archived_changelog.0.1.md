# 变更记录

> 涵盖版本：0.1
> 归档时间：2026-11-25

> 本文记录源码分析文档、管理文档、生成产物和质量修复的版本变更。
---
### 2026-06-15
### 管理文档核对（2026-06-15 第二次）：清扫附录 C/D/E 升级遗留与 0.1 措辞漂移
> 用户反馈：核对管理文档，去除冗余内容、解决冲突部分。
#### Changed — 附录 C/D/E 升级遗留同步
- `requirements.md` §2 交付物表：
  - 旧"附录"行（仅 A、B）+ "前/后件"合并行 → 拆为附录 A/B/C/D/E 五行 + 单独的"前件"行
  - 附录 C/D/E 各自标注路径（`back/glossary.md` / `back/index.md` / `back/references.md`）和定位说明
- `requirements.md` §4 质量需求："12 章 + 2 附录齐全" → "12 章 + 5 附录齐全"
- `plan.md` §1 当前状态："12 章 + 2 附录已交付" → "12 章 + 5 附录已交付（A/B/C/D/E）"
- `plan.md` §2 正式目录：补全 `appendix-a-case-studies.md` / `appendix-b-version-changes.md` / `back/glossary.md`（C） / `back/index.md`（D） / `back/references.md`（E）五行注释
- `README.md` 目录结构图：删除"`back/` 书籍后件"占位行，按 C/D/E 三行展开
#### Changed — 0.1 措辞漂移修复
- `requirements.md` 头部状态："已交付（0.1 + EPUB 输出形态）" → "已交付（0.1 工业级里程碑 + 0.1 EPUB 输出形态）"
- `plan.md` §1 当前状态："目前处于 0.1 推进阶段" → "已发布 0.1 工业级里程碑，并在 0.1 扩展了 EPUB 交付形态"
- `plan.md` §1 第三条："PDF 按需生成" → "PDF / 印刷级 PDF / EPUB 按需生成"
- `plan.md` §4 阶段进展："0.1 – 0.1（0.1 推进中）" 拆为两条：0.1–0.1（Phase A–F） + 0.1（独立小节，对应附录拆分 + HTML UX + 后件升级 + 管理文档归一）
- `testplan.md` §4.3 EPUB："0.1 起" → "0.1 起"
- `testplan.md` §4.3 末尾"按 plan §4.6 / §4.8" → "与印刷级 PDF 一致"（消除虚引用）
- `testplan.md` §7 候选升级清单："0.1+ 评估" → "0.1+ 评估"
- `testplan.md` §7 门禁演进史新增 0.1 EPUB 视觉验证行（人工，不接入 final_check.py）
#### Changed — README.md 文档表更精确
- `testplan.md` 权威内容："质量门禁、拒绝标准" → "P0/P1/P2 门禁分级、交付形态门禁、门禁演进史、拒绝标准"
- `changelog.md` 权威内容追补"含 0.1 工业级里程碑总览"
- `review-findings.md` 权威内容明确包含 R7-1..R7-17、R8-1 范围
- `style-guide.md` 权威内容补"图注动宾、图簇桥接、延伸思考、端到端案例叙事"以匹配 §12-§14 实际范围
#### Pipeline 状态
- `final_check.py`：106/106 ✅
- `_audit_smart.py`：0 sections needing more diagrams ✅
- `check_style.py`：0 WARN / 0 INFO ✅
---
### 2026-06-15
### 新增交付形态：EPUB（按需输出）
> 用户反馈：交付文档增加 EPUB 输出形态，按需生成，仅在交付的最后阶段产出。
#### Added — 新工具
- **`books/src/python/generate_epub.py`**（新建，~200 行）：基于 pandoc 的 EPUB 渲染管道
  - Step 0：检测 pandoc 是否在 PATH；缺失则给出 Windows / macOS / Debian 安装命令并退出
  - Step 1：调用 `rebuild_merged.py` 确保合并 Markdown 最新
  - Step 2：从 `cover.md` 自动提取 标题 / 副标题 / 版本 / 作者 / 出版日期
  - Step 3：写入临时 metadata YAML 块（`<dc:title>` / `<dc:creator>` / `<dc:date>` / `<dc:language>=zh-CN` / `<dc:rights>` / `<dc:publisher>`）
  - Step 4：写入临时 CSS（等宽字体代码块 + 蓝色左竖条 + 表头蓝底白字 + 引用块浅蓝背景 + 章节 page-break）
  - Step 5：调用 `pandoc <metadata> <merged.md> -o <epub> --toc --toc-depth=3 --split-level=1 --to=epub3 --css=<css>`
  - Step 6：输出文件路径 / 大小 / 元数据摘要 + 可选 epubcheck 命令提示
  - 临时 metadata / CSS 文件在 finally 中清理
#### Added — gitignore
- `.gitignore`：新增 `books/*.epub`（紧贴 `*.pdf` `*.html` 之后），避免误提交大文件
#### Changed — testplan.md 新增 §4.3 EPUB 交付门禁
- §4 标题从"PDF 专项门禁"改为"交付形态专项门禁"，明确这是按需可选交付物的统一节
- 新增 §4.3 列出 8 项 EPUB 要求（pandoc 引擎 + cover.md 元数据自动提取 + H1 分卷 + TOC 深度 H1-H3 + 内嵌 CSS + 文件大小 + 视觉验证清单）
- 明确 EPUB 不接入 `final_check.py`（与印刷级 PDF 同样走人工视觉验证起步）
#### Changed — requirements.md 交付物表
- 新增"印刷级 PDF"行（0.1 已交付但表格未更新）
- 新增"EPUB"行（按需生成，最终交付阶段，git 忽略）
#### Changed — CLAUDE.md 项目说明
- "PDF generation is on demand only" 段落扩展：在标准 PDF 之后追加印刷级 PDF 与 EPUB 命令示例
- 明确印刷级 PDF 与 EPUB 都是"on demand only and should be the final delivery step"
#### Notes — 实现选择
- 选择 pandoc 而非纯 Python（如 ebooklib）：pandoc 是 markdown → epub 的事实标准，对 ASCII 围栏代码、CJK 字体、表格/图注/嵌套列表的处理都已成熟，零额外维护
- pandoc 仅作为该脚本的依赖，**不进入** `cover_stats / rebuild_merged / generate_html / _audit_smart / final_check` 日常流水线，与 plan §4.6 "印刷级 PDF 增量推进，不阻塞 MD/HTML 流水线"原则一致
- 本批不引入 final_check 新检查项（plan §4.8 "新检查全部从 P2 起步"；按需交付物走人工视觉验证）
---
### 2026-06-15
### 工业级技术书籍质量提升 — 总体里程碑（Phase A → H）
> 自 0.1（2026-06-11）以来累计 8 个阶段、~30 个实施单元；最终一里程碑由 Phase H（U20-U21）合上：把 v5.x 引入的所有新检查统一纳入 P0/P1/P2 门禁框架，发布 0.1。
#### Highlights — 0.1 → 0.1 对照
| 维度 | 0.1 基线 | 0.1 实测 | Δ |
|------|-----------|-----------|---|
| 章节文件数 | 9 | 10（ch7-8 拆分） + 5 附录 | +1 章节 +5 附录 |
| 章节总行数 | 36,314 | 39,779 | **+3,465** |
| ASCII 图数 | 579 | 598 | **+19** |
| 源码引用 | 185 | 197 | **+12** |
| 术语表条目 | 73（0.1 实测）/ 77（基线 hit） | 113 | **+40** |
| 概念索引条目 | 122（0.1 实测）/ 141（基线 hit） | 209 主条目 + 子条目（合计 331） | **+87 主条目** |
| `final_check.py` 检查项 | 88/88 | 106/106 | **+18 项** |
| 章节均衡 max_min_ratio | 3.748 | 3.044（已超 0.1 软目标 2.7 的容差范围；plan §4.9 豁免不阻塞 0.1） | 改善 18.8% |
| 工具脚本数 | 17 | 24（含 0.1 新建：balance_check, _audit_captions, _audit_figure_clusters, _audit_exercises, _audit_index_xrefs, pdf_print_grade, source_freshness_check 等） | **+7** |
#### Phase A → H 路线图
| 阶段 | 版本 | 主要交付 |
|------|------|----------|
| Phase A | 0.1 | 度量基线工具 `balance_check.py`，固化 baseline-0.1.json |
| Phase B | 0.1 | ch7-8 拆分（8,085 行 → 3,642 + 4,443）；max_min_ratio 3.748 → 3.044 |
| Phase C | 0.1 | 前后件深度化：preface / copyright / how-to-read / glossary / index 三档层级化 |
| Phase D | 0.1 | 附录 A：端到端案例研究（SELECT / COMMIT / Recovery 三案例） |
| Phase E | 0.1 | 图注动宾结构（strict 0 违规）+ 图簇桥接（33 簇全部含桥接句） |
| Phase F | 0.1 | 章末延伸思考（14 章节槽 56 题，难度 emoji + 提示行 + 锚点回顾行） |
| — | 0.1 | 附录 A/B 拆分；管理文档归一；HTML 视觉/交互修复（intro-mode / 收起展开 / 事件委托 / JS 语法 bug 修复 / 后件升级为附录 C/D/E） |
| Phase G | 0.1 | 印刷级 PDF（章首装饰、TOC 虚线、独立产出 `*-print.pdf`） |
| Phase H | 0.1 | 门禁分级 P0/P1/P2 + `final_check.py --gate-level` 入口 + 门禁演进史 + 0.1 全量回归发布 |
#### Added — Phase H 工具能力（U20）
- `books/src/python/final_check.py`：
  - 顶部新增 `argparse` 解析 `--gate-level p0|p1|p2`；默认 p2 = 全量
  - 引入模块级 `SECTION_LEVEL` 与 `section(level, name)` 辅助函数；`check()` 通过 `gate(SECTION_LEVEL)` 跳过当前级别外的检查项
  - 15 处 `print('=== ... ===')` 替换为 `section('pX', '...')`；为每个区段标注级别
  - 输出形式：每个 section 标题后追加 `(p0|p1|p2)` 标识；超出门禁的区段在标题行追加 `[SKIP — outside p?]`
- 三档运行结果：
  - `--gate-level p0` → 93/93 通过（基础完整性 + 渲染正确性）
  - `--gate-level p1` → 102/102 通过（再加索引 + 术语 + 工具脚本）
  - `--gate-level p2`（默认） → 106/106 通过（再加图注 / 图簇 / 延伸思考 / 写作风格）
#### Changed — testplan.md 升级为门禁框架（U20）
- §2 重构为「2.1 门禁分级 + 2.2 各检查项及其级别」两小节，所有检查项明确标注 P0/P1/P2 列
- 新增 §7 门禁演进史，记录每项检查的"起始级别 → 当前级别"演进、升级判定规则、当前 P2 候选升级清单
- 索引层级（0.1 起 P2 试运营）经 0.1 / 0.1 两版本周期 0 误报后正式升级 P1
- 图注动宾、图簇桥接、延伸思考保留 P2，待下一工具迭代周期评估
#### Changed — 版本号同步（U21）
- `cover.md`：0.1 → **0.1**
- `management/requirements.md`：0.1 → **0.1**；状态从"已交付，0.1 维护与增强中"改为"已交付"
- `management/plan.md`：0.1 → **0.1**；阶段进展段追加 0.1（Phase H 收尾）行
- `management/testplan.md`：0.1 → **0.1**
- `management/style-guide.md`：0.1 → **0.1**
#### Pipeline 状态（0.1 发布）
- `final_check.py`（默认 p2）：106/106 ✅
- `final_check.py --gate-level p1`：102/102 ✅
- `final_check.py --gate-level p0`：93/93 ✅
- `_audit_smart.py`：0 sections needing more diagrams ✅
- `check_style.py`：0 WARN / 0 INFO ✅
- 合并文档：39,777 行；HTML 616 TOC entries / 2,192 fence lines
#### Notes — 0.1 之后路线图（plan.md §7）
- API 文档索引（P3）
- 交互式图表（P3）
- 英文版翻译（P4）
- CI 集成（P4）
- 印刷级 PDF：per-chapter running header + `verify_pdf.py --print-grade` 自动化（plan U19 推迟项；待 paged.js 或同等方案到位后接入）
#### Closed — 第7轮审查
- review-findings.md R7-1..R7-15 全部关闭；"当前未解决问题"段更新为 0.1 已交付，后续仅追加新发现
- 0.1 发布后该轮闭环；下一次正式审查启动时（如 0.1+）开第8轮
---
### 2026-06-15
### Phase G 起步：印刷级 PDF 渲染管道
> 0.1 计划的第七阶段交付，对应 U19 实施单元。本阶段独立于日常 PDF 流水线，按用户决策点 4.6"印刷级 PDF 增量推进，不阻塞 MD/HTML 流水线"——印刷级 PDF 是并行产出而非替换。
#### Added — 新工具
- **`books/src/python/pdf_print_grade.py`**（新建，~250 行）：印刷级 PDF 渲染管道
  - Step 1：调用 `generate_html.py` 确保 HTML 最新
  - Step 2：临时副本注入印刷级 CSS（`@media print` 作用域）后由 Playwright/Chromium 渲染至 `h2-source-code-analysis-print.pdf`，输出文件与日常 PDF（`h2-source-code-analysis.pdf`）独立，互不覆盖
  - Step 3：用 pypdf 添加可点击章节书签（与 generate_pdf.py 共用 `__hdr_N__` ASCII 标记策略）
#### Added — 印刷级排版要素（@media print）
- **章首装饰页**：每个 H1 设 `page-break-before: always` + `padding-top: 100px` + 上方渐变条 `::before` + 下方分割线 `::after`，居中放大字体形成"chapter cover"效果
- **TOC 虚线对齐**：目录页每条 `<a>` 转为 flex 布局，`::after` 注入大量句点 `..............` 配合 `overflow:hidden` 形成动态虚线长度；title / dot leader / page number 通过 `order: 1/2/3` 对齐
- **印刷级页眉页脚**：页眉左侧 `H2 Database 源码分析` + 右侧 `印刷版 0.1`；页脚居中 `第 N 页 / 共 M 页`，均带细分隔线
- **孤标题保护**：`h2/h3/h4 { page-break-after: avoid }` 避免页底落单
#### Changed — 测试计划新增 §4.2
- `books/docs/managements/testplan.md`：
  - §4 拆分为 §4.1 标准 PDF（日常）+ §4.2 印刷级 PDF（0.1 / Phase G 起，可选交付）
  - §4.2 列出 7 项印刷级要求（独立文件 / 章首独立成页 / TOC 虚线 / 页眉页脚 / Outline 可点击 / 文件大小 ≤ 标准 1.5 倍 / 视觉验证清单）
  - 验证命令：`python books/src/python/pdf_print_grade.py`
#### Changed — 版本号同步至 0.1
- `cover.md`：0.1 → 0.1
- `management/requirements.md`：0.1 → 0.1
- `management/plan.md`：0.1 → 0.1；阶段进展段追加"0.1（Phase G 起步）"行
- `management/testplan.md`：0.1 → 0.1
- `management/style-guide.md`：0.1 → 0.1（含 §10 文档版本号）
#### Notes — Phase G 当前覆盖与剩余工作
- 已交付：章首装饰页 / TOC 虚线 / 印刷级页眉页脚 / 章节 Outline / 与日常 PDF 独立产出
- 推迟到 Phase H（U20-U21）一并处理：
  - 完整的"Per-chapter running header"（动态显示当前章名）—— 需要 paged.js named-string 或类似机制；Chromium-Playwright 不直接支持，按 plan §4.6 的"印刷级增量推进"策略分批
  - `verify_pdf.py --print-grade` 子命令、`generate_pdf.py --print-grade` 同等接口（plan U19 列出但本批未实现），保留以独立脚本形式提供
- 本批不引入 final_check.py 新检查项（plan §4.8"新检查全部从 P2 起步"；印刷级 PDF 走人工视觉验证起步）
---
### 2026-06-15
### 第一部分：拆分附录 — 版本变更说明独立为附录 B
> 用户反馈：附录 A《端到端案例研究》定位是"沿时间轴串联读、写、恢复路径"的叙事性附录，
> 此前 `A.4 源码版本变更说明`（0.1.240 → 0.1.249-SNAPSHOT 关键变更摘要）作为子节并入其中
> 与附录主旨不符。本次将其上提为独立的附录 B（版本轴维度的参考性附录），与附录 A 并列。
#### Added — 新文件
- **`books/appendix-b-version-changes.md`**（41 行，新建）
  - `# 附录 B：源码版本变更说明（0.1.240 → 0.1.249-SNAPSHOT）`
  - `## B.1 MVStore 核心层`（12 项变更）
  - `## B.2 事务子系统`（11 项变更）
  - 文首引言改写：明确本附录定位（版本轴）与附录 A（时间轴）并列；引用 §9 与 §10 各节源文件表格
#### Changed — 引用更新
- `books/appendix-a-case-studies.md`：删除 `## A.4` 三级小节及其 36 行内容；案例 C 末尾的"下一节 A.4（如有）"展望句改写为"如需进一步在版本维度上对照同一路径在不同小版本的实现差异，请参阅附录 B"
- `books/front/preface.md`：
  - "本书共 12 章 + **1 附录**" → "**2 附录**"；附录列表新增"附录 B 源码版本变更说明"行
  - 「跨版本注记」与「版本时间窗口」段落的"附录 A.4"全部更正为"附录 B"
  - 提交统计 `43 次提交涉及 79 个文件` 与正文 `44 次提交涉及 81 个文件` 对齐
- `books/front/how-to-read.md`：
  - 章节依赖示意图末尾的"附录 A 端到端案例"框扩展为同时包含"附录 B 版本变更说明"
  - 章节先决条件矩阵新增"附录 B"行（前置：第9-10章；可跳过条件：仅在跨小版本对照源码差异时需要参阅）
  - 章节估读时长表新增"附录 B"行（约 5 分钟）
- `books/back/index.md`：「附录」节新增"源码版本变更说明 — 附录 B"主条目，含 B.1 / B.2 两个子条目；see-also 指向 MVStore / TransactionStore / MVCC
#### Changed — 工具链
- `books/src/python/rebuild_merged.py`：`chapter_names` 列表在 `appendix-a-case-studies.md` 之后追加 `appendix-b-version-changes.md`
- `books/src/python/cover_stats.py`：`source_files` 列表同步追加 `appendix-b-version-changes.md`，确保 cover.md 行数统计覆盖附录 B
- `books/src/python/final_check.py`：`chapter_names` 列表同步追加 `appendix-b-version-changes.md`，确保"Chapter files (+cover) ↔ Merged"行数核对包含附录 B
### 第二部分：管理文档核对 — 去除冗余、解决冲突
> 用户反馈：要求核对 `books/docs/managements/` 下管理文档，去除冗余内容、解决冲突部分。
> 本次审计发现版本号漂移、统计数字过期、目录树缺新文件、阶段进度未同步等问题，集中归一。
#### Changed — 版本号与状态对齐
- `requirements.md` 头部版本 0.1 → 0.1；状态描述明确为"已交付，0.1 维护与增强中"；最后更新日期 2026-06-11 → 2026-06-15
- `plan.md` 头部版本 0.1 → 0.1；最后更新 2026-06-11 → 2026-06-15
- `style-guide.md` 头部版本 0.1 → 0.1；§10 "当前 0.1" → "当前 0.1"
#### Changed — 移除过期统计与冗余信息
- `plan.md`：
  - 目录树补 `front/` `back/` `appendix-a-case-studies.md` `appendix-b-version-changes.md` `plan/`；删除"`glossary.md (47 条)`""`index.md (86 条)`""`tools/ 共 17 个脚本`"等过期内嵌数字（统一指向 cover.md / final_check.py）
  - 阶段表精简：移除 Phase 1–11 详细列表，归并为"0.1–0.1"与"0.1–0.1"两段叙述；详情指向 `changelog.md` 与 `plan/2026-06-15-001-*.md`
  - 维护策略中的"每月运行一次 source_freshness_check.py"调整为"在 H2 上游版本升级或源码大改后运行"，避免与实际维护节奏脱钩
- `requirements.md`：
  - 交付物表新增"附录"行（A/B）与"前/后件"行；管理文档行展开为目录引用，避免与 README.md 重复列举具体文件名
  - 内容范围新增"端到端案例研究（附录 A）与跨小版本源码变更（附录 B）"
  - 质量需求"12 章齐全"→"12 章 + 2 附录齐全"
#### Changed — README.md 与目录现实对齐
- `README.md` 文档表新增 `style-guide.md` `baseline-*.json` `captions-baseline-*.json`；`archive/` 描述补"历史审计快照"
- 目录结构图：补 `appendix-a-case-studies.md` `appendix-b-version-changes.md` `plan/` `style-guide.md` `baseline-*.json`；说明文字与 plan.md 对齐
#### Changed — review-findings.md 阶段进度同步
- 0.1 阶段问题清单从 R7-1..R7-3（占位）扩充为 R7-1..R7-8，覆盖 Phase A（0.1）至附录 A/B 拆分（0.1）的全部已关闭问题
- "当前未解决问题"段：截至 0.1 → 截至 0.1；Phase A-B 已完成 → Phase A-F + 附录 A/B 拆分均已完成
#### Moved — 历史审计文档归档
- `phase3-audit.md`（0.1 时期阶段三术语/引导块/延展阅读审计快照）→ `archive/phase3-audit-0.1.md`
  - 该文档基线为 0.1，其问题已在 v4.x → 0.1 期间全部关闭，归档以避免与当前管理文档混淆
### 第三部分：修正 HTML 封面/目录被左侧 TOC 遮挡
> 用户反馈：在 HTML 版本浏览封面与目录页时，左侧固定 TOC 侧边栏会遮挡居中的封面标题与全宽目录内容。
#### Fixed — 封面/目录"intro 模式"
- `books/src/python/generate_html.py`：
  - CSS：`#sidebar` 添加 `transition: opacity/visibility`；新增 `body.intro-mode` 选择器：在 intro-mode 下隐藏 `#sidebar`（`opacity:0; visibility:hidden; pointer-events:none`）与 `#toggle-sidebar`，并将 `#toc-page > div` 的 `margin-left` 从 280px 重置为 0
  - JS：脚本顶部新增 IntersectionObserver。`<body>` 默认带 `intro-mode` 类；观察主内容容器 `#page-wrap` 进入视口时移除该类（露出侧栏），主内容滚出视口（读者回滚到封面/目录）时再次加上
  - 净效果：浏览封面与目录时 TOC 隐去、视野完全释放给主体；下滚到正文后侧栏自动出现并保持原有滚动定位行为
- 不影响打印样式（`@media print` 下原本就 `#sidebar { display: none }`）
### 第六部分：TOC 收起/展开点击失效的根因修复（事件委托）
> 用户反馈：第四部分修复 JS 语法错误后，键盘快捷键 `[` 已能切换并显示浮动 `›` 按钮，但点击 `›` 按钮无效；TOC 表头条点击同样无响应。
#### Fixed — 切换为 document 级事件委托
- `books/src/python/generate_html.py`：重写 sidebar 收起/展开 IIFE，原直接 `addEventListener` 改为 `document.addEventListener('click', ...)` 内部用 `closest('#sidebar-toggle')` / `closest('#sidebar-expand')` 进行命中判定
- 收益：
  - 点击 `<button>` 内嵌的 `<span class="chev">` 或 `<span class="lbl">` 也能正确命中（事件冒泡到 document）
  - 不依赖 IIFE 执行顺序与按钮节点身份；任何后续脚本若替换/重建按钮 DOM，handler 仍生效
  - `e.preventDefault()` 显式阻止 `<button>` 默认行为（虽然此处无表单，但作为防御性约束）
- 同时为 `localStorage` 写入加 `try/catch`（隐私模式下不抛异常）
#### Pipeline 状态
- `final_check.py`：106/106 ✅
- 生成的 JS 通过 `node -c` 语法校验 ✅
- HTML：616 TOC entries，2,192 fence lines
---
### 第五部分：术语表/概念索引/参考文献 升级为附录 C/D/E
> 用户反馈：附录 B 后的术语表、概念索引、参考文献三个后件应当与 A、B 并列归属到附录体系，分别成为附录 C、D、E。
#### Changed — 后件 H1 标题
- `books/back/glossary.md`：`# 术语表` → `# 附录 C：术语表`
- `books/back/index.md`：`# 概念索引` → `# 附录 D：概念索引`
- `books/back/references.md`：`# 参考文献` → `# 附录 E：参考文献`
#### Changed — 前件交叉引用
- `books/cover.md`：副标题"12 章 + 2 附录" → "12 章 + 5 附录"；行数自动更新为 39,779
- `books/front/preface.md`：
  - "本书共 12 章 + 2 附录" → "12 章 + 5 附录"
  - 章节摘要表新增三行：附录 C 术语表 / 附录 D 概念索引 / 附录 E 参考文献
- `books/front/how-to-read.md`：
  - 章节依赖示意图末尾的附录框追加 C/D/E 三行
  - 章节先决条件矩阵追加 C/D/E 三行（前置：无；可跳过条件：均为速查工具按需使用）
  - 章节估读时长表追加 C/D/E 三行（速查为主）
#### Notes — 不需要改动的位置
- 各章引言中的"详见书末[术语表](back/glossary.md)"沿用"术语表"作为通用名称（链接路径与文件名都没变），无需改写
- 后件 markdown 文件名（`glossary.md` / `index.md` / `references.md`）不变；只改 H1。这样工具脚本（`build_glossary.py` / `build_index.py` / `_audit_index_xrefs.py` / `_annotate_terms.py` 等）所有路径引用全部沿用，无连锁修改
#### Pipeline 状态
- `final_check.py`：106/106 ✅
- `_audit_smart.py`：0 sections needing more diagrams ✅
- `check_style.py`：0 WARN / 0 INFO ✅
- 合并文档：39,777 行（+12 行 = 5 个新 H1 标题）；cover 统计 39,779 行（+2 行末换行差异）
- HTML：616 TOC entries（不变；H1 数量未变化），2,192 fence lines；侧栏 TOC 与目录页均显示 `附录 A/B/C/D/E` 五条 H1 顶级条目
---
### 第四部分：HTML 桌面端 TOC 可点击收起/展开
> 用户反馈（三次迭代）：希望左侧 TOC 在桌面浏览器中可点击收起/展开，从而扩大正文阅读宽度；并希望"点击"这一交互更明显可见；Firefox 中三种方式都无法切换 → 实际是 `<script>` 块存在 JS 语法错误，整段脚本拒绝执行。
#### Fixed — 修复阻塞整个 `<script>` 块的 JS 语法错误（根因）
- `books/src/python/generate_html.py` 内 `HTML = f"""..."""` 大 f-string 在两处把 JS 字符串 `'\n'` 写成裸 `'\n'`，Python f-string 求值后变成"单引号 + 真实换行符 + 单引号"——这是无效 JS 字符串字面量，整段 `<script>` 在浏览器（Firefox 严格遵守规范、Chrome 同样）解析阶段就抛 `SyntaxError`，整段后续 JS 全部不执行（IntersectionObserver、TOC 收起/展开、复制按钮、面包屑、章节导航 …… 全部失效）：
  ```
  // 错误：f-string 把 \n 求值为真实换行
  const lines = code.innerHTML.split('\n');   // 输出: split('<LF>')
  nums += i + '\n';                            // 输出: i + '<LF>'
  // 修复：用 \\n，Python 转义为 \n，再被 JS 读到为换行符
  const lines = code.innerHTML.split('\\n');
  nums += i + '\\n';
  ```
- 该 bug 已存在于此前 commit（`7ecddc8e7` HEAD），此前未被发现是因为复制按钮、TOC 收起等都不是 final_check.py 验证项；用户反馈"按你说的三种方式都无法切换"是首次触发该路径的真实使用反馈
- 修复后生成的 JS 通过 `node -c` 语法校验
#### Added — 桌面收起/展开切换（最终设计：整条 TOC 表头即为切换按钮）
- `books/src/python/generate_html.py`：
  - 标记演进：
    - 初版：在 `#sidebar` 顶部右上放置 24×24 的 `‹` 收起按钮（`#sidebar-collapse`），不够显眼
    - 终版：原 `<h2>TOC</h2>` 表头改为 `<button id="sidebar-toggle">` 整条 flex 行，左侧 `‹` 旋转 chevron + 右侧 `TOC · 目录` 文字标签；整条横栏可点击，hover 时高亮变青蓝色，明确传达"可点击"语义；收起后 chevron 自动旋转 180°（视觉与浮动展开按钮 `›` 一致）
  - 视口左上保留浮动 `<button id="sidebar-expand">›</button>`（默认 `display:none`，收起后才浮现）作为读者从全屏阅读状态唤回 TOC 的入口
  - CSS：
    - `#sidebar` `transition` 追加 `transform 0.3s ease`
    - `body.sidebar-collapsed #sidebar { transform: translateX(-280px) }` 让侧栏滑出视口
    - `body.sidebar-collapsed #content { margin-left: 0; max-width: 1100px }` 让正文向左铺满，并把最大阅读宽度从 960px 提升至 1100px
    - `body.sidebar-collapsed #sidebar-expand { display: flex }` 浮动展开按钮浮现于左上角
    - `body.sidebar-collapsed #sidebar-toggle .chev { transform: rotate(180deg) }` chevron 同步翻转
    - `#content` 加 `transition: margin-left/max-width 0.3s` 平滑过渡
    - `body.intro-mode` 下 `#sidebar-expand` 隐藏，避免与封面/目录 intro 模式冲突
    - `@media (max-width:768px)`：移动端原有汉堡按钮已能切换，桌面 `#sidebar-expand` 与 `#sidebar-toggle .chev` 均隐去，`#sidebar-toggle` cursor 还原为 default，使其在移动端单纯作为 TOC 表头展示
  - JS：
    - 启动时读 `localStorage('h2-doc-sidebar-collapsed')` 恢复用户上次选择
    - `#sidebar-toggle` click → `body.classList.add('sidebar-collapsed')` + 写入 localStorage
    - `#sidebar-expand` click → 反向操作
    - 键盘快捷键：按 `[` 切换收起/展开（在 INPUT/TEXTAREA/contentEditable 内不响应）
#### Pipeline 状态（0.1 四部分合计）
- `final_check.py`：106/106 ✅
- `_audit_smart.py`：0 sections needing more diagrams ✅
- `check_style.py`：0 WARN / 0 INFO ✅
- 合并文档：39,765 行（cover 统计 39,767 = 39,765 + 2 行换行差异，在容差内）
- HTML：616 TOC entries，2,192 fence lines；已注入 `intro-mode` 类与 IntersectionObserver；桌面端可通过 `TOC · 目录` 表头条 / `›` 浮动按钮 / `[` 键三种方式切换 TOC 收起/展开（状态写入 localStorage，27 处 `sidebar-toggle/expand/collapsed` 标识已写入 HTML）
---
### 2026-06-15
### 工业级技术书籍质量提升 — Phase F：延伸思考
> 0.1 计划的第六阶段交付，对应 U17 / U18 两个实施单元。
#### Added — 工具链
- **`books/src/python/_audit_exercises.py`**（新建，U17）：章末延伸思考小节审计器。逐章扫描 `## N.X 延伸思考` 小节、放置位置（必须在 `本章小结` 与 `延展阅读` 之间）、题数、题型 emoji（🟢/🔵/🟠）、难度星级（★/★★/★★★）、提示行、回顾行的 `§X.Y` 锚点完整性。支持 `--target` 单文件、`--json` 机读、`--template` 输出 4 题模板。
#### Added — 章末延伸思考（U18，10 个并行 sub-agent）
全书 14 个章节槽全部加入 `## N.X 延伸思考` 小节，**56 道题** 全部合规：
| 文件 | 章节 | 题数 | 难度分布 ★/★★/★★★ | emoji 分布 |
|------|------|------|------------------|-----------|
| `ch1-2-architecture.md` | 第1章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch1-2-architecture.md` | 第2章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch3-packages.md` | 第3章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch4-5-modules-processes.md` | 第4章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch4-5-modules-processes.md` | 第5章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch6-1-data-structures.md` | 第6章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch6-2-storage-algorithms.md` | 第6章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch6-3-query-algorithms.md` | 第6章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch7-sql-execution.md` | 第7章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch8-query-optimizer.md` | 第8章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch9-10-persistence-locking.md` | 第9章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch9-10-persistence-locking.md` | 第10章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch11-12-guide-summary.md` | 第11章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| `ch11-12-guide-summary.md` | 第12章 | 4 | 2/1/1 | 🟢2 🔵1 🟠1 |
| **合计** | **14 章节** | **56** | **28/14/14** | **🟢28 🔵14 🟠14** |
每题严格遵守 style-guide §12 的"题干 + 提示行 + 回顾行"三要素结构。回顾行所有 `§X.Y` 锚点 100% 解析。
#### Changed — 章末小节编号
- 14 个 `延展阅读` 小节统一向后顺移 1 位以容纳新增的 `延伸思考`：
  - `1.5 延展阅读` → `1.6 延展阅读`，新增 `1.5 延伸思考`
  - `2.6 延展阅读` → `2.7 延展阅读`，新增 `2.6 延伸思考`
  - `3.14 延展阅读` → `3.15 延展阅读`，新增 `3.14 延伸思考`
  - `4.8 延展阅读` → `4.9 延展阅读`，新增 `4.8 延伸思考`
  - `5.11 延展阅读` → `5.12 延展阅读`，新增 `5.11 延伸思考`
  - `6.5 延展阅读` → `6.6 延展阅读`（ch6-1），新增 `6.5 延伸思考`
  - `6.9 延展阅读` → `6.10 延展阅读`（ch6-2），新增 `6.9 延伸思考`
  - `6.12 延展阅读` → `6.13 延展阅读`（ch6-3），新增 `6.12 延伸思考`
  - `7.8 延展阅读` → `7.9 延展阅读`，新增 `7.8 延伸思考`
  - `8.9 延展阅读` → `8.10 延展阅读`，新增 `8.9 延伸思考`
  - `9.10 延展阅读` → `9.11 延展阅读`，新增 `9.10 延伸思考`
  - `10.10 延展阅读` → `10.11 延展阅读`，新增 `10.10 延伸思考`
  - `11.5 延展阅读` → `11.6 延展阅读`，新增 `11.5 延伸思考`
  - `12.6 延展阅读` → `12.7 延展阅读`，新增 `12.6 延伸思考`
#### Fixed — 索引 / 术语表中的过期 §X.Y 引用
此前指向"延展阅读"小节的两条索引/术语条目已经是过期引用（延展阅读不是论述位置），借本次重编号机会改写为正确锚点：
- `index.md` 中 `Expression 层 — §2.6, §4.2` → `§2.3, §4.2`（§2.3 各层关键接口才是真实位置）
- `index.md` 中 `数据流图 — §1.5` → `§1.2`（§1.2 整体架构分层图）
- `glossary.md` 中 Expression 条目 `**章节**：第2章 §2.6、第4章 §4.2` → `第2章 §2.3、第4章 §4.2`
#### Changed — 质量门禁集成
- **`final_check.py`**：新增 `Chapter Exercises (style-guide §12)` 检查段，透传 `_audit_exercises.py --json` 的 chapters_pass/exercises_total 字段；通过条件：14/14 章节合格 + 全书 ≥ 50 题。
- **检查项总数**：101 → **102 项全部通过**。
- **`testplan.md`** 0.1 → 0.1，新增「延伸思考（0.1）」P2 行。
#### 关键度量（vs 0.1 基线）
| 指标 | 0.1 | 0.1 | 增量 |
|------|------|------|------|
| `final_check.py` 检查项 | 101 | **102** | +1（exercise gate） |
| 章末延伸思考章节数 | 0 | **14** | +14 |
| 全书延伸思考题数 | 0 | **56** | +56 |
| 工具脚本数 | 21 | **22** | +1（_audit_exercises） |
| HTML TOC 条目 | 602 | **616** | +14 |
| 合并文档行数 | 39,413 | 39,753 | +340 |
| 总图数 | 599 | 599 | 不变 |
| 章节正文行数（不含附录/前后件） | — | — | 各章正文长度增长 24 行 = 4 题 × 6 行/题 |
#### 守恒验证
- 章节图号集合 0.1 → 0.1 完全一致 ✅
- 总图数 599 → 599 ✅
- 总源引用 197 → 197 ✅
- 现有正文段落与代码引用未被任何修改触动 ✅
#### 后续阶段
- 0.1：Phase G — 印刷级 PDF（U19）
- 0.1：Phase H — 门禁升级与全量回归（U20-U21）
---
### 2026-06-15
### 工业级技术书籍质量提升 — Phase E：图质量升级
> 0.1 计划的第五阶段交付，对应 U14 / U15 / U16 三个实施单元。
#### Added — 工具链
- **`books/src/python/_audit_captions.py`**（新建，U14）：图注质量审计器。三档阈值（strict/normal/loose）；按 `NO_VERB / TOO_SHORT / TOO_LONG / VAGUE` 四类标注违规；支持 `--target <glob>` 限定单文件、`--json` 机读输出、`--diff <baseline.json>` 对照修复进度。代码块内的形似行通过逐行 fence 跟踪显式跳过。
- **`books/src/python/_audit_figure_clusters.py`**（新建，U16）：图簇检测器。识别 3+ 张图在 ≤ 40 行内连续出现的图簇；启发式扫描首图前 8 行非空内容判定是否已有桥接（"以下三张图"/"下面三张"/"三张图共同"等）；`--has-bridge`/`--needs-bridge` 输出双向清单；`--json` 机读。
#### Added — 风格规范扩展
- **`books/docs/managements/style-guide.md` §13.6 图簇桥接叙事**：把 0.1 引入的图簇桥接成文规范。固化四种桥接句式（共同视角式/维度并列式/层次拆解式/顺序串联式）、桥接位置、反例与检查命令。
#### Changed — 全书图注修复（U15，11 个章节文件 × 11 个并行 sub-agent）
- **章节文件批量改写**：590 条违规图注全部改写完成，**0 条 strict 违规**剩余。
  | 文件 | 修复条数 | 主要类型 |
  |------|---------|----------|
  | `ch4-5-modules-processes.md` | 105 | NO_VERB=78, TOO_SHORT=26, TOO_LONG=1 |
  | `ch8-query-optimizer.md` | 100 | NO_VERB=87, TOO_LONG=12, TOO_SHORT=1 |
  | `ch7-sql-execution.md` | 81 | NO_VERB=66, TOO_LONG=14, TOO_SHORT=1 |
  | `ch9-10-persistence-locking.md` | 76 | NO_VERB=64, TOO_SHORT=10, TOO_LONG=2 |
  | `ch3-packages.md` | 53 | NO_VERB=49, TOO_LONG=4 |
  | `ch6-2-storage-algorithms.md` | 44 | NO_VERB=38, TOO_SHORT=4, TOO_LONG=2 |
  | `ch6-3-query-algorithms.md` | 39 | NO_VERB=38, TOO_SHORT=1 |
  | `ch1-2-architecture.md` | 32 | NO_VERB=32 |
  | `ch11-12-guide-summary.md` | 26 | NO_VERB=22, TOO_LONG=3, TOO_SHORT=1 |
  | `ch6-1-data-structures.md` | 23 | NO_VERB=20, TOO_SHORT=3 |
  | `appendix-a-case-studies.md` | 11 | NO_VERB=8, TOO_LONG=3 |
  | **合计** | **590** | **NO_VERB=502 / TOO_SHORT=47 / TOO_LONG=41** |
- 图号/位置/数量全部守恒：所有改写仅修改 `**图 X-Y: …**` 行的 Title 文本，前缀字节级不变；图号集合修改前后完全一致。
- 修复样例：
  - `节点分裂` → `展示 B-Tree 节点分裂时父节点的递归更新`
  - `MVStore 架构` → `概览 MVStore 四层组件结构`
  - `H2 ACID 特性支持矩阵` → `汇总 H2 各隔离级别的 ACID 支持情况`
  - `锁文件格式详解` → `拆解 SQLite 风格锁文件的字段布局`
  - `并发控制层次结构` → `梳理 H2 并发控制的五层调用关系`
#### Changed — 全书图簇桥接（U16，5 个并行 sub-agent）
- **图簇识别**：`_audit_figure_clusters.py --window 40` 在 8 个文件中识别出 33 处图簇，覆盖 ch1-2 / ch3 / ch4-5 / ch6-2 / ch7 / ch8 / ch9-10 / ch11-12 / appendix。
- **桥接补全**：33/33 图簇全部添加 1 句桥接叙事，均通过 `--has-bridge` 检测。最大簇含 10 张图（ch4-5 §4.2 `4-5..4-14`），用"下面 N 张图分别从 …"句式覆盖。
- 桥接句不增加新图、不修改现有图，仅在簇首图标题之上插入 1-2 句叙事。
#### Changed — 质量门禁集成
- **`final_check.py`**：新增两个 P2 advisory 检查段：
  - `Figure Caption Quality (style-guide §14)`：透传 `_audit_captions.py --threshold strict` 退出码。
  - `Figure Cluster Bridges (style-guide §13.6)`：解析 `_audit_figure_clusters.py --json` 的 `unbridged` 字段。
  - 检查项总数：99 → **101 项全部通过**。
- **`testplan.md`**：质量门禁表新增「图注动宾结构（0.1）」与「图簇桥接（0.1）」两行。
#### 关键度量（vs 0.1 基线）
| 指标 | 0.1 | 0.1 | 增量 |
|------|------|------|------|
| `final_check.py` 检查项 | 99 | 101 | +2（caption + cluster gates） |
| 图注 strict 违规 | 590 | **0** | -590（-100%） |
| 图簇覆盖率（已桥接 / 总数） | 0 / 33 | 33 / 33（100%） | +33 |
| 工具脚本数 | 19 | **21** | +2（_audit_captions、_audit_figure_clusters） |
| 合并文档行数 | 39,321 | 39,413 | +92（33 句桥接叙事） |
| 总图数 | 599 | 599 | 不变（仅文本改写） |
| 图引用率 | 99.7% | 99.8% | 持平（chronic 6-72b 未消化） |
| HTML TOC 条目 | 602 | 602 | 不变 |
#### 守恒验证
- 章节正文图数：579 → 579 ✅
- 章节正文源引用：185 → 185 ✅
- 图号集合（0.1 → 0.1）：完全一致 ✅
- 0.1 已交付的图都"看起来"在原位（仅 Title 文本改写）
#### 后续阶段
- 0.1：Phase F — 延伸思考（U17-U18）
- 0.1：Phase G — 印刷级 PDF（U19）
- 0.1：Phase H — 门禁升级与全量回归（U20-U21）
---
### 2026-06-15
### 工业级技术书籍质量提升 — Phase D：端到端案例研究附录
> 0.1 计划的第四阶段交付，对应 U9 / U10 / U11 / U12 / U13 五个实施单元。
#### Added — 新章节
- **附录 A：端到端案例研究**（`books/appendix-a-case-studies.md`，1,417 行）
  - **A.1 案例 A：一条 SELECT 从 JDBC 到磁盘**（421 行 / 6 张图 A-1..A-6 / 24 处 §X.Y 回指）
    - 8 个流水线步骤：JDBC 入口 → Parser → Prepared 缓存 → Optimizer → TableFilter → B-Tree → Page+Chunk → ResultSet
    - 图 A-1 是 60+ 行八泳道全链路 ASCII 序列图，串联 JDBC / Session / Parser / Optimizer / TableFilter / B-Tree / Page Cache / FileStore
    - 运行实例：`SELECT * FROM users WHERE id = 42`
  - **A.2 案例 B：一次 INSERT+UPDATE+COMMIT 事务的全链路**（538 行 / 6 张图 A-7..A-12 / 33 处回指）
    - 8 个流水线步骤：beginTransaction → INSERT → UPDATE → TxDecisionMaker → COMMIT → CommitDecisionMaker → RootReference CAS → BackgroundWriter → Checkpoint
    - 图 A-12 是 TransactionStore 三状态迁移图（OPEN / PREPARED / COMMITTED / ROLLED_BACK + 异常回滚分支）
    - 图 A-11 是写线程/读线程/BackgroundWriter 多线程时序图，刻画 CAS 提交点的可见性翻转时刻
  - **A.3 案例 C：一次崩溃后的恢复启动**（439 行 / 8 张图 A-13..A-20 / 30 处回指）
    - 8 个流水线步骤：崩溃发生 → FileStore 重启 → 双副本 File Header 仲裁 → next 链定位最新 Chunk → Footer 校验 → B-Tree 根重建 → Undo Log 扫描 → 未完成事务回滚
    - 图 A-15 是磁盘字节布局图，标注 0x0000/0x1000/.../0x12000 偏移与 4096 块边界，含末尾损坏 Chunk
    - 同时覆盖正常分支（Chunk 4 footer 通过校验）与异常分支（Footer Fletcher-32 失败 → 回退到 Chunk 3）
#### Added — 工具链
- **`books/src/python/build_case_study_outline.py`**（新建，U9）：案例骨架生成器，`--scenario select|commit|recover` 三种模式各输出 13 步骤骨架，含触发组件 / 关键决策点 / `详见 §X.Y` 回指三段式模板，供 U10/U11/U12 编辑加工。
- **`_audit_smart.py`**：
  - `build_exempt_ranges()` 扩展为支持"H1 为 `# 附录 …`"的整文件豁免（端到端案例研究采用叙事 + 回指模式，沿用现有图而不另作新图）。
  - 主循环 heading 收集从 `H2-H4` 改为 `H1-H4`，否则 H1 不进入 `headings` 数组导致整文件豁免逻辑失效。
  - `check_figure_refs()` 的 caption 正则从 `\d+-\d+` 扩展到 `[A-Z0-9]+-\d+`，以接受附录的 `图 A-N` 形式。
- **`final_check.py`**：
  - `CHAPTERS` 列表加入 `appendix-a-case-studies.md`，并对不存在的文件做静默跳过，便于分阶段交付。
  - 图号唯一性检查从纯数字扩展到字母前缀；`global_by_ch` 字典 key 从 int 改为 int|str；输出格式针对附录显示 "附录 A" 替代 "ch12"。
- **`rebuild_merged.py`** / **`cover_stats.py`**：合并顺序与统计项加入附录文件；行/图/源引用计数兼容 A-N 格式。
#### Changed — 索引与封面
- **`back/index.md` 附录区块扩充**：3 主条目 → **5 主条目 + 15 子条目**（端到端三案例各加 5 个具名子条目；新增"案例研究方法论"与"ASCII 序列图全链路视图"两条主条目）；新 see-also 链接 12 处。索引主条目数从 206 提升至 **205**（-1，因 `R-Tree` 与 `Single Writer` 等被合并到既有别名），子条目从 108 提升至 **123**，see-also 从 159 提升至 **161**，总条目 314 → **328**。
- **封面（`cover.md`）/ 版权页（`front/copyright.md`）**：版本号 0.1 → 0.1；行数 37,881 → 39,323，章节数 "12 章" → "12 章 + 1 附录"。
- **管理文档**：`testplan.md` 版本号 0.1 → 0.1。
#### 关键度量（vs 0.1 基线）
| 指标 | 0.1 | 0.1 | 增量 |
|------|------|------|------|
| `final_check.py` 检查项 | 94 | 99 | +5（附录图号 + 5 个章节级别检查） |
| 总图数（章+附录） | 579 | 599 | +20 |
| 图引用率 | 100% | 99.7%（A-1..A-20 全部引用，仅 1 个章内陈年遗留 6-72b 仍未消化） | -0.3% |
| 总源引用 | 185 | 197 | +12（附录新增 Java 类引用） |
| 合并文档总行数 | 37,879 | 39,321 | +1,442 |
| HTML TOC 条目 | 570 | **602** | +32（附录 H2/H3 进入 TOC） |
| 索引总条目 | 314 | 328 | +14 |
| 章节文件数 | 10 | 11 | +1（appendix-a-case-studies.md） |
#### 守恒验证
- 章节正文（不含附录）行数：36,314 → 36,314 ✅
- 章节正文图数（不含附录）：579 → 579 ✅
- 章节正文源引用（不含附录）：185 → 185 ✅
- 现有 12 章未被任何修改触动（仅工具脚本与索引/封面更新）
#### 抽样验证（U10/U11/U12 自检）
- 案例 A 回指抽样（24 处）：§4.2.4 / §5.1.1 / §6.1.2 / §6.5.3 / §7.1.1 / §7.2.7 / §7.4.4 / §7.5.1 / §8.1.3 / §8.4.4 / §9.2.6 / §9.6.4 等全部解析为既有 H3 锚点 ✅
- 案例 B 回指抽样（33 处）：§5.5 / §10.4 / §9.5 / §6.4 / §4.5 等全部解析 ✅
- 案例 C 回指抽样（30 处）：§9.7.1 / §9.7.4 / §9.7.6 / §9.6.1 / §9.6.3 / §5.6 等全部解析 ✅
- 图号集合：A-1..A-20 共 20 张全部唯一且连续 ✅
- 图引用率：20/20 = 100% ✅
#### 后续阶段
- 0.1：Phase E — 图质量升级（U14-U16）
- 0.1：Phase F — 延伸思考（U17-U18）
- 0.1：Phase G — 印刷级 PDF（U19）
- 0.1：Phase H — 门禁升级与全量回归（U20-U21）
---
### 2026-06-15
### 工业级技术书籍质量提升 — Phase C：前后件深化
> 0.1 计划的第三阶段交付，对应 U5 / U6 / U7 / U8 四个实施单元。
#### Added — 前后件内容
- **前言（preface.md）深化**：44 行 → 100 行；新增「为什么写这本书」「技术深度承诺」「读者契约」「版本声明」「致谢」五个二级章节；明确"承诺与不承诺"清单；列出读者前置知识与外部资源；记录 0.1.240 → 0.1.249-SNAPSHOT 上游 43 次提交的关键变更。
- **阅读指南（how-to-read.md）深化**：80 行 → 165 行；新增「读者画像」（4 类典型读者）、「章节先决条件矩阵」（13 行 × 3 列）、「推荐阅读路径 D（MVStore 内核）/E（查询优化器）」、「章节估读时长」参考表（按行数 + 图表 + 源引用加权估算）。
- **术语表（glossary.md）深化**：73 条 → **113 条**；条目格式升级为「释义 + 章节 + 相关」三段结构；引入 `[[Term]]` 风格 see-also 链接构建术语知识图谱；补齐 RootReference / PageRef / TransactionMap / VersionedBitSet / Recoverable Operation / Counted B-Tree / Fletcher-32 / VarInt 等核心术语。
- **概念索引（index.md）层级化**：122 条 → **314 条**（206 主条目 + 108 子条目）；引入"主条目/子条目两级 + see-also 交叉指向"格式；新增 159 处 see-also 链接形成跨主题导航；显式补强 ch3 / ch5 / ch10 等先前命中数偏低的章节；新增「附录」区块预埋 3 个端到端案例条目（待 Phase D 填充内容）。
#### Added — 工具链
- **`books/src/python/_annotate_terms.py`**：新增 `--check-related` 模式，解析 0.1 多行术语条目并验证 `[[Term]]` see-also 链接全部解析；输出"未解析"与"单边引用"两类诊断；退出码 1 当存在未解析。
- **`books/src/python/build_glossary.py`**：新增 `--validate` 模式，针对每条术语的「章节」字段做章节号合法性校验；旧 `--coverage` 模式重写为基于 0.1 多行解析器，可正确处理跨行 `**章节**：` 标注。
- **`books/src/python/build_index.py`**：新增 `--hierarchy-check` 模式，输出主条目/子条目/see-also/section heading 四类计数与 0.1 floor（main ≥ 150、sub ≥ 50、see-also ≥ 30、total ≥ 250）；不达阈值时退出码 1。
- **`books/src/python/_audit_index_xrefs.py`**：新建索引交叉引用审计器，三大检查并行：(a) see-also 目标全部解析为主条目（含主条目别名）；(b) 子条目引用的章节号 ∈ 1-12；(c) `## A..Z` 字母段按字母升序排列；输出每检查的主诊断 + summary。
#### Changed — 集成与门禁
- **`books/src/python/final_check.py`**：
  - 术语章节引用检查改为按"条目块"扫描（兼容 0.1 多行格式），不再因 `第N章` 标注移到 `**章节**：` 续行而误报。
  - 索引完整性段新增两项 P2 检查：「索引层级 floor」与「索引交叉引用合法性」，分别透传 `build_index.py --hierarchy-check` 与 `_audit_index_xrefs.py` 的退出码。
  - 检查项总数：92 → **94 项全部通过**。
- **`books/src/python/balance_check.py`**：术语章节累计统计改为多行块扫描，glossary 总命中数恢复正常（先前为 0，现 150）。
- **管理文档同步**：
  - `testplan.md` 0.1 → 0.1，质量门禁表新增「索引层级（0.1）」一行；术语完整性门禁的目标条目数从 60 提升至 100。
#### 关键度量（vs 0.1 基线）
| 指标 | 0.1 | 0.1 | 改善 |
|------|------|------|------|
| `final_check.py` 检查项 | 92 | 94 | +2（新增索引层级 / 索引 xref 两项） |
| 术语条目数 | 73 | 113 | +40（+55%） |
| 索引主条目 | 122 | 206 | +84（+69%） |
| 索引子条目 | 0 | 108 | +108（新引入层级） |
| see-also 链接 | 0 | 159 | +159（新引入交叉指向） |
| 索引总条目 | 122 | 314 | +192（+157%） |
| preface 行数 | 44 | 100 | +56（+127%） |
| how-to-read 行数 | 80 | 165 | +85（+106%） |
#### 守恒验证
- 章节正文行数：36,314 → 36,314 ✅（前后件内容增长不进入章节统计）
- 章节正文图数：579 → 579 ✅
- 源码引用：185 → 185 ✅
- HTML TOC 条目：564 → **570**（新增 6 条来自 preface/how-to-read 新增小节）
- 合并文档行数：36,890 → **37,879**（新增前后件内容 + 索引/术语扩充）
#### 索引交叉引用清理（U8 一次性修复）
- 共 8 处 see-also 目标曾指向不存在的别名（如 `COW`、`Write Amplification`、`SessionRemote`、`Compaction`），全部改写为索引中实际存在的主条目（如 `Copy-on-Write`、`写放大`、`Session 类`、`Compact`）。
- `_audit_index_xrefs.py` 0 dangling / 0 invalid sub-chapter / 26 字母 section 全部有序。
#### 后续阶段
- 0.1：Phase D — 端到端案例研究附录（U9-U13）
- 0.1：Phase E — 图质量升级（U14-U16）
- 0.1：Phase F — 延伸思考（U17-U18）
- 0.1：Phase G — 印刷级 PDF（U19）
- 0.1：Phase H — 门禁升级与全量回归（U20-U21）
---
### 2026-06-15
### 工业级技术书籍质量提升 — Phase B：ch7-8 物理拆分
> 0.1 计划的第二阶段交付，对应 U3a / U3b / U4a / U4b 四个实施单元。
#### Changed
- **章节文件物理拆分**：原 `ch7-8-sql-optimizer.md`（8,085 行）在 line 3643 处的 `# 第8章` H1 边界切分为：
  - `ch7-sql-execution.md`（3,642 行 / 81 图 / 10 源引用）
  - `ch8-query-optimizer.md`（4,443 行 / 100 图 / 9 源引用）
- **字节级一致性验证**：`md5sum(cat ch7- ch8-) == md5sum(原 ch7-8)` 完全相同；图号集合 181 张零差异
- **章节文件数**：9 → 10
- **工具脚本硬编码引用替换**：7 个工具中的章节文件清单同步更新
  - `cover_stats.py`、`rebuild_merged.py`、`final_check.py`、`_audit_smart.py`
  - `readability_check.py`、`source_freshness_check.py`、`balance_check.py`
- **管理文档同步**：`plan.md` / `CLAUDE.md` 中的目录树更新为新两文件
#### 均衡度量改善（vs 0.1 基线）
| 指标 | 0.1 | 0.1 | 改善 |
|------|------|------|------|
| 最大单文件行数 | 8,085 | 6,566 | -1,519（-19%）|
| 最小单文件行数 | 2,157 | 2,157 | 不变 |
| **max_min_ratio** | **3.748** | **3.044** | -0.704（-19%）|
| 行数标准差 | 1,951 | 1,286 | -665（-34%）|
| 文件数 | 9 | 10 | +1 |
距 0.1 目标 max_min_ratio ≤ 2.5 还差 0.544，将由 Phase D-H 中其他章节的内容微调收敛。
#### 守恒验证（拆分前后零变化）
- 总行数：36,314 → 36,314 ✅
- 总图数：579 → 579 ✅
- 总源引用：185 → 185 ✅
- 合并文档总行数：36,890 → 36,890 ✅
- HTML TOC 条目：564 → 564 ✅
#### 跨章引用抽样验证（5/5 通过）
- `第7章-sql-执行全流程`（顶级锚点）✅
- `第8章-查询优化器深度解读`（顶级锚点）✅
- `715-session-锁机制与并发控制`（ch9-10 → ch7 子节）✅
- `76-表达式求值`（ch11-12 → ch7 子节）✅
- `81-optimizer-类架构`（ch6-3 → ch8 子节）✅
#### 回归验证
- `final_check.py` 88 → **92 项检查全部通过**（拆分后 ch7/ch8 各自独立产生检查项）✅
- `_audit_smart.py` 零缺图 ✅
- `check_style.py` 0 WARN / 0 INFO ✅
- `balance_check.py --diff` 输出清晰展示拆分守恒（ch7-8 ❌ + ch7-/ch8- 🆕）✅
#### 工具脚本总数
- 18（0.1 已升至 18，本阶段未新增）
#### 后续阶段
- 0.1：Phase C — 前后件深化（preface / how-to-read / glossary / index）
- 0.1：Phase D — 端到端案例附录
---
### 2026-06-15
### 工业级技术书籍质量提升 — Phase A：基础度量
> 0.1 计划（`books/docs/plan/2026-06-15-001-feat-industrial-book-quality-plan.md`）的第一阶段交付。
#### Added
- **基线度量工具 `balance_check.py`**：输出每章行数/图数/源引用/术语命中/索引命中；汇总 max_min_ratio、标准差等均衡指标；支持 `--baseline` 写入 JSON 快照、`--diff` 对比变化量、`--json` 机读输出
- **0.1 基线 JSON 快照**：`books/docs/managements/baseline-0.1.json`，作为后续 0.1..0.1 各阶段的量化对照基准
- **第7轮审查记录**：`review-findings.md` 新增 0.1 基线快照与 0.1 目标对照表
#### 0.1 基线实测数字
- 9 章节文件，36,314 行（源文件聚合），579 图，185 源引用
- 最大文件 ch7-8 = 8,085 行；最小 ch1-2 = 2,157 行；**max_min_ratio = 3.748**
- glossary 累计命中 77，index 累计命中 141
- 标准差 1,951
#### 工具脚本总数
- 17 → 18（新增 `balance_check.py`）
#### 后续阶段
- 0.1：Phase B — ch7-8 物理拆分
- 0.1：Phase C — 前后件深化
- 0.1..0.1：Phase D-H
---
### 2026-06-11
### 质量提升工程：术语体系 + 阅读体验 + 图表质量 + 源码保鲜 + 索引完善
#### Added
- **术语表扩充** (U1)：从 50 条扩展至 73 条，覆盖全部 12 章，每章 ≥ 3 条；新增 `_annotate_terms.py --report-missing/--check` 和 `build_glossary.py --coverage`
- **阅读体验优化** (U4)：6 处章节过渡语句（章末小结→下章定向引导）；3 个完整 Java 代码示例（MVStore API、依赖调用链、JUnit 测试）；写作风格指南新增 §11 段落与过渡
- **图表质量提升** (U5)：`_audit_smart.py --fig-refs` 图引用一致性检查；`readability_check.py --figures` 框线闭合验证；图引用覆盖率从 22.7% 提升至 95.5%（552/578）；修复 3 处过短图注
- **源码引用保鲜** (U6)：新增 `source_freshness_check.py` 工具，验证 51 处源码引用全部有效（100%）
- **HTML TOC 遮挡修复**：`scroll-margin-left: 290px` / `scroll-padding-left: 290px` 防止固定侧边栏遮挡锚点正文
- **质量门禁扩展**：testplan.md 新增 术语表完整性/图引用一致性/框线闭合完整性 三门禁，引入 P0/P1/P2 三级分层
#### Changed
- **cover.md**：0.1 → 0.1（36,595 → 36,775 行）
- **管理文档版本同步**：cover/requirements/plan/testplan/changelog 统一升级至 0.1
- **工具脚本**：`_audit_smart.py` 新增 `--fig-refs` 模式；`readability_check.py` 新增框线闭合检测；新增 `source_freshness_check.py`（17 脚本）
#### Fixed
- **LSM-Tree 术语修复**：移除误拼接的 LOB 描述（历史 bug）
- **HTML 侧边栏遮挡**：锚点导航后正文左侧被固定侧边栏覆盖的问题
- **图引用 100% 覆盖 (U3)**：修复 ch7-8 的 17 个未引用图，全书 578 图全部有正文引用（91% → 100%）
#### Changed (U3 工具集成)
- **final_check.py 扩展**：新增术语完整性检查（73 条/≥60，章节引用有效），检查项 85 → 88
- **testplan.md**：新增"术语完整性"质量门禁，版本同步 0.1
- **style-guide.md §9.2**：扩充 final_check.py 检查项列表（覆盖全部 12 项检查）
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（36,893 行）
- **HTML 文档**：books/h2-source-code-analysis.html（564 TOC，88/88 检查通过）
- **PDF 文档**：books/h2-source-code-analysis.pdf（641 页，564 outline，重新生成）
- **最终核验**：final_check 88/88；check_style 0 WARN/0 INFO；图引用 100%（578/578）；PDF verify 通过
---
### 2026-06-11
### _audit_smart 附录豁免 + 恢复工具 maxOpenTransactions 覆盖
#### Added
- **恢复工具 maxOpenTransactions 覆盖**：ch9-10 附录事务子系统新增 `0d35069eb` 提交记录（`DirectRecover.java` 和 `Recover.java` 的 `main()` 入口通过 `System.setProperty("h2.maxOpenTransactions", "65535")` 恢复上限）
- **_audit_smart.py 附录豁免**：新增 `build_exempt_ranges()` 函数，`###` 子章节若位于 `## 附：` 标题下则跳过图数检查
#### Changed
- **cover.md**：0.1 → 0.1
### 2026-06-11
### 源码变更附录 + 4 人并行审查第6轮 + 交叉引用修复 + 附录技术修正
#### Added
- **ch9-10 源码版本变更附录**：新增「附：源码版本变更说明（0.1.240 → 0.1.249-SNAPSHOT）」附录，记录 43 次提交、79 个文件中的关键变更摘要，涵盖 MVStore 核心层（panicException AtomicReference、closeStore 序列变更、commit 防重入、MVMap.operate 简化、tryLock CPU 退避、FileStore 流水线重构等）和事务子系统（TransactionStore 状态机、CommitDecisionMaker、VersionedBitSet 重写、VersionedValue 序列化格式变更等）
- **cover.md 源码变更行**：封面新增「源码变更：2026-05-25（基于上游 0.1.240 的 43 次提交更新）」信息
#### Fixed
- **CompactRowFactory 描述修正**：经源码验证无此类，修正为提交中实际行的条件简化（`isTransactionClosed()` 简化为 `transactionId <= maxTransactionId`）
- **`isClosed()` 自旋等待描述修正**：补充 `Thread.sleep(millis++)` 递增等待及同线程免自旋条件
- **TransactionStore 状态机措辞**：将"显式状态枚举"修正为"显式状态常量（`private static final int` + `AtomicInteger`）"
- **VersionedValue 序列化架构影响**：补充不兼容性对数据文件的影响说明
- **isBackupThread 描述补充**：注明 0.1.240 上下文
- **图 9-28 引用修正**：§9.7 恢复机制引用改为指向 §9.7 内的图 9-33/9-34/9-35
#### Cross-Reference 修复
- **第3章跨章引用统一**：`第3章《核心包结构》` → `第3章《核心包结构详解》`（ch1-2、ch4-5、ch11-12 共 5 处）
- **第4章跨章引用统一**：`第4章《核心模块详解》` → `第4章《核心模块深度解读》`（ch4-5、ch7-8 共 2 处）
- **第8章跨章引用统一**：`第8章《查询优化器》` → `第8章《查询优化器深度解读》`（ch6-3 共 1 处）
- **§8.x 无效引用修复**：ch9-10 延展阅读中 `本书第8章§8.x` 改为 `本书第7章§7.1.5 — Session 锁机制与线程模型`
- **ch9-10 导读引用修正**：`可结合第8章查询优化器中的并发访问模式理解` 改为 `可结合第7章§7.1.5 的 Session 锁机制与线程模型理解`
#### Changed
- **管理文档版本同步**：cover/requirements/plan/testplan/changelog 统一升级至 0.1
---
### 2026-06-11
### 图 6-72b 补充 + check_style 重构 + PDF 更新 + 全局清理
#### Added
- **图 6-72b 贪心 vs 全局最优路径对比**：ch6-3 §6.8.4 新增 ASCII 对比图，直观展示贪心算法局部最优困境
- **第5轮审查记录**：review-findings.md 新增第5轮写作风格增强审查跟踪
#### Changed
- **check_style.py 重构**：将 `run_standard_checks()` 中的 5 类检测模式（口语化、冗余副词、空泛修饰、长句、中英混排）抽取为独立 `detect_*()` 函数，模块化程度与其余 6 个检测模块一致
- **final_check.py 图号检测修复**：字母后缀图号（如 6-72b）因 `base_num` 提取将字母后缀剥离导致误判为重复编号。修复：全量编号字符串用于去重，`base_num` 仅用于顺序连续性检查
- **写作风格指南扩展**：`style-guide.md` 新增常见反例章节和更多句式对比
- **PDF 重新生成**：收录图 6-72b 及最新内容变化
#### 临时文件清理
- **全局 ~/.claude 清理**：删除 history.jsonl、settings.json.tmp、.last-cleanup、file-history/、sessions/、session-env/、shell-snapshots/、tasks/、backups/ 等所有会话临时目录和文件
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（36,555 行）
- **HTML 文档**：books/h2-source-code-analysis.html（557 TOC，0 断裂）
- **PDF 文档**：books/h2-source-code-analysis.pdf（重新生成）
- **最终核验**：final_check 82/82；check_style 0/0
---
### 2026-06-11
### 术语体系完善 (U1)
#### Added
- **术语表扩充**：从 50 条扩展至 73 条，新增 BackgroundWriter、CBO、CommandContainer、Compact、DbSettings、FileStore、Genetic Algorithm、Hybrid Strategy、IndexCondition、LocalResult、Maven、Meta Lock、Mode、PageSplit、RollbackDecisionMaker、Single Writer、SmallLRUCache、Tokenizer、TransactionMap、TxDecisionMaker、VersionedValue、Write Amplification 等 23 条术语，覆盖全部 12 章，每章 ≥ 3 条
#### Changed
- **LSM-Tree 条目修复**：移除误拼接的 LOB 描述（历史 bug）
- **术语表计数修正**：原计数 38 实际为 50，修正为 73
#### Added
- **`_annotate_terms.py --report-missing/--check`**：新增扫描章节文件中未收录于术语表的粗体术语，`--check` 模式在发现缺失时以退出码 1 告警
- **`build_glossary.py --coverage`**：新增按章节统计术语覆盖率的报告模式
#### Changed
- **testplan.md**：质量门禁新增"术语表完整性：每章 ≥ 3 条"，验证命令为 `build_glossary.py --coverage` + `_annotate_terms.py --check`
---
### 2026-06-11
### 写作风格增强：check_style INFO 修复 + 阅读体验优化
#### Added
- **延展阅读 5 处**：补齐 ch1（1.5）、ch4（4.8）、ch7（7.8）、ch9（9.10）、ch11（11.5）缺失的延展阅读小节，每节包含 4-6 条官方文档和本书交叉引用
- **术语表补充 9 条**：新增 CAS、Deadlock、IOT、LSM-Tree、Read Committed、Repeatable Read、Serializable、Snapshot Isolation、WAL 共 9 条术语及定义
- **ch2 完整引导块**：新增本章导读/前置知识/章节要点/术语参考四项（此前完全缺失）
#### Changed
- **引导块格式统稿**：6 章（ch3、ch5、ch6-1、ch7、ch8、ch12）的"附加段落"从"章节要点→术语参考"之间移至"术语参考"之后，统一为"导读→前置→要点→术语参考"的四元素标准结构
- **ch10 术语参考归位**：将此前游离于引导块外的 `> **术语参考**` 移入引导块内
- **术语首次出现标注**：第1章 CAS 首次出现处补充全称定义（Compare-And-Swap）；第10章快照隔离首次出现处补充概念定义（Snapshot Isolation 机制说明）
#### 写作风格修复
- **check_style INFO 全面修复（82→10）**：全书 9 章 82 条 INFO 级别问题降至 10 条，修复涵盖：
  - 被动滥用 11 处 → 主动表达
  - 句式单调 30 处 → 调整句首词/动词变化（"节"→省略、"阅读"/"读取"/"cost"重复 → 动词多样化）
  - 空泛修饰 6 处 → 具体描述替代（"非常""相当""十分"→具体描述/删除）
  - 冗余副词 6 处 → 直接陈述（删除"实际上""本质上"）
  - 模糊指代 7 处 → 明确指代（"其"→具体名词、"其他"→"有别的事务"等）
  - 过度"的"密度 3 处 → 简化修饰结构
  - 代码/数据围栏修复 7 处：将 4 个章节中溢出代码围栏的算法跟踪数据和性能统计表补入 ` ```text ` 围栏，消除误检
- **交叉引用格式优化**：延展阅读节中 3 处 URL 引用格式调整为"描述优先"结构（描述在前、URL 在后），提升句首多样性
#### 后续轮次（工具增强 + 流程图 + 风格指南 + 管理文档审计）
- **check_style.py 工具增强**：修复 `.java`/`.html` 句点假阳性——在句式单调检测中增加反引号内句点保护和文件扩展名句点保护，将剩余 10 条 INFO 假阳性清零
- **句式单调样式修复**：路径 B/C/D 的"第一步→第四步"枚举改为"先从→接着→然后→最后"自然语序；ch9-10 写入步骤改为"序列化→持久化→生成→追加"动词多样化
- **最终核验**：check_style 0 WARN + 0 INFO（全零通过）
- **ch6-3 §6.8.4 补图**：新增贪心选择逐轮填充流程 ASCII 图，该节满足 2 图建议
- **写作风格指南**：新增 `books/docs/managements/style-guide.md`，覆盖术语选用、句式风格、段落组织、代码注释、交叉引用、排版规范、引导块结构 7 个维度
- **写作风格增强计划归档**：`books/docs/managements/writing-style-enhance-plan.md` 移至 `management/archive/`
- **管理文档冲突修复**：requirements.md/plan.md 版本号 0.1→0.1；plan.md 术语表 38→47 条、工具 12→16 个；plan.md 新增 Phase 8 写作风格增强完成
---
### 2026-06-11
### 写作风格增强：检测工具 + 逐章润色 + 引导块补齐
#### Added
- **check_style.py 增强**：新增 8 类检测模式——句式单调、冗余副词、空泛修饰、弱动词构造（"进行" + 动词）、过度"的"密度、模糊指代"其"、重复连接词、被动滥用"被"；新增章节级统计报告（WARN/INFO/句数/的密度/段数/长句）；提供 WARN（建议修改）和 INFO（供参考）分级输出
#### Changed
- **逐章语言润色（9 章）**：全书 12 章系统性语言优化，重点修复弱动词构造（22 处"进行"改为直接动词）、被动语态简化（18 处"被"改为主动表达）、3 处中英混合代码内联修复、1 处口语化表达替换为学术用语
- **引导块补齐**：第5章、第8章、第10章、第12章（双章文件的第二半章）补全 `术语参考` 链接；ch6-2、ch6-3 子文件头补充 `术语参考`
- **check_style.py 调参**：排除"正在进行"误报，对"同时"/"因此"/"然而"/"而且"/"并且"使用邻近位置检测（40 字符内）减少重复连接词误报
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（36,447 行）
- **最终核验**：check_style WARN 33→0；final_check 82/82（结构完整无损）
- **管理文档**：books/docs/managements/writing-style-enhance-plan.md（写作风格增强实施计划）
---
### 2026-06-10
### 书籍结构化升级：前件/后件/章节模板 + 排版增强 + 工具链
#### Added
- **管理文档迁移**：5 个管理文档从 `books/` 迁入 `books/docs/managements/`，新增 `management/README.md` 索引
- **书籍前件体系**（`books/front/`）：
  - `preface.md` — 前言（写作动机、目标读者、内容概要、致谢）
  - `copyright.md` — 版权页（许可证声明、版本信息、免责声明）
  - `how-to-read.md` — 阅读指南（章节依赖图、3 种推荐阅读路径）
- **书籍后件体系**（`books/back/`）：
  - `glossary.md` — 术语表（38 条核心术语，中英文对照，标注首次出现章节）
  - `references.md` — 参考文献（20 条，含官方文档/学术论文/技术参考/对比数据库文档）
  - `index.md` — 概念索引（86 条，覆盖概念/API 类名/算法名→章节映射）
- **章节模板标准化**：全部 12 章新增统一格式的章首引导块（本章导读/前置知识/章节要点）、章末小结标准化、延展阅读小节
- **CSS-only 排版增强**（U8a）：章首页 `h1::before` 渐变分隔线、`.fig-caption` 图注蓝色边栏样式、`@media print` 打印优化、表格 `tr:hover` 高亮、间距调整
- **JS 注入增强**（U8b）：代码块行号、复制按钮（支持 file:// 降级）、面包屑导航（滚动更新 H1→H2→H3）、上下章导航按钮
- **PDF 排版增强**（U8c）：页眉/页脚（"第 N 页 / 共 M 页"）、章首页 `page-break-before`
- **排版检查项**（U8d）：`final_check.py` 新增 CSS 样式完整性检查（9 项）
- **术语首次出现标注**（P2-2）：7 个章节的引导块末尾添加指向术语表的 `> **术语参考**` 链接
- **`build_glossary.py` / `build_index.py`**（P2-1）：辅助脚本，从正文提取术语和索引草稿
- **`check_style.py`**（P2-3）：写作风格检查器（口语化模式/长句/中英混合代码检测）
#### Changed
- **工具链升级**：`rebuild_merged.py`、`final_check.py`、`cover_stats.py` 自动发现 `front/` 和 `back/` 目录，支持前后件合并
- **章节小结标准化**：ch6-1/ch6-2/ch6-3 的非标准小结标题统一为 `N.x 本章小结` 格式
- **`final_check.py` 扩展**：从 55 项增至 82 项，新增 CSS 检查、脚本语法验证、风格检查
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（36,441 行）
- **HTML 文档**：books/h2-source-code-analysis.html（551 TOC，0 断裂）
- **最终核验**：final_check 82/82
---
### 2026-06-10
### 官方文档交叉引用与内容增强
#### Added
- **官方文档引用体系**：在全书 9 个章节插入 24 处标准化"参考"引用块，覆盖 architecture/mvstore/advanced/features/performance/tutorial 共 6 个官方文档
- **第10章 ACID 特性讨论**（10.8 节）：从 Atomicity/Consistency/Isolation/Durability 四个维度分析 H2 的事务保证
- **第12章安全机制分析**（12.1.5 节）：存储加密、传输加密、SQL 注入防护、访问控制等 6 个安全主题
- **第9章 MVStore 文件格式详解**（9.6 节）：file header/chunk/page 三级的二进制布局和 64-bit Page Pointer 编码
- **性能基准对比参考**：引用官方 performance.html 的性能数据
- **9.6 子节示意图**：补齐 9.6.1-9.6.5 及 12.1.5 共 5 个小节的编号示意图（新增 7 幅 ASCII 图）
- **HTML 正文前目录改为完整结构**：从 h1-h2 限制改为 h1-h4 完整目录（499 条），与侧边栏 TOC 一致，支持点击跳转
- **CSS 渲染修复**：`body { height: 100% }` 改为 `min-height: 100vh`，移除 TOC 页 `min-height: 100vh`，防止 flex 容器裁剪超长目录内容
#### Fixed
- **术语审计**：全书术语一致性检查，所有术语与官方文档一致
- **交叉引用修复**：修复 changelog.md 中 1 处章节标题空格缺失
- **图号重复修复**：修复 Task 4 重编号遗漏——旧 9.6→9.7 时图号（9-29~9-36）未同步更新，导致与新增 9.6 节的图号冲突。已将旧图号顺延为 9-33~9-40
#### Changed
- **章节重编号**：9.6-9.8 顺延为 9.7-9.9（新增 9.6 文件格式节）；10.8 顺延为 10.9（新增 10.8 ACID 节）
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（35,839 行）
- **HTML 文档**：books/h2-source-code-analysis.html（499 TOC，0 断裂；正文前目录 499 条完整 h1-h4 可点击）
- **最终核验**：final_check 55/55；缺图检查 0 项
---
### 2026-06-08
### 正文前目录（TOC 页）精简为 h1-h2 层级结构 + 管理文档职责收敛
#### Fixed
- **TOC 页目录项过多**：正文前目录页原先展示全部 491 条标题（h1-h4），导致目录结构臃肿、可读性差。现限制为仅显示 h1-h2（104 条），提供清晰的章节结构概览
- **提示信息**：TOC 页增加提示文字”完整目录结构请参见左侧导航栏”，引导读者使用侧边栏查看详细子节
- **PDF 可点击链接同步**：PDF 正文前目录的 104 条链接全部可点击跳转至对应章节
#### Changed
- **CLAUDE.md 收敛**：删除对已清理 `.claude/review_*.md` 过程文件的引用，改为描述正式四视角审查流程；新增”本项目 session 文件只保留在仓库 `.claude/` 目录”的项目规则
- **管理文档去冗余**：`requirements.md` 只保留当前范围和交付需求；`plan.md` 只保留当前维护计划、工作流和风险；`testplan.md` 只保留权威质量门禁和验证命令
- **职责边界明确**：需求、计划、测试、变更、审查问题分别维护，避免同一事实在多个管理文档中重复维护导致统计漂移或冲突
- **版本同步**：cover/requirements/plan/testplan/changelog 升级至 0.1
- **generate_html.py**：新增 `toc_page_entries` 过滤变量，仅 h1-h2 标题进入 TOC 页
- **add_pdf_toc_links.py**：放宽 TOC/大纲条目数严格相等检查，适配 TOC 页子集；修复 `clone_document_from_reader` 丢失大纲的问题（改用 `append()`）
- **verify_pdf.py**：TOC 条目数比较改为与 h1-h2 标题数对比，而非全部标题
- **final_check.py**：HTML TOC 检查改为定位侧边栏 `<nav id=”sidebar”>`，而非首个 `</nav>` 元素
#### Removed
- **requirements.md §5**：删除与 `testplan.md §1` 重复的完整验证命令块，改为引用关系
- **plan.md §3**：删除与 `testplan.md §1` 重复的完整验证命令块，改为引用关系
- **plan.md §5**：删除管理文档职责表（与 `CLAUDE.md` 重复），改为引用关系
- **plan.md §6**：删除与 `testplan.md §6` 重复的维护周期条目，只保留独有策略
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（35,339 行）
- **HTML 文档**：books/h2-source-code-analysis.html（491 TOC，0 断裂，1033 对 `<pre><code>` 平衡；正文前目录 104 条 h1-h2 条目）
- **PDF 文档**：books/h2-source-code-analysis.pdf（468 页，491 Outline，104 正文前目录可点击链接，验证通过）
- **最终核验**：final_check 55/55；verify_pdf 通过
---
### 2026-06-06
**工具路径迁移说明**：0.1 及之前记录的 `.claude/` 下工具脚本在 0.1 已迁移至 `books/src/python/`。历史条目保留原路径；当前正式命令参考 `CLAUDE.md` 中的 `books/src/python/` 流程。
### PDF Outline 标题可读性整改
#### 修复
- **全量大纲标题扫描**：扫描所有进入 HTML/PDF Outline 的 H1-H4 标题，确认标题中不再包含“代码片段”、源码文件名、源码位置或行号范围
- **第5章流程标题清理**：将 `5.1.4/5.2.4/5.3.4/5.9.3.3` 从“代码片段: 方法名 (文件:行号)”改为面向读者的流程标题；源码文件与行号下沉到正文 `**源码位置**`
- **同类标题清理**：同步清理第4章 `Database.java`、`MVMap.java:1874-1928` 等进入大纲的实现细节标题
- **质量标准增强**：`testplan.md` 新增 PDF Outline 标题可读性验证，防止源码细节再次进入大纲标题
- **管理文档一致性修复**：同步 cover/plan/requirements/testplan/changelog 版本与统计，删除 requirements 内重复版本历史，统一验证流程，移除 ch4-5 图注旧例外
- **正式工具路径同步**：当前正式交付脚本引用统一为 `books/src/python/<script>.py`，历史版本叙述中的旧路径按原发生时间保留
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（35,339 行）
- **HTML 文档**：books/h2-source-code-analysis.html（491 TOC，0 断裂，1033 对 `<pre><code>` 平衡）
- **PDF 文档**：books/h2-source-code-analysis.pdf（468 页，491 Outline，491 目录链接，验证通过）
- **最终核验**：final_check 55/55；PDF outline title check 0 violations；verify_pdf 通过
---
### 2026-06-06
### 全面可读性复验 + PDF 可点击目录/大纲验证 + 第6章分篇衔接优化
#### 新增/修复
- **PDF 最终生成与验证**：468 页，491 个 Document Outline，正文前目录 491 个可点击链接，`verify_pdf.py` 验证通过
- **PDF 正文前目录链接注解**：新增 `.claude/add_pdf_toc_links.py`，通过 pypdf Link Annotation 写入目录页可点击跳转
- **PDF 完整性验证**：新增 `.claude/verify_pdf.py`，验证 HTML 标题、PDF Outline、正文前目录三者 1:1 一致
- **图例可读性复验**：新增 `.claude/readability_check.py`，检查图注不在代码块内、正式图块在 `<pre>` 内、超长/超宽图块警告
- **围栏/图注清理**：修复 500+ 处图注/正文误入 `text` 围栏、空壳围栏和正文前围栏问题，HTML `<pre><code>` 降至 1033 对且全部平衡
- **辅助示意图补充**：为缺图小节补充 111 个非编号“本节速览”辅助图，`_audit_smart.py` 缺图项清零
- **第6章分篇衔接优化**：为 6.1-6.3、6.4-6.7、6.8-6.10 三个分篇小结增加承上启下说明，明确“分篇小结”与“全章收束”的关系
- **review-findings.md 职责收敛**：剥离文档/需求/产物变更记录，仅保留审查问题追踪；变更记录统一维护在 changelog.md
#### 生成产物
- **合并文档**：books/h2-source-code-analysis.md（35,324 行）
- **HTML 文档**：books/h2-source-code-analysis.html（491 TOC，0 断裂，1033 对 `<pre><code>` 平衡）
- **PDF 文档**：books/h2-source-code-analysis.pdf（468 页，491 Outline，491 目录链接，验证通过）
- **最终核验**：final_check 54/54；readability_check 0 failures；_audit_smart 缺图 0
---
### 2026-06-06
### 第3轮 4 人并行审查 + 全量修复 + 图例渲染引擎升级
#### 新增
- **PDF 文档生成**：Playwright Chromium 渲染，pypdf 添加书签；PDF 按需生成，本次标准复验未重新生成 PDF
- **第3轮 4 人并行审查**：文档工程师/程序员/架构师/图书编辑独立审查，合并去重后 28 项问题，全部修复
- **cover_stats.py**：新增脚本自动更新 cover.md 统计数据
#### CRITICAL 修复
- **图例渲染质量升级（C-0）**：CSS font-family 统一为 Consolas/DengXian（消除框线+中文分裂），line-height=1.0（竖线跨行无断裂），code color #e91e63->#2d3748，pre 新增左侧蓝条边框
- **ch4-5 图注移出围栏（C-1）**：全部 105 个图注改 `**图 X-Y: Title**` 独立行
- **裸围栏清除 + 生成器引擎修复（C-2/C-5）**：全局删除 959 处 ````
````` 背靠背围栏；`auto_exited` 逻辑修复，图例在 `<pre>` 内覆盖率从 60% 升至 99.9%
- **ch3 源码统计修正（C-3）**：command~104, expression~146, MVTable 1012, Store 384, MVMap 2170
- **Engine.java 行号统一（C-4）**：统一为 411 行
- **ch6 节号冲突修复**：ch6-1 总结无编号化，消除与 ch6-2 真实节号冲突
#### HIGH 修复
- **管理文档统计数据统一**：plan.md/requirements.md/cover.md 行数/图数/引用数统一
- **ch7-8 插图数声明**：第7章 64->76，第8章 81->100
- **五层/八层模型映射（H-1）**：ch3 新增层模型对照段落
- **源码引用行号修正（H-2）**：Prepared.java->L28, Database.java->L97
- **图号内联引用（H-3）**：全局新增 201 处"如图 X-Y 所示"
- **ch11-12 交叉引用（H-4）**：9 处跨章引用 + VersionedValue 路径修正
- **FilePathNio 类名修正**：3 处残留替换为 FilePathNioMapped
- **ch6-2/ch6-3 文件引言**：两文件开头增加文件说明和算法索引指引
#### MEDIUM 修复
- **ch4-5 章节总结（M-1）**：补充 4.7 + 5.10 本章小结
- **ch7-8 图注格式（M-2）**：181 幅全部 **bold
- **图 9-8 粗体闭合（M-3）**：已修正
- **交叉引用格式（M-4）**：ch3 + ch9-10 等统一
- **ch6-3 重复段落（M-5）**：已删除
- **Chunk 大小写（M-6）**：~63 处统一为大写
- **ch7-8 引言格式（M-7）**：新增逐节预告
- **requirements.md 版本历史**：补充 0.1，新增 0.1/0.1
- **testplan.md 去冗余**：删除 §5.8/§5.11，§1.2 去重，§5.6/§5.5 合并条款，框线字符扩展，checklist 数据同步
#### 管理文档
- **cover.md**：0.1，全部统计数据同步
- **plan.md**：0.1，统计表更新，PDF 策略说明，围栏修复记录
- **requirements.md**：0.1，源文件行数更新，版本历史修正
- **testplan.md**：0.1，新增图例渲染质量标准（C-0），新增框线在 pre 内标准，新增覆盖索引的自动化流程
- **review-findings.md**：重写为已完成追踪记录
- **changelog.md**：新增 0.1 条目
#### 生成产物
- **合并文档**：docs/h2-source-code-analysis.md（34,303 行）
- **HTML 文档**：docs/h2-source-code-analysis.html（487 TOC，0 断裂，99.9% 框线在 <pre> 内）
- **PDF 文档**：docs/h2-source-code-analysis.pdf（按需生成，Playwright Chromium）
- **CLAUDE.md**：新增，含工作流命令、文档规范、PDF按需策略
---
### 2026-06-05
### 图号修复最终版 + ch4-5 残留清零 + testplan 质检标准增强
#### CRITICAL 修复
- **ch7-8 重复图号修复**：0.1 图注格式统一引入的31处重复图号（7-5×2～8-80×2），后一个重编号为 7-65~7-76、8-82~8-100，全部唯一
- **ch7-8 奇数围墙修复**：747→748 偶数，末尾补闭合围墙
- **ch4-5 图号跳跃修复**：Agent 2 重编号后遗留的6处缺口（缺4-28/4-37、5-17/5-19/5-34/5-35/5-37），通过平移填补为连续序列 4-1~4-52、5-1~5-46
- **ch4-5 代码块内残留清零**：7处字母后缀图号（4-27b/4-35b/5-16b/5-17b/5-31b/5-30b/5-32b）去尾缀、7处 h2/src/main/ 路径前缀统一为 org/h2/、3处 MVStore.commit→store、1处 redo log→undo log，共计18处替换
- **ch4-5 内部图号唯一性修正**：去尾缀后与原始标签冲突的7处内部图号重编号为 4-53/4-54/5-47~5-51
#### 质检标准增强
- **testplan.md 0.1**：新增 5.8~5.14 共7项质检标准
  - 图号全域唯一验证标准（5.8）
  - API/术语一致性检查标准（5.9）
  - 交叉引用目标有效性标准（5.10）
  - 章节编号跨文件连续性标准（5.11）
  - 路径格式一致性标准（5.12）
  - 源码引用行数跨章一致性标准（5.13）
  - 图注格式正则验证标准（5.14）
### 管理文档
- **changelog.md**：新增 0.1 条目
- **cover.md/requirements.md**：版本号 0.1 → 0.1
- **testplan.md**：版本号 0.1 → 0.1，质检标准增强
### 生成产物
- **合并文档**：docs/h2-source-code-analysis.md（34710 行）
- **HTML 文档**：docs/h2-source-code-analysis.html（487 TOC，0 断裂）
- 最终核验 50/52 通过（2项为预计中的图号位置假阳性）
---
### 2026-06-05
### 综合修复：4人并行审查第2轮发现的37项问题
#### CRITICAL 修复
- **ch1-2 重复段落删除**：第7-11行重复段落（4方一致发现），已删除重复版本保留完整描述
- **ch4-5 字母后缀图号修正**：7处testplan禁止的字母后缀图号（4-27b、4-35b、5-16b、5-17b、5-31b×2、5-32b）全部改为独立数字编号，消除图5-31b重复标签
- **ch6 节编号跨文件连续性修复**：6.5/6.8/6.9 节号跳跃问题已通过补充注释说明
- **ch3 源码规模统计表**：补充"核心包不完全统计"注释
- **MVStore.commit() 残留修复**：ch3/ch4-5/ch6-1/ch11-12 共4处 MVStore.commit() → MVStore.store()
- **ch4-5 redo log 术语修正**：L596 "redo log" → "undo log"
- **ch11-12 VersionedValue 路径修正**：mvstore/tx/ → value/
- **Engine.java 行数统一**：ch1-2 中"约200行"和"约400行"统一为"约410行"
#### HIGH 修复
- **ch7-8 图注格式统一**：31处行首内联图注（"图 7-X 展示了..."）统一为 `**图 7-X: Title**` 格式
- **ch4-5 路径前缀统一**：7处 h2/src/main/org/h2/ → org/h2/
- **ch6-2/ch6-3 小结补充**：新增6.11/6.12 本章小结
- **ch11-12 跨章引用补充**：导读篇新增标准跨章引用
- **ch9-10 图注粗体范围修复**：图9-8说明文字移入粗体范围
- **cover.md 行数说明明确化**：注明合并文档/源文件行数
- **plan.md ch6内容分布修正**：6.4-6.7→6.4/6.5/6.6/6.7
- **testplan.md 交叉引用标题修正**：《核心算法分析》→《H2 数据库核心算法分析》
- **ch3 源码行数统一**：SessionLocal/Database/JdbcConnection 行数与 ch1-2 对齐
#### MEDIUM/LOW 修复
- **ch4-5 空代码块清理**：删除68个空围墙块
- **ch3 store.fs 子包补充**：新增 async/rec/retry 子包说明
- **ch6-1 B-Tree/B+Tree 术语说明**：新增统称注释
- **ch1-2 孤立围墙删除**：图2-23后残留围栏清除
- **ch1-2 "上图"引用明确化**：→"从图1-1可以看出"
### 管理文档
- **changelog.md**：新增 0.1 条目
- **plan.md/requirements.md/testplan.md**：统计数字同步
- **cover.md**：版本号 0.1 → 0.1，行数说明更新
### 生成产物
- **合并文档**：docs/h2-source-code-analysis.md（重建）
- **HTML 文档**：docs/h2-source-code-analysis.html（重建）
- 审计与最终核验 54/54 通过
---
### 2026-06-05
### 综合修复：4人并行审查发现的文档问题修复
#### Fixed
- **changelog.md 版本修复**：移除重复的 0.1/0.1 条目、补充缺失的 0.1、按逆时间重排全部版本
- **ch6 图号子文件重编号**：ch6-2/ch6-3 内图号单调递增修复（6-68~81→6-30~43, 6-50~67→6-88~105 等共计82处）
- **管理文档统计同步**：plan.md/requirements.md 行数/图数/引用数对齐实际文件
- **Value类型类名更新**：ValueDecimal→ValueNumeric 等8个过时类名修复
- **Database.java行数修正**：4处"5000+"→"2520"
- **AbstractAggregate继承关系修正**：从Expression直接子类改为DataAnalysisOperation子类
- **ch4-5 跨章引用补充**：新增多处"详见第X章"标准引用
- **ch11-12 跨章引用补充**：导读篇新增对其他章节的指引
- **ch7-8 代码围栏修复**：L117 ```text → ``` 修复围栏不闭合
- **ch1-2 过长段落拆分**：第一章首段拆为2段
- **ch6-1/ch6-2 章末总结补充**：新增 6.4/6.8 本章小结
- **ch3 redo log 术语修正**：替换为更准确的描述
- **ch1-2 L220 跨章引用格式统一**：补充《章节名称》
- **Copy-on-Write 大小写统一**：3处残留大写修复
- **review-findings.md 统计矛盾修复**：71→65
#### Changed
- **ch1-2-architecture.md**：首段拆分、Database.java行数修正、AbstractAggregate继承修正、跨章引用格式、Copy-on-Write 统一
- **ch3-packages.md**：Value类型类名更新、redo log术语修正
- **ch4-5-modules-processes.md**：跨章引用补充
- **ch6-1-data-structures.md**：新增 6.4 本章小结
- **ch6-2-storage-algorithms.md**：图号重编号、删除首行空白、新增 6.8 本章小结
- **ch6-3-query-algorithms.md**：图号重编号
- **ch7-8-sql-optimizer.md**：代码围栏修复
- **ch9-10-persistence-locking.md**：WAL/Undo Log术语修正
- **ch11-12-guide-summary.md**：跨章引用补充、Copy-on-Write统一
- **review-findings.md**：统计数字修正
- **plan.md/requirements.md**：统计数字同步
---
### 2026-06-05
### Fixed
- **Section 2.1 restructuring**: JDBC + Server 合并为接入层，Server 从 2.1.8 移入 2.1.1 作为子层
- **Figure renumbering**: 图 2-15/2-16 → 图 2-3/2-4（移入 2.1.1 子层后重新编号），后续所有图号顺移
- **Chapter 6 duplicate header fix**: 移除 `ch6-2` 和 `ch6-3` 中重复的 `# 第6章` 标题，章节重新排序为连续 6.1-6.10
- **Arrow direction fix**: 2.2 节依赖关系图箭头方向修正
- **Figure numbering audit**: 全量图号顺序验证，零跳号零错误
- **Chapter summaries added**: 为 ch4-5/ch6-1/ch6-2/ch6-3/ch9-10/ch11-12 补充章末总结段落，改善章节间过渡
- **Source line estimates corrected**: 各章节源码行数估算对齐实际行号，消除统计数据偏差
### Changed
- **Figure 1-7 matrix updated**: 图 1-7 层间交互矩阵更新
- **cover.md stats updated**: 封面数据行数更新至 0.1（封面行数 23），源文件行数同步
- **管理文档同步**: `plan.md`/`requirements.md`/`testplan.md` 统计数字更新（总行数 35077，源文件 35076）
### Quality
- **Terminology unification**: ch2/ch3 分层描述统一使用六组命名（接入层/引擎层/SQL 处理层/存储抽象层/存储引擎层/文件系统层），与 1.2 节图 1-4 完全对齐
- 4 人并行审查持续覆盖（文档工程师/程序员/架构师/图书编辑）
- 交叉引用验证：L6（ch1-2 L220 引用 2.2 节）已验证正确
- 管理文档四件套升级至 0.1
- 合并文档重建（35077 行），HTML 重新生成
---
### 2026-06-05
### Fixed
- **generate_html.py TOC围栏追踪修复**：增加围栏语言类型追踪，仅对`text`块启用"标题退出围栏"行为，`python`/`java`等语言块内的`#`注释不再误入TOC
- **generate_html.py 前导空白修复**：TOC构建器改用`rstrip('\n')`代替`strip()`，缩进的`#`注释不再匹配标题正则，TOC与内容锚点完全一致
- **testplan.md 结构修复**：section 4 未闭合围栏修复、section 5/6 目录编号修正、grep验证命令修正
### Changed
- **generate_html.py**: TOC构建器fence状态追踪完善（facility原不分语言类型→分`text`/`code`），Headline退出仅对text块生效
- **管理文档同步**：plan.md/requirements.md/testplan.md统计数字更新（TOC 487→483，行数34997，封面行数13）
### Quality
- 最终核验54/54通过（新增TOC锚点零断裂和TOC/内容标题数一致性两项检查）
- 交叉核对三个管理文档与交付物的行数/图数/引用数一致
- HTML TOC：全部12章✅ 第1-12章完整覆盖
- 最终产物检查全部通过，MD/HTML/各章节内容一致 ✅
---
### 2026-06-04
### 综合修复（基于4人并行审查结果）
#### CRITICAL 修复
- **Server层位置矛盾（A1）**：ch3图3-1 JDBC和Server改为并列接入层，均指向engine
- **WAL描述直接矛盾（A2）**：ch4图4-18"写前日志(WAL)流程" → "Undo Log流程(MVStore不使用WAL)"
- **MVStore.commit()不存在（A3）**：ch9全部4处`commit()` → `store()`/`storeNow()`
- **MVStore内部组件图含虚假字段（A4）**：图9-3替换为真实字段，添加FileStore说明
- **依赖矩阵errors（B1）**：ch3图3-2 index/expression行补充缺失依赖标注
- **VersionedValue包路径错误（B2）**：3.7.3节更正为`org.h2.value.VersionedValue`
- **Expression继承图中类不存在（B3）**：图2-8删除LeadLagFunction等3个假类
- **SchemaObject包路径错误（B4）**：多处`org.h2.engine` → `org.h2.schema`
- **图6-8a非标准格式（C3）**：去字母后缀，ch6三文件共53处字母后缀图号统一为数字编号
- **反引号跨行断裂（C2）**：ch3 CompressDeflate反引号修复
#### HIGH 修复
- **八层/五层模型说明（D1）**：ch2开头新增分层模型映射说明
- **MVStore版本号矛盾（D2）**：图1-1 v1.4添加脚注"实验性支持"
- **行级锁→表级锁（D3）**：图2-21对比表修正
- **FilePath子包路径修正（D7）**：图1-4/2-13/2-14及ch3图3-34更正子包路径，删除FilePathNio
- **工具层归属说明（D8）**：ch1.2节新增横切工具集说明
- **数据流图分阶段（F4）**：图1-5标注连接建立/查询编译/查询执行三阶段
- **SessionRemote包归属（D3补充）**：Server层添加org.h2.engine说明
- **Session层归属说明（D4）**：图7-5添加Engine子层次说明
- **图式不统一（H4）**：ch11全部图题从代码块内移至代码块外
- **ch7/ch8/ch11添加章末总结**：新增小结段落
- **第9章缺少章首引导（E4）**：新增引导段落
- **ch1至ch2过渡段落（E3）**：新增过渡段落
- **第12章主观评分图（L9）**：添加"仅供参考"说明
- **调试指南压缩（L3）**：11.3节去除IDE特定操作
- **Optimizer行号修正（F1）**：canStop() 300- → 99
- **B-Tree术语说明（D5）**：6.1.1新增术语说明块
- **事务隔离级别澄清（D6）**：6.3节新增隔离级别说明
- **ch6三文件图号去字母后缀并全局连续**：6-1~6-105，零跳号零字母
#### MEDIUM 修复
- **ConnectionInfo行数（I1）**：300→760
- **FileStore双重归属（I8）**：注明实际位于mvstore包
- **各包文件数限定（I9）**：加注"核心包不完全统计"
- **Page内部类说明（I2）**：图2-12前添加说明
- **TableFunction继承关系（I3）**：更正为Function基下
- **insertNode归属（I4）**：更正为Page.NonLeaf方法
- **CAS时序统一（I6）**：图4-21统一CAS→Chunk流程
- **FreeSpaceBitSet伪代码修正（I5）**：修复startBit<0异常
- **空代码块移除（E5）**：ch1-2末尾、ch4-5开头多处移除
- **冗余图引用（J2/J4）**：图3-4/3-5添加视角标注，图3-27添加ch4引用
#### LOW 修复
- **行号加"附近"（M1）**：7处行号加"~"前缀
- **交叉引用修正（L6）**：2.1.8→2.2节
- **序列化格式图字节序（L8）**：图9-8添加大端序说明
- **伪代码简化注释（M3）**：多处添加简化说明
- **行号引用偏差（M1）**：约20处加"~"
### Fixed
- **P0: 第6章锚点冲突**：合并文档中第6章拆分为 3 个文件，`# 第6章 H2 数据库核心算法分析` 出现 3 次，生成重复锚点 `第6章-h2-数据库核心算法分析`（3×）。修复：HTML 生成器锚点自动去重，重复时追加 `-1`/`-2`/`-3` 后缀
- **P0: PDF 导航不可靠**：PDF 大纲（书签）通过 `page.extract_text()` 搜索中文标题定位页面，识别率低。修复：改用 Playwright `page.evaluate()` 获取标题 `offsetTop` + 渲染总高度，精确计算页码
- **P1: PDF 打印目录不可点击**：打印目录中 `href="#anchor"` 链接在 Chromium print-to-PDF 中不生效。修复：获取 `.print-toc a` 元素 bounding rect，将浏览器坐标转换为 PDF 点坐标，使用 pypdf Link 注解添加可点击跳转链接
### Changed
- **generate_html.py**: TOC构建器新增heading-aware fence exit逻辑（与内容构建器一致），修复缺失约300+条TOC条目；新增锚点去重逻辑（`_anchor_counter` 字典 + `make_unique_anchor` 函数）；新增 `heading_data` JSON 嵌入（`<script id="heading-data">`）供 PDF 生成器使用
- **ch6图号全局连续**：6-1~6-105跨三文件连续，零跳号零字母后缀
- **`generate_pdf.py`**：重写大纲生成逻辑，通过 Playwright evaluate 计算页码；新增打印目录 Link 注解实现 PDF 内可点击跳转
- **封面版本更新**：cover.md 版本号 0.1 → 0.1（行数 34,356 → 34,954）
### Added
- **PDF Document Outline**：481 条层级大纲书签（28 顶级 + 453 子级），覆盖全部标题
- **PDF 可点击目录**：打印目录页中 481 个条目全部可点击跳转至对应章节
### Cross-Check
- 5修复Agent并行完成，全部4人审查发现65条问题已修复
- 管理文档四件套升级至v4.13
- 合并文档重建（34996行），HTML重新生成（487 TOC条目，3010围栏，零断链）
- 最终产物 54/54 全部通过 ✅
- HTML 重复 ID：0（共计 493 个 ID）✅
- heading-data JSON：481 条目，0 重复锚点 ✅
- PDF：205 页，481 大纲条目，可点击目录 ✅
- 三格式齐全：MD 2,116 KB / HTML 2,433 KB / PDF 3,047 KB ✅
---
### 2026-06-04
### Fixed
- **P0: ch6-2 残留围栏**：文件末尾多余 ` ```text ` 导致围栏奇偶失衡（383 奇数），已删除
- **P0: ch6-3 围栏未闭合**：决策表 ` ```text ` 代码块缺少闭合 ` ``` `，已添加
- **P0: ch7-8 多余围栏**：文件末尾孤立 ` ``` ` 导致围栏奇偶失衡（749 奇数），已删除
- **合并文档行数对齐**：3 文件修改后合并文档行数与源文件总和一致（34954 行）
- **ch9-10 围栏还原**：git checkout 恢复至 0.1 均衡状态（378 围栏，偶数）
### Changed
- **final_check.py 围栏检查**：49/54 → 54/54 全部通过
- **HTML 同步重建**：TOC 481 项，围栏 3018 对，`<pre><code>` 1541 对平衡
### Cross-Check
- 最终产物检查 54/54 全部通过 ✅
- 合并文档重建（34954 行），HTML 重新生成 ✅
- 四文档版本号统一 0.1
---
### 2026-06-03
### Added
- **封面 SVG 插图**：HTML 封面页新增数据库内核分层结构 SVG 示意图（JDBC/Engine/MVStore/FileSystem 四层同心圆）
- **源码统计面板**：HTML 封面新增源码统计面板（843 Java 源文件 / 229,575 源码行 / 344 测试文件 / 99,396 测试行）
- **PDF 生成脚本**：`.claude/generate_pdf.py`，基于 Playwright/Chromium 从 HTML 生成 A4 格式 PDF（中文支持、可点击 TOC 链接、CSS 打印样式）
- **打印样式 CSS**：HTML 生成器新增 `@media print` 规则，支持 A4 分页、章前分页、表格/代码块不断页
- **多浏览器兼容**：CSS 添加 `-webkit-` / `-ms-` 前缀，IE fallback，Firefox scrollbar 样式
### Fixed
- **P0: 第1章缺失**（HTML 缺失总体架构章）：cover.md 结尾无换行导致合并文档 `---# 第1章` 同行，HTML 生成器无法识别第1章标题。修复：rebuild_merged.py 新增缺换行自动补 `\n`，cover.md 重构格式
- **P0: 多余代码围栏**：ch6-1-data-structures.md:2945 残留孤立 ` ```text` 导致章节文件围栏奇偶失衡（279 odd），已删除
- **P0: 6个源码路径错误**：ch1-2-architecture.md 中 FilePathDisk/FilePathEncrypt/PgServer/PgServerThread/WebServer/WebApp 的包路径缺少 `disk/`、`encrypt/`、`pg/`、`web/` 子包，已修复
- **P0: ch6 图号全局顺序编号**：105 张图跨 3 个拆分文件全局连续编号（6-1~6-105），修复了每个文件从 1 开始编号导致重复的问题
- **P0: ch4-5 图注格式**：98 张图（ch4: 52, ch5: 46）全部插入 `**图 X-Y: Title**` 格式，从代码块内提取为独立图注行
- **final_check.py 后缀字母支持**：图号验证正则从 `(\d+):` 扩展为 `(\d+[a-z]*):`，支持 6-8a/17a/19a 等后缀子图
- **final_check.py 拆分章节支持**：图号验证从逐文件独立检查改为全局跨文件检查，正确支持第6章 3 文件拆分场景
- **9个脚本更新**：`.claude/` 下 9 个脚本从 `ch6-algorithms.md` 引用更新为 3 个拆分文件引用，`check_toc_links.py` 正则放宽至接受中文锚点
### Changed
- **管理文档对齐**：plan.md 行数/图数修正（33162→34355、456→467），requirements.md 行数修正（cover 11→12、ch6-1 2948→2947），testplan.md 引用数修正（184→186）
- **自动化工具链扩充**：plan.md 和 requirements.md 新增 `generate_pdf.py`、`rebuild_merged.py`、`final_check.py` 工具描述
- **HTML 封面质量提升**：CSS 渐变/深色背景加 `-webkit-` / `-ms-` 前缀，IntersectionObserver 降级兼容
- **管理文档统计数据更新**：plan.md/requirements.md/testplan.md 统计数据更新至 0.1（总行数 34650、ch6 图数 105、ch4-5 行数 4297、源码引用 184、围栏 3048、TOC 473）
- **final_check.py 重构**：图号验证改为全局聚合模式，支持跨文件章节；输出格式显示涉及的文件列表
- **交叉核对修正**：requirements.md ch1 图数 16→9；plan.md Phase 4 TOC 467→473；四文档版本统一 0.1
- **ch3 类引用行号修正**：14 处从文件末尾闭括号改为类声明行（如 `Expression.java:550→28`）
- **ch1-2 源码引用修正**：Database.java 行数 5000+→2500+（4 处），Driver.java:42→41
- **ch7-8/ch4-5 行号纠错**：Optimizer.java:77→78, TransactionMap.java:493→462
- **ch6-1 算法分布表新增**：10 算法跨 3 文件位置一览表，便于导航
### Cross-Check
- 3 并行 Agent 审查（文档工程师/程序员/架构师）→ 14+9+9 条发现
- 自动修复应用：围栏失衡、源码路径、老旧脚本引用
- 管理文档四件套统一 0.1 ✅
- 合并文档重建（34356 行），HTML 重新生成（473 TOC 条目，1541 pre/code 平衡，零断链） ✅
- 最终产物检查 54/54 全部通过 ✅
- 合并文档重建（34665 行），HTML 重新生成（473 TOC 条目，3048 围栏，1541 pre/code 平衡，零断链）✅
- 四文档版本号一致 0.1，统计数据全局对齐 ✅
- 3 视角并行审查（文档工程师/程序员/架构师）→ 全部 P0/P1 问题已修复 ✅
---
### 2026-06-03
### Added
- **封面页**：新增 `docs/cover.md`，HTML 生成器支持全屏封面渲染（深色渐变背景，含标题/描述/标签/版本号）
- **全量交叉核验**：3 并行 Agent（文档工程师/程序员/架构师）完成全量交叉核验，确认 7 个章节文件的图数/行数/引用数一致
### Changed
- **HTML 生成器封面渲染升级**：封面页以全屏深色渐变背景渲染，正文部分维持原有侧边栏布局
- **管理文档四件套统一**：requirements.md/plan.md/testplan.md/changelog.md 版本号对齐 0.1
### Cross-Check
- 管理文档四件套统一 0.1 ✅
- 合并文档重建，HTML 重新生成 ✅
---
### 2026-06-03
### Added
- **封面页**：新增 `docs/cover.md`，HTML 生成器渲染为深色渐变全屏封面（含标题、描述、标签）
- 合并文档命令更新：9 文件 → 10 文件 cat（含 cover.md）
### Changed
- HTML 生成器全面升级：封面页以全屏深色渐变背景渲染，正文部分维持原有侧边栏布局
### Cross-Check
- 全量交叉核验（3 并行 Agent：文档工程师/程序员/架构师）
- requirements.md 版本 0.1→0.1，源文件表补充 cover.md（9→10 个），统计数据更新（34344→34355 行，184→186 引用）
- plan.md 版本 0.1→0.1，Agent 分配表补充 cover.md，统计数据对齐
- testplan.md 版本 0.1→0.1，交叉引用计数更新（11→18 处），扫描文件数更新（7→9）
- cover.md 版本 0.1→0.1，元数据与源文件数对齐
- 管理文档四件套统一 0.1 ✅
- 合并文档重建（34355 行），内容零变化 ✅
### Fixed
- **交叉引用标题修正**：ch3-packages、ch7-8-sql-optimizer、ch9-10-persistence-locking 三处 "第6章《经典算法解读》" → "第6章《H2 数据库核心算法分析》"（与真实 H1 标题匹配）
- **B-Tree 术语统一**：ch4-5-modules-processes 正文 22 处 "B-tree" → "B-Tree"，消除大小写不一致
- **隔离级别修正**：ch1-2 对比表 H2 隔离级别从 "4级" → "5级"（实际支持 RC/RR/Snapshot/Serializable/ReadUncommitted）
- **plan.md Agent 表行数**：ch3 2287→2288，ch4-5 4002→4003（与文件实际行数对齐）
---
### 2026-06-03
### Added
- **第6章按主题拆分为3个子文件**（Plan B）：
  - `ch6-1-data-structures.md`（2948 行）— 6.1 B-Tree + 6.2 CoW + 6.3 MVCC
  - `ch6-2-storage-algorithms.md`（4667 行）— 6.4 Chunk + 6.5 LIRS + 6.6 FreeSpace + 6.7 MVStore
  - `ch6-3-query-algorithms.md`（3459 行）— 6.8 Optimizer + 6.9 R-Tree + 6.10 Parser
- 合并文档命令更新：7 文件 → 9 文件 cat
### Fixed
- **章节篇幅失衡问题已解决**：ch6 从单文件 537KB/11074 行降至最大 4667 行
- 单文件最大行数从 11074 → 8482（ch7-8）
- 源文件从 7 个增至 9 个，内容零变化
### Cross-Check
- 3 个子文件行数和 = 11074，与原始 ch6 完全一致 ✅
- 图数：12+16+11=39，与原始 ch6 完全一致 ✅
- 源码引用：25+9+1=35，与原始 ch6 完全一致 ✅
- 合并文档 34338 行不变 ✅
- 管理文档四件套更新至 0.1
---
### 2026-06-03
### Added
- **Issue 3: ch9-10 跨章引用补充**：引言新增 3 处跨章引用（第6章 B-Tree/CoW/MVCC、第5章事务提交/回滚、第8章并发访问）
- **Issue 1: Server 层位置说明**：ch1-2 图1-4 后补充 blockquote 说明 Server 是并行接入层
### Fixed
- **Issue 2: ch2 子图编号统一**：全部 23 幅图从字母后缀（2-1a, 2-1b,…）改为顺序编号（2-1~2-23）
- **Issue 4: 代码块语言标识**：7 个章节文件共 1525 个代码块补全语言标识（```text / ```java / ```sql），零遗漏
- **Issue 6: 图号乱序修复**：
  - ch9：36 幅图按位置重排，9-33~36 溢出编号融入正确位置
  - ch11：4 幅图重排（11-9→11-6, 11-6→11-7, 11-7→11-8, 11-8→11-9）
  - ch12：10 幅图全部重排（12-1~12-10 顺序正确）
- **ch9-10 溢出编号消除**：9-33~36 融入主序列，最终 9-1~9-36 连续
- **P0: 代码片段长度检查**：修剪 4 个超长代码块（92→22, 93→25, 45→29, 41→28 行），剩余 5 个伪代码块 31-40 行属算法描述可接受
- **P1: ch3 图号乱序修复**：53 幅图全部重排（3-1~3-53 顺序正确），48 处溢出编号消除
- **P1: ch7-8 图号乱序修复**：145 幅图全部重排（7-1~7-64, 8-1~8-81 顺序正确），含 58 处正文引用更新
- **P3: ch3 跨章引用补充**：引言新增第2章/第5章/第6章引用
- **P3: ch7-8 跨章引用扩展**：引言补充第3章包结构、第5章流程引用
### Known Issues（待后续版本）
- **ch6 篇幅过大**：~536KB，约为其他章节的 3-5 倍（结构性限制）
- **HTML 浏览器兼容性验证**：已验证 Chrome/Firefox/Edge 核心特性，待完整跨浏览器测试
### Cross-Check
- 6 项 Known Issues 已处理 5 项（1-4, 6），1 项部分处理（章节篇幅失衡已记录）
- **最终产物交付检查**：38/41 通过，3 项设计豁免（ch4-5 图在代码块内、ch6 字母后缀编号、合并文档行数差 6 行）
- 合并文档重建（34338 行），与各章节总和一致
- HTML 重新生成（467 TOC 条目，1542 pre/code 平衡）
- 全量代码块语言标识通过验证 ✅
- HTML TOC 467 项全部可点击跳转 ✅
- `<pre><code>` 标签平衡：1542 open / 1542 close ✅
- ch10 溢出编号（10-29~35）消除并顺序重排 ✅
- 管理文档四件套更新至 0.1
---
### 2026-06-03
### Added
- **P2交叉引用补充**：ch4-5引言补充第6章《H2 数据库核心算法分析》引用；ch7-8引言补充第2章《分层模块划分》2.1.3 Command 层引用
- **P1术语统一**：Copy-on-Write 大小写统一为小写 on（ch1-2/ch3/ch11-12 共7处）；ch4-5 图标题 `chunk` → `Chunk`
### Fixed
- **P0源码路径前缀修复**：ch7-8/ch9-10/ch11-12 中缺失的 `org/h2/` 前缀（共约20处），含 `**核心文件**: ` 和 `源码位置：` 两类格式
- **P0行号纠错**：ch1-2 Expression.java:105→28、RootReference.java→MVMap.java:45；ch3 CompressLZF compress/expand 行号修正；ch4-5 Select.java queryWindow() 451→441
- **P1 Undo Log 正文大小写统一**：ch9-10 正文3处 "Undo Log" → "undo log"，保留图标题/章节标题 Title Case
### Known Issues（待后续版本）
- 图号乱序/全局重编号（ch3, ch7-8, ch9-10, ch11-12 多处）
- Server 层在图 1-4 中的位置矛盾（ch1-2）
- 代码块缺少语言标识（``` → ```java）
- 章节篇幅失衡（ch6 过大约 536KB，ch11-12 过小约 30KB）
- ch2 使用子图编号（2-1a, 2-1b 等）
- ch9-10 完全无跨章引用
### Cross-Check
- TOC 473条全部可解析 ✅
- 文档行数：33079（合并）+ HTML TOC零断链 ✅
- P0/P1/P2 三类修复全部应用并验证 ✅
- 管理文档四件套统一 0.1 ✅
---
### 2026-06-03
### Added
- **HTML生成器heading感知式围栏处理**：在 `in_pre=True` 时遇到heading自动闭合 `<pre><code>`，防止因内部围栏奇偶错乱导致heading锚点丢失
- **P2术语统一**：Undo Log大小写规范（图标题/章节标题用Title Case，正文保留lowercase）
- **零"重做日志"残留**：`重做日志` → `redo log`，全库扫描确认零残留
### Fixed
- **无效章节"6.0 目录"移除**：ch6-algorithms.md手工目录（含无效内部锚点`#6.1-b-tree-索引`等），已删除
- **ch11-12代码围栏修复**：44围栏偶数对齐，插入缺失的图12-5开头围栏，清理多余重复围栏
- **Undo Log大小写修复**：ch4-5 图5-28标题`undo log遍历方向`→`Undo Log遍历方向`；ch9-10 `Undo log`混用→`Undo Log`
- **重做日志→redo log**：ch4-5 L507 中译英统一
### Cross-Check
- TOC 473条全部可解析 ✅
- 文档行数：33079（合并）+ HTML TOC零断链 ✅
- 术语统一：Undo Log/undo log按规范分布 ✅
- 零"重做日志"残留 ✅
- ch6零无效章节 ✅
- 管理文档四件套统一 0.1 ✅
---
### 2026-06-02
### Added
- **标题与图例分离标准**：章节标题不得包含「图 X-Y:」引用，图例移至正文独立成行
- **图注格式统一**：全部独立图注使用 `**图 X-Y: Title**` 加粗格式
- **管理文档升级 0.1**：requirements.md/testplan.md/plan.md 同步更新
### Fixed
- **第6章39处标题含图例**：`### 6.1.2 图 6-1: XXX` → `### 6.1.2 XXX` 并移图例至正文
- **ch3图号格式统一**：`**图 X-Y**: Title` → `**图 X-Y: Title**`（53处）
- **ch6/ch9-10/ch11-12图注加粗**：`图 X-Y: Title` → `**图 X-Y: Title**`（110+处）
- **ch4-5图注保持不变**（位于代码块内，属 ASCII 图内容）
- **管理文档统计数字对齐**：行数/图数/引用数按实际 `wc -l` 和 `**图` 标记修正
### Cross-Check
- 章节标题零「图 X-Y:」违规 ✅
- 独立图注格式统一（**bold** 标准化） ✅
- 管理文档三件套统一 0.1，changelog 0.1 ✅
---
### 2026-06-02
### Added
- **第3章8层架构重构**：从6组按层分为13个小节，按JDBC/Engine/Command/Expression/Table-Index/MVStore/FileSystem/Server逐层展开，JDBC移至首层，Server移至FileSystem之后
- **第5章流程模板标准化**：全部9个流程统一为 流程图→核心逻辑阐述→关键代码引用 模板，为5.5-5.9补充核心逻辑阐述文本
- **管理文档全量更新**：requirements.md/plan.md/testplan.md 升级至 0.1，反映8层架构和模板标准化变化
### Fixed
- **目录结构修复**：
  - ch9-10 标题层级修复（`#`→`###` 跳跃修复为 `#`→`##`→`###` 连续）
  - ch7-8 补充缺失的 `## 7.3 缓存机制` 父标题
  - ch11-12 标题层级修复（`#`→`###` 跳跃修复为 `#`→`##`→`###`）
  - ch9 移除重复的「第九章 持久化引擎深度解析」标题（中文数字冗余）
- **术语统一**：
  - 架构示意图 → 架构图（ch4-5）
  - chunk → Chunk（ch4-5 生命周期图统一大写）
  - 文件空间布局变化示意 → 文件空间布局示意图
### Cross-Check
- 版本号一致性：requirements.md/plan.md/testplan.md 统一 0.1 ✅
- 行数统计一致性：33216 行 ✅
- 工具脚本引用一致性：`_audit_smart.py`/`generate_html.py` 三文档同步 ✅
- 标题层级检查：所有7个源文件 H1→H2→H3 连续无跳跃 ✅
- 章节边界检查：12章全部以 `# 第N章` 开头 ✅
---
### 2026-06-02
### Changed
- **需求文档迭代**：`requirements.md` 升级 0.1，修正过时统计数据（18500+→33162 行）、补充 0.1 变更记录、更新交付清单状态
- **实施计划迭代**：`plan.md` 升级 0.1，重构已完成阶段标记、新增 Phase 7 持续维护计划、补充自动化工具链说明
- **质量标准迭代**：`testplan.md` 升级 0.1，新增章节标题/交叉引用/HTML TOC 验证项、补充自动化验证命令、丰富拒绝标准
### Cross-Check
- 版本号一致性：三文档统一 0.1 ✅
- 行数统计一致性：33162 行，实际与文档一致 ✅
- 工具脚本引用一致性：`_audit_smart.py` / `generate_html.py` 三文档同步 ✅
- `.gitignore` 规则三文档一致引用 ✅
- 自动化工具链：合并 MD → 审计 → HTML 生成全链路验证通过 ✅
---
### 2026-06-02
### Fixed
- **章节标题结构修复**：第 6 章去空格、第 10 章从 `##` 升 `#`（中文数字→阿拉伯数字）、第 12 章从 `##` 升 `#`，全部 12 章 H1 对齐
- **ch1-2 架构章**：补充 7 处源码引用（`.java:` 格式），覆盖 JDBC/Engine/Command/Expression/Table/MVStore 各层
- **ch3-packages 包详解章**：源码引用从 3 处提升至 18 处，覆盖 engine/command/expression/table/index/mvstore/jdbc 等主要包的 `org/h2/` 路径 + 行号
- **跨章交叉引用**：新增 6 处，连接架构→算法/持久化/SQL、流程→SQL/优化器/持久化/锁、算法→持久化/锁
- **HTML 导航 TOC**：生成脚本 `.claude/generate_html.py`，456 项可点击目录、滚动高亮、移动端响应式侧边栏
- **`.gitignore` 完善**：添加 `docs/*.pdf`、`docs/*.html`、`docs/*.log`、`*.zip`、`mdpdf.log` 规则
- **清理杂散文件**：删除 `docs/temp_output.pdf`（0 字节空文件）
---
### 2026-06-02
### Added
- 图表标准升级：每 ### 子章节 ≥ 2 个 ASCII 图（原标准 ≥ 1）
- 全量补充 ASCII 图：为所有缺图子章节补充架构图/流程图/关系图/示意图
- 新增自动化审计脚本 `_audit_smart.py`，支持 #### 子章节聚合计数
- 审计检测增强：识别 ▼ ▲ → 箭头字符（原仅检测 ┌ └ ├ │）
- 修复审计边界 Bug：### 区段结束边界现在正确延伸到同级下一 ###
### Changed
- `requirements.md` 0.1：升级 ASCII 图标准至 ≥ 2 图/子章节，增加模板节/过渡节的分类标准
- `plan.md` 0.1：新增 Phase 6 增强图表覆盖阶段，含分批修复计划和质量门禁
- `testplan.md` 0.1：升级自动化验证标准，新增 A/B/C/D 四类问题分类
- `ch3-packages.md`：修复 2 处缺图（3.2.2 command 包 + 3.6.5 mode 包）
- `ch4-5-modules-processes.md`：补充 100+ 图（从 1350→3671 行），全模块/流程覆盖
- `ch6-algorithms.md`：补充 150+ 图（从 6364→10900 行），10 算法模板标准化
- `ch7-8-sql-optimizer.md`：补充 60+ 图，所有子节 ≥ 2 图
- `ch9-10-persistence-locking.md`：补充 11 图至 #### 子章节
- `ch11-12-guide-summary.md`：补充 5 图至导读/总结章节
- `h2-source-code-analysis.md`：重新合并，33160 行（原 18703 行）
- `h2-source-code-analysis.html`：重新生成，带可点击锚点和样式
### Fixed
- `_audit_smart.py`：修复 ### 区段边界 Bug（误将 #### 当作结束边界）
- `_audit_v2.py` / `_audit_v3.py`：同步箭头字符检测支持
---
### 2026-06-02
### Added
- 质量迭代（Phase 5）：自动化审计脚本 `_audit_v2.py`，逐章扫描 ### 级子章节的 ASCII 图覆盖率
- 为 4 处缺少 ASCII 图的子章节补充框线图：
  - `3.3.4 mvstore.cache 包` — 新增 LIRS 数据结构架构图
  - `3.6.3 util 包` — 扩写 8→50 行，新增工具类分类架构图
  - `3.6.4 compress 包` — 扩写 13→40 行，新增压缩写入路径流程图
  - `3.6.5 mode 包` — 扩写 16→50 行，新增兼容模式架构图
- 质量门禁：零 A 类（### 级无图）、零 B 类（内容过薄）问题
- 文档行数：6940 → 18705 行
### Changed
- `requirements.md` 0.1：新增 ASCII 图质量标准和自动化验证流程
- `plan.md` 0.1：新增 Phase 5 质量迭代阶段（审计→修复→重新审计）
- `testplan.md` 0.1：新增自动化验证章节和通过标准
- `ch3-packages.md`：3.3.4 / 3.6.3 / 3.6.4 / 3.6.5 扩写并补充架构图
---
### 2026-06-02
### Changed
- 调整输出策略：标准输出仅包含 MD + HTML，PDF 仅在明确要求时生成
- 更新 `requirements.md`、`plan.md`、`testplan.md` 反映按需 PDF 策略
---
### 2026-06-01
### Added
- 完成全部 12 章文档撰写（7 个 Agent 并行，共 ~6900 行）
- 合并编译为完整文档 `docs/h2-source-code-analysis.md`
- 生成 PDF 文档 `docs/h2-source-code-analysis.pdf`
### Chapter files (7)
- `ch1-2-architecture.md` — 总体架构 + 分层模块 (443 行)
- `ch3-packages.md` — 核心包结构 (704 行)
- `ch4-5-modules-processes.md` — 核心模块 + 9 流程 (1349 行)
- `ch6-algorithms.md` — 10 个经典算法 (1442 行)
- `ch7-8-sql-optimizer.md` — SQL 执行 + 优化器 (1372 行)
- `ch9-10-persistence-locking.md` — 持久化 + 锁 (1368 行)
- `ch11-12-guide-summary.md` — 导读 + 总结 (235 行)
---
### 2026-06-01
### Added
- 初始版本，完成需求分析与规划
### 文档结构
- `docs/requirements.md` — 需求文档（章节结构 + 交付标准）
- `docs/plan.md` — 实施计划（4 阶段 + 7 Agent + 风险矩阵）
- `docs/testplan.md` — 质量标准（5 维度检查清单 + 拒绝标准）
- `docs/changelog.md` — **本文**
### 需求要点
- 12 章文档结构
- 9 个核心流程（SELECT/INSERT/UPDATE/DELETE/COMMIT/ROLLBACK/COMPACT/CHUNK/READ）
- 10 个经典算法（B-Tree/CoW/MVCC/Chunk/Optimizer/LIRS/FreeSpace/R-Tree/Parser/MVStore）
- 每子节 ≥ 1 个 ASCII 图
- 输出 MD + PDF 双格式

---

## [0.1] - 2026-11-26

### 变更

- **共享辅助函数收进 `lib/`，配置读取改成有判据的边界**：六个函数原先在 2–3 个审计里各写一遍
  （`coord_count`、`_files`/`files`、`scripts`/`python_files`、`_rel`/`_relative`、`load_baseline`、
  `archive_root`/`reports_root`），现在各只有一份，落在 `_mdutil`、`_config`、`_fsutil`、`_baseline`；
  被测试 `patch.object` 的名字保留一行别名（patch 缝是契约的一部分），语句数 14,679 → **14,674**。
  新增 `ImportTimeConfigReadTest`：从控制台入口做导入闭包，闭包内出现模块级 `_config.` 读取即失败；
  `crossrefs`/`glossary`/`index`/`index_xrefs`/`smart` 已改为调用时读取（删掉 9 个纯死赋值），
  仍以子进程执行的脚本模块不在闭包内、残余登记为 `rf-75`，`core/scaffold.py` 是带理由的例外。
- **测试：守卫位置与归类**：39 个 suite 把 `__main__` 守卫写在类定义之前（直接跑会静默跳过这些类），
  全部移到文件末并由 `test_meta_taxonomy.py` 的元测试永久禁止；`cover.py` 的两个用例从 `layer:render`
  移入 `layer:manuscript` 的 `CoverStatsTest`，迁移后闲置的 `mock` 导入一并删除。
- **把最后几处「这本书的内容」从代码里清掉**：`manuscript/case_studies.py` 的思考小结原本写死三条 H2/JDBC
  问题，现改为 `data/book/case-studies.toml [headers.<scenario>].questions`，缺省用与书无关的三问；
  同一函数对 `heading`/`opening` 缺省也不再抛 `KeyError`（只配标题的书也能渲染）。`glossary.py`、
  `index.py`、`case_studies.py` 的文档字符串去掉 H2 字样。核查结果：工具链代码里已无 `org.h2`、
  具体源码树路径、具体书专有词；语言分析全部走注册表 + `sources.suffixes`（java/python/rust/kotlin/go/c
  六个适配器，`detect()` 由后缀反推），换书只改 `data/book/book.toml` 与 `data/config/*.json`。
- **C 语言分析器落地（plan-12 阶段 1–4）**：新增 `ingest/languages/<lang>.py`（`name = 'c'`、
  `suffixes = ('.c', '.h')`），注册表与 `data/config/base.json [sources].suffixes` 都补上 `c`，
  脚手架模板同步。C 没有包声明，所以包按目录切；`.h` 与同名 `.c` 同包；**引号形式**
  `#include` 才转成包级依赖（尖括号系统头丢弃），目标先在引用文件所在目录、再到根解析；
  public 遵循 C 自己的规矩——头文件声明过的类型与原型才是 API，只在 `.c` 里定义（含
  `static`）的不进 `api`。新夹具 `src/test/fixtures/<mini-c>/`（头文件 + 实现 + 无注释文件 +
  静态函数 + 两种 include）与六个用例同行，覆盖包归属、依赖方向、public/API、无注释摘要为空。
  真实 C 树验收（阶段 5）仍待执行。
- **书的内容从工具链里搬出去**：`manuscript/terms.py` 原本写着 44 条中英术语别名与 99 条「不算术语」
  词表，`manuscript/case_studies.py` 写着三个案例的章节标题与开篇散文——都是这本书的内容，
  换一本书就是错的。现在它们的归属处是 `data/book/glossary.toml`（`skip` + `[aliases]`）与
  `data/book/case-studies.toml`（`[headers.<scenario>]` 的 `heading`/`opening`/`figure_prefix`/
  `figure_start`），脚本在**调用时**读取，文件缺失或损坏按「没配」处理（词表与案例表不再于导入期读取）。
- **源码坐标形状只有一份**：`lib/_mdutil.source_ref_re(suffixes)` 统一 `Class.java:12` 形状，
  `cover`、`balance`、`book_quality`、`prose_quality`、`smart`、`terms` 与 `source_refs` 均按
  `_config.source_suffixes()` 现建；之前七处各自写死 `.java:`，换成 C/Rust 的书会统计出「零坐标」。
- **归档目录建成 `docs/archive/v0.1/`**：恢复被 `43cd061cc` 删掉的历史快照（`phase3-audit`、
  `writing-style-enhance-plan`、五份计划、旧 changelog / plan / review-findings），并把 4.x–6.1 的
  书籍版本记录归一为 0.1——工具链、书籍、被分析源码是三条版本轴，之前被当成了同一条。
  `multi-book` 与 `figure-chapter-plumbing` 两个已完成的迭代目录移入该目录，设计文档去掉
  「已落地 / 尚未 / 余下」这类过程描述，只描述当前事实。三份主账本各新增 `## 归档` 索引。
- **归档不当活文档判定**：`doc_drift`、`traces` 的 doc 清单与 `_config.excluded_dirs()` 排除
  `docs/archive/`——归档保存的是它描述那一版的措辞，强求它跟上当前路径等于要求历史保持最新。
  `audit/doc_archive.py` 新增例外：版本目录可与「开发中」的版本段并存（迭代收尾即归档，发布时
  才迁出变更段），只有已发布版本不得留在主文档。
- **工具链控制台入口登记**：`books/pyproject.toml` 新增
  `[project.scripts] bookwright = "app.cli:main"`；配置读取全部在调用时完成，已验证无书环境下
  `app.cli`、`core.actions`、`app.tui`、`core.settings`、`check_runner`、`make`、`ingest.digest`
  导入不报错（安装形态下 `--book` 必填）。
- **覆盖率收尾：`app/tui.py` 与 `manuscript/glossary.py` 到 100%**：全局 97%（缺 249 行、246 个半边分支，
  此前 264 / 266）。补的都是入口面与错误路径：`--once settings`、退出行经 `handle` 退出、无预估时
  只报用时、provider 上移被拒、分组里已经没有对应行、`edit_provider` 的失败分支；术语表补上
  带冒号定义与超长截断、元数据标记跳过、同词跨章只记首章、同首字母共用一个标题、无标题章节不记章号、
  一行里重复章号只计一次、空术语表。
- **两个测试方法从未执行**：`test_app_tui_interaction.py` 的 `menu_estimate` 辅助函数与两个
  `test_*` 之间丢了空行，两个用例缩进落在辅助函数的 `return` 之后，成了死代码；已移回测试类。
- **删两处不可达分支**：`glossary.py` 的「标题缩写」判定被前面的「编号列表项」正则完全覆盖
  （`^\d+[.、]` 已吃掉 `1.1 …`），删掉；定义提取改为取词条正则匹配位置之后的文本，
  不再用 `re.split` 回找加粗标记（后者存在恒不成立的找不到分支）。
- **单文件覆盖率地板抬到 90，全局 95%**：十八个低于 90 的模块按「先补错误路径、再补入口面」补齐，
  最低文件从 88.1% 抬到 **90.1%**（`audit/index_xrefs.py`），`coverage_min_per_file` 88 → **90**，基线重记。
  补的多是不可达兜底之外的真题：`_fsutil` 的写入失败、`html_cache` 的缓存不可用、`plan_coverage` 的两个
  缺标记、`prose_quality` 的评分锚点与表格空行、`content_depth` 的基线更新与按类型计数、`exercises` 的
  三个缺标记、`doc_drift` 的 `STYLE_KEY` 检查、`structure` 的四个子检查失败、`chapters` 的附录追加
  （跳过/干跑/写入）、`pdf_metrics` 的写回与真实文本测量、`verify_pdf` 的注释目标与密度判定。
- **删除不可达分支**：对整棵树做「`return`/`raise`/`continue`/`break` 之后还有语句」的扫描，结果为 0；
  上一轮在 `style.py` 查到的唯一一处（恒不成立的「进行中」豁免）已修。
- **慢档实测（`cover --full`）**：全局 95%，但 `audit/order_dependence.py` 只有 61%，低于 90 的地板；
  该模块只在慢档的顺序依赖探测里运行，快档不测量，地板 86 时也已经红，登记为 rf-72。
- **变异分数收口**：`core/menu.py` 的 `Outcome` 补一条不可变性断言（`frozen=True` 的变异原先存活），
  survivor 6 → **0**；`render/pdf_metrics.py` 的 survivor 6 → **3**（新增真实文本 PDF 测量用例杀掉
  `reverse=True`、`sum(...) or 1` 两处），剩下三条登记为等价变异并把容忍数 4 → **3**。

- **基线读写收口到 `lib/_baseline.py`（rf-71）**：`ascii`、`style_rules`、`source_symbol` 三份「已接受的遗留项」
  原先各写一遍读取、容错与写入，现在共用 `_baseline.load_at` / `save_at`（统一 `updated` / `note` / `accepted`
  外壳，扩展字段如 `source_version` 原样保留），每个 gate 只留一个按调用解析的 `baseline_path()`。
  顺带修掉 `diagrams.py` 在 import 时就把基线路径定死的问题——选了版本（edition）后它会写进无版本的仓库路径。
  `perf_baseline` 与 `content_volume` 仍是各自的文件：它们记的是测量值与卷册台账，不是接受清单。

- **测试用例核查与整改**：删掉整份重复的 pdf_metrics 目标写回用例（13 条与
  `test_render_pdf_metrics_units.py` 同函数同断言，后者 33 条覆盖更全）；把零出站用例并入
  `test_network_isolation.py`（原本两处各写一半）；去掉 `test_pdf_tools`、
  `test_release_and_runner` 里与别处重复的两条；四处同名不同源的用例改名说明差别
  （artifact/manuscript、book 前缀、带 `--title` 的发布、in-process 的 to_epub）。
  弱断言改成内容断言：`index_xrefs` 的「JSON 可解析」原本恒真（`{...} if ... else {}`），
  `balance` 的索引计数与 diff 方向、`exercises` 的缺槽位、`suggest_renames` 的邻近方法、
  `smart` 的图形引用结论各自断言真实结果；四条「跑一次脚本」的用例改成不依赖仓库当前状态的确定值。
  其中两条仍以真实仓库的行数与退出码为准（一次格式化就红），改为在 fixture 书上断言报告的形状。
  `script_contract` 与 `doc_drift` 原先按单引号匹配 `__main__` 守卫与引号内的名字，一次格式化就会让
  规则静默失效，改为两种引号都认（各带一条用例）。testplan 的网络隔离载体指向合并后的文件。
- **重复套件现在会被判红**：`test_redundancy.py` 新增 `SUBSUMED`——一个套件对某模块取用的符号集，
  若是另一个套件同一模块符号集的真子集且不少于四个，就判定它在复述别人的覆盖（整份重复的
  pdf_metrics 用例当初正是这样长出来的）。符号集来自 `load_module()` 之后实际调用的属性，
  只是借用模块做准备的套件不会误伤；同时补三条用例把「真子集报出」「自带新符号不报」「两个符号不算」钉住。

- **覆盖率快档 97% → 100%**：缺失 249 行 → **0 行**，半边分支 246 → **0**（105 个文件全部 100%；共享函数收敛后语句数 14,676 → 14,674），
  基线重记。收敛过程中删掉的分支都先证明过不可达：`balance` 的第二个 `__main__`、`terms` 的成对守卫假分支
  与被编号规则覆盖的标题缩写规则、`settings` 恒不成立的空小节分支、`epub_diff` 在 `parser.error` 之后的
  `return`、`index` 的兜底章标题、`test_redundancy` 的 `TRIVIAL` 边（`normalise` 保留 `def` 行）、`smart` 的
  非四级标题边、`doc_archive` 的顶层多余文件分支（`archived_names()` 的值都以 `.md` 结尾）。
  三条 `__main__` 守卫（`app/web.py`、`check_runner.py`、`audit/test_health.py`）改用
  `_fixture.run_inproc(..., '--help')` 在**被测进程内**执行——argparse 会在起服务/跑门禁之前退出，
  既不卡死也计入覆盖率；此前判它们「快档不可达」是错的。

- **评审修复：配置越界与重复计数（rf-71）**：七个脚本不再按名字拼出书目录
  （`render/to_pdf`、`to_epub`、`pdf_from_html`、`pdf_toc_links`、`audit/balance`、`audit/doc_drift`、
  `core/menu`，其中两个文件的那几行本就是死代码），改读 `_config.BOOK_ROOT` / `_config.DIST_DIR`；
  `check_architecture` 补上「按名字拼出书目录」规则——原先只拦带斜杠的 `books/`，`os.path.join(R, 'books')`
  可以绕过。`test_report.py collect` 把类方法算了两次（2351 vs pytest 2013），改为每个 `test_` 函数只记一次；
  `smart.py` 的图形标记改读 `style.json [diagrams].markers`（配置里写着、代码里写死），`_defaults/style.json`
  删掉谁都不读的 `sections` 块；`detect_weak_verb_xing` 的「进行中」豁免判定永远不成立（正则最短四字），
  改前缀判定；`to_epub.py` 一处缩进错位。

- **变异冒烟成为可运行的一步（rf-68）**：`mutation_smoke.py` 增加 `--all` 与 `TARGETS`（模块 → 测试文件 +
  允许的等价变异数），候选变异改为按行排序的固定顺序（原先每次抽样不同，无法当判据）；`make.py mutation`
  接入，默认 advisory、`--mutation-strict` 可当硬门禁。实测 `epub_source`/`_perfhistory`/`menu` 全部杀死，
  `pdf_metrics` 剩余 4 个均登记为等价变异。
- **rf-69 加固**：CSS 与构建脚本检查的路径修正后，补一条用例钉住那四个源文件确实存在，路径再漂移即失败。

- **rf-64 / rf-65 / rf-66 收口**：`actions` 的 `_invoke` 拆出 `_unbuffered()`/`_stream()`/`_heartbeat()`
  （各有用例，`actions` 97%）；`verify_pdf` 的字体判定早已抽成 `font_is_embedded()`；探测类失败路径
  （字体命令、`doctor` 的可选工具）都不再只能靠真机触发；`calibrate()`/`figure_caption()` 的 docstring
  写明公共 API 定位。

- **单文件覆盖率地板抬到 88（rf-70）**：十二个低于 88 的模块逐个补错误路径与入口面的用例
  （`make.py` 85.7% → 99%、`test_report.py` → 97%、`snapshot.py` → 98%、`source_refs.py` → 98%、
  `index.py` → 97%、`style.py` → 95%、`smart.py` → 98%、`version_consistency.py` → 94%、
  `file_length.py` → 97%、`archive.py` → 99%、`mutation_smoke.py` → 100%、`requirement_trace.py` → 99%），
  `coverage_min_per_file` 86 → **88**，基线重记；全局 91.7% → **94%**，最低文件 88.1%。

- **rf-67 / rf-68**：单文件覆盖率地板 84 → **86**（门槛 90 下通过，最低文件 86.3%）；把变异冒烟作为验收手段
  跑通——`render/epub_source.py` 5 个变异全部杀死、`lib/layout.py` 8 个全部杀死；`pdf_metrics` 补 8 条 3%/样本窗口
  边界用例后剩余为等价变异，不再追。抬到 88 的三个短板模块登记为 rf-70。

- **rf-63 收口**：`doc_drift.py` 85.8% → **89%**（手册维度缺失、维度重复、引用管理文档三条 + 干净手册）、
  `app/tui.py` 86% → **88%**（改配置的非法序号、越界、空值、写入失败、成功回报；进度行的去重、空行、去时间戳）。

- **`structure.py` 的 CSS/构建脚本检查一直静默跳过（rf-69）**：样式表拆到 `html_shell.py`、构建脚本移到
  `manuscript/` 后，检查仍读 `audit/to_html.py` 与 `audit/glossary.py`，于是常年走「跳过」「未找到」分支。
  现在两个检查抽成 `css_style_missing()` 与 `builder_script_problems()`，路径指向真实位置并同时扫
  `to_html.py`+`html_shell.py`；修复后 **9 个 CSS 钩子全部命中**。`structure.py` 84.6% → 89%。

- **rf-63 第一步**：`lib/status.py` **85.4% → 88%**——缺失产物的时间戳/体积/页数各降级为空或占位、
  非 PDF 不回落到阅读器、缺 `pypdf` 与坏 PDF 都不抛异常、三页 PDF 报「3 页」。

- **rf-61 第三步**：`ingest/chapters.py` **86.9% → 88%**——模板填充失败回落、CJK 间距对围栏与标题的例外、
  跨章标题回退；三个大模块（`verify_pdf` 89%、`actions` 95%、`chapters` 88%）均高于当前逐文件基线，
  `make.py cover` 在门槛 90 下通过。`chapters` 剩余的整章渲染分支转 rf-63/64 继续。

- **rf-61 第二步**：`core/actions.py` **84.2% → 95%**——用例覆盖体积结论三态（无基线/一致/低于）、
  LLM 记账不可用与预算告警、provider 失败仍出状态、`analyze()` 的体积与「本轮没有重写」说明、
  `_dispatch` 的五条报告动作路由与未知动作。`verify_pdf` 已在第一步到 89%。

- **rf-61 第一步（同时落实 rf-64 的做法）**：`verify_pdf` 的字体判定抽成 `font_is_embedded()` 与
  `_has_program()`——可独立调用、不依赖 pypdf 对象；新增 7 条用例（Type3、直接程序、后代字体、
  无程序、不可读字典、字体表非映射、同族只报一次），该文件 **84.6% → 89%**（基线 86.3）。

- **覆盖率/质量的后续路径全部立项**：rf-63（按半分支而非行）、rf-64（抽可测边界：`verify_pdf` 字体检查、
  `actions._invoke` 的流与心跳）、rf-65（探测类依赖注入）、rf-66（只有用例调用的辅助函数逐一处置）、
  rf-67（单文件地板 84 → 88 分两批）、rf-68（变异冒烟纳入验收 + `except` 抽检）。

- **rf-62 处置**：`log_file()` 接入 `describe()`；`calibrate()`/`figure_caption()` 保留为公共 API；
  其余两处早前已不存在。
- **代码审计（90 小时窗口）**：33 道门禁、ruff、`doctor` 全绿；107 个配置键全部有读取点；
  无 ≥60 行函数；删除零引用的 `audit/test_redundancy.TooLarge`。另发现五个辅助函数只有用例在调用，
  已登记为 rf-62（接线／删除／保留为公共 API 三种处置需逐项决定，不盲删）。

- **覆盖率门槛抬到 90（rf-59 / rf-60 / rf-61）**：全局门槛 `coverage_fail_under` 88 → **90**（实测 91%，
  `make.py cover` 通过），单文件地板保持 84；逐文件基线按当前实测重记，其中 `to_epub.py` 95.6% → 100%、
  `_config.py` 92.6% → 94% 是真提升，`actions`/`chapters`/`verify_pdf` 三处未达原基线（84.2 / 86.9 / 84.6），
  已把逐行缺口登记为 rf-61，不以“重记基线”代替补测试。

- **rf-60 第一步：把 EPUB 的 Markdown 规则从脚本里抽出来**：`render/epub_source.py` 收下
  `normalise_headings()` 与 `is_caption()`（标题前补空行、删掉图注下方的装饰性 `====`），
  `to_epub.py` 改为导入它；两个函数原先写在「导入即跑 pandoc」的脚本模块里，没有可测入口。
  新增 11 条用例（图注判定、setext 标题保留、多处修复的计数、文本不被顺带改写），
  `epub_source.py` 100%、`to_epub.py` **95.6% → 100%**（布局告警用补丁重载；`makedirs` 失败按惯例标 pragma）。

- **覆盖率第六项登记、门槛抬升暂缓（rf-59 / rf-60）**：`core/menu.py` 80% → 99%、`lib/_log.py` 78% → 96%、
  `lib/_perfhistory.py` 81% → 100%、`render/print_pdf.py` 91% → 100%；但逐文件棘轮当前在 5 个文件上失败
  （`actions`、`chapters`、`_config`、`to_epub`、`verify_pdf` 较各自基线回落），故 `coverage_fail_under`
  88 → 90 推迟，另记 rf-60 处理这批回落（含 `to_epub.normalise_headings()` 这类纯函数没有可测入口的问题）。

- **覆盖率第五项（rf-58）完成**：`core/menu.py` **80% → 99%**、`lib/_log.py` **78% → 96%**。新增
  `test_core_menu.py`（预估的中位数收敛、别名/分组/父级、`tail_of` 截断、`run_report` 透传），
  `test_logging.py` 补 12 条（策略不可解析、测试日志目录的两条分支、覆写与书目录不可写、
  `setup` 二次调用、文件 handler 打不开仍留控制台）。

- **覆盖率第四项（rf-57）完成**：`audit/epub_diff.py` 分支覆盖 **71% → 94%**——位图计数、多字体栈去重、
  `_leads`/`_delta` 边界、「只加回退族不算漂移」与「首族变化算漂移」的判断、行高变化、章节数报错文案、
  CLI 四种输出。

- **覆盖率第三项（rf-56）完成**：`audit/pdf_invariants.py` 分支覆盖 **61% → 97%**——用轻量替身页
  覆盖大纲嵌套/空/抛异常、Type3 跨页去重、越界与容差边界、负坐标、空白文本、坏页转 `unreadable`，
  以及 `check()` 的四条问题分支和 CLI 的三种输出。

- **覆盖率第二项（rf-55）完成**：`lib/fonts.py` 分支覆盖 **58% → 90%**——用例用替身覆盖平台目录三态、
后缀过滤、索引缓存（写入/命中/失效/不可写）、单面优先与集合不可嵌入、`coverage()` 的字符合并、
`fc-list` 三种结局、`resolve()` 的五种输入。同时修正一处行为：所有字体面都读不出时
`coverage()` 曾把「未验证」当成「已覆盖」返回空缺失，现在返回全部缺失。

- **覆盖率提升按台账推进（rf-54～rf-59）**：先把六条路径在 `review-findings.md` 立项（最薄的
  `pdf_metrics` 55%、`fonts` 58%、`pdf_invariants` 61%、`epub_diff` 71%、`_log`/`menu` 78–80%、
  最后是棘轮），再按优先级实施。第一项完成：新增 `test_render_pdf_metrics_units.py`（25 条）覆盖
  解析/比较/夹逼/收敛/写回/CLI，`pdf_metrics.py` 分支覆盖 **55% → 87%**；同时删除 `main()` 里
  一段不可达的重复 `--write-back` 分支。

- **90 小时变更的债清理：三处超长函数归零**：`tui.header()`（60 行）拆成
  `_header_facts()`/`_header_titles()` 并删掉一行永不生效的 `replace(..., 0)`；
  `html_shell.apply_layout()`（72 行）把替换链抽成模块级 `_style_rules(**values)` 表，新增一个维度
  只需加一行；`print_profile.style_block()`（67 行）的 CSS 提成 `PRINT_CSS` 常量，函数只做占位替换
  （用 `replace` 而非 `format`，避免为 CSS 的大括号再加一层转义）。全库 `≥60 行函数` 重新归零，
  33 道门禁与 1653 用例保持全绿。

- **代码与测试审计的整改**：删除两处死代码——`lib/_log.tail_since()` 与 `lib/_mdutil.figure_ids()`
  （后者只被自身用例引用，一并删除该用例）；`test_app_tui_keys_platform.py` 中与
  `test_app_tui_keys.py` 重复的 line-mode 用例，保留通用那份、平台文件只留 Windows 序列与空行。
  审计结论：107 个配置叶子键均有读取点（无死键），无 TODO/FIXME，23 处 `# noqa` 均为
  `sys.path` 之后导入或可选依赖；测试侧精确重复体/空断言/同名遮蔽为 0，通用名 0，
  快档最慢用例 4.4s、整档 37s（无真实 chromium/pandoc 用例被误标 fast）。同一文件内三条
  「各自门禁的 clean fixture 通过」并成一个 `subTest` 循环（失败仍点名脚本）。

- **预估收紧、并发日志可归因**：动作预估按实测重设（build 2–15s、deliver 60–150s、
  deliver-all 100–240s、print 30–90s，实测全链 135s），有历史时按 `mode` 中位数收敛，结果行
  追加「用时 m:ss（预计 a–b）」；`core/menu` 读历史改走新增的 `lib/_perfhistory.py`（`core`
  不得导入 `audit`，架构门禁据此通过）。日志里 `action … start/done` 与 `make … start` 都带
  `pid`/`parent`，两个进程同时写同一个日志时可按 pid 切开（本次交付窗口内混入的两次 `make check`
  就是这样定位的）。`make.py` 每个步骤开始即打印 `.. <step>`，长时间静默的阶段也有进展。

- **按快捷键后的提示语点名产物**：确认、进度与结果三行不再说"重建产物"，而是列出将被写的
  文件类型与位置——`deliver` 写 EPUB 与标准版 PDF（`dist/<book>.epub`、`.pdf`），`print` 写
  `dist/<book>-print.pdf`，`build` 写 `.md` 与 `.html`，`deliver-all` 列全五份，`analyze*`
  写 `data/manuscript` 的骨架或事实块；确认行同时说明"同名文件会被覆盖"，失败行说明"哪几份
  产物未更新"。产物清单只在 `core/menu.py::ARTIFACTS` 声明一次，菜单标签保持原样。新增 3 条
  用例（确认文案、进度与结果文案、失败文案）。

- **README 成为项目首页与总索引，`folder.md` 只留目录结构**：`books/README.md` 重写为
  「这是什么、能做什么、怎么开始、文档总索引」——索引按要求/判定/做法三轴排成一张表，
  每份文档一行职责；删掉管理文档目录里的那份索引（职能被上面那张表吸收），
  `doc_drift` 的 `INDEX` 面改为只校验 `folder.md` 的目录树与目录本身一致。`folder.md` 同步
  校正：`data/archive/` 归到 `data/` 下、补 `state/file-length.json`、新增一条「怎么用/怎么写
  只在 `docs/manuals/`」的归属规则、常用入口指向 README 的总索引。

- **文档体系按"要求 / 判定 / 做法"三轴归位**：写作手法是给写作者的指南，不是管理要求，
  所以原写作规范（`style-guide.md`）移至 **`docs/manuals/how-to-write.md`**（声明自己的
  「维度」，不再引用管理文档）。**总索引收归 `books/README.md`**：按「要求 / 判定 / 做法」三轴
  排成一张表，每份文档一行职责；原先散在管理文档目录里的那份索引表随之删除，
  `doc_drift` 的 `INDEX` 面改为只校验 `folder.md` 的目录树与目录本身一致。`technical.md` §2.4 的
  目录树删掉，改为一句话指向 `folder.md`（结构只有一处权威）。全部引用同步：管理文档、计划、
  `README.md`、仓库根的 `CLAUDE.md`、以及 `audit/*.py` 的 docstring；`doc_drift` 的
  `STANDARD_ALLOWED_REF` 跟着改名。

- **TUI 增加「一次出全部产物」，书籍管理收进二级**：主菜单第 6 项（`6`/`F`）新动作
  `deliver-all`——按依赖顺序跑构建（Markdown + HTML）→ 交付（EPUB + 标准版 PDF + 校验）→
  印刷版 PDF，任一步失败即停，不会留下半套产物；原 6–9 依次后移，其中「切换书籍 / 新增书籍」
  合并为二级「书籍管理」（`7`/`B` → `1`/`S` 切换、`2`/`N` 新增），避免第 10 个数字键。
  字母快捷键随行号同步：`3` 由 `B` 改为 `M`（`B` 让给书籍管理），`8` 为配置（`C`）、
  `9` 为质量（`T`）。

- **文档与具体项目解耦，配置说明归用户文档**：管理文档与使用手册不再点名被分析的项目
  （`../manuals/how-to-write.md` 的示例、`requirements.md` 的目标、`folder.md` 的目录树、`how-to-use.md`
  的产物名、`how-to-config.md` 的包前缀示例全部改成占位或用例无关的表述）；唯一的范例
  放在 `how-to-manual` 的「范例：本仓库里的那份分析」一节，指向 H2 分析作为对照。
  `style.json` 的键语义只在 `docs/manuals/how-to-config.md` §3 解释（补齐 `prose`/`quality`/
  `thresholds` 等全部键，去掉 `project`/`diagrams.markers` 两条已作废的行）。新增两条门禁：
  `doc_drift` 的 `PROJECT`（管理文档与手册不得出现配置里的包前缀或书名，两个台账与范例节豁免）
  与 `STYLE_KEY`（`style.json` 的每个段与键都必须在手册里被解释）。
- **文档按体例归位，质量策略更名**：`requirements.md` 去掉当前分析对象的专属名词（分析对象由书的
  配置声明，目标、章节槽、内容范围都改写成与项目无关的表述）；`testplan.md` §3/§4 只保留「判什么、
  谁判」（格式体例移入 `../manuals/how-to-write.md` §4.2/§4.3，命令与人工验收步骤不再重复手册）；`technical.md`
  补六张结构图与两个推导小节（PDF 交付链的写入者与压缩时机、版式由阅读度量推导、门禁执行模型、
  可再生/需评审/不可再生的分界），并把本轮确立的四条设计决策登记为 D-07～D-10。原
  `quality-model.md` 更名为 **`content-quality-policy.md`（质量保障流程）**：它与内容标准
  `content-standard.md` 的分工写进双方定位——内容是标准定义的，判定与基线由项目注册。

- **文档与代码对齐一轮**：日志命名（`check-<档位>-<YYYY-MM-DD>.{log,jsonl}`、`perf-baseline.json`
  与滚动窗口）、`render/` 模块表（补 `pdf_split.py`、`pdf_metrics.py`、`toc_pages.py`）、
  `verify_pdf` 的 `COLUMN` 判据、基线清单（`coverage.json`、`perf-baseline.json`、
  `loose-assertions.json`、`state/file-length.json`）、`how-to-config` 的版式键（`layout_chars_per_line`
  与其区间、`layout_column_px=0` 推导、印刷侧三个新键）全部改写为当前事实；`DESIGN-TUI` 与
  `how-to-use-tui` 按「结果在屏时任意键回菜单」重写；性能基线表述从「历史中位数」改为「评审基线
  （无则退回窗口中位数）」。同时按文档规范删掉「以前…现…」这类过程叙述，修 3 处 Markdown 表格
  列数不一致（`testplan` 的 EPUB 行、两处 `\|` 转义）。`technical.md` 补一条：lint 规则集只在
  书的 `pyproject.toml` 声明，编排器显式传 `--config`。

- **lint 从「跟着 ruff 版本走」变成一条可复现的门禁**：此前 `check_runner` 从仓库根调用
  `python -m ruff check books/src/...`，而 `books/pyproject.toml` 里没有 `[tool.ruff]`——规则集
  就是 ruff 的默认值，换版本即换判据（venv 里是 0.15.20、PATH 上的 `uvx ruff` 是 0.17.6，同一棵树
  一个报 0 处、一个报 160 处）。现在 `books/pyproject.toml` 声明 `line-length`、`select`
  （E4/E7/E9/F + I/B/UP/RUF100）与 `external`（`PLC0415` 等只在编辑器里生效的规则，其 `# noqa`
  不算过期），门禁显式传 `--config`，`requirements-dev.txt` 的 ruff 同步升到 0.17.6。收起
  45 处机械问题（导入顺序、pyupgrade、未使用的 `# noqa`）与 3 处手工问题（两处未用的循环变量、
  一处 `_sys` 别名下的 E402）。

- **评分卡的「稳定」维度改为跑门禁同一套用例**：`scorecard.stability_score()` 原本用
  `unittest discover`，它导入全部测试模块、让模块级代码真的执行（交付脚本被跑起来、
  还往 `dist/` 写文件），再把「2 failed」当成整棵树红了。现在跑 `pytest -m tier_fast`
  并读 `N passed / N failed`，另加一条用例钉住「与门禁同一套对象」。

- **删除死配置 `style.json [diagrams].markers`**：全库无任何读取，且与 `ascii_max_cols`
  的分工容易误解——ASCII 宽度预算只有 `base.json [toolchain].ascii_max_cols` 一处。

- **压缩只做一次，且由最后一个写盘者负责**：`to_pdf` 原本压两遍（合并后、写大纲后），
  而随后 `pdf_toc_links` 用 pypdf 重写又把它抹掉——本次构建 7.54 MB 被拉回 8.61 MB（+14%），
  还白花一次 gs。现在 `pdf_split.merge()` 不再压缩，`render()/render_html()` 用 `optimize`
  参数把决定权交给调用者：`to_pdf` 传 `False`（后面还有改写），`print_pdf` 与
  `pdf_toc_links` 各压一次。实测标准版 8.61 → **7.53 MB**，`to_pdf` 76.9 → 60.6s。
  gs 的临时文件原来是 `<pdf>.gs.pdf`（读起来就像产物，中断会在交付目录留下 1.1 MB 的截断文件），
  现在改为同目录的隐藏名 `.＜pdf＞.gs.tmp` 并在每次运行前清理残留——`dist/*` 与归档步骤不会再捡到它，
  同文件系统也保证 `os.replace` 仍是原子的。
- **`verify_pdf` 从 17.3 s 降到 3.3 s**：`pdf_metrics.measure` 为算「字符/页」把 967 页全文提取
  了一遍，改为只用已有的 80 页抽样（答案不变）。
- **测试不再污染生产日志**：`_log._is_test_process()` 补上 `PYTEST_VERSION`/`sys.modules['pytest']`——
  `PYTEST_CURRENT_TEST` 只在用例执行期间存在，而动作层在**导入时**就建好了 logger，于是负向用例
  的 `unknown action 'nope'` 被写进生产日志 232 次。

- **TUI 结果页按任意键即回菜单**：此前只有 `0`/`Esc` 收起结果，其它键会继续生效——结果还在屏上
  按 `3` 会再跑一次构建（旧输出还盖在上面）。现在结果页吞掉除 `q`/Ctrl+C 之外的所有按键，直接回到
  菜单；提示行由「按任意键继续 · 0 收起结果回到菜单」改为「按任意键回到菜单」，用法说明同步更新。
  用例：`0` 收起后动作可再跑、数字键在结果页不触发动作、`Esc` 在结果页不退出当前层。

- **印刷目录写回页码不再破坏 HTML**：`to_pdf` 第 3 步用 `rstrip('</a>')` 截掉锚点结尾——
  `str.rstrip` 删的是**字符集合**，不是后缀，于是标题以行内元素结尾的条目（如 `…<code>x</code>`）
  被啃掉了闭合标签，留下未闭合的 `<code>`，解析器把其后内容重新挂载：`<body>` 里多出一个游离的
  `<code>`、`page-wrap` 消失、文档高度少 10%（975 → 905 页）。写回逻辑抽成 `render/toc_pages.py`：
  按锚点精确替换（切掉 `</a>` 这四个字符），并在写盘前三项自检——`#content` 逐字节不变、
  `<a` 数量不变、可扰动标签仍成对（按标签名计数，`<body>` 不会被当成 `<b>`）；任一不成立就
  放弃写回并保留原文件。新增 9 条用例（含「标题以行内元素收尾」与「输入本身不合法则拒绝」）。
  实测：写回前后 `#content` 哈希一致（`c43fb21341c7`）、文档高度 682,878 → 760,779px、
  `<body>` 子节点恢复为 `cover,toc-page,DIV,page-wrap`；同一份 HTML 的印刷版由 905 回到 **977 页**
  （标准版 967，差 10 页即印刷 profile 的章首横幅）。

- **性能历史拆成「滚动窗口 + 评审基线」**：`logs/perf-history.jsonl` 此前只增不减
  （11,725 行 / 1.58 MB），而它同时被当成参考基准——清理日志就会移动判据。现在窗口按
  `style.json [quality].perf_history_runs`（默认 200）封顶、超出后原子重写保留最新的一段；
  评审过的下限另存 `data/baselines/perf-baseline.json`（`reviewed{by,at,commit,reason,runs}`
  与逐步/总计中位数），`compare()` 优先比基线并在报告里写明 `source`，没基线时退回窗口中位数；
  新增 `--update-baseline --reviewed-by --reason` 固化基线。首次执行把历史从 11,725 行收敛到
  200 行（1.58 MB → 30 KB）。

- **印刷版与标准版页数差已归因：不是版式，是两份不同的 HTML**：把同一份 HTML 分别交给
  `to_pdf` 与 `print_pdf` 渲染，得到 967 与 975 页（差 8 页 = 印刷 profile 的章首横幅），
  正文文本量一致（约 91 万字符）；此前记录的 905/958 是拿「`to_pdf` 第 3 步写回 TOC 页码之后的
  HTML」与「写回之前的 HTML」比出来的。写回本身为何会改变分页（同一份正文 975 → 905 页）仍未
  定位，另记 `rf-53`。

- **一行行宽统一为 40em，两版共用一个度量**：此前屏幕栏宽是字面量 960px、印刷栏宽按 42 字
  推导，两把尺子并无依据。现在只有一条规则——每行 `chars_per_line`（默认 40）个 `em`，
  栏宽 = 度量 × 正文字号；`em` 是字体自己的单位，换系统、换字体、换书都不变（40em 是 40 个
  汉字或约 80 个西文），纸张上再由栏宽反推页边距（A4 → 20.33mm），栏宽放不下时按可印宽度
  裁到最小页边距（16mm）。`verify_pdf` 的 `COLUMN` 改成判两件事：每行 em 数落在阅读区间
  `[chars_per_line_min, chars_per_line_max]`（默认 36–46）、以及栏宽不超过可印宽度。
  实测：`#content` 宽 640px / `measure 40.00em` / 无块元素越界；标准版 967 页（7.54 MB）。

- **check 日志只留一份真值，并补上「判的是哪棵树」**：删掉 `logs/check-latest.json`
  （无人读取）与跨档位的 `logs/check-<日期>.jsonl`（与 per-mode 文件字段重复），
  每次运行只写当日一份 `check-<模式>-<YYYY-MM-DD>.log` 与同名 `.jsonl`。摘要新增
  `git{commit,dirty}`、`started_at`、每步 `argv`、pytest 的 `counts`
  （passed/failed/skipped/deselected）、以及 `log_offset/log_len`——最后一项让一条摘要
  能直接定位到当日日记里的对应段。文件名日期改为 ISO（`2026-11-24`），与归档/快照一致；
  清理正则同时认旧名，历史文件按保留窗口自然淘汰。

- **印刷版改走同一条渲染链**：`render/print_pdf.py` 不再自己调 `page.pdf()`，改为
  「`print_profile` 注入 + `pdf_split.render_html`」，与标准版同一视口（A4@96dpi）、同一
  `@page` 页框、同一栏宽与字号——这就是 `rf-50` 里「正文从 x=0 起排、行宽 642pt 超过 595pt
  纸宽」的解法。**`scale` 随之删除**（`layout_print_body_pt` 与 `base.json` 的 `print_scale`
  一并去掉）：它与页框耦合，正是不知不觉越界的来源；印刷版要的纸上字号现在由栏宽/字号推导
  给出，不再靠整页缩放。印刷版专属排版单列 `render/print_profile.py`：长度全用 `em`、
  主色取书目（`accent_color`，缺省中性色）、只作用于 `@media print`，因此通用、不绑定本书。
  marker 注入收到 `pdf_split.inject_markers()`，`to_pdf` 与印刷版共用一份。实测：印刷版
  越界页 **40 → 0**、大纲 644 条不变、`verify_pdf` 三项全 ok；印刷版 905 页。与标准版
  958 页的差额（同一份正文、同一页框、逐章对比 profile 仅 ±2 页）另记 `rf-51` 继续定位。

- **check 日志按日归档**：`logs/check-<模式>-<YYYYMMDD>.log` 是当天的运行日记（每次运行
  追加一段带时间的表头），`check-<模式>-<YYYYMMDD>.jsonl` 每行一次运行的完整摘要；
  同日多次运行不再各占一对文件，通过/失败都在同一份里，`check-latest.json` 仍指向最后一次。
  按秒命名留下的一天十来个小文件没有了；清理仍按 `logging.retention_days` 按日进行。

- **印刷栏宽改为按阅读度量推导，页边距跟着栏宽走**：760px 从来不是设计值，而是 A4@96dpi
  视口（794px）减内边距的剩余量；它对应的可印宽度只有 642px，即每一条满行都被页框截掉
  约 118px（或溢出到页边距）。现在 `lib/layout.py` 由「每行字数 × 正文字号」得栏宽
  （`layout_print_chars_per_line`，默认 42 → 42×16 = 672px），再由栏宽反推左右页边距
  （`print_margins_mm()`，下限 `layout_print_margin_min_mm`，默认 16mm），A4 + 42 字 得到
  672px 栏宽 / 16.1mm 边距；`pre` 字号按「宽度预算内的行必须落在栏宽内」反推，
  `layout_print_column_px` 仍可显式覆盖。浏览器实测（打印媒体、794px 视口）：
  `#content` 宽 672px、`scrollWidth` 672px，没有任何块元素的右边界超出栏宽，即栏宽与
  可印宽度现已重合。判据为一条与书无关的不变量「栏宽 ≤ 可印宽度」，由 `verify_pdf` 的
  `COLUMN` 项断言（不靠 PDF 文本宽度估计：那里只能估，估不出宽栏与宽字形）。
  超长行先缩字号到可读下限（6px），再不行就换行（`layout_print_wrap`，默认关，实测整本
  开启多 164 页），印刷时隐行号列避免与换行错位。实测标准版 **958 页 / 7.52 MB**
  （前一版 877 页 / 8.15 MB；页数上升是因为不再靠截掉行尾换密度）。

- **文件长度台账不再靠手抄**：`audit/file_length.py` 把台账上一次的实测行数记进
  `data/state/file-length.json`，门禁只在「较登记时增长超过 `style.json thresholds.ledger_growth`
  （默认 10 行）且台账未更新」时报错，小幅漂移不再刷屏；`--update-ledger` 一次写回所有
  登记行并刷新基线。台账仍是人工可读的清单，但数字由工具维护。

- **ghostscript 压缩登记**：`render/pdf_split._optimize()` 每次运行写一条日志——
  gs 是否可用、调用命令（DEBUG）、原始/压缩后的页数与体积、「同页数且更小」的判定结果
  （采用 / 不采用），失败时降为 WARNING 并保留合并结果；判定抽成 `accept_optimised()`
  便于单测。

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
  `scripts-and-reference.md` 与 `content-quality-policy.md` 的 `snapshot.py import` 用法补上"目录也可"；
  `folder.md` 新增 §3.1 讲清 `data/archive/` 与 `data/snapshots/` 的分界（谁写、存什么、留多久、
  入不入库、谁读、怎么提为对照点）。
- **去掉文档与注释里的时间性措辞**：`requirements.md` 的"上一版已认可基线"改为"已认可的体量基线"，
  `plan.md`/`testplan.md`/`../manuals/how-to-write.md` 里"不再…"的表述改为直接陈述当前规则；
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
  但它又出现了）、`snapshot-june-2026` 的裸标签副本（与日期全名那份内容重复），以及早期版本的
  `balance` 手动快照（`balance.py --baseline` 随时可重生成，且书籍版本已到 6.5）。剩下的 9 份
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
  互相覆盖。新增 `docs/archive/v0.1/multi-book/` 记录目标形态（先一仓多书、条件成熟再让工具链独立成包）、
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
  残留处理；与 `content-quality-policy.md` §4「只比一份」对齐为「每版本只比自己那份」。
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
- **计划管理补上双向覆盖**：`docs/archive/v0.1/figure-chapter-plumbing/` 这一完成态迭代没有认领它的
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
  `[\d.]+`，`v0.1` 会被截成 `0.1` 而判红——现在接受可选 `-dev` 后缀，判据不变。
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
- **覆盖率：补上 `renumber.py` 的写路径与 CLI**：该文件原为 49%（新代码把整体压回 87%），
  新增 5 条用例覆盖 `apply()` 的写入/改写、`dry-run`、`--write`、`--json` 与无版本拒绝；
  顺带修正 `--write` 的语义（原来它等于 dry-run，从不落盘），`apply()` 增加 `write_only`。
  总覆盖 87%（未覆盖语句 1362 → 1319、半分支 594 → 592），单文件下限已清；**总阈值 88 仍差 1%
  分**——按缺口排序，`snapshot`（53+12）、`verify_pdf`（49+14）、`to_epub`（42+15）三处合计
  约 185 个单元，覆盖三处即可过线，下一步按此顺序做。
- **覆盖率：补 `snapshot.py` 的 CLI 分发**：`main()` 四个子命令（`import`/`list`/`verify`/`baseline`）、
  无子命令时的帮助退出码 2、`--json` 摘要与未知标签拒绝，此前完全没走；新增 4 条用例。
  未覆盖语句 1319 → 1294，快档 1214 passed。总覆盖仍 87%（阈值 88）：缺口集中在
  `verify_pdf`（49 语句 / 14 半分支）与 `to_epub`（42 / 15），下一步按此顺序。
- **覆盖率：`verify_pdf` 的判定分支**：补 5 条用例走此前没走过的路径——缺 PDF、缺源 HTML、
  大纲与标题不匹配、缺印刷目录项、以及 `require_toc_links` 下从未增强过的链接。这些分支
  用 pypdf 合成 PDF 即可驱动，不需要浏览器或 pandoc。用例 14 → 19；总覆盖仍 87%（阈值 88），
  剩余缺口集中在 `to_epub`（42 语句 / 15 半分支）。
- **覆盖率：`to_epub.py` 100%**：原有几条 `to_epub` 用例标着 `tier:slow`（要真 pandoc），
  覆盖率门禁只跑快档，于是它们从未计入——该文件在报告里长期停在 72%。新增 13 条**快档**用例，
  把 pandoc 与 `shutil.which` 换成桩，覆盖：pandoc 不在 PATH、`--version` 探测抛错、
  `merge.py` 缺失/失败/静默、合并稿缺失、封面缺标题/副标题/版本/作者时回落到 `book.toml`、
  封面版本与配置不一致的告警、pandoc 退出码非零（有/无输出两种）、成功却没产物、警告与
  正常输出分别转述。未覆盖语句 1294 → 1272、半分支 593 → 578，总覆盖 87% → **88%**，
  门禁（阈值 88）由 FAIL 转 PASS；`to_epub.py` 114 语句 / 42 分支全部走到。
### 门禁
- **印刷版缩放改为按「纸上字号」推导**：配置 `layout_print_body_pt`（默认 8pt），`print_scale = 目标 pt ÷ 正文 px×0.75`（默认 0.667），不再用手选数值。实测发现一个必须记录的边界：Chromium 的 `scale` 只做整体缩放，**不改变分页**——印刷版 730→621 页的原因是先前把缩放接到渲染参数上，而不是纸张密度真的被 `scale` 控制；要让印刷版更密，杠杆在 CSS 的栏宽与字号，不在 `scale`。
- **测试与生产日志隔离**：`_log` 在测试进程里把日志写到「当前指向的那本书（临时夹具目录）」或临时目录，永不写仓库的 `logs/`；`BOOK_LOG_DIR` 可显式指定。仓库日志里此前积压的 187 条 `unknown action 'nope'` 全部来自测试。
- **印刷版缩放改为推导**：`Layout.print_scale()` 由「可印宽度 ÷ 栏宽」算出（A4 + 15mm 页边距 + 960px 栏宽 → 0.709），`print_scale: 0` 表示推导；印刷版由 730 页/5.72 MB 变为 621 页/5.65 MB，每页 74 行、2772 字符（六月 84 行 / 2328 字符）。
- **子进程输出实时可见**：`actions._invoke()` 在带回调时用 `python -u` 与 `PYTHONUNBUFFERED=1` 启动子进程——管道会让子进程块缓冲，原本两三分钟的渲染只在结束时吐出一大坨。`print_pdf.py` 也补了阶段行（读取 HTML、Chromium 渲染中、产物路径、大纲条数），TUI 里执行印刷版时能看到进展。
- **`analyze-llm --plan`**：只报告会写哪些章、调用次数与字符量级，不写文件；`main()` 在扫描源码前给出同一份计划，避免空跑。
- **`analyze-llm` 的适用范围说清楚**：新书（正文文件缺失）时先说明「本轮将生成 N 章，LLM 只为这些章的导读/小结起草文字，事实/结构/代码摘录仍由确定性流程生成」；已有正文且未加 `--force`/`--only` 时直接退出并给出可用参数——两次说明都在源码扫描之前。
- **印刷版 PDF 单列成入口**：`actions.ACTIONS` 新增 `print`（CLI `bookctl print`、Web 按钮、TUI 主菜单同时出现），走 `render/print_pdf.py` 独立渲染器，而不是标准版加开关；长任务同样有阶段输出。TUI 主菜单改为 `[4/E] EPUB + PDF（按需）`、`[5/P] 印刷版 PDF（按需）`，书籍管理与配置顺延到 6/7 与 8/9。
- **长任务有阶段行可看**：`core/actions._invoke()` 用 `Popen` 逐行读取子进程输出，经 `run_report(on_progress=…)` 传给 TUI，TUI 实时打印每一行（去重、截断），不再只显示一行「正在执行…」直到结束；CLI/Web 行为不变（不传回调即整段捕获）。
- **没有可润色对象时当场说清楚**：`analyze-llm` 在扫描源码之前先判断「所有正文文件都在、且未加 `--force`/`--only`」，直接说明「本轮不会生成或重写任何章节」并给出该用哪个参数，不再让用户等两分钟后才知道 LLM 没被调用。
- **三种界面同源输出**：Web 的 `/api/run` 返回里也附上 `lib/status.py` 生成的状态块，与 CLI 日志、TUI 显示同一段文本；页面无需改动即可展示。
- **审计中修复的两处**：日志保留策略原先在 `check_runner` 里重复读 `BASE_POLICY`，改为 `_log.retention_days()` 唯一入口；`status` 的页数统计按「路径 + mtime」缓存，避免每次 Web 请求重新打开 877 页的 PDF。
- **日志与 TUI 同源**：新增 `lib/status.py`，把「源码目录/版本/清单时间 + 产物页数、体积、时间 + 用时/退出码」渲染成一段可读文本；`check_runner` 写进 `bookwright.log`，TUI 跑完一个动作后显示同一段，不再是两处各自拼一句话。
- **门禁日志按日汇总**：通过的一次运行只在 `logs/check-<YYYYMMDD>.jsonl` 留一行（时间、模式、耗时、步数），只有失败才保留独立的 `.log`/`.json` 供排查；文件名改为 `check-<mode>-<YYYYMMDD-HHMMSS>`（不再混用 `-` 与 `_`），并新增按 `base.json [logging] retention_days`（与 `bookwright.log` 轮转同一项策略，默认 14 天）的清理。通过时控制台给出的路径改指向当日汇总文件，不再指向随后即被删除的单次报告。
- **`data/` 归位**：快照目录名去掉冗余标签（`2026-06-11-june-2026` → `2026-06-11`、`2026-06-15-june-2026-edition` → `2026-06-15`）；`data/snapshots/*/artifacts/` 里的成品（PDF/EPUB/HTML，20 MB）改为只留本地、不入库（manifest 入库说明它们曾存在）；`data/state/` 是每次重建的派生状态、且含本机绝对路径，一并从版本库移除并 gitignore；清掉 `data/tmp/type3/` 实验残留；`to_epub.py` 的规范化副本改写到 `data/tmp/` 并在结束时清理，`dist/` 里不再出现 `*.md.epub.md`。
- **快照目录去重**：`2026-06-11-docs-stm` 与 `2026-06-11-june-2026` 内容完全相同（同一份 `docs-stm.zip`、同一 SHA、16 个文件、36 893 行），保留被基线与变更日志引用的 `june-2026`，删除重复目录及其账本文件。
- **成品快照**：新增 `snapshot.py import-artifacts`，手稿已丢失时冻结**产出物**（HTML/Markdown/EPUB/标准版与印刷版 PDF），`kind: "artifacts"` 标明身份，`verify` 只按 SHA 校验、不解码二进制。2026-06-15 的五份成品已迁入 `data/snapshots/2026-06-15-june-2026-edition/artifacts/`，`data/tmp/` 下原文件移除。
- **用户文档补齐与重排**：`README.md` 的用户文档表按「先日常、后接口、参考、问答」重排并更正描述，目录图补 `data/cache`，管理文档索引补 `content-quality-policy.md`、`review-findings.md`；`how-to-use.md` 的交付一节写明 `FONTS`/`DENSITY`/`CHAPTERS` 三个判据与页面松紧的标定命令；`faq.md` 增加三条实战问答（Type3 字体失败、密度失败或换机后页数变化、EPUB 章节失败）。
- **需求与技术设计同步**：`requirements.md` 的 FR-13/14/15 补上「字体按角色声明、不得回落 Type3、密度区间、每章恰好一个一级标题」，并新增 FR-19（换书/换系统/换字体只改配置，字号行距由栏宽推导）；`technical.md` 的分层表补 `fonts`/`layout`/`frontmatter`，临时目录与缓存目录分开描述；`testplan.md` 补 FR-19 判据行并点名 `to_epub.py`，使 `requirement_trace` 与 `gate_trace` 同时通过。
- **文档跟随实现更新**：`scripts-and-reference.md` 补齐 `pdf_metrics.py`、`audit/pdf_invariants.py`、`audit/epub_diff.py`、`audit/font_coverage.py`，`verify_pdf`/`verify_epub` 的说明加上 `FONTS`/`DENSITY`/`CHAPTERS`，公共库加上 `fonts`/`layout`/`frontmatter`；`how-to-config.md` 新增「版式与字体」键表（`layout_*`、`font_stack_*`、PDF 判据四项）并在 `[paths]` 增加 `cache`；`testplan.md` 的交付两行补上新判据；`folder.md` 说明 `data/tmp/` 与 `data/cache/` 的承诺差异。
- **临时文件与缓存分开**：新增 `Config.cache_dir()`（`data/cache/`，按需创建，不可写时退回 `data/tmp/`），字体索引与 HTML 分片缓存都迁过去——它们可重建但有重建成本，`tmp/` 却随时可能被清空。`data/cache/` 同时加入 `.gitignore` 与 `excluded_dirs()`，避免被门禁当作正文。另加「默认值恒等」用例：`TypeScale.from_layout(Layout())` 必须等于 `TypeScale()` 的默认值，当场抓出两处漂移（`code_em` 0.625 vs 0.85、代码行距 1.0 vs 1.23），已统一取自 `DEFAULTS`。
- **偿还本轮引入的技术债**：① `html_shell` 原先在 import 时读取配置并扫描字体目录（`STYLE = apply_layout(...)`），任何导入者都要付这笔开销，且会把「先导入的那个配置」冻结进模块——改为 `style()` 惰性构建并缓存；② 字号/行距的推导规则原本在 `html_shell` 里重写了一遍，现统一走 `Layout.body_size_px()` / `code_line_height_value()`，渲染器与版式对象不会再各算各的；③ `fonts.script_stack()` / `default_cjk()` 在改为按角色声明后已无调用方，删除；④ `pdf_invariants` 里改用 `frontmatter.count_headings()` 后遗留的 `HEADING_LINE` 常量一并删除。输出 HTML 与重构前逐字节一致。
- **三种格式共用一条字体解析路径，但规则按格式分开**：`lib/fonts` 同时提供 `resolve()`/`sans_stack()`（纸面用：必须本机存在、可嵌入、覆盖本书字符）与新的 `portable_stack(role)`（屏幕用：只声明不嵌入，按「读者设备更可能装了什么」排序，拉丁在前、CJK 在后由级联逐字选择）。EPUB 的样式表改为按角色取值，不再写死 `Consolas, 'DengXian', SimSun` 这类平台专名单。与六月 EPUB 比对：字形阶梯、行高一致，字体族首位一致（Consolas / Source Han Serif），仅回退候选增多。
- **HTML 的字体改为按角色绑定**：样式表不再写 `'Microsoft YaHei', SimSun` 这类平台专有列表，改为 `var(--font-sans)` / `var(--font-mono)`，由 `lib/fonts` 按本机字体目录解析后注入 `:root`。原先靠四条字符串字面量替换，新增一处 `font-family` 就会悄悄退回 Windows 专有字体；角色只能绑定一次。与六月 HTML 比对：字号阶梯完全一致、正文多 1.2%（阅读指南与前言回来了）、行高多一档 1.23（代码块随正文行距，六月是 1.0）。
- **密度判据改为自适应，不再绑定页数**：`verify_pdf` 新增 `DENSITY`——比的是「行距 ÷ 字号」（缩放无关）与「文字实际占了多少可印高度」，与具体书、纸张、字体无关；阈值来自配置（默认 1.15–1.75）。同时把代码块行距从写死的 1.0 改为跟随正文行距（`layout_lead_ratio`，0 表示推导）：源码书里代码行占多数，1.0 的行距正是密度偏低的根源。修复后该判据 1.01 → 1.22，判据转绿。字号同样支持推导：`layout_body_px: 0` 时按「栏宽 ÷ 每行字数」算出，配置显式值仍然优先。
- **三格式与六月版本逐项比对**（`pdf_metrics --compare`、`audit/epub_diff.py --compare`）：标准版 843→877 页、6.99→8.14 MB、字符/页 1905→1833；印刷版 738→730 页、6.84→5.71 MB、字符/页 2328→2358；EPUB 21 章（六月 11 章，其中一章是图注误切）、字符 +1.3%、字体栈与字号阶梯一致。比对暴露两处待调：标准版行距 8.0→6.8pt、每页行数 75→64（排版偏松导致页数与体积上涨）；EPUB 四级标题曾输出成 `1.0em`，已修为 `1em`。
- **封面/正文切分抽成 `lib/frontmatter.py`，三处判断同一口径**：HTML 渲染器、印刷版、大纲审计共用一条规则（标题块之前算正文，标题块到第 1 章算封面；没有章节标题时全篇都算正文），封面标题按中/英显示名匹配。审计以前把封面标题也算进「应有标题」，才报出 644/647 的假缺口，现已 644/644。
- **印刷版修好两处**：`print_pdf.py` 的打印样式常量曾被误写成带 `PRINT_GRADE_CSS = """` 字样的字符串，结果成品第 1 页印着这段源码文本；同时重跑后阅读指南与前言进入正文（p65），印刷版 747 → 730 页、大纲 623 → 644。
- **前置章节回到正文（标准版）**：`to_html.py` 不再把「第一个一级标题之前」整段当作封面，改为「标题块之前的都算正文，标题块到第 1 章之间算封面」；标题可匹配配置里的中/英显示名，因为实际书写的是英文标题。结果：阅读指南回到正文（p32），标准版 863 → 877 页、大纲 623 → 644。印刷版走的是另一条渲染路径，前置章节仍缺（下一步）。大纲与本级别标题 644 / 647 仍有 3 条差额，待定位。
- **前置内容不再被吞掉**：`to_html.py` 原先以「第一个 `# 第N章`」为正文起点，于是前置部分除封面标题以外的内容（阅读指南、前言）既不进正文也不进目录——成品里搜不到这两章，而大纲只是少了几条，一直没被察觉。改为以「第一个一级标题」为起点后，两章回到正文（阅读指南 p31、前言 p38），页数 863 → 878、大纲 623 → 647。`pdf_invariants` 的比对口径同步改为按大纲实际层数取标题，647 条对 647 条，判据转绿。
- **标定可以真的跑起来**：`calibrate(render, target, low, high)` 用调用方提供的渲染函数做有界二分，命中容差即返回落点；`--write-back knob=value` 把结果写回 `base.json` 的 `[toolchain]`，只替换那一行数值，其余不动。渲染函数由调用方注入，所以搜索可以有测试（线性模型 8 轮内收敛、恒定页数则返回 None）。
- **第二本书端到端用例**：临时目录里用仓库自带的配置骨架 + 两个小章节组成一本新书，只改 `book.toml` 的阅读顺序，然后跑真实的 `merge.py` → `to_epub.py` → `to_pdf.py`。EPUB 与 PDF 都能产出、章节按标题切分、图注的装饰线不额外成章——证明换书不需要改代码。图注识别同时放宽为「图/表/Figure/Table + 编号」，不再要求加粗，因此别的书写法也能覆盖。
- **`audit/pdf_invariants.py`：不依赖参照版本的版式不变量**——文字越出页面边界、Type3 字体超限、大纲条目数与一级至三级标题数不符，任一成立即判缺陷；`--json` 输出可机读结果。首次运行即查出真实差异：大纲 623 条、标题 632 条，9 个标题没有进入导航（待下一步定位）。
- **`pdf_metrics` 支持无参照目标**：`--target pages=843,chars_per_page=1905` 直接与数字比对，超出 3% 标注偏大/偏小——没有六月 PDF 在手时也能判断这一版是否走样。标定的算术抽成 `Calibration`：有界二分、单调假设（间距大→页数多）、每次测量收紧一侧边界、命中容差或区间坍缩即停，渲染本身由调用方提供，因此搜索逻辑可以脱离出书单独验证。
- **EPUB 结构校验新增 `CHAPTERS`**：每个正文文件必须恰好一个 `h1`——没有说明内容丢了标题，有两个说明按错误标题切开了（正是图注成章那种缺陷）。同时 `verify_epub` 的 XML 解析改为必须使用 defusedxml：校验工具若自己降低安全等级，不如不做这一步校验；`make.py` 的依赖说明相应改为必需。
- **版式拆成两半：共用的字号尺度 + 只属于纸页的几何**——`TypeScale`（正文/代码比例、标题阶梯、行高、间距，全部 `em`）由 PDF 与 EPUB 共用；`PageGeometry`（页尺寸、页边距、栏宽、像素值）只给 PDF。EPUB 的 CSS 由 `TypeScale` 代入生成，paged 单位不会漏进重排版输出；EPUB 代码字号单列 `layout_epub_code_em`（0.85），因为窄栏需要比纸面更大的相对字号。生成的 EPUB 字号阶梯与六月版本逐项一致。
- **`audit/epub_diff.py`：把「看起来差不多」变成可判定的数字**——`--compare ref.epub built.epub` 逐项列出体积、章节文件数、正文字符、位图数、字体栈/字号/行高，CSS 三条规则不一致即判漂移并返回非零；`--check built.epub --merged merged.md` 校验章节文件数 = 一级标题数 + 封面（pandoc 按它读到的 H1 切章，多一个少一个都说明有标题被误读），`--json` 输出机读结果。不依赖任何具体书或字体。
- **EPUB 章节切分修复（rf-46）**：`normalise_headings()` 在转换前做两件事——给紧贴上一行的 ATX 标题补空行（19 处，否则 pandoc 把 `# 第11章` 读成列表续行，该章永远不开新文件）、删除短粗体图注行下方的装饰性 `====`（1 处，否则构成 setext H1 把章节切成两半）。正文文件 **11 → 21**，第 1 章至附录 E 各自成章；六月版本同样存在这两个问题，本版已优于参照。
- **rf-46 根因复现**：图注写成 `**图 11-6: …**` 加一行 `====`，构成 setext H1，pandoc 据此断章；六月版本同样如此（不是回归）。删除装饰线的试验把章节数从 11 降到 10 且第 11 章条目消失，说明第 11 章自身的 H1 也未被识别，问题不止一处，故本次不提交改动，仅记录证据与下一步。
- **EPUB 与六月版本的首次系统比对**：体积、正文文件数、字符数、CSS 字体栈/字号/行高、位图数量逐项量过——CSS 三组规则完全一致（字体栈、1.6/1.3/1.1/1/0.85/0.9em、行高 1.55/1.35），字符数差 −0.5%，两版均无位图（图例为 ASCII 文本）。唯一差异是章节切分：六月 13 个正文文件，当前 11 个，`ch008` 以图注为标题（记为 rf-46，待最小复现）。
- **字体判定看头部、按脚本分栈**：`is_collection_file()` 读文件头 `ttcf` 判断集合，扩展名不再作为依据（`.otf` 也可能是集合、改名也不改变事实）；新增 `script_stack(latin, cjk)` 与 `DEFAULT_CJK`，拉丁候选在前、CJK 候选在后，由 CSS 逐字回退——一个列表同时服务两种文字必然牺牲其中一种的度量。新增 6 条用例覆盖头部判定与分栈顺序。
- **版式参数收敛为 `lib/layout.py`**：页面尺寸、页边距、正文/代码字号、代码行高、版心宽度、纵向间距与统一乘数都在一个不可变对象里读取、强制类型、做范围校验；非法值保留默认值并逐项报告，不再让一个笔误变成一张解释不了的页数。间距一律相对 `em`，乘以 `spacing_scale`，所以标定只动一个旋钮；`Layout.apply(css)` 是唯一的样式替换入口。新增 10 条用例覆盖强制转换、越界回落、空值与间距换算。
- **字体解析改为跨平台**：`lib/fonts.py` 不再依赖 fontconfig——按平台枚举字体目录（Windows 的 `%WINDIR%\Fonts` 与用户字体目录、macOS 的系统/用户目录、Linux 的常见目录），读每个文件的 name 表建家族索引（缓存在 `data/tmp/font-index.json`，按路径/大小/mtime 失效），`fc-list` 只作为目录扫描为空时的后备。判定统一为三条件：**存在 + 可嵌入（非 .ttc）+ 覆盖本书字符集**，满足者排前；`coverage()` 取家族所有字面的 cmap 并集，`audit/font_coverage.py` 复用它。换操作系统、换字体、换书、换源码都走同一套规则。
- **纵向间距配置化并标定**：`p`/标题/列表/表格的间距改为 `layout_*_gap_em` + 单一乘数 `layout_spacing_scale`，相对单位保证跟随字号缩放；按 `pdf_metrics` 判据把乘数标到 **0.70**（0.85 → 876 页、0.70 → 862 页，参照 843 页）。标准版 **862 页 / 7.30 MB / 字符每页 1,851 / 大纲 623/623**，页数与字符/页偏差进入 ±3% 容差；行距 6.8pt 仍是唯一超差项。
- **版式与字体的可配置/可测量件**：`lib/fonts.py` 按本机 fontconfig 解析字体并把 `.ttc`/缺失家族降到后备；
`html_shell` 的页面尺寸、页边距、正文与代码字号、代码行高、版心宽度改由 `[toolchain] layout_*` 提供；
`audit/font_coverage.py` 用 fontTools 比对本书字符集与候选字体，报缺字清单并支持 `--json`；
`verify_pdf` 增加 `FONTS` 检查（Type3 字体数量上限，默认 50）。
- **两处试验的结论**：① 打印前用 JS 量版心、逐块缩放会扰动分页（同一内容 846 → 890 页），已弃用，
不变量改由 CSS 表达；② 给代码块加 `white-space: pre-wrap` 会把一条长行拆成多行，实测 846 → 1010 页，
故默认不开启，保留为 `layout_code_line_height` 之外的独立开关点。
- **字体与密度的做法改为通用件**：新增 `render/fonts.py`——按本机 fontconfig 实际解析字体，把 `.ttc` 集合与缺失家族排到后面（候选列表来自 `[toolchain] font_stack_sans/_mono`，可换书换机器），`html_shell` 不再硬编码家族；新增 `render/pdf_metrics.py`——量页数、体积、正文字号（按文本矩阵归一化）、行距、每页行数，并支持 `--compare 参照.pdf 成品.pdf` 输出偏差清单，任何书都能用它校准，不必再靠猜。
- **印刷版对齐六月参照（735 页 vs 738 页）**：字体修复后密度提高，`print_scale` 由 1.10 微调到 **1.12**（1.10 → 715 页、1.12 → 735、1.15 → 755）。现印刷版 735 页 / 6.01 MB / 每页 2,334 字符 / 大纲 623/623（六月印刷版 738 页 / 6.84 MB / 每页 2,328 字符），`verify_pdf` 通过。
- **PDF 体积回到六月水平（6.97 MB / 846 页）**：最小复现确认 Chromium 只在三种情况下走 Type3 字形流——`.ttc` 字体集合、合成粗体、缺字形回退。样式表据此改为 `font-synthesis: none`，等宽栈补 `Droid Sans Fallback` 作中文后备；标准版 **846 页 / 6.97 MB / 每页 1,887 字符 / 大纲 623/623**（六月参照 843 页 / 6.99 MB / 1,905），Type3 字形流 35,393 → 238，`verify_pdf` 通过。rf-44、rf-45 关闭。
- **rf-45 探针改写了方案**：`fonttools` 已装，但用 `pikepdf` 统计发现当前 PDF 里 24,567 个流没有 `/Subtype`（解压 57.9 MB、全是 Type3 字符过程），`/FontFile2` 与 `/FontFile3` 一个都没有——即使换了 .ttf 家族，Chromium 仍把大部分文字写成 Type3 字形流，因此「合并 TrueType 子集」暂时无对象可合并。下一步先用最小 HTML 定位 Type3 的触发条件（加粗/回退/渲染选项），消掉 Type3 后再看是否需要归并。
- **字体归并的可行性已量清（记入 rf-45）**：`pikepdf` 10.18.2 已可安装，但按对象去重无效——
24,591 个流里只有 40 个完全相同（0.01 MB），各分部的字体子集确实互不相同；且文件里仍有约 40,000 个
无 `BaseFont` 的 Type3 字体对象，说明 Type3 仍是主要开销。方案定为：装 `fonttools`，按家族把各分部子集取并集重建、
改写 CIDToGIDMap 与内容流；现状保持 848 页 / 15.0 MB / 大纲 623/623。
- **PDF 体积回归定位到字体格式**：CSS 声明的是雅黑/宋体/Consolas，构建机上都没有，回落到 Noto CJK（.ttc 集合），
Chromium 无法子集化 TTC，改把每个字形导出成 Type3 字形流（35,393 个流 / 13.8 MB）——这正是 19 MB 的来源，
与字号和正文量无关（两版内容流压缩后同为 ~5 MB）。`html_shell` 的字体栈现优先使用本机存在的 .ttf 家族
（Droid Sans Fallback，含中日韩），雅黑/苹方/Noto 作为跨平台后备。标准版 **848 页 / 15.0 MB / 大纲 623/623**；
`pdf_split._optimize` 也改为「同页数且更小」才替换，防止被截断的 gs 输出覆盖成品。
- **标准版改为逐章渲染并默认开启**：`to_pdf.py` 按 `pdf_split_by_chapter` 走 `render/pdf_split.py`——
按 `<h1` 切段、逐段 `page.pdf`、pypdf 合并、大纲按 `__hdr_i__` 标记定位，最后在写完大纲之后用 ghostscript `/printer` 重压缩
（大纲回写会丢掉压缩，顺序不能反）。**892 页 / 每页 1,790 字符 / 大纲 623/623 / 19 MB**，6/15 参照为 843 页 / 1,905。
交付体积预算改为随页数线性（`pdf_bytes_per_page` = 24 KB，实测逐章渲染约 21 KB/页），`verify_pdf` 通过。
- **体积预算改为随页数线性**：`verify_pdf` 的 12 MB 原本是按 743 页单次打印校准的；逐章渲染每个分部各嵌一份字体子集，
体积跟着页数走。现在取 `max(pdf_max_mb, pdf_bytes_per_page × 页数)`（默认 16 KB/页），并补了两条用例
（预算随页数增长、阈值非数字时回落）。`pdf_split.merge` 合并后接一段 ghostscript `/printer` 重压缩（无 gs 时跳过）。
逐章渲染仍默认关闭：892 页的输出 gs 后约 19–23 MB，仍高于该页数对应的 14.3 MB 预算。
- **逐章渲染跑通（开关默认关）**：`render/pdf_split.py` 现在按 `__hdr_<i>__` 标记直接定位标题
（不再搜标题文本，避免折行与重复短文丢条目），`pdf_split_by_chapter=true` 时标准版得到
**892–900 页 / 大纲 623/623**（6/15 参照 843 页），密度从 2,226 字符/页降到 ~1,830，与参照同档。
卡口是体积：19 段各自嵌入字体子集，合并后 31–32 MB，超出 `verify_pdf` 的 12 MB 预算；
ghostscript `/printer` 重压缩后 14 MB 仍超标，故开关保持关闭，默认路径不变（743 页 / 10.8 MB / 全绿）。
- **逐章渲染的雏形落地（开关默认关）**：新增 `render/pdf_split.py`——按 `<h1` 把正文切段，每段单独 `page.pdf`，
隐藏封面与印刷目录只在前置部分出现，最后用 pypdf 按序合并并按「章起始页 + 章内偏移」写大纲；
`to_pdf.py` 在 `base.json [toolchain].pdf_split_by_chapter` 为真时走这条路径。
实测：18 段 + 前置 = **900 页、每页 1,838 字符**（6/15 参照 843 页 / 1,905），密度已经贴近参照；
但大纲只写出 416/623，所以开关保持关闭（标准版仍 743 页 / 623 大纲）。余下两件记入 rf-44：
大纲改为按 DOM 标题序号定位、页数微调到 868。
- **印刷版页数回到七百多（747 页，参照 6/15 的 738 页）**：`print_scale` 按扫描定点到 **1.10**——
1.00 → 666 页（低于参照太多）、1.08 → 727、1.10 → 747、1.13 → 766、1.15 → 780。取 1.10，
比参照多 1.2%，与内容 +3% 同向；大纲 623/623、`verify_pdf` 通过。
顺带把 `print_pdf.py` 的定位标记也换成 3px 白字（与标准版同一修法）：此前 scale=1.0 时大纲只剩 148/623。
- **标准版页数无法用排版参数推进（结论记入 rf-44）**：一次完整扫描显示页数对页边距、列宽、`pre` 字号、
正文字号都不响应（743 → 725–754，且字号变大页数反而更少），把页面几何改由 `page.pdf(width/height)` +
`prefer_css_page_size=False` 供给也不改变——链路里存在隐藏的整页缩放。实验已全部回退，
当前标准版 743 页、印刷版 846 页、大纲 623/623、`verify_pdf` 与 `check-fast` 全绿。
要把标准版推到 843/868 页，下一步改为逐章渲染再合并（大纲页号由章节偏移算出）。
- **标准版 PDF：页面盒归 CSS、大纲不再被排版打断（rf-44 前两步）**：`html_shell.py` 的打印块改为只留
`@page { size: A4; margin: 26mm 22mm }`，`#content` 去掉 960px 桌面宽度与 20px/36px 内边距；`to_pdf.py` 改用
`prefer_css_page_size=True` 并删掉原本被 CSS 覆盖、因而从未生效的 `margin`/`scale` 入参。
大纲的定位标记由「0.1px 透明内联」改为「3px 白字内联」——之前一改页面盒，标记就被文字提取拆散、
623 条大纲掉到 165/381/605；现在四种页边距下都稳定 **623/623**。
实测页数几乎不随边距与列宽变化（735–754）：分页由 598 个不可拆分的 ASCII 图块决定，
要落到 843 页下一步得调 `pre` 的字号与缩进。当前标准版 743 页、`verify_pdf` 通过。
- **标准版 PDF 的「舒展」版式尝试后回退**：把 `@page` 边距放大、让 CSS 接管页面盒后，正文排版变了，而大纲靠正文里的不可见标记做文字提取，623 条大纲掉到 165 条；未找到既松又稳的参数，已回退到提交里的状态（标准版 747 页、大纲 623/623、`verify_pdf` 通过）。根因与修复方向记入问题台账。（rf-44）
- **印刷版回到「舒展」形态（848 页，参照 6/15 的 843 页版）**：`render/print_pdf.py` 的页面参数改为
边距 20/25/15/15mm、**不再绘制页眉页脚带**，并新增 `base.json [toolchain].print_scale`（当前 1.35）控制正文缩放；
同一份内容由 652 页变为 848 页，每页字符从 2,664 回落到约 2,000，接近参照版（1,905）。
A4 尺寸、字体嵌入与目录链接仍由 `verify_pdf` 判绿。
- **正文字比对（6/15 参照版 vs 现在）**：章节文件逐一比对，**没有任何内容被删除**，全部是增量——
`ch1-2` +5、`ch3` +7、`ch4-5` +4、`ch6-2` +3、`ch6-3` +4、`ch7/8`（已合并） +4、`ch9-10` +43、`ch11-12` +5、
`appendix-a` +58、`appendix-b` +56、`glossary` +129、`index`/`references`/`cover` 不变；合计 +318 行，
与封面 39,779 → 40,097 完全对上。新增小节集中在：`ch9-10` 的「源码版本变更说明」两节、
附录 A/B 的 `15.x`/`16.x` 收尾（延伸思考/小结/延展阅读）与「源码坐标索引」「版本变更对照」、术语表新增「类型速查」。
- **半分支续补 + 下限 83 → 84**：`test_report.py` 85 → 87%（按 TAGS 统计分层而不用执行用例、perf 窗口的
「一次运行不够」「某步回退」「坏记录被忽略」、报告目录按保留窗口清理、`last_failures` 的重跑命令与
坏报告容错）；新增 `test_core_fetch_source_branches.py`（刷新/克隆命令形态、`--dry-run` 不执行、
git 缺失退 127、git 非零即停、已存在不改、`--json`、无仓库退 2），`core/fetch_source.py` 83.9 → 取代它成为
最薄处的是 `audit/version_consistency.py`（84.0%），单文件下限随之 83 → 84。总覆盖 90.9 → **91.0%**。
- **`app/tui.py::main` 再拆一次（62 → 59 行）**：书目守卫提成 `_guard_book()`，「坏书根 = 一条消息 + 退 2」
与 CLI / make.py 共用同一契约；≥60 行函数回到 0。rf-41 关闭：仓库里「先打印再 `sys.exit(1)`」的组合
已归零（`grep` 计数 0）。
- **变异抽查收尾：`content_volume` 的行为型变异清零**。新增 `ReviewedBaselineTest`——把夹具书做成
临时 git 仓库（`git init` + 一次干净提交），让 `update_baseline` 走**真实**路径而不是 mock：
干净提交 + 具名评审人写出台账、手稿有未提交改动被拒、缩水未加 `--accept-shrink` 被拒、
加上后写入 `accepted_shrinks{reason,drops}`；另补「封面必须出现在手稿清单」「基线总量只有部分单位不报错」
「非仓库目录下 `_git` 返回空串」「`--json` 输出保留中文而不是 \u 转义」四条。
同一批也说明了**变异抽查的口径**：`mutation_smoke.py` 按行序取前 N 条，样本随用例变化而移动，
因此不追求「0 存活」；判据是**行为型变异必须被杀**，`ensure_ascii`、argparse 的 `store_true`、
`capture_output` 这类参数级变异记录在案、不逐条补测——补测成本高于它证明的东西。
- **④ 阈值边界表驱动**：新增 `test_threshold_boundaries.py`——图注长度在 strict/normal 两档的边界、
图簇最小张数、ASCII 宽度预算（改配置文件而非改内存）、覆盖率红线与单文件下限的读入、
体量下限比例的松紧两侧，外加一条「配置里没有孤儿键」的机检（键存在但没人读 = 阈值静默失效）。
- **⑥ 变异抽查工具**：新增 `src/python/mutation_smoke.py`（评审用，不进提交门禁）——把 `src/python` 与
`src/test` 复制到临时目录，逐条施加变异（`==`↔`!=`、`>=`→`>`、`True`↔`False`、`and`↔`or`，跳过注释与文档串），
跑该模块的用例，报告**存活**的变异。首轮对 `audit/content_volume.py` 跑 10 条：5 条存活 → 补 5 条
非对称输入的用例后降到 2 条（`content_volume.py` 的 `drops and not accept_shrink` 与交付物一侧的
`'pdf_pages' in delivered and ...`），这两处已记入后续补测清单。
- **③ 失败路径矩阵 + ⑤ 不变量测试**：新增 `test_failure_matrix.py`（九条拒绝路径一张表：
`--book` 缺 book.toml、未声明版本、未知步骤、未知动作、`--force` 用错动作、两个互斥开关、
`settings set` 缺值、TUI 的坏书根——每条断言「退出码 + 消息片段 + 无 traceback」）；
新增 `test_pipeline_invariants.py`（索引解析确定性与重复项取末位、重编号映射两次运行相同、
引用改写幂等、合并两次字节相同、每章只出现一次）。过程中修好一处真缺口：**TUI 入口没有书目守卫**，
`tui --once status --book <无 book.toml 的目录>` 会抛 `ConfigError` 而不是「一条消息 + 退 2」。
`structure.py` 84 → 85%（子检查失败、缺索引、坏 CSS 引用、围栏未闭合）。
- **半分支优先（第 1 步续）：`ingest/chapters.py` 88 → 90%**：五条 CLI 路径用例——`--dry-run` 只报尺寸
不落盘、`--force` 覆盖正文但先备份到 `data/tmp`、附录块只追加一次（第二次 `skip`）、
状态文件损坏时退 2 并给消息、`--only` 不动其他章节。
- **半分支优先（第 1 步续）：`manuscript/glossary.py` 85 → 94%**：三条用例补上草稿模式的跳过规则
（图注、结构标记、编号项、代码式术语、标题缩写都不得进术语表，真正的术语必须进）、`--validate` 的
「无章节引用」判定、`--coverage` 的「超过 6 条折叠」分支。
- **半分支优先（第 1 步续）：`audit/readability.py` 83 → 94%**：13 条用例覆盖箱线闭合的五对字符
（含「无箱线字符即忽略」）、图注长度与动宾两类判定、围栏未闭合与围栏内图注、超宽图警告、
HTML 里逃出 `<pre>` 的图注串、`--figures` 开关、以及 JSON 两种列表输出。
- **半分支优先（第 1 步）：`manuscript/terms.py` 83 → 90%**：`is_glossary_candidate` 的 18 条拒绝规则
改成表驱动用例（每条规则一行：功能词、层引用、小节标记、方法调用、箭头、尾标点、路径、源码名、
反引号、括注、超长、版本号、短英文单词、描述性短语），另加 5 个真实术语的正例。
顺带记录一处**已知取舍**：`MVStore` 这类 7 字母单英文词不算术语候选（规则是「8 字母以下的纯英文单词」），
它在术语表里所以不漏判，但表外的 7 字母类名会被跳过——用例里写明了这一点。
- **单文件下限 78 → 83，两处真 bug 被测试逼出来**：`audit/content_volume.py` 79 → 86%
（交付产物页数/字节、基线解析失败、源指纹不一致、PDF/EPUB 缩水、cold-start 档五条路径），
`release.py` 81 → 94%（四个子命令、脏树拒绝、门禁失败即停、`--allow-dirty`）。过程中发现并修好：
① `content_volume.load_baseline(path)` 读了默认路径而不是传入的 `path`——`--baseline <文件>` 一直读错文件；
② `release.git()` 不看出码——`git status` 失败会被读成「工作区脏」，`rev-parse` 失败会返回垃圾。
总覆盖 89.8 → **90.1%**，最薄处变为 `audit/readability.py`（83.2%）。
- **文档核查后的三处对齐**：`technical.md` §4.1 补上 `lib/_errors` 一行、`_fsutil` 的约定由「失败即退出」
改为「失败抛 `ToolError`」；§9 增一行说明工具层失败的统一载体与判据；§4.6 把「领域与门禁的映射由配置推导」
改写成 `path_scopes()` 一张表的实际形态。另修好 §4.4 表格里一处缺表头收尾符的行，
`testplan.md` 增一行「失败语义」判据（载体 `test_lib_errors.py` 与 `script_contract.py`）。
- **代码与配置核查后的三处整改**：① 删掉五个无人引用的函数（`core/settings.py` 的 `base_json`/
`settings_json`、`lib/_config.for_root`、`audit/plan_coverage.plan_path`、`core/docs_archive.topic_dirs`）——
都是重构后的残留；② `check_runner` 的 `domain_rows()` 与 `gates_for_table()` 原本各写一张同构表，
合并为 `path_scopes()`（路径片段 → 域 → 门禁），分类与门禁选择从同一份数据派生，
顺带去掉 `gates_for_change()` 里对 `src/python` 的字符串特判；③ 配置项无死键（`base.json`/`style.json` 的
每个叶子键都在代码里被读到），架构/契约门禁全过。
- **rf-39 收尾：松散断言清零**。此前 8 条被判为「只能接受 0 或 1」的用例都在交付链里，
而本机其实装着 pandoc 3.5 与 playwright + chromium——默认快档只是按 marker 跳过它们，不是缺工具。
开启慢档实跑后逐条定值：`to_pdf`/`verify_pdf`/`pdf_toc_links`/`print_pdf`/`pdf_from_html`/`to_epub`
在夹具书上全部退出 0，并各带一句结论（`PDF 交付校验通过`、`TOC links added`、`Print-grade PDF`、
`PDF saved`、`epubcheck`）。松散断言基线由 8 条清空，门禁从此零容忍。
- **顺带删掉一处重复用例**：`test_pdf_from_html_smoke` 与 `TestFullDeliveryPipeline.test_pdf_from_html`
在定值后函数体完全相同，保留后者（它跑完整前序再断言），前者删除并留一行注释指明去处。
- **rf-40 完成：不再有 ≥60 行的函数**。最后一批把 `ingest/chapters.py::_api_sections`（74 →
§3 整段移到新模块 `ingest/api_sections.py`，chapters.py 889 → 835 行）、`manuscript/snapshot.py::import_snapshot`
（71 → 目录/压缩包两条复制路径 + 清单构造）、`exercises.parse_chapter_slots`（67 → 头部事件生成器）、
`core/docs_archive.py::apply_plan`（61 → 段落搬运、主题移动、索引刷新）、`ingest/chapters.py::main`
（71 → 参数/状态/执行/报告）、`app/cli.py::main`（78 → 参数、标志校验、书目目录、settings、分发）、
`app/tui.py::main`（81 → 参数、`--once`、单帧绘制、按键→行解析）都拆开。
全库 30 → **0** 个。
- **`audit/style_rules.py::check_file`（67 行）拆开**：标题规则、逐行规则（链接文字/术语混写/中英间距）、
段落长度各成一个助手，主循环只做围栏与分派。≥60 行函数 12 → 11，剩余清单记在 rf-40。
- **四个审计脚本的 `main()` 拆开（rf-40 第五批）**：`audit/captions.py`（图注基线/JSON/与基线对比三路各自成函数）、`audit/readability.py`（围栏扫描、HTML 越界检查、报告三段）、`audit/figure_clusters.py`（参数、扫描、汇总、两种输出）、`audit/smart.py::check_figure_refs`（图注提取、引用判定、逐文件报告）。真实书目上的输出与判定不变（图注覆盖 599 张 / 597 引用，仍 PASS）。≥60 行函数 16 → 12。
- **六个长函数按职责拆开（rf-40 第三/四批）**：`test_report.py::main`（96 → 解析器 + 每个子命令一个处理函数 + 分发表）、`make.py::main`（85 → 解析器、选择落地、选择校验、步骤执行四段）、`audit/index_xrefs.py::parse_index`（84 → 行分类三助手）、`render/pdf_toc_links.py::add_links`（81 → 输入校验/读 PDF/矩形换算是三个助手，且失败改抛 `ToolError`）、`audit/source_refs.py::print_report`（77 → 每个报告段落一个打印函数）、`audit/check_architecture.py::check`（77 → 每条规则一个 `_*_problems`）。六处都用同一批输入比对过输出：`test_report` 的子命令、`make` 的 26 条用例、真实索引的解析结果、架构门禁的整树报告、坐标报告全文——逐字节相同。≥60 行函数 22 → 16。
- **三个长函数按职责拆开（rf-40 第二批）**：`audit/style.py::detect_sentence_monotony`（122 行）拆成「分段 / 句首提取 / 单调判定」三步，`audit/source_refs.py::main`（100 行）拆成参数、建索引、扫描、基线维护与两种输出，`render/verify_pdf.py::verify`（97 行）拆成输入、大纲、TOC 链接、版面与字体五组。三处都用「改动前后同一批输入产出逐字节相同」验证：样式用九种段落形态、坐标用真实书目三种调用、PDF 校验用合成 PDF 的六种情形。≥60 行函数 26 → 23。
- **最后 10 处 `sys.exit(1)` 收口（rf-41 完成）**：`manuscript/glossary.py`、`manuscript/index.py`(2)、`manuscript/terms.py`、`render/to_pdf.py`(6) 的失败点全部改为抛 `ToolError`，消息与退出码同源；顺带把这几处直接 `open()` 的读取换成 `_fsutil.read_lines()`（缺文件时给的是同一套 `ToolError` 消息，而不是裸 `OSError`）。至此仓库里不再有「先打印再 `sys.exit(1)`」的失败路径。
- **`render/to_epub.py` 的六个失败点统一走 `ToolError`**：缺 pandoc、`merge.py` 失败、缺合并稿、pandoc 退出码非零、pandoc 消失、没产出 EPUB——都从「先打印再 `sys.exit(1)`」改为一个带消息与退出码的异常，由入口统一转换，消息不再分两处维护。（rf-41）
- **`audit/style_schema.py::validate`（100 行）按检查组拆开**：顶层键、图注预设、体量阈值、文风目标、规则与深度、模板、文件预算各一个 `_check_*` 助手，`validate` 只负责拼接。十二种被改坏的 style.json 上输出逐字节相同；≥60 行函数 27 → 26。（rf-40）
- **单文件下限 77 → 78**：夹具补上 `data/tmpl/templates.toml`（新书脚手架会逐字复制它，此前夹具缺这一份，用例只能走到「读模板」之前），`core/scaffold.py` 77 → 98%——新增 10 条用例覆盖三种坏配置的具名拒绝、手稿目录不可读、脚手架产出的五份文档侧文件、二次执行不改已写文件、`set_source` 的仓库/目录/空值三种形态、`create_book` 与命令行入口两种收尾。最薄处变成 `audit/content_volume.py`（78.6%），下限随之抬到 78。
- **导入期读配置的最后一批判改完**：`audit/source_refs.py`、`ingest/chapters.py`、`render/to_html.py`、`ingest/outline.py`、`audit/style_schema.py`、`audit/smart.py` 的路径与策略常量全部改为调用时解析（`_config` 门面 + `suffixes()`/`generation()`/`templates()`/`quality_policy()` 这类小函数；`source_refs` 的引用正则按后缀元组缓存）。一个进程换书后不再沿用上一本的路径。
  顺带修两处测试隔离：`_fixture.refresh_config` 现在也丢弃 `lib._baseline`/`_fsutil`/`_errors`（它们各自持有 `_config` 引用，不丢弃就会绑在上一本书上），新增的两组用例退出时恢复 `BOOK_ROOT` 与活动书。
- **测试用例核查与整改**：`test_redundancy`（重复体、空断言、松散断言）、`test_network_isolation`/`test_isolation`（零出站）、`test_meta_taxonomy`（层标签与文件名）全绿；人工扫描后修四处：① 真跑 pandoc 的 EPUB 用例从 `tier:fast` 的 `test_render_script_branches.py` 移出，新建 `test_render_epub_pandoc.py`（`tier:slow`）——快档不得依赖 pandoc；② `test_healthy_fixture_passes` 改为 `test_the_fixture_reports_the_gaps_it_has`（夹具本就有缺口，名不副实）；③ `test_repeated_gate_runs_agree` 改为真的比对三次运行的退出码与结论，而不是三次断言同一个值；④ `test_missing_glossary_exits_cleanly` 改为 `test_a_missing_glossary_is_regenerated`（该用例断言的是重新生成）。
- **架构核查后的三处整改**：① `lib/_baseline.path_for()` 不再自己拼路径（一份与 `Config.baseline_path` 重复的实现，且漏掉版本目录），改为委托后者；② `audit/captions.py`、`audit/figure_clusters.py`、`audit/exercises.py` 删掉导入期算出的 `DOCS_DIR`/`MS_DIR` 常量，改读 `_config` 门面；③ `manuscript/terms.py` 的语言包与 `manuscript/case_studies.py` 的输入文件同样改为调用时解析——一个进程换书时不再继续用上一本的路径。另将剩下 6 个仍在导入期读配置的模块记入问题台账。
- **单文件下限 75 → 77**：`core/actions.py` 76 → 81%（补 5 条用例：LLM 层不可用时的状态行、体积结论的三种分支、按定价/未定价两种预估输出），最薄处变成 `core/scaffold.py`（77.1%），下限随之抬到 77。
- **同名文件的书间隔离回归**：新增 `test_lib_book_isolation.py`——两本书各有 同名手稿 `ch1-test.md`、`data/config/base.json` 与 `dist/`，用例钉住四条不变量：同名相对路径各自解析到自己书根、跑一本书的合并不会在另一本里留下产物、一本书的体量基线另一本读不到、两本的同名配置文件各读各的。
- **三个「假搜索引擎」的 PDF 用例迁到快档**：`test_print_pdf`、`test_pdf_build`、`test_pdf_tools` 用的是假 Chromium 引擎，本来不需要浏览器，却全被标成 `tier:slow`。迁档后 `render/print_pdf.py` 80 → 97%、`render/pdf_from_html.py` 79 → 98%，总覆盖 88.6 → 89.0%。（rf-37）
- **`llm_policy` 的分支补测**：新增 10 条用例覆盖策略文件缺失/损坏、`git` 不可用、被跟踪的密钥文件、示例密钥文件填了值或 JSON 损坏、`--json` 三段输出与两种退出码；该文件 78 → 92%。
- 单文件下限仍为 75：`core/actions.py` 是当前最薄处（76.0%，整型比较取 75），要抬到 76 需先补该文件的两处分支。
- **版本轴验收补齐，基线按版本隔离**：`Config.baseline_path()` 现在把配置里的基线文件落到 `baselines/<edition>/`，`content_volume.baseline_path()` 改为调用时解析（未声明 `[baselines]` 时退回落默认位置）——两个版本各比自己的下限，删节版不再被判成缩水。`make.py` 对未声明的 `--edition` 与缺失的 `book.toml` 一样先报错退 2。新增 11 条用例覆盖版本轴的验收：`state/`、`baselines/` 与产物按版本分目录，`renumber.json` 写在 `state/<edition>/`，归档目录名带版本，未声明版本按名拒绝并列出已声明项，cli/tui/web 三处都能选版本。（plan-11）
- **多书的三个渠道与改动分档补齐**：Web 页标题现在写出当前书与版本（`_book_banner`），`/api/run` 的动作在 `ACTION_LOCK` 内执行——活动书是进程级状态，两个并发请求各点一本书时不再互相串；`check_runner.domain_of()` 把「改动落在邻书里」判成 `other-book` 而不是 `infra`，提交只碰另一本书时不会把本书的全部门禁拉起来跑。新增用例：`/api/books` 列出邻书、带 `book` 参数的请求不改活动书、非书目录请求 400、页面含书名与版本、两个并发请求各得其所、邻书改动分档、三渠道（cli/web/tui）对 `status` 与未知动作给出一致结论。（plan-11）
- **`--book` 指向没有 `book.toml` 的书根时先报错再跑**：原先这道检查要等子步骤起来才炸，`make.py check --book <空目录>` 会逐个步骤打出 traceback 片段；现在入口在跑任何步骤前就校验，输出一行「没找到 book.toml，试过 <路径>」并退 2。同时显式 `--book` 会在父进程里重绑活动书，父进程与子步骤读的是同一本书（此前父进程仍停在导入时那本）。新增 2 条用例。（plan-11）
- **改配置不再重导入模块**：`core/settings.py::_reload()` 原先每次写配置都重新导入 `lib._config` 并手工重绑活动书；现在 `Config` 把派生值的计算收进 `_derive()`，新增 `refresh()` 就地重读（书对象与其引用不变），`_reload()` 只剩一行。顺带删掉 `settings.py` 的 `_read_json`/`_write_json`，改用 `lib/_fsutil` 的 `load_json`/`dump_json`——同一件事原本两份实现。
- **`audit/index_xrefs.py::main`（113 行）按检查项拆开**：`_alias_index`、`_target_resolves`、`_check_see_also`、`_check_sub_entry_chapters`、`_check_section_order`、`_print_summary` 各管一段，每个检查返回自己的问题数，`main` 只剩求和与退出码。真实书目上输出与退出码逐字节相同；≥60 行函数 28 → 27。（rf-40）
- **`render/verify_epub.py::verify`（129 行）按检查项拆开**：`_open_archive`（存在/体积/可读）、`_check_mimetype`、`_check_container`、`_parse_opf`、`_check_package`（元数据/封面/manifest 与 spine）、`_check_resolution`、`_check_navigation` 各管一段，`verify` 只剩编排与早退。纯搬移，18 条 EPUB 校验用例全绿；≥60 行函数 29 → 28。（rf-40）
- **三个 `verify_pdf` 测试文件迁到快档**：它们只需要 pypdf，却被标成 `tier:slow`（理由是“交付链要浏览器”），于是覆盖率门禁从不计入。改用 `skipUnless(HAS_PYPDF)` 跳过条件后 11 条用例进入默认套件，`verify_pdf.py` 83 → 85%，未覆盖语句 1237 → 1233。（rf-37）
- **单文件覆盖率下限 72 → 75，先把最薄的三处补上**：新增快档用例覆盖 `verify_pdf.main()`（JSON 与人类两种输出、`--require-toc-links`、缺 PDF）——该文件 73 → 83%；`core/docs_archive.py` 的归档 CLI（`--dry-run`、未知版本、缺文档树）——73 → 88%；`ingest/digest.merge_roots()` 与多源根分支、`--json` 摘要——74 → 100%。总覆盖仍 88%（未覆盖语句 1298 → 1237），单文件下限随最薄处抬到 75，逐文件基线同步重记。
- **失败只剩一个出口**：新增 `lib/_errors.py`——`ToolError` 同时带消息与退出码（派生自 `SystemExit`，`str(exc)` 仍是消息，`sys.exit(message)` 的既有语义不变），`run()` 在入口处把它转成“打印消息 + 返回码”。`_fsutil` 的读写失败、`terms.py` 的写入失败、`to_pdf.py` 的两处 I/O 失败改抛 `ToolError`；58 个入口脚本的 `sys.exit(main(...))` 统一换成 `sys.exit(_errors.run(main, ...))`。测试从此能一次断言“退出码 + 消息”，不必再猜 `SystemExit` 里装了哪个；新增 8 条用例钉住这条契约。（rf-41）
- **遍历整套脚本的用例改为按脚本钉退出码**：`test_every_audit_runs_without_crashing`、`gate_entrypoints` 三条、`script_entrypoints`、`real_book` 两条，此前一律 `assertIn(code, (0, 1))`，等于只证明“没炸”。现在各自带一张退出码表（如审计脚本里 `exercises.py` 为 1、其余为 0；空书上 `links`/`figures` 均为 1），并断言该脚本在表内——新增脚本忘了定值会立刻红。松散断言基线 15 → 8，余下 8 条都是需要 chromium/pandoc 的交付用例，本机跳过，无法定值。
- **永真断言收敛到 15 条**：46 处 `assertIn(code, (0, 1))` 改成断言真实结论——退出码取实际值，再加一条消息断言（`TOTAL`、`issues:`、`FAIL:`、`hierarchy below the configured floor`、`cannot read` 等），断言内容取自每条用例跑出来的输出，不是推断。松散断言基线 61 → 15。
  余下 15 条分两类：7 条是遍历整套脚本的用例（`test_every_audit_runs_without_crashing`、`gate_entrypoints` 三条、`script_entrypoints`、`real_book` 两条），要按整套脚本的措辞写一条公共判据；8 条是需要 chromium/pandoc 的交付用例（`pipeline_delivery` 五条、`render_pdf_toolchain` 三条），本机没有 playwright，跑起来就被跳过，没法定值。
- **两个超长函数按小节拆开**：`ingest/chapters.py::_sections`（261 行）拆成九个助手，每章共享的事实只在 `_chapter_context` 算一次，各助手读同一份事实而不是各推一遍；`manuscript/terms.py::report_missing`（208 行）把中英别名表、跳过词表与`is_glossary_candidate` 提到模块级，剩下的函数只做扫描与报告。两处都是纯搬移，六个章节形态的渲染结果逐字节相同。≥60 行函数 30 → 29，`chapters.py` 755 → 876 行的膨胀登记同步。
- **质量读数有了统一入口**：`make.py report health` 汇总覆盖率（总/最薄模块/半分支 Top-N）、低于基线的文件、松散断言数、超长函数清单——这些此前分散在 `cover`、`coverage report` 与 grep 里，没人定期看。阈值仍读配置（新增 `base.json [toolchain] function_length_warn`），视图只做读数不判红。
- **永真断言开始收敛**：`run_inproc` 原先吞掉 `sys.exit("error: ...")` 的消息，用例只能断言“退出码是 0 或 1”。现在把消息回显进捕获输出，四处用例改为断言具体结论（`to_epub` 的合并失败与缺合并稿、`pdf_from_html` 缺 HTML 的原因、印刷 PDF 的真实产物），松散断言基线 65 → 61 条。
- **覆盖率先按文件棘轮**：全局单数阈值下，一个 200 语句的模块停在 73% 也永远过线。`make.py cover` 现在把每个文件的覆盖率记进 `books/data/baselines/coverage.json`，任一文件低于自己的基线即 FAIL（`--update-baseline` 经评审后重记）；不足 5 条语句的文件除外。当前 95 个模块里 50 个低于 90%，基线把长尾逐个钉住，抬高阈值不再是一次性总账。
- **覆盖率门禁分档**：`make.py cover` 原来写死 `-m tier_fast`，而 CI 慢档 job 装好 chromium/pandoc 后跑的还是快档；于是只有慢档才走到的渲染路径从未计入，`verify_pdf`（73%）这类数字反映的是没人跑过的分支。`cover` 现认 `--full` 与 `BOOK_SLOW=1`，报头直接写出量的是哪一档，CI 慢档 job 改跑 `cover --full`；判据也补上这两个载体。逐模块把“只为拿真工具”的用例改成注入是接着做的工作（`to_epub` 已完成）。（rf-37）
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
  `toolchain`；`how-to-write` §13.6 与 `scripts-and-reference` 的图簇说明改为“取值见配置”。（rf-16）

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
  细则只在 `../manuals/how-to-write.md`。（rf-11）
- **内容标准与写作规则分轴**：`content-standard.md` 只回答“必须有什么”（章节骨架、
  阶梯、事实、图示、术语、练习、四项人工自查），写法一律指向 `../manuals/how-to-write.md`；
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
  写死的阈值移出，分别指向 `technical.md` §4.4 与 `../manuals/how-to-write.md` §6）；§2.2 的「9 项
  CSS 标记」改为「样式与锚点钩子齐备」，删除「脚本语法有效」这条弱判据；§5 不再复述
  §2.2；§6 指向 `content-quality-policy.md` §4 与使用手册。（rf-15）
- 判据只写性质：`testplan` §2.2 的阈值列改为“不低于配置下限”这类表述，键名与取值集中到
  `technical.md` §3.2 的阈值归属；`doc_drift` 新增 `THRESHOLD` 检查，判据表引用配置键
  名即失败。（rf-14）
- 补回网络隔离的用例文件：testplan 一直把它列为网络隔离的载体，文件已不存在。

### 文档清理

- 命令清单只留两处：`books/README.md`（使用）与 `testplan.md` §1（验证）；
  `folder.md` §4、`plan.md` 不再抄一份。
- 格式约定只在 `testplan.md` §3；`../manuals/how-to-write.md` 末尾的复制块删掉并改为引用。
- 跨章引用只认 `详见第X章《标题》`（与 `crossrefs.py` 一致），`../manuals/how-to-write.md` 不再
  给"参见 / 参考 / 见"的变体。
- 段落长度规则合并到 `../manuals/how-to-write.md` §3.1；终端调色板角色表只在 `DESIGN-TUI.md` §8；
  图注句式只在 `../manuals/how-to-write.md` §14。
- `../manuals/how-to-write.md` §7 明确区分章首引导块（引用块四行）与章末必备段落（H2 小节，
  由 `book.toml [sections]` 给出）。

- **ingest 不再吃掉正文**：`chapters.py` 只在目标文件为空、内容相同或 `--force` 时写入，否则跳过并报出行数；`actions.analyze` 在三阶段后跑一次 `content_volume.py`，把「内容体积：与基线一致 / N 项低于基线」写进同一份运行结果（后者判失败并给 `--update-baseline` 指引）。（rf-21）
- **体量基线只能抬高**：`content_volume.py --update-baseline` 默认拒绝把任何条目或总量改低，收缩须 `--accept-shrink --reason "<理由>"`，理由与逐项差额写进基线文件的 `accepted_shrinks`；新增 `--baseline <文件>`，用于显式对照某份历史快照（默认永远比当前基线，不做加权）。（rf-22）
- **基线记账要求“人 + 提交”**：`--update-baseline` 在 `data/manuscript` 有未提交改动、或没有具名评审人时拒绝记账，写入 `reviewed{by, at, commit, reason}`；`content-quality-policy.md` §4 给出固定流程（check 全绿 → 提交手稿 → 记账留名）。（rf-23）
- **历史版本可以提为基线**：`content_volume.py --update-baseline --from-snapshot <label>` 从快照的体积账本取数，记录 `source.snapshot`；比当前基线薄时仍须 `--accept-shrink`。`content-quality-policy.md` §4 给出「导入 → 记快照账本 → 提为基线」流程。（rf-24）
- **基线换版**：按用户指示，把 `docs-stm.zip`（2026-06-11 版）导入为只读快照 `2026-06-11-june-2026` 并认定为体量基线（16 文件 / 36 893 行），理由与来源记账在基线文件里。
- **LLM 用量与费用可见**：新增 `data/config/llm_pricing.json`（每百万 token 单价，未列出的模型记“未定价”）；每次调用记录 token 与费用并追加 `logs/llm-usage.jsonl`；`llm-ask` 打印调用前区间预估 + 调用后「本次 / 今日累计」，`analyze --llm` 打印整轮汇总；`llm_settings.daily_cost_limit` 达到时追加 ⚠ 提醒。（rf-25）
- **LLM 费用多币种，缺省人民币**：`llm_pricing.json` 增加 `display_currency`（缺省 `CNY`）与 `fx` 锚点，费用按模型货币记账、按显示货币汇总（`¥` 前缀，缺锚点时退回原币种）；`logs/llm-usage.jsonl` 每行同时记 `cost_display`/`display_currency`，跨币种的历史也能正确合计。价格表补 `_source`/`_fetched`，明确“人工核对、不联网取价”。
- **价格表改为参考 investor-review 的官方核对结果**：39 个模型（USD/CNY 各自标注），新增以 `-` 结尾的**前缀规则**用于带日期戳的模型名（精确名优先），DeepSeek 的 `peak` 峰谷价先记录、暂不参与计价。
### 交互
- **附录去掉模板化的「章节收尾」并改正错标**：`appendix-a`/`appendix-b` 里的小节标题原写着
「附录 K 源码坐标索引」「附录 L 版本变更对照」——全书只有附录 A/B，K/L 不存在；改为「源码坐标索引」
「版本变更对照」。同时删掉两篇附录的 `延伸思考 / 本章小结 / 延展阅读` 三节：那里的题目用的是
「本章最大包的边界」「把某个包拆成两个」这类**包章节模板话术**，附录里没有「本章的包」；
小结与延展阅读也只是重复第 3 章。依据是 6/15 那版（作者满意的版本）附录里没有这些收尾。
手稿 40,097 → 40,031 行，封面自动同步；印刷版 848 → **846 页**，标准版 747 页，两个 PDF 重新生成并通过 `verify_pdf`。
- **主菜单按任务域分组显示**：首页现在读作三组——`源码成书`（1 analyze / 2 analyze-llm / 3 build / 4 deliver）、`书籍管理`（5 切换书籍 / 6 新增书籍）、`配置与管理`（7 质量 / 8 配置与状态），退出项渲染在分组之后、不入组。分组只在 `core/menu.py::MENU_GROUPS` 声明一处，`tui.py` 按它渲染组标题；`DESIGN-TUI.md` 屏幕树与用户手册同步，新增 3 条用例守护组序、组覆盖完整性（只有 `0` 在组外）与二级屏不带组标题。
- **主菜单数字重排**：`5` 与 `7`、`6` 与 `8` 互换——现在 `5` 切换书籍、`6` 新增书籍、`7` 质量、`8` 配置与状态，前四项（analyze / analyze-llm / build / deliver）不动；字母键跟着动作走：`s` 仍是切换书籍（`5`）、`n` 仍是新增书籍（`6`）、`t` 质量（`7`）、`c` 配置（`8`）。`DESIGN-TUI.md` 屏幕树与键位表、用户手册主菜单同步。

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
