# H2 源码分析文档 — 质量提升实施计划

> 目标：在现有自动化验证全部通过（82/82）的基础上，将文档质量从"通过格式检查"提升至"高质量技术书籍"水准
> 版本：v4.29 → 目标 v5.0
> 创建：2026-06-11
> 保存：docs-stm/plan/

---

## 一、问题帧

### 1.1 当前状态

- 12 章 + 1 附录，36,595 行，578 图，185 引用
- `final_check.py` 82/82 全部通过
- `check_style.py` 0 警告（写作风格零问题）
- `_audit_smart.py` 0 缺图项
- 6 轮多视角审查完成，所有记录问题已关闭
- 16 个工具脚本覆盖生成、审计、验证全链路
- 写作风格指南（10 节）、术语表（38 条）、概念索引（86 条）

### 1.2 现有覆盖与缺口

| 维度 | 现有工具覆盖 | 缺口 |
|------|-------------|------|
| 结构格式 | ✅ `final_check` 82项全面覆盖 | 章节篇幅均衡性 |
| 图数覆盖 | ✅ `_audit_smart` 每### ≥2图 | 图质（非数量）、图引用一致性 |
| 写作风格 | ✅ `check_style` 11类检测 | 段落长度分布、渐进式展开 |
| 交叉引用 | ✅ `final_check` 跨章引用验证 | 引用上下文铺垫质量 |
| 术语一致性 | ⚡ `_annotate_terms.py` 存在但未集成 | 术语表不完整、首次出现标注覆盖度 |
| 索引体系 | ⚡ `build_index.py`/`build_glossary.py` 存在但未集成流水线 | 索引条目密度、术语与索引联动 |
| 代码保鲜 | ❌ 无 | H2 源码变更导致行号/API过时无感知 |
| 图质评估 | ❌ 无 | 图可读性、信息密度、与正文对应 |
| 章节过渡 | ❌ 无 | 章间衔接质量、阅读曲线平顺度 |
| 示例完整性 | ❌ 无 | 伪代码与真实代码比例、示例覆盖度 |

---

## 二、范围边界

### 2.1 包含

- 全部 12 章 + 附录 + 前后件（glossary/index/references）
- 管理文档（requirements/plan/testplan/changelog/review-findings/style-guide）
- 工具脚本（`docs-stm/tools/`）
- 写作风格指南更新

### 2.2 不包含

- 新增章节或内容重写（此计划聚焦质量提升，非内容扩展）
- 英文版本翻译
- CI/CD 集成
- 交互式图表迁移（Mermaid 等）

### 2.3 后续增强项

- 自动化源码比对流水线（检测 H2 源码变更对文档行号的影响）
- 增量质量门禁（PR 级别而非全量）
- 阅读体验量化指标（段落长度分布、Flesch 可读性等）

---

## 三、关键技术决策

### 3.1 工具集成策略

**决策**：将现有独立工具（`build_glossary.py`、`build_index.py`、`_annotate_terms.py`、`_audit_crossrefs.py`、`_audit_figures.py`）逐步集成到标准流水线中，而非新建工具。

**理由**：已有工具覆盖了多个缺口维度，只是未纳入 `testplan.md` 的标准验证流程。先集成可快速获得价值。

### 3.2 维度优先级

**决策**：按"最大读者价值 → 最小实施成本"排序，而非按工具存在与否。

**理由**：术语体系和索引系统直接影响读者查找效率，但修复成本低。代码保鲜影响技术准确性但实现成本高。排序为：

1. 术语体系完善（高价值/低成本）
2. 索引体系完善（高价值/中成本）
3. 工具集成与流水线增强（中价值/中成本）
4. 阅读体验优化（高价值/高成本）
5. 图表质量提升（中价值/中成本）
6. 代码保鲜机制（高价值/高成本）

### 3.3 质量门禁分层

**决策**：新增 P0/P1/P2 三级质量门禁，P0 为阻塞级（不得交付），P1 为严重（应修复后交付），P2 为建议（可暂缓）。

**理由**：36,595 行的技术书不可能一次性零瑕疵。分层门禁允许渐进式提升，避免「全有或全无」的停滞。

---

## 四、实施单元

### U1. 术语体系完善

**目标**：术语表从 38 条扩展至 60+ 条，覆盖全书 12 章所有核心专业术语

**依赖**：无

**文件**：
- `docs-stm/back/glossary.md` — 修改
- `docs-stm/tools/_annotate_terms.py` — 修改（增强检测模式）
- `docs-stm/tools/build_glossary.py` — 修改（增加章节覆盖报告）
- `docs-stm/management/testplan.md` — 修改（新增术语验证项）

**方法**：
1. 对 12 章逐章扫描，提取遗漏的专业术语（关键词：未出现在 glossary.md 但出现在正文中的 `org/h2/` 类名、算法名、协议名、隔离级别等）
2. 每章补充 2-4 条遗漏术语，确保每章至少有 3 条术语覆盖
3. 增强 `_annotate_terms.py`，新增「术语遗漏报告」模式：扫描正文中符合术语模式（中英文混写、反引号括起的类名、首次出现的英文缩写）但未在 glossary.md 中的条目
4. 更新 `testplan.md` 新增「术语表完整性」验证项
5. 对 ch11-12（目前覆盖最少）等薄弱章节专项补充

**测试场景**：
- 扫描全书，验证每章至少 3 条术语在 glossary.md 中有对应条目
- 验证 glossary.md 所有条目的首次出现章节标注与正文实际首次出现匹配
- 验证 `_annotate_terms.py --report-missing` 输出不超过 5 条假阳性

**验证**：`python docs-stm/tools/_annotate_terms.py --check` 零遗漏告警

### U2. 概念索引完善

**目标**：索引从 86 条扩展至 120+ 条，覆盖关键类名、算法名、概念术语与章节的映射

**依赖**：U1（术语体系完善后，部分术语可直接进入索引）

**文件**：
- `docs-stm/back/index.md` — 修改
- `docs-stm/tools/build_index.py` — 修改（增加章节覆盖度报告、条目密度分析）
- `docs-stm/tools/final_check.py` — 修改（新增索引完整性检查）
- `docs-stm/management/testplan.md` — 修改

**方法**：
1. 分析现有 86 条索引的章节分布，识别覆盖不足的章节
2. 为 ch3（包详解，目前仅有 4 条索引）补充关键包/类条目
3. 为 ch8（优化器，目前仅有 2 条索引）补充优化相关概念
4. 将 U1 新增术语中适合索引的条目加入 index.md
5. 增强 `build_index.py`：新增章节覆盖度报告，输出每章索引条目密度
6. 将索引验证加入 `final_check.py`：验证 `index.md` 中引用的章节号在对应章节文件中存在

**测试场景**：
- 全书 12 章，每章至少 5 条索引条目
- `index.md` 中引用的所有章节号在正文中可找到匹配内容
- `build_index.py --coverage` 报告显示无零覆盖章节

**验证**：`final_check.py` 索引检查通过（新增检查项），每章索引密度 ≥ 5 条

### U3. 工具集成与流水线增强

**目标**：将现有零散工具纳入标准流水线，消除被忽视的质量维度

**依赖**：U1（术语工具集成）、U2（索引工具集成）

**文件**：
- `docs-stm/tools/final_check.py` — 修改（新增 glossary/index 验证、交叉引用完整度检查）
- `docs-stm/management/testplan.md` — 修改（更新质量门禁表、验证流程）
- `docs-stm/management/style-guide.md` — 修改（更新第9章工具行为描述）

**方法**：
1. 审查所有 `docs-stm/tools/_audit_*.py` 脚本，确定可集成到 `final_check.py` 的检查项
2. 将 `_audit_crossrefs.py` 的核心逻辑整合进 `final_check.py` 的交叉引用检查模块
3. 将 `_audit_figures.py` 的核心逻辑整合进 `final_check.py` 的图号检查模块
4. 新增 `final_check.py` 检查：glossary.md 的章节引用有效性、index.md 的引用有效性
5. 更新 `testplan.md`：质量门禁表新增术语/索引/交叉引用完整度条目
6. 在 `testplan.md` 的标准验证流程中可选加入 `build_glossary.py` 和 `build_index.py`（辅助性，非阻塞）
7. 更新 `style-guide.md` §9 反映工具行为变化

**测试场景**：
- `final_check.py` 扩展后通过数 ≥ 原有 82 项（只增不减）
- `_audit_crossrefs.py` 和 `_audit_figures.py` 的去重检查通过 final_check 模拟
- testplan.md 质量标准表与 final_check 实际检查项一致

**验证**：`final_check.py` 扩展后通过，`testplan.md` 与工具实际行为一致

### U4. 阅读体验优化

**目标**：系统性提升渐进式展开、段落结构、章节过渡和示例完整性

**依赖**：无

**文件**：
- `docs-stm/ch*.md`（全部 9 个源文件） — 修改
- `docs-stm/tools/check_style.py` — 可选增强
- `docs-stm/management/style-guide.md` — 修改（补充段落和过渡章节）

**方法**：
1. **段落长度审计**：编写一次性分析脚本，统计每章的段落长度分布（以空行分隔），标记超长段落（>15 行）和超短段落（单行）
2. **章节过渡审计**：逐章检查章末小结→下章章首引导之间的过渡质量，标记无过渡或过渡生硬处
3. **渐进式展开审计**：每章选择 3 个关键概念，检查是否遵循「是什么→为什么→怎么用」的渐进模式
4. **示例完整性审计**：检查每章核心算法/流程是否至少有一个完整代码示例（非伪代码片段）
5. 修复发现的问题：拆分超长段落、补充过渡语句、补充缺失的示例
6. 将本次审计中发现的系统性模式补充到 `style-guide.md`（如过渡段落写作规范、段落长度建议）

**测试场景**：
- 全书无 >15 行段落（代码围栏和列表不计入）
- 每章至少 1 句明确指向下一章内容的过渡语句
- 每章核心算法/流程有至少 1 个配套示例

**验证**：段落审计脚本输出零违规，章节过渡检查零缺失

### U5. 图表质量提升

**目标**：从「有图」到「好图」——提升 ASCII 图的清晰度、信息密度和与正文的对应关系

**依赖**：无

**文件**：
- `docs-stm/ch*.md`（全部 9 个源文件） — 修改
- `docs-stm/tools/_audit_smart.py` — 修改
- `docs-stm/tools/readability_check.py` — 修改（增强图质检查）
- `docs-stm/management/testplan.md` — 修改

**方法**：
1. **图引用一致性检查**：扫描全书，验证每张 `**图 X-Y:` 在正文中至少有 1 处 "如图 X-Y 所示" 引用（已有201处，但可能有遗漏）
2. **图注质量检查**：验证图注是否包含「主语 + 谓语 + 宾语」结构（如「B-Tree 插入过程中的节点分裂」，而非「节点分裂」）
3. **图比例检查**：对超宽图（>80 字符宽）、超高图（>40 行）标记建议拆分
4. **框线字符完整性检查**：验证 ASCII 图的框线是否闭合（┌ 有对应的 ┘ 等）
5. 修复 `_audit_smart.py`：新增图引用计数报告输出
6. 修复 `readability_check.py`：新增框线闭合验证、图注质量标记
7. 对发现问题的图逐一修复

**测试场景**：
- 全书 578 张图，每张至少 1 处正文引用
- 图注全部包含有效的动宾结构
- 零未闭合框线图

**验证**：`readability_check.py --figures` 零违规，`_audit_smart.py --reference-check` 零遗漏

### U6. 源码引用保鲜机制

**目标**：建立对 H2 源码变更的感知机制，防止行号/API/类名过时

**依赖**：无

**文件**：
- `docs-stm/tools/` — 新建 `source_freshness_check.py`
- `docs-stm/management/testplan.md` — 修改
- `docs-stm/management/plan.md` — 修改

**方法**：
1. 新建 `source_freshness_check.py`，实现以下功能：
   - 从 `docs-stm/ch*.md` 中提取所有 `ClassName.java:行号` 引用
   - 对照 `h2/src/main/` 下的实际 Java 源文件，验证行号是否仍在有效范围内（类声明行 ~ 类结束行）
   - 报告行号偏移量（当前行号 vs 源文件实际行数）
   - 报告已不存在的类/方法引用
2. 该脚本作为可选检查（非阻塞），加入 `testplan.md` 的「周期性维护」章节
3. 更新 `plan.md` 维护策略，建议每月运行一次

**测试场景**：
- 在 v4.29 基线运行，记录当前行号偏差报告
- 验证偏差报告中的假阳性率 < 10%（通过处理多文件同名类等情况）

**验证**：`python docs-stm/tools/source_freshness_check.py` 成功输出报告，无异常崩溃

---

## 五、实施顺序与依赖关系

```text
U1 术语体系完善 ──────┐
                      ├──→ U3 工具集成（依赖 U1、U2 的产出）
U2 概念索引完善 ──────┘

U4 阅读体验优化 ────── 独立，可与 U1/U2 并行

U5 图表质量提升 ────── 独立，可与 U1/U2/U4 并行

U6 源码引用保鲜 ────── 独立，可与所有单元并行（新增工具需读取 U4 修改后的文件）
```

**并行策略**：
- 第一批（并行）：U1 + U4 + U5 + U6（无相互依赖）
- 第二批（U1、U2 完成后串行启动）：U3

**工作量估算**（单 Agent 执行）：
| 单元 | 估算 | 说明 |
|------|------|------|
| U1 | 3-5 天 | 逐章扫描、补术语、增强工具 |
| U2 | 2-4 天 | 索引扩展、工具增强、集成验证 |
| U3 | 1-2 天 | 工具整合、final_check 扩展 |
| U4 | 5-8 天 | 逐章审计与修复 |
| U5 | 3-5 天 | 工具增强 + 问题图修复 |
| U6 | 1-2 天 | 新工具开发 |

采用 4 人并行 Agent 模式（与过往审查方式一致）可将总工期缩短 50-60%。

---

## 六、质量门禁

执行顺序：每完成一个 U 单元后运行标准验证流水线，所有 U 单元完成后运行全量回归。

### 6.1 标准验证流水线（每次变更后）

```bash
python docs-stm/tools/cover_stats.py
python docs-stm/tools/rebuild_merged.py
python docs-stm/tools/generate_html.py
python docs-stm/tools/_audit_smart.py
python docs-stm/tools/final_check.py
python docs-stm/tools/check_style.py
```

### 6.2 新增检查

| 新增检查 | 关联工具 | P0/P1/P2 |
|---------|---------|-----------|
| 术语表完整性（每章 ≥ 3 条） | `_annotate_terms.py --check` | P1 |
| 索引章节覆盖（每章 ≥ 5 条） | `build_index.py --coverage` | P1 |
| 索引引用有效性 | `final_check.py`（新增） | P0 |
| 术语章节标注准确性 | `final_check.py`（新增） | P1 |
| 图注引用一致性 | `_audit_smart.py` / `readability_check.py` | P1 |
| 框线闭合完整性 | `readability_check.py`（增强） | P2 |
| 段落长度（>15 行标记） | `check_style.py`（增强） | P2 |
| 源码行号保鲜 | `source_freshness_check.py` | P2 |

### 6.3 回归门禁（v5.0 交付）

- `final_check.py` ≥ 原有 82 项 + 新增检查项全部通过
- `check_style.py` 零警告
- `_audit_smart.py` 零缺图
- 术语表 ≥ 60 条
- 索引 ≥ 120 条
- 图引用一致性 ≥ 95%（允许少量过渡性图无需显式引用）

---

## 七、交付标准

### 7.1 v5.0 交付清单

| 交付物 | 状态 |
|--------|------|
| `docs-stm/back/glossary.md`（60+ 条） | 新增 |
| `docs-stm/back/index.md`（120+ 条） | 新增 |
| `docs-stm/tools/final_check.py`（90+ 检查项） | 修改 |
| `docs-stm/tools/source_freshness_check.py` | 新增 |
| `docs-stm/tools/_annotate_terms.py`（增强） | 修改 |
| `docs-stm/tools/build_glossary.py`（增强） | 修改 |
| `docs-stm/tools/build_index.py`（增强） | 修改 |
| `docs-stm/tools/readability_check.py`（增强） | 修改 |
| `docs-stm/tools/check_style.py`（可选增强） | 修改 |
| `docs-stm/management/testplan.md`（更新） | 修改 |
| `docs-stm/management/style-guide.md`（更新） | 修改 |
| `docs-stm/management/plan.md`（更新） | 修改 |
| `docs-stm/h2-source-code-analysis.md`（合并文档） | 重建 |
| `docs-stm/h2-source-code-analysis.html`（HTML） | 重建 |

### 7.2 版本命名

- 当前基線：v4.29
- 目标版本：v5.0（质量里程碑）

---

## 八、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| U4 阅读体验审计发现大量问题 | 中 | 高 — 工期超出预期 | 分层处理：P0/P1 必须修复，P2 记录待下轮 |
| 源码行号保鲜报告假阳性率高 | 高 | 中 — 工具信任度下降 | 设计时预留排除规则机制；首次运行人工审查结果 |
| 术语扫描工具误报率过高 | 中 | 中 — 需人工验证增加工作量 | 为 `_annotate_terms.py` 添加白名单/排除规则 |
| 部分章节术语覆盖不足（ch11-12 仅2章共用2314行） | 高 | 低 — 内容偏少是结构性的 | 降低 ch11-12 的术语密度要求至每章 2 条 |
| 最终回归时 final_check 扩展项与现有 82 项冲突 | 低 | 高 — 回归失败 | U3 在实施时先跑全量回归确认零退步，再添加新检查 |

---

## 九、验收检查清单

- [ ] 所有 12 章 + 附录完成 U1 术语审计
- [ ] `glossary.md` ≥ 60 条，每章 ≥ 3 条
- [ ] `index.md` ≥ 120 条，每章 ≥ 5 条
- [ ] `final_check.py` 扩展后 ≥ 原有 82 项全部通过 + 新增检查项
- [ ] `check_style.py` 零警告
- [ ] `_audit_smart.py` 零缺图
- [ ] 阅读体验审计：零 >15 行段落（代码围栏和列表除外）
- [ ] 图引用一致性 ≥ 95%
- [ ] `source_freshness_check.py` 可运行输出报告
- [ ] `testplan.md` 质量标准表与扩展后的 final_check 一致
- [ ] 流水线：cover_stats → rebuild_merged → generate_html → final_check → check_style 全通过
