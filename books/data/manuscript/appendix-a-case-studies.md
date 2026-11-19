# 附录 A：端到端案例研究

> 本附录用三个端到端案例把分散在第 1-10 章的关键论述连成单线叙事：
> 案例 A 跟踪一条 SELECT 从 JDBC 入口到磁盘的全过程；
> 案例 B 拆解一次 INSERT+UPDATE+COMMIT 事务在内存与磁盘上的事件链；
> 案例 C 演示崩溃后恢复启动的决策路径，包括正常分支与异常分支。
> 每个步骤均给出 §X.Y 回指，便于读者按需深入原章节。

本附录不引入新的源码论断——所有事实都来自正文章节，
附录的价值在于把按主题切分的章节重新拼成按时间切分的故事，
让读者获得完整的端到端心智模型。

---

## A.1 案例 A：一条 SELECT 从 JDBC 到磁盘

凌晨三点，某线上服务执行了一条最普通不过的语句：

```sql
SELECT * FROM users WHERE id = 42;
```

调用方拿到结果用了不到十毫秒，但这十毫秒里 H2 引擎穿过了 JDBC、Session、
Parser、Optimizer、TableFilter、B-Tree、Page Cache 与 FileStore 八个层次。
本案例以这条等值点查为主线，把分散在第 4、6、7、8、9 章的关键节点重新
串接成一条端到端的执行轨迹，并在每一步给出 §X.Y 回指，便于读者按图索骥。
本节不复述原文段落，只做"叙事重组"——把固定步骤按时间顺序压扁成一根
单线，再以子流程图刻画其内部决策。

如图 A-1 所示，全链路泳道图给出整体形貌；后续 A-2 至 A-6 各自聚焦一个
子阶段。读者若只想了解整体，可只读 §A.1.1 与 §A.1.8；若想深入某一步，
可沿 `详见 §X.Y` 跳转回原章节。

**图 A-1: 串联 SELECT 八泳道执行轨迹**

```text
  时间轴 ──►       准备阶段                     执行阶段
  ┌──────────┐  ┌────────────────────┐  ┌───────────────────────┐
  │  JDBC    │  │ executeQuery(sql)  │  │ rs.next() / getInt()   │
  │          │  │  ↓ prepareCommand  │  │  ↑ JdbcResultSet 包装  │
  └────┬─────┘  └──────────┬─────────┘  └───────────▲───────────┘
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐  ┌────────────────────┐  ┌───────────┴───────────┐
  │ Session  │  │ prepareLocal()     │  │ lock() / unlock()      │
  │ Local    │  │  查询缓存检查       │  │ checkParameters()      │
  └────┬─────┘  └──────────┬─────────┘  └───────────▲───────────┘
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐  ┌────────────────────┐              │
  │ Parser   │  │ tokenize()         │              │
  │          │  │  parseSelect()     │              │
  │          │  │  → Select 节点      │              │
  └────┬─────┘  └──────────┬─────────┘              │
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐  ┌────────────────────┐              │
  │ Optimizer│  │ optimize()         │              │
  │          │  │  cost = rows*N+...  │              │
  │          │  │  PlanItem 选定      │              │
  └────┬─────┘  └──────────┬─────────┘              │
       │                   │                        │
       ▼                   ▼                        │
  ┌──────────┐                      ┌──────────────────────────┐
  │TableFiltr│◄─── plan ────────────│ topTableFilter.next()    │
  │          │                      │  cursor.find(SearchRow)  │
  │          │                      │  isOk(filterCondition)   │
  └────┬─────┘                      └────────────┬─────────────┘
       │                                         │
       ▼                                         ▼
  ┌──────────┐                      ┌──────────────────────────┐
  │  B-Tree  │                      │ MVMap.get(key=42)        │
  │  索引    │                      │  Page.binarySearch()     │
  └────┬─────┘                      └────────────┬─────────────┘
       │                                         │
       ▼                                         ▼
  ┌──────────┐                      ┌──────────────────────────┐
  │PageCache │                      │ CacheLongKeyLIRS.get(pos)│
  │  LIRS    │                      │  hot/cold 队列状态变更    │
  └────┬─────┘                      └────────────┬─────────────┘
       │ miss                                    │ hit
       ▼                                         ▼
  ┌──────────┐                      ┌──────────────────────────┐
  │FileStore │                      │ readFully(ByteBuffer)    │
  │          │                      │  Chunk 解压 → Page 反序列化│
  └──────────┘                      └──────────────────────────┘
```


该泳道图按"准备阶段"与"执行阶段"两段切分时间轴：准备阶段把 SQL 文本翻译
成可执行计划，执行阶段则驱动游标向 Store 层取行。Parser 与 Optimizer 是
纯准备阶段组件，FileStore 是纯执行阶段组件，其余四层跨阶段（详见 §7.5.1）。

下面 8 个步骤按时间顺序展开，每步附带一段动机说明、一段源码引用与一处
回指——读者可以直接以 §X.Y 跳转回原章节深入阅读。

### A.1.1 JDBC 入口与 SessionLocal 路由

应用线程调用 `Statement.executeQuery(String)` 后，控制权落入 H2 的
`org/h2/jdbc/JdbcStatement.java`。该方法不直接执行 SQL，而是先把当前
连接绑定的 `SessionLocal` 取出，再以 `session.prepareCommand(sql, fetch)`
进入引擎层。这条边界把"网络/JDBC 协议"与"SQL 引擎"切开：JDBC 层只关心
ResultSet 包装、超时取消与生成键回传；SQL 引擎层只关心解析、优化与执行。
等值点查 `WHERE id = 42` 在此处仍以原始字符串形式存在，没有任何编译动作。

```java
// org/h2/jdbc/JdbcStatement.java:executeQuery
synchronized (session) {
    setExecutingStatement(command);
    ResultInterface result = command.executeQuery(maxRows, scrollable);
    resultSet = new JdbcResultSet(conn, this, command, result, ...);
}
```

`SessionLocal` 是会话级的"上下文中枢"：它持有当前事务、锁集合、临时表、
查询缓存与自增主键计数器。准备阶段的所有路径都先穿过 `SessionLocal`，再
分发给 `Parser` 或 `Command` 子类（详见 §4.2.4）。会话锁通过
`synchronized(session)` 串行化同一连接的请求，避免 JDBC 用户在多线程下
并发使用同一连接造成内部状态错乱（详见 §7.1.1）。

### A.1.2 Parser 词法切分与递归下降

`SessionLocal.prepareLocal(sql)` 在缓存未命中时构造 `Parser` 实例，调用
`Parser.prepareCommand(sql)`。Parser 的工作分两步：先由内置 Tokenizer
按字符流扫出 token 序列；再由 `parseSelect()` 等手写递归下降函数把 token
组装成 AST。H2 的特别之处在于：解析器直接构造可执行的 `Expression` 树，
而非先构造抽象 AST 再翻译——这种"AST 即执行计划"的紧耦合简化了内存模型，
但要求重写阶段必须就地变换原树（详见 §7.2.3）。

```java
// org/h2/command/Parser.java:prepareCommand
read();
Prepared p = parsePrepared();   // → parseSelect() → Select
p.setSQL(sql);
p.setParameterList(parameters);
return p;
```

如图 A-2 所示，对 `SELECT * FROM users WHERE id = 42` 的 AST 由一个
`Select` 根节点、一个 `TableFilter` 引用和一棵 `Comparison` 子树组成。
`Comparison` 的左子树是 `ExpressionColumn(id)`，右子树是 `ValueInteger(42)`。
这棵树在后续阶段被反复访问：Optimizer 用它估算选择率，TableFilter 用它
抽取索引条件，最终在执行阶段由 `Comparison.evaluate()` 完成行级判定
（详见 §7.6.3）。

**图 A-2: 展示等值点查的表达式树骨架**

```text
                  Select(root)
                    │
        ┌───────────┼─────────────┐
        ▼           ▼             ▼
   visibleCols  filterList   condition
   ['*' 展开]  [TableFilter] Comparison(=)
                    │           │   │
                    ▼           ▼   ▼
                MVTable     ExpCol  ValInt
                 users      id      42
```


`*` 在 `Select.prepare()` 中被展开为表的全部列引用；`id = 42` 中的字面量
`42` 被装箱为 `ValueInteger` 并在类型推导阶段与 `id` 列的 INT 类型对齐
（详见 §7.2.7）。Parser 在此节点完成符号绑定但不做任何代价估算。

### A.1.3 Prepared 编译与查询缓存

回到 `SessionLocal.prepareLocal()`，编译完的 `Prepared` 被包装成
`CommandContainer` 并放入会话级 `Map<String, Command>` 缓存。下次同一
SQL 文本进入时，会话先以 `sql` 为 key 查询缓存命中，并通过 schema 版本号
比对决定是否需要重编译——DDL 修改了表结构后，旧 Prepared 必须作废
（详见 §7.3.1、§7.3.6）。等值点查在生产环境通常会反复出现，缓存命中率
直接决定 OLTP 短查询的延迟下界。

```java
// org/h2/engine/SessionLocal.java:prepareLocal
Command command = queryCache != null ? queryCache.get(sql) : null;
if (command == null || !command.canReuse()) {
    Parser parser = new Parser(this);
    command = parser.prepareCommand(sql);
    if (queryCache != null && command.isCacheable()) {
        queryCache.put(sql, command);
    }
}
```

`CommandContainer.canReuse()` 检查参数是否仍可绑定、Schema 是否未变更，
两者皆通过则跳过整个 Parser 与 Optimizer 阶段，直接进入执行（详见 §7.4.4）。
本案例首次执行走完整路径，第二次起直接在 `CommandContainer.query()` 处分叉。

### A.1.4 Optimizer 代价模型与计划选择

`Prepared.prepare()` 触发 `Optimizer.optimize()`。对单表查询，Optimizer
跳过连接顺序枚举，仅遍历 `users` 表的所有索引，为每个候选生成一个
`PlanItem`，调用 `index.getCost(...)` 估算代价。对 `WHERE id = 42`：

- 主键索引上，`id` 是首列，匹配等值条件，代价模型给出 `cost ≈ 3 + lookupCost`，等于一次 B-Tree 路径下降。
- 非主键的二级索引若不包含 `id`，则代价为全索引扫描的 `rowCount * STEP_COST`。
- 全表顺序扫描代价为 `rowCount * 10`。

```java
// org/h2/table/TableFilter.java:getBestPlanItem
for (int i = 0; i < indexes.size(); i++) {
    Index index = indexes.get(i);
    double cost = index.getCost(session, masks, filters, ...);
    if (cost < bestCost) { bestIndex = index; bestCost = cost; }
}
```

如图 A-3 所示，三种候选的代价矩阵呈数量级差距。代价模型是乘法复合：
`rowCount × selectivity × ioWeight + lookupCost`，其中 `selectivity` 由
`IndexCondition` 的掩码决定（详见 §8.3.2、§8.4.4）。等值条件在主键上
返回最小可能选择率 `1/rowCount`，因此主键索引必然胜出。

**图 A-3: 对比三种候选索引在等值点查下的代价矩阵**

```text
  候选计划             掩码      选择率    代价     被选中
  ────────────────────────────────────────────────────────
  PK_USERS (id) ─────  EQUALITY  1/N       3.0      ★
  IDX_USERS_NAME ────  无匹配    1.0       N×2.0
  全表扫描 ──────────   —         1.0       N×10.0
                        │          │         │
                        ▼          ▼         ▼
                    IndexCond  Statistics  PlanItem.cost
```


Optimizer 的早停机制在此场景几乎瞬间生效——首个候选即接近理论下界，
`canStop()` 直接返回 `true`，无需进入暴力枚举或遗传策略（详见 §8.1.3）。

### A.1.5 TableFilter 索引匹配与条件下推

Optimizer 选定 `PK_USERS` 后，把 `PlanItem` 安装到 `TableFilter` 上。
`TableFilter` 是 H2 执行引擎的迭代器抽象：它包装一张表、一条索引和一组
`IndexCondition`，对外提供 `next()` 方法逐行返回。

```java
// org/h2/table/TableFilter.java:prepare
this.index = item.getIndex();
this.indexConditions = filters; // 等值掩码 + 范围掩码
session.getDatabase().getCompareMode();
```

`WHERE id = 42` 在 `TableFilter.prepare()` 中被拆成两类：可下推到索引的
`IndexCondition.EQUALITY(id, 42)` 与剩余的 `filterCondition`。等值点查
全部条件都能下推，因此 `filterCondition == null`，每行都不必再做表达式
求值（详见 §8.4.2、§8.4.3）。索引下推把"过滤"从执行层迁移到存储层，
是 OLTP 微秒级延迟的关键来源之一。

`TableFilter` 在 `next()` 中先用 `IndexCondition` 构造 `SearchRow(id=42)`，
再调用 `index.find(session, first=42, last=42)` 返回 `Cursor`。Cursor
本身只持有 B-Tree 路径与位置游标，不立刻读取数据（详见 §8.5.1、§5.1.1）。

### A.1.6 B-Tree 路径下降与 Page Pointer 解码

`MVPrimaryIndex.find()` 委托给 `MVMap.get(42L)`，后者从 `RootReference`
拿到当前根 `Page`，再沿 B-Tree 自顶向下做二分查找。每一层都执行一次
`Page.binarySearch(key)`：在键数组上做经典二分，定位下一层子页指针，
直到落入叶节点（详见 §6.1.4）。

```java
// org/h2/mvstore/Page.java:binarySearch
int low = 0, high = entryCount - 1;
while (low <= high) {
    int x = (low + high) >>> 1;
    int cmp = compare(keys[x], key);
    if (cmp < 0) low = x + 1;
    else if (cmp > 0) high = x - 1;
    else return x;
}
return -(low + 1);
```

每一层的子指针不是简单的内存引用，而是一个 64 位的 `Page Pointer`，
编码了 `chunkId | offset | length | type`。如图 A-4 所示，路径下降在三层
B-Tree 上至多触发三次 Page 解码（详见 §6.1.2）。

以下三张图共同呈现等值点查的三个视角：图 A-4 刻画三层 B-Tree 的路径下降，图 A-5 拆解 Page Pointer 的 64 位字段布局，图 A-6 归纳 LIRS 缓存在等值点查下热/冷队列的状态转移。

**图 A-4: 刻画三层 B-Tree 在等值点查下的路径下降**

```text
       Root (NonLeaf, level 2)
       ┌─────────────────────────┐
       │ keys: [200, 400, 600]   │
       │ children:[P1,P2,P3,P4]  │
       └────────┬────────────────┘
       42 < 200 │ 取 P1
                ▼
       Inner (NonLeaf, level 1)
       ┌─────────────────────────┐
       │ keys: [50, 100, 150]    │
       │ children:[L1,L2,L3,L4]  │
       └────────┬────────────────┘
       42 < 50  │ 取 L1
                ▼
       Leaf (level 0)
       ┌─────────────────────────┐
       │ keys: [10,20,30,42,48]  │
       │ values: [r10,r20,...,r48]│
       └─────────────────────────┘
                ▲
                │ binarySearch → idx=3
                │ value = SearchRow(42, name='Bob', ...)
```


每条路径上的子指针均需先经 Page Pointer 解码才能加载下一层。如图 A-5
所示，64 位指针的字段排布把"哪个 Chunk、Chunk 内偏移、Page 长度、是否
叶节点"压缩进一个 `long`，使得任何节点的物理定位无需额外查表
（详见 §9.6.4）。

**图 A-5: 拆解 Page Pointer 64 位字段布局**

```text
  bit  63        32 31      8 7      1 0
       ┌───────────┬──────────┬───────┬─┐
       │ chunkId   │  offset  │length │T│
       │ 32 位     │   24 位   │  6 位 │1│
       └─────┬─────┴────┬─────┴───┬───┴─┘
             │          │         │   └── type: 0=Leaf 1=NonLeaf
             │          │         └────── length: 解压后块长度桶号
             │          └──────────────── offset: Chunk 内字节偏移
             └─────────────────────────── chunkId: 跨 Chunk 引用标识

  示例：0x0000_0007_0001_5C09
        chunkId=7, offset=22016, length 桶=12, type=Leaf
```


24 位偏移配合 6 位长度桶，保证 H2 的单 Chunk 上限为 16 MB；超过即触发
新 Chunk（详见 §9.3.2）。

### A.1.7 LIRS 缓存命中与 FileStore 物理 I/O

每次解码出 Page Pointer，`MVMap` 都先调用 `cache.get(pos)` 询问 LIRS
缓存。`CacheLongKeyLIRS` 维护两条链表：Stack 记录"近期被访问且预计仍
热"的页，Queue 记录"冷页候选"。命中分两类：在 Stack 上命中只把节点
提升到栈顶；在 Queue 上命中则进一步看节点是否曾在 Stack 上出现过——
若是，则提升为"重用热页"，挤出栈底冷页（详见 §6.5.3）。

```java
// org/h2/mvstore/cache/CacheLongKeyLIRS.java:get
Entry<V> e = find(key);
if (e == null) return null;             // miss
if (e.isHot()) { hit++; access(e); }    // 直接命中
else hitNonResident(e);                 // 历史栈命中 → 升级
return e.value;
```

如图 A-6 所示，等值点查只触碰三个 Page，对扫描型负载常见的"短期高频
访问无未来"模式天然抗污染——这正是 LIRS 相对 LRU 的核心优势
（详见 §6.5.5）。

**图 A-6: 归纳 LIRS 在等值点查下热/冷队列的状态转移**

```text
  访问序列：Root → Inner → Leaf （三次 get）
  ─────────────────────────────────────────────────────────
  初态       Stack: [P9, P8, P7]      Queue: [Q3, Q2, Q1]
  访问 Root  Stack: [Root, P9, P8]    Queue: [Q3, Q2, Q1]
             P7 退出栈（被 Root 顶出）
  访问 Inner Stack: [Inner, Root, P9] Queue: [P8, Q3, Q2]
             P8 从栈底降级到 Queue 头
  访问 Leaf  Stack: [Leaf, Inner,Root]Queue: [P9, P8, Q3]
             P9 降级；Q1, Q2 被驱逐写盘
  ─────────────────────────────────────────────────────────
  关键：等值点查只增三个 hot，不会冲掉更早的工作集 P*。
        相同访问换成 LRU 链表，则会把 P9/P8/P7 全部挤出。
```


若三次 `cache.get` 全部命中，整次查询不触发任何磁盘 I/O，延迟落在
百微秒量级。一旦未命中，`MVStore.readPage(pos)` 接管：从 Page Pointer
解出 `chunkId`，查 `Chunk` 元数据拿到文件偏移，调用
`FileStore.readFully(ByteBuffer, position)` 读入字节，再走 LZF 解压、
CRC 校验、Page 反序列化四道工序（详见 §9.2.6、§9.6.4）。读完的 Page
回填进 LIRS 缓存，下次同 key 即命中。

### A.1.8 Value 解码与 ResultSet 回包

叶节点中 `key=42` 对应的 `value` 是一个 `ValueRow`，内部按列序号存放
`Value[]`。`MVPrimaryIndex` 把 `ValueRow` 包装成 `Row` 后交还给
`TableFilter`。`Select.queryWithoutCache()` 把每个被选中的行追加进
`LocalResult`：等值点查最多得到一行，因此 `LocalResult` 立即闭合
（详见 §5.1.1）。

```java
// org/h2/command/query/Select.java:queryWithoutCache 关键片段
while (topTableFilter.next()) {
    if (condition == null || condition.getBooleanValue(session)) {
        Value[] row = expressions ... evaluate ...;
        result.addRow(row);
        if (limitRows != -1 && result.getRowCount() >= limitRows) break;
    }
}
```

`LocalResult` 经 `CommandContainer.executeQuery()` 上抛，被 `JdbcResultSet`
重新包装为 JDBC 协议层对象。应用线程在 `rs.next()` 返回 `true` 后调用
`rs.getInt("id")`，触发 `ValueInt.getInt()`——这是整个链路最后一次
类型转换。会话锁在结果集闭合时释放（详见 §7.4.2、§4.2.4）。至此，
"SELECT 42" 完成从 SQL 文本到磁盘字节再返回到 Java 整数的完整往返。

回顾全流程：JDBC 与 SessionLocal 提供边界与上下文，Parser 把字符串
变成 `Expression` 树，Optimizer 用代价模型把搜索空间剪到一条路径，
TableFilter 把过滤条件下推给索引，B-Tree 的 Page Pointer 把逻辑键映射
到物理偏移，LIRS 与 FileStore 决定这次访问到底打中内存还是磁盘，最后
`LocalResult` 与 `JdbcResultSet` 把结果折回 JDBC 协议——八个层次配合，
整体延迟可压到亚毫秒级。

### A.1.X 思考小结

下面三道自查题用来检验读者是否能把本案例的关键决策迁移到其他场景。

**1. 🟢★ 叙述等值点查下 Optimizer 为何能在第一次循环就调用 `canStop()` 提前终止？换成范围查询 `id BETWEEN 100 AND 200` 时这一终止条件是否仍然成立？**

> 提示：从代价矩阵的"理论下界"与索引选择率的关系入手，比较等值与范围两种 IndexCondition 的代价复合公式。
> 回顾：§8.1.3、§8.4.4

**2. 🔵★★ 若把 H2 的 LIRS 缓存替换为简单 LRU，本案例的三次 Page 访问延迟会如何变化？再设想一个并发的全表扫描线程同时运行，两种缓存策略在工作集保持上的差异会落在哪一步？**

> 提示：抓住 LIRS 的"Stack + Queue 双队列"如何区分一次性访问与重用访问，并结合扫描型负载的污染模式。
> 回顾：§6.5.3、§6.5.5

**3. 🟠★★★ 在 H2 测试目录下编写一段 JUnit 用例，对同一条 `SELECT * FROM users WHERE id = ?` 反复执行 1 万次并打印 `CommandContainer.canReuse()` 的命中次数；再在两次执行之间穿插一条 `ALTER TABLE users ADD COLUMN tag VARCHAR(8)`，观察缓存被作废的瞬间。**

> 提示：参考 `org/h2/test/db/TestPreparedStatement.java` 的现有测试骨架；DDL 触发的缓存失效路径见正文相应说明。
> 回顾：§7.3.6、§7.4.4

---

> **本案例的回指清单**：§4.2.4、§5.1.1、§6.1.2、§6.1.4、§6.5.3、§6.5.5、§7.1.1、
> §7.2.3、§7.2.7、§7.3.1、§7.3.6、§7.4.2、§7.4.4、§7.5.1、§7.6.3、§8.1.3、§8.3.2、
> §8.4.2、§8.4.3、§8.4.4、§8.5.1、§9.2.6、§9.3.2、§9.6.4。读者可按这条索引在原章节
> 中验证每一处源码引用。

---

## A.2 案例 B：一次 INSERT+UPDATE+COMMIT 事务的全链路

本案例承接案例 A 的"读路径"叙事，转入 H2 的"写—提交路径"。读路径关心的是
"在某一刻看到了什么"，写路径关心的则是"如何让一组修改原子地变成所有事务都
能看到的事实"。两者在 H2 内部由同一套 MVCC 机制串联——`VersionedValue`、
`TransactionStore`、`RootReference`——但在写入侧增加了 Undo Log、
`TxDecisionMaker`、`CommitDecisionMaker`、后台 Chunk 落盘与 Checkpoint
等关键环节。本案例选取一个被工程实践高频使用的最小完整场景：先 `INSERT` 一
条用户记录，再 `UPDATE` 同一行的某个字段，最后通过显式 `COMMIT` 让该事务对
其他会话可见。

为了让叙事可被源码逐行追溯，案例使用如下脚本作为运行实例。所有 §X.Y 反向
引用、`ClassName.java:行号`、字段名均以仓库当前主分支 (`org/h2/...`) 为
准；与案例 A 一致，文中不再重复打印每一行 SQL 的 AST/计划，而是聚焦在
TransactionStore 状态、`MVMap` 根引用、Undo Log、可见性翻转与 Chunk 持久
化这一条主线上。

```sql
-- 运行实例：账号表 users(id BIGINT PK, name VARCHAR, email VARCHAR)
-- 由会话 S1 执行；S2 是与 S1 并发的只读观察者。
BEGIN;                                              -- 步骤 ①
INSERT INTO users(id, name, email)
       VALUES (101, 'Alice', 'alice@example.com');  -- 步骤 ②
UPDATE users SET email = 'alice@h2.local'
       WHERE id = 101;                              -- 步骤 ③
COMMIT;                                             -- 步骤 ④
```

预期外部行为是：在步骤 ④ 之前，S2 看到的是"键 101 不存在"；步骤 ④ 完成后，
S2 看到的是 `(101, 'Alice', 'alice@h2.local')`。本案例要回答的问题是：
**"步骤 ④ 之中，到底哪一行 Java 代码使得 S2 的观感发生了瞬时翻转？"**
答案被分散在 `org/h2/engine/SessionLocal.java`、
`org/h2/mvstore/tx/TransactionStore.java`、
`org/h2/mvstore/RootReference.java` 与
`org/h2/mvstore/MVStore.java` 之中，下文按管线顺序逐段展开。

### A.2.1 beginTransaction：会话注册与 OPEN 状态登记

会话层入口为 `SessionLocal.getTransaction()`（`SessionLocal.java`
事务子句首次写入时延迟调用），它在内部调用
`TransactionStore.begin(...)`（`TransactionStore.java:455` 附近）。
`begin` 做三件事：在 `openTransactions`（`VersionedBitSet`，COW）
中通过 CAS 翻转一位、为该事务分配独立的 `undoLogs[txId]` 子映射、
把 `Transaction` 对象写入 `transactions[txId]` 槽位。事务 ID 随即被
固定为后续所有 `operationId` 的高 24 位（详见 §4.5 Undo Log 编码）。

如图 A-7 所示，注册流程对全局状态的影响是**纯增量的**：除了 BitSet 内部
通过 COW 创建新版本外，没有任何已存在的数据结构被写改。这与 §10.5
RootReference 的不可变性规约一致——任何"并发可见的状态"都通过整体替换
而非就地修改来表达。

```text
                        SessionLocal.beginTransaction()
                                 │
                                 ▼
                  TransactionStore.begin(isolationLevel)
                                 │
   ┌─────────────────────────────┼─────────────────────────────┐
   ▼                             ▼                             ▼
┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ openTransactions│   │ undoLogs[txId]      │   │ transactions[txId]  │
│ COW 翻转 bit[id]│   │ 新建 MVMap          │   │ new Transaction(    │
│ via CAS         │   │ name=".undoLog.id"  │   │   status=OPEN, …)   │
└────────┬────────┘   └──────────┬──────────┘   └──────────┬──────────┘
         │                       │                         │
         └───────────┬───────────┴───────────┬─────────────┘
                     ▼                       ▼
            VersionedBitSet 新版本     Transaction 对象就绪
                     ▼                       ▼
            其他事务可见到 "txId 已开启"，但不可见任何数据变更
```
**图 A-7: 描绘 begin 对全局事务表的三项写入**

注册完成后，会话拿到一个尚未关联任何变更的 `Transaction` 句柄。其
`status` 字段固定为 `OPEN`（详见 §4.5 状态机定义）。在第一次写操作触达
之前，`undoLogs[txId]` 是空的子映射，对其他事务而言这条事务"在场但无
影响"。这种"先注册后写入"的次序是 H2 在崩溃恢复中识别 in-flight 事务的
必要前提（详见 §9.7 TransactionStore 的恢复）。

### A.2.2 INSERT：TransactionMap.put 写入未提交 VersionedValue 与 Undo Log

`INSERT` 路径的入口是 `org/h2/command/dml/Insert.update()`，它穿过
`MVTable.addRow()`，最终调用到 `TransactionMap.putCommitted(...)` 或
`TransactionMap.put(key, value)`。后者把工作委托给
`MVMap.operate(key, value, txDecisionMaker)`（`MVMap.java`），并在
进入 B-Tree 改写之前先调用
`TxDecisionMaker.logAndDecideToPut()`（`TxDecisionMaker.java:162`），
后者**先把旧值写入 Undo Log，再返回 PUT 决策**。这里"旧值"对 INSERT
而言是 `null`，因此 `Record(mapId=usersDataMapId, key=101,
oldValue=null)` 被追加到 `undoLogs[txId]`，随后真正的
`VersionedValue` 写入数据 map。

如图 A-8 所示，单次 INSERT 在 H2 内部其实是"两次有序写"：先写 Undo
Log（保证回滚可逆），再写数据（保证读取可见性）。这与传统 WAL 数据库的
"先日志再页面"思想一致，但日志载体本身就是一棵 MVMap（详见 §9.4 为什么
不需要 WAL）。

```text
   Insert.update()
        │
        ▼
   MVTable.addRow(row)
        │
        ▼
   TransactionMap.put(101, Row{Alice,…})
        │
        ▼
   MVMap.operate(101, value, TxDecisionMaker)
        │
   ┌────┴──────────────────────────────────────┐
   ▼ 1. logAndDecideToPut                       │
 Undo Log 子映射 undoLogs[txId]:                │
   key   = (txId << 40) | logId=0               │
   value = Record(mapId, key=101, oldValue=null)│
   ▼ 2. Decision.PUT                            │
   ▼ 3. CAS 改写 RootReference                  │
 users 数据 map[101] =                           │
   VersionedValue{                              │
     operationId   = (txId << 40) | logId=0,    │
     committedValue= null,                      │
     currentValue  = Row{101,Alice,alice@…}     │
   }                                            │
   └────────────────────────────────────────────┘
```
**图 A-8: 拆解 INSERT 的"先日志后数据"两次写**

`VersionedValue` 的三个字段对应三种事务视角：`operationId` 标识"谁在
写"，`committedValue` 标识"全局已提交版本"（INSERT 阶段为 `null`，
因为之前不存在），`currentValue` 标识"当前事务可见的最新值"（详见 §10.2
VersionedValue 结构）。其他事务此刻读取 `key=101` 时，通过
`TransactionMap.get()` 内部分支会判断 `operationId` 不属于自己且事务未
提交，于是返回 `committedValue=null`，即"看不到这行"。

> **源码路径**：`org/h2/mvstore/tx/TransactionMap.java`、
> `org/h2/mvstore/tx/TxDecisionMaker.java:73-166`、
> `org/h2/mvstore/MVMap.java:operate(...)`。

### A.2.3 UPDATE：第二个未提交版本与 TxDecisionMaker 的冲突分支

紧随 INSERT 的 `UPDATE users SET email='alice@h2.local' WHERE
id=101` 同样路由到 `TransactionMap.put(101, newRow)`。但这一次
`existingValue` 已经是上一步留下的 `VersionedValue`，其 `operationId`
属于**当前事务自身**。`TxDecisionMaker.decide()`（`TxDecisionMaker.java:73-116`）
会进入"情况 2：同一事务的修改"分支，再次调用
`logAndDecideToPut(currentValue=oldRow, committedValue=null)`，
追加第二条 Undo Log 记录 `Record(mapId, key=101, oldValue=oldRow)`，
随后用新 `VersionedValue` 覆盖数据 map 中 `key=101` 的槽位。

这里的关键工程细节是：**Undo Log 的旧值是"步骤前的可见值"，而不是"原始
未修改值"。** 因此回滚时，逆序回放两条 Undo Log 即可一步步退回到 INSERT
之前的状态——先把 `key=101` 还原为 `oldRow`，再把它移除，回到 `null`
（详见 §5.6 ROLLBACK 与 §4.5 rollbackTo 流程）。

```text
   UPDATE 触发后 TxDecisionMaker.decide(existing) 决策树:

   existing == null ? ───── YES ──▶ 情况 1: 直接 PUT (不应出现)
            │
            NO
            ▼
   getOperationId(existing) == NO_OPERATION_ID ? ─ YES ─▶ 情况 1: PUT
            │
            NO
            ▼
   blockingId == thisTxId ? ─── YES ──▶ 情况 2: 自写覆盖
            │                                │
            NO                               ▼ logAndDecideToPut
            ▼                          追加 Undo Log entry #2
   isCommitted(blockingId) ? ── YES ─▶ 情况 3: 已提交,可写
            │
            NO
            ▼
   existsBlockingTx ? ───── YES ──▶ 情况 4: ABORT,等待
            │
            NO
            ▼
   isRepeatedOperation ? ── YES ──▶ 情况 5: 残留覆盖
            │
            NO
            ▼
   情况 6: REPEAT 重试
```
**图 A-9: 展示 TxDecisionMaker 六分支决策的命中路径**

如图 A-9 所示，本案例命中的是"情况 2"。值得强调的是：**情况 2 仍然写
Undo Log**——并不是"自己写自己"就可以省略日志。这是 H2 在源码层面对回
滚正确性的硬约束，否则同一事务内的多步修改将无法逐步退回。`undoLogs`
子映射在事务结束前都是仅追加的，`logId` 单调递增，对应 `opId` 的低 40
位（详见 §4.5 Undo Log 编码格式）。

第二次 PUT 完成后，`users` 数据 map 中 `key=101` 的 `VersionedValue`
变成：`operationId=(txId<<40)|1`、`committedValue=null`、
`currentValue=Row{101, Alice, alice@h2.local}`。`undoLogs[txId]` 长
度为 2。两次写都已经体现在 `MVMap` 的内存版本链中，但**对其他事务仍然
不可见**——可见性最终由后续 `commit()` 触发的"批量翻转"决定。

### A.2.4 COMMIT 触发：SessionLocal.commit 到 TransactionStore.commit

会话端 `COMMIT` 由 `TransactionCommand.update()` 调用
`SessionLocal.commit(false)`（`SessionLocal.java:686` 附近）。该方法
执行三步：`beforeCommitOrRollback()` 做 LOB 与触发器准备；
`transaction.commit()` 委派给 `TransactionStore.commit()`；
`endTransaction()` 释放表锁与会话级状态。COMMIT 是**纯内存操作**，
不调用 `FileChannel.force()`，磁盘可见性由独立的 Checkpoint 负责
（详见 §5.5 COMMIT 流程总览与 §9.5 Checkpoint 触发条件）。

`TransactionStore.commit(Transaction t, boolean recovery)`
（`TransactionStore.java:579`）是真正的提交核心，按时序它做五件事：
①`flipCommittingTransactionsBit(txId, true)` 把"正在提交"位设上；
②`notifyAllWaitingTransactions()` 唤醒被本事务阻塞的写者；
③`markUndoLogAsCommitted(txId, version)` 把 Undo Log 子映射重命名为
`.undoLog-<id>`（点改横，作为崩溃恢复时"已成功 mark commit"的语义信号，
详见 §9.7 TransactionStore 的恢复）；④遍历 `undoLogs[txId]`，对每条
`Record(mapId, key, oldValue)` 调用对应数据 map 的
`map.operate(key, null, commitDecisionMaker)`；⑤
`flipCommittingTransactionsBit(txId, false)` 清除提交位。

```text
   SessionLocal.commit(false)
        │
        ▼
   transaction.commit()  ──▶  TransactionStore.commit(t, recovery=false)
                                       │
                                       ▼
   ① flip bit committingTransactions[txId]=1 (CAS over VersionedBitSet)
                                       │
                                       ▼
   ② notifyAllWaitingTransactions()  → 唤醒 §10.2.4 中 ABORT 的写者
                                       │
                                       ▼
   ③ markUndoLogAsCommitted(txId, version)  // ".undoLog.7" → ".undoLog-7"
                                       │
                                       ▼
   ④ for each Record in undoLogs[txId]:
        map = openMap(mapId)
        map.operate(key, null, CommitDecisionMaker)   ◀── §A.2.5
                                       │
                                       ▼
   ⑤ undoLogs[txId].clear() + flip committingTransactions[txId]=0
                                       │
                                       ▼
   返回 SessionLocal → endTransaction() 释放表锁与 LOB
```
**图 A-10: 列出 COMMIT 五步内部时序**

如图 A-10 所示，第一步与第五步形成一个"夹住"的临界区：在两次 flip 之间，其他事务通过
`isCommitted(txId)` 看到的是"提交中"，进而触发 §10.2.4 情况 3 的
"视为已提交"分支。这是 MVCC 模式下"长链路提交期间不阻塞读"的关键——其
他事务读取 `committedValue` 还是 `currentValue` 完全由 BitSet 当前
状态决定，**不需要等待 commit 完成**（详见 §10.4 隔离级别与 §10.5
RootReference 快照一致性）。

### A.2.5 CommitDecisionMaker：Undo Log 扫描与 VersionedValue 翻转

`CommitDecisionMaker.decide()`（`CommitDecisionMaker.java:25`）的工
作是逐条把"未提交版本"翻转为"已提交版本"。对每个 `key`：若
`existingValue.operationId` 属于本事务，构造一个新的 `VersionedValue`
其中 `operationId=NO_OPERATION_ID`、`committedValue=currentValue`、
`currentValue=currentValue`，然后返回 `Decision.PUT`，由 `MVMap` 在
B-Tree 上 CAS 写入；否则返回 `ABORT`，跳过该键。

回到运行实例：UPDATE 后 `key=101` 的 `VersionedValue` 是
`{op=(txId<<40)|1, committed=null, current=Row{Alice,alice@h2.local}}`。
扫描第一条 Undo Log（INSERT 那条）时，CommitDecisionMaker 会构造
`{op=NO_OP, committed=current, current=current}` 并 PUT；扫描第二条
（UPDATE 那条）时，由于此时 `operationId` 已经是 `NO_OP`，
`decide()` 进入 `existingValue==null || op==NO_OP_ID` 的快路径，依然
返回 PUT 但本质上是幂等覆盖——这正是为什么遍历顺序无关、且重复扫描安全
的原因（详见 §10.2 VersionedValue 与 §5.5.3.1 CommitDecisionMaker
关键代码）。

```text
   CommitDecisionMaker.decide(existing):

       existing == null ?
           │
           ├─ YES → ABORT  (该键早已被同事务的另一条记录处理过)
           │
           └─ NO
                │
                ▼
       getTransactionId(existing.operationId) == thisTxId ?
                │
                ├─ NO → ABORT  (其他事务的修改, 不能覆盖)
                │
                └─ YES
                     │
                     ▼
       构造 cleared = VersionedValue(
                         operationId   = NO_OPERATION_ID,
                         committedValue= existing.currentValue,
                         currentValue  = existing.currentValue)
                     │
                     ▼
       return MVMap.Decision.PUT  →  MVMap CAS 替换 B-Tree 节点
```

注意：`CommitDecisionMaker` 不会清除 `currentValue`，它只是把
`committedValue` 提升为与 `currentValue` 一致，并把 `operationId`
归零。因此从其他事务的视角，**"翻转"是一次原子的语义抬升**：原本它
们看到的是 `committedValue=null`（看不到行），翻转之后立即看到的是
`committedValue=Row{...}`（行可见），中间没有可观测的中间态。

### A.2.6 RootReference CAS：原子可见性翻转的最小不可分原语

虽然 §A.2.5 的 `CommitDecisionMaker` 是逐键 PUT，但**真正让"看不见
→看见"瞬间发生**的硬件级原子操作，是 `MVMap.operate` 内部对
`AtomicReference<RootReference>` 的 `compareAndSet` 调用
（`MVMap.java:45`、详见 §10.5 CAS 更新机制）。每一次 PUT 都会创建一
条新版本链 `v_new → v_old → ...`，并通过 CAS 把 `root` 指向
`v_new`；CAS 失败时进入 §10.5.3 的三级退避（spin-wait → yield →
synchronized wait）。

如图 A-11 所示，写者线程 W、读者线程 R 与 BackgroundWriter 线程 B
在同一时间轴上的动作可以被精确刻画：R 在 W 完成 CAS 之前读取看到旧根，
之后立刻看到新根；B 在 R/W 之间的任意时刻被唤醒，但它读取的是
"某个时刻的根快照"，并把对应的页落到 Chunk 中（详见 §A.2.7 与 §9.5
后台写入线程）。

```text
   时间轴 ────────────────────────────────────────────────────────────────────────────▶
   ─────────────────────────────────────────────────────────────────────────────────
   W (writer S1) │
                 │ t0 ─▶ Insert.put(101)         (TransactionMap.put → MVMap.operate)
                 │ t1 ─▶ Update.put(101)         (第二次 PUT, 写第二条 Undo Log)
                 │ t2 ─▶ flipCommittingBit(true) (committingTransactions[txId]=1)
                 │ t3 ─▶ CommitDecisionMaker 扫描 undoLog 两条记录
                 │ t4 ─▶ root.compareAndSet(v_old, v_new)   ◀══════ 原子可见性翻转
                 │ t5 ─▶ flipCommittingBit(false) + undoLog.clear()
   ─────────────────────────────────────────────────────────────────────────────────
   R (reader S2) │
                 │ t0─t1 ─▶ get(101)→null              (读 root v0, op=txS1, 未提交)
                 │ t2    ─▶ get(101)→null              (读 root v0, committingBit=1
                 │                                     仍判 committedValue=null,见§10.2.4)
                 │ t3    ─▶ get(101)→null              (CDM 扫描进行中, 根尚未替换)
                 │ t4    ─▶ get(101)→Row{Alice,alice@h2.local}   ◀═ 第一次看见行
                 │ t5    ─▶ get(101)→Row{Alice,alice@h2.local}   (committingBit=0)
   ─────────────────────────────────────────────────────────────────────────────────
   B (BgWriter)  │
                 │ t0─t1 ─▶ sleep(autoCommitDelay = 1s)
                 │ t2    ─▶ tick: hasUnsavedChanges()? → no  (CAS 尚未发生)
                 │ t3    ─▶ sleep(...)
                 │ t4─t5 ─▶ tick: hasUnsavedChanges()? → yes  (新 root 可见)
                 │ t6    ─▶ storeLock.tryLock() OK → store(syncWrite=false)
                 │ t6    ─▶ collectDirtyPages → buildChunk(k) → FileChannel.write
                 │ t6    ─▶ updateChunkRegistry → updateStoreHeader(currentVersion++)
                 │ t6    ─▶ storeLock.unlock()                   (持久性边界完成)
   ─────────────────────────────────────────────────────────────────────────────────
                                                  ▲
                                                  │
                                            t4 = 可见性翻转 (CAS 成功)
                                            t6 = 持久性边界 (Chunk + Header)
```
**图 A-11: 对比 CAS 提交前后的可见性翻转时刻**

图中 `t4` 是本案例最重要的"时间锚点"：在 `t4` 之前的任意纳秒，R 读到
的都是 `null`；在 `t4` 之后的任意纳秒，R 读到的都是新行。Java 内存模
型对 `AtomicReference.compareAndSet` 的 happens-before 规约保证了
这一点（详见 §10.5.6 CAS 重试循环与退避策略）。值得注意的是：
BackgroundWriter 在 `t6` 才把新页写入磁盘，但**这与 R 的可见性翻转无
关**——可见性是内存级的，持久性是磁盘级的，两者解耦。

### A.2.7 BackgroundWriter：脏页收集与新 Chunk 写入

`MVStore` 在构造时通过 `setAutoCommitDelay()`（`MVStore.java:310`
附近）启动后台写入线程，默认周期 1 秒。每个 tick 它执行
`writeOrClose()`：检查 `hasUnsavedChanges()`，若 true 则尝试取得
非阻塞 `storeLock`，调用 `store(false)`，进入 §9.5.6 的脏页收集与
§9.5.2 的 `store()` 完整流程。脏页来自 §A.2.5 中 CommitDecisionMaker
留下的所有"新 RootReference 链"。

`store()` 的输出是一段连续的字节，写入到下一个空闲块，对应一个新的
`Chunk` 对象（详见 §6.4 Chunk 压缩整理与 §9.3.4 Chunk 生命周期）。
该 Chunk 中包含本事务两次 PUT 产生的全部新页，以及由其它并发事务在该
间隔内产生的页。一个 Chunk 不专属于一个事务——这与传统 WAL "事务一
段日志"的强耦合不同，这是 MVStore "页中心、版本链、批量落盘"设计的体
现（详见 §9.4.3 传统 WAL 与 MVStore 隐式日志对比）。

```text
   BackgroundWriter tick:
   ┌──────────────────────────────────────────────────────┐
   │  hasUnsavedChanges()?                                │
   │     │                                                │
   │     ├─ NO  → continue sleep (autoCommitDelay)        │
   │     │                                                │
   │     └─ YES                                           │
   │         │                                            │
   │         ▼                                            │
   │  storeLock.tryLock()  (非阻塞)                       │
   │         │                                            │
   │         ├─ FAIL → 留给下一个 tick                     │
   │         │                                            │
   │         └─ OK                                        │
   │             │                                        │
   │             ▼                                        │
   │  store(syncWrite=false)                              │
   │     ├─ collectDirtyPages()       ── §9.5.6           │
   │     ├─ buildChunk(pages, version)                    │
   │     ├─ allocateBlocks(FreeSpaceBitSet)  ── §6.6      │
   │     ├─ FileChannel.write(chunkBytes)                 │
   │     └─ updateChunkRegistry()                         │
   │             │                                        │
   │             ▼                                        │
   │  storeLock.unlock()                                  │
   └──────────────────────────────────────────────────────┘
```

在 `syncWrite=false` 路径下，后台 tick **不调用** `force()`，因此
即使 Chunk 字节已落盘，OS 的 page cache 可能仍未刷到块设备；只有
`sync()`、显式 `commit + autoCommit + sync` 或关闭路径才会触发
`force()`（详见 §9.5.3 后台写入线程对 `syncWrite` 标志的处理）。
这是 H2 默认配置下"COMMIT 的可见性"与"COMMIT 的持久性"之间的核心
权衡——案例 C 将专门讨论这一权衡在崩溃场景下的恢复路径。

### A.2.8 Checkpoint：File Header 同步与版本提升

`store()` 的尾部会更新 `Store Header`：把"最新有效版本"指向刚写入的
Chunk 起始块，同时把 `currentVersion` 提升到该 Chunk 对应的全局版本
号（详见 §9.3.3 Store Header 详细格式与 §9.6.2 File Header 格式）。
H2 在文件起始与中段保留**两份** Store Header，按版本号选取较新者，
保证即使一份 header 写入过程中崩溃，另一份依然指向上一个完整版本——
这是 H2 在 §9.4.4 中描述的"原子提交边界"的物理实现。

如图 A-12 所示（本案例第六张图），TransactionStore 的状态机视角把
A.2.1 至 A.2.8 八个步骤压缩为四个宏观阶段：OPEN、PREPARED（仅
两阶段提交场景）、COMMITTED、ROLLED\_BACK。本案例没有进入 PREPARED
分支（详见 §4.5 二阶段提交支持），但状态机把它列出便于读者把握全貌。

```text
   ┌─────────────────────────────────────────────────────────────────┐
   │            TransactionStore Transaction 状态机                    │
   │  (注: 图中箭头标签标注触发动作 / 关键 BitSet 翻转)                  │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                 │
   │     ┌─────────┐                                                 │
   │     │ NOT_INIT│                                                 │
   │     └────┬────┘                                                 │
   │          │ TransactionStore.begin()                             │
   │          │ openTx[id] := 1                                      │
   │          ▼                                                      │
   │     ┌─────────┐  prepare(commitName)   ┌──────────┐             │
   │     │  OPEN   │ ─────────────────────▶ │ PREPARED │             │
   │     │         │                        │          │             │
   │     └──┬──┬───┘                        └────┬─────┘             │
   │        │  │                                 │                   │
   │        │  │ rollback / rollbackTo          │ commit (XA)        │
   │        │  ▼                                ▼                    │
   │        │  ┌───────────────┐         ┌──────────────┐            │
   │        │  │ ROLLED_BACK   │         │ COMMITTED    │            │
   │        │  │ openTx[id]:=0 │         │ openTx[id]:=0│            │
   │        │  │ undoLog 逆序  │         │ undoLog 顺序 │            │
   │        │  │ 恢复 oldValue │         │ 翻转 op=NO_OP│            │
   │        │  └───────┬───────┘         └──────┬───────┘            │
   │        │          │                        │                    │
   │        │          ▼                        ▼                    │
   │        │   transactions[id]=null    transactions[id]=null       │
   │        │   undoLogs[id].clear()     undoLogs[id].clear()        │
   │        │                                                        │
   │        │ commit (一阶段, 本案例路径)                              │
   │        ▼                                                        │
   │   ┌─────────────────┐                                           │
   │   │ committingTx=1  │  ← flipCommittingTransactionsBit(true)    │
   │   │ (临时子状态)    │                                            │
   │   └────────┬────────┘                                           │
   │            │ CommitDecisionMaker 扫完 + RootReference CAS       │
   │            ▼                                                    │
   │   ┌─────────────────┐                                           │
   │   │ committingTx=0  │  ← flipCommittingTransactionsBit(false)   │
   │   │ + COMMITTED     │                                           │
   │   └─────────────────┘                                           │
   │                                                                 │
   │  备注: PREPARED → ROLLED_BACK 在 XA recover 时也成立              │
   │        (详见 §9.7 TransactionStore 的恢复)                       │
   └─────────────────────────────────────────────────────────────────┘
```
**图 A-12: 展示 TransactionStore 状态迁移与回滚分支**

`COMMITTED` 不是终态：当 `transactions[id]` 槽被 `null` 化、
`undoLogs[id]` 子映射被 `clear()` 后，事务对象就被回收，`txId` 可能
被未来的新事务重用（详见 §4.5 数组索引映射关系）。这是 H2 把
`MAX_OPEN_TRANSACTIONS=255` 这一硬上限做得可接受的关键——只要事务流
转足够快，槽位池就不会耗尽。

### A.2.9 端到端复盘：从 SQL 到磁盘的责任划分

回到运行实例：会话 S1 提交 `(101, 'Alice', 'alice@h2.local')` 后，S2
立刻可读到这一行；但磁盘上对应的 Chunk 可能要到 1 秒后才被
BackgroundWriter 写入，再到下一次显式 `sync()` 或关闭才进入持久化语义。
这条链路的责任划分与典型缩写如下：

| 阶段 | 责任组件 | 关键产出 | 反向引用 |
| --- | --- | --- | --- |
| ① begin | SessionLocal / TransactionStore | openTx 位、undo 子映射、Tx 对象 | 详见 §4.5 |
| ② INSERT | TransactionMap / TxDecisionMaker | Undo Log #0、未提交 VersionedValue | 详见 §10.2 |
| ③ UPDATE | TransactionMap / TxDecisionMaker | Undo Log #1、新未提交 VersionedValue | 详见 §10.4 |
| ④ commit 触发 | SessionLocal.commit | 委派至 TransactionStore.commit | 详见 §5.5 |
| ⑤ CDM 扫描 | CommitDecisionMaker / MVMap.operate | committedValue 抬升 | 详见 §5.5.3.1 |
| ⑥ root CAS | RootReference (AtomicReference) | 原子可见性翻转 | 详见 §10.5 |
| ⑦ Chunk 落盘 | BackgroundWriter / store() | 新 Chunk + page 字节 | 详见 §9.5 与 §6.4 |
| ⑧ Header 同步 | Store Header 双写 | currentVersion 提升 | 详见 §9.6 |

⑥ 是"逻辑可见性"边界，⑧ 是"物理持久性"边界。两者在源码中由不同子系
统拥有，由 BackgroundWriter 这条无锁后台线程把它们桥接为最终一致的
状态。这种**"内存提交—后台落盘"**的两段式设计，是 MVStore 与 H2
SQL 引擎组合时性能特征的根本来源（详见 §9.4 Crash Safety 与 §9.5.4
检查点触发条件详解）。

值得指出的是，本案例没有讨论 `SET LOCK_MODE`、`SET WRITE_DELAY` 等
影响默认行为的会话级开关——它们会改变 ⑥ 与 ⑧ 之间的"窗口宽度"，但不
改变责任划分。在工程部署中，关键决策是：是否允许出现"已 commit 但
未持久化"的窗口；H2 的默认答案是"是"，为此提供了 `SET WRITE_DELAY 0`
等显式收紧选项。

### A.2.10 思考小结

读者可以用以下三个问题自检对本案例的掌握程度：

1. **对一行被同一事务修改两次的键，为什么 `CommitDecisionMaker` 扫
   到第二条 Undo Log 时仍然返回 PUT 而不是 ABORT？这与 `existingValue
   .operationId == NO_OP_ID` 的快路径有什么关系？**（提示：详见 §10.2
   VersionedValue 结构与 §5.5.3.1 CommitDecisionMaker 关键代码。）

2. **若 BackgroundWriter 在 §A.2.5 完成后、§A.2.8 完成前进程崩溃，
   下次启动时 H2 如何判断本事务"已经成功 commit"？为什么 Undo Log 子
   映射的命名从 `.undoLog.<id>` 变成 `.undoLog-<id>` 起到了关键作用？**
   （提示：详见 §9.7 TransactionStore 的恢复与 §4.5 markUndoLogAsCommitted。）

3. **为什么 §A.2.6 中 RootReference CAS 是"可见性翻转"的最小不可分
   原语，而不是 §A.2.4 中 `flipCommittingTransactionsBit(true)`？
   把两者交换次序会导致什么读异常？**（提示：详见 §10.5 RootReference
   CAS 与 §10.4 隔离级别实现。）

完成本案例后，建议沿着以下顺序进入案例 C：把"crash 发生在 §A.2.5 与
§A.2.8 之间"作为思想实验起点，复用本案例建立的状态时间轴，观察
TransactionStore.recovery 路径如何重建 OPEN/COMMITTED 集合，从而把
A.2 的"提交全链路"推广为"crash + recovery 全链路"。

---

---

## A.3 案例 C：一次崩溃后的恢复启动

本案例展示 H2 在进程被强制终止之后再次打开数据库时，MVStore 如何利用双副本 File Header、Chunk Footer 中的 Fletcher-32 校验和以及 Undo Log 的命名约定，把磁盘上的字节流恢复到一个一致的运行时状态。与案例 A 的"读路径"和案例 B 的"写路径"不同，本案例关注的是"启动路径"：从 `MVStore.openInternal()` 到对外开放写入之间，恢复子系统经过的 8 个流水线步骤。每一步都需要在"前向推进"与"回退到上一已知良好状态"之间做出明确决策，而决策依据则来自磁盘上的校验信息以及 Undo Log map 名后缀（详见 §9.7.1）。

为了让讨论具体化，本案例使用如下运行示例：一个 H2 数据库在崩溃前已经成功提交了 3 个事务（生成 Chunk 1、Chunk 2、Chunk 3），最新的 File Header 双副本指向 Chunk 3。第 4 个事务正在写入：Chunk 4 的 Header 与若干 Page 已经落盘，但写到 Chunk 4 Footer 的最后 64 字节时操作系统断电，Footer 中的 Fletcher-32 字段尚未更新；同时 File Header 副本仍然停留在指向 Chunk 3 的旧版本上。我们将以这一实例贯穿全篇，明确每个分支的决策点。

### A.3.1 崩溃发生场景：第 4 个事务写到一半

在崩溃发生时，进程内存中存在 4 个 Transaction 对象：T1、T2、T3 已经依次调用 `TransactionStore.commit()` 完成提交（详见 §4.5），它们的 undo log map 后缀已从 `.undoLog.<id>` 重命名为 `.undoLog-<id>` 或被 `clear()`；T4 调用了 `MVMap.put()` 写入了若干 VersionedValueUncommitted 节点，并通过 `MVStore.commit()` 触发了一次检查点（详见 §9.5）。检查点逻辑把 T4 的事务变更打包成 Chunk 4，连同最新的 layoutMap、metaMap root 一起 append 到文件末尾。崩溃恰好发生在 `serializeToBuffer()` 执行到末尾 Footer 写入阶段，但磁盘扇区原子写入边界尚未跨越。

```text
┌──────────────────────────────────────────────────────────────────┐
│  崩溃前后进程内存与磁盘状态                                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   崩溃前 (in-flight)            │   崩溃后 (on-disk reality)       │
│   ─────────────────────────     │   ─────────────────────────       │
│   内存:                          │   磁盘:                          │
│     T1, T2, T3 = COMMITTED       │     File Header 0 → Chunk 3      │
│     T4 = OPEN, 已写 4 条 undo    │     File Header 1 → Chunk 3      │
│     committingTransactions       │     Chunk 1 (good footer)        │
│       BitSet = {4}               │     Chunk 2 (good footer)        │
│     dirty meta map root          │     Chunk 3 (good footer)        │
│                                  │     Chunk 4 (header+pages,       │
│   FileChannel 写指针位于         │             FOOTER 字节缺失)     │
│     Chunk 4 footer 起始处        │                                  │
│                                  │   操作系统的 page cache 被丢弃     │
│  ─────────  电源切断 / kill -9   │   只有 fsync 之前的字节才在盘上   │
│                                  │                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 A-13: 对比崩溃前后内存与磁盘状态**

如图 A-13 所示，进程内存中的 `committingTransactions` BitSet、`undoLogs[]` 数组、所有 RootReference 链以及 dirty page 表都被无差别清除；恢复子系统能够利用的输入只有磁盘上残留的字节流（详见 §9.7.6）。Chunk 4 的"半成品"特征是本案例两个分支的分水岭：File Header 仍然指向 Chunk 3，因此正常路径会先把 Chunk 3 当作起点；而 Chunk 4 的 Header 已经落盘，但 Footer 校验失败，因此异常路径会被触发——后续步骤将在同一棵决策树上把这两条分支收敛回一致状态。

需要强调的一点是：H2 不依赖传统 WAL 进行重做，而是依赖"最新一个完整 Chunk"的快照语义（详见 §9.4.2）。这意味着崩溃后丢失的最大粒度是"一个 Chunk 中所有 commit 的变更"。本案例中第 4 个事务的所有效果都将被丢弃，但这并不违反 ACID——T4 在 SQL 客户端那一侧从未收到 `COMMIT OK` 响应。

为了让恢复决策更清晰，下面把崩溃发生前后磁盘上的"承诺位"摘录如下。承诺位即决定一段字节是否被恢复流程视为"已存在"的关键校验字段：

- File Header 的 `fletcher` 字段：决定 Block 0 / Block 1 是否参与版本仲裁；
- Chunk Footer 的 `fletcher` 字段：决定整个 chunk 的所有 page 是否被采纳；
- metaMap 中的 `chunk.<id>` 条目：决定 chunk 是否被纳入 FreeSpaceBitSet 的 used 区间；
- undo log map 名后缀（`.` 或 `-`）：决定事务在恢复期是 rollback 还是 commit-redo。

这些承诺位之间的语义优先级是从外向内的：File Header → Chunk Footer → metaMap chunk 条目 → undo log 名后缀。前一级失败会让后一级的所有信息被丢弃，这是 ACID 原子性"全有或全无"的物理体现（详见 §9.4.4）。

### A.3.2 进程重启与 FileStore 重新打开

操作员重新启动 JVM，应用层调用 `DriverManager.getConnection()`，最终进入 `MVStore.openInternal()`（`org/h2/mvstore/MVStore.java`）。该方法首先构造 `SingleFileStore`，调用 `FileStore.open(fileName, readOnly)` 打开底层 `FileChannel`，并尝试获取文件锁（默认 `FileLockMethod.FS`）。文件锁的目的是防止两个 JVM 同时执行恢复流程造成状态分裂。

```text
┌────────────────────────────────────────────────────────┐
│  阶段 1: FileStore 重新打开                              │
├────────────────────────────────────────────────────────┤
│                                                        │
│   MVStore.openInternal()                               │
│       │                                                │
│       ├─ new SingleFileStore(this, config)             │
│       │   └─ FileChannel.open(path, READ, WRITE)       │
│       │                                                │
│       ├─ acquireFileLock()                             │
│       │   ├─ 成功 → 进入恢复流程                          │
│       │   └─ 失败 → 抛 DbException(FILE_LOCKED_1)       │
│       │                                                │
│       ├─ readStoreHeader()                             │
│       │   └─ 见 A.3.3                                   │
│       │                                                │
│       └─ setLastChunk(...)                             │
│           └─ 见 A.3.4 / A.3.5                           │
│                                                        │
└────────────────────────────────────────────────────────┘
```
**图 A-14: 追踪 FileStore 重启与锁获取顺序**

如图 A-14 所示，恢复流程必须先确认排他持有文件锁，否则后续任何字节读取都可能与另一个写入者竞争。`SingleFileStore.start()` 在 `org/h2/mvstore/SingleFileStore.java` 中实现：它把 `FileChannel.position(0)` 复位到文件开头，然后申请一段 8 KB 缓冲区，准备一次性读入两份 File Header。决策点在于：如果 `tryLock()` 返回 null，说明已有进程持有锁，恢复流程必须中止并向上层抛出异常——H2 不会"乐观恢复"。

文件本身长度可由 `FileChannel.size()` 直接获得，记为 `fileLen`。本例中假定 `fileLen = 4096 × (2 + nBlocks(Chunk1..Chunk4))`，注意 Chunk 4 的 Footer 字节虽然短缺，但操作系统已把 Chunk 4 的 Header + Page 区块对齐到 4 KB 边界，所以 `fileLen` 仍然是一个块对齐值。这一观察是 A.3.4 中"沿 next 链遍历"能够正确停止的前提（详见 §9.6.1）。

### A.3.3 双副本 File Header 读取与版本仲裁

`readStoreHeader()` 是恢复流程的第一个关键决策点。它读取文件的前两个 4 KB 块（Block 0、Block 1），分别解析为 key-value 文本格式的 File Header，再分别校验 Fletcher-32（详见 §9.6.2）。两份 header 的存在不是为了多版本，而是为了防止"写 Header 过程中崩溃"导致两份都损坏的概率被压缩到可忽略。

```text
┌─────────────────────────────────────────────────────────────────────────┐
│        磁盘文件字节布局（运行示例：3 个完整 Chunk + 1 个半 Chunk）         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  offset 0x00000000 ┌───────────────────────────────────────┐            │
│                    │ File Header 0  (block 0, 4 KB)        │            │
│                    │   H:2,block:N3,blockSize:1000,        │            │
│                    │   chunk:3,version:3,fletcher:0x91A2..│            │
│  offset 0x00001000 ├───────────────────────────────────────┤  ← 4096    │
│                    │ File Header 1  (block 1, 4 KB)        │            │
│                    │   H:2,block:N3,...,version:3,         │            │
│                    │   fletcher:0x91A2.. (与 header 0 一致)│            │
│  offset 0x00002000 ├───────────────────────────────────────┤  ← 8192    │
│                    │ Chunk 1   header | pages | footer ✓   │            │
│                    │   chunk:1,block:2,version:1,...       │            │
│                    │   footer fletcher = 0xAED9A4F6 (good) │            │
│  offset 0x00006000 ├───────────────────────────────────────┤  ← 24576   │
│                    │ Chunk 2   header | pages | footer ✓   │            │
│                    │   chunk:2,version:2,fletcher=0x5C... │            │
│  offset 0x0000A000 ├───────────────────────────────────────┤  ← 40960   │
│                    │ Chunk 3   header | pages | footer ✓   │            │
│                    │   chunk:3,version:3,fletcher=0x91A2.. │            │
│                    │   next = block N4 (= Chunk 4 起点)    │            │
│  offset 0x0000F000 ├───────────────────────────────────────┤  ← 61440   │
│                    │ Chunk 4   header ✓                    │            │
│                    │ Chunk 4   pages  ✓ (部分写入)         │            │
│                    │ Chunk 4   footer  ✗ (Fletcher 字段未写)│           │
│  offset 0x00012000 └───────────────────────────────────────┘  ← 73728   │
│                                                                         │
│  说明:                                                                   │
│    * block size = 4096 字节（File Header 的 blockSize:1000_16）          │
│    * File Header 双副本严格占据 block 0 / block 1                       │
│    * Chunk N 的起点 = blockSize × Chunk.block 字段                      │
│    * Footer 长度 = 128 字节，固定贴在 chunk 末尾                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```
**图 A-15: 标注磁盘字节布局与末尾损坏 Chunk**

如图 A-15 所示，本案例中两份 File Header 的字节内容完全一致，因为最近一次成功的 commit（即提交 T3 时）已把"指向 Chunk 3"这一信息写入了双副本，且后续的"乐观跳过"机制让它们保持稳定。仲裁规则在 `FileStore.parseStoreHeader()` 中实现：

```java
// 仲裁逻辑（伪代码，详见 FileStore.java 内 parseStoreHeader / selectBestHeader）
StoreHeader h0 = parseStoreHeader(buf, 0);
StoreHeader h1 = parseStoreHeader(buf, 1);
StoreHeader best;
if (h0.valid && h1.valid) {
    best = (h0.version >= h1.version) ? h0 : h1;
} else if (h0.valid) {
    best = h0;
} else if (h1.valid) {
    best = h1;
} else {
    // 都损坏 → 退化到从文件末尾扫描 chunk footer
    best = scanChunkFootersBackward();
}
```

决策点在于：两份均有效时取版本号大的；其一损坏时取另一份；两份均损坏时回退到末尾扫描（详见 §9.6.2）。本案例命中第一条分支：`best = h0`，`best.chunk = 3`，`best.block = N3`。注意 `block` 字段并不一定指向"绝对最新"的 chunk——为了减少对 File Header 的写放大，MVStore 允许 `next` 链跳转最多 20 跳后才回写 header（详见 §9.6.3）。

### A.3.4 沿 next 链定位最新 Chunk

拿到候选 chunk 之后，`setLastChunk(Chunk c)` 会从 `c` 的 footer 出发沿 `next` 字段向前扫描，逐个尝试把 next 指向的 chunk 当作"更新的版本"。这个步骤的核心目的是：在 File Header 没有写入最新位置的场景下，仍能找到最新的有效 chunk。

```text
┌────────────────────────────────────────────────────────────┐
│      next 链扫描（最多 20 跳）                               │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   起点 = File Header.chunk = Chunk 3                       │
│                                                            │
│   loop ≤ 20:                                               │
│      读取 candidate.footer                                  │
│        ├─ Fletcher-32 OK?                                  │
│        │     │                                              │
│        │     ├── YES → accept candidate, 跳到 next         │
│        │     │         如果 next 越界或 = 0 → 停止           │
│        │     │                                              │
│        │     └── NO  → reject candidate, 回退到上一已知好   │
│        │                的 chunk，停止                      │
│        │                                                    │
│        └─ 跳数 == 20?                                       │
│              └── YES → 强制停止（详见 §9.6.3 next 上限）   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```
**图 A-16: 描绘 next 链扫描决策路径**

如图 A-16 所示，恢复流程沿着 Chunk 3 → Chunk 4 的 next 链前进。Chunk 3 的 footer 写道 `next = N4`，于是引擎读取 offset `0xF000` 处的字节，尝试解析 Chunk 4 的 footer。如果 Chunk 4 footer 的 Fletcher-32 校验失败（本案例的异常分支），整个 next 链立即截断，最近一次"已 accept"的 chunk（即 Chunk 3）被定为 lastChunk。这个决策的本质是：**Footer 的 Fletcher 校验是 Chunk 完整写入的"提交位"**——一旦校验失败，恢复子系统就把这个 chunk 当作从未存在过来处理（详见 §9.7.7 的"写入 Chunk 数据中崩溃"行）。

如果换成"正常路径"——即 Chunk 4 的 footer 已经完整落盘——next 链会成功 accept Chunk 4，再尝试沿 Chunk 4 的 next 字段继续，直到遇到无效 footer 或越过 20 跳上限为止。两种路径在此步骤的输出虽然不同（lastChunk = Chunk 3 vs Chunk 4），但后续步骤对它们的处理方式是同构的：都是"以 lastChunk 为根重建状态"。

### A.3.5 Chunk Footer 校验：正常分支与异常分支

本节单独把 Footer 校验抽出来分析，因为它是整个恢复流程中唯一一个"产生分支"的决策点。Footer 长度固定 128 字节（详见 §9.3.2），格式为：

```text
chunk:<id>,block:<n>,version:<v>,fletcher:<crc>
```

引擎读取 footer 后，先按文本协议解析得到 `chunk`、`block`、`version`，再对 footer 自身（除 fletcher 字段外）计算 Fletcher-32 并与字段值比较。任一不一致都视为校验失败。

```text
┌──────────────────────────────────────────────────────────────┐
│   Chunk Footer 校验决策树                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   读取 footer (128 B, 末端贴齐 chunk 末尾)                    │
│         │                                                    │
│         ▼                                                    │
│   parseKeyValue("chunk:..,block:..,version:..,fletcher:..") │
│         │                                                    │
│         ▼                                                    │
│   字段缺失 / 非法整数?                                        │
│       ├── YES → REJECT (异常分支)                            │
│       └── NO                                                 │
│              │                                                │
│              ▼                                                │
│       computed = Fletcher32(footer 除 fletcher 字段外)       │
│       claimed  = 解析得到的 fletcher                          │
│              │                                                │
│              ▼                                                │
│       computed == claimed ?                                   │
│              ├── YES → ACCEPT (正常分支)                      │
│              │         lastChunk = this chunk                │
│              │         读取 chunk header 中的 root, layout    │
│              │                                                │
│              └── NO  → REJECT (异常分支)                      │
│                        lastChunk = 前一已 accept 的 chunk    │
│                        Chunk 4 的 header / pages 全部丢弃    │
│                        (它们尚未提交)                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
**图 A-17: 拆解 Chunk Footer 校验与分支收敛**

如图 A-17 所示，正常分支与异常分支在此处分流，但都会回到同一棵后续流程上：

- **正常分支（footer 完整）**：Chunk 4 被 accept，root、layoutMap 字段从 Chunk 4 header 中读出。后续 B-Tree 重建会以 Chunk 4 中的 root 为入口，T4 的修改对客户端可见——这要求 T4 在崩溃前已经走完了 `TransactionStore.commit()` 的全部三阶段（详见 §9.7.3）。
- **异常分支（footer Fletcher 不一致或字段缺失）**：Chunk 4 被 reject，恢复子系统回到 Chunk 3 作为 lastChunk。T4 的所有修改（无论它的 undo log 标记了什么）都被视为"从未发生"。这正是 H2 不需要 redo 的原因：**没有 footer，就没有 commit**。

本案例命中异常分支：Chunk 4 footer 缺少 fletcher 字段或字段值与重新计算的 Fletcher-32 不匹配，恢复子系统选择 Chunk 3。

### A.3.6 B-Tree 根重建与 layoutMap 回填

确定 lastChunk 之后，恢复流程进入"重建运行时状态"阶段。`MVStore.setLastChunk()` 从 `lastChunk.header` 中拿到 layoutMap 的 root 位置（chunk/offset/length 三元组），调用 `Page.read()` 递归从磁盘加载 layoutMap 的全部节点（详见 §9.2 中 Page 反序列化流程的描述）。layoutMap 是一个 mapId → rootPagePos 的映射，覆盖了数据库中所有 MVMap（用户表、索引、metaMap、undoLog map 等）。

```text
┌──────────────────────────────────────────────────────────────────┐
│   阶段 4: 通过 layoutMap 回填所有 MVMap 的根                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   layoutMap (来自 Chunk 3 header)                                │
│      ┌─────────────────────────────────┐                          │
│      │ key=1  → rootPos(chunk=3, ...) │ metaMap                  │
│      │ key=2  → rootPos(chunk=3, ...) │ users 表的主索引          │
│      │ key=3  → rootPos(chunk=2, ...) │ users.idx_email         │
│      │ key=N  → rootPos(chunk=K, ...) │ ...                       │
│      └─────────────────────────────────┘                          │
│              │                                                    │
│              ▼                                                    │
│   for each (mapId, rootPos):                                     │
│      page = Page.read(rootPos)                                    │
│      MVMap m = openMap(mapId)                                     │
│      m.setRootReference(new RootReference(page))                  │
│              │                                                    │
│              ▼                                                    │
│   metaMap 中扫描 "undoLog.*" 名前缀                               │
│      ├── 找到 ".undoLog.4"  → T4 状态 = OPEN                      │
│      ├── 找到 ".undoLog.3"  → 不存在 (commit 后已清理)             │
│      └── 找到 ".undoLog-X"  → COMMITTED 但未清理 (本例无)         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 A-18: 演示 layoutMap 驱动的 root 回填**

如图 A-18 所示，layoutMap 的存在让恢复流程不需要扫描整个文件来寻找 page 边界——它一次性给出了所有"活根"的位置。但要注意：异常分支下 lastChunk 是 Chunk 3，因此 layoutMap 自身也来自 Chunk 3，这意味着**T4 引入的任何新建 map（例如新建表带来的索引）都不会出现在 layoutMap 里**——它们随同 Chunk 4 一并消失（详见 §6.2 中 mapId 单调递增的描述）。这是 ACID 中的 A（原子性）在 MVStore 上的具体落地：要么整个 Chunk 生效，要么完全不生效。

### A.3.7 Undo Log 扫描与未完成事务回滚

B-Tree 根重建后，`TransactionStore.open()` 被调用。它在 metaMap 中查找所有以 `.undoLog.` 或 `.undoLog-` 开头的 map 名（详见 §4.5.2），命名后缀承载事务状态：

| map 名后缀 | 事务状态     | 恢复动作                        |
|------------|-------------|---------------------------------|
| `.`        | OPEN        | 用 RollbackDecisionMaker 回滚    |
| `-`        | COMMITTED   | 用 CommitDecisionMaker 重做      |

```text
┌────────────────────────────────────────────────────────────────────┐
│        恢复期未完成事务处理时序图                                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  TransactionStore.open()                                           │
│        │                                                           │
│        ├─ 扫描 metaMap → 发现 ".undoLog.4"                          │
│        │     suffix = "."  → T4 = OPEN                              │
│        │                                                           │
│        ├─ openTransaction(id=4, status=OPEN)                       │
│        │     └─ 重建 Transaction 对象, status = STATUS_OPEN         │
│        │                                                           │
│        ├─ 调用 t4.rollback()                                       │
│        │     └─ Transaction.java:561                               │
│        │     └─ markTransactionEnd()                               │
│        │     └─ store.rollbackTo(t4, maxLogId, 0)                  │
│        │                                                           │
│        ├─ TransactionStore.rollbackTo()                            │
│        │     └─ TransactionStore.java:824                          │
│        │     └─ 逆序遍历 undoLog[4]:                                │
│        │           for logId = max-1 .. 0:                         │
│        │              undoKey = (4 << 40) | logId                  │
│        │              undoLog.operate(undoKey, null, RDM)          │
│        │                                                           │
│        ├─ RollbackDecisionMaker.decide()                           │
│        │     └─ RollbackDecisionMaker.java:34                      │
│        │     └─ Record(mapId, key, oldValue) 解码:                 │
│        │           oldValue == null → REMOVE(key)                  │
│        │           oldValue != null → PUT(key, oldValue)           │
│        │                                                           │
│        ├─ undoLog[4].clear()                                       │
│        │                                                           │
│        └─ 从 metaMap 删除 ".undoLog.4" 条目                          │
│                                                                    │
│   注:committingTransactions BitSet 是 in-memory 的, 重建为空集     │
│       (详见 §9.7.6: BitSet 不持久化)                                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```
**图 A-19: 追踪未完成事务的回滚序列**

如图 A-19 所示，T4 由于其 undo log 后缀仍是 `.`，被识别为 OPEN。`RollbackDecisionMaker.decide()` 的逻辑（详见 §5.6）逐条恢复 oldValue：原 INSERT 的记录被 REMOVE 抹除，原 UPDATE 的记录被 PUT 回旧值。这一步与 SQL 层的 ROLLBACK 命令走的是完全相同的代码路径——区别只在于 ROLLBACK 由用户线程触发，而恢复期的回滚由 `TransactionStore.open()` 在打开数据库时自动触发（详见 §9.7.4 阶段 5）。

值得注意的是：在异常分支下，整个 Chunk 4 都被丢弃，这意味着 T4 的 undo log 事实上**根本没有写入磁盘**（它原本就在 Chunk 4 中），因此扫描 metaMap 时根本不会发现 `.undoLog.4`。本案例中 T4 的回滚动作其实是"零操作"——A.3.7 所描述的回滚流程，是在另一种崩溃场景下（Chunk 4 落盘成功、但 commit 阶段崩溃）触发的。我们仍然完整描述这条路径，以便读者理解恢复决策矩阵的两个相邻单元（详见 §9.7.7 中"事务写入 undo log 后崩溃"和"commit() 期间崩溃"两行）。

如果后缀是 `-`（COMMITTED），恢复路径会走 `commit(t, recovery=true)` 而非 rollback：CommitDecisionMaker 把 VersionedValueUncommitted 转换为 VersionedValue，去掉 operationId。这一动作是**幂等**的——崩溃前如果已经部分提交过，重做不会破坏一致性（详见 §9.7.6 末尾的"未决问题与解决方案"段落）。

### A.3.8 Free Space 重算与对外开放写入

最后一步是把磁盘上的字节占用情况重新加载到内存中的 `FreeSpaceBitSet`（`org/h2/mvstore/FreeSpaceBitSet.java`，详见 §6.4）。BitSet 不持久化，必须在每次打开时根据 lastChunk 之前的所有"活 chunk"重新计算：

```text
┌────────────────────────────────────────────────────────────┐
│   阶段 6: FreeSpaceBitSet 重算                              │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   freeSpace = new FreeSpaceBitSet(reservedBlocks=2)        │
│   // block 0,1 被 File Header 双副本永久占用                │
│                                                            │
│   for chunk in metaMap.chunks:                             │
│      freeSpace.markUsed(chunk.block, chunk.len)            │
│                                                            │
│   // 异常分支补充:                                          │
│   if (Chunk 4 字节区间存在但已 reject):                     │
│      // 不 mark used → 该区间在 BitSet 中保持 free          │
│      // 下次 commit 时可被覆盖                               │
│                                                            │
│   // 此时 freeSpace 反映了真实的"活字节"分布                │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

完成 BitSet 重建后，`MVStore.openComplete()` 把状态机推进到 `STATE_OPEN`（详见 §9.1 状态机定义），背景写入线程（BackgroundWriterThread）启动，定时检查点开始运行。此时数据库才真正可以接受新的写入请求——任何新提交的事务会从下一个 chunk id（本例中是 4，注意 Chunk 4 的字节虽然存在但未被记录在 metaMap 里，它的 block 区间属于 free space，会被新 chunk 覆盖）开始递增（详见 §9.6.3 中"chunk id 单调递增"的说明）。

值得详细说明的是 FreeSpaceBitSet 的"重算而非加载"策略。MVStore 没有把 BitSet 持久化到文件，原因有三：第一，BitSet 是高频更新的内存结构，每次 commit 都会变化，持久化会引入新的写放大；第二，从 metaMap 中的 chunk 列表出发，可以严格、确定地重算出 BitSet，不存在"持久化 BitSet 与磁盘真实占用不一致"的可能；第三，重算过程的复杂度是 O(C)，C 为 chunk 数，对常见数据库通常在 10⁴ 量级，恢复期内可以在毫秒级完成（详见 §6.4.5 状态转换图）。

另一个值得展开的设计细节是"Chunk 4 的字节并没有被物理覆盖"。在异常分支下，恢复流程把 Chunk 4 占用的 block 区间标记为 free，但并不会主动 zero-fill 这些字节。这意味着如果进一步发生第二次崩溃，磁盘上仍然存在三类数据：完整的 File Header 双副本、Chunk 1～3 的有效字节、Chunk 4 的"幽灵字节"。第二次重启时，next 链扫描会再次拒绝 Chunk 4，得到与本次相同的恢复结果——这种**确定性 + 幂等性**的组合是 H2 恢复机制最重要的工程性质（详见 §9.7.5 决策树）。

```text
┌──────────────────────────────────────────────────────────────────┐
│        恢复决策汇总矩阵                                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   场景                  │ 触发的检测      │ 恢复动作      │ 数据丢失 │
│   ─────────────────────┼───────────────┼─────────────┼─────────  │
│   File Header 1 损坏   │ block 0 校验失败│ 选 block 1  │ 无         │
│   File Header 2 损坏   │ block 1 校验失败│ 选 block 0  │ 无         │
│   两 Header 都损坏     │ 两次校验失败    │ 末尾扫描     │ 取决末尾   │
│   Chunk N footer 损坏  │ Fletcher 不匹配 │ 回退 Chunk N-1│ Chunk N  │
│   Chunk N header 损坏  │ 字段解析失败    │ 跳过 Chunk N │ Chunk N    │
│   未完成事务           │ undoLog.<id>.   │ rollback    │ T 的修改  │
│   未清理已提交事务      │ undoLog-<id>-   │ commit 重做  │ 无         │
│   FreeSpaceBitSet 误差 │ 重新扫描        │ 全量重建     │ 无         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
**图 A-20: 汇总恢复决策矩阵**

如图 A-20 所示，本案例（异常分支：Chunk 4 footer 损坏）落在第四行：恢复动作是回退到 Chunk 3，T4 的所有修改丢失。从 SQL 客户端角度看，T4 没有收到 `COMMIT OK`，因此 ACID 的 D（持久性）并未被违反——只对已确认提交的事务承诺持久性。

恢复完成的最终状态是：

- 内存中重建出 metaMap、layoutMap 以及 T1、T2、T3 看到过的所有用户表 root；
- `committingTransactions` BitSet 为空集；
- 没有任何 `Transaction` 对象处于 OPEN 状态；
- FreeSpaceBitSet 把 block 0、1（双 header）以及 Chunk 1～3 的字节区间标记为 used，其余（包括 Chunk 4 占用的字节）标记为 free，可被下一个 chunk 覆写；
- MVStore 状态机推进到 `STATE_OPEN`，对外开放写入。

至此，恢复流水线的 8 个步骤全部走完。此时如果应用层立刻发起一个新事务 T5，它的 chunk id 会从最近一次成功 commit（Chunk 3）的下一位继续递增，而磁盘上残存的 Chunk 4 字节会在下一个检查点被新 chunk 覆盖（详见 §9.5 中检查点的覆盖语义）。

把整条恢复路径与 §9.7.7 中的崩溃-恢复矩阵交叉对照可以发现：本案例中 Chunk 4 footer 损坏对应矩阵第 1 行（"写入 Chunk 数据中崩溃"），其数据保证为"最多丢失一个 Chunk"。而正常分支（footer 完整、但 commit() 未完成）则对应矩阵第 4 行（"commit() 期间崩溃"），其数据保证为"不丢失已提交的数据"。两条路径在本案例的同一棵决策树上汇合，最终都让数据库回到一致的可用状态。这种**两条物理路径、一条语义路径**的设计，是 H2 在"无 WAL"前提下仍能提供完整 ACID 保证的根本原因（详见 §9.4.2 与 §10.8 中 ACID 视角的总结）。

最后，从可观测性视角整理一组本案例中可被外部观察到的事件序列，这对生产环境调试很有帮助：

```text
   t0   进程启动, JVM 加载                                    [外部可见]
   t1   FileChannel.open(.mv.db, READ|WRITE)                [文件锁日志]
   t2   readStoreHeader(): block 0 OK, block 1 OK            [trace log]
   t3   pickHeader: chunk=3, version=3                       [trace log]
   t4   setLastChunk(3): footer OK                           [trace log]
   t5   next 链跳到 Chunk 4: footer Fletcher MISMATCH         [WARN log]
   t6   accept Chunk 3 as lastChunk, drop Chunk 4 bytes      [INFO log]
   t7   layoutMap loaded: N maps                             [trace log]
   t8   metaMap scan: undoLog.* count = 0 (本异常分支)        [INFO log]
   t9   FreeSpaceBitSet built: used=K blocks, free=M blocks  [INFO log]
   t10  MVStore.openComplete(): state=OPEN                   [INFO log]
   t11  BackgroundWriterThread started                        [INFO log]
   t12  数据库就绪, 开始服务新连接                              [外部可见]
```

如果换成正常分支（Chunk 4 footer 完好但 commit() 中途崩溃），t8 行会变为"undoLog.* count = 1, suffix=`-`, redo commit"，t9 之后的 BitSet 中 Chunk 4 区间会变成 used 而非 free。两条路径的可观测差异恰好对应它们的语义差异，运维人员可据此精准定位崩溃发生的物理位置（详见 §9.7.4 阶段对照）。

### A.3.9 思考小结

下面是三个用以自检的练习题，覆盖本案例中尚未展开的细节，建议读者结合源码反复推演：

1. 如果 Chunk 4 的 footer 校验恰好通过（fletcher 字段刚好凑巧匹配损坏的字节序列），但 Chunk 4 中某个 leaf page 的 page-level checksum 失败，恢复流程会如何处理？请结合 Page 反序列化路径的 checksum 检查给出答案（详见 §9.6.4）。
2. 双副本 File Header 都损坏、且文件末尾若干 chunk 的 footer 也损坏时，`scanChunkFootersBackward()` 会从后往前扫描寻找最后一个有效 footer。这个回退路径的最坏复杂度是 O(N)（N=chunk 数），在大数据库上可能造成长时间不可用。请讨论 H2 用什么机制把概率降到最低（详见 §9.6.2 中"两份 header 冗余写入"和 §9.7.7 中"两个都无效"行）。
3. 在恢复过程中，`committingTransactions` BitSet 不持久化，因此重建时为空集。请说明：在"commit() 已 flip BitSet，但尚未遍历 undo log 完成"的场景下，恢复期如何只通过 undo log map 名后缀就把这种"半提交"事务推进到一致状态——并给出幂等性论证（详见 §5.6 中 RollbackDecisionMaker 的中止保护与 §9.7.6 中 VersionedBitSet 的恢复处理）。

本案例至此结束。三条端到端路径——SELECT 读路径（A.1）、COMMIT 写路径（A.2）、崩溃恢复路径（A.3）——共同覆盖了 H2 在"读—写—恢复"三个维度上的 ACID 落地视图。如需进一步在版本维度上对照同一路径在不同小版本的实现差异，请参阅附录 B《源码版本变更说明》。

---

**附：本案例引用的源码位置一览**

下表汇总本案例中提到的全部源码符号、所在文件与近似行号，便于读者按图索骥：

| 符号 / 函数                                | 文件路径                                                  | 行号       |
|--------------------------------------------|----------------------------------------------------------|------------|
| `MVStore.openInternal()`                   | `org/h2/mvstore/MVStore.java`                            | 259-319    |
| `MVStore.setLastChunk()`                   | `org/h2/mvstore/MVStore.java`                            | (内部)     |
| `MVStore.openComplete()`                   | `org/h2/mvstore/MVStore.java`                            | (状态切换) |
| `FileStore.readStoreHeader()`              | `org/h2/mvstore/FileStore.java`                          | 962        |
| `FileStore.serializeToBuffer()`            | `org/h2/mvstore/FileStore.java`                          | 1467-1517  |
| `SingleFileStore.start()`                  | `org/h2/mvstore/SingleFileStore.java`                    | (open)     |
| `Chunk.FOOTER_LENGTH`                      | `org/h2/mvstore/Chunk.java`                              | 44         |
| `Page.read()`                              | `org/h2/mvstore/Page.java`                               | 594-675    |
| `TransactionStore.open()`                  | `org/h2/mvstore/tx/TransactionStore.java`                | (打开)     |
| `TransactionStore.commit(t, recovery)`     | `org/h2/mvstore/tx/TransactionStore.java`                | 579-633    |
| `TransactionStore.rollbackTo()`            | `org/h2/mvstore/tx/TransactionStore.java`                | 824-833    |
| `RollbackDecisionMaker.decide()`           | `org/h2/mvstore/tx/RollbackDecisionMaker.java`           | 34-48      |
| `Transaction.rollback()`                   | `org/h2/mvstore/tx/Transaction.java`                     | 561        |
| `FreeSpaceBitSet.allocate()`               | `org/h2/mvstore/FreeSpaceBitSet.java`                    | 140-169    |
| `FreeSpaceBitSet.free()`                   | `org/h2/mvstore/FreeSpaceBitSet.java`                    | 196-202    |

行号以 H2 v2.x 主干为准；不同小版本可能有 ±10 行偏差，但以函数签名为准检索仍可定位（详见 §3 各包索引）。

