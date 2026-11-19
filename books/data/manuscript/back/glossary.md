# 附录 C：术语表

> 本书核心术语的中英文对照、详细定义、章节索引与相关术语。条目按字母顺序排列。每条遵循"释义 + 章节 + 相关"三段结构，便于读者从任一入口跳转到完整讨论。

## A

- **ACID**: Atomicity, Consistency, Isolation, Durability — 数据库事务四大特性。
  原子性保证事务要么全部提交要么全部回滚；一致性确保事务前后数据满足业务约束；
  隔离性界定并发事务间的可见性；持久性承诺已提交数据在崩溃后仍可恢复。
  **章节**：第10章 §10.5（H2 的 ACID 实现剖析）
  **相关**：[[MVCC]]、[[Undo Log]]、[[Snapshot Isolation]]

- **Append-Only**: 仅追加写入策略。MVStore 的核心写入模式——新数据只追加到文件末尾，
  不覆盖已有数据；旧版本通过 Compact 阶段集中回收。该策略将随机写转换为顺序写，
  天然契合 Copy-on-Write 与崩溃恢复的简化。
  **章节**：第9章 §9.1（MVStore 架构）、第6章 §6.4（Chunk）
  **相关**：[[COW / Copy-on-Write]]、[[Log-Structured Storage]]、[[Chunk]]

- **AbstractAggregate**: 聚合函数抽象基类。继承自 `DataAnalysisOperation`，是
  SUM/COUNT/AVG/MIN/MAX 等内置聚合函数与窗口函数的共同祖先，定义聚合状态的
  累积、合并、最终输出三阶段接口。
  **章节**：第7章 §7.6（表达式求值）
  **相关**：[[Aggregate]]、[[Expression]]

- **Aggregate**: 聚合函数。SQL 中将一组行折叠为单值的函数（COUNT、SUM 等）。
  H2 的实现支持 GROUP BY、HAVING、DISTINCT 修饰符与窗口函数 OVER 子句。
  **章节**：第7章 §7.6、第11章 §11.1
  **相关**：[[AbstractAggregate]]、[[Window 函数]]、[[SelectGroups]]

## B

- **BackgroundWriter**: 后台写入线程。MVStore 周期性执行自动提交（auto-commit）
  与 Compact 操作的守护线程，避免主线程被 I/O 阻塞。`autoCommitDelay` 参数
  控制其触发频率。
  **章节**：第9章 §9.5（检查点机制）
  **相关**：[[Compact]]、[[Chunk]]、[[FileStore]]

- **B-Tree**: 平衡多路查找树（Balanced Tree）。H2 的索引核心数据结构，每个内部节点
  可有多个子节点（典型分支因子 100-200），保证树高对数级增长，支持高效的键值查找
  与范围扫描。H2 实际使用的是 Counted B-Tree 变种。
  **章节**：第6章 §6.1（数据结构篇）
  **相关**：[[Counted B-Tree]]、[[PageSplit]]、[[Page]]、[[MVMap]]

- **Block**: MVStore 文件的最小分配单元。固定为 4096 字节，匹配磁盘扇区与操作系统
  页大小。一个 Chunk 由若干连续 Block 组成，FreeSpaceBitSet 以 Block 为粒度
  跟踪空闲空间。
  **章节**：第9章 §9.6（文件格式详解）
  **相关**：[[Chunk]]、[[Free Space]]、[[FreeSpaceBitSet]]

- **Bloom 过滤**: 布隆过滤器，一种概率型数据结构，用于快速判定元素"可能存在"或
  "肯定不存在"，假阳性率可调。H2 在某些查询路径下用其加速点查。
  **章节**：第12章 §12.1
  **相关**：[[HASH 索引]]

## C

- **CAS (Compare-And-Swap)**: 比较并交换原子原语。通过 `AtomicReference.compareAndSet`
  实现无锁的 RootReference 更新，是 MVCC 无锁读取的核心支撑。失败时通常配合
  自旋重试或退避策略。
  **章节**：第1章、第10章 §10.4
  **相关**：[[MVCC]]、[[RootReference]]、[[Single Writer]]

- **Chunk**: MVStore 中一次 commit 写入的所有数据集合。包含 Header、若干 Page、
  Footer，是 MVStore 的"逻辑事务单元"——崩溃恢复时按 Chunk 边界回滚到最近一致点。
  **章节**：第6章 §6.4、第9章 §9.3、§9.6
  **相关**：[[Block]]、[[Page]]、[[Append-Only]]、[[Fletcher-32]]

- **Checkpoint**: 检查点，将内存中的脏数据强制刷到磁盘并更新 File Header 的同步点。
  MVStore 通过 `MVStore.commit()` 与 `BackgroundWriter` 触发。
  **章节**：第9章 §9.5
  **相关**：[[BackgroundWriter]]、[[FileStore]]、[[File Header]]

- **ConnectionInfo**: 连接信息对象。封装 JDBC URL 中的所有参数（用户名、密码、
  schema、URL 参数）并经多层校验——从客户端 URL 解析直到 Database 实例化。
  **章节**：第2章 §2.2
  **相关**：[[JDBC]]、[[Engine]]、[[DbSettings]]

- **COW / Copy-on-Write**: 写时复制。修改数据时不直接覆盖原数据，而是将修改后的
  数据写入新位置，父节点递归复制更新。在 B-Tree 上等价于"修改一条路径上的所有节点"。
  H2 的 MVStore 是 COW B-Tree 的典型实现。
  **章节**：第6章 §6.2
  **相关**：[[B-Tree]]、[[MVCC]]、[[Append-Only]]、[[Write Amplification]]

- **Counted B-Tree**: 计数 B-Tree，在内部节点中额外存储子树条目数（`totalCount`），
  支持高效的索引访问（按序号取第 N 个元素）和范围计数（COUNT(*) 不必扫表）。
  **章节**：第9章 §9.6
  **相关**：[[B-Tree]]、[[Page]]

- **CBO / Cost-Based Optimization**: 基于代价的查询优化。Optimizer 估算每个候选执行
  计划的代价（行数 × 单位成本），从中选择最优方案。代价模型综合考虑表大小、索引选择性
  与连接顺序。
  **章节**：第8章 §8.1、§8.3
  **相关**：[[Optimizer]]、[[IndexCondition]]、[[Genetic Algorithm]]

- **CommandContainer**: 命令容器。包装 `Prepared` 对象，提供统一的 query/update
  执行入口并支持重编译检测——当依赖的 schema 对象发生变更时自动失效缓存。
  **章节**：第7章 §7.4
  **相关**：[[Prepared Statement]]、[[Parser]]

- **CommitDecisionMaker**: 提交决策器。事务提交时扫描 Undo Log，将每条记录从
  "uncommitted" 状态转为 "committed"，使变更对其他事务可见。
  **章节**：第5章 §5.5
  **相关**：[[TransactionStore]]、[[Undo Log]]、[[VersionedValue]]、[[RollbackDecisionMaker]]

- **Compact**: 紧凑化/压缩整理。MVStore 通过重写低填充率 Chunk 回收磁盘空间的过程。
  类似 LSM-Tree 的 compaction，但在 COW B-Tree 上的实现更轻量。
  **章节**：第6章 §6.4、第9章 §9.5
  **相关**：[[Chunk]]、[[Free Space]]、[[Write Amplification]]

- **Column**: 列对象。H2 中表示表的一列，含数据类型、约束、默认值与生成表达式。
  **章节**：第3章 §3.6
  **相关**：[[Value]]、[[Table]]

- **CTE**: Common Table Expression，公用表表达式。SQL 中以 `WITH` 关键字声明的
  临时结果集，支持递归与多次引用。
  **章节**：第1章 §1.1
  **相关**：[[Parser]]、[[Recursive Descent Parser]]

## D

- **DDL**: Data Definition Language，数据定义语言。CREATE/ALTER/DROP 等改变 schema
  结构的语句。H2 中由 `Database.lockMeta()` 配合 Meta Lock 串行执行。
  **章节**：第5章
  **相关**：[[Meta Lock]]、[[SchemaObject]]

- **Database**: 数据库实例的顶层对象。持有 schema、settings、session 池、
  存储引擎引用与全局锁。`Engine.openDatabase()` 是其入口工厂方法。
  **章节**：第2章 §2.3、第3章 §3.3
  **相关**：[[Engine]]、[[Session]]、[[SchemaObject]]

- **DbSettings**: 数据库配置项。集中管理缓存大小、日志模式、MVCC 行为等运行时参数。
  通过 JDBC URL 参数或 `SET` 语句覆盖默认值。
  **章节**：第3章 §3.3
  **相关**：[[Database]]、[[ConnectionInfo]]

- **Deadlock**: 死锁。两个或多个事务互相等待对方释放锁而导致的无限阻塞。
  H2 通过锁超时（`LOCK_TIMEOUT`）+ 等待图分析检测并主动回滚牺牲者。
  **章节**：第10章 §10.3、第4章 §4.6
  **相关**：[[Lock]]、[[Meta Lock]]

- **DML**: Data Manipulation Language，数据操作语言。SELECT/INSERT/UPDATE/DELETE
  等改变数据但不改变 schema 的语句。
  **章节**：第5章、第7章
  **相关**：[[CommandContainer]]、[[Optimizer]]

- **Driver**: H2 的 JDBC Driver 实现（`org.h2.Driver`）。注册为 JDBC 服务后被
  `DriverManager.getConnection()` 自动发现，是嵌入式与远程模式连接的统一入口。
  **章节**：第2章 §2.2、第3章 §3.2
  **相关**：[[JDBC]]、[[JdbcConnection]]、[[ConnectionInfo]]

## E

- **Engine**: 数据库引擎层入口。负责打开/关闭数据库实例、管理连接池与生命周期。
  `Engine.java` 是 H2 启动路径的关键节点（约 410 行）。
  **章节**：第2章 §2.3、第3章 §3.3
  **相关**：[[Database]]、[[ConnectionInfo]]、[[SessionLocal]]

- **Expression**: 表达式基类。所有 SQL 表达式（比较、算术、函数调用、子查询）的祖先，
  定义 `getValue()` 求值接口。表达式树同时是 H2 的执行计划——这是 H2 简化内存模型的
  关键设计选择。
  **章节**：第2章 §2.3、第4章 §4.2
  **相关**：[[Aggregate]]、[[IndexCondition]]、[[TableFilter]]

## F

- **File Header**: MVStore 文件开头的两个 4096 字节元数据块（双重备份）。
  以 key-value 文本形式记录最新 Chunk 的位置、文件版本、加密信息等。崩溃恢复
  从 File Header 起步。
  **章节**：第9章 §9.3、§9.6
  **相关**：[[FileStore]]、[[Chunk]]、[[Recover]]

- **Fletcher-32**: 高效的 32 位 checksum 算法。MVStore 用于校验 Chunk Footer
  的完整性。比 CRC32 计算更快，碰撞率对该用途已足够低。
  **章节**：第9章 §9.3、§9.6
  **相关**：[[Chunk]]、[[Recover]]

- **FileStore**: 文件存储抽象。MVStore 的 I/O 层，负责 Chunk 的读写、文件锁
  与 File Header 管理。屏蔽底层 FileChannel 的复杂性。
  **章节**：第9章 §9.1、§9.2
  **相关**：[[FilePath]]、[[BackgroundWriter]]、[[File Header]]

- **FilePath**: 文件路径抽象。屏蔽 FileSystemDisk/Encrypt/NioMapped 等底层
  实现差异，使 MVStore 能透明支持磁盘、加密、内存映射等多种存储后端。
  **章节**：第3章 §3.8
  **相关**：[[FileStore]]、[[FilePathDisk]]、[[FilePathEncrypt]]、[[FilePathNioMapped]]

- **FilePathDisk**: 磁盘文件实现。`FilePath` 的标准实现，直接操作 OS 文件系统。
  **章节**：第2章 §2.10
  **相关**：[[FilePath]]、[[FileStore]]

- **FilePathEncrypt**: 加密文件实现。在读写时透明地用 XTS-AES 加密/解密文件块。
  **章节**：第2章 §2.10、第9章 §9.8
  **相关**：[[FilePath]]、[[XTS-AES 加密]]

- **FilePathNioMapped**: 内存映射文件实现。基于 Java NIO `MappedByteBuffer`，
  适合超大数据库以利用 OS 页缓存。
  **章节**：第2章 §2.10
  **相关**：[[FilePath]]

- **Free Space**: MVStore 的空闲空间管理机制。跟踪哪些 Block 已被 Compact 释放
  且可被新 Chunk 重用，由 `FreeSpaceBitSet` 实现。
  **章节**：第6章 §6.6
  **相关**：[[FreeSpaceBitSet]]、[[Compact]]、[[Block]]

- **FreeSpaceBitSet**: 位图实现的空闲空间管理器。每个 bit 表示一个 Block
  是否空闲，分配时从首个 0 位起搜索连续区间。
  **章节**：第5章 §5.7、第6章 §6.6
  **相关**：[[Free Space]]、[[Block]]

## G

- **Genetic Algorithm**: 遗传算法。H2 优化器在大规模多表 JOIN（≥7 表）时使用的
  随机搜索策略——通过"染色体"编码连接顺序、交叉与变异生成新候选、按代价择优。
  **章节**：第8章 §8.2
  **相关**":  [[Optimizer]]、[[Hybrid Strategy]]、[[CBO / Cost-Based Optimization]]

## H

- **H2**: 纯 Java 实现的嵌入式关系数据库管理系统（Hypersonic 2 / Java SQL Database）。
  由 Thomas Mueller 于 2004 年创立，核心 JAR 约 2MB，支持嵌入式与服务器两种模式。
  **章节**：第1章 §1.1
  **相关**：[[MVStore]]、[[PageStore]]

- **HASH 索引**: 基于哈希表的索引结构。仅支持等值查询（不支持范围），适合精确查找。
  **章节**：第2章 §2.8
  **相关**：[[B-Tree]]、[[Index]]

- **Hybrid Strategy**: 混合优化策略。暴力枚举（小表 ≤ 5）+ 贪心填充（中等规模）
  + 遗传算法（大规模）的组合，根据表数量自动切换。
  **章节**：第8章 §8.2
  **相关**：[[Genetic Algorithm]]、[[Optimizer]]

## I

- **Index**: 索引基类。所有索引实现（B-Tree、HASH、SpatialIndex）的祖先，
  定义 `find()`、`add()`、`remove()`、`getCost()` 等接口。
  **章节**：第2章 §2.8、第4章 §4.4
  **相关**：[[B-Tree]]、[[HASH 索引]]、[[R-Tree]]

- **IndexCondition**: 索引谓词。描述可被索引加速的 WHERE 条件片段（EQUALITY、
  RANGE、SPATIAL 三类），是 Optimizer 选择索引的输入。
  **章节**：第4章 §4.4、第8章 §8.4
  **相关**：[[Index]]、[[Optimizer]]、[[Expression]]

- **IOT / Index-Organized Table**: 索引组织表。数据行直接以索引树（B-Tree）的
  叶子节点存储，无独立堆文件。MVStore 模式下的 H2 表本质即 IOT。
  **章节**：第3章
  **相关**：[[B-Tree]]、[[MVTable]]

- **ISODEBUG**: H2 的调试输出宏。通过 `ISODEBUG` 系统属性控制详细日志的开关。
  **章节**：第11章 §11.3
  **相关**：[[测试框架]]

## J

- **JDBC**: Java Database Connectivity。Java 数据库连接的标准 API。H2 的 JDBC 实现
  位于 `org.h2.jdbc` 包，包括 Driver、Connection、Statement、PreparedStatement、
  ResultSet 等。
  **章节**：第2章 §2.1、第3章 §3.2
  **相关**：[[JdbcConnection]]、[[Driver]]、[[Session]]

- **JdbcConnection**: H2 对 `java.sql.Connection` 的实现。每个 Connection 持有
  一个 SessionLocal 与若干 Command 对象。
  **章节**：第3章 §3.2
  **相关**：[[Session]]、[[CommandContainer]]

- **JSON**: H2 支持 JSON 数据类型与 SQL 标准 JSON 函数（JSON_OBJECT、JSON_ARRAY 等）。
  **章节**：第1章 §1.1
  **相关**：[[Value]]

## L

- **LIRS**: Low Inter-reference Recency Set。低互引用最近集缓存替换算法，通过维护
  "热"与"冷"两个 LRU 队列区分高频访问与一次性扫描，比纯 LRU 更能抵抗扫描污染。
  **章节**：第6章 §6.5
  **相关**：[[Cache]]、[[扫描抗性]]

- **LOB**: Large Object（CLOB/BLOB）。大对象数据。H2 对超过阈值的 LOB 单独存储，
  正文行只保存引用。
  **章节**：第7章 §7.2
  **相关**：[[Value]]

- **LSM-Tree / Log-Structured Merge-Tree**: 日志结构合并树。一种针对写优化的
  数据结构，通过分层合并将随机写转换为顺序写。MVStore 不是纯粹 LSM-Tree，但借鉴了
  Append-Only 写入与后台 Compact 的核心思想。
  **章节**：第1章、第9章
  **相关**：[[Append-Only]]、[[Compact]]、[[Log-Structured Storage]]

- **LocalResult**: 本地结果集。查询执行时在内存中构建的中间结果集，支持排序、
  去重、投影。规模大时溢出到磁盘临时文件。
  **章节**：第7章 §7.5
  **相关**：[[Query]]

- **Log-Structured Storage**: 日志结构存储。按写入顺序追加数据而非原地更新的
  存储范式，崩溃恢复简化为"找到最后一个完整 Chunk"。
  **章节**：第6章、第9章 §9.1
  **相关**：[[Append-Only]]、[[LSM-Tree]]、[[MVStore]]

- **Lock**: 锁基类。H2 提供 Shared/Exclusive 两类锁。MVStore 模式下行级锁主要
  通过 MVCC 实现，仅 DDL 与少数 DML 路径使用显式锁。
  **章节**：第10章 §10.1、§10.2
  **相关**：[[Meta Lock]]、[[Deadlock]]

## M

- **Maven**: H2 项目的构建工具。`h2/pom.xml` 定义依赖、编译目标（Java 11）与
  打包流程。
  **章节**：第11章 §11.3
  **相关**：[[测试框架]]

- **Meta Lock**: 元数据锁。Database 内部用于元数据并发控制的轻量级锁，
  保护 schema 修改、表创建/删除等操作。
  **章节**：第4章 §4.1、第10章 §10.1
  **相关**：[[Lock]]、[[DDL]]、[[Database]]

- **Mode**: SQL 兼容模式。H2 通过 `org.h2.engine.Mode` 描述 Oracle/MySQL/
  PostgreSQL/MSSQLServer 等方言差异规则。
  **章节**：第3章 §3.6
  **相关**：[[Parser]]、[[Database]]

- **MVCC**: Multi-Version Concurrency Control，多版本并发控制。通过维护数据的
  多个版本实现读写不互斥——读事务读取一致性快照，写事务用 first-committer-wins
  解决冲突。
  **章节**：第6章 §6.3、第10章 §10.4
  **相关**：[[Snapshot Isolation]]、[[VersionedValue]]、[[TxDecisionMaker]]

- **MVMap**: MVStore 的核心 API。基于 Counted B-Tree 的有序键值映射，
  支持快照读、版本回滚、范围扫描。所有 H2 表与索引都构建在 MVMap 之上。
  **章节**：第4章 §4.6、第9章 §9.2
  **相关**：[[MVStore]]、[[B-Tree]]、[[Page]]

- **MVStore**: H2 自 v2.0 起的默认存储引擎。基于日志结构的多版本键值存储，
  以 COW B-Tree 实现 MVCC。
  **章节**：第4章 §4.6、第9章
  **相关**：[[MVMap]]、[[FileStore]]、[[Chunk]]、[[PageStore]]

- **MVTable**: MVStore 模式下的 Table 实现。将每张 SQL 表映射为一个 MVMap。
  约 1012 行核心逻辑覆盖增删改查与索引联动。
  **章节**：第3章
  **相关**：[[Table]]、[[MVMap]]、[[IOT / Index-Organized Table]]

- **MVStoreTool**: MVStore 的离线工具集。包含 `dump`、`compact`、`info`、
  `simulateCrash` 等命令行子命令，用于运维与测试。
  **章节**：第11章 §11.3
  **相关**：[[MVStore]]、[[Recover]]

## O

- **Optimizer**: 查询优化器。负责选择最高效的执行计划，核心职责是连接顺序选择
  与索引选择。`Optimizer.canStop()` 决定何时终止搜索。
  **章节**：第8章 §8.1
  **相关**：[[CBO / Cost-Based Optimization]]、[[Hybrid Strategy]]、[[IndexCondition]]

## P

- **Page**: MVStore 的最小数据单元。存储一个 B-Tree 节点（叶或内部）的序列化数据。
  Page 内通过 VarInt 紧凑编码减小空间占用。
  **章节**：第9章 §9.6
  **相关**：[[B-Tree]]、[[Chunk]]、[[VarInt / VarLong]]、[[Page Pointer]]

- **Page Pointer**: 64-bit 编码的 Page 位置引用。包含 chunk ID、块内偏移、
  长度代码与节点类型四个字段。是 MVStore 跨 Chunk 引用的统一寻址方案。
  **章节**：第9章 §9.6
  **相关**：[[Page]]、[[Chunk]]

- **PageRef**: Page 的内存引用。包装 Page Pointer 与可能的弱引用，支持懒加载与
  缓存淘汰。
  **章节**：第9章 §9.2
  **相关**：[[Page]]、[[Page Pointer]]、[[LIRS]]

- **PageSplit**: 页面分裂。B-Tree 节点满时按中位数分为左右两页，并向上提升分隔键
  到父节点的操作。MVStore 中分裂总是产生新页（COW），不修改原页。
  **章节**：第6章 §6.1、§6.7
  **相关**：[[B-Tree]]、[[COW / Copy-on-Write]]

- **PageStore**: H2 v1.x 使用的旧版存储引擎。在 v2.0 中被 MVStore 取代。
  本书仅在第1章历史背景中提及，不做深入分析。
  **章节**：第1章 §1.1
  **相关**：[[MVStore]]

- **Parser**: 递归下降解析器。将 SQL 文本（经 Tokenizer 词法分析后）解析为
  Expression 树（即执行计划）。
  **章节**：第6章 §6.10、第8章 §8.2
  **相关**：[[Tokenizer]]、[[Recursive Descent Parser]]、[[Expression]]

- **Prepared / Prepared Statement**: 预编译语句。`Prepared` 是所有命令对象的基类，
  封装编译后的执行计划与参数槽。`PreparedStatement` 是其 JDBC 包装。
  **章节**：第7章 §7.1、§7.4
  **相关**：[[CommandContainer]]、[[Parser]]

## Q

- **Query**: 查询基类。`Select`、`SelectUnion`、`CTE` 等查询类型的共同祖先。
  定义 `prepare()` → `optimize()` → `query()` 三阶段执行框架。
  **章节**：第7章 §7.5、第11章 §11.1
  **相关**：[[Select]]、[[Optimizer]]、[[LocalResult]]

## R

- **R-Tree**: 空间索引结构。用于多维数据（地理坐标、矩形区域）的范围查询与
  最近邻查询。每个节点对应一个最小外包矩形（MBR）。H2 通过 `MVRTreeMap` 实现。
  **章节**：第6章 §6.9
  **相关**：[[Index]]、[[MVMap]]

- **Read Committed**: 读已提交。SQL 标准事务隔离级别，仅允许读取已提交的数据。
  H2 默认隔离级别。
  **章节**：第10章 §10.2
  **相关**：[[隔离级别]]、[[Snapshot Isolation]]

- **Recursive Descent Parser**: 递归下降解析器。手写的自顶向下解析方法，每个
  语法规则对应一个递归函数。H2 选择手写解析器而非 yacc/ANTLR，是其代码简洁的关键
  设计选择之一。
  **章节**：第6章 §6.10、第8章 §8.2
  **相关**：[[Parser]]、[[Tokenizer]]

- **Recoverable Operation**: 可恢复操作。MVStore 中所有写操作必须可在崩溃后从
  Undo Log 与 Chunk 链路恢复。设计上排除了不可逆的就地变更。
  **章节**：第9章 §9.7
  **相关**：[[Recover]]、[[Undo Log]]、[[Append-Only]]

- **Recover**: 恢复工具与流程。`org.h2.tools.Recover` 是离线恢复入口，
  也是崩溃后启动时自动恢复路径的复用基础。
  **章节**：第9章 §9.7
  **相关**：[[Recoverable Operation]]、[[File Header]]、[[Chunk]]

- **Repeatable Read**: 可重复读。SQL 标准事务隔离级别，保证同一事务内多次读取
  同一数据的结果一致。
  **章节**：第10章 §10.2
  **相关**：[[隔离级别]]、[[MVCC]]

- **RollbackDecisionMaker**: 回滚决策器。事务回滚时逆序遍历 Undo Log，将每条记录
  恢复到修改前的旧值。
  **章节**：第5章 §5.6
  **相关**：[[CommitDecisionMaker]]、[[Undo Log]]、[[TransactionStore]]

- **RootReference**: MVStore 中指向 root page 的引用。MVCC 的关键——每次提交
  通过 CAS 原子更新该引用，旧版本保留供并发读事务访问。
  **章节**：第9章 §9.2、第10章 §10.4
  **相关**：[[CAS]]、[[MVCC]]、[[Page]]、[[Single Writer]]

## S

- **Savepoint**: 保存点。事务中的中间状态标记，支持 `ROLLBACK TO SAVEPOINT`
  回滚到指定保存点而不放弃整个事务。
  **章节**：第5章 §5.5
  **相关**：[[Transaction]]、[[Undo Log]]

- **Schema**: SQL 模式。H2 的 schema 是表、视图、函数等数据库对象的命名空间容器。
  **章节**：第3章 §3.3
  **相关**：[[SchemaObject]]、[[Database]]

- **SchemaObject**: schema 对象基类。`Table`、`View`、`Index`、`Sequence` 等
  共同祖先，提供命名、所有者、注释、依赖跟踪等通用能力。
  **章节**：第3章 §3.3
  **相关**：[[Schema]]、[[Database]]

- **Select**: SELECT 命令实现类。最复杂的命令类型，聚合查询优化、表过滤、
  索引选择、表达式求值四大功能。
  **章节**：第7章 §7.1、第11章 §11.1
  **相关**：[[Query]]、[[TableFilter]]、[[Optimizer]]

- **SelectGroups**: SELECT 的分组上下文。GROUP BY 与窗口函数的状态容器。
  **章节**：第7章 §7.6
  **相关**：[[Aggregate]]、[[Window 函数]]

- **Serializable**: 可串行化。SQL 标准最严格的事务隔离级别，保证并发执行结果与
  某种串行执行顺序一致。
  **章节**：第10章 §10.2
  **相关**：[[隔离级别]]、[[MVCC]]

- **Session / SessionLocal**: 会话抽象。代表一个数据库连接及其状态——当前事务、
  锁、临时对象、查询缓存。`SessionLocal` 是嵌入式模式实现；`SessionRemote` 是
  服务器模式客户端实现。
  **章节**：第2章 §2.3、第7章 §7.1.5
  **相关**：[[JdbcConnection]]、[[Database]]、[[Lock]]

- **SessionRemote**: 服务器模式下的会话客户端。通过 TCP/PG 协议与远程 H2 服务器
  通信。
  **章节**：第2章 §2.1
  **相关**：[[Session]]、[[TcpServer]]

- **Single Writer**: 单写入者模型。MVStore 任何时刻仅一个线程能修改 RootReference，
  通过此约束 + CAS 实现无锁并发。
  **章节**：第10章 §10.4、第12章 §12.1
  **相关**：[[CAS]]、[[RootReference]]、[[MVCC]]

- **SmallLRUCache**: 小型 LRU 缓存。SessionLocal 用于缓存已编译的查询计划，
  减少重复解析开销。
  **章节**：第11章 §11.1
  **相关**：[[LIRS]]、[[Prepared Statement]]

- **Snapshot Isolation**: 快照隔离。MVCC 实现的隔离级别——事务读取启动时刻的一致性
  快照，写操作采用 first-committer-wins 策略。可能出现写偏斜异常。
  **章节**：第6章 §6.3、第10章 §10.2、§10.4
  **相关**：[[MVCC]]、[[VersionedValue]]、[[写偏斜]]

- **SocketConnect**: H2 网络模式下客户端连接远程数据库的方式。
  **章节**：第2章 §2.2
  **相关**：[[SessionRemote]]、[[TcpServer]]

## T

- **Table**: 表对象基类。`MVTable`、`RegularTable`、`MetaTable` 等共同祖先。
  **章节**：第2章 §2.8、第4章 §4.4
  **相关**：[[MVTable]]、[[Index]]、[[SchemaObject]]

- **TableFilter**: 表过滤器。Optimizer 选择执行计划后，每个表实例化为一个
  TableFilter，承载该表的访问顺序、索引选择、WHERE 条件下推。
  **章节**：第3章 §3.6、第8章 §8.5
  **相关**：[[Select]]、[[IndexCondition]]、[[Optimizer]]

- **TcpServer**: H2 服务器模式的 TCP 监听器。
  **章节**：第3章 §3.9
  **相关**：[[Server]]、[[SessionRemote]]

- **Tokenizer**: 词法分析器。将 SQL 文本拆解为 token 流供 Parser 消费。
  关注字符级细节（关键字识别、字符串字面量、数字、标识符）。
  **章节**：第3章 §3.4、第6章 §6.10
  **相关**：[[Parser]]、[[Recursive Descent Parser]]

- **Transaction**: 事务。H2 支持 ACID 事务特性，提供多级隔离级别。
  事务的实际管理由 TransactionStore 承担。
  **章节**：第5章 §5.5
  **相关**：[[ACID]]、[[TransactionStore]]、[[隔离级别]]

- **TransactionMap**: 事务感知的 MVMap 包装。根据事务可见性规则（快照隔离）
  过滤版本化数据，对应用代码呈现一致性视图。
  **章节**：第10章 §10.4、第12章 §12.1
  **相关**：[[MVMap]]、[[Snapshot Isolation]]、[[VersionedValue]]

- **TransactionStore**: MVStore 之上的事务管理器。使用单独的 MVMap 存储 Undo Log，
  维护事务状态机（OPEN/PREPARED/COMMITTED/ROLLED_BACK）。
  **章节**：第4章 §4.5、第10章 §10.4
  **相关**：[[Transaction]]、[[Undo Log]]、[[CommitDecisionMaker]]、[[VersionedValue]]

- **TxDecisionMaker**: 写冲突检测器。检查目标键的最新版本是否由并发事务写入，
  以决定本事务的写操作能否提交。
  **章节**：第10章 §10.4
  **相关**：[[MVCC]]、[[VersionedValue]]、[[CommitDecisionMaker]]

## U

- **Undo Log**: 撤销日志。事务回滚时恢复数据所需的旧值记录。MVStore 模式下
  Undo Log 是 TransactionStore 维护的一个 MVMap，而非独立日志文件。
  **章节**：第5章 §5.5、§5.6
  **相关**：[[TransactionStore]]、[[CommitDecisionMaker]]、[[RollbackDecisionMaker]]

- **URL Remap**: H2 的 URL 重映射机制。通过配置文件将数据库路径映射到不同的
  物理位置，便于环境迁移。
  **章节**：第2章 §2.2
  **相关**：[[ConnectionInfo]]

## V

- **Value**: H2 值类型基类。所有 SQL 值（ValueInteger、ValueVarchar、ValueNumeric
  等）的祖先，定义比较、转换、序列化接口。
  **章节**：第3章 §3.10
  **相关**：[[Column]]、[[Expression]]

- **VarInt / VarLong**: 变长整数编码。MVStore 用于优化 Page 中整型字段的空间占用——
  小整数仅占 1-2 字节，大整数最多 5 字节（VarInt）或 9 字节（VarLong）。
  **章节**：第9章 §9.6
  **相关**：[[Page]]、[[Chunk]]

- **VersionedValue**: 版本化值。存储同一键的多个版本（committed/uncommitted）以实现
  MVCC。每个版本含 transactionId、operationId、value 三元组。
  **章节**：第4章 §4.5、第10章 §10.4
  **相关**：[[MVCC]]、[[TransactionStore]]、[[VersionedBitSet]]

- **VersionedBitSet**: 版本化位集。TransactionStore 用于跟踪事务可见性的位图结构，
  v2.4.249-SNAPSHOT 中重写为更紧凑的实现。
  **章节**：第10章 §10.4
  **相关**：[[VersionedValue]]、[[TransactionStore]]

## W

- **WAL / Write-Ahead Log**: 预写日志。在写入数据前先将修改记录到日志文件中的策略。
  传统数据库（PostgreSQL/InnoDB）依赖 WAL 实现持久性。MVStore **不使用** 显式 WAL，
  而是通过"B-Tree 版本化根指针 + 原子 Chunk 写入"达到等价效果。
  **章节**：第9章 §9.1
  **相关**：[[Append-Only]]、[[Log-Structured Storage]]、[[Chunk]]

- **Window 函数**: 窗口函数。SQL `OVER` 子句的实现，包括 ROW_NUMBER、RANK、
  LEAD/LAG 等。基于 SelectGroups 分组逻辑。
  **章节**：第7章 §7.6、第11章 §11.1
  **相关**：[[Aggregate]]、[[SelectGroups]]

- **Write Amplification**: 写放大。COW B-Tree 与 Log-Structured 存储中实际物理
  写入量与逻辑数据量的比值。MVStore 的 Compact 与 LIRS 缓存共同抑制写放大。
  **章节**：第12章 §12.1
  **相关**：[[COW / Copy-on-Write]]、[[Compact]]、[[Log-Structured Storage]]

## X

- **XTS-AES 加密**: H2 文件加密所用的分组密码模式。XTS（XEX-based Tweaked
  CodeBook with Ciphertext Stealing）适合存储加密——同一密钥下不同位置加密结果不同。
  **章节**：第9章 §9.8
  **相关**：[[FilePathEncrypt]]

## Z

- **隔离级别**: SQL 事务隔离级别总称。从弱到强：READ_UNCOMMITTED、READ_COMMITTED、
  REPEATABLE_READ、SNAPSHOT、SERIALIZABLE。H2 默认 READ_COMMITTED，MVStore 模式
  下 SNAPSHOT 性能最佳。
  **章节**：第10章 §10.2
  **相关**：[[Read Committed]]、[[Repeatable Read]]、[[Serializable]]、[[Snapshot Isolation]]

- **写偏斜**: Write Skew，快照隔离的特征异常。两个并发事务读取相同数据并各自写入
  不同行，导致违反全局约束。Snapshot Isolation 不能消除写偏斜，需提升至 Serializable。
  **章节**：第10章 §10.2
  **相关**：[[Snapshot Isolation]]、[[Serializable]]

- **扫描抗性**: Scan Resistance，缓存替换算法的属性。指算法在面对一次性扫描负载时
  保持热数据不被淘汰的能力。LIRS 优于 LRU 的关键差异点。
  **章节**：第6章 §6.5
  **相关**：[[LIRS]]

- **测试框架**: H2 的多层测试体系。`org.h2.test` 包覆盖单元测试（JUnit）、
  集成测试（TestAll 主入口）、性能基准（TestPerformance）、模糊测试（TestRandom*）。
  Maven 通过 `mvn test` 触发标准测试目标。
  **章节**：第11章 §11.3
  **相关**：[[Maven]]、[[ISODEBUG]]、[[MVStoreTool]]

---

*共收录 100+ 条核心术语。每条术语包含详细释义、章节定位与相关术语链接，便于读者从任一入口跳转到完整讨论。术语间的 `[[相关]]` 链接形成知识图谱：术语本身的章节字段标注首次出现的详细章节（§子节级）。*
