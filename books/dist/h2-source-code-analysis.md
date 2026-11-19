---

**版权信息**

本书是对 H2 Database（v2.4.249-SNAPSHOT）Java 源码的分析文档。

**作者**: 其·龙（Stallman Wang）  
**联系邮箱**: [stallman.wang@foxmail.com](mailto:stallman.wang@foxmail.com)

**H2 Database** 采用 Mozilla Public License 2.0（MPL 2.0）开源许可证发布。本书的分析内容基于 H2 源码，遵循 MPL 2.0 许可证的条款。

**本书版本**: v5.6 · 2026-06-15  
**源码版本**: H2 Database 2.4.249-SNAPSHOT  
**源码地址**: https://github.com/h2database/h2database

**免责声明**: 本书为技术分析文档，所描述的实现细节和分析结论基于特定版本源码。H2 Database 及其商标归其各自所有者所有。本书作者不对文档中可能存在的技术错误或遗漏承担责任。

---

# 阅读指南

## 章节依赖关系

本书各章节之间存在前置知识依赖。以下示意图展示了建议的阅读路径：

```text
                        ┌─────────────────┐
                        │  第1章 H2 概述    │
                        │  第2章 分层架构    │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
             ┌──────┴──────┐          ┌───────┴────────┐
             │  第3章 包结构 │          │  第7章 SQL 执行  │
             └──────┬──────┘          │  第8章 查询优化   │
                    │                  └───────┬────────┘
             ┌──────┴──────┐                   │
             │ 第4-5章 流程  │                  │
             └──────┬──────┘                   │
                    │                          │
          ┌─────────┴──────────┐               │
          │                    │               │
   ┌──────┴──────┐    ┌───────┴───────┐       │
   │ 第6章 算法    │    │ 第9章 持久化   │       │
   │(10 个算法)   │    │ 第10章 锁     │◄──────┘
   └──────┬──────┘    └───────┬───────┘
          │                    │
          └────────┬───────────┘
                   │
          ┌────────┴────────┐
          │ 第11章 开发指南   │
          │ 第12章 总结      │
          └────────┬────────┘
                   │
          ┌────────┴──────────┐
          │ 附录 A 端到端案例   │
          │ 附录 B 版本变更说明 │
          │ 附录 C 术语表       │
          │ 附录 D 概念索引     │
          │ 附录 E 参考文献     │
          └───────────────────┘
```

## 读者画像

不同读者对本书的需求不同。下表勾勒 4 类典型读者画像，并指出各自最快进入价值的章节入口。

| 画像 | 描述 | 主要诉求 | 推荐入口 |
|------|------|---------|---------|
| **H2 用户** | 在生产或开发环境使用 H2 已 6 个月以上，熟悉常用 SQL 与 JDBC 接口，但对 H2 内部机制不了解 | 排查性能问题、理解配置参数背后的机制、避免常见使用陷阱 | §1.1 + §2.1-2.3 + §7.1-7.2 + §8.4 |
| **数据库内核学习者** | 计算机本科或研究生，正在学习数据库实现原理，希望通过真实开源项目巩固理论 | 完整理解一个 DBMS 的所有子系统及其交互 | 通读全书 + 附录 A 案例研究 |
| **H2 贡献者** | 准备向 H2 提交 PR 或定制内部分支的开发者 | 快速定位代码、理解架构边界、避免破坏现有契约 | §1-2 + §3 + 按需读 §4-10 + §11 |
| **Java 系统设计爱好者** | 关注高性能、高并发系统设计的资深 Java 开发者，并不一定准备写数据库 | 学习日志结构存储、无锁并发、缓存策略等通用设计模式 | §6.2-6.7 + §9 + §10 + §6.5 |

## 章节先决条件矩阵

每章的实际阅读门槛可分为"前置章节"（本书内）与"前置外部知识"（本书外）两类。下表给出每章的具体要求，并标注哪些章节可以**安全跳过**。

| 章节 | 前置章节 | 前置外部知识 | 可跳过条件 |
|------|----------|-------------|-----------|
| 第1章 | 无 | 数据库基本概念 | 已熟悉 H2 历史与基本特性 |
| 第2章 | 第1章 | 软件分层架构概念 | 不可跳过——后续多章引用 |
| 第3章 | 第2章 | Java 包与类的组织 | 仅作为参考字典查阅时可跳过通读 |
| 第4-5章 | 第2、3章 | Java 集合与并发原语 | 仅关注存储引擎或算法时可只读 §4.6 |
| 第6章 | 第2章 | 数据结构基础（树、哈希、图） | 仅关注 SQL 流程时可只读 §6.1-6.3、§6.10 |
| 第7章 | 第4-5章、第6.10节 | SQL 语法基础 | 仅关注存储引擎时可跳过 |
| 第8章 | 第7章、第6.8节 | 查询代价模型概念 | 仅关注存储或并发时可跳过 |
| 第9章 | 第6.1-6.7节 | 文件 I/O 基础 | 仅关注 SQL 处理时可跳过 |
| 第10章 | 第6.3节、第9章 | 并发控制基础概念 | 仅做单线程嵌入式使用时可跳过 |
| 第11章 | 第1-3章 | Java 调试与测试基础 | 仅做架构理解时可跳过 |
| 第12章 | 全书 | 无 | 不可跳过——总览价值高 |
| 附录 A | 第1-10章 | 无 | 单独阅读价值有限，建议在通读后阅读 |
| 附录 B | 第9-10章 | 无 | 仅在跨小版本对照源码差异时需要参阅 |
| 附录 C | 无 | 无 | 术语速查工具，按需使用 |
| 附录 D | 无 | 无 | 概念位置索引，按需使用 |
| 附录 E | 无 | 无 | 延伸阅读资料，按需使用 |

## 推荐阅读路径

下面给出 5 条阅读路径，每条对应不同目标读者画像与目标深度。读者可按目标选择，也可灵活组合。

### 路径 A：快速上手（适合 H2 用户/集成者）

**目标**：在最短时间内理解 H2 的核心架构和使用要点。

1. 第1章 §1.1-1.2 — H2 概述与架构总览
2. 第2章 §2.1-2.3 — 接入层与引擎层
3. 第7章 §7.1-7.2 — SELECT/INSERT/UPDATE/DELETE 执行流程
4. 第8章 §8.4 — 执行计划分析
5. 第12章 §12.2 — H2 与其他数据库的对比

**预计阅读时间**：约 1-2 小时。

### 路径 B：全面掌握（适合数据库学习者）

**目标**：系统理解 H2 的完整实现。

按章节顺序通读第1章至第12章，最后阅读附录 A 端到端案例研究以串联全书。每个算法章节（第6章）建议对照源码文件进行阅读。

**预计阅读时间**：约 8-12 小时。

### 路径 C：开发者视角（适合 H2 贡献者/定制者）

**目标**：获得修改和扩展 H2 所需的知识。

1. 第1-2章 — 理解整体架构
2. 第3章 — 掌握包结构和类职责
3. 第4-5章 — 理解核心流程
4. 按需选择以下深度阅读方向：
   - SQL 相关 → 第7-8章
   - 存储引擎 → 第6章 §6.1-6.7 + 第9章
   - 并发控制 → 第10章
5. 第11章 — 调试环境与测试框架
6. 附录 A — 选择与目标领域最相关的案例

**预计阅读时间**：取决于关注领域，每个深度方向约 2-4 小时。

### 路径 D：MVStore 内核研究

**目标**：专精 H2 的存储引擎，把它当作日志结构存储的学习样本。

1. 第1章 §1.1 — H2 与 MVStore 的历史关系
2. 第2章 §2.9-2.10 — 存储抽象层与文件系统层
3. 第6章 §6.2-6.7 — Copy-on-Write、MVCC、Chunk、LIRS、FreeSpace、MVStore 平衡
4. 第9章 — 持久化引擎全章
5. 第10章 §10.4 — MVCC 实现细节
6. 附录 A 案例 C — 一次崩溃恢复

**预计阅读时间**：约 4-6 小时。

### 路径 E：查询优化器深度

**目标**：专精 H2 的 SQL 处理与查询优化，理解一个完整 CBO 的实现。

1. 第6章 §6.10 — Parser 递归下降解析
2. 第6章 §6.8 — Optimizer 算法
3. 第7章 — SQL 执行全流程
4. 第8章 — 查询优化器深度解读全章
5. 附录 A 案例 A — 一条 SELECT 从 JDBC 到磁盘

**预计阅读时间**：约 3-5 小时。

## 章节估读时长

下表给出每章的参考阅读时长。估算基准：纯阅读速度按 1 行/3 秒计，图表按每张额外 30 秒，源码对照按每条引用额外 1 分钟。读者可按自身节奏调整。

| 章节 | 行数 | 图数 | 源引用 | 估读时长 |
|------|------|------|--------|---------|
| 第1-2章 | 2,157 | 32 | 7 | 约 110 分钟 |
| 第3章 | 2,262 | 53 | 18 | 约 130 分钟 |
| 第4-5章 | 3,893 | 105 | 86 | 约 270 分钟 |
| 第6.1节（数据结构） | 2,841 | 23 | 25 | 约 165 分钟 |
| 第6.2节（存储算法） | 4,618 | 44 | 9 | 约 260 分钟 |
| 第6.3节（查询算法） | 3,503 | 39 | 1 | 约 200 分钟 |
| 第7章 | 3,642 | 81 | 10 | 约 235 分钟 |
| 第8章 | 4,443 | 100 | 9 | 约 280 分钟 |
| 第9-10章 | 6,566 | 76 | 19 | 约 390 分钟 |
| 第11-12章 | 2,389 | 26 | 1 | 约 135 分钟 |
| 附录 A | ~1,200 | ~16 | — | 约 70 分钟 |
| 附录 B | ~50 | — | — | 约 5 分钟 |
| 附录 C | ~600 | — | — | 速查为主 |
| 附录 D | ~580 | — | — | 速查为主 |
| 附录 E | ~70 | — | — | 速查为主 |
| **全书** | **~37,500** | **~595** | **185** | **约 38 小时** |

精读全书约 38 小时；按路径 A 快速通读约 1-2 小时；按路径 B 主线通读约 8-12 小时。

## 阅读建议

- 本书包含 578+ 幅 ASCII 示意图。这些图是理解技术概念的重要辅助，建议不要跳过。
- 第6章是全书最长的章节（跨 3 个文件），包含 10 个独立的算法分析。可以按兴趣分次阅读。
- 第9-10 章（持久化与锁）和第7-8 章（SQL 执行）之间存在交叉引用关系，建议先后连续阅读。
- 每章末尾的「延伸思考」（v6.0 起加入）是引导读者将本章知识转化为可应用思维的工具，配合「延展阅读」中的官方文档与外部参考链接使用效果最佳。
- 附录 A 的端到端案例建议在通读完第1-10章后阅读——它把分散在各章的步骤按时间顺序串成主线，能在很短时间内帮助读者建立对 H2 整体行为的直观理解。
- 配合源码阅读时推荐使用 IntelliJ IDEA 或 Eclipse 等支持"按行号跳转"的 IDE，可极大提升源码引用的查阅效率。
# 前言

## 写作动机

H2 Database 是一个纯 Java 实现的嵌入式关系数据库，以其小巧（核心 JAR 约 2MB）、快速、功能完整而闻名。在软件开发领域，H2 被广泛用于单元测试、开发环境、嵌入式应用和轻量级数据存储场景，是 Java 生态中最受欢迎的嵌入式数据库之一。然而，H2 的源码实现长期以来缺乏系统化的中文分析资料——开发者们能熟练使用 H2 的各种特性，却对其内部的架构设计、存储引擎、查询优化和并发控制机制缺乏深入理解。

本书的写作动机正是填补这一空白。我们相信，深入理解 H2 的源码实现不仅有助于读者更高效地使用 H2，更能从中汲取优秀的系统设计经验——MVStore 存储引擎是日志结构存储（Log-Structured Storage）在 Java 环境中的杰出实践，其 B-Tree 与 Copy-on-Write 的结合方式、LIRS 缓存替换策略、递归下降解析器实现等，都是极具学习价值的设计范例。

## 为什么写这本书

H2 项目自 2004 年由 Thomas Mueller 创立以来，始终保持小而精的代码风格。整个核心引擎不足 23 万行 Java 代码，却完整实现了 SQL 标准的大部分语法、ACID 事务、MVCC 并发控制、B-Tree 索引、查询优化器和持久化引擎。这种"麻雀虽小，五脏俱全"的工程美学，使 H2 成为学习数据库内核的理想样本——读者无需在数百万行代码中迷失，就能完整观察一个生产级数据库的全貌。

然而，理想的样本也需要合适的导览。市面上中文数据库内核书籍主要聚焦于 PostgreSQL、MySQL/InnoDB 这类大型系统，篇幅动辄千页，且默认读者已有相当数据库实现基础。对希望"先看一个完整的小系统再学复杂系统"的读者而言，缺少一本中等深度、源码对应清晰、语言友好的导引材料。

本书与官方文档的差异同样值得说明：H2 官方文档（h2database.com/html）以**用户视角**为主，重点是 SQL 兼容性、安装配置、参数说明和常见问题解答。本书则以**实现者视角**切入，回答"H2 在底层如何做到这件事"的问题——为什么选 MVStore 而非 PageStore，为什么 Append-Only 写入能简化崩溃恢复，为什么 LIRS 比 LRU 更适合数据库缓存场景。两类材料互补使用，效果最佳。

## 技术深度承诺

为帮助读者快速判断本书是否符合预期，我们明确列出本书的承诺与不承诺。

**本书承诺**：

- **源码级精读**：每一项关键论述都附 `ClassName.java:行号` 引用，读者可同步打开源码对照阅读
- **行号准确**：基于 H2 v2.4.249-SNAPSHOT 版本，所有行号在 `source_freshness_check.py` 工具持续校验下保证有效
- **跨版本注记**：当源码在分析期间发生结构性变更（如 v2.4.240 → v2.4.249-SNAPSHOT 的 44 次提交），附录 B 给出变更摘要
- **图文同源**：578 幅 ASCII 示意图全部由作者基于源码绘制，每张图都对应正文具体段落
- **术语严谨**：术语表与索引交叉验证，每个核心概念在全书首次出现处给出定义

**本书不承诺**：

- **JDBC API 教程**：本书不教读者如何用 JDBC 连接 H2、执行查询、处理结果集，这部分由 Java SE 文档与 H2 quickstart 覆盖
- **SQL 标准讲解**：本书不讲 GROUP BY、JOIN 语义、范式理论，这部分由《数据库系统概念》等教材覆盖
- **性能调优指南**：本书不提供"如何让你的 H2 实例跑得更快"的运维建议，这部分由 H2 performance.html 官方文档覆盖
- **替代官方文档**：本书是源码分析，不是参考手册；当读者需要查询 SQL 函数列表或配置参数时，应回到官方文档

## 目标读者

本书适合以下类型的读者：

- **H2 用户与集成开发者**：希望通过理解 H2 的内部机制来优化使用方式、排查性能问题的开发者。建议从第1-2章（总体架构）和第7-8章（SQL 执行与优化器）入手。
- **数据库内核学习者**：正在学习数据库实现原理，希望通过一个真实且精简的开源项目来理解理论知识如何落地的学生和工程师。建议按章节顺序通读。
- **H2 贡献者与定制开发者**：需要修改 H2 源码或为其贡献补丁的开发者。建议先阅读第1-2章（架构）和第3章（包结构），然后根据感兴趣的领域阅读对应的模块专章。
- **Java 系统设计爱好者**：对高并发、高性能系统设计感兴趣的开发者。MVStore 存储引擎（第9章）的日志结构设计和并发控制（第10章）尤其值得关注。

## 读者契约

为获得最佳阅读效果，建议读者具备以下前置知识。不满足这些条件的读者，本书并非完全不可读，但部分章节的关键论述可能需要反复查阅外部资料。

**前置知识要求**：

- **Java 基础**：能阅读使用泛型、内部类、并发原语（`AtomicReference` / `synchronized`）的 Java 代码。本书源码示例假设读者无需查阅 Java 语法即可理解代码意图
- **SQL 基础**：理解 SELECT/INSERT/UPDATE/DELETE 的基本语义、JOIN 类型、索引概念。本书不讲 SQL 语法但会讨论 SQL 语句如何被解析与优化
- **数据库内核入门概念**：知道事务、ACID、隔离级别、索引、锁、MVCC 这些术语大致含义。本书会深入它们的实现细节，但不会从零开始解释为什么需要它们

**不满足前置条件时的引导**：

- 缺 Java 基础 → 推荐《Java 核心技术（卷1）》（Cay S. Horstmann）或 [Oracle Java SE 文档](https://docs.oracle.com/en/java/javase/)
- 缺 SQL 基础 → 推荐 [W3Schools SQL 教程](https://www.w3schools.com/sql/) 或《SQL 必知必会》（Ben Forta）
- 缺数据库内核入门 → 推荐《数据库系统概念》（Silberschatz 等）前 6 章，或 [CMU 15-445 课程](https://15445.courses.cs.cmu.edu/) 的视频讲座

## 内容概要

本书共 12 章 + 5 附录，覆盖 H2 Database 的主要源码模块：

| 章节 | 主题 | 核心内容 |
|------|------|---------|
| 第1章 | H2 概述 | 发展历史、核心特性、与其他嵌入式数据库的对比 |
| 第2章 | 分层模块划分 | 八层架构详解（JDBC/Server/Engine/Command/Expression/Table-Index/MVStore/FileSystem） |
| 第3章 | 核心包结构 | `org.h2` 主要包的类职责和依赖关系 |
| 第4-5章 | 核心模块与流程 | Command/Expression/Table-Index 模块详解，9 大核心流程 |
| 第6章 | 核心算法分析 | B-Tree、Copy-on-Write、MVCC、Chunk、LIRS、Optimizer、R-Tree、递归下降解析等 10 个算法 |
| 第7章 | SQL 执行全流程 | SELECT/INSERT/UPDATE/DELETE 的执行链路 |
| 第8章 | 查询优化器 | 基于代价的优化、Join 顺序选择、表达式的索引优化 |
| 第9章 | 持久化引擎 | MVStore 的 Architecture、Chunk/Page 文件格式、检查点机制 |
| 第10章 | 锁与并发控制 | 表级锁、MVCC 实现、事务隔离级别 |
| 第11章 | 开发指南 | 源码阅读路线、调试环境搭建、测试框架 |
| 第12章 | 总结 | H2 设计哲学、适用场景、与其他数据库的深度对比 |
| 附录 A | 端到端案例研究 | 一条 SELECT 全链路、一次事务 COMMIT、一次崩溃恢复 |
| 附录 B | 源码版本变更说明 | v2.4.240 → v2.4.249-SNAPSHOT 关键变更（MVStore 核心层、事务子系统） |
| 附录 C | 术语表 | 113 条术语的中英文对照、详细定义、章节索引与相关术语 |
| 附录 D | 概念索引 | 关键概念、API 类名与算法名的层级化章节位置索引 |
| 附录 E | 参考文献 | 官方文档、学术论文、技术资料分类清单 |

## 版本声明

**基础源码版本**：H2 v2.4.249-SNAPSHOT。本书所有源码引用、行号标注、类继承关系分析均基于此版本。

**版本时间窗口**：v2.4.240（2026-04）→ v2.4.249-SNAPSHOT（2026-05），上游 44 次提交涉及 81 个文件。其中影响本书叙述的关键变更包括：MVStore 核心层的 `panicException AtomicReference` 引入、`closeStore` 序列重构、`commit` 防重入逻辑、`MVMap.operate` 简化、`tryLock` CPU 退避策略、FileStore 流水线重构；事务子系统的 `TransactionStore` 状态机改造、`CommitDecisionMaker` 引入、`VersionedBitSet` 重写、`VersionedValue` 序列化格式变更等。详细差异见**附录 B《源码版本变更说明》**。

**与未来版本的兼容性**：H2 上游每个小版本可能引入行号偏移、类重命名或方法签名调整。本书附带 `source_freshness_check.py` 工具，可对照新版本源码自动检测过期引用。建议每月或每次升级 H2 版本后运行一次该工具。

## 致谢

**致 H2 项目团队**：感谢 H2 Database 的创始人 Thomas Mueller 和全体贡献者，为 Java 社区提供了如此优秀的嵌入式数据库实现。H2 的代码风格——精简、自洽、注释克制但论述清晰——本身就是优秀软件工程的范例。

**致评审者**：本书写作过程中经历了 7 轮多视角审查（架构师、文档工程师、源码引用核对者、图书编辑视角并行复核），评审者们贡献的逐行反馈使本书的源码引用、章节衔接、术语一致性达到了远超初稿的质量水准。

**致工具作者**：本书的质量验证依赖 17 个 Python 工具脚本组成的流水线（`final_check.py`、`_audit_smart.py`、`check_style.py` 等）。这些工具在写作中持续演进，覆盖了从图号唯一性到术语表完整性的近百项自动检查。没有这套工具链，全书数万行内容的一致性几乎不可能维持。

**致读者反馈**：感谢所有提供过反馈的早期读者。读者关于"哪些章节需要更多过渡"、"哪些图过于密集"、"哪些术语首次出现时缺少定义"的具体意见，直接驱动了第8-11轮的全书结构调整。

---

*本书为源码分析文档，非 H2 Database 官方文档。书中分析基于特定版本源码，可能与您使用的版本存在差异。当本书内容与官方文档冲突时，请以官方文档为准。*
# H2 Database Source Code Analysis

## H2 Database 源码全面分析与解读

版本 v6.1 · 2026-06-15 · 6,564 行 · 12 章 + 5 附录

**作者：其·龙（Stallman Wang）**
**联系邮箱：[stallman.wang@foxmail.com](mailto:stallman.wang@foxmail.com)**

深入剖析 H2 Database v2.x 核心源码，覆盖总体架构、分层模块、核心包结构、模块流程、经典算法、SQL 执行全流程、查询优化器、持久化引擎与锁实现。

## 源代码信息

| 项目 | 数据 |
|------|------|
| H2 版本 | 2.4.249-SNAPSHOT |
| 编程语言 | 纯 Java（编译目标 Java 11） |
| Maven 构建 | pom.xml 多模块 |
| 源文件数 | 843 个 Java 文件 |
| 源码行数 | 229,575 行 |
| 测试文件数 | 344 个 Java 测试文件 |
| 测试行数 | 99,396 行 |
| 代码总规模 | 1,187 个文件 · 328,971 行 |
| 源码变更 | 2026-05-25（基于上游 v2.4.240 的 44 次提交更新） |

共 10 个经典算法 · 20 幅 ASCII 示意图 · 411 处源码引用

---
# 第1章 H2 总体架构

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、12,044 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 1.1 模块版图

本章覆盖 1 个包、11,839 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.engine` | 28 | 11,839 | Contains high level classes of the database and classes that don't fit in another sub-package. |

## 1.2 核心类型

在 `org.h2.engine` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 1.2.1 `org.h2.engine`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Database` | 2,566 | 152 | （无类注释，按方法名归纳） |
| `SessionLocal` | 2,156 | 135 | （无类注释，按方法名归纳） |
| `SessionRemote` | 1,068 | 53 | （无类注释，按方法名归纳） |
| `Mode` | 776 | 5 | （无类注释，按方法名归纳） |

## 1.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Database.addDatabaseObject()` | `org/h2/engine/Database.java:948` |
| `Database.addSchemaObject()` | `org/h2/engine/Database.java:923` |
| `SessionLocal.addLocalTempTable()` | `org/h2/engine/SessionLocal.java:397` |
| `SessionLocal.addLocalTempTableConstraint()` | `org/h2/engine/SessionLocal.java:510` |
| `SessionRemote.addTemporaryLob()` | `org/h2/engine/SessionRemote.java:819` |
| `SessionRemote.autoCommitIfCluster()` | `org/h2/engine/SessionRemote.java:296` |

## 1.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Database` | `org.h2.engine` | 2,566 | 152 |
| `SessionLocal` | `org.h2.engine` | 2,156 | 135 |
| `SessionRemote` | `org.h2.engine` | 1,068 | 53 |
| `Mode` | `org.h2.engine` | 776 | 5 |
| `ConnectionInfo` | `org.h2.engine` | 766 | 25 |

## 1.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 1.3.2.1 `Database`

`Database` 位于 `org.h2.engine`，2,566 行、152 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 22%，包级依赖 8 个。

### 1.3.2.2 `SessionLocal`

`SessionLocal` 位于 `org.h2.engine`，2,156 行、135 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 18%，包级依赖 8 个。

### 1.3.2.3 `SessionRemote`

`SessionRemote` 位于 `org.h2.engine`，1,068 行、53 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 1.3.2.4 `Mode`

`Mode` 位于 `org.h2.engine`，776 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 8 个。

### 1.3.2.5 `ConnectionInfo`

`ConnectionInfo` 位于 `org.h2.engine`，766 行、25 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 1.3.2.6 `Constants`

`Constants` 位于 `org.h2.engine`，520 行、0 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

## 1.3.2 源码坐标明细

本章主责包中 20 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Database.addDatabaseObject()` | `org/h2/engine/Database.java:948` |
| `Database.addSchemaObject()` | `org/h2/engine/Database.java:923` |
| `Database.allocateObjectId()` | `org/h2/engine/Database.java:1369` |
| `Database.checkPowerOff()` | `org/h2/engine/Database.java:475` |
| `SessionLocal.addLocalTempTable()` | `org/h2/engine/SessionLocal.java:397` |
| `SessionLocal.addLocalTempTableConstraint()` | `org/h2/engine/SessionLocal.java:510` |
| `SessionLocal.addLocalTempTableIndex()` | `org/h2/engine/SessionLocal.java:454` |
| `SessionLocal.addProcedure()` | `org/h2/engine/SessionLocal.java:1424` |
| `SessionRemote.addTemporaryLob()` | `org/h2/engine/SessionRemote.java:819` |
| `SessionRemote.autoCommitIfCluster()` | `org/h2/engine/SessionRemote.java:296` |
| `SessionRemote.cancel()` | `org/h2/engine/SessionRemote.java:197` |
| `SessionRemote.cancelStatement()` | `org/h2/engine/SessionRemote.java:208` |
| `Mode.getEnum()` | `org/h2/engine/Mode.java:766` |
| `Mode.getInstance()` | `org/h2/engine/Mode.java:754` |
| `Mode.getName()` | `org/h2/engine/Mode.java:762` |
| `Mode.getRegular()` | `org/h2/engine/Mode.java:758` |
| `ConnectionInfo.cleanAuthenticationInfo()` | `org/h2/engine/ConnectionInfo.java:761` |
| `ConnectionInfo.clone()` | `org/h2/engine/ConnectionInfo.java:185` |
| `ConnectionInfo.getDbSettings()` | `org/h2/engine/ConnectionInfo.java:717` |
| `ConnectionInfo.getFilePasswordHash()` | `org/h2/engine/ConnectionInfo.java:480` |

## 1.4 阅读路径

读 `org.h2.engine` 的 28 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.engine` 的 package-info 与 `Database`，建立第1章的职责边界。
2. 再读 `Database` 的 152 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.engine`（本章最小包，11,839 行）的实现，关注容量与失败路径。

跨章衔接请对照第2章《分层模块划分》。

## 1.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.engine` | `org.h2.util`, `org.h2.message`, `org.h2.value`, `org.h2.api` |

## 1.6 设计权衡

- `org.h2.engine` 用 28 个文件换到 11,839 行实现，平均每文件 422 行，其中 `Database` 独占 2,566 行、152 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.engine`（11,839 行）与 `org.h2.engine` 的职责差是本章最值得记的一条边界。

## 1.7 常见误区

- 把 `org.h2.engine` 的 11,839 行当作复杂度上限：`Database` 之外的 27 个文件多为类型族与样板。
- 只看 `Database` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.engine` 与 `org.h2.engine` 视为可互换：前者 28 文件、后者 28 文件，扩展点分布完全不同。

## 1.8 深读要点

规模信号：`org.h2.engine` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.engine` 依赖 8 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`Database` 的公开方法 152 个，读它等于读本章的主干。

## 1.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Database**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **CAS (Compare-And-Swap)**：详见[术语表](back/glossary.md)对应条目。
- **CTE**：详见[术语表](back/glossary.md)对应条目。
- **JSON**：详见[术语表](back/glossary.md)对应条目。
- **LSM-Tree / Log-Structured Merge-Tree**：详见[术语表](back/glossary.md)对应条目。
- **PageStore**：详见[术语表](back/glossary.md)对应条目。

## 1.9 知识点清单

1. `org.h2.engine` 的 `Database`：2,566 行、152 个公开方法，职责按方法名归纳
2. `org.h2.engine` 的 `SessionLocal`：2,156 行、135 个公开方法，职责按方法名归纳

## 1.9 本章小结

- 本章覆盖 1 个包、11,839 行。
- 关键入口与源码坐标见 §1.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 1.10 延伸思考

**1. 🟢★ 指出 `org.h2.engine` 中 `Database` 与 `SessionLocal` 的分工差异，并给出调用方向。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**2. 🔵★★ 围绕 `org.h2.engine` 的 `Database`，说明它为什么需要独立成类型而不是并入 `SessionLocal`。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**3. 🟠★★★ 以 `org.h2.engine` 的 `Database` 为入口，画出一次完整调用经过的包。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.engine` 的一个类型，你保留 `Database` 还是 `SessionLocal`？说明代价。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

## 1.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.engine`：28 个文件、11,839 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.engine`（11,839 行）：两者的并发与一致性策略不同，差异落在 `Database` 的 152 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 1.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.engine` | `org.h2.util` | 55 |
| `org.h2.engine` | `org.h2.message` | 33 |
| `org.h2.engine` | `org.h2.value` | 26 |

## 1.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.engine` 与 `org.h2.engine` 的调用方向？`Database` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.engine` 的调用链讲到落盘或返回，并说清 `org.h2.engine` 与 `org.h2.engine` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.engine` 的注释与实现对不上，你信哪一边，为什么？

## 1.12 延展阅读

- 详见第2章《分层模块划分》。

# 第2章 分层模块划分

## 2.1 模块版图

本章覆盖 1 个包、205 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2` | 1 | 205 | Implementation of the JDBC driver. |

## 2.2 核心类型

在 `org.h2` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 2.2.1 `org.h2`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Driver` | 205 | 11 | （无类注释，按方法名归纳） |

## 2.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Driver.acceptsURL()` | `org/h2/Driver.java:76` |
| `Driver.connect()` | `org/h2/Driver.java:55` |

## 2.3.1 公共类型清单

本章抽样类型按包分组，共 1 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Driver` | `org.h2` | 205 | 11 |

## 2.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 2.3.2.1 `Driver`

`Driver` 位于 `org.h2`，205 行、11 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 100%，包级依赖 0 个。

## 2.3.2 源码坐标明细

本章主责包中 4 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Driver.acceptsURL()` | `org/h2/Driver.java:76` |
| `Driver.connect()` | `org/h2/Driver.java:55` |
| `Driver.getMajorVersion()` | `org/h2/Driver.java:95` |
| `Driver.getMinorVersion()` | `org/h2/Driver.java:106` |

## 2.4 阅读路径

读 `org.h2` 的 1 个文件时，先看骨架类，再沿 `—` 方向下钻。

1. 先读 `org.h2` 的 package-info 与 `Driver`，建立第2章的职责边界。
2. 再读 `Driver` 的 11 个公开入口，确认它对 `—` 的调用方向与加锁方式。
3. 最后读 `org.h2`（本章最小包，205 行）的实现，关注容量与失败路径。

跨章衔接请对照第1章《H2 总体架构》。

## 2.5 设计权衡

- `org.h2` 用 1 个文件换到 205 行实现，平均每文件 205 行，其中 `Driver` 独占 205 行、11 个公开方法。
- 该包对外声明了 0 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2`（205 行）与 `org.h2` 的职责差是本章最值得记的一条边界。

## 2.6 常见误区

- 把 `org.h2` 的 205 行当作复杂度上限：`Driver` 之外的 0 个文件多为类型族与样板。
- 只看 `Driver` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2` 与 `org.h2` 视为可互换：前者 1 文件、后者 1 文件，扩展点分布完全不同。

## 2.7 深读要点

规模信号：`org.h2` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2` 依赖 0 个 `org.h2` 包，其中 `—` 出现最频繁。
入口信号：`Driver` 的公开方法 11 个，读它等于读本章的主干。

## 2.7 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Driver**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。
- **ConnectionInfo**：详见[术语表](back/glossary.md)对应条目。
- **Database**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **FilePathDisk**：详见[术语表](back/glossary.md)对应条目。

## 2.9 知识点清单

1. `org.h2` 的 `Driver`：205 行、11 个公开方法，职责按方法名归纳

## 2.8 本章小结

- 本章覆盖 1 个包、205 行。
- 关键入口与源码坐标见 §2.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 2.9 延伸思考

**1. 🟢★ 指出 `org.h2` 中 `Driver` 与 `相邻工具类型` 的分工差异，并给出调用方向。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**2. 🔵★★ 围绕 `org.h2` 的 `Driver`，说明它为什么需要独立成类型而不是并入 `相邻工具类型`。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**3. 🟠★★★ 以 `org.h2` 的 `Driver` 为入口，画出一次完整调用经过的包。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2` 的一个类型，你保留 `Driver` 还是 `相邻工具类型`？说明代价。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

## 2.10 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2`：1 个文件、205 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2`（205 行）：两者的扩展与兼容策略不同，差异落在 `Driver` 的 11 个公开方法里。
- 若扩展与兼容假设被打破（0 个依赖变化），最先受影响的调用链从 `—` 进入。

## 2.10.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2` 与 `org.h2` 的调用方向？`Driver` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2` 的调用链讲到落盘或返回，并说清 `org.h2` 与 `org.h2` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2` 的注释与实现对不上，你信哪一边，为什么？

## 2.11 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2` | 第1章《H2 总体架构》 |

## 2.11 延展阅读

- 详见第1章《H2 总体架构》。
# 第3章 包结构与模块职责

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、7,363 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 3.1 模块版图

本章覆盖 2 个包、7,363 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.api` | 12 | 4,150 | Contains interfaces for user-defined extensions, such as triggers and user-defined aggregate functions. |
| `org.h2.schema` | 11 | 3,213 | Schema implementation and objects that are stored in a schema (for example, sequences and constants). |

## 3.2 核心类型

在 `org.h2.api` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 3.2.1 `org.h2.api`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ErrorCode` | 2,367 | 2 | （无类注释，按方法名归纳） |
| `Interval` | 636 | 33 | （无类注释，按方法名归纳） |
| `IntervalQualifier` | 353 | 13 | （无类注释，按方法名归纳） |
| `H2Type` | 322 | 6 | （无类注释，按方法名归纳） |

### 3.2.2 `org.h2.schema`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Schema` | 848 | 51 | （无类注释，按方法名归纳） |
| `Sequence` | 586 | 25 | （无类注释，按方法名归纳） |
| `FunctionAlias` | 562 | 22 | （无类注释，按方法名归纳） |
| `TriggerObject` | 543 | 28 | （无类注释，按方法名归纳） |

## 3.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `ErrorCode.isCommon()` | `org/h2/api/ErrorCode.java:2287` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `Interval.getDays()` | `org/h2/api/Interval.java:543` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `IntervalQualifier.hasDays()` | `org/h2/api/IntervalQualifier.java:165` |
| `Schema.add()` | `org/h2/schema/Schema.java:267` |
| `Schema.canDrop()` | `org/h2/schema/Schema.java:92` |
| `Sequence.close()` | `org/h2/schema/Sequence.java:553` |
| `Sequence.flush()` | `org/h2/schema/Sequence.java:510` |
| `FunctionAlias.compareTo()` | `org/h2/schema/FunctionAlias.java:546` |
| `FunctionAlias.findJavaMethod()` | `org/h2/schema/FunctionAlias.java:243` |

## 3.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `ErrorCode` | `org.h2.api` | 2,367 | 2 |
| `Interval` | `org.h2.api` | 636 | 33 |
| `IntervalQualifier` | `org.h2.api` | 353 | 13 |
| `H2Type` | `org.h2.api` | 322 | 6 |
| `DatabaseEventListener` | `org.h2.api` | 113 | 0 |
| `Schema` | `org.h2.schema` | 848 | 51 |
| `Sequence` | `org.h2.schema` | 586 | 25 |
| `FunctionAlias` | `org.h2.schema` | 562 | 22 |
| `TriggerObject` | `org.h2.schema` | 543 | 28 |
| `Domain` | `org.h2.schema` | 241 | 22 |

## 3.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 3.3.2.1 `ErrorCode`

`ErrorCode` 位于 `org.h2.api`，2,367 行、2 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 57%，包级依赖 7 个。

### 3.3.2.2 `Interval`

`Interval` 位于 `org.h2.api`，636 行、33 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 15%，包级依赖 7 个。

### 3.3.2.3 `IntervalQualifier`

`IntervalQualifier` 位于 `org.h2.api`，353 行、13 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 7 个。

### 3.3.2.4 `H2Type`

`H2Type` 位于 `org.h2.api`，322 行、6 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 7 个。

### 3.3.2.5 `DatabaseEventListener`

`DatabaseEventListener` 位于 `org.h2.api`，113 行、0 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 7 个。

### 3.3.2.6 `Trigger`

`Trigger` 位于 `org.h2.api`，105 行、0 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 7 个。

### 3.3.2.7 `Schema`

`Schema` 位于 `org.h2.schema`，848 行、51 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 26%，包级依赖 8 个。

### 3.3.2.8 `Sequence`

`Sequence` 位于 `org.h2.schema`，586 行、25 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 18%，包级依赖 8 个。

### 3.3.2.9 `FunctionAlias`

`FunctionAlias` 位于 `org.h2.schema`，562 行、22 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 17%，包级依赖 8 个。

### 3.3.2.10 `TriggerObject`

`TriggerObject` 位于 `org.h2.schema`，543 行、28 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 17%，包级依赖 8 个。

### 3.3.2.11 `Domain`

`Domain` 位于 `org.h2.schema`，241 行、22 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 3.3.2.12 `UserAggregate`

`UserAggregate` 位于 `org.h2.schema`，120 行、9 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

## 3.3.2 源码坐标明细

本章主责包中 38 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `ErrorCode.isCommon()` | `org/h2/api/ErrorCode.java:2287` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `Interval.getDays()` | `org/h2/api/Interval.java:543` |
| `Interval.getHours()` | `org/h2/api/Interval.java:552` |
| `Interval.getLeading()` | `org/h2/api/Interval.java:506` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `IntervalQualifier.hasDays()` | `org/h2/api/IntervalQualifier.java:165` |
| `IntervalQualifier.hasHours()` | `org/h2/api/IntervalQualifier.java:182` |
| `IntervalQualifier.hasMinutes()` | `org/h2/api/IntervalQualifier.java:201` |
| `H2Type.array()` | `org/h2/api/H2Type.java:258` |
| `H2Type.getName()` | `org/h2/api/H2Type.java:296` |
| `H2Type.getVendor()` | `org/h2/api/H2Type.java:301` |
| `H2Type.getVendorTypeNumber()` | `org/h2/api/H2Type.java:312` |
| `Schema.add()` | `org/h2/schema/Schema.java:267` |
| `Schema.canDrop()` | `org/h2/schema/Schema.java:92` |
| `Schema.createSynonym()` | `org/h2/schema/Schema.java:814` |
| `Schema.createTable()` | `org/h2/schema/Schema.java:786` |
| `Sequence.close()` | `org/h2/schema/Sequence.java:553` |
| `Sequence.flush()` | `org/h2/schema/Sequence.java:510` |

## 3.4 阅读路径

读 `org.h2.api` 的 12 个文件时，先看骨架类，再沿 `org.h2.security.auth` 方向下钻。

1. 先读 `org.h2.api` 的 package-info 与 `ErrorCode`，建立第3章的职责边界。
2. 再读 `ErrorCode` 的 2 个公开入口，确认它对 `org.h2.security.auth` 的调用方向与加锁方式。
3. 最后读 `org.h2.schema`（本章最小包，3,213 行）的实现，关注容量与失败路径。

跨章衔接请对照第4章《包结构与模块职责》。

## 3.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.api` | `org.h2.security.auth`, `org.h2.value`, `org.h2.util.DateTimeUtils`, `org.h2.message` |
| `org.h2.schema` | `org.h2.engine`, `org.h2.value`, `org.h2.message`, `org.h2.table` |

## 3.6 设计权衡

- `org.h2.api` 用 12 个文件换到 4,150 行实现，平均每文件 345 行，其中 `ErrorCode` 独占 2,367 行、2 个公开方法。
- 该包对外声明了 7 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.schema`（3,213 行）与 `org.h2.api` 的职责差是本章最值得记的一条边界。

## 3.7 常见误区

- 把 `org.h2.api` 的 4,150 行当作复杂度上限：`ErrorCode` 之外的 11 个文件多为类型族与样板。
- 只看 `ErrorCode` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.api` 与 `org.h2.schema` 视为可互换：前者 12 文件、后者 11 文件，扩展点分布完全不同。

## 3.8 深读要点

规模信号：`org.h2.api` 占本章 56% 的实现行数，改动风险最高。
耦合信号：`org.h2.api` 依赖 7 个 `org.h2` 包，其中 `org.h2.security.auth` 出现最频繁。
入口信号：`ErrorCode` 的公开方法 2 个，读它等于读本章的主干。

## 3.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Schema**：详见[术语表](back/glossary.md)对应条目。
- **Column**：详见[术语表](back/glossary.md)对应条目。
- **Database**：详见[术语表](back/glossary.md)对应条目。
- **DbSettings**：详见[术语表](back/glossary.md)对应条目。
- **Driver**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。

## 3.9 知识点清单

1. `org.h2.api` 的 `ErrorCode`：2,367 行、2 个公开方法，职责按方法名归纳
2. `org.h2.api` 的 `Interval`：636 行、33 个公开方法，职责按方法名归纳
3. `org.h2.schema` 的 `Schema`：848 行、51 个公开方法，职责按方法名归纳
4. `org.h2.schema` 的 `Sequence`：586 行、25 个公开方法，职责按方法名归纳

## 3.9 本章小结

- 本章覆盖 2 个包、7,363 行。
- 关键入口与源码坐标见 §3.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 3.10 延伸思考

**1. 🟢★ 指出 `org.h2.api` 中 `ErrorCode` 与 `Interval` 的分工差异，并给出调用方向。**

> 提示：第3章 §3.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

**2. 🔵★★ 围绕 `org.h2.schema` 的 `Schema`，说明它为什么需要独立成类型而不是并入 `Sequence`。**

> 提示：第3章 §3.2 的表格给出 `Schema` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

**3. 🟠★★★ 以 `org.h2.api` 的 `ErrorCode` 为入口，画出一次完整调用经过的包。**

> 提示：第3章 §3.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.schema` 的一个类型，你保留 `Schema` 还是 `Sequence`？说明代价。**

> 提示：第3章 §3.2 的表格给出 `Schema` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

## 3.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.api`：12 个文件、4,150 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.schema`（3,213 行）：两者的演化与版本策略不同，差异落在 `ErrorCode` 的 2 个公开方法里。
- 若演化与版本假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2.security.auth` 进入。

## 3.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.api` | `org.h2.security.auth` | 5 |
| `org.h2.api` | `org.h2.value` | 3 |
| `org.h2.api` | `org.h2.util.DateTimeUtils` | 2 |
| `org.h2.schema` | `org.h2.engine` | 29 |
| `org.h2.schema` | `org.h2.value` | 16 |
| `org.h2.schema` | `org.h2.message` | 13 |

## 3.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.api` 与 `org.h2.schema` 的调用方向？`ErrorCode` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.api` 的调用链讲到落盘或返回，并说清 `org.h2.api` 与 `org.h2.schema` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.api` 的注释与实现对不上，你信哪一边，为什么？

## 3.12 延展阅读

- 详见第4章《包结构与模块职责》。
# 第4章 模块边界与依赖治理

> **本章导读**：本章由源码清单汇总而成，覆盖 1 个包、15,014 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 4.1 模块版图

本章覆盖 1 个包、15,014 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.command` | 11 | 15,014 | This package contains the parser and the base classes for prepared SQL statements. |

## 4.2 核心类型

在 `org.h2.command` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 4.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |

## 4.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `org/h2/command/Parser.java:9446` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `org/h2/command/ParserBase.java:743` |

## 4.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 |
| `ParserBase` | `org.h2.command` | 771 | 8 |
| `Token` | `org.h2.command` | 758 | 5 |
| `CommandInterface` | `org.h2.command` | 654 | 0 |

## 4.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 4.3.2.1 `Parser`

`Parser` 位于 `org.h2.command`，9,470 行、9 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 63%，包级依赖 8 个。

### 4.3.2.2 `Tokenizer`

`Tokenizer` 位于 `org.h2.command`，1,522 行、0 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

### 4.3.2.3 `ParserBase`

`ParserBase` 位于 `org.h2.command`，771 行、8 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 4.3.2.4 `Token`

`Token` 位于 `org.h2.command`，758 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 4.3.2.5 `CommandInterface`

`CommandInterface` 位于 `org.h2.command`，654 行、0 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

### 4.3.2.6 `Prepared`

`Prepared` 位于 `org.h2.command`，503 行、33 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 8 个。

## 4.3.2 源码坐标明细

本章主责包中 13 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `org/h2/command/Parser.java:9446` |
| `Parser.parseExpression()` | `org/h2/command/Parser.java:9434` |
| `Parser.parseTableName()` | `org/h2/command/Parser.java:9463` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `org/h2/command/ParserBase.java:743` |
| `ParserBase.parseColumnList()` | `org/h2/command/ParserBase.java:247` |
| `ParserBase.parseNonKeywords()` | `org/h2/command/ParserBase.java:72` |
| `Token.toString()` | `org/h2/command/Token.java:476` |
| `Prepared.checkCanceled()` | `org/h2/command/Prepared.java:340` |
| `Prepared.collectDependencies()` | `org/h2/command/Prepared.java:486` |
| `Prepared.getCurrentRowNumber()` | `org/h2/command/Prepared.java:418` |
| `Prepared.getParameters()` | `org/h2/command/Prepared.java:167` |

## 4.4 阅读路径

读 `org.h2.command` 的 11 个文件时，先看骨架类，再沿 `org.h2.util.ParserUtil` 方向下钻。

1. 先读 `org.h2.command` 的 package-info 与 `Parser`，建立第4章的职责边界。
2. 再读 `Parser` 的 9 个公开入口，确认它对 `org.h2.util.ParserUtil` 的调用方向与加锁方式。
3. 最后读 `org.h2.command`（本章最小包，15,014 行）的实现，关注容量与失败路径。

跨章衔接请对照第5章《进程内数据流》。

## 4.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil`, `org.h2.expression.function`, `org.h2.value`, `org.h2.expression` |

## 4.6 设计权衡

- `org.h2.command` 用 11 个文件换到 15,014 行实现，平均每文件 1,364 行，其中 `Parser` 独占 9,470 行、9 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.command`（15,014 行）与 `org.h2.command` 的职责差是本章最值得记的一条边界。

## 4.7 常见误区

- 把 `org.h2.command` 的 15,014 行当作复杂度上限：`Parser` 之外的 10 个文件多为类型族与样板。
- 只看 `Parser` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.command` 与 `org.h2.command` 视为可互换：前者 11 文件、后者 11 文件，扩展点分布完全不同。

## 4.8 深读要点

规模信号：`org.h2.command` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.command` 依赖 8 个 `org.h2` 包，其中 `org.h2.util.ParserUtil` 出现最频繁。
入口信号：`Parser` 的公开方法 9 个，读它等于读本章的主干。

## 4.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Parser**：详见[术语表](back/glossary.md)对应条目。
- **Deadlock**：详见[术语表](back/glossary.md)对应条目。
- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **Index**：详见[术语表](back/glossary.md)对应条目。
- **IndexCondition**：详见[术语表](back/glossary.md)对应条目。
- **Meta Lock**：详见[术语表](back/glossary.md)对应条目。
- **MVMap**：详见[术语表](back/glossary.md)对应条目。

## 4.9 知识点清单

1. `org.h2.command` 的 `Parser`：9,470 行、9 个公开方法，职责按方法名归纳
2. `org.h2.command` 的 `Tokenizer`：1,522 行、0 个公开方法，职责按方法名归纳

## 4.9 本章小结

- 本章覆盖 1 个包、15,014 行。
- 关键入口与源码坐标见 §4.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 4.10 延伸思考

**1. 🟢★ 指出 `org.h2.command` 中 `Parser` 与 `Tokenizer` 的分工差异，并给出调用方向。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**2. 🔵★★ 围绕 `org.h2.command` 的 `Parser`，说明它为什么需要独立成类型而不是并入 `Tokenizer`。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**3. 🟠★★★ 以 `org.h2.command` 的 `Parser` 为入口，画出一次完整调用经过的包。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.command` 的一个类型，你保留 `Parser` 还是 `Tokenizer`？说明代价。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

## 4.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.command`：11 个文件、15,014 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.command`（15,014 行）：两者的性能与规模策略不同，差异落在 `Parser` 的 9 个公开方法里。
- 若性能与规模假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util.ParserUtil` 进入。

## 4.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil` | 188 |
| `org.h2.command` | `org.h2.expression.function` | 44 |
| `org.h2.command` | `org.h2.value` | 41 |

## 4.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.command` 与 `org.h2.command` 的调用方向？`Parser` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.command` 的调用链讲到落盘或返回，并说清 `org.h2.command` 与 `org.h2.command` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.command` 的注释与实现对不上，你信哪一边，为什么？

## 4.12 延展阅读

- 详见第5章《进程内数据流》。

# 第5章 进程内数据流

## 5.1 模块版图

本章覆盖 1 个包、15,014 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.command` | 11 | 15,014 | This package contains the parser and the base classes for prepared SQL statements. |

## 5.2 核心类型

在 `org.h2.command` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 5.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |

## 5.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `org/h2/command/Parser.java:9446` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `org/h2/command/ParserBase.java:743` |

## 5.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 |
| `ParserBase` | `org.h2.command` | 771 | 8 |
| `Token` | `org.h2.command` | 758 | 5 |
| `CommandInterface` | `org.h2.command` | 654 | 0 |

## 5.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 5.3.2.1 `Parser`

`Parser` 位于 `org.h2.command`，9,470 行、9 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 63%，包级依赖 8 个。

### 5.3.2.2 `Tokenizer`

`Tokenizer` 位于 `org.h2.command`，1,522 行、0 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

### 5.3.2.3 `ParserBase`

`ParserBase` 位于 `org.h2.command`，771 行、8 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 5.3.2.4 `Token`

`Token` 位于 `org.h2.command`，758 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 5.3.2.5 `CommandInterface`

`CommandInterface` 位于 `org.h2.command`，654 行、0 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

### 5.3.2.6 `Prepared`

`Prepared` 位于 `org.h2.command`，503 行、33 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 8 个。

## 5.3.2 源码坐标明细

本章主责包中 13 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `org/h2/command/Parser.java:9446` |
| `Parser.parseExpression()` | `org/h2/command/Parser.java:9434` |
| `Parser.parseTableName()` | `org/h2/command/Parser.java:9463` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `org/h2/command/ParserBase.java:743` |
| `ParserBase.parseColumnList()` | `org/h2/command/ParserBase.java:247` |
| `ParserBase.parseNonKeywords()` | `org/h2/command/ParserBase.java:72` |
| `Token.toString()` | `org/h2/command/Token.java:476` |
| `Prepared.checkCanceled()` | `org/h2/command/Prepared.java:340` |
| `Prepared.collectDependencies()` | `org/h2/command/Prepared.java:486` |
| `Prepared.getCurrentRowNumber()` | `org/h2/command/Prepared.java:418` |
| `Prepared.getParameters()` | `org/h2/command/Prepared.java:167` |

## 5.4 阅读路径

读 `org.h2.command` 的 11 个文件时，先看骨架类，再沿 `org.h2.util.ParserUtil` 方向下钻。

1. 先读 `org.h2.command` 的 package-info 与 `Parser`，建立第5章的职责边界。
2. 再读 `Parser` 的 9 个公开入口，确认它对 `org.h2.util.ParserUtil` 的调用方向与加锁方式。
3. 最后读 `org.h2.command`（本章最小包，15,014 行）的实现，关注容量与失败路径。

跨章衔接请对照第4章《模块边界与依赖治理》。

## 5.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil`, `org.h2.expression.function`, `org.h2.value`, `org.h2.expression` |

## 5.6 设计权衡

- `org.h2.command` 用 11 个文件换到 15,014 行实现，平均每文件 1,364 行，其中 `Parser` 独占 9,470 行、9 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.command`（15,014 行）与 `org.h2.command` 的职责差是本章最值得记的一条边界。

## 5.7 常见误区

- 把 `org.h2.command` 的 15,014 行当作复杂度上限：`Parser` 之外的 10 个文件多为类型族与样板。
- 只看 `Parser` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.command` 与 `org.h2.command` 视为可互换：前者 11 文件、后者 11 文件，扩展点分布完全不同。

## 5.8 深读要点

规模信号：`org.h2.command` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.command` 依赖 8 个 `org.h2` 包，其中 `org.h2.util.ParserUtil` 出现最频繁。
入口信号：`Parser` 的公开方法 9 个，读它等于读本章的主干。

## 5.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Parser**：详见[术语表](back/glossary.md)对应条目。
- **CommitDecisionMaker**：详见[术语表](back/glossary.md)对应条目。
- **DDL**：详见[术语表](back/glossary.md)对应条目。
- **DML**：详见[术语表](back/glossary.md)对应条目。
- **FreeSpaceBitSet**：详见[术语表](back/glossary.md)对应条目。
- **RollbackDecisionMaker**：详见[术语表](back/glossary.md)对应条目。
- **Savepoint**：详见[术语表](back/glossary.md)对应条目。

## 5.9 知识点清单

1. `org.h2.command` 的 `Parser`：9,470 行、9 个公开方法，职责按方法名归纳
2. `org.h2.command` 的 `Tokenizer`：1,522 行、0 个公开方法，职责按方法名归纳

## 5.9 本章小结

- 本章覆盖 1 个包、15,014 行。
- 关键入口与源码坐标见 §5.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 5.10 延伸思考

**1. 🟢★ 指出 `org.h2.command` 中 `Parser` 与 `Tokenizer` 的分工差异，并给出调用方向。**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**2. 🔵★★ 围绕 `org.h2.command` 的 `Parser`，说明它为什么需要独立成类型而不是并入 `Tokenizer`。**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**3. 🟠★★★ 以 `org.h2.command` 的 `Parser` 为入口，画出一次完整调用经过的包。**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.command` 的一个类型，你保留 `Parser` 还是 `Tokenizer`？说明代价。**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

## 5.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.command`：11 个文件、15,014 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.command`（15,014 行）：两者的并发与一致性策略不同，差异落在 `Parser` 的 9 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util.ParserUtil` 进入。

## 5.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil` | 188 |
| `org.h2.command` | `org.h2.expression.function` | 44 |
| `org.h2.command` | `org.h2.value` | 41 |

## 5.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.command` 与 `org.h2.command` 的调用方向？`Parser` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.command` 的调用链讲到落盘或返回，并说清 `org.h2.command` 与 `org.h2.command` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.command` 的注释与实现对不上，你信哪一边，为什么？

## 5.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.command` | 第4章《模块边界与依赖治理》 |

## 5.12 延展阅读

- 详见第4章《模块边界与依赖治理》。
# 第6章 数据结构：值、行与页

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、19,178 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 6.1 模块版图

本章覆盖 2 个包、19,178 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.value` | 55 | 15,501 | Data type and value implementations. |
| `org.h2.result` | 21 | 3,677 | Implementation of row and internal result sets. |

## 6.2 核心类型

在 `org.h2.value` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 6.2.1 `org.h2.value`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Value` | 2,873 | 67 | （无类注释，按方法名归纳） |
| `TypeInfo` | 1,539 | 23 | （无类注释，按方法名归纳） |
| `Transfer` | 1,368 | 31 | （无类注释，按方法名归纳） |
| `DataType` | 828 | 25 | （无类注释，按方法名归纳） |

### 6.2.2 `org.h2.result`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `LocalResult` | 710 | 42 | （无类注释，按方法名归纳） |
| `UpdatableRow` | 341 | 5 | （无类注释，按方法名归纳） |
| `SortOrder` | 334 | 15 | （无类注释，按方法名归纳） |
| `SimpleResult` | 303 | 31 | （无类注释，按方法名归纳） |

## 6.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `org/h2/value/Value.java:929` |
| `Value.castTo()` | `org/h2/value/Value.java:1105` |
| `TypeInfo.areSameTypes()` | `org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `org/h2/value/TypeInfo.java:764` |
| `Transfer.close()` | `org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `org/h2/value/Transfer.java:216` |
| `LocalResult.addRow()` | `org/h2/result/LocalResult.java:420` |
| `LocalResult.addRowForTable()` | `org/h2/result/LocalResult.java:404` |
| `UpdatableRow.deleteRow()` | `org/h2/result/UpdatableRow.java:257` |
| `UpdatableRow.insertRow()` | `org/h2/result/UpdatableRow.java:309` |
| `SortOrder.addNullOrdering()` | `org/h2/result/SortOrder.java:312` |
| `SortOrder.compare()` | `org/h2/result/SortOrder.java:162` |

## 6.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Value` | `org.h2.value` | 2,873 | 67 |
| `TypeInfo` | `org.h2.value` | 1,539 | 23 |
| `Transfer` | `org.h2.value` | 1,368 | 31 |
| `DataType` | `org.h2.value` | 828 | 25 |
| `ValueToObjectConverter` | `org.h2.value` | 642 | 6 |
| `LocalResult` | `org.h2.result` | 710 | 42 |
| `UpdatableRow` | `org.h2.result` | 341 | 5 |
| `SortOrder` | `org.h2.result` | 334 | 15 |
| `SimpleResult` | `org.h2.result` | 303 | 31 |
| `ResultRemote` | `org.h2.result` | 287 | 17 |

## 6.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 6.3.2.1 `Value`

`Value` 位于 `org.h2.value`，2,873 行、67 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

### 6.3.2.2 `TypeInfo`

`TypeInfo` 位于 `org.h2.value`，1,539 行、23 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

### 6.3.2.3 `Transfer`

`Transfer` 位于 `org.h2.value`，1,368 行、31 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 6.3.2.4 `DataType`

`DataType` 位于 `org.h2.value`，828 行、25 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 6.3.2.5 `ValueToObjectConverter`

`ValueToObjectConverter` 位于 `org.h2.value`，642 行、6 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

### 6.3.2.6 `ValueToObjectConverter2`

`ValueToObjectConverter2` 位于 `org.h2.value`，433 行、2 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 8 个。

### 6.3.2.7 `LocalResult`

`LocalResult` 位于 `org.h2.result`，710 行、42 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

### 6.3.2.8 `UpdatableRow`

`UpdatableRow` 位于 `org.h2.result`，341 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 6.3.2.9 `SortOrder`

`SortOrder` 位于 `org.h2.result`，334 行、15 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 6.3.2.10 `SimpleResult`

`SimpleResult` 位于 `org.h2.result`，303 行、31 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 6.3.2.11 `ResultRemote`

`ResultRemote` 位于 `org.h2.result`，287 行、17 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 6.3.2.12 `RowFactory`

`RowFactory` 位于 `org.h2.result`，201 行、17 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

## 6.3.2 源码坐标明细

本章主责包中 46 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `org/h2/value/Value.java:929` |
| `Value.castTo()` | `org/h2/value/Value.java:1105` |
| `Value.charLength()` | `org/h2/value/Value.java:2832` |
| `Value.clearCache()` | `org/h2/value/Value.java:773` |
| `TypeInfo.areSameTypes()` | `org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `org/h2/value/TypeInfo.java:764` |
| `TypeInfo.equals()` | `org/h2/value/TypeInfo.java:1397` |
| `TypeInfo.getDecimalPrecision()` | `org/h2/value/TypeInfo.java:1490` |
| `Transfer.close()` | `org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `org/h2/value/Transfer.java:216` |
| `Transfer.getSocket()` | `org/h2/value/Transfer.java:1289` |
| `Transfer.getVersion()` | `org/h2/value/Transfer.java:1330` |
| `DataType.addPrecision()` | `org/h2/value/DataType.java:791` |
| `DataType.areStableComparable()` | `org/h2/value/DataType.java:592` |
| `DataType.convertSQLTypeToValueType()` | `org/h2/value/DataType.java:366` |
| `DataType.convertTypeToSQLType()` | `org/h2/value/DataType.java:343` |
| `ValueToObjectConverter.getDefaultClass()` | `org/h2/value/ValueToObjectConverter.java:403` |
| `ValueToObjectConverter.objectToValue()` | `org/h2/value/ValueToObjectConverter.java:85` |
| `ValueToObjectConverter.readValue()` | `org/h2/value/ValueToObjectConverter.java:624` |
| `ValueToObjectConverter.valueToDefaultArray()` | `org/h2/value/ValueToObjectConverter.java:603` |

## 6.4 阅读路径

读 `org.h2.value` 的 55 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.value` 的 package-info 与 `Value`，建立第6章的职责边界。
2. 再读 `Value` 的 67 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.result`（本章最小包，3,677 行）的实现，关注容量与失败路径。

跨章衔接请对照第7章《数据结构：值、行与页》。

## 6.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.value` | `org.h2.util`, `org.h2.engine`, `org.h2.message`, `org.h2.api` |
| `org.h2.result` | `org.h2.value`, `org.h2.engine`, `org.h2.util`, `org.h2.expression` |

## 6.6 设计权衡

- `org.h2.value` 用 55 个文件换到 15,501 行实现，平均每文件 281 行，其中 `Value` 独占 2,873 行、67 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.result`（3,677 行）与 `org.h2.value` 的职责差是本章最值得记的一条边界。

## 6.7 常见误区

- 把 `org.h2.value` 的 15,501 行当作复杂度上限：`Value` 之外的 54 个文件多为类型族与样板。
- 只看 `Value` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.value` 与 `org.h2.result` 视为可互换：前者 55 文件、后者 21 文件，扩展点分布完全不同。

## 6.8 深读要点

规模信号：`org.h2.value` 占本章 81% 的实现行数，改动风险最高。
耦合信号：`org.h2.value` 依赖 8 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`Value` 的公开方法 67 个，读它等于读本章的主干。

## 6.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Value**：详见[术语表](back/glossary.md)对应条目。
- **Append-Only**：详见[术语表](back/glossary.md)对应条目。
- **B-Tree**：详见[术语表](back/glossary.md)对应条目。
- **Chunk**：详见[术语表](back/glossary.md)对应条目。
- **COW / Copy-on-Write**：详见[术语表](back/glossary.md)对应条目。
- **Compact**：详见[术语表](back/glossary.md)对应条目。
- **Free Space**：详见[术语表](back/glossary.md)对应条目。

## 6.9 知识点清单

1. `org.h2.value` 的 `Value`：2,873 行、67 个公开方法，职责按方法名归纳
2. `org.h2.value` 的 `TypeInfo`：1,539 行、23 个公开方法，职责按方法名归纳
3. `org.h2.result` 的 `LocalResult`：710 行、42 个公开方法，职责按方法名归纳
4. `org.h2.result` 的 `UpdatableRow`：341 行、5 个公开方法，职责按方法名归纳

## 6.9 本章小结

- 本章覆盖 2 个包、19,178 行。
- 关键入口与源码坐标见 §6.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 6.10 延伸思考

**1. 🟢★ 指出 `org.h2.value` 中 `Value` 与 `TypeInfo` 的分工差异，并给出调用方向。**

> 提示：第6章 §6.2 的表格给出 `Value` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**2. 🔵★★ 围绕 `org.h2.result` 的 `LocalResult`，说明它为什么需要独立成类型而不是并入 `UpdatableRow`。**

> 提示：第6章 §6.2 的表格给出 `LocalResult` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**3. 🟠★★★ 以 `org.h2.value` 的 `Value` 为入口，画出一次完整调用经过的包。**

> 提示：第6章 §6.2 的表格给出 `Value` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.result` 的一个类型，你保留 `LocalResult` 还是 `UpdatableRow`？说明代价。**

> 提示：第6章 §6.2 的表格给出 `LocalResult` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

## 6.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.value`：55 个文件、15,501 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.result`（3,677 行）：两者的扩展与兼容策略不同，差异落在 `Value` 的 67 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 6.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.value` | `org.h2.util` | 63 |
| `org.h2.value` | `org.h2.engine` | 59 |
| `org.h2.value` | `org.h2.message` | 40 |
| `org.h2.result` | `org.h2.value` | 45 |
| `org.h2.result` | `org.h2.engine` | 21 |
| `org.h2.result` | `org.h2.util` | 8 |

## 6.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.value` 与 `org.h2.result` 的调用方向？`Value` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.value` 的调用链讲到落盘或返回，并说清 `org.h2.value` 与 `org.h2.result` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.value` 的注释与实现对不上，你信哪一边，为什么？

## 6.12 延展阅读

- 详见第7章《数据结构：值、行与页》。
# 第7章 存储与压缩算法

> **本章导读**：本章由源码清单汇总而成，覆盖 1 个包、14,505 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 7.1 模块版图

本章覆盖 1 个包、14,505 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.mvstore` | 20 | 14,505 | A persistent storage for tree maps. |

## 7.2 核心类型

在 `org.h2.mvstore` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 7.2.1 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |

## 7.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `FileStore.accountForRemovedPage()` | `org/h2/mvstore/FileStore.java:2178` |
| `FileStore.backup()` | `org/h2/mvstore/FileStore.java:1432` |
| `MVStore.adoptFileStore()` | `org/h2/mvstore/MVStore.java:2183` |
| `MVStore.autoCommitBufferSize()` | `org/h2/mvstore/MVStore.java:2003` |
| `MVMap.append()` | `org/h2/mvstore/MVMap.java:1364` |
| `MVMap.ceilingKey()` | `org/h2/mvstore/MVMap.java:325` |

## 7.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `FileStore` | `org.h2.mvstore` | 2,386 | 64 |
| `MVStore` | `org.h2.mvstore` | 2,215 | 85 |
| `MVMap` | `org.h2.mvstore` | 2,181 | 102 |
| `Page` | `org.h2.mvstore` | 1,779 | 77 |
| `DataUtils` | `org.h2.mvstore` | 1,185 | 45 |

## 7.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 7.3.2.1 `FileStore`

`FileStore` 位于 `org.h2.mvstore`，2,386 行、64 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 16%，包级依赖 7 个。

### 7.3.2.2 `MVStore`

`MVStore` 位于 `org.h2.mvstore`，2,215 行、85 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 15%，包级依赖 7 个。

### 7.3.2.3 `MVMap`

`MVMap` 位于 `org.h2.mvstore`，2,181 行、102 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 15%，包级依赖 7 个。

### 7.3.2.4 `Page`

`Page` 位于 `org.h2.mvstore`，1,779 行、77 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 12%，包级依赖 7 个。

### 7.3.2.5 `DataUtils`

`DataUtils` 位于 `org.h2.mvstore`，1,185 行、45 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 7 个。

### 7.3.2.6 `RandomAccessStore`

`RandomAccessStore` 位于 `org.h2.mvstore`，851 行、10 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 7 个。

## 7.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `FileStore.accountForRemovedPage()` | `org/h2/mvstore/FileStore.java:2178` |
| `FileStore.backup()` | `org/h2/mvstore/FileStore.java:1432` |
| `FileStore.bind()` | `org/h2/mvstore/FileStore.java:281` |
| `FileStore.clear()` | `org/h2/mvstore/FileStore.java:1397` |
| `MVStore.adoptFileStore()` | `org/h2/mvstore/MVStore.java:2183` |
| `MVStore.autoCommitBufferSize()` | `org/h2/mvstore/MVStore.java:2003` |
| `MVStore.autoCommitDisabled()` | `org/h2/mvstore/MVStore.java:1981` |
| `MVStore.autoCompactFillRate()` | `org/h2/mvstore/MVStore.java:2021` |
| `MVMap.append()` | `org/h2/mvstore/MVMap.java:1364` |
| `MVMap.ceilingKey()` | `org/h2/mvstore/MVMap.java:325` |
| `MVMap.clear()` | `org/h2/mvstore/MVMap.java:441` |
| `MVMap.contains()` | `org/h2/mvstore/MVMap.java:763` |
| `Page.copy()` | `org/h2/mvstore/Page.java:382` |
| `Page.createEmptyLeaf()` | `org/h2/mvstore/Page.java:156` |
| `Page.createKeyStorage()` | `org/h2/mvstore/Page.java:1001` |
| `Page.createNode()` | `org/h2/mvstore/Page.java:188` |
| `DataUtils.appendMap()` | `org/h2/mvstore/DataUtils.java:690` |
| `DataUtils.checkArgument()` | `org/h2/mvstore/DataUtils.java:955` |
| `DataUtils.composePagePos()` | `org/h2/mvstore/DataUtils.java:627` |
| `DataUtils.composeTocElement()` | `org/h2/mvstore/DataUtils.java:660` |

## 7.4 阅读路径

读 `org.h2.mvstore` 的 20 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.mvstore` 的 package-info 与 `FileStore`，建立第7章的职责边界。
2. 再读 `FileStore` 的 64 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.mvstore`（本章最小包，14,505 行）的实现，关注容量与失败路径。

跨章衔接请对照第8章《存储与压缩算法》。

## 7.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.mvstore` | `org.h2.util`, `org.h2.compress`, `org.h2.store.fs`, `org.h2.store.fs.encrypt` |

## 7.6 设计权衡

- `org.h2.mvstore` 用 20 个文件换到 14,505 行实现，平均每文件 725 行，其中 `FileStore` 独占 2,386 行、64 个公开方法。
- 该包对外声明了 7 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.mvstore`（14,505 行）与 `org.h2.mvstore` 的职责差是本章最值得记的一条边界。

## 7.7 常见误区

- 把 `org.h2.mvstore` 的 14,505 行当作复杂度上限：`FileStore` 之外的 19 个文件多为类型族与样板。
- 只看 `FileStore` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.mvstore` 与 `org.h2.mvstore` 视为可互换：前者 20 文件、后者 20 文件，扩展点分布完全不同。

## 7.8 深读要点

规模信号：`org.h2.mvstore` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.mvstore` 依赖 7 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`FileStore` 的公开方法 64 个，读它等于读本章的主干。

## 7.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **MVStore**：详见[术语表](back/glossary.md)对应条目。
- **AbstractAggregate**：详见[术语表](back/glossary.md)对应条目。
- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **CommandContainer**：详见[术语表](back/glossary.md)对应条目。
- **DML**：详见[术语表](back/glossary.md)对应条目。
- **LOB**：详见[术语表](back/glossary.md)对应条目。
- **LocalResult**：详见[术语表](back/glossary.md)对应条目。

## 7.9 知识点清单

1. `org.h2.mvstore` 的 `FileStore`：2,386 行、64 个公开方法，职责按方法名归纳
2. `org.h2.mvstore` 的 `MVStore`：2,215 行、85 个公开方法，职责按方法名归纳

## 7.9 本章小结

- 本章覆盖 1 个包、14,505 行。
- 关键入口与源码坐标见 §7.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 7.10 延伸思考

**1. 🟢★ 指出 `org.h2.mvstore` 中 `FileStore` 与 `MVStore` 的分工差异，并给出调用方向。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**2. 🔵★★ 围绕 `org.h2.mvstore` 的 `FileStore`，说明它为什么需要独立成类型而不是并入 `MVStore`。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**3. 🟠★★★ 以 `org.h2.mvstore` 的 `FileStore` 为入口，画出一次完整调用经过的包。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.mvstore` 的一个类型，你保留 `FileStore` 还是 `MVStore`？说明代价。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

## 7.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.mvstore`：20 个文件、14,505 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.mvstore`（14,505 行）：两者的演化与版本策略不同，差异落在 `FileStore` 的 64 个公开方法里。
- 若演化与版本假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 7.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.mvstore` | `org.h2.util` | 10 |
| `org.h2.mvstore` | `org.h2.compress` | 7 |
| `org.h2.mvstore` | `org.h2.store.fs` | 5 |

## 7.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.mvstore` 与 `org.h2.mvstore` 的调用方向？`FileStore` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.mvstore` 的调用链讲到落盘或返回，并说清 `org.h2.mvstore` 与 `org.h2.mvstore` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.mvstore` 的注释与实现对不上，你信哪一边，为什么？

## 7.12 延展阅读

- 详见第8章《存储与压缩算法》。
# 第8章 索引与表达式求值

> **本章导读**：本章由源码清单汇总而成，覆盖 1 个包、4,093 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 8.1 模块版图

本章覆盖 1 个包、4,093 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.index` | 23 | 4,093 | Various table index implementations, as well as cursors to navigate in an index. |

## 8.2 核心类型

在 `org.h2.index` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 8.2.1 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |

## 8.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Index.add()` | `org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `org/h2/index/Index.java:379` |
| `IndexCondition.cloneWithIndexColumns()` | `org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `org/h2/index/IndexCondition.java:122` |
| `IndexCursor.canUseIndexForIn()` | `org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `org/h2/index/IndexCursor.java:289` |

## 8.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Index` | `org.h2.index` | 834 | 37 |
| `IndexCondition` | `org.h2.index` | 675 | 24 |
| `IndexCursor` | `org.h2.index` | 494 | 13 |
| `LinkedIndex` | `org.h2.index` | 298 | 13 |
| `RegularQueryExpressionIndex` | `org.h2.index` | 223 | 4 |

## 8.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 8.3.2.1 `Index`

`Index` 位于 `org.h2.index`，834 行、37 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 20%，包级依赖 8 个。

### 8.3.2.2 `IndexCondition`

`IndexCondition` 位于 `org.h2.index`，675 行、24 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 16%，包级依赖 8 个。

### 8.3.2.3 `IndexCursor`

`IndexCursor` 位于 `org.h2.index`，494 行、13 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 12%，包级依赖 8 个。

### 8.3.2.4 `LinkedIndex`

`LinkedIndex` 位于 `org.h2.index`，298 行、13 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 8 个。

### 8.3.2.5 `RegularQueryExpressionIndex`

`RegularQueryExpressionIndex` 位于 `org.h2.index`，223 行、4 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 8.3.2.6 `IndexType`

`IndexType` 位于 `org.h2.index`，222 行、16 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

## 8.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Index.add()` | `org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `org/h2/index/Index.java:379` |
| `Index.canFindNext()` | `org/h2/index/Index.java:302` |
| `Index.canGetFirstOrLast()` | `org/h2/index/Index.java:293` |
| `IndexCondition.cloneWithIndexColumns()` | `org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `org/h2/index/IndexCondition.java:122` |
| `IndexCondition.getColumn()` | `org/h2/index/IndexCondition.java:472` |
| `IndexCondition.getColumns()` | `org/h2/index/IndexCondition.java:485` |
| `IndexCursor.canUseIndexForIn()` | `org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `org/h2/index/IndexCursor.java:289` |
| `IndexCursor.get()` | `org/h2/index/IndexCursor.java:411` |
| `IndexCursor.getEnd()` | `org/h2/index/IndexCursor.java:406` |
| `LinkedIndex.add()` | `org/h2/index/LinkedIndex.java:61` |
| `LinkedIndex.checkRename()` | `org/h2/index/LinkedIndex.java:199` |
| `LinkedIndex.close()` | `org/h2/index/LinkedIndex.java:52` |
| `LinkedIndex.find()` | `org/h2/index/LinkedIndex.java:90` |
| `RegularQueryExpressionIndex.find()` | `org/h2/index/RegularQueryExpressionIndex.java:161` |
| `RegularQueryExpressionIndex.findByGeometry()` | `org/h2/index/RegularQueryExpressionIndex.java:166` |
| `RegularQueryExpressionIndex.getCost()` | `org/h2/index/RegularQueryExpressionIndex.java:155` |
| `RegularQueryExpressionIndex.isExpired()` | `org/h2/index/RegularQueryExpressionIndex.java:149` |

## 8.4 阅读路径

读 `org.h2.index` 的 23 个文件时，先看骨架类，再沿 `org.h2.result` 方向下钻。

1. 先读 `org.h2.index` 的 package-info 与 `Index`，建立第8章的职责边界。
2. 再读 `Index` 的 37 个公开入口，确认它对 `org.h2.result` 的调用方向与加锁方式。
3. 最后读 `org.h2.index`（本章最小包，4,093 行）的实现，关注容量与失败路径。

跨章衔接请对照第9章《索引与表达式求值》。

## 8.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.index` | `org.h2.result`, `org.h2.table`, `org.h2.value`, `org.h2.engine` |

## 8.6 设计权衡

- `org.h2.index` 用 23 个文件换到 4,093 行实现，平均每文件 177 行，其中 `Index` 独占 834 行、37 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.index`（4,093 行）与 `org.h2.index` 的职责差是本章最值得记的一条边界。

## 8.7 常见误区

- 把 `org.h2.index` 的 4,093 行当作复杂度上限：`Index` 之外的 22 个文件多为类型族与样板。
- 只看 `Index` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.index` 与 `org.h2.index` 视为可互换：前者 23 文件、后者 23 文件，扩展点分布完全不同。

## 8.8 深读要点

规模信号：`org.h2.index` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.index` 依赖 8 个 `org.h2` 包，其中 `org.h2.result` 出现最频繁。
入口信号：`Index` 的公开方法 37 个，读它等于读本章的主干。

## 8.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Index**：详见[术语表](back/glossary.md)对应条目。
- **Table**：详见[术语表](back/glossary.md)对应条目。
- **CBO / Cost-Based Optimization**：详见[术语表](back/glossary.md)对应条目。
- **Genetic Algorithm**：详见[术语表](back/glossary.md)对应条目。
- **Hybrid Strategy**：详见[术语表](back/glossary.md)对应条目。
- **IndexCondition**：详见[术语表](back/glossary.md)对应条目。
- **Optimizer**：详见[术语表](back/glossary.md)对应条目。

## 8.9 知识点清单

1. `org.h2.index` 的 `Index`：834 行、37 个公开方法，职责按方法名归纳
2. `org.h2.index` 的 `IndexCondition`：675 行、24 个公开方法，职责按方法名归纳

## 8.9 本章小结

- 本章覆盖 1 个包、4,093 行。
- 关键入口与源码坐标见 §8.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 8.10 延伸思考

**1. 🟢★ 指出 `org.h2.index` 中 `Index` 与 `IndexCondition` 的分工差异，并给出调用方向。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**2. 🔵★★ 围绕 `org.h2.index` 的 `Index`，说明它为什么需要独立成类型而不是并入 `IndexCondition`。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**3. 🟠★★★ 以 `org.h2.index` 的 `Index` 为入口，画出一次完整调用经过的包。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.index` 的一个类型，你保留 `Index` 还是 `IndexCondition`？说明代价。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

## 8.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.index`：23 个文件、4,093 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.index`（4,093 行）：两者的性能与规模策略不同，差异落在 `Index` 的 37 个公开方法里。
- 若性能与规模假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.result` 进入。

## 8.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.index` | `org.h2.result` | 51 |
| `org.h2.index` | `org.h2.table` | 41 |
| `org.h2.index` | `org.h2.value` | 27 |

## 8.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.index` 与 `org.h2.index` 的调用方向？`Index` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.index` 的调用链讲到落盘或返回，并说清 `org.h2.index` 与 `org.h2.index` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.index` 的注释与实现对不上，你信哪一边，为什么？

## 8.12 延展阅读

- 详见第9章《索引与表达式求值》。
# 第9章 SQL 解析与执行

> **本章导读**：本章由源码清单汇总而成，覆盖 4 个包、28,352 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 9.1 模块版图

本章覆盖 4 个包、28,352 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.expression.function` | 50 | 9,509 | Functions. |
| `org.h2.command.ddl` | 63 | 7,262 | Contains DDL (data definition language) and related SQL statements. |
| `org.h2.expression` | 35 | 5,832 | Expressions include mathematical operations, simple values, and others. |
| `org.h2.command.dml` | 24 | 5,749 | Contains DML (data manipulation language) and related SQL statements. |

## 9.2 核心类型

在 `org.h2.expression.function` 之外，本章还有 3 个包；下表每包取前 4 个类型，按规模降序。

### 9.2.1 `org.h2.expression.function`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ToCharFunction` | 1,156 | 8 | （无类注释，按方法名归纳） |
| `DateTimeFunction` | 1,081 | 7 | （无类注释，按方法名归纳） |
| `BitFunction` | 730 | 5 | （无类注释，按方法名归纳） |
| `MathFunction` | 405 | 3 | （无类注释，按方法名归纳） |

### 9.2.2 `org.h2.command.ddl`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `AlterTableAlterColumn` | 734 | 17 | （无类注释，按方法名归纳） |
| `AlterTableAddConstraint` | 520 | 18 | （无类注释，按方法名归纳） |
| `SequenceOptions` | 363 | 18 | （无类注释，按方法名归纳） |
| `CreateTable` | 275 | 17 | （无类注释，按方法名归纳） |

### 9.2.3 `org.h2.expression`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ExpressionColumn` | 553 | 23 | （无类注释，按方法名归纳） |
| `Expression` | 551 | 41 | （无类注释，按方法名归纳） |
| `BinaryOperation` | 455 | 6 | （无类注释，按方法名归纳） |
| `ExpressionVisitor` | 417 | 17 | （无类注释，按方法名归纳） |

### 9.2.4 `org.h2.command.dml`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ScriptCommand` | 858 | 23 | （无类注释，按方法名归纳） |
| `Set` | 652 | 9 | （无类注释，按方法名归纳） |
| `MergeUsing` | 598 | 20 | （无类注释，按方法名归纳） |
| `SetClauseList` | 507 | 3 | （无类注释，按方法名归纳） |

## 9.3 关键 API 与源码坐标

把 4 个包的关键入口与源码位置对应起来，共 12 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ToCharFunction.apply()` | `org/h2/expression/function/ToCharFunction.java:1088` |
| `ToCharFunction.clearNames()` | `org/h2/expression/function/ToCharFunction.java:552` |
| `DateTimeFunction.dateadd()` | `org/h2/expression/function/DateTimeFunction.java:656` |
| `DateTimeFunction.getField()` | `org/h2/expression/function/DateTimeFunction.java:241` |
| `BitFunction.checkArgType()` | `org/h2/expression/function/BitFunction.java:709` |
| `BitFunction.getBitwise()` | `org/h2/expression/function/BitFunction.java:455` |
| `AlterTableAlterColumn.addColumn()` | `org/h2/command/ddl/AlterTableAlterColumn.java:719` |
| `AlterTableAlterColumn.getType()` | `org/h2/command/ddl/AlterTableAlterColumn.java:710` |
| `AlterTableAddConstraint.getConstraintName()` | `org/h2/command/ddl/AlterTableAddConstraint.java:448` |
| `AlterTableAddConstraint.getIndexColumns()` | `org/h2/command/ddl/AlterTableAddConstraint.java:480` |
| `SequenceOptions.getBounds()` | `org/h2/command/ddl/SequenceOptions.java:241` |
| `SequenceOptions.getCacheSize()` | `org/h2/command/ddl/SequenceOptions.java:346` |
| `ExpressionColumn.createIndexConditions()` | `org/h2/expression/ExpressionColumn.java:499` |
| `ExpressionColumn.getAlias()` | `org/h2/expression/ExpressionColumn.java:404` |
| `Expression.addFilterConditions()` | `org/h2/expression/Expression.java:477` |
| `Expression.createIndexConditions()` | `org/h2/expression/Expression.java:354` |
| `BinaryOperation.getOperationType()` | `org/h2/expression/BinaryOperation.java:450` |
| `BinaryOperation.getUnenclosedSQL()` | `org/h2/expression/BinaryOperation.java:74` |
| `ScriptCommand.close()` | `org/h2/command/dml/ScriptCommand.java:677` |
| `ScriptCommand.collectDependencies()` | `org/h2/command/dml/ScriptCommand.java:119` |

## 9.3.1 公共类型清单

本章抽样类型按包分组，共 20 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `ToCharFunction` | `org.h2.expression.function` | 1,156 | 8 |
| `DateTimeFunction` | `org.h2.expression.function` | 1,081 | 7 |
| `BitFunction` | `org.h2.expression.function` | 730 | 5 |
| `MathFunction` | `org.h2.expression.function` | 405 | 3 |
| `DateTimeFormatFunction` | `org.h2.expression.function` | 339 | 7 |
| `AlterTableAlterColumn` | `org.h2.command.ddl` | 734 | 17 |
| `AlterTableAddConstraint` | `org.h2.command.ddl` | 520 | 18 |
| `SequenceOptions` | `org.h2.command.ddl` | 363 | 18 |
| `CreateTable` | `org.h2.command.ddl` | 275 | 17 |
| `Analyze` | `org.h2.command.ddl` | 258 | 5 |
| `ExpressionColumn` | `org.h2.expression` | 553 | 23 |
| `Expression` | `org.h2.expression` | 551 | 41 |
| `BinaryOperation` | `org.h2.expression` | 455 | 6 |
| `ExpressionVisitor` | `org.h2.expression` | 417 | 17 |
| `IntervalOperation` | `org.h2.expression` | 381 | 4 |
| `ScriptCommand` | `org.h2.command.dml` | 858 | 23 |
| `Set` | `org.h2.command.dml` | 652 | 9 |
| `MergeUsing` | `org.h2.command.dml` | 598 | 20 |
| `SetClauseList` | `org.h2.command.dml` | 507 | 3 |
| `Insert` | `org.h2.command.dml` | 456 | 19 |

## 9.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 9.3.2.1 `ToCharFunction`

`ToCharFunction` 位于 `org.h2.expression.function`，1,156 行、8 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 12%，包级依赖 8 个。

### 9.3.2.2 `DateTimeFunction`

`DateTimeFunction` 位于 `org.h2.expression.function`，1,081 行、7 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 11%，包级依赖 8 个。

### 9.3.2.3 `BitFunction`

`BitFunction` 位于 `org.h2.expression.function`，730 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 9.3.2.4 `MathFunction`

`MathFunction` 位于 `org.h2.expression.function`，405 行、3 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

### 9.3.2.5 `AlterTableAlterColumn`

`AlterTableAlterColumn` 位于 `org.h2.command.ddl`，734 行、17 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

### 9.3.2.6 `AlterTableAddConstraint`

`AlterTableAddConstraint` 位于 `org.h2.command.ddl`，520 行、18 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 8 个。

### 9.3.2.7 `SequenceOptions`

`SequenceOptions` 位于 `org.h2.command.ddl`，363 行、18 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 9.3.2.8 `CreateTable`

`CreateTable` 位于 `org.h2.command.ddl`，275 行、17 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

### 9.3.2.9 `ExpressionColumn`

`ExpressionColumn` 位于 `org.h2.expression`，553 行、23 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 9.3.2.10 `Expression`

`Expression` 位于 `org.h2.expression`，551 行、41 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 9.3.2.11 `BinaryOperation`

`BinaryOperation` 位于 `org.h2.expression`，455 行、6 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 9.3.2.12 `ExpressionVisitor`

`ExpressionVisitor` 位于 `org.h2.expression`，417 行、17 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 8 个。

### 9.3.2.13 `ScriptCommand`

`ScriptCommand` 位于 `org.h2.command.dml`，858 行、23 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 15%，包级依赖 8 个。

### 9.3.2.14 `Set`

`Set` 位于 `org.h2.command.dml`，652 行、9 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 11%，包级依赖 8 个。

### 9.3.2.15 `MergeUsing`

`MergeUsing` 位于 `org.h2.command.dml`，598 行、20 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

### 9.3.2.16 `SetClauseList`

`SetClauseList` 位于 `org.h2.command.dml`，507 行、3 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

## 9.3.2 源码坐标明细

本章主责包中 93 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `ToCharFunction.apply()` | `org/h2/expression/function/ToCharFunction.java:1088` |
| `ToCharFunction.clearNames()` | `org/h2/expression/function/ToCharFunction.java:552` |
| `ToCharFunction.getDateNames()` | `org/h2/expression/function/ToCharFunction.java:527` |
| `ToCharFunction.getName()` | `org/h2/expression/function/ToCharFunction.java:1151` |
| `DateTimeFunction.dateadd()` | `org/h2/expression/function/DateTimeFunction.java:656` |
| `DateTimeFunction.getField()` | `org/h2/expression/function/DateTimeFunction.java:241` |
| `DateTimeFunction.getFieldName()` | `org/h2/expression/function/DateTimeFunction.java:337` |
| `DateTimeFunction.getName()` | `org/h2/expression/function/DateTimeFunction.java:1076` |
| `BitFunction.checkArgType()` | `org/h2/expression/function/BitFunction.java:709` |
| `BitFunction.getBitwise()` | `org/h2/expression/function/BitFunction.java:455` |
| `BitFunction.getName()` | `org/h2/expression/function/BitFunction.java:725` |
| `BitFunction.getValue()` | `org/h2/expression/function/BitFunction.java:123` |
| `MathFunction.getName()` | `org/h2/expression/function/MathFunction.java:400` |
| `MathFunction.getValue()` | `org/h2/expression/function/MathFunction.java:87` |
| `MathFunction.optimize()` | `org/h2/expression/function/MathFunction.java:216` |
| `DateTimeFormatFunction.equals()` | `org/h2/expression/function/DateTimeFormatFunction.java:69` |
| `DateTimeFormatFunction.formatDateTime()` | `org/h2/expression/function/DateTimeFormatFunction.java:155` |
| `DateTimeFormatFunction.getName()` | `org/h2/expression/function/DateTimeFormatFunction.java:334` |
| `DateTimeFormatFunction.getValue()` | `org/h2/expression/function/DateTimeFormatFunction.java:119` |
| `StringFunction1.getName()` | `org/h2/expression/function/StringFunction1.java:279` |

## 9.4 阅读路径

读 `org.h2.expression.function` 的 50 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.expression.function` 的 package-info 与 `ToCharFunction`，建立第9章的职责边界。
2. 再读 `ToCharFunction` 的 8 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.command.dml`（本章最小包，5,749 行）的实现，关注容量与失败路径。

跨章衔接请对照第10章《SQL 解析与执行》。

## 9.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.expression.function` | `org.h2.value`, `org.h2.expression`, `org.h2.engine`, `org.h2.message` |
| `org.h2.command.ddl` | `org.h2.engine`, `org.h2.schema`, `org.h2.table`, `org.h2.command` |
| `org.h2.expression` | `org.h2.value`, `org.h2.table`, `org.h2.engine`, `org.h2.message` |
| `org.h2.command.dml` | `org.h2.engine`, `org.h2.expression`, `org.h2.result`, `org.h2.command` |

## 9.6 设计权衡

- `org.h2.expression.function` 用 50 个文件换到 9,509 行实现，平均每文件 190 行，其中 `ToCharFunction` 独占 1,156 行、8 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.command.ddl`（7,262 行）与 `org.h2.expression.function` 的职责差是本章最值得记的一条边界。

## 9.7 常见误区

- 把 `org.h2.expression.function` 的 9,509 行当作复杂度上限：`ToCharFunction` 之外的 49 个文件多为类型族与样板。
- 只看 `ToCharFunction` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.expression.function` 与 `org.h2.command.ddl` 视为可互换：前者 50 文件、后者 63 文件，扩展点分布完全不同。

## 9.8 深读要点

规模信号：`org.h2.expression.function` 占本章 34% 的实现行数，改动风险最高。
耦合信号：`org.h2.expression.function` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`ToCharFunction` 的公开方法 8 个，读它等于读本章的主干。

## 9.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **DDL**：详见[术语表](back/glossary.md)对应条目。
- **DML**：详见[术语表](back/glossary.md)对应条目。
- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Value**：详见[术语表](back/glossary.md)对应条目。
- **Append-Only**：详见[术语表](back/glossary.md)对应条目。
- **BackgroundWriter**：详见[术语表](back/glossary.md)对应条目。
- **Block**：详见[术语表](back/glossary.md)对应条目。

## 9.9 知识点清单

1. `org.h2.expression.function` 的 `ToCharFunction`：1,156 行、8 个公开方法，职责按方法名归纳
2. `org.h2.expression.function` 的 `DateTimeFunction`：1,081 行、7 个公开方法，职责按方法名归纳
3. `org.h2.command.ddl` 的 `AlterTableAlterColumn`：734 行、17 个公开方法，职责按方法名归纳
4. `org.h2.command.ddl` 的 `AlterTableAddConstraint`：520 行、18 个公开方法，职责按方法名归纳
5. `org.h2.expression` 的 `ExpressionColumn`：553 行、23 个公开方法，职责按方法名归纳
6. `org.h2.expression` 的 `Expression`：551 行、41 个公开方法，职责按方法名归纳
7. `org.h2.command.dml` 的 `ScriptCommand`：858 行、23 个公开方法，职责按方法名归纳
8. `org.h2.command.dml` 的 `Set`：652 行、9 个公开方法，职责按方法名归纳

## 9.9 本章小结

- 本章覆盖 4 个包、28,352 行。
- 关键入口与源码坐标见 §9.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 9.10 延伸思考

**1. 🟢★ 指出 `org.h2.expression.function` 中 `ToCharFunction` 与 `DateTimeFunction` 的分工差异，并给出调用方向。**

> 提示：第9章 §9.2 的表格给出 `ToCharFunction` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**2. 🔵★★ 围绕 `org.h2.command.ddl` 的 `AlterTableAlterColumn`，说明它为什么需要独立成类型而不是并入 `AlterTableAddConstraint`。**

> 提示：第9章 §9.2 的表格给出 `AlterTableAlterColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**3. 🟠★★★ 以 `org.h2.expression` 的 `ExpressionColumn` 为入口，画出一次完整调用经过的包。**

> 提示：第9章 §9.2 的表格给出 `ExpressionColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.command.dml` 的一个类型，你保留 `ScriptCommand` 还是 `Set`？说明代价。**

> 提示：第9章 §9.2 的表格给出 `ScriptCommand` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

## 9.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.expression.function`：50 个文件、9,509 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.command.ddl`（7,262 行）：两者的并发与一致性策略不同，差异落在 `ToCharFunction` 的 8 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 9.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.expression.function` | `org.h2.value` | 209 |
| `org.h2.expression.function` | `org.h2.expression` | 103 |
| `org.h2.expression.function` | `org.h2.engine` | 58 |
| `org.h2.command.ddl` | `org.h2.engine` | 151 |
| `org.h2.command.ddl` | `org.h2.schema` | 83 |
| `org.h2.command.ddl` | `org.h2.table` | 68 |
| `org.h2.expression` | `org.h2.value` | 125 |
| `org.h2.expression` | `org.h2.table` | 37 |
| `org.h2.expression` | `org.h2.engine` | 34 |
| `org.h2.command.dml` | `org.h2.engine` | 59 |
| `org.h2.command.dml` | `org.h2.expression` | 42 |
| `org.h2.command.dml` | `org.h2.result` | 40 |

## 9.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.expression.function` 与 `org.h2.command.ddl` 的调用方向？`ToCharFunction` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.expression.function` 的调用链讲到落盘或返回，并说清 `org.h2.expression.function` 与 `org.h2.command.ddl` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.expression.function` 的注释与实现对不上，你信哪一边，为什么？

## 9.12 延展阅读

- 详见第10章《SQL 解析与执行》。
# 第10章 查询优化器

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、16,254 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 10.1 模块版图

本章覆盖 2 个包、16,254 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.table` | 31 | 13,388 | Classes related to a table and table meta data. |
| `org.h2.expression.analysis` | 10 | 2,866 | Base classes for data analysis operations and implementations of window functions. |

## 10.2 核心类型

在 `org.h2.table` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 10.2.1 `org.h2.table`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | 3,299 | 6 | （无类注释，按方法名归纳） |
| `InformationSchemaTableLegacy` | 2,324 | 2 | （无类注释，按方法名归纳） |
| `Table` | 1,446 | 98 | （无类注释，按方法名归纳） |
| `TableFilter` | 1,310 | 66 | （无类注释，按方法名归纳） |

### 10.2.2 `org.h2.expression.analysis`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `WindowFrame` | 878 | 19 | （无类注释，按方法名归纳） |
| `DataAnalysisOperation` | 546 | 9 | （无类注释，按方法名归纳） |
| `WindowFunction` | 545 | 12 | （无类注释，按方法名归纳） |
| `Window` | 339 | 11 | （无类注释，按方法名归纳） |

## 10.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `InformationSchemaTable.canGetRowCount()` | `org/h2/table/InformationSchemaTable.java:3057` |
| `InformationSchemaTable.generateRows()` | `org/h2/table/InformationSchemaTable.java:881` |
| `InformationSchemaTableLegacy.generateRows()` | `org/h2/table/InformationSchemaTableLegacy.java:731` |
| `InformationSchemaTableLegacy.getMaxDataModificationId()` | `org/h2/table/InformationSchemaTableLegacy.java:2310` |
| `Table.addConstraint()` | `org/h2/table/Table.java:1109` |
| `Table.addDependencies()` | `org/h2/table/Table.java:417` |
| `WindowFrame.getEndIndex()` | `org/h2/expression/analysis/WindowFrame.java:239` |
| `WindowFrame.getExclusion()` | `org/h2/expression/analysis/WindowFrame.java:439` |
| `DataAnalysisOperation.getOverCondition()` | `org/h2/expression/analysis/DataAnalysisOperation.java:97` |
| `DataAnalysisOperation.getValue()` | `org/h2/expression/analysis/DataAnalysisOperation.java:388` |
| `WindowFunction.getCost()` | `org/h2/expression/analysis/WindowFunction.java:534` |
| `WindowFunction.getFunctionType()` | `org/h2/expression/analysis/WindowFunction.java:122` |

## 10.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | `org.h2.table` | 3,299 | 6 |
| `InformationSchemaTableLegacy` | `org.h2.table` | 2,324 | 2 |
| `Table` | `org.h2.table` | 1,446 | 98 |
| `TableFilter` | `org.h2.table` | 1,310 | 66 |
| `Column` | `org.h2.table` | 867 | 58 |
| `WindowFrame` | `org.h2.expression.analysis` | 878 | 19 |
| `DataAnalysisOperation` | `org.h2.expression.analysis` | 546 | 9 |
| `WindowFunction` | `org.h2.expression.analysis` | 545 | 12 |
| `Window` | `org.h2.expression.analysis` | 339 | 11 |
| `WindowFrameBound` | `org.h2.expression.analysis` | 165 | 6 |

## 10.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 10.3.2.1 `InformationSchemaTable`

`InformationSchemaTable` 位于 `org.h2.table`，3,299 行、6 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 25%，包级依赖 8 个。

### 10.3.2.2 `InformationSchemaTableLegacy`

`InformationSchemaTableLegacy` 位于 `org.h2.table`，2,324 行、2 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 17%，包级依赖 8 个。

### 10.3.2.3 `Table`

`Table` 位于 `org.h2.table`，1,446 行、98 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 11%，包级依赖 8 个。

### 10.3.2.4 `TableFilter`

`TableFilter` 位于 `org.h2.table`，1,310 行、66 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

### 10.3.2.5 `Column`

`Column` 位于 `org.h2.table`，867 行、58 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 10.3.2.6 `TableLink`

`TableLink` 位于 `org.h2.table`，718 行、35 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 10.3.2.7 `WindowFrame`

`WindowFrame` 位于 `org.h2.expression.analysis`，878 行、19 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 31%，包级依赖 8 个。

### 10.3.2.8 `DataAnalysisOperation`

`DataAnalysisOperation` 位于 `org.h2.expression.analysis`，546 行、9 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

### 10.3.2.9 `WindowFunction`

`WindowFunction` 位于 `org.h2.expression.analysis`，545 行、12 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

### 10.3.2.10 `Window`

`Window` 位于 `org.h2.expression.analysis`，339 行、11 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 12%，包级依赖 8 个。

### 10.3.2.11 `WindowFrameBound`

`WindowFrameBound` 位于 `org.h2.expression.analysis`，165 行、6 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 10.3.2.12 `WindowFunctionType`

`WindowFunctionType` 位于 `org.h2.expression.analysis`，142 行、3 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

## 10.3.2 源码坐标明细

本章主责包中 45 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `InformationSchemaTable.canGetRowCount()` | `org/h2/table/InformationSchemaTable.java:3057` |
| `InformationSchemaTable.generateRows()` | `org/h2/table/InformationSchemaTable.java:881` |
| `InformationSchemaTable.getMaxDataModificationId()` | `org/h2/table/InformationSchemaTable.java:2974` |
| `InformationSchemaTable.getRowCount()` | `org/h2/table/InformationSchemaTable.java:2993` |
| `InformationSchemaTableLegacy.generateRows()` | `org/h2/table/InformationSchemaTableLegacy.java:731` |
| `InformationSchemaTableLegacy.getMaxDataModificationId()` | `org/h2/table/InformationSchemaTableLegacy.java:2310` |
| `Table.addConstraint()` | `org/h2/table/Table.java:1109` |
| `Table.addDependencies()` | `org/h2/table/Table.java:417` |
| `Table.addDependentMaterializedView()` | `org/h2/table/Table.java:1091` |
| `Table.addDependentView()` | `org/h2/table/Table.java:1082` |
| `TableFilter.accept()` | `org/h2/table/TableFilter.java:1304` |
| `TableFilter.addCommonJoinColumnToExclude()` | `org/h2/table/TableFilter.java:1195` |
| `TableFilter.addCommonJoinColumns()` | `org/h2/table/TableFilter.java:1179` |
| `TableFilter.addFilter()` | `org/h2/table/TableFilter.java:676` |
| `Column.convert()` | `org/h2/table/Column.java:182` |
| `Column.copy()` | `org/h2/table/Column.java:846` |
| `Column.equals()` | `org/h2/table/Column.java:144` |
| `Column.getClone()` | `org/h2/table/Column.java:169` |
| `TableLink.addIndex()` | `org/h2/table/TableLink.java:398` |
| `TableLink.addRow()` | `org/h2/table/TableLink.java:426` |

## 10.4 阅读路径

读 `org.h2.table` 的 31 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.table` 的 package-info 与 `InformationSchemaTable`，建立第10章的职责边界。
2. 再读 `InformationSchemaTable` 的 6 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.expression.analysis`（本章最小包，2,866 行）的实现，关注容量与失败路径。

跨章衔接请对照第11章《查询优化器》。

## 10.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.table` | `org.h2.value`, `org.h2.engine`, `org.h2.result`, `org.h2.index` |
| `org.h2.expression.analysis` | `org.h2.value`, `org.h2.expression`, `org.h2.table`, `org.h2.command.query` |

## 10.6 设计权衡

- `org.h2.table` 用 31 个文件换到 13,388 行实现，平均每文件 431 行，其中 `InformationSchemaTable` 独占 3,299 行、6 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.expression.analysis`（2,866 行）与 `org.h2.table` 的职责差是本章最值得记的一条边界。

## 10.7 常见误区

- 把 `org.h2.table` 的 13,388 行当作复杂度上限：`InformationSchemaTable` 之外的 30 个文件多为类型族与样板。
- 只看 `InformationSchemaTable` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.table` 与 `org.h2.expression.analysis` 视为可互换：前者 31 文件、后者 10 文件，扩展点分布完全不同。

## 10.8 深读要点

规模信号：`org.h2.table` 占本章 82% 的实现行数，改动风险最高。
耦合信号：`org.h2.table` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`InformationSchemaTable` 的公开方法 6 个，读它等于读本章的主干。

## 10.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Table**：详见[术语表](back/glossary.md)对应条目。
- **ACID**：详见[术语表](back/glossary.md)对应条目。
- **CAS (Compare-And-Swap)**：详见[术语表](back/glossary.md)对应条目。
- **Deadlock**：详见[术语表](back/glossary.md)对应条目。
- **Lock**：详见[术语表](back/glossary.md)对应条目。
- **Meta Lock**：详见[术语表](back/glossary.md)对应条目。

## 10.9 知识点清单

1. `org.h2.table` 的 `InformationSchemaTable`：3,299 行、6 个公开方法，职责按方法名归纳
2. `org.h2.table` 的 `InformationSchemaTableLegacy`：2,324 行、2 个公开方法，职责按方法名归纳
3. `org.h2.expression.analysis` 的 `WindowFrame`：878 行、19 个公开方法，职责按方法名归纳
4. `org.h2.expression.analysis` 的 `DataAnalysisOperation`：546 行、9 个公开方法，职责按方法名归纳

## 10.9 本章小结

- 本章覆盖 2 个包、16,254 行。
- 关键入口与源码坐标见 §10.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 10.10 延伸思考

**1. 🟢★ 指出 `org.h2.table` 中 `InformationSchemaTable` 与 `InformationSchemaTableLegacy` 的分工差异，并给出调用方向。**

> 提示：第10章 §10.2 的表格给出 `InformationSchemaTable` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**2. 🔵★★ 围绕 `org.h2.expression.analysis` 的 `WindowFrame`，说明它为什么需要独立成类型而不是并入 `DataAnalysisOperation`。**

> 提示：第10章 §10.2 的表格给出 `WindowFrame` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**3. 🟠★★★ 以 `org.h2.table` 的 `InformationSchemaTable` 为入口，画出一次完整调用经过的包。**

> 提示：第10章 §10.2 的表格给出 `InformationSchemaTable` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.expression.analysis` 的一个类型，你保留 `WindowFrame` 还是 `DataAnalysisOperation`？说明代价。**

> 提示：第10章 §10.2 的表格给出 `WindowFrame` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

## 10.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.table`：31 个文件、13,388 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.expression.analysis`（2,866 行）：两者的扩展与兼容策略不同，差异落在 `InformationSchemaTable` 的 6 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 10.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.table` | `org.h2.value` | 59 |
| `org.h2.table` | `org.h2.engine` | 57 |
| `org.h2.table` | `org.h2.result` | 42 |
| `org.h2.expression.analysis` | `org.h2.value` | 12 |
| `org.h2.expression.analysis` | `org.h2.expression` | 9 |
| `org.h2.expression.analysis` | `org.h2.table` | 8 |

## 10.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.table` 与 `org.h2.expression.analysis` 的调用方向？`InformationSchemaTable` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.table` 的调用链讲到落盘或返回，并说清 `org.h2.table` 与 `org.h2.expression.analysis` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.table` 的注释与实现对不上，你信哪一边，为什么？

## 10.12 延展阅读

- 详见第11章《查询优化器》。
# 第11章 持久化

> **本章导读**：本章由源码清单汇总而成，覆盖 3 个包、18,506 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 11.1 模块版图

本章覆盖 2 个包、17,172 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.util` | 48 | 14,460 | Internal utility classes. |
| `org.h2.store` | 17 | 2,712 | Storage abstractions and helper classes. |

## 11.2 核心类型

在 `org.h2.util` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 11.2.1 `org.h2.util`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `StringUtils` | 1,415 | 55 | （无类注释，按方法名归纳） |
| `DateTimeUtils` | 1,171 | 42 | （无类注释，按方法名归纳） |
| `DateTimeTemplate` | 859 | 5 | （无类注释，按方法名归纳） |
| `IntervalUtils` | 857 | 12 | （无类注释，按方法名归纳） |

### 11.2.2 `org.h2.store`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileLock` | 514 | 8 | （无类注释，按方法名归纳） |
| `FileStore` | 513 | 22 | （无类注释，按方法名归纳） |
| `Data` | 220 | 13 | （无类注释，按方法名归纳） |
| `RecoverTester` | 176 | 3 | （无类注释，按方法名归纳） |

## 11.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `StringUtils.addAsterisk()` | `org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `org/h2/util/StringUtils.java:1277` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `org/h2/util/DateTimeUtils.java:857` |
| `DateTimeTemplate.format()` | `org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `org/h2/util/DateTimeTemplate.java:430` |
| `FileLock.getFileLockMethod()` | `org/h2/store/FileLock.java:458` |
| `FileLock.getUniqueId()` | `org/h2/store/FileLock.java:472` |
| `FileStore.autoDelete()` | `org/h2/store/FileStore.java:429` |
| `FileStore.close()` | `org/h2/store/FileStore.java:221` |
| `Data.checkCapacity()` | `org/h2/store/Data.java:171` |
| `Data.copyString()` | `org/h2/store/Data.java:204` |

## 11.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `StringUtils` | `org.h2.util` | 1,415 | 55 |
| `DateTimeUtils` | `org.h2.util` | 1,171 | 42 |
| `DateTimeTemplate` | `org.h2.util` | 859 | 5 |
| `IntervalUtils` | `org.h2.util` | 857 | 12 |
| `Utils` | `org.h2.util` | 832 | 34 |
| `FileLock` | `org.h2.store` | 514 | 8 |
| `FileStore` | `org.h2.store` | 513 | 22 |
| `Data` | `org.h2.store` | 220 | 13 |
| `RecoverTester` | `org.h2.store` | 176 | 3 |
| `FileStoreInputStream` | `org.h2.store` | 155 | 5 |

## 11.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 11.3.2.1 `StringUtils`

`StringUtils` 位于 `org.h2.util`，1,415 行、55 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

### 11.3.2.2 `DateTimeUtils`

`DateTimeUtils` 位于 `org.h2.util`，1,171 行、42 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 11.3.2.3 `DateTimeTemplate`

`DateTimeTemplate` 位于 `org.h2.util`，859 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 11.3.2.4 `IntervalUtils`

`IntervalUtils` 位于 `org.h2.util`，857 行、12 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 11.3.2.5 `Utils`

`Utils` 位于 `org.h2.util`，832 行、34 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 11.3.2.6 `JdbcUtils`

`JdbcUtils` 位于 `org.h2.util`，785 行、17 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

### 11.3.2.7 `FileLock`

`FileLock` 位于 `org.h2.store`，514 行、8 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

### 11.3.2.8 `FileStore`

`FileStore` 位于 `org.h2.store`，513 行、22 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

### 11.3.2.9 `Data`

`Data` 位于 `org.h2.store`，220 行、13 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 11.3.2.10 `RecoverTester`

`RecoverTester` 位于 `org.h2.store`，176 行、3 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 11.3.2.11 `FileStoreInputStream`

`FileStoreInputStream` 位于 `org.h2.store`，155 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

### 11.3.2.12 `DataReader`

`DataReader` 位于 `org.h2.store`，133 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

## 11.3.2 源码坐标明细

本章主责包中 45 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `StringUtils.addAsterisk()` | `org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `org/h2/util/StringUtils.java:1277` |
| `StringUtils.appendToLength()` | `org/h2/util/StringUtils.java:1360` |
| `StringUtils.appendTwoDigits()` | `org/h2/util/StringUtils.java:1327` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `org/h2/util/DateTimeUtils.java:857` |
| `DateTimeUtils.appendDate()` | `org/h2/util/DateTimeUtils.java:981` |
| `DateTimeUtils.appendTime()` | `org/h2/util/DateTimeUtils.java:1003` |
| `DateTimeTemplate.format()` | `org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `org/h2/util/DateTimeTemplate.java:430` |
| `DateTimeTemplate.parse()` | `org/h2/util/DateTimeTemplate.java:183` |
| `IntervalUtils.appendInterval()` | `org/h2/util/IntervalUtils.java:402` |
| `IntervalUtils.daysFromInterval()` | `org/h2/util/IntervalUtils.java:724` |
| `IntervalUtils.hoursFromInterval()` | `org/h2/util/IntervalUtils.java:753` |
| `IntervalUtils.intervalFromAbsolute()` | `org/h2/util/IntervalUtils.java:540` |
| `Utils.callMethod()` | `org/h2/util/Utils.java:465` |
| `Utils.callStaticMethod()` | `org/h2/util/Utils.java:446` |
| `Utils.cloneByteArray()` | `org/h2/util/Utils.java:218` |
| `Utils.collectGarbage()` | `org/h2/util/Utils.java:289` |
| `JdbcUtils.addClassFactory()` | `org/h2/util/JdbcUtils.java:114` |

## 11.4 阅读路径

读 `org.h2.util` 的 48 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.util` 的 package-info 与 `StringUtils`，建立第11章的职责边界。
2. 再读 `StringUtils` 的 55 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.store`（本章最小包，2,712 行）的实现，关注容量与失败路径。

跨章衔接请对照第12章《并发控制》。

## 11.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.util` | `org.h2.value`, `org.h2.engine`, `org.h2.message`, `org.h2.api` |
| `org.h2.store` | `org.h2.engine`, `org.h2.util`, `org.h2.message`, `org.h2.value` |

## 11.6 设计权衡

- `org.h2.util` 用 48 个文件换到 14,460 行实现，平均每文件 301 行，其中 `StringUtils` 独占 1,415 行、55 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.store`（2,712 行）与 `org.h2.util` 的职责差是本章最值得记的一条边界。

## 11.7 常见误区

- 把 `org.h2.util` 的 14,460 行当作复杂度上限：`StringUtils` 之外的 47 个文件多为类型族与样板。
- 只看 `StringUtils` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.util` 与 `org.h2.store` 视为可互换：前者 48 文件、后者 17 文件，扩展点分布完全不同。

## 11.8 深读要点

规模信号：`org.h2.util` 占本章 84% 的实现行数，改动风险最高。
耦合信号：`org.h2.util` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`StringUtils` 的公开方法 55 个，读它等于读本章的主干。

## 11.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **ISODEBUG**：详见[术语表](back/glossary.md)对应条目。
- **Maven**：详见[术语表](back/glossary.md)对应条目。
- **MVStoreTool**：详见[术语表](back/glossary.md)对应条目。
- **Query**：详见[术语表](back/glossary.md)对应条目。
- **Select**：详见[术语表](back/glossary.md)对应条目。
- **SmallLRUCache**：详见[术语表](back/glossary.md)对应条目。

## 11.9 知识点清单

1. `org.h2.util` 的 `StringUtils`：1,415 行、55 个公开方法，职责按方法名归纳
2. `org.h2.util` 的 `DateTimeUtils`：1,171 行、42 个公开方法，职责按方法名归纳
3. `org.h2.store` 的 `FileLock`：514 行、8 个公开方法，职责按方法名归纳
4. `org.h2.store` 的 `FileStore`：513 行、22 个公开方法，职责按方法名归纳

## 11.9 本章小结

- 本章覆盖 2 个包、17,172 行。
- 关键入口与源码坐标见 §11.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 11.10 延伸思考

**1. 🟢★ 指出 `org.h2.util` 中 `StringUtils` 与 `DateTimeUtils` 的分工差异，并给出调用方向。**

> 提示：第11章 §11.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**2. 🔵★★ 围绕 `org.h2.store` 的 `FileLock`，说明它为什么需要独立成类型而不是并入 `FileStore`。**

> 提示：第11章 §11.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**3. 🟠★★★ 以 `org.h2.util` 的 `StringUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第11章 §11.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.store` 的一个类型，你保留 `FileLock` 还是 `FileStore`？说明代价。**

> 提示：第11章 §11.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

## 11.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.util`：48 个文件、14,460 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.store`（2,712 行）：两者的演化与版本策略不同，差异落在 `StringUtils` 的 55 个公开方法里。
- 若演化与版本假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 11.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.util` | `org.h2.value` | 35 |
| `org.h2.util` | `org.h2.engine` | 18 |
| `org.h2.util` | `org.h2.message` | 16 |
| `org.h2.store` | `org.h2.engine` | 16 |
| `org.h2.store` | `org.h2.util` | 14 |
| `org.h2.store` | `org.h2.message` | 11 |

## 11.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.util` 与 `org.h2.store` 的调用方向？`StringUtils` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.util` 的调用链讲到落盘或返回，并说清 `org.h2.util` 与 `org.h2.store` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.util` 的注释与实现对不上，你信哪一边，为什么？

## 11.12 延展阅读

- 详见第12章《并发控制》。

# 第12章 并发控制

## 12.1 模块版图

本章覆盖 1 个包、1,334 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.store.fs` | 7 | 1,334 | A file system abstraction. |

## 12.2 核心类型

在 `org.h2.store.fs` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 12.2.1 `org.h2.store.fs`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileUtils` | 477 | 29 | （无类注释，按方法名归纳） |
| `FilePath` | 353 | 28 | （无类注释，按方法名归纳） |
| `FilePathWrapper` | 171 | 22 | （无类注释，按方法名归纳） |
| `FakeFileChannel` | 112 | 16 | （无类注释，按方法名归纳） |

## 12.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `FileUtils.canWrite()` | `org/h2/store/fs/FileUtils.java:317` |
| `FileUtils.createDirectories()` | `org/h2/store/fs/FileUtils.java:372` |
| `FilePath.canWrite()` | `org/h2/store/fs/FilePath.java:201` |
| `FilePath.createDirectory()` | `org/h2/store/fs/FilePath.java:206` |
| `FilePathWrapper.canWrite()` | `org/h2/store/fs/FilePathWrapper.java:72` |
| `FilePathWrapper.createDirectory()` | `org/h2/store/fs/FilePathWrapper.java:77` |

## 12.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `FileUtils` | `org.h2.store.fs` | 477 | 29 |
| `FilePath` | `org.h2.store.fs` | 353 | 28 |
| `FilePathWrapper` | `org.h2.store.fs` | 171 | 22 |
| `FakeFileChannel` | `org.h2.store.fs` | 112 | 16 |
| `FileBase` | `org.h2.store.fs` | 92 | 10 |

## 12.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 12.3.2.1 `FileUtils`

`FileUtils` 位于 `org.h2.store.fs`，477 行、29 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 36%，包级依赖 2 个。

### 12.3.2.2 `FilePath`

`FilePath` 位于 `org.h2.store.fs`，353 行、28 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 26%，包级依赖 2 个。

### 12.3.2.3 `FilePathWrapper`

`FilePathWrapper` 位于 `org.h2.store.fs`，171 行、22 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 13%，包级依赖 2 个。

### 12.3.2.4 `FakeFileChannel`

`FakeFileChannel` 位于 `org.h2.store.fs`，112 行、16 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 2 个。

### 12.3.2.5 `FileBase`

`FileBase` 位于 `org.h2.store.fs`，92 行、10 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 2 个。

### 12.3.2.6 `FileBaseDefault`

`FileBaseDefault` 位于 `org.h2.store.fs`，69 行、5 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 2 个。

## 12.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `FileUtils.canWrite()` | `org/h2/store/fs/FileUtils.java:317` |
| `FileUtils.createDirectories()` | `org/h2/store/fs/FileUtils.java:372` |
| `FileUtils.createDirectory()` | `org/h2/store/fs/FileUtils.java:84` |
| `FileUtils.createFile()` | `org/h2/store/fs/FileUtils.java:96` |
| `FilePath.canWrite()` | `org/h2/store/fs/FilePath.java:201` |
| `FilePath.createDirectory()` | `org/h2/store/fs/FilePath.java:206` |
| `FilePath.createFile()` | `org/h2/store/fs/FilePath.java:132` |
| `FilePath.createTempFile()` | `org/h2/store/fs/FilePath.java:284` |
| `FilePathWrapper.canWrite()` | `org/h2/store/fs/FilePathWrapper.java:72` |
| `FilePathWrapper.createDirectory()` | `org/h2/store/fs/FilePathWrapper.java:77` |
| `FilePathWrapper.createFile()` | `org/h2/store/fs/FilePathWrapper.java:82` |
| `FilePathWrapper.createTempFile()` | `org/h2/store/fs/FilePathWrapper.java:166` |
| `FakeFileChannel.force()` | `org/h2/store/fs/FakeFileChannel.java:109` |
| `FakeFileChannel.lock()` | `org/h2/store/fs/FakeFileChannel.java:34` |
| `FakeFileChannel.map()` | `org/h2/store/fs/FakeFileChannel.java:39` |
| `FakeFileChannel.position()` | `org/h2/store/fs/FakeFileChannel.java:44` |
| `FileBase.force()` | `org/h2/store/fs/FileBase.java:42` |
| `FileBase.lock()` | `org/h2/store/fs/FileBase.java:52` |
| `FileBase.map()` | `org/h2/store/fs/FileBase.java:58` |
| `FileBase.read()` | `org/h2/store/fs/FileBase.java:22` |

## 12.4 阅读路径

读 `org.h2.store.fs` 的 7 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.store.fs` 的 package-info 与 `FileUtils`，建立第12章的职责边界。
2. 再读 `FileUtils` 的 29 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.store.fs`（本章最小包，1,334 行）的实现，关注容量与失败路径。

跨章衔接请对照第11章《持久化》。

## 12.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.store.fs` | `org.h2.util`, `org.h2.engine` |

## 12.6 设计权衡

- `org.h2.store.fs` 用 7 个文件换到 1,334 行实现，平均每文件 190 行，其中 `FileUtils` 独占 477 行、29 个公开方法。
- 该包对外声明了 2 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.store.fs`（1,334 行）与 `org.h2.store.fs` 的职责差是本章最值得记的一条边界。

## 12.7 常见误区

- 把 `org.h2.store.fs` 的 1,334 行当作复杂度上限：`FileUtils` 之外的 6 个文件多为类型族与样板。
- 只看 `FileUtils` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.store.fs` 与 `org.h2.store.fs` 视为可互换：前者 7 文件、后者 7 文件，扩展点分布完全不同。

## 12.8 深读要点

规模信号：`org.h2.store.fs` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.store.fs` 依赖 2 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`FileUtils` 的公开方法 29 个，读它等于读本章的主干。

## 12.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Bloom 过滤**：详见[术语表](back/glossary.md)对应条目。
- **Single Writer**：详见[术语表](back/glossary.md)对应条目。
- **TransactionMap**：详见[术语表](back/glossary.md)对应条目。
- **Write Amplification**：详见[术语表](back/glossary.md)对应条目。

## 12.9 知识点清单

1. `org.h2.store.fs` 的 `FileUtils`：477 行、29 个公开方法，职责按方法名归纳
2. `org.h2.store.fs` 的 `FilePath`：353 行、28 个公开方法，职责按方法名归纳

## 12.9 本章小结

- 本章覆盖 1 个包、1,334 行。
- 关键入口与源码坐标见 §12.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 12.10 延伸思考

**1. 🟢★ 指出 `org.h2.store.fs` 中 `FileUtils` 与 `FilePath` 的分工差异，并给出调用方向。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**2. 🔵★★ 围绕 `org.h2.store.fs` 的 `FileUtils`，说明它为什么需要独立成类型而不是并入 `FilePath`。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**3. 🟠★★★ 以 `org.h2.store.fs` 的 `FileUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.store.fs` 的一个类型，你保留 `FileUtils` 还是 `FilePath`？说明代价。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

## 12.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.store.fs`：7 个文件、1,334 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.store.fs`（1,334 行）：两者的性能与规模策略不同，差异落在 `FileUtils` 的 29 个公开方法里。
- 若性能与规模假设被打破（2 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 12.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.store.fs` | `org.h2.util` | 1 |
| `org.h2.store.fs` | `org.h2.engine` | 1 |

## 12.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.store.fs` 与 `org.h2.store.fs` 的调用方向？`FileUtils` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.store.fs` 的调用链讲到落盘或返回，并说清 `org.h2.store.fs` 与 `org.h2.store.fs` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.store.fs` 的注释与实现对不上，你信哪一边，为什么？

## 12.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.store.fs` | 第11章《持久化》 |

## 12.12 延展阅读

- 详见第11章《持久化》。
# 第13章 二次开发指南

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、28,187 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 13.1 模块版图

本章覆盖 1 个包、17,319 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.jdbc` | 27 | 17,319 | Implementation of the JDBC API (package { |

## 13.2 核心类型

在 `org.h2.jdbc` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 13.2.1 `org.h2.jdbc`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `JdbcResultSet` | 4,291 | 199 | （无类注释，按方法名归纳） |
| `JdbcDatabaseMetaData` | 2,756 | 177 | （无类注释，按方法名归纳） |
| `JdbcConnection` | 1,930 | 62 | （无类注释，按方法名归纳） |
| `JdbcCallableStatement` | 1,863 | 117 | （无类注释，按方法名归纳） |

## 13.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `JdbcResultSet.absolute()` | `org/h2/jdbc/JdbcResultSet.java:3173` |
| `JdbcResultSet.afterLast()` | `org/h2/jdbc/JdbcResultSet.java:3105` |
| `JdbcDatabaseMetaData.allProceduresAreCallable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:305` |
| `JdbcDatabaseMetaData.allTablesAreSelectable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:316` |
| `JdbcConnection.abort()` | `org/h2/jdbc/JdbcConnection.java:1832` |
| `JdbcConnection.clearWarnings()` | `org/h2/jdbc/JdbcConnection.java:655` |

## 13.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `JdbcResultSet` | `org.h2.jdbc` | 4,291 | 199 |
| `JdbcDatabaseMetaData` | `org.h2.jdbc` | 2,756 | 177 |
| `JdbcConnection` | `org.h2.jdbc` | 1,930 | 62 |
| `JdbcCallableStatement` | `org.h2.jdbc` | 1,863 | 117 |
| `JdbcPreparedStatement` | `org.h2.jdbc` | 1,629 | 65 |

## 13.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 13.3.2.1 `JdbcResultSet`

`JdbcResultSet` 位于 `org.h2.jdbc`，4,291 行、199 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 25%，包级依赖 8 个。

### 13.3.2.2 `JdbcDatabaseMetaData`

`JdbcDatabaseMetaData` 位于 `org.h2.jdbc`，2,756 行、177 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 16%，包级依赖 8 个。

### 13.3.2.3 `JdbcConnection`

`JdbcConnection` 位于 `org.h2.jdbc`，1,930 行、62 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 11%，包级依赖 8 个。

### 13.3.2.4 `JdbcCallableStatement`

`JdbcCallableStatement` 位于 `org.h2.jdbc`，1,863 行、117 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 11%，包级依赖 8 个。

### 13.3.2.5 `JdbcPreparedStatement`

`JdbcPreparedStatement` 位于 `org.h2.jdbc`，1,629 行、65 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 13.3.2.6 `JdbcStatement`

`JdbcStatement` 位于 `org.h2.jdbc`，1,502 行、56 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

## 13.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `JdbcResultSet.absolute()` | `org/h2/jdbc/JdbcResultSet.java:3173` |
| `JdbcResultSet.afterLast()` | `org/h2/jdbc/JdbcResultSet.java:3105` |
| `JdbcResultSet.beforeFirst()` | `org/h2/jdbc/JdbcResultSet.java:3086` |
| `JdbcResultSet.cancelRowUpdates()` | `org/h2/jdbc/JdbcResultSet.java:3432` |
| `JdbcDatabaseMetaData.allProceduresAreCallable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:305` |
| `JdbcDatabaseMetaData.allTablesAreSelectable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:316` |
| `JdbcDatabaseMetaData.autoCommitFailureClosesAllResultSets()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:2598` |
| `JdbcDatabaseMetaData.dataDefinitionCausesTransactionCommit()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:1814` |
| `JdbcConnection.abort()` | `org/h2/jdbc/JdbcConnection.java:1832` |
| `JdbcConnection.clearWarnings()` | `org/h2/jdbc/JdbcConnection.java:655` |
| `JdbcConnection.close()` | `org/h2/jdbc/JdbcConnection.java:355` |
| `JdbcConnection.commit()` | `org/h2/jdbc/JdbcConnection.java:480` |
| `JdbcCallableStatement.executeLargeUpdate()` | `org/h2/jdbc/JdbcCallableStatement.java:119` |
| `JdbcCallableStatement.executeUpdate()` | `org/h2/jdbc/JdbcCallableStatement.java:89` |
| `JdbcCallableStatement.getArray()` | `org/h2/jdbc/JdbcCallableStatement.java:512` |
| `JdbcCallableStatement.getBigDecimal()` | `org/h2/jdbc/JdbcCallableStatement.java:351` |
| `JdbcPreparedStatement.addBatch()` | `org/h2/jdbc/JdbcPreparedStatement.java:326` |
| `JdbcPreparedStatement.clearBatch()` | `org/h2/jdbc/JdbcPreparedStatement.java:1222` |
| `JdbcPreparedStatement.clearParameters()` | `org/h2/jdbc/JdbcPreparedStatement.java:289` |
| `JdbcPreparedStatement.close()` | `org/h2/jdbc/JdbcPreparedStatement.java:1238` |

## 13.4 阅读路径

读 `org.h2.jdbc` 的 27 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.jdbc` 的 package-info 与 `JdbcResultSet`，建立第13章的职责边界。
2. 再读 `JdbcResultSet` 的 199 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.jdbc`（本章最小包，17,319 行）的实现，关注容量与失败路径。

跨章衔接请对照第14章《全书总结》。

## 13.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.jdbc` | `org.h2.value`, `org.h2.message`, `org.h2.util`, `org.h2.engine` |

## 13.6 设计权衡

- `org.h2.jdbc` 用 27 个文件换到 17,319 行实现，平均每文件 641 行，其中 `JdbcResultSet` 独占 4,291 行、199 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.jdbc`（17,319 行）与 `org.h2.jdbc` 的职责差是本章最值得记的一条边界。

## 13.7 常见误区

- 把 `org.h2.jdbc` 的 17,319 行当作复杂度上限：`JdbcResultSet` 之外的 26 个文件多为类型族与样板。
- 只看 `JdbcResultSet` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.jdbc` 与 `org.h2.jdbc` 视为可互换：前者 27 文件、后者 27 文件，扩展点分布完全不同。

## 13.8 深读要点

规模信号：`org.h2.jdbc` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.jdbc` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`JdbcResultSet` 的公开方法 199 个，读它等于读本章的主干。

## 13.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。

## 13.9 知识点清单

1. `org.h2.jdbc` 的 `JdbcResultSet`：4,291 行、199 个公开方法，职责按方法名归纳
2. `org.h2.jdbc` 的 `JdbcDatabaseMetaData`：2,756 行、177 个公开方法，职责按方法名归纳

## 13.9 本章小结

- 本章覆盖 1 个包、17,319 行。
- 关键入口与源码坐标见 §13.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 13.10 延伸思考

**1. 🟢★ 指出 `org.h2.jdbc` 中 `JdbcResultSet` 与 `JdbcDatabaseMetaData` 的分工差异，并给出调用方向。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**2. 🔵★★ 围绕 `org.h2.jdbc` 的 `JdbcResultSet`，说明它为什么需要独立成类型而不是并入 `JdbcDatabaseMetaData`。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**3. 🟠★★★ 以 `org.h2.jdbc` 的 `JdbcResultSet` 为入口，画出一次完整调用经过的包。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.jdbc` 的一个类型，你保留 `JdbcResultSet` 还是 `JdbcDatabaseMetaData`？说明代价。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

## 13.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.jdbc`：27 个文件、17,319 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.jdbc`（17,319 行）：两者的并发与一致性策略不同，差异落在 `JdbcResultSet` 的 199 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 13.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.jdbc` | `org.h2.value` | 57 |
| `org.h2.jdbc` | `org.h2.message` | 43 |
| `org.h2.jdbc` | `org.h2.util` | 19 |

## 13.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.jdbc` 与 `org.h2.jdbc` 的调用方向？`JdbcResultSet` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.jdbc` 的调用链讲到落盘或返回，并说清 `org.h2.jdbc` 与 `org.h2.jdbc` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.jdbc` 的注释与实现对不上，你信哪一边，为什么？

## 13.12 延展阅读

- 详见第14章《全书总结》。

# 第14章 全书总结

## 14.1 模块版图

本章覆盖 1 个包、10,868 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.tools` | 23 | 10,868 | Various tools. |

## 14.2 核心类型

在 `org.h2.tools` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 14.2.1 `org.h2.tools`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `SimpleResultSet` | 2,480 | 228 | （无类注释，按方法名归纳） |
| `Csv` | 986 | 33 | （无类注释，按方法名归纳） |
| `Recover` | 922 | 18 | （无类注释，按方法名归纳） |
| `Server` | 823 | 19 | （无类注释，按方法名归纳） |

## 14.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `SimpleResultSet.absolute()` | `org/h2/tools/SimpleResultSet.java:2229` |
| `SimpleResultSet.addColumn()` | `org/h2/tools/SimpleResultSet.java:100` |
| `Csv.close()` | `org/h2/tools/Csv.java:639` |
| `Csv.getBinaryColumns()` | `org/h2/tools/Csv.java:909` |
| `Recover.checkPowerOff()` | `org/h2/tools/Recover.java:857` |
| `Recover.checkWritingAllowed()` | `org/h2/tools/Recover.java:865` |

## 14.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `SimpleResultSet` | `org.h2.tools` | 2,480 | 228 |
| `Csv` | `org.h2.tools` | 986 | 33 |
| `Recover` | `org.h2.tools` | 922 | 18 |
| `Server` | `org.h2.tools` | 823 | 19 |
| `DirectRecover` | `org.h2.tools` | 767 | 11 |

## 14.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 14.3.2.1 `SimpleResultSet`

`SimpleResultSet` 位于 `org.h2.tools`，2,480 行、228 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 23%，包级依赖 8 个。

### 14.3.2.2 `Csv`

`Csv` 位于 `org.h2.tools`，986 行、33 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

### 14.3.2.3 `Recover`

`Recover` 位于 `org.h2.tools`，922 行、18 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 14.3.2.4 `Server`

`Server` 位于 `org.h2.tools`，823 行、19 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

### 14.3.2.5 `DirectRecover`

`DirectRecover` 位于 `org.h2.tools`，767 行、11 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 8 个。

### 14.3.2.6 `Shell`

`Shell` 位于 `org.h2.tools`，639 行、7 个公开方法。

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

## 14.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `SimpleResultSet.absolute()` | `org/h2/tools/SimpleResultSet.java:2229` |
| `SimpleResultSet.addColumn()` | `org/h2/tools/SimpleResultSet.java:100` |
| `SimpleResultSet.addRow()` | `org/h2/tools/SimpleResultSet.java:133` |
| `SimpleResultSet.afterLast()` | `org/h2/tools/SimpleResultSet.java:2069` |
| `Csv.close()` | `org/h2/tools/Csv.java:639` |
| `Csv.getBinaryColumns()` | `org/h2/tools/Csv.java:909` |
| `Csv.getCaseSensitiveColumnNames()` | `org/h2/tools/Csv.java:687` |
| `Csv.getEscapeCharacter()` | `org/h2/tools/Csv.java:782` |
| `Recover.checkPowerOff()` | `org/h2/tools/Recover.java:857` |
| `Recover.checkWritingAllowed()` | `org/h2/tools/Recover.java:865` |
| `Recover.execute()` | `org/h2/tools/Recover.java:239` |
| `Recover.getCompareMode()` | `org/h2/tools/Recover.java:918` |
| `Server.createPgServer()` | `org/h2/tools/Server.java:539` |
| `Server.createTcpServer()` | `org/h2/tools/Server.java:511` |
| `Server.createWebServer()` | `org/h2/tools/Server.java:466` |
| `Server.getPort()` | `org/h2/tools/Server.java:640` |
| `DirectRecover.close()` | `org/h2/tools/DirectRecover.java:462` |
| `DirectRecover.execute()` | `org/h2/tools/DirectRecover.java:759` |
| `DirectRecover.finish()` | `org/h2/tools/DirectRecover.java:178` |
| `DirectRecover.getAvailableCompressionTypes()` | `org/h2/tools/DirectRecover.java:723` |

## 14.4 阅读路径

读 `org.h2.tools` 的 23 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.tools` 的 package-info 与 `SimpleResultSet`，建立第14章的职责边界。
2. 再读 `SimpleResultSet` 的 228 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.tools`（本章最小包，10,868 行）的实现，关注容量与失败路径。

跨章衔接请对照第13章《二次开发指南》。

## 14.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.tools` | `org.h2.util`, `org.h2.engine`, `org.h2.value`, `org.h2.message` |

## 14.6 设计权衡

- `org.h2.tools` 用 23 个文件换到 10,868 行实现，平均每文件 472 行，其中 `SimpleResultSet` 独占 2,480 行、228 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.tools`（10,868 行）与 `org.h2.tools` 的职责差是本章最值得记的一条边界。

## 14.7 常见误区

- 把 `org.h2.tools` 的 10,868 行当作复杂度上限：`SimpleResultSet` 之外的 22 个文件多为类型族与样板。
- 只看 `SimpleResultSet` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.tools` 与 `org.h2.tools` 视为可互换：前者 23 文件、后者 23 文件，扩展点分布完全不同。

## 14.8 深读要点

规模信号：`org.h2.tools` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.tools` 依赖 8 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`SimpleResultSet` 的公开方法 228 个，读它等于读本章的主干。

## 14.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。

## 14.9 知识点清单

1. `org.h2.tools` 的 `SimpleResultSet`：2,480 行、228 个公开方法，职责按方法名归纳
2. `org.h2.tools` 的 `Csv`：986 行、33 个公开方法，职责按方法名归纳

## 14.9 本章小结

- 本章覆盖 1 个包、10,868 行。
- 关键入口与源码坐标见 §14.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 14.10 延伸思考

**1. 🟢★ 指出 `org.h2.tools` 中 `SimpleResultSet` 与 `Csv` 的分工差异，并给出调用方向。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**2. 🔵★★ 围绕 `org.h2.tools` 的 `SimpleResultSet`，说明它为什么需要独立成类型而不是并入 `Csv`。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**3. 🟠★★★ 以 `org.h2.tools` 的 `SimpleResultSet` 为入口，画出一次完整调用经过的包。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.tools` 的一个类型，你保留 `SimpleResultSet` 还是 `Csv`？说明代价。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

## 14.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.tools`：23 个文件、10,868 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.tools`（10,868 行）：两者的扩展与兼容策略不同，差异落在 `SimpleResultSet` 的 228 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 14.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.tools` | `org.h2.util` | 53 |
| `org.h2.tools` | `org.h2.engine` | 14 |
| `org.h2.tools` | `org.h2.value` | 14 |

## 14.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.tools` 与 `org.h2.tools` 的调用方向？`SimpleResultSet` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.tools` 的调用链讲到落盘或返回，并说清 `org.h2.tools` 与 `org.h2.tools` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.tools` 的注释与实现对不上，你信哪一边，为什么？

## 14.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.tools` | 第13章《二次开发指南》 |

## 14.12 延展阅读

- 详见第13章《二次开发指南》。
# 附录 A：端到端案例研究

> 本附录用三个端到端案例把分散在第 1-10 章的关键论述连成单线叙事：
> 案例 A 跟踪一条 SELECT 从 JDBC 入口到磁盘的全过程；
> 案例 B 拆解一次 INSERT+UPDATE+COMMIT 事务在内存与磁盘上的事件链；
> 案例 C 演示崩溃后恢复启动的决策路径，包括正常分支与异常分支。
> 每个步骤均给出 §X.Y 回指，便于读者按需深入原章节。

本附录不引入新的源码论断——所有事实都来自正文章节，
附录的价值在于把按主题切分的章节重新拼成按时间切分的故事，
让读者获得完整的端到端心智模型。

---

## A.1 案例 A：一条 SELECT 从 JDBC 到磁盘

凌晨三点，某线上服务执行了一条最普通不过的语句：

```sql
SELECT * FROM users WHERE id = 42;
```

调用方拿到结果用了不到十毫秒，但这十毫秒里 H2 引擎穿过了 JDBC、Session、
Parser、Optimizer、TableFilter、B-Tree、Page Cache 与 FileStore 八个层次。
本案例以这条等值点查为主线，把分散在第 4、6、7、8、9 章的关键节点重新
串接成一条端到端的执行轨迹，并在每一步给出 §X.Y 回指，便于读者按图索骥。
本节不复述原文段落，只做"叙事重组"——把固定步骤按时间顺序压扁成一根
单线，再以子流程图刻画其内部决策。

如图 A-1 所示，全链路泳道图给出整体形貌；后续 A-2 至 A-6 各自聚焦一个
子阶段。读者若只想了解整体，可只读 §A.1.1 与 §A.1.8；若想深入某一步，
可沿 `详见 §X.Y` 跳转回原章节。

**图 A-1: 串联 SELECT 八泳道执行轨迹**

```text
  时间轴 ──►       准备阶段                     执行阶段
  ┌──────────┐  ┌────────────────────┐  ┌───────────────────────┐
  │  JDBC    │  │ executeQuery(sql)  │  │ rs.next() / getInt()   │
  │          │  │  ↓ prepareCommand  │  │  ↑ JdbcResultSet 包装  │
  └────┬─────┘  └──────────┬─────────┘  └───────────▲───────────┘
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐  ┌────────────────────┐  ┌───────────┴───────────┐
  │ Session  │  │ prepareLocal()     │  │ lock() / unlock()      │
  │ Local    │  │  查询缓存检查       │  │ checkParameters()      │
  └────┬─────┘  └──────────┬─────────┘  └───────────▲───────────┘
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐  ┌────────────────────┐              │
  │ Parser   │  │ tokenize()         │              │
  │          │  │  parseSelect()     │              │
  │          │  │  → Select 节点      │              │
  └────┬─────┘  └──────────┬─────────┘              │
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐  ┌────────────────────┐              │
  │ Optimizer│  │ optimize()         │              │
  │          │  │  cost = rows*N+...  │              │
  │          │  │  PlanItem 选定      │              │
  └────┬─────┘  └──────────┬─────────┘              │
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐                      ┌──────────────────────────┐
  │TableFiltr│◄─── plan ────────────│ topTableFilter.next()    │
  │          │                      │  cursor.find(SearchRow)  │
  │          │                      │  isOk(filterCondition)   │
  └────┬─────┘                      └────────────┬─────────────┘
       │                                         │
       ▼                                         ▼
  ┌──────────┐                      ┌──────────────────────────┐
  │  B-Tree  │                      │ MVMap.get(key=42)        │
  │  索引    │                      │  Page.binarySearch()     │
  └────┬─────┘                      └────────────┬─────────────┘
       │                                         │
       ▼                                         ▼
  ┌──────────┐                      ┌──────────────────────────┐
  │PageCache │                      │ CacheLongKeyLIRS.get(pos)│
  │  LIRS    │                      │  hot/cold 队列状态变更    │
  └────┬─────┘                      └────────────┬─────────────┘
       │ miss                                    │ hit
       ▼                                         ▼
  ┌──────────┐                      ┌──────────────────────────┐
  │FileStore │                      │ readFully(ByteBuffer)    │
  │          │                      │  Chunk 解压 → Page 反序列化│
  └──────────┘                      └──────────────────────────┘
```


该泳道图按"准备阶段"与"执行阶段"两段切分时间轴：准备阶段把 SQL 文本翻译
成可执行计划，执行阶段则驱动游标向 Store 层取行。Parser 与 Optimizer 是
纯准备阶段组件，FileStore 是纯执行阶段组件，其余四层跨阶段（详见 §7.5.1）。

下面 8 个步骤按时间顺序展开，每步附带一段动机说明、一段源码引用与一处
回指——读者可以直接以 §X.Y 跳转回原章节深入阅读。

### A.1.1 JDBC 入口与 SessionLocal 路由

应用线程调用 `Statement.executeQuery(String)` 后，控制权落入 H2 的
`org/h2/jdbc/JdbcStatement.java`。该方法不直接执行 SQL，而是先把当前
连接绑定的 `SessionLocal` 取出，再以 `session.prepareCommand(sql, fetch)`
进入引擎层。这条边界把"网络/JDBC 协议"与"SQL 引擎"切开：JDBC 层只关心
ResultSet 包装、超时取消与生成键回传；SQL 引擎层只关心解析、优化与执行。
等值点查 `WHERE id = 42` 在此处仍以原始字符串形式存在，没有任何编译动作。

```java
// org/h2/jdbc/JdbcStatement.java:executeQuery
synchronized (session) {
    setExecutingStatement(command);
    ResultInterface result = command.executeQuery(maxRows, scrollable);
    resultSet = new JdbcResultSet(conn, this, command, result, ...);
}
```

`SessionLocal` 是会话级的"上下文中枢"：它持有当前事务、锁集合、临时表、
查询缓存与自增主键计数器。准备阶段的所有路径都先穿过 `SessionLocal`，再
分发给 `Parser` 或 `Command` 子类（详见 §4.2.4）。会话锁通过
`synchronized(session)` 串行化同一连接的请求，避免 JDBC 用户在多线程下
并发使用同一连接造成内部状态错乱（详见 §7.1.1）。

### A.1.2 Parser 词法切分与递归下降

`SessionLocal.prepareLocal(sql)` 在缓存未命中时构造 `Parser` 实例，调用
`Parser.prepareCommand(sql)`。Parser 的工作分两步：先由内置 Tokenizer
按字符流扫出 token 序列；再由 `parseSelect()` 等手写递归下降函数把 token
组装成 AST。H2 的特别之处在于：解析器直接构造可执行的 `Expression` 树，
而非先构造抽象 AST 再翻译——这种"AST 即执行计划"的紧耦合简化了内存模型，
但要求重写阶段必须就地变换原树（详见 §7.2.3）。

```java
// org/h2/command/Parser.java:prepareCommand
read();
Prepared p = parsePrepared();   // → parseSelect() → Select
p.setSQL(sql);
p.setParameterList(parameters);
return p;
```

如图 A-2 所示，对 `SELECT * FROM users WHERE id = 42` 的 AST 由一个
`Select` 根节点、一个 `TableFilter` 引用和一棵 `Comparison` 子树组成。
`Comparison` 的左子树是 `ExpressionColumn(id)`，右子树是 `ValueInteger(42)`。
这棵树在后续阶段被反复访问：Optimizer 用它估算选择率，TableFilter 用它
抽取索引条件，最终在执行阶段由 `Comparison.evaluate()` 完成行级判定
（详见 §7.6.3）。

**图 A-2: 展示等值点查的表达式树骨架**

```text
                  Select(root)
                    │
        ┌───────────┼─────────────┐
        ▼           ▼             ▼
   visibleCols  filterList   condition
   ['*' 展开]  [TableFilter] Comparison(=)
                    │           │   │
                    ▼           ▼   ▼
                MVTable     ExpCol  ValInt
                 users      id      42
```


`*` 在 `Select.prepare()` 中被展开为表的全部列引用；`id = 42` 中的字面量
`42` 被装箱为 `ValueInteger` 并在类型推导阶段与 `id` 列的 INT 类型对齐
（详见 §7.2.7）。Parser 在此节点完成符号绑定但不做任何代价估算。

### A.1.3 Prepared 编译与查询缓存

回到 `SessionLocal.prepareLocal()`，编译完的 `Prepared` 被包装成
`CommandContainer` 并放入会话级 `Map<String, Command>` 缓存。下次同一
SQL 文本进入时，会话先以 `sql` 为 key 查询缓存命中，并通过 schema 版本号
比对决定是否需要重编译——DDL 修改了表结构后，旧 Prepared 必须作废
（详见 §7.3.1、§7.3.6）。等值点查在生产环境通常会反复出现，缓存命中率
直接决定 OLTP 短查询的延迟下界。

```java
// org/h2/engine/SessionLocal.java:prepareLocal
Command command = queryCache != null ? queryCache.get(sql) : null;
if (command == null || !command.canReuse()) {
    Parser parser = new Parser(this);
    command = parser.prepareCommand(sql);
    if (queryCache != null && command.isCacheable()) {
        queryCache.put(sql, command);
    }
}
```

`CommandContainer.canReuse()` 检查参数是否仍可绑定、Schema 是否未变更，
两者皆通过则跳过整个 Parser 与 Optimizer 阶段，直接进入执行（详见 §7.4.4）。
本案例首次执行走完整路径，第二次起直接在 `CommandContainer.query()` 处分叉。

### A.1.4 Optimizer 代价模型与计划选择

`Prepared.prepare()` 触发 `Optimizer.optimize()`。对单表查询，Optimizer
跳过连接顺序枚举，仅遍历 `users` 表的所有索引，为每个候选生成一个
`PlanItem`，调用 `index.getCost(...)` 估算代价。对 `WHERE id = 42`：

- 主键索引上，`id` 是首列，匹配等值条件，代价模型给出 `cost ≈ 3 + lookupCost`，等于一次 B-Tree 路径下降。
- 非主键的二级索引若不包含 `id`，则代价为全索引扫描的 `rowCount * STEP_COST`。
- 全表顺序扫描代价为 `rowCount * 10`。

```java
// org/h2/table/TableFilter.java:getBestPlanItem
for (int i = 0; i < indexes.size(); i++) {
    Index index = indexes.get(i);
    double cost = index.getCost(session, masks, filters, ...);
    if (cost < bestCost) { bestIndex = index; bestCost = cost; }
}
```

如图 A-3 所示，三种候选的代价矩阵呈数量级差距。代价模型是乘法复合：
`rowCount × selectivity × ioWeight + lookupCost`，其中 `selectivity` 由
`IndexCondition` 的掩码决定（详见 §8.3.2、§8.4.4）。等值条件在主键上
返回最小可能选择率 `1/rowCount`，因此主键索引必然胜出。

**图 A-3: 对比三种候选索引在等值点查下的代价矩阵**

```text
  候选计划             掩码      选择率    代价     被选中
  ────────────────────────────────────────────────────────
  PK_USERS (id) ─────  EQUALITY  1/N       3.0      ★
  IDX_USERS_NAME ────  无匹配    1.0       N×2.0
  全表扫描 ──────────   —         1.0       N×10.0
                        │          │         │
                        ▼          ▼         ▼
                    IndexCond  Statistics  PlanItem.cost
```


Optimizer 的早停机制在此场景几乎瞬间生效——首个候选即接近理论下界，
`canStop()` 直接返回 `true`，无需进入暴力枚举或遗传策略（详见 §8.1.3）。

### A.1.5 TableFilter 索引匹配与条件下推

Optimizer 选定 `PK_USERS` 后，把 `PlanItem` 安装到 `TableFilter` 上。
`TableFilter` 是 H2 执行引擎的迭代器抽象：它包装一张表、一条索引和一组
`IndexCondition`，对外提供 `next()` 方法逐行返回。

```java
// org/h2/table/TableFilter.java:prepare
this.index = item.getIndex();
this.indexConditions = filters; // 等值掩码 + 范围掩码
session.getDatabase().getCompareMode();
```

`WHERE id = 42` 在 `TableFilter.prepare()` 中被拆成两类：可下推到索引的
`IndexCondition.EQUALITY(id, 42)` 与剩余的 `filterCondition`。等值点查
全部条件都能下推，因此 `filterCondition == null`，每行都不必再做表达式
求值（详见 §8.4.2、§8.4.3）。索引下推把"过滤"从执行层迁移到存储层，
是 OLTP 微秒级延迟的关键来源之一。

`TableFilter` 在 `next()` 中先用 `IndexCondition` 构造 `SearchRow(id=42)`，
再调用 `index.find(session, first=42, last=42)` 返回 `Cursor`。Cursor
本身只持有 B-Tree 路径与位置游标，不立刻读取数据（详见 §8.5.1、§5.1.1）。

### A.1.6 B-Tree 路径下降与 Page Pointer 解码

`MVPrimaryIndex.find()` 委托给 `MVMap.get(42L)`，后者从 `RootReference`
拿到当前根 `Page`，再沿 B-Tree 自顶向下做二分查找。每一层都执行一次
`Page.binarySearch(key)`：在键数组上做经典二分，定位下一层子页指针，
直到落入叶节点（详见 §6.1.4）。

```java
// org/h2/mvstore/Page.java:binarySearch
int low = 0, high = entryCount - 1;
while (low <= high) {
    int x = (low + high) >>> 1;
    int cmp = compare(keys[x], key);
    if (cmp < 0) low = x + 1;
    else if (cmp > 0) high = x - 1;
    else return x;
}
return -(low + 1);
```

每一层的子指针不是简单的内存引用，而是一个 64 位的 `Page Pointer`，
编码了 `chunkId | offset | length | type`。如图 A-4 所示，路径下降在三层
B-Tree 上至多触发三次 Page 解码（详见 §6.1.2）。

以下三张图共同呈现等值点查的三个视角：图 A-4 刻画三层 B-Tree 的路径下降，图 A-5 拆解 Page Pointer 的 64 位字段布局，图 A-6 归纳 LIRS 缓存在等值点查下热/冷队列的状态转移。

**图 A-4: 刻画三层 B-Tree 在等值点查下的路径下降**

```text
       Root (NonLeaf, level 2)
       ┌─────────────────────────┐
       │ keys: [200, 400, 600]   │
       │ children:[P1,P2,P3,P4]  │
       └────────┬────────────────┘
       42 < 200 │ 取 P1
                ▼
       Inner (NonLeaf, level 1)
       ┌─────────────────────────┐
       │ keys: [50, 100, 150]    │
       │ children:[L1,L2,L3,L4]  │
       └────────┬────────────────┘
       42 < 50  │ 取 L1
                ▼
       Leaf (level 0)
       ┌─────────────────────────┐
       │ keys: [10,20,30,42,48]  │
       │ values: [r10,r20,...,r48]│
       └─────────────────────────┘
                ▲
                │ binarySearch → idx=3
                │ value = SearchRow(42, name='Bob', ...)
```


每条路径上的子指针均需先经 Page Pointer 解码才能加载下一层。如图 A-5
所示，64 位指针的字段排布把"哪个 Chunk、Chunk 内偏移、Page 长度、是否
叶节点"压缩进一个 `long`，使得任何节点的物理定位无需额外查表
（详见 §9.6.4）。

**图 A-5: 拆解 Page Pointer 64 位字段布局**

```text
  bit  63        32 31      8 7      1 0
       ┌───────────┬──────────┬───────┬─┐
       │ chunkId   │  offset  │length │T│
       │ 32 位     │   24 位   │  6 位 │1│
       └─────┬─────┴────┬─────┴───┬───┴─┘
             │          │         │   └── type: 0=Leaf 1=NonLeaf
             │          │         └────── length: 解压后块长度桶号
             │          └──────────────── offset: Chunk 内字节偏移
             └─────────────────────────── chunkId: 跨 Chunk 引用标识

  示例：0x0000_0007_0001_5C09
        chunkId=7, offset=22016, length 桶=12, type=Leaf
```


24 位偏移配合 6 位长度桶，保证 H2 的单 Chunk 上限为 16 MB；超过即触发
新 Chunk（详见 §9.3.2）。

### A.1.7 LIRS 缓存命中与 FileStore 物理 I/O

每次解码出 Page Pointer，`MVMap` 都先调用 `cache.get(pos)` 询问 LIRS
缓存。`CacheLongKeyLIRS` 维护两条链表：Stack 记录"近期被访问且预计仍
热"的页，Queue 记录"冷页候选"。命中分两类：在 Stack 上命中只把节点
提升到栈顶；在 Queue 上命中则进一步看节点是否曾在 Stack 上出现过——
若是，则提升为"重用热页"，挤出栈底冷页（详见 §6.5.3）。

```java
// org/h2/mvstore/cache/CacheLongKeyLIRS.java:get
Entry<V> e = find(key);
if (e == null) return null;             // miss
if (e.isHot()) { hit++; access(e); }    // 直接命中
else hitNonResident(e);                 // 历史栈命中 → 升级
return e.value;
```

如图 A-6 所示，等值点查只触碰三个 Page，对扫描型负载常见的"短期高频
访问无未来"模式天然抗污染——这正是 LIRS 相对 LRU 的核心优势
（详见 §6.5.5）。

**图 A-6: 归纳 LIRS 在等值点查下热/冷队列的状态转移**

```text
  访问序列：Root → Inner → Leaf （三次 get）
  ─────────────────────────────────────────────────────────
  初态       Stack: [P9, P8, P7]      Queue: [Q3, Q2, Q1]
  访问 Root  Stack: [Root, P9, P8]    Queue: [Q3, Q2, Q1]
             P7 退出栈（被 Root 顶出）
  访问 Inner Stack: [Inner, Root, P9] Queue: [P8, Q3, Q2]
             P8 从栈底降级到 Queue 头
  访问 Leaf  Stack: [Leaf, Inner,Root]Queue: [P9, P8, Q3]
             P9 降级；Q1, Q2 被驱逐写盘
  ─────────────────────────────────────────────────────────
  关键：等值点查只增三个 hot，不会冲掉更早的工作集 P*。
        相同访问换成 LRU 链表，则会把 P9/P8/P7 全部挤出。
```


若三次 `cache.get` 全部命中，整次查询不触发任何磁盘 I/O，延迟落在
百微秒量级。一旦未命中，`MVStore.readPage(pos)` 接管：从 Page Pointer
解出 `chunkId`，查 `Chunk` 元数据拿到文件偏移，调用
`FileStore.readFully(ByteBuffer, position)` 读入字节，再走 LZF 解压、
CRC 校验、Page 反序列化四道工序（详见 §9.2.6、§9.6.4）。读完的 Page
回填进 LIRS 缓存，下次同 key 即命中。

### A.1.8 Value 解码与 ResultSet 回包

叶节点中 `key=42` 对应的 `value` 是一个 `ValueRow`，内部按列序号存放
`Value[]`。`MVPrimaryIndex` 把 `ValueRow` 包装成 `Row` 后交还给
`TableFilter`。`Select.queryWithoutCache()` 把每个被选中的行追加进
`LocalResult`：等值点查最多得到一行，因此 `LocalResult` 立即闭合
（详见 §5.1.1）。

```java
// org/h2/command/query/Select.java:queryWithoutCache 关键片段
while (topTableFilter.next()) {
    if (condition == null || condition.getBooleanValue(session)) {
        Value[] row = expressions ... evaluate ...;
        result.addRow(row);
        if (limitRows != -1 && result.getRowCount() >= limitRows) break;
    }
}
```

`LocalResult` 经 `CommandContainer.executeQuery()` 上抛，被 `JdbcResultSet`
重新包装为 JDBC 协议层对象。应用线程在 `rs.next()` 返回 `true` 后调用
`rs.getInt("id")`，触发 `ValueInt.getInt()`——这是整个链路最后一次
类型转换。会话锁在结果集闭合时释放（详见 §7.4.2、§4.2.4）。至此，
"SELECT 42" 完成从 SQL 文本到磁盘字节再返回到 Java 整数的完整往返。

回顾全流程：JDBC 与 SessionLocal 提供边界与上下文，Parser 把字符串
变成 `Expression` 树，Optimizer 用代价模型把搜索空间剪到一条路径，
TableFilter 把过滤条件下推给索引，B-Tree 的 Page Pointer 把逻辑键映射
到物理偏移，LIRS 与 FileStore 决定这次访问到底打中内存还是磁盘，最后
`LocalResult` 与 `JdbcResultSet` 把结果折回 JDBC 协议——八个层次配合，
整体延迟可压到亚毫秒级。

### A.1.X 思考小结

下面三道自查题用来检验读者是否能把本案例的关键决策迁移到其他场景。

**1. 🟢★ 叙述等值点查下 Optimizer 为何能在第一次循环就调用 `canStop()` 提前终止？换成范围查询 `id BETWEEN 100 AND 200` 时这一终止条件是否仍然成立？**

> 提示：从代价矩阵的"理论下界"与索引选择率的关系入手，比较等值与范围两种 IndexCondition 的代价复合公式。
> 回顾：§8.1.3、§8.4.4

**2. 🔵★★ 若把 H2 的 LIRS 缓存替换为简单 LRU，本案例的三次 Page 访问延迟会如何变化？再设想一个并发的全表扫描线程同时运行，两种缓存策略在工作集保持上的差异会落在哪一步？**

> 提示：抓住 LIRS 的"Stack + Queue 双队列"如何区分一次性访问与重用访问，并结合扫描型负载的污染模式。
> 回顾：§6.5.3、§6.5.5

**3. 🟠★★★ 在 H2 测试目录下编写一段 JUnit 用例，对同一条 `SELECT * FROM users WHERE id = ?` 反复执行 1 万次并打印 `CommandContainer.canReuse()` 的命中次数；再在两次执行之间穿插一条 `ALTER TABLE users ADD COLUMN tag VARCHAR(8)`，观察缓存被作废的瞬间。**

> 提示：参考 `org/h2/test/db/TestPreparedStatement.java` 的现有测试骨架；DDL 触发的缓存失效路径见正文相应说明。
> 回顾：§7.3.6、§7.4.4

---

> **本案例的回指清单**：§4.2.4、§5.1.1、§6.1.2、§6.1.4、§6.5.3、§6.5.5、§7.1.1、
> §7.2.3、§7.2.7、§7.3.1、§7.3.6、§7.4.2、§7.4.4、§7.5.1、§7.6.3、§8.1.3、§8.3.2、
> §8.4.2、§8.4.3、§8.4.4、§8.5.1、§9.2.6、§9.3.2、§9.6.4。读者可按这条索引在原章节
> 中验证每一处源码引用。

---

## A.2 案例 B：一次 INSERT+UPDATE+COMMIT 事务的全链路

本案例承接案例 A 的"读路径"叙事，转入 H2 的"写—提交路径"。读路径关心的是
"在某一刻看到了什么"，写路径关心的则是"如何让一组修改原子地变成所有事务都
能看到的事实"。两者在 H2 内部由同一套 MVCC 机制串联——`VersionedValue`、
`TransactionStore`、`RootReference`——但在写入侧增加了 Undo Log、
`TxDecisionMaker`、`CommitDecisionMaker`、后台 Chunk 落盘与 Checkpoint
等关键环节。本案例选取一个被工程实践高频使用的最小完整场景：先 `INSERT` 一
条用户记录，再 `UPDATE` 同一行的某个字段，最后通过显式 `COMMIT` 让该事务对
其他会话可见。

为了让叙事可被源码逐行追溯，案例使用如下脚本作为运行实例。所有 §X.Y 反向
引用、`ClassName.java:行号`、字段名均以仓库当前主分支 (`org/h2/...`) 为
准；与案例 A 一致，文中不再重复打印每一行 SQL 的 AST/计划，而是聚焦在
TransactionStore 状态、`MVMap` 根引用、Undo Log、可见性翻转与 Chunk 持久
化这一条主线上。

```sql
-- 运行实例：账号表 users(id BIGINT PK, name VARCHAR, email VARCHAR)
-- 由会话 S1 执行；S2 是与 S1 并发的只读观察者。
BEGIN;                                              -- 步骤 ①
INSERT INTO users(id, name, email)
       VALUES (101, 'Alice', 'alice@example.com');  -- 步骤 ②
UPDATE users SET email = 'alice@h2.local'
       WHERE id = 101;                              -- 步骤 ③
COMMIT;                                             -- 步骤 ④
```

预期外部行为是：在步骤 ④ 之前，S2 看到的是"键 101 不存在"；步骤 ④ 完成后，
S2 看到的是 `(101, 'Alice', 'alice@h2.local')`。本案例要回答的问题是：
**"步骤 ④ 之中，到底哪一行 Java 代码使得 S2 的观感发生了瞬时翻转？"**
答案被分散在 `org/h2/engine/SessionLocal.java`、
`org/h2/mvstore/tx/TransactionStore.java`、
`org/h2/mvstore/RootReference.java` 与
`org/h2/mvstore/MVStore.java` 之中，下文按管线顺序逐段展开。

### A.2.1 beginTransaction：会话注册与 OPEN 状态登记

会话层入口为 `SessionLocal.getTransaction()`（`SessionLocal.java`
事务子句首次写入时延迟调用），它在内部调用
`TransactionStore.begin(...)`（`TransactionStore.java:455` 附近）。
`begin` 做三件事：在 `openTransactions`（`VersionedBitSet`，COW）
中通过 CAS 翻转一位、为该事务分配独立的 `undoLogs[txId]` 子映射、
把 `Transaction` 对象写入 `transactions[txId]` 槽位。事务 ID 随即被
固定为后续所有 `operationId` 的高 24 位（详见 §4.5 Undo Log 编码）。

如图 A-7 所示，注册流程对全局状态的影响是**纯增量的**：除了 BitSet 内部
通过 COW 创建新版本外，没有任何已存在的数据结构被写改。这与 §10.5
RootReference 的不可变性规约一致——任何"并发可见的状态"都通过整体替换
而非就地修改来表达。

```text
                        SessionLocal.beginTransaction()
                                 │
                                 ▼
                  TransactionStore.begin(isolationLevel)
                                 │
   ┌─────────────────────────────┼─────────────────────────────┐
   ▼                             ▼                             ▼
┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ openTransactions│   │ undoLogs[txId]      │   │ transactions[txId]  │
│ COW 翻转 bit[id]│   │ 新建 MVMap          │   │ new Transaction(    │
│ via CAS         │   │ name=".undoLog.id"  │   │   status=OPEN, …)   │
└────────┬────────┘   └──────────┬──────────┘   └──────────┬──────────┘
         │                       │                         │
         └───────────┬───────────┴───────────┬─────────────┘
                     ▼                       ▼
            VersionedBitSet 新版本     Transaction 对象就绪
                     ▼                       ▼
            其他事务可见到 "txId 已开启"，但不可见任何数据变更
```
**图 A-7: 描绘 begin 对全局事务表的三项写入**

注册完成后，会话拿到一个尚未关联任何变更的 `Transaction` 句柄。其
`status` 字段固定为 `OPEN`（详见 §4.5 状态机定义）。在第一次写操作触达
之前，`undoLogs[txId]` 是空的子映射，对其他事务而言这条事务"在场但无
影响"。这种"先注册后写入"的次序是 H2 在崩溃恢复中识别 in-flight 事务的
必要前提（详见 §9.7 TransactionStore 的恢复）。

### A.2.2 INSERT：TransactionMap.put 写入未提交 VersionedValue 与 Undo Log

`INSERT` 路径的入口是 `org/h2/command/dml/Insert.update()`，它穿过
`MVTable.addRow()`，最终调用到 `TransactionMap.putCommitted(...)` 或
`TransactionMap.put(key, value)`。后者把工作委托给
`MVMap.operate(key, value, txDecisionMaker)`（`MVMap.java`），并在
进入 B-Tree 改写之前先调用
`TxDecisionMaker.logAndDecideToPut()`（`TxDecisionMaker.java:162`），
后者**先把旧值写入 Undo Log，再返回 PUT 决策**。这里"旧值"对 INSERT
而言是 `null`，因此 `Record(mapId=usersDataMapId, key=101,
oldValue=null)` 被追加到 `undoLogs[txId]`，随后真正的
`VersionedValue` 写入数据 map。

如图 A-8 所示，单次 INSERT 在 H2 内部其实是"两次有序写"：先写 Undo
Log（保证回滚可逆），再写数据（保证读取可见性）。这与传统 WAL 数据库的
"先日志再页面"思想一致，但日志载体本身就是一棵 MVMap（详见 §9.4 为什么
不需要 WAL）。

```text
   Insert.update()
        │
        ▼
   MVTable.addRow(row)
        │
        ▼
   TransactionMap.put(101, Row{Alice,…})
        │
        ▼
   MVMap.operate(101, value, TxDecisionMaker)
        │
   ┌────┴──────────────────────────────────────┐
   ▼ 1. logAndDecideToPut                       │
 Undo Log 子映射 undoLogs[txId]:                │
   key   = (txId << 40) | logId=0               │
   value = Record(mapId, key=101, oldValue=null)│
   ▼ 2. Decision.PUT                            │
   ▼ 3. CAS 改写 RootReference                  │
 users 数据 map[101] =                           │
   VersionedValue{                              │
     operationId   = (txId << 40) | logId=0,    │
     committedValue= null,                      │
     currentValue  = Row{101,Alice,alice@…}     │
   }                                            │
   └────────────────────────────────────────────┘
```
**图 A-8: 拆解 INSERT 的"先日志后数据"两次写**

`VersionedValue` 的三个字段对应三种事务视角：`operationId` 标识"谁在
写"，`committedValue` 标识"全局已提交版本"（INSERT 阶段为 `null`，
因为之前不存在），`currentValue` 标识"当前事务可见的最新值"（详见 §10.2
VersionedValue 结构）。其他事务此刻读取 `key=101` 时，通过
`TransactionMap.get()` 内部分支会判断 `operationId` 不属于自己且事务未
提交，于是返回 `committedValue=null`，即"看不到这行"。

> **源码路径**：`org/h2/mvstore/tx/TransactionMap.java`、
> `org/h2/mvstore/tx/TxDecisionMaker.java:73-166`、
> `org/h2/mvstore/MVMap.java:operate(...)`。

### A.2.3 UPDATE：第二个未提交版本与 TxDecisionMaker 的冲突分支

紧随 INSERT 的 `UPDATE users SET email='alice@h2.local' WHERE
id=101` 同样路由到 `TransactionMap.put(101, newRow)`。但这一次
`existingValue` 已经是上一步留下的 `VersionedValue`，其 `operationId`
属于**当前事务自身**。`TxDecisionMaker.decide()`（`TxDecisionMaker.java:73-116`）
会进入"情况 2：同一事务的修改"分支，再次调用
`logAndDecideToPut(currentValue=oldRow, committedValue=null)`，
追加第二条 Undo Log 记录 `Record(mapId, key=101, oldValue=oldRow)`，
随后用新 `VersionedValue` 覆盖数据 map 中 `key=101` 的槽位。

这里的关键工程细节是：**Undo Log 的旧值是"步骤前的可见值"，而不是"原始
未修改值"。** 因此回滚时，逆序回放两条 Undo Log 即可一步步退回到 INSERT
之前的状态——先把 `key=101` 还原为 `oldRow`，再把它移除，回到 `null`
（详见 §5.6 ROLLBACK 与 §4.5 rollbackTo 流程）。

```text
   UPDATE 触发后 TxDecisionMaker.decide(existing) 决策树:

   existing == null ? ───── YES ──▶ 情况 1: 直接 PUT (不应出现)
            │
            NO
            ▼
   getOperationId(existing) == NO_OPERATION_ID ? ─ YES ─▶ 情况 1: PUT
            │
            NO
            ▼
   blockingId == thisTxId ? ─── YES ──▶ 情况 2: 自写覆盖
            │                                │
            NO                               ▼ logAndDecideToPut
            ▼                          追加 Undo Log entry #2
   isCommitted(blockingId) ? ── YES ─▶ 情况 3: 已提交,可写
            │
            NO
            ▼
   existsBlockingTx ? ───── YES ──▶ 情况 4: ABORT,等待
            │
            NO
            ▼
   isRepeatedOperation ? ── YES ──▶ 情况 5: 残留覆盖
            │
            NO
            ▼
   情况 6: REPEAT 重试
```
**图 A-9: 展示 TxDecisionMaker 六分支决策的命中路径**

如图 A-9 所示，本案例命中的是"情况 2"。值得强调的是：**情况 2 仍然写
Undo Log**——并不是"自己写自己"就可以省略日志。这是 H2 在源码层面对回
滚正确性的硬约束，否则同一事务内的多步修改将无法逐步退回。`undoLogs`
子映射在事务结束前都是仅追加的，`logId` 单调递增，对应 `opId` 的低 40
位（详见 §4.5 Undo Log 编码格式）。

第二次 PUT 完成后，`users` 数据 map 中 `key=101` 的 `VersionedValue`
变成：`operationId=(txId<<40)|1`、`committedValue=null`、
`currentValue=Row{101, Alice, alice@h2.local}`。`undoLogs[txId]` 长
度为 2。两次写都已经体现在 `MVMap` 的内存版本链中，但**对其他事务仍然
不可见**——可见性最终由后续 `commit()` 触发的"批量翻转"决定。

### A.2.4 COMMIT 触发：SessionLocal.commit 到 TransactionStore.commit

会话端 `COMMIT` 由 `TransactionCommand.update()` 调用
`SessionLocal.commit(false)`（`SessionLocal.java:686` 附近）。该方法
执行三步：`beforeCommitOrRollback()` 做 LOB 与触发器准备；
`transaction.commit()` 委派给 `TransactionStore.commit()`；
`endTransaction()` 释放表锁与会话级状态。COMMIT 是**纯内存操作**，
不调用 `FileChannel.force()`，磁盘可见性由独立的 Checkpoint 负责
（详见 §5.5 COMMIT 流程总览与 §9.5 Checkpoint 触发条件）。

`TransactionStore.commit(Transaction t, boolean recovery)`
（`TransactionStore.java:579`）是真正的提交核心，按时序它做五件事：
①`flipCommittingTransactionsBit(txId, true)` 把"正在提交"位设上；
②`notifyAllWaitingTransactions()` 唤醒被本事务阻塞的写者；
③`markUndoLogAsCommitted(txId, version)` 把 Undo Log 子映射重命名为
`.undoLog-<id>`（点改横，作为崩溃恢复时"已成功 mark commit"的语义信号，
详见 §9.7 TransactionStore 的恢复）；④遍历 `undoLogs[txId]`，对每条
`Record(mapId, key, oldValue)` 调用对应数据 map 的
`map.operate(key, null, commitDecisionMaker)`；⑤
`flipCommittingTransactionsBit(txId, false)` 清除提交位。

```text
   SessionLocal.commit(false)
        │
        ▼
   transaction.commit()  ──▶  TransactionStore.commit(t, recovery=false)
                                       │
                                       ▼
   ① flip bit committingTransactions[txId]=1 (CAS over VersionedBitSet)
                                       │
                                       ▼
   ② notifyAllWaitingTransactions()  → 唤醒 §10.2.4 中 ABORT 的写者
                                       │
                                       ▼
   ③ markUndoLogAsCommitted(txId, version)  // ".undoLog.7" → ".undoLog-7"
                                       │
                                       ▼
   ④ for each Record in undoLogs[txId]:
        map = openMap(mapId)
        map.operate(key, null, CommitDecisionMaker)   ◀── §A.2.5
                                       │
                                       ▼
   ⑤ undoLogs[txId].clear() + flip committingTransactions[txId]=0
                                       │
                                       ▼
   返回 SessionLocal → endTransaction() 释放表锁与 LOB
```
**图 A-10: 列出 COMMIT 五步内部时序**

如图 A-10 所示，第一步与第五步形成一个"夹住"的临界区：在两次 flip 之间，其他事务通过
`isCommitted(txId)` 看到的是"提交中"，进而触发 §10.2.4 情况 3 的
"视为已提交"分支。这是 MVCC 模式下"长链路提交期间不阻塞读"的关键——其
他事务读取 `committedValue` 还是 `currentValue` 完全由 BitSet 当前
状态决定，**不需要等待 commit 完成**（详见 §10.4 隔离级别与 §10.5
RootReference 快照一致性）。

### A.2.5 CommitDecisionMaker：Undo Log 扫描与 VersionedValue 翻转

`CommitDecisionMaker.decide()`（`CommitDecisionMaker.java:25`）的工
作是逐条把"未提交版本"翻转为"已提交版本"。对每个 `key`：若
`existingValue.operationId` 属于本事务，构造一个新的 `VersionedValue`
其中 `operationId=NO_OPERATION_ID`、`committedValue=currentValue`、
`currentValue=currentValue`，然后返回 `Decision.PUT`，由 `MVMap` 在
B-Tree 上 CAS 写入；否则返回 `ABORT`，跳过该键。

回到运行实例：UPDATE 后 `key=101` 的 `VersionedValue` 是
`{op=(txId<<40)|1, committed=null, current=Row{Alice,alice@h2.local}}`。
扫描第一条 Undo Log（INSERT 那条）时，CommitDecisionMaker 会构造
`{op=NO_OP, committed=current, current=current}` 并 PUT；扫描第二条
（UPDATE 那条）时，由于此时 `operationId` 已经是 `NO_OP`，
`decide()` 进入 `existingValue==null || op==NO_OP_ID` 的快路径，依然
返回 PUT 但本质上是幂等覆盖——这正是为什么遍历顺序无关、且重复扫描安全
的原因（详见 §10.2 VersionedValue 与 §5.5.3.1 CommitDecisionMaker
关键代码）。

```text
   CommitDecisionMaker.decide(existing):

       existing == null ?
           │
           ├─ YES → ABORT  (该键早已被同事务的另一条记录处理过)
           │
           └─ NO
                │
                ▼
       getTransactionId(existing.operationId) == thisTxId ?
                │
                ├─ NO → ABORT  (其他事务的修改, 不能覆盖)
                │
                └─ YES
                     │
                     ▼
       构造 cleared = VersionedValue(
                         operationId   = NO_OPERATION_ID,
                         committedValue= existing.currentValue,
                         currentValue  = existing.currentValue)
                     │
                     ▼
       return MVMap.Decision.PUT  →  MVMap CAS 替换 B-Tree 节点
```

注意：`CommitDecisionMaker` 不会清除 `currentValue`，它只是把
`committedValue` 提升为与 `currentValue` 一致，并把 `operationId`
归零。因此从其他事务的视角，**"翻转"是一次原子的语义抬升**：原本它
们看到的是 `committedValue=null`（看不到行），翻转之后立即看到的是
`committedValue=Row{...}`（行可见），中间没有可观测的中间态。

### A.2.6 RootReference CAS：原子可见性翻转的最小不可分原语

虽然 §A.2.5 的 `CommitDecisionMaker` 是逐键 PUT，但**真正让"看不见
→看见"瞬间发生**的硬件级原子操作，是 `MVMap.operate` 内部对
`AtomicReference<RootReference>` 的 `compareAndSet` 调用
（`MVMap.java:45`、详见 §10.5 CAS 更新机制）。每一次 PUT 都会创建一
条新版本链 `v_new → v_old → ...`，并通过 CAS 把 `root` 指向
`v_new`；CAS 失败时进入 §10.5.3 的三级退避（spin-wait → yield →
synchronized wait）。

如图 A-11 所示，写者线程 W、读者线程 R 与 BackgroundWriter 线程 B
在同一时间轴上的动作可以被精确刻画：R 在 W 完成 CAS 之前读取看到旧根，
之后立刻看到新根；B 在 R/W 之间的任意时刻被唤醒，但它读取的是
"某个时刻的根快照"，并把对应的页落到 Chunk 中（详见 §A.2.7 与 §9.5
后台写入线程）。

```text
   时间轴 ────────────────────────────────────────────────────────────────────────────▶
   ─────────────────────────────────────────────────────────────────────────────────
   W (writer S1) │
                 │ t0 ─▶ Insert.put(101)         (TransactionMap.put → MVMap.operate)
                 │ t1 ─▶ Update.put(101)         (第二次 PUT, 写第二条 Undo Log)
                 │ t2 ─▶ flipCommittingBit(true) (committingTransactions[txId]=1)
                 │ t3 ─▶ CommitDecisionMaker 扫描 undoLog 两条记录
                 │ t4 ─▶ root.compareAndSet(v_old, v_new)   ◀══════ 原子可见性翻转
                 │ t5 ─▶ flipCommittingBit(false) + undoLog.clear()
   ─────────────────────────────────────────────────────────────────────────────────
   R (reader S2) │
                 │ t0─t1 ─▶ get(101)→null              (读 root v0, op=txS1, 未提交)
                 │ t2    ─▶ get(101)→null              (读 root v0, committingBit=1
                 │                                     仍判 committedValue=null,见§10.2.4)
                 │ t3    ─▶ get(101)→null              (CDM 扫描进行中, 根尚未替换)
                 │ t4    ─▶ get(101)→Row{Alice,alice@h2.local}   ◀═ 第一次看见行
                 │ t5    ─▶ get(101)→Row{Alice,alice@h2.local}   (committingBit=0)
   ─────────────────────────────────────────────────────────────────────────────────
   B (BgWriter)  │
                 │ t0─t1 ─▶ sleep(autoCommitDelay = 1s)
                 │ t2    ─▶ tick: hasUnsavedChanges()? → no  (CAS 尚未发生)
                 │ t3    ─▶ sleep(...)
                 │ t4─t5 ─▶ tick: hasUnsavedChanges()? → yes  (新 root 可见)
                 │ t6    ─▶ storeLock.tryLock() OK → store(syncWrite=false)
                 │ t6    ─▶ collectDirtyPages → buildChunk(k) → FileChannel.write
                 │ t6    ─▶ updateChunkRegistry → updateStoreHeader(currentVersion++)
                 │ t6    ─▶ storeLock.unlock()                   (持久性边界完成)
   ─────────────────────────────────────────────────────────────────────────────────
                                                  ▲
                                                  │
                                            t4 = 可见性翻转 (CAS 成功)
                                            t6 = 持久性边界 (Chunk + Header)
```
**图 A-11: 对比 CAS 提交前后的可见性翻转时刻**

图中 `t4` 是本案例最重要的"时间锚点"：在 `t4` 之前的任意纳秒，R 读到
的都是 `null`；在 `t4` 之后的任意纳秒，R 读到的都是新行。Java 内存模
型对 `AtomicReference.compareAndSet` 的 happens-before 规约保证了
这一点（详见 §10.5.6 CAS 重试循环与退避策略）。值得注意的是：
BackgroundWriter 在 `t6` 才把新页写入磁盘，但**这与 R 的可见性翻转无
关**——可见性是内存级的，持久性是磁盘级的，两者解耦。

### A.2.7 BackgroundWriter：脏页收集与新 Chunk 写入

`MVStore` 在构造时通过 `setAutoCommitDelay()`（`MVStore.java:310`
附近）启动后台写入线程，默认周期 1 秒。每个 tick 它执行
`writeOrClose()`：检查 `hasUnsavedChanges()`，若 true 则尝试取得
非阻塞 `storeLock`，调用 `store(false)`，进入 §9.5.6 的脏页收集与
§9.5.2 的 `store()` 完整流程。脏页来自 §A.2.5 中 CommitDecisionMaker
留下的所有"新 RootReference 链"。

`store()` 的输出是一段连续的字节，写入到下一个空闲块，对应一个新的
`Chunk` 对象（详见 §6.4 Chunk 压缩整理与 §9.3.4 Chunk 生命周期）。
该 Chunk 中包含本事务两次 PUT 产生的全部新页，以及由其它并发事务在该
间隔内产生的页。一个 Chunk 不专属于一个事务——这与传统 WAL "事务一
段日志"的强耦合不同，这是 MVStore "页中心、版本链、批量落盘"设计的体
现（详见 §9.4.3 传统 WAL 与 MVStore 隐式日志对比）。

```text
   BackgroundWriter tick:
   ┌──────────────────────────────────────────────────────┐
   │  hasUnsavedChanges()?                                │
   │     │                                                │
   │     ├─ NO  → continue sleep (autoCommitDelay)        │
   │     │                                                │
   │     └─ YES                                           │
   │         │                                            │
   │         ▼                                            │
   │  storeLock.tryLock()  (非阻塞)                       │
   │         │                                            │
   │         ├─ FAIL → 留给下一个 tick                     │
   │         │                                            │
   │         └─ OK                                        │
   │             │                                        │
   │             ▼                                        │
   │  store(syncWrite=false)                              │
   │     ├─ collectDirtyPages()       ── §9.5.6           │
   │     ├─ buildChunk(pages, version)                    │
   │     ├─ allocateBlocks(FreeSpaceBitSet)  ── §6.6      │
   │     ├─ FileChannel.write(chunkBytes)                 │
   │     └─ updateChunkRegistry()                         │
   │             │                                        │
   │             ▼                                        │
   │  storeLock.unlock()                                  │
   └──────────────────────────────────────────────────────┘
```

在 `syncWrite=false` 路径下，后台 tick **不调用** `force()`，因此
即使 Chunk 字节已落盘，OS 的 page cache 可能仍未刷到块设备；只有
`sync()`、显式 `commit + autoCommit + sync` 或关闭路径才会触发
`force()`（详见 §9.5.3 后台写入线程对 `syncWrite` 标志的处理）。
这是 H2 默认配置下"COMMIT 的可见性"与"COMMIT 的持久性"之间的核心
权衡——案例 C 将专门讨论这一权衡在崩溃场景下的恢复路径。

### A.2.8 Checkpoint：File Header 同步与版本提升

`store()` 的尾部会更新 `Store Header`：把"最新有效版本"指向刚写入的
Chunk 起始块，同时把 `currentVersion` 提升到该 Chunk 对应的全局版本
号（详见 §9.3.3 Store Header 详细格式与 §9.6.2 File Header 格式）。
H2 在文件起始与中段保留**两份** Store Header，按版本号选取较新者，
保证即使一份 header 写入过程中崩溃，另一份依然指向上一个完整版本——
这是 H2 在 §9.4.4 中描述的"原子提交边界"的物理实现。

如图 A-12 所示（本案例第六张图），TransactionStore 的状态机视角把
A.2.1 至 A.2.8 八个步骤压缩为四个宏观阶段：OPEN、PREPARED（仅
两阶段提交场景）、COMMITTED、ROLLED\_BACK。本案例没有进入 PREPARED
分支（详见 §4.5 二阶段提交支持），但状态机把它列出便于读者把握全貌。

```text
   ┌─────────────────────────────────────────────────────────────────┐
   │            TransactionStore Transaction 状态机                    │
   │  (注: 图中箭头标签标注触发动作 / 关键 BitSet 翻转)                  │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                 │
   │     ┌─────────┐                                                 │
   │     │ NOT_INIT│                                                 │
   │     └────┬────┘                                                 │
   │          │ TransactionStore.begin()                             │
   │          │ openTx[id] := 1                                      │
   │          ▼                                                      │
   │     ┌─────────┐  prepare(commitName)   ┌──────────┐             │
   │     │  OPEN   │ ─────────────────────▶ │ PREPARED │             │
   │     │         │                        │          │             │
   │     └──┬──┬───┘                        └────┬─────┘             │
   │        │  │                                 │                   │
   │        │  │ rollback / rollbackTo          │ commit (XA)        │
   │        │  ▼                                ▼                    │
   │        │  ┌───────────────┐         ┌──────────────┐            │
   │        │  │ ROLLED_BACK   │         │ COMMITTED    │            │
   │        │  │ openTx[id]:=0 │         │ openTx[id]:=0│            │
   │        │  │ undoLog 逆序  │         │ undoLog 顺序 │            │
   │        │  │ 恢复 oldValue │         │ 翻转 op=NO_OP│            │
   │        │  └───────┬───────┘         └──────┬───────┘            │
   │        │          │                        │                    │
   │        │          ▼                        ▼                    │
   │        │   transactions[id]=null    transactions[id]=null       │
   │        │   undoLogs[id].clear()     undoLogs[id].clear()        │
   │        │                                                        │
   │        │ commit (一阶段, 本案例路径)                              │
   │        ▼                                                        │
   │   ┌─────────────────┐                                           │
   │   │ committingTx=1  │  ← flipCommittingTransactionsBit(true)    │
   │   │ (临时子状态)    │                                            │
   │   └────────┬────────┘                                           │
   │            │ CommitDecisionMaker 扫完 + RootReference CAS       │
   │            ▼                                                    │
   │   ┌─────────────────┐                                           │
   │   │ committingTx=0  │  ← flipCommittingTransactionsBit(false)   │
   │   │ + COMMITTED     │                                           │
   │   └─────────────────┘                                           │
   │                                                                 │
   │  备注: PREPARED → ROLLED_BACK 在 XA recover 时也成立              │
   │        (详见 §9.7 TransactionStore 的恢复)                       │
   └─────────────────────────────────────────────────────────────────┘
```
**图 A-12: 展示 TransactionStore 状态迁移与回滚分支**

`COMMITTED` 不是终态：当 `transactions[id]` 槽被 `null` 化、
`undoLogs[id]` 子映射被 `clear()` 后，事务对象就被回收，`txId` 可能
被未来的新事务重用（详见 §4.5 数组索引映射关系）。这是 H2 把
`MAX_OPEN_TRANSACTIONS=255` 这一硬上限做得可接受的关键——只要事务流
转足够快，槽位池就不会耗尽。

### A.2.9 端到端复盘：从 SQL 到磁盘的责任划分

回到运行实例：会话 S1 提交 `(101, 'Alice', 'alice@h2.local')` 后，S2
立刻可读到这一行；但磁盘上对应的 Chunk 可能要到 1 秒后才被
BackgroundWriter 写入，再到下一次显式 `sync()` 或关闭才进入持久化语义。
这条链路的责任划分与典型缩写如下：

| 阶段 | 责任组件 | 关键产出 | 反向引用 |
| --- | --- | --- | --- |
| ① begin | SessionLocal / TransactionStore | openTx 位、undo 子映射、Tx 对象 | 详见 §4.5 |
| ② INSERT | TransactionMap / TxDecisionMaker | Undo Log #0、未提交 VersionedValue | 详见 §10.2 |
| ③ UPDATE | TransactionMap / TxDecisionMaker | Undo Log #1、新未提交 VersionedValue | 详见 §10.4 |
| ④ commit 触发 | SessionLocal.commit | 委派至 TransactionStore.commit | 详见 §5.5 |
| ⑤ CDM 扫描 | CommitDecisionMaker / MVMap.operate | committedValue 抬升 | 详见 §5.5.3.1 |
| ⑥ root CAS | RootReference (AtomicReference) | 原子可见性翻转 | 详见 §10.5 |
| ⑦ Chunk 落盘 | BackgroundWriter / store() | 新 Chunk + page 字节 | 详见 §9.5 与 §6.4 |
| ⑧ Header 同步 | Store Header 双写 | currentVersion 提升 | 详见 §9.6 |

⑥ 是"逻辑可见性"边界，⑧ 是"物理持久性"边界。两者在源码中由不同子系
统拥有，由 BackgroundWriter 这条无锁后台线程把它们桥接为最终一致的
状态。这种**"内存提交—后台落盘"**的两段式设计，是 MVStore 与 H2
SQL 引擎组合时性能特征的根本来源（详见 §9.4 Crash Safety 与 §9.5.4
检查点触发条件详解）。

值得指出的是，本案例没有讨论 `SET LOCK_MODE`、`SET WRITE_DELAY` 等
影响默认行为的会话级开关——它们会改变 ⑥ 与 ⑧ 之间的"窗口宽度"，但不
改变责任划分。在工程部署中，关键决策是：是否允许出现"已 commit 但
未持久化"的窗口；H2 的默认答案是"是"，为此提供了 `SET WRITE_DELAY 0`
等显式收紧选项。

### A.2.10 思考小结

读者可以用以下三个问题自检对本案例的掌握程度：

1. **对一行被同一事务修改两次的键，为什么 `CommitDecisionMaker` 扫
   到第二条 Undo Log 时仍然返回 PUT 而不是 ABORT？这与 `existingValue
   .operationId == NO_OP_ID` 的快路径有什么关系？**（提示：详见 §10.2
   VersionedValue 结构与 §5.5.3.1 CommitDecisionMaker 关键代码。）

2. **若 BackgroundWriter 在 §A.2.5 完成后、§A.2.8 完成前进程崩溃，
   下次启动时 H2 如何判断本事务"已经成功 commit"？为什么 Undo Log 子
   映射的命名从 `.undoLog.<id>` 变成 `.undoLog-<id>` 起到了关键作用？**
   （提示：详见 §9.7 TransactionStore 的恢复与 §4.5 markUndoLogAsCommitted。）

3. **为什么 §A.2.6 中 RootReference CAS 是"可见性翻转"的最小不可分
   原语，而不是 §A.2.4 中 `flipCommittingTransactionsBit(true)`？
   把两者交换次序会导致什么读异常？**（提示：详见 §10.5 RootReference
   CAS 与 §10.4 隔离级别实现。）

完成本案例后，建议沿着以下顺序进入案例 C：把"crash 发生在 §A.2.5 与
§A.2.8 之间"作为思想实验起点，复用本案例建立的状态时间轴，观察
TransactionStore.recovery 路径如何重建 OPEN/COMMITTED 集合，从而把
A.2 的"提交全链路"推广为"crash + recovery 全链路"。

---

---

## A.3 案例 C：一次崩溃后的恢复启动

本案例展示 H2 在进程被强制终止之后再次打开数据库时，MVStore 如何利用双副本 File Header、Chunk Footer 中的 Fletcher-32 校验和以及 Undo Log 的命名约定，把磁盘上的字节流恢复到一个一致的运行时状态。与案例 A 的"读路径"和案例 B 的"写路径"不同，本案例关注的是"启动路径"：从 `MVStore.openInternal()` 到对外开放写入之间，恢复子系统经过的 8 个流水线步骤。每一步都需要在"前向推进"与"回退到上一已知良好状态"之间做出明确决策，而决策依据则来自磁盘上的校验信息以及 Undo Log map 名后缀（详见 §9.7.1）。

为了让讨论具体化，本案例使用如下运行示例：一个 H2 数据库在崩溃前已经成功提交了 3 个事务（生成 Chunk 1、Chunk 2、Chunk 3），最新的 File Header 双副本指向 Chunk 3。第 4 个事务正在写入：Chunk 4 的 Header 与若干 Page 已经落盘，但写到 Chunk 4 Footer 的最后 64 字节时操作系统断电，Footer 中的 Fletcher-32 字段尚未更新；同时 File Header 副本仍然停留在指向 Chunk 3 的旧版本上。我们将以这一实例贯穿全篇，明确每个分支的决策点。

### A.3.1 崩溃发生场景：第 4 个事务写到一半

在崩溃发生时，进程内存中存在 4 个 Transaction 对象：T1、T2、T3 已经依次调用 `TransactionStore.commit()` 完成提交（详见 §4.5），它们的 undo log map 后缀已从 `.undoLog.<id>` 重命名为 `.undoLog-<id>` 或被 `clear()`；T4 调用了 `MVMap.put()` 写入了若干 VersionedValueUncommitted 节点，并通过 `MVStore.commit()` 触发了一次检查点（详见 §9.5）。检查点逻辑把 T4 的事务变更打包成 Chunk 4，连同最新的 layoutMap、metaMap root 一起 append 到文件末尾。崩溃恰好发生在 `serializeToBuffer()` 执行到末尾 Footer 写入阶段，但磁盘扇区原子写入边界尚未跨越。

```text
┌──────────────────────────────────────────────────────────────────┐
│  崩溃前后进程内存与磁盘状态                                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   崩溃前 (in-flight)            │   崩溃后 (on-disk reality)       │
│   ─────────────────────────     │   ─────────────────────────       │
│   内存:                          │   磁盘:                          │
│     T1, T2, T3 = COMMITTED       │     File Header 0 → Chunk 3      │
│     T4 = OPEN, 已写 4 条 undo    │     File Header 1 → Chunk 3      │
│     committingTransactions       │     Chunk 1 (good footer)        │
│       BitSet = {4}               │     Chunk 2 (good footer)        │
│     dirty meta map root          │     Chunk 3 (good footer)        │
│                                  │     Chunk 4 (header+pages,       │
│   FileChannel 写指针位于         │             FOOTER 字节缺失)     │
│     Chunk 4 footer 起始处        │                                  │
│                                  │   操作系统的 page cache 被丢弃     │
│  ─────────  电源切断 / kill -9   │   只有 fsync 之前的字节才在盘上   │
│                                  │                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 A-13: 对比崩溃前后内存与磁盘状态**

如图 A-13 所示，进程内存中的 `committingTransactions` BitSet、`undoLogs[]` 数组、所有 RootReference 链以及 dirty page 表都被无差别清除；恢复子系统能够利用的输入只有磁盘上残留的字节流（详见 §9.7.6）。Chunk 4 的"半成品"特征是本案例两个分支的分水岭：File Header 仍然指向 Chunk 3，因此正常路径会先把 Chunk 3 当作起点；而 Chunk 4 的 Header 已经落盘，但 Footer 校验失败，因此异常路径会被触发——后续步骤将在同一棵决策树上把这两条分支收敛回一致状态。

需要强调的一点是：H2 不依赖传统 WAL 进行重做，而是依赖"最新一个完整 Chunk"的快照语义（详见 §9.4.2）。这意味着崩溃后丢失的最大粒度是"一个 Chunk 中所有 commit 的变更"。本案例中第 4 个事务的所有效果都将被丢弃，但这并不违反 ACID——T4 在 SQL 客户端那一侧从未收到 `COMMIT OK` 响应。

为了让恢复决策更清晰，下面把崩溃发生前后磁盘上的"承诺位"摘录如下。承诺位即决定一段字节是否被恢复流程视为"已存在"的关键校验字段：

- File Header 的 `fletcher` 字段：决定 Block 0 / Block 1 是否参与版本仲裁；
- Chunk Footer 的 `fletcher` 字段：决定整个 chunk 的所有 page 是否被采纳；
- metaMap 中的 `chunk.<id>` 条目：决定 chunk 是否被纳入 FreeSpaceBitSet 的 used 区间；
- undo log map 名后缀（`.` 或 `-`）：决定事务在恢复期是 rollback 还是 commit-redo。

这些承诺位之间的语义优先级是从外向内的：File Header → Chunk Footer → metaMap chunk 条目 → undo log 名后缀。前一级失败会让后一级的所有信息被丢弃，这是 ACID 原子性"全有或全无"的物理体现（详见 §9.4.4）。

### A.3.2 进程重启与 FileStore 重新打开

操作员重新启动 JVM，应用层调用 `DriverManager.getConnection()`，最终进入 `MVStore.openInternal()`（`org/h2/mvstore/MVStore.java`）。该方法首先构造 `SingleFileStore`，调用 `FileStore.open(fileName, readOnly)` 打开底层 `FileChannel`，并尝试获取文件锁（默认 `FileLockMethod.FS`）。文件锁的目的是防止两个 JVM 同时执行恢复流程造成状态分裂。

```text
┌────────────────────────────────────────────────────────┐
│  阶段 1: FileStore 重新打开                              │
├────────────────────────────────────────────────────────┤
│                                                        │
│   MVStore.openInternal()                               │
│       │                                                │
│       ├─ new SingleFileStore(this, config)             │
│       │   └─ FileChannel.open(path, READ, WRITE)       │
│       │                                                │
│       ├─ acquireFileLock()                             │
│       │   ├─ 成功 → 进入恢复流程                          │
│       │   └─ 失败 → 抛 DbException(FILE_LOCKED_1)       │
│       │                                                │
│       ├─ readStoreHeader()                             │
│       │   └─ 见 A.3.3                                   │
│       │                                                │
│       └─ setLastChunk(...)                             │
│           └─ 见 A.3.4 / A.3.5                           │
│                                                        │
└────────────────────────────────────────────────────────┘
```
**图 A-14: 追踪 FileStore 重启与锁获取顺序**

如图 A-14 所示，恢复流程必须先确认排他持有文件锁，否则后续任何字节读取都可能与另一个写入者竞争。`SingleFileStore.start()` 在 `org/h2/mvstore/SingleFileStore.java` 中实现：它把 `FileChannel.position(0)` 复位到文件开头，然后申请一段 8 KB 缓冲区，准备一次性读入两份 File Header。决策点在于：如果 `tryLock()` 返回 null，说明已有进程持有锁，恢复流程必须中止并向上层抛出异常——H2 不会"乐观恢复"。

文件本身长度可由 `FileChannel.size()` 直接获得，记为 `fileLen`。本例中假定 `fileLen = 4096 × (2 + nBlocks(Chunk1..Chunk4))`，注意 Chunk 4 的 Footer 字节虽然短缺，但操作系统已把 Chunk 4 的 Header + Page 区块对齐到 4 KB 边界，所以 `fileLen` 仍然是一个块对齐值。这一观察是 A.3.4 中"沿 next 链遍历"能够正确停止的前提（详见 §9.6.1）。

### A.3.3 双副本 File Header 读取与版本仲裁

`readStoreHeader()` 是恢复流程的第一个关键决策点。它读取文件的前两个 4 KB 块（Block 0、Block 1），分别解析为 key-value 文本格式的 File Header，再分别校验 Fletcher-32（详见 §9.6.2）。两份 header 的存在不是为了多版本，而是为了防止"写 Header 过程中崩溃"导致两份都损坏的概率被压缩到可忽略。

```text
┌─────────────────────────────────────────────────────────────────────────┐
│        磁盘文件字节布局（运行示例：3 个完整 Chunk + 1 个半 Chunk）         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  offset 0x00000000 ┌───────────────────────────────────────┐            │
│                    │ File Header 0  (block 0, 4 KB)        │            │
│                    │   H:2,block:N3,blockSize:1000,        │            │
│                    │   chunk:3,version:3,fletcher:0x91A2..│            │
│  offset 0x00001000 ├───────────────────────────────────────┤  ← 4096    │
│                    │ File Header 1  (block 1, 4 KB)        │            │
│                    │   H:2,block:N3,...,version:3,         │            │
│                    │   fletcher:0x91A2.. (与 header 0 一致)│            │
│  offset 0x00002000 ├───────────────────────────────────────┤  ← 8192    │
│                    │ Chunk 1   header | pages | footer ✓   │            │
│                    │   chunk:1,block:2,version:1,...       │            │
│                    │   footer fletcher = 0xAED9A4F6 (good) │            │
│  offset 0x00006000 ├───────────────────────────────────────┤  ← 24576   │
│                    │ Chunk 2   header | pages | footer ✓   │            │
│                    │   chunk:2,version:2,fletcher=0x5C... │            │
│  offset 0x0000A000 ├───────────────────────────────────────┤  ← 40960   │
│                    │ Chunk 3   header | pages | footer ✓   │            │
│                    │   chunk:3,version:3,fletcher=0x91A2.. │            │
│                    │   next = block N4 (= Chunk 4 起点)    │            │
│  offset 0x0000F000 ├───────────────────────────────────────┤  ← 61440   │
│                    │ Chunk 4   header ✓                    │            │
│                    │ Chunk 4   pages  ✓ (部分写入)         │            │
│                    │ Chunk 4   footer  ✗ (Fletcher 字段未写)│           │
│  offset 0x00012000 └───────────────────────────────────────┘  ← 73728   │
│                                                                         │
│  说明:                                                                   │
│    * block size = 4096 字节（File Header 的 blockSize:1000_16）          │
│    * File Header 双副本严格占据 block 0 / block 1                       │
│    * Chunk N 的起点 = blockSize × Chunk.block 字段                      │
│    * Footer 长度 = 128 字节，固定贴在 chunk 末尾                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```
**图 A-15: 标注磁盘字节布局与末尾损坏 Chunk**

如图 A-15 所示，本案例中两份 File Header 的字节内容完全一致，因为最近一次成功的 commit（即提交 T3 时）已把"指向 Chunk 3"这一信息写入了双副本，且后续的"乐观跳过"机制让它们保持稳定。仲裁规则在 `FileStore.parseStoreHeader()` 中实现：

```java
// 仲裁逻辑（伪代码，详见 FileStore.java 内 parseStoreHeader / selectBestHeader）
StoreHeader h0 = parseStoreHeader(buf, 0);
StoreHeader h1 = parseStoreHeader(buf, 1);
StoreHeader best;
if (h0.valid && h1.valid) {
    best = (h0.version >= h1.version) ? h0 : h1;
} else if (h0.valid) {
    best = h0;
} else if (h1.valid) {
    best = h1;
} else {
    // 都损坏 → 退化到从文件末尾扫描 chunk footer
    best = scanChunkFootersBackward();
}
```

决策点在于：两份均有效时取版本号大的；其一损坏时取另一份；两份均损坏时回退到末尾扫描（详见 §9.6.2）。本案例命中第一条分支：`best = h0`，`best.chunk = 3`，`best.block = N3`。注意 `block` 字段并不一定指向"绝对最新"的 chunk——为了减少对 File Header 的写放大，MVStore 允许 `next` 链跳转最多 20 跳后才回写 header（详见 §9.6.3）。

### A.3.4 沿 next 链定位最新 Chunk

拿到候选 chunk 之后，`setLastChunk(Chunk c)` 会从 `c` 的 footer 出发沿 `next` 字段向前扫描，逐个尝试把 next 指向的 chunk 当作"更新的版本"。这个步骤的核心目的是：在 File Header 没有写入最新位置的场景下，仍能找到最新的有效 chunk。

```text
┌────────────────────────────────────────────────────────────┐
│      next 链扫描（最多 20 跳）                               │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   起点 = File Header.chunk = Chunk 3                       │
│                                                            │
│   loop ≤ 20:                                               │
│      读取 candidate.footer                                  │
│        ├─ Fletcher-32 OK?                                  │
│        │     │                                              │
│        │     ├── YES → accept candidate, 跳到 next         │
│        │     │         如果 next 越界或 = 0 → 停止           │
│        │     │                                              │
│        │     └── NO  → reject candidate, 回退到上一已知好   │
│        │                的 chunk，停止                      │
│        │                                                    │
│        └─ 跳数 == 20?                                       │
│              └── YES → 强制停止（详见 §9.6.3 next 上限）   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```
**图 A-16: 描绘 next 链扫描决策路径**

如图 A-16 所示，恢复流程沿着 Chunk 3 → Chunk 4 的 next 链前进。Chunk 3 的 footer 写道 `next = N4`，于是引擎读取 offset `0xF000` 处的字节，尝试解析 Chunk 4 的 footer。如果 Chunk 4 footer 的 Fletcher-32 校验失败（本案例的异常分支），整个 next 链立即截断，最近一次"已 accept"的 chunk（即 Chunk 3）被定为 lastChunk。这个决策的本质是：**Footer 的 Fletcher 校验是 Chunk 完整写入的"提交位"**——一旦校验失败，恢复子系统就把这个 chunk 当作从未存在过来处理（详见 §9.7.7 的"写入 Chunk 数据中崩溃"行）。

如果换成"正常路径"——即 Chunk 4 的 footer 已经完整落盘——next 链会成功 accept Chunk 4，再尝试沿 Chunk 4 的 next 字段继续，直到遇到无效 footer 或越过 20 跳上限为止。两种路径在此步骤的输出虽然不同（lastChunk = Chunk 3 vs Chunk 4），但后续步骤对它们的处理方式是同构的：都是"以 lastChunk 为根重建状态"。

### A.3.5 Chunk Footer 校验：正常分支与异常分支

本节单独把 Footer 校验抽出来分析，因为它是整个恢复流程中唯一一个"产生分支"的决策点。Footer 长度固定 128 字节（详见 §9.3.2），格式为：

```text
chunk:<id>,block:<n>,version:<v>,fletcher:<crc>
```

引擎读取 footer 后，先按文本协议解析得到 `chunk`、`block`、`version`，再对 footer 自身（除 fletcher 字段外）计算 Fletcher-32 并与字段值比较。任一不一致都视为校验失败。

```text
┌──────────────────────────────────────────────────────────────┐
│   Chunk Footer 校验决策树                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   读取 footer (128 B, 末端贴齐 chunk 末尾)                    │
│         │                                                    │
│         ▼                                                    │
│   parseKeyValue("chunk:..,block:..,version:..,fletcher:..") │
│         │                                                    │
│         ▼                                                    │
│   字段缺失 / 非法整数?                                        │
│       ├── YES → REJECT (异常分支)                            │
│       └── NO                                                 │
│              │                                                │
│              ▼                                                │
│       computed = Fletcher32(footer 除 fletcher 字段外)       │
│       claimed  = 解析得到的 fletcher                          │
│              │                                                │
│              ▼                                                │
│       computed == claimed ?                                   │
│              ├── YES → ACCEPT (正常分支)                      │
│              │         lastChunk = this chunk                │
│              │         读取 chunk header 中的 root, layout    │
│              │                                                │
│              └── NO  → REJECT (异常分支)                      │
│                        lastChunk = 前一已 accept 的 chunk    │
│                        Chunk 4 的 header / pages 全部丢弃    │
│                        (它们尚未提交)                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
**图 A-17: 拆解 Chunk Footer 校验与分支收敛**

如图 A-17 所示，正常分支与异常分支在此处分流，但都会回到同一棵后续流程上：

- **正常分支（footer 完整）**：Chunk 4 被 accept，root、layoutMap 字段从 Chunk 4 header 中读出。后续 B-Tree 重建会以 Chunk 4 中的 root 为入口，T4 的修改对客户端可见——这要求 T4 在崩溃前已经走完了 `TransactionStore.commit()` 的全部三阶段（详见 §9.7.3）。
- **异常分支（footer Fletcher 不一致或字段缺失）**：Chunk 4 被 reject，恢复子系统回到 Chunk 3 作为 lastChunk。T4 的所有修改（无论它的 undo log 标记了什么）都被视为"从未发生"。这正是 H2 不需要 redo 的原因：**没有 footer，就没有 commit**。

本案例命中异常分支：Chunk 4 footer 缺少 fletcher 字段或字段值与重新计算的 Fletcher-32 不匹配，恢复子系统选择 Chunk 3。

### A.3.6 B-Tree 根重建与 layoutMap 回填

确定 lastChunk 之后，恢复流程进入"重建运行时状态"阶段。`MVStore.setLastChunk()` 从 `lastChunk.header` 中拿到 layoutMap 的 root 位置（chunk/offset/length 三元组），调用 `Page.read()` 递归从磁盘加载 layoutMap 的全部节点（详见 §9.2 中 Page 反序列化流程的描述）。layoutMap 是一个 mapId → rootPagePos 的映射，覆盖了数据库中所有 MVMap（用户表、索引、metaMap、undoLog map 等）。

```text
┌──────────────────────────────────────────────────────────────────┐
│   阶段 4: 通过 layoutMap 回填所有 MVMap 的根                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   layoutMap (来自 Chunk 3 header)                                │
│      ┌─────────────────────────────────┐                          │
│      │ key=1  → rootPos(chunk=3, ...) │ metaMap                  │
│      │ key=2  → rootPos(chunk=3, ...) │ users 表的主索引          │
│      │ key=3  → rootPos(chunk=2, ...) │ users.idx_email         │
│      │ key=N  → rootPos(chunk=K, ...) │ ...                       │
│      └─────────────────────────────────┘                          │
│              │                                                    │
│              ▼                                                    │
│   for each (mapId, rootPos):                                     │
│      page = Page.read(rootPos)                                    │
│      MVMap m = openMap(mapId)                                     │
│      m.setRootReference(new RootReference(page))                  │
│              │                                                    │
│              ▼                                                    │
│   metaMap 中扫描 "undoLog.*" 名前缀                               │
│      ├── 找到 ".undoLog.4"  → T4 状态 = OPEN                      │
│      ├── 找到 ".undoLog.3"  → 不存在 (commit 后已清理)             │
│      └── 找到 ".undoLog-X"  → COMMITTED 但未清理 (本例无)         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 A-18: 演示 layoutMap 驱动的 root 回填**

如图 A-18 所示，layoutMap 的存在让恢复流程不需要扫描整个文件来寻找 page 边界——它一次性给出了所有"活根"的位置。但要注意：异常分支下 lastChunk 是 Chunk 3，因此 layoutMap 自身也来自 Chunk 3，这意味着**T4 引入的任何新建 map（例如新建表带来的索引）都不会出现在 layoutMap 里**——它们随同 Chunk 4 一并消失（详见 §6.2 中 mapId 单调递增的描述）。这是 ACID 中的 A（原子性）在 MVStore 上的具体落地：要么整个 Chunk 生效，要么完全不生效。

### A.3.7 Undo Log 扫描与未完成事务回滚

B-Tree 根重建后，`TransactionStore.open()` 被调用。它在 metaMap 中查找所有以 `.undoLog.` 或 `.undoLog-` 开头的 map 名（详见 §4.5.2），命名后缀承载事务状态：

| map 名后缀 | 事务状态     | 恢复动作                        |
|------------|-------------|---------------------------------|
| `.`        | OPEN        | 用 RollbackDecisionMaker 回滚    |
| `-`        | COMMITTED   | 用 CommitDecisionMaker 重做      |

```text
┌────────────────────────────────────────────────────────────────────┐
│        恢复期未完成事务处理时序图                                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  TransactionStore.open()                                           │
│        │                                                           │
│        ├─ 扫描 metaMap → 发现 ".undoLog.4"                          │
│        │     suffix = "."  → T4 = OPEN                              │
│        │                                                           │
│        ├─ openTransaction(id=4, status=OPEN)                       │
│        │     └─ 重建 Transaction 对象, status = STATUS_OPEN         │
│        │                                                           │
│        ├─ 调用 t4.rollback()                                       │
│        │     └─ Transaction.java:561                               │
│        │     └─ markTransactionEnd()                               │
│        │     └─ store.rollbackTo(t4, maxLogId, 0)                  │
│        │                                                           │
│        ├─ TransactionStore.rollbackTo()                            │
│        │     └─ TransactionStore.java:824                          │
│        │     └─ 逆序遍历 undoLog[4]:                                │
│        │           for logId = max-1 .. 0:                         │
│        │              undoKey = (4 << 40) | logId                  │
│        │              undoLog.operate(undoKey, null, RDM)          │
│        │                                                           │
│        ├─ RollbackDecisionMaker.decide()                           │
│        │     └─ RollbackDecisionMaker.java:34                      │
│        │     └─ Record(mapId, key, oldValue) 解码:                 │
│        │           oldValue == null → REMOVE(key)                  │
│        │           oldValue != null → PUT(key, oldValue)           │
│        │                                                           │
│        ├─ undoLog[4].clear()                                       │
│        │                                                           │
│        └─ 从 metaMap 删除 ".undoLog.4" 条目                          │
│                                                                    │
│   注:committingTransactions BitSet 是 in-memory 的, 重建为空集     │
│       (详见 §9.7.6: BitSet 不持久化)                                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```
**图 A-19: 追踪未完成事务的回滚序列**

如图 A-19 所示，T4 由于其 undo log 后缀仍是 `.`，被识别为 OPEN。`RollbackDecisionMaker.decide()` 的逻辑（详见 §5.6）逐条恢复 oldValue：原 INSERT 的记录被 REMOVE 抹除，原 UPDATE 的记录被 PUT 回旧值。这一步与 SQL 层的 ROLLBACK 命令走的是完全相同的代码路径——区别只在于 ROLLBACK 由用户线程触发，而恢复期的回滚由 `TransactionStore.open()` 在打开数据库时自动触发（详见 §9.7.4 阶段 5）。

值得注意的是：在异常分支下，整个 Chunk 4 都被丢弃，这意味着 T4 的 undo log 事实上**根本没有写入磁盘**（它原本就在 Chunk 4 中），因此扫描 metaMap 时根本不会发现 `.undoLog.4`。本案例中 T4 的回滚动作其实是"零操作"——A.3.7 所描述的回滚流程，是在另一种崩溃场景下（Chunk 4 落盘成功、但 commit 阶段崩溃）触发的。我们仍然完整描述这条路径，以便读者理解恢复决策矩阵的两个相邻单元（详见 §9.7.7 中"事务写入 undo log 后崩溃"和"commit() 期间崩溃"两行）。

如果后缀是 `-`（COMMITTED），恢复路径会走 `commit(t, recovery=true)` 而非 rollback：CommitDecisionMaker 把 VersionedValueUncommitted 转换为 VersionedValue，去掉 operationId。这一动作是**幂等**的——崩溃前如果已经部分提交过，重做不会破坏一致性（详见 §9.7.6 末尾的"未决问题与解决方案"段落）。

### A.3.8 Free Space 重算与对外开放写入

最后一步是把磁盘上的字节占用情况重新加载到内存中的 `FreeSpaceBitSet`（`org/h2/mvstore/FreeSpaceBitSet.java`，详见 §6.4）。BitSet 不持久化，必须在每次打开时根据 lastChunk 之前的所有"活 chunk"重新计算：

```text
┌────────────────────────────────────────────────────────────┐
│   阶段 6: FreeSpaceBitSet 重算                              │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   freeSpace = new FreeSpaceBitSet(reservedBlocks=2)        │
│   // block 0,1 被 File Header 双副本永久占用                │
│                                                            │
│   for chunk in metaMap.chunks:                             │
│      freeSpace.markUsed(chunk.block, chunk.len)            │
│                                                            │
│   // 异常分支补充:                                          │
│   if (Chunk 4 字节区间存在但已 reject):                     │
│      // 不 mark used → 该区间在 BitSet 中保持 free          │
│      // 下次 commit 时可被覆盖                               │
│                                                            │
│   // 此时 freeSpace 反映了真实的"活字节"分布                │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

完成 BitSet 重建后，`MVStore.openComplete()` 把状态机推进到 `STATE_OPEN`（详见 §9.1 状态机定义），背景写入线程（BackgroundWriterThread）启动，定时检查点开始运行。此时数据库才真正可以接受新的写入请求——任何新提交的事务会从下一个 chunk id（本例中是 4，注意 Chunk 4 的字节虽然存在但未被记录在 metaMap 里，它的 block 区间属于 free space，会被新 chunk 覆盖）开始递增（详见 §9.6.3 中"chunk id 单调递增"的说明）。

值得详细说明的是 FreeSpaceBitSet 的"重算而非加载"策略。MVStore 没有把 BitSet 持久化到文件，原因有三：第一，BitSet 是高频更新的内存结构，每次 commit 都会变化，持久化会引入新的写放大；第二，从 metaMap 中的 chunk 列表出发，可以严格、确定地重算出 BitSet，不存在"持久化 BitSet 与磁盘真实占用不一致"的可能；第三，重算过程的复杂度是 O(C)，C 为 chunk 数，对常见数据库通常在 10⁴ 量级，恢复期内可以在毫秒级完成（详见 §6.4.5 状态转换图）。

另一个值得展开的设计细节是"Chunk 4 的字节并没有被物理覆盖"。在异常分支下，恢复流程把 Chunk 4 占用的 block 区间标记为 free，但并不会主动 zero-fill 这些字节。这意味着如果进一步发生第二次崩溃，磁盘上仍然存在三类数据：完整的 File Header 双副本、Chunk 1～3 的有效字节、Chunk 4 的"幽灵字节"。第二次重启时，next 链扫描会再次拒绝 Chunk 4，得到与本次相同的恢复结果——这种**确定性 + 幂等性**的组合是 H2 恢复机制最重要的工程性质（详见 §9.7.5 决策树）。

```text
┌──────────────────────────────────────────────────────────────────┐
│        恢复决策汇总矩阵                                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   场景                  │ 触发的检测      │ 恢复动作      │ 数据丢失 │
│   ─────────────────────┼───────────────┼─────────────┼─────────  │
│   File Header 1 损坏   │ block 0 校验失败│ 选 block 1  │ 无         │
│   File Header 2 损坏   │ block 1 校验失败│ 选 block 0  │ 无         │
│   两 Header 都损坏     │ 两次校验失败    │ 末尾扫描     │ 取决末尾   │
│   Chunk N footer 损坏  │ Fletcher 不匹配 │ 回退 Chunk N-1│ Chunk N  │
│   Chunk N header 损坏  │ 字段解析失败    │ 跳过 Chunk N │ Chunk N    │
│   未完成事务           │ undoLog.<id>.   │ rollback    │ T 的修改  │
│   未清理已提交事务      │ undoLog-<id>-   │ commit 重做  │ 无         │
│   FreeSpaceBitSet 误差 │ 重新扫描        │ 全量重建     │ 无         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 A-20: 汇总恢复决策矩阵**

如图 A-20 所示，本案例（异常分支：Chunk 4 footer 损坏）落在第四行：恢复动作是回退到 Chunk 3，T4 的所有修改丢失。从 SQL 客户端角度看，T4 没有收到 `COMMIT OK`，因此 ACID 的 D（持久性）并未被违反——只对已确认提交的事务承诺持久性。

恢复完成的最终状态是：

- 内存中重建出 metaMap、layoutMap 以及 T1、T2、T3 看到过的所有用户表 root；
- `committingTransactions` BitSet 为空集；
- 没有任何 `Transaction` 对象处于 OPEN 状态；
- FreeSpaceBitSet 把 block 0、1（双 header）以及 Chunk 1～3 的字节区间标记为 used，其余（包括 Chunk 4 占用的字节）标记为 free，可被下一个 chunk 覆写；
- MVStore 状态机推进到 `STATE_OPEN`，对外开放写入。

至此，恢复流水线的 8 个步骤全部走完。此时如果应用层立刻发起一个新事务 T5，它的 chunk id 会从最近一次成功 commit（Chunk 3）的下一位继续递增，而磁盘上残存的 Chunk 4 字节会在下一个检查点被新 chunk 覆盖（详见 §9.5 中检查点的覆盖语义）。

把整条恢复路径与 §9.7.7 中的崩溃-恢复矩阵交叉对照可以发现：本案例中 Chunk 4 footer 损坏对应矩阵第 1 行（"写入 Chunk 数据中崩溃"），其数据保证为"最多丢失一个 Chunk"。而正常分支（footer 完整、但 commit() 未完成）则对应矩阵第 4 行（"commit() 期间崩溃"），其数据保证为"不丢失已提交的数据"。两条路径在本案例的同一棵决策树上汇合，最终都让数据库回到一致的可用状态。这种**两条物理路径、一条语义路径**的设计，是 H2 在"无 WAL"前提下仍能提供完整 ACID 保证的根本原因（详见 §9.4.2 与 §10.8 中 ACID 视角的总结）。

最后，从可观测性视角整理一组本案例中可被外部观察到的事件序列，这对生产环境调试很有帮助：

```text
   t0   进程启动, JVM 加载                                    [外部可见]
   t1   FileChannel.open(.mv.db, READ|WRITE)                [文件锁日志]
   t2   readStoreHeader(): block 0 OK, block 1 OK            [trace log]
   t3   pickHeader: chunk=3, version=3                       [trace log]
   t4   setLastChunk(3): footer OK                           [trace log]
   t5   next 链跳到 Chunk 4: footer Fletcher MISMATCH         [WARN log]
   t6   accept Chunk 3 as lastChunk, drop Chunk 4 bytes      [INFO log]
   t7   layoutMap loaded: N maps                             [trace log]
   t8   metaMap scan: undoLog.* count = 0 (本异常分支)        [INFO log]
   t9   FreeSpaceBitSet built: used=K blocks, free=M blocks  [INFO log]
   t10  MVStore.openComplete(): state=OPEN                   [INFO log]
   t11  BackgroundWriterThread started                        [INFO log]
   t12  数据库就绪, 开始服务新连接                              [外部可见]
```

如果换成正常分支（Chunk 4 footer 完好但 commit() 中途崩溃），t8 行会变为"undoLog.* count = 1, suffix=`-`, redo commit"，t9 之后的 BitSet 中 Chunk 4 区间会变成 used 而非 free。两条路径的可观测差异恰好对应它们的语义差异，运维人员可据此精准定位崩溃发生的物理位置（详见 §9.7.4 阶段对照）。

### A.3.9 思考小结

下面是三个用以自检的练习题，覆盖本案例中尚未展开的细节，建议读者结合源码反复推演：

1. 如果 Chunk 4 的 footer 校验恰好通过（fletcher 字段刚好凑巧匹配损坏的字节序列），但 Chunk 4 中某个 leaf page 的 page-level checksum 失败，恢复流程会如何处理？请结合 Page 反序列化路径的 checksum 检查给出答案（详见 §9.6.4）。
2. 双副本 File Header 都损坏、且文件末尾若干 chunk 的 footer 也损坏时，`scanChunkFootersBackward()` 会从后往前扫描寻找最后一个有效 footer。这个回退路径的最坏复杂度是 O(N)（N=chunk 数），在大数据库上可能造成长时间不可用。请讨论 H2 用什么机制把概率降到最低（详见 §9.6.2 中"两份 header 冗余写入"和 §9.7.7 中"两个都无效"行）。
3. 在恢复过程中，`committingTransactions` BitSet 不持久化，因此重建时为空集。请说明：在"commit() 已 flip BitSet，但尚未遍历 undo log 完成"的场景下，恢复期如何只通过 undo log map 名后缀就把这种"半提交"事务推进到一致状态——并给出幂等性论证（详见 §5.6 中 RollbackDecisionMaker 的中止保护与 §9.7.6 中 VersionedBitSet 的恢复处理）。

本案例至此结束。三条端到端路径——SELECT 读路径（A.1）、COMMIT 写路径（A.2）、崩溃恢复路径（A.3）——共同覆盖了 H2 在"读—写—恢复"三个维度上的 ACID 落地视图。如需进一步在版本维度上对照同一路径在不同小版本的实现差异，请参阅附录 B《源码版本变更说明》。

---

**附：本案例引用的源码位置一览**

下表汇总本案例中提到的全部源码符号、所在文件与近似行号，便于读者按图索骥：

| 符号 / 函数                                | 文件路径                                                  | 行号       |
|--------------------------------------------|----------------------------------------------------------|------------|
| `MVStore.openInternal()`                   | `org/h2/mvstore/MVStore.java`                            | 259-319    |
| `MVStore.setLastChunk()`                   | `org/h2/mvstore/MVStore.java`                            | (内部)     |
| `MVStore.openComplete()`                   | `org/h2/mvstore/MVStore.java`                            | (状态切换) |
| `FileStore.readStoreHeader()`              | `org/h2/mvstore/FileStore.java`                          | 962        |
| `FileStore.serializeToBuffer()`            | `org/h2/mvstore/FileStore.java`                          | 1467-1517  |
| `SingleFileStore.start()`                  | `org/h2/mvstore/SingleFileStore.java`                    | (open)     |
| `Chunk.FOOTER_LENGTH`                      | `org/h2/mvstore/Chunk.java`                              | 44         |
| `Page.read()`                              | `org/h2/mvstore/Page.java`                               | 594-675    |
| `TransactionStore.open()`                  | `org/h2/mvstore/tx/TransactionStore.java`                | (打开)     |
| `TransactionStore.commit(t, recovery)`     | `org/h2/mvstore/tx/TransactionStore.java`                | 579-633    |
| `TransactionStore.rollbackTo()`            | `org/h2/mvstore/tx/TransactionStore.java`                | 824-833    |
| `RollbackDecisionMaker.decide()`           | `org/h2/mvstore/tx/RollbackDecisionMaker.java`           | 34-48      |
| `Transaction.rollback()`                   | `org/h2/mvstore/tx/Transaction.java`                     | 561        |
| `FreeSpaceBitSet.allocate()`               | `org/h2/mvstore/FreeSpaceBitSet.java`                    | 140-169    |
| `FreeSpaceBitSet.free()`                   | `org/h2/mvstore/FreeSpaceBitSet.java`                    | 196-202    |

行号以 H2 v2.x 主干为准；不同小版本可能有 ±10 行偏差，但以函数签名为准检索仍可定位（详见 §3 各包索引）。

## 15.1 附录 K 源码坐标索引

本节由源码清单生成，覆盖 5 个包，行号对应当前源码树。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `Token.toString()` | `org/h2/command/Token.java:476` |
| `FileStore.accountForRemovedPage()` | `org/h2/mvstore/FileStore.java:2178` |
| `MVStore.adoptFileStore()` | `org/h2/mvstore/MVStore.java:2183` |
| `MVMap.append()` | `org/h2/mvstore/MVMap.java:1364` |
| `Page.copy()` | `org/h2/mvstore/Page.java:382` |
| `Database.addDatabaseObject()` | `org/h2/engine/Database.java:948` |
| `SessionLocal.addLocalTempTable()` | `org/h2/engine/SessionLocal.java:397` |
| `SessionRemote.addTemporaryLob()` | `org/h2/engine/SessionRemote.java:819` |
| `Mode.getEnum()` | `org/h2/engine/Mode.java:766` |
| `ExpressionColumn.createIndexConditions()` | `org/h2/expression/ExpressionColumn.java:499` |
| `Expression.addFilterConditions()` | `org/h2/expression/Expression.java:477` |
| `BinaryOperation.getOperationType()` | `org/h2/expression/BinaryOperation.java:450` |
| `ExpressionVisitor.addDataModificationId()` | `org/h2/expression/ExpressionVisitor.java:361` |
| `Index.add()` | `org/h2/index/Index.java:210` |
| `IndexCondition.cloneWithIndexColumns()` | `org/h2/index/IndexCondition.java:559` |
| `IndexCursor.canUseIndexForIn()` | `org/h2/index/IndexCursor.java:318` |
| `LinkedIndex.add()` | `org/h2/index/LinkedIndex.java:61` |

## 15.2 延伸思考

下列题目面向"用坐标串起一次完整调用"。

**1. 🟢★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：先从 §15.1 的坐标表挑一个入口。
> 回顾：§15.1 附录 K 源码坐标索引

**2. 🔵★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：先从 §15.1 的坐标表挑一个入口。
> 回顾：§15.1 附录 K 源码坐标索引

**3. 🟠★★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：先从 §15.1 的坐标表挑一个入口。
> 回顾：§15.1 附录 K 源码坐标索引

**4. 🟢★★★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：先从 §15.1 的坐标表挑一个入口。
> 回顾：§15.1 附录 K 源码坐标索引

## 15.3 本章小结

- 本节给出 19 个可核验的源码坐标。
- 上游升级后重新生成即可刷新行号。

## 15.4 延展阅读

- 详见第3章《包结构与模块职责》。
# 附录 B：源码版本变更说明（v2.4.240 → v2.4.249-SNAPSHOT）

> 本书以 H2 v2.4.249-SNAPSHOT 为基础源码版本进行分析。撰写期间，
> 上游主干自 v2.4.240（2026-04）至 v2.4.249-SNAPSHOT（2026-05）累计 44 次提交，
> 涉及 81 个文件。本附录摘录其中影响第 9-10 章（持久化与并发控制）叙述的关键变更，
> 供读者在对照其他小版本源码时快速理解差异。
>
> 本附录不复述算法本体——算法描述以正文为准；本附录仅给出与正文叙述相关的"实现差异点"。
> 对应源文件索引见正文 §9 与 §10 各节的源文件表格。
>
> 本附录与附录 A《端到端案例研究》并列：附录 A 沿时间维度串联读、写、恢复三条路径；
> 本附录沿版本维度记录同一条路径在不同小版本上的实现差异。

## B.1 MVStore 核心层

- **panicException 改为 AtomicReference**：原先为 `volatile` 字段，现改为 `AtomicReference` + `compareAndSet`，确保仅捕获首个 panic 异常。新增 `panic(Throwable)` 重载作为标准入口。后台线程在 panic 状态下不再调用 `closeImmediately()`，仅通过 `handleException()` 记录。
- **closeStore() 序列变更**：`commit()` 移至 maps 关闭循环之后；状态转换从 `if (state == STATE_OPEN)` 守卫改为 `assert state == STATE_OPEN` + 无条件转换。新增 `closingThreadId` 追踪。
- **`isClosed()` 自旋等待**：若发现其他线程正在执行 `closeStore()`，当前线程将以 `Thread.sleep(millis++)` 从 1ms 递增等待，仅在 `closingThreadId != Thread.currentThread().getId()`（不同线程）时触发。
- **commit() 防重入**：通过快照记录 `versionAtStart`，若在锁重入时版本已变化，则跳过本次提交，防止嵌套提交。
- **MVMap.operate() 简化**：所有页面操作逻辑（拆分、删除、复制、根分裂）从 `operate()` 内联代码移至 `DecisionMaker.decide(CursorPos, K, V)` 方法。`operate()` 仅负责任务重试/中止/应用循环。
- **tryLock() CPU 感知退避**：根据 `Runtime.getRuntime().availableProcessors()` 自适应旋转等待。前 `CPU_COUNT` 次使用 `Thread.onSpinWait()`，随后 `Thread.yield()`，再降级为 `lock.wait(1)`。移除 `Thread.sleep(contention)`。
- **CursorPos 树遍历路径重用**：`traverseDown()` 新增 `existing CursorPos` 参数。重试时可复用上次遍历路径。若页面键数组未变（`sameKeys()` 引用相等性检查），连二分查找结果也可重用。
- **Page 批量删除**：`Page.remove(long positionsToRemove)` 新增位掩码批量删除方法，可在一次操作中移除多个键值对。
- **编译压缩优化**：`TransactionStore.isTransactionClosed()` 的条件判断简化为 `transactionId <= maxTransactionId`，减少冗余方法调用。
- **FileStore 流水线重构**：新增 `recentlySaved` 队列（`LinkedBlockingQueue<Chunk>`），chunk 元数据提交至 layout map 被延迟到下一个 chunk 创建时。`saveRecentChunksInLayout(long version)` 作为刷新方法，由 `stop()` 在最终提交前调用。修复因 layout map 不完整导致的 ChunkNotFound 问题。
- **moveChunk 错误恢复**：移动操作失败时恢复 chunk 原始 block 位置并释放新分配空间。
- **isBackupThread 判定移除**：原 `isBackupThread` 逻辑已被 H2_THREAD_GROUP 的线程分组机制替代，后台线程的身份识别统一基于线程组归属。

## B.2 事务子系统

- **TransactionStore 状态机**：引入显式状态常量（OPEN→INITIALIZING→READY→CLOSING→CLOSED = 0→4），配合 `AtomicInteger` 替代原先的 `boolean init` 标志。`init()` 和 `close()` 均使用 CAS 原子转换，防止并发竞态。
- **CommitDecisionMaker（新增）**：实现 page-level 决策机制，以页为单位批量处理提交逻辑，而非逐条处理 undo log 条目。通过 `haveSeenEntry(int entryId)` 实现同一条目的去重，配合 `VersionedValueCommitted.getInstance(value, entryId)` 将条目标记为已提交。
- **等待事务提前通知**：`TransactionStore.commit()` 在 undo log 回放前即调用 `notifyAllWaitingTransactions()`，使受阻塞的事务更早被唤醒。
- **MAX_OPEN_TRANSACTIONS 默认值调整**：从 65535 降为 255，现可通过 `h2.maxOpenTransactions` 系统属性配置。`undoLogs` 数组大小调整为 `MAX_OPEN_TRANSACTIONS + 1`。
- **恢复工具 maxOpenTransactions 覆盖**：`DirectRecover.java` 和 `Recover.java` 的 `main()` 入口处通过 `System.setProperty("h2.maxOpenTransactions", "65535")` 将上限恢复为 65535。此变更为以命令行的方式运行恢复工具时默认放宽限制，不影响嵌入式运行。
- **VersionedBitSet 重写**：不再继承 `java.util.BitSet`，改为不可变的 `long[]` 包装类。`clone()` 调用全部移除，通过构造器 `VersionedBitSet(VersionedBitSet, int)` 创建新实例并翻转指定位。
- **BitSetHelper（新增）**：提供基于 `long[]` 的最小 BitSet 功能（get/flip/nextSetBit/nextClearBit/length），通过不可变模式保证线程安全。
- **committingTransactions 类型迁移**：`TransactionStore.committingTransactions` 从 `BitSet` 改为 `long[]`，波及 `TransactionMap`、`Snapshot`、`Transaction` 等 7 个文件。`Snapshot.hashCode()` 改用 `System.identityHashCode()`。
- **VersionedValue 序列化格式变更**：序列化从"先写 operationId varLong"改为"先写 flags 字节"——根据 flags 决定后续字段的存在。已持久化的旧版本（v2.4.240）数据文件不兼容此格式。**架构影响**：此变更意味着 v2.4.249-SNAPSHOT 无法直接读取 v2.4.240 创建的 MVStore 数据文件，需通过数据迁移或 DDL 重新导入。
- **事务恢复排序**：非正常关闭后的残余事务按提交序列号（commitment order）排序注册，确保重放顺序正确。
- **死锁修复**：`saveChunkMetadataChanges()` 去除忙等轮询；`acceptChunkOccupancyChanges()` 将未分配 chunk 的 `RemovedPageInfo` 压回队列。`Transaction.waitForThisToEnd()` 新增 `STATUS_COMMITTED` 检查。

## 16.1 附录 L 版本变更对照

本节由源码清单生成，覆盖 4 个包，行号对应当前源码树。

| 入口 | 源码坐标 |
| --- | --- |
| `FileStore.accountForRemovedPage()` | `org/h2/mvstore/FileStore.java:2178` |
| `MVStore.adoptFileStore()` | `org/h2/mvstore/MVStore.java:2183` |
| `MVMap.append()` | `org/h2/mvstore/MVMap.java:1364` |
| `Page.copy()` | `org/h2/mvstore/Page.java:382` |
| `Database.addDatabaseObject()` | `org/h2/engine/Database.java:948` |
| `SessionLocal.addLocalTempTable()` | `org/h2/engine/SessionLocal.java:397` |
| `SessionRemote.addTemporaryLob()` | `org/h2/engine/SessionRemote.java:819` |
| `Mode.getEnum()` | `org/h2/engine/Mode.java:766` |
| `SimpleResultSet.absolute()` | `org/h2/tools/SimpleResultSet.java:2229` |
| `Csv.close()` | `org/h2/tools/Csv.java:639` |
| `Recover.checkPowerOff()` | `org/h2/tools/Recover.java:857` |
| `Server.createPgServer()` | `org/h2/tools/Server.java:539` |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `H2Type.array()` | `org/h2/api/H2Type.java:258` |

## 16.2 延伸思考

下列题目面向"用坐标串起一次完整调用"。

**1. 🟢★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：先从 §16.1 的坐标表挑一个入口。
> 回顾：§16.1 附录 L 版本变更对照

**2. 🔵★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：先从 §16.1 的坐标表挑一个入口。
> 回顾：§16.1 附录 L 版本变更对照

**3. 🟠★★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：先从 §16.1 的坐标表挑一个入口。
> 回顾：§16.1 附录 L 版本变更对照

**4. 🟢★★★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：先从 §16.1 的坐标表挑一个入口。
> 回顾：§16.1 附录 L 版本变更对照

## 16.3 本章小结

- 本节给出 16 个可核验的源码坐标。
- 上游升级后重新生成即可刷新行号。

## 16.4 延展阅读

- 详见第3章《包结构与模块职责》。
# 附录 C：术语表

> 本书核心术语的中英文对照、详细定义、章节索引与相关术语。条目按字母顺序排列。每条遵循"释义 + 章节 + 相关"三段结构，便于读者从任一入口跳转到完整讨论。

## A

- **ACID**: Atomicity, Consistency, Isolation, Durability — 数据库事务四大特性。
  原子性保证事务要么全部提交要么全部回滚；一致性确保事务前后数据满足业务约束；
  隔离性界定并发事务间的可见性；持久性承诺已提交数据在崩溃后仍可恢复。
  **章节**：第10章 §10.5（H2 的 ACID 实现剖析）
  **相关**：[[MVCC]]、[[Undo Log]]、[[Snapshot Isolation]]

- **Append-Only**: 仅追加写入策略。MVStore 的核心写入模式——新数据只追加到文件末尾，
  不覆盖已有数据；旧版本通过 Compact 阶段集中回收。该策略将随机写转换为顺序写，
  天然契合 Copy-on-Write 与崩溃恢复的简化。
  **章节**：第9章 §9.1（MVStore 架构）、第6章 §6.4（Chunk）
  **相关**：[[COW / Copy-on-Write]]、[[Log-Structured Storage]]、[[Chunk]]

- **AbstractAggregate**: 聚合函数抽象基类。继承自 `DataAnalysisOperation`，是
  SUM/COUNT/AVG/MIN/MAX 等内置聚合函数与窗口函数的共同祖先，定义聚合状态的
  累积、合并、最终输出三阶段接口。
  **章节**：第7章 §7.6（表达式求值）
  **相关**：[[Aggregate]]、[[Expression]]

- **Aggregate**: 聚合函数。SQL 中将一组行折叠为单值的函数（COUNT、SUM 等）。
  H2 的实现支持 GROUP BY、HAVING、DISTINCT 修饰符与窗口函数 OVER 子句。
  **章节**：第7章 §7.6、第11章 §11.1
  **相关**：[[AbstractAggregate]]、[[Window 函数]]、[[SelectGroups]]

## B

- **BackgroundWriter**: 后台写入线程。MVStore 周期性执行自动提交（auto-commit）
  与 Compact 操作的守护线程，避免主线程被 I/O 阻塞。`autoCommitDelay` 参数
  控制其触发频率。
  **章节**：第9章 §9.5（检查点机制）
  **相关**：[[Compact]]、[[Chunk]]、[[FileStore]]

- **B-Tree**: 平衡多路查找树（Balanced Tree）。H2 的索引核心数据结构，每个内部节点
  可有多个子节点（典型分支因子 100-200），保证树高对数级增长，支持高效的键值查找
  与范围扫描。H2 实际使用的是 Counted B-Tree 变种。
  **章节**：第6章 §6.1（数据结构篇）
  **相关**：[[Counted B-Tree]]、[[PageSplit]]、[[Page]]、[[MVMap]]

- **Block**: MVStore 文件的最小分配单元。固定为 4096 字节，匹配磁盘扇区与操作系统
  页大小。一个 Chunk 由若干连续 Block 组成，FreeSpaceBitSet 以 Block 为粒度
  跟踪空闲空间。
  **章节**：第9章 §9.6（文件格式详解）
  **相关**：[[Chunk]]、[[Free Space]]、[[FreeSpaceBitSet]]

- **Bloom 过滤**: 布隆过滤器，一种概率型数据结构，用于快速判定元素"可能存在"或
  "肯定不存在"，假阳性率可调。H2 在某些查询路径下用其加速点查。
  **章节**：第12章 §12.1
  **相关**：[[HASH 索引]]

## C

- **CAS (Compare-And-Swap)**: 比较并交换原子原语。通过 `AtomicReference.compareAndSet`
  实现无锁的 RootReference 更新，是 MVCC 无锁读取的核心支撑。失败时通常配合
  自旋重试或退避策略。
  **章节**：第1章、第10章 §10.4
  **相关**：[[MVCC]]、[[RootReference]]、[[Single Writer]]

- **Chunk**: MVStore 中一次 commit 写入的所有数据集合。包含 Header、若干 Page、
  Footer，是 MVStore 的"逻辑事务单元"——崩溃恢复时按 Chunk 边界回滚到最近一致点。
  **章节**：第6章 §6.4、第9章 §9.3、§9.6
  **相关**：[[Block]]、[[Page]]、[[Append-Only]]、[[Fletcher-32]]

- **Checkpoint**: 检查点，将内存中的脏数据强制刷到磁盘并更新 File Header 的同步点。
  MVStore 通过 `MVStore.commit()` 与 `BackgroundWriter` 触发。
  **章节**：第9章 §9.5
  **相关**：[[BackgroundWriter]]、[[FileStore]]、[[File Header]]

- **ConnectionInfo**: 连接信息对象。封装 JDBC URL 中的所有参数（用户名、密码、
  schema、URL 参数）并经多层校验——从客户端 URL 解析直到 Database 实例化。
  **章节**：第2章 §2.2
  **相关**：[[JDBC]]、[[Engine]]、[[DbSettings]]

- **COW / Copy-on-Write**: 写时复制。修改数据时不直接覆盖原数据，而是将修改后的
  数据写入新位置，父节点递归复制更新。在 B-Tree 上等价于"修改一条路径上的所有节点"。
  H2 的 MVStore 是 COW B-Tree 的典型实现。
  **章节**：第6章 §6.2
  **相关**：[[B-Tree]]、[[MVCC]]、[[Append-Only]]、[[Write Amplification]]

- **Counted B-Tree**: 计数 B-Tree，在内部节点中额外存储子树条目数（`totalCount`），
  支持高效的索引访问（按序号取第 N 个元素）和范围计数（COUNT(*) 不必扫表）。
  **章节**：第9章 §9.6
  **相关**：[[B-Tree]]、[[Page]]

- **CBO / Cost-Based Optimization**: 基于代价的查询优化。Optimizer 估算每个候选执行
  计划的代价（行数 × 单位成本），从中选择最优方案。代价模型综合考虑表大小、索引选择性
  与连接顺序。
  **章节**：第8章 §8.1、§8.3
  **相关**：[[Optimizer]]、[[IndexCondition]]、[[Genetic Algorithm]]

- **CommandContainer**: 命令容器。包装 `Prepared` 对象，提供统一的 query/update
  执行入口并支持重编译检测——当依赖的 schema 对象发生变更时自动失效缓存。
  **章节**：第7章 §7.4
  **相关**：[[Prepared Statement]]、[[Parser]]

- **CommitDecisionMaker**: 提交决策器。事务提交时扫描 Undo Log，将每条记录从
  "uncommitted" 状态转为 "committed"，使变更对其他事务可见。
  **章节**：第5章 §5.5
  **相关**：[[TransactionStore]]、[[Undo Log]]、[[VersionedValue]]、[[RollbackDecisionMaker]]

- **Compact**: 紧凑化/压缩整理。MVStore 通过重写低填充率 Chunk 回收磁盘空间的过程。
  类似 LSM-Tree 的 compaction，但在 COW B-Tree 上的实现更轻量。
  **章节**：第6章 §6.4、第9章 §9.5
  **相关**：[[Chunk]]、[[Free Space]]、[[Write Amplification]]

- **Column**: 列对象。H2 中表示表的一列，含数据类型、约束、默认值与生成表达式。
  **章节**：第3章 §3.6
  **相关**：[[Value]]、[[Table]]

- **CTE**: Common Table Expression，公用表表达式。SQL 中以 `WITH` 关键字声明的
  临时结果集，支持递归与多次引用。
  **章节**：第1章 §1.1
  **相关**：[[Parser]]、[[Recursive Descent Parser]]

## D

- **DDL**: Data Definition Language，数据定义语言。CREATE/ALTER/DROP 等改变 schema
  结构的语句。H2 中由 `Database.lockMeta()` 配合 Meta Lock 串行执行。
  **章节**：第5章
  **相关**：[[Meta Lock]]、[[SchemaObject]]

- **Database**: 数据库实例的顶层对象。持有 schema、settings、session 池、
  存储引擎引用与全局锁。`Engine.openDatabase()` 是其入口工厂方法。
  **章节**：第2章 §2.3、第3章 §3.3
  **相关**：[[Engine]]、[[Session]]、[[SchemaObject]]

- **DbSettings**: 数据库配置项。集中管理缓存大小、日志模式、MVCC 行为等运行时参数。
  通过 JDBC URL 参数或 `SET` 语句覆盖默认值。
  **章节**：第3章 §3.3
  **相关**：[[Database]]、[[ConnectionInfo]]

- **Deadlock**: 死锁。两个或多个事务互相等待对方释放锁而导致的无限阻塞。
  H2 通过锁超时（`LOCK_TIMEOUT`）+ 等待图分析检测并主动回滚牺牲者。
  **章节**：第10章 §10.3、第4章 §4.6
  **相关**：[[Lock]]、[[Meta Lock]]

- **DML**: Data Manipulation Language，数据操作语言。SELECT/INSERT/UPDATE/DELETE
  等改变数据但不改变 schema 的语句。
  **章节**：第5章、第7章
  **相关**：[[CommandContainer]]、[[Optimizer]]

- **Driver**: H2 的 JDBC Driver 实现（`org.h2.Driver`）。注册为 JDBC 服务后被
  `DriverManager.getConnection()` 自动发现，是嵌入式与远程模式连接的统一入口。
  **章节**：第2章 §2.2、第3章 §3.2
  **相关**：[[JDBC]]、[[JdbcConnection]]、[[ConnectionInfo]]

## E

- **Engine**: 数据库引擎层入口。负责打开/关闭数据库实例、管理连接池与生命周期。
  `Engine.java` 是 H2 启动路径的关键节点（约 410 行）。
  **章节**：第2章 §2.3、第3章 §3.3
  **相关**：[[Database]]、[[ConnectionInfo]]、[[SessionLocal]]

- **Expression**: 表达式基类。所有 SQL 表达式（比较、算术、函数调用、子查询）的祖先，
  定义 `getValue()` 求值接口。表达式树同时是 H2 的执行计划——这是 H2 简化内存模型的
  关键设计选择。
  **章节**：第2章 §2.3、第4章 §4.2
  **相关**：[[Aggregate]]、[[IndexCondition]]、[[TableFilter]]

## F

- **File Header**: MVStore 文件开头的两个 4096 字节元数据块（双重备份）。
  以 key-value 文本形式记录最新 Chunk 的位置、文件版本、加密信息等。崩溃恢复
  从 File Header 起步。
  **章节**：第9章 §9.3、§9.6
  **相关**：[[FileStore]]、[[Chunk]]、[[Recover]]

- **Fletcher-32**: 高效的 32 位 checksum 算法。MVStore 用于校验 Chunk Footer
  的完整性。比 CRC32 计算更快，碰撞率对该用途已足够低。
  **章节**：第9章 §9.3、§9.6
  **相关**：[[Chunk]]、[[Recover]]

- **FileStore**: 文件存储抽象。MVStore 的 I/O 层，负责 Chunk 的读写、文件锁
  与 File Header 管理。屏蔽底层 FileChannel 的复杂性。
  **章节**：第9章 §9.1、§9.2
  **相关**：[[FilePath]]、[[BackgroundWriter]]、[[File Header]]

- **FilePath**: 文件路径抽象。屏蔽 FileSystemDisk/Encrypt/NioMapped 等底层
  实现差异，使 MVStore 能透明支持磁盘、加密、内存映射等多种存储后端。
  **章节**：第3章 §3.8
  **相关**：[[FileStore]]、[[FilePathDisk]]、[[FilePathEncrypt]]、[[FilePathNioMapped]]

- **FilePathDisk**: 磁盘文件实现。`FilePath` 的标准实现，直接操作 OS 文件系统。
  **章节**：第2章 §2.10
  **相关**：[[FilePath]]、[[FileStore]]

- **FilePathEncrypt**: 加密文件实现。在读写时透明地用 XTS-AES 加密/解密文件块。
  **章节**：第2章 §2.10、第9章 §9.8
  **相关**：[[FilePath]]、[[XTS-AES 加密]]

- **FilePathNioMapped**: 内存映射文件实现。基于 Java NIO `MappedByteBuffer`，
  适合超大数据库以利用 OS 页缓存。
  **章节**：第2章 §2.10
  **相关**：[[FilePath]]

- **Free Space**: MVStore 的空闲空间管理机制。跟踪哪些 Block 已被 Compact 释放
  且可被新 Chunk 重用，由 `FreeSpaceBitSet` 实现。
  **章节**：第6章 §6.6
  **相关**：[[FreeSpaceBitSet]]、[[Compact]]、[[Block]]

- **FreeSpaceBitSet**: 位图实现的空闲空间管理器。每个 bit 表示一个 Block
  是否空闲，分配时从首个 0 位起搜索连续区间。
  **章节**：第5章 §5.7、第6章 §6.6
  **相关**：[[Free Space]]、[[Block]]

## G

- **Genetic Algorithm**: 遗传算法。H2 优化器在大规模多表 JOIN（≥7 表）时使用的
  随机搜索策略——通过"染色体"编码连接顺序、交叉与变异生成新候选、按代价择优。
  **章节**：第8章 §8.2
  **相关**":  [[Optimizer]]、[[Hybrid Strategy]]、[[CBO / Cost-Based Optimization]]

## H

- **H2**: 纯 Java 实现的嵌入式关系数据库管理系统（Hypersonic 2 / Java SQL Database）。
  由 Thomas Mueller 于 2004 年创立，核心 JAR 约 2MB，支持嵌入式与服务器两种模式。
  **章节**：第1章 §1.1
  **相关**：[[MVStore]]、[[PageStore]]

- **HASH 索引**: 基于哈希表的索引结构。仅支持等值查询（不支持范围），适合精确查找。
  **章节**：第2章 §2.8
  **相关**：[[B-Tree]]、[[Index]]

- **Hybrid Strategy**: 混合优化策略。暴力枚举（小表 ≤ 5）+ 贪心填充（中等规模）
  + 遗传算法（大规模）的组合，根据表数量自动切换。
  **章节**：第8章 §8.2
  **相关**：[[Genetic Algorithm]]、[[Optimizer]]

## I

- **Index**: 索引基类。所有索引实现（B-Tree、HASH、SpatialIndex）的祖先，
  定义 `find()`、`add()`、`remove()`、`getCost()` 等接口。
  **章节**：第2章 §2.8、第4章 §4.4
  **相关**：[[B-Tree]]、[[HASH 索引]]、[[R-Tree]]

- **IndexCondition**: 索引谓词。描述可被索引加速的 WHERE 条件片段（EQUALITY、
  RANGE、SPATIAL 三类），是 Optimizer 选择索引的输入。
  **章节**：第4章 §4.4、第8章 §8.4
  **相关**：[[Index]]、[[Optimizer]]、[[Expression]]

- **IOT / Index-Organized Table**: 索引组织表。数据行直接以索引树（B-Tree）的
  叶子节点存储，无独立堆文件。MVStore 模式下的 H2 表本质即 IOT。
  **章节**：第3章
  **相关**：[[B-Tree]]、[[MVTable]]

- **ISODEBUG**: H2 的调试输出宏。通过 `ISODEBUG` 系统属性控制详细日志的开关。
  **章节**：第11章 §11.3
  **相关**：[[测试框架]]

## J

- **JDBC**: Java Database Connectivity。Java 数据库连接的标准 API。H2 的 JDBC 实现
  位于 `org.h2.jdbc` 包，包括 Driver、Connection、Statement、PreparedStatement、
  ResultSet 等。
  **章节**：第2章 §2.1、第3章 §3.2
  **相关**：[[JdbcConnection]]、[[Driver]]、[[Session]]

- **JdbcConnection**: H2 对 `java.sql.Connection` 的实现。每个 Connection 持有
  一个 SessionLocal 与若干 Command 对象。
  **章节**：第3章 §3.2
  **相关**：[[Session]]、[[CommandContainer]]

- **JSON**: H2 支持 JSON 数据类型与 SQL 标准 JSON 函数（JSON_OBJECT、JSON_ARRAY 等）。
  **章节**：第1章 §1.1
  **相关**：[[Value]]

## L

- **LIRS**: Low Inter-reference Recency Set。低互引用最近集缓存替换算法，通过维护
  "热"与"冷"两个 LRU 队列区分高频访问与一次性扫描，比纯 LRU 更能抵抗扫描污染。
  **章节**：第6章 §6.5
  **相关**：[[Cache]]、[[扫描抗性]]

- **LOB**: Large Object（CLOB/BLOB）。大对象数据。H2 对超过阈值的 LOB 单独存储，
  正文行只保存引用。
  **章节**：第7章 §7.2
  **相关**：[[Value]]

- **LSM-Tree / Log-Structured Merge-Tree**: 日志结构合并树。一种针对写优化的
  数据结构，通过分层合并将随机写转换为顺序写。MVStore 不是纯粹 LSM-Tree，但借鉴了
  Append-Only 写入与后台 Compact 的核心思想。
  **章节**：第1章、第9章
  **相关**：[[Append-Only]]、[[Compact]]、[[Log-Structured Storage]]

- **LocalResult**: 本地结果集。查询执行时在内存中构建的中间结果集，支持排序、
  去重、投影。规模大时溢出到磁盘临时文件。
  **章节**：第7章 §7.5
  **相关**：[[Query]]

- **Log-Structured Storage**: 日志结构存储。按写入顺序追加数据而非原地更新的
  存储范式，崩溃恢复简化为"找到最后一个完整 Chunk"。
  **章节**：第6章、第9章 §9.1
  **相关**：[[Append-Only]]、[[LSM-Tree]]、[[MVStore]]

- **Lock**: 锁基类。H2 提供 Shared/Exclusive 两类锁。MVStore 模式下行级锁主要
  通过 MVCC 实现，仅 DDL 与少数 DML 路径使用显式锁。
  **章节**：第10章 §10.1、§10.2
  **相关**：[[Meta Lock]]、[[Deadlock]]

## M

- **Maven**: H2 项目的构建工具。`h2/pom.xml` 定义依赖、编译目标（Java 11）与
  打包流程。
  **章节**：第11章 §11.3
  **相关**：[[测试框架]]

- **Meta Lock**: 元数据锁。Database 内部用于元数据并发控制的轻量级锁，
  保护 schema 修改、表创建/删除等操作。
  **章节**：第4章 §4.1、第10章 §10.1
  **相关**：[[Lock]]、[[DDL]]、[[Database]]

- **Mode**: SQL 兼容模式。H2 通过 `org.h2.engine.Mode` 描述 Oracle/MySQL/
  PostgreSQL/MSSQLServer 等方言差异规则。
  **章节**：第3章 §3.6
  **相关**：[[Parser]]、[[Database]]

- **MVCC**: Multi-Version Concurrency Control，多版本并发控制。通过维护数据的
  多个版本实现读写不互斥——读事务读取一致性快照，写事务用 first-committer-wins
  解决冲突。
  **章节**：第6章 §6.3、第10章 §10.4
  **相关**：[[Snapshot Isolation]]、[[VersionedValue]]、[[TxDecisionMaker]]

- **MVMap**: MVStore 的核心 API。基于 Counted B-Tree 的有序键值映射，
  支持快照读、版本回滚、范围扫描。所有 H2 表与索引都构建在 MVMap 之上。
  **章节**：第4章 §4.6、第9章 §9.2
  **相关**：[[MVStore]]、[[B-Tree]]、[[Page]]

- **MVStore**: H2 自 v2.0 起的默认存储引擎。基于日志结构的多版本键值存储，
  以 COW B-Tree 实现 MVCC。
  **章节**：第4章 §4.6、第9章
  **相关**：[[MVMap]]、[[FileStore]]、[[Chunk]]、[[PageStore]]

- **MVTable**: MVStore 模式下的 Table 实现。将每张 SQL 表映射为一个 MVMap。
  约 1012 行核心逻辑覆盖增删改查与索引联动。
  **章节**：第3章
  **相关**：[[Table]]、[[MVMap]]、[[IOT / Index-Organized Table]]

- **MVStoreTool**: MVStore 的离线工具集。包含 `dump`、`compact`、`info`、
  `simulateCrash` 等命令行子命令，用于运维与测试。
  **章节**：第11章 §11.3
  **相关**：[[MVStore]]、[[Recover]]

## O

- **Optimizer**: 查询优化器。负责选择最高效的执行计划，核心职责是连接顺序选择
  与索引选择。`Optimizer.canStop()` 决定何时终止搜索。
  **章节**：第8章 §8.1
  **相关**：[[CBO / Cost-Based Optimization]]、[[Hybrid Strategy]]、[[IndexCondition]]

## P

- **Page**: MVStore 的最小数据单元。存储一个 B-Tree 节点（叶或内部）的序列化数据。
  Page 内通过 VarInt 紧凑编码减小空间占用。
  **章节**：第9章 §9.6
  **相关**：[[B-Tree]]、[[Chunk]]、[[VarInt / VarLong]]、[[Page Pointer]]

- **Page Pointer**: 64-bit 编码的 Page 位置引用。包含 chunk ID、块内偏移、
  长度代码与节点类型四个字段。是 MVStore 跨 Chunk 引用的统一寻址方案。
  **章节**：第9章 §9.6
  **相关**：[[Page]]、[[Chunk]]

- **PageRef**: Page 的内存引用。包装 Page Pointer 与可能的弱引用，支持懒加载与
  缓存淘汰。
  **章节**：第9章 §9.2
  **相关**：[[Page]]、[[Page Pointer]]、[[LIRS]]

- **PageSplit**: 页面分裂。B-Tree 节点满时按中位数分为左右两页，并向上提升分隔键
  到父节点的操作。MVStore 中分裂总是产生新页（COW），不修改原页。
  **章节**：第6章 §6.1、§6.7
  **相关**：[[B-Tree]]、[[COW / Copy-on-Write]]

- **PageStore**: H2 v1.x 使用的旧版存储引擎。在 v2.0 中被 MVStore 取代。
  本书仅在第1章历史背景中提及，不做深入分析。
  **章节**：第1章 §1.1
  **相关**：[[MVStore]]

- **Parser**: 递归下降解析器。将 SQL 文本（经 Tokenizer 词法分析后）解析为
  Expression 树（即执行计划）。
  **章节**：第6章 §6.10、第8章 §8.2
  **相关**：[[Tokenizer]]、[[Recursive Descent Parser]]、[[Expression]]

- **Prepared / Prepared Statement**: 预编译语句。`Prepared` 是所有命令对象的基类，
  封装编译后的执行计划与参数槽。`PreparedStatement` 是其 JDBC 包装。
  **章节**：第7章 §7.1、§7.4
  **相关**：[[CommandContainer]]、[[Parser]]

## Q

- **Query**: 查询基类。`Select`、`SelectUnion`、`CTE` 等查询类型的共同祖先。
  定义 `prepare()` → `optimize()` → `query()` 三阶段执行框架。
  **章节**：第7章 §7.5、第11章 §11.1
  **相关**：[[Select]]、[[Optimizer]]、[[LocalResult]]

## R

- **R-Tree**: 空间索引结构。用于多维数据（地理坐标、矩形区域）的范围查询与
  最近邻查询。每个节点对应一个最小外包矩形（MBR）。H2 通过 `MVRTreeMap` 实现。
  **章节**：第6章 §6.9
  **相关**：[[Index]]、[[MVMap]]

- **Read Committed**: 读已提交。SQL 标准事务隔离级别，仅允许读取已提交的数据。
  H2 默认隔离级别。
  **章节**：第10章 §10.2
  **相关**：[[隔离级别]]、[[Snapshot Isolation]]

- **Recursive Descent Parser**: 递归下降解析器。手写的自顶向下解析方法，每个
  语法规则对应一个递归函数。H2 选择手写解析器而非 yacc/ANTLR，是其代码简洁的关键
  设计选择之一。
  **章节**：第6章 §6.10、第8章 §8.2
  **相关**：[[Parser]]、[[Tokenizer]]

- **Recoverable Operation**: 可恢复操作。MVStore 中所有写操作必须可在崩溃后从
  Undo Log 与 Chunk 链路恢复。设计上排除了不可逆的就地变更。
  **章节**：第9章 §9.7
  **相关**：[[Recover]]、[[Undo Log]]、[[Append-Only]]

- **Recover**: 恢复工具与流程。`org.h2.tools.Recover` 是离线恢复入口，
  也是崩溃后启动时自动恢复路径的复用基础。
  **章节**：第9章 §9.7
  **相关**：[[Recoverable Operation]]、[[File Header]]、[[Chunk]]

- **Repeatable Read**: 可重复读。SQL 标准事务隔离级别，保证同一事务内多次读取
  同一数据的结果一致。
  **章节**：第10章 §10.2
  **相关**：[[隔离级别]]、[[MVCC]]

- **RollbackDecisionMaker**: 回滚决策器。事务回滚时逆序遍历 Undo Log，将每条记录
  恢复到修改前的旧值。
  **章节**：第5章 §5.6
  **相关**：[[CommitDecisionMaker]]、[[Undo Log]]、[[TransactionStore]]

- **RootReference**: MVStore 中指向 root page 的引用。MVCC 的关键——每次提交
  通过 CAS 原子更新该引用，旧版本保留供并发读事务访问。
  **章节**：第9章 §9.2、第10章 §10.4
  **相关**：[[CAS]]、[[MVCC]]、[[Page]]、[[Single Writer]]

## S

- **Savepoint**: 保存点。事务中的中间状态标记，支持 `ROLLBACK TO SAVEPOINT`
  回滚到指定保存点而不放弃整个事务。
  **章节**：第5章 §5.5
  **相关**：[[Transaction]]、[[Undo Log]]

- **Schema**: SQL 模式。H2 的 schema 是表、视图、函数等数据库对象的命名空间容器。
  **章节**：第3章 §3.3
  **相关**：[[SchemaObject]]、[[Database]]

- **SchemaObject**: schema 对象基类。`Table`、`View`、`Index`、`Sequence` 等
  共同祖先，提供命名、所有者、注释、依赖跟踪等通用能力。
  **章节**：第3章 §3.3
  **相关**：[[Schema]]、[[Database]]

- **Select**: SELECT 命令实现类。最复杂的命令类型，聚合查询优化、表过滤、
  索引选择、表达式求值四大功能。
  **章节**：第7章 §7.1、第11章 §11.1
  **相关**：[[Query]]、[[TableFilter]]、[[Optimizer]]

- **SelectGroups**: SELECT 的分组上下文。GROUP BY 与窗口函数的状态容器。
  **章节**：第7章 §7.6
  **相关**：[[Aggregate]]、[[Window 函数]]

- **Serializable**: 可串行化。SQL 标准最严格的事务隔离级别，保证并发执行结果与
  某种串行执行顺序一致。
  **章节**：第10章 §10.2
  **相关**：[[隔离级别]]、[[MVCC]]

- **Session / SessionLocal**: 会话抽象。代表一个数据库连接及其状态——当前事务、
  锁、临时对象、查询缓存。`SessionLocal` 是嵌入式模式实现；`SessionRemote` 是
  服务器模式客户端实现。
  **章节**：第2章 §2.3、第7章 §7.1.5
  **相关**：[[JdbcConnection]]、[[Database]]、[[Lock]]

- **SessionRemote**: 服务器模式下的会话客户端。通过 TCP/PG 协议与远程 H2 服务器
  通信。
  **章节**：第2章 §2.1
  **相关**：[[Session]]、[[TcpServer]]

- **Single Writer**: 单写入者模型。MVStore 任何时刻仅一个线程能修改 RootReference，
  通过此约束 + CAS 实现无锁并发。
  **章节**：第10章 §10.4、第12章 §12.1
  **相关**：[[CAS]]、[[RootReference]]、[[MVCC]]

- **SmallLRUCache**: 小型 LRU 缓存。SessionLocal 用于缓存已编译的查询计划，
  减少重复解析开销。
  **章节**：第11章 §11.1
  **相关**：[[LIRS]]、[[Prepared Statement]]

- **Snapshot Isolation**: 快照隔离。MVCC 实现的隔离级别——事务读取启动时刻的一致性
  快照，写操作采用 first-committer-wins 策略。可能出现写偏斜异常。
  **章节**：第6章 §6.3、第10章 §10.2、§10.4
  **相关**：[[MVCC]]、[[VersionedValue]]、[[写偏斜]]

- **SocketConnect**: H2 网络模式下客户端连接远程数据库的方式。
  **章节**：第2章 §2.2
  **相关**：[[SessionRemote]]、[[TcpServer]]

## T

- **Table**: 表对象基类。`MVTable`、`RegularTable`、`MetaTable` 等共同祖先。
  **章节**：第2章 §2.8、第4章 §4.4
  **相关**：[[MVTable]]、[[Index]]、[[SchemaObject]]

- **TableFilter**: 表过滤器。Optimizer 选择执行计划后，每个表实例化为一个
  TableFilter，承载该表的访问顺序、索引选择、WHERE 条件下推。
  **章节**：第3章 §3.6、第8章 §8.5
  **相关**：[[Select]]、[[IndexCondition]]、[[Optimizer]]

- **TcpServer**: H2 服务器模式的 TCP 监听器。
  **章节**：第3章 §3.9
  **相关**：[[Server]]、[[SessionRemote]]

- **Tokenizer**: 词法分析器。将 SQL 文本拆解为 token 流供 Parser 消费。
  关注字符级细节（关键字识别、字符串字面量、数字、标识符）。
  **章节**：第3章 §3.4、第6章 §6.10
  **相关**：[[Parser]]、[[Recursive Descent Parser]]

- **Transaction**: 事务。H2 支持 ACID 事务特性，提供多级隔离级别。
  事务的实际管理由 TransactionStore 承担。
  **章节**：第5章 §5.5
  **相关**：[[ACID]]、[[TransactionStore]]、[[隔离级别]]

- **TransactionMap**: 事务感知的 MVMap 包装。根据事务可见性规则（快照隔离）
  过滤版本化数据，对应用代码呈现一致性视图。
  **章节**：第10章 §10.4、第12章 §12.1
  **相关**：[[MVMap]]、[[Snapshot Isolation]]、[[VersionedValue]]

- **TransactionStore**: MVStore 之上的事务管理器。使用单独的 MVMap 存储 Undo Log，
  维护事务状态机（OPEN/PREPARED/COMMITTED/ROLLED_BACK）。
  **章节**：第4章 §4.5、第10章 §10.4
  **相关**：[[Transaction]]、[[Undo Log]]、[[CommitDecisionMaker]]、[[VersionedValue]]

- **TxDecisionMaker**: 写冲突检测器。检查目标键的最新版本是否由并发事务写入，
  以决定本事务的写操作能否提交。
  **章节**：第10章 §10.4
  **相关**：[[MVCC]]、[[VersionedValue]]、[[CommitDecisionMaker]]

## U

- **Undo Log**: 撤销日志。事务回滚时恢复数据所需的旧值记录。MVStore 模式下
  Undo Log 是 TransactionStore 维护的一个 MVMap，而非独立日志文件。
  **章节**：第5章 §5.5、§5.6
  **相关**：[[TransactionStore]]、[[CommitDecisionMaker]]、[[RollbackDecisionMaker]]

- **URL Remap**: H2 的 URL 重映射机制。通过配置文件将数据库路径映射到不同的
  物理位置，便于环境迁移。
  **章节**：第2章 §2.2
  **相关**：[[ConnectionInfo]]

## V

- **Value**: H2 值类型基类。所有 SQL 值（ValueInteger、ValueVarchar、ValueNumeric
  等）的祖先，定义比较、转换、序列化接口。
  **章节**：第3章 §3.10
  **相关**：[[Column]]、[[Expression]]

- **VarInt / VarLong**: 变长整数编码。MVStore 用于优化 Page 中整型字段的空间占用——
  小整数仅占 1-2 字节，大整数最多 5 字节（VarInt）或 9 字节（VarLong）。
  **章节**：第9章 §9.6
  **相关**：[[Page]]、[[Chunk]]

- **VersionedValue**: 版本化值。存储同一键的多个版本（committed/uncommitted）以实现
  MVCC。每个版本含 transactionId、operationId、value 三元组。
  **章节**：第4章 §4.5、第10章 §10.4
  **相关**：[[MVCC]]、[[TransactionStore]]、[[VersionedBitSet]]

- **VersionedBitSet**: 版本化位集。TransactionStore 用于跟踪事务可见性的位图结构，
  v2.4.249-SNAPSHOT 中重写为更紧凑的实现。
  **章节**：第10章 §10.4
  **相关**：[[VersionedValue]]、[[TransactionStore]]

## W

- **WAL / Write-Ahead Log**: 预写日志。在写入数据前先将修改记录到日志文件中的策略。
  传统数据库（PostgreSQL/InnoDB）依赖 WAL 实现持久性。MVStore **不使用** 显式 WAL，
  而是通过"B-Tree 版本化根指针 + 原子 Chunk 写入"达到等价效果。
  **章节**：第9章 §9.1
  **相关**：[[Append-Only]]、[[Log-Structured Storage]]、[[Chunk]]

- **Window 函数**: 窗口函数。SQL `OVER` 子句的实现，包括 ROW_NUMBER、RANK、
  LEAD/LAG 等。基于 SelectGroups 分组逻辑。
  **章节**：第7章 §7.6、第11章 §11.1
  **相关**：[[Aggregate]]、[[SelectGroups]]

- **Write Amplification**: 写放大。COW B-Tree 与 Log-Structured 存储中实际物理
  写入量与逻辑数据量的比值。MVStore 的 Compact 与 LIRS 缓存共同抑制写放大。
  **章节**：第12章 §12.1
  **相关**：[[COW / Copy-on-Write]]、[[Compact]]、[[Log-Structured Storage]]

## X

- **XTS-AES 加密**: H2 文件加密所用的分组密码模式。XTS（XEX-based Tweaked
  CodeBook with Ciphertext Stealing）适合存储加密——同一密钥下不同位置加密结果不同。
  **章节**：第9章 §9.8
  **相关**：[[FilePathEncrypt]]

## Z

- **隔离级别**: SQL 事务隔离级别总称。从弱到强：READ_UNCOMMITTED、READ_COMMITTED、
  REPEATABLE_READ、SNAPSHOT、SERIALIZABLE。H2 默认 READ_COMMITTED，MVStore 模式
  下 SNAPSHOT 性能最佳。
  **章节**：第10章 §10.2
  **相关**：[[Read Committed]]、[[Repeatable Read]]、[[Serializable]]、[[Snapshot Isolation]]

- **写偏斜**: Write Skew，快照隔离的特征异常。两个并发事务读取相同数据并各自写入
  不同行，导致违反全局约束。Snapshot Isolation 不能消除写偏斜，需提升至 Serializable。
  **章节**：第10章 §10.2
  **相关**：[[Snapshot Isolation]]、[[Serializable]]

- **扫描抗性**: Scan Resistance，缓存替换算法的属性。指算法在面对一次性扫描负载时
  保持热数据不被淘汰的能力。LIRS 优于 LRU 的关键差异点。
  **章节**：第6章 §6.5
  **相关**：[[LIRS]]

- **测试框架**: H2 的多层测试体系。`org.h2.test` 包覆盖单元测试（JUnit）、
  集成测试（TestAll 主入口）、性能基准（TestPerformance）、模糊测试（TestRandom*）。
  Maven 通过 `mvn test` 触发标准测试目标。
  **章节**：第11章 §11.3
  **相关**：[[Maven]]、[[ISODEBUG]]、[[MVStoreTool]]

---

*共收录 100+ 条核心术语。每条术语包含详细释义、章节定位与相关术语链接，便于读者从任一入口跳转到完整讨论。术语间的 `[[相关]]` 链接形成知识图谱：术语本身的章节字段标注首次出现的详细章节（§子节级）。*
# 附录 D：概念索引

> 关键概念、API 类名和算法名的章节位置索引。条目按字母顺序排列；中文词条单列于末尾。
> 主条目以 `- 名称 — 章节` 形式；子条目缩进两空格；`see also:` 行列出相关索引项。

## A

- ACID 特性 — §10.5
  - 原子性 — §10.5.1
  - 一致性 — §10.5.2
  - 隔离性 — §10.5.3
  - 持久性 — §10.5.4
  see also: MVCC, Undo Log, Snapshot Isolation
- AbstractAggregate 类 — §7.6
  see also: Aggregate, Expression
- Aggregate（聚合函数）— §7.6, §11.1
  - SUM/COUNT/AVG — §7.6.1
  - DISTINCT 修饰 — §7.6.2
  - 与 Window 函数对比 — §7.6.3
  see also: AbstractAggregate, SelectGroups, Window 函数
- Append-Only 写入 — §9.1, §6.4
  see also: Chunk, Copy-on-Write, Log-Structured Storage
- AtomicReference — §1, §10.4
  see also: CAS, RootReference, Single Writer
- 安全机制 — §12.1
  - SQL 注入防护 — §12.1.5
  - 存储加密 — §12.1.5
  - 传输加密 — §12.1.5
  - 访问控制 — §12.1.5
  see also: XTS-AES, FilePathEncrypt
- 暴力枚举连接 — §6.8, §8.2

## B

- B-Tree 索引 — §6.1
  - 节点分裂 — §6.1.3, §6.7.2
  - 节点合并 — §6.1.4, §6.7.3
  - 范围扫描 — §6.1.5
  - 与 Counted B-Tree 对比 — §9.6.2
  - 与 LSM-Tree 对比 — §1.1
  see also: Counted B-Tree, MVMap, Page 格式, Copy-on-Write
- BackgroundWriter — §9.5
  - autoCommitDelay 参数 — §9.5.1
  - 触发时机 — §9.5.2
  see also: Compact, FileStore, Checkpoint
- Batch 更新 — §7.2
  see also: PreparedStatement
- Bloom 过滤 — §12.1
- Block（4096 字节单元）— §9.6
  see also: Chunk, Free Space, FreeSpaceBitSet
- BTree 类 (`org/h2/mvstore/tx/`) — §4
  see also: TransactionStore
- 表级锁 — §10.1
  see also: Lock, Meta Lock
- 表过滤器 — 见 TableFilter
- 表索引层 — §2.8
  see also: Table, Index

## C

- CAS（Compare-And-Swap）— §1, §10.4
  - 在 RootReference 更新中的使用 — §10.4.2
  - 与自旋退避 — §10.4.3
  see also: AtomicReference, MVCC, Single Writer
- CBO（Cost-Based Optimization）— §8.1
  see also: Optimizer, IndexCondition, JOIN 优化
- Checkpoint — §9.5
  see also: BackgroundWriter, FileStore, File Header
- Chunk 文件格式 — §9.3, §9.6
  - Header 布局 — §9.6.1
  - Page 区编码 — §9.6.2
  - Footer 与 checksum — §9.6.3
  see also: Block, Page, Page Pointer
- Chunk 压缩整理 — §6.4, §9.5
  see also: Compact, Free Space, 写放大
- Column 类 — §3.6
  see also: Value, Table
- Command 层 — §2.4, §4.1
  - Command Pattern — §4.1.1
  - 生命周期 — §4.1.2
  see also: CommandContainer, Prepared, Parser
- CommandContainer — §7.4
  see also: Prepared / PreparedStatement, Parser, SmallLRUCache
- COMMIT 流程 — §5.5
  - 阶段：扫描 Undo Log — §5.5.2
  - 阶段：原子状态切换 — §5.5.3
  see also: CommitDecisionMaker, TransactionStore, Undo Log
- CommitDecisionMaker — §5.5
  see also: RollbackDecisionMaker, TransactionStore, VersionedValue
- COMPACT 流程 — §5.8
  see also: Compact, Chunk, Free Space
- Compact（紧凑化）— §6.4, §9.5
  - 触发阈值 — §6.4.3
  - 重写过程 — §6.4.4
  see also: Chunk, Compact, Free Space, 写放大
- ConnectionInfo 类 — §2.2
  see also: JDBC, Driver, Database
- Copy-on-Write 版本管理 — §6.2
  - 节点复制规则 — §6.2.2
  - 路径递归更新 — §6.2.3
  - 与 MVCC 联动 — §6.3
  see also: B-Tree, MVCC, RootReference, Append-Only
- Counted B-Tree — §9.6
  - totalCount 字段 — §9.6.4
  - COUNT(*) 优化 — §9.6.5
  see also: B-Tree, Page
- 测试框架 — §11.3
  see also: Maven, ISODEBUG, MVStoreTool
- 词法分析器 — 见 Tokenizer
- 存储引擎 — §1.1, §2.9
  see also: MVStore, PageStore, FileStore

## D

- Database 类 — §2.3, §3.3
  - openDatabase 入口 — §2.3.1
  - 全局状态管理 — §3.3.2
  see also: Engine, Session, SchemaObject, DbSettings
- DbSettings — §3.3
  see also: Database, ConnectionInfo
- DDL（数据定义）— §5
  see also: Meta Lock, SchemaObject
- Deadlock（死锁）— §10.3
  - 检测算法（等待图）— §10.3.2
  - 锁超时 — §10.3.3
  - 牺牲者选择 — §10.3.4
  see also: Lock, Meta Lock, LOCK_TIMEOUT
- DELETE 流程 — §5.4, §7.2
  see also: DML, Undo Log, MVCC
- DML（数据操作）— §5, §7
  see also: DDL, CommandContainer
- Driver 类 — §2.2, §3.2
  see also: JDBC, JdbcConnection, ConnectionInfo
- 笛卡尔积消除 — §8.3
- 调试技巧 — §11.3
  see also: ISODEBUG, 测试框架
- 单写入者 — 见 Single Writer
- 动手练习 — §12.4
- 多版本并发控制 — 见 MVCC

## E

- Engine 类 — §2.3, §3.3
  see also: Database, ConnectionInfo
- Expression 层 — §2.3, §4.2
  - 继承体系 — §4.2.1
  - getValue 接口 — §4.2.2
  - 表达式即执行计划 — §6.10.4
  see also: Aggregate, Window 函数, Parser

## F

- File Header 格式 — §9.3, §9.6
  - 双重备份策略 — §9.3.2
  - 关键字段 — §9.6.1
  see also: FileStore, Recover, Chunk
- FilePath 抽象 — §3.8
  see also: FilePathDisk, FilePathEncrypt, FilePathNioMapped
- FilePathDisk 类 — §2.10
- FilePathEncrypt 类 — §2.10, §9.8
  see also: XTS-AES 加密
- FilePathNioMapped 类 — §2.10
- FileStore 类 — §2.9, §9.1
  see also: FilePath, Chunk, BackgroundWriter
- Fletcher-32 Checksum — §9.3, §9.6
  see also: Chunk, Recover
- Free Space 管理 — §6.6
  see also: FreeSpaceBitSet, Compact, Block
- FreeSpaceBitSet — §5.7, §6.6
  see also: Free Space, Block
- 分页缓存 — 见 LIRS
- 复制-on-Write — 见 Copy-on-Write

## G

- Genetic Algorithm（遗传算法）— §6.8, §8.2
  - 染色体编码 — §8.2.3
  - 交叉与变异 — §8.2.4
  see also: Optimizer, Hybrid Strategy
- 共享锁 — §10.1
  see also: Lock, 排他锁
- 隔离级别对比 — §6.3, §10.2
  see also: Read Committed, Repeatable Read, Snapshot Isolation, Serializable
- 隔离级别 — 见 隔离级别对比

## H

- H2 发展历史 — §1.1
- H2 核心特性 — §1.1
- H2 与其他数据库对比 — §12.2
  - vs SQLite — §12.2.1
  - vs Derby — §12.2.2
  - vs HSQLDB — §12.2.3
- HASH 索引 — §2.8
  see also: Index, B-Tree
- Hybrid Strategy — §8.2
  see also: Genetic Algorithm, Optimizer, CBO
- 后台写入线程 — §9.5
  see also: BackgroundWriter, Compact
- 恢复机制 — §9.7
  see also: Recover, File Header, Chunk
- 滑动窗口 — 见 Window 函数

## I

- Index 层 — §2.8
  see also: B-Tree, HASH 索引, R-Tree
- IndexCondition — §4.4, §8.4
  - EQUALITY/RANGE/SPATIAL 三类 — §8.4.2
  see also: Index, Optimizer, Expression
- INSERT 流程 — §5.2, §7.2
  see also: DML, MVCC, Undo Log
- IOT（索引组织表）— §3
  see also: B-Tree, MVTable
- ISODEBUG — §11.3
  see also: 测试框架
- 一致性快照 — 见 Snapshot Isolation
- 引用计数 — §6.5

## J

- JDBC 接入层 — §2.1, §3.2
  - Driver 注册 — §3.2.1
  - Connection 生命周期 — §3.2.2
  see also: JdbcConnection, Driver, Session
- JdbcConnection 类 — §3.2
  see also: JDBC, Session
- JOIN 优化 — §8.2, §8.3
  - 连接顺序选择 — §8.2
  - 谓词下推 — §8.3
  - 子查询展开 — §8.3
  see also: Genetic Algorithm, Hybrid Strategy
- JSON 数据类型 — §1.1
  see also: Value
- 架构设计权衡 — §12.1
- 检查点 — 见 Checkpoint
- 聚合函数 — 见 Aggregate
- 基于代价优化 — 见 CBO
- 接入层 — §2.1
  see also: JDBC, Server, SocketConnect

## K

- 快照隔离 — §6.3, §10.2, §10.4
  - 读写规则 — §10.2.3
  - first-committer-wins — §10.4.5
  - 写偏斜异常 — §10.2.4
  see also: MVCC, VersionedValue, Serializable, 写偏斜
- 空间查询遍历 — §6.9
  see also: R-Tree 空间索引
- 空间索引 — 见 R-Tree

## L

- LIRS 缓存替换 — §6.5
  - 热/冷队列 — §6.5.2
  - 扫描抗性 — §6.5.4
  - 与 LRU 对比 — §6.5.5
  see also: SmallLRUCache, 扫描抗性
- LOB 处理 — §7.2
  see also: Value
- LOCK_TIMEOUT — §10.3
  see also: Deadlock, Lock
- Lock 类 — §10.1, §10.2
  - Shared/Exclusive — §10.1.2
  - 锁等待 — §10.1.3
  see also: Meta Lock, Deadlock
- Log-Structured Storage — §9.1
  see also: Append-Only, LSM-Tree, MVStore
- LSM-Tree — §1.1, §9.1
  see also: Log-Structured Storage, Compact
- 连接顺序优化 — §8.2
  see also: Genetic Algorithm, Hybrid Strategy
- 列对象 — 见 Column

## M

- Maven 构建 — §11.3
  see also: 测试框架
- Meta Lock（元数据锁）— §4.1, §10.1
  see also: Lock, DDL, Database
- Mode（SQL 兼容模式）— §3.6
  - Oracle 模式 — §3.6.2
  - MySQL 模式 — §3.6.3
  - PostgreSQL 模式 — §3.6.4
  see also: Parser, Database
- MVCC（多版本并发控制）— §6.3, §10.4
  - 无锁读取 — §10.4.2
  - 写冲突检测 — §10.4.4
  - 与 COW 联动 — §6.3.3
  see also: Snapshot Isolation, VersionedValue, TxDecisionMaker, RootReference
- MVMap 类 — §4.6, §9.2
  - 快照读 — §9.2.3
  - 范围扫描 — §9.2.4
  - operate 接口 — §9.2.5
  see also: MVStore, B-Tree, Page
- MVStore 架构 — §4.6, §9.1
  - 启动流程 — §9.1.2
  - 关闭流程 — §9.1.3
  - 与 PageStore 对比 — §1.1
  see also: MVMap, FileStore, Chunk
- MVStore 文件格式 — §9.6
  see also: File Header, Chunk, Page Pointer
- MVStore 平衡 — §6.7
  see also: B-Tree, PageSplit
- MVStoreTool — §11.3
  see also: 测试框架, Recover
- MVTable — §3
  see also: Table, MVMap, IOT
- Merge 类 — §11.1
  see also: Query
- 命令层 — 见 Command 层
- 命令容器 — 见 CommandContainer

## N

- NIO 内存映射 — §2.10
  see also: FilePathNioMapped

## O

- Optimizer 查询优化 — §8.1
  - canStop 终止条件 — §8.1.3
  - 代价模型 — §8.3
  see also: CBO, Hybrid Strategy, IndexCondition
- 外连接优化 — §8.3

## P

- Page 格式 — §9.6
  - 内部节点编码 — §9.6.2
  - 叶节点编码 — §9.6.3
  - VarInt 紧凑编码 — §9.6.6
  see also: B-Tree, Chunk, VarInt
- Page Pointer 编码 — §9.6
  - 64-bit 字段拆分 — §9.6.4
  - chunkId/offset/length — §9.6.4
  see also: Chunk, Page
- PageRef — §9.2
  see also: Page, LIRS
- PageSplit（页面分裂）— §6.1, §6.7
  see also: B-Tree, Copy-on-Write
- PageStore 存储引擎 — §1.1
  see also: MVStore
- Parser 递归下降解析 — §6.10, §8.2
  - parseSelect — §6.10.3
  - parseExpression — §6.10.4
  - 错误恢复 — §6.10.5
  see also: Tokenizer, Recursive Descent Parser
- Prepared / PreparedStatement — §7.1, §7.4
  - 编译缓存 — §7.4.2
  - 参数绑定 — §7.4.3
  see also: CommandContainer, SmallLRUCache
- 排他锁 — §10.1
  see also: Lock, 共享锁
- 谓词下推 — §8.3
  see also: TableFilter, IndexCondition

## Q

- Query 类 — §11.1
  see also: Select, Optimizer
- 嵌入式/服务器模式 — §1.2
  see also: Session 类, TcpServer
- 全链路追踪 — §7.5
- 全局优化 — 见 Optimizer

## R

- R-Tree 空间索引 — §6.9
  - MBR（最小外包矩形）— §6.9.2
  - 空间分裂 — §6.9.3
  see also: Index 层, R-Tree
- READ 流程 — §5.9
  see also: SELECT 流程, MVCC
- Read Committed — §10.2
  see also: 隔离级别对比
- Recover 工具 — §9.7
  see also: 恢复机制, File Header
- Recursive Descent Parser — §6.10, §8.2
  see also: Parser, Tokenizer
- Repeatable Read — §10.2
  see also: 隔离级别对比, MVCC
- ROLLBACK 流程 — §5.6
  see also: RollbackDecisionMaker, Undo Log
- RollbackDecisionMaker — §5.6
  see also: CommitDecisionMaker, Undo Log
- RootReference — §9.2, §10.4
  - CAS 更新 — §10.4.2
  - 版本快照 — §9.2.6
  see also: CAS, MVCC, Single Writer
- 容错机制 — §12.1
- 阅读路线 — §11.2
- 阅读工具 — §12.4

## S

- Savepoint — §5.5
  see also: Transaction, Undo Log
- SchemaObject — §3.3
  see also: Database, Table
- SELECT 流程 — §5.1, §7.1
  - JDBC 入口 — §7.1.1
  - 解析阶段 — §7.2
  - 优化阶段 — §8
  - 执行阶段 — §7.5
  see also: Select, Query, Parser, Optimizer
- Select 类 — §7.1, §11.1
  see also: Query, TableFilter
- SelectGroups — §7.6
  see also: Aggregate, Window 函数
- Serializable — §10.2
  see also: 隔离级别对比, Snapshot Isolation
- Server 层 — §2.1, §3.9
  see also: TcpServer, Session 类
- Session 类 — §2.3
  - SessionLocal（嵌入式）— §2.3.2
  - SessionRemote（远程）— §2.3.3
  see also: Database, JdbcConnection, Lock
- Single Writer 模型 — §10.4, §12.1
  see also: CAS, RootReference, MVCC
- SmallLRUCache — §11.1
  see also: LIRS, Prepared
- Snapshot Isolation — §10.2, §10.4
  see also: 快照隔离, MVCC, 写偏斜
- SocketConnect — §2.2
  see also: Session 类, Server 层
- SQL 执行链路 — §7
  see also: SELECT 流程, Parser, Optimizer
- 死锁检测 — §4.6, §10.3
  see also: Deadlock, LOCK_TIMEOUT
- 扫描抗性 — §6.5
  see also: LIRS
- 树分裂与合并 — §6.7
  see also: PageSplit, B-Tree
- 锁超时 — §10.3
  see also: Deadlock, LOCK_TIMEOUT
- 数据流图 — §1.2
- 视图 — §3.3

## T

- Table 层 — §2.8, §4.4
  see also: Index, MVTable
- TableFilter — §3.6, §8.5
  see also: Select, IndexCondition
- TableIndex 层 — §2.8
- TcpServer — §3.9
  see also: Server 层, Session 类
- Tokenizer 类 — §3.4, §6.10
  see also: Parser, Recursive Descent Parser
- TransactionMap — §10.4, §12.1
  see also: MVMap, VersionedValue, Snapshot Isolation
- TransactionStore — §4.5, §10.4
  see also: Transaction, Undo Log, CommitDecisionMaker
- Transaction 概念 — §5.5
  see also: ACID, TransactionStore
- TxDecisionMaker — §10.4
  see also: MVCC, VersionedValue
- 事务隔离级别 — §10.2
  see also: 隔离级别对比
- 提交决策器 — 见 CommitDecisionMaker

## U

- Undo Log — §5.5, §5.6
  - 结构 — §5.5.2
  - 提交时清理 — §5.5.4
  - 回滚时回放 — §5.6.2
  see also: TransactionStore, CommitDecisionMaker, RollbackDecisionMaker
- UPDATE 流程 — §5.3, §7.2
  see also: DML, MVCC

## V

- Value 类型系统 — §3.10
  - ValueInteger / ValueVarchar / ValueNumeric — §3.10.2
  - 比较与转换 — §3.10.3
  see also: Column
- VarInt 编码 — §9.6
  see also: Page, Chunk
- VersionedBitSet — §10.4
  see also: VersionedValue, TransactionStore
- VersionedValue — §4.5, §10.4
  - committed 版本 — §10.4.3
  - uncommitted 版本 — §10.4.4
  see also: MVCC, TransactionStore
- 谓词下推 — 见 Q 区
- 文件存储 — 见 FileStore
- 文件格式 — 见 MVStore 文件格式
- 文件系统抽象 — §3.8
  see also: FilePath

## W

- WAL（预写日志）— §9.1
  - H2 不使用显式 WAL 的原因 — §9.1.4
  see also: Append-Only, Chunk, Log-Structured Storage
- Window 函数 — §7.6, §11.1
  - ROW_NUMBER / RANK — §7.6.4
  - LEAD/LAG — §7.6.5
  see also: Aggregate, SelectGroups
- 谓词下推 — §8.3
- 文件系统抽象（FilePath）— §3.8
- 无锁读 — §10.4
  see also: CAS, MVCC, Single Writer

## X

- XTS-AES 加密 — §9.8
  see also: FilePathEncrypt
- 写冲突检测 — §6.3, §10.2, §10.4
  see also: TxDecisionMaker, Snapshot Isolation
- 写放大 — §12.1
  see also: Compact
- 写偏斜 — §10.2
  see also: Snapshot Isolation, Serializable
- 行级锁 — §10.2
  see also: MVCC

## Y

- 压缩流水线 — §9.8
  see also: XTS-AES 加密
- 页面分裂 — §6.1, §6.7
  see also: PageSplit, B-Tree
- 页面指针 — 见 Page Pointer
- 源码学习价值 — §12.3
- 遗传算法 — §6.8, §8.2
  see also: Genetic Algorithm
- 优化器 — 见 Optimizer

## Z

- 脏页收集 — §9.5
  see also: BackgroundWriter
- 执行计划 — §8.2
  - 表达式即执行计划 — §6.10.4
  see also: Expression, Optimizer
- 子查询优化 — §8.3
  see also: JOIN 优化
- 紧凑化 — 见 Compact
- 字典归并 — §8.3
- 主键与索引 — §2.8
  see also: B-Tree, Index, IOT

## 数字

- 八层架构 — §1.2, §2
  see also: 五层模型
- 五层模型 — §1.2
  see also: 八层架构

## 附录

- 端到端 SELECT 案例 — 附录 A.1
  - JDBC → SessionLocal 入口 — 附录 A.1.1
  - Parser 词法切分与递归下降 — 附录 A.1.2
  - Optimizer 代价矩阵选择 — 附录 A.1.4
  - B-Tree 路径下降与 Page Pointer — 附录 A.1.6
  - LIRS 缓存命中模式 — 附录 A.1.7
  see also: SELECT 流程, Parser 递归下降解析, Optimizer 查询优化, LIRS 缓存替换
- 端到端 COMMIT 案例 — 附录 A.2
  - INSERT/UPDATE Undo Log 累积 — 附录 A.2.2
  - TxDecisionMaker 写冲突 — 附录 A.2.3
  - CommitDecisionMaker Undo Log 翻转 — 附录 A.2.5
  - RootReference CAS 提交点 — 附录 A.2.6
  - BackgroundWriter 后台落盘 — 附录 A.2.7
  see also: TransactionStore, COMMIT 流程, MVCC, 快照隔离
- 端到端崩溃恢复案例 — 附录 A.3
  - File Header 双副本仲裁 — 附录 A.3.3
  - Chunk Footer Fletcher-32 校验 — 附录 A.3.5
  - layoutMap 驱动的 root 回填 — 附录 A.3.6
  - 未完成事务回滚 — 附录 A.3.7
  - Chunk 校验失败异常分支 — 附录 A.3.5
  see also: Recover 工具, File Header 格式, Chunk 文件格式, RollbackDecisionMaker
- 案例研究方法论 — 附录 A
  see also: 端到端 SELECT 案例, 端到端 COMMIT 案例, 端到端崩溃恢复案例
- ASCII 序列图全链路视图 — 附录 A.1
  see also: 全链路追踪
- 源码版本变更说明 — 附录 B
  - MVStore 核心层变更（panicException、closeStore、tryLock CPU 退避、FileStore 流水线）— 附录 B.1
  - 事务子系统变更（TransactionStore 状态机、CommitDecisionMaker、VersionedBitSet、VersionedValue 序列化）— 附录 B.2
  see also: MVStore, TransactionStore, MVCC

---

*共收录 300+ 条索引（含主条目与子条目）。每个主条目指向首次出现或最相关的章节；子条目对主题做更细粒度的章节分布；`see also` 行连接概念上相关的索引项，便于读者跨章探索。*
# 附录 E：参考文献

> 本书在分析和撰写过程中参考的官方文档、学术论文和技术资料。分类整理如下。

---

## H2 官方文档

H2 Database 官方文档是本书最主要的参考来源。以下文档随 H2 源码提供，位于 `h2/src/docsrc/html/` 目录：

1. **《Architecture》** (`architecture.html`)
   H2 整体架构的分层描述，包含 JDBC 驱动、引擎层、存储层等核心组件的设计说明。

2. **《MVStore》** (`mvstore.html`)
   MVStore 存储引擎的完整文档，包括文件格式（file header/chunk/page 三级布局）、事务机制、缓存策略和性能调优。

3. **《Advanced》** (`advanced.html`)
   高级特性文档，涵盖事务隔离级别、MVCC 行为、ACID 保证、SQL 注入防护、远程访问安全、锁超时等。

4. **《Features》** (`features.html`)
   特性清单，包含连接模式、SQL 支持、集群模式和功能完整特性列表。

5. **《Performance》** (`performance.html`)
   性能基准测试结果（H2 vs HSQLDB/Derby/PostgreSQL/MySQL），以及数据库性能调优指南和内置分析器使用说明。

6. **《Security》** (`security.html`)
   安全特性文档，包括存储加密、传输加密、访问控制和类加载限制。

7. **《Tutorial》** (`tutorial.html`)
   H2 使用教程，包含命令行工具说明、嵌入式和客户端-服务器模式的快速入门指南。

## 学术论文

8. **Bayer, R. & McCreight, E. (1972).** *Organization and Maintenance of Large Ordered Indexes.* Acta Informatica, 1(3), 173-189.
   B-Tree 的原始论文，提出了平衡多路查找树的数据结构和维护算法。

9. **Jiang, S. & Zhang, X. (2002).** *LIRS: An Efficient Low Inter-reference Recency Set Replacement Policy to Improve Buffer Cache Performance.* ACM SIGMETRICS.
   LIRS 缓存替换算法的原始论文，提出了基于 IRR（Inter-Reference Recency）的缓存替换策略。

10. **Guttman, A. (1984).** *R-Trees: A Dynamic Index Structure for Spatial Searching.* ACM SIGMOD.
    R-Tree 空间索引的原始论文。

11. **Bernstein, P. A., Hadzilacos, V. & Goodman, N. (1987).** *Concurrency Control and Recovery in Database Systems.* Addison-Wesley.
    数据库并发控制和恢复的经典参考书，涉及 MVCC、锁协议和恢复算法。

12. **Gray, J. & Reuter, A. (1993).** *Transaction Processing: Concepts and Techniques.* Morgan Kaufmann.
    事务处理的权威著作，涵盖 ACID 特性、隔离级别和恢复机制的完整理论。

13. **Codd, E. F. (1970).** *A Relational Model of Data for Large Shared Data Banks.* Communications of the ACM, 13(6), 377-387.
    关系模型的奠基性论文。

## 技术参考

14. **Oracle Corporation. (2024).** *Java Platform, Standard Edition API Specification.*
    Java 标准库 API 文档，涉及 `java.nio.channels.FileChannel`、`java.sql` 等核心接口。

15. **ISO/IEC 9075:2023.** *Information technology — Database languages — SQL.*
    SQL 标准，H2 实现了 SQL'99+ 的大部分特性。

## 对比数据库文档

16. **SQLite Consortium. (2024).** *SQLite Documentation.* https://www.sqlite.org/docs.html
17. **Apache Software Foundation. (2024).** *Apache Derby Documentation.* https://db.apache.org/derby/docs/
18. **The HSQL Development Group. (2024).** *HSQLDB Documentation.* https://hsqldb.org/doc/
19. **PostgreSQL Global Development Group. (2024).** *PostgreSQL Documentation.* https://www.postgresql.org/docs/
20. **Oracle Corporation. (2024).** *MySQL Documentation.* https://dev.mysql.com/doc/

---

*共收录 20 条参考文献。编号采用 [作者, 年份] 格式标识学术论文，H2 官方文档以《标题》格式引用，技术参考和对比数据库文档以组织名和年份标识。*
