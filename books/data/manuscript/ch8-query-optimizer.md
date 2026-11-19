# 第10章 查询优化器

> **本章导读**：本章《查询优化器》由源码清单汇总而成，覆盖 2 个包、16,277 行实现，旨在梳理查询优化器的代码结构与核心实现。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 10.1 模块版图

本章覆盖 2 个包、16,277 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.table` | 32 | 13,399 | （无包注释，按主类型归纳） |
| `org.h2.expression.analysis` | 11 | 2,878 | （无包注释，按主类型归纳） |

## 10.2 核心类型

在 `org.h2.table` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 10.2.1 `org.h2.table`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | 3,299 | 6 | （无类注释，按方法名归纳） |
| `InformationSchemaTableLegacy` | 2,324 | 2 | （无类注释，按方法名归纳） |
| `Table` | 1,446 | 98 | （无类注释，按方法名归纳） |
| `TableFilter` | 1,310 | 66 | （无类注释，按方法名归纳） |

### 10.2.2 `org.h2.expression.analysis`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `WindowFrame` | 878 | 19 | （无类注释，按方法名归纳） |
| `DataAnalysisOperation` | 546 | 9 | （无类注释，按方法名归纳） |
| `WindowFunction` | 545 | 12 | （无类注释，按方法名归纳） |
| `Window` | 339 | 11 | （无类注释，按方法名归纳） |

## 10.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `InformationSchemaTable.canGetRowCount()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:3057` |
| `InformationSchemaTable.generateRows()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:881` |
| `InformationSchemaTableLegacy.generateRows()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTableLegacy.java:731` |
| `InformationSchemaTableLegacy.getMaxDataModificationId()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTableLegacy.java:2310` |
| `Table.addConstraint()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:1109` |
| `Table.addDependencies()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:417` |
| `WindowFrame.getEndIndex()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/expression/analysis/WindowFrame.java:239` |
| `WindowFrame.getExclusion()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/expression/analysis/WindowFrame.java:439` |
| `DataAnalysisOperation.getOverCondition()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/expression/analysis/DataAnalysisOperation.java:97` |
| `DataAnalysisOperation.getValue()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/expression/analysis/DataAnalysisOperation.java:388` |
| `WindowFunction.getCost()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/expression/analysis/WindowFunction.java:534` |
| `WindowFunction.getFunctionType()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/expression/analysis/WindowFunction.java:122` |

## 10.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | `org.h2.table` | 3,299 | 6 |
| `InformationSchemaTableLegacy` | `org.h2.table` | 2,324 | 2 |
| `Table` | `org.h2.table` | 1,446 | 98 |
| `TableFilter` | `org.h2.table` | 1,310 | 66 |
| `Column` | `org.h2.table` | 867 | 58 |
| `WindowFrame` | `org.h2.expression.analysis` | 878 | 19 |
| `DataAnalysisOperation` | `org.h2.expression.analysis` | 546 | 9 |
| `WindowFunction` | `org.h2.expression.analysis` | 545 | 12 |
| `Window` | `org.h2.expression.analysis` | 339 | 11 |
| `WindowFrameBound` | `org.h2.expression.analysis` | 165 | 6 |

## 10.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 10.3.2.1 `InformationSchemaTable`

`InformationSchemaTable` 位于 `org.h2.table`，3,299 行、6 个公开方法。它占该包实现的 25%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.2 `InformationSchemaTableLegacy`

`InformationSchemaTableLegacy` 位于 `org.h2.table`，2,324 行、2 个公开方法。它占该包实现的 17%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.3 `Table`

`Table` 位于 `org.h2.table`，1,446 行、98 个公开方法。它占该包实现的 11%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.4 `TableFilter`

`TableFilter` 位于 `org.h2.table`，1,310 行、66 个公开方法。它占该包实现的 10%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.5 `Column`

`Column` 位于 `org.h2.table`，867 行、58 个公开方法。它占该包实现的 6%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.6 `TableLink`

`TableLink` 位于 `org.h2.table`，718 行、35 个公开方法。它占该包实现的 5%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.7 `WindowFrame`

`WindowFrame` 位于 `org.h2.expression.analysis`，878 行、19 个公开方法。它占该包实现的 31%，包内排名第 7。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.8 `DataAnalysisOperation`

`DataAnalysisOperation` 位于 `org.h2.expression.analysis`，546 行、9 个公开方法。它占该包实现的 19%，包内排名第 8。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.9 `WindowFunction`

`WindowFunction` 位于 `org.h2.expression.analysis`，545 行、12 个公开方法。它占该包实现的 19%，包内排名第 9。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.10 `Window`

`Window` 位于 `org.h2.expression.analysis`，339 行、11 个公开方法。它占该包实现的 12%，包内排名第 10。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.11 `WindowFrameBound`

`WindowFrameBound` 位于 `org.h2.expression.analysis`，165 行、6 个公开方法。它占该包实现的 6%，包内排名第 11。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 10.3.2.12 `WindowFunctionType`

`WindowFunctionType` 位于 `org.h2.expression.analysis`，142 行、3 个公开方法。它占该包实现的 5%，包内排名第 12。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

## 10.3.2 源码坐标明细

本章主责包中 65 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `InformationSchemaTable.canGetRowCount()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:3057` |
| `InformationSchemaTable.generateRows()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:881` |
| `InformationSchemaTable.getMaxDataModificationId()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:2974` |
| `InformationSchemaTable.getRowCount()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:2993` |
| `InformationSchemaTable.getRowCountApproximation()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:2998` |
| `InformationSchemaTable.isView()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTable.java:2988` |
| `InformationSchemaTableLegacy.generateRows()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTableLegacy.java:731` |
| `InformationSchemaTableLegacy.getMaxDataModificationId()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/InformationSchemaTableLegacy.java:2310` |
| `Table.addConstraint()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:1109` |
| `Table.addDependencies()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:417` |
| `Table.addDependentMaterializedView()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:1091` |
| `Table.addDependentView()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:1082` |
| `Table.addIndex()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:171` |
| `Table.addRow()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/Table.java:232` |
| `TableFilter.accept()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/TableFilter.java:1304` |
| `TableFilter.addCommonJoinColumnToExclude()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/TableFilter.java:1195` |
| `TableFilter.addCommonJoinColumns()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/TableFilter.java:1179` |
| `TableFilter.addFilter()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/TableFilter.java:676` |
| `TableFilter.addFilterCondition()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/TableFilter.java:617` |
| `TableFilter.addIndexCondition()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/table/TableFilter.java:607` |

## 10.4 阅读路径

读 `org.h2.table` 的 32 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.table` 的 package-info 与 `InformationSchemaTable`，建立第10章的职责边界。
2. 再读 `InformationSchemaTable` 的 6 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.expression.analysis`（本章最小包，2,878 行）的实现，关注容量与失败路径。

跨章衔接请对照第11章《查询优化器》。

## 10.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.table` | `org.h2`, `org.h2.command`, `org.h2.constraint`, `org.h2.engine` |
| `org.h2.expression.analysis` | `org.h2`, `org.h2.command`, `org.h2.expression` |

## 10.6 设计权衡

`org.h2.table` 有 32 个文件、13,399 行。平均每文件 418 行。

其中 `InformationSchemaTable` 独占 3,299 行，6 个公开方法。规模集中，风险也集中。

它对外声明 8 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.expression.analysis`（2,878 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 10.7 常见误区

把 `org.h2.table` 的行数当作复杂度上限是误读。`InformationSchemaTable` 之外还有 31 个文件，其中多为类型族与样板。

只读 `InformationSchemaTable` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.table` 与 `org.h2.expression.analysis` 不能互换。前者 32 个文件，后者 11 个文件，扩展点分布完全不同。

## 10.8 深读要点

规模信号：`org.h2.table` 占本章 82% 的实现行数，改动风险最高。
耦合信号：`org.h2.table` 依赖 8 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`InformationSchemaTable` 的公开方法 6 个，读它等于读本章的主干。

## 10.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Table**：详见[术语表](back/glossary.md)对应条目。

## 10.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `InformationSchemaTable` | `org.h2.table` | 3,299 | 6 | 按方法名归纳 |
| `InformationSchemaTableLegacy` | `org.h2.table` | 2,324 | 2 | 按方法名归纳 |
| `WindowFrame` | `org.h2.expression.analysis` | 878 | 19 | 按方法名归纳 |
| `DataAnalysisOperation` | `org.h2.expression.analysis` | 546 | 9 | 按方法名归纳 |

## 10.9 本章小结

本章覆盖 2 个包、共 16,277 行，内容主要集中在 org.h2.table 包。
- 关键入口与源码坐标见 §10.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 10.10 延伸思考

**1. 🟢★ 说明 `InformationSchemaTable` 与 `InformationSchemaTableLegacy` 的分工差异。给出调用方向。**

> 提示：第10章 §10.2 的表格给出 `InformationSchemaTable` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**2. 🔵★★ `WindowFrame` 为什么独立成类型，而不是并入 `DataAnalysisOperation`？**

> 提示：第10章 §10.2 的表格给出 `WindowFrame` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**3. 🟠★★★ 以 `InformationSchemaTable` 为入口，画出一次完整调用经过的包。**

> 提示：第10章 §10.2 的表格给出 `InformationSchemaTable` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `WindowFrame` 还是 `DataAnalysisOperation`？说明代价。**

> 提示：第10章 §10.2 的表格给出 `WindowFrame` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§10.2 核心类型

## 10.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.table`：32 个文件、13,399 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.expression.analysis`（2,878 行）：两者的扩展与兼容策略不同，差异落在 `InformationSchemaTable` 的 6 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 10.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.table` | `org.h2` | 352 |
| `org.h2.table` | `org.h2.command` | 19 |
| `org.h2.table` | `org.h2.constraint` | 3 |
| `org.h2.expression.analysis` | `org.h2` | 45 |
| `org.h2.expression.analysis` | `org.h2.command` | 7 |
| `org.h2.expression.analysis` | `org.h2.expression` | 1 |

## 10.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.table` 与 `org.h2.expression.analysis` 的调用方向？`InformationSchemaTable` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.table` 的调用链讲到落盘或返回，并说清 `org.h2.table` 与 `org.h2.expression.analysis` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.table` 的注释与实现对不上，你信哪一边，为什么？

## 10.12 延展阅读

- 详见第11章《查询优化器》。
