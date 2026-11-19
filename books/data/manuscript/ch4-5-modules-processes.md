# 第4章 模块边界与依赖治理

> **本章导读**：本章由源码清单汇总而成，覆盖 4 个包、44,070 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 4.1 模块版图

本章覆盖 2 个包、29,519 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.command` | 11 | 15,014 | This package contains the parser and the base classes for prepared SQL statements. |
| `org.h2.mvstore` | 20 | 14,505 | A persistent storage for tree maps. |

## 4.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 4.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |
| `CommandInterface` | 654 | 0 | （无类注释，按方法名归纳） |
| `Prepared` | 503 | 33 | （无类注释，按方法名归纳） |

### 4.2.2 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |
| `DataUtils` | 1,185 | 45 | （无类注释，按方法名归纳） |
| `RandomAccessStore` | 851 | 10 | （无类注释，按方法名归纳） |

## 4.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
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

## 4.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第5章《进程内数据流》。

## 4.5 本章小结

- 本章覆盖 2 个包、29,519 行。
- 关键入口与源码坐标见 §4.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 4.6 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §4.1 的表格，按规模排序挑选目标包。
> 回顾：§4.1 模块版图

**2. 🔵★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §4.1 的表格，按规模排序挑选目标包。
> 回顾：§4.1 模块版图

**3. 🟠★★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §4.1 的表格，按规模排序挑选目标包。
> 回顾：§4.1 模块版图

**4. 🟢★★★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §4.1 的表格，按规模排序挑选目标包。
> 回顾：§4.1 模块版图

## 4.7 延展阅读

- 详见第5章《进程内数据流》。

# 第5章 进程内数据流

## 5.1 模块版图

本章覆盖 2 个包、14,551 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.engine` | 28 | 11,839 | Contains high level classes of the database and classes that don't fit in another sub-package. |
| `org.h2.store` | 17 | 2,712 | Storage abstractions and helper classes. |

## 5.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 5.2.1 `org.h2.engine`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Database` | 2,566 | 152 | （无类注释，按方法名归纳） |
| `SessionLocal` | 2,156 | 135 | （无类注释，按方法名归纳） |
| `SessionRemote` | 1,068 | 53 | （无类注释，按方法名归纳） |
| `Mode` | 776 | 5 | （无类注释，按方法名归纳） |
| `ConnectionInfo` | 766 | 25 | （无类注释，按方法名归纳） |
| `Constants` | 520 | 0 | （无类注释，按方法名归纳） |

### 5.2.2 `org.h2.store`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileLock` | 514 | 8 | （无类注释，按方法名归纳） |
| `FileStore` | 513 | 22 | （无类注释，按方法名归纳） |
| `Data` | 220 | 13 | （无类注释，按方法名归纳） |
| `RecoverTester` | 176 | 3 | （无类注释，按方法名归纳） |
| `FileStoreInputStream` | 155 | 5 | （无类注释，按方法名归纳） |
| `DataReader` | 133 | 5 | （无类注释，按方法名归纳） |

## 5.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Database.addDatabaseObject()` | `org/h2/engine/Database.java:948` |
| `Database.addSchemaObject()` | `org/h2/engine/Database.java:923` |
| `SessionLocal.addLocalTempTable()` | `org/h2/engine/SessionLocal.java:397` |
| `SessionLocal.addLocalTempTableConstraint()` | `org/h2/engine/SessionLocal.java:510` |
| `SessionRemote.addTemporaryLob()` | `org/h2/engine/SessionRemote.java:819` |
| `SessionRemote.autoCommitIfCluster()` | `org/h2/engine/SessionRemote.java:296` |
| `FileLock.getFileLockMethod()` | `org/h2/store/FileLock.java:458` |
| `FileLock.getUniqueId()` | `org/h2/store/FileLock.java:472` |
| `FileStore.autoDelete()` | `org/h2/store/FileStore.java:429` |
| `FileStore.close()` | `org/h2/store/FileStore.java:221` |
| `Data.checkCapacity()` | `org/h2/store/Data.java:171` |
| `Data.copyString()` | `org/h2/store/Data.java:204` |

## 5.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第4章《模块边界与依赖治理》。

## 5.5 本章小结

- 本章覆盖 2 个包、14,551 行。
- 关键入口与源码坐标见 §5.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 5.6 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §5.1 的表格，按规模排序挑选目标包。
> 回顾：§5.1 模块版图

**2. 🔵★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §5.1 的表格，按规模排序挑选目标包。
> 回顾：§5.1 模块版图

**3. 🟠★★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §5.1 的表格，按规模排序挑选目标包。
> 回顾：§5.1 模块版图

**4. 🟢★★★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §5.1 的表格，按规模排序挑选目标包。
> 回顾：§5.1 模块版图

## 5.7 延展阅读

- 详见第4章《模块边界与依赖治理》。
