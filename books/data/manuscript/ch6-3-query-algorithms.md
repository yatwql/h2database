# 第8章 索引与表达式求值

> **本章导读**：本章由源码清单汇总而成，覆盖 1 个包、4,105 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 8.1 模块版图

本章覆盖 1 个包、4,105 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.index` | 24 | 4,105 | （无包注释，按主类型归纳） |

## 8.2 核心类型

在 `org.h2.index` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 8.2.1 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |

## 8.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Index.add()` | `h2/src/main/org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `h2/src/main/org/h2/index/Index.java:379` |
| `IndexCondition.cloneWithIndexColumns()` | `h2/src/main/org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `h2/src/main/org/h2/index/IndexCondition.java:122` |
| `IndexCursor.canUseIndexForIn()` | `h2/src/main/org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `h2/src/main/org/h2/index/IndexCursor.java:289` |

## 8.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Index` | `org.h2.index` | 834 | 37 |
| `IndexCondition` | `org.h2.index` | 675 | 24 |
| `IndexCursor` | `org.h2.index` | 494 | 13 |
| `LinkedIndex` | `org.h2.index` | 298 | 13 |
| `RegularQueryExpressionIndex` | `org.h2.index` | 223 | 4 |

## 8.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 8.3.2.1 `Index`

`Index` 位于 `org.h2.index`，834 行、37 个公开方法。它占该包实现的 20%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 8.3.2.2 `IndexCondition`

`IndexCondition` 位于 `org.h2.index`，675 行、24 个公开方法。它占该包实现的 16%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 8.3.2.3 `IndexCursor`

`IndexCursor` 位于 `org.h2.index`，494 行、13 个公开方法。它占该包实现的 12%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 8.3.2.4 `LinkedIndex`

`LinkedIndex` 位于 `org.h2.index`，298 行、13 个公开方法。它占该包实现的 7%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 8.3.2.5 `RegularQueryExpressionIndex`

`RegularQueryExpressionIndex` 位于 `org.h2.index`，223 行、4 个公开方法。它占该包实现的 5%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 8.3.2.6 `IndexType`

`IndexType` 位于 `org.h2.index`，222 行、16 个公开方法。它占该包实现的 5%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

## 8.3.2 源码坐标明细

本章主责包中 34 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Index.add()` | `h2/src/main/org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `h2/src/main/org/h2/index/Index.java:379` |
| `Index.canFindNext()` | `h2/src/main/org/h2/index/Index.java:302` |
| `Index.canGetFirstOrLast()` | `h2/src/main/org/h2/index/Index.java:293` |
| `Index.canScan()` | `h2/src/main/org/h2/index/Index.java:539` |
| `Index.close()` | `h2/src/main/org/h2/index/Index.java:202` |
| `IndexCondition.cloneWithIndexColumns()` | `h2/src/main/org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `h2/src/main/org/h2/index/IndexCondition.java:122` |
| `IndexCondition.getColumn()` | `h2/src/main/org/h2/index/IndexCondition.java:472` |
| `IndexCondition.getColumns()` | `h2/src/main/org/h2/index/IndexCondition.java:485` |
| `IndexCondition.getCompareType()` | `h2/src/main/org/h2/index/IndexCondition.java:462` |
| `IndexCondition.getCompoundInList()` | `h2/src/main/org/h2/index/IndexCondition.java:144` |
| `IndexCursor.canUseIndexForIn()` | `h2/src/main/org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `h2/src/main/org/h2/index/IndexCursor.java:289` |
| `IndexCursor.get()` | `h2/src/main/org/h2/index/IndexCursor.java:411` |
| `IndexCursor.getEnd()` | `h2/src/main/org/h2/index/IndexCursor.java:406` |
| `IndexCursor.getInColumnPosition()` | `h2/src/main/org/h2/index/IndexCursor.java:237` |
| `IndexCursor.getSearchRow()` | `h2/src/main/org/h2/index/IndexCursor.java:419` |
| `LinkedIndex.add()` | `h2/src/main/org/h2/index/LinkedIndex.java:61` |
| `LinkedIndex.checkRename()` | `h2/src/main/org/h2/index/LinkedIndex.java:199` |

## 8.4 阅读路径

读 `org.h2.index` 的 24 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.index` 的 package-info 与 `Index`，建立第8章的职责边界。
2. 再读 `Index` 的 37 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.index`（本章最小包，4,105 行）的实现，关注容量与失败路径。

跨章衔接请对照第9章《索引与表达式求值》。

## 8.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.index` | `org.h2`, `org.h2.command`, `org.h2.expression`, `org.h2.util` |

## 8.6 设计权衡

`org.h2.index` 有 24 个文件、4,105 行。平均每文件 171 行。

其中 `Index` 独占 834 行，37 个公开方法。规模集中，风险也集中。

它对外声明 4 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.index`（4,105 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 8.7 常见误区

把 `org.h2.index` 的行数当作复杂度上限是误读。`Index` 之外还有 23 个文件，其中多为类型族与样板。

只读 `Index` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.index` 与 `org.h2.index` 不能互换。前者 24 个文件，后者 24 个文件，扩展点分布完全不同。

## 8.8 深读要点

规模信号：`org.h2.index` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.index` 依赖 4 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`Index` 的公开方法 37 个，读它等于读本章的主干。

## 8.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Index**：详见[术语表](back/glossary.md)对应条目。
- **ACID**：详见[术语表](back/glossary.md)对应条目。
- **CAS (Compare-And-Swap)**：详见[术语表](back/glossary.md)对应条目。
- **Deadlock**：详见[术语表](back/glossary.md)对应条目。
- **Lock**：详见[术语表](back/glossary.md)对应条目。
- **Meta Lock**：详见[术语表](back/glossary.md)对应条目。
- **MVCC**：详见[术语表](back/glossary.md)对应条目。

## 8.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `Index` | `org.h2.index` | 834 | 37 | 按方法名归纳 |
| `IndexCondition` | `org.h2.index` | 675 | 24 | 按方法名归纳 |

## 8.9 本章小结

- 本章覆盖 1 个包、4,105 行。
- 关键入口与源码坐标见 §8.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 8.10 延伸思考

**1. 🟢★ 说明 `Index` 与 `IndexCondition` 的分工差异。给出调用方向。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**2. 🔵★★ `Index` 为什么独立成类型，而不是并入 `IndexCondition`？**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**3. 🟠★★★ 以 `Index` 为入口，画出一次完整调用经过的包。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `Index` 还是 `IndexCondition`？说明代价。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

## 8.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.index`：24 个文件、4,105 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.index`（4,105 行）：两者的性能与规模策略不同，差异落在 `Index` 的 37 个公开方法里。
- 若性能与规模假设被打破（4 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 8.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.index` | `org.h2` | 175 |
| `org.h2.index` | `org.h2.command` | 13 |
| `org.h2.index` | `org.h2.expression` | 3 |

## 8.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.index` 与 `org.h2.index` 的调用方向？`Index` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.index` 的调用链讲到落盘或返回，并说清 `org.h2.index` 与 `org.h2.index` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.index` 的注释与实现对不上，你信哪一边，为什么？

## 8.12 延展阅读

- 详见第9章《索引与表达式求值》。
