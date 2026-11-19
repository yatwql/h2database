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

在 `org.h2.table` 之外，本章还有 2 个包；下表每包取前 4 个类型，按规模降序。

### 10.2.1 `org.h2.table`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | 3,299 | 6 | （无类注释，按方法名归纳） |
| `InformationSchemaTableLegacy` | 2,324 | 2 | （无类注释，按方法名归纳） |
| `Table` | 1,446 | 98 | （无类注释，按方法名归纳） |
| `TableFilter` | 1,310 | 66 | （无类注释，按方法名归纳） |

### 10.2.2 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |

### 10.2.3 `org.h2.expression.analysis`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `WindowFrame` | 878 | 19 | （无类注释，按方法名归纳） |
| `DataAnalysisOperation` | 546 | 9 | （无类注释，按方法名归纳） |
| `WindowFunction` | 545 | 12 | （无类注释，按方法名归纳） |
| `Window` | 339 | 11 | （无类注释，按方法名归纳） |

## 10.3 关键 API 与源码坐标

把 3 个包的关键入口与源码位置对应起来，共 9 条坐标，行号由脚本核验。

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

## 10.3.1 公共类型清单

本章抽样类型按包分组，共 15 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | `org.h2.table` | 3,299 | 6 |
| `InformationSchemaTableLegacy` | `org.h2.table` | 2,324 | 2 |
| `Table` | `org.h2.table` | 1,446 | 98 |
| `TableFilter` | `org.h2.table` | 1,310 | 66 |
| `Column` | `org.h2.table` | 867 | 58 |
| `Index` | `org.h2.index` | 834 | 37 |
| `IndexCondition` | `org.h2.index` | 675 | 24 |
| `IndexCursor` | `org.h2.index` | 494 | 13 |
| `LinkedIndex` | `org.h2.index` | 298 | 13 |
| `RegularQueryExpressionIndex` | `org.h2.index` | 223 | 4 |
| `WindowFrame` | `org.h2.expression.analysis` | 878 | 19 |
| `DataAnalysisOperation` | `org.h2.expression.analysis` | 546 | 9 |
| `WindowFunction` | `org.h2.expression.analysis` | 545 | 12 |
| `Window` | `org.h2.expression.analysis` | 339 | 11 |
| `WindowFrameBound` | `org.h2.expression.analysis` | 165 | 6 |

## 10.4 阅读路径

读 `org.h2.table` 的 31 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.table` 的 package-info 与 `InformationSchemaTable`，建立第10章的职责边界。
2. 再读 `InformationSchemaTable` 的 6 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.expression.analysis`（本章最小包，2,866 行）的实现，关注容量与失败路径。

跨章衔接请对照第11章《查询优化器》。

## 10.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.table` | `org.h2.value`, `org.h2.engine`, `org.h2.result`, `org.h2.index` |
| `org.h2.index` | `org.h2.result`, `org.h2.table`, `org.h2.value`, `org.h2.engine` |
| `org.h2.expression.analysis` | `org.h2.value`, `org.h2.expression`, `org.h2.table`, `org.h2.command.query` |

## 10.6 设计权衡

- `org.h2.table` 用 31 个文件换到 13,388 行实现，平均每文件 431 行，其中 `InformationSchemaTable` 独占 3,299 行、6 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.index`（4,093 行）与 `org.h2.table` 的职责差是本章最值得记的一条边界。

## 10.7 常见误区

- 把 `org.h2.table` 的 13,388 行当作复杂度上限：`InformationSchemaTable` 之外的 30 个文件多为类型族与样板。
- 只看 `InformationSchemaTable` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.table` 与 `org.h2.index` 视为可互换：前者 31 文件、后者 23 文件，扩展点分布完全不同。

## 10.8 深读要点

规模信号：`org.h2.table` 占本章 66% 的实现行数，改动风险最高。
耦合信号：`org.h2.table` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`InformationSchemaTable` 的公开方法 6 个，读它等于读本章的主干。

## 10.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Index**：详见[术语表](back/glossary.md)对应条目。
- **Table**：详见[术语表](back/glossary.md)对应条目。

## 10.9 知识点清单

1. `org.h2.table` 的 `InformationSchemaTable`：3,299 行、6 个公开方法，职责按方法名归纳
2. `org.h2.table` 的 `InformationSchemaTableLegacy`：2,324 行、2 个公开方法，职责按方法名归纳
3. `org.h2.index` 的 `Index`：834 行、37 个公开方法，职责按方法名归纳
4. `org.h2.index` 的 `IndexCondition`：675 行、24 个公开方法，职责按方法名归纳
5. `org.h2.expression.analysis` 的 `WindowFrame`：878 行、19 个公开方法，职责按方法名归纳
6. `org.h2.expression.analysis` 的 `DataAnalysisOperation`：546 行、9 个公开方法，职责按方法名归纳

## 10.9 本章小结

- 本章覆盖 3 个包、20,347 行。
- 关键入口与源码坐标见 §10.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 10.10 延伸思考

**1. 🟢★ 指出 `org.h2.table` 中 `InformationSchemaTable` 与 `InformationSchemaTableLegacy` 的分工差异，并给出调用方向。**

> 提示：第10章 §10.2 的表格给出 `InformationSchemaTable` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**2. 🔵★★ 围绕 `org.h2.index` 的 `Index`，说明它为什么需要独立成类型而不是并入 `IndexCondition`。**

> 提示：第10章 §10.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**3. 🟠★★★ 以 `org.h2.expression.analysis` 的 `WindowFrame` 为入口，画出一次完整调用经过的包。**

> 提示：第10章 §10.2 的表格给出 `WindowFrame` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.table` 的一个类型，你保留 `InformationSchemaTable` 还是 `InformationSchemaTableLegacy`？说明代价。**

> 提示：第10章 §10.2 的表格给出 `InformationSchemaTable` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

## 10.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.table`：31 个文件、13,388 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.index`（4,093 行）：两者的扩展与兼容策略不同，差异落在 `InformationSchemaTable` 的 6 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 10.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.table` | `org.h2.value` | 59 |
| `org.h2.table` | `org.h2.engine` | 57 |
| `org.h2.table` | `org.h2.result` | 42 |
| `org.h2.index` | `org.h2.result` | 51 |
| `org.h2.index` | `org.h2.table` | 41 |
| `org.h2.index` | `org.h2.value` | 27 |
| `org.h2.expression.analysis` | `org.h2.value` | 12 |
| `org.h2.expression.analysis` | `org.h2.expression` | 9 |
| `org.h2.expression.analysis` | `org.h2.table` | 8 |

## 10.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.table` 与 `org.h2.index` 之间的调用方向？
- `InformationSchemaTable` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.table` 的调用链讲到落盘或返回？
- `org.h2.table` 与 `org.h2.index` 若合并，会丢掉哪个扩展点？
- `org.h2.table` 的注释与实现若不一致，你信哪一边，为什么？

## 10.12 延展阅读

- 详见第11章《查询优化器》。
