# 第6章 数据结构：值、行与页

> **本章导读**：本章由源码清单汇总而成，覆盖 4 个包、48,143 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 6.1 模块版图

本章覆盖 4 个包、48,143 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.value` | 55 | 15,501 | Data type and value implementations. |
| `org.h2.mvstore` | 20 | 14,505 | A persistent storage for tree maps. |
| `org.h2.util` | 48 | 14,460 | Internal utility classes. |
| `org.h2.result` | 21 | 3,677 | Implementation of row and internal result sets. |

## 6.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 6.2.1 `org.h2.value`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Value` | 2,873 | 67 | （无类注释，按方法名归纳） |
| `TypeInfo` | 1,539 | 23 | （无类注释，按方法名归纳） |
| `Transfer` | 1,368 | 31 | （无类注释，按方法名归纳） |
| `DataType` | 828 | 25 | （无类注释，按方法名归纳） |
| `ValueToObjectConverter` | 642 | 6 | （无类注释，按方法名归纳） |
| `ValueToObjectConverter2` | 433 | 2 | （无类注释，按方法名归纳） |

### 6.2.2 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |
| `DataUtils` | 1,185 | 45 | （无类注释，按方法名归纳） |
| `RandomAccessStore` | 851 | 10 | （无类注释，按方法名归纳） |

### 6.2.3 `org.h2.util`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `StringUtils` | 1,415 | 55 | （无类注释，按方法名归纳） |
| `DateTimeUtils` | 1,171 | 42 | （无类注释，按方法名归纳） |
| `DateTimeTemplate` | 859 | 5 | （无类注释，按方法名归纳） |
| `IntervalUtils` | 857 | 12 | （无类注释，按方法名归纳） |
| `Utils` | 832 | 34 | （无类注释，按方法名归纳） |
| `JdbcUtils` | 785 | 17 | （无类注释，按方法名归纳） |

### 6.2.4 `org.h2.result`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `LocalResult` | 710 | 42 | （无类注释，按方法名归纳） |
| `UpdatableRow` | 341 | 5 | （无类注释，按方法名归纳） |
| `SortOrder` | 334 | 15 | （无类注释，按方法名归纳） |
| `SimpleResult` | 303 | 31 | （无类注释，按方法名归纳） |
| `ResultRemote` | 287 | 17 | （无类注释，按方法名归纳） |
| `RowFactory` | 201 | 17 | （无类注释，按方法名归纳） |

## 6.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `org/h2/value/Value.java:929` |
| `Value.castTo()` | `org/h2/value/Value.java:1105` |
| `TypeInfo.areSameTypes()` | `org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `org/h2/value/TypeInfo.java:764` |
| `Transfer.close()` | `org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `org/h2/value/Transfer.java:216` |
| `FileStore.accountForRemovedPage()` | `org/h2/mvstore/FileStore.java:2178` |
| `FileStore.backup()` | `org/h2/mvstore/FileStore.java:1432` |
| `MVStore.adoptFileStore()` | `org/h2/mvstore/MVStore.java:2183` |
| `MVStore.autoCommitBufferSize()` | `org/h2/mvstore/MVStore.java:2003` |
| `MVMap.append()` | `org/h2/mvstore/MVMap.java:1364` |
| `MVMap.ceilingKey()` | `org/h2/mvstore/MVMap.java:325` |
| `StringUtils.addAsterisk()` | `org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `org/h2/util/StringUtils.java:1277` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `org/h2/util/DateTimeUtils.java:857` |
| `DateTimeTemplate.format()` | `org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `org/h2/util/DateTimeTemplate.java:430` |
| `LocalResult.addRow()` | `org/h2/result/LocalResult.java:420` |
| `LocalResult.addRowForTable()` | `org/h2/result/LocalResult.java:404` |

## 6.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第7章《数据结构：值、行与页》。

## 6.5 本章小结

- 本章覆盖 4 个包、48,143 行。
- 关键入口与源码坐标见 §6.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 6.6 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §6.1 的表格，按规模排序挑选目标包。
> 回顾：§6.1 模块版图

**2. 🔵★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §6.1 的表格，按规模排序挑选目标包。
> 回顾：§6.1 模块版图

**3. 🟠★★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §6.1 的表格，按规模排序挑选目标包。
> 回顾：§6.1 模块版图

**4. 🟢★★★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §6.1 的表格，按规模排序挑选目标包。
> 回顾：§6.1 模块版图

## 6.7 延展阅读

- 详见第7章《数据结构：值、行与页》。
