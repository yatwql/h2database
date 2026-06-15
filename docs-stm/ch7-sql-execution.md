# 第7章 SQL 执行全流程

> **本章导读**: 本章跟踪 SQL 语句从客户端到引擎再到存储的完整执行链路，重点分析 SELECT、INSERT、UPDATE、DELETE 四大 DML 语句的执行流程。从 Parser 解析、Prepared 编译到最终执行的各阶段，结合源码类和方法进行逐层剖析。
> **前置知识**: 第4章《核心模块深度解读》§4.1-4.2（Command/Expression 模块）；第5章《核心流程解读》§5.1-5.4（流程入口）
> **章节要点**:
> - 理解 SQL 语句从解析到执行的全链路
> - 掌握 SELECT 的查询编译和执行过程
> - 熟悉 INSERT/UPDATE/DELETE 的修改执行流程
> - 了解 LOB 处理、Batch 更新等特殊机制
> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

> 本章追踪一条 SQL 语句从 JDBC 接口到存储层的完整执行链路，涵盖解析、缓存、Command 框架与表达式求值。Command 层整体架构详见第2章《分层模块划分》2.1.3 Command 层，相关包结构详见第3章《核心包结构详解》3.4-3.5 节。各核心算法的基础原理详见第6章《H2 数据库核心算法分析》。完整流程可结合第5章《核心流程解读》第5.1-5.4 节的 SELECT/INSERT/UPDATE/DELETE 流程对照阅读。本章共 81 张插图，信息量较大，建议分段阅读。

本章结构：7.1 介绍 JDBC 入口与连接建立，7.2 详解 SQL 解析流程，7.3 说明缓存机制，7.4 剖析 Command 执行框架，7.5 展示完整 ASCII 流程图，7.6 探讨表达式求值，7.7 总结全章要点。

---

## 7.1 JDBC 层入口

H2 的 JDBC 驱动实现了标准 `java.sql` 接口，所有 SQL 语句的入口分为两类：`Statement` 与 `PreparedStatement`。

### 7.1.1 `JdbcStatement.executeQuery(String sql)`

源码位置：`jdbc/JdbcStatement.java:82`

```java
public ResultSet executeQuery(String sql) throws SQLException {
    session.lock();
    try {
        closeOldResultSet();
        CommandInterface command = conn.prepareCommand(sql);
        result = command.executeQuery(maxRows, fetchSize, scrollable);
        resultSet = new JdbcResultSet(conn, this, command, result, id, ...);
    } finally {
        session.unlock();
    }
}
```

核心步骤：
1. `session.lock()` — 获取 session 级互斥锁，保证线程安全
2. `conn.prepareCommand(sql)` — 将 SQL 文本解析为可执行的 Command 对象
3. `command.executeQuery(...)` — 执行查询，返回 `ResultInterface`
4. `new JdbcResultSet(...)` — 将结果包装为 JDBC 标准 ResultSet

方法执行流程中的锁生命周期如下所示：

```text
JdbcStatement.executeQuery(sql)
  │
  ├── session.lock()                          ← 获取锁
  │     │
  │     ├── closeOldResultSet()               ← 清理上一次结果集
  │     │
  │     ├── conn.prepareCommand(sql)          ← 解析 SQL → Command
  │     │     └── SessionLocal.prepareCommand()
  │     │           ├── prepareLocal()        ← 缓存检查 + 解析
  │     │           └── return CommandContainer
  │     │
  │     ├── command.executeQuery(maxRows)     ← 执行查询
  │     │     └── Select.query() → TableFilter 迭代
  │     │
  │     └── new JdbcResultSet(command, result) ← 包装为 JDBC 结果集
  │
  └── session.unlock()                        ← 释放锁
```
**图 7-1: 追踪 executeQuery 的锁生命周期**

如图 7-1 所示，该图展示了 `executeQuery` 方法的完整执行路径。锁的获取和释放在方法的入口和出口处，中间的全部操作（包括 SQL 解析、查询执行和结果包装）都在锁保护下完成。这种粗粒度加锁策略简化了并发控制，但要求解析和执行阶段的耗时尽量短——这正是查询缓存存在的重要原因之一。

```text
JDBC 层各组件职责与调用关系
                        │
  ┌─────────────────────────────────────────────────────────────┐
  │  JdbcStatement (JDBC 标准接口实现)                            │
  │                                                              │
  │  职责: SQL 文本入口                                          │
  │  ┌───────────────────────────────────────────────────────┐   │
  │  │  executeQuery(String sql)                             │   │
  │  │  executeUpdate(String sql)                            │   │
  │  │  execute(String sql)                                  │   │
  │  └──────────────────────┬────────────────────────────────┘   │
  └─────────────────────────┼────────────────────────────────────┘
                            │ 委托
                            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  JdbcConnection (连接管理)                                    │
  │                                                              │
  │  职责: 管理 Session、创建 Command                            │
  │  ┌───────────────────────────────────────────────────────┐   │
  │  │  prepareCommand()        → SessionLocal.prepare()     │   │
  │  │  prepareAutoCloseZap()   → 自动关闭包装               │   │
  │  └──────────────────────┬────────────────────────────────┘   │
  └─────────────────────────┼────────────────────────────────────┘
                            │ 委托
                            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  JdbcResultSet (结果集包装)                                   │
  │                                                              │
  │  职责: 包装 ResultInterface 为 JDBC 标准                     │
  │  ┌───────────────────────────────────────────────────────┐   │
  │  │  构造时绑定: conn, command, result, id                │   │
  │  │  生命周期: 与 Command 绑定, close 时释放              │   │
  │  └───────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────┘
```
**图 7-2: 拆解 JDBC 层组件职责与调用关系**

> **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#result_sets`)
> 列出了所有返回结果集的语句类型以及大结果集的外部排序机制。

### 7.1.2 `JdbcPreparedStatement.executeQuery()`

如图 7-2 所示，源码位置：`jdbc/JdbcPreparedStatement.java:115`

```java
public ResultSet executeQuery() throws SQLException {
    session.lock();
    try {
        // command 已在 prepare 阶段创建
        command.executeQuery(maxRows, fetchSize, scrollable);
    } finally {
        session.unlock();
    }
}
```

`PreparedStatement` 的 `command` 在构造时已创建，此处直接复用，无需重复解析。

Statement 与 PreparedStatement 的执行流程对比：

```text
Statement 执行路径 (每次完整编译):
  executeQuery(sql)
    ├── lock()
    ├── conn.prepareCommand(sql)    ← 包含解析 + 优化 + 计划
    │     ├── Parser 解析            (CPU 密集)
    │     ├── Optimizer 优化         (CPU 密集)
    │     └── 生成执行计划
    ├── command.query()              ← 执行
    ├── unlock()
    └── 返回结果

PreparedStatement 执行路径 (仅执行):
  executeQuery()                    ← 无 SQL 参数
    ├── lock()
    ├── command.query()             ← 直接执行已编译计划
    │     └── 跳过解析 + 优化      (零开销)
    ├── unlock()
    └── 返回结果

  性能差异:
  ┌──────────────────────────────┬───────────────┬──────────────────┐
  │ 环节                         │ Statement     │ PreparedStatement │
  ├──────────────────────────────┼───────────────┼──────────────────┤
  │ 每次执行解析?                │ 是            │ 否 (一次编译)    │
  │ 每次执行优化?                │ 是            │ 否 (一次优化)    │
  │ 每次加锁/解锁?               │ 是            │ 是               │
  │ 解析耗时占比 (典型查询)      │ 30%-60%      │ 0%               │
  │ SQL 注入防护                 │ 无            │ 天然防御         │
  └──────────────────────────────┴───────────────┴──────────────────┘
```
**图 7-3: 对比 Statement 与 Prepared 的执行路径**

如图 7-3 所示，该图直观对比了两种语句类型在执行阶段的差异。Statement 在每次 `executeQuery()` 时都要经历完整的编译过程（解析、优化、计划生成），而 PreparedStatement 的编译工作在 `prepareStatement()` 阶段已提前完成，后续的 `executeQuery()` 仅触发执行。对于高频执行的查询，PreparedStatement 可消除 30%-60% 的解析开销，并且在执行路径中天然不具备 SQL 注入的风险——参数值在编译后作为数据绑定，不参与 SQL 文本拼接。

### 7.1.3 入口调用链

```text
JdbcStatement.executeQuery(sql)
  │
  ├─ session.lock()
  ├─ conn.prepareCommand(sql)    → SessionLocal.prepareCommand()
  │     └─ prepareLocal(sql)     → 解析 + 缓存
  ├─ command.executeQuery(...)    → CommandContainer.query()
  │     └─ prepared.query(...)   → Select.query()
  └─ new JdbcResultSet(...)      → 包装结果
```

调用链中各组件所属层次和职责划分：

```text
┌──────────────────────────────────────────────────────────────────┐
│  JDBC 层 (JdbcStatement / JdbcPreparedStatement)                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  executeQuery(sql) → 标准 JDBC 接口入口                     │  │
│  │  new JdbcResultSet() → 将内部结果包装为 JDBC ResultSet     │  │
│  └───────────────────────┬────────────────────────────────────┘  │
└──────────────────────────┼───────────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────────┐
│  Session 层 (SessionLocal)                                       │
│  ┌───────────────────────┴────────────────────────────────────┐  │
│  │  prepareCommand(sql)  ← 加锁 + 缓存检查                     │  │
│  │  prepareLocal(sql)    ← 缓存命中直接返回, 未命中则解析      │  │
│  └───────────────────────┬────────────────────────────────────┘  │
└──────────────────────────┼───────────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────────┐
│  Command 层 (CommandContainer)                                   │
│  ┌───────────────────────┴────────────────────────────────────┐  │
│  │  query(maxRows)      ← 统一的查询执行入口                  │  │
│  │  prepared.query()    ← 委托给 Select/Insert 等子类         │  │
│  └───────────────────────┬────────────────────────────────────┘  │
└──────────────────────────┼───────────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────────┐
│  Engine 层 (Select / Insert / Update / Delete)                   │
│  ┌───────────────────────┴────────────────────────────────────┐  │
│  │  query() / update()  ← 实际执行查询逻辑                     │  │
│  │  preparePlan()       ← 调用 Optimizer 生成执行计划          │  │
│  │  TableFilter.next()  ← 行迭代循环                          │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```
**图 7-4: 拆解 JDBC 入口调用链的层次职责**

如图 7-5 所示，如图 7-4 所示，跟踪一次 `executeQuery` 调用，可以看到它穿透了 H2 内核的四个层次：JDBC 接口层负责标准协议适配，Session 层负责并发控制和缓存，Command 层提供统一的命令执行抽象，Engine 层负责实际的查询执行和优化。每一层在调用链中都有明确的职责边界，调用链的方向也是单向的——上层调用下层，下层不反向依赖上层。

### 7.1.4 JDBC 层架构分层详解

**图 7-5: 概览 JDBC 到 Store 的五层架构**

```text
如图 7-65 所示，┌──────────────────────────────────────────────────────────────────────────┐
│                          应用层 (客户端代码)                               │
│    ┌────────────────────────┐    ┌──────────────────────────────┐        │
│    │  Statement             │    │  PreparedStatement            │        │
│    │  executeQuery(sql)     │    │  executeQuery()               │        │
│    │  executeUpdate(sql)    │    │  executeUpdate()              │        │
│    └───────────┬────────────┘    └─────────────┬────────────────┘        │
│                │                               │                          │
│                └───────────────┬───────────────┘                          │
│                                │                                          │
│                                ▼                                          │
│                    ┌──────────────────────┐                               │
│                    │  Connection           │                               │
│                    │  prepareCommand(sql)  │                               │
│                    └──────────┬───────────┘                               │
└───────────────────────────────┼───────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Session 层                                      │
│    ┌────────────────────────────────────────────────────────────────┐    │
│    │  SessionLocal                                                  │    │
│    │  ┌──────────────────────────────────────────────────────────┐  │    │
│    │  │ prepareCommand(sql)                                      │  │    │
│    │  │  1. lock()                     ← 线程互斥锁             │  │    │
│    │  │  2. prepareLocal(sql)          ← 缓存 + 解析            │  │    │
│    │  │  3. unlock()                   ← 释放锁                 │  │    │
│    │  └──────────────────────────────────────────────────────────┘  │    │
│    │  queryCache: SmallLRUCache<String, Command>                    │    │
│    │  modificationMetaID: long (DDL 变更追踪)                      │    │
│    └────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┼───────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Command 层                                      │
│    ┌────────────────────────────────┐  ┌──────────────────────────┐      │
│    │  CommandContainer              │  │  CommandList             │      │
│    │  ┌───────────────────────────┐ │  │  commands: Command[]    │      │
│    │  │ prepared: Prepared       │ │  │  支持批处理执行         │      │
│    │  │ query(maxRows)           │ │  └──────────────────────────┘      │
│    │  │ update(genKeysRequest)   │ │                                     │
│    │  └───────────────────────────┘ │                                     │
│    └────────────────────────────────┘                                     │
└───────────────────────────────┼───────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Engine 层                                       │
│    ┌────────────────────────────────────────────────────────────────┐    │
│    │  Prepared (抽象基类)                                           │    │
│    │   ├── Select   → 查询执行, 内部调用 Optimizer                 │    │
│    │   ├── Insert   → 插入执行                                     │    │
│    │   ├── Update   → 更新执行                                     │    │
│    │   └── Delete   → 删除执行                                     │    │
│    │                                                                │    │
│    │  核心方法链路: init() → prepare() → preparePlan() → query()    │    │
│    └────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┼───────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Store 层                                        │
│    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│    │  MVStore         │  │  MVTable         │  │  Index           │     │
│    │  持久化 B-Tree    │  │  行数据增删改查  │  │  B+Tree / Hash   │     │
│    └──────────────────┘  └──────────────────┘  └──────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
```
**图 7-65: 概览 JDBC 与内核通信的分层架构**

该图展示了 H2 数据库的经典分层架构。SQL 请求从最上层的应用层发起，依次穿透 Session 层、Command 层、Engine 层，最终到达底层的 Store 存储层。每一层都具有明确的职责边界和稳定的接口契约，层与层之间通过方法调用传递数据，体现了关注点分离的设计原则。

各层职责详述如下：

1. **应用层 (客户端代码)** — 实现标准 `java.sql` 接口，包括 `Statement`、`PreparedStatement`、`Connection` 等 JDBC 核心接口。这一层对上层应用完全透明，应用开发者只需面向 JDBC 标准 API 编程，无需了解 H2 内部实现。`JdbcConnection.prepareCommand(sql)` 是 SQL 请求进入内核的关键入口。

2. **Session 层** — 以 `SessionLocal` 为核心，是每个数据库连接对应的工作线程上下文。核心职责包括：线程同步（`lock/unlock` 机制保证单个 session 内线程安全）、查询缓存管理（`SmallLRUCache` 缓存已编译的 Command 对象）、元数据版本追踪（`modificationMetaID` 在 DDL 后递增以触发缓存失效）。Session 层在整个链路中扮演着"交通指挥"的角色。注：在 ch1-2 的八层模型中，`SessionLocal` 归入 Engine 层，此处为方便理解其独立职责而单独列出，可视为 Engine 层的子层次。

3. **Command 层** — `CommandContainer` 包装已编译的 `Prepared` 对象，提供 `query()` 和 `update()` 两个统一入口。`CommandList` 支持批量 SQL 的顺序执行。这一层屏蔽了不同 SQL 类型（SELECT、INSERT、UPDATE、DELETE）的执行差异，提供统一的命令执行接口。

4. **Engine 层** — 包含 `Select`、`Insert`、`Update`、`Delete` 等 `Prepared` 子类，负责实际的查询优化和执行。其中 `Select` 是最复杂的子类，它在 `preparePlan()` 阶段调用 `Optimizer` 生成最优执行计划，在 `queryWithoutCache()` 阶段驱动 `TableFilter` 的行迭代循环。

5. **Store 层** — 提供底层的持久化存储能力。`MVStore` 实现了基于多版本并发控制的存储引擎，`MVTable` 管理表的行数据，`Index` 接口定义了 B-Tree 索引、哈希索引等多种索引结构的统一访问协议。这一层是 H2 高性能读写的基础。

各层之间的数据传递关系可以通过以下数据流图进一步理解：

```text
如图 7-6 所示，各层间数据传递与格式转换
                        │
  ┌──────────────────────┴──────────────────────┐
  │  应用层 (JDBC)  格式: JDBC 标准接口          │
  │                                             │
  │  输入: SQL 字符串                           │
  │   ┌─ Statement: "SELECT * FROM t WHERE id=1"│
  │   └─ PreparedStatement: 预编译 SQL + 参数   │
  │                                             │
  │  输出: JdbcResultSet (JDBC 标准结果集)      │
  └──────────────────────┬──────────────────────┘
                         │ SQL String / Command
                         ▼
  ┌──────────────────────┬──────────────────────┐
  │  Session 层  格式: 命令 + 会话上下文        │
  │                                             │
  │  输入: SQL 字符串                           │
  │  处理: 缓存查询 → 命中则复用, 未命中则下发  │
  │  输出: CommandContainer (已编译命令)        │
  └──────────────────────┬──────────────────────┘
                         │ Command
                         ▼
  ┌──────────────────────┬──────────────────────┐
  │  Command 层  格式: 统一命令接口             │
  │                                             │
  │  输入: Prepared 对象 (Select/Insert/...)    │
  │  处理: recompileIfRequired → checkParams    │
  │  输出: ResultInterface (内部结果表示)       │
  └──────────────────────┬──────────────────────┘
                         │ Row[] / Cursor
                         ▼
  ┌──────────────────────┬──────────────────────┐
  │  Engine / Store 层  格式: 行数据 + 索引页   │
  │                                             │
  │  输入: TableFilter 链 + PlanItem            │
  │  处理: 游标遍历 → 条件过滤 → 行构建         │
  │  输出: 行数组 (Value[][])                   │
  └─────────────────────────────────────────────┘
```
**图 7-6: 刻画 各层间数据传递与格式转换**

如图 7-7 所示，该图补充了图 7-5 的静态结构视图，从动态数据流的角度展示了 SQL 请求在各层之间传递时的格式转换。在每个层边界上，数据的表示形式都发生了改变：从应用层的 SQL 文本，到 Session 层的 Command 对象，再到 Command 层的内部结果表示，最后到 Store 层的行数据。每一层都加工和转换输入数据，然后传递给下一层——这是典型的分层架构数据流模式。

**图 7-7: 对比 两种 JDBC 语句的内部处理差异**

```text
Statement 生命周期 (每次执行独立):
                                                     H2 内核
 客户端                                                     │
   │                                                         │
   │  executeQuery(sql_1)                                    │
   │─────────────────────────────────────────────────────────→│
   │                                                          │  prepareCommand(sql_1)
   │                                                          │    ├─ Parser 解析 SQL  (开销大)
   │                                                          │    ├─ Optimizer 优化  (开销大)
   │                                                          │    └─ 生成 CommandContainer
   │                                                          │  command.query(maxRows)
   │←──────────────────────────────────────────────────────────│
   │                                                          │
   │  executeQuery(sql_2)   ← 即使 SQL 相同也重新解析          │
   │─────────────────────────────────────────────────────────→│
   │                                                          │  prepareCommand(sql_2)
   │                                                          │    ├─ Parser 解析       (重复)
   │                                                          │    ├─ Optimizer 优化    (重复)
   │                                                          │    └─ 生成 CommandContainer
   │                                                          │  command.query(maxRows)
   │←──────────────────────────────────────────────────────────│

如图 7-66 所示，PreparedStatement 生命周期 (一次编译, 多次执行):
 客户端                                                     H2 内核
   │                                                         │
   │  prepareStatement(sql)                                   │
   │─────────────────────────────────────────────────────────→│
   │                                                          │  prepareCommand(sql)
   │                                                          │    ├─ Parser 解析       (仅此一次)
   │                                                          │    ├─ Optimizer 优化    (仅此一次)
   │                                                          │    └─ 生成 CommandContainer
   │←────── PreparedStatement 引用 ───────────────────────────│
   │                                                          │
   │  setInt(1, 100)                  ← 仅客户端参数绑定      │
   │  executeQuery()                                           │
   │─────────────────────────────────────────────────────────→│
   │                                                          │  command.query(maxRows)
   │                                                          │    └─ 直接复用已编译计划
   │←──────────────────────────────────────────────────────────│
   │                                                          │
   │  setInt(1, 200)                  ← 重新绑定参数          │
   │  executeQuery()                                           │
   │─────────────────────────────────────────────────────────→│
   │                                                          │  command.query(maxRows)
   │                                                          │    └─ 再次复用
   │←──────────────────────────────────────────────────────────│
   │                                                          │
   │  close()                                                  │
   │─────────────────────────────────────────────────────────→│
   │                                                          │  释放资源
```

下面四张图按"生命周期 → 开销规模 → 并发竞争 → 协作放行"的顺序串联：图 7-66 对比 Statement 与 PreparedStatement 的执行流程，图 7-8 量化重复执行下解析阶段的累积开销，图 7-9 描绘 Session 级锁的竞争路径，图 7-67 演示锁释放后不同 Session 之间的并发协作。

**图 7-66: 对比 Statement 与 Prepared 的生命周期**

上图展示了两种 JDBC 语句执行方式的本质差异，核心区别在于"解析与执行是否分离"：

Statement 的特点是**每次调用 executeQuery 都走完整的编译-执行流程**。每次请求中，H2 内核都要重新执行词法分析、语法分析、语义分析、查询优化和计划生成。即使多次发送完全相同的 SQL 文本，解析和优化阶段也会重复执行。对于 OLTP 场景中高频执行的查询（例如在循环中反复执行相同 SQL），Statement 模式的解析开销会显著影响系统吞吐量。

PreparedStatement 的核心优势在于**一次编译，多次执行**。在 `prepareStatement()` 阶段，内核完成所有的解析、优化和计划生成工作，生成 `CommandContainer` 对象，并由客户端持有该对象的引用（通过 JDBC 驱动封装在 `JdbcPreparedStatement` 中）。后续每次调用 `executeQuery()`，客户端仅需通过 `setXxx()` 方法绑定参数，然后直接触发已编译计划的执行。内核无需重新解析 SQL，也无需重新选择执行计划。

两者的性能差异随执行次数增加而放大：对于执行 N 次的查询，Statement 的解析开销约为 O(N)，而 PreparedStatement 约为 O(1)。在高并发 OLTP 系统中，这一差异使 PreparedStatement 的收益尤为突出。此外，PreparedStatement 天然防止 SQL 注入攻击，因为参数值在编译后作为数据安全地绑定到查询计划中，不会参与 SQL 文本拼接，从根源上消除了恶意 SQL 片段被解释为语法结构的可能性。

从执行时间的构成看，两种模式的开销差异随执行次数增长而急剧拉大：

```text
执行 N 次相同查询的开销对比:

Statement 模式:
                  解析    执行    解析    执行            解析    执行
  SQL 传入 ───────┬──────┬──────┬──────┬──────┬─ ... ─┬──────┬──────┐
                  1      2      3      4             N-1    N
                  时间 →  O(N × (解析 + 执行))

PreparedStatement 模式:
            解析    执行 执行         执行
  SQL 传入 ─┬──────┬──────┬──────┬─ ... ─┬──────┐
             1      2     3             N
             时间 →  O(解析 + N × 执行)

  如图 7-8 所示，N=1 时:  Statement   = PreparedStatement       (无差异)
  N=10 时: Statement   ≈ PreparedStatement × 2   (差 2 倍)
  N=100 时: Statement  ≈ PreparedStatement × 10  (差 10 倍)
  N=1000 时: Statement ≈ PreparedStatement × 100 (差 100 倍)
```
**图 7-8: 对比 执行次数增长下的解析开销**

如图 7-9 所示，该图从执行时间构成的角度量化了两种模式的差异。Statement 在每次执行时都在解析阶段付出额外代价，该代价占总执行时间的 30%-60%。PreparedStatement 仅在第一次编译时付出解析代价，后续的执行仅包含实际查询开销。在循环执行或高频调用的 OLTP 场景中，PreparedStatement 的性能优势随执行次数线性增长——执行 N 次时，Statement 的开销约为 O(N×P)（P 为解析开销），而 PreparedStatement 仅为 O(P)。

### 7.1.5 Session 锁机制与并发控制
**图 7-9: 刻画 Session 级锁的竞争路径**

```text
如图 7-67 所示，线程 A (持有 Session 1)             线程 B (持有 Session 2)        线程 C (共享 Session 1)
      │                                    │                            │
      │                                    │                            │
      │  session.lock()                    │                            │
      │    │                               │                            │
      │    │ 获取锁成功                     │                            │
      │    │                               │                            │
      │    │ 执行 SQL 处理:                │  session.lock()            │
      │    │  ├─ Parser 解析               │    │                       │
      │    │  ├─ Optimizer 优化            │    │ 等待锁 (BLOCKED)       │
      │    │  ├─ TableFilter 迭代          │    │                       │
      │    │  └─ 表达式求值                 │    │                       │
      │    │                               │    │                       │
      │    │  (处理中... 约 5ms)           │    │ (等待中... 约 5ms)    │
      │    │                               │    │                       │
      │  session.unlock() ──────────────────┼───→│                       │
      │                                    │    │                       │
      │                                    │◄───┘ 获取锁成功           │
      │                                    │    │                       │
      │                                    │    │ 执行 SQL 处理         │
      │                                    │    │  (约 3ms)             │
      │                                    │    │                       │
      │                                    │  session.unlock()          │
      │                                    │                            │
      │                                    │                            │  session.lock()
      │  (线程 A 可继续执行其他工作)        │                            │    │
      │                                    │                            │  (无需等待,             )
      │                                    │                            │  (不同 Session 完全并行)
```
**图 7-67: 演示 Session 锁与并发控制的协作**

H2 采用 session 级互斥锁来保证线程安全，这一设计在简单性和并发性之间做出了明确的取舍：

1. **锁的范围**：锁定粒度为单个 `SessionLocal` 实例。同一个 session 内的 SQL 执行是串行化的，但不同 session 之间的执行完全并行。这意味着如果应用使用连接池处理多个并发请求，每个请求使用不同的连接（即不同的 Session），则锁竞争几乎为零。

2. **锁机制**：采用 Java `ReentrantLock`（方法 `SessionLocal.lock()` / `SessionLocal.unlock()`）。相比于 `synchronized` 关键字，`ReentrantLock` 提供更灵活锁操作，包括可中断锁获取、超时尝试和公平性策略。

3. **可重入性**：`ReentrantLock` 支持可重入，即同一个线程可以多次获取同一把锁而不会死锁。这在子查询递归执行等场景下至关重要——当 `Subquery.getValue()` 递归调用 `prepareCommand` 时，同一个线程会重复获取锁，可重入机制确保这样的调用不会阻塞。

4. **锁持有时间**：从 `prepareCommand` 到结果返回的完整路径都在锁保护下执行。这意味着即使是解析阶段的耗时也会阻塞同 session 的其他操作。查询缓存在减少锁持有时间方面发挥了重要作用——缓存命中时直接返回已编译的 Command，大幅缩短了锁保护路径。

5. **对比细粒度锁**：与支持行级锁或页级锁的数据库（如 PostgreSQL、InnoDB）不同，H2 使用粗粒度的 session 锁。这种设计在单线程或低并发场景下性能优越，但在大量并发访问同一条连接时可能成为瓶颈。H2 的定位是嵌入式数据库，通常每个应用实例只有一个连接，因此 session 锁的设计是合理且高效的。

锁的可重入特性在子查询嵌套执行中的作用可以通过以下时序图理解：

```text
锁可重入性在子查询中的应用:

线程 T (持有 Session S1)
  │
  ├── session.lock()                     ← 第一次获取锁 (计数=1)
  │     │
  │     ├── 执行外层查询
  │     │     │
  │     │     ├── TableFilter 迭代
  │     │     │     │
  │     │     │     ├── 遇到 Subquery 表达式
  │     │     │     │     │
  │     │     │     │     └── Subquery.getValue()
  │     │     │     │           │
  │     │     │     │           └── query.query(0)       ← 执行子查询
  │     │     │     │                 │
  │     │     │     │                 ├── prepareCommand() ← 需要获取锁!
  │     │     │     │                 │     │
  │     │     │     │                 │     ├── session.lock()
  │     │     │     │                 │     │     └── ReentrantLock 允许
  │     │     │     │                 │     │         同线程重入 (计数=2)
  │     │     │     │                 │     │
  │     │     │     │                 │     ├── 子查询解析与执行
  │     │     │     │                 │     │
  │     │     │     │                 │     └── session.unlock() (计数=1)
  │     │     │     │                 │
  │     │     │     │                 └── 返回子查询结果
  │     │     │     │
  │     │     │     └── 继续外层迭代
  │     │     │
  │     │     └── 外层查询完成
  │     │
  │     └── session.unlock()           ← 真正释放锁 (计数=0)
  │
  └── (继续其他工作)

  如图 7-10 所示，没有可重入锁会怎样?
    ┌─────────────────────────────────────────────────────┐
    │  Subquery.getValue() 调用 query.query(0)            │
    │    → prepareCommand() → session.lock()              │
    │    → 同一个线程, 但锁已被自己持有!                  │
    │    → 不可重入锁: 死锁!                              │
    │    → ReentrantLock: 允许重入, 正常执行              │
    └─────────────────────────────────────────────────────┘
```
**图 7-10: 演示 锁可重入性在子查询中的应用**

该图揭示了锁可重入性在嵌套查询场景中的关键作用。H2 使用 `ReentrantLock` 而非 `synchronized` 的一个重要原因就是支持可重入：当子查询表达式 `Subquery.getValue()` 在执行过程中递归调用 `prepareCommand` 时，同一个线程需要再次获取 session 锁。如果锁不可重入（如普通的互斥锁），这将导致死锁——线程在等待自己已经持有的锁。`ReentrantLock` 通过持有计数机制解决了这一问题，允许同一个线程多次获取同一把锁，每次 `unlock()` 递减计数，只有当计数归零时才真正释放锁。

---

## 7.2 SQL 解析

H2 的解析器（`Parser`）采用手写递归下降方式，没有使用 ANTLR 或 JavaCC 等解析器生成器。

### 7.2.1 `SessionLocal.prepareCommand(String sql)`

源码位置：`org/h2/engine/SessionLocal.java:560`

```java
public CommandInterface prepareCommand(String sql) {
    lock();
    try {
        return prepareLocal(sql);
    } finally {
        unlock();
    }
}
```

如图 7-5 所示，该方法是 SQL 编译的入口，执行流程从加锁开始到释放锁结束：

```text
prepareCommand(sql) 执行流程
                        │
  ┌─────────────────────┴─────────────────────┐
  │  1. lock()                                │
  │     └── session.lock()                    │
  │         └── 获取 ReentrantLock            │
  │              (同线程可重入)               │
  └─────────────────────┬─────────────────────┘
                        │
                        ▼
  ┌─────────────────────┴─────────────────────┐
  │  2. prepareLocal(sql)                     │
  │     │                                     │
  │     ├── 查询缓存存在?                     │
  │     │   ├── YES → queryCache.get(sql)     │
  │     │   │    ├── 命中 → command.reuse()   │
  │     │   │    └── 未命中 → 解析            │
  │     │   └── NO → 直接解析                 │
  │     │                                     │
  │     ├── Parser.prepareCommand(sql)         │
  │     │   └── 词法分析 → 语法分析 → Command │
  │     │                                     │
  │     └── 入缓存 (if cacheable)             │
  │         └── queryCache.put(sql, command)  │
  │                                           │
  │     return command                        │
  └─────────────────────┬─────────────────────┘
                        │
                        ▼
  ┌─────────────────────┴─────────────────────┐
  │  3. unlock()                              │
  │     └── session.unlock()                  │
  │         └── ReentrantLock 释放            │
  └───────────────────────────────────────────┘
```
**图 7-11: 追踪 prepareCommand 三阶段执行路径**

如图 7-11 所示，该方法由三阶段组成：加锁、编译、解锁。`prepareLocal(sql)` 是核心编译逻辑的委托方法，包含缓存检查和实际解析。

```text
锁在 Session 方法调用链中的传递路径
                        │
  ┌───────────────────────────────────────────────────────────────────┐
  │  prepareCommand(sql)                                              │
  │    lock()                                                         │
  │    │                                                              │
  │    └── prepareLocal(sql)                     (同一线程, 重入)      │
  │          │                                                        │
  │          ├── queryCache.get(sql)              ← 读缓存             │
  │          │                                                        │
  │          ├── parser.prepareCommand(sql)       ← 解析              │
  │          │     │                                                  │
  │          │     ├── Parser 内部可能触发:                            │
  │          │     │     ├── SessionLocal.getSchema()    (重入 ✓)      │
  │          │     │     ├── SessionLocal.findTable()   (重入 ✓)      │
  │          │     │     └── Database.getMetaData()     (无需锁)      │
  │          │     │                                                  │
  │          │     └── 解析完成, 返回 Command 对象                    │
  │          │                                                        │
  │          ├── queryCache.put(sql, cmd)          ← 写缓存            │
  │          │                                                        │
  │          └── return command                                       │
  │    │                                                              │
  │    unlock()                                                       │
  └───────────────────────────────────────────────────────────────────┘
                        │
  锁特性说明:
    ├── ReentrantLock: 同一线程可多次 lock() 而不死锁
    ├── 重入计数: 每次 lock() +1, unlock() -1, 归零时释放
    └── 适用范围: 仅保护 Session 内部状态 (缓存 + 上下文)
```
**图 7-12: 追踪 锁在 Session 调用链中的传递路径**

### 7.2.2 `SessionLocal.prepareLocal(String sql)`

如图 7-12 所示，源码位置：`org/h2/engine/SessionLocal.java:622`

```java
public Command prepareLocal(String sql) {
    // 1. 检查查询缓存
    if (queryCacheSize > 0) {
        command = queryCache.get(sql);
        if (command != null && command.canReuse()) {
            command.reuse();
            return command;  // cache hit
        }
    }
    // 2. 解析
    Parser parser = new Parser(this);
    command = parser.prepareCommand(sql);
    // 3. 入缓存
    if (queryCache != null && command.isCacheable()) {
        queryCache.put(sql, command);
    }
    return command;
}
```

方法内部包含两条执行路径——缓存命中时的快速路径和缓存未命中时的完整编译路径：

```text
prepareLocal() 的两种执行路径

快路径 (Cache Hit):
  queryCache.get(sql) → 命中
    │
    ├── command.canReuse()?
    │     ├── YES → command.reuse() → return command
    │     └── NO  → 降级到慢路径
    │
  耗时: ≈ 0.01ms (仅哈希查找 + 复用检查)

慢路径 (Cache Miss):
  queryCache.get(sql) → 未命中 或 不可复用
    │
    ├── new Parser(session)
    ├── parser.prepareCommand(sql)
    │     ├── 词法分析: tokenize(sql)  → 0.1-0.5ms
    │     ├── 语法分析: parseQuery()    → 0.2-2ms
    │     ├── Select.init()            → 0.1-0.5ms
    │     ├── Select.prepare()          → 0.5-5ms (含 Optimizer)
    │     └── new CommandContainer()   → <0.01ms
    │
    └── isCacheable()?
          ├── YES → queryCache.put(sql, command)
          └── NO  → 跳过缓存
    │
  耗时: ≈ 1-10ms (SQL 复杂度相关)

  性能提升:
  ┌──────────────────────┬──────────────┬──────────────┐
  │ 指标                 │ 快路径       │ 慢路径       │
  ├──────────────────────┼──────────────┼──────────────┤
  │ 典型耗时             │ 0.01ms       │ 1-10ms       │
  │ 加速比               │ 100x-1000x  │ 1x           │
  │ 触发条件             │ SQL 文本相同  │ 首次或 DDL 后 │
  │ CPU 消耗             │ 几乎为零      │ 解析 + 优化  │
  └──────────────────────┴──────────────┴──────────────┘
```
**图 7-13: 对比 prepareLocal 缓存命中与未命中路径**

如图 7-13 所示，缓存命中的快路径比完整编译的慢路径快 100-1000 倍。对于 OLTP 场景中重复执行的查询（如 `SELECT * FROM users WHERE id = ?`），缓存命中率通常超过 99%，这意味着绝大部分 `prepareLocal` 调用在微秒级别完成。

### 7.2.3 `Parser.prepareCommand(String sql)`

源码位置：`org/h2/command/Parser.java:485`

`Parser` 根据 SQL 的第一个关键字分发：

```text
Parser.prepareCommand(sql)
  │
  ├─ SELECT / TABLE / VALUES / WITH → parseQuery()  → Select
  ├─ INSERT                          → parseInsert() → Insert
  ├─ UPDATE                          → parseUpdate() → Update
  ├─ DELETE                          → parseDelete() → Delete
  ├─ CREATE                          → parseCreate()  → Create*
  ├─ ALTER                           → parseAlter()   → Alter*
  ├─ DROP                            → parseDrop()    → Drop*
  └─ ...其他                          → 对应 parse 方法
```

返回值包装为 `CommandContainer(session, sql, prepared)`，多条语句用 `CommandList`。

Parser 根据 SQL 第一个关键字的分发结构可按语句类型分组如下：

```text
SQL 关键字分发树
                        │
      解析入口: prepareCommand(sql)
                        │
                        ▼
             读取第一个 Token (关键字)
                        │
          ┌─────────────┴─────────────┐
          │                           │
     ┌────┴────┐               ┌─────┴──────┐
     │ DML 类   │               │  DDL 类     │
     │          │               │             │
     ├─ SELECT  │               ├─ CREATE     │
     ├─ INSERT  │               ├─ ALTER      │
     ├─ UPDATE  │               ├─ DROP       │
     ├─ DELETE  │               ├─ TRUNCATE   │
     ├─ MERGE   │               └─ ...        │
     └────┬─────┘                              │
          │                           ┌─────┴──────┐
          │                           │  其他类     │
          │                           │             │
          │                           ├─ CALL       │
          │                           ├─ EXPLAIN    │
          │                           ├─ SHOW       │
          │                           ├─ HELP       │
          │                           ├─ SCRIPT     │
          │                           └─ ...        │
          │                           └─────┬──────┘
          │                                  │
          ▼                                  ▼
   parseQuery/parseInsert/...         parseCreate/parseAlter/...
          │                                  │
          ▼                                  ▼
   Prepared 子类对象                   Create*/Alter* 对象
   (Select/Insert/...)                (DDL 语句)
```
**图 7-14: 拆解 Parser 关键字分发分支结构**

如图 7-14 所示，该图展示了 Parser 入口方法的分发逻辑。`prepareCommand` 读取 SQL 的第一个 token 后，根据其类型将控制权转交给对应的 parse 方法。DML 类语句（SELECT/INSERT/UPDATE/DELETE/MERGE）和 DDL 类语句（CREATE/ALTER/DROP）分别由不同的 parse 方法族处理。这种基于关键字的分发模式是手写解析器的典型设计——每个 SQL 关键字对应一个解析方法，方法之间通过关键字识别切换，无需解析器生成器的辅助。对于多条语句（以 `;` 分隔），则使用 `CommandList` 包装为复合命令。

### 7.2.4 解析流程

```text
SQL: "SELECT t.name FROM test t WHERE t.id = ? ORDER BY t.name"
  │
  ▼
Parser.parse(sql)
  │
  ├─ 词法分析: tokenize → [SELECT, t, ., name, FROM, test, t, WHERE, ...]
  │
  ├─ 识别关键字 "SELECT" → parseQuery()
  │     │
  │     ├─ parseSelect(): 解析 SELECT 列表
  │     ├─ parseFrom():   解析 FROM 子句 → 创建 TableFilter
  │     ├─ parseWhere():  解析 WHERE 子句 → 创建 Expression 树
  │     └─ parseOrder():  解析 ORDER BY
  │
  ├─ 返回 Select 对象（Prepared 的子类）
  │
  └─ new CommandContainer(session, sql, select)
```

解析过程可以抽象为从原始 SQL 文本到内部对象的三阶段管道：

```text
SQL 解析三阶段管道

阶段 1: 字符序列 → Token 序列
  "SELECT t.name FROM test t WHERE t.id = ? ORDER BY t.name"
    │
    │  tokenize()  词法分析
    │  ┌─────────────────────────────────────────────────────┐
    │  │ 逐个字符扫描 → 识别关键字 / 标识符 / 运算符 / 常量  │
    │  └─────────────────────────────────────────────────────┘
    │
    ▼
  Token 流: [SELECT] [IDENTIFIER:t] [.] [IDENTIFIER:name] [FROM]
            [IDENTIFIER:test] [IDENTIFIER:t] [WHERE] [IDENTIFIER:t]
            [.] [IDENTIFIER:id] [=] [?] [ORDER] [BY] [IDENTIFIER:t]
            [.] [IDENTIFIER:name]

阶段 2: Token 序列 → AST
  Token 流
    │
    │  parseQuery()  语法分析
    │  ┌─────────────────────────────────────────────────────┐
    │  │ 递归下降: 根据语法规则消费 Token, 构建对象结构      │
    │  │ parseSelect() → 消费 SELECT 相关 Token              │
    │  │ parseFrom()   → 消费 FROM 相关 Token                │
    │  │ parseWhere()  → 消费 WHERE 相关 Token               │
    │  │ parseOrder()  → 消费 ORDER BY 相关 Token            │
    │  └─────────────────────────────────────────────────────┘
    │
    ▼
  Select 对象 (包含 Expression 树, TableFilter 等)

阶段 3: AST → 可执行 Command
  Select 对象
    │
    │  new CommandContainer()
    │  ┌─────────────────────────────────────────────────────┐
    │  │ 将 Select 包装为 CommandContainer                   │
    │  │ 如果 SQL 包含多条语句 → CommandList                 │
    │  └─────────────────────────────────────────────────────┘
    │
    ▼
  CommandContainer (session, sql, select)
```
**图 7-15: 拆解 SQL 解析的词法语法包装三阶段**

如图 7-15 所示，该图将解析过程抽象为三个转换阶段：词法分析将字符序列转换为 Token 序列，语法分析将 Token 序列转换为面向对象的 AST（抽象语法树），最后的包装阶段将 AST 嵌入 Command 框架。每一阶段的输出是下一阶段的输入，形成了清晰的转换流水线。这种管道设计使得每一阶段可以独立优化——例如，词法分析器可以缓存 Token 流以实现快速重解析，语法分析器可以增量更新 AST。

### 7.2.5 解析阶段序列图

```text
Parser
  │
  │──nextToken()──────────────────────────────→ 词法分析
  │
  │──parseSelect()
  │    │
  │    ├──readColumnName()                    → 识别 "t.name"
  │    ├──readAlias()                         → 识别别名
  │    └──expressions.add(expr)              → 加入 SELECT 列表
  │
  │──parseFrom()
  │    │
  │    ├──readTableName()                    → 识别 "test"
  │    ├──readAlias()                        → 识别 "t"
  │    └──new TableFilter(session, table, alias, ...)
  │
  │──parseWhere()
  │    │
  │    ├──readColumnName()                   → "t.id"
  │    ├──readOperator()                     → "="
  │    ├──readParameter()                    → "?"
  │    └──new Comparison(EQUAL, exprCol, param)
  │
  │──parseOrder()
  │    └──sort.add(orderItem)
  │
  └──→ Select 对象
```

解析器内部各方法之间的调用关系及与表达式的交互可以进一步展开如下：

```text
parseQuery() 内部方法调用与对象创建时序
                        │
  外层方法              │  内层方法               │  创建的对象
                        │                         │
  parseQuery()          │                         │
    │                   │                         │
    ├── parseSelect()   │                         │
    │     │             │                         │
    │     ├── readColumnName()                    │
    │     │   └── readTerm()                      │
    │     │        → 消费 IDENTIFIER 序列         │
    │     │             │                         │  ExpressionColumn
    │     │             │                         │  (table=t, col=name)
    │     │             │                         │
    │     └── 添加到 selectList                   │  Expression[]
    │                   │                         │
    ├── parseFrom()     │                         │
    │     │             │                         │
    │     ├── readTableName()                     │
    │     │   → 消费 IDENTIFIER:test              │
    │     ├── readAlias()                         │
    │     │   → 消费 IDENTIFIER:t                 │
    │     └── new TableFilter()                   │  TableFilter
    │                   │                         │
    ├── parseWhere()    │                         │
    │     │             │                         │
    │     ├── readColumnName()                    │  ExpressionColumn
    │     ├── readOperator()                      │
    │     │   → 消费 '='                          │
    │     ├── readParameter()                     │  Parameter
    │     │   → 消费 '?'                          │
    │     └── new Comparison(EQUAL, ...)          │  Comparison
    │                   │                         │
    ├── parseOrder()    │                         │
    │     └── readOrderItem()                     │
    │         → 消费 ORDER BY 列和方向             │  OrderItem[]
    │                   │                         │
    └── return Select   │                         │  Select
```
**图 7-16: 追踪 parseQuery 内部方法与对象创建时序**

如图 7-16 所示，该图详细展开了解析器在 parseQuery 方法内部的调用链和对象创建过程。每个 parse 方法都对应 SQL 语法中的一个产生式：parseSelect 对应 SELECT 列表，parseFrom 对应 FROM 子句，parseWhere 对应 WHERE 条件。每个 parse 方法内部调用 read* 系列方法来消费 Token 流并创建相应的表达式对象。这种"一个方法对应一个语法规则"的设计使得代码结构与 SQL 语法高度对应，便于维护和扩展。


### 7.2.6 递归下降解析器调用栈

**图 7-17: 追踪 解析器内部的方法调用链**

如图 7-17 所示，H2 的 Parser 采用经典的手写递归下降解析方式，每个 SQL 语法规则对应一个独立的解析方法，方法之间通过相互调用来模拟语法树的递归下降过程。

```text
Parser.prepareCommand(sql)                                    ← 入口方法
  │
  ├─ tokenize(sql) → tokens[]                                ← 词法分析
  │     │
  │     ├─ readToken() → 识别 "SELECT" 关键字
  │     ├─ readToken() → 识别 "T" 标识符
  │     ├─ readToken() → 识别 "." 分隔符
  │     ├─ readToken() → 识别 "NAME" 标识符
  │     ├─ readToken() → 识别 "FROM" 关键字
  │     ├─ readToken() → 识别 "TEST" 标识符
  │     ├─ readToken() → 识别 "T" 标识符
  │     ├─ readToken() → 识别 "WHERE" 关键字
  │     └─ ...              继续处理剩余 token
  │
  ├─ parseQuery()                                            ← 语法分析入口
  │     │
  │     ├─ parseSelect()                                     ← 解析 SELECT 列表
  │     │     │
  │     │     ├─ readColumnName()  → ExpressionColumn("T.NAME")
  │     │     ├─ readAlias()       → null
  │     │     └─ select.addColumn(expr)
  │     │
  │     ├─ parseFrom()                                       ← 解析 FROM 子句
  │     │     │
  │     │     ├─ readTableName()  → "TEST"
  │     │     ├─ readAlias()      → "T"
  │     │     └─ new TableFilter(session, table, alias)
  │     │
  │     ├─ parseWhere()                                      ← 解析 WHERE 子句
  │     │     │
  │     │     ├─ readColumnName()  → ExpressionColumn("T.ID")
  │     │     ├─ readOperator()    → Comparison.EQUAL
  │     │     ├─ readParameter()   → Parameter(?)
  │     │     └─ new Comparison(EQUAL, left, right)
  │     │
  │     ├─ parseOrder()                                      ← 解析 ORDER BY
  │     │     └─ orderList.add(OrderItem("T.NAME", ASC))
  │     │
  │     └─ return Select对象
  │
  └─ return new CommandContainer(sql, select)                ← 包装返回
```
**图 7-77: 展示 递归下降解析器的调用栈结构**

如图 7-77 所示，该图揭示了递归下降解析的核心运作方式：`prepareCommand` 作为唯一的入口方法，首先调用 `tokenize` 将原始 SQL 文本切分为 token 流，然后分发到 `parseQuery` 方法。`parseQuery` 根据 SQL 类型（本例中为 SELECT）将控制权转交给 `parseSelect`。在 `parseSelect` 内部，解析过程按照 SQL 语法规则逐层深入：先解析 SELECT 列表中的列名和别名，再解析 FROM 子句中的表名和连接关系，接着解析 WHERE 子句中的条件表达式，最后处理 ORDER BY、GROUP BY 等排序和分组子句。

这种设计模式的核心优点在于：
- **代码与语法一一对应**：每个解析方法对应一个语法产生式，代码结构清晰易读
- **错误报告精准**：在哪个方法中抛出异常，就对应到哪个语法位置
- **支持任意前瞻**：方法可以在需要时超前读取多个 token，不受固定前瞻限制
- **性能优越**：无解析器生成器的启动开销，路径针对数据库 SQL 高度优化

缺点也很明显：Parser 的代码量较大（`Parser.java` 约 9300 行），维护成本高于使用 ANTLR 等生成器的方案。

从方法调用的深度角度，可以更直观地理解递归下降解析的嵌套层次：

```text
递归下降解析方法嵌套深度 (以 SELECT 为例)

深度 0: Parser.prepareCommand(sql)
  │
  ├── 深度 1: tokenize(sql)
  │     └── 深度 2: readToken()       ← 逐 token 读取
  │           └── 深度 3: 字符判断    ← 区分关键字/标识符/运算符
  │
  ├── 深度 1: parseQuery()
  │     │
  │     ├── 深度 2: parseSelect()
  │     │     ├── 深度 3: readColumnName()
  │     │     │     └── 深度 4: readTerm()    ← 消费 token 序列
  │     │     ├── 深度 3: readAlias()
  │     │     └── 深度 3: 循环 addColumn()
  │     │
  │     ├── 深度 2: parseFrom()
  │     │     ├── 深度 3: readTableName()
  │     │     ├── 深度 3: readAlias()
  │     │     └── 深度 3: 处理 JOIN (递归)
  │     │           └── 深度 4: parseJoin()
  │     │                 └── 深度 5: parseCondition()
  │     │
  │     ├── 深度 2: parseWhere()
  │     │     └── 深度 3: parseCondition()    ← 递归处理 AND/OR
  │     │           ├── 深度 4: parseAnd()
  │     │           └── 深度 4: parseOr()
  │     │
  │     └── 深度 2: parseOrder()
  │           └── 深度 3: readOrderItem()
  │
  └── 深度 1: new CommandContainer()

  最大嵌套深度: 5 (当 FROM 包含 JOIN 且 WHERE 包含嵌套条件时)
```
**图 7-18: 刻画 递归下降解析方法的嵌套深度**

如图 7-18 所示，该图从调用栈深度的角度展示了递归下降解析的层次结构。最大嵌套深度通常不超过 5 层——即使在处理 JOIN 和嵌套条件时，递归深度也是有限的。这种浅层递归保证了调用栈不会溢出，同时也说明了解析器的控制流是扁平的（相比于表达式求值的深层递归）。每个解析方法的职责边界清晰，方法的返回即为对应语法元素的解析完成时刻。

**图 7-19: 追踪 词法分析器 Token 流的生成路径**

如图 7-19 所示，在递归下降解析之前，Parser 需要先将原始 SQL 文本转换为 Token 流。H2 的 `Parser` 内部集成了手写的词法分析器，`nextToken()` 方法负责从当前位置读取下一个 Token。

```text
原始 SQL 字符串: "SELECT t.name FROM test t WHERE t.id = ?"
                        │
                        ▼
nextToken() 循环:
                        │
  ┌─────────────────────┴──────────────────────┐
  │  字符类型判断                                │
  │                                            │
  │  当前字符 c = readChar()                   │
  │      │                                     │
  │      ├─ c 是字母 ─→ 进入标识符/关键字状态    │
  │      │     │                                │
  │      │     ├─ 累积字符直到非字母数字         │
  │      │     ├─ 查关键字表:                   │
  │      │     │   "SELECT" → KEYWORD_SELECT   │
  │      │     │   "FROM"   → KEYWORD_FROM     │
  │      │     │   "WHERE"  → KEYWORD_WHERE    │
  │      │     │   其他     → IDENTIFIER        │
  │      │     └─ 返回 Token(type, value)       │
  │      │                                     │
  │      ├─ c 是数字 ─→ 进入数值常量状态          │
  │      │     │                                │
  │      │     ├─ 累积数字和小数点               │
  │      │     └─ 返回 Token(NUMERIC, value)    │
  │      │                                     │
  │      ├─ c 是单引号 ─→ 进入字符串状态          │
  │      │     │                                │
  │      │     ├─ 累积直到下一个单引号           │
  │      │     └─ 返回 Token(STRING, value)     │
  │      │                                     │
  │      ├─ c 是运算符 ─→ 进入运算符状态          │
  │      │     │                                │
  │      │     ├─ '='  → 返回 Token(EQUAL)     │
  │      │     ├─ '>'  → 检查下一个字符         │
  │      │     │    ├─ '=' → Token(BIGGER_EQUAL)│
  │      │     │    └─ else → Token(BIGGER)    │
  │      │     ├─ '<'  → 检查下一个字符         │
  │      │     │    ├─ '=' → Token(SMALLER_EQUAL)
  │      │     │    ├─ '>' → Token(NOT_EQUAL)  │
  │      │     │    └─ else → Token(SMALLER)   │
  │      │     └─ ...其他运算符                  │
  │      │                                     │
  │      ├─ c 是 '?' ─→ 返回 Token(PARAMETER)   │
  │      │                                     │
  │      ├─ c 是 ';' ─→ 返回 Token(SEMICOLON)   │
  │      │                                     │
  │      └─ c 是空白 ─→ 跳过, 继续读下一个字符   │
  │                                            │
  └─────────────────────────────────────────────┘
        │
        ▼
  Token 流: [SELECT] [IDENTIFIER:t] [.] [IDENTIFIER:name]
            [FROM] [IDENTIFIER:test] [IDENTIFIER:t]
            [WHERE] [IDENTIFIER:t] [.] [IDENTIFIER:id]
            [=] [?]
            
  送入 Parser.parseQuery() 进行语法分析
```
**图 7-78: 拆解 Tokenizer 字符分类与状态切换**

如图 7-78 所示，词法分析是 SQL 解析的第一阶段，其核心任务是将字符序列转换为有意义的 Token 序列。H2 的词法分析器嵌入在 `Parser.java` 中，没有独立的 Tokenizer 类，这种设计在减少对象创建开销的同时，也使得解析器的代码组织更紧凑。

Token 的类型包括：
- **关键字**：如 SELECT、FROM、WHERE、AND、OR、ORDER 等 SQL 保留字。H2 不区分大小写，关键字表使用小写存储，比较时统一转换
- **标识符**：表名、列名、别名等用户定义名称。支持双引号引用的带特殊字符的标识符
- **数值常量**：整数和浮点数字面值
- **字符串常量**：单引号包围的字符串字面值
- **运算符**：=、>、<、>=、<=、<> 等比较运算符，以及 +、-、*、/ 等算术运算符
- **分隔符**：. (点号)、, (逗号)、( (左括号)、) (右括号)、; (分号)
- **参数占位符**：? 表示参数化查询中的占位符

词法分析器使用一个位置指针遍历 SQL 字符数组，通过 `nextToken()` 方法逐个读取 Token。该方法不回溯（backtracking），保证了 O(n) 的时间复杂度。在识别标识符时，分析器会查关键字表以区分保留字和普通标识符——这一设计使得关键字可以作为列名使用（除非在特定语法位置有歧义）。

SQL 文本到 Token 流的转换过程可以通过以下示例直观展示输入输出关系：

```text
Token 生成示例: 输入 SQL → Token 流

输入: "SELECT t.name FROM test t WHERE t.id = ?"
                        │
                        ▼
  位置 0: 'S' ─→ 字母 → 累积: "SELECT" → 查关键字表 → KEYWORD_SELECT
  位置 6: ' '  ─→ 空白 → 跳过
  位置 7: 't'  ─→ 字母 → 累积: "t"     → 查关键字表 → IDENTIFIER
  位置 8: '.'  ─→ 分隔符 → DOT
  位置 9: 'n'  ─→ 字母 → 累积: "name"  → 查关键字表 → IDENTIFIER
  位置 13: ' ' ─→ 空白 → 跳过
  位置 14: 'F' ─→ 字母 → 累积: "FROM"  → 查关键字表 → KEYWORD_FROM
  位置 18: ' ' ─→ 空白 → 跳过
  位置 19: 't' ─→ 字母 → 累积: "test"  → 查关键字表 → IDENTIFIER
  位置 23: ' ' ─→ 空白 → 跳过
  位置 24: 't' ─→ 字母 → 累积: "t"     → 查关键字表 → IDENTIFIER
  位置 25: ' ' ─→ 空白 → 跳过
  位置 26: 'W' ─→ 字母 → 累积: "WHERE" → 查关键字表 → KEYWORD_WHERE
  位置 31: ' ' ─→ 空白 → 跳过
  位置 32: 't' ─→ 字母 → 累积: "t"     → IDENTIFIER
  位置 33: '.' ─→ DOT
  位置 34: 'i' ─→ 字母 → 累积: "id"    → IDENTIFIER
  位置 36: ' ' ─→ 空白 → 跳过
  位置 37: '=' ─→ 运算符 → EQUAL
  位置 38: ' ' ─→ 空白 → 跳过
  位置 39: '?' ─→ 参数占位符 → PARAMETER
  位置 40: 结束

输出 Token 流:
  0: KEYWORD_SELECT  "SELECT"
  1: IDENTIFIER      "t"
  2: DOT             "."
  3: IDENTIFIER      "name"
  4: KEYWORD_FROM    "FROM"
  5: IDENTIFIER      "test"
  6: IDENTIFIER      "t"
  7: KEYWORD_WHERE   "WHERE"
  8: IDENTIFIER      "t"
  9: DOT             "."
  10: IDENTIFIER      "id"
  11: EQUAL           "="
  12: PARAMETER       "?"
```
**图 7-20: 演示 SQL 文本到 Token 流的逐字符切分**

```text
如图 7-20 所示，该图以逐字符方式展示了词法分析器如何处理一条具体的 SQL 语句。位置指针从 0 开始顺序扫描字符，对每个字符判断其类型（字母→标识符/关键字、数字→数值、运算符→运算符等），然后累积字符直到无法继续匹配为止。关键字识别的关键步骤是查表：累积的字符串先与关键字表比较，匹配则返回关键字类型，不匹配则作为普通标识符。这种设计使得 `SELECT` 作为关键字返回 `KEYWORD_SELECT`，而 `test` 这样的表名则返回 `IDENTIFIER`。整个扫描过程是 O(n) 的，每个字符只被读取一次。
```

### 7.2.7 抽象语法树构建过程
**图 7-21: 追踪 SQL 文本到 AST 的两阶段构建路径**

如图 7-21 所示，通过词法分析和语法分析后，Parser 将 SQL 文本转化为面向对象的抽象语法树（AST）。

```text
SQL: "SELECT t.name, t.id FROM test t WHERE t.id = 1 ORDER BY t.name"
                        │
                        ▼
     ┌─────────────────────────────────────────────────────────┐
     │  CommandContainer                                         │
     │  ┌───────────────────────────────────────────────────┐   │
     │  │  Select                                            │   │
     │  │  ┌──────────────────────────────────────────┐      │   │
     │  │  │  selectList: Expression[]                 │      │   │
     │  │  │   ├── ExpressionColumn (table=t, col=name)│      │   │
     │  │  │   └── ExpressionColumn (table=t, col=id)  │      │   │
     │  │  │                                            │      │   │
     │  │  │  from: TableFilter[]                      │      │   │
     │  │  │   └── TableFilter (table=test, alias=t)    │      │   │
     │  │  │                                            │      │   │
     │  │  │  whereCondition: Expression                 │      │   │
     │  │  │   └── Comparison (type=EQUAL)              │      │   │
     │  │  │        ├── left: ExpressionColumn (t.id)   │      │   │
     │  │  │        └── right: ValueExpression (1)     │      │   │
     │  │  │                                            │      │   │
     │  │  │  orderList: OrderItem[]                    │      │   │
     │  │  │   └── OrderItem (expr=t.name, type=ASC)   │      │   │
     │  │  └──────────────────────────────────────────┘      │   │
     │  └───────────────────────────────────────────────────┘   │
     └─────────────────────────────────────────────────────────┘
                        │
                        ▼
    在 Select.prepare() 阶段, AST 进一步扩展:
                        │
                        ▼
     ┌─────────────────────────────────────────────────────────┐
     │  Select (已准备)                                         │
     │  ┌───────────────────────────────────────────────────┐   │
     │  │  expandSelectList() → 展开 * 为具体列名            │   │
     │  │  mapColumns()       → 列引用绑定到 TableFilter    │   │
     │  │  init()             → 初始化子查询, 聚合函数        │   │
     │  │  preparePlan()      → Optimizer 生成执行计划        │   │
     │  │  createIndexConditions() → 提取索引可用条件         │   │
     │  └───────────────────────────────────────────────────┘   │
     └─────────────────────────────────────────────────────────┘
```
**图 7-79: 拆解 AST 在解析与准备阶段的扩展**

如图 7-79 所示，该图展示了从 SQL 文本到内存对象结构的两个阶段：

**第一阶段：Parser 构建原始 AST**

在解析阶段，Parser 创建了面向对象的层次结构：顶层是 `CommandContainer`，内部持有 `Select`（或 `Insert`/`Update`/`Delete` 等其他 `Prepared` 子类）。`Select` 内部进一步细分为 `selectList`（列表达式数组）、`from`（表过滤器数组）、`whereCondition`（条件表达式树）、`orderList`（排序项数组）。条件表达式本身也是一个递归结构：`Comparison` 作为二元操作符包含左右两个子表达式，子表达式可以是 `ExpressionColumn`（列引用）、`ValueExpression`（常量）、`Subquery`（子查询）或 `Parameter`（参数占位符）。

**第二阶段：prepare() 语义扩展**

在 `Select.prepare()` 阶段，原始的 AST 经过语义分析得到扩展和充实：
- `expandSelectList()` — 将 `SELECT *` 展开为具体的列引用列表
- `mapColumns()` — 将每个 `ExpressionColumn` 中的列名解析为具体的 `TableFilter` + 列序号映射。此时会检查列名的歧义性（如果多个表有同名列，需要表名前缀消除歧义）
- `init()` — 初始化子查询、聚合函数、窗口函数等复杂表达式，创建必要的中间数据结构
- `preparePlan()` — 调用 `Optimizer` 生成最优连接顺序和索引选择方案
- `createIndexConditions()` — 遍历 WHERE 条件树，提取可以与索引匹配的条件片段，为后续的索引选择做准备

这种两阶段设计（解析 + 准备）将语法分析（Parsing）与语义分析（Semantic Analysis）分离。语法分析阶段只关心 SQL 文本的结构合法性，语义分析阶段才处理列存在性验证、类型检查和执行计划优化。这种关注点分离使代码结构更加清晰，也为查询缓存提供了便利——SQL 文本相同即可复用 AST，无需重复语义分析。

从 SQL 语句到最终执行计划的对象变换过程可以总结为以下转换链：

```text
SQL 到执行计划的对象变换链
                        │
  步骤 1: SQL 文本
    "SELECT t.name FROM test t WHERE t.id = 1 ORDER BY t.name"
                        │
                        │ Parser.parse()  ← 语法分析
                        ▼
  步骤 2: 原始 AST (Select 对象)
    ┌──────────────────────────────────────────┐
    │  Select                                  │
    │  ├── selectList: Expression[]            │
    │  ├── from: TableFilter[]                 │
    │  ├── whereCondition: Expression          │
    │  └── orderList: OrderItem[]              │
    └──────────────────────────────────────────┘
                        │
                        │ Select.init() + prepare()  ← 语义分析
                        ▼
  步骤 3: 已准备 AST (带语义信息)
    ┌──────────────────────────────────────────┐
    │  Select (已准备)                          │
    │  ├── SELECT * 已展开为具体列              │
    │  ├── 列引用已绑定到 TableFilter + 列序号   │
    │  ├── 子查询已初始化                        │
    │  └── 索引条件已提取                        │
    └──────────────────────────────────────────┘
                        │
                        │ Select.preparePlan() → Optimizer  ← 查询优化
                        ▼
  步骤 4: 执行计划 (带 PlanItem)
    ┌──────────────────────────────────────────┐
    │  Select (已优化)                          │
    │  ├── topTableFilter: T1 → T2 (连接顺序)   │
    │  ├── T1.planItem: {index: PK, cost:1}    │
    │  ├── T2.planItem: {index: IDX, cost:5}   │
    │  └── indexConditions 已设置               │
    └──────────────────────────────────────────┘
                        │
                        │ Select.query()  ← 执行查询
                        ▼
  步骤 5: 结果集 (ResultInterface)
    ┌──────────────────────────────────────────┐
    │  PseudoResultSet 或 LocalResult           │
    │  ├── rows: Value[][]                     │
    │  └── rowCount: int                       │
    └──────────────────────────────────────────┘

  数据规模变化 (典型查询):
    SQL 文本:  ~100 字符
    AST:       ~10-50 个对象
    执行计划:   ~10-30 个对象
    结果集:     ~N 行 × M 列
```
**图 7-22: 追踪 SQL 到执行计划的对象变换链**

如图 7-22 所示，该图展示了 SQL 到执行结果的完整变换链。每个变换步骤都加工和转换数据：Parser 将文本转换为 AST，语义分析为 AST 绑定列引用和类型信息，优化器选择连接顺序和索引，执行器驱动内核迭代数据行。每个步骤的输入输出数据结构和规模都不同。值得注意的是，优化阶段是唯一可能改变数据结构的步骤——它会重排 TableFilter 的顺序。这种"先优化后执行"的策略是关系数据库的通用设计模式。

## 7.3 缓存机制

### 7.3.1 缓存结构

`SessionLocal` 内部维护一个 `SmallLRUCache`（LRU 策略），大小由 `queryCacheSize` 控制：

```java
// SessionLocal.java:628-642
if (queryCacheSize > 0) {
    if (queryCache == null) {
        queryCache = SmallLRUCache.newInstance(queryCacheSize);
        modificationMetaID = getDatabase().getModificationMetaId();
    } else {
        long newModificationMetaID = getDatabase().getModificationMetaId();
        if (newModificationMetaID != modificationMetaID) {
            queryCache.clear();      // DDL 后清空缓存
            modificationMetaID = newModificationMetaID;
        }
        command = queryCache.get(sql);      // 精确匹配 SQL 文本
        if (command != null && command.canReuse()) {
            command.reuse();
            return command;                 // 缓存命中
        }
    }
}
```

缓存在整个 Session 中的位置和与周边组件的关系如下：

```text
查询缓存在 Session 中的位置
                        │
  ┌──────────────────────────────────────────────────────────┐
  │  SessionLocal                                             │
  │                                                           │
  │  ┌────────────────────────────────────────────────────┐   │
  │  │  queryCache: SmallLRUCache<String, Command>         │   │
  │  │  ┌──────────────────────────────────────────────┐  │   │
  │  │  │  键 (K): SQL 文本                              │  │   │
  │  │  │    "SELECT * FROM t WHERE id = ?"             │  │   │
  │  │  │    "INSERT INTO t VALUES (?, ?)"              │  │   │
  │  │  │    ...                                        │  │   │
  │  │  ├──────────────────────────────────────────────┤  │   │
  │  │  │  值 (V): Command 对象                          │  │   │
  │  │  │    CommandContainer(prepared=Select)          │  │   │
  │  │  │    CommandContainer(prepared=Insert)          │  │   │
  │  │  │    ...                                        │  │   │
  │  │  ├──────────────────────────────────────────────┤  │   │
  │  │  │  属性:                                        │  │   │
  │  │  │    maxSize: 8 (默认, 可通过 SQL 设置调整)     │  │   │
  │  │  │    currentSize: 3                            │  │   │
  │  │  └──────────────────────────────────────────────┘  │   │
  │  │                                                      │   │
  │  │  modificationMetaID: long                          │   │
  │  │    └── 与 Database.modificationMetaID 比较          │   │
  │  │        用于检测 DDL 变更                            │   │
  │  └────────────────────────────────────────────────────┘   │
  │                                                           │
  │  prepareLocal(sql) 调用路径:                               │
  │    ┌──────────┐    ┌──────────────┐    ┌─────────────┐    │
  │    │ 缓存检查  │───→│ 缓存命中?    │───→│ command.    │    │
  │    │ cache.get │    │  ├─ YES:    │    │ reuse()     │    │
  │    │ (sql)     │    │  └─ NO:     │    │             │    │
  │    └──────────┘    │     parser   │    │ return cmd  │    │
  │                    │     .prepare │    └─────────────┘    │
  │                    └──────────────┘                       │
  └──────────────────────────────────────────────────────────┘
```
**图 7-23: 拆解 SmallLRUCache 在 Session 的位置**

如图 7-23 所示，该图展示了查询缓存在 Session 中的存储结构和访问方式。缓存的核心是一个 `SmallLRUCache` 实例，以 SQL 文本为键、以 `Command` 对象为值。每个 Session 持有自己的缓存实例，缓存大小默认不超过 8 条。`modificationMetaID` 是缓存的版本控制字段，与 `Database` 层协同工作来实现 DDL 后的缓存失效。prepareLocal 方法的调用路径中，缓存检查总是最先执行——这是保证性能的关键：缓存命中时完全跳过解析和优化阶段。

```text
SmallLRUCache 驱逐过程 (maxSize = 4)
                        │
  初始状态: 缓存为空
    ┌──────────────────────────────────┐
    │   [空]                           │
    └──────────────────────────────────┘
                        │
  INSERT 1 → 插入 "SELECT 1"
    ┌──────────────────────────────────┐
    │  ["SELECT 1"]                    │  最近使用
    └──────────────────────────────────┘
                        │
  INSERT 2 → 插入 "SELECT 2"
    ┌──────────────────────────────────┐
    │  ["SELECT 2", "SELECT 1"]       │  最近使用
    └──────────────────────────────────┘
                        │
  INSERT 3, INSERT 4 (已满)
    ┌──────────────────────────────────┐
    │  ["SELECT 4", "SELECT 3",       │  最近使用
    │   "SELECT 2", "SELECT 1"]       │
    └──────────────────────────────────┘
                        │
  ACCESS "SELECT 1" (命中, 移到头部)
    ┌──────────────────────────────────┐
    │  ["SELECT 1", "SELECT 4",       │  最近使用
    │   "SELECT 3", "SELECT 2"]       │
    └──────────────────────────────────┘
                        │
  INSERT 5 (已满, 驱逐 SELECT 2)
    ┌──────────────────────────────────┐
    │  ["SELECT 5", "SELECT 1",       │  最近使用
    │   "SELECT 4", "SELECT 3"]       │
    └──────────────────────────────────┘
    驱逐 "SELECT 2" (最久未访问) ──────→ 丢弃
```
**图 7-24: 演示 SmallLRUCache 的 LRU 驱逐过程**

### 7.3.2 缓存失效

如图 7-24 所示，缓存失效有三种触发场景，每种场景的处理方式不同：

```text
缓存失效的三种场景
                        │
  场景 1: DDL 操作                     场景 2: 非缓存语句         场景 3: 命令不可复用
  (CREATE/ALTER/DROP)                  (SELECT FOR UPDATE 等)     (表已删除等)
                        │                     │                         │
  Database              │                     │                         │
  modificationMetaID++  │                     │                         │
        │               │                     │                         │
        ▼               │                     │                         │
  SessionLocal          │                     │                         │
  检测到版本不匹配       │                     │                         │
        │               │                     │                         │
  queryCache.clear()    │              isCacheable()=false       command.canReuse()=false
  全部清空!             │              跳过缓存写入              放弃缓存项, 重新解析
                        │                     │                         │
  影响范围: 所有 Session  │             影响范围: 仅当前语句     影响范围: 仅当前语句
  开销: 全缓存遍历 O(n)   │             开销: 几乎为零          开销: 一次额外检查
```
**图 7-25: 罗列 缓存失效的三种触发场景**

如图 7-25 所示，三种失效场景的严重程度不同：DDL 导致的全部缓存清空影响最大，但发生频率最低（仅在表结构变更时）。非缓存语句和命令不可复用是局部影响，只涉及当前语句。失效策略的设计目标是正确性高于性能——宁可多失效也不能返回过时的查询计划。

```text
如图 7-26 所示，DDL 缓存失效跨 Session 传播流程
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  Session A                        Session B                      │
  │  ┌───────────┐                    ┌───────────┐                  │
  │  │ queryCache│                    │ queryCache│                  │
  │  │ ┌───────┐ │                    │ ┌───────┐ │                  │
  │  │ │SEL 1  │ │                    │ │SEL 2  │ │                  │
  │  │ │SEL 2  │ │                    │ │SEL 3  │ │                  │
  │  │ │INS 1  │ │                    │ │SEL 1  │ │                  │
  │  │ └───────┘ │                    │ └───────┘ │                  │
  │  └───────────┘                    └───────────┘                  │
  └─────────────────────────────────────────────────────────────────┘
                              │
  ┌─────────────────────────────────────────────────────────────────┐
  │  Database 层 (全局 meta 版本控制)                                 │
  │                                                                  │
  │  modificationMetaID (初始 = 0)                                    │
  │                                                                  │
  │  Session A 执行: ALTER TABLE t ADD COLUMN x INT                  │
  │    ↓                                                              │
  │  Database.modificationMetaID++  (1 → 2)                          │
  │    ↓                                                              │
  │  广播: 所有 Session 在下次 prepareLocal() 时检测                 │
  └─────────────────────────────────────────────────────────────────┘
                              │
  ┌─────────────────────────────────────────────────────────────────┐
  │  Session A (执行 DDL 的 Session):                                 │
  │    1. DDL 直接写库, 修改 meta                                      │
  │    2. Database.modificationMetaID++                               │
  │    3. SessionA.queryCache 在 prepareLocal() 开始时检测:            │
  │       newID != localCachedID  →  clear() + 更新本地 ID            │
  │                                                                  │
  │  Session B (其他 Session):                                        │
  │    1. 下次 prepareLocal(sql) 时:                                  │
  │       queryCache.get(sql) → 查询命中                              │
  │       command.canReuse()  → true                                  │
  │       command.reuse()     → 返回旧计划 (⚠ 仍使用旧 Schema!)       │
  │                                                                  │
  │    2. 在进入 prepareLocal 前检测:                                  │
  │       newModificationMetaID != modificationMetaID                 │
  │       → queryCache.clear()                                       │
  │       → 重新解析, 使用新 Schema                                   │
  └─────────────────────────────────────────────────────────────────┘
```
**图 7-26: 追踪 DDL 引发的跨 Session 缓存失效路径**

### 7.3.3 缓存关键路径

```text
prepareLocal(sql)
  │
  ├─ queryCache.get(sql)
  │     ├─ 命中 → command.reuse() → return
  │     └─ 未命中 → parser.prepareCommand(sql)
  │
  └─ queryCache.put(sql, command)  ← 缓存新语句
```

在 prepareLocal 中，缓存决策路径可以分为三种情况：

```text
prepareLocal 三路分支决策
                        │
  prepareLocal(sql)
    │
    ├── 1. queryCacheSize == 0?
    │     └── YES → 缓存已禁用
    │           └── parser.prepareCommand(sql)    ← 每次都完整解析
    │                 └── return command
    │
    ├── 2. queryCache.get(sql) 命中 + canReuse()?
    │     └── YES → 缓存命中
    │           ├── command.reuse()               ← 重置执行状态
    │           └── return command                ← 耗时 ≈ 0.01ms
    │
    └── 3. 缓存未命中 / 不可复用
          │
          ├── new Parser(session)                 ← 创建解析器
          ├── parser.prepareCommand(sql)          ← 完整编译
          │     └── 耗时 ≈ 1-10ms
          │
          └── isCacheable()?
                ├── YES → queryCache.put(sql, cmd)  ← 入缓存
                └── NO  → 跳过缓存
                      └── return command

  如图 7-27 所示，各分支的耗时占比:
  ┌──────────────────┬────────────┬────────────┬─────────────┐
  │ 分支              │ 耗时       │ 占比       │ 优化建议     │
  ├──────────────────┼────────────┼────────────┼─────────────┤
  │ 缓存命中          │ 0.01ms     │ <1%        │ 无 (已达最优) │
  │ 缓存未命中 + 解析  │ 1-10ms    │ 99%+       │ 扩大缓存     │
  │ 缓存禁用          │ 1-10ms    │ 99%+       │ 启用缓存     │
  └──────────────────┴────────────┴────────────┴─────────────┘
```
**图 7-27: 对比 prepareLocal 三路分支耗时占比**

如图 7-28 所示，该图将 `prepareLocal` 的缓存逻辑总结为三个清晰的分支。对于 OLTP 系统，目标是将路径 2（缓存命中）的占比提升到 99% 以上——这意味着只有首次执行和 DDL 后需要走完整的解析路径。路径 1（缓存禁用）通常出现在测试环境或特殊的低内存场景中，生产环境应确保 `queryCacheSize > 0`。

### 7.3.4 SmallLRUCache 内部结构

**图 7-28: 拆解 SmallLRUCache 哈希表与双向链表**

查询缓存使用 `SmallLRUCache` 实现，这是一种基于双向链表 + 哈希表的 LRU 缓存结构。

```text
SmallLRUCache<String, Command> 内部结构:

 ┌─────────────────────────────────────────────────────────────────┐
 │  hashMap: HashMap<K, Node<K,V>>                                 │
 │  ┌─────────────────────────────────────────────────────────┐    │
 │  │  hash("SELECT * FROM test WHERE id = ?") → 0xA3F2       │    │
 │  │                                                          │    │
 │  │  bucket[0xA3F2 % n] → Node(key=sql1, value=cmd1)       │    │
 │  │  bucket[...]        → Node(key=sql2, value=cmd2)       │    │
 │  │  bucket[...]        → Node(key=sql3, value=cmd3)       │    │
 │  └─────────────────────────────────────────────────────────┘    │
 │                                                                  │
 │  双向链表 (LRU 顺序):                                            │
 │                                                                  │
 │   最近使用 (链表头)             最近最少使用 (链表尾)            │
 │   ┌──────┐    ┌──────┐    ┌──────┐                              │
 │   │cmd2  │◄──►│cmd1  │◄──►│cmd3  │                              │
 │   │key=s2│    │key=s1│    │key=s3│                              │
 │   └──────┘    └──────┘    └──────┘                              │
 │      ↑           ↑            ↑                                 │
 │    head        mid          tail  ← 淘汰时从尾部移除            │
 │                                                                  │
 │  maxSize: 8 (默认)                                              │
 │  currentSize: 3                                                 │
 └─────────────────────────────────────────────────────────────────┘

访问 cmd2 后的链表状态 (cmd2 移到头部):
   ┌──────┐    ┌──────┐    ┌──────┐
   │cmd2  │◄──►│cmd1  │◄──►│cmd3  │
   └──────┘    └──────┘    └──────┘
      ↑           ↑            ↑
    head                     tail

如图 7-80 所示，插入新 cmd4 (缓存已满, 淘汰尾部 cmd3):
   ┌──────┐    ┌──────┐    ┌──────┐
   │cmd4  │◄──►│cmd2  │◄──►│cmd1  │
   └──────┘    └──────┘    └──────┘
      ↑                       ↑
    head                    tail  (cmd3 已被移除)
```
**图 7-80: 标注 SmallLRUCache 双向链表的访问与淘汰**

`SmallLRUCache` 是 H2 针对查询缓存场景专门优化的 LRU 实现，结合了哈希表的快速查找和双向链表的顺序维护能力：

- 哈希表提供 O(1) 的随机访问能力。给定 SQL 文本，通过 `hashCode()` 计算哈希值后直接在桶中定位对应的缓存节点
- 双向链表维护缓存项的访问顺序。每次缓存命中时，将对应节点移动到链表头部；缓存未命中时在头部插入新节点
- 当缓存大小超过 `maxSize` 时，从链表尾部淘汰最久未使用的节点
- H2 的默认缓存大小为 8，这在大多数 OLTP 场景下已足够——实际应用中重复执行的查询通常只有少数几条核心 SQL

LRU 策略的有效性基于"访问局部性"原理：同一个 session 中，刚刚执行过的 SQL 往往会在短时间内再次执行。将最近使用的缓存项保留在链表头部，确保它们不会被过早淘汰。

SmallLRUCache 的 get/put 操作在哈希表和双向链表上的协作流程如下：

```java
SmallLRUCache.get(key) 和 put(key, value) 的操作流程

get(key):
  1. hash = key.hashCode()
  2. bucket = hashMap.get(hash)          ← O(1) 哈希查找
  3. if bucket == null → return null     ← 未命中
  4. node = bucket.getValue()
  5. moveToHead(node)                    ← 移到链表头 (LRU 更新)
  6. return node.getValue()

put(key, value):
  1. hash = key.hashCode()
  2. if hashMap.containsKey(hash):
       node = hashMap.get(hash)
       node.setValue(value)              ← 更新已有节点
       moveToHead(node)
  3. else:
       if size >= maxSize:
         tail = removeTail()             ← 淘汰尾部 (LRU 淘汰)
         hashMap.remove(tail.getKey())
       newNode = new Node(key, value)
       addToHead(newNode)                ← 插入链表头
       hashMap.put(hash, newNode)
       size++

moveToHead(node):
  1. if node == head → return            ← 已在头部
  2. node.prev.next = node.next          ← 从当前位置移除
  3. node.next.prev = node.prev
  4. node.next = head                    ← 插入头部
  5. node.prev = null
  6. head.prev = node
  7. head = node

  如图 7-29 所示，SmallLRUCache 操作时间复杂度:
  ┌────────────┬──────────┬──────────────────────┐
  │ 操作        │ 复杂度   │ 说明                  │
  ├────────────┼──────────┼──────────────────────┤
  │ get(key)   │ O(1)     │ 哈希查找 + 链表移动   │
  │ put(key,v) │ O(1)     │ 哈希插入 + 链表操作   │
  │ remove(k)  │ O(1)     │ 哈希删除 + 链表操作   │
  │ clear()    │ O(n)     │ 清空哈希表和链表       │
  └────────────┴──────────┴──────────────────────┘
```
**图 7-29: 拆解 SmallLRUCache get/put 的链表协作**

如图 7-30 所示，该图展示了 SmallLRUCache 的 get 和 put 方法在哈希表和双向链表上的完整操作步骤。get 操作首先通过哈希表进行 O(1) 查找，如果找到则将对应节点移动到链表头部（更新 LRU 顺序）并返回值。put 操作需要处理命中更新和未命中插入两种子情况：命中时直接更新值并移动到头部，未命中时需要先检查容量，必要时淘汰链表尾部的最近最少使用节点，然后创建新节点插入头部。所有操作的时间复杂度均为 O(1)，这是 LRU 缓存的经典实现方式。

### 7.3.5 缓存完整决策流程

**图 7-30: 拆解 prepareLocal 缓存命中决策流程**

```text
如图 7-68 所示，prepareLocal(sql)
  │
  ├─ 1. queryCacheSize > 0 ?
  │     │
  │     ├── NO ──→ 跳过缓存, 直接解析
  │     │         parser.prepareCommand(sql)
  │     │         return command
  │     │
  │     └── YES ──→ 继续
  │
  ├─ 2. queryCache == null ?
  │     │
  │     ├── YES ──→ new SmallLRUCache(queryCacheSize)
  │     │           modificationMetaID = database.getModificationMetaId()
  │     │
  │     └── NO ──→ 继续
  │
  ├─ 3. 检查 DDL 版本:
  │     currentMetaID = database.getModificationMetaId()
  │     │
  │     ├── currentMetaID != modificationMetaID ?
  │     │     │
  │     │     ├── YES ──→ DDL 已变更
  │     │     │           queryCache.clear()     ← 全部缓存失效
  │     │     │           modificationMetaID = currentMetaID
  │     │     │
  │     │     └── NO ──→ 缓存未因 DDL 失效
  │     │
  │     └── (继续)
  │
  ├─ 4. queryCache.get(sql)
  │     │
  │     ├── 命中 ──→ command.canReuse() ?
  │     │     │
  │     │     ├── YES ──→ command.reuse()     ← 参数重新绑定
  │     │     │           return command       ← 缓存命中, 直接返回
  │     │     │
  │     │     └── NO ──→ 命令不可复用, 走解析
  │     │
  │     └── 未命中 ──→ 走解析
  │
  ├─ 5. 解析 (缓存未命中或不可用时):
  │     parser = new Parser(this)
  │     command = parser.prepareCommand(sql)   ← 完整解析
  │
  ├─ 6. 尝试入缓存:
  │     command.isCacheable() ?
  │     │
  │     ├── YES ──→ queryCache.put(sql, command)
  │     │
  │     └── NO ──→ 不入缓存
  │
  └─ 7. return command
```
**图 7-68: 归纳 缓存命中决策的七步检查流程**

该图详细展示了查询缓存的完整决策路径，核心设计要点包括：

1. **DDL 版本检查优先于缓存查找**：每次请求都先检查 `modificationMetaID`。一旦发生 DDL 操作（CREATE/ALTER/DROP），全部缓存立即清空。这是因为 DDL 可能改变表结构、索引分布或统计信息，使得已编译的查询计划变得过时。

2. **双重检查机制**：缓存命中后还需要检查 `command.canReuse()`。这个方法检查命令是否因为会话状态变更而不再可用（例如引用的表已被删除）。这提供了第二层安全校验。

3. **缓存条件限制**：`isCacheable()` 返回 false 的情况包括：包含 CURRENT_TIMESTAMP 等非确定性函数的查询、SELECT FOR UPDATE 语句、使用了临时表的查询等。这些查询每次执行都可能产生不同结果或需要特殊处理，因此不适合缓存。

缓存决策流程中的关键检查点及其检查内容总结如下：

```text
缓存决策关键检查点总结

检查点 1: queryCacheSize > 0?
  ├── 检查目的: 缓存是否启用
  ├── 配置来源: Session 设置 (SET QUERY_CACHE_SIZE)
  └── 通过条件: 用户启用了缓存

检查点 2: modificationMetaID 匹配?
  ├── 检查目的: DDL 是否已发生
  ├── 比较双方:
  │     ├── Session 缓存的 modificationMetaID
  │     └── Database 当前 modificationMetaID
  ├── 通过条件: 两者相等 (无 DDL)
  └── 不一致后果: queryCache.clear() + 更新版本号

检查点 3: queryCache.get(sql) 命中?
  ├── 检查目的: 相同 SQL 是否已编译
  ├── 匹配方式: SQL 字符串精确匹配
  ├── 通过条件: hashCode 和 equals 均相等
  └── 命中后: 还需检查 canReuse()

检查点 4: command.canReuse()?
  ├── 检查目的: 缓存的命令是否仍有效
  ├── 检查内容: 引用的表/列是否存在
  ├── 通过条件: 所有依赖对象均有效
  └── 不通过: 降级到完整解析

如图 7-31 所示，检查点 5: command.isCacheable()?
  ├── 检查目的: 此类型语句是否可缓存
  ├── 不可缓存类型: FOR UPDATE, 非确定性函数, 临时表
  ├── 通过条件: 语句类型支持缓存
  └── 不通过: 不入缓存, 下次仍完整解析
```
**图 7-31: 汇总 缓存决策五个关键检查点**

如图 7-32 所示，该图将图 7-30 的完整决策流程提炼为五个关键检查点。这些检查点按执行顺序排列，任何一个检查点不通过都可能改变决策路径（跳过缓存、清空缓存或不入缓存）。理解每个检查点的目的和通过条件，有助于诊断与缓存相关的性能问题——例如，如果查询频繁重新编译，检查 modificationMetaID 是否因 DDL 频繁变化、或 isCacheable() 是否返回 false。

### 7.3.6 DDL 缓存失效传播机制

**图 7-32: 追踪 DDL 操作到缓存失效的传播路径**

```text
DDL 操作执行路径:
                      SessionLocal                       Database
  CommandContainer        │                                │
  (ALTER TABLE)           │                                │
       │                  │                                │
       │── update() ──────→                                │
       │                  │── prepared.update()            │
       │                  │     │                          │
       │                  │     ├── table.removeIndex()    │
       │                  │     ├── table.addColumn()      │
       │                  │     └── ...                    │
       │                  │                                │
       │                  │── database.nextModificationMetaId()
       │                  │     │                          │
       │                  │     └── modificationMetaID++   │
       │                  │         (版本号递增)             │
       │                  │                                │

其他 Session 的下一次查询:

  如图 7-69 所示，Session B                SessionLocal B                Database
  executeQuery(sql)             │                           │
       │                        │                           │
       │── prepareCommand() ────→                           │
       │                        │── prepareLocal()          │
       │                        │     │                     │
       │                        │     ├─ 检查 DDL 版本      │
       │                        │     │  current = getModificationMetaId()
       │                        │     │  cached = session.modificationMetaID
       │                        │     │                     │
       │                        │     │  current != cached ?│
       │                        │     │  YES!               │
       │                        │     │                     │
       │                        │     ├─ queryCache.clear()│
       │                        │     │  (清空所有缓存)      │
       │                        │     │                     │
       │                        │     ├─ 更新版本号         │
       │                        │     │                     │
       │                        │     └─ 重新解析 SQL       │
       │                        │                           │
```
**图 7-69: 演示 DDL 操作与缓存失效的跨 Session 时序**

该图展示了 DDL 操作触发缓存失效的完整时序。关键设计原理是使用**全局版本号**（`modificationMetaID`）作为缓存一致性的令牌：

1. **版本号存储**：`Database` 类维护一个单调递增的 `modificationMetaID` 计数器，每次执行 DDL 操作时递增。每个 `SessionLocal` 缓存自己上次检查时的版本号。

2. **惰性失效**：H2 采用惰性失效策略——DDL 操作本身不清除任何 session 的缓存，仅递增全局版本号。每个 session 在下一次查询时发现版本不匹配后才清理自己的缓存。这种策略将缓存失效的开销平摊到后续查询中，避免了 DDL 操作时的全局同步开销。

3. **多会话一致性**：由于每个 session 独立维护自己的 `queryCache`，DDL 后的缓存失效也是各自独立完成的。Session A 执行 ALTER TABLE 后，Session B 的下一次查询会检测到版本变化并清空自己的缓存。这种设计避免了跨 session 的直接通信，也简化了并发控制。

4. **影响范围**：`modificationMetaID` 的变化会清空全部缓存，而非仅清空受影响的表。这是一种粗粒度的失效策略——实现简单，不会遗漏，但可能误伤与 DDL 无关的缓存项。对于 H2 这种嵌入式数据库，查询缓存大小通常很小（默认 8），清空全部缓存的成本极低。

`modificationMetaID` 版本号的生命周期展示了 DDL、缓存和查询之间的时序关系：

```text
modificationMetaID 版本号生命周期
                        │
  ┌────────────────────────────────────────────────────────────┐
  │  Database.modificationMetaID (全局版本号)                   │
  │                                                            │
  │  版本 0 ─── DDL ─→ 版本 1 ─── DDL ─→ 版本 2 ── ... ──→ 版本 N  │
  │      │              │              │                  │        │
  │      │              │              │                  │        │
  │      ▼              ▼              ▼                  ▼        │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐           ┌─────────┐  │
  │  │ 创建 DB  │  │ ALTER   │  │ CREATE  │           │ DROP    │  │
  │  │ 初始状态 │  │ TABLE   │  │ INDEX   │           │ TABLE   │  │
  │  └─────────┘  └─────────┘  └─────────┘           └─────────┘  │
  └────────────────────────────────────────────────────────────┘
                        │
  Session A 的视角:
    版本 2 时缓存了 SELECT * FROM t
    │
    ├── Session 缓存的版本号: 2
    ├── 缓存的查询计划: SELECT * FROM t (基于版本 2 的表结构)
    │
    ├── ALTER TABLE t ADD COLUMN ... → 版本号变为 3
    │
    └── Session A 下一次查询:
          │
          ├── 发现 Database.version=3 ≠ Session.version=2
          ├── queryCache.clear()      ← 全部缓存失效
          ├── Session.version = 3     ← 同步版本号
          └── 重新解析并缓存新计划

  如图 7-33 所示，缓存命中场景 (无 DDL 时):
    Session 版本: 3
    Database 版本: 3
    版本匹配 → 缓存可用 → 直接返回已编译计划
```
**图 7-33: 追踪 modificationMetaID 版本号生命周期**

该图展示了全局版本号在 DDL 缓存失效中的完整生命周期。每次 DDL 操作都会递增 `Database` 层的全局版本号，而每个 Session 的缓存只在自己下一次查询时比对版本。版本比对是一个 O(1) 的长整型比较，其开销可以忽略不计。这种"版本号令牌"的设计是一种典型的乐观并发控制策略——假设大多数时候没有 DDL 发生，因此版本比对总是通过，缓存始终有效。仅在 DDL 发生时（罕见事件），才需要执行缓存清空的开销。

---

## 7.4 Command 执行框架

### 7.4.1 `CommandContainer` 结构

源码位置：`org/h2/command/CommandContainer.java`

`CommandContainer` 是 `Command` 的实现类，内部持有一个 `Prepared prepared` 对象。

```text
CommandContainer
  │
  ├─ prepared: Prepared        ← Select / Insert / Update 等
  ├─ query(maxRows)            ← SELECT 执行入口
  └─ update(request)           ← INSERT/UPDATE/DELETE 执行入口
```

CommandContainer 在 Command 接口实现层次中的位置如下：

```text
如图 7-34 所示，Command 接口方法实现: CommandContainer
                        │
  ┌─────────────────────────────────────────────────────────────┐
  │  CommandContainer                                            │
  │                                                              │
  │  核心字段:                                                    │
  │    ├── session: SessionLocal     ← 会话上下文                 │
  │    ├── prepared: Prepared        ← 已编译的查询计划           │
  │    └── sql: String               ← 原始 SQL 文本              │
  │                                                              │
  │  核心方法:                                                    │
  │    ├── query(maxRows)            → prepared.query()          │
  │    ├── update(request)           → prepared.update()         │
  │    ├── recompileIfRequired()     → 按需重新编译               │
  │    ├── canReuse()                → true (默认可复用)          │
  │    ├── isCacheable()             → prepared.isCacheable()    │
  │    └── reuse()                   → 重置参数绑定状态           │
  │                                                              │
  │  组合关系: CommandContainer ──1:1──→ Prepared                 │
  │             一个 CommandContainer 包装一个 Prepared 对象      │
  └─────────────────────────────────────────────────────────────┘
```
**图 7-34: 拆解 CommandContainer 字段与方法布局**

> **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#large_objects`)
> 说明了 CLOB/BLOB 的存储策略和 `MAX_LENGTH_INPLACE_LOB` 阈值配置。

### 7.4.2 `CommandContainer.query(long maxRows)`

```java
// CommandContainer.java:216
public ResultInterface query(long maxrows) {
    recompileIfRequired();      // 检查是否需要重新编译
    start();                    // 事务/锁管理
    prepared.checkParameters(); // 检查参数绑定
    ResultInterface result = prepared.query(maxrows);
    return result;
}
```

如图 7-26 所示，query 方法的执行路径包含三个阶段——防御性检查、执行前准备和实际查询：

```text
CommandContainer.query() 执行阶段
                        │
  阶段 1: 防御性检查
    │
    └── recompileIfRequired()
          │
          ├── needRecompile() == true?
          │     ├── YES → 重新解析 + 准备 (耗时 ≈ 1-10ms)
          │     └── NO  → 跳过 (耗时 ≈ 0.001ms)
          │
          ├── 场景: 表结构变更后首次查询
          └── 目的: 确保执行计划与当前表结构一致

  阶段 2: 执行前准备
    │
    ├── start()
    │     ├── session.checkCommit()
    │     ├── session.setCurrentCommand(this)
    │     └── trace 日志
    │
    └── checkParameters()
          ├── 遍历所有 Parameter
          ├── 检查每个参数值是否已设置
          └── 未设置的参数 → SQLException

  阶段 3: 实际执行
    │
    └── prepared.query(maxRows)
          ├── Select.query()     → 查询执行 + 结果集构建
          ├── Insert.query()     → 一般不使用
          ├── Update.query()     → 一般不使用
          └── Delete.query()     → 一般不使用
```
**图 7-35: 拆解 query 防御检查与执行三阶段**

### 7.4.3 `CommandContainer.update(Object generatedKeysRequest)`

```java
// CommandContainer.java:124
public ResultWithGeneratedKeys update(Object generatedKeysRequest) {
    recompileIfRequired();
    start();
    prepared.checkParameters();
    ResultWithGeneratedKeys result;
    // DML 语句处理生成键
    if (generatedKeysRequest != null && ...) {
        result = executeUpdateWithGeneratedKeys(...);
    } else {
        result = ResultWithGeneratedKeys.of(prepared.update());
    }
    return result;
}
```

如图 7-35 所示，update 方法与 query 方法共享前三个阶段，差异在于最后的分发路径：

```text
update 与 query 的执行路径对比
                        │
                     ┌──────────────────────────────────────┐
                     │  共享阶段:                            │
                     │  ├── recompileIfRequired()           │
                     │  ├── start()                         │
                     │  └── checkParameters()               │
                     └───────────┬──────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
          ┌──────────────────┐    ┌──────────────────────┐
          │  query(maxRows)  │    │ update(request)       │
          │                  │    │                      │
          │  prepared.query()│    │ prepared.update()    │
          │  → SELECT        │    │ → INSERT/UPDATE/DELETE│
          │  → 返回结果集    │    │ → 返回影响行数      │
          │  → ResultInterface│    │ → ResultWithGenKeys │
          └──────────────────┘    └──────────────────────┘
                    │                         │
                    ▼                         ▼
          ┌──────────────────┐    ┌──────────────────────┐
          │  JdbcResultSet   │    │ 批量执行时:           │
          │  包装            │    │  executeUpdateWith   │
          │                  │    │  GeneratedKeys()     │
          └──────────────────┘    └──────────────────────┘
```
**图 7-36: 对比 update 与 query 的执行路径**

如图 7-36 所示，query 和 update 共享相同的防御性检查和执行前准备逻辑，区别仅在于最终分发的 Preapred 子类方法和返回值处理方式。

```text
ResultWithGeneratedKeys 内部结构
                        │
  ResultWithGeneratedKeys
    │
    ├── 无生成键请求 (generatedKeysRequest == null)
    │     │
    │     └── ResultWithGeneratedKeys.of(prepared.update())
    │           │
    │           ├── prepared.update() → int (影响行数)
    │           │
    │           └── ResultWithGeneratedKeys
    │                 ├── updateCount: int (例如 1)
    │                 └── generatedKeys: null
    │
    └── 有生成键请求 (generatedKeysRequest != null)
          │
          └── executeUpdateWithGeneratedKeys(request)
                │
                ├── Step 1: 解析请求列
                │     ├── generatedKeysRequest = Boolean TRUE
                │     │     → 全部列作为生成键
                │     └── generatedKeysRequest = int[] 列索引
                │           → 指定列作为生成键
                │
                ├── Step 2: 执行 DML
                │     └── prepared.update()
                │           ├── INSERT → 生成自增 ID
                │           └── UPDATE → 返回影响行数
                │
                └── Step 3: 构造结果
                      ├── ResultWithGeneratedKeys
                      │     ├── updateCount: int
                      │     └── generatedKeys: ResultInterface ← 生成键集合
                      │
                      └── JdbcResultSet(generatedKeys)
                            └── 用户通过 getGeneratedKeys() 获取
```
**图 7-37: 拆解 生成键结果对象的两条构造路径**

### 7.4.4 重新编译机制

```java
// CommandContainer.java:107
private void recompileIfRequired() {
    if (prepared.needRecompile()) {
        prepared.setModificationMetaId(0);
        String sql = prepared.getSQL();
        Parser parser = new Parser(session);
        parser.setSuppliedParameters(prepared.getParameters());
        prepared = parser.parse(sql, tokens);  // 重新解析
        prepared.prepare();                     // 重新准备
    }
}
```

如图 7-37 所示，当表结构发生变化（如添加索引）且语句设置了 `alwaysRecompile` 标志时触发。

重新编译机制的执行过程可以分为七个步骤：

```text
重新编译七步流程
                        │
  触发: needRecompile() == true
    │
    ├── Step 1: 清空版本号
    │     prepared.setModificationMetaId(0)
    │     目的: 强制 prepare() 重新获取最新版本号
    │
    ├── Step 2: 获取原始 SQL
    │     sql = prepared.getSQL()
    │     注意: 这是原始的 SQL 文本, 不是已绑定的参数值
    │
    ├── Step 3: 创建新 Parser
    │     parser = new Parser(session)
    │     每次重新编译都创建新的 Parser 实例
    │
    ├── Step 4: 传递已有参数
    │     parser.setSuppliedParameters(prepared.getParameters())
    │     目的: 保留已绑定的参数值, 避免客户端重新绑定
    │
    ├── Step 5: 重新解析
    │     prepared = parser.parse(sql)
    │     重新执行词法分析 + 语法分析
    │
    ├── Step 6: 重新准备
    │     prepared.prepare()
    │     列展开 → 类型解析 → preparePlan() → Optimizer
    │
    └── Step 7: 原子替换
          this.prepared = newPrepared
          旧的 Prepared 被 GC 回收

  如图 7-38 所示，重新编译与首次编译的对比:
  ┌──────────────┬──────────────────┬──────────────────┐
  │ 环节          │ 首次编译         │ 重新编译          │
  ├──────────────┼──────────────────┼──────────────────┤
  │ 创建 Parser  │ new Parser()     │ new Parser()     │
  │ 词法分析     │ tokenize(sql)    │ tokenize(sql)    │
  │ 语法分析     │ parseQuery()     │ parseQuery()     │
  │ 语义分析     │ init()           │ init()           │
  │ 优化         │ preparePlan()    │ preparePlan()    │
  │ 参数传递     │ 客户端绑定       │ 自动传递已有参数  │
  └──────────────┴──────────────────┴──────────────────┘
```
**图 7-38: 拆解 重新编译的七步流程**

### 7.4.5 Command 执行框架总览

```text
JDBC 层
  │
  ▼
CommandContainer
  │
  ├─ recompileIfRequired()
  │     └─ Parser.parse() + Prepared.prepare()
  │
  ├─ checkParameters()
  │     └─ 验证所有参数已绑定
  │
  ├─ prepared.query(maxRows)
  │     └─ 多态分发:
  │           ├─ Select.query()    → 查询执行
  │           ├─ Insert.query()    → 一般不调用
  │           └─ ...
  │
  └─ ResultInterface
        └─ JdbcResultSet 包装
```

Command 执行框架中 query 和 update 方法在整个调用链中的位置和作用范围如下：

```text
如图 7-39 所示，Command 执行框架方法调用全景
                        │
  JdbcStatement         │  JdbcPreparedStatement
    executeQuery(sql)   │    executeQuery()
    executeUpdate(sql)  │    executeUpdate()
        │               │        │
        └───────────────┼────────┘
                        │
                        ▼
  JdbcConnection
    prepareCommand(sql)          ← 首次编译
        │
        ▼
  CommandContainer               ← 已编译命令
        │
        ├── query(maxRows)       ← SELECT 统一入口
        │     ├── recompileIfRequired()
        │     ├── start()
        │     ├── checkParameters()
        │     └── prepared.query()
        │           └── Select.query() → 行迭代
        │
        └── update(request)      ← DML 统一入口
              ├── recompileIfRequired()
              ├── start()
              ├── checkParameters()
              └── prepared.update()
                    ├── Insert.update() → addRow()
                    ├── Update.update() → updateRow()
                    └── Delete.update() → removeRow()
                        │
                        ▼
              ResultWithGeneratedKeys
```
**图 7-39: 概览 Command 框架的方法调用全景**

如图 7-40 所示，该图展示了从 JDBC 层到 Command 层再到 Prepared 层的完整调用链。`CommandContainer` 作为 JDBC 层和 Engine 层之间的桥梁，其 `query()` 和 `update()` 两个方法屏蔽了底层 Prepared 子类的复杂分发逻辑，为上层提供了统一的执行入口。


### 7.4.6 Command 类继承层次

**图 7-40: 拆解 Command 框架的继承与组合关系**

```text
Command (接口, command/Command.java)
  │   接口方法: query(), update(), canReuse(), isCacheable(), ...
  │
  ├── CommandContainer                          ← 单语句容器
  │    ├── prepared: Prepared                   ← 已编译的查询计划
  │    ├── query(maxRows) → prepared.query()
  │    ├── update(request) → prepared.update()
  │    ├── recompileIfRequired()                ← 按需重新编译
  │    └── isCacheable() → prepared.isCacheable()
  │
  ├── CommandList                               ← 多语句容器
  │    ├── commands: ArrayList<Command>         ← 子命令列表
  │    │     └── [cmd1, cmd2, cmd3, ...]
  │    ├── query(maxRows)                       ← 分发到所有子命令
  │    └── update(request)                      ← 依次执行所有子命令
  │
  └── CommandRemote                             ← 远程执行 (C/S 模式)
       └── 通过网络发送 SQL 到服务端执行

Prepared (抽象基类, command/Prepared.java)
  │   核心方法: prepare(), query(), update(), isCacheable()
  │
  ├── Select                                    ← SELECT 查询
  │    ├── preparePlan() → Optimizer.optimize()
  │    ├── queryWithoutCache() → TableFilter 迭代
  │    └── createIndexConditions() → 提取索引条件
  │
  ├── Insert                                    ← INSERT 插入
  │    └── update() → table.addRow()
  │
  ├── Update                                    ← UPDATE 更新
  │    └── update() → table.updateRow()
  │
  ├── Delete                                    ← DELETE 删除
  │    └── update() → table.removeRow()
  │
  ├── Merge                                     ← MERGE 合并
  │
  └── Call                                      ← CALL 语句
       └── 调用 Java 方法或函数

组合关系:
  JdbcStatement → JdbcConnection → SessionLocal → CommandContainer → Prepared
                                                                    ↓
                                                             Select / Insert / ...

  如图 7-70 所示，SessionLocal.queryCache: SmallLRUCache<String, Command>
       │
       └── 缓存键: SQL 文本 → 缓存值: CommandContainer
```

下面三张图把 Command 框架拆成三个层次：图 7-70 描绘 Command 与 Prepared 的继承层次，图 7-41 横向对比各子类的方法实现矩阵，图 7-42 追踪 `CommandContainer.query` 的五阶段执行路径。

**图 7-70: 展示 Command 与 Prepared 的继承层次**

该图揭示了 H2 Command 框架的完整类型层次。设计上采用**组合优于继承**的原则：`CommandContainer` 通过组合方式持有一个 `Prepared` 对象，将"命令执行"与"查询计划"两个概念解耦：

- **Command 接口**定义了命令执行器的通用协议，包括 `query()`（返回结果集）、`update()`（返回影响行数）、`canReuse()`（是否可复用）、`isCacheable()`（是否可缓存）
- **CommandContainer** 是单语句的默认实现，内部委托给 `Prepared` 对象执行实际逻辑
- **CommandList** 支持多条 SQL 的批量执行，内部持有 `Command` 数组，按顺序逐一执行
- **Prepared 抽象基类**是所有 SQL 语句类型的共同祖先，定义了查询计划的生命周期方法。每个子类（Select、Insert、Update、Delete）对应一种 SQL 语句类型
- **Select** 是最复杂的子类，拥有独立的 `preparePlan()` 和 `Optimizer` 调用

这种设计使得 JBDC 层只需要依赖 `Command` 接口，无需关心具体的 SQL 类型。`CommandContainer` 负责按需重新编译，`Prepared` 负责实际的查询执行，形成了职责分明的两层结构。

Command 接口和 Prepared 抽象类的核心方法矩阵展示了不同类型语句的方法实现差异：

```text
如图 7-41 所示，Command/Prepared 方法实现矩阵
                        │
  ┌─────────────────────┬──────────┬──────────┬──────────┬──────────┐
  │ 方法                 │ Command  │ Prepared │ Select   │ Insert   │
  │                     │ (接口)   │ (抽象类) │          │          │
  ├─────────────────────┼──────────┼──────────┼──────────┼──────────┤
  │ query(maxRows)      │ 抽象     │ 默认空   │ 实现 ✓   │ 空      │
  │ update(request)     │ 抽象     │ 默认空   │ 空       │ 实现 ✓  │
  │ prepare()           │ -        │ 抽象     │ 实现 ✓   │ 实现 ✓  │
  │ isCacheable()       │ 抽象     │ 默认:true│ true     │ true    │
  │ canReuse()          │ 抽象     │ 默认:true│ true     │ true    │
  │ needRecompile()     │ -        │ 默认     │ 版本检查 │ 版本检查│
  │ getSQL()            │ 抽象     │ 抽象     │ 返回 SQL │ 返回 SQL│
  ├─────────────────────┼──────────┼──────────┼──────────┴──────────┤
  │                     │          │          │                      │
  │ Select 特有方法:     │          │          │                     │
  │  preparePlan()      │ -        │ -        │ → Optimizer.optimize│
  │  queryWithoutCache() │ -       │ -        │ → TableFilter 迭代   │
  │  createIndexConditions│ -      │ -        │ 提取索引条件         │
  └─────────────────────┴──────────┴──────────┴──────────────────────┘
```
**图 7-41: 对比 Command 与 Prepared 子类方法实现**

如图 7-42 所示，该矩阵展示了 Command 接口和 Prepared 抽象类及其子类的方法实现情况。`query()` 在 Select 中有实质性实现而其它子类为空，`update()` 只在 Insert/Update/Delete 中有实现。这种设计使得 `CommandContainer` 可以统一调用 `query()` 和 `update()`，而具体的执行逻辑由多态分发到对应的 Prepared 子类。Select 是唯一拥有 `preparePlan()` 和 `queryWithoutCache()` 方法的子类，体现了 SELECT 查询在优化和执行上的复杂性远高于 DML 语句。

### 7.4.7 CommandContainer 内部执行路径

**图 7-42: 追踪 CommandContainer.query 的五阶段**

```text
如图 7-71 所示，CommandContainer.query(maxRows)
  │
  ├── 1. recompileIfRequired()
  │     │
  │     ├── prepared.needRecompile() ?
  │     │     │
  │     │     ├── YES:
  │     │     │     prepared.setModificationMetaId(0)
  │     │     │     sql = prepared.getSQL()
  │     │     │     parser = new Parser(session)
  │     │     │     parser.setSuppliedParameters(params)
  │     │     │     prepared = parser.parse(sql)   ← 重新解析
  │     │     │     prepared.prepare()             ← 重新准备
  │     │     │
  │     │     └── NO: 跳过
  │     │
  │     └── (继续)
  │
  ├── 2. start()
  │     │
  │     ├── session.checkCommit()        ← 检查事务提交
  │     ├── session.setCurrentCommand()  ← 设置当前命令上下文
  │     └── trace 日志记录
  │
  ├── 3. prepared.checkParameters()
  │     │
  │     ├── 遍历所有 Parameter 对象
  │     ├── 检查每个参数是否已设置值
  │     └── 未设置的参数抛出 SQLException
  │
  ├── 4. prepared.query(maxRows)
  │     │
  │     ├── Select.query()
  │     │     │
  │     │     ├── queryCacheHash != null ?
  │     │     │     ├── YES → 尝试结果集缓存 (queryCache.find())
  │     │     │     └── NO  → queryWithoutCache(maxRows)
  │     │     │
  │     │     ├── queryWithoutCache(maxRows)
  │     │     │     │
  │     │     │     ├── startQuery(session)          ← TableFilter 初始化
  │     │     │     ├── reset()                      ← 游标重置
  │     │     │     │
  │     │     │     ├── 行迭代循环:
  │     │     │     │     while (topTableFilter.next())
  │     │     │     │         row = 构建结果行
  │     │     │     │         addRow(row)
  │     │     │     │
  │     │     │     ├── result = new PseudoResultSet(rows)
  │     │     │     └── return result
  │     │     │
  │     │     └── 结果集缓存 (如果启用)
  │     │
  │     └── return ResultInterface
  │
  ├── 5. stop()                            ← 清理资源
  │
  └── return result
```
**图 7-71: 拆解 query 五阶段的内部执行路径**

该图将 `query()` 方法展开为五个顺序阶段。其中 `recompileIfRequired()` 是最重要的防御性检查——当表结构变更后，缓存的 `Prepared` 对象可能已过时，需要重新解析和计划生成。`checkParameters()` 确保所有参数都已绑定，防止因参数缺失导致的运行时错误。`prepared.query(maxRows)` 是核心执行阶段，对于 SELECT 语句，它进入 `Select.queryWithoutCache()` 内部的 TableFilter 行迭代循环，逐行读取匹配的结果。

在 `query()` 方法的五阶段执行路径中，每个阶段的耗时分布和异常可能性有显著差异：

```text
query() 五阶段耗时与风险分析
                        │
  ┌─────────────────────────────────────────────────────────────┐
  │  阶段 1: recompileIfRequired()                               │
  │  ├── 典型耗时: 0.001ms (跳过) / 1-10ms (重新编译)            │
  │  ├── 发生频率: 仅在 DDL 后第一次执行                          │
  │  ├── 异常风险: 低 (解析异常已在首次编译时处理)                │
  │  └── 优化建议: 避免频繁 DDL                                   │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌──────────────────────────┴──────────────────────────────────┐
  │  阶段 2: start()                                             │
  │  ├── 典型耗时: < 0.01ms                                      │
  │  ├── 发生频率: 每次执行                                      │
  │  ├── 异常风险: 中 (事务冲突)                                  │
  │  └── 优化建议: 缩短事务持有时间                               │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌──────────────────────────┴──────────────────────────────────┐
  │  阶段 3: checkParameters()                                   │
  │  ├── 典型耗时: < 0.01ms (已绑定) / 抛出异常 (未绑定)         │
  │  ├── 发生频率: 每次执行                                      │
  │  ├── 异常风险: 高 (参数未绑定 → SQLException)                │
  │  └── 优化建议: 确保所有参数已 setXxx()                        │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌──────────────────────────┴──────────────────────────────────┐
  │  阶段 4: prepared.query(maxRows)                             │
  │  ├── 典型耗时: 0.1ms - 1000ms+ (数据量和索引决定)            │
  │  ├── 发生频率: 每次执行                                      │
  │  ├── 异常风险: 中 (数据约束、锁等待)                          │
  │  └── 优化建议: 索引优化 → 减少扫描行数                       │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌──────────────────────────┴──────────────────────────────────┐
  │  阶段 5: stop()                                              │
  │  ├── 典型耗时: < 0.01ms                                      │
  │  ├── 发生频率: 每次执行                                      │
  │  ├── 异常风险: 低                                            │
  │  └── 优化建议: (无需优化)                                    │
  └─────────────────────────────────────────────────────────────┘

  如图 7-43 所示，性能分析要点:
  ┌──────────────────────────────────────────────────────┐
  │  总执行时间 ≈ 阶段 4 耗时 (99%+)                      │
  │  阶段 4 的优化是查询性能调优的核心战场                  │
  │  → 索引优化: 减少 TableFilter.next() 调用次数         │
  │  → 查询改写: 减少中间结果行数                          │
  │  → 列选择优化: 减少表达式求值次数                      │
  └──────────────────────────────────────────────────────┘
```
**图 7-43: 剖析 query 五阶段耗时与异常风险**

如图 7-44 所示，该图从性能和风险两个维度分析了 `query()` 方法的五个执行阶段。`prepared.query(maxRows)` 是绝对的热点阶段，占总执行时间的 99% 以上。前三个阶段（recompileIfRequired + start + checkParameters）的开销即使全部加起来也不到 0.1ms，在大多数查询中可忽略不计。因此，查询性能调优的核心应该聚焦于阶段 4——减少 `TableFilter.next()` 的迭代次数和单次迭代的开销。

### 7.4.8 重新编译决策树

**图 7-44: 拆解 recompileIfRequired 的决策树**

```text
如图 7-72 所示，recompileIfRequired() 决策树
  │
  ├── 触发条件: needRecompile()
  │     │
  │     ├── alwaysRecompile 标志为 true ?
  │     │     │
  │     │     ├── YES → 需要重新编译
  │     │     │         (通常在表结构可能变化的场景设置)
  │     │     │
  │     │     └── NO → 检查元数据版本
  │     │
  │     ├── 当前 modificationMetaId != prepared 编译时的版本 ?
  │     │     │
  │     │     ├── YES → DDL 已发生, 需要重新编译
  │     │     │
  │     │     └── NO → 无需重新编译
  │     │
  │     └── 结果:
  │           ├── needRecompile == false → 直接跳过, 使用现有计划
  │           └── needRecompile == true  → 进入重新编译流程
  │
  ├── 重新编译流程:
  │     │
  │     ├── 1. prepared.setModificationMetaId(0)
  │     │     清空版本号, 强制后续的 prepare() 重新获取最新版本
  │     │
  │     ├── 2. sql = prepared.getSQL()
  │     │     从 Prepared 对象中获取原始 SQL 字符串
  │     │
  │     ├── 3. new Parser(session)
  │     │     创建新的 Parser 实例
  │     │
  │     ├── 4. parser.setSuppliedParameters(params)
  │     │     将之前已绑定的参数传递给新的 Parser
  │     │
  │     ├── 5. prepared = parser.parse(sql)
  │     │     重新执行词法/语法分析, 生成新的 Prepared 对象
  │     │
  │     ├── 6. newPrepared.prepare()
  │     │     执行语义分析和计划生成 (包含 Optimizer 调用)
  │     │
  │     └── 7. this.prepared = newPrepared
  │          原子替换: 旧的 Prepared 被 GC 回收
  │
  └── 重新编译的影响:
        │
        ├── 性能开销: 完整的解析 + 优化 + 计划生成
        ├── 触发频率: 仅在 DDL 后第一次执行时触发
        └── 对比缓存: 与 queryCache 不同, 这里重新生成的是 Prepared 对象
                     而不是从缓存中查找
```
**图 7-72: 梳理 recompileIfRequired 七步重编译路径**

重新编译机制是 H2 保证执行计划时效性的关键设计。当表结构发生变化（例如新增索引、修改列定义）后，原有的执行计划可能不再最优甚至不再有效。`recompileIfRequired()` 通过惰性检测机制——在执行查询前检查元数据版本号——确保始终使用与当前表结构一致的最新计划。与查询缓存不同，重新编译发生在 `CommandContainer` 级别，生成新的 `Prepared` 实例后通过原子替换方式更新内部引用，保证了线程安全性。

重新编译需要同时满足的触发条件及其与查询缓存的交互关系如下：

```text
如图 7-45 所示，重新编译触发条件与缓存交互
                        │
  CommandContainer.query() / update()
    │
    ├── 检查条件: prepared.needRecompile()
    │     │
    │     ├── alwaysRecompile == true ?
    │     │     ├── 设置场景: 打开的 ResultSet 持有的语句
    │     │     │             需要在表结构变更时动态适应
    │     │     └── 触发规则: 每次 query/update 都检查
    │     │
    │     └── modificationMetaID 变化 ?
    │           ├── prepared 编译时记录的元数据版本号
    │           └── 与当前 Database.modificationMetaID 比较
    │                 │
    │                 ├── 相等 → 无需重新编译
    │                 └── 不等 → DDL 已发生, 需要重新编译
    │
    ├── 触发重新编译时的整体流程:
    │
    │   ┌──────────┐    queryCache         ┌──────────┐
    │   │prepared  │    缓存查找?           │new       │
    │   │(旧, 无效)│──────→ 未命中 ────────→│prepared  │
    │   └──────────┘    (SQL 可能不同)      │(新, 有效)│
    │                                          │
    │                                      prepare()
    │                                      └── Optimizer 重新优化
    │                                          │
    │                                          ▼
    │                                     this.prepared = newPrepared
    │
    └── 与 queryCache 的关系:
          │
          ├── 不同层级: queryCache 在 SessionLocal 层
          │            recompile 在 CommandContainer 层
          │
          ├── 不同时机: queryCache 在 prepareLocal() 时检查
          │            recompile 在 query/update 执行前检查
          │
          └── 不同目的: queryCache 避免重复编译
                       recompile 保证计划时效性
```
**图 7-45: 梳理 重编译触发条件与缓存交互**

该图展示了重新编译的触发条件及其与查询缓存的交互关系。重新编译的触发条件是 `needRecompile()` 返回 true，这发生在 `alwaysRecompile` 标志设置或元数据版本号变化时。重新编译在 `CommandContainer` 层执行，与 Session 层的查询缓存是两个独立的机制——查询缓存避免的是"相同 SQL 的重复编译"，而重新编译处理的是"表结构变更后的计划更新"。两者配合工作：DDL 发生后，查询缓存被整体清空，下次查询时重新编译生成新计划，新计划又可缓存供后续复用。

---

## 7.5 全链路 ASCII 序列图

```text
JdbcStatement    SessionLocal     Parser         Select        Optimizer     TableFilter     MVStore
      │               │             │              │              │              │              │
      │──prepareCmd()─→             │              │              │              │              │
      │               │             │              │              │              │              │
      │               │──parse()───→              │              │              │              │
      │               │             │              │              │              │              │
      │               │             │──parseQuery()─────────────→              │              │
      │               │             │              │              │              │              │
      │               │             │              │──init()──────              │              │
      │               │             │              │ (expand columns,           │              │
      │               │             │              │  map columns,              │              │
      │               │             │              │  resolve types)            │              │
      │               │             │              │              │              │              │
      │               │             │              │──prepare()───              │              │
      │               │             │              │              │              │              │
      │               │             │              │──preparePlan()              │              │
      │               │             │              │              │              │              │
      │               │             │              │──optimizePlan()────────────→              │
      │               │             │              │              │              │              │
      │               │             │              │              │──getBestPlanItem()─────────→ │
      │               │             │              │              │              │              │
      │               │             │              │              │              │──cost()──────→│
      │               │             │              │              │              │ (index scan   │
      │               │             │              │              │              │  cost est.)   │
      │               │             │              │              │              │              │
      │               │             │              │←──topFilter ←──────────────┘              │
      │               │             │              │              │              │              │
      │               │             │              │←──Prepared.prepared ────────              │
      │               │             │              │              │              │              │
      │               │←──CommandContainer ────────              │              │              │
      │               │             │              │              │              │              │
      │──executeQuery()───────────────→            │              │              │              │
      │               │             │              │              │              │              │
      │               │─lock()──────               │              │              │              │
      │               │             │              │              │              │              │
      │               │──CommandContainer.query()──│              │              │              │
      │               │             │              │              │              │              │
      │               │             │              │──queryWithoutCache()        │              │
      │               │             │              │              │              │              │
      │               │             │              │──startQuery()──────────────→               │
      │               │             │              │              │              │              │
      │               │             │              │──reset()────────────────────→               │
      │               │             │              │              │              │              │
      │               │             │              │──fetchNextRow()             │              │
      │               │             │              │              │              │              │
      │               │             │              │              │──next()───────→              │
      │               │             │              │              │              │              │
      │               │             │              │              │   cursor.find()──────────────→
      │               │             │              │              │   (index lookup)              │
      │               │             │              │              │              │              │
      │               │             │              │              │   currentSearchRow ←──────────┘
      │               │             │              │              │              │              │
      │               │             │              │              │──isOk(filterCondition)       │
      │               │             │              │              │──isOk(joinCondition)         │
      │               │             │              │              │              │              │
      │               │             │              │              │──join.next()──→               │
      │               │             │              │              │   (inner table)              │
      │               │             │              │              │              │              │
      │               │             │              │              │──get()─────────→              │
      │               │             │              │              │   (read row)                  │
      │               │             │              │              │              │              │
      │               │             │              │←──row[] ←───┘              │              │
      │               │             │              │              │              │              │
      │               │             │              │──expr.getValue(session)                   │
      │               │             │              │   (表达式求值)                            │
      │               │             │              │              │              │              │
      │               │←──ResultInterface ─────────               │              │              │
      │               │             │              │              │              │              │
      │←──JdbcResultSet ────────────               │              │              │              │
      │               │             │              │              │              │              │
```

图中的核心调用顺序说明：

```text
如图 7-46 所示，1. **准备阶段**: JDBC → `prepareLocal` → Parser 解析 → `Select.init()` 扩展列 → `Select.prepare()` → `preparePlan()` → `Optimizer.optimize()` → 选取最优 TableFilter 链
2. **执行阶段**: JDBC → `CommandContainer.query()` → `Select.queryWithoutCache()` → `TableFilter.next()` 循环读取 → 表达式求值 → 输出结果行
```

### 7.5.1 全链路执行阶段泳道图

**图 7-46: 概览 五泳道下 SQL 全链路阶段与数据流**

```text
如图 7-73 所示，泳道图: SQL 全链路执行阶段划分
                          准备阶段                          执行阶段
  ┌─────────────┐  ┌──────────────────────┐  ┌──────────────────────────┐
  │  JDBC 层    │  │ prepareCommand       │  │ executeQuery             │
  │             │  │  conn.prepare         │  │  command.query(maxRows)  │
  │             │  │  → SessionLocal       │  │  → CommandContainer      │
  │             │  │                      │  │                          │
  │             │  │ ▲                    │  │ ▲                        │
  └─────────────┘  └─┼────────────────────┘  └─┼────────────────────────┘
                     │                          │
                     │                          │
  ┌─────────────┐  ┌─┼────────────────────┐  ┌─┼────────────────────────┐
  │  Session 层 │  │ │                    │  │ │                        │
  │             │  │ │ prepareLocal()     │  │ │ lock()                  │
  │             │  │ │  查询缓存检查       │  │ │ checkParameters()       │
  │             │  │ │  cache hit → return│  │ │ unlock()                │
  │             │  │ │  cache miss → ↓    │  │ │                        │
  │             │  │ ▼                    │  │ │                        │
  └─────────────┘  └──────────────────────┘  └─┼────────────────────────┘
                     │                          │
                     │                          │
  ┌─────────────┐  ┌─┼────────────────────┐  ┌─┼────────────────────────┐
  │  Parser     │  │ │                    │  │ │                        │
  │  /Command   │  │ │ Parser.parse(sql)  │  │ │ CommandContainer.query │
  │             │  │ │ 词法分析 → 语法分析  │  │ │  → prepared.query()   │
  │             │  │ │ 创建 Select 对象    │  │ │  → Select.query()      │
  │             │  │ │                    │  │ │                        │
  │             │  │ │ prepared.prepare() │  │ │                        │
  │             │  │ │ 列展开 → 类型解析   │  │ │                        │
  │             │  │ │ preparePlan()      │  │ │                        │
  │             │  │ │ → Optimizer ↓      │  │ │                        │
  │             │  │ ▼                    │  │ ▼                        │
  └─────────────┘  └──────────────────────┘  └──────────────────────────┘
                     │                          │
                     │                          │
  ┌─────────────┐  ┌─┼────────────────────┐  ┌─┼────────────────────────┐
  │  Optimizer  │  │ │                    │  │ │                        │
  │  /TableFtr  │  │ │ optimize()         │  │ │ topTableFilter.next()  │
  │             │  │ │ 暴力/贪心/遗传策略  │  │ │  cursor.find()         │
  │             │  │ │ 代价计算 → 选择计划 │  │ │  cursor.next()         │
  │             │  │ │ 设置 TableFilter链  │  │ │  isOk(filterCond)      │
  │             │  │ │                    │  │ │  join.next()            │
  │             │  │ ▼                    │  │ │                        │
  └─────────────┘  └──────────────────────┘  └─┼────────────────────────┘
                                                │
  ┌─────────────┐                               │
  │  Store 层   │                               │
  │             │                               │
  │  MVStore    │                               │
  │   B-Tree     │◄──────────────────────────────┘
  │   索引      │    cursor.find() / cursor.next()
  └─────────────┘
```

这组图按"全景 → 角色 → 数据 → 映射 → 热点"顺序串联五个层次：图 7-73 给出 SQL 全链路五泳道执行阶段概览，图 7-47 归纳各组件在准备与执行阶段中的角色定位，图 7-48 刻画准备阶段产物到执行阶段的数据依赖，图 7-74 拆解准备产物到执行阶段的消费关系，图 7-49 汇总准备产物到执行消费的映射表。

**图 7-73: 概览 SQL 全链路五泳道执行阶段**

该图将 SQL 执行的全生命周期按组件划分为五个泳道（JDBC 层、Session 层、Parser/Command 层、Optimizer/TableFilter 层、Store 层），并按照时间维度分为"准备阶段"和"执行阶段"两个大的时间窗口：

1. **准备阶段**从 `prepareCommand` 开始，依次经过 Session 层的缓存检查、Parser 的词法语法分析、Select 的语义准备（列展开、类型解析），最后调用 Optimizer 生成执行计划。这一阶段的产出物是已编译的 `CommandContainer`（内含 `Select` 对象和最优的 `TableFilter` 链）。

2. **执行阶段**从 `command.executeQuery()` 开始，进入 `CommandContainer.query()` → `prepared.query()` → `Select.queryWithoutCache()` 的调用链，最终由 `topTableFilter.next()` 驱动 Store 层的游标迭代，逐行读取数据，过滤并计算表达式。

从泳道图可以进一步抽象出各组件在准备阶段和执行阶段中扮演的角色类型：

```text
如图 7-47 所示，组件在准备/执行阶段中的角色定位
                        │
  ┌──────────────┬───────────────────┬───────────────────────┐
  │ 组件          │ 准备阶段角色       │ 执行阶段角色           │
  ├──────────────┼───────────────────┼───────────────────────┤
  │ JDBC 层      │ 请求发起者         │ 结果集包装者           │
  │              │ prepareCommand()  │ JdbcResultSet         │
  ├──────────────┼───────────────────┼───────────────────────┤
  │ Session 层   │ 缓存管理器         │ 锁管理器               │
  │              │ cache get/put     │ lock/unlock           │
  ├──────────────┼───────────────────┼───────────────────────┤
  │ Parser       │ 编译器             │ 不参与                 │
  │ /Command     │ SQL → AST         │ (仅按需重新编译)       │
  ├──────────────┼───────────────────┼───────────────────────┤
  │ Optimizer    │ 优化器             │ 不参与                 │
  │ /TableFilter │ 连接顺序 + 索引    │ (计划已固定)           │
  ├──────────────┼───────────────────┼───────────────────────┤
  │ Select       │ 语义分析器         │ 执行引擎               │
  │              │ init + prepare    │ queryWithoutCache()   │
  ├──────────────┼───────────────────┼───────────────────────┤
  │ Store 层     │ 不参与             │ 数据提供者             │
  │              │                   │ cursor.find/next      │
  └──────────────┴───────────────────┴───────────────────────┘
```
**图 7-47: 归纳 各组件在准备与执行阶段的角色**

如图 7-48 所示，该表总结了各组件在两个阶段中扮演的角色。Parser 和 Optimizer 是纯"准备阶段"组件——它们在 SQL 编译后不再参与执行。Store 层是纯"执行阶段"组件——它不关心 SQL 的解析和优化，只按索引游标的指令提供数据。Session 层和 Select 是跨阶段组件：Session 层在准备阶段负责缓存管理，在执行阶段负责锁控制；Select 在准备阶段负责语义分析，在执行阶段负责驱动行迭代。

### 7.5.2 准备阶段与执行阶段数据流

**图 7-48: 刻画 准备阶段产物到执行阶段的数据依赖**

```text
如图 7-74 所示，准备阶段产物                              执行阶段消费
┌──────────────────────┐               ┌────────────────────────────┐
│  CommandContainer     │               │                            │
│  ┌────────────────┐   │               │  query(maxRows)            │
│  │  Select         │   │               │    │                       │
│  │  (已编译)        │   │               │    ├─ recompileIfRequired│
│  │                  │   │               │    │  (防御性检查)        │
│  │  selectList:     │──┼─列表达式────┼─→│    ├─ checkParameters    │
│  │  Expression[]    │   │               │    │  (验证参数绑定)      │
│  │                  │   │               │    └─ prepared.query()   │
│  │  topFilter:      │──┼─最优表访问顺序─→│         │               │
│  │  TableFilter     │   │               │         ├─ 游标定位       │
│  │    │             │   │               │         ├─ 行迭代         │
│  │    ├─ cursor     │──┼─索引游标───────┼→│         ├─ 条件过滤     │
│  │    ├─ planItem   │──┼─索引 + 代价───┼→│         └─ 列值求值     │
│  │    └─ join       │──┼─连接顺序───────┼→│                            │
│  │                  │   │               └────────────────────────────┘
│  │  conditions:     │──┼─过滤条件树─────┼→  isOk(filterCondition)
│  │  Expression      │   │                    │
│  │                  │   │                    ├── filterCondition
│  │  IndexConditions │──┼─索引条件─────────┼→│  cursor.find()
│  │                  │   │                    └── joinCondition
│  └────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```
**图 7-74: 拆解 准备产物到执行阶段的消费关系**

该图揭示了准备阶段的产物如何被执行阶段消费。每个在准备阶段确定的数据结构——列表达式、表访问顺序、索引选择、过滤条件树——在执行阶段都有明确的消费位置。这种分离使两个阶段可以独立优化：准备阶段专注于选择最优计划（代价较高），执行阶段专注于高效迭代（性能敏感）。

从数据依赖关系可以进一步总结出准备阶段各个产物在执行阶段的对应消费位置和消费方式：

```text
如图 7-49 所示，准备产物 → 执行消费映射表
                        │
  ┌──────────────────────────┬──────────────────────────┬────────────────┐
  │ 准备阶段产物              │ 执行阶段消费位置          │ 消费方式        │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ selectList: Expression[] │ 行输出循环                │ getValue()     │
  │                         │ row[i] = expr.getValue()  │ 多态求值       │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ topFilter: TableFilter   │ topTableFilter.next()    │ 状态机驱动     │
  │                         │ 最外层行迭代循环          │ next() 调用    │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ planItem.index: Index    │ cursor.find() / next()   │ 索引定位       │
  │                         │ 游标初始化 + 遍历        │ B-Tree遍历     │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ indexConditions          │ cursor.find(session,     │ 范围条件设置   │
  │                         │   indexConditions)        │ start/end      │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ filterCondition: Expr    │ isOk(filterCondition)    │ 表达式求值     │
  │                         │ 过滤条件检查              │ 短路优化       │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ joinCondition: Expr      │ isOk(joinCondition)      │ 表达式求值     │
  │                         │ 连接条件检查              │ 逐行过滤       │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ join: TableFilter 链     │ join.next()              │ 嵌套循环       │
  │                         │ 内表迭代                  │ 递归调用       │
  ├──────────────────────────┼──────────────────────────┼────────────────┤
  │ masks: int[]             │ cursor 查找              │ 索引列匹配     │
  │                         │ B-Tree定位                │ 位运算检查     │
  └──────────────────────────┴──────────────────────────┴────────────────┘
```
**图 7-49: 汇总 准备产物到执行消费的映射**

该表为图 7-48 的数据流图提供了补充说明，详细列出了每个准备阶段产物在执行阶段的具体消费位置和消费方式。这张映射表有助于理解"准备阶段做了什么，执行阶段用了什么"：例如，`planItem.index` 在执行阶段用于 `cursor.find()` 初始化游标，`masks` 数组用于索引条件匹配，`joinCondition` 用于行过滤。如果某个准备产物在执行阶段没有被消费（或者消费方式异常），就意味着可能产生了不必要的计算开销。

### 7.5.3 执行阶段性能热点

从执行阶段的角度看，SQL 执行时间主要分布在以下热点路径中：

1. **TableFilter.next() 循环** — 这是最内层的循环体，调用频率最高。对于百万行级别的全表扫描，`next()` 方法的每次调用都在毫秒以下，但累计时间占比最大
2. **cursor.find() / cursor.next()** — 索引游标的 B-Tree遍历，涉及磁盘 I/O 或缓存访问
3. **isOk(filterCondition)** — 条件表达式的递归求值，Expression 树遍历的开销
4. **getValue(session)** — 每列的表达式求值，多态分发和类型转换的开销

在性能调优时，应优先关注热点 1 和 2——减少 `next()` 的调用次数（通过索引过滤减少扫描行数）是提升查询性能最有效的手段。

执行阶段各热点的相对耗时分布可以通过以下调用频次和单次开销对比来理解：

```text
执行阶段性能热点分析
                        │
  ┌─────────────────────────────────────────────────────────────┐
  │  热点 1: TableFilter.next() 循环                            │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  调用次数: 扫描行数 (N 行)                            │  │
  │  │  单次开销: ~0.1μs (状态机跳转)                        │  │
  │  │  总开销: N × 0.1μs = N/10,000,000 秒                 │  │
  │  │  优化手段: 索引过滤减少 N                              │  │
  │  └───────────────────────────────────────────────────────┘  │
  │                                                             │
  │  热点 2: cursor.find() / cursor.next()                      │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  调用次数: 扫描行数 (N 行)                            │  │
  │  │  单次开销: ~1-10μs (B-Tree页访问)                      │  │
  │  │  总开销: N × 5μs (典型值)                             │  │
  │  │  优化手段: 覆盖索引减少回表                            │  │
  │  └───────────────────────────────────────────────────────┘  │
  │                                                             │
  │  热点 3: isOk(filterCondition)                               │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  调用次数: 扫描行数 (N 行)                            │  │
  │  │  单次开销: ~0.5μs (表达式树遍历)                      │  │
  │  │  总开销: N × 0.5μs                                   │  │
  │  │  优化手段: 索引条件下推减少行数                       │  │
  │  └───────────────────────────────────────────────────────┘  │
  │                                                             │
  │  热点 4: expressions.getValue(session)                      │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  调用次数: 输出行数 × SELECT 列数 (M × K)            │  │
  │  │  单次开销: ~0.2μs (多态分发 + 类型转换)               │  │
  │  │  总开销: M × K × 0.2μs                               │  │
  │  │  优化手段: 减少 SELECT 列, 使用覆盖索引               │  │
  │  └───────────────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────────────┘

  如图 7-50 所示，典型查询的热点分布 (全表扫描 100 万行, SELECT 5 列):
  ┌────────────────────┬───────────┬──────────┬───────────────┐
  │ 热点               │ 相对占比  │ 绝对耗时 │ 优化优先级    │
  ├────────────────────┼───────────┼──────────┼───────────────┤
  │ cursor.next()      │ 50-70%    │ 5 秒     │ ★★★ 最高     │
  │ TableFilter.next() │ 5-10%     │ 0.5 秒   │ ★★            │
  │ isOk(filter)       │ 10-20%    │ 1 秒     │ ★★            │
  │ getValue()         │ 10-20%    │ 1 秒     │ ★             │
  └────────────────────┴───────────┴──────────┴───────────────┘
```
**图 7-50: 标注 执行阶段四个性能热点的分布**

该图量化了执行阶段四个热点的调用次数、单次开销和总耗时。`cursor.next()` 的 B-Tree页访问是绝对的热点——占全表扫描总耗时的 50-70%。索引覆盖扫描可以将热点 4（getValue）的开销降低到接近零，因为不需要回表读取数据页。性能调优的优先级排序是：先减少 `N`（扫描行数，通过索引过滤），再减少单次开销（通过覆盖扫描）。

---

## 7.6 表达式求值

### 7.6.1 多态分发机制

所有表达式继承自 `Expression`，核心方法：

```java
public abstract Value getValue(SessionLocal session);
```

如图 7-38 所示，`Expression.getValue(session)` 是虚方法，具体行为由子类实现：

```text
Expression.getValue(session)  (多态分发)
  │
  ├─ ExpressionColumn  → 从当前行读取列值
  ├─ Comparison        → 比较两个表达式值
  ├─ ConditionAndOr    → 短路逻辑运算 (AND/OR)
  ├─ JavaFunction      → 调用内置函数
  ├─ Subquery          → 执行子查询
  ├─ Aggregate         → 读取聚合结果
  └─ ValueExpression   → 返回常量
```

表达式求值采用**策略模式**——每个 Expression 子类实现独立的求值策略，通过 Java 虚方法分派在运行时选择正确的实现：

```text
多态分发机制详解
                        │
  调用方: isOk(filterCondition)
    │
    └── condition.getValue(session)
          │
          │  Java 虚方法分派 (VTable 查找)
          │
          ├── condition 的实际类型是 Comparison?
          │     └── Comparison.getValue() 被调用
          │           ├── left.getValue()   → 递归分派
          │           └── right.getValue()  → 递归分派
          │
          ├── condition 的实际类型是 ConditionAndOr?
          │     └── ConditionAndOr.getValue() 被调用
          │           ├── left.getValue()   → 短路检查
          │           └── right.getValue()  → 按需求值
          │
          └── 每种类型的分派路径都是编译时确定的
                (JIT 内联缓存优化后, 性能接近直接调用)

  类型               │  getValue 行为              │  返回值
  ──────────────────┼─────────────────────────────┼───────────
  ExpressionColumn  │ TableFilter.get(columnId)   │ 列值
  ValueExpression   │ 返回内部常量                 │ 常量
  Parameter         │ 返回已绑定的参数值           │ 参数值
  Comparison        │ 左右子表达式求值 + 比较      │ TRUE/FALSE/NULL
  ConditionAndOr    │ 短路求值左右子表达式          │ TRUE/FALSE
  JavaFunction      │ 参数求值 + 调用 Java 方法    │ 函数结果
  Subquery          │ 递归执行子查询               │ 标量值
  Aggregate         │ 读取分组聚合结果              │ 聚合值
```
**图 7-51: 拆解 Expression 虚方法多态分发**

如图 7-51 所示，该图展示了表达式求值的核心设计——通过 Java 虚方法实现多态分派，每种表达式类型提供独立的 `getValue()` 实现。当 `isOk(filterCondition)` 调用 `condition.getValue(session)` 时，Java 运行时根据 `condition` 的实际类型决定调用哪个子类的实现。这种设计使得求值逻辑的扩展性极好——新增一种表达式类型只需要创建一个继承 Expression 的子类并实现 `getValue()` 方法，无需修改现有代码。

### 7.6.2 `ExpressionColumn.getValue(session)`

源码位置：`org/h2/expression/ExpressionColumn.java:272`

```java
public Value getValue(SessionLocal session) {
    Select select = columnResolver.getSelect();
    if (select != null) {
        SelectGroups groupData = select.getGroupDataIfCurrent(false);
        if (groupData != null) {
            Value v = groupData.getCurrentGroupExprData(this);
            if (v != null) return v;  // 聚合结果缓存
        }
    }
    // 从当前行读取
    return columnResolver.getValue(column);
}
```

最终通过 `TableFilter.get()` 获取当前行，再按列索引取出 Value。

该方法的执行路径包含两条分支——聚合缓存读取和当前行读取：

```text
如图 7-52 所示，ExpressionColumn.getValue() 执行路径
                        │
  ExpressionColumn.getValue(session)
    │
    ├── Step 1: 检查是否在聚合查询上下文中
    │     │
    │     ├── columnResolver.getSelect() != null?
    │     │     │
    │     │     └── YES → select.getGroupDataIfCurrent(false)
    │     │           │
    │     │           ├── groupData != null?
    │     │           │     │
    │     │           │     ├── YES → groupData.getCurrentGroupExprData(this)
    │     │           │     │     │
    │     │           │     │     ├── v != null? → return v  (聚合缓存命中)
    │     │           │     │     └── v == null? → 降级到 Step 2
    │     │           │     │
    │     │           │     └── NO → 降级到 Step 2
    │     │           │
    │     │           └── (继续)
    │     │
    │     └── NO → 直接 Step 2
    │
    └── Step 2: 从当前行读取列值
          │
          └── columnResolver.getValue(column)
                │
                ├── ExpressionColumn.columnResolver
                │     → 指向 TableFilter (在 mapColumns 阶段绑定)
                │
                ├── columnResolver.getCurrentRow()
                │     → TableFilter.currentSearchRow
                │
                └── currentRow.getValue(column.getColumnId())
                      → 返回列值 (Value 类型)
```
**图 7-52: 拆解 ExpressionColumn 列值读取路径**
```text
如图 7-53 所示，ColumnResolver 绑定链 — 从列名到值的完整链路
                        │
  阶段 1: 编译期 — ExpressionColumn.mapColumns()
                        │
    ExpressionColumn("t.age")
      │
      ├── columnResolver = resolveColumnResolver(tableFilter)
      │     │
      │     ├── 遍历 Session 中的 resolveQueue
      │     ├── 查找列名 "age" 并匹配表名 "t"
      │     └── 绑定: columnResolver → TableFilter(test)
      │
      └── column = table.getColumn("age")
            │
            └── columnId = 3 (表中第 4 列)
                  │
                  绑定关系存储: columnResolver + columnId
                        │
  阶段 2: 执行期 — ExpressionColumn.getValue(session)
                        │
    ExpressionColumn(t.age)
      │
      ├── (可选) 检查聚合缓存 groupData
      │
      └── columnResolver.getValue(column)
            │
            ├── columnResolver → TableFilter
            │
            └── TableFilter.getCurrentRow()
                  │
                  └── currentRow.getValue(columnId)
                        │
                        ├── columnId = 3
                        ├── row = [101, 'John', 25, ...]
                        │                   ↑
                        │              columnId=3 → 25
                        └── return ValueInt(25)
```
**图 7-53: 追踪 ColumnResolver 从列名到值的绑定链**

### 7.6.3 `Comparison.evaluate()`

`Comparison` 对左右两个表达式分别求值，然后根据比较类型执行比较：

```java
// Comparison 伪代码
public Value getValue(SessionLocal session) {
    Value left = leftExpr.getValue(session);
    Value right = rightExpr.getValue(session);
    return compare(left, right, compareType);  // EQUAL, BIGGER, SMALLER, ...
}
```

如图 7-52 所示，Comparison 求值的数据流和执行路径如下：

```text
如图 7-54 所示，Comparison.getValue() 数据流
                        │
  Comparison.getValue(session)
    │
    ├── left = leftExpr.getValue(session)
    │     │
    │     ├── leftExpr 类型示例:
    │     │     ├── ExpressionColumn(t.age)    → 25
    │     │     ├── ExpressionColumn(t.name)   → 'John'
    │     │     ├── JavaFunction(LENGTH(t.n))  → 5
    │     │     └── Subquery(...)              → 100
    │     │
    │     └── left 类型: ValueInt / ValueString / ValueNull / ...
    │
    ├── right = rightExpr.getValue(session)
    │     │
    │     ├── rightExpr 类型示例:
    │     │     ├── ValueExpression(18)       → 18
    │     │     ├── Parameter(?)              → 已绑定值
    │     │     └── ExpressionColumn(t.flag)  → true
    │     │
    │     └── right 类型: ValueInt / ValueBoolean / ...
    │
    └── compare(left, right, compareType)
          │
          ├── 类型一致性处理:
          │     ├── left 和 right 类型相同 → 直接比较
          │     └── 类型不同 → DataType.compareWithConversion()
          │
          └── 比较操作:
                ├── EQUAL      → left == right
                ├── BIGGER     → left > right
                ├── BIGGER_EQUAL → left >= right
                ├── SMALLER    → left < right
                └── SMALLER_EQUAL → left <= right
                      │
                      ▼
                return ValueBoolean(TRUE/FALSE) / ValueNull.UNKNOWN
```
**图 7-54: 拆解 Comparison.getValue 左右求值与比较**
```text
如图 7-55 所示，三值逻辑 (NULL 处理) 在比较中的传播路径
                        │
  Comparison.getValue(session)
    │
    ├── left = leftExpr.getValue(session)
    │     │
    │     ├── 正常值 (ValueInt, ValueString, ...)
    │     └── ValueNull (NULL 字面量或 NULL 列值)
    │
    ├── right = rightExpr.getValue(session)
    │     │
    │     ├── 正常值
    │     └── ValueNull
    │
    └── compare(left, right, compareType)
          │
          ├── left == ValueNull OR right == ValueNull?
          │     │
          │     ├── YES → return ValueNull.UNKNOWN
          │     │     │
          │     │     └── SQL 语义: NULL 与任何值比较结果为 UNKNOWN
          │     │           │
          │     │           ├── WHERE 子句中 → 行被过滤 (不满足条件)
          │     │           ├── CHECK 约束中 → 视为通过 (不违反约束)
          │     │           └── JOIN 条件中 → 不匹配任何行
          │     │
          │     └── NO → 执行实际比较
          │           │
          │           ├── 类型相同 → 直接比较
          │           │     ├── EQUAL       → left == right
          │           │     ├── BIGGER      → left > right
          │           │     ├── SMALLER     → left < right
          │           │     ├── BIGGER_EQUAL → left >= right
          │           │     ├── SMALLER_EQUAL → left <= right
          │           │     ├── NOT_EQUAL   → left != right
          │           │     ├── IS_NULL     → false (值非 NULL)
          │           │     └── IS_NOT_NULL → true
          │           │
          │           └── 类型不同 → DataType.compareWithConversion()
          │                 ├── VARCHAR vs INT → 尝试类型转换
          │                 └── 转换失败 → 按类型优先级比较
          │
          └── return ValueBoolean(TRUE/FALSE) / ValueNull.UNKNOWN
```

**图 7-55: 追踪 三值逻辑 NULL 在比较中的传播路径**

### 7.6.4 `ConditionAndOr` — 短路求值

`ConditionAndOr` 实现 AND/OR 的短路逻辑。对于 `AND`，左表达式为 false 时不再求右表达式；对于 `OR`，左表达式为 true 时不再求右表达式。

```java
// ConditionAndOr 伪代码
public Value getValue(SessionLocal session) {
    Value left = leftExpr.getValue(session);
    if (and) {
        if (!left.isTrue()) return left;    // AND 短路
    } else {
        if (left.isTrue()) return left;     // OR 短路
    }
    return rightExpr.getValue(session);
}
```

如图 7-54 所示，短路求值的四种可能路径可以用真值表完整描述：

```text
短路求值真值表
                        │
  AND 操作 (and=true):
  ┌──────────┬──────────┬──────────┬──────────┬──────────────────┐
  │ left     │ right    │ left     │ 是否求值 │ 结果              │
  │ 值       │ 值       │ .isTrue()│ right?   │                   │
  ├──────────┼──────────┼──────────┼──────────┼──────────────────┤
  │ TRUE     │ TRUE     │ true     │ 是       │ TRUE             │
  │ TRUE     │ FALSE    │ true     │ 是       │ FALSE            │
  │ FALSE    │ (未求值) │ false    │ **否**   │ FALSE  (短路)    │
  │ NULL     │ (未求值) │ false    │ **否**   │ NULL   (短路)    │
  └──────────┴──────────┴──────────┴──────────┴──────────────────┘

  OR 操作 (and=false):
  ┌──────────┬──────────┬──────────┬──────────┬──────────────────┐
  │ left     │ right    │ left     │ 是否求值 │ 结果              │
  │ 值       │ 值       │ .isTrue()│ right?   │                   │
  ├──────────┼──────────┼──────────┼──────────┼──────────────────┤
  │ TRUE     │ (未求值) │ true     │ **否**   │ TRUE   (短路)    │
  │ FALSE    │ TRUE     │ false    │ 是       │ TRUE             │
  │ FALSE    │ FALSE    │ false    │ 是       │ FALSE            │
  │ NULL     │ (未求值) │ false    │ **否**   │ NULL   (短路)    │
  └──────────┴──────────┴──────────┴──────────┴──────────────────┘
```

**图 7-56: 罗列 AND/OR 短路求值真值表**

如图 7-56 所示，该真值表完整描述了 `ConditionAndOr` 短路求值的所有可能路径。关键观察：当 `left.isTrue()` 返回 false 时（对于 AND 操作），不会对 right 求值；当 `left.isTrue()` 返回 true 时（对于 OR 操作），同样不会对 right 求值。注意三值逻辑（TRUE/FALSE/NULL）的处理：NULL 在 `isTrue()` 检查中返回 false，因此对于 AND 操作，left=NULL 会导致短路并返回 NULL；对于 OR 操作，left=NULL 也会导致短路。这是因为 `NULL AND x` 和 `NULL OR x` 的结果可能为 NULL（取决于 x），但短路求值的语义是确定的——左值为 NULL 时，最终结果由右值决定，因此不能短路。

### 7.6.5 `Subquery` — 嵌套查询

子查询 Expression 内部持有一个 `Query` 对象，求值时递归执行：

```java
public Value getValue(SessionLocal session) {
    ResultInterface result = query.query(0);  // 递归执行子查询
    return result.next() ? result.currentRow()[0] : ValueNull.INSTANCE;
}
```

Subquery 的递归执行涉及多个组件的协作：

```text
Subquery.getValue() 递归执行过程
                        │
  外层查询执行中:
    isOk(filterCondition)
      └── Subquery.getValue(session)
            │
            ├── query.query(0)
            │     │
            │     ├── 注意: 递归执行子查询!
            │     │     └── 子查询本身也是一个 Select 对象
            │     │           拥有完整的解析 → 优化 → 执行流程
            │     │
            │     ├── 子查询的执行路径:
            │     │     ├── Select.queryWithoutCache()
            │     │     ├── topTableFilter.next() 循环
            │     │     ├── isOk(filterCondition)
            │     │     └── ... (与普通查询完全相同)
            │     │
            │     ├── 锁: session 锁可重入
            │     │     (ReentrantLock 支持同一线程重复获取)
            │     │
            │     └── 返回: ResultInterface (子查询结果集)
            │
            ├── result.next()?
            │     ├── YES → result.currentRow()[0]  (标量值)
            │     └── NO  → ValueNull.INSTANCE     (空结果)
            │
            └── return Value (参与外层条件求值)

  子查询类型示例:
  ┌──────────────────────┬──────────────────────┬─────────────────┐
  │ 子查询位置            │ 示例                  │ 返回值语义       │
  ├──────────────────────┼──────────────────────┼─────────────────┤
  │ WHERE col = (子查询) │ 标量子查询             │ 首行首列        │
  │ WHERE col IN (子查询)│ IN 子查询             │ boolean         │
  │ WHERE EXISTS (子查询)│ EXISTS 子查询          │ boolean         │
  └──────────────────────┴──────────────────────┴─────────────────┘
```
**图 7-57: 追踪 Subquery.getValue 的递归执行路径**

如图 7-57 所示，Subquery 求值的核心特点是**递归性**——它的 `getValue()` 方法会触发一次完整的子查询执行，包括子查询内部的解析（如果尚未编译）、优化和执行。此过程中，session 锁的可重入性至关重要：外层查询已经持有了 session 锁，子查询执行时再次获取同一把锁，`ReentrantLock` 的持有计数机制允许这种重入，避免了死锁。

### 7.6.6 表达式求值流程图

```text
fetchNextRow()
  │
  ├── topTableFilter.next()
  │     ├── cursor.find()        ← 索引定位
  │     ├── cursor.next()         ← 下一条记录
  │     └── isOk(filterCondition) ← 剩余条件过滤
  │
  ├── isConditionMet()
  │     └── condition.getValue(session)
  │           ├── Comparison.getValue()
  │           │     ├── left.getValue()   → ExpressionColumn → TableFilter.get()
  │           │     └── right.getValue()  → Parameter / ValueExpression
  │           │
  │           └── ConditionAndOr.getValue()
  │                 ├── left.getValue()    → 短路检查
  │                 └── right.getValue()   → 需要时求值
  │
  └── row[i] = expressions.get(i).getValue(session)
        ├── ExpressionColumn → 当前行的列值
        ├── JavaFunction     → 函数计算结果
        └── ...
```

在 `fetchNextRow()` 的完整流程中，表达式求值分为三个阶段，每个阶段处理不同类型的表达式：

```text
表达式求值三阶段
                        │
  fetchNextRow() 中的求值顺序
    │
    阶段 1: 索引条件求值 (cursor.find)
    │   在 cursor.find() 时使用
    │   条件类型: IndexCondition (EQUALITY / START / END)
    │   求值结果: 设置索引游标的起始/结束位置
    │   调用链: cursor.find(session, indexConditions)
    │            → IndexCondition.getValue() → 获取比较值
    │
    阶段 2: 过滤条件求值 (isOk)
    │   在 cursor.next() 后对每行执行
    │   条件类型: filterCondition (Expression 树)
    │   求值结果: TRUE(接纳) / FALSE(跳过) / NULL(跳过)
    │   调用链: isOk(filterCondition)
    │            → filterCondition.getValue(session)
    │              → 递归求值整个表达式树
    │               ├── Comparison.getValue()
    │               ├── ConditionAndOr.getValue()
    │               └── Subquery.getValue()
    │
    阶段 3: 输出列求值 (row[i])
    │   在行被接纳后对每列执行
    │   表达式类型: selectList 中的 Expression
    │   求值结果: 列值 (Value 类型)
    │   调用链: expressions[i].getValue(session)
    │            ├── ExpressionColumn.getValue() → 列值
    │            ├── JavaFunction.getValue()    → 函数结果
    │            ├── Aggregate.getValue()       → 聚合值
    │            └── ...
    │
    三阶段执行时间占比 (典型查询):
    ┌──────────────┬──────────┬─────────────────────────────────┐
    │ 阶段          │ 占比     │ 说明                            │
    ├──────────────┼──────────┼─────────────────────────────────┤
    │ 索引条件求值  │ <1%     │ 仅执行一次, 用于游标定位          │
    │ 过滤条件求值  │ 10-30%  │ 每行执行, 复杂度取决于条件树深度  │
    │ 输出列求值    │ 5-15%   │ 每行执行, 复杂度取决于列数        │
    └──────────────┴──────────┴─────────────────────────────────┘
```
**图 7-58: 拆解 表达式求值的索引/过滤/输出三阶段**

如图 7-58 所示，该图将 `fetchNextRow()` 中的表达式求值活动划分为三个按顺序执行的阶段。阶段 1 在游标定位时执行，产生索引的起始/结束位置；阶段 2 在每行读取后执行，判断过滤条件是否接纳该行；阶段 3 在接纳的行上执行，计算 SELECT 列表中的每个列值。理解这三个阶段有助于定位查询性能问题：如果过滤条件求值占比过高，说明索引过滤不足，大量行在阶段 2 被舍弃；如果输出列求值占比过高，意味着 SELECT 列太多或求值开销大。

### 7.6.7 Expression 类继承层次结构

**图 7-59: 概览 Expression 抽象类与子类体系**

如图 7-59 所示，所有表达式都继承自抽象基类 `Expression`。

```text
Expression (抽象基类, expression/Expression.java)
  │
  │  核心抽象方法:
  │    getValue(SessionLocal) : Value    ← 求值入口
  │    getType() : int                   ← 返回数据类型
  │    getCost() : int                   ← 估计表达式计算代价
  │    isEverything(ExpressionVisitor)   ← 特性检查
  │    mapColumns(ColverResolver, int)   ← 列名解析绑定
  │    optimize(SessionLocal)            ← 常量折叠优化
  │
  ├── ExpressionColumn                    ← 列引用 (如 t.name)
  │     ├── columnResolver: ColumnResolver ← 指向所属 TableFilter
  │     ├── column: Column                ← 列元数据
  │     ├── getValue(session)             ← 从 TableFilter 当前行读值
  │     ├── getType()                     ← 返回列的数据类型
  │     └── mapColumns(resolver)          ← 绑定到 TableFilter
  │
  ├── ValueExpression                     ← 常量值
  │     └── getValue(session)             ← 直接返回内部 Value
  │
  ├── Parameter                           ← 参数占位符 (?)
  │     ├── index: int                    ← 参数序号
  │     ├── setValue(value)               ← 绑定时设置值
  │     └── getValue(session)             ← 返回已绑定的值
  │
  ├── Comparison                          ← 比较表达式 (=, >, <, ...)
  │     ├── compareType: int              ← 比较类型 (EQUAL, BIGGER, ...)
  │     ├── left: Expression              ← 左操作数
  │     ├── right: Expression             ← 右操作数
  │     └── getValue(session)             ← 左右求值 → 执行比较
  │
  ├── ConditionAndOr                      ← 逻辑运算 (AND / OR)
  │     ├── and: boolean                  ← true=AND, false=OR
  │     ├── left: Expression              ← 左条件
  │     ├── right: Expression             ← 右条件
  │     └── getValue(session)             ← 短路求值
  │
  ├── ConditionInConstantSet              ← IN 常量集合
  │     ├── valueSet: HashSet<Value>      ← 常量哈希集合
  │     └── getValue(session)             ← 哈希查找 O(1)
  │
  ├── ConditionIn                         ← IN 子查询
  │     ├── left: Expression
  │     ├── right: Query                   ← 子查询
  │     └── getValue(session)             ← 执行子查询并匹配
  │
  ├── Subquery                            ← 子查询表达式
  │     ├── query: Query                   ← 子查询对象
  │     └── getValue(session)             ← query.query(0) → 取首行首列
  │
  ├── JavaFunction                        ← Java 内置函数
  │     ├── function: FunctionInfo
  │     ├── args: Expression[]            ← 函数参数
  │     └── getValue(session)             ← 计算参数 → 调用 Java 方法
  │
  ├── Aggregate                           ← 聚合函数 (COUNT, SUM, AVG, ...)
  │     ├── aggregateType: int
  │     ├── on: Expression                ← 聚合列
  │     ├── getValue(session)             ← 从 GroupData 读取聚合结果
  │     └── Stage: INIT → PREPARE → AGGREGATE → FINAL
  │
  ├── Selectivity                         ← 选择率估计
  │     └── getSelectivity()              ← 返回 0~1 的选择率
  │
  └── Alias                               ← 别名表达式
        └── getValue(session)             ← 委托给被包裹的表达式
```

下面三张图把 Expression 体系拆成三个层次：图 7-81 展示子类继承层次，图 7-60 横向对比各子类的求值深度与开销，图 7-61 演示一条复杂 WHERE 条件的递归求值过程。

**图 7-81: 展示 Expression 子类继承层次**

如图 7-81 所示，该图展示了 H2 表达系统的完整类型层次。`Expression` 是所有表达式节点的共同抽象基类，定义了一组核心方法契约。从列引用 (`ExpressionColumn`) 到常量 (`ValueExpression`)，从比较操作 (`Comparison`) 到逻辑运算 (`ConditionAndOr`)，从子查询 (`Subquery`) 到聚合函数 (`Aggregate`)，每个子类都实现了 `getValue(session)` 方法以提供对应的求值语义。

表达式树的节点组合方式与 SQL 语法直接对应。例如，`WHERE t.id = 1 AND t.name IS NOT NULL` 会被解析为：
```text
ConditionAndOr(AND)
  ├── Comparison(EQUAL)
  │     ├── ExpressionColumn(t.id)
  │     └── ValueExpression(1)
  └── Comparison(IS_NOT_NULL)
        └── ExpressionColumn(t.name)
```

不同 Expression 子类的 `getValue()` 方法在求值深度和资源消耗方面有显著差异：

```text
Expression 子类求值特征对比
                        │
  ┌──────────────────┬──────────┬──────────┬─────────────────────────────┐
  │ 子类              │ 求值深度  │ 资源消耗  │ 典型场景                    │
  ├──────────────────┼──────────┼──────────┼─────────────────────────────┤
  │ ValueExpression  │ O(1)     │ 几乎为零 │ 常量 1, 'ACTIVE'           │
  │ Parameter        │ O(1)     │ 几乎为零 │ 参数 ?                     │
  │ ExpressionColumn │ O(1)     │ 低       │ t.name, t.age              │
  │ JavaFunction     │ O(k)     │ 中       │ LENGTH(t.name)             │
  │ Comparison       │ O(k)     │ 中       │ t.age > 18                 │
  │ ConditionAndOr   │ O(k)     │ 中       │ t.age > 18 AND status=1    │
  │ ConditionIn      │ O(k+m)   │ 中-高    │ t.id IN (子查询)           │
  │ Aggregate        │ O(1)     │ 低       │ COUNT(*), SUM(amount)      │
  │ Subquery         │ O(复杂)  │ 很高     │ (SELECT MAX(p) FROM t2)    │
  ├──────────────────┼──────────┼──────────┼─────────────────────────────┤
  │ 注: k = 子表达式数量, m = 集合大小                                   │
  └─────────────────────────────────────────────────────────────────────┘
```
**图 7-60: 对比 Expression 子类的求值深度与开销**

如图 7-61 所示，如图 7-60 所示，各子类的求值特征差异决定了查询优化的方向：`Subquery` 和 `ConditionIn` 是最昂贵的表达式类型，应尽可能避免在 WHERE 条件中使用子查询；`ExpressionColumn` 的求值开销虽然低，但调用频次极高（每行每列各一次），应通过减少 SELECT 列数来优化。

### 7.6.8 表达式树递归求值过程

**图 7-61: 演示 复杂 WHERE 条件的递归求值过程**

```text
表达式树递归求值示例

SQL: WHERE t.age > 18 AND (t.status = 'ACTIVE' OR t.score >= 60)
                        │
                        ▼
           ConditionAndOr.getValue(AND)
                  left │          │ right
                       ▼          ▼
              Comparison          ConditionAndOr(OR)
              (BIGGER)           left │          │ right
              │      │                │          │
              ▼      ▼                ▼          ▼
        Expression  ValueExp     Comparison    Comparison
        Column      (18)         (EQUAL)       (BIGGER_EQUAL)
        (t.age)                  │      │       │       │
                                 ▼      ▼       ▼       ▼
                           Expression  Value  Expression  Value
                           Column      'ACTIVE' Column    (60)
                           (t.status)          (t.score)

如图 7-75 所示，求值过程 (从左到右, AND 短路):
                        │
                        ▼
  步骤 1: ConditionAndOr.getValue() → AND
     │
     ├── 评估 left (Comparison BIGGER)
     │     │
     │     ├── left.getValue()  → ExpressionColumn(t.age)
     │     │     └── TableFilter.get() → Value(25)
     │     │
     │     ├── right.getValue() → ValueExpression(18)
     │     │     └── return Value(18)
     │     │
     │     └── compare(25, 18, BIGGER) → TRUE
     │
     ├── AND 短路检查: left=TRUE, 需要继续评估 right
     │
     ├── 评估 right (ConditionAndOr → OR)
     │     │
     │     ├── 评估 left (Comparison EQUAL)
     │     │     │
     │     │     ├── left.getValue()  → ExpressionColumn(t.status)
     │     │     │     └── TableFilter.get() → Value('INACTIVE')
     │     │     │
     │     │     ├── right.getValue() → ValueExpression('ACTIVE')
     │     │     │
     │     │     └── compare('INACTIVE', 'ACTIVE', EQUAL) → FALSE
     │     │
     │     ├── OR 短路检查: left=FALSE, 需要继续评估 right
     │     │
     │     ├── 评估 right (Comparison BIGGER_EQUAL)
     │     │     │
     │     │     ├── left.getValue() → ExpressionColumn(t.score)
     │     │     │     └── TableFilter.get() → Value(85)
     │     │     │
     │     │     ├── right.getValue() → ValueExpression(60)
     │     │     │
     │     │     └── compare(85, 60, BIGGER_EQUAL) → TRUE
     │     │
     │     └── OR 结果: left=FALSE, right=TRUE → TRUE
     │
     └── AND 结果: left=TRUE, right=TRUE → TRUE
            │
            ▼
        行被接纳 (返回当前行)
```

**图 7-75: 演示 表达式树递归求值的步骤序列**

该图以具体示例展示了 `ConditionAndOr.getValue()` 如何递归驱动整个表达式树的求值。求值过程遵循深度优先、自底向上的策略：

1. 根节点 `ConditionAndOr(AND)` 首先对左子树 `Comparison(BIGGER)` 求值。`Comparison.getValue()` 先对左右子表达式递归求值，然后执行比较操作。左子表达式 `ExpressionColumn(t.age)` 从当前行的 `TableFilter` 读取列值（25），右子表达式 `ValueExpression(18)` 直接返回常量值，比较结果为 TRUE。

2. AND 短路规则生效：左子树结果为 TRUE，不能短路，需要继续评估右子树。

3. 右子树 `ConditionAndOr(OR)` 开始评估其左子树 `Comparison(EQUAL)`。同样递归求值，比较 `t.status`（'INACTIVE'）与常量 'ACTIVE'，结果为 FALSE。

4. OR 短路规则生效：左子树结果为 FALSE，不能短路，需要继续评估右子树。

5. `Comparison(BIGGER_EQUAL)` 比较 `t.score`（85）与 60，结果为 TRUE。OR 的最终结果为 FALSE || TRUE = TRUE。

6. AND 的最终结果为 TRUE && TRUE = TRUE，当前行被接纳为匹配行。

表达式树递归求值可以抽象为深度优先遍历的过程，其遍历路径与表达式树的拓扑结构直接对应：

```text
表达式树递归求值的深度优先遍历过程
                        │
  WHERE t.age > 18 AND (t.status = 'ACTIVE' OR t.score >= 60)
                        │
  遍历路径:
                        AND (根)
                        │
          ┌─────────────┴─────────────┐
          │                           │
       > 18 (左子树)               OR (右子树)
          │                           │
          │                 ┌─────────┴─────────┐
          │                 │                   │
       t.age             = 'ACTIVE'          ≥ 60 (右子树)
                          │                   │
                          │                   │
                       t.status            t.score

  递归求值顺序 (深度优先, 自底向上):
    1. t.age.getValue() → 25
    2. 18 固定常量
    3. Comparison(BIGGER, 25, 18) → TRUE
    4. t.status.getValue() → 'INACTIVE'
    5. 'ACTIVE' 固定常量
    6. Comparison(EQUAL, 'INACTIVE', 'ACTIVE') → FALSE
    7. t.score.getValue() → 85
    8. 60 固定常量
    9. Comparison(BIGGER_EQUAL, 85, 60) → TRUE
   10. ConditionAndOr(OR, FALSE, TRUE) → TRUE
   11. ConditionAndOr(AND, TRUE, TRUE) → TRUE

  如图 7-62 所示，求值路径特点:
    ├── 叶子节点: ExpressionColumn / ValueExpression → 获取原始值
    ├── 中间节点: Comparison → 对子节点求值后执行比较
    ├── 分支节点: ConditionAndOr → 短路控制
    └── 根节点: 返回最终布尔结果
```
**图 7-62: 刻画 表达式树深度优先遍历求值**

如图 7-63 所示，该图将表达式树的递归求值过程抽象为深度优先遍历。求值从树的叶子节点开始（获取列值和常量），逐层向上执行比较和逻辑运算，最终在根节点得到布尔结果。注意 `ConditionAndOr(OR)` 在步骤 6 得到 FALSE 后没有立即短路——因为子树的结构已经决定了它需要在步骤 7-9 继续求值右子树。短路实际发生在 `ConditionAndOr.getValue()` 方法内部，即步骤 10 检查左值 FALSE 后仍需评估右值（OR 操作左 FALSE 时不短路）。

### 7.6.9 短路求值与类型转换机制

**图 7-63: 拆解 短路求值控制流与隐式类型转换**

```text
短路求值控制流:

ConditionAndOr.getValue(session)    ← AND 节点入口
  │
  ├── left = leftExpr.getValue(session)   ← 始终对左子树求值
  │
  ├── if (and) {
  │     │
  │     ├── if (!left.isTrue())    ← 左为 FALSE 时短路
  │     │     └── return left      ← 右子树不被求值!
  │     │
  │     └── else → 继续
  │
  │     right = rightExpr.getValue(session)
  │     return right
  │
  └── } else {   ← OR 节点
        │
        ├── if (left.isTrue())     ← 左为 TRUE 时短路
        │     └── return left      ← 右子树不被求值!
        │
        └── else → 继续
              │
              right = rightExpr.getValue(session)
              return right
        }

类型转换在 Comparison 中的应用:

如图 7-76 所示，Comparison.getValue(session)
  │
  ├── leftVal = leftExpr.getValue(session)   ← 左表达式求值
  │     │
  │     └── leftVal 数据类型: INTEGER (t.age)
  │
  ├── rightVal = rightExpr.getValue(session) ← 右表达式求值
  │     │
  │     └── rightVal 数据类型: INTEGER (18)
  │
  ├── 类型一致性检查:
  │     │
  │     ├── leftVal.getType() == rightVal.getType() ?
  │     │     │
  │     │     ├── YES → 直接比较
  │     │     │
  │     │     └── NO → 隐式类型转换
  │     │           │
  │     │           ├── VARCHAR → VARCHAR: 直接比较
  │     │           ├── VARCHAR → INTEGER: 字符串转数字
  │     │           ├── VARCHAR → DATE: 字符串转日期
  │     │           ├── INTEGER → BIGINT: 提升到更宽类型
  │     │           └── ... (其他类型组合)
  │     │
  │     └── DataType.compareWithConversion(leftVal, rightVal, ...)
  │
  └── compare(leftVal, rightVal, compareType)
        │
        ├── EQUAL      → left == right
        ├── BIGGER     → left > right
        ├── BIGGER_EQUAL → left >= right
        ├── SMALLER    → left < right
        ├── SMALLER_EQUAL → left <= right
        ├── NOT_EQUAL  → left != right
        ├── IS_NULL    → left == NULL
        └── IS_NOT_NULL → left != NULL
```
**图 7-76: 演示 短路求值与隐式类型转换机制**

该图揭示了表达式求值中的两个关键技术细节：

**短路求值**是 `ConditionAndOr` 的核心性能优化。对于 AND 操作，如果左表达式已为 FALSE，整个 AND 表达式的结果已确定为 FALSE，无需对右表达式求值。对于 OR 操作，如果左表达式已为 TRUE，整个 OR 表达式的结果已确定为 TRUE，同样无需对右表达式求值。短路求值不仅节省了计算资源，更重要的是可以避免因右表达式的副作用（如除零错误、空指针）导致的运行时异常。例如 `WHERE a > 0 AND 1/a > 2` 在 a=0 时，左侧 a>0 为 FALSE，右侧 1/a 不会被求值，避免了除零异常。

**类型转换**是 `Comparison` 在比较不同数据类型时必须执行的步骤。H2 的 `DataType.compareWithConversion()` 方法实现了隐式类型转换规则：整数与浮点数比较时，整数提升为浮点数；字符串与数字比较时，字符串解析为数字；DATE 与 TIMESTAMP 比较时，DATE 提升为 TIMESTAMP。这些转换规则确保了跨类型比较的正确性，但也会带来额外的计算开销——在性能敏感的场景下，显式类型转换（如 `CAST(col AS TYPE)`）通常比隐式转换更高效。

类型转换发生的时机和方向可以通过以下类型转换矩阵总结：

```text
DataType.compareWithConversion() 类型转换矩阵
                        │
  左值 \ 右值    │  INTEGER   │  VARCHAR   │  DATE      │  DECIMAL
  ──────────────┼────────────┼────────────┼────────────┼────────────
  INTEGER       │ 直接比较   │ VARCHAR→INT│ 不兼容     │ INT→DECIMAL
  VARCHAR       │ VARCHAR→INT│ 直接比较   │ VARCHAR→DT│ VARCHAR→DEC
  DATE          │ 不兼容     │ DATE→VARCHAR│ 直接比较  │ 不兼容
  DECIMAL       │ DEC→INT    │ DEC→VARCHAR│ 不兼容     │ 直接比较
  TIMESTAMP     │ 不兼容     │ TS→VARCHAR │ DATE→TS    │ 不兼容
  BOOLEAN       │ BOOL→INT   │ VARCHAR→BOOL│ 不兼容   │ 不兼容
  ──────────────┴────────────┴────────────┴────────────┴────────────

  类型转换代价排序 (从低到高):
  1. INTEGER ↔ BIGINT        ← 数值提升, 无解析开销
  2. INTEGER ↔ DECIMAL       ← 精度扩展, 无解析开销
  3. DATE ↔ TIMESTAMP        ← 时间精度调整
  4. VARCHAR → INTEGER       ← 需要字符串解析 (可能抛出异常)
  5. VARCHAR → DATE          ← 需要日期格式解析 (依赖 Locale)
  6. 其他不兼容组合          ← 运行时错误

  如图 7-64 所示，性能建议:
  ┌──────────────────────────────────────────────────────────┐
  │  WHERE int_col = '123'   → 隐式转换 VARCHAR→INTEGER     │
  │                            建议: int_col = 123           │
  │                                                            │
  │  WHERE varchar_col = 123 → 隐式转换 VARCHAR→INTEGER     │
  │                            建议: varchar_col = '123'     │
  │                                                            │
  │  隐式转换的问题: 索引可能无法使用!                        │
  │  (除非转换函数支持索引, 否则索引列上的类型转换会导致      │
  │   全表扫描)                                               │
  └──────────────────────────────────────────────────────────┘
```
**图 7-64: 归纳 DataType 比较时的类型转换矩阵**

该图总结了 H2 隐式类型转换的所有组合。核心原则：比较操作中类型不匹配时，优先级较低的类型向优先级较高的类型转换（数值优先级：INTEGER < BIGINT < DECIMAL < DOUBLE）。字符串和数字的比较是隐式转换中最常见的场景——字符串 '123' 被解析为数字 123 后参与比较。需要注意的是，对索引列应用隐式类型转换可能导致索引失效：例如 `WHERE varchar_col = 123` 实际执行的是 `WHERE CAST(varchar_col AS INTEGER) = 123`，CAST 函数阻止了索引的使用。最佳实践是保证查询中的字面量类型与列定义类型一致，避免隐式转换。

## 7.7 本章小结

第 7 章完整追踪了一条 SQL 语句从 JDBC 接口到存储层的全链路执行流程。核心内容包括：JDBC 入口层的两种语句执行方式（Statement 与 PreparedStatement）及其性能差异、Session 层的缓存与锁机制、Parser 递归下降解析的三阶段管道（词法分析、语法分析、命令包装）、Command 框架的统一执行抽象、以及表达式求值的多态分发与短路求值策略。本章的流程分析为第 8 章深入查询优化器提供了执行层面的基础铺垫——理解 SQL 如何被解析和执行，是理解查询优化器如何选择最优执行计划的前提。

## 7.8 延展阅读

- H2 官方文档《SQL Grammar》(`h2/src/docsrc/html/grammar.html`) — H2 SQL 语法完整参考
- H2 官方文档《Functions》(`h2/src/docsrc/html/functions.html`) — 内置函数列表与说明
- 本书第8章《查询优化器深度解读》 — 执行计划生成与代价优化
- 本书第3章§3.4-3.5 — Command 包与 Expression 包的类层次结构
- 本书第5章§5.1 — SELECT 流程的入口与 Command 层关系

---

