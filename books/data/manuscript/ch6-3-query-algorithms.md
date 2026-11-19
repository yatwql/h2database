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

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 8.2.1 `org.h2.expression`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ExpressionColumn` | 553 | 23 | （无类注释，按方法名归纳） |
| `Expression` | 551 | 41 | （无类注释，按方法名归纳） |
| `BinaryOperation` | 455 | 6 | （无类注释，按方法名归纳） |
| `ExpressionVisitor` | 417 | 17 | （无类注释，按方法名归纳） |
| `IntervalOperation` | 381 | 4 | （无类注释，按方法名归纳） |
| `SimpleCase` | 289 | 12 | （无类注释，按方法名归纳） |

### 8.2.2 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |
| `RegularQueryExpressionIndex` | 223 | 4 | （无类注释，按方法名归纳） |
| `IndexType` | 222 | 16 | （无类注释，按方法名归纳） |

### 8.2.3 `org.h2.result`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `LocalResult` | 710 | 42 | （无类注释，按方法名归纳） |
| `UpdatableRow` | 341 | 5 | （无类注释，按方法名归纳） |
| `SortOrder` | 334 | 15 | （无类注释，按方法名归纳） |
| `SimpleResult` | 303 | 31 | （无类注释，按方法名归纳） |
| `ResultRemote` | 287 | 17 | （无类注释，按方法名归纳） |
| `RowFactory` | 201 | 17 | （无类注释，按方法名归纳） |

## 8.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

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

## 8.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第9章《索引与表达式求值》。

## 8.5 本章小结

- 本章覆盖 3 个包、13,602 行。
- 关键入口与源码坐标见 §8.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 8.6 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §8.1 的表格，按规模排序挑选目标包。
> 回顾：§8.1 模块版图

**2. 🔵★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §8.1 的表格，按规模排序挑选目标包。
> 回顾：§8.1 模块版图

**3. 🟠★★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §8.1 的表格，按规模排序挑选目标包。
> 回顾：§8.1 模块版图

**4. 🟢★★★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §8.1 的表格，按规模排序挑选目标包。
> 回顾：§8.1 模块版图

## 8.7 延展阅读

- 详见第9章《索引与表达式求值》。
