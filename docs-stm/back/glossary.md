# 术语表

> 本书核心术语的中英文对照和简要定义。条目按字母顺序排列，括号内标注首次出现的章节。

## A

- **ACID**: Atomicity, Consistency, Isolation, Durability — 数据库事务四大特性（第10章）
- **Append-Only**: 仅追加写入策略，MVStore 的核心写入模式：新数据只追加到文件末尾，不覆盖已有数据（第9章）

## B

- **BackgroundWriter**: 后台写入线程，MVStore 的周期性执行自动提交和紧凑化的后台守护线程（第9章）
- **B-Tree**: 平衡多路查找树（Balanced Tree），H2 中作为索引的核心数据结构，支持高效的键值查找和范围扫描（第6章 §6.1）
- **Block**: MVStore 文件的最小分配单元，固定为 4096 字节（匹配磁盘扇区大小）（第9章）

## C

- **CAS (Compare-And-Swap)**: 比较并交换，一种无锁同步原语，通过 AtomicReference 实现 B-Tree 根引用的原子更新，是 MVCC 无锁读取的核心支撑（第1章, 第10章）
- **Chunk**: MVStore 中一次 commit 写入的所有数据的集合，包含 header、若干 page 和 footer（第6章 §6.4, 第9章）
- **COW / Copy-on-Write**: 写时复制策略：修改数据时不直接覆盖原数据，而是将修改后的数据写入新位置，父节点递归复制更新（第6章 §6.2）
- **Counted B-Tree**: 在内部节点中记录子树条目数的 B-Tree 变种，支持高效的索引访问和范围计数（第9章）
- **CBO / Cost-Based Optimization**: 基于代价的查询优化，Optimizer 根据估算的行数代价从多个执行计划中选择最优方案（第8章）
- **CommandContainer**: 命令容器，包装 Prepared 对象，提供统一的 query/update 执行入口并支持重编译检测（第7章）
- **CommitDecisionMaker**: 提交决策器，事务提交时扫描 undo log 使变更对其他事务可见（第5章）
- **Compact**: 紧凑化/压缩整理，MVStore 通过重写低填充率 Chunk 回收磁盘空间的过程（第6章）
- **CTE**: Common Table Expression，公用表表达式，SQL 中的临时结果集（第1章）

## D

- **DDL**: Data Definition Language，数据定义语言（CREATE, ALTER, DROP 等）（第5章）
- **Deadlock**: 死锁，两个或多个事务互相等待对方释放锁而导致的无限阻塞状态，H2 通过超时检测和等待图分析来识别和处理死锁（第10章）
- **DML**: Data Manipulation Language，数据操作语言（SELECT, INSERT, UPDATE, DELETE 等）（第5章）
- **DbSettings**: 数据库配置项，H2 将缓存大小、日志模式、MVCC 行为等运行时参数集中管理于 DbSettings 类（第3章）

## F

- **File Header**: MVStore 文件开头的 4096 字节元数据块，以 key-value 文本形式存储最新 chunk 的定位信息（第9章 §9.3）
- **Fletcher-32**: 一种高效的 checksum 算法，MVStore 用于校验 chunk footer 的完整性（第9章）
- **FileStore**: 文件存储抽象，MVStore 的 I/O 层，负责 Chunk 的读写、文件锁和存储头的管理（第9章）
- **Free Space**: MVStore 的空闲空间管理机制，跟踪哪些 block 可被重用（第6章 §6.6）

## G

- **Genetic Algorithm**: 遗传算法，H2 优化器在大规模多表 JOIN 时使用的随机搜索优化策略（第8章）

## H

- **H2**: 纯 Java 实现的嵌入式关系数据库管理系统（Java SQL Database）（第1章）
- **HASH 索引**: 基于哈希表的索引结构，适用于等值查询（第2章）
- **Hybrid Strategy**: 混合优化策略，暴力枚举与贪心填充结合的多表连接顺序优化方法（第8章）

## I

- **IndexCondition**: 索引谓词，描述可被索引加速的 WHERE 条件片段（EQUALITY/RANGE/SPATIAL）（第4章）
- **IOT / Index-Organized Table**: 索引组织表，数据行以索引树（B-Tree）的形式直接存储在叶子节点中的表结构（第3章）
- **ISODEBUG**: H2 的调试工具，通过 `ISODEBUG` 变量控制调试信息的输出级别（第11章）

## J

- **JDBC**: Java Database Connectivity，Java 数据库连接标准接口（第2章 §2.1）
- **JSON**: H2 支持 JSON 数据的存储和查询（第1章）

## L

- **LIRS**: Low Inter-reference Recency Set，低互引用最近集缓存替换算法，比 LRU 更能抵抗扫描污染（第6章 §6.5）
- **LOB**: Large Object，大对象（CLOB/BLOB），H2 对大对象的存储有独立处理机制（第7章）
- **LSM-Tree / Log-Structured Merge-Tree**: 日志结构合并树，一种针对写入优化的数据结构，通过分层合并将随机写转换为顺序写（第1章, 第9章）
- **LocalResult**: 本地结果集，查询执行时在内存中构建的中间结果集，支持排序、去重和投影（第7章）
- **Log-Structured Storage**: 日志结构存储，按写入顺序追加数据而非原地更新的存储方式（第6章）

## M

- **MVCC**: Multi-Version Concurrency Control，多版本并发控制，通过维护数据的多个版本来实现读写不互斥（第6章 §6.3, 第10章）
- **MVStore**: H2 自 v2.0 起使用的默认存储引擎，基于日志结构的键值存储（第9章）
- **Maven**: H2 项目的构建工具，管理 Java 依赖、编译和测试生命周期（第11章）
- **Meta Lock**: 元数据锁，Database 内部用于元数据并发控制的轻量级锁机制（第4章）
- **Mode**: SQL 兼容模式，定义 Oracle/MySQL/PostgreSQL/MSSQLServer 的方言差异规则（第3章）

## O

- **Optimizer**: 查询优化器，负责选择最高效的查询执行计划，包括连接顺序选择和索引选择（第8章）

## P

- **Page**: MVStore 中的最小数据单元，存储 B-Tree 节点（叶节点或内部节点）的序列化数据（第9章 §9.6）
- **Page Pointer**: 64-bit 编码的 page 位置引用，包含 chunk ID、块内偏移、长度代码和节点类型（第9章）
- **PageStore**: H2 v1.x 使用的旧版存储引擎，在 v2.0 中被 MVStore 取代（第1章）
- **Parser**: 递归下降解析器，将 SQL 文本解析为语法树（第6章 §6.10）
- **PageSplit**: 页面分裂，B-Tree 节点满时按中位数分为左右两页并向上提升分隔键的操作（第6章）
- **Prepared Statement**: 预编译语句，H2 通过 `SQL_PREPARED_MINIMAL_SIZE` 等参数控制编译策略（第7章）

## R

- **R-Tree**: 空间索引结构，用于多维数据的范围查询和最近邻查询（第6章 §6.9）
- **Recursive Descent Parser**: 递归下降解析器，H2 的 SQL 解析器采用这种经典的手写解析方式（第8章）
- **Read Committed**: 读已提交，SQL 标准定义的一种事务隔离级别，仅允许读取已提交的数据（第10章）
- **Repeatable Read**: 可重复读，SQL 标准定义的一种事务隔离级别，保证同一事务内多次读取同一数据的结果一致（第10章）
- **RollbackDecisionMaker**: 回滚决策器，事务回滚时逆序遍历 undo log 恢复修改前的旧值（第5章）
- **Root Reference**: MVStore 中指向 root page 的引用，用于定位 B-Tree 的根节点（第9章）

## S

- **Savepoint**: 保存点，事务中的一个中间状态标记，支持回滚到指定保存点（第5章）
- **Serializable**: 可串行化，SQL 标准中最严格的事务隔离级别，保证并发事务的执行结果与某种串行执行顺序一致（第10章）
- **Session**: H2 中的会话抽象，代表一个数据库连接及其关联的状态（第2章）
- **Snapshot Isolation**: 快照隔离，一种多版本并发控制（MVCC）隔离级别，事务读取一致性快照，写操作采用 first-committer-wins 策略（第10章）
- **Single Writer**: 单写入者模型，MVStore 使用单个写入线程配合 CAS 原子更新 RootReference 的无锁并发策略（第12章）
- **SmallLRUCache**: 小型 LRU 缓存，SessionLocal 用于缓存已编译的查询计划以减少重复解析开销（第11章）
- **SocketConnect**: H2 网络模式下客户端连接远程数据库的方式（第2章）

## T

- **Table Index**: H2 中将表和索引统一处理的抽象层次（第4章）
- **Transaction**: 事务，H2 支持 ACID 事务特性，提供多级隔离级别（第5章 §5.5）
- **Tokenizer**: 词法分析器，将 SQL 文本拆解为 token 流供递归下降解析器消费（第3章）
- **TransactionMap**: 事务感知的 MVMap 包装，根据事务可见性规则（快照隔离）过滤版本化数据（第12章）
- **TransactionStore**: MVStore 之上的事务管理器，使用单独 map 存储旧版本数据（第4章）
- **TxDecisionMaker**: 写冲突检测器，检查目标键的最新版本是否由并发事务写入以决定提交或回滚（第10章）

## U

- **Undo Log**: 撤销日志，用于事务回滚时恢复数据到修改前的状态（第5章 §5.5）
- **URL Remap**: H2 的 URL 重映射机制，通过配置文件将数据库路径映射到不同的物理位置（第2章）

## V

- **VarInt / VarLong**: 变长整数编码，MVStore 用于优化 page 中整型字段的空间占用（第9章）
- **VersionedValue**: 版本化值，存储同一键的多个版本（committed/uncommitted）以实现 MVCC 事务隔离（第10章）

## W

- **WAL / Write-Ahead Log**: 预写日志，在写入数据前先将修改记录到日志文件中的策略。MVStore 采用隐式日志方式（通过 B-Tree 版本化根指针 + 原子 Chunk 写入），不依赖传统 WAL（第9章）
- **Write Amplification**: 写放大，COW B-Tree 和 Log-Structured 存储中实际物理写入量与逻辑数据量的比值（第12章）

---

*共收录 73 条核心术语。每条术语均标注了首次出现的详细章节（§子节级），便于读者定位正文中的完整讨论。*