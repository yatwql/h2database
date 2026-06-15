# 概念索引

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

---

*共收录 300+ 条索引（含主条目与子条目）。每个主条目指向首次出现或最相关的章节；子条目对主题做更细粒度的章节分布；`see also` 行连接概念上相关的索引项，便于读者跨章探索。*
