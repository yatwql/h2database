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
