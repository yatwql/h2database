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

在 `org.h2.jdbc` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

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

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

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

## 1.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `JdbcResultSet` | `org.h2.jdbc` | 4,291 | 199 |
| `JdbcDatabaseMetaData` | `org.h2.jdbc` | 2,756 | 177 |
| `JdbcConnection` | `org.h2.jdbc` | 1,930 | 62 |
| `JdbcCallableStatement` | `org.h2.jdbc` | 1,863 | 117 |
| `JdbcPreparedStatement` | `org.h2.jdbc` | 1,629 | 65 |
| `Database` | `org.h2.engine` | 2,566 | 152 |
| `SessionLocal` | `org.h2.engine` | 2,156 | 135 |
| `SessionRemote` | `org.h2.engine` | 1,068 | 53 |
| `Mode` | `org.h2.engine` | 776 | 5 |
| `ConnectionInfo` | `org.h2.engine` | 766 | 25 |

## 1.4 阅读路径

读 `org.h2.jdbc` 的 27 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.jdbc` 的 package-info 与 `JdbcResultSet`，建立第1章的职责边界。
2. 再读 `JdbcResultSet` 的 199 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.engine`（本章最小包，11,839 行）的实现，关注容量与失败路径。

跨章衔接请对照第2章《分层模块划分》。

## 1.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.jdbc` | `org.h2.value`, `org.h2.message`, `org.h2.util`, `org.h2.engine` |
| `org.h2.engine` | `org.h2.util`, `org.h2.message`, `org.h2.value`, `org.h2.api` |

## 1.6 设计权衡

- `org.h2.jdbc` 用 27 个文件换到 17,319 行实现，平均每文件 641 行，其中 `JdbcResultSet` 独占 4,291 行、199 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.engine`（11,839 行）与 `org.h2.jdbc` 的职责差是本章最值得记的一条边界。

## 1.7 常见误区

- 把 `org.h2.jdbc` 的 17,319 行当作复杂度上限：`JdbcResultSet` 之外的 26 个文件多为类型族与样板。
- 只看 `JdbcResultSet` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.jdbc` 与 `org.h2.engine` 视为可互换：前者 27 文件、后者 28 文件，扩展点分布完全不同。

## 1.8 深读要点

规模信号：`org.h2.jdbc` 占本章 59% 的实现行数，改动风险最高。
耦合信号：`org.h2.jdbc` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`JdbcResultSet` 的公开方法 199 个，读它等于读本章的主干。

## 1.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Database**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。

## 1.9 知识点清单

1. `org.h2.jdbc` 的 `JdbcResultSet`：4,291 行、199 个公开方法，职责按方法名归纳
2. `org.h2.jdbc` 的 `JdbcDatabaseMetaData`：2,756 行、177 个公开方法，职责按方法名归纳
3. `org.h2.engine` 的 `Database`：2,566 行、152 个公开方法，职责按方法名归纳
4. `org.h2.engine` 的 `SessionLocal`：2,156 行、135 个公开方法，职责按方法名归纳

## 1.9 本章小结

- 本章覆盖 2 个包、29,158 行。
- 关键入口与源码坐标见 §1.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 1.10 延伸思考

**1. 🟢★ 指出 `org.h2.jdbc` 中 `JdbcResultSet` 与 `JdbcDatabaseMetaData` 的分工差异，并给出调用方向。**

> 提示：第1章 §1.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**2. 🔵★★ 围绕 `org.h2.engine` 的 `Database`，说明它为什么需要独立成类型而不是并入 `SessionLocal`。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**3. 🟠★★★ 以 `org.h2.jdbc` 的 `JdbcResultSet` 为入口，画出一次完整调用经过的包。**

> 提示：第1章 §1.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.engine` 的一个类型，你保留 `Database` 还是 `SessionLocal`？说明代价。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

## 1.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.jdbc`：27 个文件、17,319 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.engine`（11,839 行）：两者的并发与一致性策略不同，差异落在 `JdbcResultSet` 的 199 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 1.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.jdbc` | `org.h2.value` | 57 |
| `org.h2.jdbc` | `org.h2.message` | 43 |
| `org.h2.jdbc` | `org.h2.util` | 19 |
| `org.h2.engine` | `org.h2.util` | 55 |
| `org.h2.engine` | `org.h2.message` | 33 |
| `org.h2.engine` | `org.h2.value` | 26 |

## 1.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.jdbc` 与 `org.h2.engine` 之间的调用方向？
- `JdbcResultSet` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.jdbc` 的调用链讲到落盘或返回？
- `org.h2.jdbc` 与 `org.h2.engine` 若合并，会丢掉哪个扩展点？
- `org.h2.jdbc` 的注释与实现若不一致，你信哪一边，为什么？

## 1.12 延展阅读

- 详见第2章《分层模块划分》。

# 第2章 分层模块划分

## 2.1 模块版图

本章覆盖 2 个包、4,355 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.api` | 12 | 4,150 | Contains interfaces for user-defined extensions, such as triggers and user-defined aggregate functions. |
| `org.h2` | 1 | 205 | Implementation of the JDBC driver. |

## 2.2 核心类型

在 `org.h2.api` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

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

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

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

## 2.3.1 公共类型清单

本章抽样类型按包分组，共 6 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `ErrorCode` | `org.h2.api` | 2,367 | 2 |
| `Interval` | `org.h2.api` | 636 | 33 |
| `IntervalQualifier` | `org.h2.api` | 353 | 13 |
| `H2Type` | `org.h2.api` | 322 | 6 |
| `DatabaseEventListener` | `org.h2.api` | 113 | 0 |
| `Driver` | `org.h2` | 205 | 11 |

## 2.4 阅读路径

读 `org.h2.api` 的 12 个文件时，先看骨架类，再沿 `org.h2.security.auth` 方向下钻。

1. 先读 `org.h2.api` 的 package-info 与 `ErrorCode`，建立第2章的职责边界。
2. 再读 `ErrorCode` 的 2 个公开入口，确认它对 `org.h2.security.auth` 的调用方向与加锁方式。
3. 最后读 `org.h2`（本章最小包，205 行）的实现，关注容量与失败路径。

跨章衔接请对照第1章《H2 总体架构》。

## 2.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.api` | `org.h2.security.auth`, `org.h2.value`, `org.h2.util.DateTimeUtils`, `org.h2.message` |

## 2.6 设计权衡

- `org.h2.api` 用 12 个文件换到 4,150 行实现，平均每文件 345 行，其中 `ErrorCode` 独占 2,367 行、2 个公开方法。
- 该包对外声明了 7 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2`（205 行）与 `org.h2.api` 的职责差是本章最值得记的一条边界。

## 2.7 常见误区

- 把 `org.h2.api` 的 4,150 行当作复杂度上限：`ErrorCode` 之外的 11 个文件多为类型族与样板。
- 只看 `ErrorCode` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.api` 与 `org.h2` 视为可互换：前者 12 文件、后者 1 文件，扩展点分布完全不同。

## 2.8 深读要点

规模信号：`org.h2.api` 占本章 95% 的实现行数，改动风险最高。
耦合信号：`org.h2.api` 依赖 7 个 `org.h2` 包，其中 `org.h2.security.auth` 出现最频繁。
入口信号：`ErrorCode` 的公开方法 2 个，读它等于读本章的主干。

## 2.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **Driver**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。

## 2.9 知识点清单

1. `org.h2.api` 的 `ErrorCode`：2,367 行、2 个公开方法，职责按方法名归纳
2. `org.h2.api` 的 `Interval`：636 行、33 个公开方法，职责按方法名归纳
3. `org.h2` 的 `Driver`：205 行、11 个公开方法，职责按方法名归纳

## 2.9 本章小结

- 本章覆盖 2 个包、4,355 行。
- 关键入口与源码坐标见 §2.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 2.10 延伸思考

**1. 🟢★ 指出 `org.h2.api` 中 `ErrorCode` 与 `Interval` 的分工差异，并给出调用方向。**

> 提示：第2章 §2.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**2. 🔵★★ 围绕 `org.h2` 的 `Driver`，说明它为什么需要独立成类型而不是并入 `相邻工具类型`。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**3. 🟠★★★ 以 `org.h2.api` 的 `ErrorCode` 为入口，画出一次完整调用经过的包。**

> 提示：第2章 §2.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2` 的一个类型，你保留 `Driver` 还是 `相邻工具类型`？说明代价。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

## 2.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.api`：12 个文件、4,150 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2`（205 行）：两者的扩展与兼容策略不同，差异落在 `ErrorCode` 的 2 个公开方法里。
- 若扩展与兼容假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2.security.auth` 进入。

## 2.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.api` | `org.h2.security.auth` | 5 |
| `org.h2.api` | `org.h2.value` | 3 |
| `org.h2.api` | `org.h2.util.DateTimeUtils` | 2 |

## 2.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.api` 与 `org.h2` 之间的调用方向？
- `ErrorCode` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.api` 的调用链讲到落盘或返回？
- `org.h2.api` 与 `org.h2` 若合并，会丢掉哪个扩展点？
- `org.h2.api` 的注释与实现若不一致，你信哪一边，为什么？

## 2.12 延展阅读

- 详见第1章《H2 总体架构》。
