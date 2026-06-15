# H2 源码分析文档 — 工业级技术书籍质量提升 实施计划

> 基线：v5.0（2026-06-11 已交付，36,775 行 / 578 图 / 88 检查通过）
> 目标版本：v6.0（"工业级技术书籍"质量里程碑）
> 创建：2026-06-15
> 类型：feat
> 保存：docs-stm/plan/

---

## 一、问题帧（Problem Frame）

### 1.1 现状

v5.0 已完成"高质量技术参考"层级：

- 全流水线 `final_check.py` 88/88 通过，`check_style.py` 0 警告，`_audit_smart.py` 零缺图。
- 12 章 + 1 附录，36,775 行；578 图 100% 正文引用。
- 术语表 73 条，索引 122 条；前后件齐全（preface/copyright/how-to-read/glossary/references/index）。
- 17 个工具脚本覆盖生成、审计、验证全链路；P0/P1/P2 三级质量门禁就位。
- 6 轮多视角审查全部关闭。

### 1.2 距"工业级技术书籍"的差距

业界标杆（Pragmatic Bookshelf / Apress / O'Reilly / 机械工业出版社"深入理解"系列）共有的特征：

| 维度 | v5.0 现状 | 工业级标准 | 差距 |
|------|-----------|-----------|------|
| 章节篇幅均衡 | ch7-8 合计 8,085 行（最大），ch11-12 仅 2,389 行（最小），3.4 倍差 | 单文件 < 5,000 行；同级章节量级相当 | 高 |
| 跨章端到端叙事 | 各章孤立分析，缺"一条 SQL 全链路"主线 | 每本书有 1-3 个端到端案例研究 | 高 |
| 索引深度 | 122 条平面条目，无子条目，无 see-also | 工业级技术书索引 300-500 条，含层级与交叉指向 | 高 |
| 术语表深度 | 73 条简短释义 | 100-150 条；每条 2-3 行释义 + 章节链接 + 相关术语 | 中 |
| 思考题/动手实验 | 完全缺失 | 主流教材每章 3-10 题 | 高 |
| 前件人格化 | preface 44 行，模板化 | 作者视角、技术深度承诺、读者契约 | 中 |
| 图质量 | 数量充足、引用齐全 | 图注动宾完整、信息密度评估、图簇叙事衔接 | 中 |
| 印刷级 PDF | 有 outline + 可点击目录 | 运行页眉、章首装饰页、目录虚线对齐、页码对齐 | 中 |

### 1.3 用户决策点（已在 scoping 阶段确认）

8 项倾向已用户全部接受：ch7-8 拆分、新增端到端案例附录、ASCII-only 守约、延伸思考小节、印刷级 PDF（P2 优先级）、索引深化、前件深化、新检查从 P2 起步。

---

## 二、需求与成功标准（Requirements）

| ID | 需求 | 验证方式 |
|----|------|----------|
| R1 | ch7-8 拆分为独立 ch7 + ch8 文件，单文件 ≤ 5,000 行 | `wc -l docs-stm/ch*.md` |
| R2 | 新增端到端案例研究附录章，至少 3 个完整案例（SELECT / COMMIT / 崩溃恢复） | 文件存在 + `final_check.py` 章节完整性 |
| R3 | 索引扩展至 300+ 条，引入主条目/子条目层级和 see-also 交叉指向 | `build_index.py --coverage` + 新检查 |
| R4 | 术语表扩展至 100+ 条，每条 2-3 行释义且包含相关术语链接 | `build_glossary.py --coverage` + 新检查 |
| R5 | 全部 12 章新增"延伸思考"小节，每章 3-5 题 | 新工具 `_audit_exercises.py` |
| R6 | 前件深化：preface ≥ 100 行（作者视角/版本声明/读者契约/致谢扩展），how-to-read 增加学习路径矩阵 | 文件行数 + 内容审查 |
| R7 | 图质量升级：图注动宾结构 100% 通过、关键图簇引入桥接叙事 | `readability_check.py --captions` |
| R8 | 印刷级 PDF：运行页眉、章首装饰页、目录虚线对齐 | `verify_pdf.py --print-grade` |
| R9 | 全部新增检查纳入 P0/P1/P2 三级门禁，新检查从 P2 起步，稳定后升级 | `testplan.md` 与 `final_check.py` 实际行为一致 |
| R10 | 现有 88 项检查零退步；流水线时间不超过 v5.0 基线的 1.5 倍 | 全量回归 |

### 成功标准

- v6.0 全流水线通过（含新检查），`final_check.py` ≥ 100 项。
- 9 个章节文件均衡度：最大/最小行数比 ≤ 2.5（v5.0 是 3.4）。
- 端到端案例附录可独立阅读，包含至少 30 张图。
- 索引 ≥ 300 条，每章 ≥ 15 条，含 ≥ 50 处 see-also。
- 思考题总数 ≥ 50 题，每题指向具体章节内容。
- PDF 生成包含运行页眉、章首装饰、目录虚线，verify_pdf 通过。

---

## 三、范围边界（Scope Boundaries）

### 3.1 包含

- 12 章 + 拟新增的端到端案例附录章。
- 全部前后件（preface / copyright / how-to-read / glossary / references / index）。
- 全部 17 个工具脚本（增强）+ 4-6 个新增工具脚本。
- 管理文档（requirements / plan / testplan / changelog / review-findings / style-guide）。
- 生成产物（合并 MD / HTML / PDF）。

### 3.2 不包含

- 章节正文内容重写（仅在端到端案例附录中复用现有内容做主线串联）。
- 英文版翻译。
- Mermaid / SVG 等新图表格式（v5.0 已显式排除，本计划继续守约）。
- CI/CD 集成（已显式排除为 P4）。
- 新章节内容（除端到端案例附录外）。
- 思考题"标准答案附录"（避免内容膨胀；只在思考题处给"提示行 + 章节回链"）。

### 3.3 后续增强项（Deferred to Follow-Up Work）

- 自动化源码比对流水线（H2 上游版本变更对文档影响检测）。
- 增量质量门禁（PR 级别）。
- 阅读体验量化指标（Flesch 可读性、段落长度分布等深度统计）。
- 印刷级 PDF 的字体嵌入与排版细节（连字符、孤行控制等）。
- 思考题"参考答案附录"（如读者反馈强烈再做）。

---

## 四、关键技术决策（Key Technical Decisions）

### 4.1 迭代分阶段而非大爆炸（Phased Delivery）

**决策**：拆为 8 个迭代阶段（A→H），每阶段独立可发布，发布版本号递进（v5.1 → v5.8 → v6.0）。

**理由**：v5.0 已交付且可用；用户明确要求"逐步前进"。每阶段单独通过流水线，避免长分支冲突；任一阶段失败不影响已交付内容。

### 4.2 ch7-8 拆分采用文件切分而非内容重组

**决策**：在自然边界 line 3643（`# 第8章` H1 处）切分为 ch7-sql-execution.md + ch8-query-optimizer.md，保持图号、源码引用、章节编号原样。

**理由**：内容已是"第7章 / 第8章"两个 H1；切分是文件级操作。重新分配图号会导致大量 PDF outline / TOC / 索引 / 交叉引用同步更新，性价比低。文件切分仅触发 `rebuild_merged.py` 文件列表与图号唯一性校验。

**后果**：图号在 ch7 = 7-1..7-76，ch8 = 8-1..8-100，原本就是这样，无需重编号。索引中 §7.x / §8.x 引用全部仍有效。

### 4.3 端到端案例附录采用"叙事 + 回指"模式

**决策**：新章节《附录 A：端到端案例研究》以叙事文体串联现有 12 章内容，每个关键步骤用 `(详见 §X.Y)` 回指原章节，不复制原文，只做"故事化重组"。

**理由**：避免内容膨胀和维护双源。读者获得连贯叙事；维护者只需保证回指有效（已有交叉引用工具可校验）。

### 4.4 索引层级采用"主条目 / 子条目"两级结构

**决策**：扩展索引格式为：

```text
- B-Tree 索引 — §6.1
  - 节点分裂 — §6.1.3
  - 范围扫描 — §6.1.5
  - 与 Counted B-Tree 对比 — §9.6
  see also: MVStore, Page 格式
```

**理由**：工业级技术书索引惯例（参考《数据库系统实现》《Designing Data-Intensive Applications》中文版）。两级足够，再深则读者难以浏览。

### 4.5 思考题采用"嵌入章末 + 提示行 + 回指"格式

**决策**：每章末新增 `## N.X 延伸思考` 小节，每题包含问题 + 一行提示 + `(回顾 §X.Y)` 链接；不设独立答案附录。

**理由**：保证读者自检即时性；提示行+回链足够引导；避免独立答案附录与正文双源维护。

### 4.6 印刷级 PDF 增量推进，不阻塞 MD/HTML 流水线

**决策**：印刷级特性（运行页眉、装饰页、虚线目录）仅作用于 `generate_pdf.py` 输出，不修改源 MD；新增 `--print-grade` 标志按需启用。

**理由**：日常编辑者不应被印刷排版细节拖慢；正式交付时再开启。

### 4.7 新增工具脚本仅在必要时建，优先扩展现有脚本

**决策**：新增脚本上限为 6 个；其余以参数/模式扩展现有脚本。

**理由**：v5.0 已有 17 脚本，再增长会加大维护负担。具体新建清单：`_audit_exercises.py`、`_audit_index_xrefs.py`、`_audit_captions.py`、`balance_check.py`、`build_case_study_outline.py`（生成端到端案例骨架）、`pdf_print_grade.py`（印刷级 PDF）。

### 4.8 新检查全部从 P2 起步

**决策**：所有本计划新增的质量门禁初始为 P2（建议级）；运行 ≥ 2 个迭代周期后基于命中率与误报率评估，再决定是否升级到 P1。

**理由**：避免一次性引入大量阻塞门禁导致已交付内容回归失败。

### 4.9 章节均衡度的"软指标"

**决策**：以"最大/最小行数比 ≤ 2.5"作为软目标，不作为阻塞门禁。

**理由**：章节内容长度由源码复杂度自然决定（ch11-12 是导读+总结，本就应短），强行拉平会损害可读性。ch7-8 拆分后此比已自动从 3.4 降至约 2.7，达成大半。

---

## 五、High-Level Technical Design

### 5.1 文件层级演进

```text
docs-stm/
  cover.md                              # v5.0 → v6.0 元数据更新
  front/                                # 前件
  ├── preface.md                        # 44行 → 100+行（深化）
  ├── copyright.md                      # 不变
  └── how-to-read.md                    # 80行 → 130+行（学习路径矩阵）
  ch1-2-architecture.md                 # 不变
  ch3-packages.md                       # 不变（新增延伸思考）
  ch4-5-modules-processes.md            # 不变（新增延伸思考）
  ch6-1-data-structures.md              # 不变（新增延伸思考）
  ch6-2-storage-algorithms.md           # 不变（新增延伸思考）
  ch6-3-query-algorithms.md             # 不变（新增延伸思考）
  ch7-sql-execution.md                  # 新文件（从 ch7-8 拆分而来）
  ch8-query-optimizer.md                # 新文件
  ch9-10-persistence-locking.md         # 不变（新增延伸思考）
  ch11-12-guide-summary.md              # 不变（新增延伸思考）
  appendix-a-case-studies.md            # 新文件 — 端到端案例研究
  back/                                 # 后件
  ├── glossary.md                       # 73 → 100+条（深化释义）
  ├── references.md                     # 扩充至 30+条
  └── index.md                          # 122 → 300+条（层级 + see-also）
  management/
  ├── requirements.md                   # v5.0 → v6.0
  ├── plan.md                           # v5.0 → v6.0
  ├── testplan.md                       # 新检查纳入
  ├── changelog.md                      # v5.1..v6.0 各阶段记录
  ├── review-findings.md                # 第7轮审查记录
  └── style-guide.md                    # §12 思考题写作 / §13 印刷排版
  tools/                                # 17 → 23 脚本
    新增：_audit_exercises.py
          _audit_index_xrefs.py
          _audit_captions.py
          balance_check.py
          build_case_study_outline.py
          pdf_print_grade.py
```

### 5.2 阶段依赖与并行策略

```text
Phase A (基础)               独立  ──→ 必须最先完成（其他阶段依赖度量基线）
  ↓
Phase B (ch7-8 拆分)         独立  ──→ 优先做，触发文件列表/索引连锁
  ↓
Phase C (前后件深化)         可与 D/E 并行
Phase D (端到端案例)         可与 C/E 并行  (依赖 B 拆分后的章节锚点)
Phase E (图质量升级)         可与 C/D 并行
  ↓
Phase F (思考题)             可与 G 并行
Phase G (印刷级 PDF)         可与 F 并行
  ↓
Phase H (门禁升级 + v6.0)    必须最后
```

### 5.3 阶段-版本-门禁映射

| 阶段 | 交付版本 | 新增门禁 | 阻塞级别 |
|------|----------|---------|---------|
| A | v5.1 | balance metrics report | 信息 |
| B | v5.2 | ch7/ch8 文件存在、图号唯一性、TOC 完整 | P0 |
| C | v5.3 | 索引层级合法性、术语见缺失检测、see-also 双向 | P2 |
| D | v5.4 | appendix 文件存在、案例回指有效率 ≥ 95% | P1 |
| E | v5.5 | 图注动宾结构通过率 ≥ 95% | P2 |
| F | v5.6 | 延伸思考小节存在、每章 ≥ 3 题 | P2 |
| G | v5.7 | PDF 印刷级三件套（页眉、装饰、虚线） | P2（可选标志） |
| H | v6.0 | 全部新检查升级评估 + 全量回归 | P0 全通过 |

---

## 六、实施单元（Implementation Units）

> 单元 ID 在整个计划生命周期内稳定，不因重排而改号。

---

### Phase A — 基础与基线度量

#### U1. 度量基线工具与状态快照

**目标**：建立量化基线，让后续每阶段都能量化对比；产出可重用的均衡度量工具。

**Requirements**：R1（间接）、R10

**Dependencies**：无

**Files**：
- `docs-stm/tools/balance_check.py` — 新建
- `docs-stm/management/review-findings.md` — 新增第7轮基线快照
- `docs-stm/management/changelog.md` — v5.1 条目

**Approach**：
1. 新建 `balance_check.py`：输出每章节文件行数、图数、源码引用数、术语命中数、索引命中数；计算最大/最小比、标准差。
2. 在第7轮审查记录中固化 v5.0 基线数字（行数 36,775 / 578 图 / 73 术语 / 122 索引 / max-min ratio 3.4）。
3. 定义 v6.0 目标值，作为各阶段验收门槛对照表。
4. changelog.md 记录 v5.1 = 基线度量工具就绪。

**Patterns to follow**：参考 `cover_stats.py` 的输出风格；JSON + Markdown 双输出。

**Test scenarios**：
- 在 v5.0 基线上运行，输出与已知数字（36,775 行 / 578 图）一致。
- 输出包含 `max_min_ratio` 字段，且数值 = 8085/2156 ≈ 3.75。
- 提供 `--baseline` 模式生成对照基线 JSON 文件，后续阶段可 diff。
- 误差容忍：行数误差 ≤ 1（仅末尾换行差）。

**Verification**：`python docs-stm/tools/balance_check.py --baseline > baseline-v5.0.json` 成功输出，数字与 cover.md 一致。

---

#### U2. 风格指南扩展（工业级写作约定）

**目标**：在 style-guide.md 新增三节，约定本计划新引入的文体规范。

**Requirements**：R5、R6、R7

**Dependencies**：无

**Files**：
- `docs-stm/management/style-guide.md` — 新增 §12（思考题写作）、§13（端到端案例叙事）、§14（图注动宾结构）

**Approach**：
1. §12 思考题写作：题型分类（理解/分析/动手）、提示行格式、回指章节格式、难度标记 ★/★★/★★★。
2. §13 端到端案例叙事：开篇问题陈述 → 各章节回指 → 关键决策点剖析 → 总结模式。提供一段 200 字示例。
3. §14 图注动宾结构：动词+宾语+限定语三段式（"展示 B-Tree 节点分裂时父节点的递归更新"），列举 5 反例 5 正例。
4. 更新 style-guide.md 头部版本号 v4.27 → v6.0。

**Test scenarios**：
- §12 至少含 1 个完整思考题示例（题干+提示+回指）。
- §13 提供叙事开篇句式的 3 种变体。
- §14 反例正例对照表至少 5 行。

**Verification**：人工审查 + style-guide.md 标题层级在 final_check 中无新警告。

---

### Phase B — 章节均衡（ch7-8 拆分）

#### U3. ch7-8 文件物理拆分

**目标**：在 line 3643 的 `# 第8章` 处切分为 ch7-sql-execution.md（行 1-3642）+ ch8-query-optimizer.md（行 3643-8085），原文件删除。

**Requirements**：R1

**Dependencies**：U1（需基线对照）

**Files**：
- `docs-stm/ch7-8-sql-optimizer.md` — 删除
- `docs-stm/ch7-sql-execution.md` — 新建（约 3,642 行）
- `docs-stm/ch8-query-optimizer.md` — 新建（约 4,443 行）
- `docs-stm/tools/rebuild_merged.py` — 修改（更新文件列表）
- `docs-stm/tools/cover_stats.py` — 修改（如有硬编码列表）
- 其他 9 个工具脚本中的硬编码引用 — 全文替换

**Approach**：
1. 用 `head -n 3642` 与 `tail -n +3643` 切分原文件。
2. 验证切分后两文件 H1 分别为"第7章 SQL 执行全流程"与"第8章 查询优化器深度解读"。
3. 全工具脚本搜索 `ch7-8-sql-optimizer` 字符串，逐个替换为新两文件路径。
4. 更新 `rebuild_merged.py` 的合并顺序：cover → front → ch1-2 → ch3 → ch4-5 → ch6-1 → ch6-2 → ch6-3 → **ch7 → ch8** → ch9-10 → ch11-12 → appendix → back。
5. 验证合并文档总行数 = 各源文件总行数（误差 ≤ 子件数）。

**Patterns to follow**：参考第6章 v4.8 拆分（单文件 → 三子文件）的工具更新模式；保留原图号体系不重排。

**Execution note**：先建分支单独验证，再合并；切分后立即跑全量流水线，**不做任何内容修改**——保证除文件名外内容字节级一致。

**Test scenarios**：
- `wc -l docs-stm/ch7-sql-execution.md` ≈ 3642。
- `wc -l docs-stm/ch8-query-optimizer.md` ≈ 4443。
- `head -1` 分别为"# 第7章 SQL 执行全流程"和"# 第8章 查询优化器深度解读"。
- 合并文档总行数与拆分前一致（允许 ≤ 2 行的换行调整）。
- 拆分前后图号集合完全相同（可用 `grep -hE '^\*\*图 [0-9]+-[0-9]+:' | sort > before/after; diff` 验证）。
- `final_check.py` 通过（章节完整性、TOC、图号、源码引用全部维持）。
- `rebuild_merged.py` 文件列表中 ch7-8 已不存在。

**Verification**：
- 合并文档总行数与拆分前差 = 0（或 ≤ 2 行末尾换行）。
- `final_check.py` 88/88 维持。
- `_audit_smart.py` 零缺图维持。
- 9 个工具脚本中 `ch7-8-sql-optimizer` 字符串数为 0。

---

#### U4. ch7-8 拆分后的回归与文档同步

**目标**：拆分后的 PDF outline、HTML TOC、索引引用、交叉引用全部仍有效。

**Requirements**：R1、R10

**Dependencies**：U3

**Files**：
- `docs-stm/h2-source-code-analysis.md`、`.html`、`.pdf` — 重新生成
- `docs-stm/management/plan.md` — 文件清单更新
- `docs-stm/management/requirements.md` — 文件清单更新
- `docs-stm/cover.md` — 行数/章节数更新
- `docs-stm/management/changelog.md` — v5.2 条目

**Approach**：
1. 运行完整标准流水线 + PDF 三步验证。
2. 验证 HTML TOC 仍含全部 ch7 与 ch8 标题（约 17 个 H2）。
3. 验证 PDF outline 中第7章/第8章成为顶级条目。
4. 抽样验证 5 处跨章引用（如 ch9-10 → §7.1.5 锁机制）链接仍指向正确锚点。
5. 更新 plan.md / requirements.md 中"目录树"小节的文件列表。

**Test scenarios**：
- HTML 中 `id="第7章-sql-执行全流程"` 与 `id="第8章-查询优化器深度解读"` 各出现 1 次。
- PDF outline 顶级条目 = 12 章 + 附录 + 前后件项数（数字与 v5.0 一致）。
- 5 个抽样交叉引用 100% 解析成功（`grep "详见第7章" | head -5` 后逐条核对锚点）。

**Verification**：`final_check.py` 88/88 + `verify_pdf.py` 通过 + 抽样 5/5。

---

### Phase C — 前后件深化

#### U5. 前言（preface）深化

**目标**：从 44 行 / 模板化扩展至 100+ 行，融入作者视角、版本声明、读者契约、深度致谢。

**Requirements**：R6

**Dependencies**：无

**Files**：
- `docs-stm/front/preface.md` — 修改

**Approach**：
1. 新增"为什么写这本书"小节：3 段叙述，包括"行业现状缺口" / "我们的视角" / "本书与官方文档的差异"。
2. 新增"技术深度承诺"小节：明确本书的"承诺与不承诺"清单（承诺：源码级精读、行号准确、跨版本注记；不承诺：JDBC API 教程、SQL 标准讲解、性能调优指南）。
3. 新增"读者契约"小节：阅读前置条件（Java 基础 / SQL 基础 / 数据库内核入门概念），不满足者引导到外部资源。
4. 新增"版本声明"小节：基于 H2 v2.4.249-SNAPSHOT；与上游版本变化点（已有 ch9-10 附录）的关联说明。
5. 扩展致谢小节：分类致谢（H2 团队 / 评审者 / 工具作者 / 读者反馈）。
6. 在末尾保留"非官方文档"声明。

**Patterns to follow**：参考《Designing Data-Intensive Applications》中文版前言、《数据库系统实现》前言的章法。

**Test scenarios**：
- 总行数 ≥ 100。
- 含全部 5 个新增小节的二级标题。
- "技术深度承诺"小节含正反两份清单。
- 读者契约引用至少 3 个外部资源（如 H2 官方 quickstart、Java SE 文档、《数据库系统概念》等）。

**Verification**：`wc -l docs-stm/front/preface.md` ≥ 100；`final_check.py` 全过。

---

#### U6. 阅读指南（how-to-read）深化

**目标**：从单一依赖图扩展为"读者画像 → 学习路径 → 章节先决条件矩阵"三段结构。

**Requirements**：R6

**Dependencies**：无

**Files**：
- `docs-stm/front/how-to-read.md` — 修改

**Approach**：
1. 保留原章节依赖图。
2. 新增"读者画像"小节：4 类典型读者（H2 用户 / 数据库学习者 / 贡献者 / 系统设计爱好者）的画像描述与各自的入口章节。
3. 新增"章节先决条件矩阵"表：每章列出"前置章节" / "前置外部知识" / "可跳过条件"。
4. 扩充"推荐阅读路径"：增加 2 条新路径——"路径 D：MVStore 内核研究"（仅读 ch9 + ch6-2 + ch10）、"路径 E：查询优化器深度"（仅读 ch7 + ch8 + 部分 ch6-3）。
5. 新增"章节估读时长"参考表，按章列出阅读分钟数。

**Test scenarios**：
- 章节先决条件矩阵覆盖 12 章 + 附录共 13 行。
- 5 条阅读路径全部含目标读者、章节序列、预计时长 3 项要素。
- 估读时长表所有数值有合理来源（按 1 行/3 秒估算 + 图表加权）。

**Verification**：`wc -l docs-stm/front/how-to-read.md` ≥ 130；表格在 HTML 渲染正常。

---

#### U7. 术语表深化（73 → 100+，加见缺失检测）

**目标**：把术语表从"短释义"提升为"释义 + 章节 + 相关术语"三元结构；扩展至 100+ 条。

**Requirements**：R4

**Dependencies**：无

**Files**：
- `docs-stm/back/glossary.md` — 修改
- `docs-stm/tools/build_glossary.py` — 增强
- `docs-stm/tools/_annotate_terms.py` — 增强
- `docs-stm/management/testplan.md` — 新增 P2 门禁

**Approach**：
1. 改造 glossary.md 条目格式：

   ```markdown
   - **B-Tree**: 平衡多路查找树。H2 用 Counted B-Tree 变种作为索引主结构，
     支持高效的键值查找、范围扫描和有序遍历。
     **章节**：§6.1（数据结构），§9.6（文件格式编码）
     **相关**：[[Counted B-Tree]]、[[Page 格式]]、[[MVStore]]
   ```

2. 全章扫描，识别遗漏的核心术语（约 30 条）：典型如 RootReference、PageRef、TransactionMap 子状态、MVStoreTool、Recoverable Operation 等。
3. 增强 `_annotate_terms.py`：新增 `--check-related` 模式，验证 see-also 双向引用闭合（A 提到 B，则 B 也应提到 A 或显式标注）。
4. 增强 `build_glossary.py`：新增 `--validate` 模式，验证每条术语的"章节"字段在正文中可定位。
5. testplan.md P2 门禁新增"术语 see-also 闭合性"。

**Test scenarios**：
- glossary.md 条目数 ≥ 100。
- 抽样 10 条术语，每条含释义 ≥ 2 行 + 章节字段 + 相关字段。
- `_annotate_terms.py --check-related` 输出中 see-also 单边引用 ≤ 5%（容忍度）。
- `build_glossary.py --validate` 全部章节字段验证通过。

**Verification**：`build_glossary.py --coverage` 显示每章 ≥ 5 条术语；`_annotate_terms.py --check` 退出码 0。

---

#### U8. 索引深化（122 → 300+，引入层级与 see-also）

**目标**：扩展索引到 300+ 条，引入主条目/子条目层级与 see-also 交叉指向。

**Requirements**：R3

**Dependencies**：U7（部分新增术语会同步入索引）

**Files**：
- `docs-stm/back/index.md` — 大幅修改
- `docs-stm/tools/build_index.py` — 增强
- `docs-stm/tools/_audit_index_xrefs.py` — 新建
- `docs-stm/tools/final_check.py` — 增强（索引层级合法性检查）
- `docs-stm/management/testplan.md` — 新增门禁

**Approach**：
1. 改造索引格式（采用 4.4 节决策的两级结构）：

   ```markdown
   - B-Tree 索引 — §6.1
     - 节点分裂 — §6.1.3
     - 范围扫描 — §6.1.5
     - 与 Counted B-Tree 对比 — §9.6
     see also: MVStore, Page 格式
   ```

2. 系统性补充薄弱章节索引（ch3 当前 4 条 → 30+，ch8 当前 2 条 → 20+，ch11-12 当前 5 条 → 15+）。
3. 引入 ≥ 50 处 see-also 交叉指向。
4. 新建 `_audit_index_xrefs.py`：验证 (a) 子条目引用的章节在主条目同章或下游章；(b) see-also 目标在索引中存在；(c) 字母排序合法。
5. 增强 `build_index.py`：新增 `--hierarchy-check` 输出主/子条目深度报告。
6. 在 `final_check.py` 新增检查项："索引层级合法性"。

**Patterns to follow**：参考机械工业出版社"深入理解"系列的索引编排（先字母后中文，子条目缩进 2 空格）。

**Execution note**：本单元工作量大，建议拆为 3 个 sub-agent 并行：(a) ch1-3 + 前后件，(b) ch4-6，(c) ch7-12 + 附录。

**Test scenarios**：
- 总条目数 ≥ 300（含子条目）。
- 主条目 ≥ 150；子条目 ≥ 150。
- see-also 引用 ≥ 50 处。
- `_audit_index_xrefs.py` 输出零非法子条目章节引用。
- `_audit_index_xrefs.py` 输出零 see-also 死链。
- 抽样 10 个主条目，每个至少 1 条子条目或 see-also。
- 每章索引命中数 ≥ 15。

**Verification**：`final_check.py` 索引检查通过（新增项），`build_index.py --coverage` 每章 ≥ 15。

---

### Phase D — 端到端案例研究

#### U9. 案例骨架生成器

**目标**：新建工具，能从现有 12 章自动抽取交叉引用骨架，作为案例编写的底稿。

**Requirements**：R2

**Dependencies**：U3（拆分后的 ch7/ch8 锚点）

**Files**：
- `docs-stm/tools/build_case_study_outline.py` — 新建

**Approach**：
1. 接受参数 `--scenario select | commit | recover` 选择案例。
2. 对应每个 scenario 在内置流水线表中查找关键章节锚点（如 select：§7.1.1 → §7.4 → §8.1 → §6.1 → §9.6 → §6.5）。
3. 输出叙事骨架 markdown：每个步骤一个段落，含"步骤 N → 触发组件 → 数据结构 → 主要决策点 → 详见 §X.Y"。
4. 写出到临时文件供 U10/U11/U12 编辑加工。

**Test scenarios**：
- 三个 scenario 各能输出 ≥ 10 步骤骨架。
- 输出中每步骤含 `详见 §X.Y` 形式回指。
- 回指锚点全部解析成功（运行 `final_check.py` 后无新增断链）。

**Verification**：三个 scenario 各自产出可读的 markdown 骨架。

---

#### U10. 端到端案例 A：一条 SELECT 从 JDBC 到磁盘

**目标**：以 `SELECT * FROM users WHERE id = 42` 为例，串联 JDBC → Parser → Optimizer → TableFilter → Index → Page → Chunk → FileStore 全链路。

**Requirements**：R2

**Dependencies**：U9

**Files**：
- `docs-stm/appendix-a-case-studies.md` — 新建（A.1 节）

**Approach**：
1. 开篇 1 段问题陈述：用户视角的"我执行了一条 SQL，发生了什么？"。
2. 6-8 个流水线步骤，每步：动机 → 组件 → 关键代码片段 → 决策点剖析 → 回指 §X.Y。
3. 1 张全链路 ASCII 序列图（图 A-1）。
4. 至少 5 张子流程示意图（A-2..A-6），尽可能复用现有图的精简版。
5. 收尾"思考小结"：3 个引导读者自查的问题。

**Patterns to follow**：参考 ch7 §7.5 全链路 ASCII 序列图风格。

**Test scenarios**：
- 案例总长度 ≥ 400 行。
- 含 ≥ 6 张图（A-1..A-6+）。
- 含 ≥ 8 处 `详见 §X.Y` 回指。
- 全部回指锚点解析成功。
- 含完整 SQL 输入 → 最终行返回的端到端步骤链。

**Verification**：`final_check.py` 通过 + 抽样回指 8/8 解析成功。

---

#### U11. 端到端案例 B：一次事务的 COMMIT 全链路

**目标**：以"INSERT + UPDATE + COMMIT"事务为例，串联 Session → Undo Log → MVCC → CommitDecisionMaker → Chunk 写入 → 检查点。

**Requirements**：R2

**Dependencies**：U9

**Files**：
- `docs-stm/appendix-a-case-studies.md` — 修改（A.2 节）

**Approach**：
1. 同 U10 结构。重点：状态机迁移、CAS 操作、可见性变化的时序图。
2. 关键回指：§5.5 COMMIT 流程 / §10.4 MVCC 实现 / §9.5 后台写入 / §6.4 Chunk。
3. 至少 5 张图（含 1 张状态机图、1 张时序图）。

**Test scenarios**：
- 案例总长度 ≥ 400 行。
- 含 ≥ 5 张图（A-7..A-11+）。
- 含 ≥ 8 处回指。
- 含至少 1 张状态机迁移图。
- 含至少 1 张多线程时序图。

**Verification**：同 U10。

---

#### U12. 端到端案例 C：一次崩溃恢复

**目标**：以"进程崩溃后启动"为例，串联 FileStore 打开 → File Header 读取 → Chunk 链遍历 → Recover → Undo Log 重放 → 最终一致状态。

**Requirements**：R2

**Dependencies**：U9

**Files**：
- `docs-stm/appendix-a-case-studies.md` — 修改（A.3 节）

**Approach**：
1. 同 U10 结构。重点：恢复算法的"哪些必须做、哪些可跳过"决策点。
2. 关键回指：§9.7 恢复机制 / §9.6 文件格式 / §9.3 Chunk / 附录"事务子系统"。
3. 至少 5 张图（含 1 张文件版面布局图）。

**Test scenarios**：
- 案例总长度 ≥ 400 行。
- 含 ≥ 5 张图。
- 含至少 1 张文件版面布局图。
- 含 ≥ 8 处回指。
- 涵盖正常恢复 + 异常恢复（如 Chunk 校验失败）两条分支。

**Verification**：同 U10。

---

#### U13. 附录章整合与流水线接入

**目标**：把 appendix-a-case-studies.md 接入合并文档、HTML TOC、PDF outline、索引、术语表。

**Requirements**：R2

**Dependencies**：U10、U11、U12

**Files**：
- `docs-stm/tools/rebuild_merged.py` — 修改（合并顺序加入附录）
- `docs-stm/tools/cover_stats.py` — 修改（附录纳入统计）
- `docs-stm/tools/_audit_smart.py` — 修改（附录章是否豁免缺图检查的策略确认）
- `docs-stm/tools/final_check.py` — 修改（验证附录章存在且 H1 合法）
- `docs-stm/back/index.md` — 增加附录条目
- `docs-stm/back/glossary.md` — 如有新术语则加入
- `docs-stm/cover.md` — 行数/章节数更新
- `docs-stm/management/changelog.md` — v5.4 条目

**Approach**：
1. 合并顺序：ch11-12 之后、back/glossary 之前。
2. PDF outline 中附录作为 13 个顶级条目之一（与 12 章并列）。
3. 索引新增 5 条针对附录的条目（如"端到端 SELECT 案例 — 附录 A.1"）。
4. 验证附录章 ≥ 6 张图/小节，沿用 `_audit_smart.py` 标准；如某节图数不足，加入豁免列表（追加到 `build_exempt_ranges()`）。

**Test scenarios**：
- HTML TOC 中"附录 A：端到端案例研究"出现 1 次。
- PDF outline 顶级条目 = 13（12 章 + 附录）。
- 索引含 ≥ 5 条附录条目。
- 合并文档总行数 ≈ ch_total + appendix_total。
- `_audit_smart.py` 通过（含豁免规则）。

**Verification**：`final_check.py` 全过；`verify_pdf.py` 通过。

---

### Phase E — 图质量升级

#### U14. 图注质量审计工具

**目标**：识别图注的动宾结构合规性，输出违规清单。

**Requirements**：R7

**Dependencies**：无（可并行 Phase C/D）

**Files**：
- `docs-stm/tools/_audit_captions.py` — 新建
- `docs-stm/management/style-guide.md` — 已在 U2 §14 定义规范

**Approach**：
1. 解析全部 `**图 X-Y: Title**` 行，提取 Title 部分。
2. 用启发式规则（动词词典 + 句法长度）标记三类问题：
   - 仅名词短语（如"节点分裂"）→ 建议改为"展示 B-Tree 节点分裂时…"
   - 过短（< 6 字符）→ 建议补充上下文
   - 过长（> 40 字符）→ 建议精简
3. 输出违规列表：`<file>:<line>` + 当前 Title + 建议方向。
4. 提供 `--threshold` 参数控制严格度。

**Test scenarios**：
- 全书 578 张图，输出 < 30 张违规（基线粗扫）。
- 启发式准确率 ≥ 80%（人工抽样 30 条）。
- 不报告代码块内的形似行（保护反引号、code fence 边界）。

**Verification**：在 v5.0 基线上输出违规清单可读，无崩溃。

---

#### U15. 图注质量批量修复

**目标**：基于 U14 输出，逐章修复图注。

**Requirements**：R7

**Dependencies**：U14

**Files**：
- `docs-stm/ch*.md`（全部 9 个） — 修改

**Approach**：
1. 按章逐次修复，每章 sub-agent 并行处理。
2. 每条修复保持图号不变，仅修改 Title 文本。
3. 修复完成后重跑 `_audit_captions.py`，违规率 ≤ 5%。
4. 用 `--diff` 模式输出修改前后对照，便于审查。

**Test scenarios**：
- `_audit_captions.py` 违规数 ≤ 30（从基线下降 ≥ 50%）。
- 抽样 50 条修改前后，95% 改善（人工评估）。
- 图号集合修改前后完全一致（无意外重编号）。

**Verification**：`_audit_captions.py` 通过率 ≥ 95%，`final_check.py` 88/88 维持。

---

#### U16. 图簇桥接叙事

**目标**：识别相邻 3+ 张图的"图簇"，在簇内首图前补充 1-2 句桥接叙事。

**Requirements**：R7

**Dependencies**：U15

**Files**：
- `docs-stm/ch*.md`（部分章节，按桥接需求）— 修改
- `docs-stm/management/style-guide.md` — §13 补充图簇叙事规则

**Approach**：
1. 用脚本识别"3 张图在 ≤ 50 行内连续出现"的图簇（约 15-25 处）。
2. 每个图簇前补充 1-2 句桥接叙事："以下三张图共同呈现 X 的三个视角："等。
3. 不增加新图，仅增加叙事。

**Test scenarios**：
- 识别出的图簇数 ≥ 15。
- 每簇前的桥接叙事 ≥ 1 句。
- 桥接叙事与簇内图主题一致（人工抽样 10 簇）。

**Verification**：人工评估 + `final_check.py` 维持通过。

---

### Phase F — 延伸思考

#### U17. 延伸思考小节工具与模板

**目标**：建立"延伸思考"小节模板与校验工具，统一全书风格。

**Requirements**：R5

**Dependencies**：U2（style-guide §12 已就位）

**Files**：
- `docs-stm/tools/_audit_exercises.py` — 新建
- `docs-stm/management/style-guide.md` — §12 已就位（U2 完成）

**Approach**：
1. `_audit_exercises.py`：扫描每章是否有 `## N.X 延伸思考` 小节；统计每章题数；验证每题是否含"提示"+"回顾 §X.Y"两要素。
2. 输出：每章题数表 + 缺失或不规范题清单。
3. 提供 `--template` 模式输出模板示例，便于人工填充。

**Test scenarios**：
- 在尚未填充的 v5.0 基线上运行，输出 12 章全部"缺失"。
- 人工填入 1 章测试数据后，识别出题数 = 3 且全部合规。
- 提示行/回指缺失时正确告警。

**Verification**：工具可在零数据 / 部分数据 / 全数据三种状态下正确运行。

---

#### U18. 各章延伸思考填充

**目标**：12 章每章新增 `## N.X 延伸思考` 小节，3-5 题，覆盖三种题型（理解 / 分析 / 动手）。

**Requirements**：R5

**Dependencies**：U17

**Files**：
- `docs-stm/ch1-2-architecture.md`、`ch3-packages.md`、`ch4-5-modules-processes.md`、`ch6-1-data-structures.md`、`ch6-2-storage-algorithms.md`、`ch6-3-query-algorithms.md`、`ch7-sql-execution.md`、`ch8-query-optimizer.md`、`ch9-10-persistence-locking.md`、`ch11-12-guide-summary.md` — 全部修改

**Approach**：
1. 每章 sub-agent 并行：阅读章末小结，提炼 3-5 题。
2. 每题包含：
   - 难度（★/★★/★★★）
   - 题干（一句话）
   - 提示（一行，引导思路）
   - 回顾（指向相关 §X.Y）
3. 题型分布：约 40% 理解题 / 40% 分析题 / 20% 动手题。
4. 双章文件（ch1-2、ch4-5、ch6-1-2-3、ch9-10、ch11-12）每个独立章末各加一组。

**Patterns to follow**：style-guide §12 中的模板。

**Test scenarios**：
- 全书思考题总数 ≥ 50（12 个独立章 × 平均 4-5 题，含双章文件分别独立配题）。
- 每章题数 ≥ 3。
- 全部题含难度标记、提示行、回顾链接。
- 全部回顾链接锚点可解析。
- 题型分布大致符合 40/40/20。

**Verification**：`_audit_exercises.py` 全过 + `final_check.py` 88/88 维持。

---

### Phase G — 印刷级 PDF

#### U19. 印刷级 PDF 渲染管道

**目标**：在不影响日常 PDF 流程的前提下，新增"印刷级"PDF 选项，含运行页眉、章首装饰页、目录虚线对齐、页码对齐。

**Requirements**：R8

**Dependencies**：U13（附录已接入）

**Files**：
- `docs-stm/tools/pdf_print_grade.py` — 新建
- `docs-stm/tools/generate_html.py` — 增强（新增 `--print-grade` 模式生成印刷专用 HTML）
- `docs-stm/tools/generate_pdf.py` — 增强（接受 `--print-grade` 标志）
- `docs-stm/tools/verify_pdf.py` — 增强（接受 `--print-grade` 标志）
- `docs-stm/management/testplan.md` — 新增印刷级 PDF 验证项

**Approach**：
1. `pdf_print_grade.py` 协调三步：印刷 HTML → Chromium PDF → 后处理（页码注解、虚线对齐）。
2. 印刷专用 CSS：
   - `@page { @top-left: "H2 源码分析"; @top-right: string(chapter-name); @bottom-center: counter(page); }`
   - 章首页 `page-break-before: always` + 大号渐变标题装饰。
   - 目录条目 `<a class="toc-entry">章名 ······· 页码</a>`，CSS `border-bottom: dotted` + flex 对齐。
3. 后处理用 pypdf 添加可点击章首装饰页书签。
4. 验证三件套：(a) 每页非首页含运行页眉 (b) 章首页含装饰元素 (c) 目录页含虚线对齐。

**Patterns to follow**：参考已有的 `add_pdf_toc_links.py` 后处理模式；CSS 参考 Pagedjs 印刷级范例。

**Execution note**：先在小样章（ch11-12）验证渲染效果再全量；保留对照 `--standard` 模式不变。

**Test scenarios**：
- 普通 PDF 流程不变（`generate_pdf.py` 默认行为）。
- `--print-grade` 模式生成 PDF 含运行页眉（每非首页）。
- 章首页面有装饰元素（CSS class `chapter-cover` 在 PDF 中可见）。
- 目录页中条目含虚线对齐（视觉验证 + 后处理标记）。
- 印刷级 PDF 文件大小 ≤ 标准 PDF 1.5 倍。
- `verify_pdf.py --print-grade` 通过运行页眉/装饰/虚线三项检查。

**Verification**：印刷级 PDF 在 Chrome / Adobe Reader 中视觉验证 + verify_pdf 通过。

---

### Phase H — 门禁升级与 v6.0 收尾

#### U20. 新增门禁纳入与升级评估

**目标**：把本计划新增检查全部纳入 testplan.md P0/P1/P2 框架；评估前期阶段的运行数据决定是否升级。

**Requirements**：R9

**Dependencies**：U1-U19 全部完成

**Files**：
- `docs-stm/management/testplan.md` — 大幅修改
- `docs-stm/tools/final_check.py` — 整合所有新检查的总入口
- `docs-stm/management/review-findings.md` — 第7轮闭环记录

**Approach**：
1. 收集 U1-U19 各阶段引入的所有门禁，整理为统一表格。
2. 评估每个门禁：(a) 截至本阶段的命中数 (b) 误报率 (c) 修复成本。
3. 决定升级清单：误报率 < 10% 且修复成本可承受的 P2 → P1；其余保留 P2。
4. 更新 `final_check.py` 总入口：可选 `--gate-level p0|p1|p2` 控制运行级别。
5. testplan.md 新增"门禁演进史"小节，记录从 P2 升级到 P1 的判定过程。

**Test scenarios**：
- testplan.md 门禁表覆盖 U1-U19 引入的全部检查。
- `final_check.py --gate-level p0` 仅运行 P0 检查（核心门禁）。
- `final_check.py --gate-level p1` 运行 P0 + P1。
- `final_check.py --gate-level p2`（默认）运行全部。
- 全书在 P0 级别 100% 通过；P1 ≥ 95% 通过；P2 整体通过率 ≥ 85%。

**Verification**：`testplan.md` 与 `final_check.py` 实际行为一致；review-findings.md 第7轮闭环。

---

#### U21. v6.0 全量回归与发布

**目标**：完整流水线全部通过，cover/版本号同步，changelog 收口，发布 v6.0。

**Requirements**：R10

**Dependencies**：U20

**Files**：
- `docs-stm/cover.md` — 版本 v5.0 → v6.0
- `docs-stm/management/requirements.md` — v6.0 同步
- `docs-stm/management/plan.md` — v6.0 同步
- `docs-stm/management/testplan.md` — v6.0 同步
- `docs-stm/management/changelog.md` — v6.0 总览条目
- `docs-stm/h2-source-code-analysis.md`、`.html`、`.pdf` — 全部重新生成

**Approach**：
1. 运行全量标准流水线 + PDF 三步 + 印刷级 PDF。
2. 同步全部管理文档版本号为 v6.0。
3. changelog.md v6.0 条目记录：U1-U21 各单元产出概要、关键数字对比（基线 → v6.0）。
4. cover.md 更新行数、图数、引用数、章节数。

**Test scenarios**：
- 全部 4 类质量门禁通过：标准流水线（cover_stats / rebuild_merged / generate_html / _audit_smart / final_check）、写作风格（check_style）、印刷级 PDF（verify_pdf --print-grade）、门禁分级（final_check --gate-level p1）。
- v6.0 vs v5.0 对照表：行数 +X / 图数 +Y / 索引 +178 / 术语 +27 / 思考题 +50。
- 全部管理文档头部版本号 = v6.0。
- 第7轮 review-findings 全部关闭。

**Verification**：全量流水线通过 + 管理文档版本一致 + changelog v6.0 条目完整。

---

## 七、阶段-单元矩阵

| 阶段 | 版本 | 包含单元 | 关键产出 | 阻塞门禁 |
|------|------|---------|---------|---------|
| A 基础度量 | v5.1 | U1, U2 | balance_check.py + style-guide §12-§14 | 信息级 |
| B ch7-8 拆分 | v5.2 | U3, U4 | ch7-sql-execution.md, ch8-query-optimizer.md | P0：文件存在、图号、TOC |
| C 前后件深化 | v5.3 | U5, U6, U7, U8 | preface 100+行、how-to-read 130+行、glossary 100+条、index 300+条 | P2：层级合法、see-also 闭合 |
| D 端到端案例 | v5.4 | U9, U10, U11, U12, U13 | appendix-a-case-studies.md（≥1200行 / ≥16图 / ≥24 回指） | P1：附录存在、回指率 ≥95% |
| E 图质量升级 | v5.5 | U14, U15, U16 | 图注合规率 ≥95%、图簇桥接 ≥15处 | P2：图注动宾结构 |
| F 延伸思考 | v5.6 | U17, U18 | 50+ 题、12 章覆盖、3 题型平衡 | P2：每章 ≥3 题 |
| G 印刷级 PDF | v5.7 | U19 | pdf_print_grade.py + 印刷级 CSS | P2：可选标志 |
| H 门禁升级 + v6.0 | v6.0 | U20, U21 | testplan v6.0 + 全量回归 | P0 全过 |

---

## 八、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| ch7-8 拆分破坏 PDF outline / 跨章引用 | 中 | 高 — 回归失败需回滚 | U3 强制要求"内容字节级一致"；U4 全量验证 + 抽样 5/5 锚点 |
| 端到端案例与正文双源漂移 | 高（长期） | 中 — 准确性下降 | 4.3 决策的"叙事 + 回指"模式；附录中禁止复制正文段落 |
| 索引扩展到 300+ 条带来人工误录 | 中 | 中 — 死链 | U8 引入 `_audit_index_xrefs.py` 自动校验子条目章节有效性 |
| 思考题质量参差 | 高 | 中 — 影响读者信任 | U2 §12 模板 + 题型分布门禁 + 同行评审 |
| 印刷级 PDF 在不同 PDF 阅读器渲染差异 | 高 | 低 — P2 级可选 | 在 Chromium / Adobe Reader / SumatraPDF 三平台抽样验证 |
| 各阶段并行带来文件冲突 | 中 | 低 — 解决简单 | 阶段 C/D/E 可并行但落到不同文件；冲突文件优先按阶段顺序合并 |
| 门禁误报率高拖慢日常修订 | 中 | 中 | 4.8 决策的"P2 起步"原则 + U20 的升级评估机制 |
| 工具脚本数量再增 6 个加大维护成本 | 低 | 低 | 4.7 上限 6 个；每个脚本 ≤ 200 行；在 README 中索引清单 |
| 端到端案例 U10/U11/U12 间内容重叠 | 中 | 低 — 阅读冗余 | 三个案例覆盖三种不同视角（查询 / 写入 / 恢复），开篇问题陈述明确边界 |
| ch11-12 思考题难产（导读+总结性章节） | 中 | 低 | 此章思考题侧重"读完全书后的综合性反思"，难度可降至 ★ 级 |

---

## 九、依赖与前提

- 假设 H2 上游源码 v2.4.249-SNAPSHOT 在本计划周期内不发生破坏性变更（行号偏移在 `source_freshness_check.py` 容忍范围内）。
- 假设 `final_check.py` 88/88 基线在本计划开始前仍然成立。
- 工具开发使用 Python 3.10+，无新依赖（不引入 Pandoc / LaTeX 等）。
- 印刷级 PDF 使用 Playwright Chromium，无新外部依赖。
- 已有的 P0/P1/P2 三级门禁框架是本计划新增门禁的合法宿主。

---

## 十、验收检查清单（v6.0 交付门禁）

### 章节均衡（R1）
- [ ] ch7-sql-execution.md 与 ch8-query-optimizer.md 独立存在
- [ ] 单文件最大行数 ≤ 5,000
- [ ] 9 个章节文件最大/最小比 ≤ 2.7

### 端到端案例（R2）
- [ ] appendix-a-case-studies.md 存在且 ≥ 1,200 行
- [ ] 含 3 个案例（A.1 / A.2 / A.3）
- [ ] 共含 ≥ 16 张图（A-1..A-16+）
- [ ] 共含 ≥ 24 处 `详见 §X.Y` 回指
- [ ] 全部回指锚点 100% 有效

### 索引深化（R3）
- [ ] index.md 总条目 ≥ 300（含子条目）
- [ ] 每章索引命中 ≥ 15
- [ ] see-also 引用 ≥ 50 处
- [ ] `_audit_index_xrefs.py` 零死链

### 术语表深化（R4）
- [ ] glossary.md 条目数 ≥ 100
- [ ] 每条含释义 ≥ 2 行 + 章节字段 + 相关字段
- [ ] `_annotate_terms.py --check-related` 单边引用 ≤ 5%

### 延伸思考（R5）
- [ ] 全部 12 章（含双章文件每个独立章）含 `延伸思考` 小节
- [ ] 总题数 ≥ 50
- [ ] 每题含难度 / 提示 / 回顾三要素
- [ ] 题型分布大致符合 40/40/20

### 前件深化（R6）
- [ ] preface.md ≥ 100 行
- [ ] how-to-read.md ≥ 130 行
- [ ] preface 含技术深度承诺与读者契约小节
- [ ] how-to-read 含读者画像 + 章节先决条件矩阵 + 估读时长表

### 图质量升级（R7）
- [ ] `_audit_captions.py` 违规率 ≤ 5%
- [ ] 识别图簇 ≥ 15 处，每处含桥接叙事

### 印刷级 PDF（R8）
- [ ] 标准 PDF 流程不变
- [ ] `--print-grade` 模式生成 PDF 含运行页眉、章首装饰、虚线目录
- [ ] `verify_pdf.py --print-grade` 通过

### 门禁与流水线（R9, R10）
- [ ] `final_check.py` ≥ 100 项检查
- [ ] P0 级 100% 通过 / P1 ≥ 95% / P2 ≥ 85%
- [ ] 流水线时间 ≤ v5.0 基线 1.5 倍
- [ ] 现有 88 项检查零退步

### 管理文档
- [ ] cover.md 行数/图数/引用数/章节数同步至 v6.0
- [ ] requirements / plan / testplan / changelog / style-guide 头部版本 = v6.0
- [ ] changelog v6.0 条目含基线 → 目标对比表
- [ ] review-findings 第7轮全部关闭

---

## 十一、迭代节奏建议（执行参考，非强制）

> 实际节奏由用户决定每次推进的范围。本节仅给出"自然分批"的参考。

| 批次 | 范围 | 说明 |
|------|------|------|
| 第 1 批 | Phase A (U1, U2) | 度量基线 + 风格规范，1 个 session 内完成 |
| 第 2 批 | Phase B (U3, U4) | ch7-8 物理拆分 + 全量回归，独立 session |
| 第 3 批 | Phase C-1 (U5, U6) | 前件深化（preface + how-to-read），1 session |
| 第 4 批 | Phase C-2 (U7, U8) | 术语表 + 索引深化，并行 sub-agent，1-2 session |
| 第 5 批 | Phase D (U9-U13) | 端到端案例附录，骨架 + 三案例 + 接入，2 session |
| 第 6 批 | Phase E (U14-U16) | 图质量审计 + 修复 + 桥接叙事，1-2 session |
| 第 7 批 | Phase F (U17, U18) | 延伸思考工具 + 12 章填充，并行 sub-agent，1 session |
| 第 8 批 | Phase G (U19) | 印刷级 PDF 渲染管道，1 session |
| 第 9 批 | Phase H (U20, U21) | 门禁升级 + v6.0 收尾，1 session |

预计总投入：8-12 个 session（每 session 约 1-3 小时主操作 + 异步验证）。

---

## 十二、与既有体系的关系

- 本计划继承 v5.0 的 P0/P1/P2 三级门禁框架，不引入新框架。
- 沿用现有 17 工具脚本，仅增量扩展；新增 6 脚本上限。
- 不修改既有 88 项检查，仅追加；任何回归即视为本计划失败。
- ASCII-only 守约延续；不引入 Mermaid / SVG / 交互图。
- 端到端案例采用回指模式，不与正文产生双源。
- 印刷级 PDF 作为可选输出，日常 MD/HTML 流水线不受影响。

---

## 十三、参考与外部惯例

- 《数据库系统实现》第二版（Garcia-Molina）— 索引层级与术语表深度参考。
- 《Designing Data-Intensive Applications》中文版 — 前言风格与读者契约写法参考。
- Pragmatic Bookshelf 风格指南（公开博客）— 思考题分类与难度标记参考。
- Apress《PostgreSQL Internals》— 端到端案例研究的"叙事 + 回指"模式参考。
- 机械工业出版社"深入理解"系列 — 印刷级排版（运行页眉、章首装饰、虚线目录）参考。
