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

| 变更点 | 之前 → 现在（v2.4.240 → v2.4.249） | 读者需要知道的影响 |
| --- | --- | --- |
| `panicException` 承载方式 | `volatile` 字段 → `AtomicReference` + `compareAndSet`，新增 `panic(Throwable)` 作为标准入口 | 只捕获**首个** panic 异常；后台线程在 panic 状态下不再 `closeImmediately()`，改为 `handleException()` 记录 |
| `closeStore()` 顺序 | `commit()` 移到 maps 关闭循环之后；守卫 `if (state == STATE_OPEN)` → `assert` + 无条件转换；新增 `closingThreadId` | 关闭期间的状态判定从「静默跳过」改为「断言失败」，并发关闭由 `closingThreadId` 识别 |
| `isClosed()` 自旋 | 新增 `Thread.sleep(millis++)` 从 1ms 递增，仅在 `closingThreadId != 当前线程` 时触发 | 他线程正在关闭时不再忙等；本线程重入不会自旋 |
| `commit()` 重入 | 新增 `versionAtStart` 快照，锁重入时若版本已变则跳过本次提交 | 嵌套提交不再产生重复版本 |
| `MVMap.operate()` | 页面操作（拆分、删除、复制、根分裂）内联 → `DecisionMaker.decide(CursorPos, K, V)` | `operate()` 只负责重试/中止/应用循环，决策逻辑可单测 |
| `tryLock()` 退避 | 按 `availableProcessors()` 自适应：`onSpinWait()` → `Thread.yield()` → `lock.wait(1)`；移除 `sleep(contention)` | 高核机器上自旋更久、低核机器更早让步 |
| `CursorPos` 遍历 | `traverseDown()` 新增 `existing CursorPos` 参数；`sameKeys()` 引用相等时连二分查找结果一并重用 | 重试路径复用上次遍历结果 |
| 批量删除 | 新增 `Page.remove(long positionsToRemove)` 位掩码批量删除 | 一次操作移除多个键值对 |
| 事务关闭判定 | `isTransactionClosed()` 简化为 `transactionId <= maxTransactionId` | 去掉冗余方法调用 |
| FileStore 流水线 | 新增 `recentlySaved` 队列（`LinkedBlockingQueue<Chunk>`）；元数据延到下一个 chunk 创建时提交；`saveRecentChunksInLayout(long)` 由 `stop()` 在终提交前调用 | 修复 layout map 不完整导致的 `ChunkNotFound` |
| `moveChunk` 失败 | 失败时恢复 chunk 原始 block 位置并释放新分配空间 | 移动失败不再泄漏空间 |
| 后台线程识别 | `isBackupThread` 逻辑删除，改由 `H2_THREAD_GROUP` 线程分组判定 | 后台线程身份识别只依赖线程组归属 |

## B.2 事务子系统

| 变更点 | 之前 → 现在（v2.4.240 → v2.4.249） | 读者需要知道的影响 |
| --- | --- | --- |
| `TransactionStore` 状态 | `boolean init` → 显式状态常量 `OPEN→INITIALIZING→READY→CLOSING→CLOSED`（0→4）+ `AtomicInteger`，`init()`/`close()` 用 CAS | 并发初始化与关闭不再靠标志位竞态 |
| 提交决策 | 逐条处理 undo log → 新增 `CommitDecisionMaker` 按页批量决策，`haveSeenEntry(int)` 去重，`VersionedValueCommitted.getInstance(value, entryId)` 标记已提交 | 提交以页为单位，同一条目只处理一次 |
| 等待事务唤醒 | `commit()` 在 undo log 回放前即调用 `notifyAllWaitingTransactions()` | 被阻塞事务更早被唤醒 |
| `MAX_OPEN_TRANSACTIONS` | 65535 → 255，可经 `h2.maxOpenTransactions` 配置；`undoLogs` 数组长度为 `MAX_OPEN_TRANSACTIONS + 1` | 嵌入式默认上限收敛，需要更多并发时显式调高 |
| 恢复工具上限 | `DirectRecover`/`Recover` 的 `main()` 设 `h2.maxOpenTransactions=65535` | 命令行恢复工具默认放宽，不影响嵌入式运行 |
| `VersionedBitSet` | 继承 `java.util.BitSet` → 不可变 `long[]` 包装；`clone()` 全部移除，改由构造器 `VersionedBitSet(VersionedBitSet, int)` 翻转指定位 | 位集不可变，线程安全不再依赖外部约定 |
| `BitSetHelper` | 新增：基于 `long[]` 的最小 BitSet（`get`/`flip`/`nextSetBit`/`nextClearBit`/`length`） | 不可变模式，替代继承式复用 |
| `committingTransactions` 类型 | `BitSet` → `long[]`，波及 `TransactionMap`、`Snapshot`、`Transaction` 等 7 个文件；`Snapshot.hashCode()` 改用 `System.identityHashCode()` | 快照哈希不再按内容计算 |
| `VersionedValue` 序列化 | 先写 `operationId` varLong → 先写 flags 字节，由 flags 决定后续字段 | **v2.4.249-SNAPSHOT 读不了 v2.4.240 的数据文件**：需数据迁移或 DDL 重新导入 |
| 事务恢复排序 | 非正常关闭后的残余事务按提交序列号（commitment order）注册 | 重放顺序与提交顺序一致 |
| 死锁修复 | `saveChunkMetadataChanges()` 去忙等轮询；`acceptChunkOccupancyChanges()` 将未分配 chunk 的 `RemovedPageInfo` 压回队列；`waitForThisToEnd()` 增加 `STATUS_COMMITTED` 检查 | 关闭与回收阶段的死锁窗口收窄 |

## 16.1 版本变更对照

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
