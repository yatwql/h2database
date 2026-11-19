# 第13章 二次开发指南

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、28,187 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 13.1 模块版图

本章覆盖 1 个包、17,319 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.jdbc` | 27 | 17,319 | Implementation of the JDBC API (package { |

## 13.2 核心类型

在 `org.h2.jdbc` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 13.2.1 `org.h2.jdbc`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `JdbcResultSet` | 4,291 | 199 | （无类注释，按方法名归纳） |
| `JdbcDatabaseMetaData` | 2,756 | 177 | （无类注释，按方法名归纳） |
| `JdbcConnection` | 1,930 | 62 | （无类注释，按方法名归纳） |
| `JdbcCallableStatement` | 1,863 | 117 | （无类注释，按方法名归纳） |

## 13.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `JdbcResultSet.absolute()` | `org/h2/jdbc/JdbcResultSet.java:3173` |
| `JdbcResultSet.afterLast()` | `org/h2/jdbc/JdbcResultSet.java:3105` |
| `JdbcDatabaseMetaData.allProceduresAreCallable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:305` |
| `JdbcDatabaseMetaData.allTablesAreSelectable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:316` |
| `JdbcConnection.abort()` | `org/h2/jdbc/JdbcConnection.java:1832` |
| `JdbcConnection.clearWarnings()` | `org/h2/jdbc/JdbcConnection.java:655` |

## 13.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `JdbcResultSet` | `org.h2.jdbc` | 4,291 | 199 |
| `JdbcDatabaseMetaData` | `org.h2.jdbc` | 2,756 | 177 |
| `JdbcConnection` | `org.h2.jdbc` | 1,930 | 62 |
| `JdbcCallableStatement` | `org.h2.jdbc` | 1,863 | 117 |
| `JdbcPreparedStatement` | `org.h2.jdbc` | 1,629 | 65 |

## 13.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

**`JdbcResultSet`**（`org.h2.jdbc`，4,291 行，199 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 25%，包级依赖 8 个。

**`JdbcDatabaseMetaData`**（`org.h2.jdbc`，2,756 行，177 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 16%，包级依赖 8 个。

**`JdbcConnection`**（`org.h2.jdbc`，1,930 行，62 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 11%，包级依赖 8 个。

**`JdbcCallableStatement`**（`org.h2.jdbc`，1,863 行，117 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 11%，包级依赖 8 个。

**`JdbcPreparedStatement`**（`org.h2.jdbc`，1,629 行，65 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

**`JdbcStatement`**（`org.h2.jdbc`，1,502 行，56 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

## 13.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `JdbcResultSet.absolute()` | `org/h2/jdbc/JdbcResultSet.java:3173` |
| `JdbcResultSet.afterLast()` | `org/h2/jdbc/JdbcResultSet.java:3105` |
| `JdbcResultSet.beforeFirst()` | `org/h2/jdbc/JdbcResultSet.java:3086` |
| `JdbcResultSet.cancelRowUpdates()` | `org/h2/jdbc/JdbcResultSet.java:3432` |
| `JdbcDatabaseMetaData.allProceduresAreCallable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:305` |
| `JdbcDatabaseMetaData.allTablesAreSelectable()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:316` |
| `JdbcDatabaseMetaData.autoCommitFailureClosesAllResultSets()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:2598` |
| `JdbcDatabaseMetaData.dataDefinitionCausesTransactionCommit()` | `org/h2/jdbc/JdbcDatabaseMetaData.java:1814` |
| `JdbcConnection.abort()` | `org/h2/jdbc/JdbcConnection.java:1832` |
| `JdbcConnection.clearWarnings()` | `org/h2/jdbc/JdbcConnection.java:655` |
| `JdbcConnection.close()` | `org/h2/jdbc/JdbcConnection.java:355` |
| `JdbcConnection.commit()` | `org/h2/jdbc/JdbcConnection.java:480` |
| `JdbcCallableStatement.executeLargeUpdate()` | `org/h2/jdbc/JdbcCallableStatement.java:119` |
| `JdbcCallableStatement.executeUpdate()` | `org/h2/jdbc/JdbcCallableStatement.java:89` |
| `JdbcCallableStatement.getArray()` | `org/h2/jdbc/JdbcCallableStatement.java:512` |
| `JdbcCallableStatement.getBigDecimal()` | `org/h2/jdbc/JdbcCallableStatement.java:351` |
| `JdbcPreparedStatement.addBatch()` | `org/h2/jdbc/JdbcPreparedStatement.java:326` |
| `JdbcPreparedStatement.clearBatch()` | `org/h2/jdbc/JdbcPreparedStatement.java:1222` |
| `JdbcPreparedStatement.clearParameters()` | `org/h2/jdbc/JdbcPreparedStatement.java:289` |
| `JdbcPreparedStatement.close()` | `org/h2/jdbc/JdbcPreparedStatement.java:1238` |

## 13.4 阅读路径

读 `org.h2.jdbc` 的 27 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.jdbc` 的 package-info 与 `JdbcResultSet`，建立第13章的职责边界。
2. 再读 `JdbcResultSet` 的 199 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.jdbc`（本章最小包，17,319 行）的实现，关注容量与失败路径。

跨章衔接请对照第14章《全书总结》。

## 13.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.jdbc` | `org.h2.value`, `org.h2.message`, `org.h2.util`, `org.h2.engine` |

## 13.6 设计权衡

- `org.h2.jdbc` 用 27 个文件换到 17,319 行实现，平均每文件 641 行，其中 `JdbcResultSet` 独占 4,291 行、199 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.jdbc`（17,319 行）与 `org.h2.jdbc` 的职责差是本章最值得记的一条边界。

## 13.7 常见误区

- 把 `org.h2.jdbc` 的 17,319 行当作复杂度上限：`JdbcResultSet` 之外的 26 个文件多为类型族与样板。
- 只看 `JdbcResultSet` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.jdbc` 与 `org.h2.jdbc` 视为可互换：前者 27 文件、后者 27 文件，扩展点分布完全不同。

## 13.8 深读要点

规模信号：`org.h2.jdbc` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.jdbc` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`JdbcResultSet` 的公开方法 199 个，读它等于读本章的主干。

## 13.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。

## 13.9 知识点清单

1. `org.h2.jdbc` 的 `JdbcResultSet`：4,291 行、199 个公开方法，职责按方法名归纳
2. `org.h2.jdbc` 的 `JdbcDatabaseMetaData`：2,756 行、177 个公开方法，职责按方法名归纳

## 13.9 本章小结

- 本章覆盖 1 个包、17,319 行。
- 关键入口与源码坐标见 §13.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 13.10 延伸思考

**1. 🟢★ 指出 `org.h2.jdbc` 中 `JdbcResultSet` 与 `JdbcDatabaseMetaData` 的分工差异，并给出调用方向。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**2. 🔵★★ 围绕 `org.h2.jdbc` 的 `JdbcResultSet`，说明它为什么需要独立成类型而不是并入 `JdbcDatabaseMetaData`。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**3. 🟠★★★ 以 `org.h2.jdbc` 的 `JdbcResultSet` 为入口，画出一次完整调用经过的包。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.jdbc` 的一个类型，你保留 `JdbcResultSet` 还是 `JdbcDatabaseMetaData`？说明代价。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

## 13.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.jdbc`：27 个文件、17,319 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.jdbc`（17,319 行）：两者的并发与一致性策略不同，差异落在 `JdbcResultSet` 的 199 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 13.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.jdbc` | `org.h2.value` | 57 |
| `org.h2.jdbc` | `org.h2.message` | 43 |
| `org.h2.jdbc` | `org.h2.util` | 19 |

## 13.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.jdbc` 与 `org.h2.jdbc` 之间的调用方向？
- `JdbcResultSet` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.jdbc` 的调用链讲到落盘或返回？
- `org.h2.jdbc` 与 `org.h2.jdbc` 若合并，会丢掉哪个扩展点？
- `org.h2.jdbc` 的注释与实现若不一致，你信哪一边，为什么？

## 13.12 延展阅读

- 详见第14章《全书总结》。

# 第14章 全书总结

## 14.1 模块版图

本章覆盖 1 个包、10,868 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.tools` | 23 | 10,868 | Various tools. |

## 14.2 核心类型

在 `org.h2.tools` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 14.2.1 `org.h2.tools`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `SimpleResultSet` | 2,480 | 228 | （无类注释，按方法名归纳） |
| `Csv` | 986 | 33 | （无类注释，按方法名归纳） |
| `Recover` | 922 | 18 | （无类注释，按方法名归纳） |
| `Server` | 823 | 19 | （无类注释，按方法名归纳） |

## 14.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `SimpleResultSet.absolute()` | `org/h2/tools/SimpleResultSet.java:2229` |
| `SimpleResultSet.addColumn()` | `org/h2/tools/SimpleResultSet.java:100` |
| `Csv.close()` | `org/h2/tools/Csv.java:639` |
| `Csv.getBinaryColumns()` | `org/h2/tools/Csv.java:909` |
| `Recover.checkPowerOff()` | `org/h2/tools/Recover.java:857` |
| `Recover.checkWritingAllowed()` | `org/h2/tools/Recover.java:865` |

## 14.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `SimpleResultSet` | `org.h2.tools` | 2,480 | 228 |
| `Csv` | `org.h2.tools` | 986 | 33 |
| `Recover` | `org.h2.tools` | 922 | 18 |
| `Server` | `org.h2.tools` | 823 | 19 |
| `DirectRecover` | `org.h2.tools` | 767 | 11 |

## 14.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

**`SimpleResultSet`**（`org.h2.tools`，2,480 行，228 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 23%，包级依赖 8 个。

**`Csv`**（`org.h2.tools`，986 行，33 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

**`Recover`**（`org.h2.tools`，922 行，18 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

**`Server`**（`org.h2.tools`，823 行，19 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

**`DirectRecover`**（`org.h2.tools`，767 行，11 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 8 个。

**`Shell`**（`org.h2.tools`，639 行，7 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

## 14.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `SimpleResultSet.absolute()` | `org/h2/tools/SimpleResultSet.java:2229` |
| `SimpleResultSet.addColumn()` | `org/h2/tools/SimpleResultSet.java:100` |
| `SimpleResultSet.addRow()` | `org/h2/tools/SimpleResultSet.java:133` |
| `SimpleResultSet.afterLast()` | `org/h2/tools/SimpleResultSet.java:2069` |
| `Csv.close()` | `org/h2/tools/Csv.java:639` |
| `Csv.getBinaryColumns()` | `org/h2/tools/Csv.java:909` |
| `Csv.getCaseSensitiveColumnNames()` | `org/h2/tools/Csv.java:687` |
| `Csv.getEscapeCharacter()` | `org/h2/tools/Csv.java:782` |
| `Recover.checkPowerOff()` | `org/h2/tools/Recover.java:857` |
| `Recover.checkWritingAllowed()` | `org/h2/tools/Recover.java:865` |
| `Recover.execute()` | `org/h2/tools/Recover.java:239` |
| `Recover.getCompareMode()` | `org/h2/tools/Recover.java:918` |
| `Server.createPgServer()` | `org/h2/tools/Server.java:539` |
| `Server.createTcpServer()` | `org/h2/tools/Server.java:511` |
| `Server.createWebServer()` | `org/h2/tools/Server.java:466` |
| `Server.getPort()` | `org/h2/tools/Server.java:640` |
| `DirectRecover.close()` | `org/h2/tools/DirectRecover.java:462` |
| `DirectRecover.execute()` | `org/h2/tools/DirectRecover.java:759` |
| `DirectRecover.finish()` | `org/h2/tools/DirectRecover.java:178` |
| `DirectRecover.getAvailableCompressionTypes()` | `org/h2/tools/DirectRecover.java:723` |

## 14.4 阅读路径

读 `org.h2.tools` 的 23 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.tools` 的 package-info 与 `SimpleResultSet`，建立第14章的职责边界。
2. 再读 `SimpleResultSet` 的 228 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.tools`（本章最小包，10,868 行）的实现，关注容量与失败路径。

跨章衔接请对照第13章《二次开发指南》。

## 14.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.tools` | `org.h2.util`, `org.h2.engine`, `org.h2.value`, `org.h2.message` |

## 14.6 设计权衡

- `org.h2.tools` 用 23 个文件换到 10,868 行实现，平均每文件 472 行，其中 `SimpleResultSet` 独占 2,480 行、228 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.tools`（10,868 行）与 `org.h2.tools` 的职责差是本章最值得记的一条边界。

## 14.7 常见误区

- 把 `org.h2.tools` 的 10,868 行当作复杂度上限：`SimpleResultSet` 之外的 22 个文件多为类型族与样板。
- 只看 `SimpleResultSet` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.tools` 与 `org.h2.tools` 视为可互换：前者 23 文件、后者 23 文件，扩展点分布完全不同。

## 14.8 深读要点

规模信号：`org.h2.tools` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.tools` 依赖 8 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`SimpleResultSet` 的公开方法 228 个，读它等于读本章的主干。

## 14.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。

## 14.9 知识点清单

1. `org.h2.tools` 的 `SimpleResultSet`：2,480 行、228 个公开方法，职责按方法名归纳
2. `org.h2.tools` 的 `Csv`：986 行、33 个公开方法，职责按方法名归纳

## 14.9 本章小结

- 本章覆盖 1 个包、10,868 行。
- 关键入口与源码坐标见 §14.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 14.10 延伸思考

**1. 🟢★ 指出 `org.h2.tools` 中 `SimpleResultSet` 与 `Csv` 的分工差异，并给出调用方向。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**2. 🔵★★ 围绕 `org.h2.tools` 的 `SimpleResultSet`，说明它为什么需要独立成类型而不是并入 `Csv`。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**3. 🟠★★★ 以 `org.h2.tools` 的 `SimpleResultSet` 为入口，画出一次完整调用经过的包。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.tools` 的一个类型，你保留 `SimpleResultSet` 还是 `Csv`？说明代价。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

## 14.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.tools`：23 个文件、10,868 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.tools`（10,868 行）：两者的扩展与兼容策略不同，差异落在 `SimpleResultSet` 的 228 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 14.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.tools` | `org.h2.util` | 53 |
| `org.h2.tools` | `org.h2.engine` | 14 |
| `org.h2.tools` | `org.h2.value` | 14 |

## 14.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.tools` 与 `org.h2.tools` 之间的调用方向？
- `SimpleResultSet` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.tools` 的调用链讲到落盘或返回？
- `org.h2.tools` 与 `org.h2.tools` 若合并，会丢掉哪个扩展点？
- `org.h2.tools` 的注释与实现若不一致，你信哪一边，为什么？

## 14.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.tools` | 第13章《二次开发指南》 |

## 14.12 延展阅读

- 详见第13章《二次开发指南》。
