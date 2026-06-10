# 第3章 核心包结构详解

> **本章导读**: 本章对 H2 的 `org.h2` 主包按功能层次进行拆解，逐层分析 JDBC、Engine、Command、Expression、Table/Index、MVStore、FileSystem 和 Server 共八个层的包结构、核心类职责和依赖关系。
> **前置知识**: 第1-2章《总体架构与分层模块划分》
> **章节要点**:
> - 了解各核心包的类组成和依赖关系
> - 掌握每层的关键类及其职责
> - 理解包之间的依赖方向和层次关系
> - 熟悉工具子包的功能分类

> 本章按第2章《分层模块划分》定义的八层架构（接入层（JDBC+Server）→ 引擎层 → SQL 处理层（Command+Expression）→ 存储抽象层（Table/Index）→ 存储引擎层（MVStore）→ 文件系统层）逐层展开，对每一层涉及的 `org.h2.*` 子包及关键类进行深度解析。部分核心流程的实现位置可参考第5章《核心流程解读》，相关算法原理详见第6章《H2 数据库核心算法分析》。

## 3.1 包全景图

H2 Database 的源码根包为 `org.h2`，共包含约 843 个 Java 源文件，分布在 25 个一级子包和约 15 个二级子包中。从依赖关系的角度看，这些包构成了一个**有向无环分层图**，上层依赖下层，下层绝不反向依赖上层。

**图 3-1: org.h2 包分层依赖关系图**

```text
                    ┌─────────────────────┐  ┌──────────────────┐
                    │    org.h2.jdbc       │  │ org.h2.server    │
                    │    org.h2.jdbcx      │  │ (tcp/pg/web)     │
                    │ JDBC 接口层          │  │ Server 层         │
                    └──────────┬──────────┘  └────────┬─────────┘
                               │                      │
                               └──────────┬───────────┘
                                          │
                               ┌──────────▼──────────┐
                               │    org.h2.engine     │
                               │    引擎核心           │
                               └──────────┬──────────┘
                                          │
                   ┌──────────────────────┼──────────────────────┐
                   │                      │                      │
        ┌──────────▼──────────┐  ┌───────▼────────┐  ┌─────────▼──────────┐
        │  org.h2.command     │  │  org.h2.table  │  │  org.h2.constraint │
        │  (dml/ddl/query)    │  │  org.h2.index  │  │                    │
        └──────────┬──────────┘  └───────┬────────┘  └────────────────────┘
                   │                     │
        ┌──────────▼──────────┐  ┌───────▼────────┐
        │ org.h2.expression   │  │ org.h2.mvstore │
        │ (condition/function/ │  │  (db/tx/cache/ │
        │  aggregate/analysis) │  │   rtree/type)  │
        └─────────────────────┘  └───────┬────────┘
                                         │
                               ┌─────────▼─────────┐
                               │  org.h2.value     │  类型系统
                               │  org.h2.result    │  结果集
                               └─────────┬─────────┘
                                         │
                               ┌─────────▼─────────┐
                               │  org.h2.store     │  存储层
                               │  org.h2.store.fs  │  文件系统
                               └───────────────────┘
```

> 如图 3-1 所示，**说明**：Server层与JDBC层同属接入层，是两种并行的外部访问入口。JDBC层处理标准JDBC协议调用，Server层处理TCP/PostgreSQL/Web协议请求，二者均直接依赖engine层，不存在先后依赖关系。

**图 3-2: 核心包依赖矩阵**

如图 3-2 所示，以下矩阵展示了各一级包之间的编译期依赖关系。"●" 表示存在直接依赖，"○" 表示间接或运行时依赖，空白表示无依赖。

```text
┌─────────────────┬─────────────────────────────────────────────────────────────────────────────┐
│  被依赖 \ 依赖方 │ engine command table index expression mvstore value store store.fs jdbc    │
├─────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ engine          │   -      ●      ●     ●      ●          ○      ●     ●      -      ●      │
│ command         │   -      -      -     -      ●          -      -     -      -      -      │
│ table           │   -      -      -     ●      ●          -      ●     -      -      -      │
│ index           │   ●      -      -     -      -          -      ●     -      -      -      │
│ expression      │   -      ●      ●     -      -          -      ●     -      -      -      │
│ mvstore         │   -      -      -     -      -          -      -     ●      -      -      │
│ value           │   ●      ●      ●     ●      ●          ●      -     ●      -      ●      │
│ store           │   -      -      -     -      -          -      -     -      ●      -      │
│ store.fs        │   -      -      -     -      -          -      -     ●      -      -      │
│ jdbc            │   -      -      -     -      -          -      -     -      -      -      │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────┘
```

从矩阵中可以清晰地看出：`value` 包是最基础的被依赖包，几乎被所有上层包引用；`engine` 包是核心枢纽，依赖它或它依赖的包数量最多；`store.fs` 位于层级最底层，只被 `store` 包依赖。这种严格的单向依赖结构是 H2 保持长期可维护性的关键设计决策。

**图 3-3: H2 五层体系架构分层**

```text
┌──────────────────────────────────────────────────────────────────┐
│                      接入层 (Access Layer)                        │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐   │
│  │ org.h2.jdbc         │  │ org.h2.server                    │   │
│  │ JdbcConnection      │  │ TcpServer  PgServer  WebServer   │   │
│  │ JdbcStatement       │  │ SessionRemote                    │   │
│  │ JdbcPreparedStmt    │  │                                  │   │
│  │ JdbcResultSet       │  │                                  │   │
│  └─────────┬───────────┘  └──────────────┬───────────────────┘   │
└────────────┼─────────────────────────────┼───────────────────────┘
             │                             │
┌────────────┼─────────────────────────────┼───────────────────────┐
│            ▼                             ▼                       │
│                     引擎层 (Engine Layer)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ engine   │  │ command  │  │ table    │  │ index    │         │
│  │ Database │  │ Parser   │  │ Table    │  │ Index    │         │
│  │ Session  │  │ Prepared │  │ TableFilt│  │ IndexCndt│         │
│  │ Mode     │  │ Select   │  │ Column   │  │ Cursor   │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │             │                │
│  ┌────▼─────────────▼─────────────▼─────────────▼─────┐          │
│  │ expression                                          │          │
│  │ Expression  ValueExpr  BinaryOp  Condition  Window  │          │
│  └────────────────────┬────────────────────────────────┘          │
└───────────────────────┼───────────────────────────────────────────┘
                        │
┌───────────────────────┼───────────────────────────────────────────┐
│                       ▼                                           │
│                    存储层 (Storage Layer)                          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ org.h2.mvstore             org.h2.mvstore.db              │   │
│  │ MVStore  MVMap  Page       Store  MVTable  MVPrimaryIndex │   │
│  │ Chunk   RootReference      MVSecondaryIndex  ValueDataType│   │
│  └───────────────┬───────────────────────────────────────────┘   │
│                  │                                                │
│  ┌───────────────▼───────────────────────────────────────────┐   │
│  │ org.h2.mvstore.tx           org.h2.mvstore.cache          │   │
│  │ Transaction  TransactionMap  CacheLongKeyLIRS (LIRS)      │   │
│  │ Snapshot  VersionedValue                                  │   │
│  └───────────────┬───────────────────────────────────────────┘   │
└──────────────────┼────────────────────────────────────────────────┘
                   │
┌──────────────────┼────────────────────────────────────────────────┐
│                  ▼                                                │
│             类型与结果层 (Type & Result Layer)                     │
│  ┌─────────────────────┐  ┌─────────────────────┐                │
│  │ org.h2.value        │  │ org.h2.result       │                │
│  │ Value (20+ subtypes)│  │ LocalResult         │                │
│  │ DataType  TypeInfo  │  │ Row  SearchRow      │                │
│  │ CompareMode         │  │ SortOrder           │                │
│  └─────────────────────┘  └─────────────────────┘                │
└───────────────────────────┬───────────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────────┐
│                           ▼                                       │
│                         I/O 层                                    │
│  ┌─────────────────────┐  ┌─────────────────────┐                │
│  │ org.h2.store        │  │ org.h2.store.fs     │                │
│  │ FileStore  FileLock │  │ FilePath (策略模式)  │                │
│  │ Data  LobStorage    │  │ FileDisk  FileMem   │                │
│  │                     │  │ FileEncrypt  FileNio │                │
│  └─────────────────────┘  └─────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘
```

如图 3-3 所示，以上五层体系严格遵循"上层依赖下层，下层对上层一无所知"的原则。接入层负责协议适配，引擎层实现 SQL 语义，存储层管理持久化，类型与结果层提供数据表示，I/O 层处理物理存储。每一层都可以独立演化和测试。

以下按第2章定义的八层架构（接入层（JDBC+Server）→ 引擎层 → SQL 处理层（Command+Expression）→ 存储抽象层（Table/Index）→ 存储引擎层（MVStore）→ 文件系统层）逐层展开各包的角色与关键类，并补充类型系统与安全工具包。

> **层模型对照**：图 3-3 的"五层模型"是第2章"八层模型"的聚合视图。接入层 = JDBC + Server；引擎层 = Engine + Command + Expression + Table/Index；存储层 = MVStore；类型与结果层 = value + result；I/O 层 = FileSystem。两种视图面向不同粒度——五层适合宏观理解，八层用于源码追踪。

---

## 3.2 JDBC 层

> **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#jdbc`)
> 官方文档将 JDBC 驱动描述为整个架构的最上层入口。

### 3.2.1 jdbc 包 — JDBC 驱动实现

**路径**: `org.h2.jdbc`

**层定位**: 实现 `java.sql` 标准接口，是用户直接面对的一层。所有 JDBC 调用最终委托给 engine 层的 SessionLocal。

**关键类**:

| 类名 | 职责 |
|------|------|
| `JdbcConnection.java` | 实现 `java.sql.Connection`（`org/h2/jdbc/JdbcConnection.java:31`），管理事务边界、语句创建 |
| `JdbcStatement.java` | 实现 `java.sql.Statement`（`org/h2/jdbc/JdbcStatement.java:28`），包装 Command 对象 |
| `JdbcPreparedStatement.java` | 实现 `java.sql.PreparedStatement`，参数绑定 |
| `JdbcResultSet.java` | 实现 `java.sql.ResultSet`（`org/h2/jdbc/JdbcResultSet.java:34`），包装 LocalResult/ResultRemote |
| `JdbcDatabaseMetaData.java` | 实现 `java.sql.DatabaseMetaData` |

`org.h2.jdbcx` 包提供了 JTA/XA 分布式事务支持，主要类为 `JdbcDataSource`。

**JDBC 调用链路**:

**图 3-4: JDBC 全调用栈（关注调用链的宏观阶段：连接→编译→执行→结果）**

```text
JdbcConnection.prepareStatement(sql)
    │
    ▼
SessionLocal.prepareCommand(sql)
    │
    ▼
Parser.parse(sql) → Prepared
    │
    ▼
Prepared.query() / update()
    │
    ▼
SessionLocal 执行 → MVTable / MVMap
    │
    ▼
LocalResult (结果集)
    │
    ▼
JdbcResultSet (游标遍历)
```

**图 3-5: JDBC 方法到引擎层的完整委托链（图3-4的细化展开，遍历每个 JDBC 方法的内部委托路径）**

```text
用户代码                                   内部委托链
───────────────────────────────            ─────────────────────────────────
conn = DriverManager.getUrl()   →  Engine.createSession() → SessionLocal
conn.prepareStatement(sql)      →  SessionLocal.prepareCommand()
                                        → Parser.parse()
                                        → CommandContainer
stmt.setInt(1, 100)            →  Parameter.setValue(ValueInteger(100))
stmt.executeQuery()             →  Prepared.query()
                                        → Optimizer.findBestPlan()
                                        → TableFilter 遍历行
                                        → LocalResult
rs = stmt.getResultSet()        →  JdbcResultSet(LocalResult)
rs.next()                       →  LocalResult.next()
                                        → Row 数据返回
rs.getInt("id")                 →  Value.getInt()
rs.close()                      →  LocalResult.close()
                                        → 资源释放
stmt.close()                    →  CommandContainer 重用/释放
conn.close()                    →  SessionLocal.close()
                                        → 事务提交/回滚
                                        → MVStore 释放
```

如图 3-5 所示，JDBC 层的设计遵循"薄封装"原则——`Jdbc*` 类本身几乎不包含业务逻辑，它们的作用是将 JDBC 标准接口的方法调用转换为 engine 层的内部 API。这种设计的好处是：嵌入式模式和服务器模式可以共享同一套 engine 层代码。在服务器模式下，`JdbcConnection` 内部包装的是 `SessionRemote`（一个通过网络与 `TcpServer` 通信的代理），而嵌入式模式下直接包装 `SessionLocal`。上层 JDBC 代码不需要关心底层是哪种模式。



## 3.3 Engine 层

引擎层是 H2 的"大脑"，是数据库实例的全局中枢。本层核心为 `engine` 包，负责管理 Database 实例、会话生命周期、事务协调、安全权限与元数据。

### 3.3.1 engine 包 — 数据库实例与运行时

**路径**: `org.h2.engine`

**层定位**: 最核心的运行时层，是全局数据库实例的载体，管理连接、会话、事务、安全权限和元数据。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Database.java` | 数据库实例中枢（`org/h2/engine/Database.java:97`），持有所有 schema、user、session 的注册表，管理 MVStore 生命周期，是全局锁的协调者 |
| `Engine.java` | 全局单例（`org/h2/engine/Engine.java:37`），维护 Database 名称→实例的映射，处理连接请求的入口 |
| `SessionLocal.java` | 嵌入式会话实现（`org/h2/engine/SessionLocal.java:52`），持有当前事务状态、锁集合、undo log，是 SQL 请求的执行上下文 |
| `ConnectionInfo.java` | JDBC URL 解析器（约760行），将 `jdbc:h2:mem:test;DB_CLOSE_DELAY=-1` 解析为结构化参数 |
| `Mode.java` | SQL 兼容模式，定义了 Oracle/MySQL/PostgreSQL/MSSQLServer 的语法差异规则 |
| `DbSettings.java` | 数据库级配置项，控制缓存大小、日志模式、MVCC 行为等 |

**包内关系**:

**图 3-6: engine 包内类关系**

```text
Engine (全局入口)
   │
   ├── Database (数据库实例)
   │      ├── Schema (命名空间)
   │      ├── User / Role / Right (安全)
   │      ├── SessionLocal (活动会话)
   │      └── DbSettings (配置)
   │
   └── ConnectionInfo → Mode (连接参数 + 兼容模式)
```

如图 3-6 所示，`Engine` 是单例入口，按数据库名称查找或创建 `Database` 实例。`Database` 是整个系统的上帝对象（God Object），几乎所有全局状态的访问都要经过它。`SessionLocal` 是每次 SQL 执行的上下文容器，负责管理事务隔离级别、锁持有和本地临时数据。

**图 3-7: Database 生命周期状态图**

```text
                      ┌──────────────┐
                      │  未初始化     │
                      │  (尚未创建)   │
                      └──────┬───────┘
                             │ Engine.init()
                             ▼
                      ┌──────────────┐
                      │  初始化中     │
                      │  init()      │───────── 若失败 → 抛出异常并回滚
                      └──────┬───────┘
                             │ init() 完成
                             ▼
                      ┌──────────────┐
                      │  运行中       │
                      │  open        │───────── 接受连接和 SQL 请求
                      └──────┬───────┘
                             │ Database.close()
                             ▼
                      ┌──────────────┐
                      │  关闭中       │
                      │  close()     │───────── 刷写 MVStore → 释放资源
                      └──────┬───────┘
                             │ close() 完成
                             ▼
                      ┌──────────────┐
                      │  已关闭       │
                      │  closed      │───────── 不可再使用
                      └──────────────┘
```

如图 3-7 所示，Database 的生命周期由 Engine 管理。当第一个连接请求到达时，Engine 检查是否有对应名称的 Database 实例，如果没有则创建并调用 `init()`。init 过程包括：加载系统表、恢复 MVStore 数据、初始化权限系统和内置函数。运行期间，Database 持有全局读写锁，协调所有会话的并发访问。关闭时，Database 刷写所有待持久化的变更到 MVStore，释放文件锁和线程池资源。一旦关闭，Database 实例不可重用，必须创建新实例。

**图 3-8: Session 状态与事务协调**

```text
                    ┌─────────────────────┐
                    │  SessionLocal       │
                    │  ┌───────────────┐  │
                    │  │  undoLog      │  │  ← 记录所有未提交更改
                    │  ├───────────────┤  │
                    │  │  lockTable    │  │  ← 持有行锁/表锁集合
                    │  ├───────────────┤  │
                    │  │  transaction  │  │  ← 当前事务引用
                    │  ├───────────────┤  │
                    │  │  sessionState │  │  ← 自动提交/只读/事务隔离级
                    │  └───────────────┘  │
                    └────────┬────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   ┌────────────┐    ┌──────────────┐    ┌──────────────┐
   │ 事务开始    │    │   SQL 执行    │    │  事务结束     │
   │ setAutoCommit│   │  prepare()   │    │  commit()    │
   │  =false     │    │  query/update│    │  rollback()  │
   ├────────────┤    ├──────────────┤    ├──────────────┤
   │ 创建 Transaction│ │  Command执行 │    │ 释放锁       │
   │ 获取事务ID   │    │  行锁管理    │    │ 清空 undoLog │
   │ 记录开始时间  │    │  版本可见性  │    │ 通知 MVStore │
   └────────────┘    └──────────────┘    └──────────────┘
```

如图 3-8 所示，SessionLocal 是引擎层最活跃的对象之一。它充当了 JDBC 连接与存储引擎之间的中间人：接收来自 `JdbcConnection` 的请求，协调 `Parser` 和 `Prepared` 完成 SQL 编译，再将执行请求转发给 `MVTable` 和 `MVMap`。每个 SessionLocal 都持有独立的 undo log，这意味着事务回滚可以在不触及 MVStore 的情况下完成——只需反转 undo log 中的操作即可。

SessionLocal 同时负责锁管理。在 MVCC 模式下，写操作会在行级别加锁，锁信息存储在 `MVTable.rowLock` 的 MVMap 中。当多个会话同时修改同一行时，`TxDecisionMaker` 负责检测写冲突，决定哪个事务可以继续、哪个需要回滚。

---

## 3.4 Command 层

### 3.4.1 command 包 — SQL 解析与命令分发

**路径**: `org.h2.command`

**层定位**: SQL 语句从文本到可执行对象的转换层。Parser 产出语法树，Prepared 子类承载编译后的语义。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Parser.java` (9300+ 行) | 递归下降解析器（`org/h2/command/Parser.java:27`），手写实现，无外部依赖，覆盖完整 SQL 语法 |
| `Tokenizer.java` | 词法分析器（`org/h2/command/Tokenizer.java`），将 SQL 文本拆解为 token 流 |
| `CommandContainer.java` | Prepared 语句的包装器，支持重编译和参数绑定 |
| `Prepared.java` | 所有编译后语句的抽象基类（`org/h2/command/Prepared.java:28`），提供 `update()` / `query()` 模板方法 |

> **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#command`)
> 官方说明：Parser 直接生成命令执行对象（无中间 IR），然后在命令上运行优化步骤。

**子包**:

| 子包 | 内容 |
|------|------|
| `org.h2.command.dml` | DML 命令: Insert, Update, Delete, Merge, MergeUsing, TransactionCommand, Explain, Set |
| `org.h2.command.ddl` | DDL 命令: CreateTable, CreateIndex, AlterTable, AlterTableAddConstraint, DropTable, Analyze, GrantRevoke |
| `org.h2.command.query` | 查询: Select(2000+行), SelectUnion, Optimizer, SelectGroups, ForUpdate |

**解析流程**:

**图 3-9: SQL 解析与执行流程**

```text
SQL文本 "SELECT * FROM t WHERE id=?"
    │
    ▼
Tokenizer (词法分析)
    │
    ▼
Parser.parseSelect() (语法分析, 递归下降)
    │
    ▼
Select extends Prepared (语义分析 + 权限检查)
    │
    ▼
Optimizer (查询优化)
    │
    ▼
TableFilter / IndexCursor (执行)
```

如图 3-9 所示，`Parser.java` 是 H2 源码中最庞大的单个文件之一。它采用经典的手写递归下降模式，每一种 SQL 语法对应一个 `parseXxx()` 方法。解析器产出的 `Prepared` 子类既是语法树的表示，也是后续优化和执行的入口。

**图 3-10: Parser 命令树层次结构**

```text
Parser
  │
  ├── parseSelect()     ───→ Select (query包, 2000+行)
  ├── parseInsert()     ───→ Insert (dml包)
  ├── parseUpdate()     ───→ Update (dml包)
  ├── parseDelete()     ───→ Delete (dml包)
  ├── parseMerge()      ───→ Merge (dml包)
  ├── parseCreate()     ───→ CreateTable / CreateIndex / ... (ddl包)
  ├── parseAlter()      ───→ AlterTable / AlterIndex / ... (ddl包)
  ├── parseDrop()       ───→ DropTable / DropIndex / ... (ddl包)
  ├── parseGrantRevoke() ──→ GrantRevoke (ddl包)
  ├── parseCall()       ───→ Call (dml包)
  ├── parseExplain()    ───→ Explain (dml包)
  └── parseSet()        ───→ Set (dml包)
```

如图 3-10 所示，每个 `parseXxx()` 方法的内部实现遵循相同的模式：先调用 `readIf()` 或 `readEnum()` 检查当前 token 的关键字，然后递归调用子解析器读取表名、列名、表达式等子结构，最后构造对应的 `Prepared` 子类实例。这种设计使解析逻辑与命令逻辑完全分离——解析器负责"读懂"SQL，而 `Prepared` 子类负责"执行"语义。

**图 3-11: DML / DDL / Query 执行路径对比**

```text
DML (Insert/Update/Delete)     DDL (Create/Alter/Drop)           Query (Select)
─────────────────────────────  ────────────────────────────      ─────────────────────────
Prepared.update()              Prepared.update()                  Prepared.query()
       │                              │                                 │
       ▼                              ▼                                 ▼
权限检查                         权限检查                          权限检查
       │                              │                                 │
       ▼                              ▼                                 ▼
Table.addRow() / removeRow()     metaData.update()                Optimizer.findBestPlan()
       │                              │                                 │
       ▼                              ▼                                 ▼
MVTable 版本写                    Schema 元数据修改                 TableFilter 迭代行
       │                              │                                 │
       ▼                              ▼                                 ▼
MVMap.put() / remove()           MVStore 元数据提交               LocalResult 构建
       │                              │                                 │
       ▼                              ▼                                 ▼
Transaction.commit()             Transaction.commit()              JdbcResultSet 返回
```
**图 3-12: 命令缓存与重新编译机制**

  JdbcConnection.prepareStatement(sql)

```text
       │
       ▼
  ┌─────────────────────────────┐
  │  commandMap 缓存             │
  │  ┌───────────────────────┐  │── 命中 → 返回已缓存的
  │  │ SQL → Command         │  │    Command 对象
  │  │ SELECT * → Cmd#1      │  │
  │  │ INSERT  → Cmd#2       │  │
  │  └───────────────────────┘  │
  └──────────┬──────────────────┘
             │ 未命中 → 编译
             ▼
  ┌─────────────────────────────┐
  │  Parser 递归下降解析         │──→ Prepared → CommandContainer
  └──────────┬──────────────────┘
             │
             ▼
  ┌────────────────────────────────────────┐
  │  CommandContainer.update() / query()   │
  │                                        │
  │  ├── 版本检测: schemaVersion           │
  │  │    ├── 匹配 → 直接执行              │
  │  │    └── 不匹配 → Parser 重编译       │
  │  ├── 参数绑定                          │
  │  ├── 权限验证                          │
  │  └── 执行 DDL/DML/DQL → 返回结果       │
  └────────────────────────────────────────┘

```
从执行路径可以看出，DML 操作直接作用于 MVTable 和 MVMap，通过事务引擎保证原子性；DDL 操作主要修改 Schema 元数据（也是存储在 MVMap 中），涉及更复杂的锁策略（通常需要排他锁）；Query 操作则通过优化器选择最佳执行计划后，以只读方式遍历 MVMap 中的数据行。三种路径共享底层的存储和事务基础设施，但在锁粒度和数据修改方式上存在显著差异。

---

## 3.5 Expression 层

### 3.5.1 expression 包 — 表达式系统

**路径**: `org.h2.expression`

**层定位**: 涵盖 SQL 中所有可供计算的节点 — 列引用、字面量、运算符、函数、条件、聚合和窗口函数。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Expression.java` | 抽象基类（`org/h2/expression/Expression.java:28`），核心方法 `getValue()` 求值、`optimize()` 常量折叠优化、`mapColumns()` 列绑定 |
| `ExpressionColumn.java` | 列引用，由 tableName.columnName 定位到实际的 Column 对象 |
| `ValueExpression.java` | 字面量常量，`optimize()` 直接返回自身 |
| `BinaryOperation.java` | 二元运算（`org/h2/expression/BinaryOperation.java`）：+ - * / %，支持类型提升和精度推算 |
| `Parameter.java` | `?` 占位符，参数绑定时才完成求值 |

**子包展开**:

**图 3-13: expression 子包结构**

```text
org.h2.expression
   ├── condition/         条件表达式
   │    ├── Comparison.java      =, <>, <, >, <=, >=
   │    ├── ConditionAndOr.java  AND / OR (短路求值)
   │    ├── ConditionInConstantSet.java  IN (哈希集合优化)
   │    ├── ConditionInQuery.java        IN (子查询)
   │    ├── CompareLike.java     LIKE (模式匹配)
   │    ├── BetweenPredicate.java BETWEEN
   │    └── NullPredicate.java   IS NULL / IS NOT NULL
   │
   ├── function/          函数
   │    ├── BuiltinFunctions.java 内置函数注册中心
   │    ├── CastSpecification.java CAST / CONVERT
   │    ├── StringFunction.java   字符串函数
   │    ├── DateTimeFunction.java 日期时间函数
   │    └── MathFunction.java     数学函数
   │
   ├── aggregate/         聚合函数
   │    ├── Aggregate.java       COUNT / SUM / AVG / MIN / MAX
   │    └── AggregateType.java   聚合类型枚举
   │
   └── analysis/          窗口函数
        ├── Window.java         窗口帧定义
        └── WindowFunction.java  ROW_NUMBER / RANK / LEAD / LAG
```

如图 3-13 所示，表达式系统的设计核心是 `Expression` 的**三层接口**：`mapColumns()` 在编译期绑定列引用，`optimize()` 执行常量折叠和类型推导，`getValue()` 在运行期递归求值。这一模式使得表达式树可以被独立优化和执行。

**图 3-14: Expression 求值流程与类型提升**

```text
SQL: (price * 1.08) + CAST(shipping AS DECIMAL(10,2))

表达式树:
           ┌───────────┐
           │   加法     │  BinaryOperation(PLUS)
           └─────┬─────┘
                 │
       ┌─────────┴─────────┐
       │                   │
┌──────▼──────┐    ┌───────▼────────┐
│   乘法       │    │   CAST          │
│ BinaryOp(*) │    │ CastSpecification│
└──────┬──────┘    └───────┬────────┘
       │                   │
  ┌────┴────┐          ┌───┴───┐
  │         │          │       │
┌─▼──┐  ┌──▼───┐  ┌───▼──┐  ┌─▼────────┐
│price│  │1.08  │  │shipping│ │DECIMAL  │
│Col  │  │Value │  │Column │ │(10,2)   │
└─────┘  └──────┘  └──────┘  └─────────┘

求值过程 (自底向上):
Step 1: price.getValue() → ValueInteger(100)
Step 2: 1.08.getValue()  → ValueNumeric(1.08)
Step 3: 乘法 → 类型提升: INTEGER * DECIMAL → 100 → 100.00 DECIMAL
              结果: ValueNumeric(108.00)
Step 4: shipping.getValue() → ValueInteger(15)
Step 5: CAST → 类型转换: INTEGER → DECIMAL(10,2) → ValueNumeric(15.00)
Step 6: 加法 → DECIMAL + DECIMAL → ValueNumeric(123.00)
```

如图 3-14 所示，表达式求值由底向上递归进行。每个节点在 `getValue()` 时，先递归求值子节点，然后执行自身运算。类型提升（type promotion）在二元运算中自动发生——当 `INTEGER` 与 `DECIMAL` 相加时，前者会被隐式提升为 `DECIMAL` 以保证精度不丢失。`optimize()` 方法在编译期执行常量折叠：如果乘法运算符的两个操作数都是字面常量，`optimize()` 会直接计算出结果并将当前节点替换为 `ValueExpression`，从而在运行期免去重复计算。这种编译期优化是 H2 表达式引擎性能的重要来源。

---

## 3.6 Table/Index 层

> **参考**: H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html#table`)
> 指出 H2 将索引作为一种特殊的表来存储，Table 和 Index 在同一抽象层次。

### 3.6.1 table 包 — 表抽象与查询计划

**路径**: `org.h2.table`

**层定位**: 提供对"表"的抽象 — 不论是物理表、视图、派生表还是系统表，都统一为 `Table` 接口。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Table.java` | 抽象基类（`org/h2/table/Table.java:26`），定义 addRow/removeRow/getRowCount/getIndex 等核心契约 |
| `TableFilter.java` | FROM 子句的核心抽象（`org/h2/table/TableFilter.java:24`），负责索引选择、行过滤和表连接时的行迭代 |
| `TableView.java` | SQL 视图实现，将视图定义缓存为 Select 对象，查询时展开 |
| `Column.java` | 列定义：名称、类型、默认值、可空性、精度等 |
| `Plan.java` / `PlanItem.java` | 查询计划，由 Optimizer 生成，驱动 TableFilter 的执行顺序 |
| `CTE.java` | 公用表表达式（WITH 子句）的支持 |

**包内关系**:

**图 3-15: Table 类层次结构**

```text
Table (抽象)
   ├── TableBase (存储表基类)
   │     └── MVTable (MVCC 存储表实现)
   ├── TableView (视图, 包装 Select 查询)
   ├── MetaTable (INFORMATION_SCHEMA 系统表)
   ├── DerivedTable (派生表, FROM 子句子查询)
   ├── CTE (WITH 子句)
   ├── FunctionTable (表值函数)
   └── DualTable (虚拟双表, SELECT 1+1)

TableFilter ──→ PlanItem ──→ Plan (查询计划)
```

**图 3-16: TableFilter 连接执行时序**

```text
多表连接查询: SELECT * FROM orders o JOIN customers c ON o.cid=c.id

Optimizer 选择的执行计划:
外层驱动表: customers (全表扫描代价低)
内层被驱动表: orders (通过 cid 索引查找)

执行时序:
Step 1: TableFilter(outer) = customers
           │
           ▼
Step 2: cursor = index.find(filterCondition)
           │  returns Cursor over customer rows
           ▼
Step 3: while cursor.next():
           │  row = cursor.get()
           │  ┌─ c = current customer row
           │  ▼
           │  Step 4: TableFilter(inner) = orders
           │            │
           │            ▼
           │  Step 5: 使用 IndexCondition(EQUALITY, cid=c.id)
           │            │  orders.index.find(cid=c.id)
           │            ▼
           │  Step 6: while innerCursor.next():
           │             row = innerCursor.get()
           │             构建连接行 (o.* + c.*)
           │             添加到 LocalResult
           │
           ▼
Step 7: 返回 LocalResult → JdbcResultSet
```

如图 3-16 所示，TableFilter 是连接执行的核心引擎。Optimizer 通过 `PlanItem.cost` 估算每个 TableFilter 的扫描代价，并据此决定表的连接顺序——小表驱动大表，利用索引减少内层表的扫描行数。`IndexCondition` 描述了 WHERE 条件中可以被索引加速的谓词，TableFilter 将这些条件传递给 `Index.find()` 方法以缩小扫描范围。

**图 3-17: H2 支持的连接策略对比**

```text
连接类型         实现方式                         适用场景              代价特征
─────────────────────────────────────────────────────────────────────────────────
嵌套循环连接      TableFilter 嵌套迭代            小表驱动大表          O(n*m)
(Nested Loop)     outer.next() → inner.find()     内层表有索引可用
─────────────────────────────────────────────────────────────────────────────────
哈希连接         构建哈希表 → 探测匹配            大表无索引           O(n+m) 构建
(Hash Join)      Select 中通过条件判断启用         等值连接              O(m) 探测
─────────────────────────────────────────────────────────────────────────────────
排序归并连接     双方排序 → 归并                   排序好的结果集        O(n log n + m)
(Sort Merge)     通常用于 ORDER BY 场景            或需要有序输出
─────────────────────────────────────────────────────────────────────────────────
复合范围连接      多个 IndexCondition 组合         多列复合索引          取决于索引
(Multi-Range)    IndexCursor 多条件联合扫描        的范围查询            选择性
─────────────────────────────────────────────────────────────────────────────────
```

如图 3-17 所示，H2 的优化器在选择连接策略时，会综合考虑表大小、索引可用性、WHERE 条件类型和 ORDER BY 需求。对于 OLTP 场景，嵌套循环连接是最常用的策略，因为它能充分利用索引精确定位数据行。哈希连接在处理大表无索引的等值连接时表现更好，但需要额外的内存来构建哈希表。

---

### 3.6.2 index 包 — 索引定义与遍历

**路径**: `org.h2.index`

**层定位**: 定义索引的契约 — 查找、范围扫描、排序。索引的具体实现在 mvstore.db 中。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Index.java` | 索引抽象基类（`org/h2/index/Index.java:23`），定义 `find()` / `next()` / `getRowCount()` |
| `IndexType.java` | 索引类型描述：是否是唯一/主键/空间/哈希索引 |
| `IndexCondition.java` | 索引可用的条件片段：EQUALITY / RANGE / SPATIAL |
| `IndexCursor.java` | 索引遍历游标，维护当前扫描位置 |
| `Cursor.java` | 行迭代接口（`org/h2/index/Cursor.java`，仅含 `next()` 和 `get()`） |

Table 通过 `getIndexes()` 获取其索引列表，`TableFilter` 在 `findBestIndex()` 中根据查询条件选择代价最小的索引。`IndexCondition` 描述了索引可以加速的谓词类型，优化器利用这些信息来裁剪扫描范围。

**图 3-18: 索引扫描策略决策树**

```text
查询条件到达: WHERE id=100 AND status='ACTIVE'

可用索引: PK(id 主键), IDX_STATUS(status 二级索引)

                  ┌──────────────────────┐
                  │ WHERE 条件分析        │
                  │ IndexCondition 提取   │
                  └──────────┬───────────┘
                             │
               ┌─────────────┴─────────────┐
               │                           │
        是否有等值条件                  只有范围条件
        匹配主键索引?                    或无索引?
               │                           │
          ┌────┴────┐                ┌─────┴─────┐
          │ 是      │ 否             │ 是         │ 否
          ▼        ▼                ▼            ▼
   ┌──────────┐ ┌────────┐   ┌───────────┐ ┌───────────┐
   │主键精准   │ │二级索引 │   │范围扫描    │ │全表扫描    │
   │查找       │ │查找    │   │           │ │           │
   │代价: O(1) │ │        │   │代价: O(k)  │ │代价: O(n) │
   └──────────┘ │ 有等值? │   └───────────┘ └───────────┘
                │  ┌──┴──┐
                │  │是   │否
                │  ▼    ▼
                │┌────┐┌───────┐
                ││精准 ││范围   │
                ││查找 ││扫描   │
                ││O(1) ││O(logN)│
                │└────┘└───────┘
                │
                需要回表查询主键 → O(logN) 额外代价
```

如图 3-18 所示，索引扫描策略的选择直接影响查询性能。决策树的核心逻辑在 `TableFilter.findBestIndex()` 中实现：它遍历表的所有索引，对每个索引计算 `IndexCondition` 的匹配度，估算扫描行数，选择代价最小的索引。精准查找（等值条件匹配索引前缀）的代价最低，范围扫描次之，全表扫描最差。二级索引还需要额外考虑"回表"的开销——即通过索引键找到主键值后，再通过主键索引获取完整行数据。

**图 3-19: 主键索引与二级索引的数据流向**

```text
主键索引 (MVPrimaryIndex):
  MVMap<Long, Row>
  ┌────────┬─────────────────────────┐
  │ Key    │ Value                   │
  │ (行ID) │ (完整行数据: 所有列)    │
  ├────────┼─────────────────────────┤
  │ 1      │ {id=1, name='Alice'}    │
  │ 2      │ {id=2, name='Bob'}      │
  │ 3      │ {id=3, name='Charlie'}  │
  └────────┴─────────────────────────┘

二级索引 (MVSecondaryIndex):
  MVMap<Value, Long>
  ┌──────────────┬────────┐
  │ Key          │ Value  │
  │ (索引列值)   │ (行ID) │
  ├──────────────┼────────┤
  │ 'Alice'      │ 1      │
  │ 'Bob'        │ 2      │
  │ 'Charlie'    │ 3      │
  └──────────────┴────────┘

查找 name='Bob' 的完整行:
  1. 二级索引: 'Bob' → 行ID=2      (1次 B-Tree 查找)
  2. 回表: 行ID=2 → {id=2,name='Bob'} (1次 B-Tree 查找)
  3. 返回完整行数据

插入新行 (id=4, name='David'):
  1. MVPrimaryIndex: 行ID=4 → 完整行   (1次 B-Tree 写入)
  2. MVSecondaryIndex: 'David' → 4      (1次 B-Tree 写入)
  3. 若还有更多索引, 重复步骤2
```

如图 3-19 所示，索引组织表（Index-Organized Table, IOT）的设计使得主键索引直接包含完整行数据，避免了额外的数据存储结构。二级索引则采用"索引键→主键值"的映射，查询时需要回表。这种设计在写入时会产生写放大（每个索引都需要一次 B-Tree 写入），但换取了读取时的灵活性——可以根据任意索引列快速定位到目标行。

---

## 3.7 MVStore 层

存储层是 H2 v2.x 的核心重构成果，使用 MVStore 引擎替代了 v1.x 的 PageStore 引擎。MVStore 是一种基于 B-Tree + MVCC 的嵌入式键值存储引擎。

### 3.7.1 mvstore 包 — 键值存储引擎

**路径**: `org.h2.mvstore`

**层定位**: 纯键值存储引擎，对上层暴露简单的 Map 接口（`MVMap`），不感知任何 SQL 语义。

**关键类**:

| 类名 | 职责 |
|------|------|
| `MVStore.java` | 存储引擎核心（`org/h2/mvstore/MVStore.java:46`），管理 chunk 生命周期、commit 与 checkpoint、background writer |
| `MVMap.java` | 并发 B-Tree Map（`org/h2/mvstore/MVMap.java:40`），支持 COW（Copy-on-Write）迭代，无锁读取 |
| `Page.java` | B-Tree 节点（`org/h2/mvstore/Page.java:30`）：Leaf 页存储键值对，Non-Leaf 页存储子节点指针 |
| `Chunk.java` / `MFChunk.java` | 存储块，chunk 是连续的物理写入单元，包含多个 page |
| `RootReference.java` | B-Tree 根节点的原子引用，是实现无锁读写的关键 |
| `FreeSpaceBitSet.java` | 位图法管理 chunk 的可用空间 |
| `DataUtils.java` | 内部工具方法：页类型标记、错误码、版本号编码 |

**写流程**:

**图 3-20: MVMap 写入流程**

```text
MVMap.put(key, value)
    │
    ▼
Page 生成新版本 (COW, 沿路径复制节点)
    │
    ▼
RootReference.compareAndSet (原子切换根引用)
    │
    ▼
WriteBuffer (序列化到缓冲区)
    │
    ▼
Chunk (追加写入文件)
    │
    ▼
MVStore.store() (序列化脏页面到新 chunk 并更新 header)
```

如图 3-20 所示，`MVStore` 的核心设计理念是**无锁读取 + COW 写入**：读操作通过 `RootReference` 获取稳定的 B-Tree 根节点引用，写操作创建新的节点路径，然后通过 CAS 原子更新根引用。这使得读操作永远不会被写操作阻塞。

**图 3-21: B-Tree 结构与页分裂**

```text
B-Tree (阶数=192, 即每节点最多192个子节点):

             ┌─────────────────────────────┐
             │  根节点 (Root Page)          │
             │  [key_50] [key_150]          │
             └──────┬──────────┬────────────┘
                    │          │
            ┌───────┘          └───────┐
            │                          │
   ┌────────▼────────┐       ┌─────────▼─────────┐
   │ 内部节点         │       │ 内部节点            │
   │ [key_10][key_30] │       │ [key_80][key_120]  │
   └───┬─────┬───────┘       └───┬────────┬───────┘
       │     │                   │        │
   ┌───┘  ┌──┘             ┌─────┘   ┌───┘
   │      │                │         │
┌──▼──┐ ┌─▼──┐        ┌───▼──┐  ┌───▼───┐
│Leaf │ │Leaf│        │Leaf  │  │Leaf   │
│1-10 │ │11-30│       │51-80 │  │81-120 │
└─────┘ └────┘        └─────┘  └────────┘

页分裂示例: 向已满的叶子页插入 key=25

分裂前:  [11, 13, 15, 17, 19, 21, 23, 27, 29, 31, ...] (已满)
分裂后:  [11, 13, 15, 17, 19, 21, 23]  |  [25, 27, 29, 31, ...]
          ↑ 原页 (左半)                    ↑ 新页 (右半)

父节点更新: 在父节点中插入 key=25 作为分隔键
若父节点也满了 → 递归分裂 → 根节点分裂 → 树高度+1
```

如图 3-21 所示，B-Tree 是 MVStore 的核心数据结构。每个节点（Page）可以包含最多 192 个子节点或键值对。当叶子页写满时触发页分裂——将一半的键值对移动到新页，并在父节点中插入分隔键。页分裂可能向上传播，甚至导致根节点分裂，从而使树的高度增加一级。COW（Copy-on-Write）机制确保分裂过程中正在进行的读操作不会看到不一致的状态：写操作创建新的节点路径，通过 CAS 原子切换根引用后，旧版本对并发读仍然可见。

**图 3-22: Chunk 磁盘布局**

```text
MVStore 文件 (.mv.db)
┌─────────────────────────────────────────────────────────────────────┐
│ 文件头 (Header Block)                                                │
│ [H:2, format=2, blockSize=4096, chunkSize=..., createdAt=...]       │
├─────────────────────────────────────────────────────────────────────┤
│ Chunk 1 (起始偏移: block 1)                                          │
│ ┌─────────────────────────────────────────────────────────────────┐  │
│ │ Chunk Header: 元数据 (chunk id, 页数, 最大事务ID)               │  │
│ │ ┌───────────────────────────────────────────────────────────┐   │  │
│ │ │ Page 1: MVMap 根节点 (RootReference 序列化)               │   │  │
│ │ ├───────────────────────────────────────────────────────────┤   │  │
│ │ │ Page 2: MVMap 内部节点                                   │   │  │
│ │ ├───────────────────────────────────────────────────────────┤   │  │
│ │ │ Page 3..N: 叶子页 (键值对数据)                           │   │  │
│ │ └───────────────────────────────────────────────────────────┘   │  │
│ └─────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│ Chunk 2 (追加写入)                                                   │
│ ┌─────────────────────────────────────────────────────────────────┐  │
│ │ Chunk Header                                                   │  │
│ │ ... 页数据 ...                                                 │  │
│ └─────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│ ...                                                                │
├─────────────────────────────────────────────────────────────────────┤
│ Chunk N (最新的活跃 chunk)                                           │
├─────────────────────────────────────────────────────────────────────┤
│ Free Space (可用空间位图: FreeSpaceBitSet)                          │
└─────────────────────────────────────────────────────────────────────┘
```

如图 3-22 所示，Chunk 是 MVStore 的物理写入单元。所有写操作都是"追加写入"（append-only）的——新的页数据总是写入新的 chunk，旧的 chunk 在 compaction 之前不会被覆写。这种设计有两个重要优势：一是写操作是顺序 I/O，比随机 I/O 快得多；二是数据库崩溃时，最多丢失最后一个未完成的 chunk，不会产生部分写入导致的损坏。`FreeSpaceBitSet` 负责跟踪哪些 chunk 已被回收，供后续写入复用。

**图 3-23: Checkpoint 与 Background Writer 流程**

```text
时间线:
──────────────────────────────────────────────────────────────────────→
            │            │            │            │
      Commit 1      Commit 2      Commit 3    Checkpoint
         │             │             │            │
         ▼             ▼             ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐
   │Chunk A  │  │Chunk B  │  │Chunk C  │  │Chunk D   │
   │(commit 1) │  │(commit 2) │  │(commit 3) │  │(元数据)   │
   └─────────┘  └─────────┘  └─────────┘  └──────────┘
                                             │
                                             ▼
                                      更新 Meta Root
                                      Chunk 空间回收

Background Writer (后台 writer 线程):
                  ┌──────────────┐
                  │ 休眠 500ms    │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ 检查未提交的   │
                  │ 变更数量       │──── 若无 → 继续休眠
                  └──────┬───────┘
                         │ 超过阈值
                         ▼
                  ┌──────────────┐
                  │ 触发自动提交   │
                  │ (autoCommit)  │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ 写入变更到 Chunk│
                  │ 标记 Pos=Last │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ 定期 Checkpoint│
                  │ (每 30 秒)     │
                  └──────────────┘
```

如图 3-23 所示，MVStore 的写入策略本质上是"延迟批量写入"：每次 `put()` 操作先修改内存中的 B-Tree，在 `commit()` 时序列化脏页面到新 chunk 保证持久性，然后在后台线程中定期执行 checkpoint 将完整状态写入新的 chunk。`MetaRoot` 指针在 checkpoint 时原子更新，确保数据库重启后能从最近的 checkpoint 快速恢复。未提交的变更在崩溃后不会丢失，因为未持久化的变更会在重启时丢弃。

---

### 3.7.2 mvstore.db 包 — 关系模型桥接

**路径**: `org.h2.mvstore.db`

**层定位**: MVStore 键值语义与关系表语义之间的桥梁，将 SQL 的表/行/索引映射为 MVMap 的键值对。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Store.java` | Database ↔ MVStore 的适配器，管理 MVMap 的创建和命名 |
| `MVTable.java` | MVCC 表实现，封装行锁、版本链、事务可见性检测 |
| `MVPrimaryIndex.java` | 主键索引（聚集索引），行数据本身存储在 B-Tree 的 value 中 |
| `MVSecondaryIndex.java` | 二级索引（非聚集），从索引键映射到主键值 |
| `MVSpatialIndex.java` | 空间索引（R-Tree 实现），用于地理空间数据 |
| `ValueDataType.java` / `RowDataType.java` | 自定义序列化器，负责 Value 对象与字节流之间的转换 |

**映射关系**:

**图 3-24: 关系模型到 MVMap 的映射**

```text
关系模型                          MVMap 表示
─────────────────────────────────────────────────────────────────
MVTable (表)          →  一组命名前缀的 MVMap
MVPrimaryIndex (主键)  →  MVMap<Long, Row>  (主键→行数据)
MVSecondaryIndex (二级) →  MVMap<Value, Long> (索引键→主键)
MVTable.rowLock        →  MVMap<Long, Long>  (行ID→会话ID, 行锁)
```

如图 3-24 所示，`MVPrimaryIndex` 使用行 ID（long 类型）作为键、完整行数据作为值。`MVSecondaryIndex` 从索引键映射到主键值（即行 ID），因此需要通过主键索引的二次查找才能获取完整行。这是标准的**索引组织表 + 二级索引回表**模式。

**图 3-25: SQL INSERT 到 MVMap 的完整映射链**

```text
SQL: INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@test.com')

                      Parser.parseInsert()
                            │
                            ▼
                      Insert.update()
                            │
                            ▼
                      MVTable.addRow(row)
                            │
                            ├── 分配行ID (递增 long)
                            │
                            ├── MVPrimaryIndex.add(row)
                            │     │
                            │     ▼
                            │   MVMap<Long, Row>.put(1, rowData)
                            │     │
                            │     ▼
                            │   Row → RowDataType.write(row) → 字节数组
                            │     │
                            │     ▼
                            │   MVStore 写流程 (COW + Chunk 追加)
                            │
                            ├── MVSecondaryIndex.add(row)
                            │     │
                            │     ▼
                            │   MVMap<Value, Long>.put('Alice', 1)
                            │   MVMap<Value, Long>.put('alice@test.com', 1)
                            │
                            └── 获取行锁 (若启用了行锁)
                                  │
                                  ▼
                                MVMap<Long, Long>.put(1, sessionId)
```

如图 3-25 所示，该映射链展示了 SQL 语句如何转换为底层的键值操作。一次 INSERT 操作可能涉及 3 个或更多的 MVMap 写入（主键索引 + N 个二级索引 + 行锁）。每个 MVMap 写入最终都经过 MVStore 的 COW B-Tree 写入流程。这种分层映射使得存储引擎层不需要理解任何 SQL 语义——它只需要提供可靠的键值存储能力。

---

### 3.7.3 mvstore.tx 包 — 事务引擎

**路径**: `org.h2.mvstore.tx`

**层定位**: 在 MVStore 之上实现 ACID 事务，提供 MVCC 隔离和冲突检测。

**关键类**:

| 类名 | 职责 |
|------|------|
| `TransactionStore.java` | 事务协调器，管理事务创建、提交、回滚和 undo log |
| `Transaction.java` | 事务状态机（OPEN → COMMITTED / ROLLEDBACK / PREPARED），管理事务级 MVMap 视图 |
| `TransactionMap.java` | 事务感知的 MVMap 包装，根据事务可见性规则过滤版本 |
| `Snapshot.java` | 快照隔离实现，提供语句级一致性视图 |
| `VersionedValue`（实际位于 `org.h2.value`） | 版本化值，被 tx 包引用，存储同一键的多个版本（committed/uncommitted） |
| `TxDecisionMaker.java` | 冲突检测器，写操作时检查是否与其他事务冲突 |

**事务数据模型**:

**图 3-26: TransactionMap 可见性判断流程**

```text
TransactionMap.get(key)
    │
    ▼
从 MVMap 读取 VersionedValue
    │
    ▼
检查各版本的 ownerTxnId 和 commitTimestamp
    │
    ├── 已提交 ∧ commitTimestamp ≤ snapshotTimestamp → 可见 → 返回
    ├── 未提交 ∧ ownerTxnId = currentTxnId          → 可见 → 返回
    └── 其他                                          → 不可见 → 跳过
```

如图 3-26 所示，该事务模型实现了 **SI（Snapshot Isolation，快照隔离）**，在此基础上通过 `TxDecisionMaker` 检测写冲突，可升级到可串行化隔离级别。

**图 3-27: 事务状态机（详见第4章《核心模块深度解读》图4-38的详细版本）**

```text
                  ┌────────────┐
                  │   OPEN     │  ← 事务创建时的初始状态
                  └──────┬─────┘
                         │
           ┌─────────────┼─────────────────┐
           │             │                 │
           ▼             ▼                 ▼
    ┌───────────┐  ┌───────────┐   ┌───────────┐
    │ COMMITTED │  │ ROLLEDBACK│   │ PREPARED  │
    │ (已提交)   │  │ (已回滚)   │   │ (准备中)   │
    └───────────┘  └───────────┘   └─────┬─────┘
                                         │
                                    ┌────┴────┐
                                    │         │
                                    ▼         ▼
                              ┌────────┐ ┌────────┐
                              │COMMITTED│ │ROLLBACK│
                              │(二阶段) │ │        │
                              └────────┘ └────────┘

状态转换条件:
  OPEN → COMMITTED:  commit() 成功, 写入提交时间戳
  OPEN → ROLLEDBACK: rollback(), 撤销所有变更
  OPEN → PREPARED:   prepareCommit(), 两阶段提交准备
  PREPARED → COMMITTED: 完成二阶段提交
  PREPARED → ROLLEDBACK: prepareRollback(), 中止准备
```

如图 3-27 所示，Transaction 的状态转换是线性的，一旦转换到终态（COMMITTED 或 ROLLEDBACK）就不会再改变。`VersionedValue` 记录了每个键值对的版本链——每个版本都关联了一个事务 ID 和提交时间戳。当 `TransactionMap.get()` 被调用时，它会沿着版本链查找对当前事务可见的最新版本。可见性规则的核心是快照隔离：一个事务只能看到在其快照时间戳之前已提交的更改，以及自己所做的未提交更改。

**图 3-28: 并发事务冲突检测**

```text
场景: 事务 T1 和 T2 同时修改同一行 R

时间线:
T1: ──────BEGIN──────R.update()──────COMMIT──────
                      │               │
                      │               ▼
                      │          T1 提交成功
                      │          (写入 version_R_v2)
                      │
T2: ──────BEGIN───────────R.update()──────COMMIT──────
                          │               │
                          │               ▼
                          │          TxDecisionMaker 检测:
                          │          version_R_v2.ownerTxnId
                          │          = T1 ≠ T2
                          │          v2.committed = true
                          │          v2.commitTimestamp > T2.snapshot
                          │          → 写写冲突！
                          │
                          ▼
                    T2 抛出异常:
                    "Concurrent update to table xxx"
                    事务 T2 必须回滚重试

避免冲突的策略:
  1. SELECT ... FOR UPDATE (悲观锁)
  2. 使用可串行化隔离级别 (SI + 冲突检测)
  3. 应用层重试机制
```

如图 3-28 所示，`TxDecisionMaker` 在每次写操作时检查目标键的最新版本：如果最新版本由另一个事务写入且该事务已提交，且提交时间戳在当前事务的快照时间戳之后，则判定为写写冲突。检测到冲突后，当前事务必须回滚并由应用层重试。这种检测机制保证了可串行化隔离级别（Serializable Snapshot Isolation, SSI），在快照隔离的基础上增加了写冲突检测。

---

### 3.7.4 mvstore.cache 包 — 缓存

**路径**: `org.h2.mvstore.cache`

**关键类**:

| 类名 | 职责 |
|------|------|
| `CacheLongKeyLIRS.java` | LIRS（Low Inter-reference Recency Set）缓存算法实现，比 LRU 更好地抵抗扫描污染 |

该包只有一个类，实现了 LIRS 缓存算法。LIRS 的核心思想是区分"热数据"和"冷数据"的访问模式，即使冷数据频繁出现（如全表扫描），也不会把热数据挤出缓存。

**图 3-29: CacheLongKeyLIRS 内部数据结构**

```text
                    ┌─────────────────────────────────────┐
                    │         CacheLongKeyLIRS             │
                    │         (org.h2.mvstore.cache)        │
                    └──────────────────┬──────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
   ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
   │   LIR Stack (S)    │  │  HIR Queue (Q)     │  │  PR Queue (招募)    │
   │  ┌──────────────┐  │  │  ┌──────────────┐  │  │  ┌──────────────┐  │
   │  │  A (LIR) ↑   │  │  │  │  K (HIR)     │  │  │  │  E (PR)     │  │
   │  │  B (LIR)     │  │  │  │  J (HIR)     │  │  │  │  F (PR)     │  │
   │  │  C (LIR)     │  │  │  │  I (HIR)     │  │  │  │  G (PR)     │  │
   │  │  D (LIR)     │  │  │  │  H (HIR)     │  │  │  │  H (PR)     │  │
   │  └──────────────┘  │  │  └──────────────┘  │  │  └──────────────┘  │
   │  栈底 → 最近访问    │  │  队尾 → 最旧       │  │  招募池 → 候补    │
   └────────────────────┘  └────────────────────┘  └────────────────────┘

  核心规则:
    LIR 集合: 固定容量 (99%) → 热数据, 永不因冷数据被淘汰
    HIR 集合: 剩余容量 (1%)  → 冷数据, 可被随时淘汰
    PR 集合: 被驱逐的 HIR → 有资格晋升为 LIR 的候选

  访问命中时:
    LIR 命中 → 移动到 S 栈顶, 不变
    HIR 命中 → 移动到 S 栈顶, 若被驱逐则进入 PR

  淘汰时:
    优先淘汰 Q 队尾的 HIR → 缓存未命中时, 加载到 Q 队首
```

**图 3-30: LRU vs LIRS 缓存策略对比**

如图 3-30 所示，访问序列: A, B, C, D, E, F, A, G, H, I, J, K, A  (缓存容量=4)

LRU 行为:
  访问: A → [A]        (缓存未命中, 加载A)
  访问: B → [B, A]      (缓存未命中, 加载B)
  访问: C → [C, B, A]   (缓存未命中, 加载C)
  访问: D → [D, C, B, A] (缓存未命中, 加载D)
  访问: E → [E, D, C, B] (缓存已满, 淘汰A!)
  访问: F → [F, E, D, C] (淘汰B!)
  访问: A → [A, F, E, D] (淘汰C! 重新加载A)
  访问: G → [G, A, F, E] (淘汰D!)
  访问: H → [H, G, A, F] (淘汰E!)
  访问: I → [I, H, G, A] (淘汰F!)
  访问: J → [J, I, H, G] (淘汰A!! A 又被淘汰)
  访问: K → [K, J, I, H] (淘汰G!)
  访问: A → [A, K, J, I] (淘汰H! 再次重新加载A)

  → 扫描污染问题: A 被频繁访问, 但每次都被扫描"冷"数据挤出

LIRS 行为 (简化):
  维护两个集合:
    - LIR (热数据, 高复用距离): 固定容量, 通常占 99%
    - HIR (冷数据, 低复用距离): 剩余 1%

  关键区别: LIR 集合中的热数据不会因为冷数据的访问而被淘汰。
  A 一旦被识别为热数据 (两次以上访问), 就留在 LIR 中。

  访问: A → [A (LIR)]
  访问: B → [A (LIR), B (HIR)]
  ...扫描序列 E~K ...
  访问: A → [A (LIR), K (HIR)]
            ↑ A 始终在缓存中!

  → LIRS 有效抵抗了扫描污染

LIRS 算法通过区分"内引用间隔"和"外引用间隔"来判断数据是热还是冷。当全表扫描发生时，LRU 缓存会被扫描到的数据"污染"，热数据被挤出。而 LIRS 将频繁访问的数据标记为 Low Inter-reference Recency（LIR），将其固定在缓存中。即使大量冷数据到来，LIR 集合也不会被淘汰。这是 H2 在全表扫描场景下仍能保持良好缓存命中率的关键。`CacheLongKeyLIRS.java` 的实现使用了两个主要数据结构：一个 LIR 栈（Stack）记录所有缓存项的访问顺序，和一个 HIR 队列（Queue）管理冷数据。其核心方法 `get()` 和 `put()` 在 `CacheLongKeyLIRS.java:280-380` 实现了完整的 LIRS 算法逻辑。

---

### 3.7.5 mvstore.rtree 包 — 空间索引

**路径**: `org.h2.mvstore.rtree`

**关键类**:

| 类名 | 职责 |
|------|------|
| `MVRTreeMap.java` | R-Tree 空间索引的 Map 实现，支持多维范围查询 |
| `Spatial.java` | 空间对象的几何抽象接口 |
| `SpatialDataType.java` | 空间数据的序列化和反序列化 |

MVRTreeMap 是一棵支持动态插入/删除的 R-Tree，用于加速几何数据类型（如 `Geometry`）的空间查询（包含、相交、距离等）。

**图 3-31: R-Tree 空间索引结构**

```text
R-Tree (阶数=2, 空间维度=2):

                     ┌──────────────────────┐
                     │  根节点 (Root)         │
                     │  MBR: [0,0]→[100,100] │
                     │  ├─ Child1 MBR        │
                     │  └─ Child2 MBR        │
                     └──────────┬───────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │                                       │
   ┌────────▼────────┐                    ┌─────────▼─────────┐
   │ 内部节点 1       │                    │ 内部节点 2         │
   │ MBR: [0,0]       │                    │ MBR: [50,0]       │
   │      →[50,100]   │                    │      →[100,100]   │
   ├─────────────────┤                    ├──────────────────┤
   │ Child: Leaf A    │                    │ Child: Leaf C     │
   │ Child: Leaf B    │                    │ Child: Leaf D     │
   └────────┬────────┘                    └─────────┬─────────┘
            │                                       │
     ┌──────┴──────┐                         ┌──────┴──────┐
     │             │                         │             │
  ┌──▼──┐      ┌──▼──┐                  ┌───▼──┐      ┌───▼──┐
  │Leaf A│      │Leaf B│                  │Leaf C│      │Leaf D│
  │ rec1  │      │ rec3  │                  │ rec5  │      │ rec7  │
  │ rec2  │      │ rec4  │                  │ rec6  │      │ rec8  │
  └───────┘      └───────┘                  └───────┘      └───────┘

范围查询示例: 查找 [10,10]→[30,30] 区域内的记录
  Step 1: 从根节点开始, 检查 MBR 是否与查询范围相交
  Step 2: 递归进入相交的子节点
  Step 3: 到达叶子节点, 逐条检查记录是否在查询范围内
  Step 4: 返回所有符合条件的记录

  与传统 B-Tree 对比:
    B-Tree 只能处理一维范围查询
    R-Tree 可以高效处理二维及多维空间查询
    空间查询复杂度: O(logN) 平均, 最坏 O(N)
```

如图 3-31 所示，R-Tree 是 B-Tree 在多维空间上的推广。每个节点维护一个最小边界矩形（MBR, Minimum Bounding Rectangle），该矩形包围了其子节点所覆盖的所有空间数据。查询时，从根节点开始递归检查 MBR 是否与查询区域相交——如果不相交，则整个子树都可以跳过，从而实现空间剪枝。R-Tree 在 GIS（地理信息系统）和空间数据库中被广泛使用，H2 通过 `MVRTreeMap` 实现了对 `Geometry` 类型的高效空间查询支持。

**图 3-32: R-Tree 空间查询与 MBR 剪枝流程**

```text
空间范围查询: SELECT * FROM geom WHERE SHAPE && 'RECT(10,10,30,30)'

                    ┌──────────────────────────────┐
                    │  根节点 MBR: [0,0]→[100,100]  │
                    │  与查询区域相交 → 递归进入     │
                    └────────┬─────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
     ┌──────────▼──────────┐    ┌─────────▼───────────┐
     │ 内部节点 1            │    │ 内部节点 2            │
     │ MBR:[0,0]→[50,100]  │    │ MBR:[50,0]→[100,100]│
     │ 相交 → 继续搜索       │    │ 不相交 → 整树剪枝!   │
     └──────────┬──────────┘    └──────────────────────┘
                │
          ┌─────┴─────┐
          │           │
     ┌────▼────┐ ┌────▼────┐
     │Leaf A   │ │Leaf B   │
     │rec1[8,8] │ │rec3[25,20]│
     │rec2[12,10]││rec4[28,35]│
     └─────────┘ └─────────┘
          │           │
          ▼           ▼
     rec1∈范围    rec3∈范围
     rec2∈范围    rec4∈范围
     加入结果集    加入结果集

查询结果: 4 条记录匹配
剪枝跳过: 内部节点 2 的整棵子树
大表场景: R-Tree 剪枝可跳过 60~90% 的无效节点
```

如图 3-32 所示，该图展示了 R-Tree 在执行空间范围查询时的剪枝过程。查询从根节点开始，递归检查每个节点的 MBR 是否与查询区域相交——如果不相交，则该节点及其整棵子树都可以跳过，无需进一步搜索。在上述示例中，内部节点 2 的 MBR 完全在查询区域之外，因此其下的所有叶子节点都被直接跳过，减少了约 50% 的节点访问量。在大型空间数据集上，这种 MBR 剪枝通常可以将搜索范围缩小到整体数据的 10%~40%。

---

## 3.8 FileSystem 层

### 3.8.1 持久化与文件 I/O

#### 3.8.1.1 store 包 — 传统存储与序列化
**路径**: `org.h2.store`

**层定位**: 底层序列化工具和文件锁管理。v2.x 中大部分存储职责已迁移至 mvstore，但文件锁、数据序列化、LOB 管理等仍保留在此。

**关键类**:

| 类名 | 职责 |
|------|------|
| `FileStore.java`（实际位于 `org.h2.mvstore` 包） | 文件存储通道，提供读写锁管理和随机访问能力 |
| `FileLock.java` | 进程间文件锁协议，防止多个 JVM 进程同时打开同一数据库 |
| `Data.java` | 低层序列化工具，将基本类型和 Value 对象编码/解码为字节数组 |
| `LobStorageFrontend.java` | LOB（大对象）存储前端，将大值分割存储到 lob 表中 |

#### 3.8.1.2 store.fs 包 — 可插拔文件系统
**路径**: `org.h2.store.fs`

**层定位**: 抽象文件系统接口，支持多种后端实现。这是典型的策略模式。

**关键类**:

| 类名 | 职责 |
|------|------|
| `FilePath.java` | 抽象文件路径基类，定义 `newChannel()` / `newInputStream()` 等接口 |
| `FileUtils.java` | 静态工具方法，封装所有文件操作调用 |
| `FilePathDisk.java`（位于 `org.h2.store.fs.disk`） | 默认实现，基于 `java.nio.channels.FileChannel` |
| `FileMem.java`（位于 `org.h2.store.fs.mem`） | 纯内存文件系统，用于 `jdbc:h2:mem:` 模式 |
| `FileEncrypt.java`（位于 `org.h2.store.fs.encrypt`） | AES 加密文件系统，在读写时透明加解密 |
| `FilePathNioMapped.java`（位于 `org.h2.store.fs.niomapped`） | NIO 映射文件系统，使用 `FileChannel.map` 的零拷贝 I/O |
| `FileSplit.java`（位于 `org.h2.store.fs.split`） | 文件拆分，将大文件切分为 1GB 的片段 |
| `FileZip.java`（位于 `org.h2.store.fs.zip`） | ZIP 文件系统，支持从压缩包读取数据库文件 |

此外还有 `async/`、`rec/`、`retry/` 三个子包，分别对应 FilePathAsync、FilePathRec、FilePathRetryOnInterrupt 异步/重连/重试文件系统实现。

**文件系统栈**:

**图 3-33: FilePath 文件系统栈**

```text
FilePathDisk / FileMem / FileEncrypt
        │
        ▼
java.nio.channels.FileChannel
        │
        ▼
操作系统 VFS
```

**图 3-34: FilePath 装饰器模式层次**

```text
                        ┌──────────────┐
                        │  FilePath     │  ← 抽象基类
                        │  (abstract)   │
                        └──────────────┘
                              │
          ┌───────────────────┼────────────────────┐
          │                   │                    │
   ┌──────▼──────┐    ┌──────▼──────┐    ┌────────▼────────┐
   │ FilePathDisk │    │  FileMem    │    │ FilePathEncrypt │
   │ (本地磁盘)   │    │  (内存)     │    │ (加密, 装饰器)  │
   └──────────────┘    └─────────────┘    └────────┬────────┘
                                                   │ (装饰)
                                                   ▼
                                           ┌──────────────┐
                                           │ FilePathDisk  │
                                           │ (实际存储)    │
                                           └──────────────┘

  其他实现:
  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐
  │ FileNio    │  │ FileSplit  │  │ FileZip    │  │ FileNioMem│
  │ (NIO通道)  │  │ (文件分片)  │  │ (ZIP读取)  │  │ (NIO内存) │
  └────────────┘  └────────────┘  └────────────┘  └───────────┘
```

如图 3-34 所示，FilePath 系列采用了**策略模式 + 装饰器模式**的组合。`FilePath` 定义了统一的文件操作接口，各种具体实现提供了不同的后端策略。`FilePathEncrypt` 是装饰器模式的典型应用——它在不改变 FilePath 接口的前提下，透明地为文件 I/O 添加了 AES 加解密功能。当用户指定加密数据库时，H2 在初始化文件通道时创建 `FilePathEncrypt` 实例，其内部包装了 `FilePathDisk`。每次读写操作时，`FilePathEncrypt` 在数据到达磁盘之前完成加解密，对上层完全透明。

---

## 3.9 Server 层

### 3.9.1 server 包 — 多协议服务器

**路径**: `org.h2.server`

**层定位**: 让 H2 从嵌入式模式拓展为 C/S 模式，支持多种客户端协议。

**关键类**:

| 类名 | 职责 |
|------|------|
| `TcpServer.java` | TCP JDBC 服务器，实现与嵌入式完全一致的 JDBC 协议 |
| `PgServer.java` | PostgreSQL 线协议服务器，允许 pg 客户端连接 H2 |
| `WebServer.java` | HTTP Web 控制台服务器，提供浏览器管理界面 |

**多服务器架构**:

**图 3-35: 多协议服务器架构**

```text
Client Application
    │
    ├── jdbc:h2:tcp://localhost:9092 → TcpServer → SessionRemote → SessionLocal
    │
    ├── psql -h localhost -p 5435    → PgServer  → SessionLocal
    │
    └── http://localhost:8082        → WebServer → WebApp (H2 Console)
```

如图 3-35 所示，所有服务器在接收到请求后，最终都在本地创建 `SessionLocal` 实例，走与嵌入式模式完全相同的引擎路径。这使得服务器模式几乎没有额外的性能开销。

**图 3-36: TcpServer 线程模型与请求处理流程**

```text
TcpServer 线程模型:
┌───────────────────────────────────────────────────────────┐
│ TcpServer (主线程)                                         │
│  while(true) {                                            │
│    clientSocket = serverSocket.accept()  ← 阻塞等待连接    │
│    new Thread(new ClientHandler(clientSocket)).start()    │
│  }                                                        │
├───────────────────────────────────────────────────────────┤
│ ClientHandler 1 (线程)     │  ClientHandler 2 (线程)      │
│ while(true) {              │  while(true) {               │
│   request = readRequest()  │    request = readRequest()   │
│   session = getSession()   │    session = getSession()    │
│   result = session.exec()  │    result = session.exec()   │
│   writeResponse(result)    │    writeResponse(result)     │
│ }                          │  }                           │
└────────────────────────────┴──────────────────────────────┘

TcpServer 请求处理流程:
  Client                  TcpServer               SessionLocal          MVStore
    │                         │                       │                    │
    │── Handshake ──────────► │                       │                    │
    │◄─ SessionId ─────────── │                       │                    │
    │                         │                       │                    │
    │── Execute(sql, params)─►│── prepareCommand()───►│                    │
    │                         │                       │── Parser.parse()──►│
    │                         │                       │◄─ Prepared ───────│
    │                         │                       │                    │
    │                         │                       │── query() ────────►│
    │                         │                       │◄─ LocalResult ────│
    │◄─ ResultSet ───────────│◄──────────────────────│                    │
    │                         │                       │                    │
```

如图 3-36 所示，每个客户端连接在 TcpServer 中对应一个独立的处理线程。请求的处理流程遵循"反序列化 → 引擎执行 → 序列化结果"的模式。`SessionRemote` 在客户端扮演 `SessionLocal` 的代理——它将 JDBC 方法调用序列化为网络请求，发送到 TcpServer 端执行，再将执行结果反序列化返回给 `JdbcResultSet`。PgServer 则实现了 PostgreSQL 的线协议，使得任何支持 PostgreSQL 协议的客户端工具（如 `psql`、PgAdmin）都可以连接到 H2。共享同一引擎路径意味着：三种服务器模式（TCP、PG、Web）的查询优化和执行性能与嵌入式模式完全一致。

---

## 3.10 类型与结果

### 3.10.1 value 包 — 值类型系统

**路径**: `org.h2.value`

**层定位**: 定义 H2 内部的所有数据类型。每个 SQL 类型在运行期对应一个 `Value` 子类实例。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Value.java` | 抽象基类，定义 `getType()` / `getString()` / `compareTo()` / `convertTo()` |
| 约 20 个 `Value*` 子类 | `ValueInteger`, `ValueVarchar`, `ValueTimestamp`, `ValueNumeric`, `ValueBinary`, `ValueGeometry`, `ValueArray`, `ValueMap` (removed in v2.x), `ValueRow`, `ValueNull`, `ValueLob` 等 |
| `DataType.java` | SQL 类型 ↔ Java 类型的双向映射 |
| `TypeInfo.java` | 扩展类型元数据：精度、刻度、长度、枚举值 |
| `CompareMode.java` | 排序规则（collation），支持语言敏感的字符串比较 |

**类型转换**:

**图 3-37: 类型转换流程**

```text
ValueString → ValueNumeric:  "123.45" → 123.45
ValueInteger → ValueVarchar: 42 → "42"
ValueTimestamp → ValueDate:  2026-06-01 12:00:00 → 2026-06-01

调用链: Value.convertTo(TypeInfo)
           │
           ▼
        DataType.getTypeForTypeInfo()
           │
           ▼
        目标类型的 Value 子类构造函数
```

如图 3-37 所示，`Value` 对象是**不可变的**——所有转换操作返回新实例。这一设计简化了表达式求值中的引用管理和并发安全。

**图 3-38: Value 类型层次结构**

```text
Value (抽象基类)
  │
  ├── ValueNull          SQL NULL 的单例表示
  │
  ├── 数值类型
  │    ├── ValueBoolean      BOOLEAN (true/false)
  │    ├── ValueTinyint         TINYINT
  │    ├── ValueSmallint        SMALLINT
  │    ├── ValueInteger      INT / INTEGER
  │    ├── ValueBigint         BIGINT
  │    ├── ValueReal        REAL / FLOAT(24)
  │    ├── ValueDouble       DOUBLE / FLOAT(53)
  │    └── ValueNumeric      DECIMAL / NUMERIC (任意精度)
  │
  ├── 字符串类型
  │    ├── ValueVarchar      VARCHAR / VARCHAR2
  │    ├── ValueVarcharIgnoreCase  VARCHAR_IGNORECASE
  │    ├── ValueChar         CHAR
  │    └── ValueClob         CLOB (大文本, 流式读取)
  │
  ├── 时间类型
  │    ├── ValueDate         DATE (年-月-日)
  │    ├── ValueTime         TIME (时:分:秒)
  │    ├── ValueTimeTimeZone   TIME WITH TIME ZONE
  │    ├── ValueTimestamp    TIMESTAMP (年-月-日 时:分:秒.纳秒)
  │    └── ValueTimestampTimeZone  TIMESTAMP WITH TIME ZONE
  │
  ├── 二进制类型
  │    ├── ValueBinary        BINARY / VARBINARY
  │    └── ValueBlob         BLOB (大二进制, 流式读取)
  │
  ├── 复合类型
  │    ├── ValueArray        ARRAY (元素类型一致)
  │    ├── ValueMap (removed in v2.x)          MAP (键值对集合)
  │    └── ValueRow          ROW / 行类型 (命名或未命名字段)
  │
  ├── 空间类型
  │    └── ValueGeometry     GEOMETRY (WKB 编码)
  │
  ├── Java 互操作
  │    └── ValueJavaObject   JAVA_OBJECT (序列化 Java 对象)
  │
  └── 大对象代理
       └── ValueLob          LOB 代理 (数据存储在 lob 表中)
```

如图 3-38 所示，Value 类型层次结构反映了 H2 所支持的完整 SQL 数据类型体系。每个 `Value` 子类都是不可变的——`convertTo()` 返回新实例，`getString()` 返回格式化后的字符串。不可变性带来的好处是：表达式引擎中的中间计算结果可以安全地在多个线程之间共享，无需额外的同步保护。`ValueNumeric` 使用 `java.math.BigDecimal` 实现任意精度算术，`ValueLob` 对大对象采用延迟加载策略——实际数据存储在 lob 表中，ValueLob 只持有引用和元数据。

**图 3-39: 常见类型转换矩阵**

```text
源类型 \ 目标类型    INTEGER   VARCHAR   DECIMAL   TIMESTAMP   BOOLEAN
─────────────────────────────────────────────────────────────────────────
INTEGER            ────     '42'      42.00    异常         42≠0→TRUE
VARCHAR            parseInt  ────     新DECIMAL  parseTS     'true'→TRUE
DECIMAL            longValue toString ────      异常        非0→TRUE
TIMESTAMP          ｜       格式化    ｜        ────        异常
BOOLEAN            1/0     'TRUE'    1.00      异常         ────

典型转换逻辑 (在 Value.convertTo 中实现):
  INTEGER → VARCHAR:  ValueVarchar.get(stringCache = String.valueOf(integer))
  VARCHAR → INTEGER:  ValueInteger.get(Integer.parseInt(string))
  DECIMAL → INTEGER:  ValueInteger.get(bigDecimal.longValue())
  BOOLEAN → INTEGER:  ValueInteger.get(boolean ? 1 : 0)

异常情况:
  VARCHAR → INTEGER:  "abc" → NumberFormatException
  TIMESTAMP → BOOLEAN: 语义不兼容, 抛出异常
  NULL → ANY:  直接返回 ValueNull (空值传播)
```

如图 3-39 所示，类型转换矩阵展示了 SQL 类型之间的隐式转换规则。在表达式求值过程中，`BinaryOperation` 和 `CastSpecification` 会调用 `Value.convertTo(TypeInfo)` 来完成类型转换。转换规则的三个原则是：精度提升（INTEGER → DECIMAL 不会丢失精度）、语义兼容（DATE → TIMESTAMP 是安全的，但 BOOLEAN → TIMESTAMP 无意义）和空值传播（任何包含 NULL 的转换结果都是 NULL）。

---

### 3.10.2 result 包 — 结果集实现

**路径**: `org.h2.result`

**层定位**: 管理查询结果的传输、缓存和排序。

**关键类**:

| 类名 | 职责 |
|------|------|
| `LocalResult.java` | 内存结果集，支持 LIMIT / OFFSET 和 DISTINCT 的懒惰求值 |
| `Row.java` / `SearchRow.java` / `DefaultRow.java` | 行数据的不同表示：Row 完整行、SearchRow 索引搜索行 |
| `SortOrder.java` | 排序实现，支持多列升降序和 NULLS FIRST/LAST |
| `ResultInterface.java` | 结果集接口，`LocalResult` 和 `ResultRemote` 共同实现 |
| `RowFactory.java` | 行对象工厂，由 Store 提供具体实现 |

**图 3-40: LocalResult 结果集构造与迭代**

```text
LocalResult 构造过程:
  SELECT id, name FROM users ORDER BY name LIMIT 10

  TableFilter 遍历行 (可能数百万行)
       │
       ▼
  result.addRow(row)   ← 逐行添加到结果集缓冲区
       │
       ▼
  行数 > limit + offset?     ──是──→ 丢弃超出部分 (懒惰优化)
       │ 否
       ▼
  所有行处理完毕
       │
       ▼
  result.done()   ← 排序 + 去重 (若需要)
       │
       ├── 需要排序? → SortOrder.sort(rows) → TimSort
       ├── 需要 DISTINCT? → 哈希去重
       └── 需要 LIMIT/OFFSET? → 截取子列表
       │
       ▼
  result → JdbcResultSet

LocalResult 迭代:
  JdbcResultSet.next()
       │
       ▼
  LocalResult.next()
       │
       ├── 有预取数据? → 返回下一行
       └── 数据耗尽?   → close(), 释放资源
```

如图 3-40 所示，`LocalResult` 的设计亮点在于"懒惰"（lazy）求值。对于 `LIMIT 10` 的查询，`TableFilter` 每产生一行就调用 `addRow()`，而 `LocalResult` 内部维护一个大小为 `limit + offset + 1` 的滑动窗口——当行数超过窗口大小时，丢弃超出部分。这避免了为海量结果集分配完整的内存空间。`done()` 方法触发最终的排序和截断操作。对于 `ORDER BY` 查询，排序使用 TimSort（一种自适应归并排序），对已部分排序的数据具有 O(n) 的最佳时间复杂度。

---

## 3.11 安全与工具

### 3.11.1 security 包 — 认证与加密

**路径**: `org.h2.security`

**层定位**: 提供用户认证和存储加密。H2 支持文件级加密（AES）和密码哈希（SHA-256/SHA-3）。

**关键类**:

| 类名 | 职责 |
|------|------|
| `AES.java` | AES 加解密实现（纯 Java，无 JCE 依赖）。支持 128/256 位密钥 |
| `SHA256.java` | SHA-256 哈希实现 | |
| `SHA3.java` | SHA-3 哈希实现 |
| `Authenticator.java` / `DefaultAuthenticator.java` | 认证框架，支持可插拔的鉴权策略 |
| `XTEA.java` | XTEA 分组加密（用于旧版兼容性） |

**加密链路**:

**图 3-41: 加密与认证全流程**

```text
密码短语 → SHA256(password) → AES 密钥
    │
    ▼
FilePathEncrypt 在每次 I/O 操作时
    ├── 读: 从 FileChannel 读取密文 → AES.decrypt → 明文
    └── 写: 明文 → AES.encrypt → 写入 FileChannel
```

如图 3-41 所示，加密对上层完全透明。`FilePathEncrypt` 作为 `FilePath` 的装饰器，在 I/O 通道层面完成加解密，存储层和引擎层无需任何修改。

**图 3-42: 认证与加密的安全架构**

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     安全架构层次                                      │
├─────────────────────────────────────────────────────────────────────┤
│ 认证层 (Authentication)                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Authenticator (接口) ← DefaultAuthenticator (默认实现)        │   │
│  │   authenticate(name, password) → User                        │   │
│  │     ├── SHA256(password + salt) → 密码哈希                   │   │
│  │     └── 与存储的哈希值比对                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ 授权层 (Authorization)                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ User / Role / Right (权限模型)                                 │   │
│  │   ┌──────────┐      ┌──────────┐      ┌──────────┐          │   │
│  │   │ User     │──────│ Role     │──────│ Right    │          │   │
│  │   │ (用户)   │      │ (角色)   │      │ (权限)   │          │   │
│  │   └──────────┘      └──────────┘      └──────────┘          │   │
│  │ Right: SELECT/INSERT/UPDATE/DELETE on Table/Schema/Global    │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ 加密层 (Encryption at Rest)                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ FilePathEncrypt (装饰器模式)                                   │   │
│  │   ├── 启动时: 用户提供密码 → SHA256 → AES-128/256 密钥       │   │
│  │   ├── 文件头: 存储加密盐 (salt) 和校验和                      │   │
│  │   ├── 读路径: 128-bit 密文块 → AES/CBC 解密 → 明文块         │   │
│  │   └── 写路径: 明文块 → AES/CBC 加密 → 128-bit 密文块         │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

如图 3-42 所示，安全架构分为三层：认证层验证用户身份，授权层控制数据访问权限，加密层保护静态数据。认证使用 SHA-256 加盐哈希存储密码，防止彩虹表攻击。加密使用 AES/CBC 模式，每个 128 位块独立加密，密钥通过用户提供的密码短语派生。`FilePathEncrypt` 作为装饰器位于 I/O 栈中，其加解密过程对上层完全透明——存储层和引擎层感知不到加密的存在。`Authenticator` 采用策略模式，允许用户自定义认证逻辑（如集成 LDAP 或 OAuth）。

---

### 3.11.2 tools 包 — 运维工具

**路径**: `org.h2.tools`

**层定位**: 提供数据库运维的全部命令行工具。

**关键类**:

| 类名 | 职责 |
|------|------|
| `Server.java` | 统一服务器入口，启动 TcpServer/PgServer/WebServer |
| `Shell.java` | 交互式 SQL Shell 客户端 |
| `RunScript.java` / `Script.java` | SQL 脚本执行/导出 |
| `Backup.java` / `Restore.java` | 数据库备份与恢复 |
| `Recover.java` / `DirectRecover.java` | 从损坏的数据库文件中恢复数据 |
| `Csv.java` | CSV 文件读写工具 |
| `CompressTool.java` | 压缩工具（LZF/Deflate） |
| `DeleteDbFiles.java` | 删除数据库文件 |

**图 3-43: tools 包工具分类与用途**

```text
org.h2.tools 工具分类:
┌────────────────────────────────────────────────────────────┐
│             运维工具分类                                      │
├────────────────────────────────────────────────────────────┤
│ 启动与管理                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Server   │  │ Shell    │  │ Console  │  │ DeleteDb │  │
│  │ (启动器)  │  │ (SQL Shell)│  │ (Web控制台)│  │ (删除文件)│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
├────────────────────────────────────────────────────────────┤
│ 数据迁移                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Script   │  │ RunScript│  │ Csv      │                  │
│  │ (导出SQL) │  │ (执行SQL) │  │ (CSV读写) │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
├────────────────────────────────────────────────────────────┤
│ 备份恢复                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Backup   │  │ Restore  │  │ Recover  │                  │
│  │ (备份)    │  │ (还原)    │  │ (数据恢复) │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
├────────────────────────────────────────────────────────────┤
│ 压缩                                                        │
│  ┌──────────┐                                               │
│  │ Compress │                                               │
│  │ (LZF/Deflate) │                                          │
│  └──────────┘                                               │
└────────────────────────────────────────────────────────────┘

工具依赖关系:
  Server ──→ TcpServer, PgServer, WebServer (启动后依赖 engine)
  Script  ──→ engine (导出表结构和数据)
  Backup  ──→ store.fs (文件级别备份)
  Recover ──→ mvstore (直接解析 MVStore 文件)
  Csv     ──→ value (CSV 类型转换)
```

如图 3-43 所示，`Recover.java` 和 `DirectRecover.java` 是 H2 数据库运维中最关键的工具。当数据库文件因系统崩溃或硬件故障而损坏时，`Recover` 可以直接扫描 MVStore 文件的 chunk 结构，提取所有可读的页数据，并生成 SQL 恢复脚本。这一工具使用了 mvstore 的内部 API 来直接读取 chunk、解析页结构和反序列化行数据，绕过了 SQL 引擎层和事务层。`Script` 和 `RunScript` 则用于逻辑备份与恢复——它们导出的是纯 SQL 语句，可以在不同版本的 H2 之间迁移数据。

**图 3-44: Recover 工具数据恢复流程**

```text
Recover 工具由损坏文件重建数据库的完整流程:

    损坏的 .mv.db 文件
         │
         ▼
    ┌──────────────────────────────────────────┐
    │ Step 1: 扫描文件头, 定位所有 chunk 位置   │
    └────────────────┬─────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────┐
    │ Step 2: 逐 chunk 遍历与校验               │
    │ ├── 解析 Chunk Header (id, 页数, 版本)   │
    │ ├── 校验和验证                           │
    │ ├── 通过 → 提取页数据                     │
    │ └── 损坏 → 跳过 (记录警告日志)           │
    └────────────────┬─────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────┐
    │ Step 3: 页数据反序列化                    │
    │ ├── Leaf Page → 提取键值对 → 行数据      │
    │ ├── Internal Page → 提取子节点索引       │
    │ └── Meta Page → 提取元数据 (表结构)       │
    └────────────────┬─────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────┐
    │ Step 4: 生成 recovery.sql                │
    │ ├── CREATE TABLE (从元数据重建表结构)     │
    │ ├── CREATE INDEX (重建索引定义)          │
    │ └── INSERT INTO (逐行插入可恢复的数据)    │
    └────────────────┬─────────────────────────┘
                     │
                     ▼
    Step 5: 用户执行 recovery.sql → 重建数据库

关键设计: 恢复过程完全绕过 SQL 引擎层和事务层,
         直接解析 MVStore 文件格式.
```

如图 3-44 所示，Recover 的数据恢复流程是五步流水线：扫描文件头获取 chunk 索引表 → 逐个读取 chunk 并验证校验和 → 反序列化页数据为行记录 → 根据元数据生成 DDL 和 DML 脚本 → 用户执行脚本完成重建。绕过引擎层设计的好处是：即使引擎层元数据损坏（如系统表无法打开），Recover 仍然可以直接从文件结构层提取数据。

---

### 3.11.3 util 包 — 通用工具

**路径**: `org.h2.util`

**层定位**: 零散的通用工具类，被各层广泛使用，为整个数据库提供基础能力支撑。

**图 3-45: util 工具类分类与用途**

```text
                        org.h2.util
                            │
           ┌────────────────┼──────────────────┐
           │                │                  │
           ▼                ▼                  ▼
   ┌─────────────────┐ ┌──────────┐  ┌──────────────────┐
   │   基础工具类      │ │ 网络工具   │  │   集合与缓存      │
   ├─────────────────┤ ├──────────┤  ├──────────────────┤
   │ Utils.java      │ │NetUtils  │  │ SmallMap.java     │
   │  (集合/数组)     │ │ (地址解析) │  │ (紧凑 LRU 缓存)   │
   │                 │ │          │  │                  │
   │ MathUtils.java  │ │          │  │ CacheWriter.java │
   │  (安全随机数)    │ │          │  │ (缓存回写)        │
   │                 │ │          │  │                  │
   │ StringUtils.java│ │          │  │ Bits.java        │
   │  (引号/转义)     │ │          │  │ (位操作)          │
   │                 │ │          │  │                  │
   │ IOUtils.java    │ │          │  │                  │
   │  (流复制)       │ │          │  │                  │
   └─────────────────┘ └──────────┘  └──────────────────┘

  调用模式: util 包被 engine/command/store 等广泛使用
             Engine.java ─→ Utils.java   (集合操作)
             Store.java  ─→ IOUtils.java (文件读写)
             Server.java ─→ NetUtils.java(端口绑定)
```

如图 3-45 所示，**关键类**:

| 类名 | 职责 | 被调用方 |
|------|------|----------|
| `Utils.java` | 集合操作（`newSmallArrayList`、`newHashMap`）、数组比较 | engine, command, store |
| `MathUtils.java` | 安全随机数生成（`secureRandomInt`）、数学工具 | security, mvstore |
| `StringUtils.java` | SQL 引号处理、UNICODE 转义、大小写转换 | engine, parser |
| `NetUtils.java` | IP 地址解析、端口检查（`checkSocket`）、连接池管理 | server |
| `CacheWriter.java` | 缓存回写回调接口，由 MVStore 实现 | mvstore |
| `Bits.java` | 位操作工具（`readInt`、`writeLong` 等字节级别操作） | store, mvstore |
| `IOUtils.java` | 流复制（`copy`、`copyAndClose`）、文件读写辅助 | store, tools |
| `SmallMap.java` | 紧凑型 LRU 缓存实现，用于小型查找表 | engine |

这些工具类虽零散，但构成了 H2 各层间的基础设施层。例如 `StringUtils.java` 中的 `quoteStringSQL()` 方法被 parser 和 engine 广泛用于生成规范化的 SQL 输出；`MathUtils.java` 中的 `secureRandomInt()` 方法为 `security` 包提供密码学强度的随机数，确保会话 ID 和加密密钥的不可预测性。

### 3.11.4 compress 包 — 压缩算法

**路径**: `org.h2.compress`

**层定位**: 为 MVStore 页面压缩提供可插拔的压缩算法实现，在持久化路径中透明工作。

**图 3-46: 压缩在写入路径中的位置**

```text
  SQL 写入
     │
     ▼
  MVMap.put(key, value)
     │
     ▼
  Page 序列化为字节流 (Page.java:write)
     │
     ▼
  ┌─────────────────────────────────────┐
  │  压缩选择 (CompressLZF / Deflate)   │
  │                                     │
  │  检查 pageSettings.compressData:    │
  │    ├── false     → 不压缩, 直接写入  │
  │    ├── true+LZF  → CompressLZF.compress()  ← 默认
  │    └── true+高   → CompressDeflate.compress()
  │                                     │
  │  压缩判断: 若 compressLen >= len    │
  │  则不压缩 (存储原始数据)             │
  └──────────────┬──────────────────────┘
                 │
                 ▼
  Chunk 追加写入文件 (SingleFileStore.write)
     │
     ▼
  文件系统 (FileChannel / FilePathDisk)
```

如图 3-46 所示，**关键类**:

| 类名 | 职责 | 特性 |
|------|------|------|
| `CompressLZF.java` | LZF 快速压缩算法 | 压缩快、解压极快、压缩率 40-50%、默认选项 |
| `CompressDeflate.java` | 标准 Deflate 压缩算法（ZIP 格式） | 压缩率高 50-70%、CPU 开销大、可选 |

`CompressLZF` 是 H2 默认的页面压缩算法，设计上追求极低的 CPU 开销，适合 OLTP 场景。LZF 算法的核心思想是查找字节序列中的重复模式并用（偏移量, 长度）对替换。`CompressLZF.compress()` 在 `CompressLZF.java:158` 实现，使用哈希表快速定位重复序列。解压 `expand()` 方法在 `CompressLZF.java:370`，通过简单的内存拷贝操作还原数据，解压速度可达压缩的 3-5 倍。

`CompressDeflate` 则使用 Java 标准库的 `java.util.zip.Deflater`，提供更高的压缩率但 CPU 开销显著增加。适用于存储空间敏感但读取频率较低的归档场景。

**图 3-47: LZF 与 Deflate 压缩算法特性对比**

```text
LZF vs Deflate 压缩算法特性对比:

┌──────────────────┬─────────────────────┬─────────────────────┐
│ 特性              │ CompressLZF         │ CompressDeflate     │
├──────────────────┼─────────────────────┼─────────────────────┤
│ 算法类型          │ 快速 LZ 变体        │ Deflate (ZIP)       │
│ 压缩速度          │ 极快 (~200 MB/s)    │ 较慢 (~20 MB/s)     │
│ 解压速度          │ 极快 (~800 MB/s)    │ 中等 (~100 MB/s)    │
│ 典型压缩比        │ 1.5:1 ~ 2.5:1      │ 2:1 ~ 5:1           │
│ CPU 开销          │ 低                  │ 高 (Huffman 编码)   │
│ 内存占用          │ ~64KB 滑动窗口      │ 32~256KB 可配置     │
│ 实现方式          │ 纯 Java             │ java.util.zip       │
├──────────────────┼─────────────────────┼─────────────────────┤
│ 适用场景          │ OLTP 高频写入       │ 归档 / 空间敏感     │
│ H2 默认选项       │ 是                  │ 否 (需用户启用)     │
└──────────────────┴─────────────────────┴─────────────────────┘

LZF 压缩示例 ("ABCABCABCD"):
  输入: A B C A B C A B C D
        │   │           │
        ▼   ▼           ▼
  第 1~3 字节: "ABC" → 字面量输出
  第 4~9 字节: 匹配到前面 "ABC" (偏移量=3, 长度=6) → 引用对 (3, 6)
  第 10 字节:  "D" → 字面量输出

  压缩前: 10 字节    压缩后: 4 字节 (3 字面量 + 2 引用 + 1 字面量)
  压缩比: 2.5:1      解压速度: ~800 MB/s (纯内存拷贝)
```

如图 3-47 所示，该对比表说明了 H2 选择 LZF 作为默认压缩算法的原因：OLTP 场景下写入操作频繁，压缩和解压速度比压缩率更重要。LZF 使用简化的 LZ77 变体，只查找重复序列并用引用对替换，省去了 Deflate 中复杂的 Huffman 编码步骤。对于数据库页面这类含有大量重复模式的数据（如数字类型的零填充、字符串的公共前缀），LZF 可以在极低的 CPU 开销下获得 40%~60% 的空间节省。而 CompressDeflate 适合读取少、空间贵的归档场景，通常在备份操作中使用。

### 3.11.5 mode 包 — SQL 兼容模式

**路径**: `org.h2.mode`

**层定位**: 提供多数据库方言兼容层，使 H2 能模拟 MySQL、Oracle、PostgreSQL 等数据库的 SQL 语法和函数行为。

**图 3-48: SQL 兼容模式架构**

```text
  用户连接 ──→ SET MODE MySQL/Oracle/PostgreSQL
                    │
                    ▼
              ┌─────────────┐
              │  Mode.java   │  ← 语法规则开关
              │             │
              │  规则矩阵:   │
              │  allowXXX   │
              │  supportXXX │
              │  treatXXX   │
              └──────┬──────┘
                     │
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
  ┌────────────┐ ┌────────┐ ┌──────────────┐
  │Functions   │ │Functions│ │Functions     │
  │MySQL.java  │ │Oracle   │ │PostgreSQL    │
  │            │ │.java    │ │.java         │
  │ NOW()      │ │ NVL()   │ │ ...          │
  │ IFNULL()   │ │ DECODE()│ │              │
  │ GROUP_CONCAT│ │ TO_DATE │ │              │
  │ ...        │ │ ...     │ │              │
  └────────────┘ └────────┘ └──────────────┘
                     │
                     ▼
              ┌──────────────┐
              │  Parser.java  │ ← 模式感知解析
              │               │
              │ 根据 Mode 规则 │
              │ 调整语法解析路径│
              └──────────────┘

  工作流程:
  1. 用户执行 SET MODE MySQL
  2. Database.java 设置 session 的 Mode 对象
  3. Parser.java 解析 SQL 时查询 Mode 规则
  4. FunctionsMySQL 注册 MySQL 特有函数到 Function 表
  5. 执行函数调用时按模式分发到对应实现
```

**关键类**:

| 类名 | 职责 |
|------|------|
| `FunctionsMySQL.java` | MySQL 兼容函数（`NOW()`、`IFNULL()`、`GROUP_CONCAT()` 等 MySQL 方言） |
| `FunctionsOracle.java` | Oracle 兼容函数（`NVL()`、`DECODE()`、`TO_DATE()` 等） |
| `FunctionsPostgreSQL.java` | PostgreSQL 兼容函数 |

当用户执行 `SET MODE MySQL` 后，`Mode.java` 中的规则控制语法差异，而 `FunctionsMySQL` 等类提供特有的函数定义。`Mode.java` 位于 `org.h2.engine` 包中（而非 mode 包），定义了大量布尔开关如 `mode.nullConcatIsNull`（MySQL 的 `NULL || 'x'` 行为）、`mode.serialColumn`（Oracle 的序列语法）等。mode 包中的 `Functions*` 类通过 `Function.addFunction()` 在启动时注册到全局函数表，解析器根据当前 Mode 在函数名查找时匹配对应的实现类。

**图 3-49: 模式函数注册与运行时解析**

  系统启动时:

```text
  ┌─────────────────────────────────────────────┐
  │  Function.addFunction() 注册模式特有函数      │
  │  FunctionsMySQL   → NOW, IFNULL, ...        │
  │  FunctionsOracle  → NVL, DECODE, ...        │
  │  FunctionsPostgreSQL → ...                   │
  └──────────────────┬──────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────┐
  │  全局函数表                                   │
  │  ┌───────────┬──────────────────────────┐   │
  │  │ 函数名     │ 可用模式                  │   │
  │  ├───────────┼──────────────────────────┤   │
  │  │ NOW()     │ 默认, MySQL              │   │
  │  │ NVL()     │ Oracle                   │   │
  │  │ IFNULL()  │ MySQL                    │   │
  │  │ DECODE()  │ Oracle                   │   │
  │  └───────────┴──────────────────────────┘   │
  └──────────────────┬──────────────────────────┘
                     │
                     ▼
```
  运行时:

```text
  SET MODE Oracle → SELECT NVL(col, 0) FROM t
       │
       ▼
  ┌─────────────────────────────────────────────┐
  │  Parser 解析函数调用 NVL()                    │
  │                                             │
  │  1. Function.getFunction("NVL", mode)       │
  │  2. 查找函数表 → 存在                        │
  │  3. mode=Oracle 匹配 → 返回 Oracle 实现      │
  │  4. 执行: OracleNVL.getValue(col, 0)         │
  └─────────────────────────────────────────────┘
```

---

## 3.12 包间依赖总结

**图 3-50: 包间完整依赖关系图**

```text
                   用户应用程序
                       │
              ┌────────┴────────┐
              │   org.h2.jdbc   │  JDBC 标准接口实现
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │ org.h2.server   │  多协议服务器
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │ org.h2.engine   │  引擎核心
              └────────┬────────┘
                       │
         ┌─────────────┼──────────────┐
         │             │              │
   ┌─────┴─────┐ ┌────┴────┐  ┌──────┴──────┐
   │ command   │ │  table  │  │ constraint  │
   └─────┬─────┘ └────┬────┘  └──────┬──────┘
         │            │              │
   ┌─────┴─────┐ ┌────┴────┐        │
   │expression │ │  index  │        │
   └───────────┘ └────┬────┘        │
                      │             │
              ┌───────┴──────────────┘
              │
         ┌────┴──────────┐
         │ mvstore.tx    │  事务引擎
         └────┬──────────┘
              │
         ┌────┴──────────┐
         │ mvstore.db    │  关系→键值桥接
         └────┬──────────┘
              │
         ┌────┴──────────┐
         │ mvstore       │  键值存储引擎
         └────┬──────────┘
              │
   ┌──────────┼──────────┐
   │          │          │
┌──┴──┐  ┌────┴────┐ ┌──┴──┐
│value│  │ store   │ │ util│
│result│ │ store.fs│ │     │
└──────┘ └─────────┘ └─────┘
```

**图 3-51: 层间依赖矩阵统计**

```text
┌─────────────────────┬─────────────────────────────────────────────┐
│ 层                  │ 包含包                                      │
├─────────────────────┼─────────────────────────────────────────────┤
│ 接入层 (Access)     │ jdbc, jdbcx, server                        │
│ 引擎层 (Engine)     │ engine, command, table, index, expression  │
│                     │ constraint                                  │
│ 存储层 (Storage)    │ mvstore, mvstore.db, mvstore.tx           │
│                     │ mvstore.cache, mvstore.rtree               │
│ 类型与结果层 (Type)  │ value, result                              │
│ I/O 层 (IO)         │ store, store.fs                            │
│ 工具层 (Utility)    │ util, security, compress, mode, tools      │
├─────────────────────┼─────────────────────────────────────────────┤
│ 总包数              │ 25 个一级和二级子包                          │
│ 源码文件数          │ ~843 个 Java 文件                           │
│ 核心单向依赖路径     │ Access → Engine → Storage → Type → IO     │
│ 工具层使用方式       │ 被所有层引用, 不参与分层依赖                │
└─────────────────────┴─────────────────────────────────────────────┘
```

如图 3-51 所示，**包间依赖的四个层级**:

1. **I/O 层**（底部）: `store.fs` → `store` → `value`
2. **存储层**: `mvstore` → `mvstore.db` → `mvstore.tx`
3. **SQL 层**: `table` → `index` → `expression` → `command` → `engine`
4. **接入层**: `jdbc` / `server` → `engine`

每一层都只依赖其正下方的层，没有跳层或反向依赖。这种严格的**分层依赖**是 H2 代码可维护性的基石——替换存储引擎（PageStore → MVStore）对上层的影响被控制在 mvstore.db 的桥接层内。

**图 3-52: 包间依赖中的设计模式分布**

```text
┌────────────────────────────────────────────────────────────────────┐
│ 包                    │ 主要设计模式                                │
├────────────────────────────────────────────────────────────────────┤
│ store.fs              │ 策略模式 (FilePath 多种实现)               │
│                       │ 装饰器模式 (FileEncrypt 包装 FileDisk)     │
├────────────────────────────────────────────────────────────────────┤
│ mvstore               │ COW (写入时复制)                           │
│                       │ CAS (无锁读写的关键)                       │
├────────────────────────────────────────────────────────────────────┤
│ command               │ 模板方法 (Prepared.update/query)          │
│                       │ 组合模式 (Prepared 树)                     │
├────────────────────────────────────────────────────────────────────┤
│ expression            │ 组合模式 (表达式树)                        │
│                       │ 访问者模式 (ExpressionVisitor)             │
├────────────────────────────────────────────────────────────────────┤
│ jdbc                  │ 外观模式 (统一 JDBC 接口)                  │
│                       │ 适配器模式 (JDBC → engine API)             │
├────────────────────────────────────────────────────────────────────┤
│ server                │ 策略模式 (多协议支持)                      │
│                       │ 代理模式 (SessionRemote)                   │
├────────────────────────────────────────────────────────────────────┤
│ store                 │ 适配器模式 (FileStore 封装 FileChannel)    │
├────────────────────────────────────────────────────────────────────┤
│ security              │ 策略模式 (Authenticator)                   │
│                       │ 装饰器模式 (FilePathEncrypt)               │
├────────────────────────────────────────────────────────────────────┤
│ mvstore.db            │ 桥接模式 (关系模型 ↔ KV 存储)             │
└────────────────────────────────────────────────────────────────────┘
```

如图 3-52 所示，H2 大量使用了经典的设计模式来实现关注点分离、可扩展性和可测试性。`store.fs` 的策略模式使得新增文件系统后端（如云存储）只需实现 `FilePath` 接口；`expression` 的访问者模式使得添加新的表达式处理逻辑（如类型检查、权限验证）无需修改 Expression 子类；`command` 的模板方法模式将 SQL 执行的通用流程（权限检查、锁获取、日志记录）固化在 `Prepared` 基类中，子类只需实现具体的业务逻辑。

---

## 3.13 本章小结

本章系统性地遍历了 `org.h2` 的全部核心包：

- **引擎层**（engine / command / expression / table / index）承担了 SQL 解析、编译、优化和执行的完整链路，覆盖约 40% 的源码文件。其中 `Parser.java` 以超过 9300 行的规模成为 H2 源码中最大的单个文件，而 `Expression` 的三层接口设计（mapColumns → optimize → getValue）是理解整个表达式求值系统的关键。

- **存储层**（mvstore / mvstore.db / mvstore.tx / store / store.fs）实现了从 B-Tree 键值存储到 MVCC 关系表的完整堆栈，是 H2 v2.x 架构升级的核心。MVStore 的无锁读取 + COW 写入设计使得 H2 在 OLTP 场景下具有极高的并发吞吐量。LIRS 缓存算法进一步保证了热数据在大量扫描操作下的缓存命中率。

- **接入层**（jdbc / jdbcx / server）将存储与计算能力通过多种协议暴露给外部应用。无论是标准的 JDBC 调用、PostgreSQL 协议客户端还是 Web 控制台，最终都走相同的引擎执行路径。这种"薄封装"设计使协议扩展的成本极低。

- **类型与结果层**（value / result）支撑了所有 SQL 数据类型的表示和查询结果的封装。Value 的不可变设计简化了并发安全，LocalResult 的懒惰求值控制了内存占用。

- **安全与工具层**（security / tools / util / compress / mode）提供了加密、运维、兼容性等辅助能力。加密通过 FilePath 装饰器实现透明加解密，运维工具通过直接访问 MVStore 内部结构实现数据恢复。

**图 3-53: 各包源码规模统计**

```text
包名                    │ 文件数 │ 核心文件行数 (估算)
─────────────────────────────────────────────────────
org.h2.engine           │ ~45   │ Database(2500+), SessionLocal(2100+)
org.h2.command          │ ~104  │ Parser(9300+), Select(2000+)
org.h2.expression       │ ~146  │ 20+ 子类, 每个 200-800 行
org.h2.table            │ ~50   │ Table(1000+), TableFilter(1500+)
org.h2.index            │ ~20   │ Index, IndexCondition
org.h2.mvstore          │ ~30   │ MVStore(2000+), MVMap(2170)
org.h2.mvstore.db       │ ~25   │ MVTable(1012), Store(384)
org.h2.mvstore.tx       │ ~15   │ Transaction, TransactionMap
org.h2.store            │ ~40   │ FileStore, Data
org.h2.store.fs         │ ~25   │ 15+ FilePath 实现
org.h2.value            │ ~60   │ 20+ Value 子类 + DataType
org.h2.result           │ ~20   │ LocalResult, SortOrder
org.h2.jdbc             │ ~20   │ JdbcConnection(1900+)
org.h2.server           │ ~20   │ TcpServer, PgServer
org.h2.security         │ ~15   │ AES, SHA256
org.h2.tools            │ ~20   │ Server, Shell, Recover
─────────────────────────────────────────────────────
总计                    │ ~545  │ (核心包不完全统计，剩余 ~300 分布在 test/util/mode 等)
```

如图 3-53 所示，注：以上为核心包不完全统计，完整H2源码包含843个Java文件。

各包之间严格的单向依赖关系是 H2 架构设计的核心约束，也是理解整个代码库的导航地图。后续章节将深入核心模块的源码实现和关键算法。

## 3.14 延展阅读

- H2 官方文档《Architecture》(`h2/src/docsrc/html/architecture.html`) — 各层组件概述
- 本书第2章《分层模块划分》 — 各层的抽象职责与交互关系
- 本书第4-5章《核心模块与流程》 — Command/Expression 模块的详细分析
- 本书第9章《持久化引擎深度解析》 — MVStore 和 FileSystem 层的深入分析
