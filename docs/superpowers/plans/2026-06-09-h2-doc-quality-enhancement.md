# H2 源码分析文档质量提升计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 借鉴 H2 官方文档（`h2/src/docsrc/html/`）的权威素材，将现有 12 章 35,339 行中文源码分析文档提升至高质量中文技术书籍标准。

**架构:** 四阶段增量式质量提升：(1) 官方文档交叉引用体系构建，(2) ACID/安全/性能基准等缺失内容增补，(3) MVStore 文件格式深度增强，(4) 术语对齐与全书通读润色。每阶段产出独立的源章节变更，通过标准验证流程（`cover_stats.py → rebuild_merged.py → generate_html.py → _audit_smart.py → final_check.py`）逐阶段验证。

**策略说明:** 本计划的改动涵盖三类变更：
- **A 类 — 官方引用标注（Task 1）**：纯 markup 插入，每处改动独立且可逆，不影响内容完整性。`final_check.py` 全部通过后进入下一项。
- **B 类 — 内容增补（Task 2-5）**：在现有章节中插入新小节或补充段落。每节完成后立即运行验证流程，确保无围栏断裂或格式漂移。
- **C 类 — 术语/格式对齐（Task 6-7）**：全局搜索替换 + 人工审读，影响面最广，放在最后。

执行顺序：A → B → C，每完成一个 A/B 类子任务（即每修改一个章节文件）后运行标准验证流程。

**Tech Stack:** Python 3 (验证工具), Markdown, HTML, git

---

## 文件映射

| 文件 | 职责 | 对应官方文档素材 |
|------|------|-----------------|
| `docs-stm/ch1-2-architecture.md` | 第1-2章：总体架构 + 分层模块 | `architecture.html`, `features.html#connection_modes` |
| `docs-stm/ch3-packages.md` | 第3章：核心包结构 | `architecture.html#jdbc` 等 |
| `docs-stm/ch4-5-modules-processes.md` | 第4-5章：模块 + 流程 | `advanced.html#transaction_isolation`, `advanced.html#mvcc` |
| `docs-stm/ch6-1-data-structures.md` | 第6章算法：B-Tree, COW, MVCC | 无直接对应（源码分析独有），可引用 `mvstore.html#versions` |
| `docs-stm/ch6-2-storage-algorithms.md` | 第6章算法：Chunk, LIRS, FreeSpace, 平衡 | `mvstore.html#logStructured`, `mvstore.html#caching` |
| `docs-stm/ch6-3-query-algorithms.md` | 第6章算法：Optimizer, R-Tree, Parser | `mvstore.html#r_tree`, `performance.html#explain_plan` |
| `docs-stm/ch7-8-sql-optimizer.md` | 第7-8章：SQL 执行 + 优化器 | `advanced.html#result_sets`, `advanced.html#large_objects`, `performance.html#database_performance_tuning` |
| `docs-stm/ch9-10-persistence-locking.md` | 第9-10章：持久化 + 锁 | `mvstore.html#fileFormat`, `mvstore.html#fileFormat(Page Format)`, `advanced.html#acid`, `advanced.html#durability_problems` |
| `docs-stm/ch11-12-guide-summary.md` | 第11-12章：导读 + 总结 | `features.html#feature_list`, `tutorial.html`, `security.html` |

---

## 验证流程

每项任务完成后在项目根目录运行：

```bash
python docs-stm/tools/cover_stats.py
python docs-stm/tools/rebuild_merged.py
python docs-stm/tools/generate_html.py
python docs-stm/tools/_audit_smart.py
python docs-stm/tools/final_check.py
```

预期：`final_check.py` 全部通过（当前基线 55/55）。

---

### Task 1: 建立官方文档交叉引用体系（A 类）

**文件:** `docs-stm/ch1-2-architecture.md`, `docs-stm/ch3-packages.md`, `docs-stm/ch4-5-modules-processes.md`
`docs-stm/ch6-1-data-structures.md`, `docs-stm/ch6-2-storage-algorithms.md`, `docs-stm/ch6-3-query-algorithms.md`
`docs-stm/ch7-8-sql-optimizer.md`, `docs-stm/ch9-10-persistence-locking.md`, `docs-stm/ch11-12-guide-summary.md`

**说明:** 在全书关键论述处插入标准化的"参见官方文档"引用块。引用格式统一为：

```markdown
> **参考**: H2 官方文档《Document Title》(`h2/src/docsrc/html/page.html#section_id`)
> 描述了该机制的更多细节和配置选项。
```

每处引用只添加 1-3 行，不改变原文内容。

- [ ] **Step 1.1: ch1-2 架构章节引用的官方文档**

  在 `ch1-2-architecture.md` 插入以下 4 处引用：

  1. 在 **1.1 H2 Database 概述** 的部署模式对比处（图 1-3 之后）插入：
  ```
  > **参考**: H2 官方文档《Features》(`h2/src/docsrc/html/features.html#connection_modes`)
  > 详细说明了三种连接模式的 URL 格式、参数配置和适用场景。
  ```

  2. 在 **1.2.3 五层映射到八层** 之后插入：
  ```
  > **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#top_down`)
  > 从 JDBC 驱动到底层文件系统的分层概述与本文的五层/八层模型对照阅读。
  ```

  3. 在 **2.2 接入层（JDBC + Server）** 的 JDBC 部分插入：
  ```
  > **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#jdbc`)
  > 简要说明了 JDBC 驱动实现所在的包：`org.h2.jdbc`, `org.h2.jdbcx`。
  ```

  4. 在 **2.3 引擎层** 的 Database/Session 描述处插入：
  ```
  > **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#connection`)
  > 列出了 Session 相关的核心类及其职责。
  ```

- [ ] **Step 1.2: ch3 包结构章节引用的官方文档**

  在 `ch3-packages.md` 插入以下 3 处引用：

  1. 在 **3.2 JDBC 层** 小节开头插入：
  ```
  > **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#jdbc`)
  > 官方文档将 JDBC 驱动描述为整个架构的最上层入口。
  ```

  2. 在 **3.5 Command 层** 的 Parser 描述处插入：
  ```
  > **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#command`)
  > 官方说明：Parser 直接生成命令执行对象（无中间 IR），然后在命令上运行优化步骤。
  ```

  3. 在 **3.6 Table/Index 层** 的描述后插入：
  ```
  > **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#table`)
  > 指出 H2 将索引作为一种特殊的表来存储，Table 和 Index 在同一抽象层次。
  ```

- [ ] **Step 1.3: ch4-5 模块与流程章节引用的官方文档**

  在 `ch4-5-modules-processes.md` 插入以下 3 处引用：

  1. 在 **4.5 TransactionStore** 的事务隔离描述处插入：
  ```
  > **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#transaction_isolation`)
  > 详细列出了 H2 支持的 5 种隔离级别及其对应的 SQL 语句。
  ```

  2. 在 **4.5 TransactionStore** 的 MVCC 描述处插入：
  ```
  > **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#mvcc`)
  > 描述了 MVCC 模式下插入/更新操作只使用共享锁，仅 DDL 使用排他锁的行为。
  ```

  3. 在 **5.5 事务提交/回滚流程** 的小结后插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#transactions`)
  > 描述了 TransactionStore 的事务机制：使用单独 map 存储旧版本，支持 savepoint 和两阶段提交。
  ```

- [ ] **Step 1.4: ch6 算法章节引用的官方文档**

  在 `ch6-1-data-structures.md`, `ch6-2-storage-algorithms.md`, `ch6-3-query-algorithms.md` 插入引用：

  1. `ch6-1-data-structures.md` 在 **6.2 Copy-on-Write 版本管理** 小节开头插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#versions`)
  > 官方将版本描述为"所有 map 在特定时间点的快照"，COW 确保只有变更页被复制。
  ```

  2. `ch6-2-storage-algorithms.md` 在 **6.4 Chunk 压缩整理** 的概述处插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#logStructured`)
  > 描述了 Log Structured 存储的设计动机：小随机写入合并为大连续写操作。
  ```

  3. `ch6-2-storage-algorithms.md` 在 **6.5 LIRS 缓存替换** 小节开头插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#caching`)
  > 指出 LIRS 缓存在 page 级别工作，且能抵抗扫描操作对缓存的污染。
  ```

  4. `ch6-3-query-algorithms.md` 在 **6.9 空间索引 (R-Tree)** 小节开头插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#r_tree`)
  > 提供了 MVRTreeMap 的完整使用示例代码，包括空间键的添加和相交查询。
  ```

- [ ] **Step 1.5: ch7-8 SQL 与优化器章节引用的官方文档**

  在 `ch7-8-sql-optimizer.md` 插入以下 3 处引用：

  1. 在 **7.1 SELECT 执行流程** 的结果集处理处插入：
  ```
  > **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#result_sets`)
  > 列出了所有返回结果集的语句类型以及大结果集的外部排序机制。
  ```

  2. 在 **7.2 INSERT/UPDATE/DELETE 执行流程** 的 LOB 处理处插入：
  ```
  > **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#large_objects`)
  > 说明了 CLOB/BLOB 的存储策略和 `MAX_LENGTH_INPLACE_LOB` 阈值配置。
  ```

  3. 在 **8.4 执行计划分析** 小节末尾插入：
  ```
  > **参考**: H2 官方文档《Performance》(`h2/src/docsrc/html/performance.html#explain_plan`)
  > 描述了如何使用 EXPLAIN PLAN 分析查询执行计划并进行调优。
  ```

- [ ] **Step 1.6: ch9-10 持久化与锁章节引用的官方文档**

  在 `ch9-10-persistence-locking.md` 插入以下 5 处引用：

  1. 在 **9.1 MVStore 总体架构** 的概述处插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#overview`)
  > 官方概述指出 MVStore 是"持久化、日志结构的键值存储"，支持并发读写和事务。
  ```

  2. 在 **9.3 Chunk 文件布局** 的 Chunk 格式描述处插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
  > 详细说明了 file header 双副本设计、chunk 的 header/footer 字段定义和 checksum 机制。
  ```

  3. 在 **9.3 Chunk 文件布局** 的 Page 序列化处插入：
  ```
  > **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
  > 详细说明了 page 的二进制格式：length、checksum、mapId、keys/values 数组以及 64-bit page pointer 编码。
  ```

  4. 在 **10.3 锁实现细节** 的锁超时描述处插入：
  ```
  > **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#transaction_isolation`)
  > 说明了锁超时的行为：连接等待锁超时后抛出锁超时异常。
  ```

  5. 在 **第10章末尾（全章总结前）** 插入 ACID 引用：
  ```
  > **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#acid`)
  > 讨论了 H2 对 ACID 四个特性的支持程度，以及持久性方面的已知限制。
  ```

- [ ] **Step 1.7: ch11-12 导读与总结章节引用的官方文档**

  在 `ch11-12-guide-summary.md` 插入以下 2 处引用：

  1. 在 **11.2 调试环境搭建** 的工具列表处插入：
  ```
  > **参考**: H2 官方文档《Tutorial》(`h2/src/docsrc/html/tutorial.html#command_line_tools`)
  > 列出了 H2 提供的全部命令行工具及其用途。
  ```

  2. 在 **第12章 总结** 的特性回顾处插入：
  ```
  > **参考**: H2 官方文档《Features》(`h2/src/docsrc/html/features.html#feature_list`)
  > 官方完整特性列表，可与本书分析内容对照阅读。
  ```

- [ ] **Step 1.8: 运行标准验证流程确认无回归**

  ```bash
  cd /path/to/repo/root
  python docs-stm/tools/cover_stats.py
  python docs-stm/tools/rebuild_merged.py
  python docs-stm/tools/generate_html.py
  python docs-stm/tools/_audit_smart.py
  python docs-stm/tools/final_check.py
  ```
  预期：`final_check.py` 全部通过（55/55），无围栏断裂、无 TOC 断链。

- [ ] **Step 1.9: 提交 Task 1**

  ```bash
  git add docs-stm/
  git commit -m "docs: 建立官方文档交叉引用体系

  在全书 8 个章节的关键论述处插入标准化"参考"引用块，
  引用 h2/src/docsrc/html/ 下的 architecture.html、mvstore.html、
  advanced.html、features.html、performance.html、tutorial.html 等官方文档。
  引用格式统一，不改变原文内容，final_check 55/55 通过。"
  ```

---

### Task 2: 增补 ACID 特性讨论（B 类）

**文件:** `docs-stm/ch9-10-persistence-locking.md`

**说明:** 在第10章末尾、总结之前，增补一个独立小节，引用官方 `advanced.html#acid` 和 `advanced.html#durability_problems`，分析 H2 对 ACID 四个特性的支持程度。这是当前文档最明显的缺失之一。

- [ ] **Step 2.1: 在 ch9-10 末尾新增 10.5 节「ACID 特性与持久性讨论」**

  在 `ch9-10-persistence-locking.md` 末尾（最后一个 H2 节之后、章末总结之前）插入：

```markdown
## 10.5 ACID 特性与持久性讨论

ACID（Atomicity、Consistency、Isolation、Durability）是关系数据库事务的核心保证。
H2 官方文档在《Advanced》一章中专门讨论了 ACID 的支持范围（详见官方文档 `advanced.html#acid`）。
本章前几节已从源码层面分析了 H2 的事务、锁和持久化机制，本节从 ACID 视角进行归纳。

**图 10-18: H2 ACID 特性支持矩阵**

```text
┌─────────────────┬──────────┬─────────────────────────────────────────────────┐
│    ACID 特性     │ H2 支持  │  实现机制                                          │
├─────────────────┼──────────┼─────────────────────────────────────────────────┤
│  Atomicity      │    ✅    │ MVStore 的原子 chunk 写入 + Undo Log 回滚           │
│  原子性          │          │ commit() 要么全部写入成功，要么回滚到上一个版本        │
├─────────────────┼──────────┼─────────────────────────────────────────────────┤
│  Consistency    │    ✅    │ 约束检查（FOREIGN KEY、CHECK、NOT NULL）           │
│  一致性          │          │ MVStore 版本链确保读取到的总是一致快照               │
├─────────────────┼──────────┼─────────────────────────────────────────────────┤
│  Isolation      │    ⚠️    │ 默认 READ COMMITTED（详见 10.2 节）               │
│  隔离性          │          │ 支持 READ UNCOMMITTED / REPEATABLE READ /         │
│                  │          │ SNAPSHOT / SERIALIZABLE 四种额外级别               │
├─────────────────┼──────────┼─────────────────────────────────────────────────┤
│  Durability     │    ⚠️    │ Chunk 写入后更新 file header 双副本               │
│  持久性          │          │ ⚠️ 官方明确：不保证电源故障下的完全持久性            │
└─────────────────┴──────────┴─────────────────────────────────────────────────┘
```

**原子性（Atomicity）：** MVStore 的 commit 操作是一次原子写入：所有变更页序列化到一个 chunk 中，最后更新 file header。如果写入过程中 JVM 崩溃，file header 仍然指向旧版本，未完成的 chunk 被丢弃。Undo Log（详见第5章第5.5节）保证了单个事务内部的可回滚性。

**一致性（Consistency）：** H2 在执行 DML 时检查所有约束条件（FOREIGN KEY、CHECK、NOT NULL 等）。MVStore 的版本机制确保任何读取操作看到的都是一致的 B-Tree 快照。即使发生崩溃，恢复时 meta map 只指向完整的 chunk，不可能读到半写的数据。

**隔离性（Isolation）：** 默认 READ COMMITTED（脏读不可见，不可重复读和幻读可能）。H2 支持额外 4 种隔离级别：READ UNCOMMITTED、REPEATABLE READ、SNAPSHOT 和 SERIALIZABLE（详见第10.2节）。MVCC 模式下，读写不互相阻塞。

**持久性（Durability）：** H2 通过将数据写入 chunk 并更新 file header 来确保持久化。但官方文档明确指出："This database does not guarantee that all committed transactions survive a power failure"（详见官方文档 `advanced.html#durability_problems`）。测试表明所有数据库（包括 H2、HSQLDB、PostgreSQL、Derby）在电源故障时都可能丢失已提交事务。原因在于操作系统和硬盘的写缓存：即使 Java 调用 `FileDescriptor.sync()` 或 `FileChannel.force()`，大多数硬盘并不真正立即刷新数据到物理介质。对于需要严格持久性的场景，官方建议使用 UPS 或集群模式。

> **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#acid` 和 `advanced.html#durability_problems`)
> 完整讨论了 ACID 四个特性的支持情况，以及持久性测试的方法和结果。
```

- [ ] **Step 2.2: 在 ch9-10 章的章首小节导航中增加 10.5 的引用**

  在 `ch9-10-persistence-locking.md` 第9章引言段落（"本章将深入剖析 MVStore..."所在段落后）的 10.5 节对应位置，找到 "第10章将在此基础上进一步讨论锁与并发控制机制" 这句话，在该段落后或第10章章节描述中增加对 10.5 的提及。

  具体：找到原文第7行（"第10章将在此基础上进一步讨论锁与并发控制机制"），将其扩展为：
```
第10章将在此基础上进一步讨论锁与并发控制机制。10.5 节从 ACID 视角总结 H2 的事务保证。
```

- [ ] **Step 2.3: 运行标准验证流程**

  ```bash
  python docs-stm/tools/cover_stats.py
  python docs-stm/tools/rebuild_merged.py
  python docs-stm/tools/generate_html.py
  python docs-stm/tools/_audit_smart.py
  python docs-stm/tools/final_check.py
  ```
  预期：全部通过。注意：_audit_smart.py 可能报告新的小节缺图警告，确认图 10-18 已满足要求。

- [ ] **Step 2.4: 提交**

  ```bash
  git add docs-stm/ch9-10-persistence-locking.md
  git commit -m "docs: 增补 10.5 ACID 特性讨论

  引用官方 advanced.html#acid 和 advanced.html#durability_problems，
  从 Atomicity/Consistency/Isolation/Durability 四个维度分析 H2 的事务保证。
  新增图 10-18 ACID 支持矩阵。"
  ```

---

### Task 3: 增补安全机制分析（B 类）

**文件:** `docs-stm/ch1-2-architecture.md`, `docs-stm/ch11-12-guide-summary.md`

**说明:** 当前文档缺少安全机制的独立分析。在 ch1 的特性列表和 ch12 的总结中增补安全特性描述。引用官方 `security.html`、`advanced.html#sql_injection`、`advanced.html#remote_access`、`advanced.html#security_protocols`、`advanced.html#file_system`（加密文件系统）等素材。

- [ ] **Step 3.1: 在 ch1-2 架构章节的 1.1 特性列表中增加安全特性**

  在 `ch1-2-architecture.md` 的 "核心特性" 列表（当前约第13-19行）末尾追加一项：
```
- **多层安全**：AES 加密存储、SHA-256 密码哈希、PBKDF2 密钥派生、XTS-AES 磁盘加密、
  SSL/TLS 链路加密、SQL 注入防护（`ALLOW_LITERALS NONE`）、
  远程访问保护、类加载限制
```

- [ ] **Step 3.2: 在 ch11-12 的 12.1 特性总结中新增安全机制小节**

  在 `ch11-12-guide-summary.md` 第12章中，找到特性总结部分，新增一个安全机制子节：

```markdown
### 12.1.x 安全机制

H2 提供了多层安全防护（详见官方文档 `security.html`、`advanced.html#sql_injection`、
`advanced.html#remote_access` 和 `advanced.html#security_protocols`）：

- **存储加密**: 使用 XTS-AES 模式加密整个数据库文件，密钥通过 PBKDF2 从口令派生
  （详见 `org/h2/store/fs/FilePathEncrypt.java`）。
- **传输加密**: SSL/TLS 加密客户端-服务器通信。
- **SQL 注入防护**: 支持 `SET ALLOW_LITERALS NONE` 禁止 SQL 语句中的字面量，
   强制使用参数化查询（详见官方文档 `advanced.html#sql_injection`）。
- **访问控制**: 基于角色的授权机制（GRANT/REVOKE），支持模式级别的权限隔离。
- **远程访问保护**: 默认禁用远程连接，可通过 `-tcpAllowOthers` 等参数显式开启
  （详见官方文档 `advanced.html#remote_access`）。
- **类加载限制**: 可限制用户定义函数和触发器可加载的 Java 类
  （详见官方文档 `advanced.html#restricting_classes`）。

> **参考**: H2 官方文档《Security》(`h2/src/docsrc/html/security.html`)
> 完整安全特性列表。官方《Advanced》文档中对 SQL 注入防护、远程访问保护
> 和安全协议有更详细的配置说明。
```

- [ ] **Step 3.3: 运行标准验证流程**

  ```bash
  python docs-stm/tools/cover_stats.py
  python docs-stm/tools/rebuild_merged.py
  python docs-stm/tools/generate_html.py
  python docs-stm/tools/_audit_smart.py
  python docs-stm/tools/final_check.py
  ```

- [ ] **Step 3.4: 提交**

  ```bash
  git add docs-stm/ch1-2-architecture.md docs-stm/ch11-12-guide-summary.md
  git commit -m "docs: 增补安全机制分析

  在 ch1 核心特性列表增加多层安全项，在 ch12 特性总结中新增安全机制小节。
  引用官方 security.html, advanced.html#sql_injection, advanced.html#remote_access,
  advanced.html#security_protocols 等素材。"
  ```

---

### Task 4: 增补 MVStore 文件格式深度内容（B 类）

**文件:** `docs-stm/ch9-10-persistence-locking.md`

**说明:** 官方 `mvstore.html#fileFormat` 包含了详细的 File Header、Chunk 格式、Page 格式二进制布局，包括 64-bit page pointer 编码、counted B-tree 等细节。当前 ch9 的内容已经覆盖了架构层面，但缺少二进制级别的精确描述。新增 9.6 节专项讨论。

- [ ] **Step 4.1: 在 ch9-10 的 9.5 节之后新增 9.6 节「MVStore 文件格式详解」**

  在 `ch9-10-persistence-locking.md` 的 9.5 节之后、第10章之前插入：

```markdown
## 9.6 MVStore 文件格式详解

本节基于官方文档 `mvstore.html#fileFormat` 的说明，深入 MVStore 的二进制文件布局。
理解文件格式对于调试持久化问题、分析存储空间使用和进行数据恢复至关重要。

### 9.6.1 文件整体布局

MVStore 的数据文件由两个冗余的 file header 和一系列 chunk 组成：

```text
[ File Header 1 ] [ File Header 2 ] [ Chunk ] [ Chunk ] ... [ Chunk ]
    4 KB             4 KB             可变大小    可变大小      可变大小
```

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
> 其中的"File Format"节详细描述了文件、chunk、page 三级的二进制布局。

### 9.6.2 File Header 格式

每个 file header 固定为 4096 字节（一个 block，匹配磁盘扇区大小）。header 以 key-value 文本形式存储：

```text
H:2,block:2,blockSize:1000,chunk:7,created:1441235ef73,format:1,version:7,fletcher:3044e6cc
```

各字段含义如下：

| 字段 | 示例值 | 说明 |
|------|--------|------|
| H | 2 | 固定标识 "H:2" 表示 H2 数据库文件 |
| block | 2 | 最新 chunk 的起始 block 号（不一定是最新版本） |
| blockSize | 1000 | block 大小（十六进制），1000₁₆ = 4096 字节 |
| chunk | 7 | chunk ID（通常等于 version，但可能回卷） |
| created | 1441235ef73 | 文件创建时间（1970 年以来的毫秒数） |
| format | 1 | 文件格式版本号（当前为 1） |
| version | 7 | 该 chunk 的版本号 |
| fletcher | 3044e6cc | Fletcher-32 checksum |

打开文件时，两个 header 都被读取并校验 checksum：
- 如果两个 header 都有效，使用版本号更新的那个。
- 最新 chunk 的定位：先尝试 file header 中记录的 block，再从文件末尾的 chunk footer 反向查找。
- 如果 header 中的 chunk id/block/version 不可用，从文件最后一个 chunk 开始搜索。

### 9.6.3 Chunk 格式

每个 chunk 对应一个版本，由 header、若干 page 和 footer 组成：

```text
[ Chunk Header ] [ Page ] [ Page ] ... [ Page ] [ Chunk Footer ]
   可变大小        可变大小  可变大小             128 bytes
```

Chunk header 示例：
```text
chunk:1,block:2,len:1,map:6,max:1c0,next:3,pages:2,root:4000004f8c,time:1fc,version:1
```

Chunk footer 示例：
```text
chunk:1,block:2,version:1,fletcher:aed9a4f6
```

| 字段 | header/footer | 说明 |
|------|--------------|------|
| chunk | 两者 | chunk ID |
| block | header | chunk 起始 block 号（×blockSize=文件位置） |
| len | header | chunk 占用的 block 数 |
| map | header | 最新 map 的 ID（新建 map 时递增） |
| max | header | 所有 page 最大长度之和 |
| next | header | 预测的下一个 chunk 起始 block |
| pages | header | chunk 中包含的 page 数 |
| root | header | 元数据 root page 的位置 |
| time | header | chunk 写入时间（文件创建后的毫秒数） |
| version | 两者 | 该 chunk 代表的版本号 |
| fletcher | footer | footer 的 Fletcher-32 checksum |

关键设计要点：

1. **append-only**：chunk 从不原地更新。每次 commit 写入一个新 chunk。
2. **COW**：修改 page 时，旧 page 保留在原 chunk 中，新 page 写入新 chunk，父 page 递归复制更新。
3. **45 秒保留**：chunk 被标记为 free 后，默认至少保留 45 秒才被覆写，确保旧版本可读。
4. **空间回收**：live page 最少的 chunk 被优先 compact（重新写入新 chunk 后释放旧空间）。
5. **next 链**：file header 不一定会指向最新 chunk，而是通过 chunk 的 next 字段形成链，最长 20 跳后强制更新 header。

### 9.6.4 Page 格式

每个 page 以二进制格式存储（不可直接阅读），使用变长编码优化空间：

```text
┌─────────────────────────────────────────────────────────┐
│  Page 二进制布局                                           │
├──────────────┬──────────┬───────────────────────────────┤
│  字段          │  类型     │  说明                          │
├──────────────┼──────────┼───────────────────────────────┤
│  length      │  int(4)  │  page 字节总长度                │
│  checksum    │ short(2) │ chunk id xor 块内偏移 xor 长度  │
│  mapId       │  VarInt   │ 所属 map 的 ID                 │
│  len         │  VarInt   │ page 中键的数量                 │
│  type        │  byte(1)  │ 0=leaf, 1=internal, +2=LZF    │
│  children    │  long[]   │ 内部节点: 子 page 位置数组      │
│  childCounts │ VarLong[] │ 内部节点: 各子树条目计数        │
│  keys        │  byte[]   │ 键序列（按数据类型序列化）      │
│  values      │  byte[]   │ 叶子节点: 值序列                │
└──────────────┴──────────┴───────────────────────────────┘
```

**Page Pointer 编码（64-bit）：** 指向其他 page 的引用被编码为一个 64-bit long：

```text
┌─────26 bits─────┬──────32 bits──────┬───5 bits───┬──1 bit───┐
│    Chunk ID     │  Chunk 内偏移      │ 长度代码    │ 类型     │
│    (26 bit)     │   (32 bit)        │  (5 bit)   │ (1 bit)  │
└─────────────────┴───────────────────┴────────────┴──────────┘
```

- 26 bit chunk ID：最多支持 6710 万个 chunk
- 32 bit 偏移：支持最大 chunk 大小为 4 GB
- 5 bit 长度代码：0=32B, 1=48B, 2=64B, 3=96B, ..., 31=>1MB
  （读取 page 时只需一次 I/O，除超大 page 外）
- 1 bit 类型：0=叶子, 1=内部节点
- 不包含绝对文件位置，因此 chunk 可在文件内移动而不需修改 page pointer

**Counted B-Tree：** 内部节点中的 `childCounts` 数组记录了每个子树的总条目数。这一设计使得：
- 可以高效地通过索引访问条目（`getIndex(key)`）
- 可以快速计算两个键之间的中位数
- 可以高效地对 range 进行计数
- Iterator 支持快速 skip

### 9.6.5 元数据 Map

每个 chunk 的最后一页是元数据 map 的 root page，其位置记录在 chunk header 的 `root` 字段中。
元数据 map 存储以下信息：

- `chunk.<id>`: chunk 元数据（同上 header 内容 + live page 数 + live 最大长度）
- `map.<id>`: map 元数据（name、createVersion、type）

```text
Chunk N 的元数据 root page（chunk header 的 root 字段指向这里）
  ├── "chunk.N" → {... chunk 元数据 ...}
  ├── "map.0"   → {name: "meta", createVersion: 0, type: ...}
  ├── "map.1"   → {name: "data", createVersion: 1, type: ...}
  └── ...
```

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
> 的"Metadata Map"子节，详细说明了元数据 map 的键值格式。
```

- [ ] **Step 4.2: 在 ch9 开头的导航描述中增加对 9.6 节的引用**

  找到 `ch9-10-persistence-locking.md` 第7行（章节导航段落）：
```
9.5 节介绍检查点触发逻辑与后台写入线程
```
  将其扩展为：
```
9.5 节介绍检查点触发逻辑与后台写入线程；9.6 节详述 MVStore 的二进制文件格式
（file header、chunk、page 三级的布局与编码）。
```

- [ ] **Step 4.3: 运行标准验证流程**

  ```bash
  python docs-stm/tools/cover_stats.py
  python docs-stm/tools/rebuild_merged.py
  python docs-stm/tools/generate_html.py
  python docs-stm/tools/_audit_smart.py
  python docs-stm/tools/final_check.py
  ```

- [ ] **Step 4.4: 提交**

  ```bash
  git add docs-stm/ch9-10-persistence-locking.md
  git commit -m "docs: 增补 9.6 MVStore 文件格式详解

  引用官方 mvstore.html#fileFormat，深入分析文件整体布局、
  File Header 双副本设计、Chunk Header/Footer 字段定义、
  Page 二进制格式和 64-bit Page Pointer 编码、
  Counted B-Tree 和元数据 Map 的结构。
  新增图 10-18/10-19 等 ASCII 示意图。"
  ```

---

### Task 5: 增强性能基准对比与调优参考（B 类）

**文件:** `docs-stm/ch1-2-architecture.md`

**说明:** 官方 `performance.html` 包含 H2 与 HSQLDB、Derby、PostgreSQL、MySQL 的详细性能对比数据。在 ch1 的特性对比表之后补充性能对比数据，并引用官方文档说明。

- [ ] **Step 5.1: 在 ch1 图 1-2 特性对比之后新增性能对比补充说明**

  在 `ch1-2-architecture.md` 中，找到图 1-2 之后的段落（"从上表可见..."段落后），插入性能对比参考：

```
> **性能参考**: H2 官方文档《Performance》(`h2/src/docsrc/html/performance.html#performance_comparison`)
> 包含 H2 与 HSQLDB、Derby、PostgreSQL、MySQL 在嵌入式和 C/S 模式下的详细性能对比
> （Simple/BenchA/BenchB/BenchC 四种测试场景）。测试结果显示 H2 在嵌入式模式下
> 每秒可执行约 158,000 条语句（HSQLDB 约 85,000，Derby 约 35,000），
> 在 C/S 模式下每秒约 12,300 条语句。需注意该测试为单连接基准测试，实际性能取决于
> 应用场景和配置调优。
>
> 官方文档中还包含了数据库性能调优指南（`performance.html#database_performance_tuning`）、
> 内置分析器使用说明（`performance.html#built_in_profiler`）以及
> 数据存储与索引的工作原理（`performance.html#storage_and_indexes`）。
```

- [ ] **Step 5.2: 运行标准验证流程**

  ```bash
  python docs-stm/tools/cover_stats.py
  python docs-stm/tools/rebuild_merged.py
  python docs-stm/tools/generate_html.py
  python docs-stm/tools/_audit_smart.py
  python docs-stm/tools/final_check.py
  ```

- [ ] **Step 5.3: 提交**

  ```bash
  git add docs-stm/ch1-2-architecture.md
  git commit -m "docs: 增补性能基准对比参考

  引用官方 performance.html 的性能对比数据，补充 H2 在嵌入式和 C/S 模式下
  与 HSQLDB/Derby/PostgreSQL/MySQL 的对比。引用调优指南和内置分析器参考。"
  ```

---

### Task 6: 术语一致性审计与全书对齐（C 类）

**文件:** 全书 9 个源章节文件

**说明:** 对比官方文档中的术语使用，确保全书术语与 H2 官方用语一致。

- [ ] **Step 6.1: 官方术语对照表编制**

  基于官方 `mvstore.html`、`architecture.html`、`advanced.html` 等文档，建立全书术语审计基准。

  | 本书当前用语 | 官方用语 | 是否对齐 |
  |-------------|---------|---------|
  | COW B-Tree / Copy-on-Write 版本管理 | COW (copy on write) | ✅ |
  | Chunk 压缩整理 | compaction | ✅ |
  | LIRS 缓存替换 | LIRS cache | ✅ |
  | Log-Structured 存储 | log structured storage | ✅ |
  | MVCC 多版本控制 | multi-version concurrency control | ✅ |
  | page / 页面 | page | ✅ |
  | RootReference | root reference | ✅ |
  | 空闲空间管理 | free space | ✅ |
  | 写前日志 / WAL | transaction log / undo log | ⚠️ 注意：MVStore 不使用单独的 WAL |
  | 原子提交 | atomic commit | ✅ |

  搜索全书确认：使用以下模式搜索确认术语用法：

  ```bash
  # 搜索潜在的不一致术语（chunk/Chunk 大小写一致性）
  grep -n '\bchunk\b' docs-stm/ch9-10-persistence-locking.md | head -5
  grep -n '\bChunk\b' docs-stm/ch9-10-persistence-locking.md | head -5
  
  # 确认 WAL 术语准确使用
  grep -n 'WAL\|写前日志\|write-ahead' docs-stm/*.md
  ```

- [ ] **Step 6.2: 修复术语不一致（如发现）**

  根据 Step 6.1 的审计结果修复发现的问题。典型需检查的点：
  
  1. `WAL`/`写前日志` 的用法是否在 MVStore 上下文中准确（MVStore 不使用 WAL）
  2. `PageStore` vs `page store` 大小写一致性
  3. `MVStore` vs `MvStore` vs `mvstore` 在全书中保持一致

  使用以下命令精确搜索和替换（示例——实际按 Step 6.1 结果调整）：

  ```bash
  # 示例：统一 MVStore 大小写
  grep -rn '\bMvStore\b' docs-stm/ch*.md
  
  # 示例：确认 WAL 仅在正确上下文出现
  grep -rn '\bWAL\b' docs-stm/ch*.md
  ```

- [ ] **Step 6.3: 运行标准验证流程**

  ```bash
  python docs-stm/tools/cover_stats.py
  python docs-stm/tools/rebuild_merged.py
  python docs-stm/tools/generate_html.py
  python docs-stm/tools/_audit_smart.py
  python docs-stm/tools/final_check.py
  ```

- [ ] **Step 6.4: 提交**

  ```bash
  # 按实际修改的文件更新
  git add docs-stm/  # 如有修改
  git commit -m "docs: 术语一致性审计与修复

  对照官方 mvstore.html/architecture.html/advanced.html 等文档的术语用法，
  修复全书术语不一致问题。"
  ```

---

### Task 7: 章节间交叉引用完整性检查（C 类）

**文件:** 全书 9 个源章节文件

**说明:** 检查全书的 `详见第X章《...》` 引用是否都指向正确的 H1 标题。

- [ ] **Step 7.1: 提取所有 H1 标题**

  ```bash
  grep '^# ' docs-stm/ch1-2-architecture.md docs-stm/ch3-packages.md \
       docs-stm/ch4-5-modules-processes.md docs-stm/ch6-1-data-structures.md \
       docs-stm/ch6-2-storage-algorithms.md docs-stm/ch6-3-query-algorithms.md \
       docs-stm/ch7-8-sql-optimizer.md docs-stm/ch9-10-persistence-locking.md \
       docs-stm/ch11-12-guide-summary.md
  ```

  提取出所有的 H1 标题，作为交叉引用的合法目标列表。

- [ ] **Step 7.2: 提取所有 `详见第X章` 引用**

  ```bash
  grep -rno '详见第.*章《[^》]*》' docs-stm/ch*.md
  ```

  逐条对比提取到的引用与 Step 7.1 的 H1 标题。发现的错误用 Edit 修复。常见问题：
  - H1 标题别名与真实标题不一致（如 R4-6 修复过的类型）
  - 章号与标题不匹配（如引用"第5章"但标题第6章的内容）

- [ ] **Step 7.3: 修复发现的不一致引用**

  对每个错误执行 Edit 修复。例如：
  ```
  详见第6章《核心算法分析篇》→ 详见第6章《H2 数据库核心算法分析》
  ```

- [ ] **Step 7.4: 运行标准验证流程**

  ```bash
  python docs-stm/tools/cover_stats.py
  python docs-stm/tools/rebuild_merged.py
  python docs-stm/tools/generate_html.py
  python docs-stm/tools/_audit_smart.py
  python docs-stm/tools/final_check.py
  ```

- [ ] **Step 7.5: 提交**

  ```bash
  git add docs-stm/
  git commit -m "docs: 交叉引用完整性修复

  检查全书所有"详见第X章《...》"引用的准确性和一致性，
  修复标题别名与真实 H1 不匹配的问题。"
  ```

---

### Task 8: 全书终验与最终产物生成

**说明:** 所有内容变更完成后，进行全面验证并重新生成最终产物。

- [ ] **Step 8.1: 全量验证**

  ```bash
  # 更新统计数据
  python docs-stm/tools/cover_stats.py
  
  # 重新生成合并文档
  python docs-stm/tools/rebuild_merged.py
  
  # 重新生成 HTML（带侧边栏 TOC）
  python docs-stm/tools/generate_html.py
  
  # 智能审计（图表覆盖、缺图检查）
  python docs-stm/tools/_audit_smart.py
  
  # 最终检查（55 项全部通过）
  python docs-stm/tools/final_check.py
  ```

- [ ] **Step 8.2: PDF 专项验证（如需要正式交付）**

  ```bash
  python docs-stm/tools/generate_pdf.py
  python docs-stm/tools/add_pdf_toc_links.py
  python docs-stm/tools/verify_pdf.py
  ```

- [ ] **Step 8.3: 验证 cover.md 统计数据与实际一致**

  用 `cover_stats.py` 自动更新 cover.md：
  ```bash
  python docs-stm/tools/cover_stats.py
  cat docs-stm/cover.md
  ```
  检查版本号、行数、图数、源码引用数等与合并文档实际匹配。

- [ ] **Step 8.4: 提交最终版本**

  ```bash
  # 检查所有变更
  git diff --stat
  
  # 提交
  git add docs-stm/cover.md docs-stm/h2-source-code-analysis.md \
        docs-stm/h2-source-code-analysis.html \
        docs-stm/changelog.md
  git commit -m "docs: v4.23 质量提升 —— 官方文档引用与内容增强

  新增/变更：
  - 建立官方文档交叉引用体系（30+ 处引用 architecture/mvstore/advanced/features/performance/tutorial）
  - 增补 10.5 ACID 特性讨论（Atomicity/Consistency/Isolation/Durability）
  - 增补安全机制分析（加密/注入防护/访问控制/传输安全）
  - 增补 9.6 MVStore 文件格式详解（file header/chunk/page 二进制布局）
  - 增补性能基准对比参考（官方 benchmark 数据）
  - 术语一致性审计与章节交叉引用完整性修复"
  ```

---

### 预期产出

| 度量 | 当前 | 目标 |
|------|------|------|
| 章节数 | 12 章 | 12 章（内容扩展） |
| 总行数 | ~35,339 行 | ~36,500 行（+~1,200 行） |
| ASCII 示意图 | 571 幅 | 576 幅（+5 幅） |
| 源码引用 | 185 处 | 185 处（不变） |
| 官方文档引用 | 0 处 | 30+ 处 |
| ACID 讨论 | 无 | 10.5 独立小节 |
| 安全分析 | 无 | 12.1.x 独立小节 |
| MVStore 文件格式 | 架构级描述 | 二进制级别精确描述 |
| final_check | 55/55 | 55/55（无回归） |
