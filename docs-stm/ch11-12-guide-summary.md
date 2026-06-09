# 第11章 核心源代码导读指引

## 11.1 按功能分类的文件索引

### 11.1.1 包级依赖关系总览

```text
本节速览：11.1.1 包级依赖关系总览

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

了解 H2 各包之间的依赖关系是阅读源码的第一步。下图展示了从 JDBC 层到存储引擎的核心调用链。各包对应模块的详细分析可参阅：

- 第1章《总体架构》和第2章《分层模块划分》——了解整体架构与层间依赖
- 第3章《核心包结构详解》——了解包的构成
- 第4章《核心模块深度解读》和第5章《核心流程解读》——了解每个关键类的实现
- 第6章《H2 数据库核心算法分析》——了解 B-Tree、MVCC 等算法细节
- 第7章《SQL 执行全流程》和第8章《查询优化器深度解读》——了解查询优化机制
- 第9章《持久化引擎深度解析》和第10章《锁实现与并发控制》——了解存储和并发方面的深入内容

详见第3章《核心包结构详解》、第6章《H2 数据库核心算法分析》和第9章《持久化引擎深度解析》。

**图 11-1: H2 源码包依赖关系地图**

```text
============================================================

                          SQL 请求/结果
                              │
                              ▼
 ┌─────────────────────────────────────────────────────────┐
 │                    JDBC Layer (jdbc/)                    │
 │  JdbcConnection ──> JdbcStatement ──> JdbcResultSet    │
 │  连接管理           语句执行             结果集封装        │
 └──────────┬──────────────────────────────────────────────┘
            │ 调用 Command 接口
            ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   Command Layer (command/)               │
 │  Parser ──> Prepared ──> Select / Insert / Update       │
 │  SQL 解析    预编译命令      具体 DML 操作                │
 └──────────┬──────────────────────────────────────────────┘
            │ 依赖 Engine 和 Table
            ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   Engine Layer (engine/)                 │
 │  Engine ──> Database ──> SessionLocal ──> DbSettings   │
 │  全局入口    数据库实例     会话管理        配置体系      │
 └──────────┬──────────────────────────────────────────────┘
            │ 访问表和索引
            ▼
 ┌─────────────────────────────────────────────────────────┐
 │              Table / Index Layer (table/ + index/)       │
 │  Table ──> TableFilter ──> Index ──> IndexCursor       │
 │  表定义      过滤条件        索引查找      游标遍历       │
 └──────────┬──────────────────────────────────────────────┘
            │ 数据存储访问
            ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │                    MVStore Layer (mvstore/)                       │
 │  ┌──────────┐    ┌──────────┐    ┌──────────────────┐           │
 │  │ MVStore  │───>│ MVMap    │───>│ Page             │           │
 │  │ 存储引擎  │    │ B-Tree   │    │ 页读写 + 序列化  │           │
 │  └──────────┘    └──────────┘    └──────────────────┘           │
 │       │                │                 │                       │
 │       ▼                ▼                 ▼                       │
 │  ┌──────────┐    ┌──────────┐    ┌──────────────────┐           │
 │  │ Chunk    │    │RootRef   │    │FreeSpaceBitSet   │           │
 │  │ 存储块    │    │ 根引用    │    │ 空闲空间管理      │           │
 │  └──────────┘    └──────────┘    └──────────────────┘           │
 │                                                                  │
 │  ┌──────────────────────┐  ┌──────────────────────┐              │
 │  │ TransactionStore     │  │ CacheLongKeyLIRS     │              │
 │  │ 事务管理 + MVCC      │  │ LIRS 缓存淘汰算法     │              │
 │  └──────────────────────┘  └──────────────────────┘              │
 └──────────────────────────┬───────────────────────────────────────┘
                            │ 文件 I/O
                            ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │              Store Bridge + File System                          │
 │  mvstore/db/: Store, MVTable, MVPrimaryIndex, MVSecondaryIndex  │
 │  store/fs/:   FilePath, FilePathDisk, FilePathMem, FileEncrypt  │
 └──────────────────────────────────────────────────────────────────┘

 箭头方向 = 依赖/调用方向     ──> 数据流     - - >  控制流
```

### 11.1.2 数据库引擎核心

```text
本节速览：11.1.2 数据库引擎核心

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 (相对 src/main/org/h2/) |
|------|------|---------------------------|
| 全局入口 | Engine.java | `engine/Engine.java` |
| 数据库实例 | Database.java | `engine/Database.java` |
| 会话管理 | SessionLocal.java | `engine/SessionLocal.java` |
| 连接参数 | ConnectionInfo.java | `engine/ConnectionInfo.java` |
| 设置 | DbSettings.java | `engine/DbSettings.java` |
| 模式 | Mode.java | `engine/Mode.java` |
| 隔离级别 | IsolationLevel.java | `engine/IsolationLevel.java` |

如图 11-1 所示，**引擎核心层**是 H2 数据库的"操作系统"（详见第1章《总体架构》和第2章《分层模块划分》）。`Engine.java` 作为全局唯一的入口点，负责接收来自 JDBC 层的命令请求，创建或复用数据库实例（`Database.java`）。每个客户端连接对应一个 `SessionLocal` 对象，管理事务状态、锁资源和临时表。`DbSettings` 和 `Mode` 分别控制系统级参数和 SQL 兼容模式。这组文件构成了 H2 运行时环境的骨架——所有上层操作最终都通过这一层协调。

关键调用链：`Engine.createSession()` → `Database.getSession()` → `SessionLocal` 执行命令 → 返回结果。阅读时应关注 `SessionLocal` 如何维护事务上下文以及 `Database` 如何管理全局资源（锁、缓存、存储引擎）。

### 11.1.3 SQL 解析与执行

```text
本节速览：11.1.3 SQL 解析与执行

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| SQL 解析器 | Parser.java | `command/Parser.java` |
| 词法分析 | Tokenizer.java | `command/Tokenizer.java` |
| 命令基类 | Command.java | `command/Command.java` |
| 命令容器 | CommandContainer.java | `command/CommandContainer.java` |
| 预编译基类 | Prepared.java | `command/Prepared.java` |

**命令层**将 SQL 文本转化为可执行的命令对象（详见第7章《SQL 执行全流程》）。`Tokenizer` 将 SQL 字符串拆解为 Token 流，`Parser` 使用递归下降解析法构建抽象语法树并实例化对应的命令对象（如 `Select`、`Insert`）。所有命令继承自 `Prepared`，它负责参数绑定、权限校验和执行计划缓存。`CommandContainer` 封装了命令的完整生命周期。这一层的核心设计模式是 **Command Pattern**——每个 SQL 语句对应一个命令对象，职责单一、易于扩展。

### 11.1.4 DML

```text
本节速览：11.1.4 DML

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| SELECT | Select.java | `command/query/Select.java` |
| SELECT 基类 | Query.java | `command/query/Query.java` |
| 查询优化器 | Optimizer.java | `command/query/Optimizer.java` |
| GROUP BY | SelectGroups.java | `command/query/SelectGroups.java` |
| INSERT | Insert.java | `command/dml/Insert.java` |
| UPDATE | Update.java | `command/dml/Update.java` |
| DELETE | Delete.java | `command/dml/Delete.java` |
| MERGE | Merge.java | `command/dml/Merge.java` |
| 事务命令 | TransactionCommand.java | `command/dml/TransactionCommand.java` |

**DML（数据操作语言）** 命令是数据库最核心的执行逻辑（详见第8章《查询优化器深度解读》）。`Select.java` 是最复杂的命令，它聚合了查询优化、表过滤、索引选择和表达式求值。`Insert`、`Update`、`Delete` 相对简单，但需要与事务系统深度交互以保证 ACID 特性。`Query.java` 是所有查询操作的基类，定义了查询的通用执行框架：准备 → 优化 → 执行 → 返回结果。`Optimizer.java` 实现基于代价的查询优化（CBO），评估不同执行计划的代价以选择最优索引。

### 11.1.5 DDL

```text
本节速览：11.1.5 DDL

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| CREATE TABLE | CreateTable.java | `command/ddl/CreateTable.java` |
| CREATE INDEX | CreateIndex.java | `command/ddl/CreateIndex.java` |
| ALTER TABLE | AlterTable.java | `command/ddl/AlterTable.java` |
| 统计信息 | Analyze.java | `command/ddl/Analyze.java` |

**DDL（数据定义语言）** 命令负责数据库对象的创建和修改（详见第9章《持久化引擎深度解析》）。它们不仅要更新系统表（System Table）中的元数据，还需要与存储引擎交互以创建物理存储结构。`Analyze.java` 收集表和索引的统计信息，为查询优化器提供代价估算的依据。DDL 命令通常隐式提交当前事务，这是 SQL 标准的行为约定。

### 11.1.6 表达式系统

```text
本节速览：11.1.6 表达式系统

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| 表达式基类 | Expression.java | `expression/Expression.java` |
| 列引用 | ExpressionColumn.java | `expression/ExpressionColumn.java` |
| 比较运算 | Comparison.java | `expression/condition/Comparison.java` |
| AND/OR | ConditionAndOr.java | `expression/condition/ConditionAndOr.java` |
| 聚合函数 | Aggregate.java | `expression/aggregate/Aggregate.java` |
| 窗口函数 | Window.java | `expression/analysis/Window.java` |
| 内置函数注册 | BuiltinFunctions.java | `expression/function/BuiltinFunctions.java` |

**表达式系统**实现了 SQL 中所有值计算逻辑（详见第7章《SQL 执行全流程》第7.6节）。`Expression` 是所有表达式节点的基类，定义了 `getValue()` 接口。整个表达式树采用 **Composite Pattern** 组织：比较运算、条件组合、函数调用都是表达式的组合节点。`Aggregate` 实现聚合函数（SUM、COUNT、AVG 等），`Window` 实现窗口函数（ROW_NUMBER、RANK 等），两者都基于 `SelectGroups` 的分组逻辑。`BuiltinFunctions` 通过注册机制管理数百个内置函数，支持动态扩展。

### 11.1.7 表与索引

```text
本节速览：11.1.7 表与索引

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

| 功能 | 文件 | 路径 |
|------|------|------|
| 表基类 | Table.java | `table/Table.java` |
| 表过滤 | TableFilter.java | `table/TableFilter.java` |
| 列定义 | Column.java | `table/Column.java` |
| 查询计划 | Plan.java | `table/Plan.java` |
| 索引基类 | Index.java | `index/Index.java` |
| 索引条件 | IndexCondition.java | `index/IndexCondition.java` |
| 索引游标 | IndexCursor.java | `index/IndexCursor.java` |

**表与索引层**是 SQL 层和存储引擎之间的桥梁。`Table` 定义了关系表的抽象接口，`MVTable`（在 mvstore/db 中）是 MVStore 引擎的具体实现。`TableFilter` 负责在查询执行时应用 WHERE 条件过滤行数据，`Plan` 封装了查询计划的执行策略。`Index` 是索引的抽象基类，`MVPrimaryIndex` 和 `MVSecondaryIndex` 分别对应主键和二级索引。`IndexCursor` 提供遍历索引条目的游标机制。

以下流程图展示了 SELECT 查询从 SQL 字符串到返回结果集的完整生命周期：

**图 11-2: SELECT 查询路径追踪流程图**

```text
============================================================

  客户端输入: SELECT a.id, a.name FROM accounts a WHERE a.balance > 1000
  ───────────────────────────────────────────────────────────────

                     ┌──────────────────────┐
                     │  1. JDBC 接口层       │
  JdbcConnection     │  JdbcStatement       │
  .prepareStatement  │  .executeQuery()     │
      │              │      │               │
      └──────────────┘      │               │
                            ▼               │
                     ┌──────────────────────┘
                     │
                     ▼
  ┌───────────────────────────────────────────────┐
  │  2. 命令层: SQL 解析                           │
  │                                               │
  │  CommandContainer.executeQuery()              │
  │       │                                        │
  │       ▼                                        │
  │  Parser.parse() ──递归下降解析                  │
  │       │  ┌───────────────┐                     │
  │       │  │ tokens:       │                     │
  │       │  │ SELECT        │                     │
  │       │  │ a.id, a.name  │                     │
  │       │  │ FROM accounts │                     │
  │       │  │ a             │                     │
  │       │  │ WHERE         │                     │
  │       │  │ a.balance     │                     │
  │       │  │ > 1000        │                     │
  │       │  └───────────────┘                     │
  │       ▼                                        │
  │  Select对象创建 ──── 包含查询全部信息            │
  └───────────────────┬───────────────────────────┘
                      │
                      ▼
  ┌───────────────────────────────────────────────┐
  │  3. 查询优化                                    │
  │                                               │
  │  Select.prepare()                             │
  │       │                                        │
  │       ▼                                        │
  │  Optimizer.optimize()                         │
  │       │   ┌──────────────────────────┐         │
  │       │   │ 评估可用的索引:          │         │
  │       │   │ - 主键索引 (无效: 非主键)│         │
  │       │   │ - balance_idx (有效)    │         │
  │       │   │ 选择: balance_idx       │         │
  │       │   └──────────────────────────┘         │
  │       ▼                                        │
  │  Plan 生成 ──── 执行计划                        │
  └───────────────────┬───────────────────────────┘
                      │
                      ▼
  ┌───────────────────────────────────────────────┐
  │  4. 存储引擎: 数据读取                          │
  │                                               │
  │  MVPrimaryIndex.find(tableFilter)             │
  │       │                                        │
  │       ▼                                        │
  │  MVMap.get(key) ──> B-Tree 查找                │
  │       │  ┌────────────────────────┐            │
  │       │  │ Root → Internal → Leaf │            │
  │       │  │ 从根节点向下查找        │            │
  │       │  └────────────────────────┘            │
  │       ▼                                        │
  │  TransactionMap.get()                          │
  │       │  ┌────────────────────────┐            │
  │       │  │ 比较事务版本:          │            │
  │       │  │ 当前事务ID vs 版本ID    │            │
  │       │  │ 判断可见性 → 返回数据   │            │
  │       │  └────────────────────────┘            │
  │       ▼                                        │
  │  Page.getLeaf() ──> 反序列化条目                │
  └───────────────────┬───────────────────────────┘
                      │
                      ▼
  ┌───────────────────────────────────────────────┐
  │  5. 结果封装并返回                              │
  │                                               │
  │  JdbcResultSet ← 行数据 ← Select.executeQuery │
  │       │                                        │
  │       ▼                                        │
  │  客户端遍历 ResultSet.next()                   │
  └───────────────────────────────────────────────┘
```

### 11.1.8 MVStore 存储引擎

```text
本节速览：11.1.8 MVStore 存储引擎

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| 存储引擎 | MVStore.java | `mvstore/MVStore.java` |
| B-Tree 映射 | MVMap.java | `mvstore/MVMap.java` |
| B-Tree 页 | Page.java | `mvstore/Page.java` |
| 存储块 | Chunk.java | `mvstore/Chunk.java` |
| 根引用 | RootReference.java | `mvstore/RootReference.java` |
| 空闲空间 | FreeSpaceBitSet.java | `mvstore/FreeSpaceBitSet.java` |
| LIRS 缓存 | CacheLongKeyLIRS.java | `mvstore/cache/CacheLongKeyLIRS.java` |
| R-Tree 空间索引 | MVRTreeMap.java | `mvstore/rtree/MVRTreeMap.java` |

如图 11-2 所示，**MVStore** 是 H2 2.x 的核心存储引擎，替代了 1.x 的 PageStore。其设计融合了 COW（Copy-on-Write）B-Tree 与 Log-Structured 存储的优点。`MVStore` 管理 Chunk 的分配和回收，`MVMap` 提供键值对映射接口，底层由 `Page` 构成 B-Tree。每次写入通过 CAS 更新 `RootReference` 实现无锁读。`FreeSpaceBitSet` 追踪可用存储空间，`CacheLongKeyLIRS` 使用 LIRS 算法缓存热点页。

### 11.1.9 MVStore 数据库集成

```text
本节速览：11.1.9 MVStore 数据库集成

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| DB-Store 桥接 | Store.java | `mvstore/db/Store.java` |
| MVCC 表 | MVTable.java | `mvstore/db/MVTable.java` |
| 主键索引 | MVPrimaryIndex.java | `mvstore/db/MVPrimaryIndex.java` |
| 二级索引 | MVSecondaryIndex.java | `mvstore/db/MVSecondaryIndex.java` |
| 空间索引 | MVSpatialIndex.java | `mvstore/db/MVSpatialIndex.java` |

**集成层** 是 MVStore 存储引擎与关系表模型之间的适配层。`Store.java` 将 MVStore 封装为数据库引擎可用的存储后端，管理所有系统表和用户表对应的 MVMap。`MVTable` 实现了 `Table` 接口，提供 MVCC 语义的表操作（快照读、行级锁）。`MVPrimaryIndex` 和 `MVSecondaryIndex` 分别包装 MVMap 以提供主键和二级索引查找能力，同时维护索引间的数据一致性。

### 11.1.10 事务管理

```text
本节速览：11.1.10 事务管理

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| 事务存储 | TransactionStore.java | `mvstore/tx/TransactionStore.java` |
| 事务 | Transaction.java | `mvstore/tx/Transaction.java` |
| 事务视图 | TransactionMap.java | `mvstore/tx/TransactionMap.java` |
| 版本值 | VersionedValue.java | `value/VersionedValue.java` |
| 快照 | Snapshot.java | `mvstore/tx/Snapshot.java` |

**事务子系统**在 MVMap 的纯存储能力之上增加了 ACID 语义。`TransactionStore` 管理所有活跃事务的日志和状态，`Transaction` 代表单个事务上下文。`TransactionMap` 是事务感知的 Map 视图——它在读取 MVMap 时附加版本可见性判断，实现 MVCC。`VersionedValue` 在 Value 中嵌入版本链（事务 ID 和操作类型），`Snapshot` 提供特定时刻的一致性视图。这种分层设计使事务语义与存储引擎解耦。

### 11.1.11 JDBC 层

```text
本节速览：11.1.11 JDBC 层

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| JDBC 连接 | JdbcConnection.java | `jdbc/JdbcConnection.java` |
| JDBC 语句 | JdbcStatement.java | `jdbc/JdbcStatement.java` |
| JDBC 预编译 | JdbcPreparedStatement.java | `jdbc/JdbcPreparedStatement.java` |
| JDBC 结果集 | JdbcResultSet.java | `jdbc/JdbcResultSet.java` |

**JDBC 层** 实现标准 JDBC 4.x 接口，是 H2 对外服务的主要 API。`JdbcConnection` 封装了连接参数和会话状态，`JdbcStatement` / `JdbcPreparedStatement` 将 SQL 字符串传递给命令层执行。`JdbcResultSet` 封装查询结果，支持游标滚动、类型转换和可更新结果集。该层是调试的起点——设置断点在 `JdbcStatement.executeQuery()` 可以追踪完整执行路径。

### 11.1.12 文件系统

```text
本节速览：11.1.12 文件系统

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| 文件抽象 | FilePath.java | `store/fs/FilePath.java` |
| 磁盘文件 | FilePathDisk.java | `store/fs/disk/FilePathDisk.java` |
| 内存文件 | FilePathMem.java | `store/fs/mem/FilePathMem.java` |
| 加密文件 | FilePathEncrypt.java | `store/fs/encrypt/FilePathEncrypt.java` |

**文件系统抽象层**采用 Strategy Pattern 提供统一的文件 I/O 接口。`FilePath` 是抽象基类，`FilePathDisk` 实现本地文件系统的读写，`FilePathMem` 将数据存储在内存中（支持 H2 的内存模式），`FilePathEncrypt` 在读写时透明地执行 AES/XTS 加解密。这种设计使得存储引擎无需关心底层存储介质的差异。

### 11.1.13 服务器

```text
本节速览：11.1.13 服务器

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| TCP 服务 | TcpServer.java | `server/TcpServer.java` |
| PG 协议 | PgServer.java | `server/pg/PgServer.java` |
| Web 控制台 | WebServer.java | `server/web/WebServer.java` |

**服务器层**使 H2 可以作为网络数据库运行。`TcpServer` 实现 H2 自己的 JDBC 远程协议，`PgServer` 实现了 PostgreSQL Wire Protocol，允许 PG 客户端直接连接 H2。`WebServer` 提供基于浏览器的管理控制台，支持 SQL 编辑、查询执行和数据库管理。

### 11.1.14 工具与安全

```text
本节速览：11.1.14 工具与安全

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```

| 功能 | 文件 | 路径 |
|------|------|------|
| 服务入口 | Server.java | `tools/Server.java` |
| SQL Shell | Shell.java | `tools/Shell.java` |
| 导入导出 | Csv.java | `tools/Csv.java` |
| 备份恢复 | Backup.java / Restore.java | `tools/Backup.java` |
| 加密 | AES.java | `security/AES.java` |
| 认证 | Authenticator.java | `security/auth/Authenticator.java` |

### 11.1.15 MVStore 文件存储布局

```text
本节速览：11.1.15 MVStore 文件存储布局

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

理解 MVStore 在磁盘上的物理布局有助于调试和性能分析：

**图 11-3: MVStore 文件存储布局**

```text
============================================================

  test.mv.db 文件结构:
  ┌──────────────────────────────────────────────────────────┐
  │ 文件头 (2 KB)                                            │
  │ ├─ 魔数: "H:2"  (文件格式标识)                           │
  │ ├─ 文件格式版本号                                        │
  │ ├─ 文件创建时间戳                                        │
  │ └─ 第一个 Chunk 的偏移量                                  │
  ├──────────────────────────────────────────────────────────┤
  │ Chunk 1  (当数据库启动时创建)                             │
  │ ├─ Chunk Header: {chunkId=1, blockCount=N, ...}         │
  │ ├─ Page 0: RootReference (指向 B-Tree 根)                │
  │ ├─ Page 1: B-Tree 内部节点 (索引路由)                    │
  │ ├─ Page 2: B-Tree 叶子节点 (键值数据)                    │
  │ └─ ... (更多数据页)                                      │
  ├──────────────────────────────────────────────────────────┤
  │ Chunk 2  (当写入数据时顺序追加)                           │
  │ ├─ Chunk Header                                         │
  │ ├─ Page N: 新的 B-Tree 叶子节点                          │
  │ ├─ Page N+1: 更新的内部节点 (COW 路径)                   │
  │ └─ Page N+2: 新的 RootReference                          │
  ├──────────────────────────────────────────────────────────┤
  │ Chunk 3  (继续顺序追加)                                  │
  │ ├─ ...                                                   │
  ├──────────────────────────────────────────────────────────┤
  │ ... 更多 Chunk ...                                        │
  ├──────────────────────────────────────────────────────────┤
  │ Chunk N  (当前写入位置)                                   │
  ├──────────────────────────────────────────────────────────┤
  │ 文件尾元数据                                              │
  │ ├─ Chunk 列表 (所有 Chunk 的偏移量和大小)                 │
  │ └─ 文件校验和                                            │
  └──────────────────────────────────────────────────────────┘

  写入特点:
  ──────────
  • 所有写入都是追加(append)到文件末尾 —— 无需随机寻道
  • 定期 Compaction 回收过期 Chunk 的空间
  • 根引用通过文件头的偏移量定位
  • 崩溃恢复: 从文件头开始扫描所有 Chunk 重建最新状态
```

## 11.2 建议的阅读顺序

如图 11-3 所示，H2 源码体积适中但架构完整，建议按照"宏观 → SQL → 存储 → 高级"的递进顺序阅读，每个阶段建立在前一个阶段的理解之上。各阶段的详细背景可参阅对应章节：阶段1（宏观理解）对应第1-2章架构分层和第3章包结构，阶段2（SQL 执行）对应第4章前半部分的命令与表达式模块，阶段3（存储引擎）对应第4章后半部分的 MVStore 模块和第6章核心算法，阶段4（高级主题）对应第7-8章查询优化和第10章锁与并发控制。

**图 11-4: 四阶段阅读路线图**

```text
============================================================

  阶段 1 ┌────────────────────────────────────────────────────────┐
  宏观   │  Engine.java → Database.java → Constants.java         │
  理解   │  Mode.java → DbSettings.java                          │
  ~30min │  理解: 全局生命周期、配置体系、SQL 兼容模式             │
         │  关键概念: Session、AutoCommit、系统表                   │
         └────────────────────────────────────────────────────────┘
                              │
                              │ ▼ 掌握全局架构后进入
                              │
  阶段 2 ┌────────────────────────────────────────────────────────┐
  SQL    │  JdbcStatement → CommandContainer → Parser            │
  执行   │  Tokenizer → Select → Query → Expression              │
  ~1h    │  理解: SQL 解析、命令模式、查询对象模型                  │
         │  关键概念: AST、递归下降解析、表达式树                   │
         └────────────────────────────────────────────────────────┘
                              │
                              │ ▼ 理解查询层后深入
                              │
  阶段 3 ┌────────────────────────────────────────────────────────┐
  存储   │  MVStore → MVMap → Page → Chunk                      │
  引擎   │  RootReference → FreeSpaceBitSet                      │
  ~1.5h  │  TransactionStore → TransactionMap → VersionedValue   │
         │  理解: COW B-Tree、Log-Structured、MVCC               │
         │  关键概念: 写放大、Compaction、版本链、CAS              │
         └────────────────────────────────────────────────────────┘
                              │
                              │ ▼ 掌握核心后探索
                              │
  阶段 4 ┌────────────────────────────────────────────────────────┐
  高级   │  Optimizer → Plan → SelectGroups                      │
  主题   │  CacheLongKeyLIRS → MVRTreeMap                        │
  ~1h    │  MVTable → MVSecondaryIndex                           │
         │  理解: 查询优化、缓存算法、空间索引、表锁与并发          │
         │  关键概念: CBO、LIRS、R-Tree、行级锁                    │
         └────────────────────────────────────────────────────────┘
```

如图 11-4 所示，**第一阶段：宏观理解（~30 分钟）**

1. `Engine.java` + `Database.java` —— 理解全局生命周期
2. `Constants.java` + `DbSettings.java` —— 系统配置
3. `Mode.java` —— SQL 兼容模式

**阅读策略**：第一阶段的目标是建立"森林"而非关注"树木"。阅读 `Engine.java` 时，关注 `createSession()` 和 `createDatabase()` 方法，理解 H2 如何在首次连接时初始化数据库。`Database.java` 是全局最复杂的类之一——不要试图理解所有细节，只关注 `open()` 方法中的初始化流程：系统表创建 → 存储引擎启动 → 恢复事务 → 准备接受连接。`DbSettings` 定义了数百个配置项，阅读时只需了解分类（性能、事务、存储、安全等），无需记忆每个参数。

**第二阶段：SQL 执行（~1 小时）**

4. `JdbcStatement.java` → `Command.java` → `CommandContainer.java` —— JDBC 到命令
5. `Parser.java` + `Tokenizer.java` —— SQL 解析
6. `Select.java` + `Query.java` —— SELECT 执行

**阅读策略**：第二阶段是理解"一条 SQL 如何变成可执行对象"。从 `JdbcStatement.executeQuery()` 设置断点，跟踪调用进入 `CommandContainer`。`Parser.java` 是核心——它使用递归下降解析将 SQL 文本转换为命令对象树。阅读 `Select.java` 时，重点关注 `prepare()` 方法，它调用了 `Optimizer` 并生成执行计划。这个阶段要理解的关键是：SQL → AST → 命令对象 → 执行计划 的转化过程。初次阅读可忽略 `TableFilter` 和 `Plan` 的具体实现细节。

**第三阶段：存储引擎（~1.5 小时）**

7. `MVStore.java` —— 存储引擎入口
8. `MVMap.java` + `Page.java` —— B-Tree 实现
9. `Chunk.java` + 文件存储 —— 磁盘存储
10. `TransactionStore.java` + `TransactionMap.java` —— 事务与 MVCC

**阅读策略**：这是最核心但也是最复杂的阶段。从 `MVStore.java` 的 `open()` 方法开始，理解 Chunk 的分配策略。`MVMap.java` 的 `get()` 和 `put()` 方法展示了 COW B-Tree 的核心逻辑：读取时从根遍历到叶子，写入时复制修改路径上的所有节点。`Page` 类处理页的序列化与反序列化。`TransactionMap` 在 MVMap 之上增加了版本可见性判断——这是 MVCC 的实现核心。初次阅读应关注数据流（get/put）而非控制流（compaction、cache）。

**第四阶段：高级主题（~1 小时）**

11. `Optimizer.java` —— 查询优化
12. `MVTable.java` —— 表锁与并发
13. `CacheLongKeyLIRS.java` —— 缓存算法
14. `MVRTreeMap.java` —— 空间索引

**阅读策略**：这些主题相对独立，可按兴趣选择性阅读。`Optimizer.java` 比了解实现更重要的是理解代价模型的设计思路。`CacheLongKeyLIRS.java` 是 LIRS 算法的工业实现，可与经典 LRU 对比理解其优势。`MVRTreeMap.java` 展示了如何在 B-Tree 架构上叠加 R-Tree 空间索引。

**图 11-5: 各阶段技能图谱（前置要求与收获）**

```text
============================================================

  阶段 1 ──── 前置 ────┬─── 收获 ────
                        │
  Java SE 基础 ──────┐  ├── H2 启动流程与初始化顺序
  JDBC 接口理解 ─────┼──┤── 系统配置体系与参数分类
  基本 SQL 知识 ────┘  ├── 会话管理与事务生命周期
                        │
  ──────────────────────┴────────────────────
                        │
  阶段 2 ──── 前置 ────┬─── 收获 ────
                        │
  编译原理基础 ──────┐  ├── 递归下降解析器的实现
  SQL 语法理解 ──────┼──┤── 命令模式与 Prepared 类体系
  Java 反射 ────────┘  ├── 查询对象模型与执行计划生成
                        │
  ──────────────────────┴────────────────────
                        │
  阶段 3 ──── 前置 ────┬─── 收获 ────
                        │
  数据结构 B-Tree ──┐  ├── COW B-Tree 的工程实现
  事务 ACID 概念 ───┼──┤── Log-Structured 存储机制
  操作系统文件 I/O ─┘  ├── MVCC 事务模型与版本链
                        │
  ──────────────────────┴────────────────────
                        │
  阶段 4 ──── 前置 ────┬─── 收获 ────
                        │
  缓存算法 ─────────┐  ├── LIRS 缓存淘汰算法实现
  空间索引概念 ─────┼──┤── R-Tree 空间索引
  查询优化理论 ────┘  ├── 基于代价的优化 (CBO) 模型
                        │
  ──────────────────────┴────────────────────
```

**图 11-6: 阅读阶段文件依赖与交叉引用图**
============================================================

```text
  阶段 1 ──── 阶段 2 所需的基础知识
  ┌─────────────────────────────────────────────────────────┐
  │ Engine.java  ===>  CommandContainer 使用 Engine.execute │
  │ Database.java ===>  SessionLocal 被 Command 层调用      │
  │ Mode/DbSettings ===> Parser 解析时参考 Mode 兼容规则    │
  └─────────────────────────────────────────────────────────┘

  阶段 2 ──── 阶段 3 所需的基础知识
  ┌─────────────────────────────────────────────────────────┐
  │ Select.java ===>  Index.find() 调用存储引擎             │
  │ TableFilter ===>  访问 Table 和 Index 接口              │
  │ Expression  ===>  列引用最终需要存储引擎提供数据        │
  └─────────────────────────────────────────────────────────┘

  阶段 3 ──── 阶段 4 所需的基础知识
  ┌─────────────────────────────────────────────────────────┐
  │ MVMap/Page  ===>  MVTable 和 Index 的底层存储           │
  │ TransactionMap ==>  MVCC 版本可见性判断逻辑             │
  │ Chunk/Store  ==>  Compaction 和空间回收理解基础         │
  └─────────────────────────────────────────────────────────┘

  阶段 4 ──── 反向理解阶段 2-3 的设计意图
  ┌─────────────────────────────────────────────────────────┐
  │ Optimizer  ===> 重新理解 Select.prepare() 的查询优化    │
  │ CacheLIRS  ===> 重新理解 MVStore 的页缓存行为           │
  │ MVTable    ===> 重新理解 Table 接口与 MVCC 集成         │
  └─────────────────────────────────────────────────────────┘

  如图 11-6 所示，推荐的非线性阅读路径:
  ┌─────────────────────────────────────────────────────────┐
  │ 阶段 1 (宏观) ──> 阶段 2 (SQL) ──> 阶段 3 (存储)       │
  │     │                              │                    │
  │     └──> 阶段 2.5 (测试用例)        └──> 阶段 4 (高级)   │
  │          TestMVMap / TestMVStore        │               │
  │          验证 B-Tree 行为               │               │
  │                                        ▼               │
  │                              阶段 4.5 (动手修改)        │
  │                              修改 ──> 测试 ──> 验证循环 │
  └─────────────────────────────────────────────────────────┘

  关键: ===> "直接引用或调用"    ──> "推荐阅读顺序"

```

## 11.3 调试与测试入口

- **测试目录**: `h2/src/test/`
- **SQL 流程断点入口**: 在 `JdbcStatement.executeQuery()` 设置断点，跟踪 SQL 从 JDBC 到引擎的完整执行路径
- **测试服务器启动**: `org.h2.tools.Server` 的 `main()` 方法，支持 `-tcp`、`-web`、`-pg` 等命令行参数
- **H2 Console 地址**: `http://localhost:8082`（由 `WebServer` 提供服务）

> **参考**: H2 官方文档《Tutorial》(`h2/src/docsrc/html/tutorial.html#command_line_tools`)
> 列出了 H2 提供的全部命令行工具及其用途。

### 11.3.1 测试基础设施层级

```text
本节速览：11.3.1 测试基础设施层级

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```


**图 11-7: 测试金字塔**

```text
============================================================

                     ┌─────────────────────────────┐
                    /                              /\
                   /      E2E 测试 (TestTools)      / \
                  /  TestServer / TestReconnect     /  \
                 /  启动完整服务 → 网络协议测试     /    \
                /──────────────────────────────────/──────\
               /                                  /        \
              /       集成测试 (TestDB)            /          \
             /   TestMVCC / TestTransaction       /            \
            /   多组件交互测试 / 事务+索引协同     /              \
           /──────────────────────────────────────/────────────────\
          /                                    /                  \
         /      单元测试 (TestStore)            /                    \
        /   TestMVStore / TestMVMap / TestPage  /                      \
       /   单一组件算法验证 / B-Tree正确性       /                        \
      /────────────────────────────────────────/──────────────────────────\
     /                                                                    /
    /              基准测试 (TestBench)                                    /
   /    Benchmark / MicroBenchmark / 性能对比                             /
  /______________________________________________________________________/
```

### 11.3.2 调试 H2 Console

```text
本节速览：11.3.2 调试 H2 Console

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


**图 11-8: H2 Console 架构**

```text
============================================================

  浏览器 (http://localhost:8082)
  用户在此输入 SQL, 查看结果
       │
       │ HTTP 请求 ── SQL 字符串
       ▼
  ┌──────────────────────────────────────┐
  │  WebServer (server/web/WebServer.java) │
  │                                      │
  │  ● 提供 Web 管理界面                │
  │  ● 接收 SQL 输入                    │
  │  ● 执行内部 JDBC 连接查询           │
  │  ● 返回 HTML 格式结果               │
  └──────────────┬───────────────────────┘
                 │
                 │ 通过内部 JDBC 连接
                 ▼
  ┌──────────────────────────────────────┐
  │  Engine Layer                        │
  │                                      │
  │  执行 SQL → 返回 ResultSet           │
  │  WebServer 将结果渲染为 HTML 表格    │
  └──────────────────────────────────────┘

  启动方式:
  java -cp h2*.jar org.h2.tools.Server -web
  → 浏览器打开 http://localhost:8082

  调试技巧:
  1. 在 WebServer.update() 设置断点查看接收的 SQL
  2. 在 Engine.execute() 设置断点查看查询执行
  3. 使用 -webAllowOthers 允许远程连接
```

### 11.3.3 端到端断点追踪

**图 11-9: 断点追踪流程图 —— 追踪一条 SQL 的完整生命周期**

```text
============================================================

  断点 1                       断点 2                       断点 3
  ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
  │ JdbcStatement        │    │ CommandContainer     │    │ Prepared.query()     │
  │ executeQuery(String) │───>│ executeQuery()       │───>│                      │
  │                      │    │                      │    │ - 调用 optimize()    │
  │ 输入: SQL 字符串     │    │ 输入: 命令对象        │    │ - 生成执行计划       │
  │ stack: Jdbc → Engine │    │ stack: Command Layer  │    │ - 调用 Index.find()  │
  └──────────────────────┘    └──────────────────────┘    └──────────┬───────────┘
                                                                     │
                             断点 5                    断点 4        │
  ┌──────────────────────┐    ┌──────────────────────┐              │
  │ MVMap.get(Object)    │<───│ MVPrimaryIndex       │<─────────────┘
  │                      │    │ find(Session, ...)   │
  │ - B-Tree 导航        │    │                      │
  │ - 页遍历逻辑         │    │ - 创建 IndexCursor   │
  │ - 二分查找键         │    │ - 调用 MVMap.get()   │
  └──────────┬───────────┘    └──────────────────────┘
             │
             ▼
  ┌──────────────────────┐    ┌──────────────────────┐
  │ TransactionMap       │    │ Page.getLeaf()       │
  │ get(Object)          │<───│                      │
  │                      │    │ - 读取磁盘页         │
  │ - 读取 VersionedValue│    │ - 反序列化条目       │
  │ - 判断事务可见性     │    │ - 返回键值数据       │
  │ - 返回可见版本       │    └──────────────────────┘
  └──────────────────────┘

  关键断点位置速查表:
  ┌──────────────────────┬────────────────────────────┬──────────────────────┐
  │ 断点位置              │ 文件                       │ 用途                 │
  ├──────────────────────┼────────────────────────────┼──────────────────────┤
  │ executeQuery()       │ JdbcStatement.java         │ 追踪 SQL 入口        │
  │ parse()              │ Parser.java                │ 观察 SQL 解析过程     │
  │ optimize()           │ Optimizer.java             │ 查看执行计划选择      │
  │ find()               │ MVPrimaryIndex.java        │ 观察索引查找          │
  │ get()                │ MVMap.java                 │ B-Tree 遍历过程       │
  │ get()                │ TransactionMap.java        │ 事务版本判断          │
  │ write()              │ MVStore.java               │ 观察写入流程          │
  │ compact()            │ MVStore.java               │ 观察 Compaction       │
  └──────────────────────┴────────────────────────────┴──────────────────────┘
```

### 11.3.4 常用调试技巧

如图 11-9 所示，核心调试策略：

**1. 追踪查询执行计划**

在 `JdbcStatement.executeQuery()` 设置断点后，执行一条简单查询并单步进入 `CommandContainer` → `Prepared.query()` → `Select.prepare()`。在 `Optimizer.optimize()` 中可以观察到优化器如何评估不同索引的代价，以及最终选择哪个执行计划。

**2. 调试 MVCC 行为**

在并发场景下，在 `TransactionMap.get()` 中设置断点，观察 `VersionedValue` 的版本链和可见性判断逻辑。关键变量是 `transaction.getStatus()` 和 `VersionedValue.operationId`，它们共同决定当前事务是否可以看到某个版本的数据。

**3. 观察 COW B-Tree 写入**

在 `MVMap.put()` 设置断点，单步执行可以看到：创建新叶子节点 → 向上传播 → 创建新内部节点 → 创建新根 → CAS 更新 `RootReference`。观察前后 `RootReference` 的变化可以直观理解写时复制的机制。

**4. 使用日志**

H2 支持通过 `org.h2.Driver.trace` 开启 JDBC 追踪日志。也可以通过 `DbSettings` 设置 `traceLevel` 为 1-4 分别对应 ERROR、INFO、DEBUG、TRACE 级别，输出详细执行日志。

> 以上调试方法均可在 IDE 中通过条件断点、求值表达式和热替换等标准功能辅助完成。详细的 IDE 操作可参考各 IDE 官方文档，此处不再赘述。

**图 11-10: 关键调试入口速查图**

```text
============================================================

                    ┌─────────────────────────────────────────────┐
                    │     调试目标        断点位置                  │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   SQL 入口 ───────>│ JdbcStatement                              │
                    │  .executeQuery(String)                      │
                    │  参数: 原始 SQL 字符串                       │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   SQL 解析 ───────>│ Parser.parse()                              │
                    │  观察: Token 流构建 AST                      │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   查询优化 ───────>│ Optimizer.optimize()                        │
                    │  观察: 索引选择、代价比较                     │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   B-Tree 查找 ────>│ MVMap.get()                                 │
                    │  观察: 根到叶的二分查找路径                   │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   COW 写入 ───────>│ MVMap.put()                                 │
                    │  观察: 路径复制、CAS 更新根引用               │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   事务可见性 ─────>│ TransactionMap.get()                         │
                    │  观察: 版本链遍历、可见性判断                  │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   存储布局 ───────>│ MVStore.write()                             │
                    │  观察: Chunk 追加、页序列化                   │
                    ├─────────────────────────────────────────────┤
                    │                                             │
   Compaction ─────>│ MVStore.compact()                           │
                    │  观察: Chunk 选择、存活数据重写               │
                    └─────────────────────────────────────────────┘
```

**图 11-11: 断点调试建议步骤**

```text
============================================================

  第 1 步: 设置条件断点
  ┌──────────────────────────────────────────────────────┐
  │ 在 JdbcStatement.executeQuery(String sql) 设置断点    │
  │ 条件: sql.contains("SELECT")  只中断 SELECT 查询      │
  └──────────────────────────────────────────────────────┘

  第 2 步: 使用 Evaluate Expression
  ┌──────────────────────────────────────────────────────┐
  │ 断点暂停时, 通过 Evaluate Expression 可以:            │
  │                                                      │
  │ > session.getTransaction()      查看当前事务          │
  │ > database.getSettings()         查看配置参数          │
  │ > database.getTableOrView(...)   查看表元数据          │
  └──────────────────────────────────────────────────────┘

  第 3 步: 跟踪关键变量
  ┌──────────────────────────────────────────────────────┐
  │ Optimizer.optimize() 中的关键变量:                    │
  │                                                      │
  │  filters:   当前查询涉及的所有 TableFilter            │
  │  bestPlan:  当前最优执行计划                           │
  │  plan.cost: 各计划的估算代价                           │
  │                                                      │
  │ TransactionMap.get() 中的关键变量:                    │
  │                                                      │
  │  vv.versionChain:       版本链长度                    │
  │  transaction.status:    事务提交状态                   │
  │  opId < snapshot:       可见性判断条件                 │
  └──────────────────────────────────────────────────────┘
```

## 11.4 本章小结

如图 11-11 所示，第 11 章提供了系统性的 H2 源码研读指引。11.1 节按功能分类建立了从 JDBC 层到 MVStore 存储引擎的完整文件索引，11.2 节推荐了"宏观 → SQL → 存储 → 高级"的四阶段递进阅读顺序，11.3 节给出了从金字塔测试到断点追踪的实操调试方案。本章的导读路径为第 12 章深入架构权衡和多方向研读奠定了文件级索引基础——有了文件地图和阅读顺序后，读者可以更有针对性地阅读第 12 章中对应方向的深度分析。

---

# 第12章 总结

> **参考**: H2 官方文档《Features》(`h2/src/docsrc/html/features.html#feature_list`)
> 官方完整特性列表，可与本书分析内容对照阅读。

## 12.1 架构设计权衡

H2 在架构层面做出了一系列关键权衡，理解这些取舍有助于深刻把握其设计哲学。本节是对第 6 章各算法（COW B-Tree、Log-Structured 存储、CAS 无锁并发、分层事务模型）的设计权衡所做的总结性对比，建议结合第 6 章对应章节对照阅读。

---

### 12.1.1 权衡一：COW B-Tree vs In-place B-Tree
MVStore 采用写时复制（Copy-on-Write）B-Tree。每次写入创建新的根节点路径，旧版本数据仍然可读，从而天然支持无锁读取和 MVCC。代价是写放大（Write Amplification）较高，每次写入都需要重写从叶子到根的一条完整路径。

**图 12-1: COW B-Tree vs In-place B-Tree 对比**

```text
============================================================

  ┌──────────────────────────────────────────────────────────────┐
  │ 场景: 更新叶子节点 L3 中的键值 (Key=30, 原 Value → 新 Value)  │
  └──────────────────────────────────────────────────────────────┘

  In-place B-Tree (传统方式: SQLite, Derby, HSQLDB)
  ────────────────────────────────────────────────────────────────
      更新前                         更新后
      [R]                           [R]
     /   \                         /   \
  [I1]  [I2]                    [I1]  [I2]
  /  \   /  \                   /  \   /  \
[L1][L2][L3][L4]             [L1][L2][L3'][L4]
              ↑                           ↑
          L3: 旧值                    L3: 同一页被覆写
                                     旧版本数据丢失

  操作: 1 次磁盘 I/O (直接覆写 L3 页)
  并发: 写入时需加锁, 读操作被阻塞
  快照: 无法提供时间点一致性视图

  COW B-Tree (H2 MVStore)
  ────────────────────────────────────────────────────────────────
      更新前                            更新后
      [R]                              [R']  ← 新根
     /   \                            /   \
  [I1]  [I2]                      [I1]  [I2'] ← 新内部节点
  /  \   /  \                     /  \   /  \
[L1][L2][L3][L4]              [L1][L2][L3'][L4]
              ↑                         ↑
          L3: 旧值                   L3': 新叶子页
          (仍然可读)                  [R─I2─L3'] 是新路径

  操作: 3 次磁盘 I/O (L3' + I2' + R')
  并发: 读操作无锁, 仍可读 [R─I2─L3] 旧路径
  快照: 旧根 [R] 提供时间点一致性视图

  写放大分析:
  ─────────────
  B-Tree 高度 = h, 每次写入创建 h+1 个新页 (h 层内部节点 + 1 叶子)
  当 h=3 时, 写放大因子 = 4x (写 1 页数据, 消耗 4 页物理 I/O)

  但 COW 的优势:
  • 无需 Write-Ahead Log (WAL) —— B-Tree 本身提供崩溃一致性
  • 无锁读 —— 读性能不随写入负载下降
  • 天然支持 MVCC —— 旧版本按时间保留
  • 备份可直接使用文件快照 —— 无需特殊备份工具
```

如图 12-1 所示，**技术深度分析**：

COW B-Tree 与 In-place B-Tree 的根本区别在于对"更新"这一操作的处理方式。In-place B-Tree 遵循传统的数据库页面模型：定位到目标页 → 加锁 → 读取页到内存 → 修改 → 写回磁盘。这个过程需要 Write-Ahead Log (WAL) 保证原子性——如果写回过程中系统崩溃，WAL 用于回滚或重做。

COW B-Tree 则完全不同。当更新发生时，MVMap 不会修改现有页，而是分配新页写入新数据，然后创建从新叶子到新根的完整路径。旧路径的数据不受影响，后续读操作如果持有旧根引用，仍然可以读取到更新前的数据。这带来几个重要特性：

1. **崩溃恢复简化**：不需要 WAL。如果写入新路径的过程中系统崩溃，旧根引用仍然有效且完整。下次启动时只需读取最后一个有效的根引用即可恢复到一致状态。

2. **快照隔离**：每个事务在开始时读取当前根引用，之后即使其他事务修改了数据，该事务始终通过自己的根引用看到一致的数据集——完全不需要锁。

3. **写放大**：这是 COW 的主要代价。对于高度为 3 的 B-Tree，一次叶子页更新需要额外写入 3 个内部节点页。不过 H2 通过批量提交和 Chunk 级的顺序追加写入缓解了这个问题——多个写入的路径节点在同一个 Chunk 中连续分配，将随机小 I/O 合并为顺序大 I/O。

4. **空间回收**：旧版本数据不会被立即删除。当不再需要旧版本时（事务结束、无活跃事务引用），通过 Compaction 过程回收空间。这需要额外的 GC 机制。

**图 12-2: COW B-Tree 写入放大随时间的变化**

```text
============================================================

  初始状态 (空数据库):
  ┌─────────────────────────────────────────────────────┐
  │ 写入 1000 条记录:                                    │
  │                                                     │
  │  第 1 次写入: 创建根节点 (h=1, 写放大=1x)              │
  │  第 10 次写入: 叶子满, 分裂 (h=2, 写放大=2x)          │
  │  第 50 次写入: 内部节点满, 分裂 (h=3, 写放大=3x)      │
  │  第 100 次写入: 稳定状态 (h=3, 写放大=4x)             │
  │                                                     │
  │  稳定后每次写入: 1 叶子 + 3 内部节点 = 4 页写入       │
  └─────────────────────────────────────────────────────┘

  写放大因子与 B-Tree 高度的关系:
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  高度 h=2  每次写入: L + I  = 2 页   放大 2x         │
  │  高度 h=3  每次写入: L + I1+I2 = 3 页  放大 3x      │
  │  高度 h=4  每次写入: L + I1+I2+I3 = 4 页  放大 4x    │
  │  高度 h=5  每次写入: L + I1+I2+I3+I4 = 5 页 放大 5x  │
  │                                                     │
  │  放大因子 = h (B-Tree 高度)                          │
  │  写放大 = 写入物理页数 / 逻辑数据页数                 │
  └─────────────────────────────────────────────────────┘

  批量提交降低有效放大:
  ┌─────────────────────────────────────────────────────┐
  │ 单条提交:                                           │
  │  1 次 UPDATE → 1 数据页 + 3 内部页 = 4 页 I/O       │
  │  放大: 4x                                           │
  │                                                     │
  │ 批量提交 (100 条):                                   │
  │  100 次 UPDATE → 共享内部页修改                       │
  │  约 100 数据页 + 3 内部页 = 103 页 I/O               │
  │  平均放大: ~1.03x (接近理想值)                       │
  │                                                     │
  │ 结论: 写入负载越大, 批量提交效果越好                   │
  │ MVStore 默认在事务提交时批量刷新                      │
  └─────────────────────────────────────────────────────┘
```

---

### 12.1.2 权衡二：Log-structured + Chunk vs Traditional Page Store
如图 12-2 所示，MVStore 采用日志结构合并（Log-structured）方式，数据顺序追加写入 Chunk，而非传统数据库的随机覆写页面模型。优点是写吞吐量高、磁盘友好、自然的碎片回收（Compaction）。缺点是垃圾回收（GC）机制更复杂，需要维护 Chunk 的有效性和存活数据追踪。

**图 12-3: Log-Structured vs Traditional Page Store 写入对比**

```text
============================================================

  Traditional Page Store (随机覆写模型)
  ────────────────────────────────────────────────────────────────
  写入请求: UPDATE accounts SET balance=1500 WHERE id=42

          ┌──定位页──┐
          │           │
          ▼           │
  磁盘: [Page 1] [Page 2] [Page 3] [Page 4] [Page 5] ...
                    ↑
              随机寻道 → 定位到 Page 3
              读取 → 修改 → 随机写回

  I/O 模式: 随机读 + 随机写
  寻道时间: 每次写入 ~5-10ms 寻道
  并发写入: 多个写入线程竞争磁盘, 寻道冲突加剧
  碎片化: 频繁的原地更新导致页内碎片

  Log-Structured (H2 MVStore, 顺序追加模型)
  ────────────────────────────────────────────────────────────────
  写入请求: UPDATE accounts SET balance=1500 WHERE id=42

  磁盘文件布局:
  ┌──────────┬──────────┬──────────┬──────────┬──────────┐
  │ Chunk 1  │ Chunk 2  │ Chunk 3  │ Chunk 4  │ Chunk 5  │← 当前写位置
  └──────────┴──────────┴──────────┴──────────┴──────────┘
                                                    ↑
                                             顺序追加写入
                                             (无需寻道)

  ——— 时间线 ———
  请求 1: 顺序追加到 Chunk 5 末尾
  请求 2: 继续追加到 Chunk 5 末尾
  请求 3: 继续追加到 Chunk 5 末尾
  批量写入: 一次 fsync 提交多个写入

  I/O 模式: 顺序写, 随机读
  写入吞吐: 可达随机写的 10-100 倍
  写入聚合: 多个小写入合并为连续大 I/O

  Compaction 过程:
  ┌──────────────────────────────────────────────────────┐
  │ Chunk 1 (50% 存活)                                   │
  │ Chunk 2 (30% 存活)          Compaction               │
  │ Chunk 3 (80% 存活)  ─────────────────>  Chunk 6     │
  │ Chunk 4 (20% 存活)         合并存活数据               │
  │ Chunk 5 (当前写)                                      │
  └──────────────────────────────────────────────────────┘

  Compaction 读取 Chunk 1-4 中存活的数据,
  顺序写入新的 Chunk 6, 然后回收 Chunk 1-4 的空间
```

如图 12-3 所示，**技术深度分析**：

Log-Structured 存储受启发于 LSM-Tree (Log-Structured Merge-Tree) 的设计思想，但与 LevelDB/RocksDB 等纯 LSM 实现有所不同。H2 的 MVStore 采用"页级日志结构"——写入的单位是完整的 B-Tree 页（而非单独的键值对），这些页按写入顺序连续存储在 Chunk 中。

**与传统 Page Store 的核心差异**：

1. **写入模式**：传统数据库使用 Buffer Pool 管理脏页，后台线程随机写回各个页面。这导致磁盘寻道成为瓶颈。H2 的 MVStore 将所有写入聚合并顺序追加——即使更新的是不同 B-Tree 的不同页面，这些修改也被连续写入当前 Chunk。

2. **读取模式**：Log-Structured 的读取是随机的——数据页分散在文件各处的 Chunk 中。H2 通过 `CacheLongKeyLIRS` 缓存热点页减轻随机读的影响。LIRS 算法比 LRU 更好地抵抗扫描污染。

3. **空间放大**：Log-Structured 存储的新数据总是追加写入，旧版本数据不会被立即覆盖。空间放大率 = 磁盘占用 / 实际数据大小。H2 通过 Compaction 控制空间放大率在 1.2-1.5x 左右，Compaction 触发阈值和策略由 `MVStore` 的配置参数控制。

4. **Compaction 策略**：MVStore 的 Compaction 选择"存活率低"的 Chunk 进行合并。存活率 = Chunk 中仍被引用的数据比例。当一个 Chunk 中大部分数据已被更新或删除（即成为"垃圾"），Compaction 将该 Chunk 中剩余的存活数据读取出来，写入新的 Chunk，然后回收原 Chunk 的空间。这与 Java GC 中的"复制收集器"非常相似。

5. **写放大权衡**：
   - COW B-Tree 写放大：~4x （来自 B-Tree 路径复制）
   - Log-Structured 写放大：~1.1-1.3x （来自 Compaction 重写）
   - 总写放大 = COW 写放大 × Log-Structured 写放大 ≈ 4-6x
   - 相比 In-place B-Tree（写放大 ~1x）确实更高
   - 但写放大并非纯代价——它换来了无锁读和快照隔离

6. **恢复时间**：Log-Structured 存储崩溃恢复只需要扫描 Chunk 列表找到最后一个有效根引用，通常可以在毫秒级完成。传统 Page Store 需要重放 WAL，恢复时间与 WAL 大小成正比。

**图 12-4: MVStore Compaction 生命周期**

```text
============================================================

  ┌───────────────────────────────────────────────────────────────┐
  │ Chunk 状态转换图                                               │
  │                                                               │
  │     创建                 数据写入              旧数据失效       │
  │  ┌────────┐    ┌──────────────────┐    ┌──────────────────┐    │
  │  │ FREE   │    │   ACTIVE         │    │   OBSOLETE       │    │
  │  │ 空闲   │───>│  活跃 (可读可写)  │───>│  废弃 (等待回收)  │    │
  │  └────────┘    └──────────────────┘    └──────────────────┘    │
  │                      │                         │               │
  │                      │ Chunk 写满              │ 存活率低于阈值  │
  │                      ▼                         ▼               │
  │  ┌────────┐    ┌──────────────────┐    ┌──────────────────┐    │
  │  │ FREE   │<───│   RECLAIMED      │<───│  COMPACTING     │    │
  │  │ 空闲   │    │   已回收空间      │    │   正在合并       │    │
  │  └────────┘    └──────────────────┘    └──────────────────┘    │
  │                                                               │
  │ Compaction 触发条件:                                           │
  │ ┌───────────────────────────────────────────────────────────┐  │
  │ │  活跃 Chunk 数量超过阈值 (默认: 40)                        │  │
  │ │  文件空闲空间比例超过阈值 (默认: 20%)                       │  │
  │ │  显式调用 SHUTDOWN COMPACT 或 MVStore.compact()           │  │
  │ └───────────────────────────────────────────────────────────┘  │
  │                                                               │
  │ Compaction 选择策略:                                           │
  │ ┌───────────────────────────────────────────────────────────┐  │
  │ │ 优先选择存活率最低的 Chunk 进行合并                         │  │
  │ │ 存活率 = Chunk 中仍被引用的数据大小 / Chunk 总大小           │  │
  │ │ 例如: Chunk 存活率 20% → 重写 20% 数据, 回收 80% 空间      │  │
  │ └───────────────────────────────────────────────────────────┘  │
  └───────────────────────────────────────────────────────────────┘
```

---

### 12.1.3 权衡三：Single Writer CAS vs Read-Write Locks
如图 12-4 所示，MVStore 使用单个写入线程配合 CAS（Compare-And-Swap）更新 RootReference，实现读操作的无锁并发。读取完全无需加锁，写入通过原子操作切换 B-Tree 根引用。这种模型在读多写少的场景下性能极佳，但写入吞吐受限于单线程瓶颈。

**图 12-5: CAS + Single Writer vs Read-Write Locks 并发模型**

```text
============================================================

  Read-Write Locks (传统方式)
  ────────────────────────────────────────────────────────────────

    时间 ──────────────────────────────────────────────────────►
  读线程A: [获得读锁] 读取数据 [释放读锁]      [获得读锁] 读取 [释放]
  读线程B:    [获得读锁] 读取数据 [释放读锁]         [等待写锁] ...
  写线程C:                      [等 待 读 锁 释 放][获得写锁]写入[释放]
                              ↑ 读操作阻塞写操作         ↑ 写操作阻塞读操作

  问题: 读写互斥, 写操作延迟敏感, 高并发下锁竞争严重

  CAS + Single Writer (H2 MVStore)
  ────────────────────────────────────────────────────────────────

    时间 ──────────────────────────────────────────────────────►
  读线程A: [读取旧RootRef]遍历B-Tree... [继续读]               [读取新RootRef]
  读线程B: [读取旧RootRef]遍历B-Tree...                        [读取新RootRef]
  写线程C:              [构建新路径] [CAS]     [构建新路径] [CAS]
                                   成功                        成功

  写线程内部:
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. 读取当前 RootReference (R_old)                           │
  │ 2. 在内存中构建新 B-Tree 路径 (叶子→内部→新根 R_new)        │
  │ 3. 将修改顺序写入当前 Chunk                                 │
  │ 4. CAS(rootRef, R_old, R_new)                              │
  │    - 如果 rootRef 仍指向 R_old: 成功, R_new 生效            │
  │    - 如果 rootRef 已被其他线程修改: 重试整个流程             │
  │ 5. 旧 R_old 路径上的数据仍然可读                             │
  └─────────────────────────────────────────────────────────────┘

  CAS 实现的关键代码 (简化伪代码):
  ┌─────────────────────────────────────────────────────────────┐
  │ RootReference current = rootReference.getVolatile();        │
  │ // ... 构建新根, 写入数据 ...                                │
  │ RootReference newRoot = buildNewRoot(current);              │
  │ boolean success = rootReference.compareAndSet(current, newRoot);│
  │ if (!success) {                                             │
  │     // CAS 失败, 重试整个写入流程                             │
  │     retry();                                                 │
  │ }                                                            │
  └─────────────────────────────────────────────────────────────┘
```

如图 12-5 所示，**技术深度分析**：

**Read-Write Locks 模型**是传统数据库的经典并发控制方式。多个读取者可以同时获取读锁（共享），但写入者必须等待所有读锁释放后才能获取写锁（独占）。读操作的性能受限于锁的开销和竞争。在高并发读的场景下，锁竞争会导致吞吐量下降，而且锁的公平性设置（公平锁 vs 非公平锁）会显著影响尾延迟。

**CAS + Single Writer 模型**是 H2 MVStore 的核心创新。其本质是将"读写冲突"转化为"写写冲突"：

1. **无锁读**：读操作读取 `RootReference` 引用（通过 `getVolatile()` 或 `getAcquire()` 保证可见性），然后遍历该根指向的 B-Tree。读取过程中完全不需要获取任何锁。多个读线程可以并行执行，互不干扰。

2. **Single Writer**：虽然只有一个写入线程，但这个线程不需要等待读操作。写入线程在内存中构建新的 B-Tree 路径，完成后通过一次 CAS 操作将根引用切换到新路径。如果 CAS 失败（意味着其他写入已经改变了根引用），写入线程只需读取新根引用后重新构建路径。

3. **无阻塞的读**：这是最关键的特性——读操作永远不会因为写入而阻塞。读操作看到的是 CAS 之前或之后的根引用，无论哪种情况都是一致且完整的数据视图。这消除了读写互斥带来的性能波动。

4. **性能数据分析**：
   - 纯读负载：CAS 模型 ≈ 无锁读，吞吐量接近硬件极限
   - 读多写少（95% 读, 5% 写）：CAS 模型的吞吐量是 RW Lock 模型的 2-5 倍
   - 写密集（50% 写）：RW Lock 可能因为读写竞争导致更大延迟波动
   - 纯写负载：Single Writer 退化为单线程，但 RW Lock 的写操作也需要加锁

5. **局限性**：
   - Single Writer 成为写入瓶颈——无法利用多核并行写入
   - CAS 失败重试机制在极端竞争下可能导致活锁（实际中极少见）
   - 写操作的内存分配更频繁（需要创建新对象），增加 GC 压力

---

### 12.1.4 权衡四：事务索引（TransactionMap） vs 纯 B-Tree 遍历
H2 将版本链存储在 Value 中，通过 TransactionMap 层实现事务可见性判断，而非在 B-Tree 节点内嵌入事务信息。这种分层设计使存储引擎（MVMap）与事务语义解耦，代价是事务读需要额外的版本比较开销。

**图 12-6: TransactionMap 分层 vs 嵌入式版本链**

```text
============================================================

  方案 A: 嵌入式版本链 (在 B-Tree 节点内嵌入事务信息)
  ────────────────────────────────────────────────────────────────

  B-Tree 直接存储带版本的数据，遍历时同时完成版本判断:

  Page 叶子节点:
  ┌──────┬──────────────────────────────────────────────────┐
  │ Key  │ Value (带事务信息)                                 │
  ├──────┼──────────────────────────────────────────────────┤
  │ 1    │ (value=v1, tx=1, status=committed)               │
  │ 2    │ (value=v2, tx=2, status=committed)               │
  │ 3    │ (value=v3, tx=3, status=committed)                │
  │      │ (value=v3', tx=5, status=pending)  ← 未提交版本   │
  │ 4    │ (value=v4, tx=4, status=committed)                │
  └──────┴──────────────────────────────────────────────────┘

  优点: 单次遍历同时完成数据查找和版本判断
  缺点: 存储引擎与事务语义耦合, 无法独立测试
        增加新的隔离级别需要修改存储引擎

  方案 B: TransactionMap 分层 (H2 采用)
  ────────────────────────────────────────────────────────────────

  ┌─────────────────────────────────────────────────────────────┐
  │ 事务层: TransactionMap                                      │
  │                                                             │
  │  get(key) {                                                 │
  │      // 1. 从下层读取 VersionedValue                        │
  │      VersionedValue vv = map.get(key);                      │
  │      // 2. 遍历版本链, 找到当前事务可见的版本               │
  │      for (Entry e : vv.versionChain) {                      │
  │          if (isVisible(e.txId, e.opId)) {                    │
  │              return e.value;                                 │
  │          }                                                   │
  │      }                                                       │
  │      // 3. 无可见版本 → 等同于未找到                       │
  │      return null;                                            │
  │  }                                                           │
  │                                                             │
  │  // 可见性判断逻辑:                                          │
  │  isVisible(txId, opId) {                                    │
  │      if (txId == currentTx) return true;    // 自己可见      │
  │      if (isCommitted(txId) &&                               │
  │          opId < snapshot) return true;     // 已提交且早于快照│
  │      return false;                                           │
  │  }                                                           │
  └──────────────────────────┬──────────────────────────────────┘
                             │ 委托存储
                             ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 存储层: MVMap (纯 B-Tree, 无事务概念)                       │
  │                                                             │
  │  - 只存储键值对 (Key → VersionedValue)                      │
  │  - 不知道事务、隔离级别、版本链的存在                        │
  │  - 可以被独立测试 (不需要启动事务系统)                       │
  │  - 专注: 持久化、缓存、B-Tree 遍历                           │
  └─────────────────────────────────────────────────────────────┘

  VersionedValue 版本链结构:
  ┌─────────────────────────────────────────────────────────────┐
  │ 单个 Key 的版本链 (按操作ID降序排列):                        │
  │                                                             │
  │  current ──> +──+──────+──────+────────+                   │
  │              │v3│ tx=3 │op=5  │committed│   ← 最新版本       │
  │              +──+──────+──────+────────+                   │
  │                  ↓                                          │
  │              +──+──────+──────+────────+                   │
  │              │v2│ tx=2 │op=3  │committed│                    │
  │              +──+──────+──────+────────+                   │
  │                  ↓                                          │
  │              +──+──────+──────+────────+                   │
  │              │v1│ tx=1 │op=1  │committed│   ← 最旧版本       │
  │              +──+──────+──────+────────+                   │
  │                                                             │
  │ 每次更新创建一个新的版本链头:                                  │
  │  UPDATE → VersionedValue(新值, 当前事务ID, 递增操作ID)       │
  │  旧版本仍然是链的一部分, 通过指针引用                         │
  └─────────────────────────────────────────────────────────────┘

  TransactionMap 可见性判断示例:
  ┌─────────────────────────────────────────────────────────────┐
  │ 事务 T4 读取 Key=3:                                         │
  │                                                             │
  │  版本链: v3(tx=3) → v2(tx=2) → v1(tx=1)                   │
  │                                                             │
  │  T4 的可见性规则:                                            │
  │  1. v3: tx=3 != T4, 检查提交状态 → 已提交                    │
  │  2. op=5, T4 的快照点是 op=7                                │
  │  3. op=5 < 7 → 可见! 返回 v3                                │
  │                                                             │
  │  T5 (未提交事务) 读取 Key=3:                                 │
  │  版本链: v3(tx=3) → v2(tx=2) → v1(tx=1)                   │
  │  1. v3: tx=3 != T5, 检查提交状态 → 已提交                    │
  │  2. 返回 v3 (与 T4 相同结果)                                │
  └─────────────────────────────────────────────────────────────┘
```

如图 12-6 所示，**技术深度分析**：

**分层设计的哲学**：TransactionMap + MVMap 的分层设计遵循了"关注点分离"（Separation of Concerns）原则。MVMap 职责单一——它只负责键值对的持久化存储和 B-Tree 遍历，不知道事务的概念。TransactionMap 在 MVMap 之上增加事务语义层，处理可见性判断、版本链遍历和隔离级别实现。这种分层的直接好处是：

1. **可测试性**：MVMap 可以被独立测试，无需初始化事务系统。测试用例更简单、执行更快。

2. **可替换性**：如果未来需要改变事务模型（比如增加新的隔离级别），只需要修改 TransactionMap 层，无需改动 MVMap。

3. **代码清晰度**：每个文件的责任边界清晰，新的贡献者可以快速定位所需修改的组件。

**版本链的性能开销**：

TransactionMap 的额外开销主要来自两个方面：

1. **版本链遍历**：每次读取可能需要遍历多个版本才能找到可见的条目。在长事务或频繁更新的键上，版本链可能变得很长。H2 通过 Compaction 清理不再需要的旧版本，控制链长度。

2. **额外的间接调用**：每次 get/put 操作都经过 TransactionMap → MVMap 的委托调用。这增加了一层方法调用开销（尽管 JIT 可以内联）。

实测表明，在典型 OLTP 工作负载下（短事务、点查），TransactionMap 的开销在 5-15% 之间，相对于分层设计带来的可维护性收益是可以接受的。

**与嵌入式版本链的对比**：

嵌入式版本链（如在 PostgreSQL 的 Heap Tuple 中嵌入事务信息）可以减少间接层开销，但代价是存储引擎必须理解事务语义。这意味着：
- 存储引擎的测试必须包含事务设置
- 修改事务模型需要改动存储引擎代码
- 存储格式与事务版本格式耦合，升级困难

H2 的分层选择代表了"可维护性优先"的设计哲学——在嵌入式数据库的场景中，代码清晰度比极致的性能更重要。

---

## 12.2 H2 与其他数据库的设计差异

**图 12-7: 多维能力对比 (1-5 分, 分数越高越强)**

```text
============================================================

  ┌─────────────────────────────────────────────────────────────────┐
  │                  SQL 兼容性 (ANSI + 方言模拟)                    │
  │  H2     ████████████████████████████████████████████████████  5 │
  │  SQLite ██████████████████                                   2 │
  │  Derby  ████████████████████████████                         3 │
  │  HSQLDB ████████████████████████████                         3 │
  ├─────────────────────────────────────────────────────────────────┤
  │                    并发能力 (无锁读/高并发)                      │
  │  H2     ████████████████████████████████████████████████████  5 │
  │  SQLite ██████                                               1 │
  │  Derby  ████████████████████████████                         3 │
  │  HSQLDB ████████████████████████████                         3 │
  ├─────────────────────────────────────────────────────────────────┤
  │                  存储引擎先进性 (COW/LSM)                       │
  │  H2     ████████████████████████████████████████████████████  5 │
  │  SQLite ██████████████████                                   2 │
  │  Derby  ██████████████████                                   2 │
  │  HSQLDB ██████████████████                                   2 │
  ├─────────────────────────────────────────────────────────────────┤
  │                   网络协议丰富度 (JDBC+PG+Web)                  │
  │  H2     ████████████████████████████████████████████████████  5 │
  │  SQLite ██                                                   1 │
  │  Derby  ████████████████████████████                         3 │
  │  HSQLDB ████████████████████████████                         3 │
  ├─────────────────────────────────────────────────────────────────┤
  │                   嵌入灵活性 (嵌入/服务器双模式)                │
  │  H2     ████████████████████████████████████████████████████  5 │
  │  SQLite ████████████████████████████████████                 4 │
  │  Derby  ████████████████████████████                         3 │
  │  HSQLDB ████████████████████████████████████                 4 │
  ├─────────────────────────────────────────────────────────────────┤
  │                  文件加密安全 (AES/XTS 透明加密)                 │
  │  H2     ████████████████████████████████████████████████████  5 │
  │  SQLite ████████████████████████████                         3 │
  │  Derby  ██                                                   1 │
  │  HSQLDB ████████████████████████████                         3 │
  ├─────────────────────────────────────────────────────────────────┤
  │                    内存模式支持 (纯内存运行)                    │
  │  H2     ████████████████████████████████████████████████████  5 │
  │  SQLite ██                                                   1 │
  │  Derby  ██                                                   1 │
  │  HSQLDB ████████████████████████████████████████████████████  5 │
  ├─────────────────────────────────────────────────────────────────┤
  │                    体积轻量 (JAR 文件大小)                      │
  │  H2     ████████████████████████████████████                 4 │
  │  SQLite ████████████████████████████████████████████████████  5 │
  │  Derby  ████████████████████████████                         3 │
  │  HSQLDB ████████████████████████████████████                 4 │
  └─────────────────────────────────────────────────────────────────┘
```
> 如图 12-7 所示，以上评分基于各数据库在所列维度上的特性支持度评估，仅供参考，不代表数据库整体质量的综合排名。

| 特性 | H2 | SQLite | Derby | HSQLDB |
|------|-----|--------|-------|--------|
| 存储引擎 | MVStore（COW B-Tree） | B-Tree（in-place） | B-Tree | B-Tree |
| 并发模型 | MVCC + CAS 无锁读 | 粗粒度锁 | MVCC | MVCC |
| 事务隔离 | 5 级（RC/RR/Snapshot/Serializable/ReadUncommitted） | Serializable | Read Committed | 多级 |
| SQL 兼容 | ANSI + Oracle/PG/MySQL/MSSQL | 有限 | ANSI | ANSI |
| 网络协议 | JDBC + PG Wire + Web | 无 | JDBC | JDBC + Web |
| 嵌入/服务器 | 双模式 | 纯嵌入 | 双模式 | 双模式 |
| 内存模式 | 全内存 | 无 | 无 | 全内存 |
| 文件加密 | AES/XTS 透明加密 | 内置加密 | 无 | AES |
| 体积 | ~2MB | ~1MB | ~3MB | ~1.5MB |

**图 12-8: 四大嵌入式数据库架构并排对比**

```text
============================================================

  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │     H2       │  │   SQLite     │  │   Derby      │  │   HSQLDB     │
  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  JDBC 驱动   │  │  C 原生 API  │  │  JDBC 驱动   │  │  JDBC 驱动   │
  │  PG Wire     │  │  (sqlite3.h) │  │              │  │  Web 服务    │
  │  Web Console │  │              │  │              │  │              │
  ├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤
  │  SQL Parser  │  │  SQL Parser  │  │  SQL Parser  │  │  SQL Parser  │
  │  Oracle/PG/  │  │  标准 SQL    │  │  ANSI SQL    │  │  ANSI SQL    │
  │  MySQL/MSSQL │  │  有限扩展    │  │  无方言模拟  │  │  基本扩展    │
  ├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤
  │  MVStore     │  │  B-Tree      │  │  B-Tree +    │  │  B-Tree +    │
  │  COW B-Tree  │  │  in-place    │  │  Page Cache  │  │  Page Cache  │
  │  Log-Struct  │  │  Pager       │  │  传统页面    │  │  传统页面    │
  │  Compaction  │  │  WAL 模式    │  │  存储        │  │  存储        │
  ├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤
  │  CAS 无锁    │  │  粗粒度锁    │  │  锁 + MVCC   │  │  锁 + MVCC   │
  │  Single Wr.  │  │  读写互斥    │  │  行级锁      │  │  表级/行级锁 │
  │  + MVCC      │  │  低并发      │  │  中等并发    │  │  中等并发    │
  ├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤
  │  内存模式    │  │  纯磁盘      │  │  纯磁盘      │  │  内存模式    │
  │  文件加密    │  │  内置加密    │  │  无加密      │  │  AES 加密    │
  │  多版本快照  │  │  Serializable│  │  RC 隔离     │  │  多级隔离    │
  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

如图 12-8 所示，针对上述差异的详细说明：

**存储引擎**：H2 的 MVStore 是唯一采用 COW（Copy-on-Write）B-Tree 的嵌入式数据库。SQLite、Derby、HSQLDB 均使用就地更新（in-place update）B-Tree，写入时直接修改磁盘页面。COW 的优势在于无锁读和快照隔离，劣势在于写入放大和空间占用。SQLite 的 B-Tree 实现经过了近 25 年的优化，在单用户场景下性能极为稳定，但其粗粒度锁限制了并发能力。Derby 的 B-Tree 实现相对传统，源自 Apache Cloudscape（原 IBM 产品）。HSQLDB 的 B-Tree 实现较为简单，主要面向内存模式优化。

**并发模型**：H2 的 CAS 无锁读是其显著特色，读取完全不需要获取锁，通过原子操作读取 B-Tree 根引用即可获得一致快照。SQLite 使用粗粒度锁（整个数据库级别的读写锁），并发能力有限——虽然 WAL 模式缓解了读写互斥，但写操作之间仍然互斥。Derby 和 HSQLDB 使用传统锁机制实现 MVCC，读操作通常不会阻塞写，但锁管理开销较大。

**事务隔离**：H2 提供完整的 5 级隔离支持，包括 Oracle 风格的多版本读一致性（Snapshot Isolation）和 Serializable。SQLite 因为写操作互斥，只有 Serializable 级别可用——实际上在高隔离级别下通过串行化写操作实现。Derby 默认使用 Read Committed，也支持 Repeatable Read 和 Serializable，但不提供 Read Uncommitted 和 Snapshot Isolation。HSQLDB 提供多级隔离支持，但不同隔离级别的实现细节与 H2 有所不同。

**SQL 兼容**：H2 以其丰富的 SQL 兼容模式闻名，可以模拟 Oracle、PostgreSQL、MySQL、MSSQL 等数据库的方言特性，包括函数名差异、数据类型映射、语法扩展等。这极大地降低了数据库迁移的成本。SQLite 的 SQL 兼容性是所有主流数据库中最弱的——不支持 RIGHT/FULL OUTER JOIN、ALTER TABLE 能力有限、不支持 CHECK CONSTRAINT 强制执行等。Derby 和 HSQLDB 主要面向 ANSI SQL 标准兼容，不提供方言模拟。

**网络协议**：H2 独有地支持 PostgreSQL Wire Protocol（PgServer），使得 PostgreSQL 客户端可以直接连接到 H2。同时提供 JDBC 原生协议和 Web Console，是协议支持最丰富的嵌入式数据库。SQLite 本质上是嵌入式 C 库，不直接支持网络协议——需要借助第三方封装（如 sql.js、LiteStream）。Derby 支持 JDBC 网络服务端模式，HSQLDB 支持 JDBC 和 HTTP 服务，但两者都不支持 PG Wire 协议。

**内存模式**：H2 和 HSQLDB 支持纯内存运行模式，数据不持久化到磁盘，适用于测试和临时计算场景。H2 的内存模式通过 `jdbc:h2:mem:test` URL 启用，完全在内存中创建数据库，关闭后数据丢失。SQLite 通过 `:memory:` 支持内存数据库，但不支持内存模式和磁盘模式的混合。Derby 不具备纯内存模式，必须使用磁盘存储。

**文件加密**：H2 提供 AES/XTS 透明加密，通过 `jdbc:h2:~/test;CIPHER=AES` 启用，无需修改应用代码即可实现数据库文件的静态加密。XTS 模式比传统的 CBC 模式更适合磁盘加密，因为它支持随机访问（每个 16 字节块独立加解密）。SQLite 的 SQLCipher 扩展提供类似功能但需要额外集成。Derby 不提供内置加密。HSQLDB 支持 AES 加密但加密粒度和实现与 H2 不同。

**体积与部署**：H2 的核心 JAR 约 2MB，包含完整的 SQL 引擎、JDBC 驱动、网络服务和 Web Console。SQLite 的库文件约 1MB，但仅提供 C 语言 API，Java 封装（sqlite-jdbc）需要额外依赖。Derby 约 3MB，功能相对全面但较为臃肿。HSQLDB 约 1.5MB，在体积和功能之间取得了较好的平衡。

---

## 12.3 源码学习价值

**图 12-9: 源码学习路径图 —— 从入门到贡献的四阶段路径**

```text
============================================================

  入口阶段 ───────────────────────────────────────────────────────────┐
  (第 1-2 天)                                                         │
  ┌──────────────────────────────────────────────────────────────────┐│
  │ 目标: 搭建环境, 跑通第一个测试, 建立信心                         ││
  │                                                                  ││
  │ 任务清单:                                                        ││
  │ □ 从 GitHub 克隆项目: git clone https://github.com/h2database/  ││
  │ □ Maven 编译: mvn clean install -DskipTests                      ││
  │ □ 运行第一个测试: mvn test -Dtest=TestMVRTree                    ││
  │ □ IDE 导入: IntelliJ / Eclipse 打开 pom.xml                      ││
  │ □ 启动 H2 Console: 运行 Server.main() → localhost:8082          ││
  │ □ 设置第一个断点: JdbcStatement.executeQuery()                   ││
  └──────────────────────────────────────────────────────────────────┘│
  ────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  理解阶段 ───────────────────────────────────────────────────────────┐
  (第 1-2 周)                                                         │
  ┌──────────────────────────────────────────────────────────────────┐│
  │ 目标: 理解核心组件的设计与实现                                    ││
  │                                                                  ││
  │ 学习重点:                                                        ││
  │ • 使用本节 11.2 的四阶段阅读法系统学习源码                        ││
  │ • 每读完一个阶段, 画一张架构图巩固理解                            ││
  │ • 修改源码 + 运行测试, 验证理解是否正确                          ││
  │ • 在关键方法添加 System.out / 日志输出观察运行行为                ││
  │ • 阅读对应的单元测试理解组件的预期行为                            ││
  └──────────────────────────────────────────────────────────────────┘│
  ────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  深入阶段 ───────────────────────────────────────────────────────────┐
  (第 3-4 周)                                                         │
  ┌──────────────────────────────────────────────────────────────────┐│
  │ 目标: 深入特定模块, 达到修改和优化的能力                          ││
  │                                                                  ││
  │ 可选方向:                                                        ││
  │ ┌────────────────────┐  ┌────────────────────┐                   ││
  │ │ 存储引擎方向        │  │ SQL 引擎方向        │                   ││
  │ │ • 优化 Compaction   │  │ • 增加新 SQL 语法   │                   ││
  │ │ • 改进缓存策略      │  │ • 优化查询优化器    │                   ││
  │ │ • 自定义存储后端    │  │ • 增加新函数/聚合   │                   ││
  │ └────────────────────┘  └────────────────────┘                   ││
  │ ┌────────────────────┐  ┌────────────────────┐                   ││
  │ │ 事务方向            │  │ 协议/集成方向       │                   ││
  │ │ • 优化 MVCC 实现    │  │ • 增加新协议支持    │                   ││
  │ │ • 增加隔离级别      │  │ • 改进 PG 协议兼容  │                   ││
  │ │ • 分布式事务扩展    │  │ • 集成到其他框架    │                   ││
  │ └────────────────────┘  └────────────────────┘                   ││
  └──────────────────────────────────────────────────────────────────┘│
  ────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  贡献阶段 ───────────────────────────────────────────────────────────┐
  (第 1-3 月)                                                         │
  ┌──────────────────────────────────────────────────────────────────┐│
  │ 目标: 参与社区, 贡献代码, 成为贡献者                              ││
  │                                                                  ││
  │ 参与途径:                                                        ││
  │ • GitHub Issues 中标记 "good first issue" 的 Bug                 ││
  │ • H2 邮件列表 / GitHub Discussions 中讨论设计                     ││
  │ • 提交 Pull Request, 遵循项目的代码风格和测试要求                  ││
  │ • 编写或改进测试用例, 提升测试覆盖率                              ││
  │ • 参与 Code Review, 学习其他贡献者的设计思路                      ││
  └──────────────────────────────────────────────────────────────────┘│
  ────────────────────────────────────────────────────────────────────┘
```

如图 12-9 所示，- **完整的数据库引擎实现**：H2 是纯 Java 实现的完整关系数据库，涵盖 SQL 解析、查询优化、存储引擎、事务管理、JDBC 驱动、网络服务等所有核心组件（详见第1章《总体架构》和第2章《分层模块划分》）。研读其源码可以系统性地掌握数据库内核的工作原理。与 PostgreSQL 或 MySQL 的 C 语言源码相比，H2 的 Java 源码可读性更强，没有指针操作和手动内存管理的复杂性，更适合作为学习数据库实现的入门读物。

- **工业级算法的参考实现**：MVCC、COW B-Tree、LIRS 缓存淘汰算法、查询优化器、基于代价的优化（CBO）等数据库核心技术（详见第6章《H2 数据库核心算法分析》），在 H2 中都有高质量的实现。这些代码是理论算法走向工程实践的绝佳范例——每一行代码都能在经典教材（如《数据库系统概念》、《Transaction Processing》）中找到理论基础。

- **代码质量与可读性**：H2 源码结构清晰，命名规范，注释详尽。单文件内聚性高，核心逻辑通常集中在少数几个文件中，便于调试和追踪。代码量适中（核心引擎约 2MB），是学习大型 Java 项目的理想素材。与同等规模的 Java 项目相比，H2 的抽象层次合理，没有过度设计模式或不必要的接口层次。

- **易于调试与实验**：H2 采用单文件存储格式，无需外部依赖，可以轻松在 IDE 中启动、断点调试、修改实验。配合测试目录中的单元测试和集成测试，可以快速验证对源码的理解。修改源码后只需 `mvn compile -DskipTests` 即可重新编译，无需复杂部署流程。

- **架构演进的历史痕迹**：H2 从 1.x 的 PageStore 引擎演进到 2.x 的 MVStore 引擎（详见第9章《持久化引擎深度解析》和第10章《锁实现与并发控制》），源码中保留了清晰的版本分界和接口抽象。通过对比新旧引擎的实现，可以深入理解数据库存储引擎的演进逻辑和设计取舍——比如为什么从 page-based 转向 log-structured，为什么引入 COW B-Tree 替代 in-place 更新。

**图 12-10: H2 组件到计算机科学概念映射**

```text
============================================================

  ┌─────────────────────────────────────────────────────────┐
  │  H2 源码组件             计算机科学概念                   │
  ├─────────────────────────────────────────────────────────┤
  │                                                         │
  │  command/Tokenizer.java   编译原理: 词法分析             │
  │  command/Parser.java      编译原理: 递归下降解析        │
  │                           ⇒ 如何将文本转换为 AST         │
  │                                                         │
  │  command/query/Optimizer  查询优化:                     │
  │                           • 基于代价的优化 (CBO)        │
  │                           • 索引选择、连接顺序          │
  │                           • 谓词下推、投影消除          │
  │                                                         │
  │  mvstore/MVMap.java      数据结构:                     │
  │  mvstore/Page.java       • B-Tree / B+Tree              │
  │                           • 写时复制 (Copy-on-Write)    │
  │                           • 页分裂与合并                │
  │                                                         │
  │  mvstore/tx/             事务处理:                     │
  │  TransactionStore.java    • ACID、MVCC                  │
  │  TransactionMap.java      • Snapshot Isolation          │
  │  VersionedValue.java       • 版本链、可见性判断           │
  │                                                         │
  │  mvstore/cache/          操作系统: 缓存算法             │
  │  CacheLongKeyLIRS.java    • LIRS vs LRU                 │
  │                           • 缓存准入/淘汰策略           │
  │                           • 缓存污染问题                │
  │                                                         │
  │  mvstore/Chunk.java      存储引擎:                    │
  │  mvstore/FreeSpaceBitSet  • Log-Structured 存储        │
  │                           • LSM-Tree 理论               │
  │                           • 写放大、空间放大            │
  │                           • Compaction / GC             │
  │                                                         │
  │  mvstore/rtree/          空间数据管理:                  │
  │  MVRTreeMap.java          • R-Tree / R+Tree             │
  │                           • 空间范围查询                │
  │                           • 多维索引                    │
  │                                                         │
  │  mvstore/RootReference   并发编程:                     │
  │                           • 无锁数据结构                │
  │                           • AtomicReference + CAS      │
  │                           • volatile 语义和可见性       │
  │                                                         │
  │  mvstore/db/MVTable.java  数据库表模型:                │
  │  mvstore/db/MVPrimaryIndex • 行级锁                     │
  │                           • 索引组织表                  │
  │                           • 多版本并发控制              │
  │                                                         │
  │  command/query/          高级 SQL:                     │
  │  SelectGroups.java        • GROUP BY / 聚合            │
  │  expression/aggregate/    • HAVING 过滤                │
  │                           • 窗口函数 (OVER/PARTITION)  │
  │                                                         │
  │  security/AES.java       密码学:                       │
  │                           • AES 加密算法                │
  │                           • XTS 加密模式               │
  │                           • 透明数据加密 (TDE)         │
  │                                                         │
  │  store/fs/               文件系统抽象:                  │
  │  FilePathDisk.java        • Strategy Pattern            │
  │  FilePathMem.java         • 内存文件系统                │
  │  FilePathEncrypt.java     • 加密文件系统                │
  │                           • 适配器模式                  │
  └─────────────────────────────────────────────────────────┘
```

如图 12-10 所示，**各组件的学习要点详解**：

**SQL 解析层（command/）**：这是理解编译原理的最佳实践入口。`Tokenizer` 演示了如何将 SQL 字符串分解为 Token 流——处理关键字、标识符、数字、字符串、操作符等不同类型的词法单元。`Parser` 使用递归下降解析（Recursive Descent Parsing），为每个 SQL 语法规则（如 SELECT、FROM、WHERE、JOIN）实现一个解析方法。阅读这个模块可以直观理解"语法分析"在真实项目中的应用。与教科书中的表达式解析不同，SQL 解析器需要处理复杂的嵌套结构（子查询、JOIN 链、复杂表达式），这使它的实现更具工程参考价值。

**查询优化器（command/query/Optimizer.java）**：`Optimizer` 实现了基于代价的查询优化。它的核心是评估多个候选执行计划的代价（主要通过 `Plan.cost()` 估算需要扫描的行数），选择代价最小的计划。理解这个组件需要掌握：索引选择性（Index Selectivity）、表基数估计（Cardinality Estimation）、代价模型（Cost Model）等概念。H2 的优化器相对简单（相比 PostgreSQL 或 Oracle 成千上万行的优化器代码），正好适合初学者理解 CBO 的核心思想，而不会被过多细节淹没。

**MVMap COW B-Tree（mvstore/MVMap.java + Page.java）**：这是 H2 存储引擎最核心的数据结构。`MVMap` 提供了类似 `java.util.NavigableMap` 的接口，但底层实现是支持并发的持久化 COW B-Tree。阅读 `get()` 方法可以理解 B-Tree 的查找过程——从根节点开始，在内部节点中通过二分查找找到下一层，直到叶子节点。阅读 `put()` 方法可以理解 COW 的写入过程——复制修改路径上的每个节点。阅读这里的代码可以深入理解《算法导论》中 B-Tree 的插入、删除、分裂、合并等操作在工程实践中如何实现。

**LIRS 缓存（mvstore/cache/CacheLongKeyLIRS.java）**：LIRS（Low Inter-reference Recency Set）是对 LRU（Least Recently Used）的改进算法，能更好地抵抗扫描污染（Scan Resistance）——即大量一次性访问不会将热点数据挤出缓存。H2 的 LIRS 实现是算法论文到工程代码的直接转化。对比理解 LIRS 和 LRU 的差异，可以深入理解缓存替换策略的演进逻辑。

**事务系统（mvstore/tx/）**：`TransactionStore`、`Transaction` 和 `TransactionMap` 共同实现了 MVCC 事务模型。理解这段代码需要掌握：事务 ID 分配、提交日志（Commit Log）、快照隔离（Snapshot Isolation）、可见性规则（Visibility Rules）、写偏斜（Write Skew）等概念。`TransactionMap` 中的 `get()` 和 `put()` 方法是最值得阅读的——它们展示了如何在纯存储引擎之上增加事务语义而不修改下层代码。

**并发编程（RootReference + CAS）**：H2 的 CAS 无锁读机制是多线程编程的经典案例。`RootReference` 使用 `AtomicReference`（或 `VarHandle`) 实现 CAS 更新。读操作通过 `getVolatile()` 获取根引用后遍历 B-Tree，整个过程中读线程之间不存在任何竞争。写线程在构建完新的 B-Tree 路径后通过一次 CAS 原子性地切换根引用。这个设计展示了"无锁数据结构"（Lock-Free Data Structure）如何在实践中实现高并发。

## 12.4 多方向研读指引

前文从架构权衡、对比分析和通用学习路径的角度阐述了 H2 源码的研读方法。然而不同的开发者有着不同的学习目标和背景，采用同一条路径往往事倍功半。本节从四个不同的研读方向出发，为不同目标的读者提供量身定制的源代码阅读指引。

---

### 12.4.1 按学习目标选择阅读路径

```text
本节速览：12.4.1 按学习目标选择阅读路径

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


根据你的实际需求，可以选择以下四条路径之一作为切入点。每条路径都标注了入口类、核心文件和预期时间。

**图 12-11: 四条研读路径总览 —— 根据目标选择入口**

```text
========================================================================

  ┌────────────────────────────────────────────────────────────────────────┐
  │  路径 A: 性能优化方向                                                    │
  │  ┌──────────────────────────────────────────────────────────────────┐  │
  │  │ 目标读者: DBA / SRE / 性能调优工程师                              │  │
  │  │ 关注问题: 慢查询、磁盘 I/O 高、GC 频繁、缓存命中率低             │  │
  │  │ 阅读链: MVStore → Cache → Compaction → Optimizer                │  │
  │  └──────────────────────────────────────────────────────────────────┘  │
  │                                                                        │
  │  入口: MVStore 存储引擎                       mvstore/MVStore.java    │
  │    ├── 缓存策略与 LIRS 算法                 cache/CacheLongKeyLIRS   │
  │    ├── Chunk 管理与 Compaction 机制         mvstore/Chunk.java       │
  │    └── 查询代价估算与执行计划               command/query/Optimizer  │
  │                                                                        │
  │  关键文件: MVStore.java, CacheLongKeyLIRS.java, Chunk.java,           │
  │           FreeSpaceBitSet.java, Optimizer.java                         │
  │  预期: ~5 天掌握性能分析工具链                                        │
  ├────────────────────────────────────────────────────────────────────────┤
  │  路径 B: 功能扩展方向                                                    │
  │  ┌──────────────────────────────────────────────────────────────────┐  │
  │  │ 目标读者: SQL 引擎开发者 / 数据库定制团队                         │  │
  │  │ 关注问题: 添加新 SQL 语法、函数、聚合、数据类型                   │  │
  │  │ 阅读链: Parser → Command → Expression → DDL                      │  │
  │  └──────────────────────────────────────────────────────────────────┘  │
  │                                                                        │
  │  入口: 词法分析                            command/Tokenizer.java     │
  │    ├── 语法解析                            command/Parser.java        │
  │    ├── 命令执行                            command/Command.java       │
  │    ├── 表达式求值                          expression/Expression      │
  │    └── DDL 扩展                            command/ddl/              │
  │                                                                        │
  │  关键文件: Tokenizer.java, Parser.java, Command.java,                  │
  │           Expression.java, ddl/CreateTable.java                        │
  │  预期: ~5 天完成第一个 SQL 扩展                                        │
  ├────────────────────────────────────────────────────────────────────────┤
  │  路径 C: 问题排查方向                                                    │
  │  ┌──────────────────────────────────────────────────────────────────┐  │
  │  │ 目标读者: 维护者 / 需要定位线上 Bug 的贡献者                       │  │
  │  │ 关注问题: 并发异常、事务死锁、数据不一致、连接泄漏               │  │
  │  │ 阅读链: Engine → Session → Transaction → MVCC                    │  │
  │  └──────────────────────────────────────────────────────────────────┘  │
  │                                                                        │
  │  入口: 数据库引擎                       mvstore/db/Engine.java       │
  │    ├── 会话管理                         engine/SessionLocal.java     │
  │    ├── 事务生命周期                     mvstore/tx/Transaction.java  │
  │    ├── 版本链与可见性判断               TransactionMap.java          │
  │    └── 锁与并发控制                     db/MVTable.java              │
  │                                                                        │
  │  关键文件: Engine.java, SessionLocal.java, Transaction.java,           │
  │           TransactionMap.java, MVTable.java, VersionedValue.java       │
  │  预期: ~3 天定位和修复第一个 Bug                                       │
  ├────────────────────────────────────────────────────────────────────────┤
  │  路径 D: 系统学习方向                                                    │
  │  ┌──────────────────────────────────────────────────────────────────┐  │
  │  │ 目标读者: 数据库初学者 / 希望系统掌握数据库原理的开发者            │  │
  │  │ 关注问题: 数据库全貌、组件协作、设计哲学、架构演进               │  │
  │  │ 阅读链: Architecture → SQL → Storage → Advanced                  │  │
  │  └──────────────────────────────────────────────────────────────────┘  │
  │                                                                        │
  │  入口: 架构总览 (第 1-2 章)                                              │
  │    ├── SQL 层解析与优化               command/Parser + Optimizer     │
  │    ├── 存储引擎核心                   mvstore/MVMap + MVStore       │
  │    ├── 事务与并发                     mvstore/tx/                    │
  │    └── 高级特性                       rtree/, security/, store/fs/  │
  │                                                                        │
  │  关键文件: MVMap.java, MVStore.java, Parser.java, Optimizer.java,      │
  │           TransactionMap.java, MVRTreeMap.java, FilePath.java          │
  │  预期: ~2 周建立完整的数据库知识体系                                    │
  └────────────────────────────────────────────────────────────────────────┘
```

**路径 A 详解 —— 性能优化路径**：

如图 12-11 所示，以 MVStore 配置为起点，逐步深入性能相关的各个环节。第一步，阅读 `MVStore.java` 的构造方法和 `MVStoreConfig.java`，理解 `chunkSize`（默认 128KB）、`compactionThreshold`（默认 40 个活跃 Chunk）、`autoCompactFillRate`（默认 20%）等参数的含义。第二步，阅读 `CacheLongKeyLIRS.java`，理解 LIRS 算法的核心数据结构——栈（Stack）和队列（Queue）的维护逻辑。重点关注 `get()` 方法中的缓存命中/未命中逻辑，以及 `prune()` 方法如何淘汰冷数据。第三步，阅读 `Chunk.java` 中的存活率（`getFillRate()`）计算方法，理解 Compaction 如何选择待合并的 Chunk。第四步，阅读 `Optimizer.java` 的 `optimize()` 方法，理解查询代价模型如何影响执行计划的选择。通过这条路径，你将掌握从存储层到查询层的完整性能分析能力。

**路径 B 详解 —— 功能扩展路径**：

以 SQL 词法分析为起点，逐步深入语法解析和命令执行。第一步，阅读 `Tokenizer.java`，理解 `readToken()` 方法如何将 `SELECT * FROM t WHERE id = 1` 分解为 10 个 Token：`SELECT`、`*`、`FROM`、`t`、`WHERE`、`id`、`=`、`1`。第二步，阅读 `Parser.java` 的 `parseSelect()` 方法，理解递归下降解析的过程——`parseSelect()` 调用 `parseFrom()`，`parseFrom()` 调用 `parseWhere()`，`parseWhere()` 调用 `parseExpression()`，形成层层嵌套的调用链。第三步，阅读 `Command.java` 及其子类的 `update()` 和 `query()` 方法，理解解析后的 AST 如何被转换为可执行的数据库操作。第四步，阅读 `expression/Expression.java` 及其子类，理解条件表达式如何在 WHERE、HAVING、ON 子句中被递归求值。这条路径可以帮助你在 5 天内完成第一个 SQL 功能扩展——例如添加一个新的内置函数。

**路径 C 详解 —— 问题排查方向**：

以数据库引擎初始化为起点，逐步深入事务和并发相关代码。排查问题时最常用的是"逆向追踪法"——从异常栈顶开始，逐层向下追溯根因。第一步，阅读 `Engine.java` 的 `openSession()` 方法，理解会话的创建和数据库实例化管理。第二步，阅读 `SessionLocal.java`，重点关注事务的 begin/commit/rollback 生命周期，以及会话级别的锁管理。第三步，阅读 `mvstore/tx/Transaction.java` 和 `TransactionMap.java`，理解版本链的创建和可见性判断逻辑。这是 Bug 最密集的区域——版本链遍历时的空指针、可见性判断的边界条件、并发提交时的 CAS 竞争。第四步，阅读 `db/MVTable.java` 中的行级锁实现，理解排他锁（X Lock）和共享锁（S Lock）的申请和释放。这条路径教你如何通过设置断点和逐步调试来定位并发相关 Bug。常见排查场景包括：查询返回不一致结果（检查 TransactionMap 可见性判断）、死锁（检查 MVTable 锁顺序）、内存泄漏（检查 Compaction 回收逻辑）。

**路径 D 详解 —— 系统学习方向**：

这是最推荐的入门路径，适合希望系统掌握 H2 实现原理的读者。第一阶段（架构概览），阅读第 1-2 章的架构文档，理解 H2 的整体模块划分和数据流——从 JDBC 接口到 SQL 解析、查询优化、存储引擎、事务管理。第二阶段（SQL 层），阅读 `Parser.java` 的 SQL 解析过程和 `Optimizer.java` 的查询优化逻辑，建立对"关系型查询"的代码级理解。第三阶段（存储层），深入 `MVMap.java` 和 `MVStore.java` 的核心方法——这是 H2 最具特色的部分，COW B-Tree 的无锁并发和 Log-Structured 的顺序写入。第四阶段（高级特性），探索空间索引（`MVRTreeMap.java`）、文件系统抽象（`FilePath.java` 及其子类）、透明加密（`FilePathEncrypt.java`）等高级模块。这条路径走完，你将建立起完整的数据库内核知识体系，为深入其他数据库（PostgreSQL、MySQL、SQLite）打下坚实基础。

---

### 12.4.2 按调试场景追踪代码

在 IDE 中设置断点并逐步追踪执行流程，是理解源码最高效的方式之一。以下是三个典型的调试场景，每个场景都标注了关键的断点位置、预期观察对象和执行路径。

**图 12-12: 三大调试场景的整体调用链路**

```text
========================================================================

  场景 A: 单条 SELECT 查询 ── 从 JDBC 到存储层的完追踪
  ┌────────────────────────────────────────────────────────────────┐
  │ JdbcStatement.executeQuery(sql)                                │
  │   → Parser.parseCommand(sql)       ← 解析 SQL 文本为 AST      │
  │     → Optimizer.optimize()          ← 代价评估, 选择最优计划  │
  │       → Index.find(session, keys)   ← 索引查找定位目标行      │
  │         → TransactionMap.get(key)   ← 事务层: 版本链可见性判断│
  │           → MVMap.get(key)          ← 存储层: COW B-Tree 查找 │
  └────────────────────────────────────────────────────────────────┘

  场景 B: 事务提交 ── 从事务日志到磁盘 fsync 的完整路径
  ┌────────────────────────────────────────────────────────────────┐
  │ TransactionCommand.update()         ← 事务命令入口            │
  │   → TransactionStore.commit()       ← 写入提交日志            │
  │     → MVStore.store()               ← 存储层提交 + 写入 Chunk │
  │       → MVStore.store()             ← COW 路径写入 Chunk      │
  │         → MVStore.sync()            ← FileChannel.force()     │
  └────────────────────────────────────────────────────────────────┘

  场景 C: COW B-Tree 写入 ── 观察页复制和根引用切换
  ┌────────────────────────────────────────────────────────────────┐
  │ MVMap.put(key, value)                ← 写入入口               │
  │   → MVMap.writeOrDeleteRow()         ← 定位目标页, COW 复制   │
  │     → MVMap.setRoot(newRoot)         ← CAS 切换根引用         │
  │       → RootReference.compareAndSet() ← 原子操作              │
  │         → MVStore.store()            ← 新路径持久化           │
  └────────────────────────────────────────────────────────────────┘
```

如图 12-12 所示，**调试场景 A 详解 —— SELECT 追踪**：

打开 H2 源码后，找到 `JdbcStatement.java` 的 `executeQuery()` 方法（位于 `org/h2/jdbc/JdbcStatement.java:227`），在这一行设置第一个断点。运行一个简单的测试：`CREATE TABLE t(id INT PRIMARY KEY, name VARCHAR); INSERT INTO t VALUES(1, 'Alice'); SELECT * FROM t WHERE id=1;`。

当执行到 SELECT 语句时，断点触发。此时可以观察到 `sql` 参数即为传入的 SQL 字符串。Step Into 进入 `executeQuery()` 内部，可以看到它创建了 `JdbcPreparedStatement` 并调用 `execute()`。继续 Step Into，程序将进入 `Parser.parseCommand()`。观察 `Tokenizer` 如何将 SQL 文本分解为 Token：`SELECT` (Keyword)、`*` (Star)、`FROM` (Keyword)、`t` (Identifier)、`WHERE` (Keyword)、`id` (Identifier)、`=` (Operator)、`1` (Value)。

继续跟踪到 `Select.query()`，这里会调用 `Optimizer.optimize()`。在 Optimizer 中设置断点，可以看到 `Plan.cost()` 的计算过程——优化器会评估全表扫描和索引扫描两种方案的代价，选择 cost 更低的。由于 id 是主键，索引扫描的 cost 远低于全表扫描。最终执行进入 `MVPrimaryIndex.find()`，该方法调用 `TransactionMap.get(key)` 而不是直接调用 `MVMap.get()`——这一层是事务可见性判断的关键。在 `TransactionMap.get()` 中设置断点，观察 `VersionedValue` 的版本链遍历过程。注意观察 `isVisible()` 方法如何根据当前事务 ID 和快照点决定哪些版本可见。

**调试场景 B 详解 —— 事务提交追踪**：

在 `TransactionCommand.update()`（位于 `org/h2/command/dml/TransactionCommand.java`）设置断点，然后运行一个包含事务的测试：`CREATE TABLE t (id INT); INSERT INTO t VALUES(1); COMMIT;`。

当 `COMMIT` 语句进入 `TransactionCommand.update()` 时，注意观察 `commandType` 字段——它区分了 `BEGIN`、`COMMIT`、`ROLLBACK` 三种操作。Step Into 进入提交路径，会进入 `TransactionStore.commit()`，这里写入提交日志并更新事务状态。重点关注 `mvstore/MVStore.java` 的 `commit()` 方法——这是存储层提交的核心。在这里可以看到 `rootReference` 如何通过 CAS 从旧根切换到新根。注意观察 `store()` 方法中多个写入如何被聚合并顺序写入 Chunk——在调试器中查看 `writeBuffer` 的内容，可以看到当前 Chunk 中待写入的数据块。当执行到 `MVStore.sync()` 时，观察 `FileChannel.force(true)` 的调用。这一步将操作系统缓冲区中的数据强制刷入磁盘。如果在调试器中查看 `.mv.db` 文件的大小，可以看到每次提交后文件大小的变化。

**调试场景 C 详解 —— COW B-Tree 观察**：

在 `MVMap.put()` 设置断点，运行插入操作：`INSERT INTO t VALUES(1, 'Alice')`。当断点触发时，注意观察 `key` 和 `value` 参数。Step Into 进入 `writeOrDeleteRow()`，这里可以看到 COW 的核心逻辑：首先调用 `readRoot()` 获取当前根节点，然后从根到叶子递归查找目标位置，当发现叶子页已满时执行页分裂。在 `Page` 类的写入方法中设置断点，观察旧的叶子页如何被复制为新的叶子页（COW 复制过程）——新旧页面的 `getKeyCount()` 应完全相同，但对象地址不同。重点观察 `setRoot()` 方法的调用。在调用前后，分别记录 `System.identityHashCode(rootReference.get())` 的值。你会发现两个值不同——因为 CAS 已经将根引用指向了新构建的 B-Tree 根节点。通过对比新旧根节点的 `getKeyCount()` 和子节点指针，可以直观地看到 COW 创建的"新路径"和保留的"旧路径"。

---

### 12.4.3 动手练习建议

```text
本节速览：12.4.3 动手练习建议

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


理论阅读配合动手实践，是掌握源码最有效的方式。以下是五个经过设计的练习，难度从入门到进阶递增，每个练习都包含明确的目标、步骤和验收标准。

**图 12-13: 五项动手练习的难度分布与前置依赖**

```text
========================================================================

  练习编号      难度      练习名称               涉及模块          预计时间
  ────────────────────────────────────────────────────────────────────────
  ①             ★☆☆     添加新的 SQL 关键字     Tokenizer+Parser    ~2 小时
  ②             ★★☆     实现新的聚合函数       Expression+Aggregate ~3 小时
  ③             ★★☆     追踪 B-Tree 页分裂     MVMap+Page          ~2 小时
  ④             ★★★     修改 LIRS 缓存策略     CacheLongKeyLIRS    ~4 小时
  ⑤             ★★★     添加新的 JDBC 方法     JdbcStatement+Jdbc  ~4 小时

  练习依赖关系:
  ┌──────────────────────────────────────────────────────────────┐
  │  ① 添加关键字 ──────→ ② 实现聚合函数                        │
  │  (理解词法/语法)       (理解 Expression 框架)                │
  │                                                              │
  │  ③ 追踪页分裂 ──────→ ④ 修改缓存策略                        │
  │  (理解 B-Tree 结构)    (理解缓存算法)                        │
  │                                                              │
  │  ⑤ 添加 JDBC 方法 (独立练习, 需要理解 Jdbc 层)              │
  └──────────────────────────────────────────────────────────────┘

  难度说明: ★☆☆ 基础  ★★☆ 入门  ★★★ 进阶
```

如图 12-13 所示，**练习 1: 添加新的 SQL 关键字（难度 ★☆☆, ~2 小时）**

目标：理解 H2 的词法分析和语法解析流程，从修改 Parser.java 开始建立动手信心。

步骤：
1. 在 `Tokenizer.java` 中找到关键字定义区域（`KEYWORDS` 数组或 `isKeyword()` 方法），添加一个新关键字，例如 `MY_KEYWORD`。
2. 在 `Parser.java` 中找到一个简单命令的解析方法（例如 `parseShow()`），在你的关键字后面添加一个简单的解析逻辑——例如返回一个常量字符串。
3. 运行 `mvn test -Dtest=TestTokenizer` 验证 Tokenizer 的测试通过。
4. 在 H2 Console 中执行 `MY_KEYWORD`，观察是否能正确解析并返回结果。

验收标准：在 H2 Console 中输入 `MY_KEYWORD` 后，返回预期的结果而非 "Syntax error"。能够描述 Tokenizer 将关键字从标识符中区分出来的机制。

**练习 2: 实现新的聚合函数（难度 ★★☆, ~3 小时）**

目标：理解 H2 的 Expression 框架和聚合函数的实现模式，以 GroupConcat 或其他现有聚合为模板。

步骤：
1. 阅读 `expression/aggregate/Aggregate.java` 和 `AggregateData.java`，理解聚合函数的接口和数据结构。
2. 选择一个简单的现有聚合（如 `COUNT`）作为模板，复制其结构实现一个新聚合，例如 `PRODUCT`（计算乘积）。
3. 在 `Aggregate.getAggregateType()` 中注册新的聚合类型 ID。
4. 在 `Parser.java` 中确保新聚合的名称可以被正确解析。
5. 编写测试：`SELECT PRODUCT(price) FROM items`，验证计算结果。

验收标准：新聚合函数能在 SELECT 查询中正确执行，返回聚合后的计算结果。能够解释 AggregateData 子类如何维护中间状态以及 `getValue()` 方法如何返回最终结果。

**练习 3: 追踪并记录 B-Tree 页分裂（难度 ★★☆, ~2 小时）**

目标：通过添加日志输出，直观观察 COW B-Tree 在插入数据过程中的页分裂行为。

步骤：
1. 在 `MVMap.writeOrDeleteRow()` 和 `Page.split()` 方法中添加日志输出，记录分裂前后的键数量和各子页的键分布。
2. 在 `MVMap.setRoot()` 方法中添加日志，输出新旧根节点的 `System.identityHashCode()`。
3. 连续插入 1000 条递增主键的记录，观察 B-Tree 高度从 1 增长到 3+ 的完整过程。
4. 根据日志数据绘制 B-Tree 高度随数据量变化的趋势图。

验收标准：能清晰描述 B-Tree 的页分裂触发条件（页满）、分裂策略（键的重新分布）以及 COW 如何通过创建新路径避免阻塞读操作。

**练习 4: 修改 LIRS 缓存策略（难度 ★★★, ~4 小时）**

目标：深入理解 LIRS 缓存淘汰算法的实现，并动手修改缓存策略。

步骤：
1. 阅读 `CacheLongKeyLIRS.java`，理解 LIRS 的栈（Stack）和队列（Queue）两个核心数据结构。
2. 找到 LIRS 的淘汰决策逻辑——`prune()` 方法中如何选择被淘汰的缓存项。
3. 修改 `prune()` 方法，将 LIRS 的淘汰策略改为 LRU（只使用队列，不使用栈隔离冷数据）。
4. 实现一个 `CacheStats` 类统计修改前后的缓存命中率。
5. 运行 OLTP 模拟负载（20% 热点数据访问 80% 次数 + 大量一次扫描），对比 LRU 和 LIRS 的命中率。

验收标准：能够定量比较 LRU 和 LIRS 在不同工作负载下的命中率差异，理解 LIRS "扫描抵抗"特性的代码实现。

**练习 5: 添加新的 JDBC 方法（难度 ★★★, ~4 小时）**

目标：理解 H2 的 JDBC 驱动层实现，扩展 JDBC 接口。

步骤：
1. 在 `JdbcStatement.java` 或 `JdbcConnection.java` 中添加一个新的公开方法，例如 `getDatabaseVersion()` 返回 H2 版本号。
2. 让新方法委托到引擎层获取实际数据——在 `Engine.java` 或 `Database.java` 中添加对应的处理逻辑。
3. 编写一个 JDBC 测试程序，通过 `Connection` 或 `Statement` 对象调用新方法。
4. 确保现有 JDBC 测试全部通过：`mvn test -Dtest=TestJdbc*`。

验收标准：能够通过 JDBC API 调用新增方法并获取正确结果。能够描述 JDBC 驱动层到引擎层的完整调用链——从 `JdbcStatement` 的 Java 方法到 `Session` 的数据库操作。

---

### 12.4.4 源码阅读工具推荐

```text
本节速览：12.4.4 源码阅读工具推荐

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

  ┌────────────┐     ┌────────────┐
  │ 输入条件   │ ──▶ │ 处理路径   │
  └────────────┘     └─────┬──────┘
                            │
                            ▼
                      ┌────────────┐
                      │ 输出结果   │
                      └────────────┘
```


熟练掌握 IntelliJ IDEA（或 VS Code + Java 扩展）的导航和调试功能，可以大幅提升源码阅读效率。

**核心快捷键**：`Ctrl+B`（Cmd+B）跳转到定义，`Ctrl+Alt+B`（Cmd+Alt+B）查找接口实现，`Alt+F7` 查找方法使用处，`Ctrl+Alt+H`（Cmd+Alt+H）查看调用层次，`Ctrl+F12`（Cmd+F12）浏览文件成员列表，双击 Shift 搜索所有类/文件/符号。

**调试技巧**：条件断点（右键断点设置 `key.equals(42)`）可以只关注目标数据；断点日志（Log message to console）适合追踪高频方法如 `MVMap.get()` 而不中断执行；Evaluate Expression（Alt+F8）可以在断点暂停时调用任意方法，例如 `System.identityHashCode(rootReference.get())` 确认对象地址变化。Frame 切换可以在 Debugger 面板中快速跳转到调用栈的不同层级。

建议首次在 IntelliJ 中打开 H2 项目后，先依次打开 `Tokenizer.java`（词法分析）、`MVMap.java`（B-Tree 接口）、`MVStore.java`（存储引擎提交路径）、`TransactionMap.java`（事务分界）阅读 Javadoc，建立整体印象后再选择 12.4.2 中的调试场景进行逐步追踪。

---

## 12.5 本章小结

H2 源码研读是一个循序渐进的过程。第 11 章提供了系统性的四阶段阅读法，帮助读者从搭建环境到参与社区贡献。本章则从架构权衡、多方向研读等角度，为不同目标的读者提供了差异化的阅读路径。

无论是选择性能优化路径深入存储引擎，还是选择功能扩展路径探索 SQL 引擎，理解 H2 的设计权衡（COW vs In-place、Log-Structured vs Page Store、CAS vs Locks、分层事务 vs 嵌入式版本链）都是贯穿始终的主线。将这些权衡映射到具体的代码实现，就能从"知道原理"上升到"理解代码为什么这样写"的层面。

对于希望进一步实践的读者，建议从 12.4.3 中的练习 1 或练习 2 开始，先获得"修改源码 → 观察效果"的正反馈循环，这比一次性通读所有源码的收益更大。
