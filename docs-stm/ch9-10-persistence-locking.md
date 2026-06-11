# 第9章 持久化引擎深度解析

> **本章导读**: 本章深入分析 H2 的 MVStore 持久化引擎，从总体架构、Chunk 文件布局、Page 格式到检查点机制和文件格式（File Header、Chunk、Page 三级二进制布局）。MVStore 是 H2 v2.0 重构的核心，理解本章内容对于掌握 H2 的性能特性和存储原理至关重要。
> **前置知识**: 第6章§6.1-6.3（B-Tree、Copy-on-Write、MVCC 基础）；第6章§6.4-6.7（Chunk/LIRS/FreeSpace/MVStore 平衡）；第5章§5.5-5.6（事务提交/回滚）
> **章节要点**:
> - 理解 MVStore 的日志结构存储架构
> - 掌握 Chunk 的格式、写入和回收生命周期
> - 熟悉 Page 的二进制格式和 64-bit Page Pointer 编码
> - 了解检查点和后台写入线程的触发机制
> - 掌握 MVStore 文件的三级布局（File Header/Chunk/Page）
> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

H2 Database 从 1.4.x 版本开始实验性支持 MVStore，在 v2.0 中取代 PageStore 成为默认存储引擎。MVStore 是一种 log-structured（日志结构）、append-only（仅追加写入）、基于 B-Tree 的键值存储系统。其设计思想受 RethinkDB 的存储引擎和经典的 LSM-Tree 启发，但与 LSM-Tree 不同的是，MVStore 不使用单独的写前日志（WAL），而是通过原子性的 chunk 写入和版本化的 B-Tree 根指针来实现崩溃安全和事务持久性。

本章内容与第6章《H2 数据库核心算法分析》中的 B-Tree 索引、Copy-on-Write 版本管理及 MVCC 多版本控制等算法紧密关联（详见第6章《H2 数据库核心算法分析》第6.1-6.3节）。同时，第5章第5.5节（事务提交/回滚流程）与本章的 Undo Log 机制直接相关（详见第5章《核心流程解读》第5.5-5.6节）。锁与并发控制部分可结合第7章§7.1.5 的 Session 锁机制与线程模型理解。

本章将深入剖析 MVStore 持久化引擎的架构设计与实现细节。9.1 概述 MVStore 的总体架构、生命周期和版本控制机制；9.2 详述 B-Tree 与 Page 的内部结构和序列化格式；9.3 解析 Chunk 的文件布局与空间分配策略；9.4 说明 Undo Log 机制及崩溃安全保障；9.5 介绍检查点触发逻辑与后台写入线程；9.6 详述 MVStore 的二进制文件格式（file header、chunk、page 三级的布局与编码）。第10章将在此基础上进一步讨论锁与并发控制机制。10.8 从 ACID 视角总结 H2 的事务保证。

## 9.1 MVStore 总体架构

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#overview`)
> 官方概述指出 MVStore 是"持久化、日志结构的键值存储"，支持并发读写和事务。

MVStore 的核心架构分为三个主要层次：MVMap（B-Tree 映射层）、Chunk（存储单元层）和 FileStore（I/O 层）。此外还有后台线程负责自动提交和压缩。

**核心文件**: `org/h2/mvstore/MVStore.java`

MVStore 本身是一个顶层容器，管理着多个 MVMap 实例。每个 MVMap 是一个独立的 B-Tree，通过 mapId 唯一标识。MVStore 的生命周期包括打开、读取/写入、提交、压缩和关闭。

```text
┌──────────────────────────────────────────────────────────────┐
│                        MVStore                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           maps (ConcurrentHashMap<Integer, MVMap>)      │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  │
│  │  │ MVMap #1  │  │ MVMap #2  │  │ MVMap #3  │   ...     │  │
│  │  │ (index)   │  │ (data)    │  │ (meta)    │           │  │
│  │  └──────────┘  └──────────┘  └──────────┘             │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                MVMap 内部 (B-Tree)                       │  │
│  │                                                        │  │
│  │  root (AtomicReference<RootReference>)                  │  │
│  │       │                                                 │  │
│  │  ┌────┴──────────────┐                                  │  │
│  │  │ RootReference     │  ← immutable, CAS 更新            │  │
│  │  │  root: Page       │                                   │  │
│  │  │  version: long    │                                   │  │
│  │  │  previous: RootRef│  ← 版本链                          │  │
│  │  │  holdCount: byte  │  ← 可重入锁计数                     │  │
│  │  │  ownerId: long    │  ← 持有线程 id                     │  │
│  │  └───────────────────┘                                  │  │
│  │       │                                                 │  │
│  │  ┌────┴────────────────────┐                            │  │
│  │  │  NonLeaf Page (Node)    │  ← 内部节点                 │  │
│  │  │  keys: K[]             │                             │  │
│  │  │  children: PageRef[]   │                             │  │
│  │  │  totalCount: long      │                             │  │
│  │  └───┬───┬───┬───┬────────┘                             │  │
│  │      │   │   │   │                                      │  │
│  │  ┌───┘   │   └───┐  ...                                │  │
│  │  ▼       ▼       ▼                                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                │  │
│  │  │Leaf Page │ │Leaf Page │ │Leaf Page │  ...            │  │
│  │  │(Key/Val) │ │(Key/Val) │ │(Key/Val) │                │  │
│  │  └──────────┘ └──────────┘ └──────────┘                │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                FileStore (I/O 层)                       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐               │  │
│  │  │ Chunk #1 │ │ Chunk #2 │ │ Chunk #3 │   ...          │  │
│  │  │ [Pages] │ │ [Pages] │ │ [Pages] │                  │  │
│  │  └──────────┘ └──────────┘ └──────────┘               │  │
│  │                                                        │  │
│  │  StoreHeader: 两份冗余, 指向最新 chunk                   │  │
│  │  Layout Map:  持久化元数据, 记录 map→root 映射           │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```
**图 9-1: MVStore 整体架构图**

如图 9-1 所示，从代码层面看，MVStore 的构造过程（`MVStore.java` 第 259-319 行）完成以下初始化：

1. 解析配置参数（压缩级别、文件名、autoCommitBufferSize 等）
2. 如果指定了文件，打开 FileStore 并调用 `fileStore.start()` 读取 store header
3. 从 store header 中恢复元数据 map（`meta` MVMap）
4. 启动后台自动提交线程

MVStore 的关键设计决策是：**使用 `ReentrantLock`（名为 `storeLock`）保护主要的 store 操作（store()、close()），使用原子变量控制并发写入**。store lock 是一个公平锁（`new ReentrantLock(true)`），确保长时间运行的后台操作不会饥饿前台线程。

```java
// MVStore.java:163
private final ReentrantLock storeLock = new ReentrantLock(true);

// MVStore.java:169
private final AtomicBoolean storeOperationInProgress = new AtomicBoolean();
```

`storeOperationInProgress` 标志防止 `store()` 的重入——因为 meta map 的修改会触发 `beforeWrite()` 回调，有可能导致递归调用 `store()`。

```text
┌──────────────────────────────────────────────────────────────────┐
│              MVStore 构造与初始化流程                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MVStore.open() — 构造入口                                        │
│       │                                                          │
│       ▼                                                          │
│  第一步: 解析配置参数                                              │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 参数来源: open() 参数中的 URL (例如 jdbc:h2:file)     │        │
│  │ 解析内容:                                             │        │
│  │   fileName = "test.mv.db"  ← 数据库文件路径           │        │
│  │   autoCommitBufferSize = 1024 KB  ← 提交缓冲区大小    │        │
│  │   autoCommitDelay = 1000 ms      ← 自动提交间隔       │        │
│  │   compressMode = 0               ← 压缩模式          │        │
│  │   encryptionKey = null           ← 加密密钥          │        │
│  │   readOnly = false               ← 只读模式          │        │
│  │   retentionTime = 45000 ms       ← 版本保留时间       │        │
│  │   reuseSpace = true              ← 空间复用          │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  第二步: 打开 FileStore                                            │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ fileStore = new SingleFileStore()                     │        │
│  │ fileStore.open(fileName, readOnly, encryptionKey)     │        │
│  │   ├─ FileChannel.open(path, READ/WRITE)              │        │
│  │   ├─ fileLock.lock(method)   ← 文件级锁               │        │
│  │   └─ readStoreHeader()       ← 读取 store header     │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  第三步: 初始化元数据映射                                          │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ /* state remains STATE_OPEN (0) — no init state */   │        │
│  │ metaMap = openMetaMap()       ← 元数据 map           │        │
│  │ layoutMap = openLayoutMap()   ← 布局 map            │        │
│  │ restoreMetaMap()              ← 从磁盘恢复           │        │
│  │ restoreLayoutMap()            ← 从磁盘恢复           │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  第四步: 设置运行时状态                                            │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ state = STATE_OPEN                                   │        │
│  │ currentVersion = max(chunk.version) + 1              │        │
│  │ setAutoCommitDelay(configDelay)   ← 启动后台线程      │        │
│  │   └─ backgroundWriterThread.start()                  │        │
│  │                                                     │        │
│  │ MVStore 就绪, 可以接受读写操作                         │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-2: MVStore 构造与初始化流程**

### 9.1.1 MVStore 内部组件的关系

```text
本节速览：9.1.1 MVStore 内部组件的关系

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


如图 9-2 所示，MVStore 的内部架构包含一系列协同工作的子系统。以下组件图展示了各个内部对象之间的引用关系和职责划分：

```text
┌──────────────────────────────────────────────────────────────────┐
│                    MVStore 内部组件关系图                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MVStore (facade + orchestrator)                                 │
│  ├── fileStore: FileStore                    ← 文件 I/O 层       │
│  ├── meta: MVMap<String,String>             ← 元数据 map         │
│  ├── maps: ConcurrentHashMap<Integer,MVMap> ← 所有 map 实例      │
│  ├── storeLock: ReentrantLock               ← 公平锁              │
│  ├── storeOperationInProgress: AtomicBoolean ← CAS 防重入标志     │
│  ├── state: int                             ← OPEN/STOPPING/CLOSED│
│  ├── currentVersion: long                   ← 当前版本号          │
│  ├── compressionLevel: int                  ← 压缩等级 (0/1/2)   │
│  ├── keysPerPage: int                       ← 每页键数上限        │
│  ├── versionsToKeep: int                    ← 版本保留数          │
│  ├── oldestVersionToKeep: AtomicLong        ← 可保留的最旧版本    │
│  ├── versions: Deque<TxCounter>             ← 版本双端队列        │
│  ├── currentTxCounter: TxCounter            ← 当前事务计数器      │
│  ├── lastMapId: AtomicInteger               ← 下一个 map ID      │
│  ├── panicException: AtomicReference        ← 紧急异常            │
│  ├── updateCounter: long                    ← 更新计数器          │
│  └── updateAttemptCounter: long             ← 更新尝试计数器      │
│                                                                  │
│  内部状态标志:                                                     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ state: int  ← OPEN | STOPPING | CLOSED                │    │
│  │ saveNeeded: volatile boolean ← 需要保存标志              │    │
│  │ metaChanged: volatile boolean ← 元数据变更标志           │    │
│  │ closingThreadId: long ← 正在关闭的线程 ID                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  内存与自动提交管理:                                               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ unsavedMemory: int       ← 未保存的内存量 (字节)          │    │
│  │ autoCommitMemory: int    ← 自动提交触发阈值               │    │
│  │ storeVersion: long       ← 存储版本号                     │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  说明: 后台写入线程由 FileStore 内部类管理, 不在 MVStore 中       │
│  (MVStore 只提供 store() 方法, 由调用方决定何时触发)              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-3: MVStore 内部组件关系图**

如图 9-3 所示，MVStore 的设计遵循**外观模式（Facade Pattern）**：对外暴露统一的读写接口，对内协调各个子系统。FileStore 负责实际的磁盘 I/O，MVMap 负责 B-Tree 的内存操作，后台线程负责异步持久化和空间回收。这种分离使得每个组件的职责单一，并且可以独立测试和优化。

### 9.1.2 MVStore 生命周期状态机

```text
本节速览：9.1.2 MVStore 生命周期状态机

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


MVStore 实例在使用过程中经历三个状态，每个状态对应合法操作的集合。这些状态通过 `state` 字段（`int` 类型）追踪，定义在 `MVStore.java` 第 137-149 行：

```text
┌──────────────────────────────────────────────────────────────────┐
│                    MVStore 生命周期状态图                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│     MVStore 实例化                                                │
│         │                                                         │
│         ▼                                                         │
│   ┌─────────────┐                                                │
│   │    OPEN      │  ← state = 0 (默认值)                          │
│   │             │    正常读写 / 后台提交 / 紧缩操作                  │
│   └──────┬──────┘                                                │
│          │ close()                                                │
│          ▼                                                        │
│   ┌─────────────┐                                                │
│   │  STOPPING    │  ← 正在关闭等待 I/O 完成                        │
│   │              │    state = 1                                   │
│   │  停止接受新写入 │                                                │
│   └──────┬──────┘                                                │
│          │ 后台线程终止 + store 操作完成                              │
│          ▼                                                        │
│   ┌─────────────┐                                                │
│   │   CLOSED     │  ← 终止状态 (不可逆)                            │
│   │              │    state = 2                                   │
│   └─────────────┘                                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-4: MVStore 生命周期状态图**

如图 9-4 所示，`MVStore.java` 第 137-149 行定义了这些状态的常量和检查方法：

```java
private static final int STATE_OPEN = 0;
private static final int STATE_STOPPING = 1;
private static final int STATE_CLOSED = 2;

private volatile int state;   // 默认 STATE_OPEN (0)

boolean isOpen() {
    return state == STATE_OPEN;
}
```

生命周期中的关键转换点：
- **OPEN → STOPPING**：在 `close()` 方法开始时，停止接受新的写入操作
- **STOPPING → CLOSED**：在最后一个 store 操作和后台线程终止后
- **CLOSED** 是不可逆的终止状态，一旦关闭必须创建新实例才能重新访问数据库

### 9.1.3 写入缓存 (Write Buffer) 管理

```text
本节速览：9.1.3 写入缓存 (Write Buffer) 管理

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


MVStore 使用了一种"积累-刷盘"的写入策略，而不是每条写入都立即刷盘。写入操作首先修改内存中的 B-Tree 页面，这些修改积累在 `unsavedMemory` 计数器中。当满足条件时，后台线程将所有脏页面序列化为一个 Chunk 并写入文件。

```text
┌──────────────────────────────────────────────────────────────────┐
│                    MVStore 写入缓冲管理                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  写入路径:                                                         │
│                                                                  │
│  Session/Transaction                                              │
│       │                                                          │
│       │ map.operate(key, value, decisionMaker)                    │
│       ▼                                                          │
│  ┌────────────────┐                                              │
│  │ B-Tree 内存修改  │  ← 创建新的 Page 对象（不修改原 Page）        │
│  │ CAS 更新 root   │  ← AtomicReference.compareAndSet()          │
│  └───────┬────────┘                                              │
│          │ unsavedMemory += page.memory                           │
│          ▼                                                        │
│  ┌────────────────┐                                              │
│  │ 积累到 unsaved   │  ← 3 * unsavedMemory > 4 * autoCommitMemory │
│  │ Memory 计数器    │  → 触发自动保存                              │
│  └───────┬────────┘                                              │
│          │ 达到阈值 / autoCommitDelay 到期                          │
│          ▼                                                        │
│  ┌───────────────────┐    storeLock.lock()                        │
│  │ store() 序列化阶段  │ ──────────────────────▶ 公平锁等待          │
│  │ 收集所有脏 Map     │                                          │
│  │ RootReference     │                                          │
│  └───────┬───────────┘                                          │
│          │                                                        │
│          ▼                                                        │
│  ┌───────────────────┐                                           │
│  │ serialzeToBuffer() │  ← 所有脏页面递归序列化到 ByteBuffer       │
│  │ write() / flush()  │  ← FileChannel.write(buffer)             │
│  │ updateStoreHeader  │  ← 原子更新 store header                  │
│  └───────┬───────────┘                                          │
│          │                                                        │
│          ▼                                                        │
│  ┌───────────────────┐                                           │
│  │ releaseSavedPages()│  ← 释放已保存页面的内存引用                 │
│  │ dropUnusedChunks() │  ← 回收不再使用的 chunk                   │
│  └───────────────────┘                                           │
│                                                                  │
│  关键配置:                                                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ autoCommitMemory (默认 1 MB): 触发自动保存的内存阈值       │    │
│  │ autoCommitDelay  (默认 1000 ms): 自动保存检查间隔          │    │
│  │ autoCompactFillRate (默认 90%): 触发紧缩的填充率阈值       │    │
│  │ compressMode (默认 0): 0=不压缩 1=LZF 2=Deflate          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-5: MVStore 写入缓冲管理图**

如图 9-5 所示，`unsavedMemory` 计数器在 `MVStore.java` 第 1198-1215 行的 `accountForWrittenPage()` 中更新。每当一个 Page 被修改时，其内存占用量累加到 `unsavedMemory` 上。当 `isSaveNeeded()` 返回 true 时（第 1418-1424 行），后台线程唤醒并执行 store 操作。

这种积累型写入策略的设计目标是：
1. **减少 I/O 次数**：将多次小写入合并为一次大写入（Chunk）
2. **顺序写入优化**：Chunk 是连续写入的，可以利用磁盘的顺序写入性能
3. **减少写放大**：单次大写入比多次小写入的写放大更低
4. **原子性保障**：整个 Chunk 作为一个原子单位写入，要么全部成功要么全部失败

### 9.1.4 版本控制机制

```text
本节速览：9.1.4 版本控制机制

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


MVStore 使用全局递增版本号（`currentVersion`，`MVStore.java` 第 184 行）来管理 MVCC。每次 store 操作都会递增版本号，每个 Chunk 关联一个版本号，每个 RootReference 也关联一个版本号。

```text
┌──────────────────────────────────────────────────────────────────┐
│                    MVStore 版本控制                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  版本号分配:                                                       │
│                                                                  │
│  currentVersion (long, volatile)                                 │
│       │                                                          │
│       ├── 递增: ++currentVersion  (每次 store() 调用)              │
│       │                                                          │
│       ├── 关联到 Chunk: chunk.version = currentVersion            │
│       │                                                          │
│       ├── 关联到 RootReference: rootRef.version = currentVersion  │
│       │                                                          │
│       └── 用于 MVCC: 事务在 beginning 版本上读取                   │
│                                                                  │
│  版本链:                                                          │
│  RootReference.previous → 上一个版本的 RootReference              │
│                                                                  │
│  RootRef(v5) ← RootRef(v4) ← RootRef(v3) ← RootRef(v2)           │
│     │              │              │              │                │
│  最新版本        保留中          保留中        最旧版本             │
│                                                                  │
│  版本清理阈值: oldestVersionToKeep                                │
│  当版本 < oldestVersionToKeep → 从版本链中移除                     │
│                                                                  │
│  在 store() 后保留的版本: retentionTimeMillis 内的版本              │
│  默认: 45000 ms (45 秒)                                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-6: MVStore 版本控制图**

如图 9-6 所示，版本控制的核心作用是支持 MVCC 快照读取。当一个事务开始时，它记录当前的 `currentVersion`。在整个事务期间，它读取的 B-Tree 页面都是基于这个版本（或更早版本的）快照。即使有别的事务提交了新的修改（创建了新的 RootReference），当前事务仍然可以看到一致的旧版本数据，因为旧版本的 RootReference 仍然保留在版本链中。

## 9.2 B-Tree 与 Page 结构

MVStore 的 B-Tree 实现由 `Page<K,V>` 抽象类定义，包含两种具体子类：`NonLeaf`（内部节点）和 `Leaf`（叶子节点）。

**核心文件**: `org/h2/mvstore/Page.java`

Page 是 B-Tree 的基本构建块。每个 Page 属于一个特定的 MVMap，包含一个键数组和值数组（叶子节点）或子节点引用数组（内部节点）。

### 9.2.1 Page 字段设计

```text
本节速览：9.2.1 Page 字段设计

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`Page.java` 第 37-80 行定义了页面的核心字段：

```java
public final MVMap<K,V> map;          // 所属 map
private volatile long pos;            // 在 chunk 中的位置 (0=未保存, 1=已删除, >1=已保存)
public int pageNo = -1;               // 在 chunk 中的序号
private K[] keys;                     // 键数组
private int memory;                   // 内存占用估计
private int diskSpaceUsed;            // 磁盘空间占用
```

`pos` 字段使用 `AtomicLongFieldUpdater` 更新（第 89-91 行），这是为了在页面被保存线程写入位置信息的同时，其他线程可能并发地将页面标记为"已删除"。这种无锁并发更新是 MVStore 的经典模式。

```text
┌──────────────────────────────────────────────────────────────────┐
│              Page 对象字段内存布局及状态转换                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Page<K,V> 对象 (抽象基类)                                         │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ map (final MVMap<K,V>)                               │        │
│  │   └─ 所属 MVMap 引用, 构造时确定, 终身不变                     │
│  │                                                        │
│  │ pos (volatile long, AtomicLongFieldUpdater 更新)       │
│  │   ┌───────┬──────────────────────────────────────┐    │        │
│  │   │ 值     │ 含义                                │    │        │
│  │   ├───────┼──────────────────────────────────────┤    │        │
│  │   │ 0     │ 未持久化 (内存中的新页面)              │    │        │
│  │   │ 1     │ 已删除 (被标记为废弃, 等待回收)         │    │        │
│  │   │ > 1   │ 已持久化 (编码 chunk/offset/length)   │    │        │
│  │   └───────┴──────────────────────────────────────┘    │        │
│  │                                                        │
│  │ pageNo (int)                                           │        │
│  │   └─ 页面在 chunk 中的序号, -1 表示未分配                        │
│  │                                                        │
│  │ keys (K[])                                              │        │
│  │   └─ 键数组, 叶子节点和内部节点均包含                          │
│  │                                                        │
│  │ memory (int)                                            │        │
│  │   └─ 内存占用估计, 用于 unsavedMemory 计数                      │
│  │                                                        │
│  │ diskSpaceUsed (int)                                     │        │
│  │   └─ 磁盘空间占用, 与 memory 不同, 包含序列化后的大小             │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  状态转换:                                                        │
│                                                                  │
│  pos == 0          pos > 1              pos == 1                 │
│  ┌──────┐  write() ┌─────────┐  delete() ┌──────┐                │
│  │ NEW   │ ───────▶│ SAVED   │ ────────▶│ DEAD  │                │
│  │ (内存) │         │ (磁盘+内存)│          │ (废弃) │                │
│  └──────┘          └─────────┘          └──────┘                 │
│       │                 │                                         │
│       │ GC 回收        │ releaseSavedPages()                       │
│       ▼                 ▼                                         │
│  无引用时回收        GC 回收 (旧版本无人引用时)                      │
│                                                                  │
│  pos 使用 AtomicLongFieldUpdater 的原因:                           │
│  写入线程设置 pos > 1 和 读取线程设置 pos = 1 可能并发               │
│  需要原子性保证, 但不希望使用 synchronized 或 ReentrantLock         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-7: Page 对象字段内存布局及状态转换**

### 9.2.2 序列化格式

```text
本节速览：9.2.2 序列化格式

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-7 所示，`Page.read()` 方法（第 594-675 行）从 ByteBuffer 反序列化一个页面，格式如下：

```text
┌─────────────────────────────────────────────────────┐
│  Page 磁盘格式                                        │
├─────────────────────────────────────────────────────┤
│ pageLength (int)     ← 整个序列化后的长度              │
│ check (short)        ← 校验值 (chunkId ^ offset ^ len)│
│ pageNo (varInt)      ← 页面在 chunk 中的序号           │
│ mapId (varInt)       ← 所属 MVMap 的 id              │
│ keyCount (varInt)    ← 键的数量                       │
│ type (byte)          ← 0=leaf, 1=node; +2=compressed │
│ [children]           ← 内部节点: 子节点引用数组         │
│ [compress header]    ← 压缩时: 压缩前-压缩后的字节差    │
│ keys (...)           ← 键序列化                       │
│ values (...)         ← 叶子节点: 值序列化              │
└─────────────────────────────────────────────────────┘
```
**图 9-8: Page 磁盘序列化格式 (H2 使用大端序 big-endian)**

如图 9-8 所示，反序列化的核心流程（`Page.read()` 第 594-675 行）：
1. 读取 `pageLength` 并校验是否超出 buffer 剩余空间
2. 读取 `check` 短整数，计算校验值 `chunkId ^ offset ^ pageLength` 并对比验证
3. 解析 `pageNo`、`mapId`、`keyCount`、`type` 等元数据
4. 对压缩页面（`type & PAGE_COMPRESSED`），使用 LZF 或 Deflate 解压
5. 调用 `map.getKeyType().read()` 读出键数组
6. 叶子节点调用 `readPayLoad()` 读取值数组

### 9.2.3 压缩写入的决策逻辑

```text
本节速览：9.2.3 压缩写入的决策逻辑

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`Page.write()` 方法（第 723-793 行）在序列化到 buffer 后，会尝试压缩：

```java
// Page.java:742-775
int expLen = buff.position() - compressStart;
if (expLen > 16) {
    int compressionLevel = store.getCompressionLevel();
    if (compressionLevel > 0) {
        // 尝试压缩，如果压缩后 + 头部长度 < 原始长度，则使用压缩版本
        int compLen = compressor.compress(exp, pos, expLen, comp, 0);
        int plus = DataUtils.getVarIntLen(expLen - compLen);
        if (compLen + plus < expLen) {
            buff.position(typePos).put((byte) (type | compressType));
            // ... 写入压缩数据
        }
    }
}
```

只有当压缩后的数据确实比原始数据小时才会使用压缩版本。压缩等级分为：
- 等级 1：`CompressLZF`（快速压缩/解压，对应 `PAGE_COMPRESSED`）
- 等级 2：`CompressDeflate`（更高压缩比，对应 `PAGE_COMPRESSED_HIGH`）

```text
┌──────────────────────────────────────────────────────────────────┐
│              Page.write() 压缩决策流程                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  序列化完成后, 进入压缩决策:                                       │
│                                                                  │
│  write() 方法中:                                                  │
│       │                                                          │
│       ▼                                                          │
│  compressStart → buff.position() (记录序列化后的位置)              │
│       │                                                          │
│       ▼                                                          │
│  expLen = buff.position() - compressStart                         │
│       │                                                          │
│       ▼                                                          │
│  ┌─ expLen > 16?                                                 │
│  │    │                                                          │
│  │    ├── 否 → 数据太小, 压缩收益不大, 跳过                        │
│  │    │                                                          │
│  │    └── 是 → ──▶ compressionLevel?                              │
│  │                    │                                           │
│  │                    ├── 0 (不压缩)                               │
│  │                    │   └─ 不尝试压缩, 保留原始数据                │
│  │                    │                                           │
│  │                    ├── 1 (LZF)                                  │
│  │                    │   └─ CompressLZF.compress(exp)             │
│  │                    │                                           │
│  │                    └── 2 (Deflate)                              │
│  │                        └─ CompressDeflate.compress(exp)         │
│  │                                                                  │
│  │ 尝试压缩后:                                                      │
│  │    │                                                             │
│  │    ▼                                                             │
│  │  compLen = 压缩后长度                                            │
│  │  plus = getVarIntLen(expLen - compLen)  ← 存储差值所需字节       │
│  │    │                                                             │
│  │    ▼                                                             │
│  │  ┌─ compLen + plus < expLen?  (压缩收益检查)                     │
│  │  │    │                                                          │
│  │  │    ├── 是 → 使用压缩版本                                       │
│  │  │    │   ├─ typePos 字节: 设置 PAGE_COMPRESSED 标志             │
│  │  │    │   ├─ 写入 compressTypeLen (expLen - compLen)             │
│  │  │    │   └─ 替换原始数据为压缩数据                               │
│  │  │    │                                                          │
│  │  │    └── 否 → 保留原始数据                                      │
│  │  │        (压缩收益不够, 压缩后反而更大)                           │
│  │  │                                                              │
│  │  └── 完成, 回到 write() 主流程                                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-9: 页面压缩写入决策流程**

### 9.2.4 B-Tree 分裂与合并
如图 9-9 所示，B-Tree 的平衡通过 `split()` 和 `merge()` 实现。当页面键数超过 `keysPerPage`（默认 48）时，页面会分裂为两个。当页面键数过少时，会尝试与兄弟页面合并。

```text
分裂前 (超过容量):
┌──────────────────────────────┐
│ NonLeaf                      │
│ keys: [10, 20, 30, 40, 50]  │ ← 5 个键, 6 个子节点
│ children: [a, b, c, d, e, f]│
└──────────────────────────────┘

分裂后:
┌──────────────────────┐  ┌──────────────────────┐
│ NonLeaf (左)          │  │ NonLeaf (右)          │
│ keys: [10, 20]        │  │ keys: [40, 50]        │
│ children: [a, b, c]   │  │ children: [d, e, f]   │
└──────────────────────┘  └──────────────────────┘
        ▲                            ▲
        └──────────┬─────────────────┘
                   │ 提升键: 30
           ┌───────┴────────┐
           │ NonLeaf (父)    │
           │ keys: [30]      │
           │ children: [左,右]│
           └────────────────┘
```
**图 9-10: B-Tree 分裂示意图**

### 9.2.5 Leaf 与 NonLeaf 节点对比

```text
本节速览：9.2.5 Leaf 与 NonLeaf 节点对比

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-10 所示，`Page.java` 中的 `Leaf` 和 `NonLeaf` 子类分别位于第 340-400 行和第 410-476 行。它们在结构和使用场景上有显著差异：

```text
┌──────────────────────────────────────────────────────────────────┐
│           Leaf Page  vs  NonLeaf Page 对比图                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Leaf Page (叶子节点):              NonLeaf Page (内部节点):       │
│  ┌──────────────────────┐          ┌──────────────────────┐      │
│  │ keys: K[]            │          │ keys: K[]            │      │
│  │ values: V[]          │          │ children: PageRef[]  │      │
│  │ totalCount: long     │          │ totalCount: long     │      │
│  └──────────────────────┘          └──────────────────────┘      │
│                                                                  │
│  字段差异:                           字段差异:                     │
│  ▶ values: 存储实际数据               ▶ children: 存储子节点引用   │
│  ▶ 没有 children                     ▶ 没有 values               │
│  ▶ 所有键值对在同一页面                 ▶ 每个键对应一个子节点区间    │
│                                                                  │
│  角色:                               角色:                         │
│  ▶ 数据存储层                         ▶ 路由层                     │
│  ▶ B-Tree 最底层                      ▶ 中间/根节点                │
│  ▶ split() 产生两个 Leaf              ▶ split() 产生两个 NonLeaf  │
│  ▶ 可序列化值             ▶ 不直接序列化值                        │
│                                                                  │
│  子节点引用格式 (children 数组中的 PageRef):                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ NonLeaf children[i] → 第 i 个子节点的 pos 值         │        │
│  │ pos 编码: chunkId << 40 | offset | length            │        │
│  │ pos == 0: 未持久化 (内存中的新页面)                   │        │
│  │ pos == 1: 已删除 (被标记为回收)                       │        │
│  │ pos > 1:  已持久化 (文件中的有效位置)                 │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  内存占用计算:                                                     │
│  Leaf:  keys数组 + values数组 + 对象头 + totalCount               │
│  NonLeaf: keys数组 + children数组 (8字节/ref) + 对象头            │
│                                                                  │
│  序列化标志位 (type byte):                                        │
│  bit 0 (0x01): 1=NonLeaf, 0=Leaf                                │
│  bit 1 (0x02): 1=压缩 (PAGE_COMPRESSED)                         │
│  bit 2 (0x04): 1=高压缩 (PAGE_COMPRESSED_HIGH)                  │
│  bit 3 (0x08): 1=已移除 (PAGE_REMOVED)                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-11: Leaf vs NonLeaf 节点对比图**

### 9.2.6 Page 反序列化流程 (read)

```text
本节速览：9.2.6 Page 反序列化流程 (read)

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-11 所示，`Page.read()` 方法从磁盘上的 ByteBuffer 恢复一个完整的 Page 对象。这个过程是 MVStore 启动时加载数据和运行时按需加载页面的基础：

```text
┌──────────────────────────────────────────────────────────────────┐
│              Page.read() 反序列化流程图                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ByteBuffer (文件数据)                                            │
│       │                                                          │
│       ▼                                                          │
│  第一步: 读取 pageLength (int)                                    │
│       │                                                          │
│       ├── pageLength < 0 或 > buffer.remaining()                  │
│       │   └──→ 抛出 Error: "File corrupted in chunk ..."          │
│       │                                                          │
│       ▼                                                          │
│  第二步: 读取 check (short)                                       │
│       │                                                          │
│       ├── expected = chunkId ^ offset ^ pageLength                │
│       ├── check != expected                                       │
│       │   └──→ 抛出 Error: "File corrupted in chunk ..."          │
│       │                                                          │
│       ▼                                                          │
│  第三步: 读取 pageNo (varInt)                                     │
│       ├── 页面在 chunk 内的序号                                    │
│       │                                                          │
│       ▼                                                          │
│  第四步: 读取 mapId (varInt)                                      │
│       ├── mapId (-1 或无效)                                       │
│       │   └──→ 抛出 Error: "File corrupted in chunk ..."          │
│       │                                                          │
│       ▼                                                          │
│  第五步: 读取 keyCount (varInt)                                    │
│       │                                                          │
│       ▼                                                          │
│  第六步: 读取 type (byte)                                         │
│       │                                                          │
│       ├── (type & 1) == 0 → Leaf Page ← 数据页                    │
│       ├── (type & 1) == 1 → NonLeaf Page ← 内部节点               │
│       │                                                          │
│       ▼                                                          │
│  第七步: 条件解压                                                  │
│       │                                                          │
│       ├── (type & PAGE_COMPRESSED) != 0                           │
│       │   └──→ 读取 compressTypeLen (varInt: expLen - compLen)    │
│       │   └──→ 解压 LZF 或 Deflate 数据                          │
│       │   └──→ 将解压后的数据放回 ByteBuffer                      │
│       │                                                          │
│       ▼                                                          │
│  第八步: 读取键数组 (keys)                                         │
│       │                                                          │
│       ├── map.getKeyType().read(buff) × keyCount                  │
│       │                                                          │
│       ▼                                                          │
│  第九步: 分类型读取                                                │
│       │                                                          │
│       ├── NonLeaf: 读取 children 数组                              │
│       │   └── readChildPagePositions(buff, keyCount + 1)          │
│       │   └── 每个子节点位置: 8 字节 long (chunk+offset+len)      │
│       │                                                          │
│       └── Leaf: 调用 readPayLoad(buff, keyCount)                  │
│           └── map.getValueType().read(buff) × keyCount            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-12: Page.read() 反序列化流程图**

如图 9-12 所示，反序列化过程中最关键的校验是 `check` 值。它使用 chunkId、页面偏移量和 pageLength 三个独立来源的信息计算校验和，确保页面数据的三个维度（属于哪个 chunk、在文件中的位置、大小）与写入时一致。这种校验机制可以在页面级别检测数据损坏。

### 9.2.7 Page 序列化流程 (write)

```text
本节速览：9.2.7 Page 序列化流程 (write)

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`Page.write()` 方法是 read() 的逆过程，它将内存中的 Page 对象序列化为字节流，并可选地压缩数据部分。序列化过程在 `Page.java` 第 723-793 行实现：

```text
┌──────────────────────────────────────────────────────────────────┐
│              Page.write() 序列化流程图                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  起始: ByteBuffer (预分配, 通常 4KB)                               │
│       │                                                          │
│       ▼                                                          │
│  第一步: 预留 pageLength 位置 (4 字节, 稍后填充)                    │
│       │                                                          │
│       ▼                                                          │
│  第二步: 写入 check (short)                                       │
│       │  = chunkId ^ offset ^ 0 (占位, 稍后修正)                   │
│       │                                                          │
│       ▼                                                          │
│  第三步: 写入 pageNo (varInt)                                     │
│       │                                                          │
│       ▼                                                          │
│  第四步: 写入 mapId (varInt)                                      │
│       │                                                          │
│       ▼                                                          │
│  第五步: 写入 keyCount (varInt) + 保留 type 位置 (1 字节)           │
│       │                                                          │
│       ▼                                                          │
│  第六步: NonLeaf → 写入 children 数组 (long[] → 8 bytes each)     │
│       │                                                          │
│       ▼                                                          │
│  第七步: 标记压缩起始位置 compressStart = buff.position()           │
│       │                                                          │
│       ▼                                                          │
│  第八步: 写入 keys (使用 map.getKeyType().write())                │
│       │                                                          │
│       ▼                                                          │
│  第九步: Leaf → 写入 values (使用 map.getValueType().write())     │
│       │                                                          │
│       ▼                                                          │
│  第十步: 尝试压缩 (如果未压缩数据 > 16 字节)                        │
│       │                                                          │
│       ├── expLen = buff.position() - compressStart                │
│       ├── 尝试 LZF 或 Deflate 压缩                                │
│       ├── compLen + header < expLen?                              │
│       │   ├── 是: 替换 type 字节为压缩标志                         │
│       │   │      写入 compressTypeLen (varInt)                    │
│       │   │      替换 keys+values 区域为压缩数据                    │
│       │   └── 否: 保留原始数据 (压缩收益不够)                      │
│       │                                                          │
│       ▼                                                          │
│  第十一步: 回到 buffer 开头, 写入 pageLength                       │
│       │                                                          │
│       ▼                                                          │
│  第十二步: 修正 check 值 = chunkId ^ offset ^ pageLength          │
│       │                                                          │
│       ▼                                                          │
│  完成: ByteBuffer 准备好写入 chunk                                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-13: Page.write() 序列化流程图**

### 9.2.8 内存管理与 Page 驱逐

```text
本节速览：9.2.8 内存管理与 Page 驱逐

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-13 所示，MVStore 的内存管理比较复杂，因为页面既在内存中存在（用于快速读取），又在磁盘上存在（用于持久化）。MVStore 需要平衡内存使用和磁盘访问：

```text
┌──────────────────────────────────────────────────────────────────┐
│              Page 内存生命周期与驱逐流程                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Page 状态:                                                       │
│                                                                  │
│  ┌──────────┐     write()    ┌──────────────┐                    │
│  │  NEW      │ ────────────▶ │  PERSISTED    │                    │
│  │ (内存中)   │               │ (pos > 1)     │                    │
│  └──────────┘               └──────┬───────┘                    │
│                                    │                             │
│                            ┌───────┴───────┐                     │
│                            ▼               ▼                     │
│                     ┌────────────┐  ┌────────────┐               │
│                     │  RETAINED  │  │  EVICTED   │               │
│                     │ (被引用)    │  │ (pos==1)   │               │
│                     └────────────┘  └────────────┘               │
│                                                                  │
│  内存占用估算 (Page.java: memory 字段):                            │
│  memory = 对象头(16B) + keys数组 + values数组 + 其他字段           │
│  NonLeaf 额外: children 数组 (每个引用 8B)                        │
│                                                                  │
│  diskSpaceUsed: 页面在磁盘上的存储大小 (不同于 memory)              │
│                                                                  │
│  回收策略:                                                         │
│  1. releaseSavedPages():                                         │
│     store() 完成后, 将已持久化的页面的 memory 从 unsavedMemory 减去  │
│                                                                  │
│  2. dropUnusedChunks():                                          │
│     检查 Chunk 的 pageCountLive 字段                              │
│     如果所有页面都被标记为删除 (pageCountLive == 0)                  │
│     则整个 Chunk 可以回收                                         │
│                                                                  │
│  3. compact() / recompress():                                    │
│     读取仍然存活的页面, 重新写入新 Chunk                           │
│     旧 Chunk 被标记为废弃                                        │
│                                                                  │
│  内存压力处理:                                                     │
│  MVStore 不会主动驱逐 Page (不像传统 Buffer Pool)                   │
│  如果需要, rely on GC 回收不再被 RootReference 引用的 Page          │
│  因为 Page 是不可变的, 旧版本 Page 在没有引用时自然会被 GC 回收      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-14: Page 内存生命周期与驱逐流程**

如图 9-14 所示，MVStore 没有传统数据库中的 Buffer Pool 页面置换机制（如 LRU）。相反，它依赖于 Java GC 和不可变对象的特性。当一个页面的更新版本替代旧版本后，旧版本如果没有被任何事务的快照引用，GC 会自动回收。这种设计简化了代码，但依赖于 JVM 的内存管理和 GC 性能。

## 9.3 Chunk 文件布局

Chunk 是 MVStore 中一次性持久化写入的数据单元。每次 `store()` 调用会产生一个新的 Chunk，其中包含所有脏页面的序列化数据。

**核心文件**: `org/h2/mvstore/Chunk.java`, `mvstore/SFChunk.java`, `mvstore/FileStore.java`

### 9.3.1 Chunk 字段

```text
本节速览：9.3.1 Chunk 字段

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`Chunk.java` 第 26-148 行定义了 chunk 的关键属性：

```java
public final int id;           // chunk ID (0 ~ 2^26 - 1)
public volatile long block;    // 文件中的起始块号 (以 block 为单位)
public int len;                // chunk 长度 (以 block 为单位)
int pageCount;                 // 总页面数
int pageCountLive;             // 存活页面数
int tocPos;                    // Table of Content 在 chunk 中的偏移
long maxLen;                   // 所有页面的最大长度总和
long maxLenLive;               // 所有存活页面的最大长度总和
long version;                  // 该 chunk 对应的版本
long time;                     // 创建时间 (ms, 从 store 创建开始计时)
public long unused;            // 何时不再需要 (ms)
long unusedAtVersion;          // 可被回收的版本号
int collectPriority;           // 垃圾回收优先级 (0=需要回收, 值越大优先级越低)
```
```text
┌──────────────────────────────────────────────────────────────────┐
│              Chunk 核心字段分类与关系图                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Chunk (单个持久化单元)                                            │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  标识字段:                                                │        │
│  │  ┌──────────────────────────────────────────────┐        │        │
│  │  │ id (final)   ← chunk 唯一编号 (0 ~ 2^26 - 1) │        │        │
│  │  │ block        ← 文件中的起始块号               │        │        │
│  │  │ len          ← chunk 占用的 block 数          │        │        │
│  │  └──────────────────────────────────────────────┘        │        │
│  │                                                        │        │
│  │  页面统计:                                                  │        │
│  │  ┌──────────────────────────────────────────────┐        │        │
│  │  │ pageCount      ← 总页面数                    │        │        │
│  │  │ pageCountLive  ← 仍存活的页面数              │        │        │
│  │  │ maxLen         ← 所有页面的最大长度总和       │        │        │
│  │  │ maxLenLive     ← 存活页面的最大长度总和       │        │        │
│  │  │ tocPos         ← Table of Content 偏移       │        │        │
│  │  └──────────────────────────────────────────────┘        │        │
│  │                                                        │        │
│  │  版本与时间:                                                │        │
│  │  ┌──────────────────────────────────────────────┐        │        │
│  │  │ version    ← 创建时的 MVStore 版本号          │        │        │
│  │  │ time       ← 创建时间 (ms, 相对 store)        │        │        │
│  │  └──────────────────────────────────────────────┘        │        │
│  │                                                        │        │
│  │  回收状态:                                                  │        │
│  │  ┌──────────────────────────────────────────────┐        │        │
│  │  │ unused           ← 何时不再需要 (ms)          │        │        │
│  │  │ unusedAtVersion  ← 可被回收的版本号           │        │        │
│  │  │ collectPriority  ← 回收优先级 (0=最高)        │        │        │
│  │  └──────────────────────────────────────────────┘        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  字段间的关键关系:                                                │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ collectPriority = (version - unusedAtVersion) / 100  │        │
│  │   → 值越小, 回收优先级越高                            │        │
│  │   → 为 0 时立即回收                                   │        │
│  │                                                        │        │
│  │ pageCountLive / pageCount = 存活率                     │        │
│  │   → 存活率低 → 适合紧缩 (compact)                       │        │
│  │                                                        │        │
│  │ block + len 定义了 chunk 在文件中的物理范围               │        │
│  │ id 用于 chunk 之间的引用和 ToC 索引                     │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-15: Chunk 核心字段分类与关系图**

### 9.3.2 文件布局

```text
本节速览：9.3.2 文件布局

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-15 所示，MVStore 文件采用块对齐的布局方式，块大小固定为 4096 字节（`BLOCK_SIZE`）。

```text
┌──────────────────────────────────────────────────────────┐
│  MVStore 文件布局                                         │
├──────────────────────────────────────────────────────────┤
│ Block 0: Store Header (副本 1)                            │
│   H:2,blockSize:4096,format:3,created:...,               │
│   chunk:...,block:...,fletcher:...                        │
├──────────────────────────────────────────────────────────┤
│ Block 1: Store Header (副本 2 - 冗余保护)                 │
├──────────────────────────────────────────────────────────┤
│ Block 2+: Chunk #N                                        │
│  ┌────────────────────────────────────────────────────┐   │
│  │ Chunk Header (ASCII Map)                            │   │
│  │ chunk:3,block:2,len:47,pages:128,...                │   │
│  ├────────────────────────────────────────────────────┤   │
│  │ Page 0 (serialized bytes)                           │   │
│  ├────────────────────────────────────────────────────┤   │
│  │ Page 1                                              │   │
│  ├────────────────────────────────────────────────────┤   │
│  │ ...                                                │   │
│  ├────────────────────────────────────────────────────┤   │
│  │ Table of Content (ToC)                              │   │
│  │ [mapId|offset|len|type] × pageCount                │   │
│  ├────────────────────────────────────────────────────┤   │
│  │ Chunk Footer                                        │   │
│  │ chunk:3,len:47,version:5,fletcher:0x12345678       │   │
│  └────────────────────────────────────────────────────┘   │
│  [padding to block boundary]                              │
├──────────────────────────────────────────────────────────┤
│ Block N: Chunk #N+1                                     │
│ ...                                                      │
└──────────────────────────────────────────────────────────┘
```
**图 9-16: MVStore 文件布局**

如图 9-16 所示，**Store Header**（写两遍到 block 0 和 block 1，崩溃安全）：

H:2,blockSize:4096,format:3,created:1712345678,
formatRead:3,chunk:5,block:12,version:42,clean:1,
fletcher:0xABCD1234

Store header 中记录了最后一个有效 chunk 的位置（`chunk` + `block` 字段），这是崩溃恢复的起点。

**Chunk Header**（`Chunk.java` 第 38 行：`MAX_HEADER_LENGTH = 1024`）：

chunk:3,block:2,len:47,pages:128,pinCount:0,
max:123456,map:5,root:987654,time:3600,
version:42,next:0,toc:65432

**Chunk Footer**（`Chunk.java` 第 44 行：`FOOTER_LENGTH = 128`）：

```text
chunk:3,len:47,version:42,fletcher:0x12345678
```

Footer 中的 Fletcher32 校验和用于检测 chunk 是否完整写入。在 `SingleFileStore` 中，写入 chunk 的流程（`FileStore.java` 第 1467-1517 行 `serializeToBuffer()`）为：

1. 在 buffer 头部预留 header 空间
2. 序列化所有脏页面，递归写入
3. 持久化 Layout Map 根页面（`layoutRoot.writeUnsavedRecursive()`）
4. 生成 Table of Content（ToC）
5. 追加 footer 并校验
6. 对齐到 block 边界

**Table of Content（ToC）** 是 Chunk 中所有页面的索引，每个页面对应一个 `long` 值，编码了 `mapId + offset + length + type`。ToC 的作用是在崩溃恢复时快速枚举和校验所有页面。

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
> 详细说明了 file header 双副本设计、chunk 的 header/footer 字段定义和 checksum 机制。

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
> 详细说明了 page 的二进制格式：length、checksum、mapId、keys/values 数组以及 64-bit page pointer 编码。

### 9.3.3 Store Header 详细格式

```text
本节速览：9.3.3 Store Header 详细格式

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

Store header 是 MVStore 文件的"超级块"，位于文件最开头的两个 block 中。其格式是一个简化的 ASCII 属性映射（`DataUtils.readStoreHeader()` 第 865-901 行）：

```text
┌──────────────────────────────────────────────────────────────────┐
│              Store Header 详细格式 (Block 0 和 Block 1)            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Block 0:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ H:2,                                          ←      │        │
│  │ blockSize:4096,                                ← 块大小│        │
│  │ format:3,                                      ← 格式版本│        │
│  │ created:1712345678,                            ← 创建时间│        │
│  │ formatRead:3,                                  ← 读格式版本│        │
│  │ chunk:5,                                       ← 最后chunk│        │
│  │ block:12,                                      ← 最后block│        │
│  │ version:42,                                    ← 最后版本│        │
│  │ clean:1,                                       ← 正常关闭│        │
│  │ fletcher:0xABCD1234                            ← 校验和 │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  Block 1 (冗余副本):                                              │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 内容与 Block 0 完全相同 (在 Block 0 写入后才写入 Block 1)│        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  字段说明:                                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ H:2        → Header 版本标记 (始终为 "H:2")              │    │
│  │ blockSize  → 块大小 (固定 4096 字节)                      │    │
│  │ format     → 文件格式版本 (当前为 3)                       │    │
│  │ created    → 数据库创建时间戳 (UNIX 毫秒)                  │    │
│  │ formatRead → 可读取的最低格式版本                          │    │
│  │ chunk      → 最后一个有效 chunk 的 ID                     │    │
│  │ block      → 最后一个有效 chunk 的起始 block 号            │    │
│  │ version    → 最后一个有效 chunk 的版本号                   │    │
│  │ clean      → 是否正常关闭 (1=正常, 0=未正常关闭)          │    │
│  │ fletcher   → 整个 header 的 Fletcher32 校验和             │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  写入策略 (FileStore.java:writeStoreHeader()):                    │
│  1. 将 header 字符串编码为 UTF-8 字节                              │
│  2. 写入 Block 0 (fileChannel.write(0, buffer))                   │
│  3. 强制刷盘 (fileChannel.force())                                │
│  4. 写入 Block 1 (fileChannel.write(1, buffer))                   │
│  5. 再次刷盘 (fileChannel.force())                                │
│                                                                  │
│  崩溃安全:                                                        │
│  - 如果在写入 Block 0 后崩溃: Block 1 仍完整                       │
│  - 如果在写入 Block 1 后崩溃: 至少一份完整                          │
│  - 如果两份都完整: 取 clean==1 或 version 更高的那个                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-17: Store Header 详细格式**

如图 9-17 所示，`clean` 字段是一个重要的恢复提示。当 MVStore 正常关闭时（`close()` 成功完成），`clean` 被设置为 1。如果进程崩溃，`clean` 保持为 0，表示恢复时需要额外的校验步骤。但即使 `clean == 1`，MVStore 仍然会执行完整的校验流程——`clean` 字段只是一个提示，不是可靠性的唯一保证。

### 9.3.4 Chunk 生命周期

```text
本节速览：9.3.4 Chunk 生命周期

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

Chunk 从创建到回收经历多个阶段。每个 Chunk 的 `collectPriority` 和 `pageCountLive` 字段共同决定其当前所处的生命周期阶段：

```text
┌──────────────────────────────────────────────────────────────────┐
│                    Chunk 生命周期状态图                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐                                                   │
│  │  CREATED    │  ← 新 chunk, 正在序列化写入                        │
│  │ 状态: 写入中 │                                                   │
│  └──────┬─────┘                                                   │
│         │ write complete, store header 更新                        │
│         ▼                                                         │
│  ┌────────────┐                                                   │
│  │   ACTIVE   │  ← 正常 chunk, 包含存活页面                         │
│  │ 状态: 使用中 │  pageCountLive > 0                                │
│  │            │  collectPriority = Integer.MAX_VALUE (不入回收)     │
│  └──────┬─────┘                                                   │
│         │ 页面被更新/删除 (pageCountLive 减少)                       │
│         ▼                                                         │
│  ┌────────────┐                                                   │
│  │   OBSOLETE  │  ← 页面被新版本覆盖, 部分或全部不可用                │
│  │ 状态: 部分废弃│  pageCountLive 递减中                              │
│  │            │  collectPriority 递增 (越旧回收优先级越高)            │
│  └──────┬─────┘                                                   │
│         │ pageCountLive == 0 (所有页面已被新版本覆盖)                  │
│         ▼                                                         │
│  ┌────────────┐                                                   │
│  │   DEAD     │  ← 所有页面已废弃, 等待回收                          │
│  │ 状态: 可回收 │  collectPriority = 0 (最高回收优先级)               │
│  └──────┬─────┘                                                   │
│         │ 触发 dropUnusedChunks()                                   │
│         ▼                                                         │
│  ┌────────────┐                                                   │
│  │  RECYCLED  │  ← 空间已回收, chunk id 可被重用                     │
│  │ 状态: 已回收 │  文件空间被后续 chunk 覆盖                          │
│  └────────────┘                                                   │
│                                                                  │
│  转换条件:                                                         │
│  ACTIVE → OBSOLETE:                                               │
│    当该 chunk 中的页面被新版本替换, pageCountLive 减少               │
│                                                                  │
│  OBSOLETE → DEAD:                                                 │
│    pageCountLive 减少到 0, 并且版本 >= unusedAtVersion              │
│                                                                  │
│  DEAD → RECYCLED:                                                 │
│    dropUnusedChunks() 在 store() 时检查                            │
│    该 chunk 的 block 区域被标记为可重用                              │
│                                                                  │
│  回收统计 (Chunk.java:collectPriority 计算公式):                    │
│  priority = (int)((version - unusedAtVersion) / 100)              │
│  值越小 → 越应该被回收                                              │
│  值 == 0 → 立即回收                                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-18: Chunk 生命周期状态图**

### 9.3.5 Chunk 分配策略

```text
本节速览：9.3.5 Chunk 分配策略

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-18 所示，MVStore 的文件是追加写入的，但文件大小是有限的。当文件增长到一定大小时，MVStore 开始回收废弃 chunk 的空间。`SingleFileStore` 负责管理文件空间：

```text
┌──────────────────────────────────────────────────────────────────┐
│              Chunk 空间分配与回收策略                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  初始分配: 追加到文件末尾                                          │
│                                                                  │
│  文件: [Block 0][Block 1][Chunk 1][Chunk 2]...[Chunk N]          │
│                            ↑ 新增 chunk 追加到末尾  ↑              │
│                                                                  │
│  空间回收后: 重用已回收区域                                         │
│                                                                  │
│  文件: [Block 0][Block 1][Chunk 1][FREE][Chunk 3]...[Chunk N]    │
│                                       ↑ 新 Chunk 写入回收区域     │
│                                                                  │
│  适合存放的 free 区域条件:                                         │
│  freeBlockLen >= newChunk.blockCount                              │
│  (free 区域必须 >= 新 chunk 需要的 block 数)                       │
│                                                                  │
│  freeChunk 列表维护:                                              │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ collectPriority <= 0 ?                                    │    │
│  │   ├── 是: 立即回收, 加入 free list                        │    │
│  │   └── 否: 加入回收候选池                                  │    │
│  │                                                          │    │
│  │ dropUnusedChunks() 在每次 store() 时调用                   │    │
│  │ 遍历 chunks 列表, 检查 pageCountLive == 0                  │    │
│  │ 将废弃 chunk 的 block 区域加入 freeSpace 列表              │    │
│  │ 在 serializeToBuffer() 时优先使用 free 区域                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  紧缩 (Compact):                                                  │
│  当存活数据比例低时 (填充率 < autoCompactFillRate)                  │
│  触发紧缩操作:                                                     │
│  1. 读取低填充率 chunk 中的存活页面                                 │
│  2. 将这些页面写入新 chunk                                        │
│  3. 标记旧 chunk 为 DEAD                                         │
│  4. 旧 chunk 空间被回收                                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-19: Chunk 空间分配与回收策略**

## 9.4 Undo Log 与崩溃安全

如图 9-19 所示，MVStore 不使用传统数据库意义上的独立 WAL 文件。它采用了一种"隐式日志"策略：**B-Tree 的版本化根指针 + 原子性 Chunk 写入** 的组合提供了崩溃安全保证。

### 9.4.1 工作原理

```text
本节速览：9.4.1 工作原理

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

MVStore 的崩溃安全机制体现在以下方面：

1. **事务层（TransactionStore）的 undo log**：每次写入前，先创建 undo log 条目（`TxDecisionMaker.logAndDecideToPut()` 第 162-166 行），记录 `(mapId, key, oldValue)`。数据必须先记录到 undo log，然后才能修改 map——用于事务回滚。

2. **MVStore 层的原子提交**：调用 `store()`（内部为 `storeNow()`）时，当前版本的所有脏页面被序列化到一个新的 Chunk 中，然后 atomically 更新 store header。

```text
┌──────────────────────────────────────────────────┐
│  写入路径 (事务层 + MVStore 层)                     │
├──────────────────────────────────────────────────┤
│                                                   │
│  1. tx.log(mapId, key, oldValue)                  │
│     └─ 写入 Undo Log (记录旧值用于回滚)          │
│                                                   │
│  2. map.operate(key, newValue, decisionMaker)     │
│     └─ 修改 B-Tree (内存中)                       │
│        └─ CAS 更新 RootReference                   │
│                                                   │
│  3. store()  (自动或显式)                          │
│     └─ collectChangedMapRoots(version)            │
│     └─ serializeToBuffer(buffer, changed, chunk)  │
│     └─ write(storeBuffer) → 刷盘                  │
│     └─ updateStoreHeader() → 更新根指针           │
│                                                   │
│  4. TransactionStore.commit(t)                    │
│     └─ flipCommittingTransactionsBit(txId, true)  │
│     └─ 遍历 undo log, 应用 CommitDecisionMaker     │
│     └─ undoLog.clear()                            │
│     └─ flipCommittingTransactionsBit(txId, false) │
│                                                   │
└──────────────────────────────────────────────────┘
```
**图 9-20: MVStore 写入路径（事务层 + MVStore 层）**

### 9.4.2 为什么不需要 WAL

```text
本节速览：9.4.2 为什么不需要 WAL

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

如图 9-20 所示，MVStore 不需要传统 WAL 的原因是：

- **B-Tree 的持久化单位是 Chunk 而不是单个页面**。一个 Chunk 要么完整写入，要么完全不写入（通过 footer 中的 fletcher 校验和判断）。
- **根指针原子更新**：store header 记录最新 Chunk 的位置，只有在 Chunk 完全写入后才更新 header。
- **undo log 用于事务回滚**，而不是用于崩溃恢复。崩溃时只需要找到最后一个完整写入的 Chunk，从那里重建 B-Tree 即可。

这种设计借鉴了 log-structured 存储的思想：**将随机小写入转换为顺序大写入**，同时天然支持 MVCC（多版本并发控制）。

### 9.4.3 传统 WAL 与 MVStore 隐式日志对比

```text
本节速览：9.4.3 传统 WAL 与 MVStore 隐式日志对

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

传统数据库使用单独的 WAL 文件记录每次修改，而 MVStore 将数据和日志合并为同一个 Chunk 结构。以下是对比：

```text
┌──────────────────────────────────────────────────────────────────┐
│        传统 WAL 模式                 MVStore 隐式日志模式          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  传统关系型数据库:                     MVStore:                    │
│                                                                  │
│  写入顺序:                            写入顺序:                     │
│  1. 写入 WAL (追加)                   1. 修改内存 B-Tree           │
│  2. 修改数据页 (随机)                  2. 积累脏页面                │
│  3. 定期 Checkpoint                   3. 一次性序列化为 Chunk      │
│                                      4. 写入文件 (顺序追加)        │
│                                      5. 更新 Store Header         │
│                                                                  │
│  文件结构:                             文件结构:                    │
│  ┌──────────────────┐                 ┌──────────────────┐       │
│  │ WAL 文件          │                 │ MVStore 文件     │       │
│  │ [Record 1]       │                 │ [Header 0]       │       │
│  │ [Record 2]       │                 │ [Header 1]       │       │
│  │ [Record 3]       │                 │ [Chunk 1]        │       │
│  │ ...              │                 │  ├─ Header      │       │
│  └──────────────────┘                 │  ├─ Pages (数据) │       │
│  ┌──────────────────┐                 │  ├─ ToC (索引)  │       │
│  │ 数据文件          │                 │  └─ Footer      │       │
│  │ [Page 1]         │                 │ [Chunk 2]        │       │
│  │ [Page 2]         │                 │ ...              │       │
│  │ [Page 3]         │                 └──────────────────┘       │
│  │ ...              │                                            │
│  └──────────────────┘                                            │
│                                                                  │
│  优点:                               优点:                         │
│  ▶ 成熟, 广泛验证                      ▶ 无 WAL 放大 (不需要写两遍) │
│  ▶ 细粒度恢复                          ▶ 顺序写入, 高吞吐           │
│  ▶ 支持任意粒度的事务                    ▶ 天然支持 MVCC             │
│                                       ▶ 崩溃恢复速度快             │
│  缺点:                               缺点:                         │
│  ▶ 写放大 (WAL + 数据页写两遍)          ▶ 写放大 (旧版本保留)         │
│  ▶ 随机写入数据页的性能问题               ▶ 需要定期紧缩               │
│  ▶ 崩溃恢复可能需要 replay 大量日志       ▶ 单文件, 紧缩时压力大       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-21: 传统 WAL 与 MVStore 隐式日志对比**

### 9.4.4 原子提交与 Crash Safety

```text
本节速览：9.4.4 原子提交与 Crash Safety

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-21 所示，MVStore 的原子提交依赖于精心设计的写入顺序和校验机制。其核心思想是：**先写数据（Chunk），再写元数据（Store Header），确保数据写入完成后才暴露新版本**：

```text
┌──────────────────────────────────────────────────────────────────┐
│              MVStore 原子提交流程 （Crash-Safe）                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  时间线:                                                          │
│                                                                  │
│  步骤 1: 准备阶段                                                 │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ storeLock.lock()                                      │        │
│  │ storeOperationInProgress.CAS(false, true)             │        │
│  │ version = ++currentVersion                            │        │
│  │ dropUnusedChunks()                                    │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 2: 序列化脏页面到 ByteBuffer                                 │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ ByteBuffer buf = allocate(chunkBlockCount * BLOCK_SIZE)│        │
│  │ serializeToBuffer(buf, changedRoots, chunk)           │        │
│  │   ├─ 写入 Chunk Header (预留)                         │        │
│  │   ├─ 递归写入所有脏 Page                               │        │
│  │   ├─ 写入 layout map root                             │        │
│  │   ├─ 写入 Table of Content (ToC)                      │        │
│  │   └─ 写入 Chunk Footer (fletcher 校验和)               │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 3: 写入文件 (FileChannel)                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ fileChannel.write(buf, block * BLOCK_SIZE)           │        │
│  │ if (syncWrite) fileChannel.force(true)               │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 4: 更新 Store Header (原子提交点)                             │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ writeStoreHeader(chunk.id, chunk.block, version)     │        │
│  │   ├─ 写入 Block 0                                     │        │
│  │   ├─ fileChannel.force(true)                         │        │
│  │   ├─ 写入 Block 1 (冗余)                              │        │
│  │   └─ fileChannel.force(true)                         │        │
│  │                                                               │
│  │  ← 此处是原子提交点！                                         │        │
│  │  ← 一旦 Store Header 写入完成, 新版本对所有读取可见           │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 5: 清理阶段                                                 │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ releaseSavedPages() (释放已持久化的页面引用)           │        │
│  │ storeOperationInProgress.set(false)                   │        │
│  │ storeLock.unlock()                                    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  崩溃场景分析:                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ 崩溃发生在        │ 影响         │ 恢复行为                   │    │
│  ├──────────────────────────────────────────────────────────┤    │
│  │ 步骤 2 (序列化中)  │ 无          │ buffer 未写入文件, 无影响   │    │
│  │ 步骤 3 (写入 chunk)│ chunk 不完整 │ footer 校验和失败, 跳过     │    │
│  │ 步骤 4 (写 header) │ block 0 损坏 │ 读取 block 1 的旧 header   │    │
│  │ 步骤 4 (force 后)  │ 无          │ header 已更新, 恢复到该版本 │    │
│  │ 步骤 5 (清理中)     │ 无          │ 已提交, 版本可用            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-22: MVStore 原子提交流程与崩溃安全**

### 9.4.5 Undo Log 的 Crash Recovery 作用

```text
本节速览：9.4.5 Undo Log 的 Crash Recov

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-22 所示，虽然 undo log 主要用于事务回滚，但它在崩溃恢复中也扮演着重要角色。当系统崩溃后重启，MVStore 可以恢复到最后一个完整的 Chunk，但事务表中的 undo log 可能包含已提交但未清理或未提交但部分写入的记录：

```text
┌──────────────────────────────────────────────────────────────────┐
│              Undo Log 在 Crash Recovery 中的角色                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  场景 1: 事务已提交, undo log 标记为 COMMITTED                     │
│                                                                  │
│  UndoLog: [记录1][记录2]...[记录N]                                │
│          ↑ 所有操作已应用 CommitDecisionMaker                     │
│          ↑ undo log 已标记为清理状态                              │
│                                                                  │
│  结果: 不需要额外操作, 下次清理时删除 undo log                      │
│                                                                  │
│                                                                  │
│  场景 2: 事务未提交, undo log 标记为 OPEN                          │
│                                                                  │
│  UndoLog: [记录1][记录2]...[记录K]                                │
│          ↑ 部分写入, 事务未完成                                    │
│          ↑ 可能在崩溃时事务正在执行中                              │
│                                                                  │
│  结果: 回滚这些 undo log 条目                                      │
│        将每个键的值恢复为 undo log 中的旧值                         │
│                                                                  │
│                                                                  │
│  场景 3: committingTransactions bit 已设置                        │
│                                                                  │
│  committingTransactions: [bit 3 = true]                          │
│  (事务 3 正在提交过程中崩溃)                                       │
│                                                                  │
│  结果: 检查事务 3 的 undo log                                     │
│        如果所有操作都已成功提交 → 清理 undo log                     │
│        如果部分操作未提交 → 回滚                                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-23: Undo Log 在崩溃恢复中的角色**

## 9.5 检查点 (Checkpoint)

如图 9-23 所示，MVStore 的检查点机制比传统数据库简单得多——它将内存中的脏页面写入一个新 Chunk。

### 9.5.1 触发条件

```text
本节速览：9.5.1 触发条件

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`MVStore.java` 第 1418-1424 行决定了是否需要自动保存：

```java
// MVStore.java:1418-1424
boolean isSaveNeeded() {
    return 3 * unsavedMemory > 4 * autoCommitMemory;
}
```

当预估的未保存内存超过 autoCommitMemory 的约 133% 时，触发自动保存。此外，`saveNeeded` 标志也会在某些操作（如 map 写入回调）中被设置。

```text
┌──────────────────────────────────────────────┐
│  后台自动提交流程                               │
├──────────────────────────────────────────────┤
│                                               │
│  Background Writer Thread                     │
│       │                                       │
│       ▼                                       │
│  sleep(autoCommitDelay ms)                    │
│       │                                       │
│       ▼                                       │
│  check hasUnsavedChanges()                    │
│       │                                       │
│       ▼                                       │
│  storeLock.lock()                             │
│       │                                       │
│       ▼                                       │
│  store(syncWrite=false)                       │
│       │                                       │
│       ├─ dropUnusedChunks()                   │
│       │    └─ 回收已废弃的 chunk                │
│       │                                       │
│       ├─ collectChangedMapRoots(version)       │
│       │    └─ 遍历所有 MVMap                   │
│       │    └─ setWriteVersion(version)         │
│       │    └─ 收集有变化的 root page            │
│       │                                       │
│       ├─ serializeToBuffer()                  │
│       │    └─ 递归写入所有脏页面                │
│       │    └─ 写入 layout map root             │
│       │    └─ 写入 ToC 和 footer               │
│       │                                       │
│       ├─ storeBuffer() / write()              │
│       │    └─ 实际 I/O 写入                    │
│       │                                       │
│       └─ releaseSavedPages()                  │
│            └─ 释放旧版本引用                     │
│                                               │
│       ▼                                       │
│  storeLock.unlock()                           │
│                                               │
└──────────────────────────────────────────────┘
```
**图 9-24: 后台自动提交流程**

### 9.5.2 store() 方法的详细流程

```text
本节速览：9.5.2 store() 方法的详细流程

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

如图 9-24 所示，`MVStore.store()`（第 936-958 行）是检查点的核心：

```java
private long store(boolean syncWrite) {
    assert isLockedByCurrentThread();
    if (isOpenOrStopping() && hasUnsavedChanges()
            && storeOperationInProgress.compareAndSet(false, true)) {
        try {
            long result = ++currentVersion;      // 递增版本号
            if (fileStore == null) {
                setWriteVersion(result);          // 纯内存模式
            } else {
                if (fileStore.isReadOnly()) {
                    throw DataUtils.newMVStoreException(...);
                }
                fileStore.dropUnusedChunks();     // 回收废弃 chunk
                storeNow(syncWrite, result);      // 实际持久化
            }
            return result;
        } finally {
            storeOperationInProgress.set(false);
        }
    }
    return INITIAL_VERSION;
}
```

关键点：
- **版本号递增**：每次 store 操作都对应一个新的全局版本号，用于 MVCC 的版本管理
- **dropUnusedChunks()**：在写入新数据前，先回收不再使用的旧 chunk 空间
- **CAS 防重入**：`storeOperationInProgress` 确保不会同时执行两个 store 操作

`collectChangedMapRoots()`（第 996-1022 行）遍历所有 MVMap，找出自上次 store 后有变化的 root page，将它们收集到一个列表中，然后一起序列化到新 chunk 中。

### 9.5.3 后台写入线程

```text
本节速览：9.5.3 后台写入线程

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

后台线程在 `setAutoCommitDelay()` 中启动（第 310 行）。其主循环 `writeOrClose()` 周期性地：
1. 检查是否有未保存的更改
2. 尝试获取 store lock（非阻塞）
3. 调用 `store(false)` 写入新 chunk
4. 执行可选的紧缩操作

后台写入使用 `non-sync` 写入（`syncWrite=false`），这意味着它不会强制刷盘（不调用 `FileChannel.force()`），从而获得更好的性能。显式的 `sync()` 调用或关闭时的最后提交使用同步写入。

### 9.5.4 检查点触发条件详解

```text
本节速览：9.5.4 检查点触发条件详解

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

检查点的触发不仅仅是基于 `unsavedMemory`。多个条件共同决定何时触发检查点：

```text
┌──────────────────────────────────────────────────────────────────┐
│              检查点触发条件与决策逻辑                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  触发类型 1: 内存阈值触发 (自动)                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ isSaveNeeded() = 3 * unsavedMemory > 4 * autoCommitMemory   │        │
│  │                                                      │        │
│  │ 参数默认值: autoCommitMemory = 1 MB                  │        │
│  │ 触发阈值: unsavedMemory > ~1.33 MB                   │        │
│  │ 调整方式: 在 MVStore.open() 时传入                     │        │
│  │           例: ";autoCommitBufferSize=2" → 2 MB       │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  触发类型 2: 定时触发 (周期检查)                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ backgroundWriterThread 每 autoCommitDelay ms 检查一次 │        │
│  │                                                      │        │
│  │ 参数默认值: autoCommitDelay = 1000 ms (1 秒)         │        │
│  │ hasUnsavedChanges() 返回 true → 执行 store()         │        │
│  │ hasUnsavedChanges() 返回 false → 继续 sleep          │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  触发类型 3: 显式触发                                             │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ store() 或 storeNow() — 持久化写入                    │        │
│  │ sync()              — 强制同步刷盘                    │        │
│  │ close()             — 关闭时最后一次持久化             │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  检查点条件决策树:                                                 │
│                                                                  │
│  store() 方法入口                                                 │
│       │                                                          │
│       ▼                                                          │
│  isOpenOrStopping() && hasUnsavedChanges()?                       │
│       │                                                          │
│       ├── 否 → return INITIAL_VERSION (跳过)                      │
│       │                                                          │
│       └── 是 → storeOperationInProgress.CAS(false, true)?        │
│                  │                                                │
│                  ├── 否 → return INITIAL_VERSION (重入保护)        │
│                  │                                                │
│                  └── 是 → 执行 store                              │
│                            │                                      │
│                            ├── fileStore.dropUnusedChunks()        │
│                            ├── storeNow(syncWrite, version)       │
│                            └── storeOperationInProgress.set(false)│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-25: 检查点触发条件与决策逻辑**

### 9.5.5 检查点前后状态对比

```text
本节速览：9.5.5 检查点前后状态对比

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-25 所示，检查点执行前后，MVStore 的内部状态会经历显著变化。理解这些变化有助于把握 MVStore 的行为特征：

```text
┌──────────────────────────────────────────────────────────────────┐
│              检查点执行前后状态对比图                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  检查点之前:                                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ unsavedMemory = ~1.5 MB (大量未持久化的脏页面)        │        │
│  │ currentVersion = 42                                  │        │
│  │ 内存中的 RootReference: v42 ← v41 ← v40 ← ...       │        │
│  │ 文件中的最后一个完整 Chunk: Chunk #5 (version 40)     │        │
│  │ Store Header 指向: Chunk #5, block=12, version=40   │        │
│  │                                                              │
│  │ 部分页面已经被更新的版本覆盖, 旧版本页面在 Chunk #3, #4, #5 中  │        │
│  │ 这些旧页面中的一些 pageCountLive 已经开始减少                   │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         │ 执行 store()                                            │
│         ▼                                                         │
│  检查点期间:                                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 1. version = 43 (递增)                               │        │
│  │ 2. dropUnusedChunks() — 检查 Chunk #3, #4           │        │
│  │    如果 pageCountLive == 0 → 标记为可回收             │        │
│  │ 3. collectChangedMapRoots(43) — 收集所有修改过的 map  │        │
│  │ 4. serializeToBuffer()                               │        │
│  │    └─ 创建 Chunk #6, 包含所有脏页面的最新版本          │        │
│  │ 5. write(Chunk #6) — 写入文件                        │        │
│  │ 6. writeStoreHeader(chunk=6, block=N, version=43)    │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  检查点之后:                                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ unsavedMemory = ~0 KB (脏页面已持久化)                │        │
│  │ currentVersion = 43                                  │        │
│  │ 内存中的 RootReference: v43 ← v42 ← v41 ← v40 ← ... │        │
│  │ 文件中的最后一个完整 Chunk: Chunk #6 (version 43)     │        │
│  │ Store Header 指向: Chunk #6, block=N, version=43    │        │
│  │                                                              │
│  │ releaseSavedPages() 释放了已保存页面的内存占用                   │        │
│  │ Chunk #3, #4 中的废弃页面标记为 DEAD (可回收)                  │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-26: 检查点执行前后状态对比**

### 9.5.6 脏页收集 (Dirty Page Collection)

```text
本节速览：9.5.6 脏页收集 (Dirty Page Colle

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-26 所示，脏页收集是检查点过程中最关键的步骤之一。`collectChangedMapRoots()` 方法负责找出自上次 store 以来所有被修改的 MVMap 的根页面：

```text
┌──────────────────────────────────────────────────────────────────┐
│              脏页收集 (collectChangedMapRoots) 流程图               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  collectChangedMapRoots(long version)                             │
│       │                                                          │
│       ▼                                                          │
│  ArrayList<RootReference> changed = new ArrayList<>()             │
│       │                                                          │
│       ▼                                                          │
│  for each MVMap in fileStoreMaps:                                 │
│       │                                                          │
│       ▼                                                          │
│    RootReference rootRef = map.getRoot()                          │
│       │                                                          │
│       ▼                                                          │
│    rootRef.version == version?  (已经是当前版本)                    │
│       │                                                          │
│       ├── 是 → 跳过 (这个 map 在本次 store 中没有被修改)            │
│       │                                                          │
│       └── 否 →                                                  │
│                  │                                               │
│                  ├── map.setWriteVersion(version)                  │
│                  │   └─ 创建新的 RootReference 绑定到当前版本      │
│                  │   └─ 递归复制 B-Tree 的根路径                   │
│                  │     (路径复制: 复制根到修改点的路径上的节点)     │
│                  │                                               │
│                  └── changed.add(map.getRoot())                   │
│                      └─ 加入变更列表                              │
│                                                                  │
│       ▼                                                          │
│  return changed (变更列表)                                        │
│       │                                                          │
│       ▼                                                          │
│  在 storeNow() 中:                                                │
│  for each RootReference in changed:                               │
│       │                                                          │
│       ├── rootRef.root.writeUnsavedRecursive(buffer, chunk)       │
│       │   └─ 递归将整个 B-Tree 序列化到 buffer                    │
│       │   └─ 未修改的子树 (pos > 0) 不需要重新写入                 │
│       │   └─ 只写 pos == 0 的页面 (新创建的页面)                  │
│       │                                                          │
│       └── rootRef.root.writeToBuffer(buffer)                     │
│                                                                  │
│  只有真正被修改的页面 (pos == 0) 才会被序列化                      │
│  未被修改的页面通过引用指向旧 Chunk 中的位置                        │
│  这是 MVStore 写入优化的核心: 增量写入, 全量引用                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-27: 脏页收集流程图**

### 9.5.7 后台写入线程调度时间线

```text
本节速览：9.5.7 后台写入线程调度时间线

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-27 所示，MVStore 的后台写入线程和可能的紧缩线程以特定的调度方式运行。以下展示了在典型负载下的线程调度时间线：

```text
如图 9-28 所示，┌──────────────────────────────────────────────────────────────────┐
│              后台线程调度时间线 (典型工作负载)                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  时间  │ 前台线程操作              │ 后台写入线程                   │
│  ─────┼─────────────────────────┼─────────────────────────────  │
│       │                          │                              │
│  T0   │ Session: INSERT x100     │ sleep(autoCommitDelay=1s)    │
│  T1   │ Session: INSERT x200     │ (sleeping)                   │
│  T2   │ 3*unsavedMemory >         │ ── 唤醒 ──▶                  │
│       │ 4*autoCommitMemory       │ tryLock() → 获取 storeLock   │
│       │ (触发条件检查)            │ store() → 写入 Chunk #7    │
│  T3   │ ← 前台线程等待?           │ writeStoreHeader()           │
│       │ (后台写入时, 前台写操作     │ releaseSavedPages()          │
│       │  仍然可以修改内存 B-Tree)  │ unlock()                     │
│  T4   │ Session: UPDATE x50      │ sleep(autoCommitDelay)       │
│  T5   │ Session: SELECT (无锁读)  │ (sleeping)                   │
│  T6   │ Session: INSERT x300     │ ── 唤醒 ──▶                  │
│       │                          │ store() → 写入 Chunk #8    │
│  T7   │                          │ ── 检查紧缩条件 ──▶          │
│       │                          │ fillRate < autoCompactFill?  │
│       │                          │ compileChunks() [后台紧缩线程] │
│  T8   │ Session: INSERT x100     │ unlock()                     │
│  T9   │ Session: COMMIT          │ ── 检测到提交 ──▶             │
│       │                          │ store(syncWrite=true)        │
│       │                          │ (同步刷盘)                    │
│       │                          │ writeStoreHeader()           │
│       │                          │ FileChannel.force()          │
│  T10  │ COMMIT 返回 OK           │ sleep(autoCommitDelay)       │
│       │                          │                              │
│                                                                  │
│  关键观察:                                                        │
│  - 后台写入期间, 前台线程可以继续写入内存 B-Tree (无锁)             │
│  - 只有 store() 期间 storeLock 被持有                             │
│  - 写操作被 storeLock 阻塞, 直到 store() 完成                     │
│  - 读操作完全不受 store() 影响 (无锁读)                            │
│  - 同步写入 (syncWrite=true) 在 commit 时使用                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-28: 后台线程调度时间线**

## 9.6 MVStore 文件格式详解

本节基于官方文档 `mvstore.html#fileFormat` 的说明，深入 MVStore 的二进制文件布局。
理解文件格式对于调试持久化问题、分析存储空间使用和恢复数据都至关重要。

### 9.6.1 文件整体布局

```text
本节速览：9.6.1 文件整体布局

  如图 9-29 所示，┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ MVStore 文件 = 2×File Header + N×Chunk
        ▼
  ┌────────────┐
  │ 本节结论   │
  └─────┬──────┘
        │ File Header: 双冗余 4KB header，含最新 chunk 位置
        │ Chunk: 每次 commit 写入一个 append-only 块
        │ 文件格式: 三级层次 (file → chunk → page)
```

**图 9-29: MVStore 文件三级层次结构**

```text
如图 9-30 所示，┌──────────────────────────────────────────────────────────────────┐
│                    MVStore 文件 (.mv.db)                           │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐                              │
│  │ File Header 1 │  │ File Header 2 │    两份冗余 header         │
│  │ (4 KB)        │  │ (4 KB)        │    内容一致，校验恢复       │
│  └──────────────┘  └──────────────┘                              │
├──────────────────────────────────────────────────────────────────┤
│  ┌──── Chunk 1 ────┐  ┌──── Chunk 2 ────┐  ┌──── Chunk 3 ────┐ │
│  │ Header          │  │ Header          │  │ Header          │ │
│  │ Page 1 (root)   │  │ Page 4 (root)   │  │ Page 7 (root)   │ │
│  │ Page 2 (leaf)   │  │ Page 5 (leaf)   │  │ Page 8 (leaf)   │ │
│  │ Page 3 (leaf)   │  │                 │  │                 │ │
│  │ Footer          │  │ Footer          │  │ Footer          │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                             ...                                   │
├──────────────────────────────────────────────────────────────────┤
│  File header → chunk footer "next" 链 → 遍历查找最新 chunk       │
└──────────────────────────────────────────────────────────────────┘
```

**图 9-30: 文件打开与最新 Chunk 定位流程**

```text
┌──────────────────────────────────────┐
│  打开 MVStore 文件                     │
├──────────────────────────────────────┤
│                                      │
│  1. 读取 File Header 1               │
│     ├─ checksum 有效? → 记作候选 A    │
│     └─ 无效 → 丢弃                    │
│                                      │
│  2. 读取 File Header 2               │
│     ├─ checksum 有效? → 记作候选 B    │
│     └─ 无效 → 丢弃                    │
│                                      │
│  3. 选择版本号更大的有效 header         │
│     ├─ 从中获取 chunk/block/version   │
│     └─ 如果不可用 → 从文件末尾搜索     │
│                                      │
│  4. 从候选 chunk footer 开始          │
│     沿 "next" 链遍历                  │
│     ├─ 最多 20 跳                     │
│     ├─ 每跳校验 header + footer       │
│     └─ 找到最新有效 chunk             │
│                                      │
│  5. 从最新 chunk 的 root 字段         │
│     读取元数据 map                    │
│                                      │
└──────────────────────────────────────┘
```

MVStore 的数据文件由两个冗余的 file header 和一系列 chunk 组成：

```text
[ File Header 1 ] [ File Header 2 ] [ Chunk ] [ Chunk ] ... [ Chunk ]
    4 KB             4 KB             可变大小    可变大小      可变大小
```

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
> 其中的"File Format"节详细描述了文件、chunk、page 三级的二进制布局。

### 9.6.2 File Header 格式

```text
本节速览：9.6.2 File Header 格式

  如图 9-31 所示，┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ File Header 的 8 个字段、双冗余校验、恢复策略
        ▼
  ┌────────────┐
  │ 本节结论   │
  └─────┬──────┘
        │ 8 字段: H/block/blockSize/chunk/created/format/version/fletcher
        │ 两份 header 冗余写入，防止单次更新损坏
        │ Fletcher-32 校验和检测数据损坏
        │ header 不一定指向最新 chunk，需沿 next 链查找
```

**图 9-31: File Header 双冗余与写入策略**

```text
┌────────────────────────────────────────────────────────────────────┐
│                  写入新 Chunk 时的 File Header 更新策略              │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 预测下一个 chunk 位置 (基于当前 chunk 大小)                       │
│     ├─ 如果下次写入位置匹配预测 → 不更新 header                       │
│     ├─ 如果不匹配 → 更新 header 指向新位置                           │
│     └─ 如果 next 链超过 20 跳 → 强制更新 header                      │
│                                                                     │
│  2. header 更新时，两个副本依次写入                                   │
│     ├─ 写入 File Header 1 (可能部分失败)                             │
│     ├─ 写入 File Header 2 (可能部分失败)                             │
│     └─ 只要有一个 header 有效即可恢复                                 │
│                                                                     │
│  3. 打开时校验                                                   │
│     ├─ 两个都有效 → 用版本号更新的那个                                │
│     ├─ 一个有效 → 用有效的那个                                        │
│     └─ 都无效 → 从文件末尾的 chunk footer 搜索                        │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

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

```text
本节速览：9.6.3 Chunk 格式

  如图 9-32 所示，┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ Chunk 的 header/footer 结构、COW 机制、空间回收
        ▼
  ┌────────────┐
  │ 本节结论   │
  └─────┬──────┘
        │ 每次 commit = 一个 chunk (append-only)
        │ COW: 修改页写入新 chunk，旧页保留在旧 chunk 中
        │ 45 秒保留期后，live 数据最少的 chunk 被 compact
```

**图 9-32: Chunk COW 更新机制**

```text
Version 1 (Chunk 1):          Version 2 (Chunk 2):
┌────────────────────┐       ┌────────────────────┐
│ Root (Page 1)      │       │ Root (Page 4, NEW) │──→ Page 1 被 COW 复制
│  ├── Leaf (Page 2) │       │  ├── Leaf (Page 5) │──→ Page 2 被 COW 复制
│  └── Leaf (Page 3) │       │  └── Leaf (Page 3) │──→ Page 3 未修改，共享
└────────────────────┘       └────────────────────┘
                                      │
        旧 Chunk 1 的 Page 1,2  →  空间可回收 (无引用)
        旧 Chunk 1 的 Page 3  →  仍被 Version 2 引用，保留

Chunk 空间回收 (Compaction):
┌──────────────────────────────────────────────────────────────────┐
│  按 live 数据比例排序所有 chunk                                    │
│  ┌──────────────────────┐  ┌──────────────────────┐              │
│  │ Chunk 5 (10% live)   │  │ Chunk 3 (90% live)   │              │
│  │ → 优先 compact       │  │ → 暂不 compact       │              │
│  └──────────────────────┘  └──────────────────────┘              │
│         │                                                         │
│         ▼                                                         │
│  将 Chunk 5 中的 live 页写入新 Chunk → 释放 Chunk 5 空间          │
└──────────────────────────────────────────────────────────────────┘
```

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
3. **45 秒保留**：chunk 标记为 free 后，默认至少保留 45 秒才覆写，确保旧版本可读。
4. **空间回收**：live page 最少的 chunk 被优先 compact（重新写入新 chunk 后释放旧空间）。
5. **next 链**：file header 不一定会指向最新 chunk，而是通过 chunk 的 next 字段形成链，最长 20 跳后强制更新 header。

### 9.6.4 Page 格式

每个 page 以二进制格式存储（不可直接阅读），使用变长编码优化空间：

```text
┌─────────────────────────────────────────────────────────┐
│  Page 二进制布局                                           │
├──────────────┬──────────┬───────────────────────────────┤
│  字段         │  类型     │  说明                          │
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
│    Chunk ID     │  Chunk 内偏移      │  长度代码    │ 类型     │
│    (26 bit)     │   (32 bit)        │  (5 bit)   │ (1 bit)  │
└─────────────────┴───────────────────┴────────────┴──────────┘
```

- 26 bit chunk ID：最多支持 6710 万个 chunk
- 32 bit 偏移：支持最大 chunk 大小为 4 GB
- 5 bit 长度代码：0=32B, 1=48B, 2=64B, 3=96B, ..., 31=>1MB（读取 page 时只需一次 I/O，除超大 page 外）
- 1 bit 类型：0=叶子, 1=内部节点
- 不包含绝对文件位置，因此 chunk 可在文件内移动而不需修改 page pointer

**Counted B-Tree：** 内部节点中的 `childCounts` 数组记录了每个子树的总条目数。这一设计使得：
- 可以高效地通过索引访问条目（`getIndex(key)`）
- 可以快速计算两个键之间的中位数
- 可以高效地对 range 计数
- Iterator 支持快速 skip

### 9.6.5 元数据 Map

```text
本节速览：9.6.5 元数据 Map

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 元数据 map 存储所有 map 和 chunk 的元信息
        ▼
  ┌────────────┐
  │ 本节结论   │
  └─────┬──────┘
        │ 每个 chunk 的最后一页 = 元数据 root page
        │ 键空间: chunk.<id> → chunk 元数据
        │ 键空间: map.<id> → map 元数据 (name/version/type)
```

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

## 9.7 恢复机制

MVStore 恢复机制利用了两个冗余副本的 store header（Block 0/1）和 chunk footer 中的 fletcher 校验和。恢复过程不需要 replay undo log，而是直接从最新的完整 chunk 重建 B-Tree（详细流程见图 9-33 至图 9-35）。

### 9.7.1 恢复流程

```text
本节速览：9.7.1 恢复流程

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

**核心文件**: `org/h2/mvstore/SingleFileStore.java`, `mvstore/FileStore.java`

```text
如图 9-33 所示，┌──────────────────────────────────────────────────┐
│  崩溃恢复流程                                      │
├──────────────────────────────────────────────────┤
│                                                   │
│  1. 读取 Store Header (Block 0)                   │
│     └─ 校验 fletcher 校验和                        │
│     └─ 获取 lastChunkId 和 lastBlock               │
│                                                   │
│  2. 读取 Store Header (Block 1) — 如果 0 损坏      │
│     └─ 两份副本相互验证                            │
│                                                   │
│  3. 定位到 lastBlock，读取 Chunk Footer            │
│     └─ 校验 fletcher 校验和                        │
│     └─ 如果 chunk 完整，加载它                     │
│                                                   │
│  4. 向前扫描后续 chunk                             │
│     └─ 使用 ToC 加载所有页面                       │
│     └─ 重建每个 MVMap 的 RootReference             │
│                                                   │
│  5. 恢复 TransactionStore                         │
│     └─ 扫描 undo log maps                         │
│     └─ UNDO_LOG_OPEN → 未完成的事务，需要回滚       │
│     └─ UNDO_LOG_COMMITTED → 已提交但未清理         │
│                                                   │
│  6. 清理未完成的事务                               │
│     └─ 对 UNDO_LOG_OPEN 的事务执行回滚             │
│     └─ 如果 committingTransactions bit 已设置，    │
│         重做或回滚                                 │
│                                                   │
└──────────────────────────────────────────────────┘
```
**图 9-33: 崩溃恢复流程**

### 9.7.2 Store Header 读取

```text
本节速览：9.7.2 Store Header 读取

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

如图 9-29 所示，`readStoreHeader()`（`FileStore.java` 第 962 行，抽象方法，由 `SingleFileStore` 实现）从文件头部读取两份 store header。其策略是：

```java
// SingleFileStore 中的读取逻辑
// 1. 先尝试读取 block 0
// 2. 校验 fletcher 校验和
// 3. 如果 block 0 损坏，尝试 block 1
// 4. 对于每份 header，提取 chunk/block 信息
// 5. 选择版本号最新的有效 header
```

两份 header 保证了在写入 header 过程中发生崩溃时，至少有一份是完整的。

### 9.7.3 TransactionStore 的恢复

```text
本节速览：9.7.3 TransactionStore 的恢复

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

`TransactionStore` 在 `open()` 时执行事务恢复。其核心是扫描 undo log maps：

- 命名约定：`undoLog.<transactionId>`（后缀为 `.` 表示 OPEN，`-` 表示 COMMITTED）
- 对于 OPEN 状态的 undo log：事务需要回滚（撤销所有未提交的修改）
- 对于 COMMITTED 状态的 undo log：事务已提交但尚未清理，需要完成提交流程

```java
// TransactionStore.java:579-629
void commit(Transaction t, boolean recovery) {
    int transactionId = t.transactionId;
    // 原子操作：将 transactionId 标记为 "committing"
    VersionedBitSet commitingTx = flipCommittingTransactionsBit(transactionId, true);
    t.notifyAllWaitingTransactions();

    // 遍历 undo log，逐条应用 commit
    Cursor<Long,Record<?,?>> cursor = undoLog.cursor(null);
    CommitDecisionMaker<Object> commitDecisionMaker = new CommitDecisionMaker<>(t, ...);
    while (cursor.hasNext()) {
        long undoKey = cursor.next();
        Record<?, ?> record = cursor.getValue();
        int mapId = record.mapId;
        // 使用 map.operate() 将 VersionedValueUncommitted → VersionedValueCommitted
        map.operate(key, null, commitDecisionMaker);
    }
    undoLog.clear();
    flipCommittingTransactionsBit(transactionId, false);
}
```

`committingTransactions` BitSet 是并发控制的关键：当另一个事务读取数据时，如果发现某条记录的操作 ID 属于 `committingTransactions` 中的事务，就会认为该记录已提交，读取 `getCurrentValue()`；否则视为未提交，读取 `getCommittedValue()`。

### 9.7.4 详细恢复流程（含代码路径）

```text
本节速览：9.7.4 详细恢复流程（含代码路径）

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

MVStore 的恢复过程在 `MVStore.java` 的构造方法和 `SingleFileStore.start()` 中实现。以下展示每个步骤对应的代码路径和详细操作：

```text
如图 9-34 所示，┌──────────────────────────────────────────────────────────────────┐
│         MVStore 恢复流程 — 详细步骤与代码路径                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  阶段 1: 文件打开 (SingleFileStore.open())                         │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ FileChannel.open(path, READ/WRITE)                   │        │
│  │ fileChannel.position(0)                              │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  阶段 2: 读取和验证 Store Header                                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ readStoreHeader():                                    │        │
│  │   ├─ allocate(2 * BLOCK_SIZE)                        │        │
│  │   ├─ fileChannel.read(buffer, 0)                     │        │
│  │   ├─ parseStoreHeader(buffer, 0) // Block 0          │        │
│  │   │   ├─ 解析属性字符串                                │        │
│  │   │   ├─ fletcher 校验                               │        │
│  │   │   └─ 提取 chunk, block, version                  │        │
│  │   ├─ parseStoreHeader(buffer, 1) // Block 1          │        │
│  │   └─ selectBestHeader(h0, h1)                        │        │
│  │       ├─ 优先选 clean==1 的                           │        │
│  │       ├─ 其次选 version 更大的                         │        │
│  │       └─ 如果都无效 → 新数据库 (empty)                 │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  阶段 3: 扫描和验证 Chunk                                          │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ setLastChunk(lastChunk):                             │        │
│  │   ├─ 读取 lastChunk 的 footer                        │        │
│  │   ├─ fletcher 校验                                    │        │
│  │   ├─ 如果 footer 有效:                                │        │
│  │   │   ├─ 读取 ToC, 加载所有页面                       │        │
│  │   │   └─ 更新 meta map 和 layout map                  │        │
│  │   ├─ 如果 footer 无效:                                │        │
│  │   │   └─ 尝试前一个 chunk (回退)                       │        │
│  │   └─ 向前扫描所有后续 chunk                            │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  阶段 4: 重建 MVMap (从 layout map 恢复)                           │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ layoutMap 包含了所有 MVMap 的 root page 位置          │        │
│  │ for each entry in layoutMap:                         │        │
│  │   ├─ mapId = entry.key                               │        │
│  │   ├─ rootPos = entry.value (chunk/offset/length)     │        │
│  │   ├─ readPage(rootPos) → 递归加载 B-Tree              │        │
│  │   └─ map.setRoot(RootReference(rootPage))            │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  阶段 5: 事务恢复 (TransactionStore.open())                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ metaMap 中查找 undoLog.* 条目                         │        │
│  │ for each transaction:                                │        │
│  │   ├─ 如果 map 名以 "." 结尾 → OPEN                    │        │
│  │   │   └─ rollback() 撤销所有操作                      │        │
│  │   ├─ 如果 map 名以 "-" 结尾 → COMMITTED               │        │
│  │   │   └─ commit(recovery=true) 完成提交               │        │
│  │   └─ 清理已处理的 undo log map                        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-34: MVStore 恢复流程详细步骤与代码路径**

### 9.7.5 事务恢复决策树

```text
本节速览：9.7.5 事务恢复决策树

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-30 所示，在崩溃恢复过程中，每个事务的 undo log 需要根据其状态执行不同的恢复操作。以下决策树展示了完整的恢复逻辑：

```text
如图 9-35 所示，┌──────────────────────────────────────────────────────────────────┐
│              事务恢复决策树 (TransactionStore.open())               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  对于每个 undoLog.<txId> 条目:                                    │
│                                                                  │
│  mapName = undoLog.<txId>                                        │
│       │                                                          │
│       ▼                                                          │
│  mapName 后缀?                                                    │
│       │                                                          │
│  ┌────┴────┐                                                     │
│  ▼         ▼                                                     │
│  "."       "-"                                                    │
│  (OPEN)    (COMMITTED)                                            │
│    │         │                                                    │
│    │         │                                                    │
│    ▼         ▼                                                    │
│  未完成的事务  已提交的事务                                         │
│    │         │                                                    │
│    │         │                                                    │
│    ▼         ▼                                                    │
│  回滚!      继续提交!                                              │
│    │         │                                                    │
│    │         │                                                    │
│    ├─ 创建     ├─ flipCommittingTransactionsBit(txId, true)       │
│    │  Rollback │  → 标记为正在提交                                  │
│    │  Decision │                                                    │
│    │  Maker    ├─ 遍历 undo log 中的每条记录                        │
│    │           │  → 应用 CommitDecisionMaker                       │
│    │  ├─ 遍历   │  → 将 VersionedValueUncommitted 转换为           │
│    │  │  undo   │     VersionedValue (去掉 operationId)            │
│    │  │  log     │                                                  │
│    │  │         └─ undoLog.clear()                                 │
│    │  ├─ 对每个  └─ flipCommittingTransactionsBit(txId, false)     │
│    │  │ 条目     │                                                  │
│    │  │         │                                                  │
│    │  └─ 使用   ┌─ 特殊情况: 如果 committingTransactions bit       │
│    │     old    │   在崩溃前已设置                                  │
│    │     value  │    → 检查 commit 是否已部分完成                    │
│    │     恢复   │    → 如果已完成 → 清理 undo log                   │
│    │     原值   │    → 如果未完成 → 回滚                            │
│    │            └────────────────────────────────────────────      │
│    │                                                                  │
│    ▼                                                                  │
│  恢复完成, 移除 undo log map                                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-35: 事务恢复决策树**

### 9.7.6 VersionedBitSet 恢复状态机

```text
本节速览：9.7.6 VersionedBitSet 恢复状态机

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-31 所示，`VersionedBitSet` 是 MVStore 中追踪事务提交状态的核心数据结构。它在并发控制和崩溃恢复中起到关键作用：

```text
如图 9-36 所示，┌──────────────────────────────────────────────────────────────────┐
│           VersionedBitSet 恢复状态机                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  VersionedBitSet = BitSet + version (每次修改递增)                 │
│                                                                  │
│  用途: 记录哪些事务正在提交过程中                                    │
│  committingTransactions = VersionedBitSet                         │
│                                                                  │
│  状态转换:                                                         │
│                                                                  │
│  ┌────────────────┐                                               │
│  │  txId NOT in   │  ← 事务未提交, 或已完全提交                     │
│  │  BitSet        │                                                │
│  └───────┬────────┘                                                │
│          │ flipCommittingTransactionsBit(txId, true)               │
│          ▼                                                         │
│  ┌────────────────┐                                               │
│  │  txId IN       │  ← 事务正在提交中                               │
│  │  BitSet        │    → commit() 方法正在遍历 undo log            │
│  └───────┬────────┘    → 其他事务看到此 bit 会认为记录已提交        │
│          │                                                         │
│          ├── commit 完成: flip(txId, false)                        │
│          │    └─ txId NOT in BitSet                                │
│          │                                                         │
│          └── 崩溃: BitSet 保留在内存中, 未持久化                    │
│               ↓                                                    │
│              恢复: 扫描 undo log 中的 committingTransactions bit    │
│                                                                  │
│  恢复时的处理:                                                     │
│                                                                  │
│  committingTransactions BitSet 本身不持久化!                        │
│  因为: BitSet 是内存中的运行时状态                                  │
│                                                                  │
│  恢复方案:                                                         │
│  读取 undo log 中 map 名后缀判断事务状态                            │
│  "."  = OPEN     → 未提交, 肯定不在 committingTransactions 中      │
│  "-"  = COMMITTED → 已提交, 但 BitSet 已被清除                     │
│                                                                  │
│  未决问题: 崩溃发生在 commit() 方法内部                            │
│  flip(txId, true) 之后, 但在遍历 undo log 之前崩溃                 │
│  → 恢复时: 该事务的 undo log 是 COMMITTED 状态                     │
│    但提交操作可能未完成                                            │
│  → 解决方案: 重新执行 commit(recovery=true)                        │
│    幂等: 部分已提交的记录被再次提交也是安全的                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-36: VersionedBitSet 恢复状态机**

### 9.7.7 崩溃场景与恢复策略矩阵

```text
本节速览：9.7.7 崩溃场景与恢复策略矩阵

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-32 所示，以下矩阵总结了不同崩溃场景下 MVStore 的恢复行为和保证：

```text
如图 9-37 所示，┌──────────────────────────────────────────────────────────────────┐
│              崩溃场景与恢复策略矩阵                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  崩溃点                    │ 现象        │ 恢复策略   │ 数据保证    │
│  ─────────────────────────┼────────────┼──────────┼───────────  │
│                           │            │          │              │
│  写入 Chunk 数据中崩溃      │ Chunk 不完整│ footer    │ 最多丢失    │
│  (fileChannel.write 失败)  │            │ 校验失败  │ 一个 Chunk  │
│                           │            │ 跳过该    │ 的数据      │
│                           │            │ Chunk    │              │
│  ─────────────────────────┼────────────┼──────────┼───────────  │
│                           │            │          │              │
│  写入 Store Header        │ Block 0    │ 读取     │ 无数据丢失   │
│  Block 0 后崩溃           │ 损坏,      │ Block 1  │ (上一个      │
│                           │ Block 1    │ 的旧     │ Chunk 仍    │
│                           │ 完整       │ header   │ 有效)       │
│  ─────────────────────────┼────────────┼──────────┼───────────  │
│                           │            │          │              │
│  写入 Store Header        │ Block 1    │ 使用     │ 完全恢复     │
│  Block 1 后崩溃           │ 损坏,      │ Block 0  │              │
│                           │ Block 0    │          │              │
│                           │ 完整       │          │              │
│  ─────────────────────────┼────────────┼──────────┼───────────  │
│                           │            │          │              │
│  commit() 期间崩溃         │ undo log   │ 重新     │ 不丢失已     │
│  (flip BitSet 后、遍历     │ 标记为     │ 执行     │ 提交的       │
│  中)                      │ COMMITTED  │ commit   │ 数据        │
│                           │            │ (幂等)   │              │
│  ─────────────────────────┼────────────┼──────────┼───────────  │
│                           │            │          │              │
│  事务写入 undo log 后      │ undo log   │ 回滚     │ 无影响      │
│  崩溃 (未提交)             │ 标记为 OPEN│ 撤销     │ (未提交      │
│                           │            │ 修改     │ 的数据不    │
│                           │            │          │ 可见)       │
│  ─────────────────────────┼────────────┼──────────┼───────────  │
│                           │            │          │              │
│  紧缩期间崩溃              │ 新旧两个    │ 旧 Chunk │ 无数据丢失   │
│  (compact 写入完成,        │ Chunk 都   │ 仍然     │ (新 Chunk   │
│   未更新 header)           │ 存在       │ 有效     │ 会在下次     │
│                           │            │          │ 紧缩时清理)  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-37: 崩溃场景与恢复策略矩阵**

## 9.8 压缩与加密

如图 9-33 所示，MVStore 支持可选的页面级压缩和文件级加密。

### 9.8.1 压缩

```text
本节速览：9.8.1 压缩

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

**核心文件**: `compress/CompressLZF.java`, `compress/CompressDeflate.java`

压缩发生在 `Page.write()` 序列化之后，压缩整个键值数据区域：

| 压缩级别 | 压缩器 | 类型标志 | 特点 |
|---------|--------|---------|------|
| 0 | 无 | - | 不压缩 |
| 1 | `CompressLZF` | `PAGE_COMPRESSED` | 快速压缩/解压，适合 CPU 密集场景 |
| 2 | `CompressDeflate` | `PAGE_COMPRESSED_HIGH` | 更高压缩比，但速度较慢 |

值得注意的是，**压缩是机会主义的**：只有当压缩后的数据长度加上头部开销确实小于原始数据时，才存储压缩版本。这确保了即使是不可压缩的数据也不会膨胀。

### 9.8.2 加密

```text
本节速览：9.8.2 加密

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

**核心文件**: `org/h2/store/fs/encrypt/FilePathEncrypt.java`

文件级加密通过文件系统层（`FilePath`）的包装实现，使用 `FileStore` 的加密参数：

文件路径格式:  org/h2/store/fs/encrypt/FilePathEncrypt.java
加密模式:     XTS (基于 AES)
加密粒度:     页面级
密钥来源:     char[] encryptionKey (使用后立即清除: Arrays.fill(encryptionKey, (char) 0))
```text

XTS 模式是存储加密的标准模式（IEEE 1619），它将数据划分为固定大小的块，每个块使用不同的 tweak key 加密，从而支持随机访问解密，而无需解密整个文件。

```
```java
// MVStore.java:288-303
char[] encryptionKey = (char[]) config.remove("encryptionKey");
try {
    if (fileStoreShallBeOpen) {
        boolean readOnly = config.containsKey("readOnly");
        fileStore.open(fileName, readOnly, encryptionKey);
    }
    fileStore.bind(this);
    metaMap = fileStore.start();
} finally {
    if (encryptionKey != null) {
        Arrays.fill(encryptionKey, (char) 0);  // 立即清除密钥
    }
}
```

加密密钥在使用后立即清除（用 0 填充），防止密钥残留在内存中。文件一旦加密，整个文件（包括 store header）都是加密的，因此即使文件遭窃取也无法读取。

### 9.8.3 压缩流水线

```text
本节速览：9.8.3 压缩流水线

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

MVStore 的压缩发生在 Page 序列化的最后阶段。以下流程图展示了从原始键值数据到最终磁盘格式的完整处理过程：

```text
如图 9-38 所示，┌──────────────────────────────────────────────────────────────────┐
│              MVStore 压缩流水线 (Page.write 中的数据流)             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  原始数据:                                                        │
│  ┌──────────────────────────────────────┐                        │
│  │ keys: [K1, K2, ..., Kn]              │                        │
│  │ values: [V1, V2, ..., Vn] (Leaf)     │                        │
│  │ children: [Ref1, ..., Refn+1] (NonLeaf)│                       │
│  └──────────────────────────────────────┘                        │
│         │                                                         │
│         │ 第 1 步: 序列化 (DataUtils.writeVarInt, writeString...)  │
│         ▼                                                         │
│  ┌──────────────────────────────────────┐                        │
│  │ keys 序列化 → 字节数组                │                         │
│  │ values 序列化 → 字节数组              │                         │
│  └──────────────────────────────────────┘                        │
│         │                                                         │
│         │ 第 2 步: 合并到 buffer                                   │
│         ▼                                                         │
│  ┌──────────────────────────────────────┐                        │
│  │ [keys_bytes][values_bytes]           │                         │
│  │ len = expLen                         │                         │
│  └──────────────────────────────────────┘                        │
│         │                                                         │
│         │ 第 3 步: expLen > 16?                                   │
│         ▼                                                         │
│  ┌─────┴─────┐                                                   │
│  │ 否         │ 是                                                │
│  └─────┬─────┘                                                   │
│        │                                                          │
│        ▼                                                          │
│  保持不变            │                                            │
│  (不压缩)             │ 第 4a 步: 压缩等级 1 → CompressLZF        │
│                      │    ┌─────────────────────────┐            │
│                      │    │ LZF 压缩 (快速)           │            │
│                      │    │ 输出: compLen1 字节       │            │
│                      │    └─────────────────────────┘            │
│                      │                                            │
│                      │ 第 4b 步: 压缩等级 2 → CompressDeflate     │
│                      │    ┌─────────────────────────┐            │
│                      │    │ Deflate 压缩 (高压缩比)    │            │
│                      │    │ 输出: compLen2 字节       │            │
│                      │    └─────────────────────────┘            │
│                      │                                            │
│                      │ 第 5 步: 判断压缩收益                        │
│                      ▼                                            │
│              ┌──────────────┐                                     │
│              │ compLen +     │                                     │
│              │ header <      │                                     │
│              │ expLen?       │                                     │
│              └──────┬───────┘                                     │
│                 ┌───┴───┐                                        │
│                 ▼       ▼                                        │
│           ┌────────┐ ┌────────┐                                  │
│           │ 使用    │ │ 使用    │                                  │
│           │ 压缩    │ │ 原始    │                                  │
│           │ 版本    │ │ 数据    │                                  │
│           └────────┘ └────────┘                                  │
│                                                                  │
│  最终写入 Chunk 的数据:                                            │
│  ┌──────────────────────────────────────────────┐                │
│  │ [Page Header][type byte][压缩/原始数据][Footer]│               │
│  │ type byte: bit 1=1 if compressed             │                │
│  │ type byte: bit 2=1 if deflate compressed     │                │
│  └──────────────────────────────────────────────┘                │
│                                                                  │
│  LZF vs Deflate 对比:                                             │
│  ┌──────────────┬──────────┬──────────┬──────────┐               │
│  │ 压缩器       │ 压缩速度  │ 解压速度  │ 压缩比    │               │
│  ├──────────────┼──────────┼──────────┼──────────┤               │
│  │ 无           │ N/A      │ N/A      │ 1:1      │               │
│  │ LZF          │ 300 MB/s │ 500 MB/s │ 2:1~3:1 │               │
│  │ Deflate      │ 50 MB/s  │ 100 MB/s │ 3:1~5:1 │               │
│  └──────────────┴──────────┴──────────┴──────────┘               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-38: MVStore 压缩流水线**

### 9.8.4 XTS-AES 加密/解密流程

```text
本节速览：9.8.4 XTS-AES 加密/解密流程

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-34 所示，MVStore 的文件加密使用 XTS-AES 模式，这是一种专为存储加密设计的模式。以下流程图展示了加密和解密的数据路径：

```text
如图 9-39 所示，┌──────────────────────────────────────────────────────────────────┐
│           XTS-AES 加密/解密流程 (FilePathEncrypt)                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  XTS 模式概述:                                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ XTS = XEX (Xor-Encrypt-Xor) + Tweakable Block Cipher  │        │
│  │ IEEE 1619 标准                                         │        │
│  │ 每个 16 字节块使用不同的 tweak 值 (块号 × 多项式)        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  密钥派生:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ encryptionKey (char[])                                      │        │
│  │   │                                                        │        │
│  │   ├── KDF (密钥派生函数)                                      │        │
│  │   │                                                        │        │
│  │   ├── Key 1 (AES 加密密钥)                                   │        │
│  │   └── Key 2 (Tweak 密钥)                                    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  加密流程 (写路径):                                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 明文块 P (16 字节)                                          │        │
│  │   │                                                        │        │
│  │   ├── 计算 Tweak = blockNumber × α^(blockNumber mod 2^128)  │        │
│  │   │   (α 是 GF(2^128) 中的本原多项式)                        │        │
│  │   │                                                        │        │
│  │   ├── T ← AES_encrypt(Key2, Tweak)                         │        │
│  │   │                                                        │        │
│  │   ├── PP = P XOR T                                         │        │
│  │   │                                                        │        │
│  │   ├── CC = AES_encrypt(Key1, PP)                           │        │
│  │   │                                                        │        │
│  │   └── C = CC XOR T                                         │        │
│  │       │                                                    │        │
│  │       └── 密文块 C 写入文件                                 │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  解密流程 (读路径):                                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 密文块 C (16 字节)                                          │        │
│  │   │                                                        │        │
│  │   ├── 计算 Tweak = blockNumber × α^(blockNumber mod 2^128)  │        │
│  │   │                                                        │        │
│  │   ├── T ← AES_encrypt(Key2, Tweak)                         │        │
│  │   │                                                        │        │
│  │   ├── CC = C XOR T                                         │        │
│  │   │                                                        │        │
│  │   ├── PP = AES_decrypt(Key1, CC)                           │        │
│  │   │                                                        │        │
│  │   └── P = PP XOR T                                         │        │
│  │       │                                                    │        │
│  │       └── 明文块 P 返回给上层                               │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  加密对文件布局的影响:                                             │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ Store Header 也是加密的, 因此无法通过 hexdump 查看    │        │
│  │ 加密以 block 为单位 (1 block = 4096 字节)             │        │
│  │ 不对单独 page 加密, 而是对 page 所在的整个 block 加密  │        │
│  │ 这使得随机访问解密只需解密一个 block                    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  性能开销:                                                        │
│  XTS 加密: 每 16 字节需要 2 次 AES 操作 (加密 key + tweak)        │
│  vs 无加密: 约 50-100% 的性能损失 (取决于 CPU 的 AES-NI 支持)     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-39: XTS-AES 加密/解密流程**

### 9.8.5 性能权衡分析

```text
本节速览：9.8.5 性能权衡分析

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 9-35 所示，压缩和加密都会带来性能开销。选择正确的配置需要根据具体的工作负载特征来决定：

```text
如图 9-40 所示，┌──────────────────────────────────────────────────────────────────┐
│          压缩与加密性能权衡分析 (典型值, 基于 Intel i7)             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  写吞吐量 (MB/s, 值越大越好):                                     │
│                                                                  │
│  无压缩  ──────────────────────────────────────── 350 MB/s       │
│  LZF     ────────────────────────────────── 250 MB/s             │
│  Deflate ────────────────── 100 MB/s                             │
│  XTS     ───────────────────── 150 MB/s                          │
│  LZF+XTS ────────────── 110 MB/s                                 │
│  Deflate+XTS ──────── 60 MB/s                                    │
│                                                                  │
│  读吞吐量 (MB/s, 值越大越好):                                     │
│                                                                  │
│  无压缩  ───────────────────────────────────── 400 MB/s          │
│  LZF     ────────────────────────────────── 300 MB/s              │
│  Deflate ──────────────────── 150 MB/s                            │
│  XTS     ─────────────────────── 180 MB/s                         │
│  LZF+XTS ───────────────── 150 MB/s                               │
│  Deflate+XTS ─────────── 90 MB/s                                  │
│                                                                  │
│  空间节省 (相对无压缩):                                            │
│                                                                  │
│  文本数据:                                                        │
│  LZF:     节省 50-65%                                            │
│  Deflate: 节省 60-80%                                            │
│                                                                  │
│  二进制数据 (序列化对象):                                          │
│  LZF:     节省 20-40%                                            │
│  Deflate: 节省 30-50%                                            │
│                                                                  │
│  已压缩数据 (图片、视频):                                          │
│  LZF:     节省 0-5% (机会主义算法确保不膨胀)                       │
│  Deflate: 节省 0-8%                                              │
│                                                                  │
│  选择建议:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 场景                        │ 推荐配置                │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │ OLTP (高并发读写)           │ 关压缩, 关加密          │        │
│  │ 嵌入式设备 (CPU 受限)        │ LZF 压缩, 关加密       │        │
│  │ 分析型查询 (读多写少)        │ Deflate 压缩, 关加密   │        │
│  │ 敏感数据 (合规要求)          │ LZF + XTS 加密        │        │
│  │ 归档 (空间优先)              │ Deflate + XTS 加密    │        │
│  │ 纯内存数据库                 │ 关压缩, 关加密         │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 9-40: 压缩与加密性能权衡分析**

## 9.9 本章小结

如图 9-36 所示，本章从存储引擎的视角，深入剖析了 H2 Database 的 MVStore 持久化机制，涵盖文件结构、数据组织、事务保证、崩溃恢复及安全存储等核心议题。

- MVStore 采用 MVMap (B-Tree)、Chunk 与 FileStore 三层架构，以无锁数据结构（AtomicReference + CAS）实现高效的并发读取，同时通过版本化根指针支持 MVCC 语义。
- B-Tree 实现区分 Leaf 与 NonLeaf 两类页面，页面通过 `pos` 字段的状态转变（0 未持久化、1 已删除、>1 已持久化）实现精细化的生命周期管理。
- Chunk 是 MVStore 一次原子写入的基本单元，其文件布局包含页面对照表（ToC）与带校验和的 Footer，结构化的元数据设计为后续的垃圾回收与空间复用提供了支撑。
- MVStore 采用隐式日志策略，以 B-Tree 版本化根指针结合原子性 Chunk 写入替代传统 WAL，而事务层的 Undo Log 提供了回滚未完成事务的能力。
- 检查点机制以异步后台线程将脏页面批量写入新 Chunk，触发条件基于未保存内存阈值，回收策略通过 `unusedAtVersion` 与 `collectPriority` 实现垃圾 Chunk 的自动清理。
- 崩溃恢复依赖双冗余 Store Header 与 Chunk Footer 中的 Fletcher 校验和，从最新完整 Chunk 重建 B-Tree，并利用 Undo Log 回滚未提交事务，从而保证完整性与一致性。
- 压缩与加密是 MVStore 的可选安全与存储优化机制：压缩支持 LZF 与 Deflate 两级，采用机会主义策略确保不引起空间膨胀；加密采用 XTS-AES 模式，密钥生命周期结束后立即清除，防止敏感信息残留。

## 9.10 延展阅读

- 文件格式与 Page/Chunk 布局：H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
- LIRS 缓存与压缩策略：H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#caching`)
- 持久性已知问题：H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#durability_problems`)
- 本书第6章§6.1-6.3 — B-Tree/CoW/MVCC 算法基础
- 本书第6章§6.4-6.7 — Chunk/LIRS/FreeSpace/MVStore 平衡算法
- 本书第10章《锁实现与并发控制》 — 并发访问与事务隔离

---

# 第10章 锁实现与并发控制

> **本章导读**: 本章分析 H2 的锁机制和并发控制实现，涵盖表级锁的实现细节、事务隔离级别、MVCC 并发控制以及锁超时和死锁检测等实用主题。
> **前置知识**: 第6章§6.3（MVCC 多版本并发控制）；第5章§5.5（事务提交/回滚与 Undo Log）；第7章（SQL 执行流程中的锁获取）
> **章节要点**:
> - 理解 H2 的表级锁实现和锁升级机制
> - 掌握 5 种事务隔离级别的行为差异
> - 熟悉 MVCC 模式下读写不互斥的实现
> - 了解锁超时、死锁检测等实用机制
> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

H2 Database 的 MVStore 引擎实现了多层次的并发控制机制：表级锁、行级 MVCC、CAS 无锁读和文件级锁，共同构成了完整的并发控制体系。

## 10.1 MVTable 表级锁

**核心文件**: `org/h2/mvstore/db/MVTable.java`

`MVTable` 是 MVStore 存储模式下的表实现，它提供了表级的共享锁（读锁）和排他锁（写锁）机制。

### 10.1.1 锁状态字段

```text
本节速览：10.1.1 锁状态字段

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`MVTable.java` 第 114-133 行定义了锁的核心数据结构：

```java
// 排他锁持有者 (单个 session)
private volatile SessionLocal lockExclusiveSession;

// 共享锁持有者集合 (多个 session)
private final ConcurrentHashMap<SessionLocal, SessionLocal> lockSharedSessions
        = new ConcurrentHashMap<>();

// 等待锁的队列 (FIFO, 防止饥饿)
private final ArrayDeque<SessionLocal> waitingSessions = new ArrayDeque<>();
```

**三个关键设计点**：

1. **`lockExclusiveSession` 使用 `volatile`**——确保无锁快速读取。在获取读锁时，如果没有排他锁持有者，可以立即返回而无需进入同步块。
2. **`lockSharedSessions` 使用 `ConcurrentHashMap`**——支持并发添加/移除共享锁，且利用它作为 `ConcurrentHashSet`（值为自身）。
3. **`waitingSessions` 使用 FIFO 队列**——防止写锁饥饿。Java 的 `synchronized` 锁是偏向的（biased），直接使用 `wait/notify` 可能导致某些线程长期得不到锁。

```text
如图 10-1 所示，┌──────────────────────────────────────────────────────────────────┐
│              MVTable 锁数据结构关系图                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MVTable 实例                                                     │
│  ┌──────────────────────────────────────────────────────┐        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ lockExclusiveSession (volatile SessionLocal)  │      │        │
│  │  │   ┌─────────┬─────────────────────────┐      │      │        │
│  │  │   │ null    │ 无排他锁持有者           │      │      │        │
│  │  │   │ session │ 单个 session 持有排他锁  │      │      │        │
│  │  │   └─────────┴─────────────────────────┘      │      │        │
│  │  │   → volatile 保证所有线程的可见性              │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ lockSharedSessions (ConcurrentHashMap)        │      │        │
│  │  │   ┌──────────┐  ┌──────────┐  ┌──────────┐  │      │        │
│  │  │   │ SessionA │  │ SessionB │  │ SessionC │  │      │        │
│  │  │   │     →     │  │     →     │  │     →     │  │      │        │
│  │  │   │ self     │  │ self     │  │ self     │  │      │        │
│  │  │   └──────────┘  └──────────┘  └──────────┘  │      │        │
│  │  │   → 多个 session 可以同时持有共享锁            │      │        │
│  │  │   → ConcurrentHashMap 支持无锁并发添加移除      │      │        │
│  │  │   → 作为 ConcurrentHashSet 使用 (值为自身)     │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ waitingSessions (ArrayDeque<SessionLocal>)    │      │        │
│  │  │                                                │      │        │
│  │  │  队首 ← [Session_X | Session_Y | Session_Z] → 队尾  │        │
│  │  │   (下一个获取锁)    (最后加入的)                   │      │        │
│  │  │                                                │      │        │
│  │  │   → FIFO 队列, 防止写锁饥饿                      │      │        │
│  │  │   → synchronized 块中操作                        │      │        │
│  │  │   → doLock1() 检查自己是否是队首                   │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  锁获取条件:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 读锁成功条件: lockExclusiveSession == null              │        │
│  │             (不需要检查 waitingSessions 或 shared)      │        │
│  │                                                        │        │
│  │ 写锁成功条件: isQueueFirst                              │        │
│  │             && lockExclusiveSession == null             │        │
│  │             && lockSharedSessions.isEmpty()             │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-1: MVTable 锁数据结构关系图**

### 10.1.2 锁状态机
```text
                    如图 10-2 所示，READ LOCK (共享锁)
                         │
                    ┌────┴────┐
                    ▼         ▼
            [no exclusive]  [exclusive held]
                    │              │
              ┌─────┘        ┌─────┘
              ▼              ▼
        return false   进入同步块
              │        加入等待队列
              │        doLock1()
              │            │
              │        ┌───┴────┐
              │        ▼        ▼
              │    [超时]    [队列首位 + 无排他]
              │    throw     doLock2()
              │    LOCK_        │
              │    TIMEOUT  putIfAbsent(shared)
              │              return OK
              │
              │
                    WRITE LOCK (排他锁)
                         │
                    ┌────┴────┐
                    ▼         ▼
            [无 shared/excl]  [已被其他 session 持有]
                    │              │
            set exclusive     进入同步块
            session           加入等待队列
              │              doLock1()
              │                  │
              │              ┌───┴────┐
              │              ▼        ▼
              │          [超时]    [队列首位 + 无排他]
              │          throw    doLock2()
              │          LOCK_      │
              │          TIMEOUT  [shared 计数=0]
              │                    │
              │                set exclusive
              │                return OK
              │
              │           [shared 计数>0]
              │           (可能包含自己)
              │                │
              │           ┌────┴────┐
              │           ▼         ▼
              │       [仅自己]   [还有他人]
              │       升级锁     返回 false
              │                 继续等待
```
**图 10-2: MVTable 锁状态机**

### 10.1.3 lock() 方法的快速路径

```text
本节速览：10.1.3 lock() 方法的快速路径

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

```java
// MVTable.java:167-201
public boolean lock(SessionLocal session, int lockType) {
    if (database.getLockMode() == Constants.LOCK_MODE_OFF) {
        session.registerTableAsUpdated(this);
        return false;
    }
    if (lockType == Table.READ_LOCK && lockExclusiveSession == null) {
        return false;    // 快速路径：无排他锁时，读锁立即成功
    }
    if (lockExclusiveSession == session) {
        return true;     // 快速路径：已经持有排他锁
    }
    if (lockType != Table.EXCLUSIVE_LOCK && lockSharedSessions.containsKey(session)) {
        return true;     // 快速路径：已经持有共享锁
    }
    synchronized (this) {
        // 再次检查（双重检查锁定模式）
        // ...
        waitingSessions.addLast(session);
        doLock1(session, lockType);
    }
}
```

如图 10-1 所示，**双重检查锁定（Double-checked locking）**：在进入同步块前后都检查条件，这是为了在无竞争的情况下避免进入同步块，提高性能。

### 10.1.4 doLock1() 的等待循环

```text
本节速览：10.1.4 doLock1() 的等待循环

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

`doLock1()` 方法（第 203-246 行）实现了等待-重试循环：

1. 检查当前 session 是否是队列首位，且没有排他锁持有者
2. 如果是，调用 `doLock2()` 尝试获取锁
3. 如果否，检查死锁
4. 检查超时，抛出 `LOCK_TIMEOUT_1` 异常
5. 使用 `wait(sleep)` 进入等待（sleep 时间取 `DEADLOCK_CHECK` 和剩余超时时间的较小值，确保能及时检测死锁）

```java
checkDeadlock = true;  // 只在第一次超时检测后启用死锁检测
// ...
long sleep = Math.min(Constants.DEADLOCK_CHECK, (max - now) / 1_000_000L);
if (sleep == 0) sleep = 1;
wait(sleep);
```

### 10.1.5 unlock() 的唤醒逻辑

```text
本节速览：10.1.5 unlock() 的唤醒逻辑

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

```java
// MVTable.java:295-324
public void unlock(SessionLocal s) {
    if (lockExclusiveSession == s) {
        lockExclusiveSession = null;
        // 清理 debug 信息
    } else {
        lockSharedSessions.remove(s);
    }
    if (lockType != Table.READ_LOCK && !waitingSessions.isEmpty()) {
        synchronized (this) {
            notifyAll();  // 唤醒等待者
        }
    }
}
```

解锁时如果还有等待者，调用 `notifyAll()` 唤醒所有等待线程，而不是 `notify()`，因为可能同时有读锁和写锁等待者需要竞争。

### 10.1.6 调试支持

```text
本节速览：10.1.6 调试支持

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

当 `SysProperties.THREAD_DEADLOCK_DETECTOR` 启用时，MVTable 使用 `DebuggingThreadLocal` 跟踪锁状态：

```java
// MVTable.java:57-67
public static final DebuggingThreadLocal<String> WAITING_FOR_LOCK;
public static final DebuggingThreadLocal<ArrayList<String>> EXCLUSIVE_LOCKS;
public static final DebuggingThreadLocal<ArrayList<String>> SHARED_LOCKS;
```

这些 ThreadLocal 变量使得在死锁发生时可以打印出每个线程的锁等待链，方便调试。

### 10.1.7 共享锁获取流程

```text
本节速览：10.1.7 共享锁获取流程

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

当一个 session 请求读锁（共享锁）时，MVTable 的锁获取逻辑根据当前锁的状态采取不同的路径。以下展示了从无锁状态到多个共享锁持有者的完整流程：

```text
┌──────────────────────────────────────────────────────────────────┐
│              共享锁获取流程 (多个并发读者)                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  初始状态: 无锁                                                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ lockExclusiveSession = null                          │        │
│  │ lockSharedSessions = {}                              │        │
│  │ waitingSessions = []                                 │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  读者 A 请求读锁:                                                  │
│  lock(A, READ_LOCK)                                               │
│       │                                                          │
│       ▼                                                          │
│  lockExclusiveSession == null? → true                             │
│       │                                                          │
│       └── 快速路径: return false (立即成功)                         │
│                                                                  │
│  读者 B 请求读锁:                                                  │
│  lock(B, READ_LOCK)                                               │
│       │                                                          │
│       ▼                                                          │
│  lockExclusiveSession == null? → true                             │
│       │                                                          │
│       └── 快速路径: return false (立即成功)                         │
│                                                                  │
│  状态:                                                            │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ lockExclusiveSession = null                          │        │
│  │ lockSharedSessions = {A, B}                          │        │
│  │ waitingSessions = []                                 │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  写者 C 请求写锁 (此时有共享锁):                                    │
│  lock(C, EXCLUSIVE_LOCK)                                          │
│       │                                                          │
│       ▼                                                          │
│  lockExclusiveSession == null? → true                             │
│  lockExclusiveSession == C? → false                               │
│  lockSharedSessions.containsKey(C)? → false                       │
│       │                                                          │
│       ▼                                                          │
│  synchronized(this) → 进入同步块                                  │
│  waitingSessions.addLast(C)                                       │
│  doLock1(C, EXCLUSIVE_LOCK)                                       │
│       │                                                          │
│       ▼                                                          │
│  waitingSessions.peekFirst() == C? → true                         │
│  lockExclusiveSession == null? → true                             │
│  lockSharedSessions.isEmpty()? → false (有 A 和 B)                │
│       │                                                          │
│       ▼                                                          │
│  wait(DEADLOCK_CHECK) → 阻塞等待                                  │
│                                                                  │
│  读者 D 请求读锁 (写者在等待):                                      │
│  lock(D, READ_LOCK)                                               │
│       │                                                          │
│       ▼                                                          │
│  lockExclusiveSession == null? → true                             │
│       │                                                          │
│       └── 快速路径: return false (因为无排他锁)                    │
│                                                                  │
│  状态:                                                            │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ lockExclusiveSession = null                          │        │
│  │ lockSharedSessions = {A, B, D} (D 插队成功)           │        │
│  │ waitingSessions = [C] (C 在等待)                      │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  注意: 读锁快速路径不检查 waitingSessions!                          │
│  这意味着新的读者可以在写者等待时插队获取读锁                         │
│  这是有意设计的: 读锁不阻塞读锁                                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-3: 共享锁获取流程**

### 10.1.8 排他锁竞争流程

```text
本节速览：10.1.8 排他锁竞争流程

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-3 所示，写锁（排他锁）的获取比读锁复杂得多。当一个 session 请求排他锁时，它必须等待所有当前持有者（包括共享锁和排他锁）释放：

```text
┌──────────────────────────────────────────────────────────────────┐
│              排他锁竞争流程（写者等待多个读者）                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  初始状态: 2 个读者持有共享锁                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ lockSharedSessions = {Session_A, Session_B}          │        │
│  │ lockExclusiveSession = null                          │        │
│  │ waitingSessions = []                                 │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  写者 X 请求排他锁:                                               │
│       │                                                          │
│       ▼                                                          │
│  lock(X, EXCLUSIVE_LOCK)                                          │
│       │                                                          │
│       ├─ 快速路径 1: lockExclusiveSession == null? → true         │
│       │   继续                                                    │
│       ├─ 快速路径 2: lockExclusiveSession == X? → false          │
│       ├─ 快速路径 3: lockSharedSessions.containsKey(X)? → false  │
│       │                                                          │
│       ▼                                                          │
│  synchronized(MVTable.this)                                       │
│       │                                                          │
│       ├─ waitingSessions.addLast(X)                               │
│       │                                                          │
│       ▼                                                          │
│  doLock1(X, EXCLUSIVE_LOCK):                                      │
│       │                                                          │
│       ├─ isQueueFirst(X)? → true                                 │
│       ├─ lockExclusiveSession == null? → true                     │
│       ├─ lockSharedSessions.isEmpty()? → false (A 和 B 还在)     │
│       │         ↓                                                │
│       │  等待解除，阻塞                                          │
│       │                                                          │
│  ... Session_A 释放读锁 ...                                       │
│       │                                                          │
│       ├─ lockSharedSessions.remove(A)                             │
│       ├─ waitingSessions 非空 → notifyAll()                      │
│       │                                                          │
│       ▼                                                          │
│  doLock1(X, EXCLUSIVE_LOCK) 被唤醒:                                │
│       │                                                          │
│       ├─ isQueueFirst(X)? → true                                 │
│       ├─ lockExclusiveSession == null? → true                     │
│       ├─ lockSharedSessions.isEmpty()? → false (B 还在)          │
│       │         ↓                                                │
│       │  继续等待                                                │
│       │                                                          │
│  ... Session_B 释放读锁 ...                                       │
│       │                                                          │
│       ├─ lockSharedSessions.remove(B)                             │
│       ├─ waitingSessions 非空 → notifyAll()                      │
│       │                                                          │
│       ▼                                                          │
│  doLock1(X, EXCLUSIVE_LOCK) 被唤醒:                                │
│       │                                                          │
│       ├─ isQueueFirst(X)? → true                                 │
│       ├─ lockExclusiveSession == null? → true                     │
│       ├─ lockSharedSessions.isEmpty()? → true                    │
│       │         ↓                                                │
│       ├─ doLock2(X, EXCLUSIVE_LOCK):                              │
│       │   ├─ lockExclusiveSession = X                             │
│       │   └─ return OK                                            │
│       │                                                          │
│       ▼                                                          │
│  lock(X) 返回 true → X 持有排他锁                                  │
│                                                                  │
│  最终状态:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ lockSharedSessions = {}                              │        │
│  │ lockExclusiveSession = Session_X                     │        │
│  │ waitingSessions = []                                 │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-4: 排他锁竞争流程**

### 10.1.9 锁超时处理

> **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#transaction_isolation`)
> 说明了锁超时的行为：连接等待锁超时后抛出锁超时异常。

```text
本节速览：10.1.9 锁超时处理

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-4 所示，MVTable 的锁等待支持超时机制。每个数据库连接可以设置锁超时时间（默认 `Constants.LOCK_TIMEOUT`，通常为 2000ms）。当 session 在等待队列中超过超时时间仍未获取到锁时，会抛出超时异常：

```text
┌──────────────────────────────────────────────────────────────────┐
│              锁超时处理流程                                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  doLock1(session, lockType):                                      │
│       │                                                          │
│       ▼                                                          │
│  计算开始时间: start = System.nanoTime()                         │
│       │                                                          │
│       ▼                                                          │
│  循环开始:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │                                                      │        │
│  │  checkDeadlock = (iteration > threshold)?            │        │
│  │  isQueueFirst = waitingSessions.peekFirst() == session│        │
│  │  noExclusive = (lockExclusiveSession == null)         │        │
│  │  noShared = lockSharedSessions.isEmpty()              │        │
│  │                                                      │        │
│  │  isQueueFirst && noExclusive && (noShared || upgrade)?│        │
│  │       ├── 是 → doLock2(session, lockType) → return   │        │
│  │       └── 否 → 继续等待                               │        │
│  │                                                      │        │
│  │  now = System.nanoTime()                              │        │
│  │  remaining = lockTimeout - (now - start)              │        │
│  │                                                      │        │
│  │  remaining <= 0?                                      │        │
│  │       ├── 是 → throw LOCK_TIMEOUT_1                  │        │
│  │       └── 否 → sleep = min(DEADLOCK_CHECK, remaining)│        │
│  │              wait(sleep) → 被 notifyAll() 唤醒        │        │
│  │              └── 回到循环开始                          │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  超时异常信息:                                                     │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ DbException.get(ErrorCode.LOCK_TIMEOUT_1,            │        │
│  │     "Table \"TABLE_NAME\" cannot be locked.          │        │
│  │      Waiting for ...");                              │        │
│  │                                                      │        │
│  │ 该异常会被上层事务管理代码捕获, 触发事务回滚           │        │
│  │ 事务回滚后释放所有已持有的锁                           │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  超时 vs 死锁:                                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 场景              │ 检测方式            │ 异常类型     │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │ 正常锁竞争 (写者   │ 超时检测             │ LOCK_TIMEOUT│        │
│  │ 等待长时间事务)    │                     │             │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │ 死锁 (循环等待)    │ DFS 死锁检测         │ DEADLOCK    │        │
│  │                   │ (checkDeadlock=true) │             │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-5: 锁超时处理流程**

### 10.1.10 锁升级流程 (共享锁 → 排他锁)

```text
本节速览：10.1.10 锁升级流程 (共享锁 到 排他锁)

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-5 所示，MVTable 支持锁升级——同一个 session 可以从共享锁升级为排他锁，而不需要先释放共享锁再重新获取。这在 `doLock2()` 中实现：

```text
┌──────────────────────────────────────────────────────────────────┐
│              锁升级流程 (共享锁 → 排他锁)                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  场景: Session_A 持有共享锁, 现在需要排他锁（例如 SELECT FOR UPDATE）│
│                                                                  │
│  lock(A, EXCLUSIVE_LOCK)                                          │
│       │                                                          │
│       ▼                                                          │
│  快速路径:                                                        │
│  lockExclusiveSession == A? → false (当前不是排他持有者)           │
│  lockSharedSessions.containsKey(A)? → true (但 A 是共享持有者)     │
│       │                                                          │
│       ▼                                                          │
│  synchronized(this)                                               │
│       │                                                          │
│       ├─ 此时 lockSharedSessions = {A, Session_B}                │
│       ├─ waitingSessions.addLast(A)                               │
│       │                                                          │
│       ▼                                                          │
│  doLock1(A, EXCLUSIVE_LOCK):                                      │
│       │                                                          │
│       ├─ isQueueFirst(A)? → true                                 │
│       ├─ lockExclusiveSession == null? → true                     │
│       ├─ lockSharedSessions.isEmpty()? → false (有 A 和 B)       │
│       │         ↓                                                │
│       │  lockSharedSessions.size() == 1?                          │
│       │  (即: 仅剩 A 自己持有共享锁)                               │
│       │      ├─ 是 → 可以升级!                                   │
│       │      │   ├─ 移除自己的共享锁                              │
│       │      │   ├─ lockExclusiveSession = A                     │
│       │      │   └─ return OK                                    │
│       │      │                                                   │
│       │      └─ 否 → 还有其他人持有共享锁                          │
│       │          ├─ wait() → 等待 B 释放                         │
│       │          └─ B 释放后, 再次尝试                             │
│       │                                                          │
│       ▼                                                          │
│  lock(A) 返回 true → A 持有排他锁                                  │
│                                                                  │
│  对比: 非升级场景 (Session_C 排他锁+已是排他持有者):                │
│  lock(C, EXCLUSIVE_LOCK):                                         │
│  lockExclusiveSession == C? → true                                │
│       └── 快速路径: return true (可重入)                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-6: 锁升级流程**

## 10.2 TransactionMap 行级 MVCC

如图 10-6 所示，**核心文件**: `org/h2/mvstore/tx/TransactionMap.java`, `mvstore/tx/TxDecisionMaker.java`

`TransactionMap` 是 `MVMap` 的事务性包装器，提供了基于 MVCC 的行级并发控制。它通过 `VersionedValue` 为每个键值对维护多个版本，支持快照隔离（Snapshot Isolation——事务开始时的数据快照作为整个事务期间的一致读视图，写入时采用 first-committer-wins 策略解决冲突）。

### 10.2.1 VersionedValue 结构

```text
本节速览：10.2.1 VersionedValue 结构

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

每个 MVMap 的值是一个 `VersionedValue<V>`，包含：

VersionedValue<V>:
  operationId: long    ← 编码 (transactionId << 38 | logId)
  value: V             ← 当前值 (null 表示已删除)
  committedValue: V    ← 提交前的值 (用于回滚和空读)

`operationId` 的高 26 位是事务 ID，低 38 位是该事务内的操作序号。当 `operationId == NO_OPERATION_ID` 时，表示该记录是已提交的稳定版本。

```text
┌──────────────────────────────────────────────────────────────────┐
│              VersionedValue 结构与 operationId 编码                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  VersionedValue<V> (包级私有, 不可变)                              │
│  ┌──────────────────────────────────────────────────────┐        │
│  │                                                        │        │
│  │  operationId (long)                                     │        │
│  │  ┌──────────────────────┬──────────────────────────┐    │        │
│  │  │ transactionId (26位)  │     logId (38位)          │    │        │
│  │  │ 范围: 0 ~ 67,108,863  │ 范围: 0 ~ 274,877,906,943│    │        │
│  │  │ 最大约 6700 万并发事务 │ 每事务约 2750 亿操作       │    │        │
│  │  └──────────────────────┴──────────────────────────┘    │        │
│  │                                                        │        │
│  │  NO_OPERATION_ID = 0 (或负数) ← 表示已提交的稳定版本     │        │
│  │                                                        │        │
│  │  value (V)                                               │        │
│  │    ├── 当前值 (最新的写入)                                 │        │
│  │    └── null 表示该键已被删除                               │        │
│  │                                                        │        │
│  │  committedValue (V)                                      │        │
│  │    ├── 最后一次提交前的值                                  │        │
│  │    ├── 用于事务回滚: 恢复到此值                             │        │
│  │    └── 用于空读: 其他事务看到 committedValue 而非 value     │        │
│  │                                                        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  状态转换:                                                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 写入时:                                                 │        │
│  │  VersionedValue(operationId = tx << 38 | logId,        │        │
│  │                  value = newValue,                     │        │
│  │                  committedValue = oldCommittedValue)    │        │
│  │                                                        │        │
│  │ 提交时 (CommitDecisionMaker):                            │        │
│  │  VersionedValue(operationId = NO_OPERATION_ID,          │        │
│  │                  value = currentValue,                  │        │
│  │                  committedValue = null)                 │        │
│  │  → operationId 被清除, 表示已提交                        │        │
│  │  → committedValue 不再需要, 设为 null                   │        │
│  │                                                        │        │
│  │ 回滚时 (RollbackDecisionMaker):                          │        │
│  │  恢复到 undo log 中记录的旧 VersionedValue               │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-7: VersionedValue 结构与 operationId 编码**

### 10.2.2 快照隔离 (Snapshot Isolation)

```text
本节速览：10.2.2 快照隔离 (Snapshot Isolat

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-7 所示，`TransactionMap.getFromSnapshot()`（第 462-509 行）根据隔离级别选择不同的数据可见性策略：

```text
┌──────────────────────────────────────────────────┐
│  行级数据可见性判断                                │
├──────────────────────────────────────────────────┤
│                                                   │
│  读取键 K 的值 V                                   │
│       │                                           │
│       ▼                                           │
│  map.get(root, K) → VersionedValue                │
│       │                                           │
│       ▼                                           │
│  operationId == NO_OPERATION_ID?                   │
│       ├── yes → 已提交，直接返回 getCurrentValue() │
│       └── no → 属于某事务                          │
│                  │                                │
│                  ▼                                │
│  transactionId == 当前事务?                        │
│       ├── yes → 可见 (自己的修改)                   │
│       └── no → 检查 committingTransactions         │
│                    │                               │
│                    ▼                               │
│  在 committingTransactions 中?                      │
│       ├── yes → 已提交，返回 getCurrentValue()     │
│       └── no → 未提交，返回 getCommittedValue()    │
│                  (空读)                            │
│                                                   │
└──────────────────────────────────────────────────┘
```
**图 10-8: 行级数据可见性判断**

### 10.2.3 useSnapshot() 无锁快照

```text
本节速览：10.2.3 useSnapshot() 无锁快照

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

如图 10-8 所示，`useSnapshot()`（第 560-576 行）是 MVCC 的核心，它使用了一种"忙等"协方差法来获取一致性的快照：

```java
<R> R useSnapshot(BiFunction<RootReference<K,VersionedValue<V>>, long[], R> snapshotConsumer) {
    AtomicReference<VersionedBitSet> holder = transaction.store.committingTransactions;
    VersionedBitSet committingTransactions = holder.get();
    while (true) {
        VersionedBitSet prevCommittingTransactions = committingTransactions;
        RootReference<K, VersionedValue<V>> root = map.getRoot();
        committingTransactions = holder.get();
        if (committingTransactions == prevCommittingTransactions) {
            return snapshotConsumer.apply(root, committingTransactions.bits);
        }
    }
}
```

这个循环的目的是获取**逻辑一致**的快照——`root`（B-Tree 根引用）和 `committingTransactions`（正在提交的事务集合）必须在同一时刻捕获。因为这两个变量是独立变化的，所以需要循环等待"沉默期"。

### 10.2.4 写入冲突检测 (TxDecisionMaker)

```text
本节速览：10.2.4 写入冲突检测 (TxDecisionMak

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

**核心文件**: `org/h2/mvstore/tx/TxDecisionMaker.java`

`TxDecisionMaker.decide()` 方法（第 73-116 行）是写入冲突检测的核心：

```java
public Decision decide(VersionedValue<V> existingValue, VersionedValue<V> providedValue) {
    if (existingValue == null || existingValue.getOperationId() == NO_OPERATION_ID) {
        // 情况 1: 条目不存在或已提交 → 可以直接写入
        return logAndDecideToPut(existingValue, committedValue);
    }

    int blockingId = TransactionStore.getTransactionId(existingValue.getOperationId());

    if (isThisTransaction(blockingId)) {
        // 情况 2: 同一条事务的修改 → 覆盖写入（通常不会发生，因为是 append）
        return logAndDecideToPut(existingValue, committedValue);
    }

    if (isCommitted(blockingId)) {
        // 情况 3: 正被标识为已提交的事务 → 视为已提交
        return logAndDecideToPut(currentValue, committedValue);
    }

    if (getBlockingTransaction() != null) {
        // 情况 4: 其他未提交事务持有 → ABORT + 等待
        return Decision.ABORT;
    }

    if (isRepeatedOperation(id)) {
        // 情况 5: 不完整关闭的残留 → 覆盖
        return logAndDecideToPut(committedValue, committedValue);
    }

    // 情况 6: 阻塞事务已关闭 → REPEAT 重试
    return Decision.REPEAT;
}
```

写入冲突发生时，`TransactionMap.set()`（第 355-390 行）的处理逻辑：

```java
private V set(Object key, TxDecisionMaker<K,V> decisionMaker, int timeoutMillis) {
    do {
        result = map.operate(k, null, decisionMaker);  // 尝试原子操作
        blockingTransaction = decisionMaker.getBlockingTransaction();

        if (decision != Decision.ABORT || blockingTransaction == null) {
            return result.getCurrentValue();            // 成功或非阻塞失败
        }

        decisionMaker.reset();
    } while (transaction.waitFor(blockingTransaction, mapName, key, timeoutMillis));
    // 超时 → 抛出异常
    throw DataUtils.newMVStoreException(ERROR_TRANSACTION_LOCKED, ...);
}
```

这种 `do-while` 重试模式允许在等待阻塞事务完成后自动重试，而不需要客户端处理重试逻辑。

### 10.2.5 Undo Log 的写前记录

```text
本节速览：10.2.5 Undo Log 的写前记录

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

在 `TxDecisionMaker.logAndDecideToPut()` 中，写入数据前必须先记录 undo 日志：

```java
// TxDecisionMaker.java:162-166
Decision logAndDecideToPut(VersionedValue<V> valueToLog, V lastValue) {
    undoKey = transaction.log(mapId, key, valueToLog);  // 先写 undo log
    this.lastValue = lastValue;
    return setDecision(Decision.PUT);                     // 再决定 PUT
}
```

这使得 `TransactionStore` 能够在回滚时恢复每个键的旧值。

### 10.2.6 useSnapshot() 原子对捕获

```text
本节速览：10.2.6 useSnapshot() 原子对捕获

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`useSnapshot()` 方法的核心挑战是：B-Tree 的根引用（`RootReference`）和 `committingTransactions` BitSet 是两个独立变化的变量。要获得逻辑一致的快照，必须在同一时刻捕获它们。MVStore 通过循环检测"版本静止期"来实现：

```text
┌──────────────────────────────────────────────────────────────────┐
│              useSnapshot() 原子对捕获机制                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Thread A (调用 useSnapshot):     Thread B (提交事务):             │
│                                    │                             │
│  v1 = cTx.get() → {}               │                             │
│       │                            │                             │
│       │                            │ flip(tx5, true)             │
│       │                            │ cTx → {5} (version++)      │
│       │                            │                             │
│  root = map.getRoot() → R5         │                             │
│       │                            │                             │
│       │                            │ root = map.getRoot() → R6   │
│       │                            │                             │
│  v2 = cTx.get() → {5}             │                             │
│       │                            │                             │
│  v1 != v2? → true                  │                             │
│  (检测到变化, 重新尝试!)            │                             │
│       │                            │                             │
│  ─── 重新循环 ───                   │                             │
│       │                            │                             │
│  v1 = cTx.get() → {5}             │                             │
│       │                            │                             │
│       │                            │ flip(tx5, false)             │
│       │                            │ cTx → {} (version++)        │
│       │                            │                             │
│  root = map.getRoot() → R6         │                             │
│       │                            │                             │
│  v2 = cTx.get() → {}              │                             │
│       │                            │                             │
│  v1 != v2? → true                  │                             │
│  (又变了, 再试!)                    │                             │
│       │                            │                             │
│  ─── 重新循环 ───                   │                             │
│       │                            │                             │
│  v1 = cTx.get() → {}              │                             │
│  root = map.getRoot() → R6         │                             │
│  v2 = cTx.get() → {}              │                             │
│       │                            │                             │
│  v1 == v2? → true!                │                             │
│       │                            │                             │
│       ▼                            │                             │
│  返回: (R6, {})  ← 逻辑一致!      │                             │
│                                                                  │
│  关键洞察:                                                        │
│  由于 root 和 cTx 在不同时间更新, 无法一次捕获两者                   │
│  但 cTx 的变化比 root 频繁 (每次 commit 都变)                      │
│  当 cTx 在捕获期间不变时, root 也一定是静止的                       │
│  → 循环直到 cTx 版本不变                                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-9: useSnapshot() 原子对捕获机制**

### 10.2.7 TxDecisionMaker.decide() 完整决策流程

```text
本节速览：10.2.7 TxDecisionMaker.decid

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-9 所示，`TxDecisionMaker.decide()` 是 MVCC 写入冲突检测的核心方法。它根据现有值的状态决定是否允许写入。以下流程图展示了所有可能的分支：

```text
┌──────────────────────────────────────────────────────────────────┐
│           TxDecisionMaker.decide() 完整决策树                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  decide(existingValue, providedValue)                             │
│       │                                                          │
│       ▼                                                          │
│  existingValue == null OR                                         │
│  existingValue.getOperationId() == NO_OPERATION_ID?               │
│       │                                                          │
│       ├── YES → 情况 1: 条目不存在或已提交                        │
│       │   └── logAndDecideToPut(existingValue, committedValue)   │
│       │       └── return Decision.PUT                             │
│       │                                                          │
│       └── NO → 存在未提交的修改                                   │
│                  │                                                │
│                  ▼                                                │
│           blockingId = getTransactionId(opId)                      │
│                  │                                                │
│           isThisTransaction(blockingId)?                           │
│                  │                                                │
│           ├── YES → 情况 2: 自己修改的                           │
│           │   └── logAndDecideToPut(...) → PUT                    │
│           │                                                      │
│           └── NO → 其他事务的修改                                 │
│                  │                                                │
│           isCommitted(blockingId)?                                 │
│                  │                                                │
│           ├── YES → 情况 3: 阻塞事务已提交                       │
│           │   └── logAndDecideToPut(currentValue, committedValue) │
│           │       └── return Decision.PUT                         │
│           │                                                      │
│           └── NO → 阻塞事务未提交                                 │
│                  │                                                │
│           getBlockingTransaction() != null?                        │
│                  │                                                │
│           ├── YES → 情况 4: 另一个活动事务持有                    │
│           │   └── return Decision.ABORT                           │
│           │       (set() 方法将 waitFor 和重试)                   │
│           │                                                      │
│           └── NO → 阻塞事务信息未知                               │
│                  │                                                │
│           isRepeatedOperation(id)?                                 │
│                  │                                                │
│           ├── YES → 情况 5: 不完整关闭残留                        │
│           │   └── logAndDecideToPut(committedValue, committedValue)│
│           │       └── return Decision.PUT                         │
│           │                                                      │
│           └── NO → 情况 6: 阻塞事务已关闭                        │
│               └── return Decision.REPEAT                          │
│                   (set() 会立即重试操作)                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-10: TxDecisionMaker.decide() 完整决策树**

## 10.3 死锁检测算法

如图 10-10 所示，**核心文件**: `org/h2/mvstore/db/MVTable.java` 第 866-912 行

MVTable 使用 DFS（深度优先搜索）检测表级锁死锁。死锁检测在 `doLock1()` 的等待循环中触发，并且在第一次超时检测后开始。

### 10.3.1 算法原理

```text
本节速览：10.3.1 算法原理

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

```java
public ArrayList<SessionLocal> checkDeadlock(SessionLocal session,
        SessionLocal clash, Set<SessionLocal> visited) {
    synchronized (getClass()) {
        if (clash == null) { clash = session; visited = new HashSet<>(); }
        else if (clash == session) return new ArrayList<>(0);   // 找到环！
        else if (visited.contains(session)) return null;         // 有环但别人发现了
        visited.add(session);
        // 检查所有共享锁持有者的等待链
        for (SessionLocal s : lockSharedSessions.keySet()) {
            Table t = s.getWaitForLock();
            if (t != null) {
                ArrayList<SessionLocal> error = t.checkDeadlock(s, clash, visited);
                if (error != null) { error.add(session); return error; }
            }
        }
        // 检查排他锁持有者
        if (error == null && lockExclusiveSession != null) {
            Table t = lockExclusiveSession.getWaitForLock();
            if (t != null) {
                error = t.checkDeadlock(lockExclusiveSession, clash, visited);
                if (error != null) error.add(session);
            }
        }
        return error;
    }
}
```
```text
如图 10-11 所示，┌──────────────────────────────────────────────────────────────────┐
│              DFS 死锁检测算法 — checkDeadlock() 执行流程             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  checkDeadlock(session, clash, visited)                           │
│       │                                                          │
│       ▼                                                          │
│  synchronized(MVTable.class)                                      │
│       │                                                          │
│       ├── clash == null?                                        │
│       │   └── 是 → 初始化: clash = session, visited = {}          │
│       │                                                          │
│       ├── clash == session? (找到环?)                             │
│       │   ├── 是 → return new ArrayList<>(0)  ← 环已发现!        │
│       │   └── 否 → 继续                                           │
│       │                                                          │
│       ├── visited.contains(session)? (重复访问?)                   │
│       │   ├── 是 → return null  ← 别人会发现这个环                │
│       │   └── 否 → visited.add(session)                          │
│       │                                                          │
│       ▼                                                          │
│  遍历 lockSharedSessions (当前表的所有共享锁持有者)                  │
│       │                                                          │
│       ├── for each SessionLocal s:                                │
│       │   ├── t = s.getWaitForLock()  ← s 在等待哪张表?           │
│       │   │                                                      │
│       │   ├── t != null?                                          │
│       │   │   ├── 是 → error = t.checkDeadlock(s, clash, visited) │
│       │   │   │         → 递归到 s 正在等待的表                     │
│       │   │   │         → 从 s 继续探索等待链                       │
│       │   │   │                                                   │
│       │   │   │   ├── error != null → 收到死锁路径                 │
│       │   │   │   │   ├── error.add(session) ← 追加当前 session   │
│       │   │   │   │   └── return error                            │
│       │   │   │   │                                               │
│       │   │   │   └── error == null → 无环, 继续下一个 s            │
│       │   │   │                                                   │
│       │   │   └── 否 → s 不在等待任何表, 跳过                       │
│       │   │                                                       │
│       ▼                                                           │
│  检查 lockExclusiveSession (排他锁持有者)                            │
│       │                                                           │
│       ├── lockExclusiveSession != null?                            │
│       │   └── t = lockExclusiveSession.getWaitForLock()           │
│       │       └── 递归检查 (同共享锁流程)                            │
│       │                                                           │
│       ▼                                                           │
│  return null  ← 从当前 session 出发未发现死锁                       │
│                                                                  │
│  关键特性:                                                         │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 算法: DFS 遍历锁等待图                                │        │
│  │ 复杂度: O(V+E), V=session 数, E=等待边数              │        │
│  │ 触发时机: doLock1() 中第一次超时检测后                  │        │
│  │ 返回值: null=无环, 非空列表=死锁路径                    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-11: DFS 死锁检测算法执行流程**

### 10.3.2 死锁检测示例
```text
线程 A 持有表 T1 的排他锁，等待表 T2 的排他锁
线程 B 持有表 T2 的排他锁，等待表 T1 的排他锁

DFS 检测过程:
                             clash = A (初始)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
    B.getWaitForLock() = T1         A.getWaitForLock() = T2
    checkDeadlock(B, A, {A})        checkDeadlock(A, A, {A, B})
           │                                │
           ▼                                ▼
    T1: lockSharedSessions +     clash == session ?
    lockExclusiveSession              │ YES!
    → 检查 holder                      ▼
      A.getWaitForLock() = T2  返回 new ArrayList<>(0)
      → checkDeadlock(A, A,     → 追加 B → 追加 A
           {A, B})                              │
           ↓ 返回 [A, B, A]     ← 环已发现!
```

```text
ASCII 死锁链:
                           排他锁
  Session A ───────────────▶ Table T1
       ▲                        │
       │                    getWaitForLock?
       │                        │
       │                        ▼
       │                   Session B
       │                        │
       │                    getWaitForLock?
       │                        │
       │                        ▼
       │                   Table T2
       │                        │
       │                    getWaitForLock?
       │                        │
       └────────────────── Session A  ← 环!

  如图 10-12 所示，死锁链: A ─→ T1 ─→ B ─→ T2 ─→ A
```
**图 10-12: 死锁检测示例**

### 10.3.3 死锁解除

```text
本节速览：10.3.3 死锁解除

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

当检测到死锁时，当前等待的 session 会抛出 `DbException.get(ErrorCode.DEADLOCK_1)`：

```java
// MVTable.java:216-220
if (checkDeadlock) {
    ArrayList<SessionLocal> sessions = checkDeadlock(session, null, null);
    if (sessions != null) {
        throw DbException.get(ErrorCode.DEADLOCK_1,
                getDeadlockDetails(sessions, lockType));
    }
}
```

如图 10-11 所示，选为牺牲的 session 会释放它已持有的所有锁（通过异常传播，最终由上层事务管理代码回滚），使得线程死锁链得以解除，等待中的 session 可以继续执行。

### 10.3.4 DFS 锁等待图遍历

```text
本节速览：10.3.4 DFS 锁等待图遍历

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

MVTable 的死锁检测算法是 DFS 在锁等待图上的遍历。等待图的节点是 session，边从等待者指向持有者。以下展示了更复杂的场景：

```text
┌──────────────────────────────────────────────────────────────────┐
│          DFS 锁等待图遍历 — 3 个 Session 的死锁                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  锁等待图:                                                        │
│                                                                  │
│       排他锁                 排他锁                 排他锁         │
│  S1 ────────────▶ T1 ◀──────────── S2 ────────────▶ T2            │
│  ▲                               │                               │
│  │                               │                               │
│  │                           排他锁                               │
│  └────────────────────────────── T3 ◀─── S3 (等待)                │
│                                                                  │
│  S1 持有 T1 排他锁, 等待 T2 排他锁                                │
│  S2 持有 T2 排他锁, 等待 T3 排他锁                                │
│  S3 持有 T3 排他锁, 等待 T1 排他锁                                │
│                                                                  │
│  DFS 遍历 (从 S3 开始检测死锁):                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ checkDeadlock(S3, null, null)                        │        │
│  │   ├─ clash = S3, visited = {}                        │        │
│  │   ├─ visited.add(S3)                                 │        │
│  │   ├─ S3.getWaitForLock() = T1                        │        │
│  │   │   ↓                                              │        │
│  │   ├─ T1.checkDeadlock(S3, S3, {S3})                 │        │
│  │   │   ├─ lockExclusiveSession = S1                   │        │
│  │   │   ├─ S1.getWaitForLock() = T2                    │        │
│  │   │   │   ↓                                          │        │
│  │   │   ├─ T2.checkDeadlock(S1, S3, {S3})             │        │
│  │   │   │   ├─ lockExclusiveSession = S2               │        │
│  │   │   │   ├─ S2.getWaitForLock() = T3                │        │
│  │   │   │   │   ↓                                      │        │
│  │   │   │   ├─ T3.checkDeadlock(S2, S3, {S3})         │        │
│  │   │   │   │   ├─ lockExclusiveSession = S3           │        │
│  │   │   │   │   ├─ S3.getWaitForLock() = T1            │        │
│  │   │   │   │   │   ↓                                  │        │
│  │   │   │   │   ├─ T1.checkDeadlock(S3, S3, {S3})     │        │
│  │   │   │   │   │   ├─ clash == session → 找到环!      │        │
│  │   │   │   │   │   └─ return [] (空列表)              │        │
│  │   │   │   │   │                                       │        │
│  │   │   │   │   ├─ 收到 [] → 追加 S3                    │        │
│  │   │   │   │   └─ return [S3]                         │        │
│  │   │   │   │                                           │        │
│  │   │   │   ├─ 收到 [S3] → 追加 S2                     │        │
│  │   │   │   └─ return [S3, S2]                         │        │
│  │   │   │                                               │        │
│  │   │   ├─ 收到 [S3, S2] → 追加 S1                     │        │
│  │   │   └─ return [S3, S2, S1]                          │        │
│  │   │                                                   │        │
│  │   └─ 收到死锁路径 → 追加 S3 (起始 session)            │        │
│  │      final = [S3, S2, S1, S3]                         │        │
│  │      → throw DEADLOCK_1                               │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-13: DFS 锁等待图遍历 — 3 个 Session 死锁**

### 10.3.5 死锁解除流程

```text
本节速览：10.3.5 死锁解除流程

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-13 所示，当检测到死锁时，被选为牺牲的 session 需要释放所有已持有的锁，让等待锁的 session 继续执行：

```text
┌──────────────────────────────────────────────────────────────────┐
│              死锁解除与事务回滚流程                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  步骤 1: 检测死锁                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ Session_A 在 doLock1() 中检测到死锁                   │        │
│  │ checkDeadlock(A, null, null) 返回非空列表 [A,B,A]    │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 2: 抛出异常                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ throw DbException.get(DEADLOCK_1,                    │        │
│  │     "Session A: Table T1 lock. Session B: Table T2") │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 3: 异常向上传播                                              │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ doLock1() → lock() → MVTable.lockMVTable()            │        │
│  │   → Command.update() → Session.commit() 捕获异常      │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 4: 事务回滚                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ Session_A.rollback():                                │        │
│  │   ├─ 遍历 undo log, 撤销所有修改                       │        │
│  │   ├─ 释放所有已持有的锁 (MVTable.unlock())            │        │
│  │   │   └─ unlock() → notifyAll()                      │        │
│  │   └─ 清空 undo log                                   │        │
│  └──────────────────────────────────────────────────────┘        │
│         │                                                         │
│         ▼                                                         │
│  步骤 5: 唤醒等待者                                                │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ unlock() 中的 notifyAll() 唤醒队列中的等待 session    │        │
│  │ 被唤醒的 session 重新尝试获取锁                       │        │
│  │ 死锁链已打破, 锁获取成功                              │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  死锁解除后的锁等待图:                                             │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 前:  S1→T1→S2→T2→S3→T3→S1 (环)                     │        │
│  │ 回滚 S1 后:                                           │        │
│  │     S1 释放 T1 的锁                                    │        │
│  │     S3 获取到 T1 的锁 (S3 是 T1 的等待者)              │        │
│  │     S2 等待 T3 (S3 持有)                              │        │
│  │     环被打破！                                         │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-14: 死锁解除与事务回滚流程**

## 10.4 隔离级别实现

如图 10-14 所示，H2 的 MVStore 引擎通过 `TransactionMap` 和快照机制实现了 SQL 标准的四种隔离级别，外加 SNAPSHOT 隔离级别。

**核心文件**: `org/h2/mvstore/tx/TransactionMap.java`, `org/h2/engine/IsolationLevel.java`

### 10.4.1 隔离级别对比

```text
本节速览：10.4.1 隔离级别对比

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

```text
┌─────────────────────────────────────────────────────────────┐
│  隔离级别实现对比                                            │
├──────────────┬──────────────────┬───────────────────────────┤
│  隔离级别     │ 实现类/策略       │ 行为特征                    │
├──────────────┼──────────────────┼───────────────────────────┤
│ READ_UNCOMMITTED│ 直接返回值    │ 能读取到其他事务未提交的数据 │
│              │ (getCurrentValue)│ 脏读可能                   │
├──────────────┼──────────────────┼───────────────────────────┤
│ READ_COMMITTED│ 读快照(语句级)  │ 只能读取已提交的数据        │
│              │ + 空读          │ 不可重复读可能              │
├──────────────┼──────────────────┼───────────────────────────┤
│ REPEATABLE_READ│ 事务开始快照  │ 同一事务内多次读取结果一致  │
│              │ + 自己的修改    │ 幻读可能                   │
├──────────────┼──────────────────┼───────────────────────────┤
│ SNAPSHOT     │ 事务开始快照    │ 完全的快照隔离              │
│              │ (完整快照)      │ 无幻读，无不可重复读        │
├──────────────┼──────────────────┼───────────────────────────┤
│ SERIALIZABLE │ 快照 + 冲突检测 │ 可串行化，检测读写冲突      │
│              │ (RepeatableRead)│ 可能串行化失败              │
└──────────────┴──────────────────┴───────────────────────────┘
```
**图 10-15: 隔离级别实现对比**

### 10.4.2 TransactionMap 的迭代器实现

```text
本节速览：10.4.2 TransactionMap 的迭代器实现

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-15 所示，TransactionMap 根据隔离级别使用不同的迭代器：

**READ_UNCOMMITTED -> `UncommittedIterator`**：
始终返回数据的当前值，即使其他事务尚未提交。这是性能最高但最不安全的级别。

**READ_COMMITTED -> `CommittedIterator`**：
每次读取时获取当前已提交数据的快照。如果在同一事务内两次读取之间其他事务提交了修改，第二次读到的结果可能不同（不可重复读）。

```java
// TransactionMap.getFromSnapshot() → READ_COMMITTED (第 486-489 行)
default:
    Snapshot<K,VersionedValue<V>> snapshot = getSnapshot();
    return getFromSnapshot(snapshot.root, snapshot.committingTransactions, key);
```

其中 `getSnapshot()` 返回 `statementSnapshot`（语句级快照），每次获取时可能不同。

**REPEATABLE_READ / SNAPSHOT -> `RepeatableIterator`**：
在事务首次读取时创建快照（`promoteSnapshot()`），此后所有读取基于同一快照：

```java
// TransactionMap.java:535-539
void promoteSnapshot() {
    if (snapshot == null) {
        snapshot = statementSnapshot;  // 将语句快照提升为事务快照
    }
}
```

**SERIALIZABLE**：基于 `RepeatableIterator`，但增加额外的写-写冲突检测。`RepeatableReadLockDecisionMaker` 在 `TxDecisionMaker` 基础上会检查读取是否与已提交的更新冲突。

```text
┌──────────────────────────────────────────────────────────────────┐
│              TransactionMap 迭代器实现对比                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  迭代器类型        │ 隔离级别           │ 快照策略      │ 读现象     │
│  ─────────────────┼──────────────────┼─────────────┼──────────   │
│                    │                   │              │              │
│  Uncommitted      │ READ_UNCOMMITTED  │ 无快照        │ 脏读可能     │
│  Iterator         │                   │ getCurrent()  │              │
│                    │                   │              │              │
│  ─────────────────┼──────────────────┼─────────────┼──────────     │
│                    │                   │              │              │
│  Committed        │ READ_COMMITTED    │ 语句级快照    │ 不可重复读   │
│  Iterator         │                   │ (每次读取刷新) │              │
│                    │                   │              │              │
│  ─────────────────┼──────────────────┼─────────────┼──────────     │
│                    │                   │              │              │
│  Repeatable       │ REPEATABLE_READ   │ 事务级快照    │ 幻读可能     │
│  Iterator         │                   │ (promoteSnapshot)│             │
│                    │                   │              │              │
│  ─────────────────┼──────────────────┼─────────────┼──────────     │
│                    │                   │              │              │
│  Repeatable       │ SNAPSHOT          │ 事务开始快照  │ 无幻读       │
│  Iterator         │                   │ (begin时)     │              │
│                    │                   │              │              │
│  ─────────────────┼──────────────────┼─────────────┼──────────     │
│                    │                   │              │              │
│  Repeatable       │ SERIALIZABLE      │ 事务开始快照  │ 无幻读       │
│  Iterator +       │                   │ + Serializable│ + 串行化     │
│  ConflictCheck    │                   │   冲突检测     │ 失败可能     │
│                                                                  │
│  数据可见性算法:                                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 对于每个键值对, 迭代器检查:                            │        │
│  │  1. operationId == NO_OPERATION_ID? → 已提交, 可见    │        │
│  │  2. transactionId == 当前事务? → 自己的修改, 可见     │        │
│  │  3. 在 committingTransactions 中? → 视为已提交       │        │
│  │  4. 否则 → 未提交, 跳过或返回 committedValue          │        │
│  │                                                      │        │
│  │ 不同迭代器的区别在于 "快照" 的创建时机:                │        │
│  │ - Uncommitted: 不检查 operationId                    │        │
│  │ - Committed: 每语句创建新快照                         │        │
│  │ - Repeatable: 首次读取创建快照, 后续复用               │        │
│  │ - Snapshot: 事务开始时创建快照, 后续复用               │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-16: TransactionMap 迭代器实现对比**

### 10.4.3 语句快照与事务快照

```text
本节速览：10.4.3 语句快照与事务快照

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

如图 10-16 所示，TransactionMap 维护两个快照：

```java
// TransactionMap.java:61-66
private Snapshot<K,VersionedValue<V>> snapshot;           // 事务快照
private Snapshot<K,VersionedValue<V>> statementSnapshot;  // 语句快照
```

- **statementSnapshot**：在每个语句开始时创建（或重置）
- **snapshot**：在事务中首次写入或显式设置时创建

```java
// TransactionMap.java:523-529
Snapshot<K,VersionedValue<V>> getSnapshot() {
    return snapshot == null ? createSnapshot() : snapshot;
}

Snapshot<K,VersionedValue<V>> getStatementSnapshot() {
    return statementSnapshot == null ? createSnapshot() : statementSnapshot;
}
```

对于 REPEATABLE_READ 及更高隔离级别，`snapshot` 一旦创建就不会改变，保证了可重复读。

### 10.4.4 迭代器选择决策树

```text
本节速览：10.4.4 迭代器选择决策树

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

TransactionMap 根据隔离级别选择不同的迭代器类型。以下决策树展示了完整的迭代器选择逻辑：

```text
┌──────────────────────────────────────────────────────────────────┐
│              TransactionMap 迭代器选择决策树                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TransactionMap.iterator(key, isolationLevel)                     │
│       │                                                          │
│       ▼                                                          │
│  isolationLevel?                                                  │
│       │                                                          │
│       ├── READ_UNCOMMITTED ───────────────────────────────────┐  │
│       │   │                                                    │  │
│       │   ▼                                                    │  │
│       │  new UncommittedIterator(map, root, cTx)               │  │
│       │   │                                                    │  │
│       │   ├── getCurrentValue() 直接返回 (不过滤 operationId)   │  │
│       │   ├── 能看到所有未提交的修改                              │  │
│       │   ├── 高性能: 不需要版本检查                             │  │
│       │   └── 脏读风险: 可能读到回滚的数据                       │  │
│       │                                                        │  │
│       ├── READ_COMMITTED ────────────────────────────────────┐  │
│       │   │                                                    │  │
│       │   ▼                                                    │  │
│       │  new CommittedIterator(map, statementSnapshot)          │  │
│       │   │                                                    │  │
│       │   ├── 每次创建新的 statementSnapshot                     │  │
│       │   ├── 过滤 operationId, 只返回已提交的值                 │  │
│       │   ├── 同一事务内多次调用可能得到不同结果                  │  │
│       │   └── 不可重复读 (Non-Repeatable Read) 可能             │  │
│       │                                                        │  │
│       ├── REPEATABLE_READ ──────────────────────────────────┐  │
│       │   │                                                    │  │
│       │   ▼                                                    │  │
│       │  new RepeatableIterator(map, transactionSnapshot)       │  │
│       │   │                                                    │  │
│       │   ├── promoteSnapshot() 将语句快照提升为事务快照         │  │
│       │   ├── 同一事务内永远使用同一快照                         │  │
│       │   ├── 不可重复读被消除                                  │  │
│       │   ├── 幻读 (Phantom Read) 仍然可能                      │  │
│       │   └── 写入时使用 RepeatableReadLockDecisionMaker        │  │
│       │                                                        │  │
│       ├── SNAPSHOT ─────────────────────────────────────────┐  │
│       │   │                                                    │  │
│       │   ▼                                                    │  │
│       │  new RepeatableIterator(map, transactionSnapshot)       │  │
│       │   │                                                    │  │
│       │   ├── 与 REPEATABLE_READ 使用相同迭代器                  │  │
│       │   ├── 但快照在事务开始时创建 (不是首次读取时)             │  │
│       │   ├── 幻读也被消除 (因为是事务开始快照)                   │  │
│       │   └── 写入时检测写-写冲突                               │  │
│       │                                                        │  │
│       └── SERIALIZABLE ────────────────────────────────────┐  │
│           │                                                    │  │
│           ▼                                                    │  │
│          new RepeatableIterator(map, transactionSnapshot)       │  │
│           │                                                    │  │
│           ├── 与 REPEATABLE_READ 使用相同迭代器                  │  │
│           ├── 但增加 SerializableChecker 在读后验证              │  │
│           ├── 如果读取范围在事务期间被其他事务修改 → 失败         │  │
│           └── 可能抛出 SERIALIZATION_FAILURE                    │  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-17: TransactionMap 迭代器选择决策树**

### 10.4.5 隔离级别对比: 读现象

```text
本节速览：10.4.5 隔离级别对比: 读现象

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-17 所示，不同的隔离级别在不同的并发场景下会出现不同的读现象（脏读、不可重复读、幻读）。以下对比展示了各种隔离级别在不同场景下的行为：

```text
┌──────────────────────────────────────────────────────────────────┐
│      READ_UNCOMMITTED vs READ_COMMITTED vs REPEATABLE_READ       │
│                        隔离级别对比实验                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  场景 1: 脏读 (Dirty Read)                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 时间  │ 事务 A                      │ 事务 B         │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │ T1   │ BEGIN                       │ BEGIN          │        │
│  │ T2   │                             │ UPDATE x=200   │        │
│  │ T3   │ SELECT x                    │                │        │
│  │ T4   │                             │ ROLLBACK       │        │
│  │      │                             │ (x 回到 100)   │        │
│  │      │                             │                │        │
│  │      │ READ_UNCOMMITTED: 读到 200 (脏读! 被回滚了)   │        │
│  │      │ READ_COMMITTED:    读到 100 (正确的已提交值)   │        │
│  │      │ REPEATABLE_READ:   读到 100                   │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  场景 2: 不可重复读 (Non-Repeatable Read)                          │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 时间  │ 事务 A                      │ 事务 B         │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │ T1   │ BEGIN                       │ BEGIN          │        │
│  │ T2   │ SELECT x → 100             │                │        │
│  │ T3   │                             │ UPDATE x=200   │        │
│  │ T4   │                             │ COMMIT         │        │
│  │ T5   │ SELECT x → ?               │                │        │
│  │      │                             │                │        │
│  │      │ READ_UNCOMMITTED: 200 (看到最新但可能脏)     │        │
│  │      │ READ_COMMITTED:    200 (快照变了)            │        │
│  │      │ REPEATABLE_READ:   100 (同一事务快照)         │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  场景 3: 幻读 (Phantom Read)                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 时间  │ 事务 A                      │ 事务 B         │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │ T1   │ BEGIN                       │ BEGIN          │        │
│  │ T2   │ SELECT COUNT(*) → 100      │                │        │
│  │ T3   │                             │ INSERT (new)   │        │
│  │ T4   │                             │ COMMIT         │        │
│  │ T5   │ SELECT COUNT(*) → ?        │                │        │
│  │      │                             │                │        │
│  │      │ ALL (包括 REPEATABLE_READ): 101             │        │
│  │      │ 因为快照不防止幻读!                           │        │
│  │      │ SNAPSHOT 隔离级别: 100 (防止幻读)            │        │
│  │      │ SERIALIZABLE:    100 (防止幻读)              │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-18: 隔离级别对比实验**

### 10.4.6 快照创建时机

```text
本节速览：10.4.6 快照创建时机

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-18 所示，不同隔离级别的快照创建时机不同，这直接影响了数据的可见性范围：

```text
┌──────────────────────────────────────────────────────────────────┐
│              快照创建时机 (按隔离级别)                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  READ_UNCOMMITTED: 无快照                                        │
│  ─────────────────────────────────────────────                   │
│  时间线: ──[语句1]────[语句2]────[语句3]──                       │
│  快照:    无, 总是读取最新值                                     │
│                                                                  │
│  READ_COMMITTED: 语句级快照                                      │
│  ─────────────────────────────────────────────                   │
│  时间线: ──[语句1]────[语句2]────[语句3]──                       │
│               ↓         ↓         ↓                              │
│           快照1      快照2      快照3                             │
│           (每个语句开始都创建新快照)                               │
│                                                                  │
│  REPEATABLE_READ: 首次读取时创建事务快照                          │
│  ─────────────────────────────────────────────                   │
│  时间线: ──[语句1]────[语句2]────[语句3]──                       │
│               ↓                                                  │
│        promoteSnapshot() → 事务快照                              │
│             └── 复用同一快照 ── 复用 ──                           │
│                                                                  │
│  SNAPSHOT: 事务开始时创建快照                                     │
│  ─────────────────────────────────────────────                   │
│  时间线: ──BEGIN────[语句1]────[语句2]────[语句3]──               │
│               ↓                                                  │
│        createSnapshot() → 事务快照                                │
│             └── 复用同一快照 ─────── 复用 ────────               │
│                                                                  │
│  SERIALIZABLE: 事务开始时创建快照                                 │
│  ─────────────────────────────────────────────                   │
│  时间线: ──BEGIN────[语句1]────[语句2]────[语句3]──               │
│               ↓                                                  │
│        createSnapshot() → 事务快照 + 额外冲突检测                  │
│             └── 复用同一快照 ─────── 复用 ────────               │
│             └── 提交时检查 Serializable 冲突                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-19: 快照创建时机（按隔离级别）**

## 10.5 RootReference CAS 无锁读

如图 10-19 所示，**核心文件**: `org/h2/mvstore/RootReference.java`, `mvstore/MVMap.java`

MVMap 的根节点使用 `AtomicReference<RootReference>` 管理，这是 MVStore 无锁并发读的核心机制。

### 10.5.1 RootReference 的不可变性

```text
本节速览：10.5.1 RootReference 的不可变性

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`RootReference` 是一个不可变对象（`final` 字段），包含：

```java
// RootReference.java:16-51
public final class RootReference<K,V> {
    public final Page<K,V> root;        // B-Tree 根页面
    public final long version;          // 版本号
    private final byte holdCount;       // 可重入锁计数
    private final long ownerId;         // 锁持有者线程 ID
    volatile RootReference<K,V> previous; // 前一个版本链
    final long updateCounter;           // 成功更新计数
    final long updateAttemptCounter;    // 尝试更新计数
    private final byte appendCounter;   // append buffer 占用量
}
```
```text
┌──────────────────────────────────────────────────────────────────┐
│              RootReference 不可变对象结构                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  RootReference<K,V> (final class, 所有字段 final 或 volatile)      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ root (final Page<K,V>)                        │      │        │
│  │  │   └─ B-Tree 根页面的引用                        │      │        │
│  │  │   └─ 指向当前可见的 B-Tree 最新状态              │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ version (final long)                          │      │        │
│  │  │   └─ 创建时的 MVStore 全局版本号               │      │        │
│  │  │   └─ 用于 MVCC 快照比较                        │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ holdCount (final byte) + ownerId (final long) │      │        │
│  │  │   └─ 可重入写锁计数                           │      │        │
│  │  │   └─ holdCount=0 → 未锁定 (可读)              │      │        │
│  │  │   └─ holdCount>0 → 被 ownerId 线程锁定        │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ previous (volatile RootReference<K,V>)        │      │        │
│  │  │   └─ 指向上一个版本的 RootReference            │      │        │
│  │  │   └─ 构成版本链: v5 → v4 → v3 → ...         │      │        │
│  │  │   └─ volatile: 保证版本链可见性                │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ updateCounter (final long)                    │      │        │
│  │  │   └─ 成功 CAS 更新次数                        │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ updateAttemptCounter (final long)             │      │        │
│  │  │   └─ CAS 尝试总次数 (含失败)                  │      │        │
│  │  │   └─ ratio = attemptCounter / counter        │      │        │
│  │  │   └─ 用于估算竞争程度, 指导退避策略             │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  │  ┌──────────────────────────────────────────────┐      │        │
│  │  │ appendCounter (final byte)                    │      │        │
│  │  │   └─ append buffer 占用量                     │      │        │
│  │  └──────────────────────────────────────────────┘      │        │
│  │                                                        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  不可变性的意义:                                                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 一旦创建, 所有字段不可修改 (除 previous 为 volatile)  │        │
│  │ → 读操作不需要锁: root.get() 后直接读取字段           │        │
│  │ → 写操作创建新对象: CAS 替换整个 RootReference        │        │
│  │ → 旧版本继续可用: 通过 previous 链访问历史版本         │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-20: RootReference 不可变对象结构**

### 10.5.2 CAS 更新机制

```text
本节速览：10.5.2 CAS 更新机制

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-20 所示，`MVMap` 的根引用声明为 `AtomicReference<RootReference>`，所有对 B-Tree 结构的修改都通过 CAS 操作完成：

```java
// MVMap.java:45
private final AtomicReference<RootReference<K,V>> root;
```
```text
┌──────────────────────────────────────────────────┐
│  无锁写入流程 (CAS 循环)                           │
├──────────────────────────────────────────────────┤
│                                                   │
│  1. 获取当前 root: rootRef = root.get()            │
│                                                   │
│  2. 在现有 B-Tree 基础上创建新版本                  │
│     (不修改现有页面，创建新的 Page/NonLeaf 副本)     │
│                                                   │
│  3. 创建新的 RootReference:                        │
│     newRootRef = new RootReference(old, newPage,   │
│                    updateAttemptCounter)            │
│                                                   │
│  4. CAS 更新:                                     │
│     root.compareAndSet(rootRef, newRootRef)         │
│       ├── 成功 → 写入完成                            │
│       └── 失败 → 其他线程已更新，重试                 │
│                                                   │
│  5. CAS 失败时的退避策略:                            │
│     attempt < CPU_COUNT → spin-wait (onSpinWait)   │
│     attempt < 阈值   → Thread.yield()              │
│     否则           → synchronized wait(1ms)        │
│                                                   │
└──────────────────────────────────────────────────┘
```
**图 10-21: 无锁写入流程 (CAS 循环)**

### 10.5.3 三级退避策略

```text
本节速览：10.5.3 三级退避策略

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

如图 10-21 所示，`MVMap.tryLock()`（第 1949-1973 行）实现了三级退避策略：

```java
protected RootReference<K,V> tryLock(RootReference<K,V> rootReference, int attempt) {
    RootReference<K,V> lockedRootReference = rootReference.tryLock(attempt);
    if (lockedRootReference != null) {
        return lockedRootReference;                         // CAS 成功
    }

    if (attempt < CPU_COUNT) {
        Thread.onSpinWait();                                // 级别 1: 自旋等待
    } else {
        int estimatedContention = estimateContention(rootReference, oldRootReference);
        if (attempt < CPU_COUNT + (CPU_COUNT + estimatedContention) / 2) {
            Thread.yield();                                 // 级别 2: 让出 CPU
        } else {
            synchronized (lock) {
                notificationRequested = true;
                lock.wait(1);                               // 级别 3: 阻塞等待
            }
        }
    }
    return null;
}
```

**竞争估算**（`estimateContention()` 第 1975-1988 行）：
根据 `updateAttemptCounter/updateCounter` 的比值估算竞争激烈程度。比值越大，说明 CAS 失败率越高，竞争越激烈，退避的阈值就越低。

### 10.5.4 可重入锁

```text
本节速览：10.5.4 可重入锁

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

RootReference 通过 `holdCount` 和 `ownerId` 实现了可重入锁：

```java
// RootReference.java:78-89 (锁构造函数)
private RootReference(RootReference<K,V> r, int attempt) {
    // ...
    assert r.holdCount == 0 || r.ownerId == Thread.currentThread().getId();
    this.holdCount = (byte)(r.holdCount + 1);    // 可重入计数 +1
    this.ownerId = Thread.currentThread().getId();
}
```

- 读操作：不需要锁，直接读取 `root.get()`（无锁）
- 写操作：需要获取写锁（CAS 尝试设置 `holdCount > 0`）
- 可重入：同一个线程可以多次 lock，对应多次 unlock

### 10.5.5 版本链

```text
本节速览：10.5.5 版本链

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

`RootReference.previous` 指向同一 B-Tree 的上一个版本。这构成了一个版本链：

```java
// RootReference.java:39
volatile RootReference<K,V> previous;
```
```text
currentVersion=v5 → v4 → v3 → v2 → v1 → null
        │          │     │     │
   正在使用    可被回收    │    保留
                        (如果 oldestVersionToKeep <= v3)
```

版本链用于：
1. MVCC 快照：事务可以访问其开始时刻的版本
2. 回滚：`MVMap.rollbackTo(version)` 沿着版本链查找目标版本

当版本不再被任何事务使用时，`removeUnusedOldVersions()` 会清理它们（第 172-186 行）。

### 10.5.6 CAS 重试循环与退避策略

```text
本节速览：10.5.6 CAS 重试循环与退避策略

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

CAS 失败时的退避策略是 MVStore 无锁并发性能的关键。以下展示了不同竞争程度下的退避行为：

```text
┌──────────────────────────────────────────────────────────────────┐
│              CAS 重试循环与三级退避策略                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  tryLock(rootRef, attempt)                                        │
│       │                                                          │
│       ▼                                                          │
│  rootRef.tryLock(attempt)                                         │
│       │                                                          │
│  ┌────┴────┐                                                     │
│  │ 成功     │ 失败                                                │
│  └────┬────┘                                                     │
│       │        │                                                 │
│  return      attempt < CPU_COUNT?                                 │
│  lockedRoot     │                                                 │
│                  ├── YES: 级别 1 — 自旋等待                        │
│                  │   Thread.onSpinWait()                          │
│                  │   ← JDK 9+ 的提示指令, 告诉 CPU 我们在自旋      │
│                  │   ← 优化 CPU pipeline (减少功耗)               │
│                  │   ← 适合: 短暂等待 (<1μs)                      │
│                  │                                                │
│                  └── NO: attempt >= CPU_COUNT                     │
│                       │                                           │
│                       ▼                                           │
│                  estimateContention():                            │
│                  ratio = updateAttemptCounter / updateCounter      │
│                  threshold = CPU_COUNT + (CPU_COUNT + ratio)/2    │
│                       │                                           │
│                       ▼                                           │
│                  attempt < threshold?                             │
│                       │                                           │
│                  ┌────┴────┐                                      │
│                  │         │                                      │
│                  ▼         ▼                                      │
│           级别 2       级别 3                                     │
│       Thread.yield()  synchronized(lock)                          │
│       ← 让出时间片    ← 阻塞等待(1ms)                             │
│       ← 适合:         ← 适合:                                     │
│        短暂等待         长等待                                     │
│        (~10μs)         (>100μs)                                   │
│                                                                  │
│  退避策略与竞争程度的关系:                                          │
│                                                                  │
│  竞争程度  │ 重试次数  │ 退避级别             │ 延迟估计            │
│  ─────────┼─────────┼───────────────────┼──────────────────  │
│  低       │ 1-2     │ 级别 1 (spin)     │ 0.1-1 μs           │
│  中       │ 3-8     │ 级别 2 (yield)    │ 10-100 μs          │
│  高       │ 8+      │ 级别 3 (wait)     │ 1-10 ms            │
│  极高     │ 20+     │ 级别 3 + 重试      │ 10-100 ms          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-22: CAS 重试循环与三级退避策略**

### 10.5.7 读路径 vs 写路径

```text
本节速览：10.5.7 读路径 vs 写路径

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-22 所示，MVStore 的读和写走完全不同的路径。读路径完全无锁，写路径需要 CAS + 退避。以下展示了两种路径的完整流程对比：

```text
┌──────────────────────────────────────────────────────────────────┐
│              读路径 vs 写路径对比 (MVMap)                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  读路径 (get):                       写路径 (operate):            │
│  ┌──────────────────────┐           ┌──────────────────────┐     │
│  │ map.get(key)         │           │ map.operate(key,     │     │
│  │                      │           │   value, decision)   │     │
│  └──────────┬───────────┘           └──────────┬───────────┘     │
│             │                                   │                 │
│             ▼                                   ▼                 │
│  ┌──────────────────────┐           ┌──────────────────────┐     │
│  │ root = map.root.get()│           │ root = map.root.get()│     │
│  │ (AtomicReference,    │           │ (AtomicReference,    │     │
│  │  无锁)               │           │  无锁)               │     │
│  └──────────┬───────────┘           └──────────┬───────────┘     │
│             │                                   │                 │
│             ▼                                   ▼                 │
│  ┌──────────────────────┐           ┌──────────────────────┐     │
│  │ Page.get(key)        │           │ tryLock(root,        │     │
│  │ (B-Tree 遍历,        │           │   attempt)           │     │
│  │  纯内存操作, 无锁)   │           │ (CAS 尝试获取写锁)    │     │
│  └──────────┬───────────┘           └──────────┬───────────┘     │
│             │                                   │                 │
│             │                                   ├── 失败 →        │
│             │                                   │  退避 + 重试     │
│             ▼                                   ▼                 │
│  ┌──────────────────────┐           ┌──────────────────────┐     │
│  │ return value         │           │ 创建新 Page 对象      │     │
│  │ (可能是               │           │ (路径复制,            │     │
│  │  VersionedValue)     │           │  不可变)             │     │
│  └──────────────────────┘           └──────────┬───────────┘     │
│                                                 │                 │
│                                                 ▼                 │
│                                      ┌──────────────────────┐     │
│                                      │ 创建新的              │     │
│                                      │ RootReference         │     │
│                                      │ (不可变)              │     │
│                                      └──────────┬───────────┘     │
│                                                 │                 │
│                                                 ▼                 │
│                                      ┌──────────────────────┐     │
│                                      │ root.compareAndSet(   │     │
│                                      │   old, new)           │     │
│                                      │ CAS 更新              │     │
│                                      ├── 失败 → 重试         │     │
│                                      └── 成功 → unlock + ret │     │
│                                                                  │
│  关键区别:                                                         │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 读: 完全无锁 — 不获取 RootReference 的锁               │        │
│  │ 写: CAS + 退避 — 需要获取 RootReference 的写锁        │        │
│  │                                                      │        │
│  │ 读操作从不创建新对象 (零 GC 压力)                      │        │
│  │ 写操作创建新 Page 和 RootReference (GC 压力)          │        │
│  │                                                      │        │
│  │ 读操作可以和其他读操作完全并发                           │        │
│  │ 读操作可以和写操作并发 (读旧版本, 写新版本)              │        │
│  │ 写操作之间互斥 (CAS 保证只有一个成功)                   │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-23: 读路径 vs 写路径对比**

### 10.5.8 RootReference 锁状态

```text
本节速览：10.5.8 RootReference 锁状态

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-23 所示，RootReference 在同一个对象上实现了两种模式：无锁读和有锁写。其锁状态通过 `holdCount` 和 `ownerId` 字段区分：

```text
┌──────────────────────────────────────────────────────────────────┐
│              RootReference 锁状态与转换                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  RootReference 实例的锁状态由 (holdCount, ownerId) 决定:          │
│                                                                  │
│  ┌────────────────────┐                                          │
│  │  UNLOCKED          │  ← holdCount=0, ownerId=0                │
│  │  (未锁定)           │  ← 读操作可以直接读取                     │
│  └────────┬───────────┘  ← 写操作需要通过 CAS 获取锁              │
│           │                                                      │
│           │ tryLock() CAS 成功                                    │
│           ▼                                                      │
│  ┌────────────────────┐                                          │
│  │  LOCKED (写锁定)    │  ← holdCount=1, ownerId=threadId         │
│  │                     │  ← 当前线程可以进行写操作                  │
│  └────────┬───────────┘                                           │
│           │                                                      │
│      ┌────┴────┐                                                 │
│      │         │                                                 │
│      ▼         ▼                                                 │
│  释放锁      可重入锁定                                           │
│  unlock()    tryLock() (同一线程)                                 │
│      │         │                                                 │
│      │         ▼                                                 │
│      │  ┌────────────────────┐                                   │
│      │  │  REENTRANT         │  ← holdCount= N, ownerId=threadId │
│      │  │  (可重入)           │  ← 同一线程多次 lock               │
│      │  └────────┬───────────┘  ← unlock N 次才完全释放           │
│      │           │                                                │
│      │     unlock() 直到 holdCount=0                              │
│      │           │                                                │
│      ▼           ▼                                                │
│  ┌────────────────────┐                                          │
│  │  UNLOCKED          │  ← holdCount=0                           │
│  └────────────────────┘                                          │
│                                                                  │
│  并发场景下的状态:                                                 │
│                                                                  │
│  场景 1: 多个读者                                                │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ Reader 1: root.get() → UNLOCKED RootRef              │        │
│  │ Reader 2: root.get() → 同一 UNLOCKED RootRef         │        │
│  │ → 完全并发, 无锁争用                                  │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  场景 2: 读者 + 写者                                             │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ Reader: root.get() → RootRef v5 (UNLOCKED)           │        │
│  │ Writer: root.get() → RootRef v5 (UNLOCKED)           │        │
│  │ Writer: tryLock(v5) → CAS 成功 → LOCKED              │        │
│  │ Writer: 创建 RootRef v6, CAS 更新 root               │        │
│  │ Reader: 继续使用 RootRef v5 (完全不受影响)             │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  场景 3: 写者冲突                                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ Writer 1: tryLock(v5) → CAS 成功 → LOCKED            │        │
│  │ Writer 2: tryLock(v5) → CAS 失败 → 退避 + 重试       │        │
│  │ Writer 1: 完成, CAS 更新 root → UNLOCKED             │        │
│  │ Writer 2: 重新获取 root.get() → v6, 重试             │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-24: RootReference 锁状态与转换**

## 10.6 文件级锁

如图 10-24 所示，**核心文件**: `store/FileLock.java`

H2 使用文件级锁确保同一数据库文件不会同时被多个进程写入。`FileLock` 类实现了三种锁模式。

### 10.6.1 锁模式

```text
本节速览：10.6.1 锁模式

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

| 模式 | 方法 | 机制 | 适用场景 |
|------|------|------|---------|
| FILE | `lockFile()` | 锁文件 + 心跳看门狗 | 默认模式，适用于文件系统 |
| SOCKET | `lockSocket()` | TCP Socket 监听 | 网络文件系统，远程访问 |
| FS | - | 文件系统原生锁 | 委托给底层文件系统 |
| NO | - | 无锁 | 只读或内存数据库 |

```text
如图 10-25 所示，┌──────────────────────────────────────────────────────────────────┐
│              文件锁四种模式选择决策树                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FileLock 初始化:                                                 │
│       │                                                          │
│       ▼                                                          │
│  读取配置: lockMethod                                             │
│       │                                                          │
│       ├── "file" (默认) ───────────────────────────┐             │
│       │   │                                          │             │
│       │   ▼                                          │             │
│       │  lockFile():                                  │             │
│       │  ┌─────────────────────────────────────┐    │             │
│       │  │ 创建 .lock.db 文件                    │    │             │
│       │  │ 写入 id + method + 时间戳             │    │             │
│       │  │ 启动看门狗线程 (每 2s 更新心跳)        │    │             │
│       │  │ 冲突检测: 检查文件时间戳超时           │    │             │
│       │  │ 适用: 本地文件系统                     │    │             │
│       │  └─────────────────────────────────────┘    │             │
│       │                                              │             │
│       ├── "socket" ──────────────────────────┐      │             │
│       │   │                                      │      │             │
│       │   ▼                                      │      │             │
│       │  lockSocket():                            │      │             │
│       │  ┌─────────────────────────────────────┐ │      │             │
│       │  │ ServerSocket 监听选定端口             │ │      │             │
│       │  │ 写入 server=host:port 到 lock 文件    │ │      │             │
│       │  │ 冲突检测: TCP 连接验证                │ │      │             │
│       │  │ 适用: NFS 等网络文件系统              │ │      │             │
│       │  └─────────────────────────────────────┘ │      │             │
│       │                                              │             │
│       ├── "fs" ──────────────────────────────┐       │             │
│       │   │                                      │       │             │
│       │   ▼                                      │       │             │
│       │  委托给底层文件系统的原生锁机制:              │       │             │
│       │  ┌─────────────────────────────────────┐ │       │             │
│       │  │ 使用 FileChannel.lock() 或类似 API   │ │       │             │
│       │  │ 行为取决于 OS 和文件系统类型          │ │       │             │
│       │  │ 适合: 需要 OS 级强制锁的场景          │ │       │             │
│       │  └─────────────────────────────────────┘ │       │             │
│       │                                              │             │
│       └── "no" ───────────────────────────────┐      │             │
│           │                                      │      │             │
│           ▼                                      │      │             │
│          不进行任何锁操作:                          │      │             │
│          ┌─────────────────────────────────────┐  │      │             │
│          │ 无文件锁                              │  │      │             │
│          │ 多进程同时打开 → 数据损坏风险          │  │      │             │
│          │ 仅用于只读数据库或测试场景              │  │      │             │
│          └─────────────────────────────────────┘  │      │             │
│                                                     │             │
│  选择建议:                                            │             │
│  ┌──────────────────────────────────────────────────────┐         │
│  │ 本地开发/生产 → FILE (默认, 最可靠)                   │         │
│  │ NFS 网络文件系统 → SOCKET (避免文件锁不同步)          │         │
│  │ 特殊需求 → FS (委托 OS)                              │         │
│  │ 只读/测试 → NO (无保护)                              │         │
│  └──────────────────────────────────────────────────────┘         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-25: 文件锁四种模式选择决策树**

### 10.6.2 FILE 模式的工作原理

```text
本节速览：10.6.2 FILE 模式的工作原理

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

```text
如图 10-26 所示，┌──────────────────────────────────────────────────┐
│  FILE 模式锁流程                                   │
├──────────────────────────────────────────────────┤
│                                                   │
│  1. 创建 .lock.db 文件                             │
│     └─ Properties 格式                             │
│     └─ 包含方法 (FILE)、唯一 ID、时间戳              │
│                                                   │
│  2. 检查冲突                                      │
│     └─ 等待旧锁文件超时 (2×TIME_GRANULARITY)       │
│     └─ 读取 lock 文件，检查方法是否一致              │
│     └─ 比较 properties 是否匹配                    │
│     └─ 如果不匹配 → throw DATABASE_ALREADY_OPEN_1  │
│                                                   │
│  3. 启动看门狗线程 (watchdog)                       │
│     └─ 优先级: Thread.MAX_PRIORITY - 1             │
│     └─ 守护线程 (daemon)                           │
│     └─ 每 SLEEP_GAP×2 ms 重写 lock 文件            │
│                                                   │
│  4. 定期心跳 (run() 方法)                          │
│     └─ 保存当前时间戳 + 唯一 ID                    │
│     └─ 如果文件被删除或修改 → 检测到冲突            │
│                                                   │
└──────────────────────────────────────────────────┘
```
**图 10-26: FILE 模式锁流程**

### 10.6.3 SOCKET 模式

```text
本节速览：10.6.3 SOCKET 模式

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

SOCKET 模式创建一个 ServerSocket 监听端口，当另一个进程尝试连接时，通过握手验证：

```text
如图 10-27 所示，┌──────────────────────────────────────────────┐
│  SOCKET 模式锁验证                             │
├──────────────────────────────────────────────┤
│                                               │
│  checkServer():                               │
│  1. 读取 .lock.db 中的 server + id            │
│  2. 连接到 server:port (TCP)                  │
│  3. 发送协议版本 + id                         │
│  4. 如果返回 STATUS_OK → 数据库已被打开        │
│     → 抛出 DATABASE_ALREADY_OPEN_1             │
│  5. 如果连接失败 → 没有其他进程持有锁           │
│                                               │
└──────────────────────────────────────────────┘
```
**图 10-27: SOCKET 模式锁验证**

### 10.6.4 看门狗 (Watchdog)

```text
本节速览：10.6.4 看门狗 (Watchdog)

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

`FileLock` 实现了 `Runnable` 接口，其 `run()` 方法作为看门狗线程运行：

```java
// FileLock.java:39 类声明 + watchdog 启动
watchdog = new Thread(this, "H2 File Lock Watchdog " + fileName);
watchdog.setDaemon(true);
watchdog.setPriority(Thread.MAX_PRIORITY - 1);
watchdog.start();
```

如图 10-25 所示，看门狗的核心职责是周期性地重写锁文件（更新心跳时间戳）。如果拥有锁的进程崩溃，锁文件不会被更新，待获取锁的进程在等待一段时间后可以检测到锁已过期，从而接管。

### 10.6.5 锁文件格式 (.lock.db)

```text
本节速览：10.6.5 锁文件格式 (.lock.db)

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
#FileLock
#Mon Jun 01 12:00:00 UTC 2026
id=1234567890abcdef
method=file
server=192.168.1.1
```

Properties 文件中包含 `id`（唯一标识符）、`method`（锁方法）和可选的 `server`（SOCKET 模式用）。

### 10.6.6 文件锁心跳机制

```text
本节速览：10.6.6 文件锁心跳机制

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

FileLock 的心跳机制确保在持有锁的进程崩溃后，其他进程可以检测到锁已过期并获得对数据库的访问权。以下展示心跳的完整工作流程：

```text
┌──────────────────────────────────────────────────────────────────┐
│              文件锁心跳机制 (FileLock Watchdog)                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  时间线:                                                          │
│                                                                  │
│  进程 A (持有锁)                     进程 B (等待锁)               │
│  ─────────────────────               ─────────────────────        │
│       │                                     │                     │
│       ├── 打开 .lock.db                     │                     │
│       ├── 写入: id=A, method=FILE           │                     │
│       ├── 启动看门狗线程                     │                     │
│       │                                     │                     │
│  ─── 正常操作 ───                           │                     │
│       │                                     │                     │
│       ├── [T+0] 看门狗: 重写 lock 文件      │                     │
│       ├── [T+2s] 看门狗: 重写 lock 文件     │                     │
│       ├── [T+4s] 看门狗: 重写 lock 文件     │                     │
│       │                                     │                     │
│  ─── 进程 A 崩溃 ───                        │                     │
│       │ (看门狗线程终止)                     │                     │
│                                            ├── [T+5s] 尝试打开    │
│                                            │   发现 .lock.db 存在 │
│                                            │   检查时间戳         │
│                                            │   发现: 上次更新     │
│                                            │   T+4s, 已过 1s     │
│                                            │   (仍在超时窗口内)   │
│                                            ├── 等待 2s           │
│                                            │                     │
│                                            ├── [T+7s] 再次检查   │
│                                            │   上次更新 T+4s,     │
│                                            │   已过 3s > 2*GAP   │
│                                            │   → 锁已过期!       │
│                                            │   → 覆盖 .lock.db   │
│                                            │   → 获取锁!         │
│                                            │                     │
│                                            ▼                     │
│                                      进程 B 获得锁, 开始操作      │
│                                                                  │
│  关键参数:                                                         │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ SLEEP_GAP = 2000 ms (看门狗写入间隔)                   │        │
│  │ TIME_GRANULARITY = 2000 ms (时间粒度)                  │        │
│  │                                                      │        │
│  │ 超时计算:                                             │        │
│  │ 锁文件最后修改时间 + 2 × SLEEP_GAP = 过期时间          │        │
│  │ 即: 超过 4 秒无心跳 → 锁被视为可回收                    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-28: 文件锁心跳机制**

### 10.6.7 SOCKET 与 FILE 模式对比

```text
本节速览：10.6.7 SOCKET 与 FILE 模式对比

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-28 所示，两种锁模式有不同的适用场景和可靠性特征。以下从多个维度对比：

```text
┌──────────────────────────────────────────────────────────────────┐
│              SOCKET 锁 vs FILE 锁 对比                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  特性            │ FILE 锁                     │ SOCKET 锁        │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  锁机制          │ 文件心跳 + 时间戳             │ TCP ServerSocket │
│                  │                             │ + 连接握手        │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  检测冲突速度     │ 慢 (需等待超时 4s+)          │ 快 (连接失败 →    │
│                  │                             │ 立即知道)         │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  系统资源         │ 低 (文件 I/O, 极少量)        │ 中 (Socket,      │
│                  │                             │ 少量内存)         │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  网络文件系统     │ ❌ 不支持 (锁文件可能不同步)   │ ✓ 支持 (TCP      │
│                  │                             │ 是网络协议)      │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  崩溃检测         │ 被动 (等待超时)             │ 主动 (进程崩溃 →  │
│                  │                             │ Socket 关闭)     │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  防火墙友好       │ ✓ 是 (不涉及网络)            │ ❌ 否 (需要开放   │
│                  │                             │ 端口)            │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  端口冲突风险     │ 无                          │ 有 (需选择可用    │
│                  │                             │ 端口)            │
│  ───────────────┼────────────────────────────┼─────────────────  │
│                  │                             │                  │
│  多进程支持       │ 自然支持                     │ 需要额外握手      │
│                  │                             │ 协议              │
│                                                                  │
│  总结:                                                            │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ FILE 锁: 适合本地文件系统, 简单可靠, 崩溃检测有延迟     │        │
│  │ SOCKET 锁: 适合 NFS 等网络文件系统, 快速检测崩溃       │        │
│  │ FS 锁: 委托给文件系统, 行为取决于平台                  │        │
│  │ NO 锁: 用于只读或测试场景, 无保护                      │        │
│  │                                                      │        │
│  │ 默认选择: FILE 锁 (对所有本地部署场景最合适)           │        │
│  │ 如果需要 NFS 部署, 必须使用 SOCKET 锁                  │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-29: SOCKET 锁 vs FILE 锁对比**

### 10.6.8 锁文件格式详解

```text
本节速览：10.6.8 锁文件格式详解

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```

如图 10-29 所示，`.lock.db` 文件是一个 Java Properties 格式的文本文件，包含用于锁验证的所有必要信息：

```text
┌──────────────────────────────────────────────────────────────────┐
│              锁文件格式详解 (.lock.db)                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ #FileLock                                            │        │
│  │ #Mon Jun 01 12:00:00 UTC 2026                        │        │
│  │ id=1234567890abcdef                                  │        │
│  │ method=file                                          │        │
│  │ server=192.168.1.1:9092                              │        │
│  │                                                      │        │
│  │ # 注释行: 文件头部, 文件格式标识                        │        │
│  │ # 注释行: 文件创建时间                                │        │
│  │                                                      │        │
│  │ id: 当前锁持有者的唯一标识符                           │        │
│  │   - 格式: 16 位十六进制字符串                          │        │
│  │   - 生成: Identity.random()                           │        │
│  │   - 用途: 验证新旧锁是否属于同一实例                    │        │
│  │                                                      │        │
│  │ method: 锁方法                                       │        │
│  │   - file: FILE 模式 (默认)                            │        │
│  │   - socket: SOCKET 模式                              │        │
│  │   - 用途: 冲突检测时确保方法一致                       │        │
│  │                                                      │        │
│  │ server: 服务器地址 (仅 SOCKET 模式)                   │        │
│  │   - 格式: host:port                                  │        │
│  │   - 用途: SOCKET 模式下的连接目标                      │        │
│  │   - FILE 模式下不写入此字段                            │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  写入策略:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 初始写入: createLockFile() → store()                 │        │
│  │ 心跳更新: save() → FileOutputStream → store()        │        │
│  │           (覆盖整个文件内容)                           │        │
│  │ 文件删除: unlock() → file.delete()                    │        │
│  │           (非强制, 某些 OS 在进程崩溃后不会删除)        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  冲突检测 (checkLockFile()):                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 1. 检查文件是否存在                                   │        │
│  │ 2. 如果存在:                                         │        │
│  │    a. 读取 id 和 method                              │        │
│  │    b. 如果 id 与当前进程相同 → 重复打开, 允许          │        │
│  │    c. 如果 method 不匹配 → 抛出异常                   │        │
│  │    d. 检查时间戳是否过期 (2*SLEEP_GAP)                │        │
│  │       - 未过期 → 抛出 DATABASE_ALREADY_OPEN_1        │        │
│  │       - 过期 → 覆盖锁文件, 获取锁                     │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-30: 锁文件格式详解**

## 10.7 五层并发控制全景

如图 10-30 所示，H2 Database 的 MVStore 引擎实现了一个多层次的并发控制体系，各层次分工明确：

```text
┌──────────────────────────────────────────────────────────────────┐
│  并发控制层次 — 各层职责与交互                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  层次 5: 文件级锁 (FileLock)                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 作用: 多进程互斥                                      │        │
│  │ 范围: 整个数据库文件                                   │        │
│  │ 粒度: 进程级                                          │        │
│  │ 实现: 锁文件 + 心跳 / TCP Socket                       │        │
│  │ 冲突检测: 文件时间戳超时 / 连接失败                      │        │
│  │ 影响: 阻止第二个进程打开数据库                          │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────────────┐        │
│  │ 跨进程边界                                            │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  层次 4: Store 级并发控制 (MVStore)                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 作用: 串行化 store 和 close 操作                       │        │
│  │ 范围: 整个 MVStore 实例                               │        │
│  │ 粒度: Store 级别                                      │        │
│  │ 实现: ReentrantLock (公平锁) + AtomicBoolean          │        │
│  │ 冲突检测: storeLock.tryLock() / CAS                   │        │
│  │ 影响: 后台提交和前台 commit 互斥                        │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────────────┐        │
│  │ 写操作路径                                            │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  层次 3: B-Tree CAS 无锁并发 (RootReference)                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 作用: 无锁读 + 无锁写路径复制                          │        │
│  │ 范围: 单个 MVMap 实例                                 │        │
│  │ 粒度: B-Tree 根引用级别                                │        │
│  │ 实现: AtomicReference + CAS + 三级退避                 │        │
│  │ 冲突检测: CAS 失败 → 退避 + 重试                       │        │
│  │ 影响: 读完全无锁, 写通过 CAS 串行化                     │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────────────┐        │
│  │ 事务操作路径                                          │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  层次 2: 行级 MVCC (TransactionMap)                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 作用: 事务隔离 + 写-写冲突检测                        │        │
│  │ 范围: 单个键值对                                      │        │
│  │ 粒度: 行级                                            │        │
│  │ 实现: VersionedValue + TxDecisionMaker                │        │
│  │ 冲突检测: TxDecisionMaker.decide()                    │        │
│  │ 影响: 事务的读写可见性, 写-写冲突时的等待/回滚          │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────────────┐        │
│  │ 表操作路径                                            │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                         │
│  层次 1: 表级锁 (MVTable)                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 作用: DDL/DML 的表级互斥                              │        │
│  │ 范围: 单个表                                          │        │
│  │ 粒度: 表级                                            │        │
│  │ 实现: 共享/排他锁 + FIFO 等待队列                      │        │
│  │ 冲突检测: DFS 死锁检测                                 │        │
│  │ 影响: ALTER TABLE 等 DDL 需要排他锁                    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-31: 并发控制层次结构**

如图 10-31 所示，这种分层设计使得 MVStore 能够在保证数据一致性的同时，实现高吞吐量的读写操作。读操作为无锁（Lock-Free），写操作通过 CAS + 退避策略减少冲突，事务通过 MVCC 实现隔离性，文件锁则保证了跨进程的安全性。

```text
┌──────────────────────────────────────────────────────────────────┐
│              五层并发控制 — 请求处理路径与锁获取时机                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  一条 SQL 请求在并发控制各层次中的典型路径:                          │
│                                                                  │
│  SELECT 查询:                                                     │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  1. MVTable.lock(READ)  → 快速路径, 无排他则立即返回  │        │
│  │                           (不进入同步块, 无锁)         │        │
│  │  2. TransactionMap.get() → useSnapshot() 获取原子快照 │        │
│  │  3. MVMap.get(key)      → root.get() + Page.get()   │        │
│  │                           (完全无锁)                  │        │
│  │  4. 结果: 读路径无阻塞, 零锁开销                       │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  INSERT/UPDATE/DELETE 写入:                                       │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  1. MVTable.lock(READ)  → 快速路径                    │        │
│  │  2. TransactionMap.set() → TxDecisionMaker.decide() │        │
│  │  3. MVMap.operate()     → CAS 循环 + 三级退避        │        │
│  │  4. MVStore.store()     → storeLock.lock() (公平锁)  │        │
│  │  5. FileLock            → 看门狗线程持续心跳, 不影响  │        │
│  │  结果: 写路径在 CAS 和 storeLock 处可能阻塞            │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  DDL 操作 (ALTER TABLE):                                          │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  1. MVTable.lock(EXCLUSIVE) → 等待 FIFO 队列排他锁   │        │
│  │  2. MVTable unlock → notifyAll() 唤醒等待者          │        │
│  │  结果: DDL 期间阻塞所有对该表的读写                    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  锁获取时机总结:                                                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  层次          │ 读取操作 │ 写入操作 │ DDL 操作  │    │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │  表级锁         │ 可选     │ 共享锁   │ 排他锁    │    │        │
│  │  行级 MVCC     │ 快照     │ 冲突检测  │ 快照      │    │        │
│  │  B-Tree CAS    │ 无锁     │ CAS      │ CAS       │    │        │
│  │  Store 级锁    │ 无锁     │ store()  │ store()   │    │        │
│  │  文件锁         │ 持续心跳  │ 持续心跳  │ 持续心跳   │    │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-32: 五层并发控制请求处理路径**

### 10.7.1 各层冲突预防矩阵

```text
本节速览：10.7.1 各层冲突预防矩阵

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


如图 10-32 所示，不同的并发控制层次预防不同的冲突类型。以下矩阵展示了每个层次覆盖的冲突场景：

```text
┌──────────────────────────────────────────────────────────────────┐
│              各层冲突预防矩阵                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  冲突类型 \ 层次          │ 文件锁  │ Store锁 │ CAS   │ MVCC │ 表锁 │
│  ────────────────────────┼────────┼────────┼───────┼──────┼───── │
│                           │         │         │       │      │      │
│  多进程同时写入           │    ●    │         │       │      │      │
│                           │         │         │       │      │      │
│  store() 与 close() 竞争  │         │    ●    │       │      │      │
│                           │         │         │       │      │      │
│  B-Tree 写-写冲突         │         │         │   ●   │      │      │
│                           │         │         │       │      │      │
│  脏写 (Dirty Write)       │         │         │       │  ●   │      │
│                           │         │         │       │      │      │
│  脏读 (Dirty Read)        │         │         │       │  ●   │      │
│                           │         │         │       │      │      │
│  不可重复读                │         │         │       │  ●   │      │
│                           │         │         │       │      │      │
│  幻读 (Phantom Read)      │         │         │       │  ●   │      │
│                           │         │         │       │      │      │
│  DDL 与 DML 冲突           │         │         │       │      │  ●  │
│                           │         │         │       │      │      │
│  死锁                      │         │         │       │      │  ●  │
│                           │         │         │       │      │      │
│  ● = 该层次预防/处理此冲突  │         │         │       │      │      │
│                                                                  │
│  层次协作示例:                                                     │
│                                                                  │
│  DDL (ALTER TABLE):                                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ MVTable.lock(EXCLUSIVE)  → 等待表级排他锁            │        │
│  │ TransactionMap 操作      → MVCC 确保行级隔离         │        │
│  │ MVMap.operate()          → CAS 确保 B-Tree 原子更新  │        │
│  │ store() 或 storeNow()      → storeLock 确保串行化提交 │        │
│  │ FileLock 看门狗继续心跳    → 其他进程无法打开          │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  只读查询 (SELECT):                                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ MVTable.lock(READ)       → 快速路径 (无排他则立即返回)│        │
│  │ TransactionMap.get()      → useSnapshot() 获取快照    │        │
│  │ MVMap.get()               → root.get() 无锁读        │        │
│  │ (不需要 storeLock 或 FileLock 参与)                  │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-33: 各层冲突预防矩阵**

### 10.7.2 性能权衡分析

```text
本节速览：10.7.2 性能权衡分析

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


如图 10-33 所示，每层并发控制机制在提供安全性的同时都会带来性能开销。以下分析展示了在不同工作负载下各层次的性能特征：

```text
┌──────────────────────────────────────────────────────────────────┐
│              并发控制各层性能权衡分析                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  文件级锁 (FileLock):                                            │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 开销: 非常低                                           │        │
│  │   - 心跳写入: 每 2s 一次, 极小文件 I/O                  │        │
│  │   - 连接时: 一次锁文件读取和校验                        │        │
│  │   - 无锁竞争: 单进程场景无需竞争                        │        │
│  │ 空间: .lock.db 文件 < 1KB                             │        │
│  │ 属于: 必须开销 (没有文件锁, 多进程写入会破坏数据库)       │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  Store 级锁 (storeLock):                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 开销: 低                                              │        │
│  │   - 仅 store()/close() 时获取                         │        │
│  │   - 读操作完全不受影响                                  │        │
│  │   - 公平锁可能增加上下文切换                            │        │
│  │ 争用: 仅发生在大量并发 commit 场景                       │        │
│  │ 优化: 后台写入使用非同步写入 (不 force), 减少持锁时间     │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  CAS 无锁并发 (RootReference):                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 开销: 中 (写路径) / 无 (读路径)                        │        │
│  │   - 读: AtomicReference.get() ≈ 纳秒级               │        │
│  │   - 写 (无竞争): CAS 一次成功 ≈ 纳秒级                │        │
│  │   - 写 (有竞争): CAS 失败 + 退避 = μs~ms 级          │        │
│  │ 优势: 读操作完全无锁, 线性可扩展                        │        │
│  │ 劣势: 高竞争写入时退避导致延迟增加                       │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  行级 MVCC (TransactionMap):                                     │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 开销: 中-高                                            │        │
│  │   - VersionedValue 包装: 额外对象创建                  │        │
│  │   - TxDecisionMaker 每次操作: 决策逻辑                  │        │
│  │   - useSnapshot() 忙等: 可能多次循环                    │        │
│  │   - Undo Log 维护: 每行额外写入                         │        │
│  │ 优势: 读写不互斥, 高并发读取性能好                       │        │
│  │ 劣势: 写入路径开销较大, 需要额外的 undo log             │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  表级锁 (MVTable):                                               │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 开销: 低-中                                           │        │
│  │   - 读锁: 通常走快速路径, 无 synchronized               │        │
│  │   - 写锁: 需要 synchronized + 等待队列                 │        │
│  │   - 死锁检测: DFS 遍历, 只在超时场景触发                │        │
│  │ 影响: DDL 场景 (ALTER TABLE) 需要排他锁, 阻塞所有操作   │        │
│  │ 优化: 快速路径 + 双重检查锁定                           │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  性能特性总结:                                                    │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ 场景              │ 主要瓶颈              │ 优化建议    │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │ 高并发只读 OLAP   │ 无                    │ 无需调整    │        │
│  │ 高并发读写 OLTP   │ TxDecisionMaker      │ 短事务     │        │
│  │ 大量并发写入       │ CAS 退避 + storeLock  │ 调整 auto-  │        │
│  │                   │                      │ commitDelay │        │
│  │ DDL 密集型         │ MVTable 排他锁        │ 规划维护窗口 │        │
│  │ 多进程访问         │ FileLock 心跳         │ 用 SOCKET   │        │
│  │                   │                      │ 模式        │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-34: 并发控制各层性能权衡分析**

### 10.7.3 并发控制架构总结

```text
本节速览：10.7.3 并发控制架构总结

  ┌────────────┐
  │ 关注对象   │
  └─────┬──────┘
        │ 作用/约束
        ▼
  ┌────────────┐
  │ 本节结论   │
  └────────────┘

```


如图 10-34 所示，H2 MVStore 的五层并发控制架构体现了"关注点分离"的设计原则。每一层专注于解决一类特定的并发问题，并且层的叠加提供了多层次保护：

```text
┌──────────────────────────────────────────────────────────────────┐
│              五层并发控制总结                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  层级  │ 组件         │ 并发问题           │ 解决方案              │
│  ─────┼─────────────┼──────────────────┼──────────────────      │
│       │              │                   │                        │
│  第 1  │ MVTable     │ 表级互斥           │ 共享/排他锁 +           │
│  层    │             │ (DDL vs DML)      │ FIFO 队列 +            │
│       │             │ 死锁              │ DFS 死锁检测           │
│  ─────┼─────────────┼──────────────────┼──────────────────      │
│       │              │                   │                        │
│  第 2  │ Transaction │ 脏写/脏读          │ VersionedValue +       │
│  层    │ Map         │ 不可重复读/幻读    │ 快照隔离 +             │
│       │             │ 写-写冲突           │ TxDecisionMaker       │
│  ─────┼─────────────┼──────────────────┼──────────────────      │
│       │              │                   │                        │
│  第 3  │ MVMap +     │ B-Tree 写-写冲突   │ AtomicReference +     │
│  层    │ RootRef     │ 读-写冲突          │ CAS +                  │
│       │             │                   │ 路径复制               │
│  ─────┼─────────────┼──────────────────┼──────────────────      │
│       │              │                   │                        │
│  第 4  │ MVStore     │ 提交/关闭冲突      │ ReentrantLock +        │
│  层    │             │ store 重入         │ AtomicBoolean         │
│  ─────┼─────────────┼──────────────────┼──────────────────      │
│       │              │                   │                        │
│  第 5  │ FileLock    │ 多进程同时写入     │ 锁文件 + 心跳 /        │
│  层    │             │                   │ TCP Socket            │
│                                                                  │
│  架构总览:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  app / session / transaction                           │        │
│  │       │                                               │        │
│  │  ┌────┴──── 第 1 层: MVTable (表级互斥) ────┐        │        │
│  │  │    │                                       │        │        │
│  │  │  ┌─┴─ 第 2 层: TransactionMap (行级 MVCC) ┐ │        │        │
│  │  │  │   │                                    │ │        │        │
│  │  │  │ ┌─┴─ 第 3 层: MVMap CAS (无锁 B-Tree) ┐│ │        │        │
│  │  │  │ │  │                                   ││ │        │        │
│  │  │  │ │ ┌┴─ 第 4 层: MVStore (提交串行化) ──┐││ │        │        │
│  │  │  │ │ │  │                                │││ │        │        │
│  │  │  │ │ │ ┌┴─ 第 5 层: FileLock (进程互斥) ┐│││ │        │        │
│  │  │  │ │ │ │  磁盘文件                       ││││ │        │        │
│  │  │  │ │ │ └────────────────────────────────┘│││ │        │        │
│  │  │  │ │ └──────────────────────────────────┘││ │        │        │
│  │  │  │ └────────────────────────────────────┘│ │        │        │
│  │  │  └──────────────────────────────────────┘ │        │        │
│  │  └──────────────────────────────────────────┘        │        │
│  │                                                      │        │
│  │  越靠下的层次, 越接近硬件, 保护的对象越基础             │        │
│  │  越靠上的层次, 越接近应用, 提供的语义越丰富             │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 10-35: 五层并发控制总结**

如图 10-35 所示，这种分层设计是 H2 MVStore 高性能的关键。**读操作经过第 3 层和第 2 层时几乎无锁**（CAS 读和快照读），只有在写入或 DDL 时才会触发上层的锁机制。这种"读取优先"的设计哲学使得 H2 在 OLTP 场景下能够支持数千并发连接，同时保证 ACID 事务语义。

> **参考**: H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#acid`)
> 讨论了 H2 对 ACID 四个特性的支持程度，以及持久性方面的已知限制。

## 10.8 ACID 特性与持久性讨论

如图 10-36 所示，ACID（Atomicity、Consistency、Isolation、Durability）是关系数据库事务的核心保证。
H2 官方文档在《Advanced》一章中专门讨论了 ACID 的支持范围（详见官方文档 `advanced.html#acid`）。
本章前几节已从源码层面分析了 H2 的事务、锁和持久化机制，本节从 ACID 视角归纳。

**图 10-36: H2 ACID 特性支持矩阵**

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

## 10.9 本章小结

本章围绕 H2 Database MVStore 存储引擎的并发控制体系展开深入分析，从表级锁到文件级锁构建了完整的五层并发控制模型。

- 表级锁（MVTable）采用共享/排他锁配合 FIFO 等待队列，并通过基于 DFS 的死锁检测算法解决 DDL 与 DML 之间的互斥问题，是并发控制体系的最上层。
- 行级 MVCC（TransactionMap）基于 VersionedValue 与 TxDecisionMaker 实现快照隔离，有效防止脏写、脏读、不可重复读和幻读等并发异常，为事务提供隔离性保障。
- 死锁检测算法利用全局事务依赖图深度优先遍历，以事务超时机制为辅助，在保障正确性的同时将运行时开销降至最低。
- 隔离级别实现涵盖 READ_COMMITTED、REPEATABLE_READ 与 SERIALIZABLE 三个等级，通过提交时间戳与事务版本号的比较确定行的可见性规则。
- RootReference CAS 无锁读机制基于 AtomicReference 与三级退避策略，实现了 B-Tree 根引用的无锁更新，使读操作完全无阻塞，是高并发读取性能的核心支撑。
- 文件级锁通过锁文件心跳机制或 TCP Socket 连接保证多进程互斥访问，阻止第二个进程打开同一数据库文件，从根本上防止数据损坏。
- 五层并发控制架构体现了关注点分离的设计原则，各层专注于解决特定粒度的并发问题，层次叠加提供了从进程级到行级的多重保护，是 H2 在高并发 OLTP 场景下保证 ACID 语义的关键所在。

至此，全书从架构设计、包结构、核心流程、算法原理到持久化与并发控制的完整技术脉络已经展开。第11-12章《核心源码导读与全书总结》将转换视角，从读者实践出发，提供高效的源码阅读路线、调试环境搭建方法和测试框架使用指南，帮助读者将前10章的知识转化为实际的源码分析能力。

## 10.10 延展阅读

- 文件格式（File/Chunk/Page 三级）：H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#fileFormat`)
- ACID 特性与持久性讨论：H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#acid`)
- 持久性已知问题：H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html#durability_problems`)
- 本书第6章§6.1-6.3 — B-Tree/COW/MVCC 算法基础
- 本书第6章§6.4-6.7 — Chunk/LIRS/FreeSpace/MVStore 平衡算法
- 本书第7章§7.1.5 — Session 锁机制与线程模型

---

## 附：源码版本变更说明（v2.4.240 → v2.4.249-SNAPSHOT）

以下为本版本与 2.4.240 之间影响第9-10章的关键变更摘要（44 次提交，81 个文件）。

### MVStore 核心层

> 对应源文件：`org/h2/mvstore/MVStore.java`、`MVMap.java`、`FileStore.java`

- **panicException 改为 AtomicReference**：原先为 `volatile` 字段，现改为 `AtomicReference` + `compareAndSet`，确保仅捕获首个 panic 异常。新增 `panic(Throwable)` 重载作为标准入口。后台线程在 panic 状态下不再调用 `closeImmediately()`，仅通过 `handleException()` 记录。
- **closeStore() 序列变更**：`commit()` 移至 maps 关闭循环之后；状态转换从 `if (state == STATE_OPEN)` 守卫改为 `assert state == STATE_OPEN` + 无条件转换。新增 `closingThreadId` 追踪。
- **`isClosed()` 自旋等待**：若发现其他线程正在执行 `closeStore()`，当前线程将以 `Thread.sleep(millis++)` 从 1ms 递增等待（1ms, 2ms, 3ms...），仅在 `closingThreadId != Thread.currentThread().getId()`（不同线程）时触发。
- **commit() 防重入**：通过快照记录 `versionAtStart`，若在锁重入时版本已变化（通过 `beforeWrite` 触发），则跳过本次提交，防止嵌套提交。
- **MVMap.operate() 简化**：所有页面操作逻辑（拆分、删除、复制、根分裂）从 `operate()` 内联代码移至 `DecisionMaker.decide(CursorPos, K, V)` 方法。`operate()` 仅负责任务重试/中止/应用循环。
- **tryLock() CPU 感知退避**：根据 `Runtime.getRuntime().availableProcessors()` 自适应旋转等待。前 `CPU_COUNT` 次使用 `Thread.onSpinWait()`，随后 `Thread.yield()`，再降级为 `lock.wait(1)`（原为 `lock.wait(5)`）。移除 `Thread.sleep(contention)`。
- **CursorPos 树遍历路径重用**：`traverseDown()` 新增 `existing CursorPos` 参数。重试时可复用上次遍历路径。若页面键数组未变（`sameKeys()` 引用相等性检查），连二分查找结果也可重用。
- **Page 批量删除**：`Page.remove(long positionsToRemove)` 新增位掩码批量删除方法，可在一次操作中移除多个键值对。
- **编译压缩优化**：`TransactionStore.java` 中 `isTransactionClosed(transactionId)` 的条件判断简化为 `transactionId <= maxTransactionId`，减少冗余方法调用。相关提交标题所提 "CompactRowFactory" 实为单行简化的编译优化，并非新增独立类。
- **FileStore 流水线重构**：新增 `recentlySaved` 队列（`LinkedBlockingQueue<Chunk>`），chunk 元数据提交至 layout map 被延迟到下一个 chunk 创建时。`saveRecentChunksInLayout(long version)` 作为刷新方法，由 `stop()` 在最终提交前调用，确保 layout map 完整。修复因 layout map 不完整导致的 ChunkNotFound 问题。
- **moveChunk 错误恢复**：移动操作失败时恢复 chunk 原始 block 位置并释放新分配空间。
- **isBackupThread 判定移除**：原 `isBackupThread` 逻辑（v2.4.240 中用于标识备份压缩线程）已被 H2_THREAD_GROUP 的线程分组机制替代，后台线程的身份识别统一基于线程组归属。

### 事务子系统

> 对应源文件：`org/h2/mvstore/tx/TransactionStore.java`、`Transaction.java`、`CommitDecisionMaker.java`（新增）等

- **TransactionStore 状态机**：引入显式状态常量（`private static final int`，OPEN→INITIALIZING→READY→CLOSING→CLOSED = 0→4），配合 `AtomicInteger` 替代原先的 `boolean init` 标志。`init()` 和 `close()` 均使用 CAS 原子转换，防止并发竞态。
- **CommitDecisionMaker（新增）**：实现 page-level 决策机制，以页为单位批量处理提交逻辑，而非逐条处理 undo log 条目。通过 `haveSeenEntry(int entryId)` 实现同一条目的去重，配合 `VersionedValueCommitted.getInstance(value, entryId)` 将条目标记为已提交。
- **等待事务提前通知**：`TransactionStore.commit()` 在 undo log 回放前即调用 `notifyAllWaitingTransactions()`，使受阻塞的事务更早被唤醒。
- **MAX_OPEN_TRANSACTIONS 默认值调整**：从 65535 降为 255，现可通过 `h2.maxOpenTransactions` 系统属性配置。`undoLogs` 数组大小调整为 `MAX_OPEN_TRANSACTIONS + 1`。
- **恢复工具 maxOpenTransactions 覆盖**：`0d35069eb` 在 `DirectRecover.java` 和 `Recover.java` 的 `main()` 入口处通过 `System.setProperty("h2.maxOpenTransactions", "65535")` 将上限恢复为 65535。此变更为以命令行的方式运行恢复工具时默认放宽限制，不影响嵌入式运行。
- **VersionedBitSet 重写**：不再继承 `java.util.BitSet`，改为不可变的 `long[]` 包装类。`clone()` 调用全部移除，通过构造器 `VersionedBitSet(VersionedBitSet, int)` 创建新实例并翻转指定位。
- **BitSetHelper（新增）**：提供基于 `long[]` 的最小 BitSet 功能（get/flip/nextSetBit/nextClearBit/length），通过不可变模式保证线程安全。
- **committingTransactions 类型迁移**：`TransactionStore.committingTransactions` 从 `BitSet` 改为 `long[]`，波及 `TransactionMap`、`Snapshot`、`Transaction` 等 7 个文件。`Snapshot.hashCode()` 改用 `System.identityHashCode()`。
- **VersionedValue 序列化格式变更**：序列化从 "先写 operationId varLong" 改为 "先写 flags 字节"——根据 flags 决定后续字段（operationId/entryId/value/committedValue）的存在。已持久化的旧版本（v2.4.240）数据文件不兼容此格式。**架构影响**：此变更意味着 v2.4.249-SNAPSHOT 无法直接读取 v2.4.240 创建的 MVStore 数据文件，需通过数据迁移或 DDL 重新导入。
- **事务恢复排序**：非正常关闭后的残余事务按提交序列号（commitment order）排序注册，确保重放顺序正确。
- **死锁修复**：`saveChunkMetadataChanges()` 去除忙等轮询；`acceptChunkOccupancyChanges()` 将未分配 chunk 的 `RemovedPageInfo` 压回队列。`Transaction.waitForThisToEnd()` 新增 `STATUS_COMMITTED` 检查。
