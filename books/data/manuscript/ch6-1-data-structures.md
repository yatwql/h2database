# 第6章 数据结构：值、行与页

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、19,200 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 6.1 模块版图

本章覆盖 2 个包、19,200 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.value` | 56 | 15,512 | （无包注释，按主类型归纳） |
| `org.h2.result` | 22 | 3,688 | （无包注释，按主类型归纳） |

## 6.2 核心类型

在 `org.h2.value` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 6.2.1 `org.h2.value`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Value` | 2,873 | 67 | （无类注释，按方法名归纳） |
| `TypeInfo` | 1,539 | 23 | （无类注释，按方法名归纳） |
| `Transfer` | 1,368 | 31 | （无类注释，按方法名归纳） |
| `DataType` | 828 | 25 | （无类注释，按方法名归纳） |

### 6.2.2 `org.h2.result`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `LocalResult` | 710 | 42 | （无类注释，按方法名归纳） |
| `UpdatableRow` | 341 | 5 | （无类注释，按方法名归纳） |
| `SortOrder` | 334 | 15 | （无类注释，按方法名归纳） |
| `SimpleResult` | 303 | 31 | （无类注释，按方法名归纳） |

## 6.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `h2/src/main/org/h2/value/Value.java:929` |
| `Value.castTo()` | `h2/src/main/org/h2/value/Value.java:1105` |
| `TypeInfo.areSameTypes()` | `h2/src/main/org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `h2/src/main/org/h2/value/TypeInfo.java:764` |
| `Transfer.close()` | `h2/src/main/org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `h2/src/main/org/h2/value/Transfer.java:216` |
| `LocalResult.addRow()` | `h2/src/main/org/h2/result/LocalResult.java:420` |
| `LocalResult.addRowForTable()` | `h2/src/main/org/h2/result/LocalResult.java:404` |
| `UpdatableRow.deleteRow()` | `h2/src/main/org/h2/result/UpdatableRow.java:257` |
| `UpdatableRow.insertRow()` | `h2/src/main/org/h2/result/UpdatableRow.java:309` |
| `SortOrder.addNullOrdering()` | `h2/src/main/org/h2/result/SortOrder.java:312` |
| `SortOrder.compare()` | `h2/src/main/org/h2/result/SortOrder.java:162` |

## 6.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Value` | `org.h2.value` | 2,873 | 67 |
| `TypeInfo` | `org.h2.value` | 1,539 | 23 |
| `Transfer` | `org.h2.value` | 1,368 | 31 |
| `DataType` | `org.h2.value` | 828 | 25 |
| `ValueToObjectConverter` | `org.h2.value` | 642 | 6 |
| `LocalResult` | `org.h2.result` | 710 | 42 |
| `UpdatableRow` | `org.h2.result` | 341 | 5 |
| `SortOrder` | `org.h2.result` | 334 | 15 |
| `SimpleResult` | `org.h2.result` | 303 | 31 |
| `ResultRemote` | `org.h2.result` | 287 | 17 |

## 6.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 6.3.2.1 `Value`

`Value` 位于 `org.h2.value`，2,873 行、67 个公开方法。它占该包实现的 19%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.2 `TypeInfo`

`TypeInfo` 位于 `org.h2.value`，1,539 行、23 个公开方法。它占该包实现的 10%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.3 `Transfer`

`Transfer` 位于 `org.h2.value`，1,368 行、31 个公开方法。它占该包实现的 9%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.4 `DataType`

`DataType` 位于 `org.h2.value`，828 行、25 个公开方法。它占该包实现的 5%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.5 `ValueToObjectConverter`

`ValueToObjectConverter` 位于 `org.h2.value`，642 行、6 个公开方法。它占该包实现的 4%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.6 `ValueToObjectConverter2`

`ValueToObjectConverter2` 位于 `org.h2.value`，433 行、2 个公开方法。它占该包实现的 3%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.7 `LocalResult`

`LocalResult` 位于 `org.h2.result`，710 行、42 个公开方法。它占该包实现的 19%，包内排名第 7。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.8 `UpdatableRow`

`UpdatableRow` 位于 `org.h2.result`，341 行、5 个公开方法。它占该包实现的 9%，包内排名第 8。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.9 `SortOrder`

`SortOrder` 位于 `org.h2.result`，334 行、15 个公开方法。它占该包实现的 9%，包内排名第 9。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.10 `SimpleResult`

`SimpleResult` 位于 `org.h2.result`，303 行、31 个公开方法。它占该包实现的 8%，包内排名第 10。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.11 `ResultRemote`

`ResultRemote` 位于 `org.h2.result`，287 行、17 个公开方法。它占该包实现的 8%，包内排名第 11。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 6.3.2.12 `RowFactory`

`RowFactory` 位于 `org.h2.result`，201 行、17 个公开方法。它占该包实现的 5%，包内排名第 12。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

## 6.3.2 源码坐标明细

本章主责包中 67 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `h2/src/main/org/h2/value/Value.java:929` |
| `Value.castTo()` | `h2/src/main/org/h2/value/Value.java:1105` |
| `Value.charLength()` | `h2/src/main/org/h2/value/Value.java:2832` |
| `Value.clearCache()` | `h2/src/main/org/h2/value/Value.java:773` |
| `Value.compareTo()` | `h2/src/main/org/h2/value/Value.java:2643` |
| `Value.compareTypeSafe()` | `h2/src/main/org/h2/value/Value.java:2631` |
| `TypeInfo.areSameTypes()` | `h2/src/main/org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `h2/src/main/org/h2/value/TypeInfo.java:764` |
| `TypeInfo.equals()` | `h2/src/main/org/h2/value/TypeInfo.java:1397` |
| `TypeInfo.getDecimalPrecision()` | `h2/src/main/org/h2/value/TypeInfo.java:1490` |
| `TypeInfo.getDeclaredPrecision()` | `h2/src/main/org/h2/value/TypeInfo.java:1095` |
| `TypeInfo.getDeclaredScale()` | `h2/src/main/org/h2/value/TypeInfo.java:1166` |
| `Transfer.close()` | `h2/src/main/org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `h2/src/main/org/h2/value/Transfer.java:216` |
| `Transfer.getSocket()` | `h2/src/main/org/h2/value/Transfer.java:1289` |
| `Transfer.getVersion()` | `h2/src/main/org/h2/value/Transfer.java:1330` |
| `Transfer.init()` | `h2/src/main/org/h2/value/Transfer.java:196` |
| `Transfer.isClosed()` | `h2/src/main/org/h2/value/Transfer.java:1334` |
| `DataType.addPrecision()` | `h2/src/main/org/h2/value/DataType.java:791` |
| `DataType.areStableComparable()` | `h2/src/main/org/h2/value/DataType.java:592` |

## 6.4 阅读路径

读 `org.h2.value` 的 56 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.value` 的 package-info 与 `Value`，建立第6章的职责边界。
2. 再读 `Value` 的 67 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.result`（本章最小包，3,688 行）的实现，关注容量与失败路径。

跨章衔接请对照第7章《数据结构：值、行与页》。

## 6.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.value` | `org.h2`, `org.h2.util`, `org.h2.util.geometry`, `org.h2.engine` |
| `org.h2.result` | `org.h2`, `org.h2.mvstore`, `org.h2.command` |

## 6.6 设计权衡

`org.h2.value` 有 56 个文件、15,512 行。平均每文件 277 行。

其中 `Value` 独占 2,873 行，67 个公开方法。规模集中，风险也集中。

它对外声明 5 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.result`（3,688 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 6.7 常见误区

把 `org.h2.value` 的行数当作复杂度上限是误读。`Value` 之外还有 55 个文件，其中多为类型族与样板。

只读 `Value` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.value` 与 `org.h2.result` 不能互换。前者 56 个文件，后者 22 个文件，扩展点分布完全不同。

## 6.8 深读要点

规模信号：`org.h2.value` 占本章 81% 的实现行数，改动风险最高。
耦合信号：`org.h2.value` 依赖 5 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`Value` 的公开方法 67 个，读它等于读本章的主干。

## 6.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Value**：详见[术语表](back/glossary.md)对应条目。
- **Append-Only**：详见[术语表](back/glossary.md)对应条目。
- **AbstractAggregate**：详见[术语表](back/glossary.md)对应条目。
- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **B-Tree**：详见[术语表](back/glossary.md)对应条目。
- **Chunk**：详见[术语表](back/glossary.md)对应条目。
- **COW / Copy-on-Write**：详见[术语表](back/glossary.md)对应条目。

## 6.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `Value` | `org.h2.value` | 2,873 | 67 | 按方法名归纳 |
| `TypeInfo` | `org.h2.value` | 1,539 | 23 | 按方法名归纳 |
| `LocalResult` | `org.h2.result` | 710 | 42 | 按方法名归纳 |
| `UpdatableRow` | `org.h2.result` | 341 | 5 | 按方法名归纳 |

## 6.9 本章小结

- 本章覆盖 2 个包、19,200 行。
- 关键入口与源码坐标见 §6.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 6.10 延伸思考

**1. 🟢★ 说明 `Value` 与 `TypeInfo` 的分工差异。给出调用方向。**

> 提示：第6章 §6.2 的表格给出 `Value` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**2. 🔵★★ `LocalResult` 为什么独立成类型，而不是并入 `UpdatableRow`？**

> 提示：第6章 §6.2 的表格给出 `LocalResult` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**3. 🟠★★★ 以 `Value` 为入口，画出一次完整调用经过的包。**

> 提示：第6章 §6.2 的表格给出 `Value` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `LocalResult` 还是 `UpdatableRow`？说明代价。**

> 提示：第6章 §6.2 的表格给出 `LocalResult` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

## 6.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.value`：56 个文件、15,512 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.result`（3,688 行）：两者的扩展与兼容策略不同，差异落在 `Value` 的 67 个公开方法里。
- 若扩展与兼容假设被打破（5 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 6.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.value` | `org.h2` | 227 |
| `org.h2.value` | `org.h2.util` | 29 |
| `org.h2.value` | `org.h2.util.geometry` | 3 |
| `org.h2.result` | `org.h2` | 95 |
| `org.h2.result` | `org.h2.mvstore` | 2 |
| `org.h2.result` | `org.h2.command` | 1 |

## 6.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.value` 与 `org.h2.result` 的调用方向？`Value` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.value` 的调用链讲到落盘或返回，并说清 `org.h2.value` 与 `org.h2.result` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.value` 的注释与实现对不上，你信哪一边，为什么？

## 6.12 延展阅读

- 详见第7章《数据结构：值、行与页》。
