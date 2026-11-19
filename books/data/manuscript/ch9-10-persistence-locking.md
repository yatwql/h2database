# 第11章 持久化

> **本章导读**：本章由源码清单汇总而成，覆盖 4 个包、43,516 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 11.1 模块版图

本章覆盖 2 个包、28,965 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.mvstore` | 20 | 14,505 | A persistent storage for tree maps. |
| `org.h2.util` | 48 | 14,460 | Internal utility classes. |

## 11.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 11.2.1 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |

### 11.2.2 `org.h2.util`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `StringUtils` | 1,415 | 55 | （无类注释，按方法名归纳） |
| `DateTimeUtils` | 1,171 | 42 | （无类注释，按方法名归纳） |
| `DateTimeTemplate` | 859 | 5 | （无类注释，按方法名归纳） |
| `IntervalUtils` | 857 | 12 | （无类注释，按方法名归纳） |

## 11.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
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

## 11.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第12章《并发控制》。

## 11.5 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **MVStore**：详见[术语表](back/glossary.md)对应条目。

## 11.6 本章小结

- 本章覆盖 2 个包、28,965 行。
- 关键入口与源码坐标见 §11.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 11.7 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §11.1 的表格，按规模排序挑选目标包。
> 回顾：§11.1 模块版图

**2. 🔵★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §11.1 的表格，按规模排序挑选目标包。
> 回顾：§11.1 模块版图

**3. 🟠★★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §11.1 的表格，按规模排序挑选目标包。
> 回顾：§11.1 模块版图

**4. 🟢★★★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §11.1 的表格，按规模排序挑选目标包。
> 回顾：§11.1 模块版图

## 11.8 延展阅读

- 详见第12章《并发控制》。

# 第12章 并发控制

## 12.1 模块版图

本章覆盖 2 个包、14,551 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.engine` | 28 | 11,839 | Contains high level classes of the database and classes that don't fit in another sub-package. |
| `org.h2.store` | 17 | 2,712 | Storage abstractions and helper classes. |

## 12.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 12.2.1 `org.h2.engine`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Database` | 2,566 | 152 | （无类注释，按方法名归纳） |
| `SessionLocal` | 2,156 | 135 | （无类注释，按方法名归纳） |
| `SessionRemote` | 1,068 | 53 | （无类注释，按方法名归纳） |
| `Mode` | 776 | 5 | （无类注释，按方法名归纳） |

### 12.2.2 `org.h2.store`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileLock` | 514 | 8 | （无类注释，按方法名归纳） |
| `FileStore` | 513 | 22 | （无类注释，按方法名归纳） |
| `Data` | 220 | 13 | （无类注释，按方法名归纳） |
| `RecoverTester` | 176 | 3 | （无类注释，按方法名归纳） |

## 12.3 关键 API 与源码坐标

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

## 12.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第11章《持久化》。

## 12.5 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Database**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。

## 12.6 本章小结

- 本章覆盖 2 个包、14,551 行。
- 关键入口与源码坐标见 §12.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 12.7 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §12.1 的表格，按规模排序挑选目标包。
> 回顾：§12.1 模块版图

**2. 🔵★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §12.1 的表格，按规模排序挑选目标包。
> 回顾：§12.1 模块版图

**3. 🟠★★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §12.1 的表格，按规模排序挑选目标包。
> 回顾：§12.1 模块版图

**4. 🟢★★★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §12.1 的表格，按规模排序挑选目标包。
> 回顾：§12.1 模块版图

## 12.8 延展阅读

- 详见第11章《持久化》。
