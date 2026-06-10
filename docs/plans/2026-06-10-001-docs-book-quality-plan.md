# H2 源码分析文档 — 高质量中文技术书籍迭代计划

> **版本**: v1.0
> **状态**: active
> **最后更新**: 2026-06-10
> **目标**: 将现有 12 章 35,839 行中文源码分析文档提升至高质量中文技术书籍标准
> **基线与交付**: `docs-stm/h2-source-code-analysis.md` (v4.23, final_check 55/55)

---

## 问题框架

### 当前状态

H2 源码分析文档已完成 12 章内容交付（v4.23），通过全部 55 项质量门禁。文档已具备以下基础：

- ✅ 完整 12 章覆盖 H2 架构→包结构→模块流程→算法→SQL→持久化→锁→总结
- ✅ 578 幅 ASCII 示意图，185 处源码引用，28 处官方文档引用
- ✅ 标准化验证流水线（cover_stats → rebuild_merged → generate_html → _audit_smart → final_check）
- ✅ PDF 按需生成与验证
- ✅ 多轮四视角并行审查（架构师/文档工程师/程序员/图书编辑）
- ✅ 管理文档职责收敛，避免重复维护

### 提升目标

从"高质量源码分析文档"到"高质量中文技术书籍"的核心差距：

| 维度 | 当前状态 | 书籍水准目标 |
|------|----------|-------------|
| 书籍结构 | 无前言/版权/序言/后记 | 完整前件（版权页、前言、目录）、正文（标准化章节模板）、后件（术语表、索引、参考文献） |
| 章节模板 | 结构不统一：有的有小结，有的无 | 每章一致：章首引导→正文→章末小结→延展阅读→练习/思考题 |
| 术语体系 | 散落于正文，无统一索引 | 术语表（Glossary）独立成章/附录，首次出现标注 |
| 写作风格 | 部分章节口语化或中英夹杂不均 | 统一正式技术写作风格，专业准确、通顺可读 |
| 图示质量 | ASCII 图功能完整但视觉粗糙 | 关键图示提升为彩色/结构化渲染图，辅助理解 |
| 参考文献 | 仅 28 处嵌入式引用，无汇总 | 独立参考文献章节，含官方文档/论文/书籍/源码的全量引用 |
| 索引系统 | 无 | 概念索引、API 索引、算法索引三位一体 |
| 阅读导航 | 基本的跨章引用 | 阅读路线图（不同读者类型推荐路径）、知识点依赖图 |
| 排版品质 | Markdown 源→HTML/PDF，基础样式 | 专业书籍排版：章首页、页眉页脚、代码高亮、图表编号交叉引用 |

### 范围边界

**本计划覆盖：**
- 管理文档迁移至 `docs-stm/management/`
- 前件与后件体系构建
- 章节模板标准化
- 写作质量通检
- 术语体系与索引建立
- 图示质量增强
- 参考文献体系
- 排版品质提升
- 工具链配套更新

**不覆盖（显式非目标）：**
- 英文版翻译（已有 P4 规划，不在本书质量范围内）
- 交互式图表/迁移 Mermaid（已有 P3 规划，独立跟踪）
- CI 集成（已有 P4 规划，独立跟踪）
- 新增第13章或大幅重构章节结构
- Java 源码本身的修改

---

## 实施策略

### 执行顺序策略

采用**风险递进**策略，从低风险高收益开始，逐级递进到高风险高影响：

```
低风险 ●━━━━━━━━━━━━━━━━━○ 高风险
       ↓
Phase 0: 管理文档迁移 (纯文件移动，零内容风险)
Phase 1: 书籍结构体系 (新增文件，不影响现有正文)
Phase 2: 术语与索引 (工具辅助的文本增强)
Phase 3: 章节模板标准化 (影响正文结构，需逐章进行)
Phase 4: 写作质量通检 (全局搜索替换 + 人工审读)
Phase 5: 图示与参考增强 (局部增强，逐文件验证)
Phase 6: 排版品质提升 (工具链变更)
Phase 7: 全书终验 (综合验证)
```

每 Phase 完成后运行标准验证流水线，确保无回归。

---

## 高层面技术设计

### 文件结构变更

```
迁移前:                              迁移后:
docs-stm/                            docs-stm/
  cover.md         ───保持不变───       cover.md
  ch*.md           ───保持不变───       ch*.md
  h2-source-code-analysis.md  ──不变──  h2-source-code-analysis.md
  requirements.md  ──┐                  management/
  plan.md          ──┤                  ├── requirements.md
  testplan.md      ──┤ 迁移至            ├── plan.md
  changelog.md     ──┤ management/      ├── testplan.md
  review-findings.md ─┘                 ├── changelog.md
  tools/           ───保持不变───       ├── review-findings.md
                                       └── README.md (新增: 管理文档索引)
  front/           (新增)               tools/          (保持不变)
  ├── preface.md                       front/
  ├── copyright.md                     ├── preface.md
  └── how-to-read.md                   ├── copyright.md
  back/            (新增)               └── how-to-read.md
  ├── glossary.md                      back/
  ├── references.md                    ├── glossary.md
  └── index.md                         ├── references.md
                                       └── index.md
```

### 流水线更新

标准流水线加入新的验证步骤：

```bash
# 当前 (v4.23):
cover_stats.py → rebuild_merged.py → generate_html.py → _audit_smart.py → final_check.py

# 目标 (v4.24+):
cover_stats.py → rebuild_merged.py → generate_html.py → _audit_smart.py
  → build_glossary.py (新增) → build_index.py (新增) → final_check.py
```

### 章节模板标准化

每章统一结构：

```text
# 第N章 章节标题

> **本章导读**: 2-3 句概述本章内容和前置知识。
> **前置知识**: 需要先阅读的章节。
> **章节要点**: 读者读完本章后将理解的内容列表。

[正文内容...现有内容不动...]

## N.x 本章小结

[归纳核心观点、关键设计和学习要点]

## N.x 延展阅读

- 官方文档链接
- 本书其他章节交叉引用
- 外部参考资料

## N.x 思考与练习 (可选)

1. [基于本章内容的思考题]
2. [动手实践建议]
```

---

## 实施单元

---

### U0. 管理文档迁移至 docs-stm/management/

- **目标**: 将 5 个管理文档从 `docs-stm/` 根目录迁移到 `docs-stm/management/`，保持所有引用链完整
- **需求**: 用户明确要求；这是后续所有变更的基础清理
- **依赖**: 无

**文件:**
- `docs-stm/management/requirements.md` (从 `docs-stm/requirements.md` 迁移)
- `docs-stm/management/plan.md` (从 `docs-stm/plan.md` 迁移)
- `docs-stm/management/testplan.md` (从 `docs-stm/testplan.md` 迁移)
- `docs-stm/management/changelog.md` (从 `docs-stm/changelog.md` 迁移)
- `docs-stm/management/review-findings.md` (从 `docs-stm/review-findings.md` 迁移)
- `docs-stm/management/README.md` (新增：管理文档索引)
- `CLAUDE.md` (更新管理文档路径引用)
- `docs-stm/tools/rebuild_merged.py` (验证：合并文档需排除 management/ 目录)
- `docs-stm/tools/final_check.py` (验证：管理文档检查路径更新)

**方法:**
1. 创建 `docs-stm/management/` 目录
2. 移动 5 个管理文档到该目录
3. 创建 `management/README.md` 索引各文档职责和关系
4. 更新 `CLAUDE.md` 中的文档布局和管理文档权威说明中的路径
5. 更新 `requirements.md` §2 交付物表中的管理文档路径
6. 更新 `plan.md` §2 正式目录中的路径
7. 验证 `rebuild_merged.py` 排除 `management/` 目录（管理文档不应进入合并文档）
8. 验证 `cover_stats.py` 不将管理文档计入统计数据
9. 运行标准验证流水线确认无回归

**测试场景:**
- Happy path: 迁移后标准流水线全部通过 (final_check 55/55)
- Integration: 合并文档行数在迁移前后不变（管理文档不被合并）
- Integration: `cover_stats.py` 统计不受管理文档迁移影响
- Error: 无 — 纯文件操作

**验证:** `python docs-stm/tools/final_check.py` 全部通过；合并文档行数不变；`CLAUDE.md` 中无旧路径引用残留

---

### U1. 书籍前件体系（前言/版权/阅读指南）

- **目标**: 为全书增加正式技术书籍的前件内容：版权页、前言（序）、阅读指南
- **需求**: 专业书籍必须有正式前件
- **依赖**: 无

**文件:**
- `docs-stm/front/copyright.md` (新增：版权页、许可证声明、版本信息)
- `docs-stm/front/preface.md` (新增：前言 — 写作动机、目标读者、内容概要、致谢)
- `docs-stm/front/how-to-read.md` (新增：阅读指南 — 读者类型推荐路径、前置知识依赖图)
- `docs-stm/tools/rebuild_merged.py` (更新：合并顺序加入 front/ 内容)
- `docs-stm/cover.md` (可选：更新版本号信息)

**方法:**
1. 创建 `docs-stm/front/` 目录
2. `copyright.md`: 注明项目许可证（Apache 2.0）、版本号、免责声明、源码出处
3. `preface.md`: 撰写 ~500-800 字前言，包含写作动机、目标读者（H2 使用者/贡献者/数据库学习者）、全书内容鸟瞰、致谢
4. `how-to-read.md`: 设计阅读路线图：
   - 对 SQL 用户（快速理解架构→SQL 执行→优化器）
   - 对贡献者（架构→包结构→模块流程→算法→持久化）
   - 对学生/学习者（按章节顺序全读）
   - 以依赖图形式呈现章节间的前置关系
5. 更新 `rebuild_merged.py` 的 cat 顺序：`front/*.md → cover.md → ch*.md`
6. 运行标准验证流水线

**测试场景:**
- Happy path: 合并文档正确包含 front/ 内容，位于 cover.md 之前
- Edge: front/ 目录缺文件时合并脚本优雅处理
- Integration: HTML TOC 正确展示前言/版权/阅读指南条目

**验证:** 合并文档开头包含前言/版权/阅读指南；HTML 正确渲染封面后的前件页面；final_check 全部通过

---

### U2. 书籍后件体系（术语表/参考文献/索引）

- **目标**: 为全书增加正式后件：术语表（Glossary）、参考文献（Bibliography）、概念索引
- **需求**: 专业书籍必须有术语体系和引用索引
- **依赖**: U1（后件依赖合并后的前件顺序，但内容独立）

**文件:**
- `docs-stm/back/glossary.md` (新增：术语表，含中文术语、英文原文、简要定义、首次出现章节)
- `docs-stm/back/references.md` (新增：参考文献，含官方文档/论文/书籍/源码的完整引用)
- `docs-stm/back/index.md` (新增：概念索引，关键术语→章节映射)
- `docs-stm/tools/rebuild_merged.py` (更新：合并顺序加入 back/ 内容)
- `docs-stm/tools/build_glossary.py` (新增：术语表生成辅助脚本)
- `docs-stm/tools/build_index.py` (新增：索引生成辅助脚本)

**方法:**
1. 创建 `docs-stm/back/` 目录
2. `glossary.md`: 收录全书核心术语 ~80-120 条，格式：
   ```markdown
   ## A
   - **ACID**: Atomicity, Consistency, Isolation, Durability — 数据库事务四大特性（第10章）
   - **Append-Only**: 仅追加写入策略，MVStore 的核心写入模式（第9章）
   ```
3. `references.md`: 分类整理引用：
   - H2 官方文档（architecture.html, mvstore.html, advanced.html, performance.html, security.html, features.html, tutorial.html）
   - 学术论文（B-Tree, LIRS, MVCC 等原始论文引用）
   - 技术参考（Java NIO, FileChannel 等 JDK 文档）
   - 对比数据库（SQLite, Derby, HSQLDB 官方引用）
4. `index.md`: 提取关键概念、API 类名、算法名→章节映射
5. `build_glossary.py`: 辅助脚本，从正文提取 `**术语**` 模式生成初步术语表草稿
6. `build_index.py`: 辅助脚本，扫描全书 H3/H4 标题和 `**术语**` 模式，生成概念→章节对应关系
7. 更新 `rebuild_merged.py` 的 cat 顺序，后件放在所有 chapter 之后
8. 运行标准验证流水线

**测试场景:**
- Happy path: 合并文档正确包含 back/ 内容
- Integration: build_glossary.py 输出非空术语表
- Integration: build_index.py 正确统计关键术语频次和章节分布
- Edge: 索引条目指向的章节锚点在合并文档中存在

**验证:** 合并文档末尾包含术语表/参考文献/索引；HTML 可导航到后件页面；所有索引锚点有效

---

### U3. 章节模板标准化

- **目标**: 为全部 12 章（跨 9 个源文件）建立一致的章节模板：章首引导+正文+章末小结+延展阅读
- **需求**: 专业技术书籍要求一致的章节结构，提升可读性和专业性
- **依赖**: 无；可与 U1/U2 并行

**文件:**
- `docs-stm/ch1-2-architecture.md`
- `docs-stm/ch3-packages.md`
- `docs-stm/ch4-5-modules-processes.md`
- `docs-stm/ch6-1-data-structures.md`
- `docs-stm/ch6-2-storage-algorithms.md`
- `docs-stm/ch6-3-query-algorithms.md`
- `docs-stm/ch7-8-sql-optimizer.md`
- `docs-stm/ch9-10-persistence-locking.md`
- `docs-stm/ch11-12-guide-summary.md`
- `docs-stm/tools/final_check.py` (可选：新增章节模板一致性检查)

**方法:**
逐章检查并补充以下内容（仅添加，不改动现有正文）：

1. **章首引导块**: 每章第一段正文之前插入标准引导块：
   ```markdown
   > **本章导读**: 本章深入分析 H2 的 [主题]。[2-3 句内容概述]。
   > **前置知识**: 第X章《...》、第Y章《...》
   > **章节要点**:
   > - 理解 [核心概念1]
   > - 掌握 [核心流程2]
   > - 熟悉 [关键实现3]
   ```

2. **章末小结**: 对有章末小结的章节（ch4-5, ch6-1, ch6-2, ch6-3, ch7-8, ch9-10, ch11-12）审核并补充；对无小结的章节（ch1-2, ch3）新增。

3. **延展阅读**: 每章末尾新增 `## N.x 延展阅读` 小节，引用：
   - H2 官方文档对应章节
   - 本书其他关联章节
   - 外部参考书籍/论文

4. **章节模板一致性检查**（可选）：在 `final_check.py` 中新增可选规则，验证每章是否包含引导块和小结。

**测试场景:**
- Happy path: 所有 12 章具有一致的引导+小结+延展阅读
- Edge: ch6 跨 3 个文件但逻辑上是一章 — 引导块放在 ch6-1 开头，小结放在 ch6-3 末尾
- Edge: ch4-5 和 ch9-10 包含两章内容 — 每章应有独立的引导块和小结
- Edge: ch11-12 作为导读总结章，引导块应反映其全书定位

**验证:** 各章首部有 `> **本章导读**` 块；各章末尾有 `## N.x 本章小结` 和 `## N.x 延展阅读`；`grep -c '本章导读'` 与总章数匹配

---

### U4. 写作质量通检（风格与术语）

- **目标**: 全书正式技术写作风格统一，术语一致，消除口语化表达和中英夹杂不均
- **需求**: 高质量技术书籍要求统一的正式写作风格
- **依赖**: U3（建议在模板标准化后进行，避免重复工作）

**文件:**
- 全部 9 个源章节文件 (`docs-stm/ch*.md`)

**方法:**
分三个子阶段进行：

1. **术语一致性审计**（工具辅助）:
   - 扫描全书使用 `grep` 提取术语使用模式
   - 对照官方文档建立统一术语表（参考 v4.23 Task 6 已完成的基础）
   - 检查重点：
     - `chunk` vs `Chunk` 大小写一致性
     - `MVStore` vs `MvStore` vs `mvstore`
     - `page` vs `Page` vs `页面`
     - `undo log` vs `Undo Log` vs `撤消日志`
     - `B-Tree` vs `BTree` vs `B树`
     - 正式全称首次出现时标注英文原文（如"写时复制（Copy-on-Write, COW）"）
   - 搜索替换修复发现的不一致

2. **写作风格审计**（人工审读，逐章进行）:
   - 消除口语化表达（"我们来看"→"本节分析"、"说白了"→移除或替换）
   - 统一说明性段落句式
   - 确保每个技术论断都有出处（源码引用或官方文档）
   - 检查句子长度：技术书籍中文建议 ≤40 字/句
   - 消除不必要的英文夹杂（已有中文术语时不重复英文）

3. **代码注释风格统一**:
   - 确保所有 Java 代码块有适当的源码位置标注（`// org/h2/...java:行号`）
   - 确保伪代码块有 ````text 围栏
   - 超长代码块（>40 行）考虑截断或添加"省略非关键代码"说明

**测试场景:**
- Happy path: 全书术语一致，风格统一
- Regression: 修复后 final_check 全部通过
- Edge: 官方文档与本书用词存在合理差异时保留本书风格，但标注（如"官方术语为 X，本书简称为 Y"）

**验证:** 术语扫描无显著不一致；口语化表达数量降为零；`final_check` 全部通过

**执行说明:** 本单元最适合采用 TDD 式检查：先编写风格检查规则脚本、再逐章修复

---

### U5. 图示质量增强

- **目标**: 提升关键示意图的视觉质量，确保每幅图都能有效传达技术概念
- **需求**: 580+ 幅 ASCII 图功能完整但视觉上离书籍标准有差距
- **依赖**: 无

**方法:**
1. **图注格式审计**: 确认所有图注格式统一为 `**图 X-Y: Title**`（v4.19 已大部分完成，但做最终确认）
2. **关键图升级**: 对以下类型图评估是否需要增强：
   - 全书架构总览图（图 1-4 八层架构）：考虑拆分为多幅或添加标注
   - 核心流程图（图 4-1~4-52, 5-1~5-46）：评估流程标注完整性
   - 算法示意图（ch6 系列）：评估是否补充中间状态图
3. **新增辅助图**: 对以下可能缺图的小节补充辅助图：
   - v4.20 已补充 111 个非编号辅助图，运行 `_audit_smart.py` 确认零缺图
   - 对 _audit_smart 报告的任何新的缺图警告逐一修复
4. **图注引用审计**: 确认每幅图的正文中都有"如图 X-Y 所示"的引用（v4.19 H-3 已修复 201 处，再确认无遗漏）

**注意**: 本单元的增强重点是内容完整性，而非 ASCII 图视觉升级。ASCII→Mermaid/彩色图迁移已标记为 P3 独立跟踪。

**测试场景:**
- Happy path: `_audit_smart.py` 报告零缺图
- Integration: 图号全局唯一、连续（`final_check.py` 验证）
- Edge: 新增图不引发图号冲突

**验证:** `_audit_smart.py` 零警告；`final_check.py` 图号检查通过

---

### U6. 交叉引用与导航增强

- **目标**: 全书交叉引用全面、准确，提供多种导航路径
- **需求**: 高质量技术书籍要求读者能在章节间自如跳转
- **依赖**: U3, U4（建议先完成章节模板和写作通检再做引用增强）

**方法:**
1. **引用完整性审计**:
   - 提取所有 `详见第X章《...》` 模式，验证章节号和 H1 标题一致（v4.23 已部分完成，做全面审计）
   - 对不存在的引用目标进行修复
   - 对缺少引用的关键概念补充"详见第X章《...》"引用

2. **前向与后向引用**: 
   - 对重要概念，同时标注"将在第X章详细讨论"（前向）和"详见第X章"（后向）
   - 确保章首引导中的"前置知识"引用指向正确的章节
   - 确保章末延展阅读包含双向引用

3. **引用链接验证**: 在 HTML 中验证所有 `详见第X章` 的锚点可点击跳转（通过 `final_check.py` 已有检查）

**测试场景:**
- Happy path: 所有 `详见第X章《...》` 引用指向正确的 H1 标题且锚点有效
- Edge: 跨 3 个文件的第6章引用统一目标
- Integration: HTML 中所有交叉引用锚点无断链

**验证:** `grep '详见第'` 人工抽检 20% 条目；HTML 交叉引用链接可跳转

---

### U7. 参考文献体系与引用规范化

- **目标**: 建立全书的引用规范，将所有引用统一到标准格式，并汇总为参考文献章节
- **需求**: 专业书籍需要规范的引用体系和汇总参考文献
- **依赖**: U2（参考文献章节属于后件）

**文件:**
- `docs-stm/back/references.md` (已在 U2 创建，此处完善)
- 全部 9 个源章节文件 (`docs-stm/ch*.md`)

**方法:**
1. **引用格式标准化**: 将书中现有的各种引用统一为标准格式：
   - 官方文档引用: `> **参考**: H2 官方文档《标题》(`path`)`（v4.23 已完成 28 处）
   - 源码引用: `org/h2/...java:行号`（已规范）
   - 论文引用: `[作者, 年份]` 格式，如 `[Bayer&McCreight, 1972]`
   - 书籍引用: `[作者, 书名]` 格式
2. **参考文献收集**: 整理书中有引用的所有来源，归入 `references.md`
3. **交叉验证**: 确保 `references.md` 中的每条引用在正文中至少有 1 处使用

**测试场景:**
- Happy path: references.md 与正文引用 1:1 覆盖
- Edge: 正文引用标记与参考文献条目一一对应
- Edge: 无虚假引用（references.md 中的条目在正文均可找到）

**验证:** 参考文献条目数 ≥ 正文中独立引用源数；`references.md` 中每个条目在正文有对应引用

---

### U8. 排版品质提升（HTML/PDF）

- **目标**: 提升 HTML 和 PDF 的阅读体验，接近专业技术书籍排版水平
- **需求**: 最终交付物须具备专业排版品质
- **依赖**: U0-U7 全部完成（这是最终呈现层优化）

**文件:**
- `docs-stm/tools/generate_html.py` (更新：排版增强)
- `docs-stm/tools/generate_pdf.py` (更新：PDF 排版增强)
- `docs-stm/tools/final_check.py` (更新：新增排版检查项)

**方法:**
1. **HTML 排版增强**:
   - 章首页样式：每章开头添加 decorative 分隔，突出章标题
   - 代码块增强：行号显示、语法高亮优化、复制按钮
   - 表格样式优化：斑马纹、响应式
   - 图注样式优化：与正文视觉区隔
   - 导航增强：面包屑导航、上一章/下一章按钮
   - 打印样式优化（`@media print` 规则）

2. **PDF 排版增强**:
   - 章首页设计：独立的章标题页（与正文分页）
   - 页眉页脚：章标题 + 页码
   - 代码块分页控制（避免代码块跨页断裂）
   - 图片分页控制
   - 目录页排版优化

3. **排版检查项**:
   - 在 `final_check.py` 中新增：CSS 样式完整性检查
   - HTML 渲染可用性检查（非阻塞，提示级）

**测试场景:**
- Happy path: HTML 排版增强后无功能性回归
- Integration: HTML TOC 仍为 0 断链
- Integration: PDF 验证三步通过（generate_pdf → add_pdf_toc_links → verify_pdf）
- Edge: 长代码块在 PDF 中正确处理分页
- Visual: 章首页在 HTML/PDF 中正确渲染

**验证:** `final_check.py` 全部通过；PDF 三步验证通过；人工抽查 HTML/PDF 排版效果

---

### U9. 全书终验与 v4.24 发布

- **目标**: 所有变更完成后进行全面验证，生成最终产物，发布 v4.24
- **依赖**: U0-U8 全部完成

**方法:**
1. **全量验证流水线**:
   ```bash
   python docs-stm/tools/cover_stats.py
   python docs-stm/tools/rebuild_merged.py
   python docs-stm/tools/generate_html.py
   python docs-stm/tools/_audit_smart.py
   python docs-stm/tools/build_glossary.py  # 新增
   python docs-stm/tools/build_index.py     # 新增
   python docs-stm/tools/final_check.py
   ```
2. **PDF 验证**（按需）:
   ```bash
   python docs-stm/tools/generate_pdf.py
   python docs-stm/tools/add_pdf_toc_links.py
   python docs-stm/tools/verify_pdf.py
   ```
3. **统计数据校验**: cover.md 版本号、行数、图数、引用数与实际一致
4. **管理文档同步**: 所有管理文档版本号统一为 v4.24
5. **git 提交**与打标签

**测试场景:**
- Integration: 标准流水线全部通过
- Integration: 合并文档行数 = 各源文件行数和
- Integration: HTML TOC 与标题数 1:1
- Integration: PDF 验证通过
- Acceptance: cover.md 统计数据与实际一致

**验证:** final_check 全部通过；管理文档版本一致；cover.md 统计准确

---

## 风险与应对

| 风险 | 影响面 | 可能性 | 应对 |
|------|--------|--------|------|
| 管理文档迁移后引用断裂 | U0 | 低 | 迁移后立即运行验证流水线；grep 搜索所有旧路径引用 |
| 章节模板标准化引入格式错误 | U3 | 中 | 逐章进行，每章后运行验证流水线 |
| 写作通检导致大量格式冲突 | U4 | 中 | 使用 grep 批量替换而非逐处修改；替换后验证围栏平衡 |
| 新增工具脚本与现有流水线冲突 | U2 | 低 | 新脚本独立验证后才接入主流水线 |
| 排版修改需要 CSS/HTML 专业知识 | U8 | 中 | 增量修改，每次生成 HTML 后人工预览确认 |
| 工作量超出预期 | 全部 | 高 | 按优先级分类（P0-P2），严格截止 P0 核心项目 |
| 章节模板定义与现有内容结构冲突 | U3 | 中 | 引导块和小结只做**添加**，不改变现有正文结构；若冲突则灵活调整 |

## 依赖关系

```
U0 (管理文档迁移) ── 与 U1/U2/U3/U5 等无内容依赖，可并行执行

U1 (前件) ──┐
U2 (后件) ──┤  (U1→U2: rebuild_merged.py 需先加 front/ 再加 back/)
U3 (模板) ──┤
U5 (图示) ──┤  (可并行)
            │
U4 (写作通检) ── 建议 U3 之后
U6 (引用增强) ── 建议 U3+U4 之后
U7 (参考文献) ── U2 之后
U8 (排版品质) ── 所有内容变更完成后
U9 (终验)    ── 所有完成后
```

推荐执行顺序：**U0 → (U1 ∥ U2 ∥ U3 ∥ U5) → U4 → U6 → U7 → U8 → U9**

---

## 预期产出

| 度量 | v4.23 (当前) | v4.24 (目标) | 变化 |
|------|-------------|-------------|------|
| 章节数 | 12 章 | 12 章 | — |
| 源文件行数 | ~35,839 | ~37,500 | +~1,700 行（前/后件 + 模板新增） |
| ASCII 图数 | 578 | 585+ | +~7 图 |
| 源码引用 | 185 | 190+ | +~5 处 |
| 官方文档引用 | 28 | 35+ | +~7 处 |
| 术语表 | 无 | ~100 条 | **新增** |
| 概念索引 | 无 | ~200 条目 | **新增** |
| 参考文献 | 无 | ~30 条 | **新增** |
| 前言/版权/阅读指南 | 无 | 3 文件 | **新增** |
| 管理文档目录 | `docs-stm/` | `docs-stm/management/` | **迁移** |
| 章节模板一致性 | 不统一 | 12 章全部统一 | **增强** |
| final_check | 55/55 | 58+/58+ | +3+ 项（新增检查） |
| PDF 验证 | 通过 | 通过 | 维持 |
| 新增工具脚本 | — | 2-3 个 | build_glossary, build_index |

---

## 开放问题

1. **前件顺序**: 合并文档中 front/ 内容的排列顺序应为 `copyright → preface → how-to-read → cover → 正文` 还是 `preface → copyright → how-to-read → cover → 正文`？前者更正式，后者更常见于技术书籍。
   - **计划期间决策**: 暂定 `preface → copyright → how-to-read → cover.md → 正文`，执行时按实际情况调整。

2. **索引粒度**: 索引应细到什么级别？H3 小节级别足够还是需要 H4 子节级别？
   - **计划期间决策**: 以 H3 为主，对重要 API/算法增加 H4 级别索引。执行时以 `build_index.py` 实际输出决定。

3. **思考与练习**: 是否添加练习/思考题？考虑到本书是分析文档而非教材，思考题可能超出范围。
   - **计划期间决策**: 标记为可选（每章末尾 `## N.x 思考与练习`），执行时按章节特性决定是否添加。U3 (模板标准化) 中不强制要求。

4. **章节模板与现有内容的兼容性**: ch6 跨 3 个文件，模板的"本章小结"和"延展阅读"应放在 ch6-3 末尾（逻辑上的第6章结尾）还是 3 个文件各自有小结？
   - **计划期间决策**: 引导块放在 ch6-1 开头，延展阅读放在 ch6-3 末尾，三篇中间的过渡靠文件间的衔接段落（已有）维持。

---

## 来源与研究

- `docs-stm/management/requirements.md` — 当前需求定义
- `docs-stm/management/plan.md` — 当前实施计划，含 §7 后续增强项
- `docs-stm/management/testplan.md` — 当前质量门禁
- `docs-stm/management/changelog.md` — 版本历史（v1.0-v4.23）
- `docs-stm/management/review-findings.md` — 4 轮审查问题追踪
- `docs-stm/cover.md` — 当前统计数据
- `CLAUDEMD` — 项目工作流与文档规范
- `docs/superpowers/plans/2026-06-09-h2-doc-quality-enhancement.md` — 上一轮质量提升计划（v4.23 已执行）
