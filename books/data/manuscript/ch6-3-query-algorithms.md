# 第8章 索引与表达式求值

> **本章导读**：本章由源码清单汇总而成，覆盖 3 个包、13,602 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 8.1 模块版图

本章覆盖 3 个包、13,602 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.expression` | 35 | 5,832 | Expressions include mathematical operations, simple values, and others. |
| `org.h2.index` | 23 | 4,093 | Various table index implementations, as well as cursors to navigate in an index. |
| `org.h2.result` | 21 | 3,677 | Implementation of row and internal result sets. |

## 8.2 核心类型

在 `org.h2.expression` 之外，本章还有 2 个包；下表每包取前 4 个类型，按规模降序。

### 8.2.1 `org.h2.expression`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ExpressionColumn` | 553 | 23 | （无类注释，按方法名归纳） |
| `Expression` | 551 | 41 | （无类注释，按方法名归纳） |
| `BinaryOperation` | 455 | 6 | （无类注释，按方法名归纳） |
| `ExpressionVisitor` | 417 | 17 | （无类注释，按方法名归纳） |

### 8.2.2 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |

### 8.2.3 `org.h2.result`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `LocalResult` | 710 | 42 | （无类注释，按方法名归纳） |
| `UpdatableRow` | 341 | 5 | （无类注释，按方法名归纳） |
| `SortOrder` | 334 | 15 | （无类注释，按方法名归纳） |
| `SimpleResult` | 303 | 31 | （无类注释，按方法名归纳） |

## 8.3 关键 API 与源码坐标

把 3 个包的关键入口与源码位置对应起来，共 9 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ExpressionColumn.createIndexConditions()` | `org/h2/expression/ExpressionColumn.java:499` |
| `ExpressionColumn.getAlias()` | `org/h2/expression/ExpressionColumn.java:404` |
| `Expression.addFilterConditions()` | `org/h2/expression/Expression.java:477` |
| `Expression.createIndexConditions()` | `org/h2/expression/Expression.java:354` |
| `BinaryOperation.getOperationType()` | `org/h2/expression/BinaryOperation.java:450` |
| `BinaryOperation.getUnenclosedSQL()` | `org/h2/expression/BinaryOperation.java:74` |
| `Index.add()` | `org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `org/h2/index/Index.java:379` |
| `IndexCondition.cloneWithIndexColumns()` | `org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `org/h2/index/IndexCondition.java:122` |
| `IndexCursor.canUseIndexForIn()` | `org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `org/h2/index/IndexCursor.java:289` |
| `LocalResult.addRow()` | `org/h2/result/LocalResult.java:420` |
| `LocalResult.addRowForTable()` | `org/h2/result/LocalResult.java:404` |
| `UpdatableRow.deleteRow()` | `org/h2/result/UpdatableRow.java:257` |
| `UpdatableRow.insertRow()` | `org/h2/result/UpdatableRow.java:309` |
| `SortOrder.addNullOrdering()` | `org/h2/result/SortOrder.java:312` |
| `SortOrder.compare()` | `org/h2/result/SortOrder.java:162` |

## 8.3.1 公共类型清单

本章抽样类型按包分组，共 15 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `ExpressionColumn` | `org.h2.expression` | 553 | 23 |
| `Expression` | `org.h2.expression` | 551 | 41 |
| `BinaryOperation` | `org.h2.expression` | 455 | 6 |
| `ExpressionVisitor` | `org.h2.expression` | 417 | 17 |
| `IntervalOperation` | `org.h2.expression` | 381 | 4 |
| `Index` | `org.h2.index` | 834 | 37 |
| `IndexCondition` | `org.h2.index` | 675 | 24 |
| `IndexCursor` | `org.h2.index` | 494 | 13 |
| `LinkedIndex` | `org.h2.index` | 298 | 13 |
| `RegularQueryExpressionIndex` | `org.h2.index` | 223 | 4 |
| `LocalResult` | `org.h2.result` | 710 | 42 |
| `UpdatableRow` | `org.h2.result` | 341 | 5 |
| `SortOrder` | `org.h2.result` | 334 | 15 |
| `SimpleResult` | `org.h2.result` | 303 | 31 |
| `ResultRemote` | `org.h2.result` | 287 | 17 |

## 8.4 阅读路径

读 `org.h2.expression` 的 35 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.expression` 的 package-info 与 `ExpressionColumn`，建立第8章的职责边界。
2. 再读 `ExpressionColumn` 的 23 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.result`（本章最小包，3,677 行）的实现，关注容量与失败路径。

跨章衔接请对照第9章《索引与表达式求值》。

## 8.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.expression` | `org.h2.value`, `org.h2.table`, `org.h2.engine`, `org.h2.message` |
| `org.h2.index` | `org.h2.result`, `org.h2.table`, `org.h2.value`, `org.h2.engine` |
| `org.h2.result` | `org.h2.value`, `org.h2.engine`, `org.h2.util`, `org.h2.expression` |

## 8.6 设计权衡

- `org.h2.expression` 用 35 个文件换到 5,832 行实现，平均每文件 166 行，其中 `ExpressionColumn` 独占 553 行、23 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.index`（4,093 行）与 `org.h2.expression` 的职责差是本章最值得记的一条边界。

## 8.7 常见误区

- 把 `org.h2.expression` 的 5,832 行当作复杂度上限：`ExpressionColumn` 之外的 34 个文件多为类型族与样板。
- 只看 `ExpressionColumn` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.expression` 与 `org.h2.index` 视为可互换：前者 35 文件、后者 23 文件，扩展点分布完全不同。

## 8.8 深读要点

规模信号：`org.h2.expression` 占本章 43% 的实现行数，改动风险最高。
耦合信号：`org.h2.expression` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`ExpressionColumn` 的公开方法 23 个，读它等于读本章的主干。

## 8.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Index**：详见[术语表](back/glossary.md)对应条目。
- **Table**：详见[术语表](back/glossary.md)对应条目。
- **Value**：详见[术语表](back/glossary.md)对应条目。

## 8.9 知识点清单

1. `org.h2.expression` 的 `ExpressionColumn`：553 行、23 个公开方法，职责按方法名归纳
2. `org.h2.expression` 的 `Expression`：551 行、41 个公开方法，职责按方法名归纳
3. `org.h2.index` 的 `Index`：834 行、37 个公开方法，职责按方法名归纳
4. `org.h2.index` 的 `IndexCondition`：675 行、24 个公开方法，职责按方法名归纳
5. `org.h2.result` 的 `LocalResult`：710 行、42 个公开方法，职责按方法名归纳
6. `org.h2.result` 的 `UpdatableRow`：341 行、5 个公开方法，职责按方法名归纳

## 8.9 本章小结

- 本章覆盖 3 个包、13,602 行。
- 关键入口与源码坐标见 §8.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 8.10 延伸思考

**1. 🟢★ 指出 `org.h2.expression` 中 `ExpressionColumn` 与 `Expression` 的分工差异，并给出调用方向。**

> 提示：第8章 §8.2 的表格给出 `ExpressionColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**2. 🔵★★ 围绕 `org.h2.index` 的 `Index`，说明它为什么需要独立成类型而不是并入 `IndexCondition`。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**3. 🟠★★★ 以 `org.h2.result` 的 `LocalResult` 为入口，画出一次完整调用经过的包。**

> 提示：第8章 §8.2 的表格给出 `LocalResult` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.expression` 的一个类型，你保留 `ExpressionColumn` 还是 `Expression`？说明代价。**

> 提示：第8章 §8.2 的表格给出 `ExpressionColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

## 8.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.expression`：35 个文件、5,832 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.index`（4,093 行）：两者的性能与规模策略不同，差异落在 `ExpressionColumn` 的 23 个公开方法里。
- 若性能与规模假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 8.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.expression` | `org.h2.value` | 125 |
| `org.h2.expression` | `org.h2.table` | 37 |
| `org.h2.expression` | `org.h2.engine` | 34 |
| `org.h2.index` | `org.h2.result` | 51 |
| `org.h2.index` | `org.h2.table` | 41 |
| `org.h2.index` | `org.h2.value` | 27 |
| `org.h2.result` | `org.h2.value` | 45 |
| `org.h2.result` | `org.h2.engine` | 21 |
| `org.h2.result` | `org.h2.util` | 8 |

## 8.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.expression` 与 `org.h2.index` 之间的调用方向？
- `ExpressionColumn` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.expression` 的调用链讲到落盘或返回？
- `org.h2.expression` 与 `org.h2.index` 若合并，会丢掉哪个扩展点？
- `org.h2.expression` 的注释与实现若不一致，你信哪一边，为什么？

## 8.12 延展阅读

- 详见第9章《索引与表达式求值》。
