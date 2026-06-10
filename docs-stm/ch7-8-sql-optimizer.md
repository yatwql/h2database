# 第7章 SQL 执行全流程

> **本章导读**: 本章跟踪 SQL 语句从客户端到引擎再到存储的完整执行链路，重点分析 SELECT、INSERT、UPDATE、DELETE 四大 DML 语句的执行流程。从 Parser 解析、Prepared 编译到最终执行的各阶段，结合源码类和方法进行逐层剖析。
> **前置知识**: 第4章《核心模块详解》§4.1-4.2（Command/Expression 模块）；第5章《核心流程解读》§5.1-5.4（流程入口）
> **章节要点**:
> - 理解 SQL 语句从解析到执行的全链路
> - 掌握 SELECT 的查询编译和执行过程
> - 熟悉 INSERT/UPDATE/DELETE 的修改执行流程
> - 了解 LOB 处理、Batch 更新等特殊机制

> 本章追踪一条 SQL 语句从 JDBC 接口到存储层的完整执行链路，涵盖解析、缓存、Command 框架与表达式求值。Command 层整体架构详见第2章《分层模块划分》2.1.3 Command 层，相关包结构详见第3章《核心包结构详解》3.4-3.5 节。各核心算法的基础原理详见第6章《H2 数据库核心算法分析》。完整流程可结合第5章《核心流程解读》第5.1-5.4 节的 SELECT/INSERT/UPDATE/DELETE 流程对照阅读。本章共 81 张插图，信息量较大，建议分段阅读。

本章结构：7.1 节介绍 JDBC 入口与连接建立，7.2 节详解 SQL 解析流程，7.3 节说明缓存机制，7.4 节剖析 Command 执行框架，7.5 节展示完整 ASCII 流程图，7.6 节探讨表达式求值，7.7 节总结全章要点。

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
**图 7-1: JdbcStatement.executeQuery 执行流程与锁生命周期**

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
**图 7-2: JDBC 层各组件职责与调用关系**

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
**图 7-3: Statement 与 PreparedStatement 执行路径对比**

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
**图 7-4: 入口调用链的层次职责划分**

如图 7-4 所示，跟踪一次 `executeQuery` 调用，可以看到它穿透了 H2 内核的四个层次：JDBC 接口层负责标准协议适配，Session 层负责并发控制和缓存，Command 层提供统一的命令执行抽象，Engine 层负责实际的查询执行和优化。每一层在调用链中都有明确的职责边界，调用链的方向也是单向的——上层调用下层，下层不反向依赖上层。

### 7.1.4 JDBC 层架构分层详解

**图 7-5: 从 JDBC 客户端接口到 Store 存储引擎的完整分层架构**

```text
┌──────────────────────────────────────────────────────────────────────────┐
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
│    │  持久化 B+ 树    │  │  行数据增删改查  │  │  B+Tree / Hash   │     │
│    └──────────────────┘  └──────────────────┘  └──────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
```
**图 7-65: JDBC 层与内核通信架构分层图**

该图展示了 H2 数据库的经典分层架构。SQL 请求从最上层的应用层发起，依次穿透 Session 层、Command 层、Engine 层，最终到达底层的 Store 存储层。每一层都具有明确的职责边界和稳定的接口契约，层与层之间通过方法调用传递数据，体现了关注点分离的设计原则。

各层职责详述如下：

1. **应用层 (客户端代码)** — 实现标准 `java.sql` 接口，包括 `Statement`、`PreparedStatement`、`Connection` 等 JDBC 核心接口。这一层对上层应用完全透明，应用开发者只需面向 JDBC 标准 API 编程，无需了解 H2 内部实现。`JdbcConnection.prepareCommand(sql)` 是 SQL 请求进入内核的关键入口。

2. **Session 层** — 以 `SessionLocal` 为核心，是每个数据库连接对应的工作线程上下文。核心职责包括：线程同步（`lock/unlock` 机制保证单个 session 内线程安全）、查询缓存管理（`SmallLRUCache` 缓存已编译的 Command 对象）、元数据版本追踪（`modificationMetaID` 在 DDL 后递增以触发缓存失效）。Session 层在整个链路中扮演着"交通指挥"的角色。注：在 ch1-2 的八层模型中，`SessionLocal` 归入 Engine 层，此处为方便理解其独立职责而单独列出，可视为 Engine 层的子层次。

3. **Command 层** — `CommandContainer` 包装已编译的 `Prepared` 对象，提供 `query()` 和 `update()` 两个统一入口。`CommandList` 支持批量 SQL 的顺序执行。这一层屏蔽了不同 SQL 类型（SELECT、INSERT、UPDATE、DELETE）的执行差异，提供统一的命令执行接口。

4. **Engine 层** — 包含 `Select`、`Insert`、`Update`、`Delete` 等 `Prepared` 子类，负责实际的查询优化和执行。其中 `Select` 是最复杂的子类，它在 `preparePlan()` 阶段调用 `Optimizer` 生成最优执行计划，在 `queryWithoutCache()` 阶段驱动 `TableFilter` 的行迭代循环。

5. **Store 层** — 提供底层的持久化存储能力。`MVStore` 实现了基于多版本并发控制的存储引擎，`MVTable` 管理表的行数据，`Index` 接口定义了 B+ 树索引、哈希索引等多种索引结构的统一访问协议。这一层是 H2 高性能读写的基础。

各层之间的数据传递关系可以通过以下数据流图进一步理解：

```text
各层间数据传递与格式转换
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
**图 7-6: 各层间数据传递与格式转换**

该图补充了图 7-5 的静态结构视图，从动态数据流的角度展示了 SQL 请求在各层之间传递时的格式转换。在每个层边界上，数据的表示形式都发生了改变：从应用层的 SQL 文本，到 Session 层的 Command 对象，再到 Command 层的内部结果表示，最后到 Store 层的行数据。每一层都对其输入进行加工和转换，然后传递给下一层——这是典型的分层架构数据流模式。

**图 7-7: 两种 JDBC 语句的内部处理差异**

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

PreparedStatement 生命周期 (一次编译, 多次执行):
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
**图 7-66: Statement 与 PreparedStatement 生命周期对比**

上图展示了两种 JDBC 语句执行方式的本质差异，核心区别在于"解析与执行是否分离"：

Statement 的特点是**每次调用 executeQuery 都走完整的编译-执行流程**。每次请求中，H2 内核都要重新执行词法分析、语法分析、语义分析、查询优化和计划生成。即使多次发送完全相同的 SQL 文本，解析和优化阶段也会重复执行。对于 OLTP 场景中高频执行的查询（例如在循环中反复执行相同 SQL），Statement 模式的解析开销会显著影响系统吞吐量。

PreparedStatement 的核心优势在于**一次编译，多次执行**。在 `prepareStatement()` 阶段，内核完成所有的解析、优化和计划生成工作，生成 `CommandContainer` 对象，并由客户端持有该对象的引用（通过 JDBC 驱动封装在 `JdbcPreparedStatement` 中）。后续每次调用 `executeQuery()`，客户端仅需通过 `setXxx()` 方法绑定参数，然后直接触发已编译计划的执行。内核无需重新解析 SQL，也无需重新选择执行计划。

两者的性能差异随执行次数增加而放大：对于执行 N 次的查询，Statement 的解析开销约为 O(N)，而 PreparedStatement 约为 O(1)。这对于高并发 OLTP 系统来说，PreparedStatement 的收益非常显著。此外，PreparedStatement 天然防止 SQL 注入攻击，因为参数值在编译后作为数据安全地绑定到查询计划中，不会参与 SQL 文本拼接，从根源上消除了恶意 SQL 片段被解释为语法结构的可能性。

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

  N=1 时:  Statement   = PreparedStatement       (无差异)
  N=10 时: Statement   ≈ PreparedStatement × 2   (差 2 倍)
  N=100 时: Statement  ≈ PreparedStatement × 10  (差 10 倍)
  N=1000 时: Statement ≈ PreparedStatement × 100 (差 100 倍)
```
**图 7-8: 执行次数增长下的开销对比**

该图从执行时间构成的角度量化了两种模式的差异。Statement 在每次执行时都在解析阶段付出额外代价，该代价占总执行时间的 30%-60%。PreparedStatement 仅在第一次编译时付出解析代价，后续的执行仅包含实际查询开销。在循环执行或高频调用的 OLTP 场景中，PreparedStatement 的性能优势随执行次数线性增长——执行 N 次时，Statement 的开销约为 O(N×P)（P 为解析开销），而 PreparedStatement 仅为 O(P)。

### 7.1.5 Session 锁机制与并发控制
**图 7-9: H2 的 session 级锁竞争机制**

```text
线程 A (持有 Session 1)             线程 B (持有 Session 2)        线程 C (共享 Session 1)
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
**图 7-67: Session 锁机制与并发控制示意图**

H2 采用 session 级互斥锁来保证线程安全，这一设计在简单性和并发性之间做出了明确的取舍：

1. **锁的范围**：锁定粒度为单个 `SessionLocal` 实例。同一个 session 内的 SQL 执行是串行化的，但不同 session 之间的执行完全并行。这意味着如果应用使用连接池处理多个并发请求，每个请求使用不同的连接（即不同的 Session），则锁竞争几乎为零。

2. **锁的实现**：H2 使用 Java 的 `ReentrantLock`（位于 `SessionLocal.java` 的 `lock`/`unlock` 方法）。相比于 `synchronized` 关键字，`ReentrantLock` 提供了更灵活的锁操作，包括可中断的锁获取、超时尝试和公平性策略。

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

  没有可重入锁会怎样?
    ┌─────────────────────────────────────────────────────┐
    │  Subquery.getValue() 调用 query.query(0)            │
    │    → prepareCommand() → session.lock()              │
    │    → 同一个线程, 但锁已被自己持有!                  │
    │    → 不可重入锁: 死锁!                              │
    │    → ReentrantLock: 允许重入, 正常执行              │
    └─────────────────────────────────────────────────────┘
```
**图 7-10: 锁可重入性在子查询中的应用**

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

如图 7-5 所示，该方法是 SQL 编译的入口，其执行流程从加锁开始，到释放锁结束：

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
**图 7-11: prepareCommand 方法执行流程**

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
**图 7-12: 锁在 Session 方法调用链中的传递路径**

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
**图 7-13: prepareLocal 快慢路径对比**

如图 7-13 所示，缓存命中的快路径比完整编译的慢路径快 100-1000 倍。对于 OLTP 场景中重复执行的查询（如 `SELECT * FROM users WHERE id = ?`），缓存命中率通常超过 99%，这意味着绝大部分 `prepareLocal` 调用在微秒级别完成。

### 7.2.3 `Parser.prepareCommand(String sql)`

源码位置：`org/h2/command/Parser.java:485`

`Parser` 根据 SQL 的第一个关键字进行分发：

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
**图 7-14: Parser.prepareCommand SQL 关键字分发结构**

如图 7-14 所示，该图展示了 Parser 入口方法的分发逻辑。`prepareCommand` 读取 SQL 的第一个 token 后，根据其类型将控制权转交给对应的 parse 方法。DML 类语句（SELECT/INSERT/UPDATE/DELETE/MERGE）和 DDL 类语句（CREATE/ALTER/DROP）分别由不同的 parse 方法族处理。这种基于关键字的分发模式是手写解析器的典型设计——每个 SQL 关键字对应一个解析方法，方法之间通过关键字识别进行切换，无需解析器生成器的辅助。对于多条语句（以 `;` 分隔），则使用 `CommandList` 包装为复合命令。

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
**图 7-15: SQL 解析三阶段管道**

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
**图 7-16: parseQuery 内部方法调用与对象创建时序**

如图 7-16 所示，该图详细展开了解析器在 parseQuery 方法内部的调用链和对象创建过程。每个 parse 方法都对应 SQL 语法中的一个产生式：parseSelect 对应 SELECT 列表，parseFrom 对应 FROM 子句，parseWhere 对应 WHERE 条件。每个 parse 方法内部调用 read* 系列方法来消费 Token 流并创建相应的表达式对象。这种"一个方法对应一个语法规则"的设计使得代码结构与 SQL 语法高度对应，便于维护和扩展。


### 7.2.6 递归下降解析器调用栈

**图 7-17: 解析器内部的方法调用链**

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
**图 7-77: 递归下降解析器调用栈结构**

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
**图 7-18: 递归下降解析方法嵌套深度**

如图 7-18 所示，该图从调用栈深度的角度展示了递归下降解析的层次结构。最大嵌套深度通常不超过 5 层——即使在处理 JOIN 和嵌套条件时，递归深度也是有限的。这种浅层递归保证了调用栈不会溢出，同时也说明了解析器的控制流是扁平的（相比于表达式求值的深层递归）。每个解析方法的职责边界清晰，方法的返回即为对应语法元素的解析完成时刻。

**图 7-19: 词法分析器 Token 流生成过程**

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
**图 7-78: 词法分析器 Tokenizer 工作流程**

如图 7-78 所示，词法分析是 SQL 解析的第一阶段，其核心任务是将字符序列转换为有意义的 Token 序列。H2 的词法分析器嵌入在 `Parser.java` 中，没有独立的 Tokenizer 类，这种设计在减少对象创建开销的同时，也使得解析器的代码组织更紧凑。

Token 的类型包括：
- **关键字**：如 SELECT、FROM、WHERE、AND、OR、ORDER 等 SQL 保留字。H2 不区分大小写，关键字表使用小写存储，比较时统一转换
- **标识符**：表名、列名、别名等用户定义名称。支持双引号引用的带特殊字符的标识符
- **数值常量**：整数和浮点数字面值
- **字符串常量**：单引号包围的字符串字面值
- **运算符**：=、>、<、>=、<=、<> 等比较运算符，以及 +、-、*、/ 等算术运算符
- **分隔符**：. (点号)、, (逗号)、( (左括号)、) (右括号)、; (分号)
- **参数占位符**：? 表示参数化查询中的占位符

词法分析器使用一个位置指针遍历 SQL 字符数组，通过 `nextToken()` 方法逐个读取 Token。该方法不进行回溯（backtracking），保证了 O(n) 的时间复杂度。在识别标识符时，分析器会查关键字表以区分保留字和普通标识符——这一设计使得关键字可以作为列名使用（除非在特定语法位置有歧义）。

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
**图 7-20: Token 生成示例 — 从 SQL 文本到 Token 流**

```text
如图 7-20 所示，该图以逐字符方式展示了词法分析器如何处理一条具体的 SQL 语句。位置指针从 0 开始顺序扫描字符，对每个字符判断其类型（字母→标识符/关键字、数字→数值、运算符→运算符等），然后累积字符直到无法继续匹配为止。关键字识别的关键步骤是查表：累积的字符串先与关键字表比较，匹配则返回关键字类型，不匹配则作为普通标识符。这种设计使得 `SELECT` 作为关键字返回 `KEYWORD_SELECT`，而 `test` 这样的表名则返回 `IDENTIFIER`。整个扫描过程是 O(n) 的，每个字符只被读取一次。
```

### 7.2.7 抽象语法树构建过程
**图 7-21: 从 SQL 文本到 AST 的完整构建过程**

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
**图 7-79: 抽象语法树（AST）构建过程**

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
**图 7-22: SQL 到执行计划的对象变换链**

如图 7-22 所示，该图展示了 SQL 到执行结果的完整变换链。每个变换步骤都对数据进行加工和转换：Parser 将文本转换为 AST，语义分析为 AST 绑定列引用和类型信息，优化器选择连接顺序和索引，执行器驱动内核迭代数据行。每个步骤的输入输出数据结构和规模都不同。值得注意的是，优化阶段是唯一可能改变数据结构的步骤——它会重排 TableFilter 的顺序。这种"先优化后执行"的策略是关系数据库的通用设计模式。

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
**图 7-23: 查询缓存结构及在 Session 中的位置**

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
**图 7-24: SmallLRUCache 驱逐过程示例 (maxSize=4)**

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
**图 7-25: 缓存失效的三种场景**

如图 7-25 所示，三种失效场景的严重程度不同：DDL 导致的全部缓存清空影响最大，但发生频率最低（仅在表结构变更时）。非缓存语句和命令不可复用是局部影响，只涉及当前语句。失效策略的设计目标是正确性高于性能——宁可多失效也不能返回过时的查询计划。

```text
DDL 缓存失效跨 Session 传播流程
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
**图 7-26: DDL 缓存失效跨 Session 传播流程**

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

  各分支的耗时占比:
  ┌──────────────────┬────────────┬────────────┬─────────────┐
  │ 分支              │ 耗时       │ 占比       │ 优化建议     │
  ├──────────────────┼────────────┼────────────┼─────────────┤
  │ 缓存命中          │ 0.01ms     │ <1%        │ 无 (已达最优) │
  │ 缓存未命中 + 解析  │ 1-10ms    │ 99%+       │ 扩大缓存     │
  │ 缓存禁用          │ 1-10ms    │ 99%+       │ 启用缓存     │
  └──────────────────┴────────────┴────────────┴─────────────┘
```
**图 7-27: prepareLocal 三路分支决策与耗时占比**

该图将 `prepareLocal` 的缓存逻辑总结为三个清晰的分支。对于 OLTP 系统，目标是将路径 2（缓存命中）的占比提升到 99% 以上——这意味着只有首次执行和 DDL 后需要走完整的解析路径。路径 1（缓存禁用）通常出现在测试环境或特殊的低内存场景中，生产环境应确保 `queryCacheSize > 0`。

### 7.3.4 SmallLRUCache 内部结构

**图 7-28: SmallLRUCache 内部数据结构**

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

插入新 cmd4 (缓存已满, 淘汰尾部 cmd3):
   ┌──────┐    ┌──────┐    ┌──────┐
   │cmd4  │◄──►│cmd2  │◄──►│cmd1  │
   └──────┘    └──────┘    └──────┘
      ↑                       ↑
    head                    tail  (cmd3 已被移除)
```
**图 7-80: SmallLRUCache 内部双向链表结构**

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

  SmallLRUCache 操作时间复杂度:
  ┌────────────┬──────────┬──────────────────────┐
  │ 操作        │ 复杂度   │ 说明                  │
  ├────────────┼──────────┼──────────────────────┤
  │ get(key)   │ O(1)     │ 哈希查找 + 链表移动   │
  │ put(key,v) │ O(1)     │ 哈希插入 + 链表操作   │
  │ remove(k)  │ O(1)     │ 哈希删除 + 链表操作   │
  │ clear()    │ O(n)     │ 清空哈希表和链表       │
  └────────────┴──────────┴──────────────────────┘
```
**图 7-29: SmallLRUCache get/put 操作流程**

该图展示了 SmallLRUCache 的 get 和 put 方法在哈希表和双向链表上的完整操作步骤。get 操作首先通过哈希表进行 O(1) 查找，如果找到则将对应节点移动到链表头部（更新 LRU 顺序）并返回值。put 操作需要处理命中更新和未命中插入两种子情况：命中时直接更新值并移动到头部，未命中时需要先检查容量，必要时淘汰链表尾部的最近最少使用节点，然后创建新节点插入头部。所有操作的时间复杂度均为 O(1)，这是 LRU 缓存的经典实现方式。

### 7.3.5 缓存完整决策流程

**图 7-30: `prepareLocal()` 中的缓存逻辑展开为完整的决策流程**

```text
prepareLocal(sql)
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
**图 7-68: 缓存完整决策流程图**

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

检查点 5: command.isCacheable()?
  ├── 检查目的: 此类型语句是否可缓存
  ├── 不可缓存类型: FOR UPDATE, 非确定性函数, 临时表
  ├── 通过条件: 语句类型支持缓存
  └── 不通过: 不入缓存, 下次仍完整解析
```
**图 7-31: 缓存决策关键检查点总结**

该图将图 7-30 的完整决策流程提炼为五个关键检查点。这些检查点按执行顺序排列，任何一个检查点不通过都可能改变决策路径（跳过缓存、清空缓存或不入缓存）。理解每个检查点的目的和通过条件，有助于诊断与缓存相关的性能问题——例如，如果查询频繁重新编译，检查 modificationMetaID 是否因 DDL 频繁变化、或 isCacheable() 是否返回 false。

### 7.3.6 DDL 缓存失效传播机制

**图 7-32: DDL 操作从执行到缓存失效的完整传播路径**

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

  Session B                SessionLocal B                Database
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
**图 7-69: DDL 操作传播与缓存失效时序**

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

  缓存命中场景 (无 DDL 时):
    Session 版本: 3
    Database 版本: 3
    版本匹配 → 缓存可用 → 直接返回已编译计划
```
**图 7-33: modificationMetaID 版本号生命周期**

该图展示了全局版本号在 DDL 缓存失效中的完整生命周期。每次 DDL 操作都会递增 `Database` 层的全局版本号，而每个 Session 的缓存只在自己下一次查询时进行版本比对。版本比对是一个 O(1) 的长整型比较，其开销可以忽略不计。这种"版本号令牌"的设计是一种典型的乐观并发控制策略——假设大多数时候没有 DDL 发生，因此版本比对总是通过，缓存始终有效。仅在 DDL 发生时（罕见事件），才需要执行缓存清空的开销。

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
Command 接口方法实现: CommandContainer
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
**图 7-34: CommandContainer 结构**

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
**图 7-35: CommandContainer.query() 执行阶段**

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
**图 7-36: update 与 query 执行路径对比**

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
**图 7-37: ResultWithGeneratedKeys 内部结构**

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

  重新编译与首次编译的对比:
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
**图 7-38: 重新编译七步流程**

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
Command 执行框架方法调用全景
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
**图 7-39: Command 执行框架方法调用全景**

该图展示了从 JDBC 层到 Command 层再到 Prepared 层的完整调用链。`CommandContainer` 作为 JDBC 层和 Engine 层之间的桥梁，其 `query()` 和 `update()` 两个方法屏蔽了底层 Prepared 子类的复杂分发逻辑，为上层提供了统一的执行入口。


### 7.4.6 Command 类继承层次

**图 7-40: Command 框架中各个类的继承与组合关系**

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

  SessionLocal.queryCache: SmallLRUCache<String, Command>
       │
       └── 缓存键: SQL 文本 → 缓存值: CommandContainer
```
**图 7-70: Command 类继承层次结构图**

该图揭示了 H2 Command 框架的完整类型层次。设计上采用**组合优于继承**的原则：`CommandContainer` 通过组合方式持有一个 `Prepared` 对象，将"命令执行"与"查询计划"两个概念解耦：

- **Command 接口**定义了命令执行器的通用协议，包括 `query()`（返回结果集）、`update()`（返回影响行数）、`canReuse()`（是否可复用）、`isCacheable()`（是否可缓存）
- **CommandContainer** 是单语句的默认实现，内部委托给 `Prepared` 对象执行实际逻辑
- **CommandList** 支持多条 SQL 的批量执行，内部持有 `Command` 数组，按顺序逐一执行
- **Prepared 抽象基类**是所有 SQL 语句类型的共同祖先，定义了查询计划的生命周期方法。每个子类（Select、Insert、Update、Delete）对应一种 SQL 语句类型
- **Select** 是最复杂的子类，拥有独立的 `preparePlan()` 和 `Optimizer` 调用

这种设计使得 JBDC 层只需要依赖 `Command` 接口，无需关心具体的 SQL 类型。`CommandContainer` 负责按需重新编译，`Prepared` 负责实际的查询执行，各司其职。

Command 接口和 Prepared 抽象类的核心方法矩阵展示了不同类型语句的方法实现差异：

```text
Command/Prepared 方法实现矩阵
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
**图 7-41: Command/Prepared 方法实现矩阵**

该矩阵展示了 Command 接口和 Prepared 抽象类及其子类的方法实现情况。`query()` 在 Select 中有实质性实现而其它子类为空，`update()` 只在 Insert/Update/Delete 中有实现。这种设计使得 `CommandContainer` 可以统一调用 `query()` 和 `update()`，而具体的执行逻辑由多态分发到对应的 Prepared 子类。Select 是唯一拥有 `preparePlan()` 和 `queryWithoutCache()` 方法的子类，体现了 SELECT 查询在优化和执行上的复杂性远高于 DML 语句。

### 7.4.7 CommandContainer 内部执行路径

**图 7-42: `CommandContainer.query()` 的完整内部执行路径**

```text
CommandContainer.query(maxRows)
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
**图 7-71: CommandContainer.query() 完整内部执行路径**

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

  性能分析要点:
  ┌──────────────────────────────────────────────────────┐
  │  总执行时间 ≈ 阶段 4 耗时 (99%+)                      │
  │  阶段 4 的优化是查询性能调优的核心战场                  │
  │  → 索引优化: 减少 TableFilter.next() 调用次数         │
  │  → 查询改写: 减少中间结果行数                          │
  │  → 列选择优化: 减少表达式求值次数                      │
  └──────────────────────────────────────────────────────┘
```
**图 7-43: query() 五阶段耗时与风险分析**

该图从性能和风险两个维度分析了 `query()` 方法的五个执行阶段。`prepared.query(maxRows)` 是绝对的热点阶段，占总执行时间的 99% 以上。前三个阶段（recompileIfRequired + start + checkParameters）的开销即使全部加起来也不到 0.1ms，在大多数查询中可忽略不计。因此，查询性能调优的核心应该聚焦于阶段 4——减少 `TableFilter.next()` 的迭代次数和单次迭代的开销。

### 7.4.8 重新编译决策树

**图 7-44: `recompileIfRequired()` 的完整决策逻辑**

```text
recompileIfRequired() 决策树
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
**图 7-72: recompileIfRequired 重新编译决策树**

重新编译机制是 H2 保证执行计划时效性的关键设计。当表结构发生变化（例如新增索引、修改列定义）后，原有的执行计划可能不再最优甚至不再有效。`recompileIfRequired()` 通过惰性检测机制——在执行查询前检查元数据版本号——确保始终使用与当前表结构一致的最新计划。与查询缓存不同，重新编译发生在 `CommandContainer` 级别，生成新的 `Prepared` 实例后通过原子替换方式更新内部引用，保证了线程安全性。

重新编译需要同时满足的触发条件及其与查询缓存的交互关系如下：

```text
重新编译触发条件与缓存交互
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
**图 7-45: 重新编译触发条件与缓存交互**

该图展示了重新编译的触发条件及其与查询缓存的交互关系。重新编译的触发条件是 `needRecompile()` 返回 true，这发生在 `alwaysRecompile` 标志设置或元数据版本号变化时。重新编译在 `CommandContainer` 层执行，与 Session 层的查询缓存是两个独立的机制——查询缓存避免的是"相同 SQL 的重复编译"，而重新编译处理的是"表结构变更后的计划更新"。两者配合工作：DDL 发生后，查询缓存被整体清空，下次查询时重新编译生成新计划，然后新计划又可以被缓存起来供后续复用。

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
1. **准备阶段**: JDBC → `prepareLocal` → Parser 解析 → `Select.init()` 扩展列 → `Select.prepare()` → `preparePlan()` → `Optimizer.optimize()` → 选取最优 TableFilter 链
2. **执行阶段**: JDBC → `CommandContainer.query()` → `Select.queryWithoutCache()` → `TableFilter.next()` 循环读取 → 表达式求值 → 输出结果行
```

### 7.5.1 全链路执行阶段泳道图

**图 7-46: 上述序列图按组件划分为五个泳道，展示每个阶段的参与者和数据流动**

```text
泳道图: SQL 全链路执行阶段划分
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
  │   B+ 树     │◄──────────────────────────────┘
  │   索引      │    cursor.find() / cursor.next()
  └─────────────┘
```
**图 7-73: SQL 全链路执行阶段泳道图**

该图将 SQL 执行的全生命周期按组件划分为五个泳道（JDBC 层、Session 层、Parser/Command 层、Optimizer/TableFilter 层、Store 层），并按照时间维度分为"准备阶段"和"执行阶段"两个大的时间窗口：

1. **准备阶段**从 `prepareCommand` 开始，依次经过 Session 层的缓存检查、Parser 的词法语法分析、Select 的语义准备（列展开、类型解析），最后调用 Optimizer 生成执行计划。这一阶段的产出物是已编译的 `CommandContainer`（内含 `Select` 对象和最优的 `TableFilter` 链）。

2. **执行阶段**从 `command.executeQuery()` 开始，进入 `CommandContainer.query()` → `prepared.query()` → `Select.queryWithoutCache()` 的调用链，最终由 `topTableFilter.next()` 驱动 Store 层的游标迭代，逐行读取数据并进行过滤和表达式求值。

从泳道图可以进一步抽象出各组件在准备阶段和执行阶段中扮演的角色类型：

```text
组件在准备/执行阶段中的角色定位
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
**图 7-47: 组件在准备/执行阶段中的角色定位**

该表总结了各组件在两个阶段中扮演的角色。Parser 和 Optimizer 是纯"准备阶段"组件——它们在 SQL 编译后不再参与执行。Store 层是纯"执行阶段"组件——它不关心 SQL 的解析和优化，只按索引游标的指令提供数据。Session 层和 Select 是跨阶段组件：Session 层在准备阶段负责缓存管理，在执行阶段负责锁控制；Select 在准备阶段负责语义分析，在执行阶段负责驱动行迭代。

### 7.5.2 准备阶段与执行阶段数据流

**图 7-48: 准备阶段和执行阶段之间的数据依赖关系**

```text
准备阶段产物                              执行阶段消费
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
**图 7-74: 准备阶段与执行阶段数据依赖关系**

该图揭示了准备阶段的产物如何被执行阶段消费。每个在准备阶段确定的数据结构——列表达式、表访问顺序、索引选择、过滤条件树——在执行阶段都有明确的消费位置。这种分离使两个阶段可以独立优化：准备阶段专注于选择最优计划（代价较高），执行阶段专注于高效迭代（性能敏感）。

从数据依赖关系可以进一步总结出准备阶段各个产物在执行阶段的对应消费位置和消费方式：

```text
准备产物 → 执行消费映射表
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
  │                         │ 游标初始化 + 遍历        │ B+ 树遍历     │
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
  │                         │ B+ 树定位                │ 位运算检查     │
  └──────────────────────────┴──────────────────────────┴────────────────┘
```
**图 7-49: 准备产物到执行消费映射表**

该表为图 7-48 的数据流图提供了补充说明，详细列出了每个准备阶段产物在执行阶段的具体消费位置和消费方式。这张映射表有助于理解"准备阶段做了什么，执行阶段用了什么"：例如，`planItem.index` 在执行阶段用于 `cursor.find()` 初始化游标，`masks` 数组用于索引条件匹配，`joinCondition` 用于行过滤。如果某个准备产物在执行阶段没有被消费（或者消费方式异常），就意味着可能产生了不必要的计算开销。

### 7.5.3 执行阶段性能热点

从执行阶段的角度看，SQL 执行时间主要分布在以下热点路径中：

1. **TableFilter.next() 循环** — 这是最内层的循环体，调用频率最高。对于百万行级别的全表扫描，`next()` 方法的每次调用都在毫秒以下，但累计时间占比最大
2. **cursor.find() / cursor.next()** — 索引游标的 B+ 树遍历，涉及磁盘 I/O 或缓存访问
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
  │  │  单次开销: ~1-10μs (B+ 树页访问)                      │  │
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

  典型查询的热点分布 (全表扫描 100 万行, SELECT 5 列):
  ┌────────────────────┬───────────┬──────────┬───────────────┐
  │ 热点               │ 相对占比  │ 绝对耗时 │ 优化优先级    │
  ├────────────────────┼───────────┼──────────┼───────────────┤
  │ cursor.next()      │ 50-70%    │ 5 秒     │ ★★★ 最高     │
  │ TableFilter.next() │ 5-10%     │ 0.5 秒   │ ★★            │
  │ isOk(filter)       │ 10-20%    │ 1 秒     │ ★★            │
  │ getValue()         │ 10-20%    │ 1 秒     │ ★             │
  └────────────────────┴───────────┴──────────┴───────────────┘
```
**图 7-50: 执行阶段性能热点分布**

该图量化了执行阶段四个热点的调用次数、单次开销和总耗时。`cursor.next()` 的 B+ 树页访问是绝对的热点——占全表扫描总耗时的 50-70%。索引覆盖扫描可以将热点 4（getValue）的开销降低到接近零，因为不需要回表读取数据页。性能调优的优先级排序是：先减少 `N`（扫描行数，通过索引过滤），再减少单次开销（通过覆盖扫描）。

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
**图 7-51: 表达式多态分发机制详解**

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
ExpressionColumn.getValue() 执行路径
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
**图 7-52: ExpressionColumn.getValue() 执行路径**
```text
ColumnResolver 绑定链 — 从列名到值的完整链路
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
**图 7-53: ColumnResolver 绑定链 — 从列名到值的完整链路**

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
Comparison.getValue() 数据流
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
**图 7-54: Comparison.getValue() 数据流**
```text
三值逻辑 (NULL 处理) 在比较中的传播路径
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

**图 7-55: 三值逻辑 (NULL 处理) 在比较中的传播路径**

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

**图 7-56: 短路求值真值表**

如图 7-56 所示，该真值表完整描述了 `ConditionAndOr` 短路求值的所有可能路径。关键观察：当 `left.isTrue()` 返回 false 时（对于 AND 操作），right 不被求值；当 `left.isTrue()` 返回 true 时（对于 OR 操作），right 不被求值。注意三值逻辑（TRUE/FALSE/NULL）的处理：NULL 在 `isTrue()` 检查中返回 false，因此对于 AND 操作，left=NULL 会导致短路并返回 NULL；对于 OR 操作，left=NULL 也会导致短路。这是因为 `NULL AND x` 和 `NULL OR x` 的结果可能为 NULL（取决于 x），但短路求值的语义是确定的——左值为 NULL 时，最终结果由右值决定，因此不能短路。

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
**图 7-57: Subquery.getValue() 递归执行过程**

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
**图 7-58: 表达式求值三阶段**

如图 7-58 所示，该图将 `fetchNextRow()` 中的表达式求值活动划分为三个按顺序执行的阶段。阶段 1 在游标定位时执行，产生索引的起始/结束位置；阶段 2 在每行读取后执行，决定行是否被过滤条件接纳；阶段 3 在被接纳的行上执行，计算 SELECT 列表中的每个列值。理解这三个阶段有助于定位查询性能问题：如果过滤条件求值占比过高，说明索引过滤不足，大量行在阶段 2 被过滤掉；如果输出列求值占比过高，意味着 SELECT 列太多或求值开销大。

### 7.6.7 Expression 类继承层次结构

**图 7-59: Expression 类体系全貌**

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
**图 7-81: Expression 类继承层次结构图**

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
**图 7-60: Expression 子类求值特征对比**

如图 7-60 所示，各子类的求值特征差异决定了查询优化的方向：`Subquery` 和 `ConditionIn` 是最昂贵的表达式类型，应尽可能避免在 WHERE 条件中使用子查询；`ExpressionColumn` 的求值开销虽然低，但调用频次极高（每行每列各一次），应通过减少 SELECT 列数来优化。

### 7.6.8 表达式树递归求值过程

**图 7-61: 对一条复杂 WHERE 条件进行递归求值时的完整过程**

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

求值过程 (从左到右, AND 短路):
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

**图 7-75: 表达式树递归求值过程**

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

  求值路径特点:
    ├── 叶子节点: ExpressionColumn / ValueExpression → 获取原始值
    ├── 中间节点: Comparison → 对子节点求值后执行比较
    ├── 分支节点: ConditionAndOr → 短路控制
    └── 根节点: 返回最终布尔结果
```
**图 7-62: 表达式树深度优先遍历求值**

该图将表达式树的递归求值过程抽象为深度优先遍历。求值从树的叶子节点开始（获取列值和常量），逐层向上执行比较和逻辑运算，最终在根节点得到布尔结果。注意 `ConditionAndOr(OR)` 在步骤 6 得到 FALSE 后没有立即短路——因为子树的结构已经决定了它需要在步骤 7-9 继续求值右子树。短路实际发生在 `ConditionAndOr.getValue()` 方法内部，即步骤 10 检查左值 FALSE 后仍需评估右值（OR 操作左 FALSE 时不短路）。

### 7.6.9 短路求值与类型转换机制

**图 7-63: 短路求值的控制流和数据类型转换在表达式求值中的作用**

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

Comparison.getValue(session)
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
**图 7-76: 短路求值与类型转换机制**

该图揭示了表达式求值中的两个关键技术细节：

**短路求值**是 `ConditionAndOr` 的核心性能优化。对于 AND 操作，如果左表达式已为 FALSE，整个 AND 表达式的结果已确定为 FALSE，无需对右表达式求值。对于 OR 操作，如果左表达式已为 TRUE，整个 OR 表达式的结果已确定为 TRUE，同样无需对右表达式求值。短路求值不仅节省了计算资源，更重要的是可以避免因右表达式的副作用（如除零错误、空指针）导致的运行时异常。例如 `WHERE a > 0 AND 1/a > 2` 在 a=0 时，左侧 a>0 为 FALSE，右侧 1/a 不会被求值，避免了除零异常。

**类型转换**是 `Comparison` 在比较不同数据类型时必须执行的步骤。H2 的 `DataType.compareWithConversion()` 方法实现了隐式类型转换规则：整数与浮点数比较时，整数提升为浮点数；字符串与数字比较时，字符串被解析为数字；DATE 与 TIMESTAMP 比较时，DATE 被提升为 TIMESTAMP。这些转换规则确保了跨类型比较的正确性，但也会带来额外的计算开销——在性能敏感的场景下，显式类型转换（如 `CAST(col AS TYPE)`）通常比隐式转换更高效。

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

  性能建议:
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
**图 7-64: DataType.compareWithConversion 类型转换矩阵**

该图总结了 H2 隐式类型转换的所有组合。核心原则：比较操作中类型不匹配时，优先级较低的类型向优先级较高的类型转换（数值优先级：INTEGER < BIGINT < DECIMAL < DOUBLE）。字符串和数字的比较是隐式转换中最常见的场景——字符串 '123' 被解析为数字 123 后进行比较。需要注意的是，对索引列应用隐式类型转换可能导致索引失效：例如 `WHERE varchar_col = 123` 实际执行的是 `WHERE CAST(varchar_col AS INTEGER) = 123`，CAST 函数阻止了索引的使用。最佳实践是保证查询中的字面量类型与列定义类型一致，避免隐式转换。

## 7.7 本章小结

第 7 章完整追踪了一条 SQL 语句从 JDBC 接口到存储层的全链路执行流程。核心内容包括：JDBC 入口层的两种语句执行方式（Statement 与 PreparedStatement）及其性能差异、Session 层的缓存与锁机制、Parser 递归下降解析的三阶段管道（词法分析、语法分析、命令包装）、Command 框架的统一执行抽象、以及表达式求值的多态分发与短路求值策略。本章的流程分析为第 8 章深入查询优化器提供了执行层面的基础铺垫——理解 SQL 如何被解析和执行，是理解查询优化器如何选择最优执行计划的前提。

---

# 第8章 查询优化器深度解读

> **本章导读**: 本章深入分析 H2 查询优化器的实现，涵盖基于代价的优化框架、连接顺序选择、索引条件评估、表达式预处理和子查询优化等核心主题。
> **前置知识**: 第7章《SQL 执行全流程》§7.1（SELECT 执行流程）；第6章§6.8（Optimizer 算法基础）；第4章§4.1（Command 层）
> **章节要点**:
> - 理解查询优化的基本框架和代价估算模型
> - 掌握连接顺序选择的算法和策略
> - 熟悉索引条件下推和表达式优化的实现
> - 了解子查询和视图的优化处理

> 查询优化器是 SQL 执行的核心组件，其涉及的基础算法（B-Tree 索引、代价估算等）详见第6章《H2 数据库核心算法分析》。本章共 100 张插图，信息量较大，建议分段阅读。

本章结构：8.1 节概述 Optimizer 框架，8.2 节分析连接顺序优化，8.3 节推导演绎代价模型，8.4 节说明索引选择策略，8.5 节讲解 TableFilter 代价估算，8.6 节展示优化实现原语，8.7 节展示完整优化流程图，8.8 节总结全章要点。

---

## 8.1 Optimizer 类架构

### 8.1.1 类定义

源码位置：`org/h2/command/query/Optimizer.java`

```java
class Optimizer {
    private static final int MAX_BRUTE_FORCE_FILTERS = 7;
    private static final int MAX_BRUTE_FORCE = 2000;
    private static final int MAX_GENETIC = 500;

    private final TableFilter[] filters;
    private final Expression condition;
    private final SessionLocal session;
    private Plan bestPlan;
    private TableFilter topFilter;
    private double cost;
}
```

如图 7-61 所示，核心常量：
- `MAX_BRUTE_FORCE_FILTERS = 7` — 暴力枚举的最大表数
- `MAX_BRUTE_FORCE = 2000` — 混合策略的枚举上限
- `MAX_GENETIC = 500` — 遗传算法最大迭代次数

Optimizer 类的核心字段及其在优化过程中的作用：

```text
Optimizer 核心字段与用途
                        │
  ┌────────────────────┬────────────────────────────────────────────┐
  │ 字段                │ 用途                                       │
  ├────────────────────┼────────────────────────────────────────────┤
  │ filters            │ 输入: 参与连接的所有 TableFilter           │
  │                    │ 来源: Select.preparePlan() 传入             │
  │                    │ 长度: 即连接的表数量                        │
  ├────────────────────┼────────────────────────────────────────────┤
  │ condition          │ 输入: 完整的 WHERE 条件表达式              │
  │                    │ 用于: Plan.calculateCost() 中的条件可求值检查│
  ├────────────────────┼────────────────────────────────────────────┤
  │ session            │ 输入: 会话上下文                           │
  │                    │ 用于: 索引选择的会话级统计信息              │
  ├────────────────────┼────────────────────────────────────────────┤
  │ bestPlan           │ 输出: 当前找到的最优 Plan                 │
  │                    │ 初始: null (首次 testPlan 后更新)          │
  ├────────────────────┼────────────────────────────────────────────┤
  │ topFilter          │ 输出: 最优计划的头节点 TableFilter         │
  │                    │ 最终: Select.topTableFilter = this         │
  ├────────────────────┼────────────────────────────────────────────┤
  │ cost               │ 输出: 最优计划的代价                       │
  │                    │ 初始: -1 (表示尚未找到可行计划)            │
  │                    │ 用于: canStop() 的提前终止判断             │
  └────────────────────┴────────────────────────────────────────────┘
```
**图 8-1: Optimizer 核心字段与用途**
```text
Optimizer 字段的运行时关系
                        │
  Select.preparePlan()
    │
    ├── new Optimizer(filters, condition, session)
    │     │
    │     ├── this.filters = filters        ← TableFilter[]
    │     │     (长度 n = 连接的表数量)     ← 关键输入
    │     │
    │     ├── this.condition = condition    ← Expression (WHERE 条件)
    │     │
    │     └── this.session = session        ← SessionLocal (统计信息)
    │
    ├── optimizer.optimize()
    │     │
    │     ├── calculateBestPlan()
    │     │     │
    │     │     ├── 策略选择（根据 filters.length)
    │     │     ├── 生成最佳排列
    │     │     └── cost = 最终的最优代价 (或 -1 如无可行计划)
    │     │
    │     ├── bestPlan = 当前最优 Plan 对象
    │     │     (比较每个 testPlan 返回的 Plan)
    │     │
    │     └── topFilter = bestPlan.filters[0]
    │
    └── 输出: topFilter (已链接所有其他 TableFilter)
          └── 每个 TableFilter 已通过 setPlanItem() 设置索引
```
**图 8-2: Optimizer 字段的运行时关系**

### 8.1.2 构造与入口

```java
Optimizer(TableFilter[] filters, Expression condition, SessionLocal session)
```

如图 8-1 所示，在 `Select.preparePlan()` 中创建并调用：

```java
// Select.java:1359
Optimizer optimizer = new Optimizer(topArray, condition, session);
optimizer.optimize(parse, isSelectCommand);
topTableFilter = optimizer.getTopFilter();
```

Optimizer 对象从创建到产出最优计划的完整生命周期：

```text
Optimizer 对象生命周期
                        │
  创建: new Optimizer(filters, condition, session)
    │
    ├── 初始化: 接收 TableFilter 数组和 WHERE 条件
    ├── 状态: bestPlan=null, cost=-1, topFilter=null
    │
    ▼
  优化: optimizer.optimize(parse, isSelectCommand)
    │
    ├── parse=true? (视图解析阶段)
    │     └── YES → calculateFakePlan()
    │                  └── 创建简单的 fake plan (不执行真实代价计算)
    │
    ├── parse=false? (真实查询优化)
    │     └── YES → calculateBestPlan(isSelectCommand)
    │                  └── 选择策略 → 生成候选 Plan → 选最优
    │
    └── 后处理:
          ├── bestPlan.removeUnusableIndexConditions()
          ├── 设置 topFilter 链
          └── 设置每个 TableFilter 的 PlanItem
    │
    ▼
  结果获取: optimizer.getTopFilter()
    │
    └── 返回: topFilter (已设置 PlanItem 和 join 链)
          └── Select.topTableFilter = topFilter
```
**图 8-3: Optimizer 对象生命周期**

如图 8-3 所示，Optimizer 对象的生命周期包括三个阶段：创建（接收输入参数）、优化（选择策略并生成最优计划）、结果获取（返回配置完成的 TableFilter 链）。`parse` 参数区分了两种模式：视图解析阶段仅生成占位计划，真实查询优化阶段才执行代价计算和策略选择。

```text
构造方法与 Select.preparePlan() 的交互
                        │
  Select.preparePlan()
    │
    ├── 1. 创建 Optimizer
    │     new Optimizer(filters, condition, session)
    │     │
    │     └── filters 来源:
    │           ├── FROM user u               → TableFilter(u)
    │           ├── JOIN orders o             → TableFilter(o)
    │           └── JOIN order_items i        → TableFilter(i)
    │
    ├── 2. 调用 optimize(true)  ← 初次优化
    │     │
    │     └── 内部: calculateBestPlan(true)
    │           ├── 评估每个候选排列
    │           └── 找到最优 Plan
    │
    ├── 3. 获取结果
    │     topTableFilter = optimizer.getTopFilter()
    │
    └── 4. 设置链接
          topFilter.addJoin(optimizer.getTopFilter())
          (将优化后的计划挂载到 Select 的 topFilter 下)
```
**图 8-4: Optimizer 构造与 Select.preparePlan() 的交互**

### 8.1.3 `optimize()` 主方法

如图 8-4 所示，源码位置：`Optimizer.java:237`

```java
void optimize(boolean parse, boolean isSelectCommand) {
    if (parse) {
        calculateFakePlan();          // 视图解析阶段，无需真实代价计算
    } else {
        calculateBestPlan(isSelectCommand); // 选择最优计划
        bestPlan.removeUnusableIndexConditions(); // 清理无用索引条件
    }
    // 将最优计划的 TableFilter 链连接起来
    TableFilter[] f2 = bestPlan.getFilters();
    topFilter = f2[0];
    for (int i = 0; i < f2.length - 1; i++) {
        f2[i].addJoin(f2[i + 1], false, null);
    }
    // 为每个 TableFilter 设置 PlanItem（索引 + 代价）
    for (TableFilter f : f2) {
        PlanItem item = bestPlan.getItem(f);
        f.setPlanItem(item);
    }
}
```

`optimize()` 方法包含两个主要阶段——计划生成和结果组装：

```text
optimize() 两阶段流程
                        │
  ┌──────────────────────────────────────────────────────────────┐
  │  阶段 1: 计划生成                                              │
  │                                                               │
  │  parse?                                                       │
  │    │                                                          │
  │    ├── YES: calculateFakePlan()                               │
  │    │     └── 生成占位计划 (视图解析时使用)                     │
  │    │         bestPlan = new Plan(...)                         │
  │    │                                                          │
  │    └── NO: calculateBestPlan()                                │
  │          └── 选择连接顺序 + 索引 + 计算代价                    │
  │              bestPlan = 代价最低的 Plan                        │
  │                                                               │
  │  产出: bestPlan (包含 filters 排序 + planItems)              │
  └────────────────────────────┬─────────────────────────────────┘
                               │
  ┌────────────────────────────┴─────────────────────────────────┐
  │  阶段 2: 结果组装                                              │
  │                                                               │
  │  步骤 A: 移除无用索引条件                                      │
  │    bestPlan.removeUnusableIndexConditions()                   │
  │    └── 清理 start/end 条件中恒假的索引条件                     │
  │                                                               │
  │  步骤 B: 建立 TableFilter 链                                  │
  │    topFilter = bestPlan.filters[0]                            │
  │    for i = 0 to n-2:                                          │
  │      filters[i].addJoin(filters[i+1], false, null)            │
  │    └── 形成: topFilter → T2 → T3 → ... → Tn                  │
  │                                                               │
  │  步骤 C: 设置 PlanItem                                        │
  │    for each f in filters:                                     │
  │      f.setPlanItem(bestPlan.getItem(f))                       │
  │    └── 每个 TableFilter 获得选中的索引 + 代价 + 掩码           │
  │                                                               │
  │  产出: topTableFilter (完全配置, 可供执行)                   │
  └──────────────────────────────────────────────────────────────┘
```
**图 8-5: optimize() 两阶段流程**

如图 8-5 所示，优化过程分为计划生成和结果组装两个阶段。计划生成阶段根据 `parse` 标志决定是否执行真实代价计算；结果组装阶段将最优计划转换为可执行的 TableFilter 链结构。这种分离使得优化器的核心逻辑（代价计算 + 策略选择）与后处理逻辑（链组装 + 属性设置）保持独立，便于测试和调试。

```text
optimize() 方法的 parse 参数影响
                        │
  optimize(boolean parse)
    │
    ├── parse = true (视图解析阶段)
    │     │
    │     ├── calculateBestPlan(true)
    │     │     ├── testPlan(list, true)
    │     │     │     └── Plan.calculateCost(session, ..., true)
    │     │     │           └── isSelectCommand = true
    │     │     │                → 跳过更新操作的代价检查
    │     │     └── 正常选择最优计划
    │     │
    │     └── 用途: 创建视图或子查询时的初始化
    │           只需生成基础计划结构, 不涉及实际执行
    │
    ├── parse = false (真实查询优化)
    │     │
    │     ├── calculateBestPlan(false)
    │     │     └── testPlan(list, false)
    │     │           └── Plan.calculateCost(session, ..., false)
    │     │                 └── isSelectCommand = false
    │     │                      → 考虑更新操作 (如 SELECT FOR UPDATE)
    │     │
    │     └── 后续操作:
    │           ├── bestPlan.removeUnusableIndexConditions()
    │           ├── linkJoin(topFilter, ...)
    │           └── 设置 PlanItem
    │
    └── getTopFilter() → 两种模式都返回配置好的 topFilter
```
**图 8-6: optimize() parse 参数的作用**

### 8.1.4 三种策略的调度

```java
// Optimizer.java:78
private void calculateBestPlan(boolean isSelectCommand) {
    cost = -1;
    if (filters.length == 1) {
        testPlan(filters, isSelectCommand);          // 单表，直接评估
    } else {
        startNs = System.nanoTime();
        if (filters.length <= MAX_BRUTE_FORCE_FILTERS) {
            calculateBruteForceAll(isSelectCommand);  // ≤7表: 暴力枚举
        } else {
            calculateBruteForceSome(isSelectCommand); // 8+表: 混合策略
            random = new Random(0);
            calculateGenetic(isSelectCommand);        // 遗传算法
        }
    }
}
```

如图 8-6 所示，决策树：

```text
TableFilter 数量
    │
    ├── 1 个 ─→ testPlan()：单表直接评估
    │
    ├── 2-7 个 ─→ calculateBruteForceAll()
    │      枚举所有排列 O(n!)
    │      2! = 2, 3! = 6, ..., 7! = 5040
    │
    └── 8+ 个 ─→ calculateBruteForceSome()
    │      暴力枚举前 m 个表 + 贪心选剩余
    │      +
    │      calculateGenetic()
    │      随机变异迭代 500 轮
    │
    └── 任一策略可被 canStop() 提前终止
```

每种策略的适用场景和性能特征可以通过以下对比表快速理解：

```text
三种策略对比
                        │
  ┌──────────────────┬────────────┬─────────────┬──────────────────────┐
  │ 策略              │ 适用表数   │ 时间复杂度  │ 计划质量              │
  ├──────────────────┼────────────┼─────────────┼──────────────────────┤
  │ testPlan (单表)   │ 1          │ O(1)        │ 最优 (只有一种选择)   │
  ├──────────────────┼────────────┼─────────────┼──────────────────────┤
  │ BruteForceAll    │ 2-7        │ O(n!)       │ 最优 (全覆盖)        │
  │                  │            │ 2!=2 ~ 7!=5040                    │
  ├──────────────────┼────────────┼─────────────┼──────────────────────┤
  │ BruteForceSome   │ 8+         │ O(P(n,m))   │ 接近最优             │
  │ + Genetic        │            │ + O(500)    │ 通常是前 90%         │
  └──────────────────┴────────────┴─────────────┴──────────────────────┘
```
**图 8-7: 三种策略对比**
```text
calculateBestPlan() 完整决策流程
                        │
  calculateBestPlan(isSelectCommand)
    │
    ├── cost = -1   (重置)
    │
    ├── filters.length == 1?
    │     └── YES → testPlan(filters, isSelectCommand)
    │
    ├── filters.length <= MAX_BRUTE_FORCE_FILTERS (7)?
    │     └── YES → calculateBruteForceAll(isSelectCommand)
    │           ├── Permutations.create(filters, list)
    │           └── for x: !canStop(x) && p.next()
    │                 └── testPlan(list, isSelectCommand)
    │
    └── filters.length >= 8?
          │
          ├── calculateBruteForceSome(isSelectCommand)
          │     └── 暴力前 m 个 + 贪心剩余
          │
          └── calculateGenetic(isSelectCommand)
                └── 500 轮随机变异
          │
          └── 保留两种策略中代价最低的 Plan
    │
    └── 结果: bestPlan (或 null 如无可行计划)
          └── cost = bestPlan.calculateCost() (最优代价)
```
**图 8-8: calculateBestPlan() 完整决策流程**

### 8.1.5 提前终止机制

```java
private boolean canStop(int x) {
    return (x & 127) == 0
            && cost >= 0
            && System.nanoTime() - startNs > cost * 100_000L;
}
```

如图 8-7 所示，条件：每 128 次迭代检查一次，当已找到可行计划（cost >= 0）且耗时超过 `cost * 100μs` 时停止。这意味着如果当前最优代价为 1000，超过 100ms 后就停止搜索。

`canStop()` 的检查频次和停止条件可以通过以下判定流程理解：

```text
canStop() 判定流程与效果
                        │
  每 128 次迭代调用一次 canStop(x)
    │
    ├── (x & 127) == 0?
    │     ├── NO → 跳过, 继续搜索
    │     └── YES → 进入条件判断
    │
    ├── cost >= 0?
    │     ├── NO → 尚无可行计划, 继续搜索
    │     └── YES → 已找到至少一个可行计划
    │
    └── elapsed > cost * 100μs?
          ├── NO → 搜索时间未超阈值, 继续搜索
          └── YES → 停止搜索
                │
                └── 提前终止, 使用当前最优计划

  不同代价下的停止阈值:
  ┌──────────────┬────────────┬────────────────────────────────┐
  │ 最优代价     │ 停止阈值   │ 行为                           │
  ├──────────────┼────────────┼────────────────────────────────┤
  │ 1            │ 100μs     │ 非常容易触发 (几乎立即停止)     │
  │ 10           │ 1ms       │ 容易触发                       │
  │ 100          │ 10ms      │ 可能触发                       │
  │ 1000         │ 100ms     │ 较难触发 (搜索全部排列)         │
  │ 10000        │ 1s        │ 极难触发 (搜索全部排列)         │
  └──────────────┴────────────┴────────────────────────────────┘
```
**图 8-9: canStop() 判定流程与效果**

如图 8-9 所示，提前终止机制的核心思想是"收益递减"：如果在当前最优计划的代价对应的搜索时间内没有找到更好的计划，那么继续搜索也不太可能找到显著更优的解。`cost * 100μs` 这个公式的含义是：搜索时间与当前最优计划的代价成正比——代价越高的查询（通常是全表扫描类型的查询），搜索空间越大，但优化器愿意为之付出的搜索时间也越多。

```text
canStop() 在实际搜索中的表现分析
                        │
  6 表连接: 6! = 720 种排列, 不同代价下的终止行为
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  发现代价为 10 的计划                                               │
  │    ├── threshold = 10 × 100μs = 1ms                                │
  │    ├── 搜索约 240 种排列后停止 (第 1/3 处)                         │
  │    └── 如果前 240 种排列已包含最优, 则无质量损失                   │
  │                                                                     │
  │  发现代价为 50 的计划                                               │
  │    ├── threshold = 50 × 100μs = 5ms                                │
  │    ├── 搜索约 600 种排列后停止 (接近全部)                           │
  │    └── 基本完成全部 720 种排列的评估                                │
  │                                                                     │
  │  发现代价为 100 的计划                                              │
  │    ├── threshold = 100 × 100μs = 10ms                              │
  │    ├── 10ms 远超评估全部 720 种排列所需时间                         │
  │    └── 搜索全部 720 种排列, canStop() 不会被触发                   │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  优点:
    ├── 高选择性查询: 快速找到好计划, 立即停止, 节省 CPU
    ├── 低选择性查询: 搜索全部排列, 不会过早停止
    └── 自动适应: 无需人工配置阈值参数
                        │
  潜在问题:
    └── 如果好计划出现在搜索空间的末尾 (例如第 700 种排列)
         但前 240 种排列中就找到了代价为 10 的计划
         则搜索会在 1ms 后停止, 错过末尾更好的计划
         → 但在实际中, 搜索空间是随机分布的, 好计划在各处均可能出现
```
**图 8-10: canStop() 在实际搜索中的表现分析**

### 8.1.6 Optimizer 整体架构与对象关系

**图 8-11: Optimizer 及其核心协作对象的完整关系网络**

```text
Optimizer 核心对象关系图:

┌──────────────────────────────────────────────────────────────────────────┐
│  Select.preparePlan()                                                    │
│    │                                                                     │
│    ├── new Optimizer(filters, condition, session)                        │
│    │      │                                                              │
│    │      │  Optimizer 对象                                              │
│    │      │  ┌────────────────────────────────────────────────────────┐  │
│    │      │  │  fields:                                              │  │
│    │      │  │    filters: TableFilter[]     ← 参与连接的所有表      │  │
│    │      │  │    condition: Expression       ← WHERE 条件           │  │
│    │      │  │    bestPlan: Plan              ← 当前最优计划         │  │
│    │      │  │    topFilter: TableFilter      ← 最优计划的头节点     │  │
│    │      │  │    cost: double                ← 最优计划代价         │  │
│    │      │  │                                 │                      │  │
│    │      │  │  constants:                    │                      │  │
│    │      │  │    MAX_BRUTE_FORCE_FILTERS = 7 │                      │  │
│    │      │  │    MAX_BRUTE_FORCE        = 2000│                      │  │
│    │      │  │    MAX_GENETIC            = 500│                      │  │
│    │      │  └────────────────────────────────┼──────────────────────┘  │
│    │      │                                   │                         │
│    │      │  Optimizer.optimize()             │                         │
│    │      │    │                              │                         │
│    │      │    ├── calculateBestPlan()        │                         │
│    │      │    │    │                         │                         │
│    │      │    │    ├── 单表: testPlan()      │                         │
│    │      │    │    ├── ≤7 表: bruteForceAll()│                         │
│    │      │    │    └── ≥8 表: bruteForceSome │                         │
│    │      │    │              + genetic()     │                         │
│    │      │    │                              │                         │
│    │      │    ├── 设置 topFilter 链          │                         │
│    │      │    └── 设置 planItem              │                         │
│    │      │                                   │                         │
│    │      └───────────────────────────────────┘                         │
│    │                                                                     │
│    ├── optimizer.getTopFilter()  ← 获取最优计划头节点                   │
│    │                                                                     │
│    └── topTableFilter = optimizer.getTopFilter()                         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                          │
                          │  Plan 对象
                          │  ┌──────────────────────────────────────────┐
                          │  │  filters: TableFilter[]    ← 排列顺序   │
                          │  │  planItems: HashMap        ← 索引选择   │
                          │  │  allConditions: Expression[] ← 条件数组 │
                          │  │                                           │
                          │  │  calculateCost(session) → double         │
                          │  │    │                                      │
                          │  │    └── 迭代所有 TableFilter:             │
                          │  │          for each f in allFilters:       │
                          │  │            item = f.getBestPlanItem()    │
                          │  │            cost += cost * item.cost      │
                          │  │                                           │
                          │  └──────────────────────────────────────────┘
                          │
                          │  PlanItem 对象 (对应每个 TableFilter)
                          │  ┌──────────────────────────────────────────┐
                          │  │  cost: double           ← 估计代价      │
                          │  │  index: Index           ← 选中的索引    │
                          │  │  masks: int[]           ← 索引条件掩码  │
                          │  │  joinPlan: PlanItem     ← 连接子计划    │
                          │  │  nestedJoinPlan: PlanItem ← 嵌套连接    │
                          │  └──────────────────────────────────────────┘

调用流程:
  Select.preparePlan()
    → new Optimizer(filters, condition, session)
    → optimizer.optimize()
      → calculateBestPlan()
        → testPlan(list) 或 calculateBruteForceAll() 或 calculateGenetic()
          → new Plan(list, len, condition)
            → plan.calculateCost(session, ...)
              → tableFilter.getBestPlanItem(...)
                → table.getBestPlanItem(...)
                  → index.getCost(...)
```
**图 8-82: Optimizer 整体架构与对象关系图**

该图展示了 Optimizer 核心的三个对象层次及其协作关系：

```text
Optimizer 运行时协作时序
                        │
  Select.preparePlan()
    │
    ├── 1. 构造 Optimizer 对象
    │      new Optimizer(filters, condition, session)
    │      │
    │      ├── filters[]: 参与连接的所有 TableFilter
    │      ├── condition: 完整 WHERE 表达式树
    │      └── session: 会话上下文 (含统计信息)
    │
    ├── 2. optimizer.optimize()  →  calculateBestPlan()
    │      │
    │      │  策略选择 (根据表数量):
    │      │    ├── 单表  → testPlan()
    │      │    │     └── Plan.calculateCost() → PlanItem 填充
    │      │    │
    │      │    ├── 2-7表 → calculateBruteForceAll()
    │      │    │     └── Permutations 生成 n! 种排列
    │      │    │         └── 每排列: new Plan → calculateCost()
    │      │    │
    │      │    └── ≥8表 → 混合 + 遗传算法
    │      │          ├── calculateBruteForceSome()
    │      │          └── calculateGenetic()
    │      │
    │      └── 结果: bestPlan (代价最低)
    │
    ├── 3. 计划落地
    │      ├── topFilter = bestPlan.filters[0]
    │      ├── linkJoin(topFilter, bestPlan.filters[1..n])
    │      └── 设置每个 TableFilter 的 PlanItem
    │
    └── 4. 执行阶段
           └── topFilter.next() 循环
                 ├── cursor.find() → 索引定位
                 ├── cursor.next() → 行迭代
                 └── join.next() → 内表嵌套循环
```
**图 8-12: Optimizer 运行时协作时序**

1. **Optimizer** 是策略调度器，持有完整的 TableFilter 数组和 WHERE 条件，负责根据表数量选择合适的连接顺序策略。通过 `calculateBestPlan()` 方法生成候选 Plan，并在所有 Plan 中选择代价最低的。最终通过 `getTopFilter()` 返回最优计划的头节点。

2. **Plan** 是一个候选执行计划，包含表的访问顺序（filters 数组）和每个表对应的 PlanItem。`calculateCost()` 方法计算该计划的总体代价，采用复合乘法公式逐步累加。无效计划（join condition 引用了尚未出现的表）的代价为无穷大。

3. **PlanItem** 是 Plan 的组成部分，为每个 TableFilter 记录选中的索引、估计代价和索引条件掩码。多个 PlanItem 通过 `joinPlan` 和 `nestedJoinPlan` 字段描述连接关系。

### 8.1.7 三种策略协作流程

**图 8-13: 三种策略在 `calculateBestPlan()` 中的协作关系**

```text
calculateBestPlan() 三种策略协作概览
  │
  ├── 输入: filters[] (长度 n)
  │         condition (WHERE 条件)
  │         session (会话上下文)
  │
  ├── 步骤 1: 判断 n 值
  │     │
  │     ├── n == 1:
  │     │     testPlan(filters)           ← 单表, 直接评估
  │     │     (无排列组合, 仅需选择索引)
  │     │
  │     ├── 2 <= n <= 7:
  │     │     calculateBruteForceAll()    ← 暴力枚举
  │     │     枚举 n! 种排列
  │     │     每排列: testPlan(list)
  │     │     时间复杂度: O(n!)
  │     │
  │     └── n >= 8:
  │           │
  │           ├── calculateBruteForceSome()  ← 混合策略
  │           │     暴力枚举前 m 个位置
  │           │     贪心填充剩余位置
  │           │     m = getMaxBruteForceFilters(n)
  │           │     时间复杂度: O(P(n,m) × n²)
  │           │
  │           └── calculateGenetic()         ← 遗传算法
  │                 随机初始化排列
  │                 最多 500 轮迭代
  │                 每轮: 交换两表或完全洗牌
  │                 保留最优解
  │
  ├── 步骤 2: 汇总结果
  │     bestPlan = 代价最低的 Plan
  │     topFilter = bestPlan.filters[0]    ← 头节点
  │     linkJoin(topFilter, ...)           ← 连接 TableFilter 链
  │     for each f in bestPlan.filters:
  │         f.setPlanItem(bestPlan.getItem(f))  ← 设置索引选择
  │
  └── 输出: topTableFilter (已设置索引和 PlanItem)
```
**图 8-83: 三种策略协作流程图**

该图将三种策略视为一个统一的调度框架。`calculateBestPlan()` 方法的职责不是自己搜索，而是根据输入特征（表数量）选择合适的搜索策略，并将最终结果组装为一致的输出格式（topFilter + PlanItems）。这种策略模式（Strategy Pattern）的设计使得新增搜索策略非常容易——只需要实现一个新的策略方法，并在 `calculateBestPlan()` 中添加对应的调度条件。

```text
三种策略特性对比
                        │
  ┌────────────────────────────────────────────────────────────────────────┐
  │  维度            暴力枚举             混合策略             遗传算法    │
  ├────────────────────────────────────────────────────────────────────────┤
  │  适用表数        ≤7                   ≥8                  ≥8          │
  │  方法名          bruteForceAll()      bruteForceSome()    genetic()   │
  │  搜索方式        完全枚举             部分枚举+贪心        随机变异     │
  │  完备性          100%                 部分完备             不完备      │
  │  时间复杂度      O(n!)               O(P(n,m)×n²)        O(500)      │
  │  空间复杂度      O(n)                O(n)                O(n)        │
  │  计划质量        全局最优             近似最优             近似最优    │
  │  可提前终止      支持 (canStop)       支持 (canStop)       支持       │
  ├────────────────────────────────────────────────────────────────────────┤
  │                                                                        │
  │  阈值控制:                                                              │
  │    MAX_BRUTE_FORCE_FILTERS = 7   → 暴力枚举的最大表数                   │
  │    MAX_BRUTE_FORCE        = 2000 → 混合策略的最大评估次数               │
  │    MAX_GENETIC            = 500  → 遗传算法的最大迭代轮数               │
  │                                                                        │
  │  选择逻辑:                                                              │
  │    表数 1   → 直接评估, 无排列组合                                      │
  │    表数 2-7 → 暴力枚举全部排列                                          │
  │    表数 ≥8  → 同时运行混合 + 遗传, 取最优                              │
  └────────────────────────────────────────────────────────────────────────┘
```
**图 8-14: 三种策略特性对比表**

### 8.1.8 提前终止机制决策树

**图 8-15: `canStop()` 方法的完整决策过程及其对搜索行为的影响**

```text
canStop(x) 决策树                     x = 迭代次数
                                         │
  canStop(x)                             │
    return (x & 127) == 0               ├── 每 128 次迭代检查一次?
         && cost >= 0                   │     │
         && System.nanoTime()           │     ├── NO → 继续搜索
           - startNs > cost * 100_000L; │     │
                                         │     └── YES → 继续检查
                                         │           │
                                         ▼           ▼
                                    ┌────────────────────────────┐
                                    │ (x & 127) == 0 条件        │
                                    │ 仅当 x 是 128 的倍数时成立  │
                                    │ x=0, 128, 256, 384, ...    │
                                    └────────────┬───────────────┘
                                                 │
                                    ┌────────────▼───────────────┐
                                    │ cost >= 0?                 │
                                    │ (是否已有可行计划)          │
                                    │                            │
                                    │ YES → 继续检查耗时条件     │
                                    │ NO  → 继续搜索             │
                                    └────────────┬───────────────┘
                                                 │
                                    ┌────────────▼───────────────┐
                                    │ 耗时 > cost * 100μs?       │
                                    │                            │
                                    │ elapsed = nanoTime - start │
                                    │ threshold = cost * 100_000 │
                                    │                            │
                                    │ YES → 停止搜索              │
                                    │ NO  → 继续搜索              │
                                    └────────────┬───────────────┘
                                                 │
                                                 ▼
                                            停止 / 继续

  canStop 对搜索的影响 (以 6 表连接为例):
    │
    ├── 6! = 720 种排列
    │
    ├── 假设 testPlan 发现一个代价为 50 的计划
    │     │
    │     ├── threshold = 50 × 100μs = 5ms
    │     ├── 如果搜索超过 5ms 即停止
    │     └── 在 5ms 内通常可完成 720 种排列的评估
    │
    ├── 假设 testPlan 发现一个代价为 500 的计划
    │     │
    │     ├── threshold = 500 × 100μs = 50ms
    │     ├── 50ms 远超评估 720 种排列所需时间
    │     └── 意味着: 搜索实际上不会提前停止
    │
    └── 结论: canStop 在低成本 (高选择性) 查询中更有效
              低成本 → 阈值低 → 容易触发停止
              高成本 → 阈值高 → 搜索到全部排列
```
**图 8-84: 提前终止机制决策树**

`canStop()` 是 H2 优化器的智能中止机制。其核心理念是：如果已经找到了足够好的计划，就不必浪费 CPU 时间来搜索所有排列。决策逻辑分为三个层次：

```text
canStop() 在不同查询类型中的效果对比
                        │
  查询类型 A: 高选择性 (等值条件, 主键查找)
    │
    WHERE id = 100       ← 主键等值
    │
    ├── 找到的 Plan:
    │     cost = 1 (主键等值查找)
    │
    ├── 停止阈值:
    │     threshold = 1 × 100μs = 100μs
    │
    ├── 实际行为:
    │     首次迭代 (x=0) 调用 canStop(0)
    │     (0 & 127) == 0 → YES
    │     cost >= 0      → YES (cost=1)
    │     elapsed > 100μs? → 几乎立即满足
    │
    └── 结果: 在几个微秒内停止, 几乎不搜索排列
                        │
  查询类型 B: 中等选择性 (范围条件)
    │
    WHERE status = 'ACTIVE'   ← 二级索引, 估计 30% 行
    │
    ├── 找到的 Plan:
    │     cost = 3000 (非唯一索引扫描)
    │
    ├── 停止阈值:
    │     threshold = 3000 × 100μs = 300ms
    │
    ├── 实际行为:
    │     可以评估相当多的排列后才停止
    │     对于 6 表连接 (720 排列), 通常可完成全部评估
    │     对于 8 表连接 (40320 排列), 会提前停止
    │
    └── 结果: 搜索充分, 找到接近最优的计划
                        │
  查询类型 C: 低选择性 (无过滤条件)
    │
    (无 WHERE)          ← 全表扫描
    │
    ├── 找到的 Plan:
    │     cost = 10000 (全表扫描)
    │
    ├── 停止阈值:
    │     threshold = 10000 × 100μs = 1s
    │
    ├── 实际行为:
    │     通常远超过暴力枚举或遗传算法的完成时间
    │     搜索完整轮次后才自然结束
    │
    └── 结果: 搜索全部排列, 不会提前终止
                        │
  总结:
    ┌────────────────────────────────────────────────────────────────┐
    │  查询类型        典型代价    阈值      搜索程度               │
    ├────────────────────────────────────────────────────────────────┤
    │  主键等值         1          100μs    几乎不搜索, 立即返回     │
    │  唯一索引等值     10         1ms      有限搜索                 │
    │  普通索引扫描     100-1000   10-100ms  搜索较充分              │
    │  全表扫描         10000+     1s+      搜索全部排列             │
    └────────────────────────────────────────────────────────────────┘
```
**图 8-16: canStop() 在不同查询类型中的效果对比**

1. **频率控制**：`(x & 127) == 0` 确保检查操作每 128 次迭代才执行一次，避免高频率的 `System.nanoTime()` 调用影响性能。

2. **可行性检查**：`cost >= 0` 确保至少已找到一个可行计划。如果在第 128 次迭代时尚未找到任何有效计划（所有候选计划均为无效），则继续搜索。

3. **收益/成本权衡**：`耗时 > cost * 100μs` 是核心的权衡条件。`cost` 是当前最优计划的估计代价，`100μs` 是"每代价单位愿意支付的搜索时间"。如果一个计划的代价为 100，则最多愿意花 10ms 来搜索更好的计划。当已用搜索时间超过这个阈值时，搜索提前终止。

这种机制在实际应用中表现良好：对于选择性高的查询（如主键等值查找），优化器很快找到低代价计划并提前终止；对于全表扫描型查询（代价高），优化器会搜索所有排列以确保找到最佳连接顺序。

---

## 8.2 三种连接顺序策略

### 8.2.1 暴力枚举 — `calculateBruteForceAll()`

源码位置：`Optimizer.java:107`

```java
private void calculateBruteForceAll(boolean isSelectCommand) {
    TableFilter[] list = new TableFilter[filters.length];
    Permutations<TableFilter> p = Permutations.create(filters, list);
    for (int x = 0; !canStop(x) && p.next(); x++) {
        testPlan(list, isSelectCommand);
    }
}
```

如图 8-11 所示，利用 `Permutations` 工具类生成所有排列，逐个评估代价。

排列数量：

| 表数 | 排列数 | 可行 |
|------|--------|------|
| 1    | 1      | 直接评估 |
| 2    | 2      | 暴力 |
| 3    | 6      | 暴力 |
| 4    | 24     | 暴力 |
| 5    | 120    | 暴力 |
| 6    | 720    | 暴力 |
| 7    | 5,040  | 暴力 |
| 8    | 40,320 | 混合 |

7! = 5040 仍在合理范围，8! = 40320 开始显著变慢，因此在 8 表及以上切换策略。

```text
calculateBruteForceAll() 执行流程
                        │
  输入: filters[] (n 个 TableFilter)
                        │
                        ▼
  1. 创建输出数组 list = new TableFilter[n]
                        │
                        ▼
  2. 创建排列生成器 p = Permutations.create(filters, list)
                        │
                        ▼
  3. 循环: for (x = 0; !canStop(x) && p.next(); x++)
                        │
     ┌──────────────────────────────────────────────────────┐
     │  每次迭代:                                            │
     │                                                      │
     │  步骤 A: p.next() 生成下一排列                        │
     │    ├── 第 1 次: [T1, T2, T3, T4]  (初始排列)         │
     │    ├── 第 2 次: [T1, T2, T4, T3]                     │
     │    ├── 第 3 次: [T1, T3, T2, T4]                     │
     │    ├── ...                                           │
     │    └── 第 n! 次: [T4, T3, T2, T1] (末排列)           │
     │                                                      │
     │  步骤 B: testPlan(list) 评估当前排列的代价           │
     │    ├── new Plan(list, n, condition)                  │
     │    ├── plan.calculateCost()                          │
     │    │     ├── 迭代所有 TableFilter                    │
     │    │     ├── 对每个表: getBestPlanItem + 代价计算     │
     │    │     └── 检测无效计划 (Infinity)                  │
     │    └── 更新 bestPlan (如果较低)                       │
     │                                                      │
     │  步骤 C: 检查 canStop(x)                             │
     │    ├── 每 128 次检查一次                              │
     │    ├── 耗时 > cost × 100μs?                         │
     │    └── 是 → 提前终止                                 │
     └──────────────────────────────────────────────────────┘
                        │
                        ▼
  输出: bestPlan (代价最低的执行计划)
       topFilter = bestPlan.filters[0]
```
**图 8-17: 暴力枚举执行流程图**
```text
排列生成迭代过程 — Permutations 内部状态变化
                        │
  输入: filters = [T1, T2, T3, T4]  (4 个 TableFilter)
                        │
  Permutations.create(filters, list) 初始化:
    ┌───────────────────────────────────────────────────────────┐
    │ 内部状态:                                                   │
    │   source = [T1, T2, T3, T4]  (原始顺序, 不修改)             │
    │   result = [T1, T2, T3, T4]  (输出数组, 首排列=原始)        │
    │   index  = [0, 0, 0, 0]      (控制排列生成的指针数组)        │
    └───────────────────────────────────────────────────────────┘
                        │
  每次 p.next() 调用:
                        │
    ┌─────────────────────────────────────────────────────────┐
    │ 迭代 1: result = [T1, T2, T3, T4]  index = [0,0,0,0]   │
    │   → testPlan([T1,T2,T3,T4])                             │
    │   → 交换 T3 ↔ T4                                        │
    │                                                         │
    │ 迭代 2: result = [T1, T2, T4, T3]  index = [0,0,1,0]   │
    │   → testPlan([T1,T2,T4,T3])                             │
    │   → 重置尾部, 交换 T2 ↔ T3                              │
    │                                                         │
    │ 迭代 3: result = [T1, T3, T2, T4]  index = [0,1,0,0]   │
    │   → testPlan([T1,T3,T2,T4])                             │
    │   → 交换 T2 ↔ T4                                        │
    │                                                         │
    │ 迭代 4: result = [T1, T3, T4, T2]  index = [0,1,1,0]   │
    │   → testPlan([T1,T3,T4,T2])                             │
    │   → ...                                                 │
    │                                                         │
    │ ...                                                     │
    │                                                         │
    │ 迭代 24: result = [T4, T3, T2, T1]  index = [0,0,0,0]  │
    │   → testPlan([T4,T3,T2,T1])                             │
    │   → p.next() 返回 false (遍历完成)                       │
    └─────────────────────────────────────────────────────────┘
                        │
  Permutations 算法特性:
    ├── 不重复: 每次 next() 生成字典序的下一个排列
    ├── 无额外内存: 在原数组上就地生成
    ├── 时间复杂度: O(n!) 次 next() 调用, 每次 O(1) 交换
    └── 提前停止: 可通过 canStop() 在任意迭代终止
```
**图 8-18: 排列生成迭代过程 — Permutations 内部状态变化**

### 8.2.2 混合策略 — `calculateBruteForceSome()`

源码位置：`Optimizer.java:115`

```java
private void calculateBruteForceSome(boolean isSelectCommand) {
    int bruteForce = getMaxBruteForceFilters(filters.length);
    TableFilter[] list = new TableFilter[filters.length];
    Permutations<TableFilter> p = Permutations.create(filters, list, bruteForce);
    for (int x = 0; !canStop(x) && p.next(); x++) {
        // 标记已使用的表
        for (TableFilter f : filters)
            f.setUsed(false);
        for (int i = 0; i < bruteForce; i++)
            list[i].setUsed(true);
        // 剩余位置用贪心算法填充
        for (int i = bruteForce; i < filters.length; i++) {
            double costPart = -1.0;
            int bestPart = -1;
            for (int j = 0; j < filters.length; j++) {
                if (!filters[j].isUsed()) {
                    list[i] = filters[j];
                    Plan part = new Plan(list, i + 1, condition);
                    double costNow = part.calculateCost(...);
                    if (costPart < 0 || costNow < costPart) {
                        costPart = costNow;
                        bestPart = j;
                    }
                }
            }
            filters[bestPart].setUsed(true);
            list[i] = filters[bestPart];
        }
        testPlan(list, isSelectCommand);
    }
}
```

如图 8-17 所示，算法描述：
1. 对前 `bruteForce` 个表暴力枚举所有排列
2. 对剩余位置，依次尝试每个未使用的表，选择当前代价最低的（贪心）

**`getMaxBruteForceFilters()` 计算**：

```java
private static int getMaxBruteForceFilters(int filterCount) {
    int i = 0, j = filterCount, total = filterCount;
    while (j > 0 && total * (j * (j - 1) / 2) < MAX_BRUTE_FORCE) {
        j--;
        total *= j;
        i++;
    }
    return i;
}
```

条件：`P(n, m) * C(n-m, 2) < 2000`，其中 `P(n, m)` 是前 m 个位置的排列数，`C(n-m, 2)` 是剩余位置的贪心组合数。

示例（10 表）：

| m | P(10, m) | C(10-m, 2) | 乘积 |
|---|----------|------------|------|
| 2 | 10×9=90  | C(8,2)=28  | 2520 → 超过 2000 |
| 1 | 10       | C(9,2)=36  | 360  → 可行 |

因此 `getMaxBruteForceFilters(10)` = 1，即暴力枚举第 1 个位置，贪心选其余 9 个。

```text
calculateBruteForceSome() 执行流程 (以 10 表为例)
                        │
  输入: filters[] (10 个 TableFilter)
                        │
                        ▼
  1. 计算暴力枚举位置数
     bruteForce = getMaxBruteForceFilters(10) = 1
                        │
                        ▼
  2. 创建排列生成器 (前 bruteForce 个位置)
     Permutations.create(filters, list, 1)
     → 生成 [T1], [T2], ..., [T10] 共 10 种前缀
                        │
                        ▼
  3. 外层循环: for each 排列前缀
                        │
     ┌─────────────────────────────────────────────────────┐
     │  示例: 当前前缀 [T5]                                 │
     │                                                     │
     │  3.1 标记已使用: T5.setUsed(true)                    │
     │                                                     │
     │  3.2 内层贪心循环 (填充位置 1..9):                   │
     │      for (i = 1; i < 10; i++)                       │
     │        bestCost = -1, bestPart = -1                 │
     │        for (j = 0; j < 10; j++)                     │
     │          if (!filters[j].isUsed())                   │
     │            list[i] = filters[j]                      │
     │            Plan part = new Plan(list, i+1, cond)    │
     │            costNow = part.calculateCost(...)         │
     │            if (bestCost < 0 || costNow < bestCost)   │
     │              bestCost = costNow                     │
     │              bestPart = j                           │
     │        filters[bestPart].setUsed(true)              │
     │        list[i] = filters[bestPart]                  │
     │                                                     │
     │  3.3 评估完整排列: testPlan(list, isSelectCommand)   │
     └─────────────────────────────────────────────────────┘
                        │
                        ▼
  4. 对所有前缀重复 → 取最优 Plan
                        │
  对比: 10! = 3,628,800  vs  混合策略 ≈ 450 次评估
  加速比: ≈ 8,064 倍
```
**图 8-19: 混合策略执行流程图**

### 8.2.3 遗传算法 — `calculateGenetic()`

如图 8-19 所示，源码位置：`Optimizer.java:153`

```java
private void calculateGenetic(boolean isSelectCommand) {
    TableFilter[] best = new TableFilter[filters.length];
    TableFilter[] list = new TableFilter[filters.length];
    for (int x = 0; x < MAX_GENETIC; x++) {
        if (canStop(x)) break;
        boolean generateRandom = (x & 127) == 0;
        if (!generateRandom) {
            System.arraycopy(best, 0, list, 0, filters.length);
            if (!shuffleTwo(list)) {
                generateRandom = true;  // 所有交换已尝试过
            }
        }
        if (generateRandom) {
            switched = new BitSet();
            System.arraycopy(filters, 0, best, 0, filters.length);
            shuffleAll(best);           // 全新随机排列
            System.arraycopy(best, 0, list, 0, filters.length);
        }
        if (testPlan(list, isSelectCommand)) {
            switched = new BitSet();
            System.arraycopy(list, 0, best, 0, filters.length);
        }
    }
}
```

算法特点：
- **迭代次数**: 最多 500 轮
- **变异方式**: 每 128 轮触发一次完全洗牌，其余轮次交换两个随机位置
- **保留最优**: 如果新计划优于当前最优，更新 `best` 数组
- **去重机制**: `shuffleTwo()` 使用 `switched` BitSet 记录已尝试的交换对，避免重复评估

```text
遗传算法 calculateGenetic() 决策流程
                        │
  进入循环: for (x = 0; x < 500; x++)
                        │
                        ▼
  ┌────────────────────────────────────────────┐
  │  canStop(x) ?   ← 提前终止检查              │
  │  ├── YES → break (退出循环)                 │
  │  └── NO  → 继续                            │
  └────────────────┬───────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────┐
  │  (x & 127) == 0 ?   ← 每 128 轮触发洗牌    │
  │  ├── YES → generateRandom = true           │
  │  │          shuffleAll(best) → 全新排列    │
  │  │          (探索: 跳出局部最优)            │
  │  │                                          │
  │  └── NO  → 复制 best 到 list               │
  │             shuffleTwo(list) → 交换两位置    │
  │             (利用: 在最优解附近微调)          │
  │            如果所有交换耗尽 → generateRandom │
  └────────────────┬───────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────┐
  │  generateRandom?                           │
  │  ├── YES → switched = new BitSet()         │
  │  │          shuffleAll(best)               │
  │  │          list = best (副本)              │
  │  │                                          │
  │  └── NO  → list 已就绪                      │
  └────────────────┬───────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────┐
  │  testPlan(list) ?   ← 评估代价             │
  │  │                                         │
  │  ├── 新计划优于最优?                        │
  │  │    ├── YES → 更新 best = list           │
  │  │    │          switched = new BitSet()   │
  │  │    └── NO  → 保持当前最优               │
  │  │                                         │
  │  └── 继续下一轮迭代                         │
  └────────────────────────────────────────────┘
                   │
                   ▼
  循环结束 → 返回 bestPlan (最优排列)
```
**图 8-20: 遗传算法决策流程图**
```text
遗传算法示例 (5 表):
  │
  初始: [T1, T2, T3, T4, T5]  (FROM 子句顺序)
  │
  迭代 1:  交换位置 2,4 → [T1, T4, T3, T2, T5]  代价 120  ← 保留
  迭代 2:  交换位置 1,3 → [T3, T4, T1, T2, T5]  代价 150
  迭代 3:  交换位置 0,2 → [T1, T4, T3, T2, T5]  代价 120  ← 恢复到最优
  ...
  迭代 128: 完全洗牌 → [T5, T2, T4, T1, T3]  代价 90  ← 新的最优
  ...
  迭代 500: 返回当前最优 [T5, T2, T4, T1, T3], 代价 90
```

### 8.2.4 策略选择总图

```text
calculateBestPlan()
  │
  ├─ filters.length == 1?
  │     └─ YES → testPlan(filters)
  │
  ├─ filters.length <= 7?
  │     └─ YES → calculateBruteForceAll()
  │              枚举 n! 种排列
  │              cost 低 → 耗时短
  │              cost 高 → canStop() 提前退出
  │
  └─ filters.length >= 8?
        │
        ├─ calculateBruteForceSome()
        │     前 m 个位置: 暴力枚举
        │     剩余位置: 贪心填充
        │     m 由 getMaxBruteForceFilters() 动态计算
        │
        └─ calculateGenetic()
              每 128 轮: 完全洗牌
              其余: 随机交换两表
              保留最优 plan
```

```text
策略选择场景示例
                        │
  场景 1: 单表查询
    SELECT * FROM users WHERE id = 1
    │
    └── filters.length = 1 → testPlan(filters)
          ├── 无排列组合
          └── 仅选择最佳索引 (主键 PK)
                        │
  场景 2: 3 表连接
    SELECT * FROM a JOIN b ON a.id = b.a_id
      JOIN c ON b.id = c.b_id
    │
    └── filters.length = 3 → calculateBruteForceAll()
          ├── 3! = 6 种排列
          ├── 评估全部排列
          └── 选择全局最优
                        │
  场景 3: 10 表连接
    SELECT * FROM t1 JOIN t2 ... JOIN t10
    │
    └── filters.length = 10 → 混合 + 遗传
          ├── calculateBruteForceSome()
          │     ├── bruteForce=1 (暴力第1个位置)
          │     └── 贪心填充剩余9个
          │
          └── calculateGenetic()
                ├── 500 轮随机变异
                └── 保留最优
          │
          └── 取两种策略中的最优 Plan
```
**图 8-21: 策略选择场景示例图**

### 8.2.5 暴力枚举排列生成可视化

**图 8-22: 以 4 表连接为例，`calculateBruteForceAll()` 生成和评估所有排列的过程**

```text
暴力枚举: 4 表 (T1, T2, T3, T4) 的所有排列
                     │
                     ▼
  Permutations.create(filters) 生成 4! = 24 种排列:
                     │
  排列  1: [T1, T2, T3, T4]  cost = 198  ← 初始排列 (FROM 顺序)
  排列  2: [T1, T2, T4, T3]  cost = 215
  排列  3: [T1, T3, T2, T4]  cost = 175
  排列  4: [T1, T3, T4, T2]  cost = 190
  排列  5: [T1, T4, T2, T3]  cost = 230
  排列  6: [T1, T4, T3, T2]  cost = 210
  排列  7: [T2, T1, T3, T4]  cost = 145  ← 更优
  排列  8: [T2, T1, T4, T3]  cost = 150
  排列  9: [T2, T3, T1, T4]  cost = 120  ← 当前最优
  排列 10: [T2, T3, T4, T1]  cost = 135
  排列 11: [T2, T4, T1, T3]  cost = 160
  排列 12: [T2, T4, T3, T1]  cost = 155
  排列 13: [T3, T1, T2, T4]  cost = 90   ← 最优! (保留)
  排列 14: [T3, T1, T4, T2]  cost = 105
  排列 15: [T3, T2, T1, T4]  cost = 95
  排列 16: [T3, T2, T4, T1]  cost = 100
  排列 17: [T3, T4, T1, T2]  cost = 115
  排列 18: [T3, T4, T2, T1]  cost = 110
  排列 19: [T4, T1, T2, T3]  cost = 250
  排列 20: [T4, T1, T3, T2]  cost = 240
  排列 21: [T4, T2, T1, T3]  cost = 235
  排列 22: [T4, T2, T3, T1]  cost = 225
  排列 23: [T4, T3, T1, T2]  cost = 205
  排列 24: [T4, T3, T2, T1]  cost = 220
                     │
                     ▼
  最优: [T3, T1, T2, T4], cost = 90
  选择 topFilter = T3
  链接: T3 → T1 → T2 → T4
```
**图 8-85: 暴力枚举排列生成可视化**

该图以 4 表连接为例，展示了暴力枚举的实际运行过程。关键观察：

1. **初始排列**是 SQL 中 FROM 子句的书写顺序。这通常是 DBA 或 ORM 框架指定的顺序，但不一定是最优的
2. **排列生成**使用 `Permutations` 工具类，这是一个高效的排列迭代器，每次调用 `next()` 生成下一个排列。排列的顺序是字典序的
3. **代价分布**呈现非均匀特征：T3 作为头表的排列普遍代价较低（90-115），而 T4 作为头表的排列代价较高（205-250）。这表明 T3 是最佳驱动表
4. **搜索效率**：24 种排列在微秒级别内可完成评估。随着表数增长，评估时间呈阶乘增长——7 表的 5040 种排列仍在合理范围（毫秒级），8 表的 40320 种排列开始显著变慢

```text
暴力枚举代价分布与搜索效率
                        │
  4 表连接: 24 种排列的代价分布
                        │
  代价范围:
    ┌── 最优 [T3, T1, T2, T4]  cost = 90
    │
    ├── 良好 (90-120):   排列 9, 10, 13, 14, 15, 16  (6 种)
    │                    以 T2 或 T3 为头表
    │
    ├── 中等 (145-198):  排列 1, 3, 4, 7, 8, 17, 18  (7 种)
    │                    以 T1 为头表或 T2 为头表
    │
    └── 较差 (205-250):  排列 2, 5, 6, 19, 20, 21, 22, 23, 24  (9 种)
                         以 T4 为头表
                        │
  代价分布特征:
    头表选择对总代价的影响:
      T3 作为头表: cost = 90-115 (平均 103)
      T2 作为头表: cost = 120-160 (平均 138)
      T1 作为头表: cost = 175-230 (平均 203)
      T4 作为头表: cost = 205-250 (平均 228)

    结论: 头表选择是影响总代价的最关键因素
          T3 最适合作为驱动表 (选择性最高)
                        │
  表数增长对搜索空间的影响:
                        │
    表数   排列数    暴力枚举时间 (估计)
     4       24      < 1μs
     5      120      ~5μs
     6      720      ~30μs
     7     5,040     ~200μs
     8     40,320    ~2ms     ← 开始显著
     9     362,880   ~15ms    ← 不可接受
    10    3,628,800  ~150ms   ← 必须使用混合/遗传
```
**图 8-23: 暴力枚举代价分布与搜索效率分析**
```text
头表选择对查询效率的影响 — 行传递量对比
                        │
  SQL: SELECT * FROM T1, T2, T3, T4
       WHERE T1.id = T2.ref_id
         AND T2.id = T3.ref_id
         AND T3.id = T4.ref_id
                        │
  假设各表行数: T1=100, T2=1000, T3=10000, T4=100000
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  最优头表 T1 (最小表):                                               │
  │                                                                     │
  │  步骤  ├── 扫描 T1  (100 行)                                        │
  │        │    └── 对每行, 通过索引查找 T2.ref_id → 平均 1 行          │
  │        │        总行: T1(100) × T2(1) = 100                         │
  │        ├── 对每对 (T1, T2), 通过索引查找 T3.ref_id → 平均 0.1 行    │
  │        │        总行: 100 × 0.1 = 10                                │
  │        └── 对每对 (T1, T2, T3), 通过索引查找 T4.ref_id → 平均 0.01行│
  │                 总行: 10 × 0.01 = 0.1                               │
  │  总中间行数: 100 + 10 + 0.1 ≈ 110                                   │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  最差头表 T4 (最大表):                                               │
  │                                                                     │
  │  步骤  ├── 扫描 T4  (100000 行)                                     │
  │        │    └── 对每行, 全表扫描 T3 (无索引可用) → 10000 行/次      │
  │        │        总行: 100000 × 10000 = 1e9                          │
  │        ├── 对每对 (T4, T3), 全表扫描 T2 → 1000 行/次                │
  │        │        总行: 1e9 × 1000 = 1e12                             │
  │        └── 对每对 (T4, T3, T2), 全表扫描 T1 → 100 行/次             │
  │                 总行: 1e12 × 100 = 1e14                              │
  │  总中间行数: 天文数字, 不可执行                                       │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  结论: 头表选择决定连接查询的可行性
    最优: 小表驱动大表, 中间结果持续减小
    最差: 大表驱动小表, 中间结果爆炸增长
```
**图 8-24: 头表选择对查询效率的影响 — 行传递量对比**

### 8.2.6 混合策略算法流程详图

**图 8-25: 以 10 表连接为例，混合策略 `calculateBruteForceSome()` 的执行过程**

```text
混合策略执行示例: 10 表连接
                        │
  getMaxBruteForceFilters(10) 计算:
    │
    ├── m=2: P(10,2)=90, C(8,2)=28, 90×28=2520 > 2000  → 太大
    └── m=1: P(10,1)=10, C(9,2)=36, 10×36=360 < 2000  → 可行
                        │
  bruteForce = 1  (暴力枚举 1 个位置的 10 种选择)
                        │
  ┌────────────────────────────────────────────────────────────┐
  │  外层循环: 暴力枚举第 1 个位置 (10 种)                      │
  │                                                            │
  │  内层循环: 贪心填充位置 2~10 (每次选当前最优)               │
  │                                                            │
  │  示例: 第 1 个位置固定为 T5                                 │
  │    │                                                       │
  │    └── 位置 2: 尝试 {T1, T2, T3, T4, T6, T7, T8, T9, T10} │
  │          T1 cost_part=50 → 最优, 选 T1                     │
  │                                                            │
  │      位置 3: 尝试 {T2, T3, T4, T6, T7, T8, T9, T10}       │
  │          T3 cost_part=30 → 最优, 选 T3                     │
  │                                                            │
  │      位置 4: 尝试 {T2, T4, T6, T7, T8, T9, T10}           │
  │          T7 cost_part=45 → 最优, 选 T7                     │
  │                                                            │
  │      ...                                                   │
  │                                                            │
  │      位置 10: 剩余最后一个表                                │
  │          cost_part = 最终的 Plan 总代价                     │
  │                                                            │
  │  testPlan([T5, T1, T3, T7, ..., 最后一个表])               │
  │                                                            │
  │  ← 重复 10 次 (每个表作为第 1 位置一次)                     │
  └────────────────────────────────────────────────────────────┘
                        │
  总评估次数: 10 次 (每次评估包含 9+8+...+1 = 45 次贪心选择)
  对比暴力枚举 10!: 10! = 3,628,800
  加速比: 3,628,800 / (10 × 45) ≈ 8,064 倍
```
**图 8-86: 混合策略算法流程详图**

混合策略是 H2 在处理 8 表以上连接时的关键技术，其核心思想是"部分暴力 + 剩余贪心"。`getMaxBruteForceFilters()` 方法动态计算有多少个位置值得暴力搜索——在 `MAX_BRUTE_FORCE = 2000` 的约束下，找到使 `P(n,m) × C(n-m, 2)` 不超过 2000 的最大 m 值。

对于 10 表连接，m=1 意味着暴力枚举第 1 个位置（10 种可能），剩余的 9 个位置用贪心算法填充。贪心算法的每一步都尝试所有未使用的表，选择使当前局部代价最低的表。这种贪心策略虽然不能保证全局最优，但在表数较多时能快速找到可接受的计划。

混合策略将评估次数从 10! ≈ 360 万次降低到约 450 次，加速比超过 8000 倍，而计划质量通常只比全局最优差 10-20%。

```text
暴力枚举 vs 混合策略搜索空间对比
                        │
  不同表数下的搜索空间 (评估次数):
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  表数    暴力枚举 (n!)     混合策略 (评估次数)    加速比          │
  ├────────────────────────────────────────────────────────────────────┤
  │   8      40,320            2,184                 18x              │
  │   9      362,880           756                   480x             │
  │  10      3,628,800         450                   8,064x           │
  │  11      39,916,800        396                   100,800x         │
  │  12      479,001,600       430                   1,113,958x       │
  │  13      6,227,020,800     400                   15,567,552x      │
  │  14      87,178,291,200    520                   167,650,560x     │
  └────────────────────────────────────────────────────────────────────┘
                        │
  关键分析:
    ├── 8 表: 暴力枚举仍可接受 (4 万次评估), 混合策略优势不大
    ├── 10 表: 暴力枚举 360 万次 vs 混合策略 450 次, 差异巨大
    ├── 12 表以上: 暴力枚举完全不可行, 混合策略保持 <500 次
    └── 混合策略的评估次数在表数增长时保持稳定 (约 400-500 次)
         这是因为 getMaxBruteForceFilters() 自动调整暴力位置数
```
**图 8-26: 暴力枚举 vs 混合策略搜索空间对比**

### 8.2.7 遗传算法进化过程可视化

**图 8-27: 遗传算法在搜索最优连接顺序时，解空间中的进化轨迹**

```text
遗传算法进化过程 (8 表连接, 500 轮迭代)
                        │
  初始: [T1, T2, T3, T4, T5, T6, T7, T8]  cost = 850
                        │
  迭代轮次  当前序列                       代价    备注
   ───────  ────────────────────────────  ─────   ──────────────────
      0     [T1, T2, T3, T4, T5, T6, T7, T8]  850  初始 (FROM 顺序)
      ↓
      1     [T1, T5, T3, T4, T2, T6, T7, T8]  820  交换 1↔4
      2     [T1, T5, T3, T4, T2, T6, T7, T8]  820  未改善, 保持最优
      3     [T5, T1, T3, T4, T2, T6, T7, T8]  760  交换 0↔1, 新最优
      ↓
      ...   (继续随机交换)
      ↓
     10     [T5, T1, T7, T4, T2, T6, T3, T8]  700  交换 2↔6
     15     [T5, T1, T7, T4, T2, T6, T3, T8]  700  未改善
     22     [T5, T1, T7, T3, T2, T6, T4, T8]  680  交换 3↔6
      ↓
    128     [T8, T3, T6, T1, T5, T2, T7, T4]  550  完全洗牌! 新最优
      ↓
    129     [T8, T3, T6, T1, T5, T2, T7, T4]  550  未改善
    135     [T8, T3, T6, T7, T5, T2, T1, T4]  530  交换 3↔6
      ↓
    256     [T3, T8, T5, T1, T2, T6, T4, T7]  480  完全洗牌! 新最优
      ↓
    300     [T3, T8, T5, T1, T2, T4, T6, T7]  475  交换 5↔6
      ↓
    384     [T1, T4, T6, T2, T5, T8, T3, T7]  420  完全洗牌! 新最优
      ↓
    420     [T1, T4, T6, T2, T5, T8, T3, T7]  420  未改善
    455     [T1, T4, T6, T5, T2, T8, T3, T7]  418  交换 3↔4
      ↓
    500     [T1, T4, T6, T5, T2, T8, T3, T7]  418  最终最优
                        │
                        ▼
  最终选择: [T1, T4, T6, T5, T2, T8, T3, T7], cost = 418
  对比初始: 从 850 降低到 418, 优化了 50.8%
  对比暴力: 8! = 40320 种排列, 遗传算法仅评估 500 种
           搜索效率: 500/40320 ≈ 1.24%
```
**图 8-87: 遗传算法进化过程可视化**

该图展示了遗传算法在 500 轮迭代中的进化轨迹。算法特点包括：

1. **探索与利用的平衡**：每 128 轮触发一次"完全洗牌"（全部随机化），对应算法中的"探索"阶段，帮助跳出局部最优解。其余轮次执行"随机交换两个位置"，对应"利用"阶段，在当前最优解附近微调。

2. **最优解保留**：`testPlan()` 方法返回 true 表示当前计划优于最优计划时，更新 `best` 数组。这意味着算法始终保持从初始到当前轮次遇到的最佳解。

3. **去重机制**：`shuffleTwo()` 使用 `switched` BitSet 记录已尝试的交换对。当所有可能的交换都已尝试过后，`shuffleTwo()` 返回 false，触发下一轮完全洗牌。这避免了重复评估相同的排列。

4. **收敛速度**：从进化轨迹可以看到，最初的 128 轮中代价快速下降（850 → 550），后续的完整洗牌周期性地将解拉出局部最优。到第 384 轮后，改进速度明显放缓，说明算法已接近收敛。

5. **效率对比**：对于 8 表连接，暴力枚举需要评估 40320 种排列，而遗传算法仅评估 500 种（1.24% 的搜索空间），通常能找到接近最优的解。

```text
遗传算法收敛速度与效果分析
                        │
  8 表连接: 暴力枚举 40320 种 vs 遗传算法 500 种
                        │
  代价收敛轨迹 (每 50 轮采样):
                        │
    轮次    当前最优代价    较初始改善    阶段说明
    ─────   ───────────   ──────────   ─────────────────
      0         850          0%        初始排列 (FROM 顺序)
     50         700         17.6%      快速下降阶段
    100         650         23.5%      探索+利用
    150         580         31.8%      第一次完全洗牌后改善
    200         550         35.3%      持续优化
    250         500         41.2%      第二次完全洗牌后改善
    300         475         44.1%      微调阶段
    350         450         47.1%      接近收敛
    400         420         50.6%      第三次完全洗牌后改善
    450         418         50.8%      收敛
    500         418         50.8%      最终最优
                        │
  收敛特征分析:
    ├── 阶段 1 (0-128 轮): 快速下降
    │     代价从 850 降至 550, 降幅 35%
    │     通过局部交换快速找到较优解
    │
    ├── 阶段 2 (128-384 轮): 周期性跳跃
    │     每 128 轮完全洗牌产生的"探索"脉冲
    │     帮助跳出局部最优, 带来新的下降
    │
    └── 阶段 3 (384-500 轮): 收敛
          改善幅度 < 5%, 接近全局最优
          即使继续迭代, 改善空间有限
                        │
  质量评估:
    遗传算法最终代价 418
    对比暴力枚举理论最优 ≈ 400-450 (估计)
    偏差: 约 0-5% (在可接受范围内)
    搜索效率: 仅使用 1.24% 的搜索空间
```
**图 8-28: 遗传算法收敛速度与效果分析**
```text
遗传算法操作算子 — 交换与洗牌对比
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  算子 1: shuffleTwo() — 随机交换两个位置                             │
  │                                                                     │
  │  当前最优: [T1, T4, T6, T2, T5, T8, T3, T7]                       │
  │                        │                                            │
  │  第 1 步: 随机选择两个不同位置                                        │
  │           位置 3 = T2, 位置 5 = T8                                   │
  │                        │                                            │
  │  第 2 步: 交换两者                                                    │
  │           结果: [T1, T4, T6, T8, T5, T2, T3, T7]                   │
  │                        │                                            │
  │  第 3 步: 记录已尝试交换对                                            │
  │           switched[3] = {5}, switched[5] = {3}                      │
  │           (BitSet 跟踪, 避免重复)                                    │
  │                        │                                            │
  │  试探评估 → 新代价 vs 当前最优                                         │
  │    ├── 更优 → 更新 best 数组, 重置 switched                          │
  │    └── 更差 → 恢复原顺序, switched 记录阻止重复                       │
  │                                                                     │
  │  当 switched 中所有交换对都已尝试 → 返回 false, 触发洗牌              │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  算子 2: 完全洗牌 — 随机化全部顺序                                    │
  │                                                                     │
  │  触发条件:                                                          │
  │    ├── shuffleTwo() 返回 false (所有交换对已尝试)                     │
  │    └── 或 每 128 轮强制执行一次 (探索脉冲)                            │
  │                                                                     │
  │  执行过程:                                                          │
  │    当前最优: [T1, T4, T6, T2, T5, T8, T3, T7]                     │
  │                        │                                            │
  │    ↓ 随机洗牌:                                                       │
  │                        │                                            │
  │    新序列: [T8, T3, T6, T1, T5, T2, T7, T4]                       │
  │                        │                                            │
  │    保留: current best 不变 (保留历史最优)                             │
  │    重置: switched BitSet 清空 (允许新的交换组合)                      │
  │                                                                     │
  │  设计目的:                                                          │
  │    ├── 跳出局部最优解                                               │
  │    ├── 探索新的搜索区域                                             │
  │    └── 避免过早收敛到次优解                                          │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  两种算子的协作节奏:
    交换(利用) ──→ 洗牌(探索) ──→ 交换(利用) ──→ 洗牌(探索)
     128 轮          1 轮          128 轮          1 轮
```
**图 8-29: 遗传算法操作算子 — 交换与洗牌对比**

---

## 8.3 代价模型

### 8.3.1 `Plan` 类

源码位置：`org/h2/table/Plan.java`

```java
public class Plan {
    private final TableFilter[] filters;
    private final HashMap<TableFilter, PlanItem> planItems = new HashMap<>();
    private final Expression[] allConditions;
    private final TableFilter[] allFilters;
}
```

如图 8-20 所示，`Plan` 表示一个候选执行计划，包含表的访问顺序和使用的索引。

```text
Plan 类在优化过程中的角色
                        │
  Optimizer.optimize()
    │
    ├── 创建 Plan 对象
    │     new Plan(list, len, condition)
    │     │
    │     ├── filters: TableFilter[]   ← 传入当前排列顺序
    │     ├── planItems: HashMap       ← 初始化空集合
    │     └── allConditions:           ← 全部条件表达式
    │
    ├── Plan.calculateCost()           ← 评估此排列的代价
    │     │
    │     ├── 遍历 filters 数组
    │     ├── 对每个 TableFilter:
    │     │     ├── 选择最佳索引
    │     │     ├── 累加代价 (复合乘法)
    │     │     └── 标记可求值
    │     └── 返回总代价
    │
    ├── Plan 的比较与选择
    │     if (plan.calculateCost() < bestPlan.calculateCost())
    │         bestPlan = plan
    │
    └── 最终 bestPlan 的使用
          ├── bestPlan.filters[0] → topFilter
          ├── bestPlan.getPlanItem(filter) → PlanItem
          └── 设置每个 TableFilter 的索引和掩码
```
**图 8-30: Plan 类在优化过程中的角色**
```text
Plan 对象的创建 → 评估 → 选择完整流程
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  Optimizer.optimize()                                           │
  │    │                                                             │
  │    ├── 阶段 1: 策略选择                                            │
  │    │     ├── tryBruteForce()     ← 表数 ≤7                       │
  │    │     ├── tryBruteForceSome() ← 表数 8-10                    │
  │    │     └── tryGenetic()        ← 表数 ≥11                     │
  │    │                                                             │
  │    └── 阶段 2: 排列生成与 Plan 创建                                │
  │          │                                                       │
  │          ├── for each 排列:                                      │
  │          │     │                                                  │
  │          │     ├── new Plan(filters, len, condition)             │
  │          │     │     ├── 保存 filters 数组 (当前排列顺序)          │
  │          │     │     ├── 初始化 planItems = new HashMap<>()       │
  │          │     │     └── 保存 allConditions 引用                  │
  │          │     │                                                  │
  │          │     ├── plan.calculateCost()                          │
  │          │     │     ├── 遍历 filters, 计算每个表的 cost          │
  │          │     │     ├── 复合乘法累加                            │
  │          │     │     └── 返回总代价或 Infinity (无效计划)         │
  │          │     │                                                  │
  │          │     ├── cost < bestCost?                              │
  │          │     │     ├── YES → bestPlan = plan, bestCost = cost  │
  │          │     │     └── NO  → 丢弃 plan (GC 回收)               │
  │          │     │                                                  │
  │          │     └── canStop()? → 提前终止                         │
  │          │                                                       │
  │          └── 完成: bestPlan.filters[0] → topFilter               │
  └─────────────────────────────────────────────────────────────────┘
```
**图 8-31: Plan 对象的创建 → 评估 → 选择完整流程**

### 8.3.2 `calculateCost()` — 代价计算

源码位置：`Plan.java:103`

```java
public double calculateCost(SessionLocal session, AllColumnsForPlan allColumnsSet,
                            boolean isSelectCommand) {
    double cost = 1;
    boolean invalidPlan = false;
    for (int i = 0; i < allFilters.length; i++) {
        TableFilter tableFilter = allFilters[i];
        PlanItem item = tableFilter.getBestPlanItem(session, allFilters,
                    i, allColumnsSet, isSelectCommand);
        planItems.put(tableFilter, item);
        cost += cost * item.cost;           // 复合乘法
        setEvaluatable(tableFilter, true);
        // 检查条件是否可求值
        Expression on = tableFilter.getJoinCondition();
        if (on != null && !on.isEverything(EVALUATABLE_VISITOR)) {
            invalidPlan = true;
            break;
        }
    }
    if (invalidPlan) cost = Double.POSITIVE_INFINITY;  // 无效计划
    return cost;
}
```

如图 8-30 所示，**复合乘法**含义：
- `cost = 1 + cost × item.cost`
- 初始 cost = 1
- 每个表的代价叠加：`new_cost = current_cost + current_cost × item_cost`
- 等价于：`total_cost = ∏(1 + item_cost[i]) - 1`
- 这也等于所有中间行数的乘积和

例如 3 表连接：
- T1 代价 10，T2 代价 5，T3 代价 2
- cost = 1
- T1 后: 1 + 1×10 = 11
- T2 后: 11 + 11×5 = 66
- T3 后: 66 + 66×2 = 198
- 总代价 198

**无效计划**：如果某个 join condition 引用了尚未出现在计划中的表（即条件不可求值），则该计划代价为 `Infinity`，不会被选中。

```text
calculateCost() 代价累加过程详解
                        │
  Plan 排列: [T1, T2, T3]
                        │
  ┌──────────────────────────────────────────────────────────────────────┐
  │  cost = 1 (初始值)                                                   │
  │                                                                      │
  │  ┌──────────────────────────────────────────────────────────────────┐│
  │  │ i=0: TableFilter = T1                                            ││
  │  │  ├── getBestPlanItem(T1)  → item1 (cost=10, index=IDX_A)        ││
  │  │  ├── planItems.put(T1, item1)                                    ││
  │  │  ├── cost = 1 + 1×10 = 11                                       ││
  │  │  ├── setEvaluatable(T1, true)                                    ││
  │  │  └── T1.joinCondition → null (无连接条件)                       ││
  │  └──────────────────────────────────────────────────────────────────┘│
  │                              ↓                                       │
  │  ┌──────────────────────────────────────────────────────────────────┐│
  │  │ i=1: TableFilter = T2                                            ││
  │  │  ├── getBestPlanItem(T2)  → item2 (cost=5, index=PK_B)          ││
  │  │  ├── planItems.put(T2, item2)                                    ││
  │  │  ├── cost = 11 + 11×5 = 66                                      ││
  │  │  ├── setEvaluatable(T2, true)                                    ││
  │  │  └── T2.joinCondition: T2.b_id = T1.id                          ││
  │  │        → T1 已标记 evaluatable ✓  (条件可求值)                   ││
  │  └──────────────────────────────────────────────────────────────────┘│
  │                              ↓                                       │
  │  ┌──────────────────────────────────────────────────────────────────┐│
  │  │ i=2: TableFilter = T3                                            ││
  │  │  ├── getBestPlanItem(T3)  → item3 (cost=2, index=PK_C)          ││
  │  │  ├── planItems.put(T3, item3)                                    ││
  │  │  ├── cost = 66 + 66×2 = 198                                     ││
  │  │  ├── setEvaluatable(T3, true)                                    ││
  │  │  └── T3.joinCondition: T3.c_id = T2.id                          ││
  │  │        → T2 已标记 evaluatable ✓  (条件可求值)                   ││
  │  └──────────────────────────────────────────────────────────────────┘│
  │                              ↓                                       │
  │  return 198                                                          │
  └──────────────────────────────────────────────────────────────────────┘
```
**图 8-32: calculateCost() 代价累加过程详解**
```text
无效计划判定 — Join Condition 不可求值检测
                        │
  Plan 排列: [T3, T1, T2]  (假设 3 表连接)
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  i=0: TableFilter = T3                                          │
  │    ├── getBestPlanItem(T3) → item3                              │
  │    ├── setEvaluatable(T3, true)                                 │
  │    └── T3.joinCondition = null  ← 无连接条件                    │
  │        → 通过                                 ✓                  │
  ├─────────────────────────────────────────────────────────────────┤
  │  i=1: TableFilter = T1                                          │
  │    ├── getBestPlanItem(T1) → item1                              │
  │    ├── setEvaluatable(T1, true)                                 │
  │    └── T1.joinCondition: T1.id = T3.id                          │
  │        → T3 已 evaluatable → 条件可求值    ✓                    │
  ├─────────────────────────────────────────────────────────────────┤
  │  i=2: TableFilter = T2                                          │
  │    ├── getBestPlanItem(T2) → item2                              │
  │    ├── setEvaluatable(T2, true)                                 │
  │    └── T2.joinCondition: T2.ref = T4.id                         │
  │        → T4 未出现在计划中!                                      │
  │        → 条件不可求值                    ✗ 无效计划!              │
  │        → cost = Infinity                                         │
  └─────────────────────────────────────────────────────────────────┘
                        │
  无效计划判定规则:
    ├── joinCondition 中引用的表必须已在之前的位置出现
    ├── 通过 setEvaluatable(filter, true) 标记可求值表
    ├── on.isEverything(EVALUATABLE_VISITOR) 检查所有引用是否可求值
    └── 无效计划会被暴力枚举和混合策略自动排除, 不被选为 bestPlan
```
**图 8-33: 无效计划判定 — Join Condition 不可求值检测**

### 8.3.3 `PlanItem` 结构

源码位置：`org/h2/table/PlanItem.java`

```java
public class PlanItem {
    double cost;            // 估计代价
    private int[] masks;    // 索引条件掩码
    private Index index;    // 选中的索引
    private PlanItem joinPlan;       // 连接的子计划
    private PlanItem nestedJoinPlan; // 嵌套连接的子计划
}
```

如图 8-32 所示，`PlanItem` 封装了一个表在特定连接顺序下的最佳索引选择和代价。

```text
PlanItem 与 Plan、TableFilter 的关系
                        │
  Plan (一个候选执行计划)
    │
    ├── filters: TableFilter[]          ← 表访问顺序
    │     filters[0] = T1 (驱动表)
    │     filters[1] = T2
    │     filters[2] = T3
    │
    └── planItems: HashMap<TableFilter, PlanItem>
          │
          ├── T1 → PlanItem { cost=10, index=IDX_A, masks=[...] }
          │               └── joinPlan → T2 的 PlanItem
          │
          ├── T2 → PlanItem { cost=5, index=PK_B, masks=[...] }
          │               └── joinPlan → T3 的 PlanItem
          │
          └── T3 → PlanItem { cost=2, index=PK_C, masks=[...] }
                        └── joinPlan = null (末尾表)
                        │
  PlanItem 字段详解:
    ┌─────────────────────────────────────────────────────────────────┐
    │  cost: double     索引扫描估计代价 (由 Index.getCost() 返回)    │
    │  index: Index     该表选中的最优索引                            │
    │  masks: int[]     与索引列对应的条件掩码                        │
    │  joinPlan:        普通连接的下一个表 PlanItem (Nested Loop)     │
    │  nestedJoinPlan:  嵌套连接的子计划 (LEFT JOIN 等)              │
    └─────────────────────────────────────────────────────────────────┘
```
**图 8-34: PlanItem 与 Plan、TableFilter 的关系**

### 8.3.4 代价模型工作图

```text
Plan.calculateCost()
  │
  ├── cost = 1
  │
  ├── i=0: tableFilter = T1
  │     ├── getBestPlanItem(T1, filters, 0)
  │     ├── item.cost = 10 (索引扫描)
  │     └── cost = 1 + 1×10 = 11
  │
  ├── i=1: tableFilter = T2
  │     ├── getBestPlanItem(T2, filters, 1)
  │     ├── item.cost = 5 (唯一索引查找)
  │     ├── setEvaluatable(T2, true)
  │     ├── 检查 join condition 是否可求值
  │     └── cost = 11 + 11×5 = 66
  │
  ├── i=2: tableFilter = T3
  │     ├── getBestPlanItem(T3, filters, 2)
  │     ├── item.cost = 2 (主键查找)
  │     ├── setEvaluatable(T3, true)
  │     └── cost = 66 + 66×2 = 198
  │
  └── return 198
```

```text
代价模型核心公式对比
                        │
  不同连接顺序下的代价差异 (3 表连接)
                        │
  ┌──────────────────────────────────────────────────────────────────────┐
  │  排列              代价计算                        总代价           │
  ├──────────────────────────────────────────────────────────────────────┤
  │  [T1, T2, T3]     1+10=11, 11+55=66, 66+132=198   198              │
  │  [T1, T3, T2]     1+10=11, 11+22=33, 33+165=198   198              │
  │  [T2, T1, T3]     1+5=6, 6+60=66, 66+132=198      198              │
  │  [T2, T3, T1]     1+5=6, 6+12=18, 18+180=198      198              │
  │  [T3, T1, T2]     1+2=3, 3+30=33, 33+165=198      198              │
  │  [T3, T2, T1]     1+2=3, 3+15=18, 18+180=198      198              │
  └──────────────────────────────────────────────────────────────────────┘
                        │
  注: 在 item_cost 固定的情况下 (T1=10, T2=5, T3=2)
      所有排列的总代价相同, 均为 198
                        │
  原因: 复合乘法公式 total = ∏(1 + item_cost[i]) - 1
        乘法满足交换律: (1+10)(1+5)(1+2) = (1+5)(1+2)(1+10) = 11×6×3 = 198
                        │
  但实际 item_cost 并非固定:
    连接顺序影响索引选择 → 影响 item_cost → 影响总代价
    例如: T3 作为驱动表时, T3 的索引选择可能更优
          T1 作为驱动表时, T1 的扫描代价可能不同
                        │
  实际场景中的代价差异来源:
    ├── 驱动表的选择影响全表扫描 vs 索引扫描
    ├── 中间结果行数影响后续查找的重复次数
    └── 索引条件掩码匹配在不同顺序下效果不同
```
**图 8-35: 代价模型核心公式对比**

### 8.3.5 代价复合乘法公式可视化

**图 8-36: `Plan.calculateCost()` 的复合乘法公式展开为逐步累加的树形图**

```text
复合乘法公式推导与可视化

公式: total_cost = ∏(1 + item_cost[i]) - 1
                  i=0..n-1

物理含义: 每次累加的 cost 等于"当前中间结果行数 × 当前表扫描代价"
          ┌─────────────────────────────────────────────┐
          │  cost = 1  (初始: 1 行虚拟输入)              │
          │                                              │
          │  第 i 步: 扫描表 i 的代价 = item_cost[i]      │
          │           当前中间结果行数 = cost (之前累加)    │
          │           本次累加 = cost × item_cost[i]      │
          │           新 cost = cost + cost × item_cost[i]│
          └─────────────────────────────────────────────┘

3 表连接示例 (cost: T1=10, T2=5, T3=2):

  第 0 步: T1 代价 10
    cost = 1 + 1×10 = 11
    ├── 1 → 虚拟输入行
    └── 10 → T1 的扫描代价 (全表扫描或索引扫描)
    含义: 读取 T1 所有匹配行的代价 = 11

  第 1 步: T2 代价 5
    cost = 11 + 11×5 = 66
    ├── 11 → T1 返回的行数
    └── 5 → T2 的查找代价 (对 T1 的每一行, 在 T2 中查找)
    含义: 对 T1 的 11 行, 每行在 T2 中查找代价 5, 总代价 = 11×5 = 55
          加上之前的 11 → 66

  第 2 步: T3 代价 2
    cost = 66 + 66×2 = 198
    ├── 66 → T1 与 T2 连接后的行数
    └── 2 → T3 的查找代价
    含义: 对中间结果的 66 行, 每行在 T3 中查找代价 2, 总代价 = 66×2 = 132
          加上之前的 66 → 198

  最终代价 198 的物理意义:
    ├── 读取初始数据: 10 (T1)
    ├── 第一次连接: 11 × 5 = 55 (T1 结果驱动的 T2 查找)
    ├── 第二次连接: 66 × 2 = 132 (中间结果驱动的 T3 查找)
    └── 总代价: 10 + 55 + 132 = 197 ≈ 198 (含初始 1)

  不同连接顺序的代价差异:
    ├── [T1, T2, T3] cost = 198  (T1 驱动, 先连接 T2)
    ├── [T3, T2, T1] cost = 2 + 2×5 + 12×10 = 2+10+120 = 132
    │   (T3 驱动, 中间结果更小)
    └── 最佳顺序: 选择性最高的表在先, 最小化中间结果
```
**图 8-88: 代价复合乘法公式可视化**

复合乘法的本质是**中间结果行数的乘积和**。设第 i 个表的扫描代价为 c_i，总代价可展开为：

total_cost = 1 + c_0 + (1+c_0) × c_1 + (1+c_0)(1+c_1) × c_2 + ... = 1 + c_0 + c_1 + c_0c_1 + c_2 + c_0c_2 + c_1c_2 + c_0c_1c_2 + ...

展开后可以看到，总代价是所有可能连接路径的代价之和。低代价表先扫描的优势在于：其较小的中间结果作为后续连接的输入，大幅降低了连接的总代价。这就是为什么优化器总是倾向于将选择性高（过滤后行数少）的表放在连接顺序的前面。例如在 3 表连接中，如果将 T3（代价最低的表）放在前面，总代价从 198 降低到 132，优化了 33%。

```text
复合乘法公式展开与物理含义
                        │
  公式展开: total = ∏(1 + c_i) - 1
                 = c_0 + c_1 + c_2
                 + c_0·c_1 + c_0·c_2 + c_1·c_2
                 + c_0·c_1·c_2
                        │
  3 表示例 (T1=10, T2=5, T3=2):
                        │
  一阶项 (单表扫描代价):
    ┌── c_0 = 10          ← 读取 T1 的代价
    ├── c_1 = 5           ← 第一次连接的 T2 查找代价
    └── c_2 = 2           ← 第二次连接的 T3 查找代价
                        │
  二阶项 (中间结果代价):
    ┌── c_0·c_1 = 10×5 = 50    ← T1 驱动 T2 的中间结果代价
    ├── c_0·c_2 = 10×2 = 20    ← T1 驱动 T3 的中间结果代价
    └── c_1·c_2 = 5×2 = 10     ← T2 驱动 T3 的中间结果代价
                        │
  三阶项 (全连接代价):
    └── c_0·c_1·c_2 = 100      ← T1→T2→T3 全连接代价
                        │
  总代价 = 10 + 5 + 2 + 50 + 20 + 10 + 100 = 197 (+1 初始 = 198)
                        │
  物理含义:
    总代价 = 所有表扫描代价 + 所有中间结果连接代价
           = 17 + 80 + 100 = 197
           ≈ 1 + c_0 + c_0(1+c_1) + c_0(1+c_1)(1+c_2)
                        │
  不同顺序下二阶项差异:
    [T1,T2,T3]: c_0·c_1 = 50, c_0·c_2 = 20, c_1·c_2 = 10  → 二阶项=80
    [T3,T2,T1]: c_0·c_1 = 2,  c_0·c_2 = 10, c_1·c_2 = 5   → 二阶项=17
    ↑ 因为 T3 代价最小, 作为驱动表产生的中间结果也最小
```
**图 8-37: 复合乘法公式展开与物理含义**

### 8.3.6 PlanItem 结构详细图

**图 8-38: `PlanItem` 对象的完整结构及其在嵌套连接中的递归关系**

```text
PlanItem 对象结构:

┌─────────────────────────────────────────────────────────────────┐
│  PlanItem                                                       │
│                                                                 │
│  ├── cost: double                      ← 当前表的估计扫描代价   │
│  │     该代价由 Index.getCost() 返回                            │
│  │     物理含义: 扫描索引返回匹配行的估计代价                    │
│  │     示例: 主键等值查找 cost≈1                                │
│  │           非唯一索引 cost≈匹配行数 × 索引深度                 │
│  │           全表扫描 cost≈表总行数                              │
│  │                                                              │
│  ├── index: Index                       ← 选中的最优索引        │
│  │     类型: B+ 树索引 / 哈希索引 / 空间索引 / 无索引(全表扫描) │
│  │     在 getBestPlanItem() 阶段确定                            │
│  │                                                              │
│  ├── masks: int[]                       ← 索引条件掩码          │
│  │     掩码用于指示 IndexCondition 与索引列的匹配关系            │
│  │     每个索引列对应一个掩码值:                                │
│  │       mask[i] = 0       → 该列无匹配条件                     │
│  │       mask[i] = EQUALITY → 该列有等值匹配                    │
│  │       mask[i] = START   → 该列有范围起始条件                 │
│  │       mask[i] = END     → 该列有范围结束条件                 │
│  │                                                              │
│  ├── joinPlan: PlanItem                 ← 普通连接的子计划      │
│  │     当 TableFilter 有 join 关系时, joinPlan 描述右侧表的    │
│  │     最优访问路径。递归结构, 对应 Nested Loop Join 的内表     │
│  │                                                              │
│  └── nestedJoinPlan: PlanItem           ← 嵌套连接的子计划      │
│        当 TableFilter 有 nestedJoin 关系时, 描述嵌套连接内部的  │
│        最优计划。用于处理 LEFT JOIN 等特殊连接类型               │
│                                                                 │
│  PlanItem 递归结构示例:                                          │
│    topFilter (T1)                                               │
│      └── planItem                                               │
│            ├── index: PK_T1                                     │
│            ├── cost: 10                                         │
│            ├── masks: [1, 0, 0]                                 │
│            ├── joinPlan → T2 的 PlanItem                        │
│            │     ├── index: IDX_T2_C1                           │
│            │     ├── cost: 5                                    │
│            │     ├── masks: [0, 2, 0]                           │
│            │     └── joinPlan → T3 的 PlanItem                  │
│            │           ├── index: IDX_T3_C2                     │
│            │           ├── cost: 2                              │
│            │           └── masks: [0, 0, 1]                     │
│            └── nestedJoinPlan: null                             │
└─────────────────────────────────────────────────────────────────┘
```
**图 8-89: PlanItem 结构详细图**

PlanItem 是代价模型中粒度为单个表的数据结构。其递归结构（`joinPlan` 字段指向下一个表的 PlanItem）反映了 Nested Loop Join 的执行模型：头表驱动外层循环，后续表依次作为内层循环。`masks` 数组存储了索引条件与索引列的对应关系，在执行阶段指导 `cursor.find()` 如何利用索引进行定位。`nestedJoinPlan` 和 `joinPlan` 的分离使得 H2 可以同时处理普通连接（JOIN）和嵌套连接（LEFT JOIN / RIGHT JOIN）的不同语义。

```text
PlanItem 执行路径与代价分配
                        │
  Nested Loop Join 执行时, PlanItem 指导每个表的访问方式
                        │
  执行顺序 (自上而下):
                        │
  TopFilter (驱动表 T1)
    │
    ├── PlanItem: cost=10, index=IDX_T1_A
    │     └── cursor.find() → 使用 IDX_T1_A 定位
    │
    ├── join.next() → T2
    │     │
    │     ├── PlanItem: cost=5, index=IDX_T2_B
    │     │     └── cursor.find(T1.col) → 利用 T1 当前值查找
    │     │
    │     └── join.next() → T3
    │           │
    │           ├── PlanItem: cost=2, index=PK_T3
    │           │     └── cursor.find(T1.col, T2.col) → 精确查找
    │           │
    │           └── join = null (末尾表)
    │
    └── 执行代价分配:
          ├── T1: 访问表 T1, 代价 10
          ├── T2: 对 T1 每行访问 T2, 代价 10 × 5 = 50
          └── T3: 对 T1,T2 每组合访问 T3, 代价 50 × 2 = 100
               总执行代价 ≈ 10 + 50 + 100 = 160
               (与优化器估计的 198 略有差异, 因不含初始值)
```
**图 8-39: PlanItem 执行路径与代价分配**

### 8.3.7 无效计划判定流程

**图 8-40: `calculateCost()` 中判定计划有效性的完整流程**

```text
无效计划判定流程
                        │
  输入: Plan 对象 (包含 filters 排列顺序和 condition)
                        │
                        ▼
  calculateCost() 循环:
    │
    for i = 0 to allFilters.length - 1:
      │
      ├─ tableFilter = allFilters[i]         ← 当前处理的表
      │
      ├─ item = getBestPlanItem(...)         ← 选择索引
      │
      ├─ cost += cost * item.cost            ← 累加代价
      │
      └─ setEvaluatable(tableFilter, true)   ← 标记此表为可求值
           │
           ├── 检查当前 TableFilter 的 join condition:
           │     on = tableFilter.getJoinCondition()
           │     │
           │     ├── on == null ?
           │     │     ├── YES → 无条件, 继续循环
           │     │     └── NO  → 检查条件可求值性
           │     │
           │     └── on.isEverything(EVALUATABLE_VISITOR) ?
           │           │
           │           ├── YES → 条件可求值, 继续循环
           │           │
           │           └── NO  → 条件不可求值
           │                  │
           │                  └── invalidPlan = true
           │                        break (退出循环)
           │
           └── 示例: 无效计划判定
                 │
                 ┌──────────────────────────────────────────────┐
                 │  连接顺序: [T3, T1, T2]                      │
                 │                                              │
                 │  i=0: T3  setEvaluatable(T3)=true            │
                 │       T3.joinCondition = T3.a = T1.b        │
                 │       T1 尚未被标记为 evaluatable!           │
                 │       → 条件不可求值 → 无效计划              │
                 │                                              │
                 │  i=1: T1  setEvaluatable(T1)=true            │
                 │       T1.joinCondition = T1.c = T2.d        │
                 │       T2 尚未被标记为 evaluatable!           │
                 │       → 条件不可求值 → 无效计划              │
                 │                                              │
                 │  结论: [T3, T1, T2] 是无效连接顺序           │
                 │                                              │
                 │  尝试: [T1, T3, T2]                          │
                 │  i=0: T1, T1.a = T3.b → T3 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T1, T2, T3]                          │
                 │  i=0: T1, 无 join condition                 │
                 │  i=1: T2, T2.c = T3.d → T3 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T2, T1, T3]                          │
                 │  i=0: T2, 无 join condition                 │
                 │  i=1: T1, T1.a = T3.b → T3 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T2, T3, T1]                          │
                 │  i=0: T2, 无 join condition                 │
                 │  i=1: T3, T3.a = T1.b → T1 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T3, T2, T1] (需 T2 先于 T1)          │
                 │  i=0: T3, 无 join condition                 │
                 │  i=1: T2, 无 join condition                 │
                 │  i=2: T1, T1.a = T3.b → T3 已标记 ✓         │
                 │       T1.c = T2.d → T2 已标记 ✓             │
                 │       → 所有条件可求值 → 有效计划!           │
                 └──────────────────────────────────────────────┘
                        │
                        ▼
  结果: 有效计划 [T3, T2, T1] 推进 T3→T2→T1
       无效计划 cost = Infinity (被优化器排除)
```
**图 8-90: 无效计划判定流程**

`setEvaluatable()` 机制是 H2 保证连接顺序合法性的核心约束。在 `calculateCost()` 循环中，每当处理一个 TableFilter 后，就将其标记为"可求值"。后续表的 join condition 引用的表必须已被标记为可求值，否则计划无效。

这种约束反映了 Nested Loop Join 的物理执行模型：驱动表（外循环）必须先出现，内层循环的表才能引用驱动表的列值。如果 join condition 引用了尚未出现的表，意味着在执行当前表时无法计算该条件——因为它需要的数据尚未被读取。

图中所示的示例展示了 3 表连接的搜索空间约束：在 6 种排列中，只有那些满足"被引用表先于引用表出现"约束的排列才是有效的。这种约束大幅缩小了搜索空间，减少了需要评估的排列数量。在真实场景中，多表连接通常包含多个交叉引用的 join condition，实际有效的排列数远小于 n!。

```text
无效计划判定: 依赖关系与搜索空间缩减
                        │
  3 表连接示例: T1, T2, T3
  连接条件: T1.a = T3.b, T1.c = T2.d
                        │
  依赖关系图:
    T1 ←── T3  (T3 需要 T1 已标记)
    T1 ←── T2  (T2 需要 T1 已标记)
    │
    关键词: T1 必须先于 T2 和 T3 出现
                        │
  搜索空间缩减:
                        │
  全部 6 种排列:
    ┌────────────────────────────────────────────────────────────────┐
    │  排列              有效性    原因                              │
    ├────────────────────────────────────────────────────────────────┤
    │  [T1, T2, T3]     有效      T1→T2 ✓, T1→T3 ✓               │
    │  [T1, T3, T2]     有效      T1→T3 ✓, T1→T2 ✓               │
    │  [T2, T1, T3]     有效      T2 无条件, T1→T2 ✓, T1→T3 ✓   │
    │  [T2, T3, T1]     无效      T3 需要 T1 → T1 未标记 ✗       │
    │  [T3, T1, T2]     无效      T3 需要 T1 → T1 未标记 ✗       │
    │  [T3, T2, T1]     无效      T3 需要 T1 → T1 未标记 ✗       │
    └────────────────────────────────────────────────────────────────┘
                        │
  有效排列: [T1,T2,T3], [T1,T3,T2], [T2,T1,T3]
  搜索空间缩减: 6 → 3 (减少 50%)
                        │
  多表场景 (n 表, 全连接):
    如果所有表之间都有连接, 有效排列数 = n!
    (因为任何表都可以引用已出现的表)
                        │
  实际场景:
    连接条件通常是星型或雪花型
    事实表引用维度表
    有效排列数通常介于 n!/2 到 n! 之间
    具体取决于依赖关系图的拓扑结构
```
**图 8-41: 依赖关系与搜索空间缩减**

---

## 8.4 索引选择机制

### 8.4.1 `TableFilter.getBestPlanItem()`

源码位置：`org/h2/table/TableFilter.java:209`

为当前表从所有候选索引中选出代价最低的一个：

```text
TableFilter.getBestPlanItem(session, filters, filter, allColumnsSet, isSelectCommand)
  │
  ├── 1. 构建 masks 数组
  │     遍历 indexConditions，对每个条件设置对应列的掩码
  │
  ├── 2. 调用 table.getBestPlanItem(session, masks, filters, ...)
  │     遍历表的所有索引:
  │     ├── 对每个索引，根据 masks 判断适用性
  │     ├── 调用 index.getCost() 估算代价
  │     └── 选取最低代价索引
  │
  ├── 3. 代价调整
  │     item.cost -= item.cost × indexConditions.size() / 100 / (filter + 1)
  │     索引条件越多，代价越低，使条件多的表更早执行
  │
  └── 4. 处理嵌套连接和普通连接
        ├── nestedJoinPlan: 递归计算
        └── joinPlan: 递归计算
```

```text
getBestPlanItem() 与代价调整机制
                        │
  代价调整公式:
    item.cost = item.cost - item.cost × n / 100 / (filter + 1)
                      原始代价        索引条件数   位置权重
                        │
  示例 1: T1 (第1个位置, 有2个索引条件)
    item.cost = 50 - 50 × 2 / 100 / (0 + 1) = 50 - 1 = 49
    ↓ 条件数量大会降低代价, 使该表更可能被前置
                        │
  示例 2: T3 (第3个位置, 有2个索引条件)
    item.cost = 50 - 50 × 2 / 100 / (2 + 1) = 50 - 0.33 = 49.67
    ↓ 位置越靠后, 调整幅度越小
                        │
  示例 3: T1 (第1个位置, 无索引条件)
    item.cost = 50 - 50 × 0 / 100 / (0 + 1) = 50
    ↓ 无索引条件时, 代价不做调整
                        │
  调整效果: 索引条件多的表被"鼓励"放在连接顺序的前面
    原因: 条件多的表能更早过滤大量行, 减少后续连接代价
```
**图 8-42: getBestPlanItem() 代价调整机制**
```text
嵌套连接与普通连接的递归计算路径
                        │
  TableFilter.getBestPlanItem(session, filters, filterIndex, ...)
    │
    ├── Step 1: 为当前 TableFilter 选择最佳单表访问路径
    │     ├── 构建 masks → table.getBestPlanItem()
    │     └── 返回 PlanItem (含 selectedIndex, cost, masks)
    │
    ├── Step 2: 检查是否有嵌套连接 (nestedJoin)
    │     │
    │     ├── nestedJoin != null?
    │     │     │
    │     │     ├── YES → 递归计算嵌套连接
    │     │     │     │
    │     │     │     ├── nestedJoin.getBestPlanItem(session, ...)
    │     │     │     │     ├── 递归调用自身
    │     │     │     │     ├── 为嵌套子查询选择最佳索引
    │     │     │     │     └── 返回子 PlanItem (含子代价)
    │     │     │     │
    │     │     │     └── item.nestedJoinPlan = subPlanItem
    │     │     │
    │     │     └── NO → 跳过
    │     │
    │     └── 检查是否有普通连接 (join)
    │           │
    │           ├── join != null?
    │           │     │
    │           │     ├── YES → 递归计算连接子表
    │           │     │     │
    │           │     │     ├── join.getBestPlanItem(session, ...)
    │           │     │     │     ├── 递归到 join 链的下一节点
    │           │     │     │     └── 累加子代价
    │           │     │     │
    │           │     │     └── item.joinPlan = subPlanItem
    │           │     │
    │           │     └── NO → 完成
    │           │
    │           └── 递归终止条件: join == null && nestedJoin == null
    │
    └── return item (含完整子树 PlanItem 链)
```
**图 8-43: 嵌套连接与普通连接的递归计算路径**

### 8.4.2 `IndexCondition` 类型

源码位置：`org/h2/index/IndexCondition.java`

```java
public class IndexCondition {
    public static final int EQUALITY           = 1;   // 等值条件 =
    public static final int START              = 2;   // 范围起始 >= >
    public static final int END                = 4;   // 范围结束 <= <
    public static final int RANGE              = 6;   // BETWEEN (START|END)
    public static final int ALWAYS_FALSE       = 8;   // 恒假条件
    public static final int SPATIAL_INTERSECTS = 16;  // 空间交叉
}
```

如图 8-34 所示，条件通过**掩码**与索引匹配。每个 `IndexCondition` 都绑定到一个特定的列和一个比较类型。

```text
IndexCondition 类型与掩码取值
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  常量名              值   含义            SQL 示例                 │
  ├────────────────────────────────────────────────────────────────────┤
  │  EQUALITY            1    等值条件       col = 100                │
  │  START               2    范围起始       col > 10, col >= 5      │
  │  END                 4    范围结束       col < 20, col <= 100    │
  │  RANGE               6    范围           col BETWEEN 1 AND 100   │
  │  ALWAYS_FALSE        8    恒假           col IS NULL (无匹配)    │
  │  SPATIAL_INTERSECTS  16   空间交叉       ST_INTERSECTS(col, ...) │
  └────────────────────────────────────────────────────────────────────┘
                        │
  掩码组合规则:
    ├── 同一列上可以有多个条件
    │     col > 5 AND col < 20 → START | END = 2 | 4 = 6 (RANGE)
    │
    ├── 掩码用于与索引列匹配:
    │     如果 mask[column_id] != 0, 则该列有索引可用条件
    │     掩码值越大, 条件精度越高 (EQUALITY > START > END)
    │
    └── 掩码存储位置:
          masks 数组的长度 = 表的总列数
          masks[column_id] = 该列上的条件掩码 (多个条件按位或)
```
**图 8-44: IndexCondition 类型与掩码取值**

### 8.4.3 条件提取过程

如图 8-44 所示，在 `Select.preparePlan()` 阶段，`TableFilter.createIndexConditions()` 将 WHERE 条件拆解为与当前表相关的 `IndexCondition`：

```text
WHERE T1.a = 10 AND T1.b > 5 AND T2.c = 'x'
  │
  ├── T1 的 IndexConditions:
  │     ├── [a EQUALITY 10]     掩码: 1
  │     └── [b START 5]        掩码: 2
  │
  └── T2 的 IndexConditions:
        └── [c EQUALITY 'x']    掩码: 1
```

```text
条件提取完整流程
                        │
  SQL: SELECT * FROM t1 JOIN t2 ON t1.id = t2.t1_id
       WHERE t1.status = 'ACTIVE' AND t2.amount > 100
                        │
                        ▼
  Select.preparePlan()
    │
    ├── 1. 解析 WHERE 为表达式树
    │     AND
    │     ├── Comparison(t1.status = 'ACTIVE')
    │     └── Comparison(t2.amount > 100)
    │
    ├── 2. 绑定列到 TableFilter
    │     t1.status → TableFilter(T1), column=2
    │     t2.amount → TableFilter(T2), column=3
    │
    ├── 3. TableFilter(T1).createIndexConditions()
    │     ├── 遍历 T1 的表达式: [t1.status = 'ACTIVE']
    │     ├── t1.status 在 T1 的列中 → 创建 IndexCondition
    │     └── 结果: [status EQUALITY 'ACTIVE', mask=1]
    │
    ├── 4. TableFilter(T2).createIndexConditions()
    │     ├── 遍历 T2 的表达式: [t2.amount > 100]
    │     ├── t2.amount 在 T2 的列中 → 创建 IndexCondition
    │     └── 结果: [amount START 100, mask=2]
    │
    └── 5. 每个 TableFilter 的 indexConditions 就绪
          准备在 getBestPlanItem() 中使用
```
**图 8-45: 条件提取完整流程**

### 8.4.4 索引代价估算

如图 8-45 所示，`Index.getCost()` 基于统计信息返回大致行数：

- **主键/唯一索引**: cost ≈ 1（等值匹配时）
- **普通索引 (范围扫描)**: cost ≈ 估计匹配行数 × 索引深度
- **全表扫描**: cost ≈ 表总行数

```text
索引代价估算示例 (表 TEST, 10000 行)
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  索引类型           查询条件                  代价估算              │
  ├─────────────────────────────────────────────────────────────────────┤
  │  主键 PK(id)        id = 100                 1                     │
  │                     (等值匹配, B+树精确查找)                         │
  │                                                                     │
  │  唯一索引 UX(email)  email = 'a@b.com'       1                     │
  │                     (唯一索引等值, 与主键相同)                       │
  │                                                                     │
  │  非唯一索引          name = 'John'            50 ← 估计行数 × 1    │
  │  IDX_NAME(name)     (等值匹配, 非唯一)        (10000 × 0.5% 选择率) │
  │                                                                     │
  │  非唯一索引          name LIKE 'J%'           200                   │
  │  IDX_NAME(name)     (前缀范围)               (10000 × 2% 选择率)    │
  │                                                                     │
  │  非唯一索引          age > 18                 8000                  │
  │  IDX_AGE(age)       (范围扫描, 80% 行)        (10000 × 80%)        │
  │                                                                     │
  │  无索引 (全表扫描)   status = 'ACTIVE'        10000                 │
  │                     (逐行检查)               (全部 10000 行)        │
  └─────────────────────────────────────────────────────────────────────┘
```
**图 8-46: 索引代价估算示例**
```text
索引选择性比较 — 不同查询条件的匹配行占比
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  表 TEST (10000 行)                                                  │
  │                                                                     │
  │  索引 IDX_NAME(name) 的列值分布:                                     │
  │                                                                     │
  │  值           频率          选择性                                   │
  │  ──────────   ──────────    ─────────────────────────               │
  │  'John'       50 行         0.5%   ← 高选择性, 适合索引              │
  │  'Jane'       80 行         0.8%   ← 高选择性                       │
  │  'Smith'      200 行        2.0%   ← 中等选择性                     │
  │  'Lee'        500 行        5.0%   ← 低选择性                       │
  │  '' (空串)    1000 行       10.0%  ← 很低选择性                      │
  │  NULL         200 行        2.0%   ← 不参与索引                      │
  │  ──────────   ──────────                                             │
  │  合计         10000 行      100%                                     │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  选择性对代价的影响:
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  条件           选择性   索引代价   回表代价   总代价    建议      │
  │  ─────────────  ───────  ────────  ────────  ───────  ───────── │
  │  name = 'John'   0.5%     1          49       50      使用索引  │
  │  name = 'Lee'    5.0%     1         499      500     使用索引  │
  │  name > 'A'     90.0%     1        8999     9000    全表扫描   │
  │                    (几乎全部行, 索引+回表不如全表扫描)             │
  │  name IS NULL    2.0%    无法使用索引 → 全表扫描                  │
  │                    (NULL 不存储在非唯一索引中)                     │
  └─────────────────────────────────────────────────────────────────┘
                        │
  选择率阈值规则:
    当选择率 > 15-20% 时, 全表扫描通常比索引扫描更快
    原因: 索引扫描需要随机 I/O (回表), 而全表扫描是顺序 I/O
```
**图 8-47: 索引选择性比较 — 不同查询条件的匹配行占比**

### 8.4.5 索引条件匹配图

```text
索引选择过程
  │
  Table: TEST (10000 行)
  │
  索引:
    PK(ID)           → 唯一, B+ 树
    IDX_NAME(NAME)   → 非唯一, B+ 树
    IDX_AGE(AGE)     → 非唯一, B+ 树
  │
  WHERE: name = 'John' AND age > 25
  │
  ▼
  TableFilter.getBestPlanItem()
  │
  ├── masks: [name → EQUALITY, age → START]
  │
  ├── PK(ID): mask[ID]=0 → 不匹配, cost 忽略
  │
  ├── IDX_NAME(NAME):
  │     ├── mask[NAME]=EQUALITY (匹配)
  │     ├── 估计匹配行: 50 (根据统计)
  │     ├── cost ≈ 50
  │     └── 可以配合 age 条件做 filter
  │
  ├── IDX_AGE(AGE):
  │     ├── mask[AGE]=START (匹配)
  │     ├── 估计匹配行: 3333 (age > 25)
  │     ├── cost ≈ 3333
  │     └── 必须配合 name 条件做 filter
  │
  └── 选择: IDX_NAME (cost=50)
```

```text
索引选择决策流程 (多索引候选比较)
                        │
  输入: masks = [name → EQUALITY, age → START]
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  索引候选 1: PK(ID)                                             │
  │  ├── 索引列: [ID]                                               │
  │  ├── masks[ID]=0 → 无匹配                                       │
  │  └── 结论: 不适用, 跳过                                        │
  ├─────────────────────────────────────────────────────────────────┤
  │  索引候选 2: IDX_NAME(NAME)                                     │
  │  ├── 索引列: [NAME]                                             │
  │  ├── masks[NAME]=EQUALITY → 等值匹配 ✓                          │
  │  ├── getCost(): 估计 50 行                                      │
  │  └── 代价: cost = 50                                            │
  ├─────────────────────────────────────────────────────────────────┤
  │  索引候选 3: IDX_AGE(AGE)                                       │
  │  ├── 索引列: [AGE]                                              │
  │  ├── masks[AGE]=START → 范围起始匹配 ✓                          │
  │  ├── getCost(): 估计 3333 行                                    │
  │  └── 代价: cost = 3333                                          │
  └─────────────────────────────────────────────────────────────────┘
                        │
                        ▼
  选择: IDX_NAME (cost=50), 因为 50 < 3333
                        │
  代价调整:
    ├── indexConditions.size() = 2 (name 等值 + age filter)
    ├── filter = 0 (第 1 个位置)
    └── adjusted_cost = 50 - 50 × 2 / 100 / 1 = 50 - 1 = 49
```
**图 8-48: 索引选择决策流程**

### 8.4.6 索引覆盖扫描

当索引包含了查询所需的所有列时，H2 可以进行索引覆盖扫描（Index-Only Scan），跳过表数据访问：

```text
查询: SELECT name FROM test WHERE name = 'John'
索引: IDX_NAME(name)        ← name 列在索引中
      └── 无需回表，直接从索引读取
```

```text
索引覆盖扫描 vs 非覆盖扫描对比
                        │
  场景: 查询 name 列, 条件 name = 'John'
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  覆盖扫描 (Index-Only Scan):                                      │
  │                                                                   │
  │  SELECT name FROM test WHERE name = 'John'                        │
  │  索引 IDX_NAME(name): 包含 name 列                                │
  │                                                                   │
  │  B+树定位 → 叶子节点读取 → 直接返回 name                         │
  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                    │
  │  │ 根节点    │ →  │ 分支节点  │ →  │ 叶子节点  │ → name 值        │
  │  └──────────┘    └──────────┘    └──────────┘                    │
  │                                   key='John'                     │
  │                                                                   │
  │  I/O: 仅索引页 (3-4 次索引页读取)                                  │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  非覆盖扫描 (需回表):                                              │
  │                                                                   │
  │  SELECT name, status FROM test WHERE name = 'John'                │
  │  索引 IDX_NAME(name): 包含 name 但不包含 status                   │
  │                                                                   │
  │  B+树定位 → 叶子节点读取 → 根据 rowId 回表 → 返回完整行          │
  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
  │  │ 根节点    │ →  │ 分支节点  │ →  │ 叶子节点  │ →  │ 数据页   │    │
  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
  │                                   key='John'    rowId=123        │
  │                                                                   │
  │  I/O: 索引页 + 数据页 (4-5 次页面读取)                            │
  └────────────────────────────────────────────────────────────────────┘
                        │
  何时能使用覆盖扫描?
    ├── 索引包含 SELECT 所有列
    ├── 索引包含 WHERE 所有条件列
    └── 无需访问表数据即可完成查询
```
**图 8-49: 索引覆盖扫描 vs 非覆盖扫描对比**

### 8.4.7 索引条件掩码匹配过程详细图

**图 8-50: `masks` 数组与索引列的匹配过程**

```text
索引条件掩码匹配过程

输入: WHERE T1.a = 10 AND T1.b > 5 AND T1.c BETWEEN 1 AND 100
                        │
                        ▼
  步骤 1: 从 WHERE 条件提取 T1 的 IndexConditions
    │
    ├── condition: T1.a = 10    → IndexCondition(EQUALITY, column=a)
    ├── condition: T1.b > 5     → IndexCondition(START, column=b)
    └── condition: T1.c BETWEEN 1 AND 100
                                → IndexCondition(RANGE, column=c)
                        │
                        ▼
  步骤 2: 构建 masks 数组 (长度 = 表的总列数)
    │
    ┌─────────────────────────────────────────────────────────┐
    │                   列索引: 0    1    2    3    4          │
    │                   列名:  ID   A    B    C    D          │
    │                   masks: [0,   1,   2,   6,   0]       │
    │                           │    │    │    │              │
    │                           │    │    │    └── mask[3]=6 │
    │                           │    │    │        (START|END │
    │                           │    │    │         = RANGE)  │
    │                           │    │    └─── mask[2]=2     │
    │                           │    │            (START)     │
    │                           │    └─── mask[1]=1          │
    │                           │            (EQUALITY)       │
    │                           └─── mask[0]=0               │
    │                                       (无条件)          │
    └─────────────────────────────────────────────────────────┘
                        │
                        ▼
  步骤 3: 遍历所有索引, 比对 masks 与索引列
    │
    ├── 主键 PK(ID): 索引列 [ID]
    │     mask[0]=0 → 无匹配条件
    │     cost = 10000 (全表扫描等效代价)
    │
    ├── 索引 IDX_A(A, B): 索引列 [A, B]
    │     mask[1]=1 (EQUALITY) → A 列匹配等值条件  ✓
    │     mask[2]=2 (START)   → B 列匹配起始条件  ✓
    │     掩码覆盖: 前 2 列完全匹配
    │     cost = 50  (等值≈10行, 范围≈5倍)
    │
    ├── 索引 IDX_C(C): 索引列 [C]
    │     mask[3]=6 (RANGE) → C 列匹配范围条件     ✓
    │     但只有 C 列, 缺少 A 和 B 条件
    │     cost = 100 (范围扫描, 匹配行较多)
    │
    └── 索引 IDX_D(D): 索引列 [D]
          mask[4]=0 → 无匹配条件
          cost = 10000 (全表扫描等效代价)
                        │
                        ▼
  步骤 4: 选择最低代价索引 → IDX_A(A, B) cost=50
    │
    代价调整: item.cost = 50 - 50 × 2/100 / (0+1) = 49
    因为 T1 有 2 个索引条件, 代价微调 -1%
```
**图 8-91: 索引条件掩码匹配过程详细图**

掩码匹配是 H2 索引选择的核心算法。`masks` 数组的长度等于表的总列数，每个元素的取值表示该列上索引条件的类型（0=无条件, 1=等值, 2=范围起始, 4=范围结束, 6=范围, 8=恒假）。遍历索引时，将索引的列顺序与 `masks` 数组按位比对：对于索引的第 i 列，如果 `masks[columnId] != 0`，则该索引在该列上有匹配条件。匹配的列越多、条件类型越精确（等值优先于范围），索引的代价越低。

```text
索引掩码匹配效率分析
                        │
  不同条件类型的匹配效果排序:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  优先级   条件类型     掩码值   索引利用效率          示例         │
  ├────────────────────────────────────────────────────────────────────┤
  │  最高     等值         1      精确定位到一行       id = 100       │
  │  ↑       范围起始     2      定位到起始位置       age > 18       │
  │  │       范围结束     4      定位到结束位置       price <= 100   │
  │  │       范围(BTW)    6      定位起止范围         date BETWEEN   │
  │  最低    恒假         8      永不匹配             false条件      │
  └────────────────────────────────────────────────────────────────────┘
                        │
  组合索引匹配示例:
                        │
  索引 IDX_A_B(A, B):
  ┌────────────────────────────────────────────────────────────────────┐
  │  查询条件                    A 列掩码   B 列掩码   是否可用       │
  ├────────────────────────────────────────────────────────────────────┤
  │  WHERE a = 1                 EQUALITY   0         可用 (前缀等值)│
  │  WHERE a = 1 AND b = 2      EQUALITY   EQUALITY   可用 (完全匹配)│
  │  WHERE a = 1 AND b > 5      EQUALITY   START      可用 (范围扫描)│
  │  WHERE a > 1                 START      0         可用 (范围扫描)│
  │  WHERE b = 2                 0          EQUALITY   不可用         │
  │                              (缺少前缀列 a, 无法利用索引)          │
  └────────────────────────────────────────────────────────────────────┘
```
**图 8-51: 索引掩码匹配效率分析**

### 8.4.8 索引选择代价比较图

**图 8-52: 在多种查询条件下，不同索引的代价对比**

```text
索引代价比较 (表 TEST, 10000 行)
                        │
  ┌───────────────────────────────────────────────────────────┐
  │  索引类型          WHERE 条件              估计代价       │
  ├───────────────────────────────────────────────────────────┤
  │  PK(ID)           id = 100                1       ← 最低 │
  │  PK(ID)           id > 5000               5000           │
  │  IDX_NAME(NAME)   name = 'John'           50             │
  │  IDX_NAME(NAME)   name LIKE 'J%'          200            │
  │  IDX_AGE(AGE)     age = 25                40             │
  │  IDX_AGE(AGE)     age > 18                8000           │
  │  IDX_AGE(AGE)     age BETWEEN 20 AND 30   1000           │
  │  IDX_CAT(CAT)     cat IN ('A','B','C')    300            │
  │  (全表扫描)        无条件                   10000          │
  └───────────────────────────────────────────────────────────┘
                        │
                        ▼
  组合索引优势:

  ┌───────────────────────────────────────────────────────────┐
  │  索引                      WHERE 条件          cost      │
  ├───────────────────────────────────────────────────────────┤
  │  IDX_A_B(A, B)          a=1 AND b=10          1          │
  │  IDX_A_B(A, B)          a=1                   10         │
  │  IDX_A_B(A, B)          b=10                  10000      │
  │                         (b 的等值条件无法使用               │
  │                          因为缺少 a 条件)                  │
  │  IDX_B_A(B, A)          b=10 AND a=1          1          │
  │  IDX_B_A(B, A)          b=10                  50         │
  └───────────────────────────────────────────────────────────┘
                        │
                        ▼
  选择率对代价的影响:

  查询: status = 'PAID' AND amount > 100
    │
    ├── IDX_STATUS(status): cost = 3000
    │     等值匹配 status='PAID' → 约 3000 行
    │     amount>100 作为 filter 条件
    │
    └── IDX_AMOUNT(amount): cost = 5000
          范围匹配 amount>100 → 约 5000 行
          status='PAID' 作为 filter 条件
```
**图 8-92: 索引选择代价比较图**

该图总结了 H2 索引代价估算的典型值。核心原则：**等值条件优于范围条件，前缀匹配优于非前缀匹配**。组合索引的列顺序至关重要——最左前缀原则决定了哪些查询能有效利用索引。在缺少索引前缀列的情况下（如图中 `b=10` 查询无法使用 `IDX_A_B(A,B)`），优化器退化为全表扫描。

```text
索引代价选择的实际案例对比
                        │
  案例: 订单查询
    SELECT * FROM orders
    WHERE customer_id = 123
      AND status = 'PAID'
      AND amount > 100
                        │
  可用索引及代价估算:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  索引                           估计代价    选择理由              │
  ├────────────────────────────────────────────────────────────────────┤
  │  PK(id)                         10000      无法使用 (条件无 id)  │
  │  IDX_CUSTOMER(customer_id)      50          等值匹配, 约 50 行   │
  │  IDX_STATUS(status)             3333        等值, 但 33% 行      │
  │  IDX_AMOUNT(amount)             8000        范围, 80% 行         │
  │  IDX_C_S(customer, status)      5           双等值匹配, 约 5 行  │
  │  IDX_C_S_A(c, status, amount)   5          覆盖+双等值+范围     │
  └────────────────────────────────────────────────────────────────────┘
                        │
  最佳选择: IDX_C_S_A (覆盖索引, 不需要回表)
    └── cost = 5 (双等值条件高度精确)
                        │
  次优选择: IDX_C_S (双等值, 但需要回表读 amount)
    └── cost = 5 (但需要额外回表 I/O)
                        │
  最差选择: 全表扫描
    └── cost = 10000 (读全部 10000 行)
```
**图 8-53: 索引代价选择案例分析**

### 8.4.9 索引覆盖扫描与回表访问对比

**图 8-54: 索引覆盖扫描与普通索引访问的执行路径差异**

```text
索引覆盖扫描 vs 回表访问

场景 1: 索引覆盖扫描 (无需回表)
  ┌─────────────────────────────────────────────────────────────┐
  │  查询: SELECT name FROM test WHERE name = 'John'            │
  │  索引: IDX_NAME(name)                                       │
  │                                                            │
  │  执行路径:                                                  │
  │    cursor.find(name='John')    ← B+ 树定位到叶子节点        │
  │    leaf_node: [key='John', value=name值]                    │
  │    ↓                                                        │
  │    cursor.next()               ← 读取下一叶子节点           │
  │    leaf_node: [key='John2', value=name值]                   │
  │    ↓                                                        │
  │    直接返回 name 值, 无需访问表数据                         │
  │    I/O: 仅索引页读取                                         │
  └─────────────────────────────────────────────────────────────┘

场景 2: 普通索引访问 (需要回表)
  ┌─────────────────────────────────────────────────────────────┐
  │  查询: SELECT name, status FROM test WHERE name = 'John'    │
  │  索引: IDX_NAME(name)                                       │
  │                                                            │
  │  执行路径:                                                  │
  │    cursor.find(name='John')    ← B+ 树定位到叶子节点        │
  │    leaf_node: [key='John', rowId=123]                      │
  │    ↓                                                        │
  │    table.getRow(rowId=123)     ← 根据 rowId 回表读取数据   │
  │    data_page: [id=123, name='John', status='A', ...]       │
  │    ↓                                                        │
  │    返回 name + status 值, 需要索引 + 表两次访问             │
  │    I/O: 索引页 + 数据页读取                                  │
  └─────────────────────────────────────────────────────────────┘

场景 3: 全表扫描 (无索引)
  ┌─────────────────────────────────────────────────────────────┐
  │  查询: SELECT * FROM test WHERE status = 'ACTIVE'           │
  │  (status 列无索引)                                          │
  │                                                            │
  │  执行路径:                                                  │
  │    tableScan.next()              ← 顺序扫描表数据          │
  │    ↓                                                        │
  │    row[0]: [id=1, name='A', status='ACTIVE']               │
  │    filter: status='ACTIVE' → 匹配 ✓                        │
  │    ↓                                                        │
  │    row[1]: [id=2, name='B', status='INACTIVE']             │
  │    filter: status='ACTIVE' → 不匹配 ✗                      │
  │    ↓                                                        │
  │    ... (遍历所有 10000 行)                                  │
  │    I/O: 全部数据页读取                                       │
  └─────────────────────────────────────────────────────────────┘

  代价对比:
  ┌───────────────────────────────────────────────────────────┐
  │  访问方式            I/O 次数        适用场景              │
  ├───────────────────────────────────────────────────────────┤
  │  索引覆盖扫描         索引页数        SELECT 列均在索引中 │
  │  普通索引访问       索引页+数据页     SELECT 列超出索引   │
  │  全表扫描             全部数据页       无条件或全量查询    │
  └───────────────────────────────────────────────────────────┘
```
**图 8-93: 索引覆盖扫描与回表访问对比**

三种数据访问方式在执行路径上有本质差异：索引覆盖扫描最理想（仅索引页读取），普通索引访问需要索引 + 回表两步操作，全表扫描需要顺序读取全部数据页。优化器会根据查询的列选择性和可用索引，在三种方式中选择代价最低的方案。

```text
如何判断能否使用索引覆盖扫描?
                        │
  查询: SELECT a, b FROM test WHERE a = 1 AND c > 5
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  步骤 1: 列出查询所需的所有列                                      │
  │    ├── SELECT 列: a, b                                             │
  │    ├── WHERE 条件列: a, c                                          │
  │    └── 全部所需列: {a, b, c}                                      │
  │                                                                     │
  │  步骤 2: 检查候选索引是否包含所有列                                │
  │    ├── IDX_A(a): 包含 {a} → 缺少 b, c → 需回表                    │
  │    ├── IDX_A_B(a, b): 包含 {a, b} → 缺少 c → 需回表              │
  │    ├── IDX_A_C(a, c): 包含 {a, c} → 缺少 b → 需回表              │
  │    └── IDX_A_B_C(a, b, c): 包含 {a, b, c} → 覆盖扫描!            │
  │                                                                     │
  │  步骤 3: 选择覆盖索引或最低代价索引                                 │
  │    如果存在覆盖索引 → 优先选择 (避免回表 I/O)                       │
  │    否则 → 选择代价最低的普通索引                                    │
  └────────────────────────────────────────────────────────────────────┘
                        │
  覆盖索引的收益量化:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  场景              覆盖扫描 I/O    普通索引 I/O     节省          │
  ├────────────────────────────────────────────────────────────────────┤
  │  等值 50 行        索引页 3 次      索引 3 + 数据 50   94%        │
  │  范围 1000 行      索引页 3 次      索引 3 + 数据 1000 99.7%      │
  │  全表扫描           全部数据页        —                —          │
  └────────────────────────────────────────────────────────────────────┘
```
**图 8-55: 索引覆盖扫描判断与收益分析**

---

## 8.5 TableFilter 与条件求值

### 8.5.1 `TableFilter.next()` — 行迭代

源码位置：`org/h2/table/TableFilter.java:438`

`TableFilter.next()` 是整个查询执行的核心循环：

```java
public boolean next() {
    if (state == BEFORE_FIRST) {
        cursor.find(session, indexConditions);              // 首次：初始化游标
    } else if (state == FOUND && join != null && join.next())
        return true;                                        // 连接表有更多行
    while (true) {
        if (cursor.isAlwaysFalse()) state = AFTER_LAST;
        else if (cursor.next()) { currentSearchRow = cursor.getSearchRow(); state = FOUND; }
        else state = AFTER_LAST;
        // 嵌套连接处理（含外连接 NULL 行补全）
        if (nestedJoin != null && state == FOUND && !nestedJoin.next()) {
            state = AFTER_LAST;
            if (joinOuter && !foundOne) setNullRow();
            else continue;
        }
        if (!isOk(filterCondition)) continue;               // 过滤条件检查
        boolean joinConditionOk = isOk(joinCondition);
        if (state == FOUND) {
            if (joinConditionOk) foundOne = true; else continue;
        }
        if (join != null) { join.reset(); if (!join.next()) continue; }
        return true;
    }
}
}
```

如图 8-46 所示，`TableFilter.next()` 状态机：

```text
状态迁移:
          next() 首次调用
BEFORE_FIRST ────────────────→ cursor.find() 初始化
     │
     │ cursor.next() = true
     ├────────────────────────→ FOUND
     │                           │
     │                           ├── isOk(filter) = false → continue
     │                           ├── isOk(joinCondition) = false → continue
     │                           └── join.next() = false → continue
     │
     │ cursor.next() = false
     └────────────────────────→ AFTER_LAST
                                 │
                                 ├── joinOuter && !foundOne → NULL_ROW
                                 └── return false
```

```text
TableFilter.next() 完整执行流程
                        │
  next() 调用
    │
    ├── state == BEFORE_FIRST?
    │     └── YES → cursor.find(indexConditions) ← 游标初始化
    │
    ├── state == FOUND && join != null?
    │     └── YES → join.next()? ← 先尝试内表
    │           ├── YES → return true
    │           └── NO  → 进入 while 循环获取下一行
    │
    └── while(true) 主循环:
          │
          ├── cursor.isAlwaysFalse()?
          │     └── YES → state = AFTER_LAST
          │
          ├── cursor.next()?
          │     ├── YES → state = FOUND
          │     │         currentSearchRow = 当前行
          │     │         current = null (清除缓存的行)
          │     │
          │     │         ├── nestedJoin 处理
          │     │         │     ├── nestedJoin.next()? NO
          │     │         │     │     └── joinOuter && !foundOne?
          │     │         │     │           ├── YES → setNullRow()
          │     │         │     │           └── NO  → continue
          │     │         │     └── YES → 继续
          │     │         │
          │     │         ├── isOk(filterCondition)?
          │     │         │     ├── NO → continue (跳过)
          │     │         │     └── YES → 继续
          │     │         │
          │     │         ├── isOk(joinCondition)?
          │     │         │     ├── NO → continue (跳过)
          │     │         │     └── YES → foundOne = true
          │     │         │
          │     │         ├── join != null?
          │     │         │     ├── YES → join.reset() + join.next()?
          │     │         │     │     ├── YES → return true
          │     │         │     │     └── NO  → continue
          │     │         │     └── NO  → return true
          │     │         │
          │     │         └── return true (找到有效行)
          │     │
          │     └── NO → state = AFTER_LAST
          │
          └── AFTER_LAST → return false (行耗尽)
```
**图 8-56: TableFilter.next() 完整执行流程**

### 8.5.2 JOIN 处理

如图 8-56 所示，`TableFilter` 通过 `join` 字段形成链表结构：

```text
TableFilter 链:
            join        join
  topFilter ────→ T2 ────→ T3
     │
     │ 外循环: 遍历 T1
     │    └── 内循环: 遍历 T2 (受 T1 当前行约束)
     │        └── 内循环: 遍历 T3 (受 T1, T2 当前行约束)
     │
     └── 嵌套循环连接 (Nested Loop Join)
```
```text

**外连接处理**：
```
```java
if (joinOuter && !foundOne) {
    setNullRow();  // 返回 NULL 扩展行
}
```

当内表无匹配行时，填充 NULL 值并返回一行。

```text
TableFilter JOIN 链表结构与执行模型
                        │
  物理结构:
    topFilter (T1)
      ├── join = T2 (TableFilter 引用)
      │     ├── join = T3 (TableFilter 引用)
      │     │     └── join = null
      │     └── nestedJoin = null (或 LEFT JOIN 子计划)
      └── nestedJoin = null
                        │
  执行模型 (Nested Loop Join):
    ┌─────────────────────────────────────────────┐
    │  T1.next() 返回一行                          │
    │    └── T1.join = T2                          │
    │          │                                   │
    │          T2.reset() + T2.next()              │
    │            ├── 使用 T1 当前行作为查找条件     │
    │            └── 返回 T2 匹配行                │
    │                │                             │
    │                └── T2.join = T3              │
    │                      │                       │
    │                      T3.reset() + T3.next()  │
    │                        ├── 使用 T1,T2 查找   │
    │                        └── 返回 T3 匹配行    │
    └─────────────────────────────────────────────┘
                        │
  深度优先执行:
    T1_row1 → T2_row1 → T3_row1 (输出)
    T1_row1 → T2_row1 → T3_row2 (输出)
    T1_row1 → T2_row2 → T3_row1 (输出)
    T1_row1 → T2_row2 → T3_row2 (输出)
    T1_row2 → T2_row1 → T3_row1 (输出)
    ...
```
**图 8-57: TableFilter JOIN 链表结构与执行模型**

### 8.5.3 条件求值阶段

如图 8-57 所示，条件分为两类：
1. **Index Conditions** — 用于索引定位（start/end），在 `cursor.find()` 阶段使用
2. **Filter Condition** — 索引无法处理的条件，在 `isOk()` 阶段逐行过滤

```text
表 TEST: 10000 行, 索引 IDX_NAME(name)
查询: SELECT * FROM TEST WHERE name = 'John' AND status = 'ACTIVE'
  │
  ├── Index Condition: name = 'John'
  │     → cursor.find() 直接定位到 name='John' 的记录
  │     → 约 50 行
  │
  └── Filter Condition: status = 'ACTIVE'
        → isOk(filterCondition) 对 50 行逐行检查
        → 最终返回约 30 行
```

```text
条件求值阶段与执行效率分析
                        │
  两阶段条件求值:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  阶段 1: Index Conditions (索引条件)                               │
  │                                                                     │
  │  时机: cursor.find() 时                                             │
  │  位置: 索引层 (B+ 树遍历)                                           │
  │  效果: 直接定位到满足条件的起始/结束位置                            │
  │  开销: O(log n) 索引树深度                                          │
  │                                                                     │
  │  示例: name = 'John' → B+ 树定位到 'John' 的叶子节点               │
  │        只读取 name='John' 的 50 行                                  │
  │        避免扫描全部 10000 行                                        │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  阶段 2: Filter Conditions (过滤条件)                              │
  │                                                                     │
  │  时机: cursor.next() 后, isOk() 调用                               │
  │  位置: TableFilter 层 (行过滤)                                      │
  │  效果: 逐行检查剩余条件                                             │
  │  开销: O(m) m = 索引扫描返回的行数                                  │
  │                                                                     │
  │  示例: status = 'ACTIVE' → 对 50 行逐行检查                        │
  │        最终返回约 30 行                                             │
  └────────────────────────────────────────────────────────────────────┘
                        │
  效率分析:
    索引条件 + 过滤条件 = 避免全表扫描
    10000 行 → 索引定位到 50 行 → 过滤到 30 行
    效率提升: 10000/30 ≈ 333 倍
```
**图 8-58: 两阶段条件求值效率分析**

### 8.5.4 TableFilter 状态机增强版

**图 8-59: 以状态机形式展示 TableFilter 的生命周期**

```text
TableFilter 完整生命周期状态机
                        │
                        ▼
  ┌────────────────┐
  │  BEFORE_FIRST   │  ← TableFilter 初始状态
  │  state = -1     │
  └───────┬────────┘
          │
          │  next() 首次调用
          ▼
  ┌────────────────┐
  │  cursor.find()  │  ← 初始化游标 (索引定位)
  │  session,       │     根据 indexConditions 设置起始/结束位置
  │  indexConditions│
  └───────┬────────┘
          │
          ├──── 游标无数据? ────→ ┌────────────────┐
          │                      │  AFTER_LAST     │
          │                      │  return false   │
          │                      └────────────────┘
          │
          ├──── cursor.next() ───→ ┌────────────────┐
          │    成功                │  FOUND          │
          │                       │  state = 0      │
          │                       └───────┬────────┘
          │                               │
          │                      ┌────────┴──────────┐
          │                      │                   │
          │              ┌──────────────┐   ┌──────────────────┐
          │              │  嵌套连接?   │   │  isOk(filter)?   │
          │              │   inner      │   │                  │
          │              │  next() 检查 │   │  通过 → 继续     │
          │              └──────┬───────┘   │  失败 → continue │
          │                     │          └──────────────────┘
          │                     ▼
          │           ┌──────────────────┐
          │           │  外连接?         │
          │           │  joinOuter=false │
          │           │  无匹配→NULL行   │
          │           └──────────────────┘
          │                     │
          │                     ▼
          │              ┌──────────────────┐
          │              │  isOk(join)?     │
          │              │  通过 → 继续     │
          │              │  失败 → continue │
          │              └──────┬───────────┘
          │                     │
          │                     ▼
          │              ┌──────────────────┐
          │              │  join.next()     │
          │              │  内表迭代        │
          │              │  失败 → continue │
          │              └──────────────────┘
          │                     │
          │                     ▼
          │              ┌──────────────────┐
          │              │  return true     │
          │              │  成功返回一行    │
          │              └──────────────────┘
          │
          └──── 后续 next() 调用 ────→ ┌────────────────┐
               (state == FOUND)        │  处理连接表    │
                                       │  join.next()   │
                                       │  或用 cursor   │
                                       │  读取下一行    │
                                       └────────────────┘
```
**图 8-94: TableFilter 完整生命周期状态机**

该图将 `TableFilter.next()` 方法的状态转移展开为完整的状态机模型。`BEFORE_FIRST` → `FOUND` → `AFTER_LAST` 是三个核心状态，对应游标的初始化、迭代和耗尽阶段。嵌套循环连接在 `FOUND` 状态下通过递归调用 `join.next()` 驱动内表迭代，而 `isOk(filterCondition)` 和 `isOk(joinCondition)` 在两个关键检查点执行条件过滤。

```text
状态转移场景示例
                        │
  场景 1: 正常扫描 (有数据)
                        │
  BEFORE_FIRST
    │ next() 首次调用
    ▼
  cursor.find() → cursor.next() = true
    │
    ▼
  FOUND
    │ isOk(filter) = true
    │ isOk(join) = true
    │ join.next() = true
    ▼
  return true (输出一行)
    │
    │ 后续 next() 调用
    ▼
  FOUND (state 不变)
    │ join.next() = true → return true
    │ join.next() = false → 进入 while 循环
    │ cursor.next() = true → FOUND, 重复
    │ cursor.next() = false
    ▼
  AFTER_LAST → return false (行耗尽)
                        │
  场景 2: 空结果集
                        │
  BEFORE_FIRST
    │ next() 首次调用
    ▼
  cursor.find() → cursor.isAlwaysFalse() = true
    │
    ▼
  AFTER_LAST → return false (立即返回无数据)
                        │
  场景 3: 过滤条件全部不匹配
                        │
  BEFORE_FIRST → cursor.find() → cursor.next() = true
    │
    ▼
  FOUND → isOk(filter) = false → continue
    │       重新进入 while 循环
    │       cursor.next() = true → FOUND
    │       isOk(filter) = false → continue
    │       ... (循环直到耗尽)
    │
    ▼
  AFTER_LAST → return false
```
**图 8-60: TableFilter 状态转移场景示例**

### 8.5.5 Nested Loop Join 执行模型

**图 8-61: 3 表嵌套循环连接的物理执行过程**

```text
3 表 Nested Loop Join 执行模型 (T1 → T2 → T3)
                        │
  外层循环 (T1):        │   中层循环 (T2):        │   内层循环 (T3):
                        │                         │
  T1.next()             │                         │
    │                   │                         │
    ├─ cursor.find()    │                         │
    ├─ cursor.next()    │                         │
    │  → row T1_1       │                         │
    │                   │                         │
    ├───────────────────┼── T2.reset()             │
    │                   │    │                     │
    │                   │    ├─ T2.next()          │
    │                   │    │  ├─ cursor.find(T1) │
    │                   │    │  │  (利用 T1 当前行  │
    │                   │    │  │  作为查找条件)    │
    │                   │    │  ├─ cursor.next()   │
    │                   │    │  │  → row T2_1      │
    │                   │    │  │                  │
    │                   │    │  ├──────────────────┼── T3.reset()
    │                   │    │  │                  │    │
    │                   │    │  │                  │    ├─ T3.next()
    │                   │    │  │                  │    │  ├─ cursor.find(T1,T2)
    │                   │    │  │                  │    │  ├─ cursor.next()
    │                   │    │  │                  │    │  │  → row T3_1
    │                   │    │  │                  │    │  │
    │                   │    │  │                  │    │  ├─ isOk(filter)
    │                   │    │  │                  │    │  │  → 通过
    │                   │    │  │                  │    │  │
    │                   │    │  │                  │    │  ├─ isOk(join)
    │                   │    │  │                  │    │  │  → 通过
    │                   │    │  │                  │    │  │
    │                   │    │  │                  │    │  └─ return true
    │                   │    │  │                  │    │     → 输出行
    │                   │    │  │                  │    │       [T1_1, T2_1, T3_1]
    │                   │    │  │                  │    │
    │                   │    │  │                  │    ├─ T3.next()
    │                   │    │  │                  │    │  → row T3_2
    │                   │    │  │                  │    │  → [...]
    │                   │    │  │                  │    │
    │                   │    │  │                  │    └─ T3.next() = false
    │                   │    │  │                  │       → T3 耗尽
    │                   │    │  │                  │
    │                   │    │  └─ T3 循环结束     │
    │                   │    │                     │
    │                   │    ├─ T2.next()          │
    │                   │    │  → row T2_2         │
    │                   │    │  → [...]            │
    │                   │    │                     │
    │                   │    └─ T2.next() = false  │
    │                   │       → T2 耗尽          │
    │                   │                          │
    ├─ T1.next()        │                          │
    │  → row T1_2       │                          │
    │  → [...]          │                          │
    │                   │                          │
    └─ T1.next() = false                            │
       → T1 耗尽                                   │
                                                   ▼
  输出行序列:
    [T1_1, T2_1, T3_1]    ← T1 第一行 → T2 第一行 → T3 第一行
    [T1_1, T2_1, T3_2]    ← T1 第一行 → T2 第一行 → T3 第二行
    [T1_1, T2_2, T3_1]    ← T1 第一行 → T2 第二行 → T3 第一行
    [T1_1, T2_2, T3_2]    ← T1 第一行 → T2 第二行 → T3 第二行
    [T1_2, T2_1, T3_1]    ← T1 第二行 → T2 第一行 → T3 第一行
    ...
```
**图 8-95: Nested Loop Join 3 表执行模型**

嵌套循环连接是 H2 唯一的连接算法。外层循环的每行触发中层循环的完整扫描，中层循环的每行触发内层循环的完整扫描，依此类推。执行顺序如同三层嵌套的 for 循环：

```text
for each row in T1:       ← 外层 (驱动表)
  for each row in T2:     ← 中层 (内表 1)
    for each row in T3:   ← 内层 (内表 2)
      if (filter condition and join condition):
        output row
```

关键优化点在于：内层表的 `cursor.find()` 可以利用外层表的当前行值作为查找条件。例如，T2 的索引扫描条件可能包含 `T2.foreign_key = T1.id`，当 T1 遍历到 `id=100` 的行时，T2 的游标自动定位到 `foreign_key=100` 的位置。这种**索引驱动的嵌套循环连接**避免了内层表的全表扫描，是 H2 连接性能的核心保障。

```text
Nested Loop Join 代价分析
                        │
  3 表连接 (T1 → T2 → T3), 每表 10000 行
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  场景 A: 全表扫描 (无索引)                                         │
  │                                                                     │
  │  T1 扫描: 10000 行                                                 │
  │  T2 扫描: 对 T1 每行 → 10000 × 10000 = 100,000,000 行             │
  │  T3 扫描: 对 T1,T2 每组合 → 10⁸ × 10000 = 10¹² 行                 │
  │                                                                     │
  │  总行比较: 约 10¹²                                                  │
  │  性能: 完全不可接受!                                               │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  场景 B: 索引驱动 (内表有索引)                                      │
  │                                                                     │
  │  T1 扫描: 100 行 (有过滤条件)                                      │
  │  T2 查找: 对 T1 每行 → 100 × O(log 10000) ≈ 100 × 14 = 1400      │
  │  T3 查找: 对每组合 → (100 × 5) × 14 ≈ 7000                       │
  │                                                                     │
  │  总操作: 约 8500 次                                                 │
  │  性能: 极快!                                                       │
  └────────────────────────────────────────────────────────────────────┘
                        │
  对比: 场景 A vs 场景 B
    全表扫描 NLJ: 10¹² 次操作 ≈ 数小时
    索引驱动 NLJ: 8500 次操作 ≈ 毫秒级
    差距: 超过 1 亿倍
                        │
  结论: Nested Loop Join 在内表无索引时性能灾难
        内表连接列必须有索引!
```
**图 8-62: Nested Loop Join 索引 vs 全表扫描代价对比**

### 8.5.6 内外连接处理对比

**图 8-63: INNER JOIN 与 LEFT JOIN 在 TableFilter 处理路径上的差异**

```text
INNER JOIN vs LEFT JOIN 处理路径对比

INNER JOIN (普通内连接):
  topFilter.next()
    │
    ├── cursor.find() → cursor.next()
    │   → 找到一行
    │
    ├── isOk(filterCondition)?
    │   ├── 通过 → 继续
    │   └── 失败 → continue (跳过此行)
    │
    ├── isOk(joinCondition)?
    │   ├── 通过 → 继续
    │   └── 失败 → continue (跳过此行)
    │
    └── join.reset() → join.next()
        ├── 找到匹配 → return true
        └── 无匹配 → continue (跳过此行)

LEFT JOIN (左外连接):
  topFilter.next()
    │
    ├── cursor.find() → cursor.next()
    │   → 找到一行
    │
    ├── nestedJoin 处理
    │   │
    │   ├── nestedJoin.next()?
    │   │   ├── 找到匹配 → 正常处理
    │   │   │
    │   │   └── 无匹配 → joinOuter 检查
    │   │         │
    │   │         ├── joinOuter && !foundOne?
    │   │         │   │
    │   │         │   ├── YES → setNullRow()
    │   │         │   │        为内表列填充 NULL 值
    │   │         │   │        返回一行 (含左侧真实值 + 右侧 NULL)
    │   │         │   │
    │   │         │   └── NO → continue (跳过此行)
    │   │         │
    │   │         └── 关键差异: 外连接不会丢弃左行!
    │   │             即使右侧无匹配, 左行仍然保留
    │   │
    │   └── (继续处理)
    │
    ├── isOk(filterCondition)
    └── return true

  NULL 行结构:
  ┌────────────────────────────────────────────┐
  │  LEFT JOIN orders ON ...                   │
  │                                            │
  │  customers.id  = 100   ← 左表真实值       │
  │  customers.name = 'X'  ← 左表真实值       │
  │  orders.id     = NULL  ← 右表填充 NULL    │
  │  orders.total  = NULL  ← 右表填充 NULL    │
  └────────────────────────────────────────────┘
```

**图 8-96: 内外连接处理路径对比**

INNER JOIN 与 LEFT JOIN 在行保留策略上有本质区别。INNER JOIN 要求内表必须有匹配行，无匹配时外层行被丢弃（`continue`）。LEFT JOIN 则保证左表所有行都出现在结果中——即使内表无匹配，左表行也被保留，内表列填充 NULL 值。

`setNullRow()` 方法是 LEFT JOIN 实现的关键。当 `nestedJoin.next()` 返回 false 且 `joinOuter=true` 且 `foundOne=false` 时，`setNullRow()` 将当前 TableFilter 的行数据全部置为 NULL，但外层的 `currentSearchRow` 保持不变。这样返回给上层的结果行中，左表列包含真实值，右表列全是 NULL。

```text
INNER JOIN vs LEFT JOIN 结果行对比示例
                        │
  表数据:
    customers (左表):                orders (右表):
    ┌────┬─────────┐                ┌────┬─────────────┬────────┐
    │ id │ name    │                │ id │ customer_id │ total  │
    ├────┼─────────┤                ├────┼─────────────┼────────┤
    │ 1  │ Alice   │                │ 1  │ 1           │ 100.00 │
    │ 2  │ Bob     │                │ 2  │ 1           │ 200.00 │
    │ 3  │ Charlie │                │ 3  │ 3           │ 150.00 │
    └────┴─────────┘                └────┴─────────────┴────────┘
                        │
  INNER JOIN 结果:
    SELECT * FROM customers c INNER JOIN orders o ON c.id = o.customer_id
    ┌────┬─────────┬──────┬─────────────┬────────┐
    │ id │ name    │ id   │ customer_id │ total  │
    ├────┼─────────┼──────┼─────────────┼────────┤
    │ 1  │ Alice   │ 1    │ 1           │ 100.00 │
    │ 1  │ Alice   │ 2    │ 1           │ 200.00 │
    │ 3  │ Charlie │ 3    │ 3           │ 150.00 │
    └────┴─────────┴──────┴─────────────┴────────┘
    Bob (id=2) 无匹配行 → 被丢弃
                        │
  LEFT JOIN 结果:
    SELECT * FROM customers c LEFT JOIN orders o ON c.id = o.customer_id
    ┌────┬─────────┬──────┬─────────────┬────────┐
    │ id │ name    │ id   │ customer_id │ total  │
    ├────┼─────────┼──────┼─────────────┼────────┤
    │ 1  │ Alice   │ 1    │ 1           │ 100.00 │
    │ 1  │ Alice   │ 2    │ 1           │ 200.00 │
    │ 2  │ Bob     │ NULL │ NULL        │ NULL   │ ← 保留左行, 右列填充 NULL
    │ 3  │ Charlie │ 3    │ 3           │ 150.00 │
    └────┴─────────┴──────┴─────────────┴────────┘
    Bob (id=2) 保留 → 右表列填充 NULL
```
**图 8-64: INNER JOIN vs LEFT JOIN 结果对比示例**

---

## 8.6 优化实践建议

### 8.6.1 索引设计原则

```text
等值条件优先
  │
  WHERE a = 1 AND b > 10
  │
  ├── 最优索引: INDEX(a, b) 或 INDEX(a)
  │     a 的等值条件可精确定位
  │     b 的范围条件在索引中连续扫描
  │
  └── 次优索引: INDEX(b)
        b 的范围条件只能扫描大量行
        a 的等值条件只能作为 filter
```

```text
索引设计原则详解
                        │
  核心原则: 等值条件列放在索引最左列
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  WHERE a = 1 AND b > 10                                           │
  │                                                                     │
  │  索引 (a, b):  定位 a=1, 范围扫描 b>10      ✅ 最佳               │
  │  索引 (a):     定位 a=1, 过滤 b>10          ✅ 良好               │
  │  索引 (b, a):  范围扫描 b>10, 过滤 a=1      ❌ 差                 │
  │  索引 (b):     范围扫描 b>10, 过滤 a=1      ❌ 最差               │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  WHERE a = 1 AND b = 2 AND c > 3                                  │
  │                                                                     │
  │  索引 (a, b, c): 定位 a=1,b=2, 范围 c>3    ✅ 最佳 (最左前缀)    │
  │  索引 (a, b):    定位 a=1,b=2, 过滤 c>3    ✅ 良好               │
  │  索引 (a, c, b): 定位 a=1, 范围 c>3, 过滤 b=2 ❌ 差 (b 走 filter) │
  └────────────────────────────────────────────────────────────────────┘
                        │
  更多原则:
    ├── 选择性高的列优先: 区分度高的列在前, 快速缩小范围
    ├── 避免冗余索引: (a) 和 (a, b) 同时存在时, (a) 通常可省略
    └── 索引不是越多越好: 每个索引增加 DML 维护成本
```
**图 8-65: 索引设计原则详解**

### 8.6.2 LIKE 与索引

LIKE 'prefix%'  → 可使用索引 (转为 START/END 条件)
LIKE '%suffix'  → 无法使用索引 (需要全扫描)
LIKE '%mid%'    → 无法使用索引 (需要全扫描)

```text
LIKE 模式与索引使用对照
                        │
  LIKE 模式转换过程:
    LIKE 'prefix%' → START(prefix) + END(prefix )
    → 索引范围扫描: 从 'prefix' 到 'prefix '
    → 效率等同于 col >= 'prefix' AND col < 'prefix '
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  LIKE 模式       索引可用    B+ 树行为                            │
  ├────────────────────────────────────────────────────────────────────┤
  │  'prefix%'       可用       范围扫描 (前缀匹配)                    │
  │  '%suffix'       不可用     无法确定起始位置 (后缀未知)            │
  │  '%mid%'         不可用     无法确定起始位置 (任意位置)            │
  │  'exact'         可用       等值查找 (无通配符时)                  │
  │  'pre_fix'       部分可用   通配符前的前缀可走索引                 │
  └────────────────────────────────────────────────────────────────────┘
                        │
  优化建议:
    ├── 优先使用前缀匹配 LIKE 'prefix%'
    ├── 后缀匹配 LIKE '%suffix' 考虑全文索引
    ├── 大文本搜索考虑第三方搜索引擎
    └── 必要时使用函数索引 (H2 支持虚拟列索引)
```
**图 8-66: LIKE 模式与索引使用对照**

### 8.6.3 JOIN 顺序

```sql
-- 建议: 选择性高的表在前
SELECT * FROM orders o
  JOIN customers c ON o.customer_id = c.id
  JOIN order_items i ON o.id = i.order_id
WHERE c.country = 'CN'
  AND o.status = 'PAID'
```

如图 8-59 所示，优化器选择逻辑：
- `customers` (country='CN' 选择性高，过滤后行数少) 排在前
- `orders` (status='PAID' 选择性中等) 排在中间
- `order_items` (无过滤条件) 排在最后

```text
JOIN 顺序优化可视化
                        │
  查询:
    SELECT * FROM orders o
      JOIN customers c ON o.customer_id = c.id
      JOIN order_items i ON o.id = i.order_id
    WHERE c.country = 'CN' AND o.status = 'PAID'
                        │
  优化前 (FROM 顺序):          优化后 (优化器选择):
  orders → customers → items   customers → orders → items
    │                            │
  10000 行                      │
    │                           c: 500 行 (country='CN')
    ↓                            │
  customers (无索引扫描)         ↓
    │                           o: 100 行 (关联 orders)
    10000 × 1 = 10000            │
    ↓                            ↓
  items                        i: 500 行 (关联 items)
    │                           │
    全表扫描 → 性能差            索引驱动 → 性能优
                        │
  优化原理:
    ├── customers 有过滤条件 country='CN'
    │   选择性高 → 先执行, 中间结果小
    ├── orders 有 status='PAID' 过滤
    │   选择性中等 → 中间执行
    └── order_items 无过滤条件
        最后执行, 通过索引连接
```
**图 8-67: JOIN 顺序优化可视化**

### 8.6.4 IN 列表优化

如图 8-67 所示，对于 `IN` 常量列表，H2 使用 `ConditionInConstantSet` 转化为哈希集合：

```sql
WHERE id IN (1, 2, 3, 100, 200)
  │
  └── ConditionInConstantSet: {1, 2, 3, 100, 200} → HashSet
        ├── 可配合索引使用
        └── 常量越多优势越大
```
```text
IN 列表优化原理
                        │
  SQL: WHERE id IN (1, 2, 3, 100, 200)
                        │
  优化前: 逐 OR 比较
    id = 1 OR id = 2 OR id = 3 OR id = 100 OR id = 200
    → 对每行执行 5 次比较
    → O(n × m) 其中 n=行数, m=IN 列表大小
                        │
  优化后: 哈希集合
    ConditionInConstantSet 创建 HashSet
    → contains() 检查: O(1) 每次
    → set.contains(id) → 快速判断
                        │
  性能对比:
    ┌────────────────────────────────────────────────────────────────────┐
    │  IN 列表大小    OR 比较 (每行)    哈希集合 (每行)   加速比       │
    ├────────────────────────────────────────────────────────────────────┤
    │  5             5 次比较          1 次哈希          5x            │
    │  10            10 次比较         1 次哈希          10x           │
    │  100           100 次比较        1 次哈希          100x          │
    │  1000          1000 次比较       1 次哈希          1000x         │
    └────────────────────────────────────────────────────────────────────┘
                        │
  注意: IN 列表可与索引配合使用
    WHERE id IN (1, 2, 3) → 索引范围扫描
    WHERE name IN ('a', 'b') → 非唯一索引 + 哈希过滤
```
**图 8-68: IN 列表优化原理**

### 8.6.5 EXPLAIN PLAN

如图 8-68 所示，使用 `EXPLAIN` 查看执行计划：

```sql
EXPLAIN SELECT t.name FROM test t WHERE t.id = 1;
-- SELECT
--     "T"."NAME"
-- FROM "PUBLIC"."TEST" "T"
-- /* public.test.tableScan */
-- WHERE "T"."ID" = 1
```

注释部分显示使用的索引（`tableScan` 表示全表扫描）。

```sql
EXPLAIN SELECT t.name FROM test t WHERE t.name = 'John';
-- SELECT
--     "T"."NAME"
-- FROM "PUBLIC"."TEST" "T"
-- /* public.test.idx_name */
-- WHERE "T"."NAME" = 'John'
```

此处显示使用了 `idx_name` 索引。

```text
EXPLAIN 输出解读对比
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  输出中的索引注释          含义                     建议           │
  ├────────────────────────────────────────────────────────────────────┤
  │  tableScan               全表扫描                  需要建索引      │
  │  schema.table.index_name 使用了索引                OK             │
  │  (无注释)                可能是子查询或表达式      检查执行计划    │
  └────────────────────────────────────────────────────────────────────┘
                        │
  如何通过 EXPLAIN 诊断性能问题:
                        │
  问题 1: 期望使用索引但显示 tableScan
    原因: 查询条件不满足最左前缀原则
    解决: 检查索引列顺序是否与 WHERE 条件匹配
                        │
  问题 2: 使用了索引但查询仍慢
    原因: 索引选择性差 (匹配行太多)
    解决: 增加更精确的条件或创建复合索引
                        │
  问题 3: JOIN 查询显示内表 tableScan
    原因: 连接列缺少索引
    解决: 在连接列上创建索引 (紧急!)
```
**图 8-69: EXPLAIN 输出解读与诊断**
```text
EXPLAIN 输出结构分解 — 注释字段含义
                        │
  EXPLAIN SELECT t.name FROM test t WHERE t.id = 1;
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  SELECT                                                         │
  │      "T"."NAME"                   ← 投影列 (SELECT 子句)         │
  │  FROM "PUBLIC"."TEST" "T"         ← 数据源 (FROM 子句)           │
  │  /* public.test.tableScan */     ← 访问方法注释                  │
  │  WHERE "T"."ID" = 1              ← 过滤条件 (WHERE 子句)         │
  └─────────────────────────────────────────────────────────────────┘
                        │
  注释字段 /* ... */ 的格式:
    ┌─────────────────────────────────────────────────────────────┐
    │  /* schema.table.access_method */                            │
    │                                                              │
    │  schema:   数据库 Schema (通常为 PUBLIC)                      │
    │  table:    表名                                              │
    │  access_method: 访问方法                                      │
    │    ├── tableScan        → 全表扫描 (无可用索引)                │
    │    ├── index_name        → 使用指定索引                        │
    │    └── (无注释)           → 可能是子查询或函数表达式             │
    └─────────────────────────────────────────────────────────────┘
                        │
  多表连接时的 EXPLAIN 输出:
                        │
  EXPLAIN SELECT * FROM t1, t2 WHERE t1.id = t2.ref;
                        │
  SELECT
      "T1"."ID", "T2"."REF", ...
  FROM "PUBLIC"."T1" "T1"
  /* PUBLIC.T1.tableScan */     ← t1 的访问方法 (驱动表, 全表扫描)
  INNER JOIN "PUBLIC"."T2" "T2"
  /* PUBLIC.T2.idx_ref */       ← t2 的访问方法 (内表, 使用索引)
  ON 1=1
  WHERE "T1"."ID" = "T2"."REF"
```
**图 8-70: EXPLAIN 输出结构分解 — 注释字段含义**

### 8.6.6 常见优化检查表

| 场景 | 检查项 | 说明 |
|------|--------|------|
| WHERE 条件 | 是否有索引覆盖等值列 | 等值条件应放在索引最左列 |
| JOIN | 连接列是否有索引 | 内表的连接列必须建索引 |
| LIKE | 是否以前缀开头 | `'prefix%'` 可用索引 |
| 排序 | ORDER BY 列是否在索引中 | 避免文件排序 |
| 分组 | GROUP BY 列是否在索引中 | 索引分组排序优化 |
| 子查询 | 能否改写为 JOIN | JOIN 通常更高效 |
| IN 列表 | 是否为常量列表 | 常量列表用哈希集合优化 |

```text
常见优化问题诊断流程
                        │
  查询慢? → EXPLAIN 查看执行计划
    │
    ├── 显示 tableScan?
    │     ├── YES → WHERE 条件有索引吗?
    │     │     ├── NO  → 创建索引
    │     │     └── YES → 索引列顺序匹配吗?
    │     │           ├── YES → 索引选择性高吗?
    │     │           │     ├── YES → 检查是否被函数/类型转换阻止
    │     │           │     └── NO  → 考虑复合索引
    │     │           └── NO  → 调整索引列顺序
    │     └── NO → 索引扫描但慢?
    │           ├── YES → 检查索引选择性
    │           └── NO  → 检查 JOIN 条件和 WHERE 过滤
    │
    ├── JOIN 查询慢?
    │     ├── 内表连接列有索引吗?
    │     │     ├── NO  → 立即创建索引! (紧急)
    │     │     └── YES → 驱动表选择是否最优?
    │     │           └── 将选择性高的表前置
    │
    ├── ORDER BY 慢?
    │     ├── ORDER BY 列在索引中吗?
    │     └── NO → 创建包含排序列的复合索引
    │
    └── GROUP BY 慢?
          ├── GROUP BY 列在索引中吗?
          └── NO → 创建包含分组列的复合索引
```
**图 8-71: 常见优化问题诊断流程**
```text
优化优先级排序 — 不同优化手段的性价比
                        │
  ┌──────────────────────────────────────────────────────────────────────┐
  │  优先级                                 预期效果    实施成本           │
  │  ──────────────────────────────────────  ────────  ────────           │
  │                                                                      │
  │  P0 — 紧急 (必须立即修复)                                              │
  │    ├── JOIN 内表连接列缺少索引          10-1000×   低 (CREATE INDEX) │
  │    ├── WHERE 条件列无索引               5-100×     低                │
  │    └── 全表扫描大表                     10-100×   低                │
  │                                                                      │
  │  P1 — 重要 (应尽快优化)                                                │
  │    ├── 索引列顺序不匹配 WHERE 条件       2-10×     低                │
  │    ├── ORDER BY 无索引覆盖              2-5×      低                │
  │    ├── GROUP BY 无索引覆盖              2-5×      低                │
  │    └── 子查询可改写为 JOIN              1.5-3×    中 (SQL 改写)     │
  │                                                                      │
  │  P2 — 建议 (性能调优)                                                  │
  │    ├── IN 列表过长 (改为临时表 JOIN)    1.5-2×    中                │
  │    ├── LIKE 前缀通配符 ('%abc')          2-5×     低 (SQL 改写)     │
  │    ├── 函数/类型转换阻止索引            1.5-3×    低 (SQL 改写)     │
  │    └── SELECT * 可改为列清单             1.2-1.5×  低                │
  │                                                                      │
  │  P3 — 高级 (覆盖扫描优化)                                              │
  │    ├── 创建覆盖索引 (含 SELECT 列)       1.2-2×    中 (更大索引)     │
  │    └── 表分区 (超大型表)                 1.5-3×    高 (架构变更)     │
  └──────────────────────────────────────────────────────────────────────┘
                        │
  诊断工作流建议:
    1. EXPLAIN 查看所有慢查询的执行计划
    2. 优先修复 P0 问题 (JOIN 和 WHERE 的索引缺失)
    3. 检查索引列顺序是否匹配查询模式
    4. 分析覆盖索引的收益是否大于额外存储开销
    5. 定期复查索引使用情况, 移除未使用的索引
```
**图 8-72: 优化优先级排序 — 不同优化手段的性价比**

### 8.6.7 索引设计完整决策树

**图 8-73: 基于查询模式的索引设计决策流程**

```text
索引设计决策树
                        │
  查询模式分析
    │
    ├── WHERE 条件分析:
    │     │
    │     ├── 是否有等值条件 (col = value)?
    │     │     ├── YES → 将等值列放在索引最左前缀
    │     │     └── NO  → 考虑范围条件列
    │     │
    │     ├── 是否有范围条件 (col > value, col BETWEEN)?
    │     │     ├── YES → 放在等值列之后
    │     │     └── NO  → 考虑排序列
    │     │
    │     └── 是否有排序条件 (ORDER BY col)?
    │           ├── YES → 如果索引已包含排序列, 避免文件排序
    │           └── NO  → 考虑 SELECT 列
    │
    ├── SELECT 列分析:
    │     │
    │     └── SELECT 列是否都在索引中?
    │           ├── YES → 索引覆盖扫描 (Index-Only Scan)
    │           └── NO  → 需要回表访问
    │
    └── 决策结果:

  ┌─────────────────────────────────────────────────────────────┐
  │  WHERE a=1 AND b>10 ORDER BY c                              │
  │                                                             │
  │  最优: 复合索引(a, c, b) 或 (a, b, c)                       │
  │  ├── a: 等值条件 → 索引最左列                               │
  │  ├── c: 排序列 → 索引第二列 (避免文件排序)                   │
  │  └── b: 范围条件 → 索引第三列 (范围扫描)                     │
  │                                                             │
  │  备选: 索引(a) + 文件排序                                    │
  │  备选: 单独索引(b) (不推荐, 范围扫描代价高)                  │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  WHERE status='PAID' AND created_at > '2024-01-01'         │
  │  SELECT id, status, amount                                  │
  │                                                             │
  │  最优: 索引(status, created_at, amount)                     │
  │  ├── status: 等值条件, 过滤大量行, 可大幅缩小范围           │
  │  ├── created_at: 范围条件, 进一步缩小                       │
  │  └── amount: 包含在索引中, 实现覆盖扫描                     │
  │                                                             │
  │  次优: 单独索引(status) + 回表读取 created_at 和 amount     │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  JOIN orders ON orders.customer_id = customers.id           │
  │                                                             │
  │  必须: orders.customer_id 上有索引                          │
  │  原因: 对 customers 的每行, 需要在 orders 中快速查找        │
  │  无索引时: 对每行 customer, 全表扫描 orders → 性能灾难     │
  └─────────────────────────────────────────────────────────────┘
```
**图 8-97: 索引设计完整决策树**

该图提供了从查询模式到索引设计的完整决策路径。核心原则：

1. **等值条件列优先放在索引最左列**：等值条件可以将 B+ 树定位到精确的叶子节点，过滤效果最好
2. **排序列紧随等值列之后**：如果索引顺序与 ORDER BY 一致，可以避免文件排序
3. **范围条件放在最后**：范围条件只能匹配索引的一列，之后的索引列无法参与条件匹配
4. **SELECT 列尽量包含在索引中**：实现索引覆盖扫描，避免回表 I/O
5. **JOIN 连接列必须有索引**：否则嵌套循环连接退化为全表扫描，性能灾难

```text
索引设计决策速查表
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  查询模式                     推荐索引策略           覆盖列        │
  ├─────────────────────────────────────────────────────────────────────┤
  │  WHERE a = 1                  INDEX(a)               a            │
  │  WHERE a = 1 AND b = 2       INDEX(a, b)            a, b          │
  │  WHERE a = 1 ORDER BY c      INDEX(a, c)            a, c          │
  │  WHERE a > 1 ORDER BY b      INDEX(a, b)            a, b          │
  │  WHERE a = 1 AND b > 2       INDEX(a, b)            a, b          │
  │  WHERE a LIKE 'pre%'          INDEX(a)               a             │
  │  JOIN t ON t.a = t2.b        INDEX(a) (在 t 表)     a             │
  │  SELECT a, b WHERE a = 1     INDEX(a, b)            a, b (覆盖)   │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  反模式 (应避免的设计):
    ├── 过多单列索引: INDEX(a), INDEX(b), INDEX(c)
    │    → 应合并为复合索引 INDEX(a, b, c)
    │
    ├── 索引列顺序不当: INDEX(b, a) 当查询是 a = 1 AND b = 2
    │    → 等值条件 a 应在前
    │
    └── 索引不包含 SELECT 列: SELECT a, b 索引 INDEX(a)
          → 改为 INDEX(a, b) 实现覆盖扫描
```
**图 8-74: 索引设计决策速查表**

### 8.6.8 执行计划可视化解构

**图 8-75: 通过 EXPLAIN 输出的注释解读 H2 的执行计划**

```text
EXPLAIN 输出解读

示例 1: 全表扫描
  EXPLAIN SELECT * FROM test WHERE name = 'John';
  ─────────────────────────────────────────────────────────────
  SELECT
      "TEST"."ID",
      "TEST"."NAME",
      "TEST"."STATUS"
  FROM "PUBLIC"."TEST" "TEST"       /* PUBLIC.TEST.tableScan */
  WHERE "TEST"."NAME" = 'John'
  ─────────────────────────────────────────────────────────────
  索引注释解读: tableScan
    ├── 没有合适的索引可以使用
    ├── 执行方式: 顺序扫描全部数据行
    └── 每次读取一行 → 检查 name='John' → 匹配则返回

示例 2: 索引扫描
  EXPLAIN SELECT * FROM test WHERE name = 'John';
  (假设 name 上有索引 idx_name)
  ─────────────────────────────────────────────────────────────
  SELECT
      "TEST"."ID",
      "TEST"."NAME",
      "TEST"."STATUS"
  FROM "PUBLIC"."TEST" "TEST"       /* PUBLIC.TEST.idx_name */
  WHERE "TEST"."NAME" = 'John'
  ─────────────────────────────────────────────────────────────
  索引注释解读: idx_name
    ├── 使用索引 idx_name 进行查找
    ├── 执行方式: B+ 树定位 → 回表读取完整行
    ├── I/O 成本: 索引树深度次索引页读取 + 数据页读取
    └── 适用于: 等值匹配或前缀范围匹配

示例 3: 索引覆盖扫描
  EXPLAIN SELECT name FROM test WHERE name = 'John';
  (假设 name 上有索引 idx_name)
  ─────────────────────────────────────────────────────────────
  SELECT
      "TEST"."NAME"
  FROM "PUBLIC"."TEST" "TEST"       /* PUBLIC.TEST.idx_name */
  WHERE "TEST"."NAME" = 'John'
  ─────────────────────────────────────────────────────────────
  差异: SELECT 仅包含 name 列
    ├── idx_name 索引包含 name 列
    ├── 无需回表: 直接从索引读取 name 值
    └── I/O 成本: 仅索引页读取 (比示例 2 少一次数据页读取)

示例 4: 多表连接
  EXPLAIN SELECT * FROM customers c
    JOIN orders o ON c.id = o.customer_id
    WHERE c.country = 'CN';
  ─────────────────────────────────────────────────────────────
  SELECT
      ...
  FROM "PUBLIC"."CUSTOMERS" "C"    /* PUBLIC.CUSTOMERS.idx_country */
      INNER JOIN "PUBLIC"."ORDERS" "O" /* PUBLIC.ORDERS.idx_customer */
  WHERE "C"."COUNTRY" = 'CN'
  ─────────────────────────────────────────────────────────────
  解读:
    ├── CUSTOMERS 使用 idx_country 过滤 country='CN'
    ├── ORDERS 使用 idx_customer 进行连接查找
    └── 执行顺序: CUSTOMERS (驱动表) → ORDERS (内表)
```
**图 8-98: 执行计划可视化解构**

EXPLAIN 输出的注释部分是理解 H2 执行计划的关键。注释格式为 `/* schema.table.索引名 */`，其中索引名指示了优化器选择的访问路径。`tableScan` 表示全表扫描，是优化器无法使用索引时的兜底策略。通过对比不同查询的 EXPLAIN 输出，可以快速定位索引设计中的问题——例如，预期使用索引但实际显示 `tableScan`，通常意味着索引列顺序与查询条件不匹配。

```text
EXPLAIN 输出快速解读卡
                        │
  输出格式: /* schema.table.索引名 */
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  索引名                   含义                        行动          │
  ├─────────────────────────────────────────────────────────────────────┤
  │  tableScan               全表扫描                     检查索引      │
  │  PRIMARY_KEY_XX          主键索引                     OK            │
  │  <索引名>                普通/唯一索引                 OK            │
  │  sys:<编号>              系统内部索引                 通常 OK       │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  常见 EXPLAIN 场景识别:
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  场景 1: 索引缺失                                                  │
  │  SELECT * FROM t WHERE name = 'x'                                  │
  │  → /* PUBLIC.T.tableScan */                                        │
  │  → 建议: 在 name 列上创建索引                                      │
  │                                                                     │
  │  场景 2: 最左前缀不匹配                                             │
  │  SELECT * FROM t WHERE b = 1                                       │
  │  索引: INDEX(a, b)                                                  │
  │  → /* PUBLIC.T.tableScan */                                        │
  │  → 原因: 查询未使用前缀列 a, 索引不可用                            │
  │  → 建议: 创建 INDEX(b) 或调整查询                                  │
  │                                                                     │
  │  场景 3: 索引选择性差                                               │
  │  SELECT * FROM t WHERE status = 'ACTIVE'                           │
  │  索引: INDEX(status) (50% 行是 ACTIVE)                             │
  │  → /* PUBLIC.T.idx_status */                                       │
  │  → 虽然使用了索引, 但因匹配行太多, 可能不如全表扫描                │
  │  → 建议: 增加额外条件或创建复合索引                                │
  └─────────────────────────────────────────────────────────────────────┘
```
**图 8-76: EXPLAIN 输出快速解读卡**

### 8.6.9 优化器工作流与调优总结

**图 8-77: 查询优化器的完整工作流总结为从 SQL 到执行计划的流水线**

```text
H2 查询优化器完整工作流
                        │
  ┌────────────────────────────────────────────────────────────┐
  │  阶段 1: 解析                                               │
  │  SQL ──→ Parser.parse(sql) ──→ 抽象语法树 (AST)             │
  │  产出: Select / Insert / Update / Delete 等 Prepared 对象  │
  └──────────────────────────┬─────────────────────────────────┘
                             │
  ┌──────────────────────────▼─────────────────────────────────┐
  │  阶段 2: 语义分析                                           │
  │  Select.init()                                              │
  │    ├── expandSelectList()   ← 展开 SELECT *                 │
  │    ├── mapColumns()         ← 列名绑定到 TableFilter        │
  │    ├── resolveTypes()       ← 确定每列的数据类型            │
  │    └── createIndexConditions() ← 提取索引可用条件           │
  └──────────────────────────┬─────────────────────────────────┘
                             │
  ┌──────────────────────────▼─────────────────────────────────┐
  │  阶段 3: 优化                                               │
  │  Select.preparePlan() → Optimizer.optimize()                │
  │    ├── 连接顺序选择: 暴力/贪心/遗传                          │
  │    ├── 索引选择: 掩码匹配 → 代价最小化                       │
  │    └── 计划组装: topFilter 链 + PlanItem 配置               │
  └──────────────────────────┬─────────────────────────────────┘
                             │
  ┌──────────────────────────▼─────────────────────────────────┐
  │  阶段 4: 执行                                               │
  │  Select.queryWithoutCache()                                 │
  │    ├── topTableFilter.next() 循环                           │
  │    ├── cursor.find() → cursor.next() → 索引驱动扫描         │
  │    ├── isOk(filterCondition) → 过滤条件检查                 │
  │    ├── isOk(joinCondition) → 连接条件检查                   │
  │    ├── join.next() → 内表嵌套循环                           │
  │    └── expressions.getValue() → 列值求值                    │
  └──────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                       结果集输出
                        │
  优化器调优清单:
    │
    ├── [ ] 检查 EXPLAIN 输出, 确认使用了预期索引
    ├── [ ] 将等值条件列放在复合索引的最左列
    ├── [ ] 将选择性高的表的条件放在 WHERE 前面
    ├── [ ] JOIN 连接列是否有索引? (内表必须有索引)
    ├── [ ] ORDER BY 是否能利用索引排序? (避免文件排序)
    ├── [ ] 子查询能否改写为 JOIN? (通常更高效)
    ├── [ ] 是否使用了 SELECT *? (仅选择需要的列)
    ├── [ ] LIKE 是否以前缀开头? ('prefix%' 可用索引)
    └── [ ] 索引列是否过多? (维护成本 vs 查询收益)
```
**图 8-99: 优化器完整工作流与调优总结**

该图将查询执行的完整流程总结为四个阶段：解析、语义分析、优化和执行，并提供了优化器调优的实用清单。优化器调优的核心思想是"帮助优化器做出更好的选择"——通过合理创建索引、优化查询写法、使用 EXPLAIN 验证执行计划，将查询性能提升到最优。

```text
优化效果量化对比
                        │
  以一个典型 Web 查询为例:
    SELECT o.*, c.name, i.product_name
    FROM orders o
      JOIN customers c ON o.customer_id = c.id
      JOIN order_items i ON o.id = i.order_id
    WHERE c.email = 'user@example.com'
      AND o.status = 'PAID'
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  优化级别          执行方式                       响应时间        │
  ├────────────────────────────────────────────────────────────────────┤
  │  无优化            全表扫描全部表                  30 秒+         │
  │  基本索引          内表连接列建索引                500 毫秒       │
  │  复合索引          等值列复合索引                  10 毫秒        │
  │  覆盖索引          SELECT 列在索引中               2 毫秒         │
  └────────────────────────────────────────────────────────────────────┘
                        │
  优化收益总结:
    ├── 索引优化: 从 30 秒到 500 毫秒 (60x)
    ├── 复合索引: 从 500 到 10 毫秒 (50x)
    ├── 覆盖索引: 从 10 到 2 毫秒 (5x)
    └── 总优化: 从 30 秒到 2 毫秒 (15000x)
```
**图 8-78: 优化效果量化对比**

> **参考**: H2 官方文档《Performance》(`h2/src/docsrc/html/performance.html#explain_plan`)
> 描述了如何使用 EXPLAIN PLAN 分析查询执行计划并进行调优。

---

## 8.7 ASCII 优化流程图

```text
优化器全流程总览
                        │
  输入: SQL 查询
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  阶段 1: 解析与条件提取                                            │
  │    Parser → Expression Tree → createIndexConditions()              │
  │    产出: TableFilter 列表 + IndexCondition 数组                    │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  阶段 2: 连接顺序优化                                              │
  │    calculateBestPlan()                                             │
  │      ├── 单表: testPlan()                                          │
  │      ├── ≤7: 暴力枚举 n! 排列                                     │
  │      └── ≥8: 混合策略 + 遗传算法                                   │
  │    产出: bestPlan (最优连接顺序 + 索引选择)                        │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  阶段 3: 执行                                                      │
  │    topTableFilter.next() 循环                                       │
  │      ├── cursor.find() → 索引定位                                  │
  │      ├── cursor.next() → 行迭代                                    │
  │      ├── isOk(filterCondition) → 过滤                              │
  │      ├── isOk(joinCondition) → 连接条件                            │
  │      ├── join.next() → 内表循环                                    │
  │      └── getValue() → 列值求值                                    │
  │    产出: 结果行                                                    │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  输出: 结果集 (Result Set)
```
**图 8-79: 优化器全流程总览**
```text

SQL WHERE 子句
    │
    ▼
  Parser 解析 WHERE 条件
    │
    ├── 拆解为 Comparison、ConditionAndOr 等表达式树
    ├── mapColumns() 将列引用绑定到 TableFilter
    └── createIndexConditions() 提取索引可用条件
    │
    ▼
  每个 TableFilter 提取 IndexConditions:
    │
    ├── WHERE T1.a=1 AND T1.b>5 AND T2.c='x'
    │
    ├── T1.indexConditions:
    │     ├── [a, EQUALITY, value=1]
    │     └── [b, START, value=5]
    │
    └── T2.indexConditions:
          └── [c, EQUALITY, value='x']
    │
    ▼
  对每个表遍历索引:
    ┌─────────────────────────────────────────────┐
    │ TableFilter.getBestPlanItem()               │
    │                                             │
    │  1. 构建 masks 数组                          │
    │     mask[columnId] |= condition.getMask()   │
    │                                             │
    │  2. 对每个索引:                              │
    │     a. 比对 masks 与索引列                    │
    │     b. 调用 index.getCost() 估算代价          │
    │     c. 选择最低代价索引                       │
    │                                             │
    │  3. 代价调整:                                │
    │     cost -= cost × conditionsCount / 100    │
    │     / (filter + 1)                          │
    └─────────────────────────────────────────────┘
    │
    ▼
  枚举连接顺序:
    │
    ├── 1 个表: 直接评估
    │
    ├── ≤7 个表: 暴力枚举 O(n!)
    │     ├── 生成所有排列
    │     ├── 计算每个 Plan 的代价
    │     └── 选择总代价最低的
    │
    └── ≥8 个表: 混合 + 遗传
          ├── 混合: 暴力前 m 个 + 贪心填充剩余
          ├── 遗传: 随机变异 × 500 轮
          └── 取两者中的最优
    │
    ▼
  选中最优 Plan:
    │
    ├── topTableFilter = plan.filters[0]
    ├── 链接 TableFilter 链 (addJoin)
    └── 设置每个 TableFilter 的 PlanItem (索引 + 掩码)
    │
    ▼
  执行阶段:
    │
    ┌─────────────────────────────────────────────┐
    │ topTableFilter.next() 循环                   │
    │                                             │
    │  while (topTableFilter.next()):             │
    │    ├── cursor.find()  → 索引定位             │
    │    ├── cursor.next()  → 读取下一行            │
    │    ├── isOk(filterCondition) → 过滤           │
    │    ├── isOk(joinCondition)  → 连接条件        │
    │    ├── join.next()       → 内表迭代           │
    │    └── row[i] = expressions[i].getValue()   │
    │        → 最终结果行                          │
    └─────────────────────────────────────────────┘
    │
    ▼
  结果返回给 JDBC
```

### 8.7.1 优化器全流程集成

**图 8-80: 第 8 章讨论的所有优化器组件集成为一个完整的架构视图，展示从查询接收到执行计划产出的完整数据流**

```text
优化器全流程集成架构
                        │
  SQL 查询 ──→ Parser 解析
                        │
                        ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Select.preparePlan()                                        │
  │                                                              │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 1: createIndexConditions()                       │  │
  │  │    输入: WHERE t1.a=1 AND t1.b>5 AND t2.c='x'        │  │
  │  │    输出:                                                │  │
  │  │      T1.indexConditions ← [a:EQUALITY, b:START]       │  │
  │  │      T2.indexConditions ← [c:EQUALITY]                 │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 2: new Optimizer(topArray, condition, session)   │  │
  │  │    输入: TableFilter[] = [T1, T2, T3]                 │  │
  │  │    常量: MAX_BRUTE_FORCE_FILTERS=7                    │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 3: calculateBestPlan()                          │  │
  │  │    决策: 表数 = 3 ≤ 7 → 暴力枚举                       │  │
  │  │    枚举 3! = 6 种排列                                  │  │
  │  │    for each 排列:                                      │  │
  │  │      Plan = new Plan(filters, condition)               │  │
  │  │      cost = Plan.calculateCost(session, ...)           │  │
  │  │    bestPlan = 最低 cost 的排列                          │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 4: Plan.calculateCost()                         │  │
  │  │    cost = 1                                            │  │
  │  │    i=0: T1.cost=10, cost=1+1×10=11                    │  │
  │  │    i=1: T2.cost=5,  cost=11+11×5=66                   │  │
  │  │    i=2: T3.cost=2,  cost=66+66×2=198                  │  │
  │  │    return PlanItem[cost=198]                           │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 5: TableFilter.getBestPlanItem()                 │  │
  │  │    输入: indexConditions → masks 数组                  │  │
  │  │    过程: 遍历所有索引 → 掩码匹配 → 代价估算            │  │
  │  │    输出: PlanItem{index: IDX_AB, cost: 10}            │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 6: 结果组装                                      │  │
  │  │    topFilter = bestPlan.filters[0]                     │  │
  │  │    linkJoin(topFilter, T2, T3)                         │  │
  │  │    for each f: f.setPlanItem(planItem)                 │  │
  │  │    输出: topFilter → T2 → T3 (已配置索引和条件)        │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  └──────────────────────────────┼───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  执行阶段: Select.queryWithoutCache()                       │
  │    topTableFilter.next()循环                                 │
  │      → cursor.find(masks)  ← 使用 PlanItem 的索引和掩码    │
  │      → cursor.next()       ← 游标遍历                      │
  │      → isOk(filter)       ← WHERE 条件求值                 │
  │      → join.next()        ← 内表嵌套循环                   │
  │      → expressions[i].getValue() ← SELECT 列求值            │
  └──────────────────────────────────────────────────────────────┘
```
**图 8-100: 优化器全流程集成架构**

该图将第 8 章讨论的所有优化器组件——索引条件提取、连接顺序策略、代价计算、索引选择和结果组装——集成为一个完整的六步流水线。每一步的输入、输出和核心逻辑都展示在图中，形成了一个从原始 SQL 到可执行计划的端到端视图。优化器本质上是一个转换器：将逻辑的 SQL 查询（声明式）转换为物理的执行计划（过程式），并在转换过程中通过代价模型选择最优的物理实现。

```text
优化器核心数据流
                        │
  从 SQL 到执行计划的关键数据变换:
                        │
  SQL 文本
    │ Parser 解析
    ▼
  抽象语法树 (AST)
    │ Select.init() → mapColumns() → resolveTypes()
    ▼
  Prepared Select 对象
    │ createIndexConditions()
    ▼
  TableFilter[] + IndexCondition[]
    │ Optimizer.optimize() → calculateBestPlan()
    ▼
  Plan (bestPlan)
    │ plan.calculateCost() → 遍历 allFilters
    ▼
  PlanItem[] (每个表的最优索引和代价)
    │ setPlanItem() + linkJoin()
    ▼
  可执行计划 (topFilter → T2 → T3 ...)
    │ Select.queryWithoutCache()
    ▼
  结果集
                        │
  关键决策点:
    ├── createIndexConditions(): 哪些条件可通过索引定位?
    ├── calculateBestPlan(): 哪种连接顺序代价最低?
    ├── getBestPlanItem(): 哪个索引最适合当前表?
    └── canStop(): 搜索是否已产生足够好的计划?
```

**图 8-81: 优化器核心数据流**

---

## 8.8 本章小结

如图 8-81 所示，前面第7章完整追踪了一条 SQL 从 JDBC 到存储层的全部流程。核心链路由三个阶段组成：

1. **准备阶段**：`JdbcStatement` 发起 `prepareCommand()`，经 `SessionLocal.prepareLocal()` 到 `Parser` 解析为语法树，再通过 `Select.init()` 和 `Select.prepare()` 完成语义分析和计划生成
2. **缓存复用**：`queryCache`（`SmallLRUCache`）对相同 SQL 文本缓存已编译的 `CommandContainer`，减少重复解析代价
3. **执行阶段**：`CommandContainer.query()` 调用 `Select.queryWithoutCache()`，驱动 `TableFilter.next()` 迭代循环，通过 `Expression.getValue()` 多态求值输出结果行

第 8 章深入了查询优化器的三个核心引擎：

1. **连接顺序策略**：根据表数量动态选择 — 单表直接评估、`≤7` 表暴力枚举全排列、`≥8` 表混合暴力+贪心+遗传三种策略的组合
2. **代价模型**：`Plan.calculateCost()` 使用复合乘法公式 `cost = cost + cost × item_cost` 累计估计，无效计划标记为无穷大代价
3. **索引选择**：`TableFilter.getBestPlanItem()` 通过掩码匹配 `IndexCondition` 与索引列，选取 `Index.getCost()` 最低的索引，并通过代价调整使条件更多的表优先执行

---

## 8.x 延展阅读

- H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html`) — 结果集处理和大对象存储说明
- H2 官方文档《Performance》(`h2/src/docsrc/html/performance.html#database_performance_tuning`) — 数据库性能调优指南
- 本书第6章§6.8《Optimizer — 查询优化器》 — 优化器连接顺序选择算法
- 本书第6章§6.10《Parser — 递归下降解析》 — SQL 解析的底层实现
- 本书第5章§5.1-5.4 — DML 流程入口与 Command 层的关系
