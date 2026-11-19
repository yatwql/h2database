# 第10章 查询优化器

> **本章导读**：本章由源码清单汇总而成，覆盖 3 个包、20,347 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 10.1 模块版图

本章覆盖 3 个包、20,347 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.table` | 31 | 13,388 | Classes related to a table and table meta data. |
| `org.h2.index` | 23 | 4,093 | Various table index implementations, as well as cursors to navigate in an index. |
| `org.h2.expression.analysis` | 10 | 2,866 | Base classes for data analysis operations and implementations of window functions. |

## 10.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 10.2.1 `org.h2.table`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | 3,299 | 6 | （无类注释，按方法名归纳） |
| `InformationSchemaTableLegacy` | 2,324 | 2 | （无类注释，按方法名归纳） |
| `Table` | 1,446 | 98 | （无类注释，按方法名归纳） |
| `TableFilter` | 1,310 | 66 | （无类注释，按方法名归纳） |
| `Column` | 867 | 58 | （无类注释，按方法名归纳） |
| `TableLink` | 718 | 35 | （无类注释，按方法名归纳） |

### 10.2.2 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |
| `RegularQueryExpressionIndex` | 223 | 4 | （无类注释，按方法名归纳） |
| `IndexType` | 222 | 16 | （无类注释，按方法名归纳） |

### 10.2.3 `org.h2.expression.analysis`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `WindowFrame` | 878 | 19 | （无类注释，按方法名归纳） |
| `DataAnalysisOperation` | 546 | 9 | （无类注释，按方法名归纳） |
| `WindowFunction` | 545 | 12 | （无类注释，按方法名归纳） |
| `Window` | 339 | 11 | （无类注释，按方法名归纳） |
| `WindowFrameBound` | 165 | 6 | （无类注释，按方法名归纳） |
| `WindowFunctionType` | 142 | 3 | （无类注释，按方法名归纳） |

## 10.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `InformationSchemaTable.canGetRowCount()` | `org/h2/table/InformationSchemaTable.java:3057` |
| `InformationSchemaTable.generateRows()` | `org/h2/table/InformationSchemaTable.java:881` |
| `InformationSchemaTableLegacy.generateRows()` | `org/h2/table/InformationSchemaTableLegacy.java:731` |
| `InformationSchemaTableLegacy.getMaxDataModificationId()` | `org/h2/table/InformationSchemaTableLegacy.java:2310` |
| `Table.addConstraint()` | `org/h2/table/Table.java:1109` |
| `Table.addDependencies()` | `org/h2/table/Table.java:417` |
| `Index.add()` | `org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `org/h2/index/Index.java:379` |
| `IndexCondition.cloneWithIndexColumns()` | `org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `org/h2/index/IndexCondition.java:122` |
| `IndexCursor.canUseIndexForIn()` | `org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `org/h2/index/IndexCursor.java:289` |
| `WindowFrame.getEndIndex()` | `org/h2/expression/analysis/WindowFrame.java:239` |
| `WindowFrame.getExclusion()` | `org/h2/expression/analysis/WindowFrame.java:439` |
| `DataAnalysisOperation.getOverCondition()` | `org/h2/expression/analysis/DataAnalysisOperation.java:97` |
| `DataAnalysisOperation.getValue()` | `org/h2/expression/analysis/DataAnalysisOperation.java:388` |
| `WindowFunction.getCost()` | `org/h2/expression/analysis/WindowFunction.java:534` |
| `WindowFunction.getFunctionType()` | `org/h2/expression/analysis/WindowFunction.java:122` |

## 10.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第11章《查询优化器》。

## 10.5 本章小结

- 本章覆盖 3 个包、20,347 行。
- 关键入口与源码坐标见 §10.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 10.6 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §10.1 的表格，按规模排序挑选目标包。
> 回顾：§10.1 模块版图

**2. 🔵★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §10.1 的表格，按规模排序挑选目标包。
> 回顾：§10.1 模块版图

**3. 🟠★★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §10.1 的表格，按规模排序挑选目标包。
> 回顾：§10.1 模块版图

**4. 🟢★★★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §10.1 的表格，按规模排序挑选目标包。
> 回顾：§10.1 模块版图

## 10.7 延展阅读

- 详见第11章《查询优化器》。
