# 第3章 包结构与模块职责

> **本章导读**：本章由源码清单汇总而成，覆盖 13 个包、119,252 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 3.1 模块版图

本章覆盖 13 个包、119,252 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.value` | 55 | 15,501 | Data type and value implementations. |
| `org.h2.command` | 11 | 15,014 | This package contains the parser and the base classes for prepared SQL statements. |
| `org.h2.mvstore` | 20 | 14,505 | A persistent storage for tree maps. |
| `org.h2.util` | 48 | 14,460 | Internal utility classes. |
| `org.h2.table` | 31 | 13,388 | Classes related to a table and table meta data. |
| `org.h2.engine` | 28 | 11,839 | Contains high level classes of the database and classes that don't fit in another sub-package. |
| `org.h2.tools` | 23 | 10,868 | Various tools. |
| `org.h2.expression` | 35 | 5,832 | Expressions include mathematical operations, simple values, and others. |
| `org.h2.api` | 12 | 4,150 | Contains interfaces for user-defined extensions, such as triggers and user-defined aggregate functions. |
| `org.h2.index` | 23 | 4,093 | Various table index implementations, as well as cursors to navigate in an index. |
| `org.h2.result` | 21 | 3,677 | Implementation of row and internal result sets. |
| `org.h2.schema` | 11 | 3,213 | Schema implementation and objects that are stored in a schema (for example, sequences and constants). |
| `org.h2.store` | 17 | 2,712 | Storage abstractions and helper classes. |

## 3.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 3.2.1 `org.h2.value`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Value` | 2,873 | 67 | （无类注释，按方法名归纳） |
| `TypeInfo` | 1,539 | 23 | （无类注释，按方法名归纳） |
| `Transfer` | 1,368 | 31 | （无类注释，按方法名归纳） |
| `DataType` | 828 | 25 | （无类注释，按方法名归纳） |
| `ValueToObjectConverter` | 642 | 6 | （无类注释，按方法名归纳） |
| `ValueToObjectConverter2` | 433 | 2 | （无类注释，按方法名归纳） |

### 3.2.2 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |
| `CommandInterface` | 654 | 0 | （无类注释，按方法名归纳） |
| `Prepared` | 503 | 33 | （无类注释，按方法名归纳） |

### 3.2.3 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |
| `DataUtils` | 1,185 | 45 | （无类注释，按方法名归纳） |
| `RandomAccessStore` | 851 | 10 | （无类注释，按方法名归纳） |

### 3.2.4 `org.h2.util`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `StringUtils` | 1,415 | 55 | （无类注释，按方法名归纳） |
| `DateTimeUtils` | 1,171 | 42 | （无类注释，按方法名归纳） |
| `DateTimeTemplate` | 859 | 5 | （无类注释，按方法名归纳） |
| `IntervalUtils` | 857 | 12 | （无类注释，按方法名归纳） |
| `Utils` | 832 | 34 | （无类注释，按方法名归纳） |
| `JdbcUtils` | 785 | 17 | （无类注释，按方法名归纳） |

### 3.2.5 `org.h2.table`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `InformationSchemaTable` | 3,299 | 6 | （无类注释，按方法名归纳） |
| `InformationSchemaTableLegacy` | 2,324 | 2 | （无类注释，按方法名归纳） |
| `Table` | 1,446 | 98 | （无类注释，按方法名归纳） |
| `TableFilter` | 1,310 | 66 | （无类注释，按方法名归纳） |
| `Column` | 867 | 58 | （无类注释，按方法名归纳） |
| `TableLink` | 718 | 35 | （无类注释，按方法名归纳） |

### 3.2.6 `org.h2.engine`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Database` | 2,566 | 152 | （无类注释，按方法名归纳） |
| `SessionLocal` | 2,156 | 135 | （无类注释，按方法名归纳） |
| `SessionRemote` | 1,068 | 53 | （无类注释，按方法名归纳） |
| `Mode` | 776 | 5 | （无类注释，按方法名归纳） |
| `ConnectionInfo` | 766 | 25 | （无类注释，按方法名归纳） |
| `Constants` | 520 | 0 | （无类注释，按方法名归纳） |

### 3.2.7 `org.h2.tools`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `SimpleResultSet` | 2,480 | 228 | （无类注释，按方法名归纳） |
| `Csv` | 986 | 33 | （无类注释，按方法名归纳） |
| `Recover` | 922 | 18 | （无类注释，按方法名归纳） |
| `Server` | 823 | 19 | （无类注释，按方法名归纳） |
| `DirectRecover` | 767 | 11 | （无类注释，按方法名归纳） |
| `Shell` | 639 | 7 | （无类注释，按方法名归纳） |

### 3.2.8 `org.h2.expression`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ExpressionColumn` | 553 | 23 | （无类注释，按方法名归纳） |
| `Expression` | 551 | 41 | （无类注释，按方法名归纳） |
| `BinaryOperation` | 455 | 6 | （无类注释，按方法名归纳） |
| `ExpressionVisitor` | 417 | 17 | （无类注释，按方法名归纳） |
| `IntervalOperation` | 381 | 4 | （无类注释，按方法名归纳） |
| `SimpleCase` | 289 | 12 | （无类注释，按方法名归纳） |

### 3.2.9 `org.h2.api`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ErrorCode` | 2,367 | 2 | （无类注释，按方法名归纳） |
| `Interval` | 636 | 33 | （无类注释，按方法名归纳） |
| `IntervalQualifier` | 353 | 13 | （无类注释，按方法名归纳） |
| `H2Type` | 322 | 6 | （无类注释，按方法名归纳） |
| `DatabaseEventListener` | 113 | 0 | （无类注释，按方法名归纳） |
| `Trigger` | 105 | 0 | （无类注释，按方法名归纳） |

### 3.2.10 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |
| `RegularQueryExpressionIndex` | 223 | 4 | （无类注释，按方法名归纳） |
| `IndexType` | 222 | 16 | （无类注释，按方法名归纳） |

### 3.2.11 `org.h2.result`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `LocalResult` | 710 | 42 | （无类注释，按方法名归纳） |
| `UpdatableRow` | 341 | 5 | （无类注释，按方法名归纳） |
| `SortOrder` | 334 | 15 | （无类注释，按方法名归纳） |
| `SimpleResult` | 303 | 31 | （无类注释，按方法名归纳） |
| `ResultRemote` | 287 | 17 | （无类注释，按方法名归纳） |
| `RowFactory` | 201 | 17 | （无类注释，按方法名归纳） |

### 3.2.12 `org.h2.schema`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Schema` | 848 | 51 | （无类注释，按方法名归纳） |
| `Sequence` | 586 | 25 | （无类注释，按方法名归纳） |
| `FunctionAlias` | 562 | 22 | （无类注释，按方法名归纳） |
| `TriggerObject` | 543 | 28 | （无类注释，按方法名归纳） |
| `Domain` | 241 | 22 | （无类注释，按方法名归纳） |
| `UserAggregate` | 120 | 9 | （无类注释，按方法名归纳） |

### 3.2.13 `org.h2.store`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileLock` | 514 | 8 | （无类注释，按方法名归纳） |
| `FileStore` | 513 | 22 | （无类注释，按方法名归纳） |
| `Data` | 220 | 13 | （无类注释，按方法名归纳） |
| `RecoverTester` | 176 | 3 | （无类注释，按方法名归纳） |
| `FileStoreInputStream` | 155 | 5 | （无类注释，按方法名归纳） |
| `DataReader` | 133 | 5 | （无类注释，按方法名归纳） |

## 3.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `org/h2/value/Value.java:929` |
| `Value.castTo()` | `org/h2/value/Value.java:1105` |
| `TypeInfo.areSameTypes()` | `org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `org/h2/value/TypeInfo.java:764` |
| `Transfer.close()` | `org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `org/h2/value/Transfer.java:216` |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `org/h2/command/Parser.java:9446` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `org/h2/command/ParserBase.java:743` |
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

## 3.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第4章《包结构与模块职责》。

## 3.5 本章小结

- 本章覆盖 13 个包、119,252 行。
- 关键入口与源码坐标见 §3.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 3.6 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §3.1 的表格，按规模排序挑选目标包。
> 回顾：§3.1 模块版图

**2. 🔵★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §3.1 的表格，按规模排序挑选目标包。
> 回顾：§3.1 模块版图

**3. 🟠★★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §3.1 的表格，按规模排序挑选目标包。
> 回顾：§3.1 模块版图

**4. 🟢★★★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §3.1 的表格，按规模排序挑选目标包。
> 回顾：§3.1 模块版图

## 3.7 延展阅读

- 详见第4章《包结构与模块职责》。
