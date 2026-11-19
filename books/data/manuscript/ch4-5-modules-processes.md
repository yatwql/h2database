# 第4章 核心模块深度解读

> **本章导读**: 本章深入分析 H2 的 Command、Expression 和 Table/Index 三个核心层的模块设计和类职责。同时介绍 TransactionStore 事务存储和 MVMap 数据结构的实现机制。
> **前置知识**: 第2章《分层模块划分》§2.4-2.8（Command/Expression/Table-Index 层概览）；第3章《核心包结构详解》§3.5-3.6（对应包的类结构）
> **章节要点**:
> - 理解 Command 接口的设计模式和命令分类
> - 掌握 Expression 层的表达式树结构与求值机制
> - 熟悉 Table/Index 层的抽象层次和实现类
> - 了解 TransactionStore 的事务存储机制
> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 4.1 数据库全局中枢

**核心文件**: `org/h2/engine/Database.java` (2520 行)

Database 是 H2 数据库实例的全局中枢，实现了 `DataHandler` 和 `CastDataProvider` 接口。每个打开的数据库对应一个 Database 实例。

### 4.1.1 核心职责
- 管理 Schema、User、Role、Sequence、Constant、TableEngine 等元数据
- 协调数据库的 open/close 生命周期
- 控制 checkpoint、后台任务调度
- 持有 metadata lock 用于元数据并发控制

```text
如图 4-1 所示，┌──────────────────────────────────────┐
│  协调层                              │
│  checkpoint 触发 / 后台任务调度      │
├──────────────────────────────────────┤
│  生命周期层                          │
│  数据库 open / close 协调           │
├──────────────────────────────────────┤
│  元数据管理层                        │
│  Schema / User / Role / Sequence     │
│  Constant / TableEngine              │
├──────────────────────────────────────┤
│  并发控制层                          │
│  Metadata Lock 元数据并发            │
└──────────────────────────────────────┘
```
**图 4-1: 概览 Database 协调与元数据管理四层职责**
```text
如图 4-2 所示，外部请求 → Database
  │
  ├── open() 启动阶段
  │     ├─ 初始化 Store (MVStore)
  │     ├─ 注册内置 Schema (main/info/pg_catalog)
  │     ├─ 加载系统表
  │     └─ 恢复未完成事务
  │
  ├── 运行时阶段
  │     ├─ Schema/Table 元数据读写
  │     ├─ 会话管理 (userSessions)
  │     └─ Checkpoint 后台刷盘
  │
  └── close() 关闭阶段
        ├─ 关闭所有会话
        ├─ 提交未完成事务
        ├─ 关闭存储引擎
        └─ 释放文件锁
```
**图 4-2: 梳理 Database 启动与关闭的阶段顺序**

### 4.1.2 关键字段

```java
// Database.java:137-141 — 元数据容器
private final ConcurrentHashMap<String, RightOwner> usersAndRoles;
private final ConcurrentHashMap<String, Setting> settings;
private final ConcurrentHashMap<String, Schema> schemas;    // Schema 注册表
private final ConcurrentHashMap<String, Right> rights;
private final ConcurrentHashMap<String, Comment> comments;

// Database.java:150-152 — 内置 Schema
private final Schema mainSchema;
private final Schema infoSchema;        // INFORMATION_SCHEMA
private final Schema pgCatalogSchema;   // PG_CATALOG

// Database.java:207 — MVStore 桥接层
private final Store store;

// Database.java:145 — 活跃会话集合
private final Set<SessionLocal> userSessions;
```
```text
如图 4-3 所示，┌──────────────────────────────────────────────────┐
│  元数据容器 (ConcurrentHashMap)                   │
│  ┌──────────┬─────────┬──────────┬──────────────┐│
│  │ schemas  │ rights  │ settings │   comments   ││
│  └──────────┴─────────┴──────────┴──────────────┘│
│  ┌──────────┬───────────────────────────────────┐│
│  │ usersAndRoles                                ││
│  └──────────┴───────────────────────────────────┘│
├──────────────────────────────────────────────────┤
│  内置 Schema (final 常量)                        │
│  ┌────────────┬─────────────┬─────────────────┐  │
│  │ mainSchema │ infoSchema  │ pgCatalogSchema │  │
│  └────────────┴─────────────┴─────────────────┘  │
├──────────────────────────────────────────────────┤
│  桥接 & 会话                                     │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Store store  │  │ userSessions             │  │
│  │ (MVStore 桥接)│  │ Set<SessionLocal>       │  │
│  └──────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────┘
```
**图 4-3: 梳理 Database 元数据容器与会话字段分组**
```text
    如图 4-4 所示，schemas ────→ Schema (main/info/pg_catalog)
       │
       ├──→ Right ─────→ usersAndRoles
       ├──→ Setting
       └──→ Comment
                        Store ───→ MVStore
                           │
                           └──→ FileStore
    userSessions ──→ SessionLocal[]
```
**图 4-4: 刻画 Database 字段间的依赖与引用关系**

### 4.1.3 架构图

```text
┌──────────────────────────────────────────────────────────────┐
│                        Database                              │
│  implements DataHandler, CastDataProvider                    │
├──────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌──────────────────────────────────┐ │
│  │  schemas           │  │  usersAndRoles                   │ │
│  │  ┌ main            │  │  ┌ systemUser (DBA)             │ │
│  │  ├ information     │  │  ├ user1                        │ │
│  │  ├ pg_catalog      │  │  └ role1                        │ │
│  │  └ user_schemas... │  │                                  │ │
│  └───────────────────┘  └──────────────────────────────────┘ │
│                                                              │
│  ┌───────────────────┐  ┌──────────────────────────────────┐ │
│  │  Store store       │──│  MVStore (持久化引擎)             │ │
│  │  (桥接层)          │  │   ┌ FileStore                    │ │
│  └───────────────────┘  │   ├ MVMap[]                      │ │
│                         │   └ TransactionStore             │ │
│  ┌───────────────────┐  └──────────────────────────────────┘ │
│  │  userSessions      │                                      │
│  │  ┌ SessionLocal 1  │  ┌──────────────────────────────┐   │
│  │  ├ SessionLocal 2  │  │  meta table (sys)            │   │
│  │  └ ...             │  │  modificationDataId          │   │
│  └───────────────────┘  │  modificationMetaId           │   │
│                         └──────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```
```text
   SQL 请求
      │
      ▼
  ┌──────────┐
  │ Parser   │
  └────┬─────┘
       │ Prepared Command
       ▼
  ┌──────────┐     ┌──────────┐     ┌──────────────┐
  │ Session  │────→│ Database │────→│    Store     │
  │ Local    │     │ 中枢     │     │   (MVStore)  │
  └──────────┘     │          │     └──────┬───────┘
                   │  schemas │            │
                   │  meta锁  │     ┌──────▼───────┐
                   │ 会话管理  │     │  FileStore   │
                   └──────────┘     │  → Chunk     │
                                    │  → MVMap[]   │
                                    └──────────────┘
```

以下 7 张图共同呈现 Database 中枢与 SessionLocal 的协作脉络：图 4-5 追踪 SQL 请求穿越 Database 的链路，图 4-6 与图 4-7 拆解关键方法的调用层次，图 4-8 与图 4-9 描绘 Meta Lock 的获取与诊断，图 4-10 与图 4-11 串起 SessionLocal 到 MVMap 的写入路径。

**图 4-5: 追踪 SQL 请求穿越 Database 中枢的链路**

### 4.1.4 关键方法
如图 4-5 所示，**`open()`**: 初始化存储引擎、注册内置 Schema、加载系统表、恢复事务。

**`close()`**: 按顺序关闭会话、提交未完成事务、关闭存储引擎、释放文件锁。

**`checkpoint()`**: 触发 MVStore 刷盘，将脏页写入新 Chunk，更新 store header。

**`getSchema(String name)`**: 从 `schemas` ConcurrentHashMap 中按名称查找 Schema。

**`addTable(Table table)`**: 将表注册到对应的 Schema 中，更新 modificationMetaId。

**`getTable(String name)`**: 遍历所有 Schema 查找表。

```text
  open()
  ┌─────────────────────────────────────────────────┐
  │  initStore() → 初始化存储引擎                    │
  │  initSystemTables() → 注册内置 Schema           │
  │  loadSystemTables() → 加载系统表                │
  │  recoverTransactions() → 恢复未完成事务          │
  └─────────────────────────────────────────────────┘

  close()
  ┌─────────────────────────────────────────────────┐
  │  closeSessions() → 关闭所有会话                 │
  │  commitInProgress() → 提交未完成事务             │
  │  closeStore() → 关闭 MVStore 引擎               │
  │  releaseFileLock() → 释放文件锁                  │
  └─────────────────────────────────────────────────┘

  如图 4-6 所示，checkpoint()             addTable(table)
  ┌──────────────────┐    ┌────────────────────────┐
  │ MVStore.store() │    │ schema.getTableOrNull()│
  │ 写入新Chunk      │    │ schemas.put()          │
  │ 更新store header │    │ updateMetaId()         │
  └──────────────────┘    └────────────────────────┘
```
**图 4-6: 拆解 Database 关键方法的内部调用链**
```text
  外部调用层
      │
  ┌───┴───┐
  │ open  │──→ initStore → initSystemTables → load → recover
  ├───────┤
  │ close │──→ closeSessions → commitInProgress → closeStore
  ├───────┤
  │check  │──→ MVStore.store → FileStore.sync
  │point  │
  ├───────┤
  │add   │──→ schemas.put → modificationMetaId++
  │Table │
  ├───────┤
  │get   │──→ schemas.get(name) 或 遍历所有 Schema
  │Table │
  └───────┘
```
**图 4-7: 归纳 Database 五大方法的调用层级**
### 4.1.5 元数据锁 (Meta Lock)
如图 4-7 所示，Database 内部维护了一个用于元数据并发控制的锁机制，通过 `META_LOCK_DEBUGGING` ThreadLocal 调试跟踪。

```text
  如图 4-8 所示，线程请求元数据操作
      │
      ▼
  ┌──────────────────┐
  │ 尝试获取 Meta Lock│
  └──────┬───────────┘
         │
    ┌────┴────┐
    │ 空闲    │  占用
    └────┬────┘  └──────────────┐
         ▼                      ▼
  ┌────────────────┐   ┌────────────────────┐
  │ 获得锁         │   │ 等待/阻塞          │
  │ 执行元数据操作  │   │ META_LOCK_DEBUGGING│
  │ schemas.put()  │   │ ThreadLocal 记录   │
  │ rights.add()   │   │ 等待者 & 持有者    │
  │ ...            │   └────────────────────┘
  │ 释放锁         │
  └────────────────┘
```
**图 4-8: 追踪 Meta Lock 从空闲到释放的获取链路**
```text
  如图 4-9 所示，ThreadLocal<META_LOCK_DEBUGGING>
  ┌──────────────────────────────────────────────┐
  │  持有者线程: Thread-1 (正在执行 addTable)    │
  │  等待者队列: [Thread-2, Thread-3]            │
  │  等待时间: 150ms                             │
  │  操作类型: Schema 修改                       │
  └──────────────────────────────────────────────┘
  用途: 死锁诊断 & 长时间等待告警
```
**图 4-9: 解读 Meta Lock 死锁诊断信息字段**

---

## 4.2 SessionLocal — 会话管理

**路径**: `org/h2/engine/SessionLocal.java` (2143 行)

SessionLocal 表示一个嵌入式数据库连接。在服务器模式下，它位于服务端，与客户端的 SessionRemote 通信。

### 4.2.1 核心职责
- 管理事务状态（自动提交、隔离级别）
- 管理 LOB、临时表、锁
- 包装 TransactionStore.Transaction
- 缓存查询计划（queryCache）

```text
如图 4-10 所示，┌────────────────────────────────────────────┐
│  事务管理层                                 │
│  自动提交 / 隔离级别 / 事务状态机           │
├────────────────────────────────────────────┤
│  资源管理层                                 │
│  LOB / 临时表 / 锁 (ArrayList<Table>)      │
├────────────────────────────────────────────┤
│  持久化代理层                               │
│  包装 TransactionStore.Transaction          │
├────────────────────────────────────────────┤
│  查询优化层                                 │
│  queryCache (SmallLRUCache)                │
└────────────────────────────────────────────┘
```
**图 4-10: 概览 SessionLocal 事务、资源与缓存四层职责**
```text
  如图 4-11 所示，JDBC 请求
     │
     ▼
  SessionLocal
  ┌─────────────────────────────────────┐
  │                                     │
  │  ┌─────────────┐  ┌──────────────┐ │
  │  │ 事务状态管理  │  │  锁管理      │ │
  │  │ state:      │  │  locks:      │ │
  │  │ AtomicRef   │  │  ArrayList   │ │
  │  │ → State枚举 │  │  → Table锁   │ │
  │  └─────────────┘  └──────────────┘ │
  │                                     │
  │  ┌─────────────┐  ┌──────────────┐ │
  │  │ Transaction │  │  queryCache  │ │
  │  │ (MVCC事务)  │  │  sql→Command │ │
  │  └──────┬──────┘  └──────────────┘ │
  │         │                           │
  └─────────┼───────────────────────────┘
            │ 委托
            ▼
  TransactionStore → MVMap.operate()
```
**图 4-11: 追踪 SessionLocal 到 MVMap 的写入链路**

### 4.2.2 关键字段

```java
// SessionLocal.java:222 — 事务对象
private Transaction transaction;

// SessionLocal.java:223 — 会话状态机
private final AtomicReference<State> state = new AtomicReference<>(State.INIT);
// State 枚举: INIT, RUNNING, BLOCKED, SLEEP, THROTTLED, SUSPENDED, CLOSED

// SessionLocal.java:229 — 隔离级别
private IsolationLevel isolationLevel = IsolationLevel.READ_COMMITTED;

// SessionLocal.java:151 — 锁列表
private final ArrayList<Table> locks = Utils.newSmallArrayList();

// SessionLocal.java:190 — 查询缓存
private SmallLRUCache<String, Command> queryCache;
```
```text
如图 4-12 所示，┌──────────────────────────────────────────┐
│  事务相关                                │
│  ┌────────────────┐  ┌─────────────────┐ │
│  │ transaction    │  │ state           │ │
│  │ (Transaction)  │  │ AtomicRef<State>│ │
│  └────────────────┘  │ INIT→...→CLOSED │ │
│                       └─────────────────┘ │
├──────────────────────────────────────────┤
│  隔离 & 锁                                │
│  ┌────────────────┐  ┌─────────────────┐ │
│  │ isolationLevel │  │ locks           │ │
│  │ READ_COMMITTED │  │ ArrayList<Table>│ │
│  └────────────────┘  └─────────────────┘ │
├──────────────────────────────────────────┤
│  缓存                                    │
│  ┌──────────────────────────────────────┐│
│  │ queryCache                           ││
│  │ SmallLRUCache<String, Command>       ││
│  └──────────────────────────────────────┘│
└──────────────────────────────────────────┘
```
**图 4-12: 梳理 SessionLocal 事务、隔离与缓存字段**
```text
  如图 4-13 所示，state (AtomicReference)
     │
     ├── INIT ──→ RUNNING ──→ BLOCKED
     │                       ──→ SLEEP
     │                       ──→ THROTTLED
     │                       ──→ SUSPENDED
     │                                  ──→ CLOSED
     │
  transaction ───→ TransactionStore.Transaction
     │                │
     │                ├── transactionId
     │                ├── status (OPEN/COMMITTED/ROLLED_BACK)
     │                └── logId
     │
  locks ──→ ArrayList<Table> (表级锁集合)
  queryCache ──→ SmallLRUCache (SQL → 预编译命令)
```
**图 4-13: 刻画 SessionLocal 字段间引用关系**

### 4.2.3 架构图

```text
┌─────────────────────────────────────────────────────────────┐
│                   SessionLocal                               │
│  implements TransactionStore.RollbackListener               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │  Transaction     │    │  queryCache                     │ │
│  │  (来自 Transaction │    │  ┌ sql -> Command             │ │
│  │   Store)         │    │  └ ...                         │ │
│  ├─────────────────┤    └─────────────────────────────────┘ │
│  │  transactionId  │                                        │
│  │  status         │    ┌─────────────────────────────────┐ │
│  │  logId          │    │  locks: ArrayList<Table>        │ │
│  └─────────────────┘    │  updates: HashSet<Table>        │ │
│                         └─────────────────────────────────┘ │
│  State Machine:                                              │
│  INIT → RUNNING → BLOCKED (wait lock)                        │
│                  → SLEEP    → RUNNING → ... → CLOSED         │
│                  → THROTTLED                                  │
│                  → SUSPENDED                                  │
└─────────────────────────────────────────────────────────────┘
```
```text
         ┌─────────────────────────────────────┐
         │              INIT                    │
         └──────────────┬──────────────────────┘
                        │ open()
                        ▼
         ┌─────────────────────────────────────┐
    ┌───│              RUNNING                  │
    │   └──┬──────┬──────┬──────┬──────────────┘
    │      │      │      │      │
    ▼      ▼      ▼      ▼      ▼
 ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
 │BLK │ │SLP │ │THR │ │SUS │ │CLS │
 └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘
   │      │      │      │      │
   └──────┴──────┴──────┴──────┘
              │ resume
              ▼
         ┌─────────────────────────────────────┐
         │              RUNNING                │
         └─────────────────────────────────────┘
```
**图 4-14: 描绘 SessionLocal 七种状态的迁移路径**

### 4.2.4 关键方法
如图 4-14 所示，**`commit(boolean ddl)`** (SessionLocal.java:686):

```java
public void commit(boolean ddl) {
    beforeCommitOrRollback();
    if (hasTransaction()) {
        transaction.commit();          // → TransactionStore.commit()
        removeTemporaryLobs(true);
        endTransaction();
    }
    // ddl 时不清理临时表
}
```

**`rollback()`** (SessionLocal.java:815):
```java
public void rollback() {
    beforeCommitOrRollback();
    if (hasTransaction()) {
        rollbackTo(null);              // → Transaction.rollback()
    }
    cleanTempTables(false);
    endTransaction();
}
```

**`prepareCommand(String sql)`**: 委托给 `Parser.prepareCommand(sql)`，解析 SQL 生成 Prepared 对象。

```text
  commit(boolean ddl)
  ┌─────────────────────────────────────────────────────┐
  │  beforeCommitOrRollback()                           │
  │  if (hasTransaction())                              │
  │    transaction.commit() → TransactionStore.commit() │
  │    removeTemporaryLobs(true)                        │
  │    endTransaction()                                 │
  └─────────────────────────────────────────────────────┘

  rollback()
  ┌─────────────────────────────────────────────────────┐
  │  beforeCommitOrRollback()                           │
  │  if (hasTransaction())                              │
  │    rollbackTo(null) → Transaction.rollback()        │
  │  cleanTempTables(false)                             │
  │  endTransaction()                                   │
  └─────────────────────────────────────────────────────┘

  如图 4-15 所示，prepareCommand(String sql)
  ┌─────────────────────────────────────────────────────┐
  │  queryCache 命中 → 返回缓存的 Command              │
  │  queryCache 未命中                                  │
  │    → Parser.prepareCommand(sql)                     │
  │    → 缓存到 queryCache                              │
  └─────────────────────────────────────────────────────┘
```
**图 4-15: 拆解 commit 与 rollback 的调用步骤**
```text
┌─────────────────────┬─────────────────────────────┐
│  commit(ddl)        │  rollback()                 │
├─────────────────────┼─────────────────────────────┤
│  beforeCommitOr...  │  beforeCommitOr...          │
│  transaction.commit │  rollbackTo(null)           │
│  → 使变更可见       │  → 恢复 oldValue           │
│  removeTemporaryLobs│  cleanTempTables            │
│  endTransaction     │  endTransaction             │
│  (ddl? 清理: 跳过)  │  (始终清理临时表)           │
└─────────────────────┴─────────────────────────────┘
```
**图 4-16: 对比 commit 与 rollback 的执行差异**

---

## 4.3 MVStore — 存储引擎核心

**路径**: `org/h2/mvstore/MVStore.java` (2213 行)

如图 4-16 所示，MVStore 是一个基于 Chunk 的持久化 key-value 存储引擎，使用 B-Tree 映射 (MVMap) 和 undo log。

### 4.3.1 核心设计
- **Chunk 存储**: 数据文件按 Chunk 组织，每个 Chunk 包含连续的 page
- **B-Tree 映射**: 每个 MVMap 是一棵 COW (Copy-on-Write) B-Tree
- **后台线程**: 周期性执行写操作和 compact
- **写前日志**: 对 undo log 的操作先于数据变更

```text
如图 4-17 所示，┌────────────────────────────────────────────────────────────┐
│                     MVStore 存储引擎                        │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  存储模型: Chunk + Page                              │  │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐            │  │
│  │  │ Chunk│  │ Chunk│  │ Chunk│  │ Chunk│  ...       │  │
│  │  │ 1    │  │ 2    │  │ 3    │  │ 4    │            │  │
│  │  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘            │  │
│  │     └──────────┴──────────┴──────────┘               │  │
│  │          每个 Chunk = 连续 Page 序列                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────┐  ┌────────────────────────────┐ │
│  │ 映射: MVMap (B-Tree) │  │ 并发: COW + 无锁读         │ │
│  │ ┌─ MVMap<K,V> ─────┐│  │ ┌─ RootReference ────────┐│ │
│  │ │ Root → Page[]    ││  │ │ AtomicReference        ││ │
│  │ │ COW B-Tree       ││  │ │ CAS 更新              ││ │
│  │ └──────────────────┘│  │ └────────────────────────┘│ │
│  └──────────────────────┘  └────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 后台线程: 周期性 writeBackground()                  │  │
│  │ ┌──────────┐  →  ┌──────────┐  →  ┌──────────────┐ │  │
│  │ │ 写/刷盘   │    │ compact  │    │ housekeeping  │ │  │
│  │ └──────────┘     └──────────┘     └──────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```
**图 4-17: 概览 MVStore 的存储、映射、并发与后台四模块**
```text
  如图 4-18 所示，UPDATE 操作
     │
     ▼
  ┌────────────────────────────┐
  │ 1. 写入 undo log          │
  │    (记录 oldValue)        │
  └──────────┬─────────────────┘
             ▼
  ┌────────────────────────────┐
  │ 2. 修改 B-Tree page       │
  │    (COW 复制修改路径)     │
  └──────────┬─────────────────┘
             ▼
  ┌────────────────────────────┐
  │ 3. 提交时:                │
  │    undo log → commit      │
  └────────────────────────────┘
  保证: 崩溃时可从 undo log 恢复
```
**图 4-18: 追踪 MVStore 写前日志保证崩溃恢复的步骤**

### 4.3.2 关键字段

```java
// MVStore.java:188 — 元数据映射 (name -> id, id -> metadata)
private final MVMap<String, String> meta;

// MVStore.java:190 — 所有打开的 MVMap
private final ConcurrentHashMap<Integer, MVMap<?, ?>> maps;

// MVStore.java:175 — 文件存储
private final FileStore<?> fileStore;

// MVStore.java:208 — 当前版本号
private volatile long currentVersion;

// MVStore.java:163 — store() 操作互斥锁
private final ReentrantLock storeLock = new ReentrantLock(true);
```
```text
如图 4-19 所示，┌──────────────────────────────────────────────┐
│  元数据映射                                  │
│  ┌──────────────────────────────────────────┐│
│  │ meta (MVMap<String, String>)             ││
│  │  name.1 → mapId=1  /  root.1 → page位置 ││
│  └──────────────────────────────────────────┘│
├──────────────────────────────────────────────┤
│  数据映射容器                                │
│  ┌──────────────────────────────────────────┐│
│  │ maps (ConcurrentHashMap<Integer, MVMap>) ││
│  │  mapId 1 → 表数据   mapId 2 → 索引      ││
│  │  mapId 3 → undo log  ...                ││
│  └──────────────────────────────────────────┘│
├──────────────────────────────────────────────┤
│  持久化 & 版本                               │
│  ┌──────────────┐  ┌───────────────────────┐ │
│  │ fileStore    │  │ currentVersion       │ │
│  │ (FileStore)  │  │ (volatile long)      │ │
│  └──────────────┘  └───────────────────────┘ │
├──────────────────────────────────────────────┤
│  并发控制                                    │
│  ┌──────────────────────────────────────────┐│
│  │ storeLock (ReentrantLock)               ││
│  │ store() 操作互斥锁                       ││
│  └──────────────────────────────────────────┘│
└──────────────────────────────────────────────┘
```
**图 4-19: 梳理 MVStore 元数据、容器、文件与锁字段**
```text
  如图 4-20 所示，meta map
     │  name.1 → mapId=1
     │  root.1 → pagePos
     ▼
  maps[mapId] ──→ MVMap<K,V>
     │
     ├── MVMap.root ──→ RootReference
     │                    ├ root: Page<K,V>
     │                    ├ version: long
     │                    └ previous: RootRef
     │
     └── data ──→ FileStore
                    └─ Chunk [page][page]...
```
**图 4-20: 刻画 MVStore meta 到 Chunk 的引用链**

### 4.3.3 架构图

```text
┌────────────────────────────────────────────────────────────┐
│                       MVStore                              │
│                     AutoCloseable                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  meta map (MVMap<String, String>)                     │  │
│  │  ┌ name.1 -> mapId=1                                  │  │
│  │  ├ name.2 -> mapId=2  (反向索引由 mapId 存储)          │  │
│  │  └ root.1 -> rootPage的位置                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  maps (ConcurrentHashMap<Integer, MVMap>)            │  │
│  │  ┌ mapId 1 -> MVMap<K,V>  (表数据)                    │  │
│  │  ├ mapId 2 -> MVMap<K,V>  (索引数据)                   │  │
│  │  └ mapId 3 -> MVMap<K,V>  (undo log)                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FileStore                                            │  │
│  │  ┌ Chunk 1: [page][page][page]                       │  │
│  │  ├ Chunk 2: [page][page][page][page]                 │  │
│  │  ├ Chunk 3: ...                                      │  │
│  │  └ Store Header (lastChunk位置)                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  Background Writer Thread:                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ write/sync   │→│  compact      │→│  housekeeping    │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└────────────────────────────────────────────────────────────┘
```
```text
  put(key, value)
     │
     ▼
  ┌──────────────────────────────────────────┐
  │ 1. MVMap.operate()                      │
  │    → CAS 循环 / 锁升级                  │
  │    → COW 复制修改路径上 Page            │
  │    → 注册脏 Page                        │
  └──────────────────┬───────────────────────┘
                     ▼
  ┌──────────────────────────────────────────┐
  │ 2. MVStore.store()                     │
  │    → 生成新版本号                        │
  │    → 序列化脏 Page 到新 Chunk           │
  │    → 更新 RootReference                 │
  │    → 更新 Store Header                  │
  └──────────────────┬───────────────────────┘
                     ▼
  ┌──────────────────────────────────────────┐
  │ 3. FileStore.sync()                     │
  │    → 刷盘到物理文件                      │
  └──────────────────────────────────────────┘
```

下面 5 张图共同呈现 MVStore 写入与回收的脉络：图 4-21 切入 put 的三阶段写入，图 4-22 对比 commit 与 compact 的处理，图 4-23 给出 MVStore 与 FileStore 的方法层次，图 4-24 与图 4-25 收尾于 Chunk 的生命周期与空间管理。

**图 4-21: 追踪 MVStore put 触发的三阶段写入**

### 4.3.4 关键方法
如图 4-21 所示，**`commit()`**: 将当前版本的所有变更写入新 Chunk，更新 store header。

**`compact()`**: 委托给 `FileStore.compactStore()`，重写低填充率 Chunk，回收空间。

**`rollbackTo(long targetVersion)`**: 回滚到指定版本，丢弃 targetVersion 之后的所有变更。

```text
  commit()                           compact()
  ┌─────────────────────────┐        ┌───────────────────────────┐
  │ 所有变更 → 新版本号     │        │ 识别低填充率 Chunk        │
  │ 脏页 → 新 Chunk        │        │ 复制存活 page → 新 Chunk  │
  │ 更新 Store Header      │        │ 释放旧 Chunk 空间          │
  │ FileStore.sync() 刷盘  │        │ 更新 FreeSpaceBitSet       │
  └─────────────────────────┘        └───────────────────────────┘

  如图 4-22 所示，rollbackTo(targetVersion)
  ┌─────────────────────────────────────────────────────┐
  │ 丢弃 targetVersion 之后的所有变更                   │
  │ 恢复旧 RootReference (利用版本链 previous)           │
  │ 旧 Chunk 中的脏数据不再被引用                       │
  └─────────────────────────────────────────────────────┘
```
**图 4-22: 对比 commit 与 compact 的处理动作**
```text
  如图 4-23 所示，外部接口
     │
  ┌──┴───────────────┐
  │                  │
  ▼                  ▼
MVStore          FileStore
  │                  │
  ├─ commit()        ├─ compactStore()
  │  └ storeLock     │   └ compact()
  │    └ sync()      │     └ compactMoveChunks()
  │                  │
  ├─ compact()       │
  │  └ backing       │
  │    FileStore     │
  │                  │
  └─ rollbackTo()    └─ sync()
     └ 版本链恢复
```
**图 4-23: 梳理 MVStore 与 FileStore 的方法层次**

### 4.3.5 Chunk 生命周期图
```text
  如图 4-24 所示，┌──────────┐
  │  创建     │ ← 写入新 page → 分配新 Chunk → 序列化到文件
  └────┬─────┘
       │
       ▼
  ┌──────────┐
  │  存活     │ ← 包含可读数据，被 root reference 引用
  └────┬─────┘
       │
       ├── 压缩触发 ──────────────────────────────┐
       │                                          │
       ▼                                          ▼
  ┌──────────┐                           ┌──────────────┐
  │  压缩     │                           │ 保持存活     │
  │ (低填充率)│                           │ (高填充率)   │
  └────┬─────┘                           └──────────────┘
       │
       ▼
  ┌──────────┐
  │  回收     │ ← Chunk 标记为 free
  └────┬─────┘    FreeSpaceBitSet 记录可重用空间
       │
       ▼
  ┌──────────┐
  │ 空间重用  │ ← 新写入复盖该区域
  └──────────┘
```
**图 4-24: 追踪 Chunk 从创建到回收的生命周期阶段**
```text
┌────────┬────────┬────────┬────────┬────────┬────────┐
│ 创建    │  存活  │ 压缩中  │ 已释放  │ 重用   │        │
│ Chunk1 │ Chunk2 │ Chunk3 │ Chunk4 │ Chunk5 │ ...    │
├────────┼────────┼────────┼────────┼────────┼────────┤
│ 引用    │ 引用    │ 迁移中  │Free    │ 已写入  │        │
│ root   │ root   │ 存活   │Space   │ 新数据  │        │
│ 指向    │ 指向    │ page   │BitSet  │        │        │
└────────┴────────┴────────┴────────┴────────┴────────┘
```
**图 4-25: 刻画 Chunk 各状态与 FreeSpace 空间管理**

---

## 4.4 MVMap — 并发 B-Tree 映射

**路径**: `org/h2/mvstore/MVMap.java` (2170 行)

如图 4-25 所示，MVMap 实现了 `ConcurrentMap` 接口，是一个基于 COW (Copy-on-Write) 的并发 B-Tree。

### 4.4.1 核心设计
- **无锁读**: 读操作无需加锁，通过 `RootReference` 原子引用保证一致性
- **COW 写**: 写操作复制被修改的 page，不阻塞读线程
- **CAS 循环**: `operate()` 使用 CAS + 自旋的重试机制

```text
  如图 4-26 所示，读线程 A               写线程 B
     │                      │
     │  get(key)            │  put(key, value)
     │  │                   │
     │  │                   ▼
     │  │         ┌────────────────────┐
     │  │         │  COW 复制修改路径   │
     │  │         │  Page[Root] → Page'│
     │  │         │  Page[Int]  → Page'│
     │  │         │  Page[Leaf] → Page'│
     │  │         └────────┬───────────┘
     │  │                  │
     │  │                  ▼
     │  │         ┌────────────────────┐
     │  │         │ CAS 更新          │
     │  │         │ RootReference     │
     │  │         │ root: Page'       │
     │  │         │ version: v+1      │
     │  │         └────────────────────┘
     │  │                  │
     │  ▼                  │
  ┌────────────┐           │
  │ 读取旧 root │ ←────────┘
  │ Page       │   (写不阻塞读)
  │ (旧版本)   │
  └────────────┘
```

下面三张图共同呈现 MVMap 并发写入的实现细节：图 4-26 对比无锁读与 COW 写的并发路径，图 4-27 演示 COW B-Tree 仅复制修改路径上的页节点，图 4-53 追踪 operate() 的 CAS 自旋重试循环。

**图 4-26: 对比 MVMap 无锁读与 COW 写的并发路径**
```text
  如图 4-27 所示，修改前                         修改后
      [R]                          [R']
     /   \                        /   \
  [I1]  [I2]                  [I1']  [I2]
  / \    / \                  / \    / \
[L1][L2][L3][L4]         [L1][L2'][L3][L4]
                              ↑
                          新 Page (共享未修改部分)
  修改 L2 时 COW 复制: L2 → L2', I1 → I1', R → R'
  未修改的 I2, L1, L3, L4 仍被新旧版本共享
```
**图 4-27: 演示 COW B-Tree 仅复制修改路径上的页节点**
```text
  并发写入时 CAS 失败 → 自动重试

  如图 4-53 所示，┌────────────────────────────────────────────┐
  │ operate() 重试循环                          │
  │                                            │
  │  ┌──────────────────────────────────┐      │
  │  │ oldRef = rootRef.get()           │      │
  │  └────────────┬─────────────────────┘      │
  │               ▼                             │
  │  ┌──────────────────────────────────┐      │
  │  │ 执行操作 + COW 复制              │      │
  │  │ oldRoot → newRoot                │      │
  │  └────────────┬─────────────────────┘      │
  │               ▼                             │
  │  ┌──────────────────────────────────┐      │
  │  │ CAS(rootRef, oldRef, newRef)     │      │
  │  └──────┬───────────────────┬───────┘      │
  │         ▼                   ▼               │
  │    ┌─────────┐       ┌──────────────┐      │
  │    │ 成功!   │       │ 失败 → 重试  │      │
  │    │ 返回    │       │ 跳转到循环顶 │      │
  │    └─────────┘       └──────────────┘      │
  └────────────────────────────────────────────┘
  无锁读: 直接 rootRef.get(), 无 CAS 无等待
```
**图 4-53: 追踪 operate() 的 CAS 自旋重试循环**

### 4.4.2 RootReference 结构

```java
// MVMap.java:45 — 根 page 原子引用
private final AtomicReference<RootReference<K,V>> root;

// RootReference 包含:
// - root: 当前根 Page
// - version: 版本号
// - previous: 前一个 RootReference (用于版本链)
// - lock: 写锁 (ReentrantLock)
```
```text
  如图 4-28 所示，AtomicReference<RootReference>
     │
     │  CAS 更新
     ▼
  ┌─────────────────────────────────────────────┐
  │  RootReference (version: 10)                │
  │  ┌───────────────────────────────────────┐  │
  │  │ root: Page<K,V> (B-Tree 根)           │  │
  │  │ version: 10                           │  │
  │  │ previous: ──────────────────────┐     │  │
  │  │ lock: ReentrantLock             │     │  │
  │  └─────────────────────────────────┼─────┘  │
  └─────────────────────────────────────┼───────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────┐
  │  RootReference (version: 9)                 │
  │  ┌───────────────────────────────────────┐  │
  │  │ root: Page<K,V> (旧 B-Tree 根)        │  │
  │  │ version: 9                            │  │
  │  │ previous: ──────────────────────┐     │  │
  │  │ lock: null (读线程持有引用)      │     │  │
  │  └─────────────────────────────────┼─────┘  │
  └─────────────────────────────────────┼───────┘
                                        │
                                        ▼
                                       ...
  (版本链用于 MVCC 快照读和回滚)
```
**图 4-28: 描绘 RootReference 的版本链与前向引用**
```text
  MVMap
  ┌────────────────────────────────────┐
  │ root: AtomicReference<RootRef>    │
  │   │                               │
  │   │ 内存地址                       │
  │   ▼                               │
  │  ┌──────────────────────────────┐ │
  │  │ RootReference                │ │
  │  │  ├ root  → Page (B-Tree)    │ │
  │  │  ├ version → long           │ │
  │  │  ├ previous → RootReference │ │
  │  │  └ lock → ReentrantLock    │ │
  │  └──────────────────────────────┘ │
  └────────────────────────────────────┘
  读: root.get() → RootReference → root.Page → 遍历
  写: CAS(root, oldRef, newRef) → 原子切换
```
**图 4-29: 拆解 RootReference 的字段构成与读写路径**

### 4.4.3 读写修改核心方法

**源码位置**: `org/h2/mvstore/MVMap.java:1874-1928`

如图 4-29 所示，`operate()` 是 MVMap 的读写修改核心，使用自旋 + 锁升级的 CAS 循环：
```java
public V operate(K key, V value, DecisionMaker<V> decisionMaker) {
    CursorPos<K,V> tip = null;
    for (int attempt = 0;; decisionMaker.reset()) {
        RootReference<K,V> rootReference = flushAndGetRoot();
        boolean locked = rootReference.isLockedByCurrentThread();
        if (!locked) {
            if (attempt++ == 0) { beforeWrite(); }
            if (attempt > 5 || rootReference.isLocked()) {
                rootReference = lockRoot(rootReference, attempt);
                locked = true;  // 升级为写锁
            }
        }
        Page<K,V> rootPage = rootReference.root;
        tip = CursorPos.traverseDown(rootPage, key, tip); // B-Tree 降序遍历
        CursorPos<K,V> cp = decisionMaker.decide(tip, key, value);
        // ... 替换 page、注册脏内存 ...
        V result = index < 0 ? null : p.getValue(index);
        return result;
    }
}
```
```text
  如图 4-30 所示，入口: operate(key, value, decisionMaker)
     │
     ▼
  ┌─────────────────────────────────────────────┐
  │ attempt=0, flushAndGetRoot()               │
  └──────────────────┬──────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────┐
  │ 检查 RootReference 是否已被当前线程锁定     │
  └──────────────────┬──────────────────────────┘
                     │
              ┌──────┴──────┐
              │ 已锁定      │ 未锁定
              └──────┬──────┘
                     │          │
                     │          ▼
                     │   ┌────────────────────┐
                     │   │ attempt++          │
                     │   │ 首次 → beforeWrite │
                     │   └────────┬───────────┘
                     │            │
                     │     ┌──────┴──────┐
                     │     │ >5 或       │
                     │     │ 已被其他线程 │
                     │     │ 锁定?       │
                     │     └──────┬──────┘
                     │      YES   │   NO
                     │        │   │
                     │        ▼   │
                     │  ┌────────┐│
                     │  │ 锁升级  ││
                     │  │ lockRoot││
                     │  └────────┘│
                     ├──────┬─────┘
                     │      ▼
                     │  ┌────────────────────┐
                     │  │ B-Tree 降序遍历    │
                     │  │ CursorPos.traverse │
                     │  └────────┬───────────┘
                     │           ▼
                     │  ┌────────────────────┐
                     │  │ DecisionMaker      │
                     │  │ .decide()          │
                     │  └────────┬───────────┘
                     │           ▼
                     │  ┌────────────────────┐
                     │  │ CAS 更新           │
                     │  │ RootReference      │
                     │  │ success?           │
                     │  └────────┬───────────┘
                     │     YES   │   NO (重试)
                     │       │   └──→ 回到开头
                     │       ▼
                     │  返回结果
                     └─────────────
```
**图 4-30: 追踪 operate() 自旋至锁升级的执行路径**
```text
  自旋次数     操作
  ───────── ──────────────────────
  0         flushAndGetRoot (无锁)
  1~5       beforeWrite + 自旋重试
  6+        lockRoot() → 阻塞等待
             (ReentrantLock)

  如图 4-31 所示，示意图:
  尝试 0:  ╭────────────────╮
           │ 无锁快速路径    │
           ╰──────┬─────────╯
                  │ CAS 失败
                  ▼
  尝试 1~5: ╭────────────────╮
            │ 自旋重试 (忙等) │
            ╰──────┬─────────╯
                   │ 超过 5 次
                   ▼
  尝试 6+: ╭────────────────╮
           │ 锁升级         │
           │ ReentrantLock │
           │ (线程阻塞)     │
           ╰────────────────╯
```
**图 4-31: 解读 operate() 自旋 5 次后升级写锁的策略**
```text
     MVMap<K,V> (ConcurrentMap)
     ┌─────────────────────────────────────┐
     │  root (AtomicReference)             │
     │  └→ RootReference                   │
     │      ├ root: Page<K,V> (根节点)      │
     │      ├ version: long                │
     │      ├ previous: RootReference       │
     │      └ lock: ReentrantLock          │
     ├─────────────────────────────────────┤
     │  COW B-Tree 结构:                    │
     │                                     │
     │         [Root Page]                 │
     │        /    |     \                 │
     │   [Int]  [Int]  [Int]  ← 内部节点   │
     │   / |    / |    / |                 │
     │ [L][L] [L][L] [L][L]  ← 叶子节点    │
     │                                     │
     │  写时复制: 修改路径上所有 page       │
     └─────────────────────────────────────┘
```

### 4.4.4 读写流程对比

```text
  读路径 (get):
  ┌─── root ──→ internal ──→ internal ──→ leaf ──┐
  │  二分查找   二分查找     二分查找    取值      │
  └───────────────────────────────────────────────┘
  沿途 Page 全部共享, 不加锁

  写路径 (put):
  ┌─── root ──→ internal ──→ internal ──→ leaf ──┐
  │  COW 复制   COW 复制     COW 复制    修改     │
  └───────────────────────────────────────────────┘
  所有修改路径上的 Page 被复制, 生成新版本

  如图 4-32 所示，版本切换:
  旧 root ──→ 旧 internal ──→ 旧 internal ──→ 旧 leaf
  新 root' ─→ 新 internal' ─→ 新 internal' ─→ 新 leaf'
                                             (被修改)
  CAS(rootRef, 旧, 新) → 后续读使用新版
```
**图 4-32: 对比 B-Tree 读路径与 COW 写路径的页访问**

| 操作 | 读 (get) | 写 (put/remove) |
|------|---------|----------------|
| 锁   | 无锁    | CAS + 自旋 → 锁升级 |
| Page | 直接读  | COW 复制修改路径 |
| CAS  | 不涉及  | CAS 更新 RootReference |
| 重试 | 不重试  | CAS 失败 → 自旋重试 |

```text
  读操作:
  get(key) → root.get() → Page.get()
       ↓
  无锁, 直接读取当前 RootReference
       ↓
  B-Tree 遍历: root → internal → leaf
       ↓
  返回 values[index] 或 null

  如图 4-33 所示，写操作:
  put(key, value) → operate()
       ↓
  CAS 自旋循环:
  ┌──────────────────────────────────┐
  │  flushAndGetRoot()               │
  │  if 未锁定: attempt++            │
  │    if >5: lockRoot() → 阻塞      │
  │  B-Tree 降序遍历                 │
  │  DecisionMaker.decide()          │
  │  COW 复制修改路径 Page           │
  │  CAS 更新 RootReference          │
  │  if 失败 → 重试                  │
  └──────────────────────────────────┘
       ↓
  返回旧值或 null
```
**图 4-33: 梳理 MVMap 读写两类操作的执行决策**

---

## 4.5 TransactionStore — 事务协调器

**路径**: `org/h2/mvstore/tx/TransactionStore.java` (1065 行)

TransactionStore 实现了 MVCC 读提交 (read-committed) 事务的支持。

> **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#transaction_isolation`)
> 详细列出了 H2 支持的 5 种隔离级别及其对应的 SQL 语句。

### 4.5.1 核心数据结构
```java
// TransactionStore.java:87 — 打开事务 BitSet (COW 版本化)
private final AtomicReference<VersionedBitSet> openTransactions;

// TransactionStore.java:96 — 正在提交的事务 BitSet
final AtomicReference<VersionedBitSet> committingTransactions;

// TransactionStore.java:77 — 每个事务一个 undo log
private final MVMap<Long,Record<?,?>>[] undoLogs;

// TransactionStore.java:111 — 事务对象数组 (事务ID = 数组下标)
private final AtomicReferenceArray<Transaction> transactions;

// 常量: MAX_OPEN_TRANSACTIONS = 255
```
```text
  如图 4-34 所示，TransactionStore
  ┌────────────────────────────────────────────────┐
  │                                                │
  │  openTransactions (VersionedBitSet, COW)       │
  │  bit[0]=1 bit[1]=1 bit[2]=0 bit[3]=1 ...      │
  │  ↑ 最多 MAX_OPEN_TRANSACTIONS (255)            │
  │                                                │
  │  committingTransactions (VersionedBitSet, COW) │
  │  bit[0]=0 bit[1]=1 bit[2]=0 bit[3]=0 ...      │
  │  ↑ 正在提交的事务标记                           │
  │                                                │
  │  undoLogs[MVMap<Long,Record> 数组]              │
  │  ┌──────────┬──────────┬──────────┬───────┐   │
  │  │ txId=1   │ txId=2   │ txId=3   │ ...   │   │
  │  │ undoLog  │ undoLog  │ undoLog  │       │   │
  │  └──────────┴──────────┴──────────┴───────┘   │
  │                                                │
  │  transactions[AtomicReferenceArray]             │
  │  ┌──────────┬──────────┬──────────┬───────┐   │
  │  │ Tx(OPEN) │Tx(CMT)   │Tx(RB)    │ null  │   │
  │  └──────────┴──────────┴──────────┴───────┘   │
  │  ↑ 事务 ID = 数组下标                           │
  └────────────────────────────────────────────────┘
```

下面三张图按层次刻画 TransactionStore 的事务管理：图 4-34 刻画四大数据结构的关联，图 4-35 解读 transactionId 作为数组下标的映射，图 4-54 追踪事务在 openTx 与 cmtTx 中的状态迁移。

**图 4-34: 刻画 TransactionStore 四大数据结构的关联**
```text
  事务 ID = 1:
  openTransactions.bit[1] = 1 (打开)
  undoLogs[1] → MVMap<Long,Record> (该事务的 undo log)
  transactions[1] → Transaction(status=OPEN)

  事务 ID = 2:
  openTransactions.bit[2] = 1 (打开)
  undoLogs[2] → MVMap<Long,Record>
  transactions[2] → Transaction(status=COMMITTED)

  如图 4-35 所示，关键设计:
  所有数组/位图使用事务 ID 作为索引
  → O(1) 查找, 无锁读
  → MAX_OPEN_TRANSACTIONS = 255 限制并发
```
**图 4-35: 解读 transactionId 作为数组下标的映射**
```text
  并发事务在数据结构中的状态变迁:

  ┌──────┬──────────┬────────────────────┬────────────┐
  │ 事务 │ 阶段     │ openTx / cmtTx    │ transaction│
  ├──────┼──────────┼────────────────────┼────────────┤
  │ Tx1  │ BEGIN    │ bit[1]=1/bit[1]=0 │ OPEN       │
  │ Tx1  │ COMMIT   │ bit[1]=0/bit[1]=1 │ COMMITTING │
  │ Tx1  │ DONE     │ bit[1]=0/bit[1]=0 │ COMMITTED  │
  ├──────┼──────────┼────────────────────┼────────────┤
  │ Tx2  │ BEGIN    │ bit[2]=1/bit[2]=0 │ OPEN       │
  │ Tx2  │ ROLLBACK │ bit[2]=0/bit[2]=0 │ ROLLED_BACK│
  ├──────┼──────────┼────────────────────┼────────────┤
  │ Tx3  │ BEGIN    │ bit[3]=1/bit[3]=0 │ OPEN       │
  │ Tx3  │ (活跃中) │                    │            │
  └──────┴──────────┴────────────────────┴────────────┘

  如图 4-54 所示，关键点: 事务 ID = BitSet 索引 → O(1) 检查
          open 与 committing 互斥 → 可串行化保证
```
**图 4-54: 追踪事务在 openTx 与 cmtTx 中的状态迁移**

### 4.5.2 Undo Log 结构

```text
undoLog key:   opId = (transactionId << 40) | logId
undoLog value: Record(mapId, key, oldValue)

oldValue = VersionedValue<Object>
  ├ operationId: long (由哪个事务修改的)
  ├ committedValue: Object (已提交版本)
  └ currentValue: Object (当前/未提交版本)
```
```text
  如图 4-36 所示，事务 Tx1 执行 UPDATE t SET x=2 WHERE id=1
      │
      ▼
  ┌──────────────────────────────────────────────┐
  │  Undo Log (Tx1)                              │
  │                                              │
  │  opId=(1<<40)|0 → Record(                    │
  │    mapId=5,         ← t 表的 data map       │
  │    key=1,           ← id=1 的行              │
  │    oldValue=VV(     ← 修改前的旧值           │
  │      operationId=NO_OP_ID,                   │
  │      committedValue="x=1",                   │
  │      currentValue="x=1"                      │
  │    )                                         │
  │  )                                           │
  └──────────────────────────────────────────────┘
      │
      │ MVMap.operate(key=1, value="x=2", PUT)
      ▼
  ┌──────────────────────────────────────────────┐
  │  data map (mapId=5)                          │
  │  key=1 → VersionedValue(                    │
  │    operationId=(1<<40)|0, ← 由 Tx1 修改    │
  │    committedValue="x=1",   ← 提交前的值     │
  │    currentValue="x=2"     ← 事务内写入的值  │
  │  )                                           │
  └──────────────────────────────────────────────┘
```
**图 4-36: 刻画 Undo Log 与数据 map 的写入对应**
```text
  opId (long, 64 bit)
  ┌──────────────┬────────────────────────────────┐
  │ transactionId│            logId                │
  │ (24 bit)     │            (40 bit)             │
  │ [63:40]      │            [39:0]               │
  └──────────────┴────────────────────────────────┘

  Record 结构:
  ┌────────┬────────┬──────────────────────────────┐
  │ mapId  │  key   │        oldValue              │
  │ (int)  │ (K)    │   VersionedValue<Object>     │
  └────────┴────────┴──────────────────────────────┘

  如图 4-37 所示，示例:
  opId = (3 << 40) | 5
  → transactionId = 3, logId = 5
  → 事务 3 的第 5 条 undo 记录
```
**图 4-37: 拆解 opId 字段的事务 ID 与 logId 位布局**
```text
┌──────────────────────────────────────────────────────────────┐
│                    TransactionStore                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐   ┌─────────────────────────────┐  │
│  │ openTransactions     │   │ committingTransactions      │  │
│  │ (VersionedBitSet)    │   │ (VersionedBitSet)           │  │
│  │ bit i = 1 → 事务 i 开 │   │ bit i = 1 → 事务 i 提交中   │  │
│  └──────────────────────┘   └─────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  undoLogs[transactionId]                                 ││
│  │                                                          ││
│  │  事务 1: undoLog.1  ┌───────────────────────────────┐   ││
│  │          opId=1.0 → [mapId, key, oldValue]          │   ││
│  │          opId=1.1 → [mapId, key, oldValue]          │   ││
│  │                                                      │   ││
│  │  事务 2: undoLog.2  ┌───────────────────────────────┐   ││
│  │          opId=2.0 → [mapId, key, oldValue]          │   ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  transactions[transactionId]                             ││
│  │  ┌ Transaction 1: status=OPEN, logId=5                  ││
│  │  ├ Transaction 2: status=COMMITTED                      ││
│  │  └ Transaction 3: status=ROLLED_BACK                    ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```
```text
  如图 4-38 所示，创建事务
     │
     ▼
  ┌──────────────────────────────────────┐
  │ openTransactions.bit[id] = 1        │
  │ undoLogs[id] = new MVMap()          │
  │ transactions[id] = new Transaction()│
  └──────────┬───────────────────────────┘
             │
     ┌───────┴───────────┐
     │                   │
     ▼                   ▼
  ┌────────┐       ┌──────────┐
  │ 提交   │       │  回滚    │
  │ commit │       │ rollback │
  └───┬────┘       └────┬─────┘
      │                 │
      ▼                 ▼
  ┌──────────────────────────────────────┐
  │ committingTransactions.bit[id]=1    │
  │ 遍历 undoLog, 使变更可见             │
  │ undoLog.clear()                     │
  │ committingTransactions.bit[id]=0    │
  │ openTransactions.bit[id]=0          │
  │ transactions[id] = COMMITTED        │
  └──────────────────────────────────────┘
```
**图 4-38: 追踪 TransactionStore 中事务的生命周期阶段**

### 4.5.3 关键方法
**`commit(Transaction t, boolean recovery)`** (TransactionStore.java:579-633):

```java
void commit(Transaction t, boolean recovery) {
    int transactionId = t.transactionId;
    // 1. 原子地将事务标记为"提交中" (CAS 更新 VersionedBitSet)
    VersionedBitSet commitingTx = flipCommittingTransactionsBit(transactionId, true);
    t.notifyAllWaitingTransactions();
    t.markStatementStart(null);
    // 2. 将 undo log 标记为已提交
    markUndoLogAsCommitted(transactionId, commitingTx.getVersion());
    // 3. 遍历 undo log，使用 CommitDecisionMaker 让每个变更可见
    Cursor<Long,Record<?,?>> cursor = undoLog.cursor(null);
    while (cursor.hasNext()) {
        long undoKey = cursor.next();
        Record<?,?> record = cursor.getValue();
        int mapId = record.mapId;
        if (mapId < 0) continue;
        map.operate(key, null, commitDecisionMaker); // 使变更可见
    }
    undoLog.clear();
    flipCommittingTransactionsBit(transactionId, false); // 清除"提交中"标记
}
```
```text
  如图 4-39 所示，Step 1 ┌──────────────────────────────────┐
         │ flipCommittingTransactionsBit    │
         │ CAS: 0→1, 标记"提交中"           │
         └────────────┬─────────────────────┘
                      │
  Step 2 ┌────────────▼─────────────────────┐
         │ notifyAllWaitingTransactions()   │
         │ 唤醒等待该事务的线程             │
         └────────────┬─────────────────────┘
                      │
  Step 3 ┌────────────▼─────────────────────┐
         │ markUndoLogAsCommitted(txId, v) │
         │ ".undoLog.3" → ".undoLog-3"     │
         └────────────┬─────────────────────┘
                      │
  Step 4 ┌────────────▼─────────────────────┐
         │ 遍历 undo log:                  │
         │ for each Record(mapId, key, old)│
         │   map.operate(key, null, CDM)   │
         │   CDM: PUT(已提交版本)          │
         │   → operationId = NO_OP_ID      │
         │   → currentValue 可见           │
         └────────────┬─────────────────────┘
                      │
  Step 5 ┌────────────▼─────────────────────┐
         │ undoLog.clear()                 │
         │ flipCommittingTransactionsBit   │
         │ CAS: 1→0, 清除"提交中"标记      │
         └──────────────────────────────────┘
```
**图 4-39: 追踪 commit 的五个执行步骤**
```java

**`rollbackTo(Transaction t, long maxLogId, long toLogId)`** (TransactionStore.java:824-833):

```
```java
void rollbackTo(Transaction t, long maxLogId, long toLogId) {
    int transactionId = t.getId();
    MVMap<Long,Record<?,?>> undoLog = undoLogs[transactionId];
    RollbackDecisionMaker decisionMaker = new RollbackDecisionMaker(this, transactionId, toLogId, t.listener);
    for (long logId = maxLogId - 1; logId >= toLogId; logId--) {
        Long undoKey = getOperationId(transactionId, logId);
        undoLog.operate(undoKey, null, decisionMaker); // 恢复 oldValue
        decisionMaker.reset();
    }
}
```
```text
  如图 4-40 所示，rollbackTo(Transaction t, maxLogId, toLogId)
     │
     ▼
  ┌──────────────────────────────────────────────┐
  │ 逆序遍历 undo log:                           │
  │ for (logId = maxLogId-1; logId >= toLogId)   │
  │     undoKey = (txId << 40) | logId           │
  │     undoLog.operate(undoKey, null, RDM)      │
  └──────────────────┬───────────────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────────────┐
  │ RollbackDecisionMaker.decide():              │
  │                                              │
  │ Record(mapId, key, oldValue)                 │
  │     │                                        │
  │     ├── oldValue == null → REMOVE(key)       │
  │     │   (原 INSERT, 删除该行)                 │
  │     │                                        │
  │     └── oldValue != null → PUT(key, oldV)    │
  │         (原 UPDATE, 恢复旧值)                 │
  └──────────────────────────────────────────────┘
```

下面 4 张图共同呈现 rollback 与 BitSet 快照的设计：图 4-40 追踪 rollbackTo 逆序遍历的恢复步骤，图 4-41 对比 commit 与 rollback 的差异，图 4-42 演示 VersionedBitSet 的 COW 复制更新，图 4-43 拆解读事务双读 BitSet 的快照一致性方案。

**图 4-40: 追踪 rollbackTo 逆序遍历 undo 的恢复步骤**
```text
  如图 4-41 所示，┌─────────────────┬───────────────────────────┐
  │   COMMIT        │   ROLLBACK                │
  ├─────────────────┼───────────────────────────┤
  │ 正向遍历 undo   │ 逆向遍历 undo             │
  │ commitDecision  │ rollbackDecision          │
  │ PUT 已提交版本  │ REMOVE 或 PUT oldValue    │
  │ clear undo log  │ 保留未回滚的 undo log     │
  │ 变更可见        │ 恢复到修改前状态          │
  │ 其他事务可读    │ 仿佛修改从未发生          │
  └─────────────────┴───────────────────────────┘
```
**图 4-41: 对比事务 commit 与 rollback 的处理差异**

> **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#mvcc`)
> 描述了 MVCC 模式下插入/更新操作只使用共享锁，仅 DDL 使用排他锁的行为。

### 4.5.4 VersionedBitSet
`VersionedBitSet` (VersionedBitSet.java:14) 是不可变的 BitSet：
- 每个更新操作创建新副本（COW）
- `flipCommittingTransactionsBit()` 使用 CAS 原子更新
- 读事务获取快照时可保证一致性

```text
  初始状态:
  VersionedBitSet v1 = { bit[0]=1, bit[1]=0, bit[2]=0 }
  (事务 0 打开)

  事务 1 打开:
  flipBit(1, true)
  ┌─────────────────────────────┐
  │ v1 (旧) { bit[0]=1 }       │
  │   ↓ COW 复制 + 修改         │
  │ v2 (新) { bit[0]=1, bit[1]=1}│
  │   ↑ CAS 更新 AtomicRef     │
  └─────────────────────────────┘
  读线程仍可安全读取 v1

  如图 4-42 所示，事务 0 提交:
  flipBit(0, false)
  ┌─────────────────────────────┐
  │ v2 (旧) { bit[0]=1, bit[1]=1}│
  │   ↓ COW 复制 + 修改         │
  │ v3 (新) { bit[1]=1 }       │
  │   ↑ CAS 更新 AtomicRef     │
  └─────────────────────────────┘
```
**图 4-42: 演示 VersionedBitSet 的 COW 复制更新**
```text
  如图 4-43 所示，读事务获取快照:
  while (true) {
      prev = committingTransactions  // 读 A
      root = map.getRoot()           // 读 B
      cur = committingTransactions   // 读 C
      if (prev == cur) break         // 一致
  }
  ┌──────────────────────────────────────────────┐
  │  时间轴:                                      │
  │  ──A────B────C──→                             │
  │    │    │    │                                │
  │    ├─ 读 VersionedBitSet (快照)             │
  │    ├─ 读 RootReference (B-Tree 根)           │
  │    └─ 再次读 VersionedBitSet                 │
  │       → 相同 = 一致的快照                     │
  │       → 不同 = 重试 (有并发修改)              │
  └──────────────────────────────────────────────┘
```
**图 4-43: 拆解读事务双读 BitSet 的快照一致性方案**

---

## 4.6 MVTable — 表与锁管理

**路径**: `org/h2/mvstore/db/MVTable.java` (1012 行)

MVTable 是基于 MVStore 的表实现，管理表级共享/排他锁。

### 4.6.1 锁模型
```java
// MVTable.java:114 — 排他锁持有者
private volatile SessionLocal lockExclusiveSession;

// MVTable.java:121 — 共享锁持有者 (ConcurrentHashSet)
private final ConcurrentHashMap<SessionLocal, SessionLocal> lockSharedSessions;

// MVTable.java:133 — 等待锁的 FIFO 队列
private final ArrayDeque<SessionLocal> waitingSessions;
```
```text
  如图 4-44 所示，MVTable
  ┌──────────────────────────────────────────────┐
  │                                              │
  │  lockExclusiveSession (volatile)             │
  │  ┌──────────────────────┐                    │
  │  │ SessionLocal (1个)   │  ← 当前持有排他锁 │
  │  └──────────────────────┘                    │
  │                                              │
  │  lockSharedSessions (ConcurrentHashMap)       │
  │  ┌────────┐ ┌────────┐ ┌────────┐           │
  │  │ Sess 1 │ │ Sess 2 │ │ Sess 3 │  ...     │
  │  └────────┘ └────────┘ └────────┘           │
  │  ↑ 可多个会话同时持有共享锁                    │
  │                                              │
  │  waitingSessions (ArrayDeque, FIFO)          │
  │  ┌────┐ → ┌────┐ → ┌────┐ → ┌────┐         │
  │  │ S4 │    │ S5 │    │ S6 │    │ S7 │        │
  │  └────┘    └────┘    └────┘    └────┘        │
  │  ↑ 等待锁的 FIFO 队列                         │
  └──────────────────────────────────────────────┘
```

下面 6 张图共同呈现 MVTable 锁管理的全貌：图 4-44 刻画三类锁字段，图 4-45 与图 4-46 串起读写锁的判断与状态迁移，图 4-47 汇总共享锁与排他锁的兼容关系，图 4-48 与图 4-49 收尾于 DFS 环路检测与死锁等待环。

**图 4-44: 刻画 MVTable 排他/共享/等待三类锁字段**
```text
  请求读锁:
  检查 lockExclusiveSession == null?
     ├── YES → lockSharedSessions.add(session) ✓
     └── NO  → waitingSessions.addLast(session)
               → 阻塞直到排他锁释放

  请求写锁:
  检查 lockExclusiveSession == null
  且 lockSharedSessions 为空?
     ├── YES → lockExclusiveSession = session ✓
     └── NO  → waitingSessions.addLast(session)
               → 阻塞直到所有锁释放

  释放读锁:
  lockSharedSessions.remove(session)
  → 通知 waitingSessions 队首线程

  如图 4-45 所示，释放写锁:
  lockExclusiveSession = null
  → 通知 waitingSessions 队首线程
```
**图 4-45: 追踪 MVTable 读写锁获取与释放的判断**

### 4.6.2 锁升级规则
| 当前锁状态 | 请求读锁 | 请求写锁 |
|-----------|---------|---------|
| 无锁       | 直接获得 | 直接获得 |
| 共享锁(S)  | +1       | 等待排他 |
| 排他锁(X)  | 被阻塞   | 被阻塞 |

```text
           如图 4-46 所示，┌─────────────────────────┐
           │      无锁 (None)        │
           └───┬─────────────────┬───┘
               │                 │
       请求读锁 │           请求写锁│
               ▼                 ▼
    ┌─────────────────┐  ┌─────────────────┐
    │  共享锁 (S)     │  │  排他锁 (X)     │
    │                 │  │                 │
    │ +1 共享锁       │  │ 锁住整个表      │
    │ 多个可同时持有  │  │ 唯一持有者      │
    └──────┬──────────┘  └──────┬──────────┘
           │                    │
           │ 请求写锁           │ 任何新请求
           ▼                    ▼
    ┌─────────────────────────────────────────┐
    │         等待队列 (FIFO)                  │
    │  → 当前锁释放后, 队首线程获得锁          │
    └─────────────────────────────────────────┘
```
**图 4-46: 描绘 MVTable 无锁、共享、排他的状态迁移**
```text
             如图 4-47 所示，请求方
         ┌─────┬─────┬─────┐
         │ 无  │  S  │  X  │
  ┌──────┼─────┼─────┼─────┤
  │ 无   │  ✓  │  ✓  │  ✓  │
  ├──────┼─────┼─────┼─────┤
  │ 当前 │ S   │  ✓  │  +1 │  ✗  │
  │ 持有 ├─────┼─────┼─────┼─────┤
  │      │ X   │  ✗  │  ✗  │  ✗  │
  └──────┴─────┴─────┴─────┘
  ✓ = 立即获得, +1 = 计数+1, ✗ = 等待
```
**图 4-47: 汇总 MVTable 共享锁与排他锁的兼容关系**

### 4.6.3 死锁检测
`checkDeadlock()` 使用 DFS 环路检测算法：

会话 A 等待 表 T1 (被 B 锁住)
   → 查询 B 正在等待什么
     → B 等待 表 T2 (被 A 锁住)
       → 检测到环路: A → T1 → B → T2 → A
         → 回滚 victim (根据优先级/时间戳选择)
```text
  输入: 当前会话 session, 等待的表 table
  输出: 是否检测到死锁

  checkDeadlock(session, table):
   ┌─────────────────────────────────────────┐
   │ for each holder in table 的锁持有者:     │
   │   if holder == session:                 │
   │     → 检测到死锁!                       │
   │   if holder 在等待其他表:               │
   │     → 递归 checkDeadlock(session, 其他表)│
   └─────────────────────────────────────────┘

  如图 4-48 所示，示例: A → T1 → B → T2 → A
       ┌─────────────────────────────────┐
       │  A 等待 T1 (被 B 持有 X 锁)    │
       │    ↓                            │
       │  检查 B 的等待状态              │
       │    ↓                            │
       │  B 等待 T2 (被 A 持有 X 锁)    │
       │    ↓                            │
       │  检查 A 的等待状态 → A 在等 T1 │
       │    ↓                            │
       │  A 已在递归栈中 → 死锁! ✗      │
       │  victim = A (回滚)              │
       └─────────────────────────────────┘
```
**图 4-48: 演示 MVTable 通过 DFS 环路检测识别死锁**
```text
  如图 4-49 所示，┌─────┐          ┌─────┐
  │ T1  │◄──等待───│  A  │
  │     │          │     │
  │  X  │          │优先级│← 低 → victim
  │ 锁  │          │低   │
  │  B  │          └──┬──┘
  └──┬──┘             │
     │ 持有            │ 等待
     ▼                ▼
  ┌─────┐          ┌─────┐
  │  B  │──等待───→│ T2  │
  │     │          │     │
  │优先级│          │  X  │
  │高   │          │ 锁  │
  └─────┘          │  A  │
                   └─────┘
  环路: A → T1 (被 B锁) → B → T2 (被 A锁) → A
  选择 victim: 低优先级 A → 回滚 A, 释放 T2
```
**图 4-49: 描绘 A-T1-B-T2 形成的死锁等待环**

### 4.6.4 架构图
```text
┌──────────────────────────────────────────────────────┐
│  MVTable extends TableBase                           │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────────┐  ┌───────────────────────┐  │
│  │  Lock Management    │  │  Index Management     │  │
│  │                     │  │                       │  │
│  │  lockExclusiveSession│  │  primaryIndex:        │  │
│  │  (volatile, 1个)    │  │  MVPrimaryIndex       │  │
│  │                     │  │                       │  │
│  │  lockSharedSessions  │  │  indexes:             │  │
│  │  (ConcurrentHashMap) │  │  ArrayList<Index>     │  │
│  │                     │  │  ├ MVPrimaryIndex     │  │
│  │  waitingSessions     │  │  └ MVSecondaryIndex[] │  │
│  │  (FIFO ArrayDeque)  │  │                       │  │
│  └─────────────────────┘  └───────────────────────┘  │
│                                                      │
│  死锁检测: DFS 环路检测                               │
│  lock() → doLock1() → checkDeadlock()               │
│                                                      │
│  Data Flow:                                          │
│  addRow(session, row)                                │
│    → primaryIndex.add(session, row)                  │
│      → TransactionMap.put() → MVMap.operate()       │
│    → secondaryIndex[i].add(session, row)             │
│      → TransactionMap.put() → MVMap.operate()       │
└──────────────────────────────────────────────────────┘
```
```text
  lock(session, lockType)
    → synchronized(this)
      → waitingSessions.addLast()
      → doLock1()
        ┌──────────────────────────────────┐
        │ 快速路径:                        │
        │ 已持有排他锁 → return true       │
        │ 已持有共享锁(且非排他) → true    │
        └──────────────────────────────────┘
        ┌──────────────────────────────────┐
        │ 慢速路径:                        │
        │ synchronized 等待 + 检查死锁     │
        │ → checkDeadlock()               │
        │ → 可能阻塞                      │
        └──────────────────────────────────┘

  addRow/removeRow
    → t.setSavepoint()
    → 遍历所有索引 add/remove
    → registerTableAsUpdated()
```
**图 4-50: 追踪 MVTable lock 与 addRow 的执行步骤**

### 4.6.5 关键方法
**`lock(SessionLocal session, int lockType)`** (MVTable.java:167):

```java
public boolean lock(SessionLocal session, int lockType) {
    // 快速路径: 已持有锁
    if (lockExclusiveSession == session) return true;
    if (lockType != EXCLUSIVE_LOCK && lockSharedSessions.containsKey(session)) return true;
    synchronized (this) {
        session.setWaitForLock(this, Thread.currentThread());
        waitingSessions.addLast(session);  // 入 FIFO 队列
        doLock1(session, lockType);        // 尝试获取锁，可能阻塞
        waitingSessions.remove(session);
    }
}
```

如图 4-50 所示，**`addRow(SessionLocal session, Row row)`** (MVTable.java:515):
```java
public void addRow(SessionLocal session, Row row) {
    Transaction t = session.getTransaction();
    long savepoint = t.setSavepoint();
    for (Index index : indexes) {
        index.add(session, row);  // 主键 + 所有二级索引
    }
    session.registerTableAsUpdated(this);
}
```

**`removeRow(SessionLocal session, Row row)`** (MVTable.java:480):
```java
public void removeRow(SessionLocal session, Row row) {
    Transaction t = session.getTransaction();
    long savepoint = t.setSavepoint();
    for (int i = indexes.size() - 1; i >= 0; i--) {
        indexes.get(i).remove(session, row); // 逆序删除索引
    }
    session.registerTableAsUpdated(this);
}
```
```text
  addRow()                          removeRow()
  ┌────────────────────┐            ┌────────────────────┐
  │ setSavepoint()     │            │ setSavepoint()     │
  │ for each index:    │            │ for i = size-1..0  │
  │   index.add()      │            │   index.remove()   │
  │   → primaryIndex   │            │   → secondaryIndex │
  │   → secondaryIndex │            │   → primaryIndex   │
  │ registerAsUpdated  │            │ registerAsUpdated  │
  └────────────────────┘            └────────────────────┘

  如图 4-51 所示，updateRow()
  ┌──────────────────────────────────────────────┐
  │ setKey(oldKey)  ← 保持行 ID 不变             │
  │ setSavepoint()                                │
  │ for each index:                               │
  │   index.update(session, oldRow, newRow)       │
  │   = remove(oldRow) + add(newRow)              │
  │ registerAsUpdated()                           │
  └──────────────────────────────────────────────┘
```
**图 4-51: 对比 addRow 与 removeRow 的索引遍历顺序**
```text
  添加行 (addRow):           删除行 (removeRow):
  主索引 → 二级索引 1 → 2    二级索引 N → ... → 1 → 主索引
  (正向)                     (逆向)

  如图 4-52 所示，原因: 主索引先写入确保行存在
  逆向删除避免索引引用已删除的行
```
**图 4-52: 对比 addRow 正向与 removeRow 逆向的遍历**

---

## 4.7 本章小结

本章深入分析了 H2 Database 的六个核心模块：Database 全局入口、Session 会话管理、MVStore 存储引擎、MVMap B-Tree 映射、TransactionStore 事务协调、MVTable 表操作封装。每层围绕核心数据结构和关键源码展开，从顶层入口到底层存储构成了完整的模块链路。

## 4.8 延伸思考

下面 4 道自查题用来检验读者是否能把本章六大模块的职责切分迁移到其他场景。

**1. 🟢★ 用一句话概括 SessionLocal 持有的核心状态，并说明为什么会话本身并不直接持有"当前事务"对象。**

> 提示：把 SessionLocal 与 TransactionStore.Transaction 之间的引用方向看清楚，事务生命周期由谁创建、谁结束。
> 回顾：§4.2 SessionLocal — 会话管理、§4.5 TransactionStore — 事务协调器

**2. 🟢★ 用层次关系图说明 TransactionStore、MVStore、MVMap 三者的依赖与组合方式，并指出 TransactionStore 为什么不能直接复用 MVMap 而要包装出自己的 TransactionMap。**

> 提示：从可见性判断、Undo Log、VersionedValue 这三件事入手，思考事务语义在哪一层加入。
> 回顾：§4.3 MVStore — 存储引擎核心、§4.4 MVMap — 并发 B-Tree 映射、§4.5 TransactionStore — 事务协调器

**3. 🔵★★ 假设把 MVMap 的 `RootReference` 由 `AtomicReference` 改为普通 `volatile` 字段，仅保留可见性而放弃 CAS。这会破坏哪些既有不变量？请至少给出两条结构性理由。**

> 提示：聚焦 Copy-on-Write 提交点的写入冲突检测，并联想多个写线程同时尝试替换根节点时的中间状态。
> 回顾：§4.4 MVMap — 并发 B-Tree 映射、§4.6 MVTable — 表与锁管理

**4. 🟠★★★ 在 IntelliJ IDEA 中以 `SessionLocal.commit()` 为入口设置断点，运行一次最小提交脚本（一次 INSERT + COMMIT），记录从 SessionLocal 到 TransactionStore 再到 MVStore 的实际调用栈，并对照本章描述指出至少一个本章未显式列出的中间方法。**

> 提示：结合 IDE 的 Call Hierarchy 与运行期堆栈双视图核对；注意 commit 路径上对 Undo Log 的清理调用顺序。
> 回顾：§4.2 SessionLocal — 会话管理、§4.5 TransactionStore — 事务协调器、第4章

## 4.9 延展阅读

- H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html`) — MVStore 体系结构与 B-Tree 实现参考
- H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#transaction_isolation`) — 事务隔离级别与 MVCC 行为说明
- 本书第5章《核心流程解读》 — 各模块在 9 个核心流程中的协作方式
- 本书第6章§6.1-6.3 — B-Tree/CoW/MVCC 算法基础
- 本书第9章《持久化引擎深度解析》 — MVStore 的 Chunk 存储与恢复细节


# 第5章 核心流程解读

> **本章导读**: 本章逐一分析 H2 的 9 个核心流程：SELECT、INSERT、UPDATE、DELETE、COMMIT、ROLLBACK、COMPACT、CHUNK、READ。每个流程按照流程图→核心逻辑阐述→关键代码引用的标准化模板进行组织。
> **前置知识**: 第4章《核心模块深度解读》（各流程依赖的模块实现）；第2章§2.3-2.4（Engine/Command 层入口）
> **章节要点**:
> - 掌握 9 个核心流程的执行链路
> - 理解各流程的关键数据结构和算法
> - 熟悉流程间的依赖关系和触发条件
> - 了解流程对应的核心源码文件和方法
> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

> 本章追踪 9 个核心流程的完整执行路径。各核心算法的基础原理详见第6章《H2 数据库核心算法分析》。SQL 语句的解析与优化细节见第7章《SQL 执行全流程》和第8章《查询优化器深度解读》，事务提交与持久化机制见第9章《持久化引擎深度解析》和第10章《锁实现与并发控制》。

## 5.1 SELECT 查询流程

### 5.1.1 流程图
```text
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ JDBC Client │────→│  JdbcStatement   │────→│  Command         │
│             │     │  .executeQuery() │     │  .executeQuery()│
└──────────────┘     └──────────────────┘     └────────┬────────┘
                                                       │
                                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Parser.prepareCommand(sql)                     │
│  Parser.java:485                                                 │
│    → parse(sql, null) → Select 对象                              │
│    → Select.prepare()                                            │
│      → prepareExpressions()                                      │
│      → preparePlan() → Optimizer.optimize()                     │
└──────────────────────────────────────────────────────────────────┘
                                                       │
                                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  CommandContainer.query(maxRows)                                 │
│    → Select.query(maxRows)                                       │
│      → Query.query(limit, null)                                  │
│        → queryWithoutCache(maxRows, target)  [Select.java:806]  │
└──────────────────────────────────────────────────────────────────┘
                                                       │
                                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  queryWithoutCache()  [Select.java:806-885]                     │
│                                                                    │
│  1. 解析 offset/fetch                                            │
│  2. 创建 LocalResult (如果需要排序/去重/分组)                     │
│  3. topTableFilter.startQuery(session)  ← 打开表扫描              │
│  4. topTableFilter.reset()                                       │
│  5. topTableFilter.lock(session)      ← 获取读锁                  │
│  6. 根据查询类型分发:                                             │
│     ├ isQuickAggregateQuery → queryQuick()                       │
│     ├ isWindowQuery → queryGroupWindow() / queryWindow()         │
│     ├ isGroupQuery → queryGroupSorted() / queryGroup()           │
│     ├ isDistinctQuery → queryDistinct()                          │
│     └ 普通查询 → queryFlat()  [Select.java:733]                 │
│       └ LazyResultQueryFlat → iterate TableFilter.next()        │
│         → 逐行评估 WHERE 条件                                    │
│         → 投影列计算                                             │
└──────────────────────────────────────────────────────────────────┘
                                                       │
                                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  TableFilter.next()                                              │
│    → indexCursor.next()                                          │
│      → 读取满足索引条件的下一行                                   │
│    → 评估余下 WHERE 条件                                         │
│    → 返回匹配行                                                  │
│                                                                  │
│  对于 TransactionMap:                                            │
│  TransactionMap.get(key) → useSnapshot() [TransactionMap.java:560]│
│    → 获取 (RootReference + committingTransactions) 原子对         │
│    → getFromSnapshot() → 检查 VersionedValue.operationId         │
│      → 如果是其他事务未提交的变更: 返回 committedValue           │
│      → 否则: 返回 currentValue                                  │
└──────────────────────────────────────────────────────────────────┘
```
```text
   如图 5-1 所示，queryWithoutCache()
        │
        ▼
  ┌──────────────────────────────────────────┐
  │  解析 offset/fetch                       │
  │  创建 LocalResult (按需)                 │
  │  topTableFilter.startQuery/reset/lock   │
  └──────────────────┬───────────────────────┘
                     │
       ┌─────────────┼─────────────┬───────────┐
       │             │             │           │
       ▼             ▼             ▼           ▼
  ┌────────┐  ┌──────────┐  ┌────────┐  ┌───────────┐
  │ quick  │  │ window   │  │ group  │  │  flat     │
  │Agg     │  │ query    │  │ query  │  │  query    │
  │COUNT(*)│  │ 窗口函数  │  │ GROUP  │  │ 逐行扫描  │
  │MAX/MIN │  │ RANK()   │  │ BY     │  │ WHERE过滤 │
  │SUM     │  │ OVER()   │  │ HAVING │  │ 投影计算  │
  └────────┘  └──────────┘  └────────┘  └───────────┘
       │             │          │              │
       └─────────────┴──────────┴──────────────┘
                          │
                          ▼
                   LocalResult → 返回给客户端
```
**图 5-1: 拆解 SELECT 五种查询类型的分发分支**

### 5.1.2 核心逻辑阐述

```text
本节速览：5.1.2 核心逻辑阐述

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

SELECT 查询执行的核心路径可概括为五个阶段：(1) **SQL 解析** — `Parser.prepareCommand()` 将 SQL 文本解析为 `Select` 对象，触发列绑定和类型推导；(2) **计划生成** — `preparePlan()` 调用 `Optimizer.optimize()`，基于代价模型选择最优索引和表连接顺序；(3) **计划执行** — `queryWithoutCache()` 根据查询类型（聚合/窗口/分组/普通）分派到不同的查询方法；(4) **行迭代** — `TableFilter.next()` 驱动索引游标逐行扫描，对每行评估 WHERE 条件并计算投影列；(5) **结果组装** — 满足条件的行写入 `LocalResult`，应用排序/去重/分页后返回客户端。整个流程中，步骤 (1)(2) 仅在首次执行时发生，后续复用缓存计划。

### 5.1.3 关键代码引用
| 文件 | 行号 | 方法 |
|------|------|------|
| `Parser.java` | 485 | `prepareCommand()` |
| `Select.java` | 806 | `queryWithoutCache()` |
| `Select.java` | 733 | `queryFlat()` |
| `Select.java` | 474 | `queryGroup()` |
| `Select.java` | 451 | `queryGroupWindow()` |
| `Select.java` | 314 | `queryGroupSorted()` |
| `TransactionMap.java` | 560 | `useSnapshot()` |
| `TransactionMap.java` | 493 | `getFromSnapshot()` |
| `Optimizer.java` | — | `optimize()` |

```text
  如图 5-2 所示，Parser.java:485 ──→ Select (对象)
       │
       ▼
  Select.java:806 ──→ queryWithoutCache()
       │
       ├──→ queryFlat()    [Select.java:733]
       │     └── TableFilter.next()
       │           └── indexCursor.next()
       │
       ├──→ queryGroup()   [Select.java:474]
       │
       ├──→ queryWindow()  [Select.java:441]
       │
       └──→ TransactionMap.get(key) [TransactionMap.java:560]
              └── useSnapshot()         [560]
              └── getFromSnapshot()     [493]
```

下面 4 张图共同呈现 SELECT 执行的脉络：图 5-2 梳理从解析到 MVCC 读取的调用链，图 5-3 概览 Optimizer 选择索引与连接顺序的输出，图 5-4 拆解 queryWithoutCache 的六步步骤，图 5-5 解读 LazyResultQueryFlat 的按需迭代策略。

**图 5-2: 梳理 SELECT 从解析到 MVCC 读取的调用链**
```text
  如图 5-3 所示，Parser.parse(sql) → Select
       │
       ▼
  Select.prepare()
       │
       ├── prepareExpressions() ← 解析 SELECT 列/WHERE
       │
       └── preparePlan()
             └── Optimizer.optimize()
                   ┌──────────────────────────────────┐
                   │ 优化器决策:                       │
                   │ ├ 选择最优索引                    │
                   │ ├ 决定 JOIN 顺序                  │
                   │ ├ 谓词下推                        │
                   │ └ 确定扫描方向                    │
                   └──────────────────────────────────┘
                         │
                         ▼
                   TableFilter 链
                   (执行计划)
```
**图 5-3: 概览 Optimizer 选择索引与连接顺序的输出**

### 5.1.4 查询调度流程

**源码位置**: `org/h2/command/query/Select.java:806`

```java
protected ResultInterface queryWithoutCache(long maxRows, ResultTarget target) {
    // ... offset/fetch 解析, LocalResult 创建 ...
    topTableFilter.startQuery(session);
    topTableFilter.reset();
    topTableFilter.lock(session);
    // 根据查询类型分发
    if (isQuickAggregateQuery) {
        queryQuick(columnCount, to, ...);
    } else if (isWindowQuery) {
        queryWindow(columnCount, result, ...);
    } else if (isGroupQuery) {
        queryGroup(columnCount, result, ...);
    } else {
        lazyResult = queryFlat(columnCount, to, offset, limit, withTies, quickOffset);
    }
    // ...
}
```
```text
  如图 5-4 所示，queryWithoutCache(maxRows, target)
  ┌──────────────────────────────────────────────────┐
  │  1. 解析 offset/fetch/limit                     │
  │  2. 创建 LocalResult (排序/去重/分组)            │
  │  3. topTableFilter.startQuery(session)          │
  │  4. topTableFilter.reset()                      │
  │  5. topTableFilter.lock(session)     ← 读锁    │
  │  6. 查询类型分发:                               │
  │     ├─ quickAgg → 直接聚合(COUNT/MAX等)         │
  │     ├─ window  → 窗口函数分组                   │
  │     ├─ group   → GROUP BY 分组                  │
  │     └─ flat    → 逐行扫描 + WHERE + 投影        │
  └──────────────────────────────────────────────────┘
```
**图 5-4: 拆解 queryWithoutCache 的六步执行步骤**
```text
  如图 5-5 所示，queryFlat()
       │
       ▼
  LazyResultQueryFlat (惰性求值)
  ┌──────────────────────────────────────────────┐
  │                                              │
  │ 每次 fetch next row:                         │
  │  while (rowsRemaining > 0) {                 │
  │    topTableFilter.next()                     │
  │    → indexCursor.next()  ← 索引定位          │
  │    → evaluate WHERE 条件                     │
  │    if matches:                               │
  │      → 计算投影列                            │
  │      → 返回行                                │
  │  }                                           │
  │                                              │
  │ 特点: 按需计算, 不一次性加载所有行            │
  │ 适合 LIMIT / 流式结果                         │
  └──────────────────────────────────────────────┘
```
**图 5-5: 解读 LazyResultQueryFlat 的按需迭代策略**

---

## 5.2 INSERT 写入流程

### 5.2.1 流程图
```text
┌──────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│ JDBC Client │────→│  JdbcPreparedStatement│────→│  Command          │
│             │     │  .executeUpdate()     │     │  .executeUpdate() │
└──────────────┘     └──────────────────────┘     └─────────┬─────────┘
                                                             │
                                                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Insert.update()  [Insert.java:131]                              │
│    → insertRows()  [Insert.java:142]                            │
└──────────────────────────────────────────────────────────────────┘
                                                             │
                                                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  insertRows() 执行步骤:                                          │
│                                                                  │
│  1. session.getUser().checkTableRight(table, Right.INSERT)      │
│                                                                  │
│  2. table.fire(session, Trigger.INSERT, true)  ← BEFORE 触发器  │
│                                                                  │
│  3. 对每个 VALUES 行或 SELECT 结果行:                             │
│     a. Row newRow = table.getTemplateRow()                      │
│     b. 计算列表达式: newRow.setValue(index, e.getValue(session)) │
│     c. table.convertInsertRow(...)  ← 类型转换/默认值              │
│     d. table.lock(session, Table.WRITE_LOCK)                    │
│     e. table.addRow(session, newRow)  ← 关键步骤                 │
│        └ MVTable.addRow()  [MVTable.java:515]                   │
│          ├ MVPrimaryIndex.add() → TransactionMap.put()          │
│          │   → MVMap.operate()  [MVMap.java:1874]               │
│          └ MVSecondaryIndex[i].add() → TransactionMap.put()     │
│     f. table.fireAfterRow(...) ← AFTER 行级触发器               │
│                                                                  │
│  4. table.fire(session, Trigger.INSERT, false) ← AFTER 触发器   │
└──────────────────────────────────────────────────────────────────┘
```
```text
  INSERT INTO t VALUES (...)
  ┌─────────────────────────────────────────┐
  │ for each VALUES 行:                     │
  │   newRow = getTemplateRow()             │
  │   计算列表达式                          │
  │   convertInsertRow (类型转换)           │
  │   lock(WRITE_LOCK)                      │
  │   addRow(session, newRow)               │
  │   fireAfterRow                          │
  └─────────────────────────────────────────┘

  如图 5-6 所示，INSERT INTO t SELECT ...
  ┌─────────────────────────────────────────┐
  │ lock(WRITE_LOCK)  ← 提前锁表           │
  │ query.query(0, this) ← ResultTarget    │
  │   └ 每次回调 addRow()                   │
  │   └ fireAfterRow                       │
  └─────────────────────────────────────────┘
  区别: VALUES 批量逐行, SELECT 流式回调
```
**图 5-6: 对比 INSERT VALUES 与 SELECT 写入路径**

### 5.2.2 核心逻辑阐述

```text
本节速览：5.2.2 核心逻辑阐述

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


```text
INSERT 流程遵循"收集→执行"两阶段模式。**收集阶段**：`Insert.update()` 首先解析 VALUES 子句或子查询，生成待插入的行数据集合存储在 `rows` 列表中。每行数据经过表达式求值（`Expression.getValue()`）、类型转换（`Value.convertTo()`）和默认值填充后，确保符合列定义约束。**执行阶段**：遍历 `rows` 列表，对每行依次调用 `table.addRow()` → `MVPrimaryIndex.add()`（写入主索引 B-Tree）→ `MVSecondaryIndex[i].add()`（更新每个二级索引）。INSERT 是"先加主索引再加二级索引"的正向顺序，与 DELETE 的逆向顺序相反。所有变更在当前事务的 MVMap 版本中可见，提交后才对其他事务开放。
```

### 5.2.3 关键代码引用
| 文件 | 行号 | 方法 |
|------|------|------|
| `Insert.java` | 131 | `update()` |
| `Insert.java` | 142 | `insertRows()` |
| `MVTable.java` | 515 | `addRow()` |

```text
| `MVPrimaryIndex.java` | — | `add()` → `dataMap.put()` |
```
| `MVMap.java` | 1874 | `operate()` |

```text
  如图 5-7 所示，Insert.update()           [Insert.java:131]
       │
       ▼
  Insert.insertRows()       [Insert.java:142]
       │
       ├── lock(WRITE_LOCK)
       │
       ▼
  MVTable.addRow()          [MVTable.java:515]
       │
       ├── MVPrimaryIndex.add()
       │     └── dataMap.put()
       │           └── TransactionMap.put()
       │                 └── MVMap.operate()  [MVMap.java:1874]
       │
       └── MVSecondaryIndex[i].add()
             └── TransactionMap.put()
                   └── MVMap.operate()
```
**图 5-7: 梳理 INSERT 至 MVMap.operate 的调用链**
```text
  如图 5-8 所示，BEFORE 语句级触发器 (statement-level, INSERT=true)
       │
       ▼
  ┌─────────────────────────────────────────┐
  │ 对每行:                                  │
  │   BEFORE 行级触发器 (fireAfterRow)      │
  │   执行实际 INSERT (addRow)              │
  │   AFTER 行级触发器                      │
  └─────────────────────────────────────────┘
       │
       ▼
  AFTER 语句级触发器 (statement-level, INSERT=false)
```
**图 5-8: 梳理 INSERT 语句级与行级触发器的顺序**

### 5.2.4 行插入执行流程

**源码位置**: `org/h2/command/dml/Insert.java:142`

```java
private long insertRows() {
    session.getUser().checkTableRight(table, Right.INSERT);
    table.fire(session, Trigger.INSERT, true);
    rowNumber = 0;
    int listSize = valuesExpressionList.size();
    if (listSize > 0) {
        for (int x = 0; x < listSize; x++) {
            Row newRow = table.getTemplateRow();
            Expression[] expr = valuesExpressionList.get(x);
            for (int i = 0; i < columnLen; i++) {
                newRow.setValue(index, e.getValue(session));
            }
            table.lock(session, Table.WRITE_LOCK);
            table.addRow(session, newRow);  // MVTable.addRow()
            table.fireAfterRow(session, null, newRow, false);
        }
    } else {
        // INSERT ... SELECT
        table.lock(session, Table.WRITE_LOCK);
        query.query(0, this);  // 通过 ResultTarget 回调 addRow
    }
    table.fire(session, Trigger.INSERT, false);
    return rowNumber;
}
```
```text
  insertRows()
       │
       ▼
  ┌──────────────────────────────────────────┐
  │  checkTableRight(table, Right.INSERT)    │
  │  fire(BEFORE INSERT)                     │
  └──────────────────┬───────────────────────┘
                     │
              ┌──────┴──────┐
              │ VALUES 形式  │ SELECT 形式
              └──────┬──────┘
                     │
                     ▼
  ┌──────────────────────────────────────────┐
  │ for each VALUES row:                     │
  │   getTemplateRow()                       │
  │   计算列值                               │
  │   convertInsertRow()                     │
  │   lock(WRITE_LOCK)                       │
  │   addRow()                               │
  │   fireAfterRow()                         │
  └──────────────────────────────────────────┘

  或:

  如图 5-9 所示，┌──────────────────────────────────────────┐
  │ lock(WRITE_LOCK)                         │
  │ query.query(0, this)  ← ResultTarget   │
  │   └ addRow() 回调                        │
  │   └ fireAfterRow 回调                    │
  └──────────────────────────────────────────┘
       │
       ▼
  fire(AFTER INSERT)
  return rowNumber
```
**图 5-9: 拆解 insertRows 的两种执行分支**
```text
  如图 5-10 所示，┌─────────────┐
  │ 检查权限     │ → 用户无权限 → 抛出异常
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │ BEFORE 触发  │ → 触发器可修改行或阻止
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │ 创建新行     │ → getTemplateRow + 设置列值
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │ 获取写锁     │ → 阻塞直到获得排他锁
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │ 写入索引     │ → 主索引 + 二级索引
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │ AFTER 触发   │ → 行级 + 语句级
  └─────────────┘
```
**图 5-10: 追踪 INSERT 从权限检查到触发器的状态序列**

---

## 5.3 UPDATE 更新流程

### 5.3.1 流程图
```text
┌──────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│ JDBC Client │────→│  JdbcPreparedStatement│────→│  Command          │
│             │     │  .executeUpdate()     │     │  .executeUpdate() │
└──────────────┘     └──────────────────────┘     └─────────┬─────────┘
                                                             │
                                                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Update.update()  [Update.java:49]                              │
│  Update extends FilteredDataChangeStatement                     │
│    → DataChangeStatement                                        │
│                                                                  │
│  1. targetTableFilter.startQuery(session)                       │
│  2. targetTableFilter.reset()                                   │
│  3. table.fire(session, Trigger.UPDATE, true) ← BEFORE 触发器   │
│  4. table.lock(session, Table.WRITE_LOCK)                       │
│  5. 逐行迭代: while (nextRow(limitRows, count))                 │
│     a. Row row = lockAndRecheckCondition()  ← 检查 WHERE        │
│     b. setClauseList.prepareUpdate(...)  ← 计算 SET 表达式       │
│        → rows.addRow(newRow)  ← 收集需要更新的行                │
│  6. doUpdate(this, session, table, rows)  ← 批量执行更新        │
│     └ 对每个旧行:                                                │
│       MVTable.updateRow(session, oldRow, newRow)                 │
│       [MVTable.java:535]                                        │
│       → 对每个索引:                                              │
│         index.update(session, oldRow, newRow)                   │
│         → remove(oldRow) + add(newRow)                          │
│  7. table.fire(session, Trigger.UPDATE, false) ← AFTER 触发器   │
└──────────────────────────────────────────────────────────────────┘
```
```text
  阶段 1: 收集 (Collect)
  ┌─────────────────────────────────────────────┐
  │ startQuery → reset → lock(WRITE_LOCK)      │
  │ while nextRow():                            │
  │   lockAndRecheckCondition()                 │
  │   prepareUpdate() → compute new values      │
  │   rows.addRow(newRow)                       │
  └─────────────────────────────────────────────┘

  如图 5-11 所示，阶段 2: 执行 (Execute)
  ┌─────────────────────────────────────────────┐
  │ doUpdate(this, session, table, rows)        │
  │ for each oldRow:                            │
  │   MVTable.updateRow(oldRow, newRow)         │
  │     → for each index:                       │
  │         index.update(oldRow, newRow)        │
  │         = remove(oldRow) + add(newRow)      │
  └─────────────────────────────────────────────┘
  优势: 先在无锁阶段收集, 再批量执行写操作
```
**图 5-11: 追踪 UPDATE 收集与执行两阶段的处理**

### 5.3.2 核心逻辑阐述

```text
本节速览：5.3.2 核心逻辑阐述

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


```text
UPDATE 执行沿用了与 DELETE 相同的"收集→执行"两阶段模式，这是 MVStore 写入锁管理的关键设计。**收集阶段**：`Update.update()` 驱动 `TableFilter` 逐行扫描满足 WHERE 条件的行，将匹配行的 Row 对象暂存在 `rows` 列表中。此阶段仅持有读锁，多个更新事务可以并发扫描。**执行阶段**：获取写锁后，对 `rows` 中的每行执行 `MVTable.updateRow(session, oldRow, newRow)`。该方法内部先调用 `removeRow()` 删除旧行（逆向遍历二级索引→主索引），再调用 `addRow()` 插入新行（正向遍历主索引→二级索引）。`updateRow` 通过 MVStore 的 COW 机制创建新版本的 Page，不影响正在进行的读操作。旧版本数据在 compact 阶段被回收。
```

### 5.3.3 关键代码引用
| 文件 | 行号 | 方法 |
|------|------|------|
| `Update.java` | 34 | `class Update extends FilteredDataChangeStatement` |
| `Update.java` | 49 | `update()` |
| `MVTable.java` | 535 | `updateRow()` |
| `FilteredDataChangeStatement.java` | 18 | 抽象基类 |

```text
  如图 5-12 所示，Update.java:49
       │  extends
       ▼
  FilteredDataChangeStatement.java:18  (抽象基类)
       │  extends
       ▼
  DataChangeStatement
       │
       ▼
  MVTable.java:535  ──→ Index.update()
                        ├── MVPrimaryIndex
                        │     └── remove(old) + add(new)
                        │
                        └── MVSecondaryIndex
                              └── remove(old) + add(new)
```

下面 4 张图共同呈现 UPDATE 的执行细节：图 5-12 梳理 Update 至 MVTable 的继承层级，图 5-13 对比前后行的字段值变化，图 5-14 拆解主索引与二级索引的更新细节，图 5-15 对比主索引 PUT 与二级索引 remove+add 策略。

**图 5-12: 梳理 Update 至 MVTable 的文件继承层级**
```text
  更新前:
  Row (id=1, key=100, version=3)
  ┌─────┬──────┬──────┬──────┐
  │ id  │ name │ age  │ ver │
  ├─────┼──────┼──────┼──────┤
  │ 1   │ Bob  │ 30   │  3  │
  └─────┴──────┴──────┴──────┘

  UPDATE t SET age=31 WHERE id=1

  如图 5-13 所示，更新后:
  Row (id=1, key=100, version=4)
  ┌─────┬──────┬──────┬──────┐
  │ id  │ name │ age  │ ver │
  ├─────┼──────┼──────┼──────┤
  │ 1   │ Bob  │ 31   │  4  │
  └─────┴──────┴──────┴──────┘
  key 保持不变, version 递增
```
**图 5-13: 对比 UPDATE 前后行的字段值变化**

### 5.3.4 行更新执行流程

**源码位置**: `org/h2/mvstore/db/MVTable.java:535`

```java
public void updateRow(SessionLocal session, Row oldRow, Row newRow) {
    newRow.setKey(oldRow.getKey());  // 保持行 ID 不变
    Transaction t = session.getTransaction();
    long savepoint = t.setSavepoint();
    for (Index index : indexes) {
        index.update(session, oldRow, newRow);  // 各索引更新
    }
    session.registerTableAsUpdated(this);
}
```
```text
  如图 5-14 所示，updateRow(session, oldRow, newRow)
       │
       ▼
  setKey(oldRow.getKey()) ← 行 ID 不变
       │
       ▼
  for each index in indexes:
       │
       ├── MVPrimaryIndex.update()
       │     └── MVMap.operate(key, newValue, PUT)
       │           COW 复制: 仅更新主索引条目
       │
       ├── MVSecondaryIndex1.update()
       │     └── remove(oldRow Key) + add(newRow Key)
       │           二级索引: 删除旧条目 + 插入新条目
       │
       └── MVSecondaryIndex2.update()
             └── remove(oldRow Key) + add(newRow Key)
       │
       ▼
  registerTableAsUpdated()
```
**图 5-14: 拆解 updateRow 主索引与二级索引的更新细节**
```text
  主索引 (Primary Index):
  ┌──────────────────────────────────┐
  │ 直接 PUT(key, newRow)           │
  │ key = 行 ID (保持不变)           │
  │ → TransactionMap.put()           │
  │ → VersionedValue 替换            │
  └──────────────────────────────────┘

  如图 5-15 所示，二级索引 (Secondary Index):
  ┌──────────────────────────────────┐
  │ 先 remove 旧索引条目             │
  │ 再 add 新索引条目                │
  │ 因为索引列值可能改变              │
  │ 例: age 30→31, 索引位置变化     │
  └──────────────────────────────────┘
```
**图 5-15: 对比主索引 PUT 与二级索引 remove+add 策略**

---

## 5.4 DELETE 删除流程

### 5.4.1 流程图
```text
┌──────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│ JDBC Client │────→│  JdbcPreparedStatement│────→│  Command          │
│             │     │  .executeUpdate()     │     │  .executeUpdate() │
└──────────────┘     └──────────────────────┘     └─────────┬─────────┘
                                                             │
                                                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Delete.update()  [Delete.java:41]                               │
│  Delete extends FilteredDataChangeStatement                      │
│                                                                  │
│  1. targetTableFilter.startQuery(session)                       │
│  2. targetTableFilter.reset()                                   │
│  3. table.fire(session, Trigger.DELETE, true) ← BEFORE 触发器   │
│  4. table.lock(session, Table.WRITE_LOCK)                       │
│  5. 逐行迭代: while (nextRow(limitRows, count))                 │
│     a. Row row = lockAndRecheckCondition()  ← 检查 WHERE        │
│     b. rows.addRow(row)  ← 收集需要删除的行                     │
│  6. doDelete(this, session, table, rows)  ← 批量执行删除        │
│     └ 对每行: MVTable.removeRow(session, row)                   │
│       [MVTable.java:480]                                        │
│       → 逆序遍历索引:                                            │
│         for (int i = indexes.size()-1; i >= 0; i--)             │
│           index.remove(session, row)                            │
│         → MVPrimaryIndex.remove() → TransactionMap.remove()     │
│         → MVSecondaryIndex[i].remove()                          │
│       → 行在 MVMap 中标记为删除 (不立即回收空间)                 │
│  7. table.fire(session, Trigger.DELETE, false) ← AFTER 触发器   │
└──────────────────────────────────────────────────────────────────┘
```
```text
  阶段 1: 收集 (Collect)
  ┌─────────────────────────────────────────────┐
  │ startQuery → reset → lock(WRITE_LOCK)      │
  │ while nextRow():                            │
  │   lockAndRecheckCondition()                 │
  │   rows.addRow(row)                          │
  └─────────────────────────────────────────────┘

  如图 5-16 所示，阶段 2: 执行 (Execute)
  ┌─────────────────────────────────────────────┐
  │ doDelete(this, session, table, rows)        │
  │ for each row:                               │
  │   MVTable.removeRow(session, row)           │
  │     → 逆向遍历索引: N → ... → 1 → 主索引    │
  │     → row 标记为删除 (MVMap 中逻辑删除)     │
  └─────────────────────────────────────────────┘
```
**图 5-16: 对比 DELETE 与 UPDATE 的两阶段执行模式**

### 5.4.2 核心逻辑阐述

```text
本节速览：5.4.2 核心逻辑阐述

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


```text
DELETE 使用与 UPDATE 相同的"收集→执行"两阶段模式。**收集阶段**：`Delete.update()` 扫描满足 WHERE 条件的行，在 `rows` 列表中暂存待删除的 Row 引用。收集阶段仅持有读锁，允许多事务并发识别自己的删除目标。**执行阶段**：获取写锁后，对每行调用 `MVTable.removeRow(session, row)`。关键设计在于**逆向索引删除**：从最后一个二级索引开始删除，最后删除主索引。这一顺序确保在删除过程中不会产生指向已删除行的孤立索引条目。删除操作在 MVMap 中是**逻辑删除**——行数据仍占用空间，仅通过 VersionedValue 标记为不可见。物理空间回收发生在后续 compact 阶段，重写 Chunk 时跳过已标记删除的数据。
```

### 5.4.3 关键代码引用
| 文件 | 行号 | 方法 |
|------|------|------|
| `Delete.java` | 33 | `class Delete extends FilteredDataChangeStatement` |
| `Delete.java` | 41 | `update()` |
| `MVTable.java` | 480 | `removeRow()` |

```text
  如图 5-47 所示，Delete.java:41 (update)
       │  extends
       ▼
  FilteredDataChangeStatement
       │  extends
       ▼
  DataChangeStatement
       │
       ├── doDelete() → MVTable.removeRow() [480]
       │     ├── 逆向遍历索引
       │     │   ├── MVSecondaryIndex[n].remove()
       │     │   ├── ...
       │     │   └── MVPrimaryIndex.remove()
       │     │
       │     └── 行标记为删除 (逻辑删除)
       │
       └── fire(AFTER DELETE 触发器)
```

下面 5 张图共同呈现 DELETE 的全链路：图 5-47 梳理 Delete 至 MVTable 的继承层级，图 5-17 与图 5-48 串起索引遍历方向与触发器链，图 5-18 与图 5-19 收尾于标记到 compact 的时间线和逻辑/物理删除的可见性差异。

**图 5-47: 梳理 Delete 至 MVTable 的文件继承层级**
```text
  正向添加 (addRow):                 逆向删除 (removeRow):
  主索引 → 二级索引1 → 二级索引2    二级索引2 → 二级索引1 → 主索引
  (依赖: 主索引先存在)              (依赖: 先删引用再删主体)

  如图 5-17 所示，原因:
  addRow: 先建主记录, 再建引用
  removeRow: 先删引用(二级索引), 再删主记录
  避免孤立引用指向已删除的行
```
**图 5-17: 对比 DELETE 与 INSERT 的索引遍历方向**
```text
  如图 5-48 所示，DELETE FROM t WHERE id=1
       │
       ▼
  ┌────────────────────────────────────┐
  │ Delete.update()                    │
  │ → 解析 WHERE  → 定位匹配行         │
  └──────────┬─────────────────────────┘
             ▼
  ┌────────────────────────────────────┐
  │ TableFilter.fireBeforeRow()        │
  │ → BEFORE DELETE 触发器             │
  └──────────┬─────────────────────────┘
             ▼
  ┌────────────────────────────────────┐
  │ MVTable.removeRow(session, row)    │
  │                                    │
  │  逆向遍历索引:                     │
  │  for (i = lastIndex; i >= 0; i--) │
  │    removeFromIndex(i, row)        │
  │  removeFromPrimaryIndex(row)      │
  │  row.setDeleted(true)             │
  └──────────┬─────────────────────────┘
             ▼
  ┌────────────────────────────────────┐
  │ MVTable.fireAfterRow()             │
  │ → AFTER DELETE 触发器              │
  └────────────────────────────────────┘
```
**图 5-48: 追踪 DELETE 从权限检查到触发器的完整链**

#### 5.4.3.1 注意: 空间回收
行标记为删除后，在 MVMap 中并不立即回收空间。实际的物理删除发生在：
1. MVStore 的 compact 阶段（重写 Chunk 时跳过已删除数据）
2. 新 Chunk 写入时，旧 Chunk 中的已删除数据不再被引用

```text
  如图 5-18 所示，时间线:
  DELETE 语句
     │
     ▼
  ┌────────────────────────────────────┐
  │ MVMap.markRemoved(key)            │
  │ VersionedValue 标记为已删除        │
  │ (逻辑删除, 空间未回收)             │
  └────────────────────────────────────┘
     │
     ▼ (等待 compact 触发)
  ┌────────────────────────────────────┐
  │ MVStore compact 阶段:             │
  │ Chunk 扫描 → 识别已删除 page      │
  │ 跳过已删除数据 → 不写入新 Chunk   │
  └────────────────────────────────────┘
     │
     ▼
  ┌────────────────────────────────────┐
  │ 旧 Chunk 释放 → FreeSpaceBitSet  │
  │ 空间可被新写入重用                 │
  └────────────────────────────────────┘
```
**图 5-18: 追踪 DELETE 标记到 compact 物理回收的时间线**
```text
  如图 5-19 所示，┌──────────────┬──────────────────────────┬────────────────────┐
  │              │  逻辑删除                │  物理删除           │
  ├──────────────┼──────────────────────────┼────────────────────┤
  │ 时机         │ MVMap.remove()          │ compact 阶段       │
  │ MVMap 查询   │ 不可见 (MVCC 过滤)      │ 不存在             │
  │ undo log    │ 记录 oldValue            │ 已清除             │
  │ 空间         │ 仍占用                   │ 释放               │
  │ 回滚         │ 可恢复                   │ 不可恢复           │
  └──────────────┴──────────────────────────┴────────────────────┘
```
**图 5-19: 对比逻辑删除与物理删除的可见性差异**

---

## 5.5 事务提交 (COMMIT)

### 5.5.1 流程图
```text
┌──────────────────────────────────────────────────────────────────┐
│  TransactionCommand.update()                                     │
│    → session.commit(false)                                       │
│      → SessionLocal.commit(boolean ddl)  [SessionLocal.java:686]│
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  SessionLocal.commit(boolean ddl):                               │
│                                                                  │
│  1. beforeCommitOrRollback()  ← 预处理                           │
│  2. hasTransaction() → true:                                     │
│     a. markUsedTablesAsUpdated()                                 │
│     b. transaction.commit()  ← 关键步骤                          │
│        └ Transaction.commit()  [Transaction.java]                │
│     c. markUsedTablesAsUpdated()                                 │
│     d. removeTemporaryLobs(true)                                 │
│     e. endTransaction()                                          │
│  3. 非 DDL: cleanTempTables(), analyzeTables()                   │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  TransactionStore.commit(Transaction t, boolean recovery)         │
│  [TransactionStore.java:579]                                     │
│                                                                  │
│  1. flipCommittingTransactionsBit(txId, true)                    │
│     └ CAS 更新 VersionedBitSet, 标记该事务"正在提交"             │
│                                                                  │
│  2. t.notifyAllWaitingTransactions()  ← 唤醒等待该事务的线程     │
│                                                                  │
│  3. markUndoLogAsCommitted(txId, version)                        │
│     └ 将 undo log map 名称从 ".undoLog.3" → ".undoLog-3"        │
│       (点号改为短横线, 持久化标记提交)                           │
│                                                                  │
│  4. 创建 CommitDecisionMaker                                     │
│                                                                  │
│  5. 遍历 undo log: while (cursor.hasNext())                      │
│     a. 读取 undoKey → Record(mapId, key, oldValue)              │
│     b. 打开目标 map: map = openMap(mapId)                       │
│     c. map.operate(key, null, commitDecisionMaker)               │
│        └ CommitDecisionMaker.decide()                           │
│          → 设置 VersionedValue.operationId = NO_OPERATION_ID     │
│          → oldValue 变成 committedValue                          │
│          → 事务内写入的 newValue 变成可读                        │
│                                                                  │
│  6. undoLog.clear()  ← 清除 undo log                            │
│                                                                  │
│  7. flipCommittingTransactionsBit(txId, false)                   │
│     └ 清除"提交中"标记                                           │
└──────────────────────────────────────────────────────────────────┘
```
```text
  如图 5-20 所示，┌────────────────────────────────────────────────────────────┐
  │  Session Layer: SessionLocal.commit()                     │
  │  ┌──────────────────────────────────────────────────────┐ │
  │  │ beforeCommitOrRollback()                             │ │
  │  │ markUsedTablesAsUpdated()                            │ │
  │  │ transaction.commit() → Transaction.java              │ │
  │  │ removeTemporaryLobs()                                │ │
  │  │ endTransaction()                                     │ │
  │  │ 非 DDL: cleanTempTables + analyzeTables              │ │
  │  └──────────────────────────────────────────────────────┘ │
  └──────────────────────────┬─────────────────────────────────┘
                             │ delegate
                             ▼
  ┌────────────────────────────────────────────────────────────┐
  │  Transaction Layer: TransactionStore.commit()              │
  │  ┌──────────────────────────────────────────────────────┐ │
  │  │ flipCommittingTransactionsBit(bit, true)             │ │
  │  │ notifyAllWaitingTransactions()                       │ │
  │  │ markUndoLogAsCommitted()                             │ │
  │  │ iterate undoLog → CommitDecisionMaker                │ │
  │  │ undoLog.clear()                                      │ │
  │  │ flipCommittingTransactionsBit(bit, false)            │ │
  │  └──────────────────────────────────────────────────────┘ │
  └────────────────────────────────────────────────────────────┘
```
**图 5-20: 梳理 COMMIT 会话层与事务层的三阶段**

### 5.5.2 核心逻辑阐述
COMMIT 流程从 SessionLocal.commit() 发起，经 Transaction 层委派到 TransactionStore.commit()，核心分为三个阶段。标记阶段：将事务 ID 在 VersionedBitSet 中标记为"正在提交"(flipCommittingTransactionsBit)，同时唤醒等待该事务的等待队列，确保并发提交的顺序性。应用阶段：遍历 undo log 中的每一条变更记录，通过 CommitDecisionMaker 将 VersionedValue.operationId 清零（设为 NO_OPERATION_ID），使当前事务写入的新值对所有事务可见——此即 MVCC 中"提交即可见"的实现。清理阶段：清除 undo log 内容并从 committing 位图中移除标记。整个流程不涉及磁盘刷写（由独立 checkpoint 负责），保证 COMMIT 操作的高效性。

#### 5.5.2.1 VersionedValue 提交前后状态
```text
提交前:
  VersionedValue {
    operationId = (3 << 40) | 5  (事务3, logId 5)
    committedValue = "old_value"
    currentValue  = "new_value"
  }

提交中 (CommitDecisionMaker.apply):
  VersionedValue {
    operationId = NO_OPERATION_ID  (← 清除)
    committedValue = "new_value"   (← oldValue → newValue)
    currentValue  = "new_value"
  }

提交后:
  其他事务读取时, operationId == NO_OPERATION_ID
  → 直接返回 currentValue
```
```text
  如图 5-21 所示，状态 A (事务中, 未提交)
  ┌──────────────────────────────────┐
  │ operationId = (tx<<40)|logId    │ ← 标识修改者
  │ committedValue = "old_value"    │ ← 全局已提交版本
  │ currentValue  = "new_value"     │ ← 本事务写入
  └──────────────┬───────────────────┘
                 │ 提交
                 ▼
  状态 B (已提交)
  ┌──────────────────────────────────┐
  │ operationId = NO_OPERATION_ID   │ ← 已清除
  │ committedValue = "new_value"    │ ← old→new 已提升
  │ currentValue  = "new_value"     │ ← 未变
  └──────────────────────────────────┘
                 │ 其他事务读取
                 ▼
  状态 C (读取时)
  → operationId == NO_OP → 直接返回 currentValue
```
**图 5-21: 追踪 VersionedValue 提交前后三种状态的变迁**
```text
  如图 5-22 所示，读事务 Tx2 读取 key=1 的数据:
  ┌────────────────────────────────────────────┐
  │ VersionedValue {                           │
  │   operationId = (Tx1<<40)|0               │
  │   committedValue = "old"                   │
  │   currentValue = "new"                     │
  │ }                                          │
  │                                            │
  │ 规则:                                      │
  │ Tx2 检查 operationId:                      │
  │   ├─ NO_OPERATION_ID → currentValue (已提交)│
  │   ├─ Tx2 自己的 ID → currentValue (可见)   │
  │   ├─ 其他事务, not committing → committed  │
  │   └─ 其他事务, committing → currentValue   │
  └────────────────────────────────────────────┘
```
**图 5-22: 归纳 MVCC 读事务对四类 operationId 的处理**

### 5.5.3 关键代码引用
#### 5.5.3.1 CommitDecisionMaker 关键代码
```java
// CommitDecisionMaker.java:25
final class CommitDecisionMaker<V> extends MVMap.DecisionMaker<VersionedValue<V>> {
    public MVMap.Decision decide(CursorPos<...> tip, K key, VersionedValue<V> existingValue) {
        if (existingValue != null) {
            long opId = existingValue.getOperationId();
            if (TransactionStore.getTransactionId(opId) == transactionId) {
                // 撤销未提交的变更: 清除 operationId
                VersionedValue<V> cleared = new VersionedValue<>(...);
                decision = MVMap.Decision.PUT;
                return ...; // 替换为已提交版本
            }
        }
        decision = MVMap.Decision.ABORT; // 跳过
    }
}
```
```text
  如图 5-23 所示，CommitDecisionMaker.decide(existingValue)
       │
       ▼
  existingValue == null?
       │
       ├── YES → ABORT (不存在则跳过)
       │
       └── NO
             │
             ▼
  getTransactionId(opId) == transactionId?
       │
       ├── YES → 是当前事务的未提交变更
       │         │
       │         ├── 清除 operationId = NO_OP
       │         ├── PUT 替换为已提交版本
       │         └── 变更对新事务可见
       │
       └── NO → 其他事务的变更
                └── ABORT (跳过, 不处理)
```
**图 5-23: 拆解 CommitDecisionMaker 的决策分支**
```text
  如图 5-24 所示，遍历 undo log:
  ┌─────────────────────────────────────────────┐
  │ for each Record(mapId, key, oldValue):      │
  │   map = openMap(mapId)                      │
  │   map.operate(key, null, cdm)               │
  │     └─ cdm.decide():                        │
  │           if (my txId) → PUT(清除 opId)     │
  │           else → ABORT                      │
  └─────────────────────────────────────────────┘
  效果:
  原: operationId=(3<<40)|5, committed="A", current="B"
  提交后: operationId=NO_OP, committed="B", current="B"
  → 所有事务都能读到 B
```
**图 5-24: 追踪 CDM 清除 operationId 的执行步骤**

---

## 5.6 事务回滚 (ROLLBACK)

### 5.6.1 流程图
```text
┌──────────────────────────────────────────────────────────────────┐
│  TransactionCommand.update() → session.rollback()                │
│    → SessionLocal.rollback()  [SessionLocal.java:815]           │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  SessionLocal.rollback():                                        │
│  1. beforeCommitOrRollback()                                     │
│  2. if (hasTransaction()): rollbackTo(null)                     │
│     └ → 回滚所有变更 (savepoint = null → logIndex = 0)          │
│  3. idsToRelease = null                                          │
│  4. cleanTempTables(false)                                       │
│  5. endTransaction()                                             │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Transaction.rollback()  [Transaction.java:561]                  │
│                                                                  │
│  1. markTransactionEnd()                                         │
│  2. setStatus(STATUS_ROLLED_BACK)  ← 标记事务状态                │
│  3. if (logId > 0): 存在需要回滚的变更:                         │
│     store.rollbackTo(this, logId, 0)                             │
│     └ TransactionStore.rollbackTo(t, maxLogId, toLogId)          │
│       [TransactionStore.java:824]                                │
│  4. close(hasChanges, ex)  ← 关闭事务                           │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  TransactionStore.rollbackTo(Transaction t, maxLogId, toLogId)   │
│  [TransactionStore.java:824-833]                                 │
│                                                                  │
│  // 逆序遍历 undo log (从最新到最旧)                             │
│  for (long logId = maxLogId - 1; logId >= toLogId; logId--) {   │
│      Long undoKey = getOperationId(transactionId, logId);       │
│      undoLog.operate(undoKey, null, decisionMaker);             │
│  }                                                               │
│                                                                  │
│  RollbackDecisionMaker.decide()  [RollbackDecisionMaker.java:35]│
│                                                                  │
│  对每条 undo log 记录:                                           │
│  1. 读取 Record(mapId, key, oldValue)                            │
│  2. 打开目标 map: map = store.openMap(mapId)                    │
│  3. 检查 oldValue:                                              │
│     └ if oldValue == null: map.operate(key, null, REMOVE)       │
│                          ← 原为 INSERT: 删除                     │
│     └ else: map.operate(key, oldValue, PUT)                      │
│                          ← 原为 UPDATE: 恢复旧值                  │
│  4. 从 undo log 中删除该条目                                     │
└──────────────────────────────────────────────────────────────────┘
```
```text
  如图 5-25 所示，┌────────────────────────────────────────────────────────────┐
  │  Session Layer: SessionLocal.rollback()                   │
  │  ┌──────────────────────────────────────────────────────┐ │
  │  │ beforeCommitOrRollback()                             │ │
  │  │ rollbackTo(null) ← 回滚全部                         │ │
  │  │ cleanTempTables(false)                               │ │
  │  │ endTransaction()                                     │ │
  │  └──────────────────────────────────────────────────────┘ │
  └──────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────────┐
  │  Transaction Layer: Transaction.rollback()                 │
  │  ┌──────────────────────────────────────────────────────┐ │
  │  │ markTransactionEnd()                                 │ │
  │  │ setStatus(ROLLED_BACK)                               │ │
  │  │ store.rollbackTo(this, maxLogId, 0)                  │ │
  │  │ close(hasChanges)                                    │ │
  │  └──────────────────────────────────────────────────────┘ │
  └──────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────────┐
  │  Undo Layer: TransactionStore.rollbackTo()                 │
  │  ┌──────────────────────────────────────────────────────┐ │
  │  │ 逆序遍历 undoLog: maxLogId-1 → 0                     │ │
  │  │ 对每条: 恢复 oldValue 或 REMOVE                      │ │
  │  │ 删除 undo log 条目                                   │ │
  │  └──────────────────────────────────────────────────────┘ │
  └────────────────────────────────────────────────────────────┘
```
**图 5-25: 梳理 ROLLBACK 会话、事务与 Undo 三阶段处理**
```text
  恢复前:
  ┌────────────────────────────────────────────┐
  │ 旧值 = null (原 INSERT)                    │
  │ → map.operate(key, null, REMOVE)          │
  │ → 删除此行                                 │
  └────────────────────────────────────────────┘

  或:
  ┌────────────────────────────────────────────┐
  │ 旧值 = "old_value" (原 UPDATE)             │
  │ → map.operate(key, oldValue, PUT)         │
  │ → 恢复为旧值                               │
  └────────────────────────────────────────────┘

  如图 5-26 所示，示例:
  INSERT x=1 → undo: oldValue=null → REMOVE x
  UPDATE x=1→2 → undo: oldValue=1 → PUT x=1
```
**图 5-26: 对比 rollbackTo 两种 undo 的恢复方式**

### 5.6.2 核心逻辑阐述

```text
本节速览：5.6.2 核心逻辑阐述

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

ROLLBACK 流程与 COMMIT 对称但方向相反，其核心逻辑是从 undo log 中逆序遍历变更记录，逐条恢复旧值。入口为 SessionLocal.rollback()，经 Transaction.rollback() 委派到 TransactionStore.rollbackTo()。关键操作分两步：状态标记 — 将事务状态设为 STATUS_ROLLED_BACK，阻止后续读取；数据恢复 — 从最新 logId 到最旧反向遍历 undo log，对每条记录判断：若 oldValue 为 null 说明是 INSERT，执行 REMOVE 删除此行；若 oldValue 非 null 说明是 UPDATE，执行 PUT 恢复旧值。这种逆序恢复的设计保证了依赖顺序的正确性——先恢复最新变更，避免中间状态的引用冲突。

### 5.6.3 关键代码引用
#### 5.6.3.1 RollbackDecisionMaker 关键代码
```java
// RollbackDecisionMaker.java:34-48
public MVMap.Decision decide(Record existingValue, Record providedValue) {
    if (existingValue == null) {
        decision = MVMap.Decision.ABORT; // 保护性中止
    } else {
        VersionedValue<Object> valueToRestore = existingValue.oldValue;
        long operationId;
        if (valueToRestore == null ||
                (operationId = valueToRestore.getOperationId()) == NO_OPERATION_ID ||
                TransactionStore.getTransactionId(operationId) == transactionId
                        && TransactionStore.getLogId(operationId) < toLogId) {
            int mapId = existingValue.mapId;
            // 执行实际恢复: PUT oldValue 或 REMOVE
        }
    }
}
```
```text
  如图 5-27 所示，RollbackDecisionMaker.decide(existingValue)
       │
       ▼
  existingValue == null?
       │
       ├── YES → ABORT (没有 undo 记录, 跳过)
       │
       └── NO
             │
             ▼
  valueToRestore = existingValue.oldValue
       │
       ├── valueToRestore == null?
       │     ├── YES → oldValue 为空 = 原 INSERT
       │     │         → 执行 REMOVE (删除此行)
       │     │
       │     └── NO
       │           │
       │           ▼
       │    operationId == NO_OP 或 属于当前事务?
       │           │
       │           ├── YES → 执行 PUT(oldValue)
       │           │         恢复原始值
       │           │
       │           └── NO → ABORT
       │                    (属于其他已提交事务)
       │
       └── 执行实际的 map.operate()
```
**图 5-27: 拆解 RollbackDecisionMaker 的恢复分支**
```text
  正向遍历 (COMMIT):
  logId: 0 → 1 → 2 → ... → N
  使每个变更可见

  逆向遍历 (ROLLBACK):
  logId: N → ... → 2 → 1 → 0
  恢复每个旧值

  如图 5-28 所示，原因:
  回滚时先回滚最新操作, 避免依赖冲突
  例: INSERT x=1, UPDATE x=2
  回滚: 先恢复 x=2→1, 再删除 x (依赖正确的最终状态)
```
**图 5-28: 对比 COMMIT 与 ROLLBACK 的遍历方向**

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#transactions`)
> 描述了 TransactionStore 的事务机制：使用单独 map 存储旧版本，支持 savepoint 和两阶段提交。

---

## 5.7 空间整理 (Compaction)

### 5.7.1 流程图
```text
┌──────────────────────────────────────────────────────────────────┐
│  触发条件:                                                       │
│  ├ 后台线程: MVStore.writeBackground() → compact()              │
│  │  [MVStore.java:1112]                                         │
│  ├ 文件填充率低于阈值: autoCompactFillRate (默认 50%)           │
│  └ 主动调用: MVStore.compact()                                  │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  MVStore.compact()                                              │
│    → fileStore.compactStore(maxCompactTime)                     │
│      [FileStore.java:912]                                       │
│        → compactStore(autoCompactFillRate, maxCompactTime, ...) │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  RandomAccessStore.compactStore()  [RandomAccessStore.java:440] │
│                                                                  │
│  // 两阶段压缩                                                   │
│  setRetentionTime(0);   ← 不保留旧版本                           │
│  while (compact(thresholdFillRate, maxWriteSize)) {              │
│      sync();                                                     │
│      compactMoveChunks(thresholdFillRate, maxWriteSize, mvStore);│
│      if (超时) break;                                            │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│ Phase 1: compact()   │   │ Phase 2: compactMoveChunks()│
│                      │   │                              │
│ 1. 识别低填充率 Chunk │   │ 1. 识别文件前部可移动 Chunk  │
│ 2. 复制存活 page     │   │ 2. 按优先级排序              │
│ 3. 写入新 Chunk      │   │ 3. 重写到文件尾部            │
│ 4. 释放旧 Chunk      │   │ 4. 释放旧空间                │
│ 5. 更新 FreeSpaceBit │   │ 5. truncate() 缩短文件       │
└──────────────────────┘   └──────────────────────────────┘
```
```text
  如图 5-29 所示，MVStore 后台线程
       │
       ▼
  writeBackground()
       │
       ├── 是否需要 compact?
       │   ├── autoCompactFillRate (默认 50%)
       │   ├── 文件填充率 < 阈值
       │   └── Chunk 层碎片化
       │
       └── compact()
             │
             ▼
       fileStore.compactStore(maxCompactTime)
             │
             ▼
       RandomAccessStore.compactStore()
             │
             ├── Phase 1: compact()
             │     └── rewrite 低填充率 Chunk
             │
             └── Phase 2: compactMoveChunks()
                   └── 移动 Chunk 到文件尾 + truncate
```

下面 7 张图共同呈现 Compaction 的完整脉络：图 5-29 拆解后台线程的判断分支，图 5-30 与图 5-31 演示填充率计算与四档动作，图 5-50 与图 5-49 给出选择顺序与类继承层级，图 5-32 与图 5-51 收尾于源码调用链与 compact 前后指标对比。

**图 5-29: 拆解后台线程触发 compact 的判断分支**

### 5.7.2 核心逻辑阐述
空间整理 (Compaction) 的核心目标是回收碎片空间、降低文件大小，分为两阶段执行。Phase 1 (compact)：扫描所有 Chunk，识别填充率低于阈值的低效 Chunk，将其中的存活 page 复制到新 Chunk 后释放旧 Chunk 空间。Phase 2 (compactMoveChunks)：扫描文件头部区域的碎片化空间，将散落的 Chunk 按优先级排序并重写到文件尾部，最后通过 truncate 缩短文件。填充率计算由 FreeSpaceBitSet 基于位图实现：`fillRate = (usedBlocks * 100) / totalBlocks`，低于 autoCompactFillRate (默认 50%) 即触发整理。后台线程 writeBackground() 周期性地通过 doHousekeeping() 执行此流程。

#### 5.7.2.1 FreeSpaceBitSet 填充率计算
```java
// FreeSpaceBitSet.java:222
int getFillRate() {
    int usedBlocks = set.cardinality() - firstFreeBlock;
    int totalBlocks = set.length() - firstFreeBlock;
    return totalBlocks == 0 ? 0 : (int)((100L * usedBlocks + totalBlocks - 1) / totalBlocks);
}
```
```text
  Bitset: [1][1][0][1][1][0][0][1][0][0] ...
           ↑                          ↑
     firstFreeBlock              set.length()

  usedBlocks = cardinality - firstFreeBlock
             = (1+1+0+1+1+0+0+1) - position(firstFreeBlock)
             = 5 - 1 = 4

  totalBlocks = set.length - firstFreeBlock
              = 10 - 1 = 9

  如图 5-30 所示，fillRate = (4 * 100 + 9 - 1) / 9 = 44%
  → 填充率 44%, 低于阈值 → 触发 compact
```
**图 5-30: 演示 FreeSpaceBitSet 计算填充率的位图字段**
```text
  填充率区间        操作
  ──────────── ────────────────────
  0% - 30%    紧急 compact (重写率最高)
  30% - 50%   触发 compact (autoCompactFillRate)
  50% - 80%   不触发 (空间利用可接受)
  80% - 100%  良好 (无需干预)

  如图 5-31 所示，示例:
  ┌─────┬─────┬─────┬─────┬─────┬─────┐
  │ 90% │ 30% │ 85% │ 20% │ 70% │ 40% │ ← 各 Chunk 填充率
  └─────┴─────┴─────┴─────┴─────┴─────┘
    ↑        ↑           ↑
  保留     compact     compact
```
**图 5-31: 归纳 Chunk 填充率四档对应的压缩动作**
```text
  文件中的连续 Chunk 及其填充率:

  ┌──────────┬──────────┬──────────┬──────────┬──────────┐
  │ Chunk 0  │ Chunk 1  │ Chunk 2  │ Chunk 3  │ Chunk 4  │
  │ 填充 20% │ 填充 90% │ 填充 85% │ 填充 30% │ 填充 45% │
  └─────┬────┴─────┬────┴─────┬────┴─────┬────┴─────┬────┘
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
  │compact │ │保留    │ │保留    │ │compact │ │compact │
  │优先!   │ │(高填充)│ │(高填充)│ │(低填充)│ │(中填充)│
  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘

  如图 5-50 所示，compact 顺序: 按填充率升序
  Chunk 0(20%) → Chunk 3(30%) → Chunk 4(45%)
  (最低填充率优先, 最大空间回收效率)
```
**图 5-50: 归纳 Chunk 按填充率升序选择 compact 的顺序**

### 5.7.3 关键代码引用
| 文件 | 行号 | 方法 |
|------|------|------|
| `MVStore.java` | 1112 | `compact()` |
| `FileStore.java` | 912 | `compactStore()` |
| `RandomAccessStore.java` | 440 | `compactStore()` |
| `RandomAccessStore.java` | 463 | `compactMoveChunks()` |
| `RandomAccessStore.java` | 479 | `compactMoveChunks(long)` |
| `RandomAccessStore.java` | 487 | `findChunksToMove()` |
| `RandomAccessStore.java` | 529 | `compactMoveChunks(Iterable)` |
| `FreeSpaceBitSet.java` | 222 | `getFillRate()` |

```text
  如图 5-49 所示，MVStore
    │ 包含
    └── FileStore
          │ 抽象基类, 提供 compactStore() 接口
          │
          ├── RandomAccessStore
          │     ├── compactStore() [440] ← 主入口
          │     ├── compact()      ← Phase 1
          │     ├── compactMoveChunks() [463] ← Phase 2
          │     │     ├── findChunksToMove() [487]
          │     │     └── compactMoveChunks(Iter) [529]
          │     └── doHousekeeping() [720] ← 后台
          │
          └── FreeSpaceBitSet
                └── getFillRate() [222] ← 填充率计算
```
**图 5-49: 梳理 Compaction 相关类的继承层级**
```text
  如图 5-32 所示，MVStore.java:1112 (compact)
       │
       ▼
  FileStore.java:912 (compactStore)
       │
       ▼
  RandomAccessStore.java:440 (compactStore)
       │
       ├── 463 (compactMoveChunks)
       │     ├── 479 (compactMoveChunks long)
       │     └── 487 (findChunksToMove)
       │           └── 529 (compactMoveChunks Iterable)
       │
       └── FreeSpaceBitSet.java:222 (getFillRate)
             └── 填充率计算 → 决定是否 compact
```
**图 5-32: 梳理 Compaction 涉及的源码调用链**

#### 5.7.3.1 文件空间布局示意图
```text
压缩前:
┌────────┬────────┬────────┬────────┬────────┬────────┐
│ Chunk1 │  空    │ Chunk2 │  空   │ Chunk3 │  空    │
│ (30%)  │        │ (40%)  │       │ (90%)  │        │
└────────┴────────┴────────┴────────┴────────┴────────┘

Phase 1: compact() — 重写低填充率 Chunk
┌────────┬────────┬────────┬────────┬────────┬────────┐
│ Chunk1 │  空    │ Chunk2 │  空   │ Chunk3 │Chunk4  │
│ (已清) │        │ (已清) │       │ (90%)  │(Ch1+2) │
└────────┴────────┴────────┴────────┴────────┴────────┘

Phase 2: compactMoveChunks() — 合并 + truncate
┌────────┬────────┐
│ Chunk3 │ Chunk4 │
│ (90%)  │ (重构) │
└────────┴────────┘
```
```text
  如图 5-51 所示，compact 前:
  ┌──────────────────────────────────────────────┐
  │  文件大小: 100 MB                            │
  │  存活数据: 45 MB                             │
  │  填充率: 45%  (低于阈值, 触发 compact)      │
  │  碎片率: 30%                                 │
  └──────────────────────────────────────────────┘
       │
       ▼ compact
  ┌──────────────────────────────────────────────┐
  │  文件大小: 50 MB                             │
  │  存活数据: 45 MB                             │
  │  填充率: 90%                                 │
  │  碎片率: 5%                                  │
  │  truncate 节省: 50 MB                        │
  └──────────────────────────────────────────────┘
```
**图 5-51: 对比 compact 前后文件大小与填充率指标**

---

## 5.8 Chunk 压缩整理流程

### 5.8.1 流程图
```text
Step 1: 识别死 Chunk
  └ chunk.pageCountLive == 0 → 该 Chunk 所有 page 都已删除
  └ 直接释放空间到 FreeSpaceBitSet

Step 2: 识别部分死亡 Chunk
  └ 0 < chunk.pageCountLive < chunk.pageCount
  └ 需要将存活 page 复制到新 Chunk

Step 3: 计算压缩优先级
  └ collectPriority = f(填充率, Chunk 大小, 位置)
  └ 低填充率 + 大 Chunk = 高优先级

Step 4: 重写存活 page
  └ for each selected Chunk:
    for each live page:
      copy page content to new Chunk
      update MVMap root reference
  └ 释放旧 Chunk 空间

Step 5: 移动 Chunk (compactMoveChunks)
  └ 扫描文件从 firstFreeBlock 开始
  └ findChunksToMove(startBlock, maxBlocksToMove)
    └ 优先选择 collectPriority 高的 Chunk
    └ 受 maxWriteSize 限制
  └ 重写选中 Chunk 到文件尾部
  └ 释放原位置空间

Step 6: 截断文件
  └ getFileLengthInUse() → 计算实际使用长度
  └ truncate(end) → 缩短文件
```
```text
  如图 5-33 所示，┌─────────────────────────────────────────────┐
  │ Step 1: 识别死 Chunk                        │
  │   pageCountLive == 0 → 直接释放             │
  └──────────────────┬──────────────────────────┘
                     ▼
  ┌─────────────────────────────────────────────┐
  │ Step 2: 识别部分死亡 Chunk                  │
  │   0 < live < total → 需要重写               │
  └──────────────────┬──────────────────────────┘
                     ▼
  ┌─────────────────────────────────────────────┐
  │ Step 3: 计算压缩优先级                       │
  │   f(填充率, 大小, 位置)                     │
  └──────────────────┬──────────────────────────┘
                     ▼
  ┌─────────────────────────────────────────────┐
  │ Step 4: 重写存活 page → 新 Chunk           │
  └──────────────────┬──────────────────────────┘
                     ▼
  ┌─────────────────────────────────────────────┐
  │ Step 5: compactMoveChunks                   │
  │   移动碎片到文件尾                          │
  └──────────────────┬──────────────────────────┘
                     ▼
  ┌─────────────────────────────────────────────┐
  │ Step 6: truncate 缩短文件                   │
  └─────────────────────────────────────────────┘
```
**图 5-33: 概览 Chunk 从识别到 truncate 的六步流程**
```text
  低填充率 + 大 Chunk = 高优先级
  ┌─────┬──────┬──────────┬────────┐
  │Chunk│填充率 │ 大小(MB) │优先级  │
  ├─────┼──────┼──────────┼────────┤
  │  A  │ 20%  │  100     │ 高 ⬆  │
  │  B  │ 30%  │   50     │ 中    │
  │  C  │ 45%  │   30     │ 低    │
  │  D  │ 90%  │   10     │ 不压缩 │
  └─────┴──────┴──────────┴────────┘

  如图 5-34 所示，collectPriority = f(填充率, 大小, 位置)
  权重: 填充率(40%) + 大小(35%) + 位置(25%)
```
**图 5-34: 对比 Chunk 在不同填充率与大小下的优先级**

### 5.8.2 核心逻辑阐述

```text
本节速览：5.8.2 核心逻辑阐述

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

Chunk 压缩整理是 MVStore 在 Chunk 层面执行的碎片回收流程，与 5.7 节的全局空间整理 (Compaction) 协同工作。核心流程分六步：识别完全死亡 Chunk (pageCountLive == 0) 直接释放空间；识别部分死亡 Chunk (0 < 存活 < 总数) 需重写；按 collectPriority 函数（基于填充率、大小、位置三因子加权）计算压缩优先级；将存活 page 复制到新 Chunk 并更新 MVMap root reference；通过 compactMoveChunks 将文件头部的碎片 Chunk 移动到文件尾部；最后 truncate 截断文件回收空间。doHousekeeping() 后台线程周期执行此流程，关键判断条件为 isFragmented() 与 fillRate 阈值组合。

### 5.8.3 关键代码引用
#### 5.8.3.1 后台自动整理 (doHousekeeping)
```java
// RandomAccessStore.java:720
protected void doHousekeeping(MVStore mvStore) throws InterruptedException {
    int fileFillRate = getFillRate();
    int chunksFillRate = getChunksFillRate();
    // 文件碎片化且填充率低 → 移动 chunk
    if (isFragmented() && fileFillRate < getAutoCompactFillRate()) {
        compactMoveChunks(101, moveSize, mvStore);
    }
    // chunk 填充率低 → 重写 chunk
    if (fillRateToCompare < getTargetFillRate(idle)) {
        rewriteChunks(writeLimit, targetFillRate);
        dropUnusedChunks();
    }
}
```
```text
  如图 5-35 所示，doHousekeeping()
       │
       ▼
  fileFillRate = getFillRate()
  chunksFillRate = getChunksFillRate()
       │
       ├── isFragmented() && fileFillRate < autoCompactFillRate?
       │     │
       │     ├── YES → compactMoveChunks(101, moveSize)
       │     │          移动碎片 Chunk 到文件尾部
       │     │
       │     └── NO → 跳过 (无碎片)
       │
       └── fillRateToCompare < getTargetFillRate(idle)?
             │
             ├── YES → rewriteChunks(writeLimit, targetFillRate)
             │         └→ 重写低填充率 Chunk
             │         └→ dropUnusedChunks()
             │
             └── NO → 跳过 (填充率充足)
```
**图 5-35: 拆解 doHousekeeping 两类策略的判断分支**
```text
  ┌──────────────────┬─────────────────────┬────────────────────┐
  │ 策略             │ 条件                │ 操作               │
  ├──────────────────┼─────────────────────┼────────────────────┤
  │ compactMoveChunks│ 文件碎片化          │ 移动 Chunk 到      │
  │                  │ + 文件填充率低      │ 文件尾部, truncate│
  ├──────────────────┼─────────────────────┼────────────────────┤
  │ rewriteChunks    │ Chunk 填充率低      │ 重写低填充率       │
  │                  │                     │ Chunk, 释放旧空间  │
  └──────────────────┴─────────────────────┴────────────────────┘

  如图 5-36 所示，文件碎片化 = 文件中有大量空洞 (free blocks 分散)
  Chunk 填充率低 = Chunk 内 page 利用率低
```
**图 5-36: 对比移动 Chunk 与重写 Chunk 的处理策略**

---

## 5.9 数据读取流程

### 5.9.1 流程图
```text
TransactionMap.get(key)
  [TransactionMap.java:511-520]
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  useSnapshot()  [TransactionMap.java:560]                       │
│                                                                  │
│  // 获取一致的 (RootReference + committingTransactions) 快照     │
│  // 自旋等待直到两个变量的读取一致                              │
│                                                                  │
│  while (true) {                                                  │
│      VersionedBitSet prev = committingTransactions;             │
│      RootReference root = map.getRoot();                         │
│      committingTransactions = holder.get();                      │
│      if (committingTransactions == prev) {                       │
│          return snapshotConsumer.apply(root, ct.bits);          │
│      }                                                           │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  getFromSnapshot(rootRef, committingTransactions, key)           │
│  [TransactionMap.java:493]                                       │
│                                                                  │
│  1. VersionedValue data = map.get(root, key)  ← B-Tree 查找     │
│     └ MVMap.get() → Page.get() → 二分查找降序到叶子节点          │
│                                                                  │
│  2. if (data == null) → return null  (键不存在)                  │
│                                                                  │
│  3. long id = data.getOperationId()                              │
│     if (id == NO_OPERATION_ID) → return data.getCurrentValue()   │
│     └ 已提交: 直接返回当前值                                      │
│                                                                  │
│  4. int tx = TransactionStore.getTransactionId(id)               │
│     if (tx == this.transaction.transactionId)                    │
│       → return data.getCurrentValue()  ← 自己修改的: 可见        │
│                                                                  │
│  5. if (!BitSetHelper.get(committingTransactions, tx))           │
│       → return data.getCommittedValue()  ← 其他事务未提交: 不可见│
│                                                                  │
│  6. return data.getCurrentValue()  ← 已提交: 可见               │
└──────────────────────────────────────────────────────────────────┘
```
```text
  如图 5-37 所示，TransactionMap.get(key)
       │
       ▼
  ┌──────────────────────────────────┐
  │ useSnapshot()                    │
  │ 自旋: 获取一致的 (root + CT)    │
  └──────────────┬───────────────────┘
                 ▼
  ┌──────────────────────────────────┐
  │ getFromSnapshot(root, CT, key)  │
  │   data = map.get(root, key)     │
  │   → B-Tree 二分查找             │
  └──────────────┬───────────────────┘
                 ▼
  ┌──────────────────────────────────┐
  │ data == null?                    │
  │   YES → return null (键不存在)  │
  │   NO  → 检查 operationId        │
  └──────────────┬───────────────────┘
                 ▼
       ┌── NO_OPERATION_ID ──┐
       │ return currentValue  │
       └──────────────────────┘
       │ 是自己的事务?
       ├─ YES → return currentValue
       │
       │ 其他事务 in committing?
       ├─ NO  → return committedValue
       │
       └─ YES → return currentValue
```
**图 5-37: 追踪 TransactionMap 读取的可见性判断步骤**
```text
  场景: 并发提交导致 root 和 committingTransactions 不一致

  线程 A (读):                   线程 B (提交):
  ──────────────────             ──────────────────
  prevCT = CT (v1)
                                 CT ← flipBit (v2)
  root = getRoot() (v2)
                                 CT ← flipBit (v3)
  curCT = CT (v3)
  prevCT != curCT → 重试!

  如图 5-38 所示，重试:
  prevCT = CT (v3)
  root = getRoot() (v3)
  curCT = CT (v3)
  prevCT == curCT → 一致! 返回
```
**图 5-38: 演示 useSnapshot 自旋至两次读取一致**

### 5.9.2 核心逻辑阐述
数据读取流程从 TransactionMap.get(key) 入口，核心在于 MVCC 可见性判断与 B-Tree 索引查找的协同。流程分四步：快照获取 — useSnapshot() 通过自旋等待获得一致的 (RootReference, committingTransactions) 快照，保证读取时点的一致性；B-Tree 查找 — MVMap.get(root, key) 通过 Page.get() 在 B-Tree 中执行二分查找降序到叶子节点；可见性判断 — 对返回的 VersionedValue 检查 operationId，NO_OPERATION_ID 直接返回 currentValue（已提交），属于当前事务则返回 currentValue（自身修改可见），其他事务未提交则返回 committedValue（隐藏未提交变更）；结果返回 — 主索引直接返回行数据，二级索引需额外回表查询主索引。

#### 5.9.2.1 可见性决策表
| condition | 返回 | 含义 |
|-----------|------|------|
| data == null | null | 键不存在 |
| operationId == NO_OPERATION_ID | currentValue | 已提交版本 |
| getTransactionId(opId) == 当前事务 | currentValue | 自身未提交变更 |
| 其他事务且 not committing | committedValue | 其他事务未提交，不可见 |
| 其他事务且 committing | currentValue | 其他事务已提交（或正在提交） |

```text
  如图 5-39 所示，data = map.get(key)
       │
       ▼
  ┌─────────────────────────────────────┐
  │ data == null?                       │
  │ YES → null (键不存在)               │
  └──────────────┬──────────────────────┘
                 │ NO
                 ▼
  ┌─────────────────────────────────────┐
  │ operationId == NO_OP?               │
  │ YES → currentValue (已提交)          │
  └──────────────┬──────────────────────┘
                 │ NO
                 ▼
  ┌─────────────────────────────────────┐
  │ 属于当前事务?                       │
  │ YES → currentValue (自身修改可见)    │
  └──────────────┬──────────────────────┘
                 │ NO
                 ▼
  ┌─────────────────────────────────────┐
  │ 其他事务, in committing?           │
  │ YES → currentValue (已提交)         │
  │ NO  → committedValue (未提交, 隐藏)│
  └─────────────────────────────────────┘
```
**图 5-39: 拆解 MVCC 可见性判断的五级分支**
```text
  事务 Tx1:                      事务 Tx2:
  UPDATE t SET x=2                SELECT x FROM t
  (未提交)                           │
       │                             │
       ▼                             ▼
  ┌──────────────┐           ┌──────────────────┐
  │ x=2 (未提交) │           │ Tx2 读到 x=1     │
  │ currentValue │           │ (committedValue) │
  │ operationId  │           │ Tx1 未提交        │
  │ = (1<<40)|0  │           │ 对 Tx2 不可见    │
  └──────────────┘           └──────────────────┘

  如图 5-40 所示，Tx1 提交后:
  ┌──────────────┐           ┌──────────────────┐
  │ x=2 (已提交) │           │ Tx2 读到 x=2     │
  │ operationId  │           │ (currentValue)   │
  │ = NO_OP      │           │ 现在可见         │
  └──────────────┘           └──────────────────┘
```
**图 5-40: 演示读已提交隔离级别下的可见性变化**

### 5.9.3 关键代码引用
#### 5.9.3.1 MVMap.get() — B-Tree 读取路径
```text
MVMap.get(key)
  → get(root, key)
    → Page.get(key, ...)
      → binarySearch(keys, key)  ← 二分查找当前页
      → if 找到: return values[index]
      → if 叶子节点: return null (未找到)
      → else: 进入子节点递归查找

  Page 结构:
  ┌─────────────────────────────────┐
  │ Page<K,V>                       │
  │  keys: K[]                      │
  │  values: V[]  (叶子) /          │
  │  children: Page[]  (非叶子)     │
  │  mapRef: RootReference          │
  │  isLeaf: boolean                │
  └─────────────────────────────────┘
```
```text
  如图 5-41 所示，搜索 key=42:
  ┌─────────────────────────────────────────────┐
  │ 根 Page (内部节点):                         │
  │ keys=[10, 30, 50, 80]                       │
  │ children=[P0, P1, P2, P3, P4]              │
  │ binarySearch(42) → 插入位置在 30-50 之间    │
  │ → 进入 child[2]                             │
  └──────────────────┬──────────────────────────┘
                     ▼
  ┌─────────────────────────────────────────────┐
  │ 内部 Page:                                  │
  │ keys=[35, 40, 45]                           │
  │ children=[P0, P1, P2, P3]                   │
  │ binarySearch(42) → 插入位置在 40-45 之间    │
  │ → 进入 child[2]                             │
  └──────────────────┬──────────────────────────┘
                     ▼
  ┌─────────────────────────────────────────────┐
  │ 叶子 Page (键值存储):                       │
  │ keys=[41, 42, 43]                           │
  │ values=[v41, v42, v43]                      │
  │ binarySearch(42) → 找到 → return v42       │
  └─────────────────────────────────────────────┘
```
**图 5-41: 演示 B-Tree 二分查找定位 key=42 的路径**
```text
  如图 5-42 所示，┌─ RootReference ─────────────────────────────┐
  │  root: Page<K,V> (根)                      │
  │  version: long                             │
  └────────────────────────────────────────────┘
         │
         ▼
  ┌─ Internal Page ────────────────────────────┐
  │  keys: [10, 30, 50, 80]                   │
  │  children: [P0, P1, P2, P3, P4]           │
  │  mapRef → RootReference                   │
  │  isLeaf = false                           │
  └──────┬────────────────────────────────────┘
         │ child[2]
         ▼
  ┌─ Internal Page ────────────────────────────┐
  │  keys: [35, 40, 45]                       │
  │  children: [P0, P1, P2, P3]              │
  └──────┬────────────────────────────────────┘
         │ child[2]
         ▼
  ┌─ Leaf Page ───────────────────────────────┐
  │  keys: [41, 42, 43]                      │
  │  values: [v41, v42, v43]                 │
  │  isLeaf = true                            │
  └───────────────────────────────────────────┘
```
**图 5-42: 拆解 Page 三层结构的字段构成**

#### 5.9.3.2 读取完整调用链
```text
JdbcResultSet.next()
  → 遍历 ResultInterface
    → LocalResult.next()
      → 从内存结果中读取行
        → 数据已在 queryWithoutCache() 阶段从 MVStore 读取

TransactionMap.get(key)  [TransactionMap.java:511]
  → useSnapshot()            [TransactionMap.java:560]
  → getFromSnapshot()        [TransactionMap.java:493]
  → MVMap.get(root, key)     [MVMap.java]
  → Page.get(key)            [Page.java]
  → binarySearch + 递归下降到叶子节点

MVPrimaryIndex.find(session, searchRow)
  → dataMap.map.get(key)     ← 直接读取
  → dataMap.getFromSnapshot(key)  ← MVCC 可见性检查
```

MVSecondaryIndex.find(session, searchRow)
  → indexMap.map.get(key)    ← 二级索引读取
  → 获取主键后回表查询主索引
```text
  如图 5-43 所示，┌────────────────────────────────────────────┐
  │  JDBC 层                                  │
  │  JdbcResultSet.next()                     │
  └────────────────┬───────────────────────────┘
                   ▼
  ┌────────────────────────────────────────────┐
  │  Result 层                                │
  │  LocalResult.next()                       │
  │  (从内存结果读取)                          │
  └────────────────┬───────────────────────────┘
                   ▼
  ┌────────────────────────────────────────────┐
  │  TransactionMap 层 (MVCC)                 │
  │  TransactionMap.get(key)                  │
  │    ├ useSnapshot()                        │
  │    └ getFromSnapshot()                    │
  └────────────────┬───────────────────────────┘
                   ▼
  ┌────────────────────────────────────────────┐
  │  MVMap 层 (B-Tree)                        │
  │  MVMap.get(root, key)                     │
  │    └ Page.get(key) → 二分查找 + 递归       │
  └────────────────────────────────────────────┘
```
**图 5-43: 梳理 ResultSet 至 MVMap 的读取调用栈**
```text
  主索引读 (MVPrimaryIndex.find):
  ┌────────────────────────────────────────┐
  │ dataMap.map.get(key)                   │
  │   → TransactionMap.get(key)           │
  │     → useSnapshot()                   │
  │     → getFromSnapshot()               │
  │     → MVMap.get()                     │
  │     → 直接返回行数据                   │
  └────────────────────────────────────────┘

  如图 5-44 所示，二级索引读 (MVSecondaryIndex.find):
  ┌────────────────────────────────────────┐
  │ indexMap.map.get(key)                  │
  │   → 获取主键 (PK)                     │
  │   → 回表: primaryIndex.find(PK)       │
  │     → dataMap.map.get(PK)             │
  │     → MVCC 可见性检查                  │
  │     → 返回完整行数据                   │
  └────────────────────────────────────────┘
  二级索引需要回表, 比主索引多一次 B-Tree 查找
```
**图 5-44: 对比主索引与二级索引读取的回表差异**

#### 5.9.3.3 一致性快照读取

**源码位置**: `org/h2/mvstore/tx/TransactionMap.java:560`

```java
<R> R useSnapshot(BiFunction<RootReference<K,VersionedValue<V>>, long[], R> snapshotConsumer) {
    // 自旋直到获得一致的 (root + committingTransactions) 快照
    VersionedBitSet committingTransactions = holder.get();
    while (true) {
        VersionedBitSet prevCommittingTransactions = committingTransactions;
        RootReference<K,VersionedValue<V>> root = map.getRoot();
        committingTransactions = holder.get();
        if (committingTransactions == prevCommittingTransactions) {
            return snapshotConsumer.apply(root, committingTransactions.bits);
        }
    }
}
```
```text
  如图 5-45 所示，useSnapshot()
       │
       ▼
  ┌──────────────────────────────────────┐
  │ 初始: CT = holder.get()             │
  └──────────────┬───────────────────────┘
                 ▼
       ┌── 循环开始 ──┐
       │              │
       ▼              │
  ┌──────────────────────┐              │
  │ prevCT = CT         │              │
  │ root = getRoot()    │              │
  │ CT = holder.get()   │              │
  └──────────┬───────────┘              │
             │                          │
      prevCT == CT?                    │
       YES     NO                      │
         │      └──→ 回到循环开始 ──────┘
         ▼
  ┌──────────────────────┐
  │ 返回一致的快照       │
  │ (root, CT.bits)     │
  └──────────────────────┘
```
**图 5-45: 演示 useSnapshot 自旋等待一致快照的循环**
```text
  场景 1: 并发提交未干扰
  CT:   ──v1──────v1──────→ (无变化)
  root: ──r1──────r1──────→ (无变化)
  prevCT == CT → 一致, 返回 (r1, v1)

  场景 2: 提交恰好在两次读取之间
  CT:   ──v1──────v2──────→ (被修改)
  root: ──r1──────r2──────→ (被修改)
  prevCT(v1) != CT(v2) → 不一致, 重试

  场景 3: 重试后一致
  CT:   ──v1──v2──v2─────→ (稳定在 v2)
  root: ──r1──r2──r2─────→ (稳定在 r2)
  prevCT(v2) == CT(v2) → 一致, 返回 (r2, v2)
```
**图 5-46: 对比并发提交下三种快照一致性场景**



## 5.10 本章小结

如图 5-46 所示，本章追踪了 H2 中九个核心流程：SELECT/INSERT/UPDATE/DELETE 四大 SQL 操作、COMMIT/ROLLBACK 事务控制、Compaction 空间回收、Chunk 压缩整理以及数据读取流程。每个流程均按照"流程图→核心逻辑阐述→关键代码引用"的标准化模板展开，展示了 SQL 语句从解析到存储层的完整生命周期。

本章涉及的所有基础算法——B-Tree 查找插入、Copy-on-Write 版本管理、MVCC 可见性判断——将在第6章《H2 数据库核心算法分析》中深入展开。理解本章的流程有助于把握第6章各算法的应用场景。

## 5.11 延伸思考

下面 4 道自查题帮助读者把九个核心流程的状态机与不变量内化为可应用的判断力。

**1. 🟢★ 描述 INSERT 流程中 Undo Log 与 VersionedValue 的写入顺序，并解释为什么这一顺序对崩溃恢复至关重要。**

> 提示：从"先记录回滚信息，再发布新版本"这一通用规则出发；注意 commit 之前 VersionedValue 对其他事务尚不可见。
> 回顾：§5.2 INSERT 写入流程、§5.5 事务提交 (COMMIT)

**2. 🟢★ 比较 ROLLBACK 与 COMMIT 在状态机上的对称差异：两者从同一中间状态出发，最终如何走向相反的终态？**

> 提示：聚焦 Undo Log 的"回放方向"以及对 VersionedValue 中 committed 字段的处理；可画一个简单的状态迁移图。
> 回顾：§5.5 事务提交 (COMMIT)、§5.6 事务回滚 (ROLLBACK)

**3. 🔵★★ 若 Compaction 与 COMMIT 并发执行，哪些不变量必须由实现保护？请至少给出两条，并说明 H2 如何通过现有机制保证它们成立。**

> 提示：思考 Chunk 重写过程中"正在写入的版本"是否可被搬迁；关注根节点指针的发布点与可见性。
> 回顾：§5.5 事务提交 (COMMIT)、§5.7 空间整理 (Compaction)、§5.8 Chunk 压缩整理流程

**4. 🟠★★★ 在 H2 测试目录下编写一个用例，向数据文件目录所在磁盘注入"磁盘满"故障（可用 mock FileSystem 或预先填满的临时分区），观察 ROLLBACK 失败时 H2 进入的恢复路径，并记录最终落盘状态。**

> 提示：先定位 `org.h2.store.fs` 中的可注入接口，再结合 §5.6 的失败处理分支判断 H2 是抛异常还是把数据库标记为只读。
> 回顾：§5.6 事务回滚 (ROLLBACK)、§5.9 数据读取流程、第5章

## 5.12 延展阅读

- H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html`) — 事务隔离级别与 MVCC 行为详细说明
- H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#transactions`) — MVStore 事务机制
- 本书第7章《SQL 执行全流程》 — SELECT/INSERT/UPDATE/DELETE 的执行计划生成和执行
- 本书第9章《持久化引擎深度解析》 — COMMIT/ROLLBACK/COMPACT 的磁盘交互
- 本书第10章《锁与并发控制》 — 流程执行中的锁获取和释放


---

> 本文档基于 H2 Database 源码 (master branch, commit c39970fff) 撰写。
> 所有路径均相对于 `org/h2/`。
