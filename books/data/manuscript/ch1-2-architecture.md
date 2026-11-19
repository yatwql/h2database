# 第1章 H2 总体架构

> **本章导读**：本章由源码清单汇总而成，覆盖 4 个包、33,513 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 1.1 模块版图

本章覆盖 2 个包、29,158 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.jdbc` | 27 | 17,319 | Implementation of the JDBC API (package { |
| `org.h2.engine` | 28 | 11,839 | Contains high level classes of the database and classes that don't fit in another sub-package. |

## 1.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 1.2.1 `org.h2.jdbc`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `JdbcResultSet` | 4,291 | 199 | （无类注释，按方法名归纳） |
| `JdbcDatabaseMetaData` | 2,756 | 177 | （无类注释，按方法名归纳） |
| `JdbcConnection` | 1,930 | 62 | （无类注释，按方法名归纳） |
| `JdbcCallableStatement` | 1,863 | 117 | （无类注释，按方法名归纳） |

### 1.2.2 `org.h2.engine`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Database` | 2,566 | 152 | （无类注释，按方法名归纳） |
| `SessionLocal` | 2,156 | 135 | （无类注释，按方法名归纳） |
| `SessionRemote` | 1,068 | 53 | （无类注释，按方法名归纳） |
| `Mode` | 776 | 5 | （无类注释，按方法名归纳） |

## 1.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `JdbcResultSet.absolute()` | `org/h2/jdbc/JdbcResultSet.java:3173` |
| `JdbcResultSet.afterLast()` | `org/h2/jdbc/JdbcResultSet.java:3105` |
| `JdbcDatabaseMetaData.allProceduresAreCallable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:305` |
| `JdbcDatabaseMetaData.allTablesAreSelectable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:316` |
| `JdbcConnection.abort()` | `org/h2/jdbc/JdbcConnection.java:1832` |
| `JdbcConnection.clearWarnings()` | `org/h2/jdbc/JdbcConnection.java:655` |
| `Database.addDatabaseObject()` | `org/h2/engine/Database.java:948` |
| `Database.addSchemaObject()` | `org/h2/engine/Database.java:923` |
| `SessionLocal.addLocalTempTable()` | `org/h2/engine/SessionLocal.java:397` |
| `SessionLocal.addLocalTempTableConstraint()` | `org/h2/engine/SessionLocal.java:510` |
| `SessionRemote.addTemporaryLob()` | `org/h2/engine/SessionRemote.java:819` |
| `SessionRemote.autoCommitIfCluster()` | `org/h2/engine/SessionRemote.java:296` |

## 1.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第2章《分层模块划分》。

## 1.5 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Database**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。

## 1.6 本章小结

- 本章覆盖 2 个包、29,158 行。
- 关键入口与源码坐标见 §1.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 1.7 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §1.1 的表格，按规模排序挑选目标包。
> 回顾：§1.1 模块版图

**2. 🔵★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §1.1 的表格，按规模排序挑选目标包。
> 回顾：§1.1 模块版图

**3. 🟠★★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §1.1 的表格，按规模排序挑选目标包。
> 回顾：§1.1 模块版图

**4. 🟢★★★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §1.1 的表格，按规模排序挑选目标包。
> 回顾：§1.1 模块版图

## 1.8 延展阅读

- 详见第2章《分层模块划分》。

# 第2章 分层模块划分

## 2.1 模块版图

本章覆盖 2 个包、4,355 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.api` | 12 | 4,150 | Contains interfaces for user-defined extensions, such as triggers and user-defined aggregate functions. |
| `org.h2` | 1 | 205 | Implementation of the JDBC driver. |

## 2.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 2.2.1 `org.h2.api`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ErrorCode` | 2,367 | 2 | （无类注释，按方法名归纳） |
| `Interval` | 636 | 33 | （无类注释，按方法名归纳） |
| `IntervalQualifier` | 353 | 13 | （无类注释，按方法名归纳） |
| `H2Type` | 322 | 6 | （无类注释，按方法名归纳） |

### 2.2.2 `org.h2`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Driver` | 205 | 11 | （无类注释，按方法名归纳） |

## 2.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `ErrorCode.isCommon()` | `org/h2/api/ErrorCode.java:2287` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `Interval.getDays()` | `org/h2/api/Interval.java:543` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `IntervalQualifier.hasDays()` | `org/h2/api/IntervalQualifier.java:165` |
| `Driver.acceptsURL()` | `org/h2/Driver.java:76` |
| `Driver.connect()` | `org/h2/Driver.java:55` |

## 2.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第1章《H2 总体架构》。

## 2.5 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **Driver**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。

## 2.6 本章小结

- 本章覆盖 2 个包、4,355 行。
- 关键入口与源码坐标见 §2.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 2.7 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §2.1 的表格，按规模排序挑选目标包。
> 回顾：§2.1 模块版图

**2. 🔵★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §2.1 的表格，按规模排序挑选目标包。
> 回顾：§2.1 模块版图

**3. 🟠★★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §2.1 的表格，按规模排序挑选目标包。
> 回顾：§2.1 模块版图

**4. 🟢★★★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §2.1 的表格，按规模排序挑选目标包。
> 回顾：§2.1 模块版图

## 2.8 延展阅读

- 详见第1章《H2 总体架构》。
