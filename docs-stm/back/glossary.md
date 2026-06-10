# 术语表

> 本书核心术语的中英文对照和简要定义。条目按字母顺序排列，括号内标注首次出现的章节。

## A

- **ACID**: Atomicity, Consistency, Isolation, Durability — 数据库事务四大特性（第10章）
- **Append-Only**: 仅追加写入策略，MVStore 的核心写入模式：新数据只追加到文件末尾，不覆盖已有数据（第9章）

## B

- **B-Tree**: 平衡多路查找树（Balanced Tree），H2 中作为索引的核心数据结构，支持高效的键值查找和范围扫描（第6章 §6.1）
- **Block**: MVStore 文件的最小分配单元，固定为 4096 字节（匹配磁盘扇区大小）（第9章）

## C

- **Chunk**: MVStore 中一次 commit 写入的所有数据的集合，包含 header、若干 page 和 footer（第6章 §6.4, 第9章）
- **COW / Copy-on-Write**: 写时复制策略：修改数据时不直接覆盖原数据，而是将修改后的数据写入新位置，父节点递归复制更新（第6章 §6.2）
- **Counted B-Tree**: 在内部节点中记录子树条目数的 B-Tree 变种，支持高效的索引访问和范围计数（第9章）
- **CTE**: Common Table Expression，公用表表达式，SQL 中的临时结果集（第1章）

## D

- **DDL**: Data Definition Language，数据定义语言（CREATE, ALTER, DROP 等）（第5章）
- **DML**: Data Manipulation Language，数据操作语言（SELECT, INSERT, UPDATE, DELETE 等）（第5章）

## F

- **File Header**: MVStore 文件开头的 4096 字节元数据块，以 key-value 文本形式存储最新 chunk 的定位信息（第9章 §9.3）
- **Fletcher-32**: 一种高效的 checksum 算法，MVStore 用于校验 chunk footer 的完整性（第9章）
- **Free Space**: MVStore 的空闲空间管理机制，跟踪哪些 block 可被重用（第6章 §6.6）

## H

- **H2**: 纯 Java 实现的嵌入式关系数据库管理系统（Java SQL Database）（第1章）
- **HASH 索引**: 基于哈希表的索引结构，适用于等值查询（第2章）

## I

- **ISODEBUG**: H2 的调试工具，通过 `ISODEBUG` 变量控制调试信息的输出级别（第11章）

## J

- **JDBC**: Java Database Connectivity，Java 数据库连接标准接口（第2章 §2.1）
- **JSON**: H2 支持 JSON 数据的存储和查询（第1章）

## L

- **LIRS**: Low Inter-reference Recency Set，低互引用最近集缓存替换算法，比 LRU 更能抵抗扫描污染（第6章 §6.5）
- **LOB**: Large Object，大对象（CLOB/BLOB），H2 对大对象的存储有独立处理机制（第7章）
- **Log-Structured Storage**: 日志结构存储，按写入顺序追加数据而非原地更新的存储方式（第6章）

## M

- **MVCC**: Multi-Version Concurrency Control，多版本并发控制，通过维护数据的多个版本来实现读写不互斥（第6章 §6.3, 第10章）
- **MVStore**: H2 自 v2.0 起使用的默认存储引擎，基于日志结构的键值存储（第9章）

## O

- **Optimizer**: 查询优化器，负责选择最高效的查询执行计划，包括连接顺序选择和索引选择（第8章）

## P

- **Page**: MVStore 中的最小数据单元，存储 B-Tree 节点（叶节点或内部节点）的序列化数据（第9章 §9.6）
- **Page Pointer**: 64-bit 编码的 page 位置引用，包含 chunk ID、块内偏移、长度代码和节点类型（第9章）
- **PageStore**: H2 v1.x 使用的旧版存储引擎，在 v2.0 中被 MVStore 取代（第1章）
- **Parser**: 递归下降解析器，将 SQL 文本解析为语法树（第6章 §6.10）
- **Prepared Statement**: 预编译语句，H2 通过 `SQL_PREPARED_MINIMAL_SIZE` 等参数控制编译策略（第7章）

## R

- **R-Tree**: 空间索引结构，用于多维数据的范围查询和最近邻查询（第6章 §6.9）
- **Recursive Descent Parser**: 递归下降解析器，H2 的 SQL 解析器采用这种经典的手写解析方式（第8章）
- **Root Reference**: MVStore 中指向 root page 的引用，用于定位 B-Tree 的根节点（第9章）

## S

- **Savepoint**: 保存点，事务中的一个中间状态标记，支持回滚到指定保存点（第5章）
- **Session**: H2 中的会话抽象，代表一个数据库连接及其关联的状态（第2章）
- **SocketConnect**: H2 网络模式下客户端连接远程数据库的方式（第2章）

## T

- **Table Index**: H2 中将表和索引统一处理的抽象层次（第4章）
- **Transaction**: 事务，H2 支持 ACID 事务特性，提供多级隔离级别（第5章 §5.5）
- **TransactionStore**: MVStore 之上的事务管理器，使用单独 map 存储旧版本数据（第4章）

## U

- **Undo Log**: 撤销日志，用于事务回滚时恢复数据到修改前的状态（第5章 §5.5）
- **URL Remap**: H2 的 URL 重映射机制，通过配置文件将数据库路径映射到不同的物理位置（第2章）

## V

- **VarInt / VarLong**: 变长整数编码，MVStore 用于优化 page 中整型字段的空间占用（第9章）

---

*共收录 38 条核心术语。每条术语均标注了首次出现的详细章节（§子节级），便于读者定位正文中的完整讨论。*